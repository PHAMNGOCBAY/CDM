"""
sw_plaxis_params.py — Tính EI / EA / d_eq cho cọc ván SW dự ứng lực, nhập PLAXIS.

Công thức:
    Ec  = 4730·√fc  (MPa) — ACI 318 cho bê tông
    EA_pile = Ec · Atd       (kN)         — 1 cừ riêng
    EI_pile = Ec · Itd       (kN·m²)      — 1 cừ riêng
    EA/m    = EA_pile / w    (kN/m)       — per m wall (PLAXIS plate)
    EI/m    = EI_pile / w    (kN·m²/m)
    d_eq    = √(12·EI/EA)    (m)          — thickness equivalent
    γ_eq    = weight_T·g·L⁻¹·w⁻¹ (kN/m²)  — weight cho plate

PLAXIS 2D plain strain plate element nhập (per unit wall length):
    EA  [kN/m]      → axial stiffness
    EI  [kN·m²/m]   → bending stiffness
    w   [kN/m/m]    → weight per area
    nu  = 0.15-0.20 → Poisson cho bê tông
    d   = d_eq      → display thickness (visualization, không vào tính toán)
    Mp  = Mcr_kNm   → moment kháng nứt (cho elastoplastic)

Tài liệu: 57-sw-plaxis-EI-EA.md
"""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
_DB   = _ROOT / "data" / "TTHC.sqlite"

# Bảng tra catalog 3 cọc cừ SW + thông số bê tông
SW_CATALOG = {
    "SW-600B": {"H_mm": 600, "width_mm": 996, "t_mm": 130, "Atd_cm2": 2288.0,
                "Itd_cm4":  797396, "Mcr_kNm":  35.0 * 9.81, "weight_T": 11.0,
                "L_std_m": 20, "L_min_m": 14, "L_max_m": 26,
                "perimeter_mm": 3500.0},
    "SW-740":  {"H_mm": 740, "width_mm": 996, "t_mm": 160, "Atd_cm2": 2794.0,
                "Itd_cm4": 1480428, "Mcr_kNm":  60.4 * 9.81, "weight_T": 14.55,
                "L_std_m": 21, "L_min_m": 16, "L_max_m": 28,
                "perimeter_mm": 4205.853},
    "SW-840":  {"H_mm": 840, "width_mm": 996, "t_mm": 160, "Atd_cm2": 3107.0,
                "Itd_cm4": 2125017, "Mcr_kNm":  77.1 * 9.81, "weight_T": 16.35,
                "L_std_m": 22, "L_min_m": 17, "L_max_m": 29,
                "perimeter_mm": 4594.913},
}

# Cấp bê tông phổ biến cho cọc ván SW dự ứng lực
FC_CASES = {
    "C50": 50,   # B45 — tối thiểu
    "C60": 60,   # B55
    "C70": 70,   # B65 — mặc định dự án TTHC
    "C80": 80,   # B75 — cao cấp
}

# Hệ số bê tông
GAMMA_BT_kN_per_m3 = 24.5  # bê tông dự ứng lực
NU_BT = 0.18               # Poisson


def Ec_from_fc(fc_MPa: float) -> float:
    """Mô đun đàn hồi bê tông Ec (MPa) từ fc cylinder (MPa).

    Công thức ACI 318: Ec = 4730·√fc (MPa).
    """
    return 4730.0 * math.sqrt(max(fc_MPa, 0.0))


