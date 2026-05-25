"""
ke_cdm_dist.py — Khoảng cách từ hố khoan Kè KE đến tim cọc CDM gần nhất
            theo phương vuông góc với trục tuyến kè.

Phương pháp:
  1. Xác định trục tuyến kè bằng PCA của 8 HK trên tuyến kè SW.
  2. Chiếu vector BH→CDM lên trục tuyến (thành phần dọc) và vuông góc
     (thành phần ngang / transverse).
  3. "Gần nhất theo phương vuông góc" = cọc CDM có |d_perp| nhỏ nhất.
  4. Lưu kết quả vào SQLite `ke_cdm_distances` + JSON snapshot.

Quy ước tọa độ:
  - SQLite boreholes: x_coord_m = Northing, y_coord_m = Easting
  - SQLite cdm_toado: northing_m, easting_m
  - Array shape: row = [Northing, Easting]
"""

from __future__ import annotations
import json
import sqlite3
import math
from pathlib import Path
from datetime import datetime

import numpy as np

_ROOT   = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "data" / "TTHC.sqlite"
JSON_OUT = _ROOT / "data" / "ke_cdm_distances_202605_TTHC.json"

# HK trên tuyến kè SW (dùng để tính trục PCA)
ALIGNMENT_BHS = frozenset({
    "KE-HK2", "KE-HK3", "KE-HK6", "KE-HK7",
    "KE-HK8", "KE-HK9", "KE-HK10", "KE-HK11",
})


# ── Trục tuyến kè (PCA) ──────────────────────────────────────────────────────

