"""
import_qtt_zone.py — Khởi tạo zone QTT (Quảng Trường Trung Tâm) trong SQLite.

Nguồn: QTTT-7HK_TruHienTruong.dxf — 5 hố khoan ND-02/03/05/06/07
       (file gốc DXF chỉ có 5 HK, mặc dù tên file là 7HK)

Output:
- Thêm row vào bảng zones (code='QTT')
- Insert 5 boreholes vào bảng boreholes (zone_id = mới)
- Tham số coord/elev/depth từ header MỖI HK trong DXF
- JSON: data/zone_qtt_overview.json
"""
from __future__ import annotations
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime

import ezdxf

_ROOT = Path(__file__).resolve().parent.parent
DXF   = Path(r"G:/My Drive/202605-TRUNG TAM HCM/DIA CHAT/7. QUANG TRUONG TRUNG TAM/QTTT-7HK_TruHienTruong.dxf")
DB    = _ROOT / "data" / "TTHC.sqlite"
JSON_OUT = _ROOT / "data" / "zone_qtt_overview.json"

ZONE_CODE = "QTT"
ZONE_NAME = "Quảng Trường Trung Tâm"


def _parse_dxf_boreholes() -> list[dict]:
    """Đọc DXF, trích metadata mỗi HK (5 cái: ND-02 đến ND-07 skip 04)."""
    dxf = ezdxf.readfile(str(DXF))
    msp = dxf.modelspace()
    texts = [(round(e.dxf.insert.x, 2), round(e.dxf.insert.y, 2), e.dxf.text.strip())
             for e in msp if e.dxftype() == "TEXT"]

    # Tìm các ND-XX với y ~ 71628 (header top page 1)
    nd_anchors = sorted(
        [(x, y, t) for x, y, t in texts if re.match(r"^ND-?\d+$", t) and 71625 < y < 71630],
        key=lambda r: r[0],
    )

    boreholes = []
    for x_anchor, y_anchor, name in nd_anchors:
        # Tìm các giá trị metadata trong dải xung quanh anchor
        nearby = [(x, y, t) for x, y, t in texts
                  if abs(x - x_anchor) < 120 and y_anchor - 50 < y < y_anchor]

        # Pattern: 1191680.407 = northing, 605239.025 = easting, 1.70 = elev, 31.00 = depth
        northing = easting = elev = depth = None
        for x, y, t in nearby:
            try:
                v = float(t.replace(",", "."))
                if 1190000 < v < 1200000:    # northing VN2000
                    northing = v
                elif 600000 < v < 610000:    # easting VN2000
                    easting = v
                elif -2 < v < 5 and elev is None:    # elevation
                    elev = v
                elif 20 < v < 100 and depth is None:  # total depth
                    depth = v
            except ValueError:
                pass

        boreholes.append({
            "name":        name,
            "elevation_m": elev,
            "depth_m":     depth,
            "x_coord_m":   easting,
            "y_coord_m":   northing,
        })
    return boreholes


def main() -> None:
    print(f"Đọc DXF: {DXF.name}")
    bhs = _parse_dxf_boreholes()
    print(f"Tìm thấy {len(bhs)} hố khoan:")
    for b in bhs:
        print(f"  {b['name']:8s}  elev={b['elevation_m']}  depth={b['depth_m']}m  "
              f"E={b['x_coord_m']}  N={b['y_coord_m']}")

    con = sqlite3.connect(str(DB))
    cur = con.cursor()

    # 1. Thêm zone (nếu chưa có)
    cur.execute("SELECT id FROM zones WHERE code=?", (ZONE_CODE,))
    row = cur.fetchone()
    if row:
        zone_id = row[0]
        print(f"\nZone '{ZONE_CODE}' đã tồn tại (id={zone_id}) — sẽ cập nhật boreholes")
    else:
        cur.execute(
            "INSERT INTO zones (code, name_vi, notes) VALUES (?, ?, ?)",
            (ZONE_CODE, ZONE_NAME, f"{len(bhs)} hố khoan ND-XX (Quảng Trường TT)")
        )
        zone_id = cur.lastrowid
        print(f"\nTạo zone mới: id={zone_id}, code='{ZONE_CODE}', name='{ZONE_NAME}'")

    # 2. Insert/update boreholes
    n_ins = n_upd = 0
    for bh in bhs:
        cur.execute("SELECT id FROM boreholes WHERE name=?", (bh["name"],))
        exists = cur.fetchone()
        if exists:
            cur.execute(
                """UPDATE boreholes SET elevation_m=?, depth_m=?,
                   x_coord_m=?, y_coord_m=?, zone_id=? WHERE id=?""",
                (bh["elevation_m"], bh["depth_m"], bh["x_coord_m"], bh["y_coord_m"],
                 zone_id, exists[0])
            )
            n_upd += 1
        else:
            cur.execute(
                """INSERT INTO boreholes (name, zone_id, elevation_m, depth_m,
                   x_coord_m, y_coord_m) VALUES (?, ?, ?, ?, ?, ?)""",
                (bh["name"], zone_id, bh["elevation_m"], bh["depth_m"],
                 bh["x_coord_m"], bh["y_coord_m"])
            )
            n_ins += 1

    con.commit()
    con.close()
    print(f"\nInsert: {n_ins} HK mới, Update: {n_upd} HK")

    # 3. Lưu JSON overview
    payload = {
        "_meta": {
            "generated":   datetime.now().strftime("%Y-%m-%d"),
            "source_dxf":  str(DXF),
            "zone_code":   ZONE_CODE,
            "zone_name":   ZONE_NAME,
            "n_boreholes": len(bhs),
        },
        "boreholes": bhs,
    }
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Lưu JSON: {JSON_OUT.relative_to(_ROOT)}")
    print("\nHoàn tất. Bước tiếp theo:")
    print("  - Cập nhật app_cdm.py: _ZONE_NAMES, _CLAY_SYMBOLS")
    print("  - Bổ sung layers/lab_tests/spt_values nếu cần (chạy import_dxf_boreholes.py)")


if __name__ == "__main__":
    main()
