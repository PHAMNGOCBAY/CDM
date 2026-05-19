"""
Import KQTN (lab test results) from three Excel files into TTHC.sqlite.

Sources:
  BXN tong hop (2): HK2, HK3 boreholes (new) — VNI encoding
  BXN tong hop (3): CV-HK1..17 boreholes  — UTF-8, update Cc/Cs/k/Cv/PC
  NHC BTH:          NHC-BH-XX boreholes   — g/cm³ + kG/cm² units
  BOKE M:           KE-HK1..6 boreholes   — g/cm³ + kg/cm² units

New columns added to lab_tests: k_cm_s, Cv_cm2s, PC_kPa, qu_kPa
"""

import os
import math
import json
import sqlite3
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
DB_PATH = _ROOT / "data" / "TTHC.sqlite"

def _find(name_fragment: str) -> Path:
    """Walk DIA CHAT to find a file containing name_fragment."""
    dia_chat = _ROOT / "DIA CHAT"
    for root, _dirs, files in os.walk(dia_chat):
        for f in files:
            if name_fragment in f:
                return Path(root) / f
    raise FileNotFoundError(f"Cannot find file containing '{name_fragment}'")

BXN_FILE  = _find("BXN-3. KQTN")
NHC_FILE  = _find("NHC-2. KQTN")
BOKE_FILE = _find("BOKE-003. KQTN")

# ── Helpers ───────────────────────────────────────────────────────────────────
def ddmm_to_deg(val) -> float | None:
    """Convert stored angle to decimal degrees.

    Values > 45 are treated as DDMM (degrees*100 + minutes).
    Values ≤ 45 are already decimal degrees (e.g., phi=4 from BOKE).
    Handles M > 59 gracefully (sum to minutes, then /60).
    """
    if val is None:
        return None
    try:
        v = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or v < 0:
        return None
    if v <= 45.0:
        return v  # already decimal degrees
    d = int(v) // 100
    m = int(v) % 100
    total_min = d * 60 + m
    return total_min / 60.0


def safe(val):
    """Return None for NaN/NaT, else the value."""
    if val is None:
        return None
    try:
        if math.isnan(float(val)):
            return None
    except (TypeError, ValueError):
        pass
    return val


def parse_depth(s) -> tuple[float | None, float | None]:
    """Parse '2 - 2.2' or '1.4' into (from_m, to_m)."""
    if s is None:
        return None, None
    s = str(s).strip()
    parts = [p.strip() for p in s.replace("–", "-").split("-") if p.strip()]
    if len(parts) == 2:
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            pass
    try:
        return float(s), None
    except ValueError:
        return None, None


# ── DB helpers ─────────────────────────────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def alter_table(con: sqlite3.Connection):
    """Add new columns to lab_tests if missing."""
    cur = con.cursor()
    existing = {r["name"] for r in cur.execute("PRAGMA table_info(lab_tests)")}
    new_cols = [
        ("k_cm_s",   "REAL"),
        ("Cv_cm2s",  "REAL"),
        ("PC_kPa",   "REAL"),
        ("qu_kPa",   "REAL"),
    ]
    for col, typ in new_cols:
        if col not in existing:
            cur.execute(f"ALTER TABLE lab_tests ADD COLUMN {col} {typ}")
            print(f"  Added column: {col} {typ}")
    con.commit()


def get_borehole_id(con: sqlite3.Connection, db_name: str,
                    zone_id: int, create_if_missing=True) -> int | None:
    cur = con.cursor()
    row = cur.execute("SELECT id FROM boreholes WHERE name=?", (db_name,)).fetchone()
    if row:
        return row["id"]
    if not create_if_missing:
        return None
    cur.execute(
        "INSERT INTO boreholes (zone_id, name) VALUES (?,?)",
        (zone_id, db_name)
    )
    con.commit()
    print(f"  Created borehole: {db_name} (zone_id={zone_id})")
    return cur.lastrowid


