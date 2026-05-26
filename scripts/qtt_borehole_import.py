"""
qtt_borehole_import.py — Import hố khoan Quảng Trường Trung Tâm TTHC từ DXF.

Zone: QTTTTP — 6 hố khoan ND-02 → ND-07
DB name: QTTTTP-ND-02, ..., QTTTTP-ND-07
Output: data/qtt_boreholes_202605_TTHC.json + TTHC.sqlite
"""

from __future__ import annotations
import json, re, sqlite3

from datetime import datetime
from pathlib import Path

import ezdxf
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT   = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "data" / "TTHC.sqlite"
JSON_OUT = _ROOT / "data" / "qtt_boreholes_202605_TTHC.json"
DXF_PATH = Path(
    r"G:/My Drive/202605-TRUNG TAM HCM/QUANG TRUONG VI DAN/"
    r"HÌNH TRỤ, MC/QTTTTP HCM.Tru- INPUT SQLITE-20260526.dxf"
)

# ── Hằng số DXF ───────────────────────────────────────────────────────────────
ZONE = "QTTTTP"

# X tâm của từng cột BH trong DXF (đều nhau, bước 230 đơn vị)
BH_X_POS = [1379.3, 1609.3, 1839.3, 2069.3, 2299.3, 2529.3]
BH_NAMES  = ["ND-02", "ND-03", "ND-04", "ND-05", "ND-06", "ND-07"]

# Offset từ BH_x đến từng cột phụ trong TextYeutolop
_TY_COLS = {
    "sym":   -46,   # ký hiệu lớp (F, 1, 2, 3, 4)
    "mrl":   -39,   # mRL (cao độ, thường âm)
    "depth": -28,   # độ sâu từ mặt đất (m)
    "thick": -18,   # chiều dày (m)
}
_VALID_SYMBOLS = {"F", "1", "1b", "2", "3", "4", "5", "XMD"}

# Offset tspt từ BH_x
_SPT_DEPTH_XOFF    = 69    # cột ghi độ sâu từ/đến
_SPT_N0_XOFF       = 79    # N_seating (đoạn đầu 15 cm)
_SPT_N1_XOFF       = 84    # N1 (đoạn 2)
_SPT_N2_XOFF       = 89    # N2 (đoạn 3)
_SPT_N_XOFF        = 94    # N = N1 + N2 (giá trị dùng)

_TY_TOL = 10.0   # tolerance x (DXF units) cho TextYeutolop — nearest col wins
_SPT_TOL = 7.0   # tolerance x cho tspt

# Bảng mô tả ký hiệu đất
SYMBOL_DESC: dict[str, dict] = {
    "F":  {"uscs": "F",     "desc": "San lấp, đất đắp"},
    "1":  {"uscs": "CH",    "desc": "Bùn sét, rất dẻo, trạng thái chảy đến dẻo mềm, màu xám xanh"},
    "2":  {"uscs": "CL-CH", "desc": "Sét ít dẻo đến rất dẻo, dẻo cứng đến nửa cứng"},
    "3":  {"uscs": "ML",    "desc": "Cát bụi, kết cấu chặt vừa"},
    "4":  {"uscs": "SM",    "desc": "Cát lẫn bụi, kết cấu chặt vừa đến chặt"},
}


# ── Hàm tiện ích ──────────────────────────────────────────────────────────────

def _bh_index(x: float) -> int:
    """Tìm index BH gần nhất với x (tolerance 115 DXF)."""
    dists = [abs(x - bx) for bx in BH_X_POS]
    idx = int(np.argmin(dists))
    return idx if dists[idx] < 115 else -1


def _try_float(s: str) -> float | None:
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _collect_layer(lyr_name: str, msp) -> list[tuple[float, float, str]]:
    """Thu thập tất cả TEXT/MTEXT trong một layer DXF."""
    out = []
    for e in msp:
        if e.dxf.layer != lyr_name:
            continue
        if e.dxftype() not in ("TEXT", "MTEXT"):
            continue
        try:
            txt = (e.plain_mtext().strip()
                   if e.dxftype() == "MTEXT"
                   else e.dxf.text.strip())
            ins = e.dxf.insert
            out.append((float(ins.x), float(ins.y), txt))
        except Exception:
            pass
    return out


