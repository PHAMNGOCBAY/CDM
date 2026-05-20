"""
verify_ke_lab.py — So sánh lab_tests SQLite KE với file Excel KQTN gốc.

Nguồn: G:/.../DIA CHAT/3. KÈ (CÔNG VIÊN)/BOKE-003. KQTN_260512 CV-TTHC HCM. KQTN.xls

Sheet 'M' chứa BẢNG TỔNG HỢP KQTN. Header phức tạp 4 dòng (row 5-8), data từ row 12.

Mapping cột Excel:
  col1: HK | col2: sample | col3-4: depth from-to (m)
  col17: w% | col18: γ_natural (g/cm³ → ×9.81 kN/m³)
  col22: e0 | col25-28: LL/PL/Ip/IS_liq
  col43: c (kg/cm² → ×98.07 kPa) | col44: φ (deg)
  col62: PC (kg/cm² → ×98.07 kPa)
  col63: Cc | col64: Cs | col65: Cv (cm²/s ×10⁻³)
  col66: kv (cm/s ×10⁻⁷)
  col68: symbol TCVN

So sánh với SQLite lab_tests (đơn vị: gamma kN/m³, c kPa, PC kPa, Cv cm²/s, k cm/s).
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
DB    = _ROOT / "data" / "TTHC.sqlite"
XLS   = _ROOT / "DIA CHAT" / "3. KÈ (CÔNG VIÊN)" / "BOKE-003. KQTN_260512 CV-TTHC HCM. KQTN.xls"

# Hệ số đổi đơn vị
KG_CM2_TO_KPA = 98.0665     # 1 kg/cm² = 98.0665 kPa
G_CM3_TO_KNM3 = 9.81        # 1 g/cm³ = 9.81 kN/m³

# Cột Excel cần lấy
COLS = {
    "bh":          1,
    "sample":      2,
    "depth_from":  3,
    "depth_to":    4,
    "w_pct":       17,
    "gamma_gcm3":  18,
    "e0":          22,
    "wL_pct":      25,
    "wP_pct":      26,
    "Ip":          27,
    "IS":          28,
    "c_kgcm2":     43,
    "phi_deg":     44,
    "PC_kgcm2":    62,
    "Cc":          63,
    "Cs":          64,
    "Cv_e3":       65,    # cm²/s × 10⁻³ → raw value × 1e-3
    "kv_e7":       66,    # cm/s × 10⁻⁷ → raw value × 1e-7
    "symbol":      68,
}

TOL_RELATIVE = 0.05  # 5% tolerance


def load_excel() -> list[dict]:
    """Đọc Excel, return list of dict (1 sample = 1 dict)."""
    df = pd.read_excel(XLS, sheet_name="M", header=None)
    samples = []
    for i in range(12, len(df)):  # data từ row 12
        row = df.iloc[i]
        bh = row[COLS["bh"]]
        sample = row[COLS["sample"]]
        if pd.isna(bh) or pd.isna(sample):
            continue
        # Bỏ qua summary rows
        bh_str = str(bh).strip()
        if not bh_str.startswith("HK"):
            continue
        rec = {"row": i, "bh_xls": bh_str, "sample": str(sample).strip()}
        for k, col in COLS.items():
            if k in ("bh", "sample"):
                continue
            v = row[col]
            rec[k] = None if pd.isna(v) else v
        # Đổi đơn vị → so sánh với SQLite
        rec["gamma_kNm3_xls"] = rec["gamma_gcm3"] * G_CM3_TO_KNM3 if rec["gamma_gcm3"] else None
        rec["c_kPa_xls"]      = rec["c_kgcm2"] * KG_CM2_TO_KPA if rec["c_kgcm2"] else None
        rec["PC_kPa_xls"]     = rec["PC_kgcm2"] * KG_CM2_TO_KPA if rec["PC_kgcm2"] else None
        rec["Cv_cm2s_xls"]    = rec["Cv_e3"] * 1e-3 if rec["Cv_e3"] else None
        rec["k_cms_xls"]      = rec["kv_e7"] * 1e-7 if rec["kv_e7"] else None
        samples.append(rec)
    return samples


def load_sqlite() -> dict[tuple, dict]:
    """Index by (bh_name, depth_from_int) — depth là unique trong 1 HK.
    Sample name có thể bị duplicate (UD19→UD19A/B) nên không dùng làm key."""
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT b.name AS bh, lt.sample_id, lt.depth_from_m, lt.depth_to_m,
               lt.w_pct, lt.gamma_kNm3, lt.e0,
               lt.wL_pct, lt.wP_pct, lt.Ip,
               lt.c_kPa, lt.phi_deg,
               lt.Cc, lt.Cs, lt.PC_kPa, lt.Cv_cm2s, lt.k_cm_s,
               lt.symbol_tcvn
        FROM lab_tests lt
        JOIN boreholes b ON lt.borehole_id = b.id
        JOIN zones z ON b.zone_id = z.id
        WHERE z.code = 'KE'
        ORDER BY b.name, lt.depth_from_m
    """).fetchall()
    con.close()
    return {(r["bh"], round(r["depth_from_m"], 1)): dict(r) for r in rows}


