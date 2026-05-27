# -*- coding: utf-8 -*-
"""Tối ưu chiều dài cọc CDM theo độ lún cho phép (TCCS 41).

Thiết kế ngược: cho trước độ lún cho phép ΔS (TCCS 41 Bảng 1), tìm chiều dài cọc
CDM (độ xuyên vào lớp bùn) NGẮN NHẤT sao cho tổng lún S1 + S2 ≤ ΔS.

- S1 = lún đàn hồi khối gia cố (TCVN 9403 Phụ lục C):
       S1 = q · H_gc / (a·Ec + (1-a)·Es) × 100   [cm]
  với H_gc = độ xuyên cọc vào lớp bùn (m) — phần bùn được gia cố.
- S2 = lún cố kết phần bùn CÒN LẠI bên dưới mũi cọc (settlement_calc.calc_s2_below_cdm).

Cọc "thả nổi": khi rút ngắn để S1+S2 tăng tới ΔS, mũi cọc nằm trong lớp bùn
(chưa xuyên hết) → còn S2 > 0. Khi xuyên hết bùn → S2 ≈ 0.

Đơn vị: q [kPa] · H [m] · Ec/Es [kPa] · ΔS, S1, S2 [cm].
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))
from settlement_calc import calc_s2_below_cdm  # noqa: E402

_SOFT_SYMBOLS = ("1", "1b", "2", "XMD")


def _default_db() -> Path:
    local = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
    return local if local.exists() else _ROOT / "data" / "TTHC.sqlite"


def area_ratio(D_m: float, spacing_m: float, pattern: str = "square") -> float:
    """Tỷ lệ diện tích thay thế a = A_cọc / A_đơn_vị."""
    import math
    r = D_m / 2.0
    if pattern == "triangle":
        return math.pi * r ** 2 / (spacing_m ** 2 * math.sqrt(3) / 2.0)
    return math.pi * r ** 2 / spacing_m ** 2


def soft_profile_from_db(bh_name: str, db_path: Optional[Path] = None) -> tuple:
    """Trả về (clay_top_depth_m, H_soft_m) từ lớp đất yếu của hố khoan.
    None nếu không có dữ liệu lớp."""
    db_path = Path(db_path) if db_path else _default_db()
    ph = ",".join("?" * len(_SOFT_SYMBOLS))
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(f"""
            SELECT depth_top_m, depth_bot_m FROM layers
            WHERE borehole_id=(SELECT id FROM boreholes WHERE name=?)
              AND symbol IN ({ph})
            ORDER BY depth_top_m
        """, (bh_name, *_SOFT_SYMBOLS)).fetchall()
    if not rows:
        return None, None
    top = float(rows[0]["depth_top_m"])
    H = sum(float(r["depth_bot_m"]) - float(r["depth_top_m"]) for r in rows)
    return top, round(H, 2)


def find_cdm_length(
    bh_name: str,
    q_kPa: float,
    a: float,
    Ec_kPa: float,
    Su_kPa: float,
    target_dS_cm: float,
    h_clay_m: Optional[float] = None,
    clay_top_depth_m: Optional[float] = None,
    L_step_m: float = 0.5,
    embed_max_m: float = 1.0,
    Es_factor: float = 250.0,
    mu: float = 1.0,
    B_load_m: Optional[float] = None,
    alpha_sand_kPa: float = 2000.0,
    t_years_residual: float = 15.0,
    db_path: Optional[Path] = None,
) -> dict:
    """Tìm độ xuyên cọc CDM vào bùn (p) ngắn nhất sao cho S1+S2 ≤ ΔS.

    Trả về dict:
      p_optimal_m       : độ xuyên vào bùn tối ưu (m) — None nếu không đạt
      S1_cm, S2_cm, S_total_cm : tại p tối ưu (hoặc tại full penetration nếu không đạt)
      target_dS_cm, ok  : ΔS mục tiêu + có đạt không
      penetrates_full   : True nếu phải xuyên hết bùn
      history           : list[{p_m, S1_cm, S2_cm, S_total_cm, ok}]
      Es_kPa, a, note
    """
    db_path = Path(db_path) if db_path else _default_db()
    # cu = μ·Su (hiệu chỉnh Bjerrum, TCCS 41 Phụ lục C.5) → Es = 250·cu
    cu_kPa = mu * Su_kPa
    Es_kPa = Es_factor * cu_kPa
    composite = a * Ec_kPa + (1.0 - a) * Es_kPa

    # Hình học lớp bùn
    db_top, db_H = soft_profile_from_db(bh_name, db_path)
    clay_top = clay_top_depth_m if clay_top_depth_m is not None else db_top
    H_soft = h_clay_m if h_clay_m is not None else db_H
    if clay_top is None:
        return {"p_optimal_m": None, "S1_cm": None, "S2_cm": None, "S_total_cm": None,
                "target_dS_cm": target_dS_cm, "ok": False, "penetrates_full": False,
                "history": [], "Es_kPa": Es_kPa, "a": a,
                "mu": round(mu, 4), "cu_kPa": round(cu_kPa, 2),
                "note": f"Không có dữ liệu lớp đất yếu cho {bh_name} — không tính được."}

    # Độ xuyên TỐI ĐA: tới đáy hố khoan (qua hết vùng nén lún theo lab Cc),
    # KHÔNG giới hạn ở H_soft theo ký hiệu — vì đất nén lún (Cc) thường sâu hơn.
    with sqlite3.connect(db_path) as con:
        _md = con.execute(
            "SELECT MAX(depth_bot_m) FROM layers WHERE borehole_id=(SELECT id FROM boreholes WHERE name=?)",
            (bh_name,)).fetchone()
    max_depth = float(_md[0]) if _md and _md[0] else (clay_top + (H_soft or 30.0))
    p_max = max(round(max_depth - clay_top, 1), L_step_m)

    def _settle(p: float) -> tuple:
        # H_gc = chiều dày đất được gia cố (toàn bộ độ xuyên dưới đỉnh bùn)
        S1 = (q_kPa * p / composite) * 100.0 if composite > 0 else 0.0
        tip_depth = clay_top + p
        _s2 = calc_s2_below_cdm(bh_name, tip_depth, q_kPa=q_kPa,
                                B_load_m=B_load_m, alpha_sand_kPa=alpha_sand_kPa,
                                t_years_residual=t_years_residual, db_path=db_path)
        # So sánh với ΔS cho phép dùng LÚN TÍCH LŨY ĐẾN t năm (TCCS 41):
        # sét mềm e0≥1 ×U(t); sét cứng e0<1 + cát lấy đủ
        S2 = _s2.get("S2_15yr_cm", _s2["S2_cm"])
        return round(S1, 2), round(S2, 2)

    # Dải độ xuyên: L_step → p_max, bước L_step
    ps = []
    p = L_step_m
    while p < p_max - 1e-6:
        ps.append(round(p, 2))
        p += L_step_m
    ps.append(round(p_max, 2))

    history = []
    optimal = None
    best = None  # case tổng lún nhỏ nhất (khi không đạt)
    for p in ps:
        S1, S2 = _settle(p)
        tot = round(S1 + S2, 2)
        ok = tot <= target_dS_cm + 1e-6
        row = {"p_m": p, "S1_cm": S1, "S2_cm": S2, "S_total_cm": tot, "ok": ok}
        history.append(row)
        if ok and optimal is None:
            optimal = row
        if best is None or tot < best["S_total_cm"]:
            best = row

    if optimal is not None:
        return {"p_optimal_m": optimal["p_m"], "S1_cm": optimal["S1_cm"],
                "S2_cm": optimal["S2_cm"], "S_total_cm": optimal["S_total_cm"],
                "target_dS_cm": target_dS_cm, "ok": True,
                "penetrates_full": optimal["p_m"] >= (H_soft or 0) - 1e-6,
                "H_soft_symbol_m": H_soft, "p_max_m": p_max,
                "clay_top_m": round(clay_top, 2),
                "tip_depth_m": round(clay_top + optimal["p_m"], 2),
                "history": history, "Es_kPa": Es_kPa, "a": a,
                "mu": round(mu, 4), "cu_kPa": round(cu_kPa, 2), "note": ""}

    # Không đạt — trả về case tổng lún nhỏ nhất
    return {"p_optimal_m": None, "S1_cm": best["S1_cm"], "S2_cm": best["S2_cm"],
            "S_total_cm": best["S_total_cm"], "target_dS_cm": target_dS_cm, "ok": False,
            "penetrates_full": True, "H_soft_symbol_m": H_soft, "p_max_m": p_max,
            "clay_top_m": round(clay_top, 2),
            "tip_depth_m": round(clay_top + best["p_m"], 2),
            "history": history, "Es_kPa": Es_kPa, "a": a,
            "mu": round(mu, 4), "cu_kPa": round(cu_kPa, 2),
            "note": (f"Tổng lún nhỏ nhất đạt được = {best['S_total_cm']:.1f} cm (độ xuyên {best['p_m']:.1f} m) "
                     f"> ΔS = {target_dS_cm:.1f} cm. Cần giảm khoảng cách s (tăng tỷ lệ thay thế) hoặc tăng qu.")}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    DB = _default_db()
    print(f"DB: {DB}\n")
    # Demo: KE-HK2, D=0.8, s=1.8 square, qu=800, Su=12, q=40.8, ΔS=20cm
    a = area_ratio(0.8, 1.8, "square")
    Ec = 100 * 800 / 2.0
    for ds in (20.0, 30.0, 10.0):
        r = find_cdm_length("KE-HK2", q_kPa=40.8, a=a, Ec_kPa=Ec, Su_kPa=12.0,
                            target_dS_cm=ds, db_path=DB)
        print(f"ΔS={ds}cm → p_opt={r['p_optimal_m']}m  S1={r['S1_cm']} S2={r['S2_cm']} "
              f"tong={r['S_total_cm']}cm  ok={r['ok']}  full={r['penetrates_full']}")
        if r["note"]:
            print("   ", r["note"])
    print(f"\na={a:.4f}  (D=0.8 s=1.8 square)")
