"""
thuyvan_phuan_import.py — Parse mực nước trung bình ngày trạm Phú An sông Sài Gòn 1977–2024.

Nguồn:
  - THUYVAN-PhuAn_ H(77-24)ok.xlsx     → daily MNTB time series + annual summary
  - THUYVAN-Tidal information summary_PhuAnStation.xlsx  → đỉnh triều tối đa theo năm

Output:
  - data/thuyvan_phuan_daily_77-24.json    — daily series (year, month, day, h_cm)
  - data/thuyvan_phuan_summary.json        — annual summary + tidal peaks
  - SQLite tables: thuyvan_daily, thuyvan_annual_summary, thuyvan_tidal_peaks

Cấu trúc block 44 dòng/năm:
  [0] Trạm: Phú An
  [1] Sông: Sài Gòn ...
  [2] NĂM : XXXX
  [3] Header: 'Ngày', 'I', 'II', ..., 'XII'
  [4..34] 31 dòng dữ liệu (ngày 1-31 × 12 tháng) — cell rỗng nếu tháng không có ngày đó
  [35] 'Tổng' theo tháng
  [36] 'T bình' theo tháng
  [37] 'Max' theo tháng
  [38] 'Ngày' của Max theo tháng
  [39] 'Min' theo tháng
  [40] 'Ngày' của Min theo tháng
  [41..43] Đặc trưng năm: Trung bình / Lớn nhất / Nhỏ nhất
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
_DB   = _ROOT / "data" / "TTHC.sqlite"
_DATA = _ROOT / "data"

ROMAN_MONTHS = ["I", "II", "III", "IV", "V", "VI",
                "VII", "VIII", "IX", "X", "XI", "XII"]


def parse_daily_xlsx(fp: Path) -> tuple[list[dict], list[dict]]:
    """Đọc file XLSX 'Hn' sheet → (daily_records, annual_summary).

    daily_records: [{'year', 'month', 'day', 'iso_date', 'h_cm'}, ...]
    annual_summary: [{'year', 'avg_cm', 'max_cm', 'min_cm',
                      'max_day', 'max_month', 'min_day', 'min_month',
                      'monthly_avg_cm', 'monthly_max_cm', 'monthly_min_cm'}, ...]
    """
    from python_calamine import CalamineWorkbook
    wb = CalamineWorkbook.from_path(str(fp))
    sheet = wb.get_sheet_by_name("Hn")
    rows = sheet.to_python()

    # Tìm tất cả block "NĂM : XXXX"
    year_starts: list[tuple[int, int]] = []
    for i, row in enumerate(rows):
        if not row or len(row) < 7:
            continue
        for j, c in enumerate(row):
            if isinstance(c, str) and "NĂM" in c:
                yr = next((v for v in row[j + 1:] if v not in (None, "")), None)
                if yr is not None:
                    try:
                        year_starts.append((i, int(yr)))
                    except (ValueError, TypeError):
                        pass
                break

    daily: list[dict] = []
    annual: list[dict] = []

    for blk_idx, (row_start, year) in enumerate(year_starts):
        # row_start: vị trí 'NĂM : XXXX'
        # header tại row_start + 1
        # 31 ngày: row_start + 2 đến row_start + 32
        # 'Tổng' tại row_start + 33
        # 'T bình' tại row_start + 34
        # 'Max' tại row_start + 35
        # 'Ngày Max' tại row_start + 36
        # 'Min' tại row_start + 37
        # 'Ngày Min' tại row_start + 38
        # 'Đặc trưng' năm: row_start + 39, 40, 41

        # Parse 31 ngày × 12 tháng
        for d in range(1, 32):
            r_idx = row_start + 1 + d   # row 'Ngày 1' = row_start + 2
            if r_idx >= len(rows):
                break
            row = rows[r_idx]
            if not row or len(row) < 13:
                continue
            # Cột 0 là Ngày (số) — verify
            try:
                day_val = int(row[0])
                if day_val != d:
                    continue
            except (ValueError, TypeError):
                continue

            for m_idx, m_roman in enumerate(ROMAN_MONTHS):
                col = m_idx + 1
                if col >= len(row):
                    break
                cell = row[col]
                if cell in (None, ""):
                    continue
                try:
                    h = float(cell)
                except (ValueError, TypeError):
                    continue
                month = m_idx + 1
                # Kiểm tra ngày hợp lệ cho tháng
                try:
                    iso = date(year, month, d).isoformat()
                except ValueError:
                    # Vd: 31/02 → bỏ qua
                    continue
                daily.append({
                    "year":     year,
                    "month":    month,
                    "day":      d,
                    "iso_date": iso,
                    "h_cm":     round(h, 1),
                })

        # Annual summary — đặc trưng năm
        def _row_at(offset: int):
            ri = row_start + 39 + offset
            return rows[ri] if 0 <= ri < len(rows) else []

        # Row đặc trưng có format: ['Đặc', '', '', '    Trung bình năm : ', '', '', VALUE, 'cm', ...]
        avg_year_row = _row_at(0)
        max_year_row = _row_at(1)
        min_year_row = _row_at(2)

        def _extract_value(r):
            """Lấy giá trị numeric đầu tiên sau ô có ':'."""
            if not r:
                return None
            for i, c in enumerate(r):
                if isinstance(c, str) and ":" in c:
                    for v in r[i + 1:]:
                        if isinstance(v, (int, float)):
                            return float(v)
            return None

        def _extract_day_month(r):
            """Lấy (day, month_int) từ row Max/Min năm."""
            if not r:
                return None, None
            day_val = None
            month_str = None
            # Pattern: ..., 'Ngày', day, 'Tháng', 'IX', ...
            for i, c in enumerate(r):
                if isinstance(c, str) and "Ngày" in c:
                    for v in r[i + 1:i + 4]:
                        if isinstance(v, (int, float)):
                            day_val = int(v)
                            break
                if isinstance(c, str) and "Tháng" in c:
                    for v in r[i + 1:i + 4]:
                        if isinstance(v, str) and v.strip() in ROMAN_MONTHS:
                            month_str = v.strip()
                            break
            m_int = ROMAN_MONTHS.index(month_str) + 1 if month_str else None
            return day_val, m_int

        avg_year = _extract_value(avg_year_row)
        max_year = _extract_value(max_year_row)
        min_year = _extract_value(min_year_row)
        max_d, max_m = _extract_day_month(max_year_row)
        min_d, min_m = _extract_day_month(min_year_row)

        # Monthly stats từ block
        monthly_avg = _row_at(36 - 39)  # row_start + 36 = T bình
        monthly_max = _row_at(37 - 39)  # row_start + 37 = Max
        monthly_min = _row_at(39 - 39)  # row_start + 39 = Min

        def _12floats(r):
            if not r or len(r) < 13:
                return [None] * 12
            return [(float(c) if isinstance(c, (int, float)) else None)
                    for c in r[1:13]]

        annual.append({
            "year":            year,
            "avg_cm":          round(avg_year, 2) if avg_year is not None else None,
            "max_cm":          round(max_year, 1) if max_year is not None else None,
            "min_cm":          round(min_year, 1) if min_year is not None else None,
            "max_day":         max_d,
            "max_month":       max_m,
            "min_day":         min_d,
            "min_month":       min_m,
            "monthly_avg_cm":  [round(v, 2) if v is not None else None
                                for v in _12floats(monthly_avg)],
            "monthly_max_cm":  [round(v, 1) if v is not None else None
                                for v in _12floats(monthly_max)],
            "monthly_min_cm":  [round(v, 1) if v is not None else None
                                for v in _12floats(monthly_min)],
        })

    return daily, annual


def parse_tidal_summary_xlsx(fp: Path) -> list[dict]:
    """Parse file summary đỉnh triều tối đa theo năm.

    Returns: [{'year': int, 'peak_cm': int}, ...] (sorted by peak_cm asc as in source)
    """
    import openpyxl
    wb = openpyxl.load_workbook(fp, data_only=True)
    ws = wb["Sheet1"]
    out: list[dict] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0 or not row:
            continue
        # row: (STT, peak_cm, year)
        if len(row) < 3:
            continue
        peak, yr = row[1], row[2]
        if isinstance(peak, (int, float)) and isinstance(yr, (int, float)):
            out.append({"year": int(yr), "peak_cm": int(peak)})
    return out


def create_tables(db_path: Optional[Path] = None) -> None:
    """Tạo 3 bảng SQLite — idempotent."""
    _p = db_path or _DB
    with sqlite3.connect(_p) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS thuyvan_daily (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                station     TEXT DEFAULT 'PhuAn',
                river       TEXT DEFAULT 'SaiGon',
                year        INTEGER NOT NULL,
                month       INTEGER NOT NULL,
                day         INTEGER NOT NULL,
                iso_date    TEXT NOT NULL,
                h_cm        REAL NOT NULL,
                source      TEXT DEFAULT 'THUYVAN-PhuAn_H(77-24)ok.xlsx',
                UNIQUE (year, month, day)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS thuyvan_annual_summary (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                station         TEXT DEFAULT 'PhuAn',
                year            INTEGER NOT NULL UNIQUE,
                avg_cm          REAL,
                max_cm          REAL,
                min_cm          REAL,
                max_day         INTEGER,
                max_month       INTEGER,
                min_day         INTEGER,
                min_month       INTEGER,
                monthly_avg_cm  TEXT,
                monthly_max_cm  TEXT,
                monthly_min_cm  TEXT,
                updated_at      TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS thuyvan_tidal_peaks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                station     TEXT DEFAULT 'PhuAn',
                year        INTEGER NOT NULL UNIQUE,
                peak_cm     REAL NOT NULL,
                source      TEXT DEFAULT 'THUYVAN-Tidal information summary'
            )
        """)
        con.commit()


