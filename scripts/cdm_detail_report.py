"""Engine sinh BẢN TÍNH CHI TIẾT CDM per hố khoan — theo mẫu điển hình.

Mẫu định dạng: data/cdm_report_template_dienhinh.json (5 phần):
  1. Thông số tính toán (hình học + nền đắp + địa chất)
  2. Lún khối gia cố S1 (C.2 TCVN 9403:2012)
  3. Lún cố kết dưới mũi S2 (TCCS 41:2022 §9.1) — per-layer
  4. Lún theo thời gian (TCCS 41 §9.3) — Uv(t), ΔS còn lại
  5. Sức chịu tải cọc CDM + (kiểm đệm ALiCC)

Trả về 1 dict cho MỖI HK → UI (Streamlit) và Word builder dùng CHUNG (Rule 6 parity).

API:
  build_hk_detail(bh_name, delta_S_cm=30.0, db_path=None) -> dict
  build_6zone_detail(delta_S_cm=30.0, db_path=None) -> list[dict]   # gom theo 6 vùng

Chạy demo:  python scripts/cdm_detail_report.py KE-HK10
"""
from __future__ import annotations

import math
import sqlite3
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
_DB_DEFAULT = _ROOT / "data" / "TTHC.sqlite"

# Engine tái dùng (import mềm để demo không vỡ nếu thiếu)
from cdm_length_optimize import find_cdm_length, area_ratio  # noqa: E402
from settlement_calc import (  # noqa: E402
    calc_s2_below_cdm, bjerrum_mu, get_Ip_avg_for_bh,
    get_allowable_residual_settlement,
)
from cdm_column_calc import (  # noqa: E402
    calc_settlement_S1, calc_cdm_pile_capacity,
)

SOFT_SYMBOLS = ("1", "1b", "2", "XMD")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers DB
# ─────────────────────────────────────────────────────────────────────────────
def _con(db_path: Optional[Path]) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path or _DB_DEFAULT))
    con.row_factory = sqlite3.Row
    return con


def _read_config(con: sqlite3.Connection) -> dict:
    r = con.execute("SELECT * FROM tvtk_cdm_config WHERE id=1").fetchone()
    return dict(r) if r else {}


