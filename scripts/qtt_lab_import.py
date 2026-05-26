"""
qtt_lab_import.py — Nhập KQTN Quảng Trường Trung Tâm (QTTTTP)

Nguồn: G:\\My Drive\\202605-TRUNG TAM HCM\\QUANG TRUONG VI DAN\\HÌNH TRỤ, MC\\260524 QTTT TP. KQTN.xls
Sheet 'M', 36 mẫu từ 3 hố khoan: ND-02, ND-06, ND-07
Lưu vào: data/qtt_lab_tests_202605_TTHC.json + SQLite lab_tests
"""

from __future__ import annotations
import re, json, sqlite3, sys
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
XLS_PATH = Path(r"G:\My Drive\202605-TRUNG TAM HCM\QUANG TRUONG VI DAN\HÌNH TRỤ, MC\260524 QTTT TP. KQTN.xls")
JSON_OUT  = ROOT / "data" / "qtt_lab_tests_202605_TTHC.json"
DB_PATH   = ROOT / "data" / "TTHC.sqlite"   # main DB; script can also target backup
DB_BACKUP = ROOT / "data" / "TTHC_with_qtt_backup.sqlite"

DATA_ROW_START = 12   # row index (0-based) where data begins
ZONE_CODE = "QTT"
BH_PREFIX = "QTTTTP-"   # DB name convention

# ---------------------------------------------------------------------------
# Helper parsers
# ---------------------------------------------------------------------------

def _flt(v) -> float | None:
    try:
        f = float(v)
        return f if f == f else None   # NaN guard
    except (ValueError, TypeError):
        return None


def _parse_angle(s) -> float | None:
    """Parse Vietnamese angle strings: '7°41 '' or '7° 41'' → 7.683°"""
    if s is None or str(s).strip() == "":
        return None
    m = re.search(r"(\d+)[°°]\s*(\d+)", str(s))
    if m:
        return int(m.group(1)) + int(m.group(2)) / 60.0
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _safe_int(v) -> int | None:
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# XLS parser
# ---------------------------------------------------------------------------