def upsert_record(con: sqlite3.Connection, bh_id: int, rec: dict):
    """
    If a record with (borehole_id, sample_id) exists, UPDATE only null fields.
    Otherwise INSERT the full record.
    rec must contain 'sample_id'. All other keys map to lab_tests columns.
    """
    cur = con.cursor()
    sample_id = rec["sample_id"]
    existing = cur.execute(
        "SELECT id FROM lab_tests WHERE borehole_id=? AND sample_id=?",
        (bh_id, sample_id)
    ).fetchone()

    # filter out None values — only set fields we actually have data for
    data = {k: v for k, v in rec.items() if v is not None and k != "sample_id"}

    if existing:
        lt_id = existing["id"]
        # Only update currently-NULL fields
        if data:
            set_parts = []
            vals = []
            for col, val in data.items():
                set_parts.append(f"{col} = COALESCE({col}, ?)")
                vals.append(val)
            vals.append(lt_id)
            sql = f"UPDATE lab_tests SET {', '.join(set_parts)} WHERE id=?"
            cur.execute(sql, vals)
    else:
        cols = ["borehole_id", "sample_id"] + list(data.keys())
        placeholders = ", ".join(["?"] * len(cols))
        vals = [bh_id, sample_id] + list(data.values())
        cur.execute(
            f"INSERT INTO lab_tests ({', '.join(cols)}) VALUES ({placeholders})",
            vals
        )


# ── BXN tong hop (2) — HK2 / HK3 ─────────────────────────────────────────────
# Column mapping (0-indexed DataFrame columns, skiprows=10):
#   3=sample_id, 4=depth, 17=w%, 18=gamma, 19=gamma_dry, 21=Gs, 22=Sr, 23=n,
#   24=e0, 29=wL, 30=wP, 31=IP, 32=IL, 49=k×1e-6, 51=E_kPa, 52=Cv×1e-3,
#   54=Cc, 55=Cs, 56=PC_kPa, 65=phi(DDMM), 66=c_kPa, 68=qu_kPa,
#   69=phi_UU(DDMM), 70=Cu_UU_kPa, 76=description_vi
#   (gamma already kN/m³)
BXN2_COLS = {
    "sample_id_col": 3,
    "depth_col": 4,
    "w_pct": 17,
    "gamma_kNm3": 18,
    "gamma_dry_kNm3": 19,
    "Gs": 21,
    "Sr_pct": 22,
    "n_pct": 23,
    "e0": 24,
    "wL_pct": 29,
    "wP_pct": 30,
    "Ip": 31,
    "IS_liq": 32,
    "k_col": 49,      # × 1e-6 → cm/s
    "E_kPa": 51,
    "Cv_col": 52,     # × 1e-3 → cm²/s
    "Cc": 54,
    "Cs": 55,
    "PC_kPa": 56,     # already kPa
    "phi_col": 65,    # DDMM
    "c_kPa": 66,      # kPa
    "qu_col": 68,     # kPa
    "phi_UU_col": 69, # DDMM
    "Cu_UU_kPa": 70,
}

