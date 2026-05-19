"""
Mapping tên hố khoan KE giữa các nguồn dữ liệu — 202605-TTHC.

Nguồn gốc tên:
  pdf_name   : tên gốc trong báo cáo địa chất PDF  (3BOKECONGVIEN-HK1)
  short_name : tên ngắn không khu vực — KHÔNG DÙNG  (HK1)
  db_name    : tên chuẩn dùng MỌI NƠI              (KE-HK1)  ← CHUẨN DUY NHẤT

Quy tắc bắt buộc:
  - Mọi query SQLite, code Python, file JSON, báo cáo, bảng biểu → dùng db_name (KE-HK1)
  - KHÔNG dùng short_name (HK1) — dự án có nhiều khu vực KE/BXN/NHC, HK1 gây nhầm lẫn
  - Chỉ dùng pdf_name khi cần đối chiếu với báo cáo địa chất PDF gốc

Tuyến kè SW (theo bình đồ khảo sát):
  on_sw_alignment=True  : KE-HK2, KE-HK3, KE-HK7, KE-HK8, KE-HK9, KE-HK10, KE-HK11
  on_sw_alignment=False : KE-HK1, KE-HK4, KE-HK5, KE-HK6, KE-HK12

Hàm công khai:
  db_name(short_name)       → 'KE-HK1'
  short_name(db_name)       → 'HK1'
  pdf_name(db_name)         → '3BOKECONGVIEN-HK1'
  on_alignment(db_name)     → True/False
  alignment_boreholes()     → list[str]  (chỉ các HK trên tuyến kè)
  all_mappings()            → list[dict]
  load_from_db(db_path)     → list[dict]  (từ bảng borehole_name_mapping)
"""
import sqlite3
from pathlib import Path

_HERE = Path(__file__).parent
_DB   = _HERE.parent / "data" / "TTHC.sqlite"

# Bảng mapping tĩnh — nguồn gốc: SQLite + MD 15-soil-profile-202605-TTHC.md
_MAPPING: list[dict] = [
    {"db_name": "KE-HK1",  "short_name": "HK1",  "pdf_name": "3BOKECONGVIEN-HK1",
     "Z_m": -0.800, "x_coord_m": None,         "y_coord_m": None,
     "on_sw_alignment": False, "note": ""},
    {"db_name": "KE-HK2",  "short_name": "HK2",  "pdf_name": "3BOKECONGVIEN-HK2",
     "Z_m":  2.030, "x_coord_m": 1191606.808,  "y_coord_m": 605941.494,
     "on_sw_alignment": True,  "note": ""},
    {"db_name": "KE-HK3",  "short_name": "HK3",  "pdf_name": "3BOKECONGVIEN-HK3",
     "Z_m":  1.256, "x_coord_m": 1191735.670,  "y_coord_m": 606027.680,
     "on_sw_alignment": True,  "note": ""},
    {"db_name": "KE-HK4",  "short_name": "HK4",  "pdf_name": "3BOKECONGVIEN-HK4",
     "Z_m": -1.400, "x_coord_m": None,         "y_coord_m": None,
     "on_sw_alignment": False, "note": ""},
    {"db_name": "KE-HK5",  "short_name": "HK5",  "pdf_name": "3BOKECONGVIEN-HK5",
     "Z_m": -0.680, "x_coord_m": None,         "y_coord_m": None,
     "on_sw_alignment": False, "note": ""},
    {"db_name": "KE-HK6",  "short_name": "HK6",  "pdf_name": "3BOKECONGVIEN-HK6",
     "Z_m": -1.150, "x_coord_m": None,         "y_coord_m": None,
     "on_sw_alignment": False, "note": ""},
    {"db_name": "KE-HK7",  "short_name": "HK7",  "pdf_name": "3BOKECONGVIEN-HK7",
     "Z_m": -0.561, "x_coord_m": 1191886.862,  "y_coord_m": 605868.540,
     "on_sw_alignment": True,  "note": ""},
    {"db_name": "KE-HK8",  "short_name": "HK8",  "pdf_name": "3BOKECONGVIEN-HK8",
     "Z_m":  2.579, "x_coord_m": 1191979.459,  "y_coord_m": 605751.412,
     "on_sw_alignment": True,
     "note": "Có lớp XMD (CDM gia cố Lớp 1). su_XMD=10 kPa (su gốc Lớp 1)"},
    {"db_name": "KE-HK9",  "short_name": "HK9",  "pdf_name": "3BOKECONGVIEN-HK9",
     "Z_m": -2.250, "x_coord_m": 1191863.956,  "y_coord_m": 605805.575,
     "on_sw_alignment": True,  "note": ""},
    {"db_name": "KE-HK10", "short_name": "HK10", "pdf_name": "3BOKECONGVIEN-HK10",
     "Z_m": -0.381, "x_coord_m": 1191728.126,  "y_coord_m": 605742.279,
     "on_sw_alignment": True,
     "note": "Kiểm soát NT1 (biên 0.3m) → SW-940"},
    {"db_name": "KE-HK11", "short_name": "HK11", "pdf_name": "3BOKECONGVIEN-HK11",
     "Z_m": -0.220, "x_coord_m": 1191580.576,  "y_coord_m": 605751.153,
     "on_sw_alignment": True,  "note": ""},
    {"db_name": "KE-HK12", "short_name": "HK12", "pdf_name": "3BOKECONGVIEN-HK12",
     "Z_m": -1.058, "x_coord_m": None,         "y_coord_m": None,
     "on_sw_alignment": False,
     "note": "Có lớp XMD từ độ sâu 11m. Cọc ván SPECIAL — thiết kế riêng"},
]

