# -*- coding: utf-8 -*-
"""Lưu kết quả tính móng trụ CDM — LK2 vào SQLite (LOCAL + PROJECT) + JSON snapshot.

Bảng (tiền tố lk2_):
  - lk2_settlement_summary   : tóm tắt Sblock/Sc/S_total + thông số khối
  - lk2_settlement_sublayers : chi tiết từng phân tố (σvz, Δσ, nhánh OC/NC, Sc)
  - lk2_time_history         : lún cố kết theo thời gian (Tv, Uv, St, residual)
  - lk2_bearing              : sức chịu tải cọc (Nvl/Ndn/AIT/Pcol)
  - lk2_concrete_check       : kiểm toán lớp bê tông C10 (Mtt/Vtt/Vr/Mr)

Tuân §64 rule 8: create_table idempotent, INSERT OR REPLACE, lưu CẢ LOCAL + PROJECT.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdm_lk2_calc import (  # noqa: E402
    compute_concrete_check, compute_lk2, compute_sct, compute_time_history,
    load_lk2_dataset,
)

_ROOT = Path(__file__).resolve().parent.parent
_JSON = _ROOT / "data" / "lk2_cdm_settlement.json"
_SNAPSHOT = _ROOT / "data" / "lk2_results_snapshot.json"
_DBS = [
    Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite"),
    _ROOT / "data" / "TTHC.sqlite",
]
_BH = "LK2"


def create_tables(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS lk2_settlement_summary (
            bh_name TEXT PRIMARY KEY, D_m REAL, S_m REAL, pattern INTEGER,
            quck REAL, a_ratio REAL, Ecol REAL, Eeq REAL, L_pile_m REAL,
            P_fill REAL, Sblock_cm REAL, Sc_cm REAL, S_total_cm REAL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP);

        CREATE TABLE IF NOT EXISTS lk2_settlement_sublayers (
            bh_name TEXT, idx INTEGER, h_m REAL, z_bot_elev_m REAL,
            in_block_m REAL, sigma_vz REAL, dsigma REAL, sigma_pz REAL,
            branch TEXT, Sc_cm REAL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (bh_name, idx));

        CREATE TABLE IF NOT EXISTS lk2_time_history (
            bh_name TEXT, year REAL, Tv REAL, Uv REAL, St_cm REAL, residual_cm REAL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (bh_name, year));

        CREATE TABLE IF NOT EXISTS lk2_bearing (
            bh_name TEXT PRIMARY KEY, Ap REAL, Etd REAL, Cu_soil REAL,
            N_load REAL, Nvl REAL, Ndn REAL, Nc REAL, qp REAL, ratio_Nc_N REAL,
            ok_capacity INTEGER, sigma_col REAL, Pcol REAL,
            Qult_col_AIT REAL, Qult_soil_AIT REAL, Qa_soil REAL, ok_AIT INTEGER,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP);

        CREATE TABLE IF NOT EXISTS lk2_concrete_check (
            bh_name TEXT PRIMARY KEY, dv_m REAL, Mtt REAL, Vtt REAL,
            sigma_flex_MPa REAL, Vr REAL, Mr REAL, ok_shear INTEGER, ok_moment INTEGER,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """
    )
    con.commit()