def save_to_db(daily: list[dict], annual: list[dict], peaks: list[dict],
               db_path: Optional[Path] = None) -> None:
    _p = db_path or _DB
    create_tables(_p)
    with sqlite3.connect(_p) as con:
        for d in daily:
            con.execute("""
                INSERT INTO thuyvan_daily (year, month, day, iso_date, h_cm)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (year, month, day) DO UPDATE SET
                    h_cm = excluded.h_cm
            """, (d["year"], d["month"], d["day"], d["iso_date"], d["h_cm"]))
        for a in annual:
            con.execute("""
                INSERT INTO thuyvan_annual_summary
                    (year, avg_cm, max_cm, min_cm, max_day, max_month, min_day, min_month,
                     monthly_avg_cm, monthly_max_cm, monthly_min_cm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (year) DO UPDATE SET
                    avg_cm = excluded.avg_cm, max_cm = excluded.max_cm,
                    min_cm = excluded.min_cm,
                    max_day = excluded.max_day, max_month = excluded.max_month,
                    min_day = excluded.min_day, min_month = excluded.min_month,
                    monthly_avg_cm = excluded.monthly_avg_cm,
                    monthly_max_cm = excluded.monthly_max_cm,
                    monthly_min_cm = excluded.monthly_min_cm,
                    updated_at = datetime('now','localtime')
            """, (a["year"], a["avg_cm"], a["max_cm"], a["min_cm"],
                  a["max_day"], a["max_month"], a["min_day"], a["min_month"],
                  json.dumps(a["monthly_avg_cm"]),
                  json.dumps(a["monthly_max_cm"]),
                  json.dumps(a["monthly_min_cm"])))
        for p in peaks:
            con.execute("""
                INSERT INTO thuyvan_tidal_peaks (year, peak_cm)
                VALUES (?, ?)
                ON CONFLICT (year) DO UPDATE SET
                    peak_cm = excluded.peak_cm
            """, (p["year"], p["peak_cm"]))
        con.commit()


