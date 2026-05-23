"""Import tuyến metro từ DXF → JSON + SQLite (idempotent).

Nguồn: G:/My Drive/202605-TRUNG TAM HCM/PNBAY-TUYENMETRO INPUTSQLTIE.dxf
Hệ tọa độ DXF: VN-2000 mét (x = Easting, y = Northing)

Output:
  - data/metro_lines_202605_TTHC.json  (debug snapshot)
  - SQLite: bảng metro_lines (idempotent — DELETE source rồi INSERT lại)

Phân loại theo layer DXF → cột `category` để bản đồ tô màu/style khác nhau:
  | DXF layer                          | category          | Mô tả                  |
  |------------------------------------|-------------------|------------------------|
  | 主线左线xl (Chinese)                | centerline        | Tuyến chính metro      |
  | 00.TEDIS-RANHKIEMSOATXD            | boundary_control  | Ranh kiểm soát XD      |
  | 00.RANHGPMBTHUHOIDAT               | boundary_land     | Ranh GPMB thu hồi đất  |
  | Xref_STATION-HCMC2E$...            | boundary_station  | Ranh ga (Xref)         |
  | 4                                  | aux_tunnel        | Tường tunnel           |
  | PAN New                            | aux_panel         | Tường panel            |
  | (khác)                             | other             |                        |

Chạy: python scripts/metro_lines_import.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("Thiếu ezdxf. Chạy: pip install ezdxf", file=sys.stderr)
    sys.exit(1)

_ROOT = Path(__file__).resolve().parent.parent
_DXF  = Path(r"G:/My Drive/202605-TRUNG TAM HCM/PNBAY-TUYENMETRO INPUTSQLTIE.dxf")
_JSON = _ROOT / "data" / "metro_lines_202605_TTHC.json"
_DB   = _ROOT / "data" / "TTHC.sqlite"
_SRC  = "PNBAY-TUYENMETRO INPUTSQLTIE.dxf"


# Mapping layer DXF → category
def _categorize(layer: str) -> str:
    if "主线" in layer:
        return "centerline"
    if "TEDIS-RANHKIEMSOATXD" in layer:
        return "boundary_control"
    if "RANHGPMBTHUHOIDAT" in layer:
        return "boundary_land"
    if layer.startswith("Xref_STATION") or "STATION" in layer.upper():
        return "boundary_station"
    if layer == "4":
        return "aux_tunnel"
    if layer == "PAN New":
        return "aux_panel"
    return "other"


# ── Schema ───────────────────────────────────────────────────────────────────
def create_table(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS metro_lines (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            polyline_id INTEGER NOT NULL,
            vertex_idx  INTEGER NOT NULL,
            x_m         REAL    NOT NULL,
            y_m         REAL    NOT NULL,
            layer       TEXT    NOT NULL,
            category    TEXT    NOT NULL,
            closed      INTEGER DEFAULT 0,
            source      TEXT    NOT NULL,
            UNIQUE(polyline_id, vertex_idx, source)
        )
    """)
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_metro_lines_cat ON metro_lines(category)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_metro_lines_pl ON metro_lines(polyline_id, vertex_idx)"
    )


# ── Parser ───────────────────────────────────────────────────────────────────
def parse_dxf(dxf_path: Path) -> list[dict]:
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    rows: list[dict] = []
    for pl_idx, e in enumerate(msp.query("LWPOLYLINE")):
        layer    = e.dxf.layer
        category = _categorize(layer)
        closed   = 1 if e.closed else 0
        for v_idx, p in enumerate(e.get_points()):
            x, y = float(p[0]), float(p[1])
            rows.append({
                "polyline_id": pl_idx,
                "vertex_idx":  v_idx,
                "x_m":         round(x, 3),
                "y_m":         round(y, 3),
                "layer":       layer,
                "category":    category,
                "closed":      closed,
            })
    return rows


# ── Save JSON ────────────────────────────────────────────────────────────────
def save_json(rows: list[dict]) -> None:
    _JSON.parent.mkdir(parents=True, exist_ok=True)
    # Thống kê category
    from collections import Counter
    cat_count = Counter(r["category"] for r in rows)
    pl_count  = Counter(
        r["category"]
        for r in rows
        if r["vertex_idx"] == 0  # mỗi polyline đếm 1 lần
    )
    payload = {
        "_meta": {
            "source":    _SRC,
            "updated":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "n_vertex":  len(rows),
            "n_polyline": len({r["polyline_id"] for r in rows}),
            "crs":       "VN-2000",
            "vertex_by_category":   dict(cat_count),
            "polyline_by_category": dict(pl_count),
            "note": (
                "x_m = Easting, y_m = Northing (VN-2000). Convention giống "
                "ke_binhdo_toadoke. Khi transform sang WGS-84: "
                "trf.transform(x_m, y_m) với always_xy=True."
            ),
        },
        "vertices": rows,
    }
    _JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Save SQLite ──────────────────────────────────────────────────────────────
def save_sqlite(rows: list[dict], db_path: Path = _DB) -> None:
    con = sqlite3.connect(db_path)
    try:
        create_table(con)
        # Idempotent: xóa source cũ rồi insert lại
        con.execute("DELETE FROM metro_lines WHERE source = ?", (_SRC,))
        con.executemany(
            """INSERT INTO metro_lines
               (polyline_id, vertex_idx, x_m, y_m, layer, category, closed, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (r["polyline_id"], r["vertex_idx"], r["x_m"], r["y_m"],
                 r["layer"], r["category"], r["closed"], _SRC)
                for r in rows
            ],
        )
        con.commit()
    finally:
        con.close()


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    if not _DXF.exists():
        print(f"[ERROR] Không tìm thấy file DXF: {_DXF}", file=sys.stderr)
        sys.exit(2)

    print(f"[1/3] Đọc DXF: {_DXF.name}")
    rows = parse_dxf(_DXF)
    n_pl = len({r["polyline_id"] for r in rows})
    print(f"      → {n_pl} polyline, {len(rows)} vertex")

    # Tóm tắt theo category
    from collections import Counter
    cat_v = Counter(r["category"] for r in rows)
    cat_p = Counter(r["category"] for r in rows if r["vertex_idx"] == 0)
    print("\n  Phân loại (polyline / vertex):")
    for c in sorted(cat_v):
        print(f"    - {c:<20}: {cat_p[c]:>3} / {cat_v[c]:>5}")

    print(f"\n[2/3] Lưu JSON: {_JSON.relative_to(_ROOT)}")
    save_json(rows)

    print(f"[3/3] Cập nhật SQLite: {_DB.relative_to(_ROOT)}")
    save_sqlite(rows)

    print("\nHoàn tất.")


if __name__ == "__main__":
    main()
