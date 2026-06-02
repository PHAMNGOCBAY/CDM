"""
save_cushion_params.py — Đồng bộ JSON ↔ SQLite cho đệm cát-XM.

Single source of truth: data/cdm_cushion_params.json
Bảng SQLite: cdm_cushion_design_params (idempotent INSERT OR REPLACE)

Mỗi lần chạy:
  1. Đọc JSON `params` block
  2. Xoá toàn bộ rows cũ trong SQLite (clean slate)
  3. INSERT lại từ JSON
  4. Ghi cả LOCAL + PROJECT DB
"""
from __future__ import annotations
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
JSON_FILE = _ROOT / "data" / "cdm_cushion_params.json"
DB_LOCAL = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
DB_PROJ = _ROOT / "data" / "TTHC.sqlite"


def create_table(db: Path) -> None:
    with sqlite3.connect(db) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS cdm_cushion_design_params (
                param_key TEXT NOT NULL PRIMARY KEY,
                param_value REAL,
                unit TEXT,
                source TEXT,
                notes TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.commit()


def sync_from_json(db: Path, params: dict, ts: str) -> int:
    """Wipe + reinsert SQLite from JSON params block."""
    create_table(db)
    with sqlite3.connect(db) as con:
        con.execute("DELETE FROM cdm_cushion_design_params")
        for key, p in params.items():
            con.execute("""
                INSERT INTO cdm_cushion_design_params
                (param_key, param_value, unit, source, notes, updated_at)
                VALUES (?,?,?,?,?,?)
            """, (key, p["value"], p["unit"], p["source"], p["name"], ts))
        con.commit()
        return con.execute(
            "SELECT COUNT(*) FROM cdm_cushion_design_params"
        ).fetchone()[0]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

    if not JSON_FILE.exists():
        print(f"ERROR: JSON nguồn không tồn tại — {JSON_FILE}")
        return 1

    js = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    params = js.get("params", {})
    if not params:
        print(f"ERROR: JSON không có khoá 'params'")
        return 1

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for label, db in (("LOCAL", DB_LOCAL), ("PROJECT", DB_PROJ)):
        if not db.exists() and db == DB_LOCAL:
            print(f"{label}: skip (DB không tồn tại)")
            continue
        n = sync_from_json(db, params, ts)
        print(f"{label}: {n} params synced → {db}")
    print(f"\nNguồn: {JSON_FILE}")
    print(f"Timestamp: {ts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