def calc_ke_axis_pca(bhs: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """PCA của các HK trên tuyến → (unit_axis_vec, centroid).

    Trả về:
      axis_u : unit vector theo hướng tuyến kè (dài nhất)
      ref_pt : centroid các HK trên tuyến (điểm gốc tọa độ cục bộ)
    """
    pts = np.array([[b["northing"], b["easting"]] for b in bhs], dtype=float)
    ref = pts.mean(axis=0)
    centered = pts - ref
    _, _, Vt = np.linalg.svd(centered, full_matrices=False)
    axis_u = Vt[0]            # first PC = trục tuyến kè
    return axis_u, ref


def perp_vec(axis_u: np.ndarray) -> np.ndarray:
    """Vectơ đơn vị vuông góc với trục tuyến (xoay 90° CCW)."""
    return np.array([-axis_u[1], axis_u[0]])


# ── Tải dữ liệu từ SQLite ─────────────────────────────────────────────────────

def _load_boreholes(db_path: Path) -> list[dict]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT name,
               x_coord_m  AS northing,
               y_coord_m  AS easting,
               elevation_m
        FROM boreholes
        WHERE name LIKE 'KE-%' AND x_coord_m IS NOT NULL
        ORDER BY name
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


def _load_cdm_toado(db_path: Path, zone: str = "KE") -> tuple[np.ndarray, list[str]]:
    """Tải tất cả tọa độ CDM zone KE.  Trả (array Nx2 [N,E], names)."""
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT point_name, northing_m, easting_m
        FROM cdm_toado WHERE zone = ?
        ORDER BY point_name
    """, (zone,)).fetchall()
    con.close()
    pts   = np.array([[r["northing_m"], r["easting_m"]] for r in rows], dtype=float)
    names = [r["point_name"] for r in rows]
    return pts, names


def _load_alignment_flag(db_path: Path) -> dict[str, bool]:
    """Đọc on_sw_alignment từ ke_sw_202605_TTHC.json (nếu có)."""
    import json as _json
    ke_json = _ROOT / "data" / "ke_sw_202605_TTHC.json"
    if not ke_json.exists():
        return {}
    data = _json.loads(ke_json.read_text(encoding="utf-8"))
    return {
        f"KE-{b['name']}": bool(b.get("on_sw_alignment"))
        for b in data.get("boreholes", [])
    }


# ── Tính khoảng cách ──────────────────────────────────────────────────────────

def calc_cdm_distances(db_path: Path = DB_PATH) -> tuple[list[dict], dict]:
    """Tính khoảng cách BH → CDM gần nhất theo phương vuông góc với trục kè.

    Returns:
      results   : list[dict] per borehole
      axis_info : dict ghi lại thông số trục PCA (để debug / vẽ bình đồ)
    """
    bhs       = _load_boreholes(db_path)
    cdm_pts, cdm_names = _load_cdm_toado(db_path, zone="KE")
    align_map = _load_alignment_flag(db_path)

    # Tính trục PCA từ các HK trên tuyến kè
    align_bhs = [b for b in bhs if b["name"] in ALIGNMENT_BHS]
    axis_u, ref_pt = calc_ke_axis_pca(align_bhs)
    axis_n = perp_vec(axis_u)       # phương vuông góc với tuyến kè

    # KDTree cho lookup nhanh (fallback: brute-force nếu scipy không có)
    try:
        from scipy.spatial import cKDTree
        tree = cKDTree(cdm_pts)
        _use_kdtree = True
    except ImportError:
        _use_kdtree = False

    results = []
    for bh in bhs:
        bh_pt  = np.array([bh["northing"], bh["easting"]], dtype=float)
        bh_vec = bh_pt - ref_pt                     # vector từ centroid → BH

        # Chainage (dọc tuyến) và offset (vuông góc tuyến) của BH
        bh_chainage = float(np.dot(bh_vec, axis_u))
        bh_offset   = float(np.dot(bh_vec, axis_n))

        # Vector BH → mỗi CDM point
        vecs       = cdm_pts - bh_pt                # shape (N, 2)
        dists_eucl = np.linalg.norm(vecs, axis=1)

        # Thành phần vuông góc (transverse) và dọc tuyến
        dists_perp  = (vecs @ axis_n)               # có dấu (+/-)
        dists_along = (vecs @ axis_u)

        # ── Nearest by perpendicular distance (|d_perp| nhỏ nhất) ────────────
        idx_perp = int(np.argmin(np.abs(dists_perp)))
        # ── Nearest by Euclidean distance ────────────────────────────────────
        idx_eucl = int(np.argmin(dists_eucl))

        results.append({
            "bh_name":              bh["name"],
            "on_alignment":         bh["name"] in ALIGNMENT_BHS,
            "bh_northing_m":        round(float(bh["northing"]), 3),
            "bh_easting_m":         round(float(bh["easting"]),  3),
            "chainage_m":           round(bh_chainage, 2),
            "bh_offset_m":          round(bh_offset,   2),

            # ── Gần nhất theo vuông góc ──────────────────────────────────────
            "nearest_cdm_perp_name":     cdm_names[idx_perp],
            "nearest_cdm_perp_north_m":  round(float(cdm_pts[idx_perp, 0]), 3),
            "nearest_cdm_perp_east_m":   round(float(cdm_pts[idx_perp, 1]), 3),
            "dist_perp_m":               round(float(dists_perp[idx_perp]),  2),
            "dist_perp_abs_m":           round(abs(float(dists_perp[idx_perp])), 2),
            "dist_along_at_perp_m":      round(float(dists_along[idx_perp]), 2),
            "dist_eucl_at_perp_m":       round(float(dists_eucl[idx_perp]),  2),

            # ── Gần nhất theo Euclid (tham khảo) ────────────────────────────
            "nearest_cdm_eucl_name":     cdm_names[idx_eucl],
            "nearest_cdm_eucl_north_m":  round(float(cdm_pts[idx_eucl, 0]), 3),
            "nearest_cdm_eucl_east_m":   round(float(cdm_pts[idx_eucl, 1]), 3),
            "dist_eucl_m":               round(float(dists_eucl[idx_eucl]), 2),
            "dist_perp_at_eucl_m":       round(abs(float(dists_perp[idx_eucl])), 2),
            "dist_along_at_eucl_m":      round(float(dists_along[idx_eucl]),  2),
        })

    axis_info = {
        "axis_u":   axis_u.tolist(),
        "axis_n":   axis_n.tolist(),
        "ref_pt":   ref_pt.tolist(),          # [Northing, Easting]
        "ref_north_m": float(ref_pt[0]),
        "ref_east_m":  float(ref_pt[1]),
    }
    return results, axis_info


# ── SQLite ────────────────────────────────────────────────────────────────────

def create_table(db_path: Path = DB_PATH) -> None:
    """Tạo bảng ke_cdm_distances (idempotent)."""
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""
        CREATE TABLE IF NOT EXISTS ke_cdm_distances (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            bh_name                  TEXT NOT NULL,
            on_alignment             INTEGER,
            bh_northing_m            REAL,
            bh_easting_m             REAL,
            chainage_m               REAL,
            bh_offset_m              REAL,
            nearest_cdm_perp_name    TEXT,
            nearest_cdm_perp_north_m REAL,
            nearest_cdm_perp_east_m  REAL,
            dist_perp_m              REAL,
            dist_perp_abs_m          REAL,
            dist_along_at_perp_m     REAL,
            dist_eucl_at_perp_m      REAL,
            nearest_cdm_eucl_name    TEXT,
            nearest_cdm_eucl_north_m REAL,
            nearest_cdm_eucl_east_m  REAL,
            dist_eucl_m              REAL,
            dist_perp_at_eucl_m      REAL,
            dist_along_at_eucl_m     REAL,
            updated_at               TEXT,
            UNIQUE(bh_name)
        )
    """)
    con.commit()
    con.close()