def import_bxn2(con: sqlite3.Connection) -> dict:
    print("\n=== BXN tong hop (2): HK2 / HK3 ===")
    df = pd.read_excel(BXN_FILE, sheet_name="tong hop (2)", header=None,
                       engine="xlrd", skiprows=10)
    stats = {"rows_read": 0, "inserted": 0, "updated": 0, "skipped": 0}

    for _, row in df.iterrows():
        sample_id = safe(row.iloc[BXN2_COLS["sample_id_col"]])
        if sample_id is None:
            continue
        sample_id = str(sample_id).strip()
        if not sample_id or sample_id.lower() in ("nan", "mau", "4"):
            continue

        # Derive borehole name from sample prefix: "HK2-1" → "BXN-HK2"
        parts = sample_id.split("-")
        if len(parts) < 2:
            stats["skipped"] += 1
            continue
        bh_prefix = parts[0].strip().upper()  # e.g. "HK2"
        if bh_prefix not in ("HK2", "HK3"):
            stats["skipped"] += 1
            continue
        db_bh_name = f"BXN-{bh_prefix}"
        bh_id = get_borehole_id(con, db_bh_name, zone_id=2)

        depth_from, depth_to = parse_depth(row.iloc[BXN2_COLS["depth_col"]])
        phi = ddmm_to_deg(safe(row.iloc[BXN2_COLS["phi_col"]]))
        phi_UU = ddmm_to_deg(safe(row.iloc[BXN2_COLS["phi_UU_col"]]))

        k_raw = safe(row.iloc[BXN2_COLS["k_col"]])
        k_cms = float(k_raw) * 1e-6 if k_raw is not None else None

        cv_raw = safe(row.iloc[BXN2_COLS["Cv_col"]])
        cv = float(cv_raw) * 1e-3 if cv_raw is not None else None

        rec = {
            "sample_id": sample_id,
            "depth_from_m": depth_from,
            "depth_to_m": depth_to,
            "w_pct": safe(row.iloc[BXN2_COLS["w_pct"]]),
            "gamma_kNm3": safe(row.iloc[BXN2_COLS["gamma_kNm3"]]),
            "gamma_dry_kNm3": safe(row.iloc[BXN2_COLS["gamma_dry_kNm3"]]),
            "Gs": safe(row.iloc[BXN2_COLS["Gs"]]),
            "Sr_pct": safe(row.iloc[BXN2_COLS["Sr_pct"]]),
            "n_pct": safe(row.iloc[BXN2_COLS["n_pct"]]),
            "e0": safe(row.iloc[BXN2_COLS["e0"]]),
            "wL_pct": safe(row.iloc[BXN2_COLS["wL_pct"]]),
            "wP_pct": safe(row.iloc[BXN2_COLS["wP_pct"]]),
            "Ip": safe(row.iloc[BXN2_COLS["Ip"]]),
            "IS_liq": safe(row.iloc[BXN2_COLS["IS_liq"]]),
            "k_cm_s": k_cms,
            "E_kPa": safe(row.iloc[BXN2_COLS["E_kPa"]]),
            "Cv_cm2s": cv,
            "Cc": safe(row.iloc[BXN2_COLS["Cc"]]),
            "Cs": safe(row.iloc[BXN2_COLS["Cs"]]),
            "PC_kPa": safe(row.iloc[BXN2_COLS["PC_kPa"]]),
            "phi_deg": phi,
            "c_kPa": safe(row.iloc[BXN2_COLS["c_kPa"]]),
            "qu_kPa": safe(row.iloc[BXN2_COLS["qu_col"]]),
            "phi_UU_deg": phi_UU,
            "Cu_UU_kPa": safe(row.iloc[BXN2_COLS["Cu_UU_kPa"]]),
        }

        cur_count = con.execute(
            "SELECT COUNT(*) FROM lab_tests WHERE borehole_id=? AND sample_id=?",
            (bh_id, sample_id)
        ).fetchone()[0]

        upsert_record(con, bh_id, rec)
        stats["rows_read"] += 1
        if cur_count:
            stats["updated"] += 1
        else:
            stats["inserted"] += 1

    con.commit()
    print(f"  rows={stats['rows_read']}, inserted={stats['inserted']}, updated={stats['updated']}")
    return stats


# ── BXN tong hop (3) — CV-HK1..17 ────────────────────────────────────────────
# Column mapping (0-indexed, skiprows=10):
#   2=borehole (e.g."CV-HK2"), 3=sample_id, 4=depth
#   Physical: 17=gamma, 18=gamma_dry, 22=Sr, 23=n, 23=e0(emax?)
#   Consolidation: 39=a12, 40=E_kPa, 45=Cv(cm²/s direct), 47=Cc, 48=Cs
#   NQ HONG test: 61=PC_kPa, 62=Cc (better), 63=Cs (better)
#   Permeability: 64=Cv×1e-7, 65=k×1e-10
#   Direct shear: 59=phi(DDMM), 60=c_kPa
#   UU test: 67=phi_UU(DDMM), 68=Cu_UU_kPa
#   Symbols: 73=symbol_tcvn, 74=description_vi
BXN3_COLS = {
    "bh_col": 2,
    "sample_id_col": 3,
    "depth_col": 4,
    "gamma_kNm3": 17,
    "gamma_dry_kNm3": 18,
    "Sr_pct": 22,
    "n_pct": 23,
    "e0": 24,
    "wP_pct": 29,      # WP at 29 based on analysis (official 30)
    "Ip": 30,
    "IS_liq": 31,
    "a12_col": 39,     # a(100-200) kPa-1×10-2
    "E_kPa": 40,
    "Cv_col_nhanh": 45,  # from nén nhanh section, direct cm²/s
    "Cc_nhanh": 47,
    "Cs_nhanh": 48,
    "PC_col": 61,      # preconsolidation from NQ Hong, kPa
    "Cc": 62,          # from NQ Hong (preferred)
    "Cs": 63,
    "Cv_col": 64,      # Cv ×10-7 cm²/s
    "k_col": 65,       # k ×10-10 cm/s
    "phi_col": 59,     # direct shear phi (DDMM)
    "c_kPa": 60,
    "phi_UU_col": 67,  # UU test (DDMM)
    "Cu_UU_kPa": 68,
    "symbol_tcvn": 73,
    "description_vi": 74,
}