# ── Parse CTTLOKHOAN → header mỗi BH ─────────────────────────────────────────

def parse_headers(msp) -> list[dict]:
    """
    Trả về list 6 dict header BH:
      name, northing_m, easting_m, elevation_m, total_depth_m, date_start, date_end
    """
    texts = _collect_layer("CTTLOKHOAN", msp)

    # Chỉ lấy page 1 (y > 700)
    page1 = [(x, y, t) for x, y, t in texts if y > 700]

    headers: list[dict | None] = [None] * len(BH_X_POS)

    for bh_i, (bh_x, bh_name) in enumerate(zip(BH_X_POS, BH_NAMES)):
        # Filter texts gần cột BH này
        col = [(x, y, t) for x, y, t in page1 if abs(x - bh_x) < 200]

        # Giá trị tìm kiếm theo vị trí y chuẩn:
        # y ≈ 839.6: name
        # y ≈ 786.7: northing
        # y ≈ 783.2: easting
        # y ≈ 786.6: total depth (x = bh_x + 45)
        # y ≈ 783.1: date_start
        # y ≈ 779.7: elevation (x ≈ bh_x - 2) OR date_end (x ≈ bh_x + 38)

        northing = easting = elev = total_depth = None
        date_start = date_end = None
        name = bh_name

        for x, y, t in col:
            # Northing: 7 chữ số bắt đầu bằng 119
            if re.match(r"^119\d{4}\.\d+$", t):
                northing = float(t)
            # Easting: bắt đầu bằng 605 hoặc 606
            elif re.match(r"^60[56]\d{3}\.\d+$", t):
                easting = float(t)
            # Độ sâu tổng (31.00, 33.00, 36.00)
            elif re.match(r"^\d{2}\.\d{2}$", t) and abs(x - (bh_x + 45)) < 15:
                total_depth = float(t)
            # Cao độ mặt đất (dạng "1.700 m")
            elif re.match(r"^\d+\.\d+ m$", t):
                elev_val = _try_float(t.replace(" m", ""))
                if elev_val is not None:
                    elev = elev_val
            # Ngày (dd.mm.yyyy)
            elif re.match(r"^\d{2}\.\d{2}\.\d{4}$", t):
                d_val = datetime.strptime(t, "%d.%m.%Y")
                if date_start is None or d_val < date_start:
                    date_start = d_val
                if date_end is None or d_val > date_end:
                    date_end = d_val

        headers[bh_i] = {
            "name":          name,
            "db_name":       f"{ZONE}-{name}",
            "zone":          ZONE,
            "northing_m":    northing,
            "easting_m":     easting,
            "elevation_m":   elev,
            "total_depth_m": total_depth,
            "date_start":    date_start.strftime("%Y-%m-%d") if date_start else None,
            "date_end":      date_end.strftime("%Y-%m-%d") if date_end else None,
        }

    return [h for h in headers if h is not None]


# ── Parse TextYeutolop → lớp đất mỗi BH ──────────────────────────────────────

