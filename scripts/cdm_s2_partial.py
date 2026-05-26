"""
cdm_s2_partial.py — Tính lún cố kết S2 cho lớp đất yếu CÒN LẠI dưới mũi
cọc CDM khi cọc KHÔNG cắm hết lớp bùn (partial penetration).

Tổng lún:  S_total = S1 + S2
  S1 = lún đàn hồi khối CDM (TCVN 9403 Phụ lục C) — đã có trong settlement_calc
  S2 = lún cố kết Terzaghi của phần đất yếu DƯỚI mũi cọc

CÔNG THỨC TỪNG LỚP CON i (Terzaghi 1D):

  Trường hợp NC (σ'_v0 ≥ P_C):
     S_i = H_i · Cc/(1+e0) · log10(σ'_vf / σ'_v0)

  Trường hợp OC (σ'_vf ≤ P_C):
     S_i = H_i · Cs/(1+e0) · log10(σ'_vf / σ'_v0)

  Trường hợp cross P_C (σ'_v0 < P_C < σ'_vf):
     S_i = H_i · [Cs/(1+e0) · log10(P_C / σ'_v0)
              + Cc/(1+e0) · log10(σ'_vf / P_C)]

PHÂN BỐ ỨNG SUẤT q TRUYỀN DƯỚI MŨI CỌC CDM:

  1. infinite_slab: Δσ_z = q (plain strain — kè dài vô tận, tải đều)
                    → ÁP DỤNG mặc định cho kè SW dài tuyến.

  2. method_2to1:   Δσ_z = q · B·L / ((B+z)(L+z))    (Boussinesq xấp xỉ 2:1)
                    với B, L = kích thước móng tải, z = sâu dưới mũi cọc

Tham chiếu:
  - TCVN 9403:2012 Phụ lục C
  - TCCS 41:2022 Điều 9 + Phụ lục A
  - Terzaghi 1943

Tài liệu: 59-cdm-s2-partial.md

Public API:
  calc_S2_partial(layers, q_kPa, z_below_tip_m, gamma_w_kNm3, method)
      → S2 (cm) + chi tiết từng lớp
  calc_total_settlement_cdm(S1_cm, layers_below, q_kPa, ...)
      → S_total + breakdown
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
_DB   = _ROOT / "data" / "TTHC.sqlite"

GAMMA_W_DEFAULT = 9.81  # kN/m³


def stress_distribution_2to1(q_kPa: float, B_m: float, L_m: float,
                              z_m: float) -> float:
    """Phân bố ứng suất 2:1 (Boussinesq xấp xỉ) dưới móng B×L.

    Δσ_z = q · B·L / ((B+z)·(L+z))
    """
    if z_m < 0:
        z_m = 0.0
    denom = (B_m + z_m) * (L_m + z_m)
    return q_kPa * B_m * L_m / denom if denom > 0 else q_kPa


def stress_distribution_infinite_slab(q_kPa: float, z_m: float = 0.0) -> float:
    """Plain strain — kè dài vô tận, Δσ_z = q tại mọi độ sâu."""
    return float(q_kPa)


def _delta_sigma_z(q_kPa: float, z_m: float, method: str,
                   B_m: Optional[float] = None,
                   L_m: Optional[float] = None) -> float:
    """Wrapper chọn phương pháp phân bố ứng suất."""
    if method == "method_2to1":
        if B_m is None or L_m is None:
            raise ValueError("method_2to1 yêu cầu B_m và L_m")
        return stress_distribution_2to1(q_kPa, B_m, L_m, z_m)
    elif method == "infinite_slab":
        return stress_distribution_infinite_slab(q_kPa, z_m)
    else:
        raise ValueError(f"method không hợp lệ: {method!r}. "
                          "Dùng 'infinite_slab' hoặc 'method_2to1'.")


def _terzaghi_layer(H_i: float, e0: float, Cc: float, Cs: float,
                    sigma_v0: float, sigma_vf: float, PC: float) -> tuple[float, str]:
    """Lún 1 lớp con — tự chọn OC / NC / cross_PC.

    Returns:
        (S_i_cm, mode) — mode = 'OC' | 'NC' | 'cross_PC'
    """
    if H_i <= 0 or e0 < 0 or sigma_v0 <= 0 or sigma_vf <= sigma_v0:
        return 0.0, "skip"

    if sigma_vf <= PC:
        # OC: chỉ Cs
        S = H_i * (Cs / (1.0 + e0)) * math.log10(sigma_vf / sigma_v0)
        mode = "OC"
    elif sigma_v0 >= PC:
        # NC: chỉ Cc
        S = H_i * (Cc / (1.0 + e0)) * math.log10(sigma_vf / sigma_v0)
        mode = "NC"
    else:
        # cross_PC: Cs trong [σv0, PC] + Cc trong [PC, σvf]
        S = H_i * (
            (Cs / (1.0 + e0)) * math.log10(PC / sigma_v0) +
            (Cc / (1.0 + e0)) * math.log10(sigma_vf / PC)
        )
        mode = "cross_PC"

    return S * 100.0, mode   # m → cm


def calc_S2_partial(
    layers_below_tip: list[dict],
    q_kPa: float,
    method: str = "infinite_slab",
    B_m: Optional[float] = None,
    L_m: Optional[float] = None,
    gamma_w_kNm3: float = GAMMA_W_DEFAULT,
    sigma_v0_top_kPa: float = 0.0,
) -> dict:
    """Tính S2 cho các lớp đất yếu dưới mũi cọc CDM.

    Args:
        layers_below_tip: list[dict] mỗi dict gồm:
            {'H_m':   chiều dày lớp (m),
             'e0':    hệ số rỗng ban đầu,
             'Cc':    chỉ số nén,
             'Cs':    chỉ số nở,
             'PC_kPa':áp lực tiền cố kết,
             'gamma_kNm3':       dung trọng tự nhiên,
             'gamma_sub_kNm3':   dung trọng đẩy nổi (γ_sat - γ_w)}
        q_kPa: tải tác dụng tại đỉnh khối CDM (đã truyền 100% qua khối)
        method: 'infinite_slab' (kè dài) hoặc 'method_2to1' (móng hữu hạn)
        B_m, L_m: bề rộng × chiều dài móng (chỉ cần khi method_2to1)
        sigma_v0_top_kPa: ứng suất hữu hiệu tại mũi cọc (trên cùng layers_below)

    Returns:
        {
          'S2_cm':           tổng lún cố kết (cm),
          'method':          phương pháp phân bố ứng suất,
          'layers_detail':   [{depth_below, H_m, sigma_v0, sigma_vf,
                              delta_sigma, mode, S_i_cm}, ...],
          'q_kPa':           tải áp dụng,
          'sigma_v0_top':    ứng suất tại mũi cọc,
        }
    """
    S2_total = 0.0
    detail = []
    z_cum = 0.0     # độ sâu cumulative dưới mũi cọc
    sigma_v0_cum = float(sigma_v0_top_kPa)

    for lyr in layers_below_tip:
        H = float(lyr.get("H_m", 0))
        if H <= 0:
            continue
        e0 = float(lyr.get("e0", 0))
        Cc = float(lyr.get("Cc", 0))
        Cs = float(lyr.get("Cs", 0))
        PC = float(lyr.get("PC_kPa", 0))
        gamma = float(lyr.get("gamma_kNm3", 15.0))
        gamma_sub = float(lyr.get("gamma_sub_kNm3", gamma - gamma_w_kNm3))

        # midpoint depth dưới mũi
        z_mid = z_cum + H / 2.0
        # ứng suất hữu hiệu ban đầu tại midpoint
        sigma_v0_mid = sigma_v0_cum + gamma_sub * (H / 2.0)
        # ứng suất gia tăng do tải truyền
        delta_sigma = _delta_sigma_z(q_kPa, z_mid, method, B_m, L_m)
        sigma_vf_mid = sigma_v0_mid + delta_sigma

        S_i, mode = _terzaghi_layer(H, e0, Cc, Cs,
                                     sigma_v0_mid, sigma_vf_mid, PC)
        S2_total += S_i

        detail.append({
            "depth_below_tip_m": round(z_mid, 2),
            "H_m":               round(H, 2),
            "e0":                round(e0, 3),
            "Cc":                round(Cc, 3),
            "Cs":                round(Cs, 3),
            "PC_kPa":            round(PC, 1),
            "sigma_v0_kPa":      round(sigma_v0_mid, 1),
            "delta_sigma_kPa":   round(delta_sigma, 1),
            "sigma_vf_kPa":      round(sigma_vf_mid, 1),
            "mode":              mode,
            "S_i_cm":            round(S_i, 2),
        })

        z_cum += H
        sigma_v0_cum += gamma_sub * H   # đáy lớp

    return {
        "S2_cm":          round(S2_total, 2),
        "method":         method,
        "n_layers":       len(detail),
        "total_H_below":  round(z_cum, 2),
        "q_kPa":          float(q_kPa),
        "sigma_v0_top":   float(sigma_v0_top_kPa),
        "layers_detail":  detail,
    }


def calc_total_settlement_cdm(
    S1_cm: float,
    layers_below_tip: list[dict],
    q_kPa: float,
    method: str = "infinite_slab",
    B_m: Optional[float] = None,
    L_m: Optional[float] = None,
    sigma_v0_top_kPa: float = 0.0,
) -> dict:
    """Tính tổng lún CDM = S1 + S2 khi cọc CDM KHÔNG hết lớp bùn.

    S1 = từ settlement_calc (TCVN 9403 Phụ lục C) — passed in
    S2 = tính ở đây

    Returns:
        {'S1_cm', 'S2_cm', 'S_total_cm', 'partial_penetration': bool, ...}
    """
    r_S2 = calc_S2_partial(
        layers_below_tip, q_kPa, method, B_m, L_m,
        sigma_v0_top_kPa=sigma_v0_top_kPa,
    )
    partial = (r_S2["total_H_below"] > 0 and r_S2["n_layers"] > 0)
    return {
        "S1_cm":               round(S1_cm, 2),
        "S2_cm":               r_S2["S2_cm"],
        "S_total_cm":          round(S1_cm + r_S2["S2_cm"], 2),
        "partial_penetration": partial,
        "method":              method,
        "n_layers_below":      r_S2["n_layers"],
        "total_H_below":       r_S2["total_H_below"],
        "S2_detail":           r_S2["layers_detail"],
    }


def create_table(db_path: Optional[Path] = None) -> None:
    """Tạo bảng cdm_s2_partial_results (idempotent)."""
    _p = db_path or _DB
    with sqlite3.connect(_p) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS cdm_s2_partial_results (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_code     TEXT,
                bh_name       TEXT,
                S1_cm         REAL,
                S2_cm         REAL,
                S_total_cm    REAL,
                method        TEXT,
                q_kPa         REAL,
                n_layers      INTEGER,
                H_below_m     REAL,
                detail_json   TEXT,
                source        TEXT DEFAULT 'cdm_s2_partial.py',
                updated_at    TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE (zone_code, bh_name, method, q_kPa)
            )
        """)
        con.commit()


