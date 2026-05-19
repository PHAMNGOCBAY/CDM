"""
Import borehole log (stratigraphy) data from DXF hình trụ files into TTHC.sqlite.

Reads TEXT / MTEXT entities from GBS-formatted borehole log DXF files and extracts:
  - Borehole header: name, elevation, UTM coordinates, total depth
  - Soil layers: layer_no, depth_top_m, depth_bot_m, description
  - SPT data: depth_m, N_value (sum of last 2 intervals)

Target DB: data/TTHC.sqlite
New tables created if absent:
  strat_layers (id, borehole_id, layer_no, depth_top_m, depth_bot_m, description)
  spt_tests    (id, borehole_id, depth_from_m, depth_to_m, N1, N2, N3, N_value)
"""

import os
import re
import sqlite3
import math
from collections import defaultdict
from pathlib import Path

import ezdxf

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path(r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN")
DB_PATH = BASE / "data" / "TTHC.sqlite"
DEPLOY_DB = BASE / "cdm-deploy" / "data" / "TTHC.sqlite"

DXF_FILES = {
    "NHC": Path(r"G:\My Drive\202605-TRUNG TAM HCM\DIA CHAT\2. NHÀ HÀNH CHÍNH\NHC-1. TRỤ_TTHC_Tru hien truong.dxf"),
    "KE":  Path(r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\DIA CHAT\3. KÈ (CÔNG VIÊN)\BOKE-1. TRỤ_260512 CVTT-TTHC. Tru DC.dxf"),
}

ZONE_CODES = {"NHC": 3, "BXN": 2, "KE": 1}

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_or_create_db(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def _ensure_tables(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS strat_layers (
            id           INTEGER PRIMARY KEY,
            borehole_id  INTEGER NOT NULL REFERENCES boreholes(id),
            layer_no     INTEGER,
            depth_top_m  REAL NOT NULL,
            depth_bot_m  REAL NOT NULL,
            description  TEXT,
            UNIQUE(borehole_id, depth_top_m)
        );
        CREATE TABLE IF NOT EXISTS spt_tests (
            id           INTEGER PRIMARY KEY,
            borehole_id  INTEGER NOT NULL REFERENCES boreholes(id),
            depth_from_m REAL NOT NULL,
            depth_to_m   REAL NOT NULL,
            N1           INTEGER,
            N2           INTEGER,
            N3           INTEGER,
            N_value      INTEGER,
            UNIQUE(borehole_id, depth_from_m)
        );
    """)
    con.commit()


def _get_borehole_id(con: sqlite3.Connection, zone_id: int, bh_name: str,
                     elevation_m: float | None = None,
                     x_utm: float | None = None,
                     y_utm: float | None = None) -> int:
    row = con.execute("SELECT id FROM boreholes WHERE name = ?", (bh_name,)).fetchone()
    if row:
        bid = row["id"]
        # Update elevation/coords if not set
        if elevation_m is not None:
            con.execute(
                "UPDATE boreholes SET elevation_m = COALESCE(elevation_m, ?) WHERE id = ?",
                (elevation_m, bid),
            )
        return bid
    con.execute(
        "INSERT INTO boreholes (zone_id, name, elevation_m) VALUES (?, ?, ?)",
        (zone_id, bh_name, elevation_m),
    )
    con.commit()
    return con.execute("SELECT id FROM boreholes WHERE name = ?", (bh_name,)).fetchone()["id"]


def _upsert_layer(con: sqlite3.Connection, borehole_id: int, layer_no: int | None,
                  depth_top_m: float, depth_bot_m: float, description: str | None) -> None:
    con.execute("""
        INSERT INTO strat_layers (borehole_id, layer_no, depth_top_m, depth_bot_m, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(borehole_id, depth_top_m) DO UPDATE SET
            layer_no    = COALESCE(layer_no,    excluded.layer_no),
            depth_bot_m = COALESCE(depth_bot_m, excluded.depth_bot_m),
            description = COALESCE(description, excluded.description)
    """, (borehole_id, layer_no, round(depth_top_m, 2), round(depth_bot_m, 2), description))


def _upsert_spt(con: sqlite3.Connection, borehole_id: int,
                depth_from: float, depth_to: float,
                n1: int | None, n2: int | None, n3: int | None) -> None:
    if n2 is not None and n3 is not None:
        n_val = n2 + n3
    elif n2 is not None:
        n_val = n2  # incomplete test: N3 not recorded
    else:
        n_val = None
    con.execute("""
        INSERT INTO spt_tests (borehole_id, depth_from_m, depth_to_m, N1, N2, N3, N_value)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(borehole_id, depth_from_m) DO NOTHING
    """, (borehole_id, round(depth_from, 2), round(depth_to, 2), n1, n2, n3, n_val))


# ---------------------------------------------------------------------------
# DXF parsing helpers
# ---------------------------------------------------------------------------

# NHC: BH-03 / BH-05 ...   KE: HK1 / HK2 ...
_RE_BH = re.compile(r"^(BH-\d+|HK\d+)$")
_RE_FLOAT = re.compile(r"^-?\d+\.\d+$")
_RE_INT = re.compile(r"^\d+$")
_RE_SPT_INTERVAL = re.compile(r"^\d+\.\d{2}-\d+\.\d{2}$")  # e.g. "2.00-2.45"
_RE_SAMPLE_LABEL = re.compile(r"^[UDN]\d+$")               # U1, D1, N1 etc.


def _collect_texts(msp) -> list[tuple[float, float, str, str]]:
    """Return list of (x, y, text, etype) for all non-empty TEXT / MTEXT."""
    items = []
    for e in msp:
        if e.dxftype() == "TEXT":
            txt = e.dxf.text.strip()
            if txt:
                items.append((e.dxf.insert.x, e.dxf.insert.y, txt, "TEXT"))
        elif e.dxftype() == "MTEXT":
            txt = e.plain_text().strip()
            if txt:
                items.append((e.dxf.insert.x, e.dxf.insert.y, txt, "MTEXT"))
    return items


def _cluster_x(xs: list[float], tol: float = 3.0) -> list[list[float]]:
    """Group x values that are within tol of each other."""
    if not xs:
        return []
    xs = sorted(xs)
    groups: list[list[float]] = [[xs[0]]]
    for x in xs[1:]:
        if x - groups[-1][-1] <= tol:
            groups[-1].append(x)
        else:
            groups.append([x])
    return groups


def _find_borehole_columns(all_texts: list[tuple]) -> dict[str, float]:
    """Return {bh_name: x_column_center} using BH-XX texts at max y (page 1 header)."""
    bh_texts = [(x, y, t) for x, y, t, _ in all_texts if _RE_BH.match(t)]
    if not bh_texts:
        return {}

    max_y = max(y for _, y, _ in bh_texts)
    header_y_min = max_y - 200

    # Keep only high-y headers (page 1)
    headers = [(x, y, t) for x, y, t in bh_texts if y >= header_y_min]

    # For each bh_name, take the leftmost x (depth column side)
    by_name: dict[str, list[float]] = defaultdict(list)
    for x, y, t in headers:
        by_name[t].append(x)

    result = {}
    for name, xs in by_name.items():
        result[name] = min(xs)  # leftmost = depth column
    return result


def _build_depth_map(all_texts: list[tuple], x_col: float,
                     x_tol: float = 20.0) -> list[tuple[float, float]]:
    """
    Build (y, depth_m) pairs from integer depth tick marks in the column.
    Returns list sorted by y descending (high y = small depth).

    Handles multi-page borehole logs: each page has its own y-offset, so the
    same depth value (e.g. 20m) appears at different y positions on consecutive
    pages.  The approach is to build per-page SEGMENTS where consecutive ticks
    have scale ≈ 10 DXF units/m.  A new segment starts when depth goes
    backwards or stays the same (page break) or scale is way off (noise).
    """
    ticks = []
    for x, y, t, etype in all_texts:
        if abs(x - x_col) > x_tol:
            continue
        if not _RE_INT.match(t):
            continue
        val = int(t)
        if val > 100:
            continue
        ticks.append((y, float(val)))

    if not ticks:
        return []

    # Sort by y descending (shallowest = highest y first)
    ticks.sort(key=lambda p: -p[0])

    # Split into per-page segments.  Within a segment, consecutive pairs have
    # scale ≈ 10 DXF units / m.  A page break shows as dd == 0 (same depth
    # repeated at a lower y on the next page) or dd < 0 (layer numbers snuck
    # in).  When a break is detected, start a new segment.
    segments: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []

    for y, d in ticks:
        if not current:
            current = [(y, d)]
            continue
        y_last, d_last = current[-1]
        dy = y_last - y
        dd = d - d_last

        if dd <= 0:
            # Page break (dd=0) or backwards (layer# snuck in, dd<0)
            if len(current) >= 2:
                segments.append(current)
            current = [(y, d)]
        elif dy < 0:
            # y went up — shouldn't happen in descending sort, skip
            continue
        else:
            scale = dy / dd
            if abs(scale - 10.0) <= 3.0:
                current.append((y, d))
            # else: bad scale entry (noise) — skip

    if len(current) >= 2:
        segments.append(current)

    # Flatten all segments; within each segment pairs are ordered by y desc
    result: list[tuple[float, float]] = []
    for seg in segments:
        result.extend(seg)
    # Already y-descending within each segment; resort globally
    result.sort(key=lambda p: -p[0])
    return result


def _interp_depth(y: float, depth_map: list[tuple[float, float]]) -> float | None:
    """
    Interpolate depth from y using depth tick map.

    Only interpolates (or extrapolates) within a VALID page segment — i.e. a
    pair of consecutive entries whose Δy/Δd ≈ 10 (the expected scale).
    Page-break gaps between segments are never used for interpolation.
    """
    if not depth_map:
        return None

    SCALE = 10.0
    SCALE_TOL = 3.0

    def _valid_pair(ya: float, da: float, yb: float, db: float) -> bool:
        """True if (ya,da)→(yb,db) belongs to the same page (scale ≈ 10)."""
        if ya <= yb or db <= da:
            return False
        return abs((ya - yb) / (db - da) - SCALE) <= SCALE_TOL

    # 1. Try direct interpolation inside a valid pair
    for i in range(len(depth_map) - 1):
        y_hi, d_lo = depth_map[i]
        y_lo, d_hi = depth_map[i + 1]
        if not _valid_pair(y_hi, d_lo, y_lo, d_hi):
            continue
        if y_lo <= y <= y_hi:
            frac = (y_hi - y) / (y_hi - y_lo)
            return d_lo + frac * (d_hi - d_lo)

    # 2. Extrapolate from the nearest valid pair
    best_dist = float("inf")
    best_result = None
    for i in range(len(depth_map) - 1):
        y_hi, d_lo = depth_map[i]
        y_lo, d_hi = depth_map[i + 1]
        if not _valid_pair(y_hi, d_lo, y_lo, d_hi):
            continue
        dist = min(abs(y - y_hi), abs(y - y_lo))
        if dist < best_dist:
            best_dist = dist
            scale = (y_hi - y_lo) / (d_hi - d_lo)
            best_result = d_lo + (y_hi - y) / scale

    return best_result


_PROJECT_KEYWORDS = {
    "quảng trường", "trung tâm hành chính", "phường an khánh",
    "thủ đức", "tp. hcm", "nguyễn văn", "vũ sơn",
}


def _is_soil_desc(txt: str) -> bool:
    tl = txt.lower()
    if any(k in tl for k in _PROJECT_KEYWORDS):
        return False
    if "hố khoan kết thúc" in tl:
        return False
    # Must contain soil keywords OR be a long descriptive text
    SOIL_KW = ["sét", "cát", "sỏi", "bùn", "than bùn", "đất", "lấp", "hữu cơ",
               "cứng", "dẻo", "chảy", "xốp", "chặt", "nâu", "xám", "xanh"]
    return any(k in tl for k in SOIL_KW)


def _parse_borehole_column(
    bh_name: str, x_col: float, all_texts: list[tuple],
    all_bh_cols: dict[str, float] | None = None,
    x_width: float = 250.0,
) -> dict:
    """
    Parse one borehole column from all_texts.
    Returns dict with keys: elevation_m, x_utm, y_utm, total_depth_m, layers, spt

    Key insight: layer bottom depth text values appear at y-coordinates corresponding
    to their actual depth (bot_depth_val ≈ depth_from_y). Thickness/elevation texts
    appear at y positions that do NOT match their value, so we filter by:
        |text_value - depth_from_y(text_y)| < 2.0 m
    """
    # Filter to this column's x range.
    # For most boreholes the ~250-unit wide range naturally captures one column.
    # Closely spaced pairs (BH-27/BH-28 at x_col ± 1) share entities; both get
    # the same data, which is acceptable given identical sheet positions.
    col_texts = [
        (x, y, t, etype)
        for x, y, t, etype in all_texts
        if x_col - 50 <= x <= x_col + x_width
    ]

    # ---- Header info (high-y region) ----
    max_y = max((y for _, y, _, _ in col_texts), default=0)
    header_y_thresh = max_y - 120
    header_texts = [(x, y, t) for x, y, t, _ in col_texts if y >= header_y_thresh]

    elevation_m = None
    x_utm = None
    y_utm = None
    total_depth_m = None

    for x, y, t in header_texts:
        if not _RE_FLOAT.match(t):
            continue
        val = float(t)
        if 1_100_000 < val < 1_300_000:
            y_utm = val
        elif 550_000 < val < 700_000:
            x_utm = val
        elif val in (30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0):
            total_depth_m = val
        elif -5.0 < val < 20.0 and abs(x - x_col) < 50:
            elevation_m = val

    # ---- Depth tick map ----
    # Find depth tick column dynamically by locating the "0" integer text
    # just below the page 1 header (the shallowest depth tick).
    # This avoids confusing layer-number texts (never 0) with depth ticks.
    zero_xs = [
        x for x, y, t, et in col_texts
        if et == "TEXT" and t.strip() == "0"
        and header_y_thresh - 120 < y < header_y_thresh
        and x_col - 70 < x < x_col - 5
    ]
    depth_tick_x = min(zero_xs) if zero_xs else x_col - 30
    # Use narrow x_tol (8) so layer-number column (~16 units right) is excluded
    depth_map = _build_depth_map(col_texts, depth_tick_x, x_tol=8)
    if len(depth_map) < 3:
        depth_map = _build_depth_map(col_texts, depth_tick_x, x_tol=15)

    # ---- Soil descriptions (MTEXT in description column) ----
    soil_descs = []  # (y, text)
    for x, y, t, etype in col_texts:
        if etype == "MTEXT" and _is_soil_desc(t) and y < header_y_thresh:
            if x_col - 20 <= x <= x_col + 80:
                soil_descs.append((y, t))
    soil_descs.sort(key=lambda p: -p[0])

    # ---- Layer bottom depths ----
    # NHC format: label y matches depth_from_y within ±2.0 m
    # KE format:  label at x_col-35..x_col-5, value is the actual depth (label
    #             positioned at mid-layer y, NOT matching depth_from_y)
    bot_depth_candidates: list[float] = []

    # Strategy A (NHC): label position matches depth value
    for x, y, t, etype in col_texts:
        if etype != "TEXT" or not _RE_FLOAT.match(t):
            continue
        if not (x_col - 20 <= x <= x_col + 30):
            continue
        if y >= header_y_thresh:
            continue
        val = float(t)
        if val <= 0 or val > 105:
            continue
        depth_y = _interp_depth(y, depth_map)
        if depth_y is not None and abs(val - depth_y) < 2.0:
            bot_depth_candidates.append(round(val, 2))

    # Strategy B (KE): label at left column (x_col-35..x_col-5), value IS the depth
    if not bot_depth_candidates:
        seen_vals: set[float] = set()
        for x, y, t, etype in col_texts:
            if etype != "TEXT" or not _RE_FLOAT.match(t):
                continue
            if not (x_col - 35 <= x <= x_col - 5):
                continue
            if y >= header_y_thresh:
                continue
            val = float(t)
            if val <= 0 or val > 120:
                continue
            if val > 10000:  # UTM coords
                continue
            seen_vals.add(round(val, 2))
        bot_depth_candidates = list(seen_vals)

    bot_depths = sorted(set(bot_depth_candidates))

    # ---- Build layer skeletons ----
    layers: list[dict] = []
    top = 0.0
    for i, bot in enumerate(bot_depths):
        layers.append({
            "layer_no": i + 1,
            "depth_top_m": round(top, 2),
            "depth_bot_m": round(bot, 2),
            "description": None,
        })
        top = bot

    # ---- Match soil descriptions to layers (pass 1: depth_map from ticks) ----
    for y_desc, txt in soil_descs:
        depth_d = _interp_depth(y_desc, depth_map)
        if depth_d is None:
            continue
        for lyr in layers:
            if lyr["depth_top_m"] - 1.0 <= depth_d < lyr["depth_bot_m"] + 1.0:
                if lyr["description"] is None:
                    lyr["description"] = txt
                break

    # ---- SPT data ----
    # KE format: 4 blow counts (N_prep, N1, N2, N3) at x_col+70..+100, y_tol=8
    # NHC format: 3 blow counts at x_col+100..+170, sorted+dedup
    spt: list[dict] = []
    spt_intervals = []
    for x, y, t, etype in col_texts:
        if etype == "TEXT" and _RE_SPT_INTERVAL.match(t):
            if x_col + 60 <= x <= x_col + 180 and y < header_y_thresh:
                spt_intervals.append((y, t))

    spt_intervals.sort(key=lambda p: -p[0])

    for y_spt, interval in spt_intervals:
        parts = interval.split("-")
        if len(parts) != 2:
            continue
        try:
            d_from, d_to = float(parts[0]), float(parts[1])
        except ValueError:
            continue

        # Collect blow counts with x position for ordering
        bc_xy = []
        for x, y, t, etype in col_texts:
            if etype == "TEXT" and _RE_INT.match(t):
                if abs(y - y_spt) < 8 and x_col + 60 <= x <= x_col + 170:
                    bc = int(t)
                    if bc < 100:
                        bc_xy.append((x, bc))
        bc_xy.sort(key=lambda p: p[0])  # sort by x position left→right

        if len(bc_xy) >= 4:
            # KE format: N_prep(skip), N1, N2, N3 — N_value = N2+N3
            unique_x = []
            for bx, bv in bc_xy:
                if not unique_x or abs(bx - unique_x[-1][0]) > 2:
                    unique_x.append((bx, bv))
            vals = [v for _, v in unique_x]
            # skip first (N_prep/seating), keep next 3
            n1 = vals[1] if len(vals) > 1 else None
            n2 = vals[2] if len(vals) > 2 else None
            n3 = vals[3] if len(vals) > 3 else None
        else:
            # NHC format: sorted unique → N1, N2, N3
            vals_sorted = sorted(set(v for _, v in bc_xy))
            n1 = vals_sorted[0] if len(vals_sorted) > 0 else None
            n2 = vals_sorted[1] if len(vals_sorted) > 1 else None
            n3 = vals_sorted[2] if len(vals_sorted) > 2 else None

        if all(n == 0 for n in [n1, n2, n3] if n is not None):
            continue

        spt.append({"depth_from_m": d_from, "depth_to_m": d_to,
                    "N1": n1, "N2": n2, "N3": n3})

    # ---- Match soil descriptions (pass 2: SPT-derived calibration for KE) ----
    # When depth_map is empty (KE has no standard tick column), build a multi-page
    # depth_map from SPT interval y positions and reuse _interp_depth.
    if not any(lyr["description"] for lyr in layers) and spt:
        spt_calib: list[tuple[float, float]] = []
        for s in spt:
            y_s = next(
                (y for y, t in spt_intervals
                 if t.split("-")[0] == f"{s['depth_from_m']:.2f}"),
                None,
            )
            if y_s is not None:
                spt_calib.append((y_s, s["depth_from_m"]))
        spt_calib.sort(key=lambda p: -p[0])  # y descending = depth ascending

        # Build depth_map keeping only same-page consecutive pairs (scale ≈ 10)
        depth_map_spt: list[tuple[float, float]] = []
        for i in range(len(spt_calib) - 1):
            y_a, d_a = spt_calib[i]
            y_b, d_b = spt_calib[i + 1]
            if d_b > d_a and y_a > y_b:
                scale_pair = (y_a - y_b) / (d_b - d_a)
                if abs(scale_pair - 10.0) <= 3.0:
                    if not depth_map_spt or depth_map_spt[-1] != (y_a, d_a):
                        depth_map_spt.append((y_a, d_a))
                    depth_map_spt.append((y_b, d_b))

        if depth_map_spt:
            for y_desc, txt in soil_descs:
                depth_d = _interp_depth(y_desc, depth_map_spt)
                if depth_d is None:
                    continue
                for lyr in layers:
                    if lyr["depth_top_m"] - 1.0 <= depth_d < lyr["depth_bot_m"] + 1.0:
                        if lyr["description"] is None:
                            lyr["description"] = txt
                        break

    return {
        "elevation_m": elevation_m,
        "x_utm": x_utm,
        "y_utm": y_utm,
        "total_depth_m": total_depth_m,
        "layers": layers,
        "spt": spt,
    }


# ---------------------------------------------------------------------------
# Main import function
# ---------------------------------------------------------------------------

def import_dxf(zone_key: str, dxf_path: Path, con: sqlite3.Connection) -> dict:
    """Import one DXF file. Returns summary dict."""
    zone_id = ZONE_CODES[zone_key]
    prefix = zone_key  # e.g. "NHC"

    print(f"Reading DXF: {dxf_path.name} ...")
    doc = ezdxf.readfile(str(dxf_path), errors="surrogateescape")
    msp = doc.modelspace()

    all_texts = _collect_texts(msp)
    print(f"  Total text entities: {len(all_texts)}")

    # Find borehole columns
    bh_cols = _find_borehole_columns(all_texts)
    print(f"  Boreholes found: {sorted(bh_cols.keys())}")

    # Clear existing stratigraphy for this zone before re-importing
    bh_ids = [r[0] for r in con.execute(
        "SELECT b.id FROM boreholes b JOIN zones z ON b.zone_id=z.id WHERE z.code=?",
        (zone_key,),
    ).fetchall()]
    if bh_ids:
        ph = ",".join("?" * len(bh_ids))
        con.execute(f"DELETE FROM strat_layers WHERE borehole_id IN ({ph})", bh_ids)
        con.execute(f"DELETE FROM spt_tests    WHERE borehole_id IN ({ph})", bh_ids)
        con.commit()
        print(f"  Cleared existing strat/SPT data for {len(bh_ids)} boreholes in {zone_key}")

    summary = {"boreholes": {}}
    layers_total = 0
    spt_total = 0

    for bh_name in sorted(bh_cols.keys(), key=lambda n: (len(n), n)):
        x_col = bh_cols[bh_name]
        # NHC: prefix="NHC", bh_name="BH-03" → "NHC-BH-03"
        # KE:  prefix="KE",  bh_name="HK1"   → "KE-HK1"
        db_name = f"{prefix}-{bh_name}"

        result = _parse_borehole_column(bh_name, x_col, all_texts, all_bh_cols=bh_cols)

        print(f"  {db_name}: elev={result['elevation_m']}m, "
              f"{len(result['layers'])} layers, {len(result['spt'])} SPT")
        if result["layers"]:
            for lyr in result["layers"]:
                print(f"    [{lyr['depth_top_m']}-{lyr['depth_bot_m']}m] {lyr['description'][:60] if lyr['description'] else '(no desc)'}")

        # Save to DB
        bid = _get_borehole_id(
            con, zone_id, db_name,
            elevation_m=result["elevation_m"],
            x_utm=result["x_utm"],
            y_utm=result["y_utm"],
        )

        for lyr in result["layers"]:
            _upsert_layer(con, bid, lyr["layer_no"],
                          lyr["depth_top_m"], lyr["depth_bot_m"], lyr["description"])

        for spt in result["spt"]:
            _upsert_spt(con, bid, spt["depth_from_m"], spt["depth_to_m"],
                        spt["N1"], spt["N2"], spt["N3"])

        con.commit()

        summary["boreholes"][db_name] = {
            "n_layers": len(result["layers"]),
            "n_spt": len(result["spt"]),
            "elevation_m": result["elevation_m"],
        }
        layers_total += len(result["layers"])
        spt_total += len(result["spt"])

    summary["total_layers"] = layers_total
    summary["total_spt"] = spt_total
    return summary


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    con = _get_or_create_db(DB_PATH)
    _ensure_tables(con)

    all_summary = {}
    for zone_key, dxf_path in DXF_FILES.items():
        if not dxf_path.exists():
            print(f"File not found: {dxf_path}")
            continue
        summary = import_dxf(zone_key, dxf_path, con)
        all_summary[zone_key] = summary

    con.close()

    # Sync to deploy
    import shutil
    shutil.copy2(DB_PATH, DEPLOY_DB)
    print(f"\nSynced to {DEPLOY_DB}")

    # Write summary JSON
    out_json = BASE / "data" / "strat_import_summary.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_summary, f, ensure_ascii=False, indent=2)
    print(f"Summary: {out_json}")
    print(json.dumps(all_summary, ensure_ascii=False, indent=2))
