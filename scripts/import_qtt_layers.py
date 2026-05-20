"""
import_qtt_layers.py — Parse layers địa tầng từ DXF QTTT cho 5 HK QTT.

Nguồn: QTTT-7HK_TruHienTruong.dxf
Approach: extract layer descriptions từ MTEXT theo y position; map description →
symbol theo từ khoá ("Đá san lấp", "Bùn sét", "Sét pha", "Cát") → insert vào
layers table. Depth thiếu chừa trống (None) — user có thể bổ sung sau.

Mỗi HK có 2 page trong DXF:
- Page 1 header y ≈ 71614, depth 0 ở y ≈ 71554, scale 10 units/m → covers 0-30m
- Page 2 header y ≈ 71267, depth 30m ở y ≈ 71237, scale 10 units/m → covers 30-60m
"""
from __future__ import annotations
import re
import sqlite3
from pathlib import Path

import ezdxf

_ROOT = Path(__file__).resolve().parent.parent
DXF   = Path(r"G:/My Drive/202605-TRUNG TAM HCM/DIA CHAT/7. QUANG TRUONG TRUNG TAM/QTTT-7HK_TruHienTruong.dxf")
DB    = _ROOT / "data" / "TTHC.sqlite"

# Mapping từ khoá mô tả → symbol địa kỹ thuật
KEYWORD_TO_SYMBOL = [
    ("đá san lấp",  "F",  "Đất đắp - Đá san lấp lẫn sét"),
    ("đất đắp",     "F",  "Đất đắp"),
    ("bùn sét",     "1",  "Bùn sét yếu màu xám xanh, trạng thái chảy"),
    ("sét pha",     "3",  "Sét pha màu xám xanh, trạng thái dẻo mềm"),
    ("cát màu",     "4",  "Cát màu xám trắng kết cấu chặt vừa"),
    ("cát chặt",    "4",  "Cát chặt vừa"),
    ("cát",         "4",  "Cát kết cấu chặt vừa"),
    ("sét",         "5",  "Sét dẻo"),
]


def _map_symbol(desc: str) -> tuple[str, str]:
    """Map description → (symbol, clean_description)."""
    low = desc.lower()
    for kw, sym, clean in KEYWORD_TO_SYMBOL:
        if kw in low:
            return sym, clean
    return "?", desc[:60]


def _parse_layers_for_hk(texts, mtexts, x_anchor: float, y_header_p1: float,
                          total_depth: float) -> list[dict]:
    """Trích layers cho 1 HK từ MTEXT descriptions trong dải x_anchor ± 80.

    Page 1: y in (y_header_p1 - 350, y_header_p1 - 10), scale 10 u/m từ y_zero=y_header_p1-60
    Page 2: y_header_p2 = y_header_p1 - 347 (cách ~347 units), y_zero_p2 = y_header_p2-60
             representing depth 30-60m
    """
    y_zero_p1 = y_header_p1 - 60      # y tại depth=0 page 1
    y_header_p2 = y_header_p1 - 347   # header page 2
    y_zero_p2 = y_header_p2 - 60      # y tại depth=30 page 2 (page 2 starts depth=30)

    # Lọc MTEXT trong x_anchor ± 80 và y < y_header_p1 (bên dưới header)
    candidates = []
    for x, y, t in mtexts:
        if not (x_anchor - 80 < x < x_anchor + 80):
            continue
        # Lọc text không phải layer description (vd địa chỉ, project)
        clean = re.sub(r"\{.*?;", "", t).replace("}", "").strip()
        if any(kw in clean.lower() for kw in (
            "quảng trường", "hạ tầng", "phường", "thành phố", "hố khoan",
            "công ty", "thí nghiệm", "kết thúc",
        )):
            continue
        # Tính depth dựa trên page
        if y > y_zero_p1 - 305:    # page 1 range
            depth = (y_zero_p1 - y) / 10
            page = 1
        elif y > y_zero_p2 - 305:  # page 2 range
            depth = 30 + (y_zero_p2 - y) / 10
            page = 2
        else:
            continue
        if depth < 0 or depth > total_depth + 5:
            continue
        candidates.append((depth, clean, page))

    if not candidates:
        return []
    candidates.sort()
    # Loại trùng (cùng description trong page 1 và 2 — dùng cái đầu theo depth)
    layers = []
    seen_descs = set()
    for depth, desc, page in candidates:
        if desc in seen_descs:
            continue
        seen_descs.add(desc)
        sym, clean = _map_symbol(desc)
        layers.append({
            "symbol":      sym,
            "description": clean,
            # Depth từ MTEXT y position không chính xác (chỉ là vị trí label) →
            # CHỪA TRỐNG, user bổ sung sau khi đọc bảng địa tầng gốc
            "depth_top_m": None,
            "depth_bot_m": None,
            "thickness_m": None,
        })
    return layers


def main() -> None:
    dxf = ezdxf.readfile(str(DXF))
    msp = dxf.modelspace()
    texts  = [(round(e.dxf.insert.x, 2), round(e.dxf.insert.y, 2), e.dxf.text.strip())
              for e in msp if e.dxftype() == "TEXT"]
    mtexts = [(round(e.dxf.insert.x, 2), round(e.dxf.insert.y, 2), e.text)
              for e in msp if e.dxftype() == "MTEXT"]

    # Tìm anchor mỗi HK
    nd_anchors = sorted(
        [(x, y, t) for x, y, t in texts if re.match(r"^ND-?\d+$", t) and 71625 < y < 71630],
        key=lambda r: r[0],
    )

    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    # Tổng depth từ boreholes table
    depths = dict(cur.execute(
        "SELECT b.name, b.depth_m FROM boreholes b JOIN zones z ON b.zone_id=z.id "
        "WHERE z.code='QTT'"
    ).fetchall())

    total_layers = 0
    for x_anchor, y_anchor, name in nd_anchors:
        total_d = depths.get(name, 35.0)
        layers = _parse_layers_for_hk(texts, mtexts, x_anchor, y_anchor, total_d)
        print(f"\n{name} (depth={total_d}m) — {len(layers)} layers (depth chừa trống):")
        for L in layers:
            print(f"  {L['symbol']:3s}  {L['description'][:60]}")

        # Insert vào SQLite
        cur.execute("SELECT id FROM boreholes WHERE name=?", (name,))
        bh = cur.fetchone()
        if not bh:
            print(f"  [skip] {name} không có trong boreholes")
            continue
        bh_id = bh[0]
        # Xoá layers cũ của HK này (nếu có)
        cur.execute("DELETE FROM layers WHERE borehole_id=?", (bh_id,))
        for L in layers:
            cur.execute(
                """INSERT INTO layers (borehole_id, symbol, description,
                   depth_top_m, depth_bot_m, thickness_m)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (bh_id, L["symbol"], L["description"], L["depth_top_m"],
                 L["depth_bot_m"], L["thickness_m"])
            )
            total_layers += 1

    con.commit()
    con.close()
    print(f"\nTổng cộng: {total_layers} layers cho {len(nd_anchors)} HK QTT đã insert vào SQLite")


if __name__ == "__main__":
    main()
