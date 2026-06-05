# -*- coding: utf-8 -*-
"""Cập nhật ĐỊA TẦNG khu QTT (6 hố ND-02..07) từ file hình trụ mới nhất.

Nguồn: HÌNH TRỤ, MC-QTT/QTT-7 HO KHOAN 20260605.dxf (6 cột hố cạnh nhau).
Xoá toàn bộ lớp QTT cũ trong DB (LOCAL + PROJECT) + JSON, thay bằng dữ liệu DXF.

Mỗi lớp đọc theo marker (số hiệu lớp @cột trái + BỀ DÀY) + mô tả gần nhất; cộng dồn
bề dày → cao độ đỉnh/đáy. KHÔNG suy đoán: tổng bề dày mỗi hố = chiều sâu hố thực.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import ezdxf

_ROOT = Path(__file__).resolve().parent.parent
_DXF = Path(r"G:/My Drive/202605-TRUNG TAM HCM/DIA CHAT/7. QUANG TRUONG TRUNG TAM/"
            r"HÌNH TRỤ, MC-QTT/QTT-7 HO KHOAN 20260605.dxf")
_DBS = [Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite"), _ROOT / "data" / "TTHC.sqlite"]

_CENTERS = {"ND-02": 75.1, "ND-03": 305.1, "ND-04": 535.1,
            "ND-05": 765.1, "ND-06": 995.1, "ND-07": 1225.1}

# Mô tả CHUẨN 5 đơn vị địa chất (đầy đủ, đúng chính tả tiếng Việt) — theo DXF
U_F = "Đất san lấp: Đá đổ, sỏi sạn, cát, sét"
U_1 = "(CH) - Sét rất dẻo màu xám xanh, xám ghi, trạng thái chảy xen kẹp dẻo chảy - dẻo mềm"
U_2 = "(CH) - Sét rất dẻo màu xám xanh, trạng thái dẻo mềm"
U_3 = "(SM) - Cát lẫn bụi màu xám xanh, xám trắng, kết cấu chặt vừa"
U_4 = "(CL, CH) - Sét ít dẻo lẫn sét rất dẻo màu xám xanh, xám trắng, trạng thái dẻo cứng đến nửa cứng"


def _canon(raw: str) -> str:
    """Chuẩn hoá mô tả thô (gần marker) → 1 trong 5 đơn vị chuẩn."""
    r = raw
    if "san lấp" in r:
        return U_F
    if "Cát lẫn bụi" in r or "(SM" in r:
        return U_3
    if "ít dẻo" in r or "CL" in r:
        return U_4
    if "xen kẹp" in r or "xám ghi" in r:
        return U_1
    if "dẻo mềm" in r:
        return U_2
    return raw


def extract_layers() -> dict:
    """Trả {bh: [{'symbol','desc','thickness','top','bot'}]} từ DXF."""
    d = ezdxf.readfile(str(_DXF))
    msp = d.modelspace()
    items = []
    for e in msp:
        dt = e.dxftype()
        if dt == "TEXT":
            t = e.dxf.text
        elif dt == "MTEXT":
            t = e.plain_text()
        else:
            continue
        t = str(t).replace("\n", " ").strip()
        if t:
            items.append((e.dxf.insert.x, e.dxf.insert.y, t))

    geo = re.compile(r"Sét|Cát|Bùn|san lấp|\(CH|\(CL|\(SM")
    dec = re.compile(r"^\d+\.\d{2}$")
    symre = re.compile(r"^[0-9F]$")
    out = {}
    for bh, cx in _CENTERS.items():
        band = [(x, y, t) for x, y, t in items if cx - 58 <= x <= cx + 135]
        # marker: symbol @ cột trái + bề dày cùng y
        syms = [(round(y, 1), t) for x, y, t in band
                if symre.match(t) and cx - 54 <= x <= cx - 38]
        thks = {round(y, 1): float(t) for x, y, t in band
                if dec.match(t) and cx - 27 <= x <= cx - 8}
        descs = [(round(y, 1), t) for x, y, t in band
                 if geo.search(t) and len(t) > 18 and cx - 5 <= x <= cx + 125]

        def near_desc(ys):
            same = [(abs(yd - ys), td) for yd, td in descs
                    if (yd < -380) == (ys < -380)]
            if same:
                return min(same)[1]
            return min(((abs(yd - ys), td) for yd, td in descs))[1] if descs else "?"

        # (symbol, thickness) -> max y (chọn panel nông nhất để xếp thứ tự)
        seen = {}
        for y, s in syms:
            th = None
            for yy in (y, round(y), y - 0.1, y + 0.1, y - 0.5, y + 0.5):
                if yy in thks:
                    th = thks[yy]
                    break
            if th is None:
                continue
            key = (s, th)
            if key not in seen or y > seen[key][0]:
                seen[key] = (y, s, th)
        markers = sorted(seen.values(), key=lambda r: -r[0])  # y giảm dần = nông→sâu
        layers = []
        top = 0.0
        for y, s, th in markers:
            desc = _canon(near_desc(y))
            layers.append({"symbol": s, "desc": desc, "thickness": round(th, 2),
                           "top": round(top, 2), "bot": round(top + th, 2)})
            top += th
        out[bh] = layers
    return out


# loại đất YẾU (cố kết) để tính H_soft — sét rất dẻo CH (chảy/dẻo mềm). KHÔNG gồm
# CL,CH dẻo cứng-nửa cứng (đất cứng), cát, đất san lấp.
def _is_soft(desc: str) -> bool:
    from soil_param_stats import soil_type_of
    return soil_type_of(desc) in {"Bùn sét (chảy)", "Sét dẻo cao (CH)", "Sét pha (dẻo mềm)"}


def update_db(layers_by_bh: dict) -> None:
    for db in _DBS:
        if not db.parent.exists():
            print(f"  SKIP (no dir): {db}")
            continue
        con = sqlite3.connect(str(db))
        cur = con.cursor()
        for bh, layers in layers_by_bh.items():
            row = cur.execute("SELECT id FROM boreholes WHERE name=?", (bh,)).fetchone()
            if not row:
                print(f"  [{db.name}] {bh}: KHÔNG có trong boreholes — bỏ qua")
                continue
            bid = row[0]
            cur.execute("DELETE FROM layers WHERE borehole_id=?", (bid,))
            for L in layers:
                cur.execute(
                    "INSERT INTO layers (borehole_id, symbol, description, "
                    "depth_top_m, depth_bot_m, thickness_m) VALUES (?,?,?,?,?,?)",
                    (bid, L["symbol"], L["desc"], L["top"], L["bot"], L["thickness"]))
        con.commit()
        con.close()
        print(f"  [{db.name}] cập nhật xong layers QTT")


def update_json(layers_by_bh: dict) -> None:
    for bh, layers in layers_by_bh.items():
        nd = bh.replace("ND-", "nd").lower()        # ND-02 -> nd02
        f = _ROOT / "data" / f"qtt_{nd}_borehole.json"
        if not f.exists():
            print(f"  JSON thiếu: {f.name}")
            continue
        j = json.loads(f.read_text(encoding="utf-8"))
        elev = float(j.get("borehole", {}).get("elevation_m") or 0.0)
        jl = []
        for i, L in enumerate(layers, 1):
            jl.append({
                "order": i, "depth_top_m": L["top"], "depth_bot_m": L["bot"],
                "thickness_m": L["thickness"], "elev_bot_m": round(elev - L["bot"], 2),
                "symbol": L["symbol"], "description": L["desc"],
            })
        j["layers"] = jl
        H_soft = round(sum(L["thickness"] for L in layers if _is_soft(L["desc"])), 2)
        j.setdefault("borehole", {})["H_soft_m"] = H_soft
        j["borehole"]["n_layers"] = len(layers)
        j["borehole"]["total_depth_m"] = layers[-1]["bot"] if layers else 0.0
        j.setdefault("_meta", {})
        j["_meta"]["source_dxf"] = str(_DXF)
        j["_meta"]["symbol_source"] = "QTT-7 HO KHOAN 20260605.dxf (ký hiệu F,1,2,3,4 theo đơn vị địa chất)"
        j["_meta"]["updated"] = "2026-06-05"
        f.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  JSON {f.name}: {len(jl)} lớp, H_soft={H_soft}")


if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    data = extract_layers()
    print("=== ĐỊA TẦNG TRÍCH TỪ DXF MỚI ===")
    for bh, layers in data.items():
        tot = layers[-1]["bot"] if layers else 0
        print(f"{bh}  ({len(layers)} lớp, đáy {tot} m):")
        for L in layers:
            print(f"   [{L['symbol']}] {L['top']:>6}-{L['bot']:>6} ({L['thickness']:>5}) "
                  f"{L['desc'][:55]}")
    print("\n=== GHI DB ===")
    update_db(data)
    print("\n=== GHI JSON ===")
    update_json(data)
    print("\nXONG.")