def parse_layers(msp, headers: list[dict]) -> dict[str, list[dict]]:
    """
    Trả về dict {db_name: [layer_dict, ...]}.
    Mỗi layer_dict: symbol, uscs, description, depth_top_m, depth_bot_m,
                    thickness_m, mrl_top_m, mrl_bot_m
    """
    texts = _collect_layer("TextYeutolop", msp)
    elev_map = {h["db_name"]: h["elevation_m"] for h in headers}

    result: dict[str, list[dict]] = {}

    for bh_i, (bh_x, bh_name) in enumerate(zip(BH_X_POS, BH_NAMES)):
        db_name = f"{ZONE}-{bh_name}"
        elev = elev_map.get(db_name, 0.0) or 0.0

        # Lấy tất cả texts trong vùng TextYeutolop của BH này
        # (các cột nằm từ BH_x-54 đến BH_x-10)
        col = [(x, y, t) for x, y, t in texts
               if (bh_x - 54) <= x <= (bh_x - 10)]

        # Phân loại bằng "nearest column wins"
        _col_offsets = {k: bh_x + off for k, off in _TY_COLS.items()}

        sym_rows:   dict[float, str]   = {}   # y → symbol (F/1/2/3/4)
        thick_rows: dict[float, float] = {}   # y → thickness
        mrl_rows:   dict[float, float] = {}   # y → mRL (có thể âm)
        depth_rows: dict[float, float] = {}   # y → depth_m (dương)

        for x, y, t in col:
            yr = round(y, 1)
            # Nearest column wins
            dists = {k: abs(x - cx) for k, cx in _col_offsets.items()}
            nearest = min(dists, key=lambda k: dists[k])
            if dists[nearest] > _TY_TOL:
                continue

            if nearest == "sym":
                if t.strip() in _VALID_SYMBOLS:
                    sym_rows[yr] = t.strip()
            elif nearest == "thick":
                v = _try_float(t)
                if v is not None and v > 0:
                    thick_rows[yr] = v
            elif nearest == "mrl":
                v = _try_float(t)
                if v is not None:
                    mrl_rows[yr] = v
            elif nearest == "depth":
                v = _try_float(t)
                if v is not None and v > 0:
                    depth_rows[yr] = v

        # Tìm các y có symbol → đây là header của lớp
        # Loại bỏ y trùng lặp (page 2 = y thấp hơn cùng symbol+thickness)
        sym_y_vals = sorted(sym_rows.keys(), reverse=True)  # cao → thấp

        seen: set[tuple] = set()
        sym_y_dedup: list[float] = []
        for y_val in sym_y_vals:
            sym = sym_rows[y_val]
            thick = thick_rows.get(y_val)
            key = (sym, thick)
            if key not in seen:
                seen.add(key)
                sym_y_dedup.append(y_val)

        # Sắp xếp lại theo y giảm (từ mặt đất xuống)
        sym_y_dedup.sort(reverse=True)

        # Tìm boundary (depth_bot) cho mỗi lớp
        # boundary_rows: các y có cả mRL lẫn depth → boundary giữa hai lớp
        boundary_ys = [y for y in mrl_rows if y in depth_rows]
        boundary_ys.sort(reverse=True)  # y lớn = shallow

        # Xây dựng layers
        layers: list[dict] = []
        depth_cursor = 0.0   # running depth_top (m từ mặt đất)

        for i, sy in enumerate(sym_y_dedup):
            sym = sym_rows[sy]
            thick = thick_rows.get(sy)

            # Tìm boundary y ngay dưới sy (y nhỏ hơn sy)
            bot_y = None
            for by in boundary_ys:
                if by < sy - 1.0:
                    bot_y = by
                    break

            depth_bot = depth_rows.get(bot_y) if bot_y is not None else None
            mrl_bot   = mrl_rows.get(bot_y)   if bot_y is not None else None

            if depth_bot is None and thick is not None:
                depth_bot = round(depth_cursor + thick, 3)

            depth_top = round(depth_cursor, 3)
            if depth_bot is not None:
                thick_calc = round(depth_bot - depth_top, 3)
            else:
                thick_calc = thick

            mrl_top = round(elev - depth_top, 3) if depth_top is not None else None
            mrl_bot_calc = round(elev - depth_bot, 3) if depth_bot is not None else None

            info = SYMBOL_DESC.get(sym, {"uscs": sym, "desc": sym})
            layers.append({
                "symbol":       sym,
                "uscs":         info["uscs"],
                "description":  info["desc"],
                "depth_top_m":  depth_top,
                "depth_bot_m":  depth_bot,
                "thickness_m":  thick_calc,
                "mrl_top_m":    mrl_top,
                "mrl_bot_m":    mrl_bot_calc if mrl_bot_calc else mrl_bot,
            })

            if depth_bot is not None:
                depth_cursor = depth_bot

        result[db_name] = layers

    return result


# ── Parse tspt → SPT values mỗi BH ───────────────────────────────────────────