def read_xls(path: Path) -> list[dict]:
    try:
        import xlrd
    except ImportError:
        sys.exit("Cài xlrd: pip install xlrd==1.2.0")

    wb = xlrd.open_workbook(str(path))
    ws = wb.sheet_by_name("M")

    samples = []
    current_bh = None

    for row_idx in range(DATA_ROW_START, ws.nrows):
        row = [ws.cell_value(row_idx, c) for c in range(ws.ncols)]

        # Col 1: bh name (e.g. 'ND-02') — filled only on first row of BH block
        bh_raw = str(row[1]).strip() if row[1] else ""
        if bh_raw:
            current_bh = bh_raw

        if not current_bh:
            continue

        # Col 2: sample code
        sample_code = str(row[2]).strip() if row[2] else ""
        if not sample_code:
            continue

        # Col 0: type code for triaxial tests
        type_code = str(row[0]).strip().lower() if row[0] else ""

        # Depths
        depth_from = _flt(row[3])
        depth_to   = _flt(row[4])
        if depth_from is None:
            continue

        # --- Physical properties ---
        W_pct      = _flt(row[17])
        gamma      = _flt(row[18])   # g/cm³
        gamma_dry  = _flt(row[19])   # g/cm³
        gamma_sub  = _flt(row[20])   # g/cm³ (buoyant)
        Gs         = _flt(row[21])
        e0         = _flt(row[22])
        n_pct      = _flt(row[23])
        Sr_pct     = _flt(row[24])

        # Convert g/cm³ → kN/m³
        gamma_kNm3     = gamma     * 9.81 if gamma     is not None else None
        gamma_dry_kNm3 = gamma_dry * 9.81 if gamma_dry is not None else None
        gamma_sub_kNm3 = gamma_sub * 9.81 if gamma_sub is not None else None

        # --- Atterberg limits ---
        wL  = _flt(row[25])
        wP  = _flt(row[26])
        Ip  = _flt(row[27])
        IS  = _flt(row[28])

        # --- Direct shear (col 43 = c [kgf/cm²], col 44 = φ deg, col 45 = φ min) ---
        c_ds_raw  = _flt(row[43])
        phi_d_deg = _safe_int(row[44]) or 0
        phi_d_min = _safe_int(row[45]) or 0
        c_kPa     = c_ds_raw * 100.0 if c_ds_raw is not None else None
        phi_deg   = phi_d_deg + phi_d_min / 60.0 if (row[44] or row[45]) else None

        # --- Oedometer: void ratio e at pressure levels ---
        _e_keys  = ["e_000", "e_0125", "e_025", "e_050", "e_100", "e_200", "e_400", "e_800"]
        _e_cols  = [46, 47, 48, 49, 50, 51, 52, 53]
        e_vals   = {k: _flt(row[c]) for k, c in zip(_e_keys, _e_cols)}

        # --- Compression coefficients a [cm²/kgf] at pressure ranges ---
        _a_keys  = ["a_000_0125", "a_0125_025", "a_025_050", "a_050_100", "a_100_200", "a_200_400", "a_400_800"]
        _a_cols  = [54, 55, 56, 57, 58, 59, 60]
        a_vals   = {k: _flt(row[c]) for k, c in zip(_a_keys, _a_cols)}

        # E12 (oedometric modulus at 1-2 range) [kgf/cm²]
        E12_raw = _flt(row[61])
        E12_kPa = E12_raw * 100.0 if E12_raw is not None else None

        # Standard a1-2 value
        a12_cm2kgf = _flt(row[58])   # col 58 = a_050_100 ≈ a1-2 (0.5–1.0 range)

        # --- CU test (conditional on type_code) ---
        c_CU_kPa = c_CU_eff_kPa = phi_CU_deg = phi_CU_eff_deg = None
        if "cu" in type_code:
            c_CU_raw  = _flt(row[62])
            phi_CU    = _parse_angle(row[63])
            c_CUe_raw = _flt(row[64])
            phi_CUe   = _parse_angle(row[65])
            c_CU_kPa     = c_CU_raw  * 100.0 if c_CU_raw  is not None else None
            c_CU_eff_kPa = c_CUe_raw * 100.0 if c_CUe_raw is not None else None
            phi_CU_deg     = phi_CU
            phi_CU_eff_deg = phi_CUe

        # --- UU test ---
        c_UU_kPa = phi_UU_deg = None
        if "uu" in type_code:
            c_UU_raw   = _flt(row[66])
            phi_UU     = _parse_angle(row[67])
            c_UU_kPa   = c_UU_raw * 100.0 if c_UU_raw is not None else None
            phi_UU_deg = phi_UU

        # --- Oedometer extra params ---
        PC_raw  = _flt(row[68])
        Cc      = _flt(row[69])
        Cs      = _flt(row[70])
        cv_raw  = _flt(row[71])   # × 10⁻³ cm²/s
        kv_raw  = _flt(row[72])   # × 10⁻⁷ cm/s
        mv_raw  = _flt(row[73])   # cm²/N
        PC_kPa  = PC_raw * 100.0 if PC_raw is not None else None
        Cv_cm2s = cv_raw * 1e-3   if cv_raw is not None else None
        k_cm_s  = kv_raw * 1e-7   if kv_raw is not None else None

        # --- Unconfined compression ---
        Qu_raw  = _flt(row[74])
        Qu_kPa  = Qu_raw * 100.0 if Qu_raw is not None else None

        # --- Classification ---
        symbol_tcvn  = str(row[75]).strip() if row[75] else ""
        description  = str(row[76]).strip() if row[76] else ""

        samples.append({
            "bh_raw":       current_bh,
            "db_name":      BH_PREFIX + current_bh,
            "sample_code":  sample_code,
            "type_code":    type_code,
            "depth_from_m": depth_from,
            "depth_to_m":   depth_to,
            # physical
            "W_pct":           W_pct,
            "gamma_kNm3":      gamma_kNm3,
            "gamma_dry_kNm3":  gamma_dry_kNm3,
            "gamma_sub_kNm3":  gamma_sub_kNm3,
            "Gs":              Gs,
            "e0":              e0,
            "n_pct":           n_pct,
            "Sr_pct":          Sr_pct,
            # Atterberg
            "wL_pct":  wL,
            "wP_pct":  wP,
            "Ip":      Ip,
            "IS_liq":  IS,
            # direct shear
            "c_kPa":   c_kPa,
            "phi_deg": phi_deg,
            # oedometer — void ratios
            **{k: v for k, v in e_vals.items() if v is not None},
            # oedometer — compression coefficients
            **{k: v for k, v in a_vals.items() if v is not None},
            "a12_cm2kgf": a12_cm2kgf,
            "E12_kPa":    E12_kPa,
            # consolidation params
            "Cc":      Cc,
            "Cs":      Cs,
            "PC_kPa":  PC_kPa,
            "Cv_cm2s": Cv_cm2s,
            "k_cm_s":  k_cm_s,
            "mv":      mv_raw,
            # CU test
            "c_CU_kPa":      c_CU_kPa,
            "phi_CU_deg":    phi_CU_deg,
            "c_CU_eff_kPa":  c_CU_eff_kPa,
            "phi_CU_eff_deg":phi_CU_eff_deg,
            # UU test
            "Cu_UU_kPa":   c_UU_kPa,
            "phi_UU_deg":  phi_UU_deg,
            # unconfined
            "qu_kPa": Qu_kPa,
            # classification
            "symbol_tcvn":   symbol_tcvn,
            "description_vi": description,
        })

    return samples


