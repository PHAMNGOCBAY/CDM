"""
scripts/qtt_zone_data.py — Central loader cho zone QTT.

Truy xuất:
  - 6 hố khoan ND-02..ND-07 (từ SQLite boreholes + tvtk_bh_cdm)
  - Polygon ranh giới (15 đỉnh)
  - 162 điểm grid cao độ
  - Layers + SPT per HK
  - Lab data

API:
  load_zone_meta() → dict tổng hợp toàn zone
  load_borehole(name) → chi tiết 1 HK (header + layers + spt + lab)
  build_qtt_zone_meta_json() → ghi data/qtt_zone_meta.json

Bảng SQLite mới: qtt_zone_summary (1 row per build)
"""
from __future__ import annotations
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
DB_LOCAL = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
DB_PROJ = _ROOT / "data" / "TTHC.sqlite"

SOFT_SYMBOLS = ("1", "1b", "2", "XMD")
ZONE_CODE = "QTT"
ZONE_NAME_VI = "Quảng Trường Trung Tâm"
LOCATION_VI = "Phường An Khánh, Thành phố Thủ Đức, TP. Hồ Chí Minh"
CRS = "VN-2000 / TM-3 106° (EPSG:9210)"


def _db() -> Path:
    return DB_LOCAL if DB_LOCAL.exists() else DB_PROJ


def load_boreholes(db: Optional[Path] = None) -> list[dict]:
    """Tất cả HK QTT (prefix ND-) + thông tin cơ bản."""
    db = db or _db()
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT b.name, b.elevation_m, b.x_coord_m AS N,
                   b.y_coord_m AS E, b.depth_m,
                   t.H_soft_m, t.selected
            FROM boreholes b
            LEFT JOIN tvtk_bh_cdm t ON t.bh_name = b.name
            WHERE b.name LIKE 'ND-%'
            ORDER BY b.name
        """).fetchall()
        return [dict(r) for r in rows]


def load_layers(bh_name: str, db: Optional[Path] = None) -> list[dict]:
    """Địa tầng 1 HK."""
    db = db or _db()
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT symbol, depth_top_m, depth_bot_m, thickness_m, description
            FROM layers
            WHERE borehole_id = (SELECT id FROM boreholes WHERE name = ?)
            ORDER BY depth_top_m
        """, (bh_name,)).fetchall()
        return [dict(r) for r in rows]


def load_spt(bh_name: str, db: Optional[Path] = None) -> list[dict]:
    """SPT samples 1 HK."""
    db = db or _db()
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT depth_m, N, N1, N2, N3
            FROM spt_values
            WHERE borehole_id = (SELECT id FROM boreholes WHERE name = ?)
            ORDER BY depth_m
        """, (bh_name,)).fetchall()
        return [dict(r) for r in rows]


def load_boundary(db: Optional[Path] = None) -> list[dict]:
    """15 đỉnh polygon ranh giới QTT."""
    db = db or _db()
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT vertex_order, easting_m, northing_m
            FROM qtt_cdm_boundary
            ORDER BY vertex_order
        """).fetchall()
        return [dict(r) for r in rows]


def load_grid_summary(db: Optional[Path] = None) -> dict:
    """Tổng quan 162 điểm grid."""
    db = db or _db()
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        r = con.execute("""
            SELECT COUNT(*) AS n,
                   MIN(elev_des_m) AS des_min, MAX(elev_des_m) AS des_max,
                   AVG(elev_des_m) AS des_avg,
                   MIN(elev_nat_m) AS nat_min, MAX(elev_nat_m) AS nat_max,
                   AVG(elev_nat_m) AS nat_avg,
                   MIN(easting_m) AS e_min, MAX(easting_m) AS e_max,
                   MIN(northing_m) AS n_min, MAX(northing_m) AS n_max
            FROM qtt_elevation_points
        """).fetchone()
        return dict(r)


def load_zone_meta(db: Optional[Path] = None) -> dict:
    """Tổng hợp zone — gọn cho UI + Word."""
    db = db or _db()
    bhs = load_boreholes(db)
    boundary = load_boundary(db)
    grid = load_grid_summary(db)

    # H_soft stats
    h_softs = [b["H_soft_m"] for b in bhs if b["H_soft_m"] is not None]
    n_selected = sum(1 for b in bhs if b.get("selected") == 1)

    return {
        "zone_code": ZONE_CODE,
        "zone_name_vi": ZONE_NAME_VI,
        "location_vi": LOCATION_VI,
        "crs": CRS,
        "n_boreholes": len(bhs),
        "n_boreholes_selected": n_selected,
        "boreholes_summary": bhs,
        "boundary_n_vertices": len(boundary),
        "boundary": boundary,
        "grid": grid,
        "H_soft_stats": {
            "min": min(h_softs) if h_softs else None,
            "max": max(h_softs) if h_softs else None,
            "avg": sum(h_softs) / len(h_softs) if h_softs else None,
            "values": {b["name"]: b["H_soft_m"] for b in bhs},
        },
        "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_db": str(db),
    }