_BY_DB    = {m["db_name"]:    m for m in _MAPPING}
_BY_SHORT = {m["short_name"]: m for m in _MAPPING}
_BY_PDF   = {m["pdf_name"]:   m for m in _MAPPING}


def db_name(short: str) -> str | None:
    """'HK1' → 'KE-HK1'. Trả None nếu không tìm thấy."""
    m = _BY_SHORT.get(short)
    return m["db_name"] if m else None


def short_name(db: str) -> str | None:
    """'KE-HK1' → 'HK1'."""
    m = _BY_DB.get(db)
    return m["short_name"] if m else None


def pdf_name(db: str) -> str | None:
    """'KE-HK1' → '3BOKECONGVIEN-HK1'."""
    m = _BY_DB.get(db)
    return m["pdf_name"] if m else None


def on_alignment(db: str) -> bool:
    """'KE-HK2' → True  |  'KE-HK1' → False."""
    m = _BY_DB.get(db)
    return bool(m["on_sw_alignment"]) if m else False


def alignment_boreholes() -> list[str]:
    """Trả về list db_name các HK nằm trên tuyến kè SW."""
    return [m["db_name"] for m in _MAPPING if m["on_sw_alignment"]]


def all_mappings() -> list[dict]:
    """Trả về toàn bộ mapping dạng list[dict]."""
    return list(_MAPPING)


def load_from_db(db_path: Path = _DB) -> list[dict]:
    """Đọc mapping từ bảng borehole_name_mapping trong SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM borehole_name_mapping WHERE zone_code='KE' ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    print("=== Mapping hố khoan KE (202605-TTHC) ===")
    print(f"{'db_name':<12} {'short_name':<8} {'Z_m':>7} {'Tọa độ':>8} {'Tuyến kè':>10} {'pdf_name'}")
    for m in _MAPPING:
        coords = "Có" if m["x_coord_m"] else "Thiếu"
        tuyen = "Trên tuyến" if m["on_sw_alignment"] else "Ngoài tuyến"
        print(f"{m['db_name']:<12} {m['short_name']:<8} {m['Z_m']:>7.3f} {coords:>8}  {tuyen:<12}  {m['pdf_name']}")
    print(f"\nTrên tuyến kè SW ({len(alignment_boreholes())} HK): {', '.join(alignment_boreholes())}")

    print("\n=== Kiểm tra từ SQLite ===")
    for r in load_from_db():
        print(f"  {r['db_name']:<12} Z={r['Z_m']}  {r.get('note','')[:60]}")