# ---------------------------------------------------------------------------
# SQLite import
# ---------------------------------------------------------------------------

_NEW_COLS = [
    ("gamma_sub_kNm3",  "REAL"),
    ("c_CU_kPa",        "REAL"),
    ("phi_CU_deg",      "REAL"),
    ("c_CU_eff_kPa",    "REAL"),
    ("phi_CU_eff_deg",  "REAL"),
    ("mv",              "REAL"),
    ("E12_kPa",         "REAL"),
    # void ratios at each pressure
    ("e_000",   "REAL"), ("e_0125",  "REAL"), ("e_025",  "REAL"), ("e_050",  "REAL"),
    ("e_100",   "REAL"), ("e_200",   "REAL"), ("e_400",  "REAL"), ("e_800",  "REAL"),
    # compression coefficients
    ("a_000_0125",  "REAL"), ("a_0125_025", "REAL"), ("a_025_050",  "REAL"),
    ("a_050_100",   "REAL"), ("a_100_200",  "REAL"), ("a_200_400",  "REAL"),
    ("a_400_800",   "REAL"),
]

_BASE_COLS = [
    "borehole_id", "sample_id", "depth_from_m", "depth_to_m",
    "w_pct", "gamma_kNm3", "gamma_dry_kNm3", "Gs", "Sr_pct", "n_pct", "e0",
    "wL_pct", "wP_pct", "Ip", "IS_liq",
    "phi_deg", "c_kPa", "a12_cm2kgf", "E_kPa",
    "Cc", "Cs", "Cu_UU_kPa", "phi_UU_deg",
    "symbol_tcvn", "description_vi",
    "k_cm_s", "Cv_cm2s", "PC_kPa", "qu_kPa",
]