def import_bxn3(con: sqlite3.Connection) -> dict:
    print("\n=== BXN tong hop (3): CV-HK1..17 ===")
    df = pd.read_excel(BXN_FILE, sheet_name="tong hop (3)", header=None,
                       engine="xlrd", skiprows=10)
    stats = {"rows_read": 0, "inserted": 0, "updated": 0, "skipped": 0}

    for _, row in df.iterrows():
        bh_raw = safe(row.iloc[BXN3_COLS["bh_col"]])
        sample_id = safe(row.iloc[BXN3_COLS["sample_id_col"]])
        if bh_raw is None or sample_id is None:
            stats["skipped"] += 1
            continue
        bh_raw = str(bh_raw).strip()
        sample_id = str(sample_id).strip()
        if not bh_raw or not sample_id or bh_raw.lower() in ("nan", "ho khoan", "3"):
            stats["skipped"] += 1
            continue

        # e.g. "CV-HK2" → "BXN-CV-HK2"
        db_bh_name = f"BXN-{bh_raw}" if not bh_raw.startswith("BXN-") else bh_raw
        bh_id = get_borehole_id(con, db_bh_name, zone_id=2)

        depth_from, depth_to = parse_depth(row.iloc[BXN3_COLS["depth_col"]])

        phi = ddmm_to_deg(safe(row.iloc[BXN3_COLS["phi_col"]]))
        phi_UU = ddmm_to_deg(safe(row.iloc[BXN3_COLS["phi_UU_col"]]))

        cv_raw = safe(row.iloc[BXN3_COLS["Cv_col"]])
        cv = float(cv_raw) * 1e-7 if cv_raw is not None else None
        # fallback to nén nhanh section Cv
        if cv is None:
            cv_n = safe(row.iloc[BXN3_COLS["Cv_col_nhanh"]])
            cv = float(cv_n) if cv_n is not None else None  # already cm²/s in some rows

        k_raw = safe(row.iloc[BXN3_COLS["k_col"]])
        k_cms = float(k_raw) * 1e-10 if k_raw is not None else None

        Cc = safe(row.iloc[BXN3_COLS["Cc"]])
        Cs = safe(row.iloc[BXN3_COLS["Cs"]])
        # fallback to nén nhanh section Cc/Cs if NQ Hong not available
        if Cc is None:
            Cc = safe(row.iloc[BXN3_COLS["Cc_nhanh"]])
        if Cs is None:
            Cs = safe(row.iloc[BXN3_COLS["Cs_nhanh"]])

        PC = safe(row.iloc[BXN3_COLS["PC_col"]])  # kPa

        a12_raw = safe(row.iloc[BXN3_COLS["a12_col"]])
        # a(100-200) in kPa-1×10-2 → convert to cm²/kN: 1 kPa-1×10-2 = 0.01/kPa = 0.01 cm²/kN
        # existing DB stores a12_cm2kgf in similar units, so store as-is / 101.97
        a12 = float(a12_raw) / 101.97 if a12_raw is not None else None

        sym = safe(row.iloc[BXN3_COLS["symbol_tcvn"]])
        desc = safe(row.iloc[BXN3_COLS["description_vi"]])

        rec = {
            "sample_id": sample_id,
            "depth_from_m": depth_from,
            "depth_to_m": depth_to,
            "gamma_kNm3": safe(row.iloc[BXN3_COLS["gamma_kNm3"]]),
            "gamma_dry_kNm3": safe(row.iloc[BXN3_COLS["gamma_dry_kNm3"]]),
            "Sr_pct": safe(row.iloc[BXN3_COLS["Sr_pct"]]),
            "n_pct": safe(row.iloc[BXN3_COLS["n_pct"]]),
            "e0": safe(row.iloc[BXN3_COLS["e0"]]),
            "a12_cm2kgf": a12,
            "E_kPa": safe(row.iloc[BXN3_COLS["E_kPa"]]),
            "Cv_cm2s": cv,
            "k_cm_s": k_cms,
            "Cc": Cc,
            "Cs": Cs,
            "PC_kPa": PC,
            "phi_deg": phi,
            "c_kPa": safe(row.iloc[BXN3_COLS["c_kPa"]]),
            "phi_UU_deg": phi_UU,
            "Cu_UU_kPa": safe(row.iloc[BXN3_COLS["Cu_UU_kPa"]]),
            "symbol_tcvn": str(sym) if sym else None,
            "description_vi": str(desc) if desc else None,
        }

        cur_count = con.execute(
            "SELECT COUNT(*) FROM lab_tests WHERE borehole_id=? AND sample_id=?",
            (bh_id, sample_id)
        ).fetchone()[0]

        upsert_record(con, bh_id, rec)
        stats["rows_read"] += 1
        if cur_count:
            stats["updated"] += 1
        else:
            stats["inserted"] += 1

    con.commit()
    print(f"  rows={stats['rows_read']}, inserted={stats['inserted']}, updated={stats['updated']}")
    return stats


