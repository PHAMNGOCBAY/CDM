"""
import_ke_spt.py — Đọc SPT cho 12 hố khoan KE-HK1..HK12 từ DXF mới.

DXF: G:/My Drive/AI-SUC TAI COC THEO DAT NEN/DIA CHAT/3. KÈ (CÔNG VIÊN)/
      KE-1. TRỤ_260512 CVTT-TTHC. Tru DC.dxf

Cấu trúc:
- 12 HK xếp ngang, x_base = 50.14 + (i-1)*230 (i = 1..12)
- 4 cột SPT: col1 (N_prep, skip) / col2 (N1) / col3 (N2) / col4 (N3) — offset x_base+79/84/89/94
- Mỗi depth có depth_from (x_base+70, vd "2.00") và depth_to (vd "2.45") cách nhau ~3 y_units
- Nhiều page xếp dọc; page transition khi gặp header "HK\\d+" mới (y giảm dần ~317 unit/page)

Theo user (2026-05-20): **N = N1 + N2** (= col2 + col3 trong DXF). KHÁC chuẩn ASTM (N2+N3).

Lưu:
- SQLite TTHC.sqlite, bảng `spt_values` (xoá KE cũ trước khi insert)
- JSON: data/ke_spt_data.json
- MD:   45-ke-spt-import.md (gốc dự án)
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
DXF   = _ROOT / "DIA CHAT" / "3. KÈ (CÔNG VIÊN)" / "KE-1. TRỤ_260512 CVTT-TTHC. Tru DC.dxf"
DB    = _ROOT / "data" / "TTHC.sqlite"
JSON_OUT = _ROOT / "data" / "ke_spt_data.json"
MD_OUT   = _ROOT / "45-ke-spt-import.md"

# X offset của 4 cột SPT so với x_base của mỗi HK
SPT_COL_OFFSETS = [78.71, 83.71, 88.71, 93.62]  # N_prep, N1, N2, N3 (DXF naming)
DEPTH_COL_OFFSET = 70.0   # x_base + 70 = depth_from / depth_to label
HK_BASE_X = 50.14         # x của HK1
HK_DX     = 230.0         # khoảng cách giữa các HK


def _load_texts() -> list[tuple[float, float, str]]:
    dxf = ezdxf.readfile(DXF)
    msp = dxf.modelspace()
    return [
        (round(e.dxf.insert.x, 2), round(e.dxf.insert.y, 2), e.dxf.text.strip())
        for e in msp if e.dxftype() == "TEXT"
    ]


def _parse_hk_spt(texts, hk_idx: int) -> list[dict]:
    """Tìm tất cả SPT rows cho HK[hk_idx] (1..12) xuyên các pages."""
    x_base = HK_BASE_X + (hk_idx - 1) * HK_DX

    # Lấy text trong dải x_base..x_base+100 (toàn cột HK này)
    band = [(x, y, t) for x, y, t in texts if x_base - 2 <= x <= x_base + 100]

    # Group theo y (làm tròn 1) → mỗi row
    rows_by_y: dict[int, list[tuple[float, str]]] = defaultdict(list)
    for x, y, t in band:
        rows_by_y[round(y)].append((x, t))

    # Depth-from labels: pattern \d+\.\d{2} (không phải interval x.xx-x.xx)
    depth_pattern = re.compile(r"^\d+\.\d{2}$")

    # Tìm các y có 4 số nguyên (SPT row) và depth-from gần đó (±3 y)
    spt_rows: list[dict] = []
    for y, cells in rows_by_y.items():
        nums = []
        for x, t in cells:
            try:
                v = int(t)
                # Phải nằm trong vùng SPT cols
                if any(abs(x - (x_base + off)) < 3.0 for off in SPT_COL_OFFSETS):
                    nums.append((x, v))
            except ValueError:
                pass
        if len(nums) != 4:
            continue
        nums.sort(key=lambda p: p[0])
        # Map sang col1..col4
        col1, col2, col3, col4 = (n[1] for n in nums)
        # Tìm depth-from trong y±3 (label depth ở y+1 hoặc -1 so với SPT row)
        depth_from = None
        depth_to   = None
        for dy in range(-3, 4):
            for x2, t2 in rows_by_y.get(y + dy, []):
                if abs(x2 - (x_base + DEPTH_COL_OFFSET)) < 5 and depth_pattern.match(t2):
                    v = float(t2)
                    if depth_from is None:
                        depth_from = v
                    elif depth_to is None and v > depth_from:
                        depth_to = v
        if depth_from is None:
            continue
        # N theo user: N = N1 + N2 = col2 + col3
        N_user = col2 + col3
        N_astm = col3 + col4   # tham khảo chuẩn (N2+N3)
        spt_rows.append({
            "depth_m":    depth_from,
            "depth_to_m": depth_to,
            "N_prep":     col1,      # seating (skip)
            "N1":         col2,      # 1st 15cm
            "N2":         col3,      # 2nd 15cm
            "N3":         col4,      # 3rd 15cm
            "N":          N_user,    # user: N1+N2
            "N_astm":     N_astm,    # tham khảo: N2+N3
        })

    # Loại trùng (cùng depth) — giữ row hợp lệ nhất
    seen: dict[float, dict] = {}
    for r in spt_rows:
        d = r["depth_m"]
        if d not in seen or seen[d]["N"] < r["N"]:
            seen[d] = r
    return sorted(seen.values(), key=lambda r: r["depth_m"])


def import_all() -> dict[str, list[dict]]:
    texts = _load_texts()
    out: dict[str, list[dict]] = {}
    for i in range(1, 13):
        bh = f"KE-HK{i}"
        rows = _parse_hk_spt(texts, i)
        out[bh] = rows
        print(f"  {bh}: {len(rows)} SPT readings "
              f"(depth {rows[0]['depth_m']}–{rows[-1]['depth_m']} m)" if rows else f"  {bh}: 0 (trống)")
    return out


def save_sqlite(data: dict[str, list[dict]]) -> int:
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("PRAGMA table_info(spt_values)")
    cols = [r[1] for r in cur.fetchall()]
    if "elev_m" not in cols:
        print("  [warn] spt_values thiếu cột elev_m — bỏ qua")

    # Xoá data KE cũ
    cur.execute("""
        DELETE FROM spt_values WHERE borehole_id IN (
            SELECT b.id FROM boreholes b JOIN zones z ON b.zone_id=z.id
            WHERE z.code='KE'
        )
    """)
    n_del = cur.rowcount

    n_ins = 0
    for bh_name, rows in data.items():
        cur.execute("SELECT id, elevation_m FROM boreholes WHERE name=?", (bh_name,))
        rec = cur.fetchone()
        if rec is None:
            print(f"  [warn] {bh_name} không tồn tại trong boreholes — bỏ qua")
            continue
        bh_id, elev_m = rec
        for r in rows:
            cur.execute("""
                INSERT INTO spt_values (borehole_id, depth_m, elev_m, N1, N2, N3, N)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                bh_id, r["depth_m"],
                (elev_m - r["depth_m"]) if elev_m is not None else None,
                r["N1"], r["N2"], r["N3"], r["N"],
            ))
            n_ins += 1
    con.commit()
    con.close()
    print(f"  Xóa {n_del} dòng KE cũ → insert {n_ins} dòng mới")
    return n_ins


