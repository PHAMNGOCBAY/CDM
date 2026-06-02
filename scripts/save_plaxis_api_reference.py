"""
save_plaxis_api_reference.py — Lưu bảng tra cứu PLAXIS API attributes vào SQLite.

Table `plaxis_api_reference` (§65 docs):
  PRIMARY KEY (attribute_name, soil_model)
  cols: writable, value_type, allowed_values, notes, ref_doc

Lưu vào CẢ LOCAL + PROJECT DB.
Chạy: python scripts/save_plaxis_api_reference.py
"""
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DB = _ROOT / "data" / "TTHC.sqlite"
_DB_LOCAL = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")


_ROWS = [
    # (attribute_name, soil_model, writable, value_type, allowed, notes)
    # Common
    ("Identification", "*", 1, "string", "", "Tên material hiển thị"),
    ("SoilModel", "*", 1, "enum",
     "Mohr-Coulomb,Soft Soil,Hardening Soil,HS small,Soft Soil Creep,Linear Elastic",
     "Loại mô hình đất"),
    ("DrainageType", "Mohr-Coulomb", 1, "enum",
     "drained,undraineda,undrainedb,undrainedc,nonporous", "Kiểu thoát nước"),
    ("DrainageType", "Soft Soil", 1, "enum",
     "drained,undraineda", "SS KHÔNG hỗ trợ undrainedb/c"),
    ("gammaUnsat", "*", 1, "float", "", "kN/m³ — dung trọng tự nhiên"),
    ("gammaSat", "*", 1, "float", "", "kN/m³ — dung trọng bão hòa"),
    ("cRef", "*", 1, "float", "", "kN/m² — lực dính, PLAXIS yêu cầu > 0"),
    ("phi", "*", 1, "float", "", "deg — góc ma sát (0 cho undrained)"),
    ("K0Determination", "*", 1, "enum", "", "Phương pháp xác định K0"),
    ("K0Primary", "*", 1, "float", "", ""),
    ("K0Secondary", "*", 1, "float", "", ""),
    # Mohr-Coulomb specific
    ("ERef", "Mohr-Coulomb", 1, "float", "",
     "kN/m² — mô đun đàn hồi. CHÍNH XÁC: ERef KHÔNG phải Eref"),
    ("EOed", "Mohr-Coulomb", 1, "float", "", "kN/m² — mô đun oedometer"),
    ("nu", "Mohr-Coulomb", 1, "float", "", "Poisson"),
    ("psi", "Mohr-Coulomb (drained)", 1, "float", "",
     "deg — góc giãn nở. Read-only khi undrained"),
    ("psi", "Mohr-Coulomb (undrained)", 0, "float", "",
     "READ-ONLY khi DrainageType != drained"),
    # Soft Soil specific
    ("lambdaModified", "Soft Soil", 1, "float", "",
     "λ* = Cc / [2.303 × (1+e₀)]. CHÍNH XÁC: lambdaModified"),
    ("kappaModified", "Soft Soil", 1, "float", "",
     "κ* = Cs / [2.303 × (1+e₀)]. Mặc định λ*/10 nếu thiếu Cs"),
    ("nuUR", "Soft Soil", 1, "float", "0.10..0.20",
     "Poisson unloading-reloading. Mặc định 0.15"),
    ("M", "Soft Soil", 0, "float", "",
     "READ-ONLY. Auto = 6 sin(φ) / (3 - sin(φ))"),
    ("OCR", "Soft Soil", 1, "float", "≥1.0", "Mặc định 1.0 (NC)"),
    ("POP", "Soft Soil", 1, "float", "", "Pre-overburden pressure (kN/m²)"),
    # Borehole + SoilLayer geometry
    ("Head", "Borehole", 1, "float", "",
     "Y elevation của đỉnh BH (top of fill / surface)"),
    ("SoilLayers[i].Zones[bh_idx].Top", "SoilLayer", 0, "float", "",
     "READ-ONLY. Auto = Bottom layer trên hoặc Head cho layer 0"),
    ("SoilLayers[i].Zones[bh_idx].Bottom", "SoilLayer", 1, "float", "",
     "Y của đáy layer cho BH này. Phải monotonic giảm"),
]


def create_and_save(db_path: Path) -> int:
    with sqlite3.connect(db_path) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS plaxis_api_reference (
                attribute_name TEXT NOT NULL,
                soil_model TEXT NOT NULL,
                writable INTEGER,
                value_type TEXT,
                allowed_values TEXT,
                notes TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (attribute_name, soil_model)
            )
        """)
        n = 0
        for row in _ROWS:
            con.execute("""
                INSERT OR REPLACE INTO plaxis_api_reference
                (attribute_name, soil_model, writable, value_type,
                 allowed_values, notes, updated_at)
                VALUES (?,?,?,?,?,?, CURRENT_TIMESTAMP)
            """, row)
            n += 1
        con.commit()
    return n


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    for label, db in (("LOCAL", _DB_LOCAL), ("PROJECT", _DB)):
        if not db.exists() and db == _DB_LOCAL:
            print(f"{label}: skip (not exists)")
            continue
        n = create_and_save(db)
        print(f"{label}: {n} rows saved → {db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
