"""
concrete_modulus.py — Mô đun đàn hồi Ec bê tông theo nhiều tiêu chuẩn.

Công thức tính Ec từ fc:
    1. ACI 318:       Ec = 4730·√fc      (MPa, fc dạng cylinder)
    2. TCVN 5574:2018: bảng tra Eb theo cấp B (B25, B30, B45, B60, B80, B100...)
    3. EC2 (EN 1992): Ecm = 22·(fcm/10)^0.3 (GPa) với fcm = fc + 8 MPa
    4. AS 3600:       Ec = ρ^1.5 · (0.043·√fc)  (MPa) — bao gồm density

Tài liệu: 58-concrete-modulus.md

Public API:
    Ec_ACI318(fc_MPa)         → Ec (MPa) theo ACI 318
    Ec_EC2(fc_MPa)            → Ec (MPa) theo Eurocode 2
    Ec_TCVN5574(grade)        → Eb (MPa) theo TCVN 5574 từ cấp B (B25..B100)
    Ec_AS3600(fc, rho)        → Ec (MPa) theo AS 3600 (Úc)
    compare_all(fc)           → dict so sánh 4 công thức
    create_table(db_path)     → tạo bảng SQLite concrete_modulus_table
    save_to_db(db_path)       → populate 8 cấp BT × 4 công thức
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
_DB   = _ROOT / "data" / "TTHC.sqlite"


# ─────────────────────────────────────────────────────────────────────────
# TCVN 5574:2018 - Bảng tra Eb theo cấp độ bền B
# Đơn vị: MPa
# ─────────────────────────────────────────────────────────────────────────
TCVN5574_Eb_MPa = {
    "B15":  23_000,
    "B20":  27_000,
    "B25":  30_000,
    "B30":  32_500,
    "B35":  34_500,
    "B40":  36_000,
    "B45":  37_000,
    "B50":  38_000,
    "B55":  39_000,
    "B60":  39_500,
    "B70":  41_000,
    "B80":  42_000,
    "B90":  43_000,
    "B100": 44_000,
}

# Mapping cấp B (TCVN) → fc cylinder (MPa) gần đúng
# Lưu ý: B = cường độ lập phương 15cm × 0.778 (gần đúng cho fc cylinder)
TCVN_B_to_fc_cylinder = {
    "B15":  11.7, "B20":  15.6, "B25":  19.5,
    "B30":  23.4, "B35":  27.3, "B40":  31.2,
    "B45":  35.1, "B50":  39.0, "B55":  42.9,
    "B60":  46.8, "B70":  54.6, "B80":  62.4,
    "B90":  70.2, "B100": 78.0,
}


def Ec_ACI318(fc_MPa: float) -> float:
    """ACI 318: Ec = 4730·√fc (MPa) — bê tông thường ρ = 2400 kg/m³."""
    return 4730.0 * math.sqrt(max(fc_MPa, 0.0))


def Ec_EC2(fc_MPa: float) -> float:
    """Eurocode 2 (EN 1992-1-1): Ecm = 22·(fcm/10)^0.3 (GPa).

    fcm = fc + 8 MPa (mean strength = characteristic + 8).
    Returns Ec in MPa.
    """
    fcm = max(fc_MPa, 0.0) + 8.0
    Ecm_GPa = 22.0 * (fcm / 10.0) ** 0.3
    return Ecm_GPa * 1000.0  # GPa → MPa


def Ec_TCVN5574(grade: str) -> float:
    """TCVN 5574:2018 — tra bảng Eb (MPa) theo cấp B.

    Args:
        grade: 'B15', 'B20', 'B25', ..., 'B100'

    Raises:
        ValueError nếu grade không có trong bảng.
    """
    if grade not in TCVN5574_Eb_MPa:
        raise ValueError(
            f"Cấp BT không hợp lệ: {grade!r}. "
            f"Dùng: {list(TCVN5574_Eb_MPa.keys())}"
        )
    return float(TCVN5574_Eb_MPa[grade])


def Ec_AS3600(fc_MPa: float, rho_kg_m3: float = 2400.0) -> float:
    """AS 3600 (Úc): Ec = ρ^1.5 · (0.043·√fc) MPa.

    ρ = density bê tông (kg/m³), mặc định 2400.
    """
    fc = max(fc_MPa, 0.0)
    return rho_kg_m3 ** 1.5 * 0.043 * math.sqrt(fc)


def compare_all(fc_MPa: float, grade_tcvn: Optional[str] = None,
                rho_kg_m3: float = 2400.0) -> dict:
    """So sánh 4 công thức tại 1 fc cụ thể.

    Args:
        fc_MPa:     fc cylinder (MPa)
        grade_tcvn: cấp B TCVN tương ứng (auto suy đoán nếu None)
        rho_kg_m3:  density (kg/m³) cho AS 3600

    Returns:
        {'fc_MPa', 'grade_tcvn_guess', 'Ec_ACI318', 'Ec_EC2',
         'Ec_TCVN5574', 'Ec_AS3600', 'mean_MPa', 'std_pct'}
    """
    aci   = Ec_ACI318(fc_MPa)
    ec2   = Ec_EC2(fc_MPa)
    as3600 = Ec_AS3600(fc_MPa, rho_kg_m3)

    # Auto-guess grade TCVN
    if grade_tcvn is None:
        # find grade with fc gần nhất
        diffs = [(abs(fc_MPa - fc_cyl), g)
                 for g, fc_cyl in TCVN_B_to_fc_cylinder.items()]
        grade_tcvn = min(diffs)[1]
    try:
        tcvn = Ec_TCVN5574(grade_tcvn)
    except ValueError:
        tcvn = None

    vals = [v for v in [aci, ec2, tcvn, as3600] if v is not None]
    mean = sum(vals) / len(vals) if vals else 0.0
    std  = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5 if vals else 0.0
    std_pct = (std / mean * 100) if mean > 0 else 0.0

    return {
        "fc_MPa":           float(fc_MPa),
        "grade_tcvn_guess": grade_tcvn,
        "rho_kg_m3":        float(rho_kg_m3),
        "Ec_ACI318_MPa":    round(aci, 0),
        "Ec_EC2_MPa":       round(ec2, 0),
        "Ec_TCVN5574_MPa":  round(tcvn, 0) if tcvn else None,
        "Ec_AS3600_MPa":    round(as3600, 0),
        "mean_MPa":         round(mean, 0),
        "std_pct":          round(std_pct, 2),
    }


def create_table(db_path: Optional[Path] = None) -> None:
    """Tạo bảng concrete_modulus_table (idempotent)."""
    _p = db_path or _DB
    with sqlite3.connect(_p) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS concrete_modulus_table (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                grade_tcvn      TEXT NOT NULL UNIQUE,
                fc_MPa          REAL NOT NULL,
                Ec_ACI318_MPa   REAL,
                Ec_EC2_MPa      REAL,
                Ec_TCVN5574_MPa REAL,
                Ec_AS3600_MPa   REAL,
                mean_MPa        REAL,
                std_pct         REAL,
                source          TEXT DEFAULT 'concrete_modulus.py',
                updated_at      TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        con.commit()


def save_to_db(db_path: Optional[Path] = None) -> int:
    """Tính + lưu 14 cấp BT (B15-B100) vào SQLite."""
    _p = db_path or _DB
    create_table(_p)
    n = 0
    with sqlite3.connect(_p) as con:
        for grade, fc_cyl in TCVN_B_to_fc_cylinder.items():
            r = compare_all(fc_cyl, grade_tcvn=grade)
            con.execute("""
                INSERT INTO concrete_modulus_table
                    (grade_tcvn, fc_MPa,
                     Ec_ACI318_MPa, Ec_EC2_MPa, Ec_TCVN5574_MPa, Ec_AS3600_MPa,
                     mean_MPa, std_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (grade_tcvn) DO UPDATE SET
                    fc_MPa = excluded.fc_MPa,
                    Ec_ACI318_MPa = excluded.Ec_ACI318_MPa,
                    Ec_EC2_MPa = excluded.Ec_EC2_MPa,
                    Ec_TCVN5574_MPa = excluded.Ec_TCVN5574_MPa,
                    Ec_AS3600_MPa = excluded.Ec_AS3600_MPa,
                    mean_MPa = excluded.mean_MPa,
                    std_pct = excluded.std_pct,
                    updated_at = datetime('now','localtime')
            """, (grade, fc_cyl,
                  r["Ec_ACI318_MPa"], r["Ec_EC2_MPa"],
                  r["Ec_TCVN5574_MPa"], r["Ec_AS3600_MPa"],
                  r["mean_MPa"], r["std_pct"]))
            n += 1
        con.commit()
    return n


def list_all(db_path: Optional[Path] = None) -> list[dict]:
    """Liệt kê tất cả cấp BT đã lưu."""
    _p = db_path or _DB
    with sqlite3.connect(_p) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT grade_tcvn, fc_MPa,
                   Ec_ACI318_MPa, Ec_EC2_MPa, Ec_TCVN5574_MPa, Ec_AS3600_MPa,
                   mean_MPa, std_pct
            FROM concrete_modulus_table
            ORDER BY fc_MPa
        """).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 90)
    print("MÔ ĐUN ĐÀN HỒI Ec BÊ TÔNG — So sánh 4 tiêu chuẩn")
    print("=" * 90)
    print()
    print(f'{"Cấp B":6s}  {"fc (MPa)":>9s}  '
          f'{"ACI 318":>10s}  {"EC2":>10s}  {"TCVN 5574":>10s}  {"AS 3600":>10s}  '
          f'{"Mean":>10s}  {"σ %":>7s}')
    print('-' * 90)
    for grade, fc in TCVN_B_to_fc_cylinder.items():
        r = compare_all(fc, grade)
        print(f'{grade:6s}  {fc:9.1f}  '
              f'{r["Ec_ACI318_MPa"]:10.0f}  {r["Ec_EC2_MPa"]:10.0f}  '
              f'{r["Ec_TCVN5574_MPa"]:10.0f}  {r["Ec_AS3600_MPa"]:10.0f}  '
              f'{r["mean_MPa"]:10.0f}  {r["std_pct"]:7.2f}')
    print()
    n = save_to_db()
    print(f"Lưu vào SQLite concrete_modulus_table: {n} rows")
    print()
    print("=== Ví dụ tra cứu ===")
    print()
    for fc in [60, 70, 80]:
        r = compare_all(fc)
        print(f"  fc = {fc} MPa  →  Ec ≈ {r['mean_MPa']:.0f} MPa  "
              f"(σ {r['std_pct']:.1f}%) — grade gần nhất: {r['grade_tcvn_guess']}")
