"""bxn_lab_import.py — Trích xuất KQTN BXN từ XLS gốc → JSON + SQLite.

Nguồn: 3.KQTN_BXN-TTHC. KQTN Full gui.xls (BXN-TTHC, 17 hố CV-HK1..17, ~360 mẫu)

Đơn vị chuẩn hóa:
  - γ, γ_dry, γ_sub:  g/cm³ × 9.81 → kN/m³
  - c, PC, Cu_UU:     kgf/cm² × 100 → kPa (Vietnamese standard, 1 kgf/cm² ≈ 100 kPa)
  - φ direct shear:   cột deg + cột min → decimal deg
  - φ UU:             chuỗi "d°m'" → decimal deg
  - a12:              giữ raw cm²/kgf (≡ ×10⁻² kPa⁻¹)
  - cv:               × 10⁻³ → cm²/s
  - k:                × 10⁻⁷ → cm/s
  - E_kPa:            Eoed = (1+e0)/(a12 × 0.01) khi có a12

Usage:
  python scripts/bxn_lab_import.py            # parse + write JSON + update SQLite
  python scripts/bxn_lab_import.py --dry-run  # parse + print summary, không ghi file
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

import xlrd

ROOT = Path(__file__).resolve().parent.parent
XLS_PATH = Path(
    r"G:/My Drive/202605-TRUNG TAM HCM/DIA CHAT/"
    r"1. BÃI ĐỖ XE NGẦM/1. BÃI ĐỖ XE NGẦM/"
    r"BXN-3KQTN_BXN-TTHC KQTN Full gui-INPUT SQLTIE.xls"
)
JSON_OUT = ROOT / "data" / "bxn_lab_tests_202605_TTHC.json"
DB_PATH = ROOT / "data" / "TTHC.sqlite"

KGF_CM2_TO_KPA = 100.0
G_TO_KN_M3 = 9.81

PHI_DM_RE = re.compile(r"(-?\d+)\s*°\s*(\d+)\s*'?")


def _f(v):
    if v == "" or v is None:
        return None
    try:
        f = float(v)
        return f if f != 0 or isinstance(v, (int, float)) else None
    except (TypeError, ValueError):
        return None


def _f_nz(v):
    """Float hoặc None — coi 0 cũng là None (cột bỏ trống)."""
    f = _f(v)
    return f if f and f != 0 else None


def _phi_dm(deg_cell, min_cell) -> float | None:
    """phi từ 2 cell deg/min (cắt phẳng)."""
    d = _f(deg_cell)
    m = _f(min_cell)
    if d is None and m is None:
        return None
    return round((d or 0) + (m or 0) / 60.0, 4)


def _phi_str(cell) -> float | None:
    """phi từ chuỗi 'd°m'' (UU/CU)."""
    if cell == "" or cell is None:
        return None
    if isinstance(cell, (int, float)):
        return round(float(cell), 4) if cell else None
    m = PHI_DM_RE.search(str(cell))
    if m:
        return round(int(m.group(1)) + int(m.group(2)) / 60.0, 4)
    return _f(cell)


def _str(cell) -> str | None:
    if cell is None or cell == "":
        return None
    s = str(cell).strip()
    return s or None