def save_json(data: dict[str, list[dict]]) -> None:
    payload = {
        "_meta": {
            "generated":    datetime.now().strftime("%Y-%m-%d"),
            "source_dxf":   str(DXF.relative_to(_ROOT)),
            "n_boreholes":  len(data),
            "n_readings":   sum(len(v) for v in data.values()),
            "N_convention": "N = N1 + N2 (col2 + col3 trong DXF, theo user 2026-05-20)",
            "N_alt":        "N_astm = N2 + N3 (chuẩn ASTM, tham khảo)",
            "columns":      "col1=N_prep (seating, bỏ qua); col2=N1; col3=N2; col4=N3",
        },
        "boreholes": data,
    }
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Lưu JSON: {JSON_OUT.relative_to(_ROOT)}")


def save_md(data: dict[str, list[dict]]) -> None:
    n_rd = sum(len(v) for v in data.values())
    lines = [
        f"# 45 — Import SPT 12 Hố khoan Kè KE từ DXF",
        "",
        f"**Nguồn:** `{DXF.relative_to(_ROOT)}`",
        f"**Ngày import:** {datetime.now().strftime('%Y-%m-%d')}",
        f"**Tổng:** 12 hố khoan, {n_rd} SPT readings",
        "",
        "## Quy tắc N (theo user)",
        "",
        "Mỗi SPT row có 4 cột giá trị (theo cấu trúc DXF):",
        "",
        "| Cột DXF | Vị trí | Ý nghĩa | Sử dụng |",
        "|---|---|---|---|",
        "| col1 (x_base+79) | N_prep | Búa đặt (seating) | **Bỏ qua** |",
        "| col2 (x_base+84) | N1 | 1st 15cm penetration | **Tính N** |",
        "| col3 (x_base+89) | N2 | 2nd 15cm penetration | **Tính N** |",
        "| col4 (x_base+94) | N3 | 3rd 15cm penetration | Lưu (N_astm) |",
        "",
        "**Công thức N:** `N = N1 + N2 = col2 + col3` (theo user 2026-05-20)",
        "",
        "Tham khảo: chuẩn ASTM D1586 dùng `N_astm = N2 + N3 = col3 + col4` (bỏ 1 cột seating + 1 cột đầu).",
        "Cả 2 giá trị đều được lưu trong JSON; SQLite `spt_values.N` lưu N theo user.",
        "",
        "## Tổng quan từng hố khoan",
        "",
        "| Hố khoan | Số readings | Depth từ | Depth đến | N min | N max | N TB |",
        "|---|---|---|---|---|---|---|",
    ]
    for bh, rows in data.items():
        if not rows:
            lines.append(f"| {bh} | 0 | – | – | – | – | – |")
            continue
        ns = [r["N"] for r in rows]
        lines.append(
            f"| {bh} | {len(rows)} | {rows[0]['depth_m']:.2f} | {rows[-1]['depth_m']:.2f} | "
            f"{min(ns)} | {max(ns)} | {sum(ns)/len(ns):.1f} |"
        )
    lines.extend([
        "",
        "## Mẫu dữ liệu (KE-HK1, 5 dòng đầu)",
        "",
        "| Depth (m) | N_prep | N1 | N2 | N3 | **N (user)** | N_astm |",
        "|---|---|---|---|---|---|---|",
    ])
    for r in data.get("KE-HK1", [])[:5]:
        lines.append(
            f"| {r['depth_m']:.2f} | {r['N_prep']} | {r['N1']} | {r['N2']} | {r['N3']} | "
            f"**{r['N']}** | {r['N_astm']} |"
        )
    lines.extend([
        "",
        "## Tích hợp với engine NT2",
        "",
        "SPT data import vào `spt_values` được hàm `_get_N160_for_layer()` "
        "trong [scripts/ke_sw_nt_calc.py](scripts/ke_sw_nt_calc.py) đọc tự động.",
        "Sau khi import, các HK trên tuyến kè SW (HK2/3/7/8/9/10/11) sẽ có:",
        "- `Rs` lớp cát tính theo SPT-Meyerhof (Pt.69 TCVN 11823-10)",
        "- `Rp` khi mũi cọc trong cát tính theo Pt.68",
        "- Warning '... không có SPT → bỏ qua ma sát' biến mất",
        "",
        "Re-run: `python scripts/ke_sw_nt_calc.py` để cập nhật `ke_sw_nt_detail`.",
    ])
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Lưu MD: {MD_OUT.relative_to(_ROOT)}")


if __name__ == "__main__":
    print(f"Đọc DXF: {DXF.name}")
    data = import_all()
    print()
    save_sqlite(data)
    save_json(data)
    save_md(data)
    print("\nXong.")