def parse_spt(msp) -> dict[str, list[dict]]:
    """
    Trả về dict {db_name: [spt_dict, ...]}.
    spt_dict: depth_from_m, depth_to_m, blow_seating, blow_n1, blow_n2, N_value
    """
    texts = _collect_layer("tspt", msp)
    result: dict[str, list[dict]] = {}

    for bh_i, (bh_x, bh_name) in enumerate(zip(BH_X_POS, BH_NAMES)):
        db_name = f"{ZONE}-{bh_name}"

        # Lấy texts gần cột tspt của BH này
        x_lo = bh_x + _SPT_DEPTH_XOFF - _SPT_TOL
        x_hi = bh_x + _SPT_N_XOFF     + _SPT_TOL
        col  = [(x, y, t) for x, y, t in texts if x_lo <= x <= x_hi]

        # Phân loại
        depth_col: dict[float, float] = {}   # y → depth value
        n0_col:    dict[float, float] = {}
        n1_col:    dict[float, float] = {}
        n2_col:    dict[float, float] = {}
        nval_col:  dict[float, float] = {}

        for x, y, t in col:
            yr = round(y, 1)
            v  = _try_float(t)
            if v is None:
                continue
            if abs(x - (bh_x + _SPT_DEPTH_XOFF)) < _SPT_TOL:
                depth_col[yr] = v
            elif abs(x - (bh_x + _SPT_N0_XOFF)) < _SPT_TOL:
                n0_col[yr] = v
            elif abs(x - (bh_x + _SPT_N1_XOFF)) < _SPT_TOL:
                n1_col[yr] = v
            elif abs(x - (bh_x + _SPT_N2_XOFF)) < _SPT_TOL:
                n2_col[yr] = v
            elif abs(x - (bh_x + _SPT_N_XOFF)) < _SPT_TOL:
                nval_col[yr] = v

        # N-value rows: y có n0/n1/n2/nval
        n_ys = sorted(set(n0_col) | set(n1_col) | set(n2_col) | set(nval_col),
                      reverse=True)

        spt_list: list[dict] = []
        for ny in n_ys:
            # depth_from: depth_col ở y cao hơn 1-2 DXF units
            df = None
            for dy in sorted(depth_col, reverse=True):
                if ny < dy < ny + 3.0:
                    val = depth_col[dy]
                    # Lọc: depth_from có phần lẻ .00 hoặc kết thúc là 0
                    if val % 0.5 < 0.01 or val % 0.5 > 0.49:
                        df = val
                        break
            if df is None:
                for dy in sorted(depth_col, reverse=True):
                    if ny - 1 < dy < ny + 4.0:
                        df = depth_col[dy]
                        break
            if df is None:
                continue

            n0 = int(n0_col.get(ny, 0))
            n1 = int(n1_col.get(ny, 0))
            n2 = int(n2_col.get(ny, 0))
            nv = int(nval_col.get(ny, n1 + n2))

            spt_list.append({
                "depth_from_m":  round(df, 2),
                "depth_to_m":    round(df + 0.45, 2),
                "blow_seating":  n0,
                "blow_n1":       n1,
                "blow_n2":       n2,
                "N_value":       nv,
            })

        # Sắp xếp theo độ sâu
        spt_list.sort(key=lambda r: r["depth_from_m"])
        result[db_name] = spt_list

    return result


# ── Parse Mau → mẫu thí nghiệm ───────────────────────────────────────────────