def compute_plate_params(pile_name: str, fc_MPa: float = 70.0) -> dict:
    """Tính đầy đủ EI/EA + d_eq + w cho 1 cọc + cấp bê tông.

    Returns:
        {
            'pile': str, 'fc_MPa': float, 'fc_label': str,
            'Ec_MPa': float, 'Ec_kPa': float,
            'Atd_cm2': float, 'Itd_cm4': float, 'width_mm': int,
            'EA_per_pile_kN':     float,   # 1 cừ
            'EI_per_pile_kNm2':   float,
            'EA_per_m_kN_per_m':  float,   # per m wall length
            'EI_per_m_kNm2_per_m': float,
            'd_eq_m':             float,   # chiều dày tương đương
            'w_kN_per_m2':        float,   # cho plate input
            'nu':                 float,
            'Mcr_kNm':            float,   # mô men kháng nứt
            'plaxis_inputs':      dict,    # tóm tắt input PLAXIS
        }
    """
    if pile_name not in SW_CATALOG:
        raise ValueError(f"Cọc không có trong catalog: {pile_name!r}. "
                          f"Dùng: {list(SW_CATALOG.keys())}")
    p = SW_CATALOG[pile_name]
    width_m  = p["width_mm"] / 1000.0
    Atd_m2   = p["Atd_cm2"]  * 1e-4
    Itd_m4   = p["Itd_cm4"]  * 1e-8

    Ec_MPa = Ec_from_fc(fc_MPa)
    Ec_kPa = Ec_MPa * 1000.0

    # Per 1 cừ riêng
    EA_pile = Ec_kPa * Atd_m2     # kN
    EI_pile = Ec_kPa * Itd_m4     # kN·m²

    # Per m wall length (PLAXIS 2D plate)
    EA_m = EA_pile / width_m       # kN/m
    EI_m = EI_pile / width_m       # kN·m²/m

    # Thickness equivalent
    d_eq = math.sqrt(12.0 * EI_m / EA_m)

    # Weight cho plate: per m² mặt tường
    weight_kN_per_m_length = p["weight_T"] * 9.81 / p["L_std_m"]
    w_kN_per_m2 = weight_kN_per_m_length / width_m

    plaxis = {
        "EA_kN_per_m":    round(EA_m, 0),
        "EI_kNm2_per_m":  round(EI_m, 1),
        "d_m":            round(d_eq, 4),
        "w_kN_per_m2":    round(w_kN_per_m2, 3),
        "nu":             NU_BT,
        "Mp_kNm_per_m":   round(p["Mcr_kNm"] / width_m, 1),
        "_note":          "Plain strain plate per m wall length",
    }

    return {
        "pile":                pile_name,
        "fc_MPa":              float(fc_MPa),
        "fc_label":            f"C{int(fc_MPa)}",
        "Ec_MPa":              round(Ec_MPa, 1),
        "Ec_kPa":              round(Ec_kPa, 0),
        "Atd_cm2":             p["Atd_cm2"],
        "Itd_cm4":             p["Itd_cm4"],
        "width_mm":            p["width_mm"],
        "H_mm":                p["H_mm"],
        "Mcr_kNm":             p["Mcr_kNm"],
        "EA_per_pile_kN":      round(EA_pile, 0),
        "EI_per_pile_kNm2":    round(EI_pile, 1),
        "EA_per_m_kN_per_m":   round(EA_m, 0),
        "EI_per_m_kNm2_per_m": round(EI_m, 1),
        "d_eq_m":              round(d_eq, 4),
        "w_kN_per_m2":         round(w_kN_per_m2, 3),
        "nu":                  NU_BT,
        "plaxis_inputs":       plaxis,
    }


def compute_all() -> list[dict]:
    """Tính cho tất cả combo (cọc × cấp bê tông)."""
    out = []
    for pname in SW_CATALOG:
        for fc_lbl, fc_val in FC_CASES.items():
            r = compute_plate_params(pname, fc_val)
            out.append(r)
    return out