def _read_fill(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute(
        "SELECT name, h_m, gamma_kNm3, q_component_kPa FROM tvtk_fill_composition "
        "ORDER BY layer_order"
    ).fetchall()
    return [dict(r) for r in rows]


def _bh_meta(con: sqlite3.Connection, bh: str) -> dict:
    r = con.execute(
        "SELECT name, elevation_m, x_coord_m, y_coord_m FROM boreholes WHERE name=?",
        (bh,),
    ).fetchone()
    return dict(r) if r else {}


def _layers(con: sqlite3.Connection, bh: str) -> list[dict]:
    rows = con.execute("""
        SELECT l.symbol, l.description, l.depth_top_m, l.depth_bot_m,
               ROUND(AVG(lt.gamma_kNm3),2) AS gamma,
               ROUND(AVG(lt.e0),3)         AS e0,
               ROUND(AVG(lt.Cc),4)         AS Cc,
               ROUND(AVG(lt.Cs),4)         AS Cs,
               ROUND(AVG(lt.PC_kPa),1)     AS PC
        FROM layers l JOIN boreholes b ON l.borehole_id=b.id
        LEFT JOIN lab_tests lt ON lt.borehole_id=b.id
             AND lt.depth_from_m >= l.depth_top_m AND lt.depth_from_m < l.depth_bot_m
        WHERE b.name=? GROUP BY l.id ORDER BY l.depth_top_m
    """, (bh,)).fetchall()
    return [dict(r) for r in rows]


def _design_row(con: sqlite3.Connection, bh: str, dS: float) -> Optional[dict]:
    """Kết quả thiết kế đã tính sẵn (cdm_zone_design_results) — chuẩn headline."""
    r = con.execute(
        "SELECT zone_code, Lc_m, tip_depth_m, p_optimal_m, S1_cm, S2_cm, "
        "S_total_cm, H_soft_m, penetrates_full, force_full, ok, cdm_top_elev_m "
        "FROM cdm_zone_design_results "
        "WHERE bh_name=? AND delta_S_cm=? AND zone_code LIKE 'KE%' LIMIT 1",
        (bh, float(dS)),
    ).fetchone()
    return dict(r) if r else None


def _cu_band(con: sqlite3.Connection, bh: str, d_top: float, d_bot: float) -> Optional[float]:
    """Su VST trung bình trong dải độ sâu; fallback lab Cu_UU; None nếu không có."""
    r = con.execute("""
        SELECT AVG(v.Su_kPa) FROM vane_shear_tests v
        JOIN vst_locations loc ON v.vst_loc_id = loc.id
        WHERE loc.name=? AND v.depth_m >= ? AND v.depth_m < ?
    """, (bh, d_top, d_bot)).fetchone()
    if r and r[0]:
        return round(float(r[0]), 1)
    r2 = con.execute("""
        SELECT AVG(lt.Cu_UU_kPa) FROM lab_tests lt JOIN boreholes b ON lt.borehole_id=b.id
        WHERE b.name=? AND lt.Cu_UU_kPa>0 AND lt.depth_from_m>=? AND lt.depth_from_m<?
    """, (bh, d_top, d_bot)).fetchone()
    if r2 and r2[0]:
        return round(float(r2[0]), 1)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Engine chính
# ─────────────────────────────────────────────────────────────────────────────
def build_hk_detail(bh_name: str, delta_S_cm: float = 30.0,
                    db_path: Optional[Path] = None) -> dict:
    """Sinh dict bản tính chi tiết CDM cho 1 hố khoan."""
    db_path = db_path or _DB_DEFAULT
    con = _con(db_path)
    warns: list[str] = []
    try:
        cfg = _read_config(con)
        fill = _read_fill(con)
        meta = _bh_meta(con, bh_name)
        if not meta:
            return {"bh_name": bh_name, "ok": False,
                    "error": "Không có hố khoan trong CSDL"}

        # ── Hình học + tải ───────────────────────────────────────────────────
        D = float(cfg.get("D_mm", 800.0)) / 1000.0
        S = float(cfg.get("spacing_m", 1.8))
        pattern = cfg.get("pattern", "square")
        qu = float(cfg.get("qu_kPa", 800.0))
        Ec_factor = float(cfg.get("Ec_factor", 100.0))
        q_static = float(cfg.get("q_kPa", 40.8))          # tải lún (đắp tĩnh)
        q_settle = float(cfg.get("q_settlement_kPa", q_static))
        CDTK = float(cfg.get("settlement_design_elev_m", 2.7))
        CD1 = float(cfg.get("top_elev_m", 0.8))           # đỉnh trụ
        gwl_elev = float(cfg.get("gwl_elev_m", 0.0))
        CDTN = float(meta.get("elevation_m") or 0.0)      # tự nhiên
        a = area_ratio(D, S, pattern)
        Ac = math.pi * (D / 2.0) ** 2
        A_unit = S * S if pattern in ("square", "vuong") else (math.sqrt(3) / 2.0) * S * S
        Ec = Ec_factor * qu / 2.0                          # Ec = k·Cc, Cc=qu/2
        sum_h_fill = sum(f["h_m"] for f in fill)
        Hse = next((f["h_m"] for f in fill if "se" in f["name"].lower()
                    or "đệm" in f["name"].lower()), 0.4)
        CDld = round(CD1 + Hse, 2)                         # đỉnh lớp đệm

        # μ Bjerrum theo Ip lớp yếu
        ip = get_Ip_avg_for_bh(bh_name, db_path=db_path)
        mu = bjerrum_mu(ip) if ip else 1.0
        Su_top = _cu_band(con, bh_name, 0.0, 25.0) or 12.0
        gwt_depth = max(0.0, CDTN - gwl_elev)

        # ── Headline: ưu tiên kết quả đã tính sẵn cdm_zone_design_results ────
        drow = _design_row(con, bh_name, delta_S_cm)
        fcl = None
        clay_top = None
        if drow and drow.get("tip_depth_m") is not None:
            tip_depth = float(drow["tip_depth_m"])
            clay_top = max(0.0, tip_depth - (float(drow.get("p_optimal_m") or 0.0))) \
                if drow.get("p_optimal_m") else None
            H_soft = float(drow.get("H_soft_m") or 0.0)
            Lc = float(drow.get("Lc_m") or round(tip_depth - (CDTN - CD1), 2))
            S1_head = float(drow.get("S1_cm") or 0.0)
            S2_head = float(drow.get("S2_cm") or 0.0)
            S_total_head = float(drow.get("S_total_cm") or (S1_head + S2_head))
            force_full = bool(drow.get("force_full"))
            ok_head = bool(drow.get("ok"))
            if force_full:
                warns.append("Vùng kè — cọc xuyên hết bùn (force full penetration)")
        else:
            # Fallback: tự tối ưu khi không có sẵn trong CSDL
            fcl = find_cdm_length(
                bh_name=bh_name, q_kPa=q_static, a=a, Ec_kPa=Ec, Su_kPa=Su_top,
                target_dS_cm=delta_S_cm, mu=mu, db_path=db_path, gwl_elev_m=gwl_elev,
            )
            if not fcl or fcl.get("clay_top_m") is None:
                return {"bh_name": bh_name, "ok": False,
                        "error": "Thiếu dữ liệu lớp đất yếu (H_soft) — không tính được"}
            p_opt = fcl.get("p_optimal_m") or fcl.get("p_max_m") or 0.0
            tip_depth = float(fcl.get("tip_depth_m") or 0.0)
            H_soft = float(fcl.get("H_soft_symbol_m") or 0.0)
            Lc = round(tip_depth - (CDTN - CD1), 2)
            S1_head = float(fcl.get("S1_cm") or 0.0)
            S2_head = float(fcl.get("S2_cm") or 0.0)
            S_total_head = S1_head + S2_head
            force_full = False
            ok_head = bool(fcl.get("ok"))
            if not fcl.get("p_optimal_m"):
                warns.append(fcl.get("note") or "Không đạt ΔS trong phạm vi cho phép")

        # clay_top cho per-layer: lấy từ profile nếu chưa có
        if not clay_top:
            try:
                from cdm_length_optimize import soft_profile_from_db
                _ct, _ = soft_profile_from_db(bh_name, db_path)
                clay_top = float(_ct) if _ct is not None else 0.0
            except Exception:
                clay_top = 0.0
        CD2 = round(CDTN - tip_depth, 2)
        cu_used = round(mu * Su_top, 1)
        Es = 250.0 * cu_used
        Eeq = a * Ec + (1 - a) * Es

        # ── Phần 2.2 — S1 khối gia cố (per-layer trong vùng gia cố) ──────────
        S1_total = S1_head if S1_head else calc_settlement_S1(
            q_static, max(0.1, tip_depth - clay_top), a, Ec, Es)
        s1_layers = []
        z = clay_top
        _s1_sum = 0.0
        while z < tip_depth - 1e-6:
            h_i = min(1.0, tip_depth - z)
            cu_i = _cu_band(con, bh_name, z, z + h_i) or Su_top
            cu_i_corr = cu_i * mu
            Esoil_i = 250.0 * cu_i_corr
            Eeq_i = a * Ec + (1 - a) * Esoil_i
            Si = q_static * h_i / Eeq_i * 100.0           # cm
            _s1_sum += Si
            s1_layers.append({
                "depth_top_m": round(z, 2), "depth_bot_m": round(z + h_i, 2),
                "h_m": round(h_i, 2), "Cu_kPa": cu_i, "Cu_corr_kPa": round(cu_i_corr, 1),
                "Esoil_kPa": round(Esoil_i, 0), "Eeq_kPa": round(Eeq_i, 0),
                "Si_cm": round(Si, 3),
            })
            z += h_i
        S1_layered = round(_s1_sum, 2)

        # ── Phần 2.3 + III — S2 cố kết per-layer + lún theo thời gian ────────
        s2 = calc_s2_below_cdm(
            bh_name=bh_name, cdm_tip_depth_m=tip_depth, q_kPa=q_static,
            gwt_depth_m=gwt_depth, double_drainage=False, db_path=db_path,
        )
        S2_total = float(s2.get("S2_cm") or 0.0)
        # S2 residual: ưu tiên giá trị thiết kế đã chốt (headline), nếu không dùng tính lại
        S2_resid = S2_head if S2_head else float(s2.get("S2_15yr_cm") or S2_total)
        s2_layers = s2.get("layers", [])
        for w in s2.get("warnings", []) or []:
            warns.append(w)

        # Lún theo thời gian: quét t (năm) → S(t)=S1+S2·Uv(t)
        t_years = [1, 2, 5, 10, 15, 20, 25, 30, 40, 50]
        # Uv(t) suy từ tỉ lệ S2_resid/S2_total tại 15 năm → scale theo Terzaghi
        time_curve = []
        for t in t_years:
            s2t = calc_s2_below_cdm(
                bh_name=bh_name, cdm_tip_depth_m=tip_depth, q_kPa=q_static,
                gwt_depth_m=gwt_depth, double_drainage=False,
                t_years_residual=float(t), db_path=db_path,
            )
            s2_t = float(s2t.get("S2_15yr_cm") or 0.0)
            uv = (s2_t / S2_total) if S2_total > 1e-9 else 1.0
            time_curve.append({
                "t_years": t, "Uv_pct": round(uv * 100, 1),
                "S2_t_cm": round(s2_t, 2),
                "S_total_t_cm": round(S1_total + s2_t, 2),
            })

        # ── ΔS cho phép + verdict ────────────────────────────────────────────
        dS_allow = delta_S_cm
        try:
            _r = get_allowable_residual_settlement(
                cfg.get("road_class_code", "cat1"),
                cfg.get("position_code", "general"), db_path=db_path)
            dS_allow = float(_r.get("delta_S_cm_max", delta_S_cm))
        except Exception:
            pass
        S_design = round(S_total_head if S_total_head else (S1_total + S2_resid), 2)
        ok_settle = ok_head if drow else (S_design <= dS_allow)

        # ── Phần 4 — Sức chịu tải cọc ────────────────────────────────────────
        cap = calc_cdm_pile_capacity(D, Lc, cu_used, qu, FS=2.5)
        N_applied = q_settle * A_unit                      # tải 1 cọc (có thể gồm hoạt tải)
        N_design = float(cap.get("Q_ult_min_kN") or 0.0)
        Q_allow = cap.get("Q_allow_kN")
        ok_bearing = (N_applied <= (Q_allow or N_design)) if (Q_allow or N_design) else None

        # ── Phần 5 — Kiểm đệm ALiCC (chọc thủng) ─────────────────────────────
        cushion = None
        try:
            from cdm_cushion_params import check_alicc
            cushion = check_alicc(Hse=Hse, D=D, s=S)
        except Exception as e:
            warns.append(f"Không kiểm được đệm: {e}")

        return {
            "bh_name": bh_name, "ok": True, "delta_S_cm": delta_S_cm,
            "warnings": warns,
            "geometry": {
                "W_m": 12.0, "D_m": D, "S_m": S, "pattern": pattern,
                "Ac_m2": round(Ac, 3), "A_unit_m2": round(A_unit, 3),
                "a": round(a, 4), "a_pct": round(a * 100, 2),
                "CDTK_m": CDTK, "CDld_m": CDld, "CDTN_m": CDTN, "CDNN_m": gwl_elev,
                "CD1_m": CD1, "CD2_m": CD2, "L_m": Lc, "tip_depth_m": round(tip_depth, 2),
                "clay_top_m": round(clay_top, 2), "H_soft_m": round(H_soft, 2),
                "sum_h_fill_m": round(sum_h_fill, 2), "Hse_m": Hse,
            },
            "material": {
                "qu_kPa": qu, "Ec_factor": Ec_factor, "Ec_kPa": round(Ec, 0),
                "Es_kPa": round(Es, 0), "Eeq_kPa": round(Eeq, 0),
                "mu": round(mu, 3), "Ip": ip, "cu_used_kPa": round(cu_used, 1),
                "Cp_kPa": round(qu / 2.0, 1),
            },
            "loads": {"q_static_kPa": q_static, "q_settle_kPa": q_settle,
                      "fill": fill},
            "soil_layers": _layers(con, bh_name),
            "S1": {"S1_cm": round(S1_total, 2), "S1_layered_cm": S1_layered,
                   "layers": s1_layers},
            "S2": {"S2_cm": round(S2_total, 2), "S2_residual_cm": round(S2_resid, 2),
                   "stop_depth_m": s2.get("stop_depth_m"),
                   "n_layers": s2.get("n_layers"), "layers": s2_layers},
            "time": {"curve": time_curve, "S15_cm": round(S2_resid, 2),
                     "S_design_cm": S_design, "dS_allow_cm": dS_allow,
                     "ok": ok_settle},
            "bearing": {**cap, "N_applied_kN": round(N_applied, 2),
                        "ok": ok_bearing},
            "cushion": cushion,
        }
    finally:
        con.close()


def build_6zone_detail(delta_S_cm: float = 30.0,
                       db_path: Optional[Path] = None) -> list[dict]:
    """Gom bản tính chi tiết theo 6 vùng CDM Bờ kè KE."""
    db_path = db_path or _DB_DEFAULT
    con = _con(db_path)
    try:
        zrows = con.execute(
            "SELECT zone_no, zone_name, total_length_m FROM ke_cdm_zones ORDER BY zone_no"
        ).fetchall()
        zones = []
        for zr in zrows:
            mrows = con.execute(
                "SELECT bh_name, seq, position, elevation_m FROM ke_cdm_zone_boreholes "
                "WHERE zone_no=? ORDER BY seq", (zr["zone_no"],)
            ).fetchall()
            zones.append({"zone_no": zr["zone_no"], "zone_name": zr["zone_name"],
                          "total_length_m": zr["total_length_m"],
                          "members": [dict(m) for m in mrows]})
    finally:
        con.close()

    # Tính detail 1 lần / HK (cache cục bộ tránh trùng HK biên)
    cache: dict = {}
    for z in zones:
        z["details"] = []
        for m in z["members"]:
            bn = m["bh_name"]
            if bn not in cache:
                try:
                    cache[bn] = build_hk_detail(bn, delta_S_cm, db_path)
                except Exception as e:
                    cache[bn] = {"bh_name": bn, "ok": False, "error": str(e)}
            z["details"].append(cache[bn])
    return zones


if __name__ == "__main__":
    bh = sys.argv[1] if len(sys.argv) > 1 else "KE-HK10"
    d = build_hk_detail(bh)
    if not d.get("ok"):
        print(f"{bh}: {d.get('error')}")
    else:
        g = d["geometry"]; m = d["material"]; t = d["time"]; b = d["bearing"]
        print(f"=== {bh} (ΔS={d['delta_S_cm']}cm) ===")
        print(f"Hình học: D={g['D_m']} S={g['S_m']} a={g['a_pct']}% "
              f"CD1={g['CD1_m']} CD2={g['CD2_m']} L={g['L_m']} tip={g['tip_depth_m']}")
        print(f"Vật liệu: Ec={m['Ec_kPa']:.0f} Es={m['Es_kPa']:.0f} "
              f"Eeq={m['Eeq_kPa']:.0f} mu={m['mu']} cu={m['cu_used_kPa']}")
        print(f"S1={d['S1']['S1_cm']}cm (per-layer Σ={d['S1']['S1_layered_cm']}cm, "
              f"{len(d['S1']['layers'])} lớp)")
        print(f"S2={d['S2']['S2_cm']}cm  S2_residual(15y)={d['S2']['S2_residual_cm']}cm "
              f"({d['S2']['n_layers']} phân tố, dừng z={d['S2']['stop_depth_m']}m)")
        print(f"S_design=S1+S2res={t['S_design_cm']}cm  [S]={t['dS_allow_cm']}cm  "
              f"-> {'Đạt' if t['ok'] else 'KHÔNG đạt'}")
        print(f"SCT: N_applied={b['N_applied_kN']}kN  [N]={b.get('Q_ult_min_kN'):.1f}kN "
              f"Q_allow={b.get('Q_allow_kN')}  -> {'Đạt' if b['ok'] else 'KĐ' if b['ok'] is not None else '?'}")
        if d.get("cushion"):
            c = d["cushion"]
            print(f"Đệm ALiCC: τ_se={c['tau_se_kPa']:.1f} τ_ase={c['tau_ase_kPa']:.1f} "
                  f"ratio={c['ratio']:.2f} -> {'Đạt' if c['ok'] else 'KĐ'}")
        if d["warnings"]:
            print("Cảnh báo:", "; ".join(d["warnings"][:3]))