def parse_samples(msp) -> dict[str, list[dict]]:
    """Trả về dict {db_name: [sample_dict, ...]}.
    sample_dict: sample_code, sample_type (U/D), depth_from_m, depth_to_m
    """
    texts = _collect_layer("Mau", msp)
    result: dict[str, list[dict]] = {}

    for bh_i, (bh_x, bh_name) in enumerate(zip(BH_X_POS, BH_NAMES)):
        db_name = f"{ZONE}-{bh_name}"

        # Tọa độ cột sample code và depth range:
        # code:  x ≈ bh_x + 121
        # range: x ≈ bh_x + 115 (depth ranges "X.XX-Y.YY")
        x_lo = bh_x + 100
        x_hi = bh_x + 145
        col = [(x, y, t) for x, y, t in texts if x_lo <= x <= x_hi]

        code_rows:  dict[float, str] = {}   # y → sample code (U1, D1, ...)
        range_rows: dict[float, str] = {}   # y → depth range "X-Y"

        for x, y, t in col:
            yr = round(y, 1)
            if re.match(r"^[UuDd]\d+$", t):
                code_rows[yr] = t.upper()
            elif re.match(r"^\d+\.?\d*-\d+\.?\d*$", t):
                range_rows[yr] = t

        # Pair code với range (nearest y)
        samples: list[dict] = []
        for cy, code in code_rows.items():
            # tìm range gần nhất (trong ±30 DXF)
            best_ry, best_range = None, None
            for ry, rng in range_rows.items():
                if abs(ry - cy) < 30:
                    if best_ry is None or abs(ry - cy) < abs(best_ry - cy):
                        best_ry, best_range = ry, rng
            if best_range is None:
                continue
            parts = best_range.split("-")
            try:
                d_from = float(parts[0])
                d_to   = float(parts[1])
            except (ValueError, IndexError):
                continue
            stype = "U" if code.startswith("U") else "D"
            samples.append({
                "sample_code":  code,
                "sample_type":  stype,
                "depth_from_m": d_from,
                "depth_to_m":   d_to,
            })

        samples.sort(key=lambda r: r["depth_from_m"])
        result[db_name] = samples

    return result


# ── SQLite ────────────────────────────────────────────────────────────────────

def _create_tables(con: sqlite3.Connection) -> None:
    con.execute("PRAGMA journal_mode=WAL")

    # boreholes — thêm zone nếu chưa có
    con.execute("""
        CREATE TABLE IF NOT EXISTS boreholes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            zone        TEXT,
            x_coord_m   REAL,
            y_coord_m   REAL,
            elevation_m REAL,
            total_depth_m REAL,
            date_start  TEXT,
            date_end    TEXT,
            notes       TEXT,
            UNIQUE(name)
        )
    """)
    # Thêm cột nếu phiên bản cũ chưa có
    for col_def in [
        ("zone",          "TEXT"),
        ("date_start",    "TEXT"),
        ("date_end",      "TEXT"),
        ("total_depth_m", "REAL"),
    ]:
        try:
            con.execute(f"ALTER TABLE boreholes ADD COLUMN {col_def[0]} {col_def[1]}")
        except sqlite3.OperationalError:
            pass

    # layers — bảng có sẵn, thêm cột mới nếu cần
    con.execute("""
        CREATE TABLE IF NOT EXISTS layers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            borehole_id     INTEGER NOT NULL REFERENCES boreholes(id),
            symbol          TEXT NOT NULL,
            description     TEXT,
            depth_top_m     REAL,
            depth_bot_m     REAL,
            thickness_m     REAL
        )
    """)
    for col_def in [
        ("uscs",        "TEXT"),
        ("mrl_top_m",   "REAL"),
        ("mrl_bot_m",   "REAL"),
        ("layer_order", "INTEGER"),
        ("updated_at",  "TEXT"),
    ]:
        try:
            con.execute(f"ALTER TABLE layers ADD COLUMN {col_def[0]} {col_def[1]}")
        except sqlite3.OperationalError:
            pass
    # spt_values — bảng có sẵn schema depth_m/N1/N2/N3/N
    con.execute("""
        CREATE TABLE IF NOT EXISTS spt_values (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            borehole_id  INTEGER NOT NULL REFERENCES boreholes(id),
            depth_m      REAL NOT NULL,
            elev_m       REAL,
            N1           INTEGER,
            N2           INTEGER,
            N3           INTEGER,
            N            INTEGER
        )
    """)
    # Thêm cột bổ sung nếu chưa có
    for col_def in [("depth_to_m", "REAL"), ("updated_at", "TEXT")]:
        try:
            con.execute(f"ALTER TABLE spt_values ADD COLUMN {col_def[0]} {col_def[1]}")
        except sqlite3.OperationalError:
            pass
    # qtt_samples (samples riêng cho QTTTTP)
    con.execute("""
        CREATE TABLE IF NOT EXISTS qtt_samples (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            borehole_id     INTEGER NOT NULL REFERENCES boreholes(id),
            sample_code     TEXT,
            sample_type     TEXT,
            depth_from_m    REAL,
            depth_to_m      REAL,
            UNIQUE(borehole_id, sample_code)
        )
    """)
    con.commit()