if __name__ == "__main__":
    import sys, json
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 80)
    print("DEMO: S2 khi CDM KHÔNG hết lớp bùn (partial penetration)")
    print("=" * 80)
    print()

    # Ví dụ KE-HK1: H_soft = 25m, CDM dài 20m → còn 5m lớp bùn dưới mũi
    # Mũi cọc CDM tại độ sâu 20m, dưới đó còn 5m bùn + lớp cứng
    layers_below_demo = [
        # 5m bùn dưới mũi cọc CDM, chia 5 phụ lớp 1m mỗi cái
        {"H_m": 1.0, "e0": 1.7, "Cc": 0.50, "Cs": 0.10,
         "PC_kPa": 80, "gamma_kNm3": 16.0, "gamma_sub_kNm3": 6.19},
        {"H_m": 1.0, "e0": 1.65, "Cc": 0.48, "Cs": 0.10,
         "PC_kPa": 95, "gamma_kNm3": 16.0, "gamma_sub_kNm3": 6.19},
        {"H_m": 1.0, "e0": 1.6, "Cc": 0.45, "Cs": 0.10,
         "PC_kPa": 110, "gamma_kNm3": 16.5, "gamma_sub_kNm3": 6.69},
        {"H_m": 1.0, "e0": 1.55, "Cc": 0.42, "Cs": 0.09,
         "PC_kPa": 130, "gamma_kNm3": 16.5, "gamma_sub_kNm3": 6.69},
        {"H_m": 1.0, "e0": 1.5, "Cc": 0.40, "Cs": 0.09,
         "PC_kPa": 150, "gamma_kNm3": 17.0, "gamma_sub_kNm3": 7.19},
    ]

    # Tải truyền qua khối CDM = q_fill (giả định 100% truyền xuống mũi cọc)
    q_demo = 60.0   # kPa (tải đắp 3m × γ_fill 20)
    # σ'_v0 tại mũi cọc (sau 20m bùn): ~6 kN/m³ × 20m = 120 kPa
    sigma_v0_tip = 120.0

    # Method 1: infinite_slab (mặc định cho kè dài)
    r1 = calc_S2_partial(layers_below_demo, q_demo,
                          method="infinite_slab",
                          sigma_v0_top_kPa=sigma_v0_tip)
    print(f"=== infinite_slab (kè dài plain strain) ===")
    print(f"q = {q_demo} kPa, σ'_v0 mũi = {sigma_v0_tip} kPa, 5 lớp 1m")
    print(f"S2 = {r1['S2_cm']:.1f} cm")
    print()
    print(f'{"z mũi (m)":>10s} {"H":>4s} {"σv0":>7s} {"Δσ":>6s} {"σvf":>7s} {"mode":>9s} {"Si (cm)":>8s}')
    for d in r1["layers_detail"]:
        print(f'{d["depth_below_tip_m"]:10.1f} '
              f'{d["H_m"]:4.1f} {d["sigma_v0_kPa"]:7.1f} '
              f'{d["delta_sigma_kPa"]:6.1f} {d["sigma_vf_kPa"]:7.1f} '
              f'{d["mode"]:>9s} {d["S_i_cm"]:8.2f}')

    # Method 2: 2:1 với móng kè 4m × 50m
    print()
    r2 = calc_S2_partial(layers_below_demo, q_demo,
                          method="method_2to1", B_m=4.0, L_m=50.0,
                          sigma_v0_top_kPa=sigma_v0_tip)
    print(f"=== method_2to1 (móng 4m × 50m) ===")
    print(f"S2 = {r2['S2_cm']:.1f} cm")

    # Tổng
    print()
    print(f"=== Total settlement ===")
    S1_demo = 10.5   # giả định S1 từ TCVN 9403 Phụ lục C
    tot = calc_total_settlement_cdm(S1_demo, layers_below_demo, q_demo,
                                     method="infinite_slab",
                                     sigma_v0_top_kPa=sigma_v0_tip)
    print(f"S1 (đàn hồi khối CDM):           {tot['S1_cm']:.1f} cm")
    print(f"S2 (cố kết dưới mũi cọc):        {tot['S2_cm']:.1f} cm")
    print(f"S_total = S1 + S2:                {tot['S_total_cm']:.1f} cm")
    print(f"partial_penetration:              {tot['partial_penetration']}")

    print()
    print(f"=== SQLite ===")
    create_table()
    print("Bảng cdm_s2_partial_results: created OK")