def parse_xls(fp: Path) -> list[dict]:
    """Parse XLS → list of samples (1 dict / mẫu)."""
    wb = xlrd.open_workbook(str(fp))
    s = wb.sheet_by_index(0)
    samples = []
    for r in range(11, s.nrows):
        bh = _str(s.cell_value(r, 1))
        sample_id = _str(s.cell_value(r, 2))
        if not bh or not sample_id:
            continue
        df = _f(s.cell_value(r, 3))
        dt = _f(s.cell_value(r, 4))
        if df is None or dt is None:
            continue

        e0 = _f(s.cell_value(r, 24))
        a12 = _f_nz(s.cell_value(r, 41))
        E_kPa = None
        if e0 is not None and a12 is not None and a12 > 0:
            E_kPa = round((1.0 + e0) / (a12 * 0.01), 1)

        gamma = _f(s.cell_value(r, 18))      # g/cm³
        gamma_dry = _f(s.cell_value(r, 19))  # g/cm³
        gamma_sub = _f(s.cell_value(r, 20))  # đã ở kN/m³ trong XLS (γ_sat − γ_w)

        c_kgcm2 = _f_nz(s.cell_value(r, 40))
        PC_kgcm2 = _f_nz(s.cell_value(r, 42))
        c_UU_kgcm2 = _f_nz(s.cell_value(r, 52))

        sample = {
            "sample_id": sample_id,
            "depth_from_m": round(df, 2),
            "depth_to_m": round(dt, 2),
            "w_pct": _f_nz(s.cell_value(r, 17)),
            "gamma_kNm3": round(gamma * G_TO_KN_M3, 2) if gamma else None,
            "gamma_dry_kNm3": round(gamma_dry * G_TO_KN_M3, 2) if gamma_dry else None,
            "gamma_sub_kNm3": round(gamma_sub, 2) if gamma_sub else None,
            "Gs": _f_nz(s.cell_value(r, 21)),
            "Sr_pct": _f_nz(s.cell_value(r, 22)),
            "n_pct": _f_nz(s.cell_value(r, 23)),
            "e0": e0,
            "wL_pct": _f_nz(s.cell_value(r, 29)),
            "wP_pct": _f_nz(s.cell_value(r, 30)),
            "Ip": _f_nz(s.cell_value(r, 31)),
            "IS_liq": _f_nz(s.cell_value(r, 32)),
            "a12_kPa_inv_e2": a12,
            "E_kPa": E_kPa,
            "PC_kPa": round(PC_kgcm2 * KGF_CM2_TO_KPA, 1) if PC_kgcm2 else None,
            "Cc": _f_nz(s.cell_value(r, 43)),
            "Cs": _f_nz(s.cell_value(r, 44)),
            "Cv_cm2s": (_f_nz(s.cell_value(r, 45)) or 0) * 1e-3 or None,
            "k_cm_s": (_f_nz(s.cell_value(r, 46)) or 0) * 1e-7 or None,
            "phi_deg": _phi_dm(s.cell_value(r, 38), s.cell_value(r, 39)),
            "c_kPa": round(c_kgcm2 * KGF_CM2_TO_KPA, 1) if c_kgcm2 else None,
            "Cu_UU_kPa": round(c_UU_kgcm2 * KGF_CM2_TO_KPA, 1) if c_UU_kgcm2 else None,
            "phi_UU_deg": _phi_str(s.cell_value(r, 53)),
            "symbol_tcvn": _str(s.cell_value(r, 54)),
            "description_vi": _str(s.cell_value(r, 55)),
        }
        # Xóa key None để JSON gọn
        sample = {k: v for k, v in sample.items() if v is not None}
        samples.append((bh, sample))
    return samples


def group_by_borehole(samples: list[tuple[str, dict]]) -> list[dict]:
    """Gom mẫu theo hố khoan, sort theo depth_from."""
    bhs: dict[str, list[dict]] = {}
    for bh, sample in samples:
        bhs.setdefault(bh, []).append(sample)
    out = []
    for bh in sorted(bhs.keys(), key=lambda x: (len(x), x)):
        rows = sorted(bhs[bh], key=lambda r: r.get("depth_from_m", 0))
        out.append({"borehole": bh, "samples": rows})
    return out


