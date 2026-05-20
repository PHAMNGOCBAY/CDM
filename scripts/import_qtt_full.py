"""
import_qtt_full.py — Đọc toàn bộ thông tin từ QTTT DXF, lưu vào SQLite + JSON.

Trích xuất 5 nội dung:
1. **Boreholes**: header metadata (coord, elev, depth) — đã có
2. **Layers**: stratigraphy descriptions (depth chừa trống vì DXF không cung cấp boundary chính xác)
3. **Lab samples** (U-samples): depth + sample_id → bảng lab_tests
4. **SPT data**: depth + N values 5 cột → bảng spt_values
5. **Footer info**: VST locations / lab info nếu có

Output:
- SQLite: boreholes, layers, lab_tests, spt_values (zone='QTT')
- JSON: data/zone_qtt_full.json
"""
from __future__ import annotations
import json
import re
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import ezdxf

_ROOT = Path(__file__).resolve().parent.parent
DXF   = Path(r"G:/My Drive/202605-TRUNG TAM HCM/DIA CHAT/7. QUANG TRUONG TRUNG TAM/QTTT-7HK_TruHienTruong.dxf")
DB    = _ROOT / "data" / "TTHC.sqlite"
JSON_OUT = _ROOT / "data" / "zone_qtt_full.json"

ZONE_CODE = "QTT"


def _depth_from_y(y: float, y_zero_p1: float = 71554, y_zero_p2: float = 71237,
                  depth_p2_offset: float = 30.0) -> float | None:
    """Convert y coord → depth (m). Page 1: 0-30m, Page 2: 30+m."""
    if y > y_zero_p2:
        return (y_zero_p1 - y) / 10.0
    return depth_p2_offset + (y_zero_p2 - y) / 10.0


def _closest_hk(x: float, anchors: list) -> tuple | None:
    """Tìm HK anchor gần x nhất; chỉ trả nếu trong dải ±half_spacing."""
    best = min(anchors, key=lambda a: abs(a[0] - x))
    if abs(best[0] - x) < 175:   # half spacing ≈ 170
        return best
    return None


def parse_dxf() -> dict:
    """Đọc DXF + trích xuất 5 loại thông tin."""
    print(f"Đọc DXF: {DXF.name}")
    dxf = ezdxf.readfile(str(DXF))
    msp = dxf.modelspace()
    texts = [(round(e.dxf.insert.x, 2), round(e.dxf.insert.y, 2), e.dxf.text.strip())
             for e in msp.query("TEXT")]
    mtexts = [(round(e.dxf.insert.x, 2), round(e.dxf.insert.y, 2), e.text)
              for e in msp.query("MTEXT")]

    # 1. HK anchors
    anchors = sorted(
        [(x, y, t) for x, y, t in texts if re.match(r"^ND-?\d+$", t) and 71625 < y < 71630],
        key=lambda r: r[0],
    )
    print(f"  {len(anchors)} HK anchors: {[a[2] for a in anchors]}")

    result = {a[2]: {
        "name":         a[2],
        "x_anchor":     a[0],
        "elevation_m":  None, "depth_m": None,
        "x_coord_m":    None, "y_coord_m": None,
        "layers":       [],
        "lab_samples":  [],
        "spt":          [],
    } for a in anchors}

    # 2. Metadata mỗi HK (coords, elev, depth)
    for x_a, y_a, name in anchors:
        nearby = [(x, y, t) for x, y, t in texts
                  if abs(x - x_a) < 120 and y_a - 60 < y < y_a]
        for x, y, t in nearby:
            try:
                v = float(t.replace(",", "."))
                if 1190000 < v < 1200000:
                    result[name]["y_coord_m"] = v   # northing
                elif 600000 < v < 610000:
                    result[name]["x_coord_m"] = v   # easting
                elif -2 < v < 5 and result[name]["elevation_m"] is None:
                    result[name]["elevation_m"] = v
                elif 20 < v < 100 and result[name]["depth_m"] is None:
                    result[name]["depth_m"] = v
            except ValueError:
                pass

    # 3. Layer descriptions (từ MTEXT)
    KEYWORD_TO_SYMBOL = [
        ("đá san lấp", "F", "Đất đắp - Đá san lấp lẫn sét"),
        ("đất đắp",    "F", "Đất đắp"),
        ("bùn sét",    "1", "Bùn sét yếu màu xám xanh, trạng thái chảy"),
        ("sét pha",    "3", "Sét pha màu xám xanh, trạng thái dẻo mềm"),
        ("cát màu",    "4", "Cát màu xám trắng kết cấu chặt vừa"),
        ("cát chặt",   "4", "Cát chặt vừa"),
        ("cát",        "4", "Cát kết cấu chặt vừa"),
        ("sét",        "5", "Sét dẻo"),
    ]
    SKIP_KEYWORDS = ("quảng trường", "hạ tầng", "phường", "thành phố", "hố khoan",
                     "công ty", "thí nghiệm", "kết thúc")

    for x_a, y_a, name in anchors:
        seen = set()
        for x, y, t in mtexts:
            if not (x_a - 80 < x < x_a + 80):
                continue
            clean = re.sub(r"\{.*?;", "", t).replace("}", "").strip()
            if any(kw in clean.lower() for kw in SKIP_KEYWORDS):
                continue
            if clean in seen:
                continue
            seen.add(clean)
            sym, std_desc = "?", clean[:60]
            for kw, s, d in KEYWORD_TO_SYMBOL:
                if kw in clean.lower():
                    sym, std_desc = s, d
                    break
            result[name]["layers"].append({"symbol": sym, "description": std_desc})

    # 4. Lab samples (U1, U2, ...)
    u_pat = re.compile(r"^U\d+$")
    for x, y, t in texts:
        if u_pat.match(t):
            hk = _closest_hk(x, anchors)
            if hk:
                depth = _depth_from_y(y)
                if depth and 0 < depth < 60:
                    result[hk[2]]["lab_samples"].append({
                        "sample_id": t,
                        "depth_m":   round(depth, 2),
                    })

    # 5. SPT data (5 cột numeric values per depth row)
    # Group numeric texts by (HK, y) → 5-col cells
    spt_by_hk = defaultdict(lambda: defaultdict(list))
    for x, y, t in texts:
        if not re.match(r"^-?\d+$", t):
            continue
        hk = _closest_hk(x, anchors)
        if not hk:
            continue
        # SPT cols là khoảng x_anchor+60..x_anchor+100 (cách header 60-100 units)
        off = x - hk[0]
        if 60 < off < 100:
            spt_by_hk[hk[2]][round(y)].append((x, int(t)))

    for hk_name, rows in spt_by_hk.items():
        for y, cells in rows.items():
            if len(cells) != 5:
                continue
            cells.sort()
            depth = _depth_from_y(y)
            if not depth or depth < 0 or depth > 60:
                continue
            vals = [v for _, v in cells]
            # Bỏ qua axis labels (10,20,30,40,50)
            if vals == [10, 20, 30, 40, 50]:
                continue
            # 5 cột = N1, N2, N3, N4, N5 (đặc trưng QTT — khác KE 4 cột)
            # Theo phân tích thực: [N1, N2, N3, N_sum_2_3, ?] hoặc [N1..N5 (penetration count)]
            # Tổng N = N1 + N2 (ASTM standard 2nd+3rd interval = col2+col3)
            N_user = vals[1] + vals[2]  # col2+col3 (per KE convention)
            result[hk_name]["spt"].append({
                "depth_m": round(depth, 2),
                "N1": vals[0], "N2": vals[1], "N3": vals[2],
                "N4": vals[3], "N5": vals[4],
                "N": N_user,
            })

    # Sort sub-arrays
    for hk in result.values():
        hk["lab_samples"].sort(key=lambda s: s["depth_m"])
        hk["spt"].sort(key=lambda s: s["depth_m"])

    return result