def save_to_sqlite(
    headers: list[dict],
    layers_map: dict[str, list[dict]],
    spt_map: dict[str, list[dict]],
    samples_map: dict[str, list[dict]],
    db_path: Path = DB_PATH,
) -> None:
    con = sqlite3.connect(str(db_path))
    _create_tables(con)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Lấy zone_id cho QTT (code='QTT', id=4) — tạo nếu chưa có
    row = con.execute("SELECT id FROM zones WHERE code=?", ("QTT",)).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO zones (code, name_vi) VALUES (?,?)",
            ("QTT", "Quảng Trường Trung Tâm"),
        )
        con.commit()
        row = con.execute("SELECT id FROM zones WHERE code=?", ("QTT",)).fetchone()
    zone_id = row[0]

    for h in headers:
        con.execute("""
            INSERT INTO boreholes
                (zone_id, name, zone, x_coord_m, y_coord_m, elevation_m,
                 depth_m, total_depth_m, date_start, date_end, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(name) DO UPDATE SET
                zone_id=excluded.zone_id,
                zone=excluded.zone,
                x_coord_m=excluded.x_coord_m,
                y_coord_m=excluded.y_coord_m,
                elevation_m=excluded.elevation_m,
                depth_m=excluded.depth_m,
                total_depth_m=excluded.total_depth_m,
                date_start=excluded.date_start,
                date_end=excluded.date_end,
                notes=excluded.notes
        """, (
            zone_id, h["db_name"], h["zone"],
            h.get("northing_m"), h.get("easting_m"),
            h.get("elevation_m"),
            h.get("total_depth_m"), h.get("total_depth_m"),
            h.get("date_start"), h.get("date_end"),
            f"DXF import {now}",
        ))
    con.commit()

    # Xoá layers/SPT/samples cũ của zone QTTTTP rồi insert lại
    bh_ids = {}
    for h in headers:
        row = con.execute(
            "SELECT id FROM boreholes WHERE name=?", (h["db_name"],)
        ).fetchone()
        if row:
            bh_ids[h["db_name"]] = row[0]

    for db_name, bh_id in bh_ids.items():
        con.execute("DELETE FROM layers      WHERE borehole_id=?", (bh_id,))
        con.execute("DELETE FROM spt_values  WHERE borehole_id=?", (bh_id,))
        con.execute("DELETE FROM qtt_samples WHERE borehole_id=?", (bh_id,))

    for db_name, lyrs in layers_map.items():
        bh_id = bh_ids.get(db_name)
        if bh_id is None:
            continue
        for i, lyr in enumerate(lyrs):
            con.execute("""
                INSERT INTO layers
                    (borehole_id, symbol, uscs, description,
                     depth_top_m, depth_bot_m, thickness_m,
                     mrl_top_m, mrl_bot_m, layer_order, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                bh_id, lyr["symbol"], lyr["uscs"], lyr["description"],
                lyr["depth_top_m"], lyr["depth_bot_m"], lyr["thickness_m"],
                lyr["mrl_top_m"], lyr["mrl_bot_m"],
                i + 1, now,
            ))

    # Build elevation map for SPT depth→elev
    elev_map_spt = {h["db_name"]: (h.get("elevation_m") or 0.0) for h in headers}

    for db_name, spts in spt_map.items():
        bh_id = bh_ids.get(db_name)
        if bh_id is None:
            continue
        elev_bh = elev_map_spt.get(db_name, 0.0)
        for s in spts:
            # Map to existing schema: N1=blow_seating, N2=blow_n1, N3=blow_n2, N=N_value
            con.execute("""
                INSERT INTO spt_values
                    (borehole_id, depth_m, elev_m, N1, N2, N3, N, depth_to_m, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                bh_id,
                s["depth_from_m"],
                round(elev_bh - s["depth_from_m"], 3),
                s["blow_seating"], s["blow_n1"], s["blow_n2"], s["N_value"],
                s["depth_to_m"],
                now,
            ))

    for db_name, samps in samples_map.items():
        bh_id = bh_ids.get(db_name)
        if bh_id is None:
            continue
        for s in samps:
            con.execute("""
                INSERT INTO qtt_samples
                    (borehole_id, sample_code, sample_type, depth_from_m, depth_to_m)
                VALUES (?,?,?,?,?)
                ON CONFLICT(borehole_id, sample_code) DO NOTHING
            """, (
                bh_id, s["sample_code"], s["sample_type"],
                s["depth_from_m"], s["depth_to_m"],
            ))

    con.commit()
    con.close()