def save_to_json(daily: list[dict], annual: list[dict], peaks: list[dict]) -> None:
    _DATA.mkdir(exist_ok=True)
    meta = {
        "_meta": {
            "station": "Phú An",
            "river":   "Sài Gòn",
            "datum":   "Cao độ Quốc gia",
            "unit":    "cm",
            "source": [
                "THUYVAN-PhuAn_ H(77-24)ok.xlsx",
                "THUYVAN-Tidal information summary_PhuAnStation.xlsx",
            ],
            "n_years_daily":  len(annual),
            "n_records_daily": len(daily),
            "n_tidal_peaks":   len(peaks),
        }
    }
    with open(_DATA / "thuyvan_phuan_daily_77-24.json", "w", encoding="utf-8") as f:
        json.dump({**meta, "daily": daily}, f, ensure_ascii=False, indent=1)
    with open(_DATA / "thuyvan_phuan_summary.json", "w", encoding="utf-8") as f:
        json.dump({**meta, "annual": annual, "tidal_peaks": peaks},
                  f, ensure_ascii=False, indent=2)


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    fp_daily   = Path(r"G:\My Drive\202605-TRUNG TAM HCM\thuy van\THUYVAN-PhuAn_ H(77-24)ok.xlsx")
    fp_summary = Path(r"G:\My Drive\202605-TRUNG TAM HCM\thuy van\THUYVAN-Tidal information summary_PhuAnStation.xlsx")

    print(f"Parsing {fp_daily.name}...")
    daily, annual = parse_daily_xlsx(fp_daily)
    print(f"  Daily records: {len(daily)}  |  Annual blocks: {len(annual)}")
    print(f"  Years: {annual[0]['year']} → {annual[-1]['year']}")

    print(f"\nParsing {fp_summary.name}...")
    peaks = parse_tidal_summary_xlsx(fp_summary)
    print(f"  Tidal peaks: {len(peaks)} years")

    print("\nSaving JSON + SQLite...")
    save_to_json(daily, annual, peaks)
    save_to_db(daily, annual, peaks)
    print("  Done.")

    # Verify
    with sqlite3.connect(_DB) as con:
        for tbl in ("thuyvan_daily", "thuyvan_annual_summary", "thuyvan_tidal_peaks"):
            n = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"  {tbl}: {n} rows")


if __name__ == "__main__":
    main()
