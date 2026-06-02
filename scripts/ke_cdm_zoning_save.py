"""Lưu phân vùng gia cố CDM khu Bờ kè KE (6 vùng) vào JSON + SQLite.

Nguồn: bản vẽ trắc dọc "TRẮC DỌC CHO CÁC CỤM CỌC XI MĂNG CDM" — 6 vùng phân
chia, mỗi vùng 3 hố khoan (2 HK biên + 1 HK giữa) nối theo tuyến.

Quy ước dự án:
- Tên HK: db_name = "KE-HKx" (CLAUDE.md §10)
- Prefix module: ke_cdm_ (§11)
- Lưu CẢ JSON lẫn SQLite, idempotent (§5, Rule 8)

Bảng SQLite:
- ke_cdm_zones            : metadata mỗi vùng (số HK, tổng chiều dài, danh sách HK)
- ke_cdm_zone_boreholes   : thành viên HK của mỗi vùng (vị trí, cao độ, khoảng cách)

Chạy:  python scripts/ke_cdm_zoning_save.py
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_JSON_OUT = _ROOT / "data" / "ke_cdm_zoning_6zones.json"

# Các đường dẫn DB có thể tồn tại (ghi vào những DB nào hiện diện)
_DB_PATHS = [
    Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite"),  # LOCAL dev (nếu có)
    _ROOT / "data" / "TTHC.sqlite",                   # PROJECT (git)
]

ZONE_TITLE = "TRẮC DỌC CHO CÁC CỤM CỌC XI MĂNG CDM"
ZONE_AREA = "KE"          # Khu vực Bờ kè (Kè Công viên)
SOURCE = "Bản vẽ trắc dọc phân vùng CDM — 6 vùng (Phạm vi Vùng 1-6)"

# Cao độ miệng hố khoan (m) — đọc từ hàng "CAO ĐỘ (M)" trên bản vẽ
ELEV_M = {
    "KE-HK1": 1.830,
    "KE-HK2": 2.034,
    "KE-HK3": 1.256,
    "KE-HK4": 1.824,
    "KE-HK5": 0.883,
    "KE-HK6": -0.160,
    "KE-HK7": -0.561,
    "KE-HK8": 2.579,
    "KE-HK9": -2.250,
    "KE-HK10": -0.381,
    "KE-HK11": -0.220,
    "KE-HK12": -1.058,
}

# Mỗi vùng: danh sách HK theo thứ tự tuyến + khoảng cách (m) giữa các HK liên tiếp.
# segments[i] = khoảng cách từ bh_list[i] đến bh_list[i+1]
ZONES = {
    1: {"bh": ["KE-HK1", "KE-HK11", "KE-HK10"], "seg": [226.0, 152.9]},
    2: {"bh": ["KE-HK11", "KE-HK10", "KE-HK9"], "seg": [152.9, 167.7]},
    3: {"bh": ["KE-HK10", "KE-HK9", "KE-HK8"], "seg": [167.7, 149.5]},
    4: {"bh": ["KE-HK7", "KE-HK6", "KE-HK12"], "seg": [190.3, 134.8]},
    5: {"bh": ["KE-HK1", "KE-HK2", "KE-HK3"], "seg": [130.6, 156.9]},
    6: {"bh": ["KE-HK3", "KE-HK4", "KE-HK5"], "seg": [167.9, 130.8]},
}


def build_payload() -> dict:
    """Dựng cấu trúc dữ liệu đầy đủ cho JSON + SQLite."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    zones_out = []
    members = []  # flat list cho SQLite ke_cdm_zone_boreholes

    for zno in sorted(ZONES):
        z = ZONES[zno]
        bhs = z["bh"]
        segs = z["seg"]
        total_len = round(sum(segs), 1)
        # vị trí: HK đầu = 'start', HK cuối = 'end', còn lại = 'mid'
        zone_members = []
        for i, bh in enumerate(bhs):
            if i == 0:
                pos = "start"
            elif i == len(bhs) - 1:
                pos = "end"
            else:
                pos = "mid"
            dist_next = segs[i] if i < len(segs) else None
            rec = {
                "bh_name": bh,
                "seq": i + 1,
                "position": pos,
                "elevation_m": ELEV_M.get(bh),
                "dist_to_next_m": dist_next,
            }
            zone_members.append(rec)
            members.append({"zone_no": zno, **rec})

        zones_out.append({
            "zone_no": zno,
            "zone_name": f"Vùng {zno}",
            "n_boreholes": len(bhs),
            "bh_list": bhs,
            "total_length_m": total_len,
            "boreholes": zone_members,
        })

    all_bh = sorted({m["bh_name"] for m in members},
                    key=lambda s: int(s.replace("KE-HK", "")))
    payload = {
        "_meta": {
            "title": ZONE_TITLE,
            "area": ZONE_AREA,
            "area_desc": "Khu vực Bờ kè (Kè Công viên KE)",
            "source": SOURCE,
            "n_zones": len(zones_out),
            "n_boreholes_unique": len(all_bh),
            "updated": now,
        },
        "boreholes_unique": all_bh,
        "elevations_m": {bh: ELEV_M[bh] for bh in all_bh},
        "zones": zones_out,
        "_flat_members": members,
    }
    return payload


