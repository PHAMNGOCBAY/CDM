"""
qtt_lab_import.py
Parse ket qua thi nghiem dia chat khu vuc QTT tu:
  G:/My Drive/202605-TRUNG TAM HCM/QUANG TRUONG VI DAN/QTT-260524 QTT TP. KQTN.xls

Boreholes: ND-02, ND-06, ND-07  (36 mau)
Ghi vao: data/qtt_lab_tests_202605_TTHC.json + data/TTHC.sqlite (bang lab_tests)

Su dung:  python scripts/qtt_lab_import.py
"""
import json, re, sqlite3, datetime
from pathlib import Path
from typing import Optional
import xlrd

_ROOT    = Path(__file__).resolve().parent.parent
_XLS     = (Path(r"G:\My Drive\202605-TRUNG TAM HCM\QUANG TRUONG VI DAN")
            / "QTT-260524 QTT TP. KQTN.xls")
_DB      = _ROOT / "data" / "TTHC.sqlite"
_JSON    = _ROOT / "data" / "qtt_lab_tests_202605_TTHC.json"

# Column indices (0-based) -- sheet "M", data start row 12
_C = dict(
    bh=1, sample_id=2, depth_from=3, depth_to=4,
    w_pct=17, gamma_nat=18, gamma_dry=19, gamma_sub=20,
    Gs=21, e0=22, n_pct=23, Sr_pct=24,
    wL=25, wP=26, Ip=27, IS=28,
    c_shear=43, phi_shear=44,
    a_1_2=58, E1_2=61,
    c_CU=62, phi_CU_str=63, c_CU_eff=64, phi_CU_eff=65,
    c_UU=66, phi_UU_str=67,
    PC=68, Cc=69, Cs=70, cv_1e3=71, kv_1e7=72, Qu=74,
    symbol=75, description=76,
)
_K = 98.0665   # kgf/cm2 -> kPa
_G = 9.81      # g/cm3  -> kN/m3


def _fv(row: list, col: int) -> Optional[float]:
    v = row[col]
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


def _phi(s) -> Optional[float]:
    """Parse 'd deg m min' string e.g. '7?41 ' -> 7.683"""
    m = re.search(r'(\d+)\D+(\d+)', str(s or ''))
    return int(m.group(1)) + int(m.group(2)) / 60.0 if m else None


def _kpa(row: list, col: int) -> Optional[float]:
    v = _fv(row, col)
    return round(v * _K, 2) if v is not None else None


def parse_xls(path: Path = _XLS) -> list[dict]:
    wb = xlrd.open_workbook(str(path))
    sh = wb.sheet_by_name("M")
    records = []
    for r in range(12, sh.nrows):
        row = [sh.cell_value(r, c) for c in range(sh.ncols)]
        bh = str(row[_C["bh"]]).strip()
        if not bh:
            continue
        df = _fv(row, _C["depth_from"])
        if df is None:
            continue
        gn = _fv(row, _C["gamma_nat"])
        gd = _fv(row, _C["gamma_dry"])
        gs = _fv(row, _C["gamma_sub"])
        cv_r = _fv(row, _C["cv_1e3"])
        kv_r = _fv(row, _C["kv_1e7"])
        records.append({
            "borehole_name":   bh,
            "sample_id":       str(row[_C["sample_id"]]).strip(),
            "depth_from_m":    round(df, 2),
            "depth_to_m":      round(_fv(row, _C["depth_to"]) or df + 0.5, 2),
            "w_pct":           _fv(row, _C["w_pct"]),
            "gamma_kNm3":      round(gn * _G, 3) if gn else None,
            "gamma_dry_kNm3":  round(gd * _G, 3) if gd else None,
            "gamma_sub_kNm3":  round(gs * _G, 3) if gs else None,
            "Gs":              _fv(row, _C["Gs"]),
            "e0":              _fv(row, _C["e0"]),
            "n_pct":           _fv(row, _C["n_pct"]),
            "Sr_pct":          _fv(row, _C["Sr_pct"]),
            "wL_pct":          _fv(row, _C["wL"]),
            "wP_pct":          _fv(row, _C["wP"]),
            "Ip":              _fv(row, _C["Ip"]),
            "IS_liq":          _fv(row, _C["IS"]),
            "c_kPa":           _kpa(row, _C["c_shear"]),
            "phi_deg":         _fv(row, _C["phi_shear"]),
            "a12_cm2kgf":      _fv(row, _C["a_1_2"]),
            "E_kPa":           _kpa(row, _C["E1_2"]),
            "c_CU_kPa":        _kpa(row, _C["c_CU"]),
            "phi_CU_deg":      _phi(row[_C["phi_CU_str"]]),
            "c_CU_eff_kPa":    _kpa(row, _C["c_CU_eff"]),
            "phi_CU_eff_deg":  _phi(row[_C["phi_CU_eff"]]),
            "Cu_UU_kPa":       _kpa(row, _C["c_UU"]),
            "phi_UU_deg":      _phi(row[_C["phi_UU_str"]]),
            "PC_kPa":          _kpa(row, _C["PC"]),
            "Cc":              _fv(row, _C["Cc"]),
            "Cs":              _fv(row, _C["Cs"]),
            "Cv_cm2s":         cv_r * 1e-3 if cv_r else None,
            "k_cm_s":          kv_r * 1e-7 if kv_r else None,
            "qu_kPa":          _kpa(row, _C["Qu"]),
            "symbol_tcvn":     str(row[_C["symbol"]]).strip() or None,
            "description_vi":  str(row[_C["description"]]).strip() or None,
        })
    return records