# ── NHC BTH ───────────────────────────────────────────────────────────────────
# Column mapping (0-indexed, skiprows=12):
#   2=borehole, 3=sample_id, 4=depth_from, 6=depth_to
#   Physical: 24=W%, 29=gw(g/cm³)×9.81, 30=gc×9.81, 31=Gs, 32=e0, 33=n%, 34=S%
#   Atterberg: 25=WL, 26=WP, 27=IP, 28=LI
#   Shear: 40=phi(DDMM), 41=C(kG/cm²)×98.07
#   Consolidation: 43=Cv×1e-3, 46=k×1e-7, 47=Cc, 49=Cs, 50=PC×98.07, 51=qu×98.07
#   symbol=60, description=61
NHC_COLS = {
    "bh_col": 2,
    "sample_id_col": 3,
    "depth_from_col": 4,
    "depth_to_col": 6,
    "w_pct": 24,
    "gamma_kNm3": 29,    # g/cm³ × 9.81
    "gamma_dry_kNm3": 30,
    "Gs": 31,
    "e0": 32,
    "n_pct": 33,
    "Sr_pct": 34,
    "wL_pct": 25,
    "wP_pct": 26,
    "Ip": 27,
    "IS_liq": 28,
    "phi_col": 40,       # DDMM (or centidegrees if ≤45)
    "c_col": 41,         # kG/cm² × 98.07
    "a12_col": 42,       # cm²/kG (compressibility coefficient)
    "Cv_col": 43,        # ×10-3 cm²/s
    "k_col": 46,         # ×10-7 cm/s
    "Cc": 47,
    "Cs": 49,
    "PC_col": 50,        # kG/cm² × 98.07
    "qu_col": 51,        # kG/cm² × 98.07
    "E50_col": 52,       # kG/cm² × 98.07 → E_kPa
    "symbol_tcvn": 60,
    "description_vi": 61,
}