def load_borehole_full(bh_name: str, db: Optional[Path] = None) -> dict:
    """Chi tiết 1 HK — header + layers + spt."""
    db = db or _db()
    bhs = {b["name"]: b for b in load_boreholes(db)}
    if bh_name not in bhs:
        raise ValueError(f"HK {bh_name} không có trong zone QTT")
    return {
        "borehole": bhs[bh_name],
        "layers": load_layers(bh_name, db),
        "spt_samples": load_spt(bh_name, db),
    }


# ════════ SQLite — qtt_zone_summary table ════════
def create_zone_summary_table(db: Path) -> None:
    with sqlite3.connect(db) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS qtt_zone_summary (
                zone_code TEXT PRIMARY KEY,
                zone_name_vi TEXT,
                location_vi TEXT,
                crs TEXT,
                n_boreholes INTEGER,
                n_boreholes_selected INTEGER,
                boundary_n_vertices INTEGER,
                grid_n_points INTEGER,
                H_soft_min_m REAL,
                H_soft_max_m REAL,
                H_soft_avg_m REAL,
                elev_des_min_m REAL,
                elev_des_max_m REAL,
                elev_nat_min_m REAL,
                elev_nat_max_m REAL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.commit()


def save_zone_summary_to_db(meta: dict, db: Path) -> None:
    create_zone_summary_table(db)
    hs = meta["H_soft_stats"]
    g = meta["grid"]
    with sqlite3.connect(db) as con:
        con.execute("""
            INSERT OR REPLACE INTO qtt_zone_summary
            (zone_code, zone_name_vi, location_vi, crs,
             n_boreholes, n_boreholes_selected,
             boundary_n_vertices, grid_n_points,
             H_soft_min_m, H_soft_max_m, H_soft_avg_m,
             elev_des_min_m, elev_des_max_m,
             elev_nat_min_m, elev_nat_max_m, updated_at)
            VALUES (?,?,?,?, ?,?, ?,?, ?,?,?, ?,?, ?,?, ?)
        """, (
            meta["zone_code"], meta["zone_name_vi"], meta["location_vi"],
            meta["crs"],
            meta["n_boreholes"], meta["n_boreholes_selected"],
            meta["boundary_n_vertices"], g["n"],
            hs["min"], hs["max"], hs["avg"],
            g["des_min"], g["des_max"],
            g["nat_min"], g["nat_max"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))
        con.commit()


def build_qtt_zone_meta_json(out_path: Optional[Path] = None) -> Path:
    """Build data/qtt_zone_meta.json + lưu SQLite qtt_zone_summary 2 DB."""
    out_path = out_path or (_ROOT / "data" / "qtt_zone_meta.json")
    meta = load_zone_meta()
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    # Save SQLite summary 2 DBs
    for db in (DB_LOCAL, DB_PROJ):
        if db.exists() or db == DB_PROJ:
            save_zone_summary_to_db(meta, db)
    return out_path


# ════════ DEMO ════════
if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(f"=== QTT zone meta ===")
    out = build_qtt_zone_meta_json()
    print(f"JSON: {out} ({out.stat().st_size/1024:.1f} KB)")

    m = load_zone_meta()
    print(f"\nZone: {m['zone_name_vi']}")
    print(f"  Vị trí: {m['location_vi']}")
    print(f"  CRS: {m['crs']}")
    print(f"  Số HK: {m['n_boreholes']} (selected: {m['n_boreholes_selected']})")
    print(f"  Polygon ranh giới: {m['boundary_n_vertices']} đỉnh")
    print(f"  Grid: {m['grid']['n']} điểm")
    print(f"  Cao độ thiết kế: {m['grid']['des_min']:.2f} - {m['grid']['des_max']:.2f} m")
    print(f"  Cao độ tự nhiên: {m['grid']['nat_min']:.2f} - {m['grid']['nat_max']:.2f} m")
    print(f"  H_soft: min={m['H_soft_stats']['min']:.2f}, "
          f"avg={m['H_soft_stats']['avg']:.2f}, "
          f"max={m['H_soft_stats']['max']:.2f} m")
    print(f"\nSQLite qtt_zone_summary: đã ghi LOCAL + PROJECT")