def save_json(records: list[dict]) -> Path:
    out = {
        "_meta": {
            "source":    _XLS.name,
            "n_records": len(records),
            "boreholes": sorted({r["borehole_name"] for r in records}),
            "updated":   str(datetime.date.today()),
        },
        "records": records,
    }
    _JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return _JSON


def save_sqlite(records: list[dict], db_path: Path = _DB) -> int:
    con = sqlite3.connect(db_path)
    existing = [r[1] for r in con.execute("PRAGMA table_info(lab_tests)").fetchall()]
    if "gamma_sub_kNm3" not in existing:
        con.execute("ALTER TABLE lab_tests ADD COLUMN gamma_sub_kNm3 REAL")

    bh_ids: dict[str, int] = {}
    for bh in {r["borehole_name"] for r in records}:
        row = con.execute(
            "SELECT id FROM boreholes WHERE name=? AND zone_id=4", (bh,)
        ).fetchone()
        if row:
            bh_ids[bh] = row[0]
        else:
            print(f"  [WARN] '{bh}' khong tim thay trong zone_id=4")

    for bh_id in bh_ids.values():
        con.execute("DELETE FROM lab_tests WHERE borehole_id=?", (bh_id,))

    n = 0
    for rec in records:
        bh_id = bh_ids.get(rec["borehole_name"])
        if not bh_id:
            continue
        con.execute("""
            INSERT OR REPLACE INTO lab_tests (
                borehole_id, sample_id, depth_from_m, depth_to_m,
                w_pct, gamma_kNm3, gamma_dry_kNm3, gamma_sub_kNm3,
                Gs, e0, n_pct, Sr_pct, wL_pct, wP_pct, Ip, IS_liq,
                c_kPa, phi_deg, a12_cm2kgf, E_kPa, Cc, Cs,
                Cu_UU_kPa, phi_UU_deg,
                c_CU_kPa, phi_CU_deg, c_CU_eff_kPa, phi_CU_eff_deg,
                PC_kPa, Cv_cm2s, k_cm_s, qu_kPa,
                symbol_tcvn, description_vi
            ) VALUES (
                :bh_id, :sample_id, :depth_from_m, :depth_to_m,
                :w_pct, :gamma_kNm3, :gamma_dry_kNm3, :gamma_sub_kNm3,
                :Gs, :e0, :n_pct, :Sr_pct, :wL_pct, :wP_pct, :Ip, :IS_liq,
                :c_kPa, :phi_deg, :a12_cm2kgf, :E_kPa, :Cc, :Cs,
                :Cu_UU_kPa, :phi_UU_deg,
                :c_CU_kPa, :phi_CU_deg, :c_CU_eff_kPa, :phi_CU_eff_deg,
                :PC_kPa, :Cv_cm2s, :k_cm_s, :qu_kPa,
                :symbol_tcvn, :description_vi
            )
        """, {**rec, "bh_id": bh_id})
        n += 1

    con.commit()
    con.close()
    return n


if __name__ == "__main__":
    print(f"Doc: {_XLS.name}")
    recs = parse_xls()
    print(f"  -> {len(recs)} mau / {len({r['borehole_name'] for r in recs})} HK")
    print(f"  Cc:{sum(1 for r in recs if r['Cc'])}  PC:{sum(1 for r in recs if r['PC_kPa'])}  UU:{sum(1 for r in recs if r['Cu_UU_kPa'])}")
    jpath = save_json(recs)
    print(f"JSON -> {jpath.name}")
    n = save_sqlite(recs)
    print(f"SQLite -> {n} dong lab_tests")
    print("Xong.")
