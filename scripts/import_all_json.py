"""
import_all_json.py — Import toàn bộ *.json trong data/ vào SQLite.

Bảng SQLite chính: `json_imports`
    file_name       TEXT PK
    rel_path        TEXT  (đường dẫn tương đối từ data/)
    json_content    TEXT  (raw JSON string — dùng json_extract() để query)
    n_records       INTEGER  (số top-level entries nếu là list, hoặc null)
    keys_top        TEXT  (top-level keys, vd "_meta,boreholes")
    file_size       INTEGER
    file_mtime      TEXT
    imported_at     TEXT

Query example:
    SELECT json_extract(json_content, '$._meta.source')
    FROM json_imports WHERE file_name='thuyvan_phuan_summary.json';

Public API:
    import_all_json(db_path=None, data_dir=None) -> dict
    list_imported_files(db_path=None) -> list[dict]
    get_json(file_name, db_path=None) -> dict | None
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
_DB   = _ROOT / "data" / "TTHC.sqlite"
_DATA = _ROOT / "data"


def create_table(db_path: Optional[Path] = None) -> None:
    """Tạo bảng json_imports (idempotent)."""
    _p = db_path or _DB
    with sqlite3.connect(_p) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS json_imports (
                file_name       TEXT PRIMARY KEY,
                rel_path        TEXT,
                json_content    TEXT,
                n_records       INTEGER,
                keys_top        TEXT,
                file_size       INTEGER,
                file_mtime      TEXT,
                imported_at     TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        con.commit()


def _summarize(obj) -> tuple[int | None, str]:
    """Đếm số records + lấy top-level keys."""
    if isinstance(obj, list):
        return (len(obj), "")
    if isinstance(obj, dict):
        return (None, ",".join(list(obj.keys())[:8]))
    return (None, "")


def import_all_json(db_path: Optional[Path] = None,
                    data_dir: Optional[Path] = None,
                    pattern: str = "**/*.json",
                    skip_size_kb: int = 5000) -> dict:
    """Import tất cả *.json trong data_dir vào bảng json_imports.

    Args:
        db_path:      mặc định _DB
        data_dir:     mặc định _DATA
        pattern:      glob pattern, mặc định '**/*.json' (recursive)
        skip_size_kb: bỏ qua file lớn hơn N KB (mặc định 5MB)

    Returns:
        {'imported': int, 'skipped_large': int, 'failed': int, 'files': list}
    """
    _p   = db_path or _DB
    _dir = data_dir or _DATA
    create_table(_p)

    n_ok = n_skip = n_fail = 0
    files: list[dict] = []

    with sqlite3.connect(_p) as con:
        for f in sorted(_dir.glob(pattern)):
            if not f.is_file():
                continue
            size_kb = f.stat().st_size / 1024
            rel = f.relative_to(_dir).as_posix()

            # Bỏ qua file lớn
            if size_kb > skip_size_kb:
                n_skip += 1
                files.append({"file": f.name, "rel": rel,
                              "size_kb": round(size_kb, 1),
                              "status": "skipped (too large)"})
                continue

            try:
                content = f.read_text(encoding="utf-8")
                obj = json.loads(content)
                n_rec, keys_top = _summarize(obj)
                mtime = datetime.fromtimestamp(f.stat().st_mtime).isoformat(
                    sep=" ", timespec="seconds")

                con.execute("""
                    INSERT INTO json_imports
                        (file_name, rel_path, json_content, n_records,
                         keys_top, file_size, file_mtime, imported_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                    ON CONFLICT (file_name) DO UPDATE SET
                        rel_path = excluded.rel_path,
                        json_content = excluded.json_content,
                        n_records = excluded.n_records,
                        keys_top = excluded.keys_top,
                        file_size = excluded.file_size,
                        file_mtime = excluded.file_mtime,
                        imported_at = datetime('now','localtime')
                """, (f.name, rel, content, n_rec, keys_top,
                      f.stat().st_size, mtime))
                n_ok += 1
                files.append({
                    "file": f.name, "rel": rel,
                    "size_kb": round(size_kb, 1),
                    "n_records": n_rec, "keys": keys_top[:60],
                    "status": "OK",
                })
            except json.JSONDecodeError as e:
                n_fail += 1
                files.append({"file": f.name, "rel": rel,
                              "size_kb": round(size_kb, 1),
                              "status": f"JSON parse fail: {e}"})
            except Exception as e:
                n_fail += 1
                files.append({"file": f.name, "rel": rel,
                              "size_kb": round(size_kb, 1),
                              "status": f"Error: {e}"})
        con.commit()

    return {
        "imported": n_ok,
        "skipped_large": n_skip,
        "failed": n_fail,
        "files": files,
    }


def list_imported_files(db_path: Optional[Path] = None) -> list[dict]:
    """Liệt kê các file JSON đã import."""
    _p = db_path or _DB
    with sqlite3.connect(_p) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT file_name, rel_path, n_records, keys_top,
                   file_size, file_mtime, imported_at
            FROM json_imports
            ORDER BY file_name
        """).fetchall()
    return [dict(r) for r in rows]


def get_json(file_name: str, db_path: Optional[Path] = None) -> dict | None:
    """Lấy nội dung JSON từ SQLite (thay vì đọc file)."""
    _p = db_path or _DB
    with sqlite3.connect(_p) as con:
        r = con.execute(
            "SELECT json_content FROM json_imports WHERE file_name=?",
            (file_name,)
        ).fetchone()
        if r and r[0]:
            try:
                return json.loads(r[0])
            except json.JSONDecodeError:
                return None
    return None


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    # Import tất cả JSON cho cả 3 DB
    for db_label, db_path in [
        ("Worktree", _DB),
        ("Main local (TTHC_local)", Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")),
        ("Cloud deploy", _ROOT.parent.parent.parent.parent / "cdm-deploy" / "data" / "TTHC.sqlite"),
    ]:
        if not db_path.exists():
            print(f"\n=== {db_label}: {db_path} → SKIP (not exist) ===")
            continue
        print(f"\n=== Import vào {db_label}: {db_path} ===")
        try:
            r = import_all_json(db_path=db_path)
            print(f"  Imported: {r['imported']}  |  Skipped (large): {r['skipped_large']}  |  Failed: {r['failed']}")
            # Show first 5 + last 5
            ok_files = [f for f in r["files"] if f["status"] == "OK"]
            print(f"  Tong file OK: {len(ok_files)}")
            for f in ok_files[:5]:
                n = f"{f['n_records']} records" if f.get('n_records') else f"keys: {f.get('keys','')}"
                print(f"    {f['file']:50s}  {f['size_kb']:6.1f} KB  {n}")
            if len(ok_files) > 10:
                print(f"    ... ({len(ok_files)-10} more)")
            for f in ok_files[-5:]:
                n = f"{f['n_records']} records" if f.get('n_records') else f"keys: {f.get('keys','')}"
                print(f"    {f['file']:50s}  {f['size_kb']:6.1f} KB  {n}")
            # Failed
            failed = [f for f in r["files"] if "OK" not in f["status"]]
            if failed:
                print(f"  Failed ({len(failed)}):")
                for f in failed[:5]:
                    print(f"    {f['file']:50s}  {f['status']}")
        except Exception as e:
            print(f"  FAIL: {e}")