def _close(a, b, tol=TOL_RELATIVE) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if abs(b) < 1e-6:
        return abs(a) < 1e-6
    return abs(a - b) / abs(b) <= tol


def compare() -> None:
    xls = load_excel()
    sql = load_sqlite()
    print(f"Excel KQTN: {len(xls)} mẫu (KE-HKx)")
    print(f"SQLite lab_tests (KE): {len(sql)} mẫu")
    print()

    matches  = 0
    mismatches: list[dict] = []
    only_xls = []
    only_sql = set(sql.keys())

    for x in xls:
        key = (f"KE-{x['bh_xls']}", round(x["depth_from"], 1))
        if key not in sql:
            only_xls.append((key, x["depth_from"], x["depth_to"]))
            continue
        only_sql.discard(key)
        s = sql[key]
        diffs = []
        # Compare fields
        for fname, x_val, s_val in [
            ("depth_from", x["depth_from"], s["depth_from_m"]),
            ("depth_to",   x["depth_to"],   s["depth_to_m"]),
            ("w%",         x["w_pct"],      s["w_pct"]),
            ("γ kN/m³",   x["gamma_kNm3_xls"], s["gamma_kNm3"]),
            ("e0",         x["e0"],         s["e0"]),
            ("LL%",        x["wL_pct"],     s["wL_pct"]),
            ("PL%",        x["wP_pct"],     s["wP_pct"]),
            ("Ip",         x["Ip"],         s["Ip"]),
            ("c kPa",      x["c_kPa_xls"],  s["c_kPa"]),
            ("φ°",        x["phi_deg"],    s["phi_deg"]),
            ("Cc",         x["Cc"],         s["Cc"]),
            ("Cs",         x["Cs"],         s["Cs"]),
            ("PC kPa",     x["PC_kPa_xls"], s["PC_kPa"]),
            ("Cv cm²/s",  x["Cv_cm2s_xls"], s["Cv_cm2s"]),
            ("k cm/s",     x["k_cms_xls"],  s["k_cm_s"]),
        ]:
            if not _close(x_val, s_val):
                diffs.append((fname, x_val, s_val))
        if diffs:
            mismatches.append({"key": key, "diffs": diffs})
        else:
            matches += 1

    print(f"Khớp hoàn toàn:    {matches}/{len(xls)}")
    print(f"Khớp 1 phần (Δ):   {len(mismatches)}")
    print(f"Có trong XLS, không có SQLite: {len(only_xls)}")
    print(f"Có trong SQLite, không có XLS: {len(only_sql)}")
    print()

    if only_xls:
        print("== Mẫu trong XLS thiếu trong SQLite ==")
        for key, d_f, d_t in only_xls[:10]:
            print(f"  {key}  depth {d_f}-{d_t}m")
        if len(only_xls) > 10:
            print(f"  ... và {len(only_xls)-10} mẫu khác")
        print()

    if only_sql:
        print("== Mẫu trong SQLite không khớp XLS ==")
        for key in sorted(only_sql)[:10]:
            print(f"  {key}")
        if len(only_sql) > 10:
            print(f"  ... và {len(only_sql)-10} mẫu khác")
        print()

    if mismatches:
        print(f"== {len(mismatches)} mẫu có sai lệch >5% ==")
        for m in mismatches[:15]:
            print(f"\n  {m['key']}:")
            for fname, x_v, s_v in m["diffs"]:
                x_s = f"{x_v:.4g}" if isinstance(x_v, (int, float)) else str(x_v)
                s_s = f"{s_v:.4g}" if isinstance(s_v, (int, float)) else str(s_v)
                print(f"    {fname:12s}  XLS={x_s:>12s}  SQL={s_s:>12s}")
        if len(mismatches) > 15:
            print(f"\n  ... và {len(mismatches)-15} mẫu khác")


if __name__ == "__main__":
    compare()
