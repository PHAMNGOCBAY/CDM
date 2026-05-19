"""Kiểm tra tính đầy đủ bộ 3 file (JSON + MD + PY) cho mỗi chủ đề trong project."""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).parent.parent

_OUT_DIR = Path(r"G:\My Drive\202605-TRUNG TAM HCM\KET CAU KE")

FILE_TRIPLETS = [
    {
        "topic": "Catalog cọc SW BETON 6",
        "json": "data/sw_pile_catalog.json",
        "md":   "11-sw-pile-database.md",
        "py":   "scripts/sw_pile_database.py",
    },
    {
        "topic": "Plate properties PLAXIS",
        "json": "data/structural_presets.json",
        "md":   "10-plate-properties.md",
        "py":   "scripts/plate_properties.py",
    },
    {
        "topic": "Preset dat (HS/SS/MC) -- PY chua tao",
        "json": "data/soil_presets.json",
        "md":   "13-hardening-soil-model.md",
        "py":   "scripts/hardening_soil_material.py",  # gap truoc phien nay
    },
    {
        "topic": "Địa tầng TTHC 202605",
        "json": "data/soil_profile_202605_TTHC.json",
        "md":   "15-soil-profile-202605-TTHC.md",
        "py":   "scripts/soil_profile_TTHC.py",
    },
    {
        "topic": "Thiết kế kè SW TTHC 202605",
        "json": "data/ke_sw_202605_TTHC.json",
        "md":   "16-ke-sw-202605-TTHC.md",
        "py":   "scripts/ke_sw_TTHC.py",
    },
    {
        "topic": "Nhật ký phiên + báo cáo Word",
        "json": "data/session_log.json",
        "md":   "17-session-log.md",
        "py":   "scripts/project_check.py",
    },
    {
        "topic": "Sức chịu tải cọc đóng TCVN 11823-10:2017",
        "json": "data/driven_pile_TCVN11823.json",
        "md":   "18-driven-pile-TCVN11823.md",
        "py":   "scripts/driven_pile_TCVN11823.py",
    },
]

WORD_REPORTS = [
    {
        "topic": "Báo cáo lựa chọn cọc SW — TTHC HCM",
        "docx": _OUT_DIR / "260513 BAO CAO LUA CHON COC SW-TTHC-HCM.docx",
        "generator": "scripts/_gen_report_ke_sw_TTHC.py",
    },
]


def check() -> None:
    all_ok = True
    sep = "=" * 65
    print(f"\n{sep}")
    print("  Kiem tra bo 3 file (JSON + MD + PY)")
    print(sep)
    for t in FILE_TRIPLETS:
        print(f"\n  {t['topic']}")
        for key in ("json", "md", "py"):
            path = _ROOT / t[key]
            ok = path.exists()
            status = "OK   " if ok else "THIEU"
            print(f"    {key.upper():<4}  {status}  {t[key]}")
            if not ok:
                all_ok = False

    print(f"\n  Word Reports")
    for w in WORD_REPORTS:
        ok = w["docx"].exists()
        status = "OK   " if ok else "THIEU"
        print(f"    DOCX  {status}  {w['docx'].name}")
        if not ok:
            all_ok = False

    print(f"\n{sep}")
    print("  OK  Tat ca file day du." if all_ok else "  !!  Co file THIEU -- can bo sung.")
    print(f"{sep}\n")


if __name__ == "__main__":
    check()