def import_nhc(con: sqlite3.Connection) -> dict:
    print("\n=== NHC BTH ===")
    df = pd.read_excel(NHC_FILE, sheet_name="BTH", header=None,
                       engine="openpyxl", skiprows=12)
    stats = {"rows_read": 0, "inserted": 0, "updated": 0, "skipped": 0}

    for _, row in df.iterrows():
        bh_raw = safe(row.iloc[NHC_COLS["bh_col"]])
        sample_id = safe(row.iloc[NHC_COLS["sample_id_col"]])
        if bh_raw is None or sample_id is None:
            stats["skipped"] += 1
            continue
        bh_raw = str(bh_raw).strip()
        sample_id = str(sample_id).strip()
        if not bh_raw or not sample_id or bh_raw.lower() in ("nan", "lo khoan", "2"):
            stats["skipped"] += 1
            continue

        # "BH-01" → "NHC-BH-01", "BH20" → "NHC-BH-20"
        import re as _re
        norm = _re.sub(r'^BH(\d+)$', r'BH-\1', bh_raw)  # BH20 → BH-20
        db_bh_name = f"NHC-{norm}" if not norm.startswith("NHC-") else norm
        bh_id = get_borehole_id(con, db_bh_name, zone_id=3)

        depth_from = safe(row.iloc[NHC_COLS["depth_from_col"]])
        depth_to   = safe(row.iloc[NHC_COLS["depth_to_col"]])
        try:
            depth_from = float(depth_from) if depth_from is not None else None
            depth_to   = float(depth_to)   if depth_to   is not None else None
        except (TypeError, ValueError):
            depth_from = depth_to = None

        phi_raw = safe(row.iloc[NHC_COLS["phi_col"]])
        phi = ddmm_to_deg(phi_raw)

        kGcm2 = 98.0665  # 1 kG/cm² = 98.0665 kPa

        c_raw = safe(row.iloc[NHC_COLS["c_col"]])
        c_kPa = float(c_raw) * kGcm2 if c_raw is not None else None

        cv_raw = safe(row.iloc[NHC_COLS["Cv_col"]])
        cv = float(cv_raw) * 1e-3 if cv_raw is not None else None

        k_raw = safe(row.iloc[NHC_COLS["k_col"]])
        k_cms = float(k_raw) * 1e-7 if k_raw is not None else None

        pc_raw = safe(row.iloc[NHC_COLS["PC_col"]])
        pc_kPa = float(pc_raw) * kGcm2 if pc_raw is not None else None

        qu_raw = safe(row.iloc[NHC_COLS["qu_col"]])
        qu_kPa = float(qu_raw) * kGcm2 if qu_raw is not None else None

        e50_raw = safe(row.iloc[NHC_COLS["E50_col"]])
        e_kPa = float(e50_raw) * kGcm2 if e50_raw is not None else None

        a12_raw = safe(row.iloc[NHC_COLS["a12_col"]])
        # cm²/kG unit: 1 cm²/kG ≈ 1.02 cm²/kN (numerically close, store as-is)
        a12 = float(a12_raw) if a12_raw is not None else None

        gw_raw = safe(row.iloc[NHC_COLS["gamma_kNm3"]])
        gamma = float(gw_raw) * 9.81 if gw_raw is not None else None
        gc_raw = safe(row.iloc[NHC_COLS["gamma_dry_kNm3"]])
        gamma_dry = float(gc_raw) * 9.81 if gc_raw is not None else None

        sym  = safe(row.iloc[NHC_COLS["symbol_tcvn"]])
        desc = safe(row.iloc[NHC_COLS["description_vi"]])

        rec = {
            "sample_id": sample_id,
            "depth_from_m": depth_from,
            "depth_to_m": depth_to,
            "w_pct": safe(row.iloc[NHC_COLS["w_pct"]]),
            "gamma_kNm3": gamma,
            "gamma_dry_kNm3": gamma_dry,
            "Gs": safe(row.iloc[NHC_COLS["Gs"]]),
            "e0": safe(row.iloc[NHC_COLS["e0"]]),
            "n_pct": safe(row.iloc[NHC_COLS["n_pct"]]),
            "Sr_pct": safe(row.iloc[NHC_COLS["Sr_pct"]]),
            "wL_pct": safe(row.iloc[NHC_COLS["wL_pct"]]),
            "wP_pct": safe(row.iloc[NHC_COLS["wP_pct"]]),
            "Ip": safe(row.iloc[NHC_COLS["Ip"]]),
            "IS_liq": safe(row.iloc[NHC_COLS["IS_liq"]]),
            "phi_deg": phi,
            "c_kPa": c_kPa,
            "a12_cm2kgf": a12,
            "Cv_cm2s": cv,
            "k_cm_s": k_cms,
            "Cc": safe(row.iloc[NHC_COLS["Cc"]]),
            "Cs": safe(row.iloc[NHC_COLS["Cs"]]),
            "PC_kPa": pc_kPa,
            "qu_kPa": qu_kPa,
            "E_kPa": e_kPa,
            "symbol_tcvn": str(sym) if sym else None,
            "description_vi": str(desc) if desc else None,
        }

        cur_count = con.execute(
            "SELECT COUNT(*) FROM lab_tests WHERE borehole_id=? AND sample_id=?",
            (bh_id, sample_id)
        ).fetchone()[0]

        upsert_record(con, bh_id, rec)
        stats["rows_read"] += 1
        if cur_count:
            stats["updated"] += 1
        else:
            stats["inserted"] += 1

    con.commit()
    print(f"  rows={stats['rows_read']}, inserted={stats['inserted']}, updated={stats['updated']}")
    return stats