def create_table(db_path: Optional[Path] = None) -> None:
    """Tạo bảng sw_plaxis_plate_params (idempotent)."""
    _p = db_path or _DB
    with sqlite3.connect(_p) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS sw_plaxis_plate_params (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                pile                    TEXT NOT NULL,
                fc_MPa                  REAL NOT NULL,
                fc_label                TEXT,
                Ec_MPa                  REAL,
                Atd_cm2                 REAL,
                Itd_cm4                 REAL,
                width_mm                REAL,
                H_mm                    REAL,
                Mcr_kNm                 REAL,
                EA_per_pile_kN          REAL,
                EI_per_pile_kNm2        REAL,
                EA_per_m_kN_per_m       REAL,
                EI_per_m_kNm2_per_m     REAL,
                d_eq_m                  REAL,
                w_kN_per_m2             REAL,
                nu                      REAL DEFAULT 0.18,
                source                  TEXT DEFAULT 'sw_plaxis_params.py — Ec=4730·√fc (ACI 318)',
                updated_at              TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE (pile, fc_MPa)
            )
        """)
        con.commit()


def save_to_db(rows: list[dict], db_path: Optional[Path] = None) -> None:
    """Lưu tất cả kết quả vào SQLite. ON CONFLICT idempotent."""
    _p = db_path or _DB
    create_table(_p)
    with sqlite3.connect(_p) as con:
        for r in rows:
            con.execute("""
                INSERT INTO sw_plaxis_plate_params
                    (pile, fc_MPa, fc_label, Ec_MPa, Atd_cm2, Itd_cm4,
                     width_mm, H_mm, Mcr_kNm,
                     EA_per_pile_kN, EI_per_pile_kNm2,
                     EA_per_m_kN_per_m, EI_per_m_kNm2_per_m,
                     d_eq_m, w_kN_per_m2, nu)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (pile, fc_MPa) DO UPDATE SET
                    Ec_MPa = excluded.Ec_MPa,
                    EA_per_pile_kN = excluded.EA_per_pile_kN,
                    EI_per_pile_kNm2 = excluded.EI_per_pile_kNm2,
                    EA_per_m_kN_per_m = excluded.EA_per_m_kN_per_m,
                    EI_per_m_kNm2_per_m = excluded.EI_per_m_kNm2_per_m,
                    d_eq_m = excluded.d_eq_m,
                    w_kN_per_m2 = excluded.w_kN_per_m2,
                    updated_at = datetime('now','localtime')
            """, (r["pile"], r["fc_MPa"], r["fc_label"], r["Ec_MPa"],
                  r["Atd_cm2"], r["Itd_cm4"], r["width_mm"], r["H_mm"], r["Mcr_kNm"],
                  r["EA_per_pile_kN"], r["EI_per_pile_kNm2"],
                  r["EA_per_m_kN_per_m"], r["EI_per_m_kNm2_per_m"],
                  r["d_eq_m"], r["w_kN_per_m2"], r["nu"]))
        con.commit()


def save_to_json() -> Path:
    """Lưu vào data/sw_plaxis_params.json."""
    out_path = _ROOT / "data" / "sw_plaxis_params.json"
    rows = compute_all()
    meta = {
        "_meta": {
            "source": "scripts/sw_plaxis_params.py",
            "formula": {
                "Ec":     "4730*sqrt(fc) MPa (ACI 318)",
                "EA":     "Ec * Atd",
                "EI":     "Ec * Itd",
                "per_m":  "divide by width_mm/1000",
                "d_eq":   "sqrt(12·EI/EA)",
                "w_kN_per_m2": "weight_T * 9.81 / L_std / width",
            },
            "plaxis_2d_plate_inputs": ["EA", "EI", "d", "w", "nu", "Mp"],
            "n_piles": len(SW_CATALOG),
            "n_fc_cases": len(FC_CASES),
        },
        "results": rows,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return out_path


def print_table(rows: list[dict]) -> None:
    """In bảng tóm tắt console."""
    print(f'{"Pile":8s}  {"fc":4s}  {"Ec (MPa)":>10s}  '
          f'{"EA/m (kN/m)":>14s}  {"EI/m (kNm²/m)":>16s}  '
          f'{"d_eq (m)":>10s}  {"w (kN/m²)":>10s}  {"Mp/m (kNm/m)":>13s}')
    print('-' * 120)
    cur_pile = None
    for r in rows:
        if cur_pile != r["pile"]:
            if cur_pile is not None: print()
            cur_pile = r["pile"]
        print(f'{r["pile"]:8s}  {r["fc_label"]:4s}  {r["Ec_MPa"]:10.0f}  '
              f'{r["EA_per_m_kN_per_m"]:14,.0f}  {r["EI_per_m_kNm2_per_m"]:16,.0f}  '
              f'{r["d_eq_m"]:10.4f}  {r["w_kN_per_m2"]:10.3f}  '
              f'{r["plaxis_inputs"]["Mp_kNm_per_m"]:13.1f}')


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 80)
    print("BẢNG TÍNH EI / EA / d_eq CHO CỌC VÁN SW (input PLAXIS)")
    print("Cọc: SW-600B, SW-740, SW-840  |  Bê tông: C50/C60/C70/C80")
    print("=" * 80)
    print()
    rows = compute_all()
    print_table(rows)
    print()
    print("=" * 80)
    print("LƯU KẾT QUẢ")
    print("=" * 80)
    save_to_db(rows)
    print(f"  SQLite: bảng sw_plaxis_plate_params ({len(rows)} rows)")
    out_json = save_to_json()
    print(f"  JSON:   {out_json}")
    print()
    print("=" * 80)
    print("HƯỚNG DẪN NHẬP PLAXIS 2D (Plate element, plain strain)")
    print("=" * 80)
    print()
    print("Material → Plate → 'Elastoplastic' (chú ý nu, Mp cho elastoplastic):")
    print("  Material type:    Elastic / Elastoplastic")
    print("  Identification:   SW-740 fc=70 (vd)")
    print("  EA  (kN/m):       theo cột 'EA/m' bảng trên")
    print("  EI  (kN·m²/m):    theo cột 'EI/m'")
    print("  d   (m):          theo cột 'd_eq' (tự động tính lại nếu PLAXIS yêu cầu)")
    print("  w   (kN/m/m):     theo cột 'w'")
    print("  ν (Poisson):      0.15 - 0.20 (mặc định 0.18 cho BT DUL)")
    print("  Mp  (kN·m/m):     theo cột 'Mp/m' = Mcr/width — KHÔNG vượt giới hạn nứt")
    print()
    print("Lưu ý: PLAXIS 2D plate giả định plain strain — EA/EI per m wall length.")
    print("       KHÔNG nhập EA/EI per 1 cừ riêng (sẽ thiếu chiều rộng).")