def save_to_db(con: sqlite3.Connection, res, sct, th, cc, inp) -> None:
    create_tables(con)
    cur = con.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO lk2_settlement_summary "
        "(bh_name,D_m,S_m,pattern,quck,a_ratio,Ecol,Eeq,L_pile_m,P_fill,"
        "Sblock_cm,Sc_cm,S_total_cm,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        (_BH, inp.D_m, inp.S_m, inp.pattern, inp.quck, res.a_ratio, res.Ecol, res.Eeq,
         res.L_pile, inp.P_fill, res.Sblock_m * 100, res.Sc_m * 100, res.S_total_m * 100),
    )
    cur.execute("DELETE FROM lk2_settlement_sublayers WHERE bh_name=?", (_BH,))
    for s in res.sublayers:
        cur.execute(
            "INSERT OR REPLACE INTO lk2_settlement_sublayers "
            "(bh_name,idx,h_m,z_bot_elev_m,in_block_m,sigma_vz,dsigma,sigma_pz,branch,Sc_cm) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (_BH, s.idx, s.h, s.z_bot_elev, s.in_block_thickness, s.sigma_vz,
             s.dsigma, s.sigma_pz, s.branch, s.Sc_m * 100),
        )
    cur.execute("DELETE FROM lk2_time_history WHERE bh_name=?", (_BH,))
    for i, yr in enumerate(th.years):
        cur.execute(
            "INSERT OR REPLACE INTO lk2_time_history (bh_name,year,Tv,Uv,St_cm,residual_cm) "
            "VALUES (?,?,?,?,?,?)",
            (_BH, yr, th.Tv[i], th.Uv[i], th.St_cm[i], th.residual_cm[i]),
        )
    cur.execute(
        "INSERT OR REPLACE INTO lk2_bearing "
        "(bh_name,Ap,Etd,Cu_soil,N_load,Nvl,Ndn,Nc,qp,ratio_Nc_N,ok_capacity,"
        "sigma_col,Pcol,Qult_col_AIT,Qult_soil_AIT,Qa_soil,ok_AIT,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        (_BH, sct.Ap, sct.Etd, sct.Cu_soil, sct.N_load, sct.Nvl, sct.Ndn, sct.Nc,
         sct.qp, sct.ratio_Nc_N, int(sct.ok_capacity), sct.sigma_col, sct.Pcol,
         sct.Qult_col_AIT, sct.Qult_soil_AIT, sct.Qa_soil, int(sct.ok_AIT)),
    )
    cur.execute(
        "INSERT OR REPLACE INTO lk2_concrete_check "
        "(bh_name,dv_m,Mtt,Vtt,sigma_flex_MPa,Vr,Mr,ok_shear,ok_moment,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        (_BH, cc.dv_m, cc.Mtt, cc.Vtt, cc.sigma_flex_MPa, cc.Vr, cc.Mr,
         int(cc.ok_shear), int(cc.ok_moment)),
    )
    con.commit()


def run() -> None:
    inp, geo = load_lk2_dataset()
    full = json.loads(_JSON.read_text(encoding="utf-8"))
    res = compute_lk2(inp, geo)
    sct = compute_sct(inp, geo, res.Ecol, res.a_ratio)
    cvt, tvu, gt = full["cv_table"], full["tvu_table"], full["golden_time"]
    th = compute_time_history(res, cvt["pressure_kPa"], cvt["Cv"], tvu["Tv"], tvu["U_pct"],
                              gt["years"], allowable_cm=gt["allowable_cm"], design_time_idx=1)
    cc = compute_concrete_check(inp.D_m, inp.S_m, inp.q_total,
                                full["scalars"].get("dv_concrete_m", 0.0))

    # JSON snapshot
    snap = {
        "_meta": {"bh": _BH, "source": full["_meta"]["source"], "rule": "engine cdm_lk2_calc"},
        "summary": {"Sblock_cm": res.Sblock_m * 100, "Sc_cm": res.Sc_m * 100,
                    "S_total_cm": res.S_total_m * 100, "Eeq": res.Eeq, "a_ratio": res.a_ratio},
        "bearing": {"N": sct.N_load, "Nc": sct.Nc, "ratio": sct.ratio_Nc_N,
                    "Pcol": sct.Pcol, "Qa_soil": sct.Qa_soil, "ok": sct.ok_AIT},
        "time": {"years": th.years, "St_cm": th.St_cm, "residual_cm": th.residual_cm,
                 "residual_check_cm": th.residual_check_cm, "ok": th.ok},
        "concrete": {"Mtt": cc.Mtt, "Vtt": cc.Vtt, "Vr": cc.Vr, "Mr": cc.Mr},
    }
    _SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON snapshot -> {_SNAPSHOT}")

    for db in _DBS:
        if not db.parent.exists():
            print(f"  bo qua (khong co thu muc): {db}")
            continue
        con = sqlite3.connect(str(db))
        try:
            save_to_db(con, res, sct, th, cc, inp)
            n = con.execute("SELECT COUNT(*) FROM lk2_settlement_sublayers WHERE bh_name=?", (_BH,)).fetchone()[0]
            print(f"  luu OK: {db}  ({n} sublayers, S_total={res.S_total_m*100:.2f}cm)")
        finally:
            con.close()


if __name__ == "__main__":
    run()
