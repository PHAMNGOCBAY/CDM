# -*- coding: utf-8 -*-
"""Bộ chỉ tiêu cơ lý các lớp đất theo BCL (Ban chiến lược) — TTHC Thủ Thiêm.

Nguồn: bảng "Project TTHC tpHCM — Thu Thiem" do BCL cung cấp (ảnh hồ sơ).
Đây là bộ thông số THỐNG NHẤT (single source) để tính toán cho các hố khoan bờ kè.

Lưu: SQLite `bcl_soil_params` (LOCAL + PROJECT) + JSON data/bcl_soil_params.json.

Quy ước:
  - Cv nhập theo bảng (×10⁻⁴ cm²/s) → lưu Cv_cm2s = giá trị × 1e-4.
  - Lớp CÁT / lớp chặt: E_kPa = α_sand · N_spt (α=2000 kPa, TCVN) để tính lún đàn hồi.
  - Su (VST) lớp sét: Su = su_a + su_b · Z (kN/m²), Z = độ sâu (m).
  - PC (áp lực tiền cố kết) BCL không cho → coi sét NC (PC = σ'v0) khi tính cố kết.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
_JSON = _ROOT / "data" / "bcl_soil_params.json"
_DBS = [Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite"), _ROOT / "data" / "TTHC.sqlite"]

ALPHA_SAND = 2000.0   # Es = α·N (kPa)
SOURCE = "BCL (Ban chiến lược) — TTHC Thủ Thiêm"


def _E_from_N(N):
    return ALPHA_SAND * N if N else None


# Bộ chỉ tiêu BCL theo ký hiệu lớp địa tầng (map cột bảng BCL → symbol dự án)
# Cv_raw = giá trị bảng (×10⁻⁴ cm²/s)
BCL_PARAMS = {
    # symbol: (soil_type, N, gamma, e0, Cc, Cs, Cv_raw, PI, Wn, LL, PL, su_a, su_b, desc)
    "F":  ("Sand", 3,  17.5, 0.75, None, None, 150.0, 5.0,  None, None, None, None, None, "Cát san lấp (N=2-5)"),
    "1":  ("Clay", 1,  15.0, 2.16, 0.83, 0.11, 5.0,   37.0, 80.0, 72.0, 35.0, 5.0,  0.7,  "Sét bụi rất mềm (N=0-1)"),
    "1b": ("Clay", 4,  17.5, 1.22, 0.42, 0.07, 8.0,   22.0, 43.0, 49.0, 27.0, 5.0,  0.7,  "Sét mềm-vừa (N=3-4)"),
    "2a": ("Sand", 10, 18.5, 0.75, None, None, 150.0, 8.0,  None, None, None, None, None, "Cát pha rời-vừa (N=7-15)"),
    "2b": ("Sand", 10, 18.5, 0.75, None, None, 150.0, 8.0,  None, None, None, None, None, "Cát pha rời-vừa (N=7-15)"),
    "2c": ("Clay", 4,  18.0, 1.10, 0.35, 0.04, 4.0,   24.0, 39.6, 48.8, 24.6, 5.0,  0.7,  "TK 2b — sét rất mềm-mềm (N=4-5)"),
    "3":  ("Clay", 10, 18.3, 1.01, 0.33, 0.04, 4.0,   19.0, 35.0, 42.0, 23.0, 5.0,  0.7,  "Sét pha vừa (N=8-10)"),
    "4":  ("Sand", 20, 18.3, 0.75, None, None, 150.0, 5.0,  None, None, None, None, None, "Cát pha chặt vừa (N=20-25)"),
    "5":  ("Clay", 25, 20.2, 0.64, 0.00, 0.00, 4.0,   21.0, 22.0, 42.0, 22.0, None, None, "Sét cứng (N=20-35)"),
    "6":  ("Sand", 30, 18.2, 0.54, None, None, 150.0, 5.0,  None, None, None, None, None, "Cát chặt (N=30-40)"),
    "7":  ("Sand", 40, 17.0, 0.75, None, None, 150.0, 5.0,  None, None, None, None, None, "Cát rất chặt (N=40-50+)"),
}

_COLS = ["soil_type", "N_spt", "gamma_kNm3", "e0", "Cc", "Cs", "Cv_raw_e4", "PI",
         "Wn_pct", "LL_pct", "PL_pct", "su_a", "su_b", "desc"]


def _lab_pc_by_symbol(zone: str = "KE", db_path: Optional[Path] = None) -> dict:
    """P_c trung bình theo lớp từ THÍ NGHIỆM (lab) — bù cho BCL thiếu P_c."""
    try:
        from soil_param_stats import representative_params
        rep = representative_params(db_path)
        return {sym: p.get("PC_kPa") for (z, sym), p in rep.items()
                if z == zone and p.get("PC_kPa")}
    except Exception:
        return {}


def get_bcl_params(fill_pc_from_lab: bool = True, pc_zone: str = "KE",
                   db_path: Optional[Path] = None) -> dict:
    """Trả về dict {symbol: {field: value}} — gồm Cv_cm2s, E_kPa đã suy ra.

    fill_pc_from_lab=True: BCL thiếu P_c → lấy P_c TRUNG BÌNH từ thí nghiệm (lab) theo lớp.
    """
    lab_pc = _lab_pc_by_symbol(pc_zone, db_path) if fill_pc_from_lab else {}
    out = {}
    for sym, vals in BCL_PARAMS.items():
        d = dict(zip(_COLS, vals))
        d["Cv_cm2s"] = (d["Cv_raw_e4"] * 1e-4) if d["Cv_raw_e4"] is not None else None
        d["E_kPa"] = _E_from_N(d["N_spt"]) if d["soil_type"] == "Sand" or (d["e0"] and d["e0"] < 1) else None
        # P_c: BCL không cho → lấy từ thí nghiệm (lab). Không có → None (coi NC).
        d["PC_kPa"] = lab_pc.get(sym)
        d["PC_source"] = "lab" if lab_pc.get(sym) else "NC (σ'v0)"
        out[sym] = d
    return out


def create_table(con: sqlite3.Connection) -> None:
    con.execute(
        "CREATE TABLE IF NOT EXISTS bcl_soil_params ("
        "symbol TEXT PRIMARY KEY, soil_type TEXT, N_spt REAL, gamma_kNm3 REAL, e0 REAL, "
        "Cc REAL, Cs REAL, Cv_cm2s REAL, E_kPa REAL, PI REAL, Wn_pct REAL, LL_pct REAL, "
        "PL_pct REAL, su_a REAL, su_b REAL, PC_kPa REAL, desc TEXT, source TEXT, "
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    con.commit()


def save() -> Path:
    params = get_bcl_params()
    for db in _DBS:
        if not db.parent.exists():
            continue
        con = sqlite3.connect(str(db))
        try:
            create_table(con)
            for sym, d in params.items():
                con.execute(
                    "INSERT OR REPLACE INTO bcl_soil_params "
                    "(symbol,soil_type,N_spt,gamma_kNm3,e0,Cc,Cs,Cv_cm2s,E_kPa,PI,Wn_pct,"
                    "LL_pct,PL_pct,su_a,su_b,PC_kPa,desc,source,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                    (sym, d["soil_type"], d["N_spt"], d["gamma_kNm3"], d["e0"], d["Cc"], d["Cs"],
                     d["Cv_cm2s"], d["E_kPa"], d["PI"], d["Wn_pct"], d["LL_pct"], d["PL_pct"],
                     d["su_a"], d["su_b"], d["PC_kPa"], d["desc"], SOURCE))
            con.commit()
        finally:
            con.close()
    data = {"_meta": {"source": SOURCE, "alpha_sand_kPa": ALPHA_SAND,
                      "note": "Cv lưu cm²/s (=bảng×1e-4); E_kPa=α·N cho cát/lớp chặt; PC=None→NC"},
            "params": params}
    _JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return _JSON


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    p = save()
    print(f"Da luu BCL params -> {p}")
    print(f"{'Lop':<5}{'loai':>6}{'N':>4}{'gama':>7}{'e0':>7}{'Cc':>7}{'Cs':>7}{'Cv(cm2/s)':>12}{'E(kPa)':>9}")
    for s, d in get_bcl_params().items():
        def f(v, n=2): return f"{v:.{n}f}" if v is not None else "—"
        print(f"{s:<5}{d['soil_type']:>6}{int(d['N_spt']):>4}{f(d['gamma_kNm3']):>7}{f(d['e0'],3):>7}"
              f"{f(d['Cc'],3):>7}{f(d['Cs'],4):>7}{f(d['Cv_cm2s'],6):>12}{f(d['E_kPa'],0):>9}")
