# -*- coding: utf-8 -*-
"""
import_nhc_layers.py — Import địa tầng 16 hố khoan NHC từ DXF.

DXF: G:/My Drive/202605-TRUNG TAM HCM/DIA CHAT/2. NHÀ HÀNH CHÍNH/
      NHC-1. TRỤ_TTHC_Tru hien truong.dxf

Cấu trúc DXF (xác nhận từ scan thực tế):
  - BH header: text dạng "BH-xx" tại y≈71645, x=x_bh
  - Depth ticks: x_off≈-29.6, integer 0..100 (scale 10 DXF/m)
  - Layer symbol: x_off≈-17.6 hoặc -16.1 (lệch ±1.5), text "1".."8"
  - Elevation col: x_off≈-8.4, giá trị elevation tại mỗi sample depth
  - Page gap: 147 DXF units giữa các page (mỗi page = 20m = 200 DXF)

Target: 16 NHC BH có x/y nhưng depth_m=NULL và n_layers=0.
"""
from __future__ import annotations
import re
import sqlite3
from pathlib import Path

import ezdxf

_ROOT = Path(__file__).resolve().parent.parent
DXF   = Path(r"G:\My Drive\202605-TRUNG TAM HCM\DIA CHAT\2. NHÀ HÀNH CHÍNH\NHC-1. TRỤ_TTHC_Tru hien truong.dxf")
DB    = _ROOT / "data" / "TTHC.sqlite"

TARGET_BH = [
    "NHC-BH-03","NHC-BH-05","NHC-BH-20","NHC-BH-25","NHC-BH-26","NHC-BH-27",
    "NHC-BH-28","NHC-BH-29","NHC-BH-30","NHC-BH-32","NHC-BH-33","NHC-BH-34",
    "NHC-BH-35","NHC-BH-36","NHC-BH-37","NHC-BH-38",
]
# DXF names (without zone prefix)
DXF_NAMES = {f"BH-{bh.split('-BH-')[1]}": bh for bh in TARGET_BH}

SYM_X_OFFSETS = [-17.6, -16.1]   # layer symbol col (varies by BH)
DEPTH_X_OFFSET = -29.6            # depth tick col
PAGE_SIZE_M    = 20               # meters per page
PAGE_SIZE_DXF  = 200              # = 20m × 10 DXF/m
PAGE_GAP_DXF   = 147              # gap between pages

# Layer symbol descriptions (NHC site convention)
LAYER_DESC = {
    "1": "Lớp 1 — Đất lấp / bùn sét yếu",
    "2": "Lớp 2 — Sét / sét pha dẻo mềm",
    "3": "Lớp 3 — Sét pha dẻo cứng",
    "4": "Lớp 4 — Cát pha / cát mịn",
    "5": "Lớp 5 — Sét / sét pha nửa cứng",
    "6": "Lớp 6 — Cát vừa – thô chặt",
    "7": "Lớp 7 — Sét cứng / cuội sỏi",
    "8": "Lớp 8 — Đá phong hóa / đá cứng",
}


def _load_texts() -> list[tuple[float, float, str]]:
    doc = ezdxf.readfile(str(DXF))
    msp = doc.modelspace()
    return [
        (round(e.dxf.insert.x, 2), round(e.dxf.insert.y, 2), e.dxf.text.strip())
        for e in msp if e.dxftype() == "TEXT" and e.dxf.text.strip()
    ]


def _build_depth_y_map(texts: list, xb: float, yb: float) -> dict[int, list[float]]:
    """Xây dựng mapping depth_m → [y positions] từ depth ticks."""
    depth_ys: dict[int, list[float]] = {}
    for x, y, t in texts:
        if abs((x - xb) - DEPTH_X_OFFSET) <= 3 and y < yb:
            try:
                d = int(t)
                if 0 <= d <= 200:
                    depth_ys.setdefault(d, []).append(y)
            except ValueError:
                pass
    return depth_ys


def _y_to_depth(y: float, depth_ys: dict[int, list[float]]) -> float | None:
    """Chuyển y DXF → depth (m) dùng linear interpolation qua depth ticks."""
    # Collect all (depth, y) pairs, sorted by y desc (shallowest depth first)
    pairs = []
    for d, ys in depth_ys.items():
        for yi in ys:
            pairs.append((d, yi))
    # Sort by y descending (high y = shallow depth)
    pairs.sort(key=lambda r: -r[1])

    # Find bracketing pair
    for i in range(len(pairs) - 1):
        d1, y1 = pairs[i]       # shallower (larger y)
        d2, y2 = pairs[i + 1]   # deeper    (smaller y)
        if y >= y2 and y <= y1:
            if y1 == y2:
                return float(d1)
            frac = (y1 - y) / (y1 - y2)
            return d1 + frac * (d2 - d1)
    return None