# ── BOKE M ────────────────────────────────────────────────────────────────────
# Column mapping (0-indexed, skiprows=12):
#   1=borehole, 2=sample_id, 3=depth_from, 4=depth_to
#   Physical: 17=W%, 18=gamma_wet(g/cm³)×9.81, 19=gamma_dry×9.81, 21=Gs
#             22=n%(labeled e0 but actually porosity), 23=S%
#             25=WL, 26=WP, 27=IP, 28=IS_liq
#   Shear: 44=phi(decimal degrees), 43=C(kg/cm²)×98.07
#   Compression: 46=e0(at 0 kPa), 50=e_1.0, 51=e_2.0
#     → a12 = e_1.0 - e_2.0 (cm²/kgf)
#     → E_kPa = (1+(e_1+e_2)/2) / a12 × 98.07
BOKE_COLS = {
    "bh_col": 1,
    "sample_id_col": 2,
    "depth_from_col": 3,
    "depth_to_col": 4,
    "w_pct": 17,
    "gamma_wet_col": 18,  # g/cm³ × 9.81
    "gamma_dry_col": 19,
    "Gs": 21,
    "n_pct_col": 22,      # stored as porosity % (header says e0 but it's n%)
    "Sr_pct": 23,
    "wL_pct": 25,
    "wP_pct": 26,
    "Ip": 27,
    "IS_liq": 28,
    "phi_col": 44,        # decimal degrees
    "c_col": 43,          # kg/cm² × 98.07
    "e0_col": 46,         # void ratio at 0 kg/cm²
    "e_1kgf_col": 50,     # void ratio at 1.0 kg/cm²
    "e_2kgf_col": 51,     # void ratio at 2.0 kg/cm²
}

def import_boke(con: sqlite3.Connection) -> dict:
    print("\n=== BOKE M: KE-HK1..6 ===")
    df = pd.read_excel(BOKE_FILE, sheet_name="M", header=None,
                       engine="xlrd", skiprows=12)
    stats = {"rows_read": 0, "inserted": 0, "updated": 0, "skipped": 0}

    for _, row in df.iterrows():
        bh_raw = safe(row.iloc[BOKE_COLS["bh_col"]])
        sample_id = safe(row.iloc[BOKE_COLS["sample_id_col"]])
        if bh_raw is None or sample_id is None:
            stats["skipped"] += 1
            continue
        bh_raw = str(bh_raw).strip()
        sample_id = str(sample_id).strip()
        if not bh_raw or not sample_id or bh_raw.lower() in ("nan", "ho khoan", "2"):
            stats["skipped"] += 1
            continue

        # "HK1" → "KE-HK1"
        db_bh_name = f"KE-{bh_raw}" if not bh_raw.startswith("KE-") else bh_raw
        bh_id = get_borehole_id(con, db_bh_name, zone_id=1)

        depth_from = safe(row.iloc[BOKE_COLS["depth_from_col"]])
        depth_to   = safe(row.iloc[BOKE_COLS["depth_to_col"]])
        try:
            depth_from = float(depth_from) if depth_from is not None else None
            depth_to   = float(depth_to)   if depth_to   is not None else None
        except (TypeError, ValueError):
            depth_from = depth_to = None

        phi = ddmm_to_deg(safe(row.iloc[BOKE_COLS["phi_col"]]))

        kgcm2 = 98.0665
        c_raw = safe(row.iloc[BOKE_COLS["c_col"]])
        c_kPa = float(c_raw) * kgcm2 if c_raw is not None else None

        gw_raw = safe(row.iloc[BOKE_COLS["gamma_wet_col"]])
        gamma = float(gw_raw) * 9.81 if gw_raw is not None else None
        gc_raw = safe(row.iloc[BOKE_COLS["gamma_dry_col"]])
        gamma_dry = float(gc_raw) * 9.81 if gc_raw is not None else None

        # e0 from compression curve initial void ratio
        e0_raw = safe(row.iloc[BOKE_COLS["e0_col"]])
        e0 = float(e0_raw) if e0_raw is not None else None

        # Derive n_pct from the stored value (which is actually porosity %)
        n_raw = safe(row.iloc[BOKE_COLS["n_pct_col"]])
        n_pct = float(n_raw) if n_raw is not None else None

        # a12 and E from void ratio at 1-2 kg/cm²
        e1_raw = safe(row.iloc[BOKE_COLS["e_1kgf_col"]])
        e2_raw = safe(row.iloc[BOKE_COLS["e_2kgf_col"]])
        a12 = e_kPa = None
        if e1_raw is not None and e2_raw is not None:
            e1, e2 = float(e1_raw), float(e2_raw)
            if e1 > e2:
                a12 = e1 - e2  # cm²/kgf
                e_avg = (e1 + e2) / 2.0
                e_kPa = (1 + e_avg) / a12 * kgcm2

        rec = {
            "sample_id": sample_id,
            "depth_from_m": depth_from,
            "depth_to_m": depth_to,
            "w_pct": safe(row.iloc[BOKE_COLS["w_pct"]]),
            "gamma_kNm3": gamma,
            "gamma_dry_kNm3": gamma_dry,
            "Gs": safe(row.iloc[BOKE_COLS["Gs"]]),
            "e0": e0,
            "n_pct": n_pct,
            "Sr_pct": safe(row.iloc[BOKE_COLS["Sr_pct"]]),
            "wL_pct": safe(row.iloc[BOKE_COLS["wL_pct"]]),
            "wP_pct": safe(row.iloc[BOKE_COLS["wP_pct"]]),
            "Ip": safe(row.iloc[BOKE_COLS["Ip"]]),
            "IS_liq": safe(row.iloc[BOKE_COLS["IS_liq"]]),
            "phi_deg": phi,
            "c_kPa": c_kPa,
            "a12_cm2kgf": a12,
            "E_kPa": e_kPa,
        }

        cur_count = con.execute(
            "SELECT COUNT(*) FROM lab_tests WHERE borehole_id=? AND sample_id=?",
            (bh_id, sample_id)
        ).fetchone()[0]

        upsert_record(con, bh_id, rec)
        stats["rows_read"] += 1
        if cur_count:
            stats["updated"] += 1
        else:
            stats["inserted"] += 1

    con.commit()
    print(f"  rows={stats['rows_read']}, inserted={stats['inserted']}, updated={stats['updated']}")
    return stats


