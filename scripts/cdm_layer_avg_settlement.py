# -*- coding: utf-8 -*-
"""Tính lún dùng CHỈ TIÊU CƠ LÝ TRUNG BÌNH theo lớp (thống nhất cho mọi hố khoan).

Thay vì mỗi hố khoan dùng số liệu lab riêng (rời rạc, hay thiếu), engine này gán cho
mỗi lớp đất của mọi hố khoan bộ chỉ tiêu TRUNG BÌNH của lớp đó (theo vùng) — từ
`soil_param_stats.representative_params()`. Bảo đảm tính toán nhất quán, tái lập được.

Phương pháp (đồng bộ §71):
  - Chia phân tố 2 m từ mặt đất tự nhiên tới đáy vùng ảnh hưởng (Δσ/σ'v0 < 10%),
    mở rộng dưới đáy hố khoan bằng lớp cuối.
  - σ'v0: tích phân γ_tb của lớp (dưới MNN dùng γ' = γ − 9,81).
  - Δσ: 1D (q không đổi) hoặc Boussinesq dải (B_load_m).
  - Lớp SÉT → Terzaghi 1D (OC/NC/cross-PC) với Cc/Cs/e0/PC trung bình.
  - Lớp CÁT → đàn hồi: Si = Δσ·h/Es (Es từ E_kPa trung bình, mặc định 8000 kPa).

Lưu: SQLite cdm_avg_layer_settlement (LOCAL+PROJECT) + JSON.
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB = _ROOT / "data" / "TTHC.sqlite"
_DBS = [Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite"), _DEFAULT_DB]


def _primary_db() -> Path:
    """DB cục bộ (ngoài Google Drive) nếu có — tránh đọc file đang đồng bộ (kết quả
    nhảy giữa các lần tính). Fallback DB dự án."""
    for d in _DBS:
        if d.exists():
            return d
    return _DEFAULT_DB

GAMMA_W = 9.81
SAND_SYMBOLS = {"F", "2a", "2b", "2c", "3a", "3b", "3c", "4", "5", "5a", "5b", "6", "7", "8"}
ES_SAND_DEFAULT = 8000.0    # kPa khi lớp cát không có E trung bình
GAMMA_DEFAULT = 16.0


def _zone_of(bh: str) -> str:
    for z in ("KE", "BXN", "NHC"):
        if bh.startswith(z + "-"):
            return z
    if bh.startswith("ND-"):
        return "QTT"
    return "?"


def _dsigma(q: float, z_below: float, B_load_m: Optional[float]) -> float:
    """Δσ tại độ sâu z_below dưới mặt gia tải."""
    if not B_load_m or B_load_m <= 0:
        return q
    if z_below <= 0:
        return q
    alpha = 2.0 * math.atan(B_load_m / (2.0 * z_below))
    return q / math.pi * (alpha + math.sin(alpha))


def settle_avg(
    bh_name: str,
    H_fill_m: float,
    gamma_fill: float = 18.0,
    gwt_depth_m: float = 0.0,
    B_load_m: Optional[float] = None,
    sublayer_m: float = 2.0,
    stop_ratio: float = 0.10,
    rep: Optional[dict] = None,
    bcl_params: Optional[dict] = None,
    db_path: Optional[Path] = None,
    nc_soft_clay: bool = True,
) -> dict:
    """Lún nền chưa xử lý của 1 hố khoan dùng chỉ tiêu trung bình theo lớp.

    bcl_params: dict {symbol: {gamma_kNm3,e0,Cc,Cs,PC_kPa,E_kPa,soil_type,...}} —
    nếu cung cấp (bộ BCL) sẽ ưu tiên dùng thay cho trung bình lab.
    """
    from soil_param_stats import representative_params

    db = Path(db_path) if db_path else _primary_db()
    rep = rep if rep is not None else (representative_params(db) if bcl_params is None else {})
    zone = _zone_of(bh_name)

    con = sqlite3.connect(str(db))
    layers = con.execute(
        "SELECT l.symbol, l.depth_top_m, l.depth_bot_m FROM layers l "
        "JOIN boreholes b ON l.borehole_id=b.id WHERE b.name=? AND l.symbol IS NOT NULL "
        "ORDER BY l.depth_top_m", (bh_name,)).fetchall()
    con.close()
    if not layers:
        return {"bh": bh_name, "S_total_cm": 0.0, "layers": [], "stop_depth_m": 0.0,
                "warning": "Không có địa tầng"}

    # override XMD -> bùn 1 (KE-HK8)
    layers = [("1" if (bh_name == "KE-HK8" and s == "XMD") else s, t, b) for s, t, b in layers]
    max_depth = max(b for _, b, _ in [(s, b2, t) for s, t, b2 in layers])  # đáy HK
    last_sym = layers[-1][0]

    def _sym_at(z):
        for s, t, b in layers:
            if t <= z <= b:
                return s
        return last_sym   # mở rộng dưới đáy HK bằng lớp cuối

    def _params(sym):
        if bcl_params and sym in bcl_params:
            return bcl_params[sym]
        return rep.get((zone, sym)) or rep.get(("KE", sym)) or {}

    q = gamma_fill * H_fill_m
    EXTEND = 200.0
    z = 0.0
    cum_sigma = 0.0      # σ'v0 tích luỹ tới đỉnh phân tố
    z_below = 0.0
    S_total = 0.0
    out_layers = []
    warnings = []
    stop_reason = "max_extend"
    while z < max_depth + EXTEND:
        z_mid = z + sublayer_m / 2.0
        sym = _sym_at(z_mid)
        p = _params(sym)
        gamma = p.get("gamma_kNm3") or GAMMA_DEFAULT
        g_eff = gamma - GAMMA_W if z_mid > gwt_depth_m else gamma
        sigma_v0 = cum_sigma + g_eff * sublayer_m / 2.0
        cum_sigma += g_eff * sublayer_m

        dsig = _dsigma(q, z_mid, B_load_m)
        if sigma_v0 > 0 and dsig / sigma_v0 < stop_ratio:
            stop_reason = f"Δσ/σ'v0<{stop_ratio:.0%} tại z={z:.1f}m"
            break

        # Tiêu chí phân loại công thức tính lún (theo loại đất + hệ số rỗng e0):
        #   - Lớp CÁT (hạt rời, không có e0/Cc)         → đàn hồi: Si = Δσ·h/Es
        #   - Lớp SÉT YẾU  e0 ≥ 1, có Cc                 → nén cố kết Terzaghi (e-logp): OC/NC/cross-PC
        #   - Lớp SÉT CHẶT e0 < 1 (hoặc thiếu Cc)        → mô đun biến dạng Eoed: Si = Δσ·h/Eoed
        is_sand = sym in SAND_SYMBOLS
        Cc = p.get("Cc"); e0 = p.get("e0"); PC = p.get("PC_kPa")
        Cs = p.get("Cs") or (Cc * 0.15 if Cc else None)
        a12 = p.get("a12_cm2kgf"); E_lab = p.get("E_kPa")
        Si = 0.0
        method = "-"

        if (e0 is not None) and (e0 >= 1.0) and Cc:
            # SÉT YẾU (e0 ≥ 1 = bùn trạng thái chảy) → nén cố kết Terzaghi 1D.
            # nc_soft_clay=True: coi là CỐ KẾT THƯỜNG (Pc=σ'v0) → dùng Cc toàn bộ, tránh
            # OC giả tạo ở lớp nông do Pc thí nghiệm (một giá trị) áp cho cả lớp bùn dày.
            PC_use = sigma_v0 if nc_soft_clay else (PC or sigma_v0)
            sig_f = sigma_v0 + dsig
            fac = sublayer_m / (1.0 + e0)
            if sigma_v0 >= PC_use:        # NC
                Si = fac * Cc * math.log10(sig_f / sigma_v0)
                method = "sét cố kết-NC bùn chảy (e≥1)" if nc_soft_clay else "sét cố kết-NC (e≥1)"
            elif sig_f > PC_use:          # cross-PC
                Si = fac * (Cs or 0) * math.log10(PC_use / sigma_v0) + fac * Cc * math.log10(sig_f / PC_use)
                method = "sét cố kết-cross (e≥1)"
            else:                          # OC
                Si = fac * (Cs or 0) * math.log10(sig_f / sigma_v0); method = "sét cố kết-OC (e≥1)"
        elif (e0 is not None) and (e0 < 1.0):
            # e0 < 1 → mô đun biến dạng: Eoed = (1+e0)/a12 × 98,0665 (fallback E_kPa = α·N)
            Eoed = ((1.0 + e0) / a12 * 98.0665) if a12 else (E_lab or 0)
            if Eoed > 0:
                Si = dsig * sublayer_m / Eoed
                method = "cát đàn hồi (Es)" if p.get("soil_type") == "Sand" else "sét Eoed (e<1)"
            else:
                warnings.append(f"Lớp {sym} (e<1): thiếu a12/E")
        else:
            # CÁT / lớp hạt rời (không có e0) → đàn hồi Es
            Es = E_lab or ES_SAND_DEFAULT
            Si = dsig * sublayer_m / Es; method = "cát đàn hồi (Es)"
        S_total += Si
        out_layers.append({
            "z_mid_m": round(z_mid, 1), "symbol": sym, "is_sand": is_sand,
            "gamma": round(gamma, 2), "gamma_eff": round(g_eff, 2),
            "below_gwt": z_mid > gwt_depth_m,
            "e0": round(e0, 3) if e0 is not None else None,
            "Cc": round(Cc, 3) if Cc is not None else None,
            "Cs": round(Cs, 4) if Cs is not None else None,
            "PC_kPa": round(PC, 1) if PC is not None else None,
            "Cv_cm2s": p.get("Cv_cm2s"),
            "is_consol": method.startswith("sét cố kết"),
            "sigma_v0_kPa": round(sigma_v0, 1),
            "dsigma_kPa": round(dsig, 1), "Si_cm": round(Si * 100, 2), "method": method,
        })
        z_below += sublayer_m
        z += sublayer_m

    return {
        "bh": bh_name, "zone": zone, "q_kPa": round(q, 1),
        "S_total_cm": round(S_total * 100, 1), "stop_depth_m": round(z, 1),
        "stop_reason": stop_reason, "n_layers": len(out_layers),
        "layers": out_layers, "warnings": warnings,
    }


_YEAR_SEC = 12 * 30 * 24 * 60 * 60   # 31_104_000 s (quy ước 360 ngày)


def _U_terzaghi(Tv: float) -> float:
    """Độ cố kết trung bình U(Tv) — lý thuyết Terzaghi (cố kết 1D)."""
    if Tv <= 0:
        return 0.0
    if Tv < 0.2827:                      # U < 0.6
        U = math.sqrt(4.0 * Tv / math.pi)
    else:
        U = 1.0 - (8.0 / math.pi ** 2) * math.exp(-math.pi ** 2 * Tv / 4.0)
    return min(U, 0.999)


def time_history(res: dict, t_years: list[float], double_drainage: bool = True,
                 m_coef: float = 1.0) -> dict:
    """Lún theo thời gian từ kết quả settle_avg.

    Tách: S_tức thời (cát + sét chặt) + S_cố kết (sét yếu phát triển theo U(t)).
    Cv tương đương: Ctbv = (H·100)² / (Σ h·100/√Cv)²  (chỉ phân tố sét cố kết).
    H thoát nước = H_sét cố kết /2 (thoát 2 mặt) hoặc /1 (thoát 1 mặt).

    m_coef (TCCS 41:2022 Điều 9.2.1 SĐ1): hệ số kinh nghiệm 1,1–1,4.
      Tổng lún S = m·Sc (CT 30a); lún tức thời lớp bùn S_i = (m−1)·Sc (CT 30b),
      do đất yếu đẩy trồi ngang dưới tải đắp. m=1,0 → bỏ qua (mặc định, tương thích cũ).
    St(t) = S_tức thời + U(Tv)·S_cố kết ;  Tv = Ctbv·t/(H·100)².
    """
    consol = [L for L in res["layers"] if L.get("is_consol") and L.get("Cv_cm2s")]
    S_consol = round(sum(L["Si_cm"] for L in consol), 2)
    S_imm_elastic = round(res["S_total_cm"] - S_consol, 2)   # tức thời cát + sét chặt
    Si_mud = round((m_coef - 1.0) * S_consol, 2)             # tức thời lớp bùn (CT 30b)
    S_imm = round(S_imm_elastic + Si_mud, 2)                 # tổng lún tức thời
    S_inf = round(S_imm + S_consol, 2)                       # = S_imm_elastic + m·Sc

    H_clay = round(len(consol) * 2.0, 2)   # bề dày sét cố kết (phân tố 2m)
    sum_term = sum(2.0 * 100.0 / math.sqrt(L["Cv_cm2s"]) for L in consol) if consol else 0.0
    Ctbv = (((H_clay * 100.0) ** 2) / sum_term ** 2) if sum_term else 0.0
    H_drain = (H_clay / 2.0 if double_drainage else H_clay)

    out_t, out_Tv, out_U, out_St, out_res = [], [], [], [], []
    for t in t_years:
        if H_drain > 0 and Ctbv > 0:
            Tv = Ctbv * t * _YEAR_SEC / ((H_drain * 100.0) ** 2)
        else:
            Tv = 99.0
        U = _U_terzaghi(Tv)
        St = round(S_imm + U * S_consol, 2)
        out_t.append(t); out_Tv.append(round(Tv, 4)); out_U.append(round(U * 100, 1))
        out_St.append(St); out_res.append(round(S_inf - St, 2))
    return {
        "S_inf_cm": S_inf, "S_immediate_cm": S_imm, "S_consol_cm": S_consol,
        "S_imm_elastic_cm": S_imm_elastic, "Si_mud_cm": Si_mud, "m_coef": m_coef,
        "Ctbv_cm2s": Ctbv, "H_clay_m": H_clay, "H_drain_m": round(H_drain, 2),
        "double_drainage": double_drainage,
        "years": out_t, "Tv": out_Tv, "U_pct": out_U, "St_cm": out_St, "residual_cm": out_res,
    }


def create_table(con: sqlite3.Connection) -> None:
    con.execute(
        "CREATE TABLE IF NOT EXISTS cdm_avg_layer_settlement ("
        "zone TEXT, bh_name TEXT, H_fill_m REAL, gamma_fill REAL, q_kPa REAL, "
        "gwt_depth_m REAL, S_total_cm REAL, stop_depth_m REAL, n_layers INTEGER, "
        "method TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (zone, bh_name))")
    con.commit()


def save_results(rows: list[dict], gamma_fill: float, method: str = "avg_layer") -> None:
    for db in _DBS:
        if not db.parent.exists():
            continue
        con = sqlite3.connect(str(db))
        try:
            create_table(con)
            for r in rows:
                con.execute(
                    "INSERT OR REPLACE INTO cdm_avg_layer_settlement "
                    "(zone,bh_name,H_fill_m,gamma_fill,q_kPa,gwt_depth_m,S_total_cm,"
                    "stop_depth_m,n_layers,method,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                    (r.get("zone"), r["bh"], r.get("H_fill_m"), gamma_fill, r.get("q_kPa"),
                     r.get("gwt_depth_m"), r.get("S_total_cm"), r.get("stop_depth_m"),
                     r.get("n_layers"), method))
            con.commit()
        finally:
            con.close()


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    from cdm_no_treat_settlement import ZONE_FILL_CONFIG
    print("Lun chua xu ly dung CHI TIEU TRUNG BINH theo lop (6 vung BCL):")
    print(f"{'Vung':<11}{'HK':<9}{'Hdap':>6}{'q':>7}{'S_inf':>8}{'d_anhh':>7}")
    rows = []
    for c in ZONE_FILL_CONFIG:
        r = settle_avg(c["bh"], H_fill_m=c["H_fill_1"], gamma_fill=18.0,
                       gwt_depth_m=max(0.0, c["CDTN"] - 0.0))
        r["H_fill_m"] = c["H_fill_1"]; r["gwt_depth_m"] = max(0.0, c["CDTN"])
        rows.append(r)
        print(f"{c['zone']:<11}{c['bh']:<9}{c['H_fill_1']:>6.2f}{r['q_kPa']:>7.1f}"
              f"{r['S_total_cm']:>8.1f}{r['stop_depth_m']:>7.1f}")
    save_results(rows, 18.0)
    print("Da luu SQLite cdm_avg_layer_settlement.")