def update_db(samples: list[dict], db_path: Path) -> int:
    con = sqlite3.connect(str(db_path), timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=OFF")

    # Add missing columns idempotently
    existing = {r[1] for r in con.execute("PRAGMA table_info(lab_tests)").fetchall()}
    for col_name, col_type in _NEW_COLS:
        if col_name not in existing:
            con.execute(f"ALTER TABLE lab_tests ADD COLUMN {col_name} {col_type}")
    con.commit()

    # Get borehole_id map for QTT
    bh_rows = con.execute(
        "SELECT name, id FROM boreholes WHERE zone_id=4"
    ).fetchall()
    bh_map = {r[0]: r[1] for r in bh_rows}

    # Delete existing QTT lab tests (re-import is idempotent)
    qtt_bh_ids = list(bh_map.values())
    if qtt_bh_ids:
        placeholders = ",".join("?" * len(qtt_bh_ids))
        con.execute(f"DELETE FROM lab_tests WHERE borehole_id IN ({placeholders})", qtt_bh_ids)
    con.commit()

    n_inserted = 0
    all_cols = _BASE_COLS + [c[0] for c in _NEW_COLS]

    for s in samples:
        bh_id = bh_map.get(s["db_name"])
        if bh_id is None:
            print(f"  Cảnh báo: không tìm thấy BH {s['db_name']} trong SQLite — bỏ qua")
            continue

        row = {
            "borehole_id":    bh_id,
            "sample_id":      s["sample_code"],
            "depth_from_m":   s["depth_from_m"],
            "depth_to_m":     s["depth_to_m"],
            "w_pct":          s.get("W_pct"),
            "gamma_kNm3":     s.get("gamma_kNm3"),
            "gamma_dry_kNm3": s.get("gamma_dry_kNm3"),
            "Gs":             s.get("Gs"),
            "Sr_pct":         s.get("Sr_pct"),
            "n_pct":          s.get("n_pct"),
            "e0":             s.get("e0"),
            "wL_pct":         s.get("wL_pct"),
            "wP_pct":         s.get("wP_pct"),
            "Ip":             s.get("Ip"),
            "IS_liq":         s.get("IS_liq"),
            "phi_deg":        s.get("phi_deg"),
            "c_kPa":          s.get("c_kPa"),
            "a12_cm2kgf":     s.get("a12_cm2kgf"),
            "E_kPa":          s.get("E12_kPa"),
            "Cc":             s.get("Cc"),
            "Cs":             s.get("Cs"),
            "Cu_UU_kPa":      s.get("Cu_UU_kPa"),
            "phi_UU_deg":     s.get("phi_UU_deg"),
            "symbol_tcvn":    s.get("symbol_tcvn"),
            "description_vi": s.get("description_vi"),
            "k_cm_s":         s.get("k_cm_s"),
            "Cv_cm2s":        s.get("Cv_cm2s"),
            "PC_kPa":         s.get("PC_kPa"),
            "qu_kPa":         s.get("qu_kPa"),
            # new QTT-specific
            "gamma_sub_kNm3":  s.get("gamma_sub_kNm3"),
            "c_CU_kPa":        s.get("c_CU_kPa"),
            "phi_CU_deg":      s.get("phi_CU_deg"),
            "c_CU_eff_kPa":    s.get("c_CU_eff_kPa"),
            "phi_CU_eff_deg":  s.get("phi_CU_eff_deg"),
            "mv":              s.get("mv"),
            "E12_kPa":         s.get("E12_kPa"),
            **{k: s.get(k) for k, _ in _NEW_COLS[7:]},  # e_ and a_ columns
        }

        cols_to_insert = [c for c in all_cols if row.get(c) is not None]
        cols_to_insert_list = ["borehole_id", "sample_id", "depth_from_m", "depth_to_m"] + \
                               [c for c in cols_to_insert if c not in ("borehole_id","sample_id","depth_from_m","depth_to_m")]
        placeholders = ",".join("?" * len(cols_to_insert_list))
        vals = [row[c] for c in cols_to_insert_list]

        con.execute(
            f"INSERT INTO lab_tests ({','.join(cols_to_insert_list)}) VALUES ({placeholders})",
            vals
        )
        n_inserted += 1

    con.commit()
    con.close()
    return n_inserted


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def write_json(samples: list[dict], path: Path) -> None:
    # Group by borehole
    bhs: dict[str, list] = {}
    for s in samples:
        bhs.setdefault(s["db_name"], []).append(s)

    out = {
        "_meta": {
            "source": str(XLS_PATH),
            "zone":   "QTTTTP",
            "zone_code": ZONE_CODE,
            "updated": datetime.now().isoformat(timespec="seconds"),
            "n_boreholes": len(bhs),
            "n_samples":   len(samples),
        },
        "boreholes": [
            {
                "db_name": bh_name,
                "bh_raw":  bh_name.replace(BH_PREFIX, ""),
                "n_samples": len(slist),
                "samples": slist,
            }
            for bh_name, slist in sorted(bhs.items())
        ]
    }
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON: {path} ({len(samples)} mẫu)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print("Doc XLS ...")
    samples = read_xls(XLS_PATH)
    print(f"Đọc được {len(samples)} mẫu từ {len({s['db_name'] for s in samples})} hố khoan")

    # Summary
    by_bh: dict[str, int] = {}
    for s in samples:
        by_bh[s["db_name"]] = by_bh.get(s["db_name"], 0) + 1
    for bh, n in sorted(by_bh.items()):
        print(f"  {bh}: {n} mẫu")

    # Write JSON
    write_json(samples, JSON_OUT)

    # Write to SQLite — try main DB first, fall back to backup
    db_targets = [DB_PATH, DB_BACKUP]
    for db in db_targets:
        try:
            n = update_db(samples, db)
            print(f"SQLite ({db.name}): đã ghi {n} dòng vào lab_tests")
            break
        except Exception as e:
            print(f"  Lỗi {db.name}: {e} — thử backup …")
    else:
        print("  Không ghi được SQLite — chỉ có JSON.")

    print("Xong.")