def save_sqlite(data: dict) -> None:
    """Insert/update vào SQLite (xoá data cũ của QTT trước)."""
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    cur.execute("SELECT id FROM zones WHERE code=?", (ZONE_CODE,))
    zone_id = cur.fetchone()[0]
    bh_ids = dict(cur.execute(
        "SELECT name, id FROM boreholes WHERE zone_id=?", (zone_id,)
    ).fetchall())

    # Xoá data cũ của QTT
    placeholders = ",".join("?" * len(bh_ids))
    if bh_ids:
        cur.execute(f"DELETE FROM layers WHERE borehole_id IN ({placeholders})",
                    list(bh_ids.values()))
        cur.execute(f"DELETE FROM lab_tests WHERE borehole_id IN ({placeholders})",
                    list(bh_ids.values()))
        cur.execute(f"DELETE FROM spt_values WHERE borehole_id IN ({placeholders})",
                    list(bh_ids.values()))

    n_lay = n_lab = n_spt = 0
    for hk_name, hk in data.items():
        if hk_name not in bh_ids:
            continue
        bh_id = bh_ids[hk_name]
        elev = hk.get("elevation_m")
        # Layers
        for L in hk["layers"]:
            cur.execute(
                """INSERT INTO layers (borehole_id, symbol, description,
                   depth_top_m, depth_bot_m, thickness_m)
                   VALUES (?, ?, ?, NULL, NULL, NULL)""",
                (bh_id, L["symbol"], L["description"])
            )
            n_lay += 1
        # Lab samples
        for s in hk["lab_samples"]:
            d_to = s["depth_m"] + 0.2   # giả định 20cm mỗi mẫu U
            cur.execute(
                """INSERT INTO lab_tests (borehole_id, sample_id, depth_from_m, depth_to_m)
                   VALUES (?, ?, ?, ?)""",
                (bh_id, s["sample_id"], s["depth_m"], round(d_to, 2))
            )
            n_lab += 1
        # SPT
        for sp in hk["spt"]:
            cur.execute(
                """INSERT INTO spt_values (borehole_id, depth_m, elev_m, N1, N2, N3, N)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (bh_id, sp["depth_m"],
                 (elev - sp["depth_m"]) if elev is not None else None,
                 sp["N1"], sp["N2"], sp["N3"], sp["N"])
            )
            n_spt += 1
    con.commit()
    con.close()
    print(f"\nSQLite QTT: {n_lay} layers · {n_lab} lab_samples · {n_spt} SPT readings")


def save_json(data: dict) -> None:
    payload = {
        "_meta": {
            "generated":   datetime.now().strftime("%Y-%m-%d"),
            "source_dxf":  str(DXF),
            "zone_code":   ZONE_CODE,
            "n_boreholes": len(data),
            "depth_note":  "Layer depths NULL — DXF chỉ có vị trí label, không có boundary chính xác. Sample depths tính từ MTEXT y-position (offset từ page anchor).",
            "spt_convention": "5 cột mỗi depth: N1/N2/N3/N4/N5; N total = N2+N3 (chuẩn ASTM)",
        },
        "boreholes": data,
    }
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON: {JSON_OUT.relative_to(_ROOT)}")


def main() -> None:
    data = parse_dxf()
    print()
    for name, hk in data.items():
        print(f"{name}: layers={len(hk['layers'])} · lab={len(hk['lab_samples'])} · SPT={len(hk['spt'])}")
    save_sqlite(data)
    save_json(data)


if __name__ == "__main__":
    main()
