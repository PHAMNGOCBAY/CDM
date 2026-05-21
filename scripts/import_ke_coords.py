# -*- coding: utf-8 -*-
"""
import_ke_coords.py — Trích tọa độ VN-2000 cho 12 HK KE từ DXF và cập nhật SQLite.

DXF layout:
  y=94.75 / 44.75: HK names (HK1..HK12), x_base = 50.14 + (i-1)*230
  y=41.85: Northing VN-2000 (x_base - 2)
  y=38.19: Easting  VN-2000 (x_base - 2)
  y=34.68: Elevation (m), text = "X.XXX m"

Quy ước DB: x_coord_m = Northing, y_coord_m = Easting  (giống BXN/NHC).
"""
from __future__ import annotations
import re
import sqlite3
from pathlib import Path

import ezdxf

_ROOT   = Path(__file__).resolve().parent.parent
DXF     = _ROOT / "DIA CHAT" / "3. KÈ (CÔNG VIÊN)" / "KE-1. TRỤ_260512 CVTT-TTHC. Tru DC.dxf"
DB      = _ROOT / "data" / "TTHC.sqlite"

HK_BASE_X = 50.14
HK_DX     = 230.0

NORTHING_Y = 41.85
EASTING_Y  = 38.19
ELEV_Y     = 34.68
ELEV_PATTERN = re.compile(r"^(-?\d+\.\d+)\s*m$")


def extract_coords_from_dxf() -> dict[str, dict]:
    """Return {bh_name: {northing, easting, elevation}} for all 12 HK."""
    doc = ezdxf.readfile(str(DXF))
    msp = doc.modelspace()
    texts = [
        (round(e.dxf.insert.x, 2), round(e.dxf.insert.y, 2), e.dxf.text.strip())
        for e in msp if e.dxftype() == "TEXT" and e.dxf.text.strip()
    ]

    coords: dict[str, dict] = {}
    for i in range(1, 13):
        bh   = f"KE-HK{i}"
        xb   = HK_BASE_X + (i - 1) * HK_DX
        tol  = 3.0  # x tolerance

        def _get(target_y: float, alt_y: float | None = None) -> str | None:
            for x, y, t in texts:
                if abs(x - xb) <= tol and abs(y - target_y) <= 0.2:
                    return t
            if alt_y is not None:
                for x, y, t in texts:
                    if abs(x - xb) <= tol and abs(y - alt_y) <= 0.2:
                        return t
            return None

        northing_t = _get(NORTHING_Y)
        easting_t  = _get(EASTING_Y)
        elev_t     = _get(ELEV_Y)

        northing = float(northing_t) if northing_t and northing_t.replace(".", "").isdigit() else None
        easting  = float(easting_t)  if easting_t  and easting_t.replace(".", "").isdigit()  else None
        elev     = None
        if elev_t:
            m = ELEV_PATTERN.match(elev_t)
            if m:
                elev = float(m.group(1))

        coords[bh] = {"northing": northing, "easting": easting, "elevation": elev}

    return coords


def update_sqlite(coords: dict[str, dict]) -> None:
    con = sqlite3.connect(DB)
    cur = con.cursor()

    updated = 0
    for bh_name, c in coords.items():
        if c["northing"] is None or c["easting"] is None:
            print(f"  [skip] {bh_name}: thiếu northing hoặc easting")
            continue

        # Chỉ cập nhật HK còn thiếu x/y (tránh ghi đè data đúng)
        cur.execute("SELECT id, x_coord_m, y_coord_m, elevation_m FROM boreholes WHERE name=?", (bh_name,))
        row = cur.fetchone()
        if row is None:
            print(f"  [warn] {bh_name} không tìm thấy trong boreholes")
            continue
        bh_id, x_old, y_old, elev_old = row

        updates = {}
        if x_old is None:
            updates["x_coord_m"] = c["northing"]
        if y_old is None:
            updates["y_coord_m"] = c["easting"]
        if elev_old is None and c["elevation"] is not None:
            updates["elevation_m"] = c["elevation"]

        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates)
            cur.execute(f"UPDATE boreholes SET {set_clause} WHERE id=?",
                        list(updates.values()) + [bh_id])
            print(f"  {bh_name}: UPDATE {updates}")
            updated += 1
        else:
            print(f"  {bh_name}: đã có tọa độ, bỏ qua")

    con.commit()
    con.close()
    print(f"\n  Cập nhật {updated} hố khoan.")


def main() -> None:
    print(f"DXF: {DXF.name} — exists={DXF.exists()}")
    coords = extract_coords_from_dxf()

    print("\nTọa độ trích từ DXF:")
    print(f"  {'HK':<12} {'Northing':>14} {'Easting':>13} {'Elevation':>10}")
    for bh, c in coords.items():
        n = f"{c['northing']:.3f}" if c["northing"] else "N/A"
        e = f"{c['easting']:.3f}"  if c["easting"]  else "N/A"
        z = f"{c['elevation']:.3f}" if c["elevation"] is not None else "N/A"
        print(f"  {bh:<12} {n:>14} {e:>13} {z:>10}")

    print("\nCập nhật SQLite...")
    update_sqlite(coords)

    # Verify
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""
        SELECT b.name, b.x_coord_m, b.y_coord_m, b.elevation_m, b.depth_m
        FROM boreholes b JOIN zones z ON z.id=b.zone_id
        WHERE z.code='KE' ORDER BY b.name
    """)
    print("\nKết quả sau import (KE):")
    print(f"  {'Name':<12} {'Northing':>14} {'Easting':>13} {'Elev':>8} {'Depth':>7} {'3D?':>5}")
    n_ok = 0
    for r in cur.fetchall():
        ok = all(v is not None for v in r[1:4])
        n_ok += 1 if ok else 0
        flag = "OK" if ok else "MISS"
        print(f"  {r[0]:<12} {str(r[1] or 'N/A'):>14} {str(r[2] or 'N/A'):>13} "
              f"{str(r[3] or 'N/A'):>8} {str(r[4] or 'N/A'):>7} {flag:>5}")
    print(f"\n  Hiển thị 3D: {n_ok}/12 HK đủ tọa độ.")
    con.close()


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