# ── Summary ───────────────────────────────────────────────────────────────────
def save_summary(results: dict):
    out_path = _ROOT / "data" / "kqtn_import_summary.json"
    cur = get_db().cursor()

    # Per-borehole stats
    bh_stats = cur.execute("""
        SELECT b.name,
               COUNT(*) as n,
               SUM(CASE WHEN lt.Cc IS NOT NULL THEN 1 ELSE 0 END) n_Cc,
               SUM(CASE WHEN lt.Cv_cm2s IS NOT NULL THEN 1 ELSE 0 END) n_Cv,
               SUM(CASE WHEN lt.k_cm_s IS NOT NULL THEN 1 ELSE 0 END) n_k,
               SUM(CASE WHEN lt.PC_kPa IS NOT NULL THEN 1 ELSE 0 END) n_PC
        FROM lab_tests lt JOIN boreholes b ON lt.borehole_id = b.id
        GROUP BY b.name ORDER BY b.name
    """).fetchall()

    summary = {
        "_meta": {
            "updated": "2026-05-18",
            "sources": [
                str(BXN_FILE.name),
                str(NHC_FILE.name),
                str(BOKE_FILE.name),
            ],
        },
        "import_results": results,
        "boreholes": [
            {
                "name": r[0], "n_samples": r[1],
                "n_Cc": r[2], "n_Cv": r[3], "n_k": r[4], "n_PC": r[5],
            }
            for r in bh_stats
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSaved summary → {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"DB: {DB_PATH}")
    print(f"BXN: {BXN_FILE.name}")
    print(f"NHC: {NHC_FILE.name}")
    print(f"BOKE: {BOKE_FILE.name}")

    con = get_db()
    print("\n[1] Altering lab_tests schema...")
    alter_table(con)

    print("\n[2] Importing data...")
    results = {}
    results["bxn_tong_hop_2"] = import_bxn2(con)
    results["bxn_tong_hop_3"] = import_bxn3(con)
    results["nhc_bth"]        = import_nhc(con)
    results["boke_m"]         = import_boke(con)

    print("\n[3] Saving summary JSON...")
    save_summary(results)

    # Final counts
    cur = con.cursor()
    total = cur.execute("SELECT COUNT(*) FROM lab_tests").fetchone()[0]
    n_Cc  = cur.execute("SELECT COUNT(*) FROM lab_tests WHERE Cc IS NOT NULL").fetchone()[0]
    n_k   = cur.execute("SELECT COUNT(*) FROM lab_tests WHERE k_cm_s IS NOT NULL").fetchone()[0]
    n_Cv  = cur.execute("SELECT COUNT(*) FROM lab_tests WHERE Cv_cm2s IS NOT NULL").fetchone()[0]
    n_PC  = cur.execute("SELECT COUNT(*) FROM lab_tests WHERE PC_kPa IS NOT NULL").fetchone()[0]
    print(f"\n=== DB summary ===")
    print(f"  Total lab_tests rows : {total}")
    print(f"  Rows with Cc         : {n_Cc}")
    print(f"  Rows with k_cm_s     : {n_k}")
    print(f"  Rows with Cv_cm2s    : {n_Cv}")
    print(f"  Rows with PC_kPa     : {n_PC}")
    con.close()


if __name__ == "__main__":
    main()
