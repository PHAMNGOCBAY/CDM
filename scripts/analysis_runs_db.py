"""analysis_runs_db.py — Schema thống nhất lưu kết quả mô phỏng địa kỹ thuật.

Mục đích: lưu kết quả của MỌI phương pháp / phần mềm (PLAXIS, FEM2D scikit-fem,
Winkler 1D, giải tích Eurocode, v.v.) vào CÙNG MỘT bảng để so sánh chéo sau này.

Schema:
  analysis_runs
    id              INTEGER PK
    created_at      TEXT     ISO timestamp
    zone            TEXT     'KE' / 'BXN' / 'NHC'
    bh_name         TEXT     'KE-HK1' (NULL nếu không gắn BH)
    method          TEXT     'LE_continuum' / 'MC_plastic' / 'Winkler_PyNite' / 'PLAXIS_PhiCRed' / 'Eurocode_Bishop' ...
    software        TEXT     'scikit-fem' / 'PLAXIS_2D_2024' / 'custom_NumPy' / ...
    version         TEXT     phiên bản lib / commit hash
    label           TEXT     tên ngắn để hiển thị trong UI
    description     TEXT     mô tả tự do
    params_json     TEXT     input parameters (mesh size, material props, BCs)
    output_json     TEXT     output (metric tổng hợp, ví dụ {sigma_yy_min, u_y_min, ...})
    blob_path       TEXT     đường dẫn tới file .npz/.json chứa field arrays full (NULL nếu nhỏ)
    runtime_s       REAL     thời gian chạy
    notes           TEXT

Triết lý:
  - params_json + output_json chứa scalar / dict nhỏ — query JSON1 được
  - blob_path trỏ tới file ngoài cho field arrays lớn (nodes, elements, σ_xx[N], u[N])
  - 1 run = 1 dòng. Comparison = SELECT WHERE method IN (...) AND bh_name=?

Usage:
  from analysis_runs_db import save_run, get_run, list_runs, init_schema
  init_schema()
  run_id = save_run(zone='KE', bh_name='KE-HK1', method='LE_continuum',
                    software='scikit-fem', version='12.0.1',
                    params={'mesh_size': 0.5}, output={'sigma_yy_min_kPa': -123.4},
                    label='LE gravity 50m')
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "TTHC.sqlite"
BLOB_DIR = ROOT / "data" / "analysis_blobs"

DDL = """
CREATE TABLE IF NOT EXISTS analysis_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    zone            TEXT,
    bh_name         TEXT,
    method          TEXT    NOT NULL,
    software        TEXT,
    version         TEXT,
    label           TEXT,
    description     TEXT,
    params_json     TEXT,
    output_json     TEXT,
    blob_path       TEXT,
    runtime_s       REAL,
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_method   ON analysis_runs(method);
CREATE INDEX IF NOT EXISTS idx_runs_zone_bh  ON analysis_runs(zone, bh_name);
CREATE INDEX IF NOT EXISTS idx_runs_created  ON analysis_runs(created_at DESC);
"""


def init_schema(db_path: Path = DB_PATH) -> None:
    """Tạo bảng + index nếu chưa có. Idempotent."""
    BLOB_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(DDL)
        conn.commit()


def save_run(
    *,
    method: str,
    software: str | None = None,
    version: str | None = None,
    zone: str | None = None,
    bh_name: str | None = None,
    label: str | None = None,
    description: str | None = None,
    params: dict | None = None,
    output: dict | None = None,
    blob_path: str | Path | None = None,
    runtime_s: float | None = None,
    notes: str | None = None,
    db_path: Path = DB_PATH,
) -> int:
    """Lưu 1 run, trả về run_id.

    params và output là dict thuần Python (sẽ json.dumps). Số/ndarray nhỏ OK.
    Với field arrays lớn (nodes[N×2], σ_xx[Nelem]) → save .npz ngoài và set blob_path.
    """
    p_json = json.dumps(params, ensure_ascii=False, default=_json_default) if params else None
    o_json = json.dumps(output, ensure_ascii=False, default=_json_default) if output else None
    bp = str(blob_path) if blob_path else None

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO analysis_runs
               (zone, bh_name, method, software, version, label, description,
                params_json, output_json, blob_path, runtime_s, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (zone, bh_name, method, software, version, label, description,
             p_json, o_json, bp, runtime_s, notes),
        )
        conn.commit()
        return cur.lastrowid


def get_run(run_id: int, db_path: Path = DB_PATH) -> dict | None:
    """Đọc 1 run, parse JSON fields tự động."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM analysis_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["params"] = json.loads(d.pop("params_json")) if d["params_json"] else {}
    d["output"] = json.loads(d.pop("output_json")) if d["output_json"] else {}
    return d


def list_runs(
    *,
    zone: str | None = None,
    bh_name: str | None = None,
    method: str | None = None,
    limit: int = 200,
    db_path: Path = DB_PATH,
) -> list[dict]:
    """Liệt kê runs (mới nhất trước). Trả về list[dict] với scalar columns + parsed JSON."""
    sql = "SELECT * FROM analysis_runs WHERE 1=1"
    args: list = []
    if zone:
        sql += " AND zone = ?"; args.append(zone)
    if bh_name:
        sql += " AND bh_name = ?"; args.append(bh_name)
    if method:
        sql += " AND method = ?"; args.append(method)
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, args).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["params"] = json.loads(d.pop("params_json")) if d["params_json"] else {}
        d["output"] = json.loads(d.pop("output_json")) if d["output_json"] else {}
        out.append(d)
    return out


def delete_run(run_id: int, db_path: Path = DB_PATH) -> bool:
    """Xóa 1 run (+ blob file nếu có). Trả True nếu xóa được."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT blob_path FROM analysis_runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return False
        if row[0]:
            try:
                Path(row[0]).unlink(missing_ok=True)
            except OSError:
                pass
        conn.execute("DELETE FROM analysis_runs WHERE id = ?", (run_id,))
        conn.commit()
    return True


def make_blob_path(method: str, ext: str = "npz") -> Path:
    """Sinh đường dẫn blob duy nhất trong data/analysis_blobs/."""
    BLOB_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    micro = int(time.time() * 1e6) % 1_000_000
    return BLOB_DIR / f"{method}_{ts}_{micro:06d}.{ext}"


def _json_default(o):
    """Encoder cho ndarray, datetime."""
    import numpy as np
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (datetime,)):
        return o.isoformat()
    raise TypeError(f"Không JSON-serializable: {type(o)}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true", help="Tạo schema")
    ap.add_argument("--list", action="store_true", help="Liệt kê runs")
    ap.add_argument("--zone", help="Filter zone")
    ap.add_argument("--method", help="Filter method")
    args = ap.parse_args()

    if args.init:
        init_schema()
        print(f"Schema OK: {DB_PATH}")
    if args.list:
        runs = list_runs(zone=args.zone, method=args.method)
        if not runs:
            print("Không có run nào.")
        else:
            print(f"{'id':>4} {'created':<20} {'zone':<5} {'bh':<12} {'method':<20} {'software':<15} {'label'}")
            for r in runs:
                print(f"{r['id']:>4} {r['created_at']:<20} {r['zone'] or '-':<5} "
                      f"{r['bh_name'] or '-':<12} {r['method']:<20} "
                      f"{r['software'] or '-':<15} {r['label'] or ''}")