# ── JSON ─────────────────────────────────────────────────────────────────────

def save_to_json(
    headers: list[dict],
    layers_map: dict[str, list[dict]],
    spt_map: dict[str, list[dict]],
    samples_map: dict[str, list[dict]],
    out: Path = JSON_OUT,
) -> None:
    payload = {
        "_meta": {
            "generated":   datetime.now().strftime("%Y-%m-%d"),
            "zone":        ZONE,
            "n_boreholes": len(headers),
            "source":      DXF_PATH.name,
            "description": "Hố khoan Quảng Trường Trung Tâm TTHC HCM — 6 HK ND-02..ND-07",
            "coord_system": "VN-2000, x_coord_m=Northing, y_coord_m=Easting",
        },
        "boreholes": [
            {
                **h,
                "layers":  layers_map.get(h["db_name"], []),
                "spt":     spt_map.get(h["db_name"], []),
                "samples": samples_map.get(h["db_name"], []),
            }
            for h in headers
        ],
    }
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def run_import(dxf_path: Path = DXF_PATH) -> tuple[list[dict], dict, dict, dict]:
    print(f"Đọc DXF: {dxf_path.name}")
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    print("  → parse headers (CTTLOKHOAN)...")
    headers = parse_headers(msp)

    print("  → parse layers (TextYeutolop)...")
    layers_map = parse_layers(msp, headers)

    print("  → parse SPT (tspt)...")
    spt_map = parse_spt(msp)

    print("  → parse samples (Mau)...")
    samples_map = parse_samples(msp)

    return headers, layers_map, spt_map, samples_map


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    headers, layers_map, spt_map, samples_map = run_import()

    # In tóm tắt
    print(f"\n{'='*65}")
    print(f"{'BH':<16} {'N (m)':>12} {'E (m)':>12} {'Elev':>6} {'Depth':>6} {'Layers':>6} {'SPT':>5}")
    print("-" * 65)
    for h in headers:
        db = h["db_name"]
        print(
            f"{db:<16} {h.get('northing_m',0):>12.3f} {h.get('easting_m',0):>12.3f}"
            f" {h.get('elevation_m',0):>6.2f} {h.get('total_depth_m',0):>6.1f}"
            f" {len(layers_map.get(db,[])):>6} {len(spt_map.get(db,[])):>5}"
        )

    print("\nLớp đất chi tiết:")
    for h in headers:
        db = h["db_name"]
        lyrs = layers_map.get(db, [])
        print(f"\n  {db} (elev={h.get('elevation_m',0):.3f}m):")
        for lyr in lyrs:
            print(
                f"    {lyr['symbol']:3s}  {lyr['depth_top_m']:5.2f}→{lyr['depth_bot_m']:5.2f}m"
                f"  ({lyr['thickness_m']:.2f}m)  mRL {lyr.get('mrl_bot_m',0):.2f}m"
                f"  [{lyr['uscs']}]"
            )

    print("\nSPT (top 3 mỗi BH):")
    for h in headers:
        db  = h["db_name"]
        spt = spt_map.get(db, [])
        nonzero = [s for s in spt if s["N_value"] > 0]
        print(f"  {db}: {len(spt)} intervals, N>0: {len(nonzero)}, "
              f"N_max={max((s['N_value'] for s in spt), default=0)}")

    print(f"\nLưu SQLite → {DB_PATH.name}")
    save_to_sqlite(headers, layers_map, spt_map, samples_map)

    print(f"Lưu JSON   → {JSON_OUT.name}")
    save_to_json(headers, layers_map, spt_map, samples_map)

    total_spt = sum(len(v) for v in spt_map.values())
    total_lyr = sum(len(v) for v in layers_map.values())
    print(f"\nXong: {len(headers)} BH, {total_lyr} lớp, {total_spt} SPT readings")
