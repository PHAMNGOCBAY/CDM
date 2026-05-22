"""ke_lab_import.py — Trích xuất KQTN KE từ XLS gốc → JSON + SQLite.

Nguồn: KE-3 KQTN_260519 CV-TTHC HCM. KQTN Full INPUT SQLTIE.xls
       (sheet 'M', 12 hố HK1..HK12, ~206 mẫu)

KE-3 KHÁC BXN-3 ở column layout — xem CLAUDE.md §11c.

Đơn vị chuẩn hóa:
  - γ, γ_dry, γ_sub: g/cm³ × 9.81 → kN/m³
  - c, c_UU, c_CU, c'_CU, PC: kgf/cm² × 100 → kPa
  - φ shear: cột 39 (deg) + cột 40 (min) → decimal deg
  - φ UU/CU/CU': DDMM integer (1 cell) → decimal deg
  - cv: × 10⁻³ → cm²/s
  - k:  × 10⁻⁷ → cm/s
  - E_kPa: Eoed = (1+e0)/(a12 × 0.01) khi có a12

Usage:
  python scripts/ke_lab_import.py            # parse + write JSON + update SQLite
  python scripts/ke_lab_import.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import xlrd

ROOT = Path(__file__).resolve().parent.parent
XLS_PATH = Path(
    r"G:/My Drive/202605-TRUNG TAM HCM/DIA CHAT/"
    r"3. KÈ (CÔNG VIÊN)/3. KÈ (CÔNG VIÊN)/"
    r"KE-3 KQTN_260519 CV-TTHC HCM. KQTN Full INPUT SQLTIE.xls"
)
JSON_OUT = ROOT / "data" / "ke_lab_tests_202605_TTHC.json"
DB_PATH = ROOT / "data" / "TTHC.sqlite"

KGF_CM2_TO_KPA = 100.0
G_TO_KN_M3 = 9.81


def _f(v):
    if v == "" or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _f_nz(v):
    f = _f(v)
    return f if f and f != 0 else None


def _phi_dm(deg_cell, min_cell) -> float | None:
    """φ shear: cột deg + cột min → decimal deg."""
    d = _f(deg_cell)
    m = _f(min_cell)
    if d is None and m is None:
        return None
    return round((d or 0) + (m or 0) / 60.0, 4)


def _phi_ddmm(cell) -> float | None:
    """φ UU/CU/CU': DDMM integer trong 1 cell → decimal deg.
    Ví dụ: 339 → 3°39' = 3.65 ; 1612 → 16°12' = 16.2 ; 2458 → 24°58' = 24.97
    Giá trị < 100 coi là decimal degrees thuần (ít gặp nhưng giữ chuẩn).
    """
    v = _f(cell)
    if v is None or v == 0:
        return None
    if v < 100:
        return round(v, 4)
    iv = int(round(v))
    d = iv // 100
    m = iv % 100
    return round(d + m / 60.0, 4)


def _str(cell) -> str | None:
    if cell is None or cell == "":
        return None
    s = str(cell).strip()
    return s or None


def parse_xls(fp: Path) -> list[tuple[str, dict]]:
    """Parse sheet 'M' → list[(bh_raw, sample_dict)]."""
    wb = xlrd.open_workbook(str(fp))
    s = wb.sheet_by_index(0)
    samples = []
    for r in range(s.nrows):
        bh = _str(s.cell_value(r, 1))
        sample_id = _str(s.cell_value(r, 2))
        if not bh or not sample_id:
            continue
        if not bh.startswith(("HK", "CV", "KE")):
            continue
        df = _f(s.cell_value(r, 3))
        dt = _f(s.cell_value(r, 4))
        if df is None or dt is None:
            continue

        e0 = _f(s.cell_value(r, 22))   # KE: col 22 = e0
        a12 = _f_nz(s.cell_value(r, 41))
        E_kPa = None
        if e0 is not None and a12 is not None and a12 > 0:
            E_kPa = round((1.0 + e0) / (a12 * 0.01), 1)

        gamma = _f(s.cell_value(r, 18))
        gamma_dry = _f(s.cell_value(r, 19))
        gamma_sub = _f(s.cell_value(r, 20))  # KE: col 20 = g/cm³ (KHÁC BXN)

        c_kgcm2 = _f_nz(s.cell_value(r, 38))    # KE: c shear ở col 38
        c_UU_kgcm2 = _f_nz(s.cell_value(r, 42))
        c_CU_kgcm2 = _f_nz(s.cell_value(r, 44))
        c_CU_eff_kgcm2 = _f_nz(s.cell_value(r, 46))
        PC_kgcm2 = _f_nz(s.cell_value(r, 48))   # KE: PC ở col 48

        sample = {
            "sample_id": sample_id,
            "depth_from_m": round(df, 2),
            "depth_to_m": round(dt, 2),
            "w_pct": _f_nz(s.cell_value(r, 17)),
            "gamma_kNm3": round(gamma * G_TO_KN_M3, 2) if gamma else None,
            "gamma_dry_kNm3": round(gamma_dry * G_TO_KN_M3, 2) if gamma_dry else None,
            "gamma_sub_kNm3": round(gamma_sub * G_TO_KN_M3, 2) if gamma_sub else None,
            "Gs": _f_nz(s.cell_value(r, 21)),
            "e0": e0,
            "n_pct": _f_nz(s.cell_value(r, 23)),
            "Sr_pct": _f_nz(s.cell_value(r, 24)),
            "wL_pct": _f_nz(s.cell_value(r, 25)),
            "wP_pct": _f_nz(s.cell_value(r, 26)),
            "Ip": _f_nz(s.cell_value(r, 27)),
            "IS_liq": _f_nz(s.cell_value(r, 28)),
            "phi_deg": _phi_dm(s.cell_value(r, 39), s.cell_value(r, 40)),
            "c_kPa": round(c_kgcm2 * KGF_CM2_TO_KPA, 2) if c_kgcm2 else None,
            "a12_kPa_inv_e2": a12,
            "E_kPa": E_kPa,
            "Cu_UU_kPa": round(c_UU_kgcm2 * KGF_CM2_TO_KPA, 2) if c_UU_kgcm2 else None,
            "phi_UU_deg": _phi_ddmm(s.cell_value(r, 43)),
            "c_CU_kPa": round(c_CU_kgcm2 * KGF_CM2_TO_KPA, 2) if c_CU_kgcm2 else None,
            "phi_CU_deg": _phi_ddmm(s.cell_value(r, 45)),
            "c_CU_eff_kPa": round(c_CU_eff_kgcm2 * KGF_CM2_TO_KPA, 2) if c_CU_eff_kgcm2 else None,
            "phi_CU_eff_deg": _phi_ddmm(s.cell_value(r, 47)),
            "PC_kPa": round(PC_kgcm2 * KGF_CM2_TO_KPA, 1) if PC_kgcm2 else None,
            "Cc": _f_nz(s.cell_value(r, 49)),
            "Cs": _f_nz(s.cell_value(r, 50)),
            "Cv_cm2s": (_f_nz(s.cell_value(r, 51)) or 0) * 1e-3 or None,
            "k_cm_s": (_f_nz(s.cell_value(r, 52)) or 0) * 1e-7 or None,
            "mv_cm2kgf": _f_nz(s.cell_value(r, 53)),
            "symbol_tcvn": _str(s.cell_value(r, 54)),
            "description_vi": _str(s.cell_value(r, 55)),
        }
        sample = {k: v for k, v in sample.items() if v is not None}
        samples.append((bh, sample))
    return samples


def group_by_borehole(samples):
    bhs = {}
    for bh, sample in samples:
        bhs.setdefault(bh, []).append(sample)
    out = []
    for bh in sorted(bhs.keys(), key=lambda x: (len(x), x)):
        rows = sorted(bhs[bh], key=lambda r: r.get("depth_from_m", 0))
        out.append({"borehole": bh, "samples": rows})
    return out


def write_json(boreholes, n_samples):
    payload = {
        "_meta": {
            "project": "260512 CVTT-TTHC — Trung tâm Hành chính TP.HCM",
            "zone": "KE — Kè Công Viên",
            "source": "KE-3 KQTN_260519 CV-TTHC HCM. KQTN Full INPUT SQLTIE.xls (sheet 'M', 12 hố HK1..HK12)",
            "standard": (
                "TCVN 4200:2012 (cắt phẳng), "
                "TCVN 4200:1995 (nén lún), "
                "TCVN 4197:2012 (Atterberg), "
                "TCVN 8868:2011 (3 trục UU/CU)"
            ),
            "updated": date.today().isoformat(),
            "n_boreholes": len(boreholes),
            "n_samples": n_samples,
            "units": {
                "gamma_*_kNm3": "g/cm³ × 9.81 → kN/m³ (3 cột γ/γ_dry/γ_sub)",
                "c_kPa / Cu_UU_kPa / c_CU_kPa / c_CU_eff_kPa / PC_kPa": "× 100 từ kgf/cm²",
                "phi_deg": "decimal deg từ col 39 (deg) + col 40 (min)",
                "phi_UU_deg / phi_CU_deg / phi_CU_eff_deg": "DDMM integer → d + m/60",
                "a12_kPa_inv_e2": "raw cm²/kgf",
                "Cv_cm2s": "raw × 10⁻³ cm²/s",
                "k_cm_s": "raw × 10⁻⁷ cm/s",
                "mv_cm2kgf": "raw, cm²/kgf",
                "E_kPa": "Eoed = (1+e0)/(a12 × 0.01)",
            },
            "notes": {
                "borehole_naming": "HKx trong XLS → KE-HKx trong SQLite (zone prefix)",
                "layout_diff_vs_bxn": "Cột e0/Sr/n đảo vị (cols 22/24/23 KE vs 24/22/23 BXN). c-shear ở col 38 (KE) vs col 40 (BXN). UU/CU phi dạng DDMM (KE) vs chuỗi 'd°m'' (BXN UU only).",
            },
        },
        "boreholes": boreholes,
    }
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def update_sqlite(samples):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Map BH name → id
    cur.execute("SELECT id, name FROM boreholes WHERE name LIKE 'KE-HK%'")
    bh_id_map = {name: bid for bid, name in cur.fetchall()}

    missing = []
    for bh, _ in samples:
        db_name = f"KE-{bh}"
        if db_name not in bh_id_map:
            missing.append(db_name)
    if missing:
        return 0, 0, sorted(set(missing))

    bh_ids = list(set(bh_id_map[f"KE-{bh}"] for bh, _ in samples))
    placeholders = ",".join("?" * len(bh_ids))
    cur.execute(f"DELETE FROM lab_tests WHERE borehole_id IN ({placeholders})", bh_ids)
    n_deleted = cur.rowcount

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
    for bh, s in samples:
        db_name = f"KE-{bh}"
        cur.execute(sql, [
            bh_id_map[db_name],
            s["sample_id"], s["depth_from_m"], s["depth_to_m"],
            s.get("w_pct"), s.get("gamma_kNm3"), s.get("gamma_dry_kNm3"),
            s.get("Gs"), s.get("Sr_pct"), s.get("n_pct"), s.get("e0"),
            s.get("wL_pct"), s.get("wP_pct"), s.get("Ip"), s.get("IS_liq"),
            s.get("phi_deg"), s.get("c_kPa"), s.get("a12_kPa_inv_e2"), s.get("E_kPa"),
            s.get("Cc"), s.get("Cs"),
            s.get("Cu_UU_kPa"), s.get("phi_UU_deg"),
            s.get("symbol_tcvn"), s.get("description_vi"),
            s.get("k_cm_s"), s.get("Cv_cm2s"), s.get("PC_kPa"),
        ])
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
    n_total = sum(len(b["samples"]) for b in boreholes)

    print(f"Parsed: {len(boreholes)} hố khoan, {n_total} mẫu")
    for bh in boreholes:
        n_uu = sum(1 for s in bh["samples"] if "Cu_UU_kPa" in s)
        n_cu = sum(1 for s in bh["samples"] if "c_CU_kPa" in s)
        n_oed = sum(1 for s in bh["samples"] if "PC_kPa" in s)
        print(f"  {bh['borehole']:<6} {len(bh['samples']):>3} mẫu  "
              f"(UU:{n_uu}, CU:{n_cu}, oed:{n_oed})")

    if args.dry_run:
        if boreholes and boreholes[0]["samples"]:
            print("\nMẫu đầu tiên:")
            print(json.dumps(boreholes[0]["samples"][0], ensure_ascii=False, indent=2))
        return 0

    write_json(boreholes, n_total)
    print(f"\nJSON ghi: {JSON_OUT}")

    n_del, n_ins, missing = update_sqlite(samples)
    if missing:
        print(f"LỖI: thiếu BH trong boreholes: {missing}", file=sys.stderr)
        return 3
    print(f"SQLite: xóa {n_del} dòng cũ, chèn {n_ins} dòng mới vào lab_tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