def write_json(boreholes: list[dict], n_samples: int) -> None:
    payload = {
        "_meta": {
            "project": "260512 CVTT-TTHC — Trung tâm Hành chính TP.HCM",
            "zone": "BXN — Bãi Đỗ Xe Ngầm",
            "source": "BXN-3KQTN_BXN-TTHC KQTN Full gui-INPUT SQLTIE.xls (sheet 'M', 17 hố CV-HK1..17)",
            "standard": (
                "TCVN 4200:2012 (cắt phẳng), "
                "TCVN 4200:1995 (nén lún), "
                "TCVN 4197:2012 (Atterberg), "
                "TCVN 8868:2011 (3 trục UU)"
            ),
            "updated": date.today().isoformat(),
            "n_boreholes": len(boreholes),
            "n_samples": n_samples,
            "units": {
                "gamma_kNm3": "γ × 9.81 từ g/cm³",
                "c_kPa / Cu_UU_kPa / PC_kPa": "× 100 từ kgf/cm² (1 kgf/cm² ≈ 100 kPa)",
                "phi_deg": "decimal degree từ cột deg + cột min",
                "phi_UU_deg": "decimal degree từ chuỗi 'd°m''",
                "a12_kPa_inv_e2": "raw cm²/kgf (≡ ×10⁻² kPa⁻¹)",
                "Cv_cm2s": "raw × 10⁻³ cm²/s",
                "k_cm_s": "raw × 10⁻⁷ cm/s",
                "E_kPa": "Eoed = (1+e0)/(a12 × 0.01)",
            },
            "notes": {
                "borehole_naming": "CV-HKx trong XLS → BXN-CV-HKx trong SQLite (zone prefix)",
                "exclusions": "BXN-HK2, BXN-HK3 (50 mẫu mỗi HK) là dữ liệu khảo sát cũ — không có trong XLS này, giữ nguyên trong SQLite",
            },
        },
        "boreholes": boreholes,
    }
    JSON_OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def update_sqlite(samples: list[tuple[str, dict]]) -> tuple[int, int, list[str]]:
    """DELETE BXN-CV-HKx hiện có, INSERT new từ XLS.

    Returns: (n_deleted, n_inserted, missing_bh_names)
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Lấy map BH name → id (chỉ BXN-CV-HKx)
    cur.execute("SELECT id, name FROM boreholes WHERE name LIKE 'BXN-CV-%'")
    bh_id_map = {name: bid for bid, name in cur.fetchall()}

    db_names = []
    missing = []
    for bh, _ in samples:
        db_name = f"BXN-{bh}"  # CV-HK1 → BXN-CV-HK1
        if db_name not in bh_id_map:
            missing.append(db_name)
        db_names.append(db_name)

    if missing:
        return 0, 0, sorted(set(missing))

    # DELETE old BXN-CV-HKx rows
    bh_ids = list(set(bh_id_map[n] for n in set(db_names)))
    placeholders = ",".join("?" * len(bh_ids))
    cur.execute(
        f"DELETE FROM lab_tests WHERE borehole_id IN ({placeholders})", bh_ids
    )
    n_deleted = cur.rowcount

    # INSERT new
    cols = [
        "borehole_id", "sample_id", "depth_from_m", "depth_to_m",
        "w_pct", "gamma_kNm3", "gamma_dry_kNm3", "Gs", "Sr_pct", "n_pct", "e0",
        "wL_pct", "wP_pct", "Ip", "IS_liq",
        "phi_deg", "c_kPa", "a12_cm2kgf", "E_kPa", "Cc", "Cs",
        "Cu_UU_kPa", "phi_UU_deg",
        "symbol_tcvn", "description_vi",
        "k_cm_s", "Cv_cm2s", "PC_kPa",
    ]
    placeholders = ",".join("?" * len(cols))
    sql = f"INSERT INTO lab_tests ({','.join(cols)}) VALUES ({placeholders})"
    n_inserted = 0
    for bh, sample in samples:
        db_name = f"BXN-{bh}"
        row = [
            bh_id_map[db_name],
            sample["sample_id"],
            sample["depth_from_m"],
            sample["depth_to_m"],
            sample.get("w_pct"),
            sample.get("gamma_kNm3"),
            sample.get("gamma_dry_kNm3"),
            sample.get("Gs"),
            sample.get("Sr_pct"),
            sample.get("n_pct"),
            sample.get("e0"),
            sample.get("wL_pct"),
            sample.get("wP_pct"),
            sample.get("Ip"),
            sample.get("IS_liq"),
            sample.get("phi_deg"),
            sample.get("c_kPa"),
            sample.get("a12_kPa_inv_e2"),
            sample.get("E_kPa"),
            sample.get("Cc"),
            sample.get("Cs"),
            sample.get("Cu_UU_kPa"),
            sample.get("phi_UU_deg"),
            sample.get("symbol_tcvn"),
            sample.get("description_vi"),
            sample.get("k_cm_s"),
            sample.get("Cv_cm2s"),
            sample.get("PC_kPa"),
        ]
        cur.execute(sql, row)
        n_inserted += 1

    conn.commit()
    conn.close()
    return n_deleted, n_inserted, []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not XLS_PATH.exists():
        print(f"XLS không tồn tại: {XLS_PATH}", file=sys.stderr)
        return 2

    samples = parse_xls(XLS_PATH)
    boreholes = group_by_borehole(samples)
    n_total = sum(len(bh["samples"]) for bh in boreholes)

    print(f"Parsed: {len(boreholes)} hố khoan, {n_total} mẫu")
    for bh in boreholes:
        with_uu = sum(1 for s in bh["samples"] if "Cu_UU_kPa" in s)
        with_oed = sum(1 for s in bh["samples"] if "Cc" in s)
        print(f"  {bh['borehole']:<8} {len(bh['samples']):>3} mẫu  "
              f"(UU: {with_uu}, oedometer: {with_oed})")

    if args.dry_run:
        print("\n[dry-run] không ghi file.")
        # Show first sample
        if boreholes and boreholes[0]["samples"]:
            print("\nMẫu đầu tiên:")
            print(json.dumps(boreholes[0]["samples"][0], ensure_ascii=False, indent=2))
        return 0

    write_json(boreholes, n_total)
    print(f"\nJSON ghi: {JSON_OUT}")

    n_del, n_ins, missing = update_sqlite(samples)
    if missing:
        print(f"LỖI: HK chưa có trong bảng boreholes: {missing}", file=sys.stderr)
        return 3
    print(f"SQLite: xóa {n_del} dòng cũ, chèn {n_ins} dòng mới vào lab_tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
