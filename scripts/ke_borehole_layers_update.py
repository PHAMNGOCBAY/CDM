"""ke_borehole_layers_update.py — Cập nhật tọa độ + cao độ + địa tầng 12 HK KE.

Nguồn: hồ sơ khảo sát địa chất công trình Trung tâm hành chính TP.HCM
       (bảng thống kê do user cung cấp 2026-05-22).

Cập nhật:
  - `boreholes` (KE-HK1..HK12): x_coord_m, y_coord_m, elevation_m
  - `layers` (KE-HK1..HK12): xóa hết, chèn lại theo data mới
  - JSON `data/ke_layers_202605_TTHC.json`: snapshot để dễ tra cứu

Usage:
  python scripts/ke_borehole_layers_update.py
  python scripts/ke_borehole_layers_update.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "TTHC.sqlite"
JSON_OUT = ROOT / "data" / "ke_layers_202605_TTHC.json"


# ── DATA: 12 HK KE — (symbol, description, depth_bot_m) theo thứ tự từ trên xuống
# depth_top sẽ tự suy ra = depth_bot của lớp trước (hoặc 0.0 cho lớp đầu)
KE_DATA: dict[str, dict] = {
    "HK1":  {"x": 1191494.989, "y": 605877.216, "elev":  1.830, "layers": [
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                              24.80),
        ("2a",  "Cát lẫn sét, bụi màu xám xanh, kết cấu chặt vừa",                        29.20),
        ("3",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm - dẻo cứng",                37.00),
        ("5",   "Sét ít dẻo màu nâu vàng, trạng thái nửa cứng - cứng",                    50.00),
    ]},
    "HK2":  {"x": 1191606.808, "y": 605941.494, "elev":  2.034, "layers": [
        ("F",   "Lớp san lấp",                                                              2.10),
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                              22.10),
        ("2a",  "Cát lẫn sét, bụi màu xám xanh, kết cấu chặt vừa",                        27.70),
        ("3",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm - dẻo cứng",                33.60),
        ("4",   "Cát lẫn sét bụi, màu xám xanh, kết cấu chặt vừa",                        42.60),
        ("5",   "Sét ít dẻo màu nâu vàng, trạng thái nửa cứng - cứng",                    46.00),
    ]},
    "HK3":  {"x": 1191735.670, "y": 606027.680, "elev":  1.256, "layers": [
        ("F",   "Lớp san lấp",                                                              1.00),
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                              20.20),
        ("2b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",            29.00),
        ("3",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm - dẻo cứng",                31.00),
        ("3",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm - dẻo cứng",                35.00),
        ("4",   "Cát lẫn sét bụi, màu xám xanh, kết cấu chặt vừa",                        40.30),
        ("5",   "Sét ít dẻo màu nâu vàng, trạng thái nửa cứng - cứng",                    46.00),
    ]},
    "HK4":  {"x": 1191862.312, "y": 606118.657, "elev":  1.824, "layers": [
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                              21.30),
        ("2b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",            29.00),
        ("4",   "Cát lẫn sét bụi, màu xám xanh, kết cấu chặt vừa",                        37.70),
        ("5",   "Sét ít dẻo màu nâu vàng, trạng thái nửa cứng - cứng",                    40.00),
    ]},
    "HK5":  {"x": 1191991.551, "y": 606111.803, "elev":  0.883, "layers": [
        ("F",   "Lớp san lấp",                                                              1.10),
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                              21.20),
        ("2b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",            23.00),
        ("2b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",            29.30),
        ("2b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",            36.80),
        ("5",   "Sét ít dẻo màu nâu vàng, trạng thái nửa cứng - cứng",                    41.70),
        ("6",   "Cát lẫn sét, màu nâu vàng, kết cấu chặt",                                43.40),
        ("6",   "Cát lẫn bụi, màu xám nâu, kết cấu chặt",                                 51.50),
        ("6",   "Cát lẫn bụi, màu xám nâu, kết cấu chặt",                                 55.60),
        ("6",   "Cát lẫn sét, màu nâu vàng, kết cấu chặt",                                57.20),
        ("6",   "Cát lẫn sét, màu nâu vàng, kết cấu chặt",                                61.20),
        ("6",   "Cát lẫn sét, màu nâu vàng, kết cấu chặt",                                71.50),
        ("7",   "Cát lẫn bụi màu xám nâu, kết cấu chặt",                                  85.00),
    ]},
    "HK6":  {"x": 1191971.117, "y": 606004.520, "elev": -0.160, "layers": [
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                              17.00),
        ("1b",  "Sét ít dẻo xen kẹp cát lẫn sét, bụi màu xám xanh, xám ghi, "
                "trạng thái dẻo chảy - dẻo mềm",                                          19.00),
        ("1b",  "Sét ít dẻo xen kẹp cát lẫn sét, bụi màu xám xanh, xám ghi, "
                "trạng thái dẻo chảy - dẻo mềm",                                          23.50),
        ("2b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",            31.00),
        ("4",   "Cát lẫn sét bụi, màu xám xanh, kết cấu chặt vừa",                        33.60),
        ("5",   "Sét ít dẻo màu nâu vàng, trạng thái nửa cứng - cứng",                    40.00),
    ]},
    "HK7":  {"x": 1191886.862, "y": 605868.540, "elev": -0.561, "layers": [
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                              21.00),
        ("2b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",            30.80),
        ("3",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm - dẻo cứng",                33.00),
        ("4",   "Cát lẫn sét bụi, màu xám xanh, kết cấu chặt vừa",                        35.00),
        ("5",   "Sét ít dẻo màu nâu vàng, trạng thái nửa cứng - cứng",                    40.00),
    ]},
    "HK8":  {"x": 1191979.459, "y": 605751.412, "elev":  2.579, "layers": [
        ("F",   "Lớp san lấp",                                                              2.90),
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                                6.70),
        ("XMD", "Xi măng đất",                                                             22.40),
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                              27.00),
        ("1b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",            28.80),
        ("2c",  "Cát lẫn sét, bụi màu xám xanh, kết cấu chặt vừa",                        32.00),
        ("4",   "Cát lẫn sét bụi, màu xám xanh, kết cấu chặt vừa",                        40.00),
    ]},
    "HK9":  {"x": 1191863.956, "y": 605805.575, "elev": -2.250, "layers": [
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                              21.00),
        ("1b",  "Sét ít dẻo xen kẹp cát lẫn sét, bụi màu xám xanh, "
                "trạng thái dẻo chảy - dẻo mềm",                                          23.50),
        ("2b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",            27.00),
        ("3",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm - dẻo cứng",                29.50),
        ("3",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm - dẻo cứng",                31.50),
        ("4",   "Cát lẫn sét bụi, màu xám xanh, kết cấu chặt vừa",                        36.60),
        ("5",   "Sét ít dẻo màu nâu vàng, trạng thái nửa cứng - cứng",                    47.00),
        ("6",   "Cát lẫn sét, màu nâu vàng, kết cấu chặt",                                53.00),
        ("6",   "Cát lẫn sét, màu nâu vàng, kết cấu chặt",                                62.10),
        ("7",   "Cát lẫn bụi màu xám nâu, kết cấu chặt",                                  63.10),
        ("7",   "Cát lẫn bụi màu xám nâu, kết cấu chặt",                                  70.00),
    ]},
    "HK10": {"x": 1191728.126, "y": 605742.279, "elev": -0.381, "layers": [
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                              25.00),
        ("1b",  "Sét ít dẻo xen kẹp cát lẫn sét, bụi màu xám xanh, "
                "trạng thái dẻo chảy - dẻo mềm",                                          27.00),
        ("2b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",            28.80),
        ("3",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm - dẻo cứng",                30.10),
        ("3",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm - dẻo cứng",                34.10),
        ("4",   "Cát lẫn sét bụi, màu xám xanh, kết cấu chặt vừa",                        41.00),
        ("5",   "Sét ít dẻo màu nâu vàng, trạng thái nửa cứng - cứng",                    46.00),
    ]},
    "HK11": {"x": 1191580.576, "y": 605751.153, "elev": -0.220, "layers": [
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                              24.20),
        ("1b",  "Sét ít dẻo xen kẹp cát lẫn sét, bụi màu xám xanh, "
                "trạng thái dẻo chảy - dẻo mềm",                                          25.20),
        ("2b",  "Cát lẫn sét, bụi màu xám xanh, kết cấu xốp xen kẹp chặt vừa",            29.00),
        ("3",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm - dẻo cứng",                30.10),
        ("4",   "Cát lẫn sét bụi, màu xám xanh, kết cấu chặt vừa",                        41.20),
        ("5",   "Sét ít dẻo màu nâu vàng, trạng thái nửa cứng - cứng",                    46.00),
    ]},
    "HK12": {"x": 1192085.504, "y": 606075.287, "elev": -1.058, "layers": [
        ("1",   "Sét rất dẻo màu xám xanh, trạng thái chảy",                              11.00),
        # Đáy XMD = elev -24.96 m, depth = -1.058 - (-24.96) = 23.902 m (user 2026-05-22)
        ("XMD", "Xi măng đất",                                                             23.902),
        ("1b",  "Sét ít dẻo xen kẹp cát lẫn sét, bụi màu xám xanh, "
                "trạng thái dẻo chảy - dẻo mềm",                                          27.00),
        ("3",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm - dẻo cứng",                31.00),
        ("3",   "Sét rất dẻo màu xám xanh, trạng thái dẻo mềm - dẻo cứng",                35.00),
        ("4",   "Cát lẫn sét bụi, màu xám xanh, kết cấu chặt vừa",                        36.00),
    ]},
}


def build_layers_with_top(raw_layers: list[tuple[str, str, float]]
                           ) -> list[dict]:
    """Bổ sung depth_top + thickness từ chuỗi (symbol, desc, depth_bot)."""
    out = []
    depth_top = 0.0
    for symbol, desc, depth_bot in raw_layers:
        depth_bot = float(depth_bot)
        thk = depth_bot - depth_top
        out.append({
            "symbol":       symbol,
            "description":  desc,
            "depth_top_m":  round(depth_top, 3),
            "depth_bot_m":  round(depth_bot, 3),
            "thickness_m":  round(thk, 3),
        })
        depth_top = depth_bot
    return out


def write_json(data: dict[str, dict]) -> None:
    payload = {
        "_meta": {
            "project":   "260512 CVTT-TTHC — Trung tâm Hành chính TP.HCM",
            "zone":      "KE — Kè Công Viên",
            "source":    "Hồ sơ khảo sát địa chất công trình TTHC (user nhập)",
            "updated":   date.today().isoformat(),
            "n_boreholes": len(data),
        },
        "boreholes": [
            {
                "name":         f"KE-{nm}",
                "name_raw":     nm,
                "x_coord_m":    d["x"],
                "y_coord_m":    d["y"],
                "elevation_m":  d["elev"],
                "layers":       build_layers_with_top(d["layers"]),
            } for nm, d in data.items()
        ],
    }
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")


def _ensure_data_versions_table(cur: sqlite3.Cursor) -> None:
    """Bảng key-value tracking version của các tập dữ liệu nguồn.

    Mọi cache downstream (ke_sw_stability, ke_sw_nt_detail...) so sánh với
    `ts` của key này để biết có stale hay không.
    """
    cur.execute("""
        CREATE TABLE IF NOT EXISTS data_versions (
            data_key TEXT PRIMARY KEY,
            ts       TEXT NOT NULL,
            note     TEXT
        )
    """)


def _bump_data_version(cur: sqlite3.Cursor, key: str, note: str = "") -> None:
    """Ghi/cập nhật mốc thời gian cho 1 nguồn dữ liệu."""
    from datetime import datetime as _dt
    cur.execute("""
        INSERT OR REPLACE INTO data_versions (data_key, ts, note)
        VALUES (?, ?, ?)
    """, (key, _dt.now().strftime("%Y-%m-%d %H:%M:%S"), note))


def update_db(data: dict[str, dict]) -> tuple[int, int, int]:
    """Update boreholes + layers cho KE-HK1..HK12.

    Returns (n_bh_updated, n_layers_deleted, n_layers_inserted).
    """
    n_bh_upd = 0; n_lay_del = 0; n_lay_ins = 0
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        cur = conn.cursor()
        _ensure_data_versions_table(cur)

        # Map HK name → id
        cur.execute("SELECT id, name FROM boreholes WHERE name LIKE 'KE-HK%'")
        bh_id_map = {name: bid for bid, name in cur.fetchall()}

        for nm, d in data.items():
            db_name = f"KE-{nm}"
            if db_name not in bh_id_map:
                print(f"WARN: {db_name} không có trong DB — bỏ qua", file=sys.stderr)
                continue
            bh_id = bh_id_map[db_name]

            # 1. Update boreholes (x, y, elevation, depth tổng = đáy lớp cuối)
            _layers_full = build_layers_with_top(d["layers"])
            _max_depth = _layers_full[-1]["depth_bot_m"] if _layers_full else 0.0
            cur.execute("""
                UPDATE boreholes
                SET x_coord_m = ?, y_coord_m = ?, elevation_m = ?, depth_m = ?
                WHERE id = ?
            """, (float(d["x"]), float(d["y"]), float(d["elev"]),
                  float(_max_depth), bh_id))
            n_bh_upd += cur.rowcount

            # 2. DELETE old layers
            cur.execute("DELETE FROM layers WHERE borehole_id = ?", (bh_id,))
            n_lay_del += cur.rowcount

            # 3. INSERT new layers
            for ly in _layers_full:
                cur.execute("""
                    INSERT INTO layers (borehole_id, symbol, description,
                                         depth_top_m, depth_bot_m, thickness_m)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (bh_id, ly["symbol"], ly["description"],
                      ly["depth_top_m"], ly["depth_bot_m"], ly["thickness_m"]))
                n_lay_ins += 1

        # Bump version → mọi cache downstream sẽ phát hiện stale qua ts compare
        _bump_data_version(
            cur, "ke_geology",
            note=f"updated {len(data)} HK · {n_lay_ins} layers",
        )
        conn.commit()
    return n_bh_upd, n_lay_del, n_lay_ins


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                     help="Không ghi DB, chỉ in tổng số layers per HK")
    args = ap.parse_args()

    print(f"Boreholes: {len(KE_DATA)} HK KE")
    total_lay = 0
    for nm, d in KE_DATA.items():
        lays = build_layers_with_top(d["layers"])
        total_lay += len(lays)
        print(f"  KE-{nm:<5}  X={d['x']:,.3f}  Y={d['y']:,.3f}  Z={d['elev']:+.3f}m  "
              f"layers={len(lays)}  max depth={lays[-1]['depth_bot_m']:.1f}m")
    print(f"Total layers: {total_lay}")

    if args.dry_run:
        print("\n[dry-run] không ghi DB/JSON.")
        return 0

    write_json(KE_DATA)
    print(f"\nJSON ghi: {JSON_OUT}")
    n_bh, n_del, n_ins = update_db(KE_DATA)
    print(f"SQLite: cập nhật {n_bh} boreholes, xóa {n_del} layers cũ, "
          f"chèn {n_ins} layers mới.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