def save_to_sqlite(results: list[dict], db_path: Path = DB_PATH) -> None:
    create_table(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    for r in results:
        con.execute("""
            INSERT OR REPLACE INTO ke_cdm_distances
            (bh_name, on_alignment, bh_northing_m, bh_easting_m,
             chainage_m, bh_offset_m,
             nearest_cdm_perp_name, nearest_cdm_perp_north_m, nearest_cdm_perp_east_m,
             dist_perp_m, dist_perp_abs_m, dist_along_at_perp_m, dist_eucl_at_perp_m,
             nearest_cdm_eucl_name, nearest_cdm_eucl_north_m, nearest_cdm_eucl_east_m,
             dist_eucl_m, dist_perp_at_eucl_m, dist_along_at_eucl_m,
             updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            r["bh_name"], int(r["on_alignment"]),
            r["bh_northing_m"], r["bh_easting_m"],
            r["chainage_m"], r["bh_offset_m"],
            r["nearest_cdm_perp_name"],
            r["nearest_cdm_perp_north_m"], r["nearest_cdm_perp_east_m"],
            r["dist_perp_m"], r["dist_perp_abs_m"],
            r["dist_along_at_perp_m"], r["dist_eucl_at_perp_m"],
            r["nearest_cdm_eucl_name"],
            r["nearest_cdm_eucl_north_m"], r["nearest_cdm_eucl_east_m"],
            r["dist_eucl_m"], r["dist_perp_at_eucl_m"], r["dist_along_at_eucl_m"],
            now,
        ))
    con.commit()
    con.close()


def save_to_json(results: list[dict], axis_info: dict,
                 out_path: Path = JSON_OUT) -> None:
    payload = {
        "_meta": {
            "generated":    datetime.now().strftime("%Y-%m-%d"),
            "description":  "Khoảng cách hố khoan KE → tim cọc CDM gần nhất theo phương vuông góc",
            "method":       "PCA của 8 HK trên tuyến kè → trục u + pháp tuyến n; d_perp = proj(BH→CDM, n)",
            "zone":         "KE",
            "cdm_source":   "SQLite cdm_toado WHERE zone='KE'",
            "bh_source":    "SQLite boreholes WHERE name LIKE 'KE-%'",
        },
        "axis_pca": axis_info,
        "boreholes": results,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Public helper — load results from SQLite ──────────────────────────────────

def load_cdm_distances(db_path: Path = DB_PATH) -> dict[str, dict]:
    """Đọc ke_cdm_distances từ SQLite → dict {bh_name: row_dict}."""
    try:
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM ke_cdm_distances ORDER BY bh_name").fetchall()
        con.close()
        return {dict(r)["bh_name"]: dict(r) for r in rows}
    except Exception:
        return {}


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("Tính khoảng cách BH → CDM gần nhất theo phương vuông góc...")
    results, axis_info = calc_cdm_distances()

    print(f"\nTrục kè PCA:")
    print(f"  axis_u = ({axis_info['axis_u'][0]:.4f}, {axis_info['axis_u'][1]:.4f})  [Northing, Easting]")
    print(f"  ref_pt = N={axis_info['ref_north_m']:.1f}  E={axis_info['ref_east_m']:.1f}")

    print(f"\n{'BH':<12} {'Chainage':>10} {'Offset':>8}  {'d_perp':>8}  {'CDM gần nhất (perp)':>20}  {'d_eucl':>8}")
    print("-" * 80)
    for r in results:
        flag = "*" if r["on_alignment"] else " "
        print(
            f"{flag}{r['bh_name']:<11} {r['chainage_m']:>10.1f} {r['bh_offset_m']:>8.1f}  "
            f"{r['dist_perp_abs_m']:>8.2f}  {r['nearest_cdm_perp_name']:>20}  "
            f"{r['dist_eucl_m']:>8.2f}"
        )

    save_to_sqlite(results)
    save_to_json(results, axis_info)
    print(f"\nĐã lưu {len(results)} hố khoan → SQLite ke_cdm_distances + {JSON_OUT.name}")