def parse_layers(texts: list, bh_dxf: str) -> list[dict]:
    """Trích layer list cho 1 BH. Return [{symbol, depth_top_m, depth_bot_m, description}]."""
    # Find topmost BH header
    bh_candidates = [(x, y) for x, y, t in texts if t == bh_dxf]
    if not bh_candidates:
        return []
    xb, yb = max(bh_candidates, key=lambda r: r[1])

    depth_ys = _build_depth_y_map(texts, xb, yb)
    if not depth_ys:
        return []

    # max depth from ticks
    max_depth = max(depth_ys.keys())

    # Collect symbol texts (first occurrence per symbol = shallowest depth)
    sym_seen: dict[str, float] = {}   # symbol → depth_m (first/shallowest)
    for x, y, t in texts:
        x_off = x - xb
        if any(abs(x_off - so) <= 2 for so in SYM_X_OFFSETS) and y < yb:
            if re.match(r"^\d{1,2}$", t) and t.isdigit():
                depth = _y_to_depth(y, depth_ys)
                if depth is None:
                    continue
                depth = round(depth, 1)
                if t not in sym_seen or depth < sym_seen[t]:
                    sym_seen[t] = depth

    if not sym_seen:
        return []

    # Sort symbols by depth (shallowest first)
    sym_list = sorted(sym_seen.items(), key=lambda r: r[1])

    # Build layers with depth_top / depth_bot
    layers = []
    for i, (sym, dep_top) in enumerate(sym_list):
        dep_bot = sym_list[i + 1][1] if i + 1 < len(sym_list) else float(max_depth)
        layers.append({
            "symbol":      sym,
            "depth_top_m": round(dep_top, 2),
            "depth_bot_m": round(dep_bot, 2),
            "description": LAYER_DESC.get(sym, f"Lớp {sym}"),
        })

    return layers


def update_sqlite(data: dict[str, tuple[int, list[dict]]]) -> None:
    """data = {db_name: (total_depth_m, [layer_dicts])}"""
    con = sqlite3.connect(DB)
    cur = con.cursor()

    # Ensure layers table has description column
    cur.execute("PRAGMA table_info(layers)")
    cols = {r[1] for r in cur.fetchall()}

    n_bh = 0
    n_layers = 0
    for bh_db, (total_depth, layers) in data.items():
        cur.execute("SELECT id, elevation_m FROM boreholes WHERE name=?", (bh_db,))
        row = cur.fetchone()
        if row is None:
            print(f"  [warn] {bh_db} không tìm thấy trong boreholes")
            continue
        bh_id, elev_m = row

        # Update depth_m
        cur.execute("UPDATE boreholes SET depth_m=? WHERE id=?", (total_depth, bh_id))

        # Delete old layers (idempotent)
        cur.execute("DELETE FROM layers WHERE borehole_id=?", (bh_id,))

        # Insert layers
        for ly in layers:
            if "description" in cols:
                cur.execute(
                    "INSERT INTO layers (borehole_id, symbol, depth_top_m, depth_bot_m, description) VALUES (?,?,?,?,?)",
                    (bh_id, ly["symbol"], ly["depth_top_m"], ly["depth_bot_m"], ly["description"]),
                )
            else:
                cur.execute(
                    "INSERT INTO layers (borehole_id, symbol, depth_top_m, depth_bot_m) VALUES (?,?,?,?)",
                    (bh_id, ly["symbol"], ly["depth_top_m"], ly["depth_bot_m"]),
                )
            n_layers += 1

        n_bh += 1
        sym_summary = ", ".join(f"{l['symbol']}@{l['depth_top_m']}" for l in layers)
        print(f"  {bh_db}: depth={total_depth}m, {len(layers)} layers ({sym_summary})")

    con.commit()
    con.close()
    print(f"\n  Cập nhật {n_bh} BH, {n_layers} layers.")


def main() -> None:
    print(f"DXF: {DXF.name} — exists={DXF.exists()}")
    texts = _load_texts()
    print(f"Loaded {len(texts)} TEXT entities.")

    data: dict[str, tuple[int, list[dict]]] = {}
    for dxf_name, db_name in DXF_NAMES.items():
        layers = parse_layers(texts, dxf_name)
        # max depth from ticks
        bh_candidates = [(x, y) for x, y, t in texts if t == dxf_name]
        if not bh_candidates:
            print(f"  [skip] {dxf_name}: không tìm thấy trong DXF")
            continue
        xb, yb = max(bh_candidates, key=lambda r: r[1])
        depth_ys = _build_depth_y_map(texts, xb, yb)
        max_d = max(depth_ys.keys()) if depth_ys else 0
        data[db_name] = (max_d, layers)
        print(f"  {dxf_name} → {db_name}: depth={max_d}m, {len(layers)} layers parsed")

    print("\nCập nhật SQLite...")
    update_sqlite(data)

    # Verify
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""
        SELECT b.name, b.x_coord_m, b.elevation_m, b.depth_m,
               COUNT(l.id) n_layers
        FROM boreholes b
        LEFT JOIN layers l ON l.borehole_id=b.id
        WHERE b.name LIKE 'NHC-%'
          AND b.x_coord_m IS NOT NULL
        GROUP BY b.id ORDER BY b.name
    """)
    print("\nNHC BH sau import (có tọa độ):")
    print(f"  {'Name':<16} {'Elev':>6} {'Depth':>7} {'Layers':>7} {'3D?':>5}")
    n_ok = 0
    for r in cur.fetchall():
        ok = r[2] is not None and r[3] is not None
        n_ok += 1 if ok else 0
        print(f"  {r[0]:<16} {str(r[2] or 'N/A'):>6} {str(r[3] or 'N/A'):>7} {r[4]:>7} {'OK' if ok else 'MISS':>5}")
    print(f"\n  Hiển thị 3D: {n_ok} NHC BH đủ điều kiện.")
    con.close()


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
