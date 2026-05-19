"""
Tính khoảng cách giữa các hố khoan và kiểm tra theo TCCS 41:2022 Điều 5.3.2.

Hàm công khai:
- calc_pairwise_distances(bhs)                    → list[dict], sort theo distance_m
- check_spacing_532(bhs, design_step, same_zone)  → dict kết quả + summary
- create_borehole_distances_table(db_path)         → None (idempotent)
- save_distances_to_db(bhs, design_step, db_path) → int số hàng ghi
"""
import math
import sqlite3
from itertools import combinations
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).parent
_DB   = _HERE.parent / "data" / "TTHC.sqlite"

# TCCS41 Điều 5.3.2 — giới hạn khoảng cách hố khoan
SPACING_LIMITS: dict[str, dict] = {
    "LAPDA": {
        "min_m": 250.0,
        "max_m": 500.0,
        "label": "Lập dự án đầu tư — Điều 5.3.2.1",
        "min_bh_cross_section": 1,
    },
    "BVTK": {
        "min_m": 100.0,
        "max_m": 150.0,
        "label": "Bước BVTK — dọc tuyến — Điều 5.3.2.2",
        "min_bh_cross_section": 3,
    },
    "BVTK_matcat": {
        "min_m": 150.0,
        "max_m": 300.0,
        "label": "BVTK — khoảng cách giữa các mặt cắt — Điều 5.3.2.2",
        "min_bh_cross_section": 3,
    },
}


def _dist_2d(b1: dict, b2: dict) -> float:
    """Khoảng cách nằm ngang 2D giữa 2 hố khoan (m)."""
    return math.hypot(
        b1["x_coord_m"] - b2["x_coord_m"],
        b1["y_coord_m"] - b2["y_coord_m"],
    )


def calc_pairwise_distances(bhs: list[dict]) -> list[dict]:
    """
    Tính khoảng cách từng cặp hố khoan.

    Input: list[dict] với keys: name, zone, x_coord_m, y_coord_m
    Output: list[dict] sort theo distance_m tăng dần.
    """
    result = []
    for b1, b2 in combinations(bhs, 2):
        d = _dist_2d(b1, b2)
        result.append({
            "bh1":       b1["name"],
            "bh2":       b2["name"],
            "zone1":     b1.get("zone", ""),
            "zone2":     b2.get("zone", ""),
            "same_zone": b1.get("zone") == b2.get("zone"),
            "distance_m": round(d, 1),
            "dx_m":       round(b2["x_coord_m"] - b1["x_coord_m"], 1),
            "dy_m":       round(b2["y_coord_m"] - b1["y_coord_m"], 1),
            "x1": b1["x_coord_m"], "y1": b1["y_coord_m"],
            "x2": b2["x_coord_m"], "y2": b2["y_coord_m"],
        })
    result.sort(key=lambda r: r["distance_m"])
    return result


def check_spacing_532(
    bhs: list[dict],
    design_step: str = "BVTK",
    same_zone_only: bool = True,
) -> dict:
    """
    Kiểm tra khoảng cách hố khoan vs TCCS41 Điều 5.3.2.

    Returns dict:
      design_step, limit_label, limit_min_m, limit_max_m,
      pairs: [{bh1, bh2, zone1, zone2, distance_m, compliant, status, ...}],
      summary: {n_pairs, n_ok, n_too_close, n_too_far, min_dist_m, max_dist_m}
    """
    lim  = SPACING_LIMITS.get(design_step, SPACING_LIMITS["BVTK"])
    dmin = lim["min_m"]
    dmax = lim["max_m"]

    pairs = calc_pairwise_distances(bhs)
    if same_zone_only:
        pairs = [p for p in pairs if p["same_zone"]]

    checked = []
    for p in pairs:
        d = p["distance_m"]
        if d < dmin:
            status, ok = "Gần quá", False
        elif d > dmax:
            status, ok = "Xa quá", False
        else:
            status, ok = "Đạt", True
        checked.append({
            **p,
            "compliant":   ok,
            "status":      status,
            "limit_min_m": dmin,
            "limit_max_m": dmax,
        })

    dists = [c["distance_m"] for c in checked]
    return {
        "design_step":  design_step,
        "limit_label":  lim["label"],
        "limit_min_m":  dmin,
        "limit_max_m":  dmax,
        "pairs":        checked,
        "summary": {
            "n_pairs":     len(checked),
            "n_ok":        sum(1 for c in checked if c["compliant"]),
            "n_too_close": sum(1 for c in checked if c["status"] == "Gần quá"),
            "n_too_far":   sum(1 for c in checked if c["status"] == "Xa quá"),
            "min_dist_m":  min(dists) if dists else None,
            "max_dist_m":  max(dists) if dists else None,
        },
    }


def create_borehole_distances_table(db_path: Optional[Path] = None) -> None:
    """Tạo bảng borehole_distances trong SQLite (idempotent)."""
    db = db_path or _DB
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS borehole_distances (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            bh1_name     TEXT NOT NULL,
            bh2_name     TEXT NOT NULL,
            zone1        TEXT,
            zone2        TEXT,
            distance_m   REAL NOT NULL,
            dx_m         REAL,
            dy_m         REAL,
            design_step  TEXT,
            limit_min_m  REAL,
            limit_max_m  REAL,
            compliant    INTEGER,
            status       TEXT,
            created_at   TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(bh1_name, bh2_name, design_step)
        )
    """)
    conn.commit()
    conn.close()


def save_distances_to_db(
    bhs: list[dict],
    design_step: str = "BVTK",
    db_path: Optional[Path] = None,
    same_zone_only: bool = True,
) -> int:
    """Tính và lưu khoảng cách vào SQLite. Trả về số hàng đã ghi."""
    db = db_path or _DB
    create_borehole_distances_table(db)
    result = check_spacing_532(bhs, design_step, same_zone_only)
    conn = sqlite3.connect(db)
    n = 0
    for p in result["pairs"]:
        conn.execute("""
            INSERT OR REPLACE INTO borehole_distances
              (bh1_name, bh2_name, zone1, zone2, distance_m, dx_m, dy_m,
               design_step, limit_min_m, limit_max_m, compliant, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            p["bh1"], p["bh2"], p["zone1"], p["zone2"],
            p["distance_m"], p["dx_m"], p["dy_m"],
            design_step, p["limit_min_m"], p["limit_max_m"],
            int(p["compliant"]), p["status"],
        ))
        n += 1
    conn.commit()
    conn.close()
    return n


if __name__ == "__main__":
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    bhs = [dict(r) for r in conn.execute(
        "SELECT b.name, z.code zone, b.x_coord_m, b.y_coord_m "
        "FROM boreholes b JOIN zones z ON z.id=b.zone_id "
        "WHERE b.x_coord_m IS NOT NULL"
    ).fetchall()]
    conn.close()

    for step in ("LAPDA", "BVTK"):
        res = check_spacing_532(bhs, step)
        s   = res["summary"]
        print(f"\n{res['limit_label']} ({res['limit_min_m']:.0f}–{res['limit_max_m']:.0f} m):")
        print(f"  Tổng cặp: {s['n_pairs']} | Đạt: {s['n_ok']} | "
              f"Gần quá: {s['n_too_close']} | Xa quá: {s['n_too_far']}")
        if s["min_dist_m"] is not None:
            print(f"  Khoảng cách: {s['min_dist_m']:.1f} – {s['max_dist_m']:.1f} m")
        n = save_distances_to_db(bhs, step)
        print(f"  Đã lưu {n} cặp vào borehole_distances")