def write_json(payload: dict) -> None:
    out = {k: v for k, v in payload.items() if k != "_flat_members"}
    _JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    _JSON_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"[JSON] {_JSON_OUT}  ({len(out['zones'])} vùng)")


def create_tables(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS ke_cdm_zones (
            zone_no         INTEGER PRIMARY KEY,
            zone_name       TEXT,
            area            TEXT,
            n_boreholes     INTEGER,
            bh_list         TEXT,          -- JSON array tên HK theo thứ tự tuyến
            total_length_m  REAL,
            source          TEXT,
            updated_at      TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ke_cdm_zone_boreholes (
            zone_no         INTEGER,
            bh_name         TEXT,
            seq             INTEGER,        -- thứ tự trong tuyến (1-based)
            position        TEXT,           -- start | mid | end
            elevation_m     REAL,
            dist_to_next_m  REAL,           -- khoảng cách tới HK kế tiếp (m)
            updated_at      TEXT,
            PRIMARY KEY (zone_no, bh_name)
        )
    """)


def save_sqlite(payload: dict, db_path: Path) -> int:
    con = sqlite3.connect(str(db_path))
    try:
        create_tables(con)
        now = payload["_meta"]["updated"]
        for z in payload["zones"]:
            con.execute(
                "INSERT OR REPLACE INTO ke_cdm_zones "
                "(zone_no, zone_name, area, n_boreholes, bh_list, "
                " total_length_m, source, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (z["zone_no"], z["zone_name"], ZONE_AREA, z["n_boreholes"],
                 json.dumps(z["bh_list"], ensure_ascii=False),
                 z["total_length_m"], SOURCE, now),
            )
        for m in payload["_flat_members"]:
            con.execute(
                "INSERT OR REPLACE INTO ke_cdm_zone_boreholes "
                "(zone_no, bh_name, seq, position, elevation_m, "
                " dist_to_next_m, updated_at) VALUES (?,?,?,?,?,?,?)",
                (m["zone_no"], m["bh_name"], m["seq"], m["position"],
                 m["elevation_m"], m["dist_to_next_m"], now),
            )
        con.commit()
        n_zones = con.execute("SELECT COUNT(*) FROM ke_cdm_zones").fetchone()[0]
        n_mem = con.execute(
            "SELECT COUNT(*) FROM ke_cdm_zone_boreholes").fetchone()[0]
        print(f"[SQLite] {db_path}  -> ke_cdm_zones={n_zones}, "
              f"ke_cdm_zone_boreholes={n_mem}")
        return n_mem
    finally:
        con.close()


def main() -> None:
    payload = build_payload()
    write_json(payload)
    wrote_any = False
    for db in _DB_PATHS:
        if db.exists():
            save_sqlite(payload, db)
            wrote_any = True
        else:
            print(f"[skip] khong ton tai: {db}")
    if not wrote_any:
        print("[WARN] khong tim thay DB nao de ghi!")

    m = payload["_meta"]
    print(f"\nTong: {m['n_zones']} vung, "
          f"{m['n_boreholes_unique']} HK rieng biet")


if __name__ == "__main__":
    main()
