"""§72 Task 8 — Dự báo lún khi KHÔNG xử lý (no treatment).

Cho mỗi HK:
- S_inf_cm    = tổng lún cố kết theo TCCS 41 Phụ lục C (Cc/Cs/e0 lab + σ'v + Δσ).
                Tích phân toàn bộ chiều dày bùn (từ đỉnh tới đáy lớp yếu).
- S_15y_cm    = S_inf × U(15 năm) với U từ Terzaghi 1D, Cv lab, H_drain = H_soft/2
                (cố kết 2 mặt cho trường hợp không xử lý — đáy bùn thường tiếp giáp
                lớp cát chặt thoát nước).
- U_15y       = 0..1, mức độ cố kết tại 15 năm.

Lưu bảng `cdm_zone_no_treat_predict` (PK: zone_code, bh_name).

Engine source: scripts/settlement_calc.py (`calc_settlement_from_db` + `calc_time_series`).
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from settlement_calc import (  # type: ignore
    calc_settlement_from_db,
    calc_time_series,
)
from qtt_cdm_analysis import (  # type: ignore
    ZONE_DEFS,
    get_zone_selected_hks,
    soft_profile_from_db,
    get_qtt_load_q,
    get_qtt_fill_total_thickness,
    _db_path,
)
import math


def _bh_has_cc(bh_name: str, db_path: Path) -> bool:
    """True nếu HK có ≥1 mẫu Cc trong lab_tests."""
    with sqlite3.connect(db_path) as con:
        n = con.execute(
            "SELECT COUNT(*) FROM lab_tests lt "
            "JOIN boreholes b ON lt.borehole_id = b.id "
            "WHERE b.name=? AND lt.Cc IS NOT NULL AND lt.Cc > 0",
            (bh_name,),
        ).fetchone()[0]
    return n > 0


def _nearest_cc_in_zone(bh_E: float, bh_N: float,
                          prefix: str, db_path: Path) -> tuple:
    """Tìm HK gần nhất trong CÙNG zone (theo prefix) có ≥1 mẫu Cc."""
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT b.name, b.x_coord_m AS N, b.y_coord_m AS E "
            "FROM boreholes b "
            "JOIN lab_tests lt ON lt.borehole_id = b.id "
            "WHERE b.name LIKE ? AND lt.Cc IS NOT NULL AND lt.Cc > 0 "
            "  AND b.x_coord_m IS NOT NULL AND b.y_coord_m IS NOT NULL "
            "GROUP BY b.id",
            (prefix,),
        ).fetchall()
    best = None; best_d = float("inf")
    for r in rows:
        if r["E"] is None or r["N"] is None:
            continue
        d = math.hypot(float(r["E"]) - bh_E, float(r["N"]) - bh_N)
        if d < best_d:
            best_d = d; best = r["name"]
    return best, best_d


def create_table(db_path: Path | None = None) -> None:
    db = db_path or _db_path()
    with sqlite3.connect(db) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS cdm_zone_no_treat_predict (
                zone_code TEXT NOT NULL,
                bh_name TEXT NOT NULL,
                selected INTEGER DEFAULT 1,
                H_soft_m REAL,
                q_kPa REAL,
                clay_top_m REAL,
                S_inf_cm REAL,
                S_15y_cm REAL,
                U_15y REAL,
                Cv_avg_m2_year REAL,
                method TEXT,
                note TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (zone_code, bh_name)
            )
        """)
        # §72 Task U — ALTER TABLE thêm cột PA2 (đắp 0.0 → TK)
        # §72 Task W — ALTER TABLE thêm cột PA3a/b/c (TK_max/TK_avg/TN_max của zone)
        for col_sql in (
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN H_fill_pa2_m REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN q_pa2_kPa REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S_inf_pa2_cm REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S_15y_pa2_cm REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN U_15y_pa2 REAL",
            # PA3a — TK_max của zone
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN q_pa3a_kPa REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S1_pa3a_cm REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S2_pa3a_cm REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S_total_pa3a_cm REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S_15y_pa3a_cm REAL",
            # PA3b — TK_avg
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN q_pa3b_kPa REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S1_pa3b_cm REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S2_pa3b_cm REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S_total_pa3b_cm REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S_15y_pa3b_cm REAL",
            # PA3c — TN_max của zone
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN q_pa3c_kPa REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S1_pa3c_cm REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S2_pa3c_cm REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S_total_pa3c_cm REAL",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN S_15y_pa3c_cm REAL",
            # §72 Task Y — Mượn Cc khi HK không có TN nén cố kết
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN cc_source TEXT",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN cc_borrowed INTEGER",
            "ALTER TABLE cdm_zone_no_treat_predict ADD COLUMN cc_dist_m REAL",
        ):
            try:
                con.execute(col_sql)
            except sqlite3.OperationalError:
                pass  # column exists
        con.commit()


def predict_zone(zone_code: str,
                  t_years: float = 15.0,
                  db_path: Path | None = None) -> int:
    """Tính S_inf + S(15y) cho TẤT CẢ HK trong zone, lưu DB."""
    db = db_path or _db_path()
    create_table(db)
    if zone_code not in ZONE_DEFS:
        return 0

    q_kPa = get_qtt_load_q(db)
    fill_h = get_qtt_fill_total_thickness(db)
    hks = get_zone_selected_hks(zone_code, db_path=db, include_unselected=True)
    n_written = 0

    # §72 Issue V #1 fix — γ_fill TB từ tvtk_fill_composition (không hardcode 18)
    with sqlite3.connect(db) as _con_g:
        comp_rows = _con_g.execute(
            "SELECT h_m, gamma_kNm3 FROM tvtk_fill_composition "
            "WHERE h_m > 0 AND gamma_kNm3 > 0"
        ).fetchall()
    if comp_rows:
        _tot_h = sum(r[0] for r in comp_rows)
        GAMMA_FILL = sum(r[0] * r[1] for r in comp_rows) / _tot_h
    else:
        GAMMA_FILL = 18.0  # fallback nếu composition trống

    # §72 Task W — Zone-level stats cho PA3
    with sqlite3.connect(db) as _con_z:
        # TK max/avg từ grid points (QTT) hoặc design global
        try:
            r = _con_z.execute(
                "SELECT MAX(elev_des_m), AVG(elev_des_m), MIN(elev_des_m) "
                "FROM qtt_elevation_points WHERE elev_des_m IS NOT NULL"
            ).fetchone()
            TK_max_zone = float(r[0]) if r and r[0] else 2.70
            TK_avg_zone = float(r[1]) if r and r[1] else 2.70
        except sqlite3.OperationalError:
            TK_max_zone = 2.70; TK_avg_zone = 2.70
        # TN max/avg theo zone (qua prefix HK)
        prefix = ZONE_DEFS[zone_code]["bh_prefix"] + "%"
        r = _con_z.execute(
            "SELECT MAX(elevation_m), AVG(elevation_m) FROM boreholes "
            "WHERE name LIKE ?", (prefix,),
        ).fetchone()
        TN_max_zone = float(r[0]) if r and r[0] else 0.0
        TN_avg_zone = float(r[1]) if r and r[1] else 0.0

    # GAMMA_FILL đã set ở trên từ tvtk_fill_composition — KHÔNG hardcode lại

    with sqlite3.connect(db) as con:
        # design elev
        row = con.execute(
            "SELECT settlement_design_elev_m FROM tvtk_cdm_config WHERE id=1"
        ).fetchone()
        design_elev = float(row[0]) if row and row[0] is not None else 2.70

        prefix = ZONE_DEFS[zone_code]["bh_prefix"] + "%"
        for hk in hks:
            name = hk["bh_name"]
            sel = int(hk.get("selected", 1) or 0)
            nat = float(hk["nat"]) if hk.get("nat") is not None else 0.0
            E = float(hk["E"]) if hk.get("E") is not None else None
            N = float(hk["N"]) if hk.get("N") is not None else None

            clay_top, H_soft = soft_profile_from_db(name, db)
            if clay_top is None or H_soft <= 0:
                con.execute("""
                    INSERT OR REPLACE INTO cdm_zone_no_treat_predict
                    (zone_code, bh_name, selected, H_soft_m, q_kPa,
                     S_inf_cm, S_15y_cm, U_15y, method, note, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)
                """, (zone_code, name, sel, None, q_kPa,
                       None, None, None, "no_soft", "Không có lớp bùn"))
                n_written += 1
                continue

            # §72 Task Y — Nếu HK không có Cc, mượn từ HK gần nhất cùng zone
            # (§15 Số liệu giả định — lấy từ HK gần nhất)
            cc_source = name
            cc_borrowed = 0
            cc_dist = 0.0
            calc_bh = name  # HK để gọi calc_settlement_from_db
            if not _bh_has_cc(name, db) and E is not None and N is not None:
                nearest, dist = _nearest_cc_in_zone(E, N, prefix, db)
                if nearest:
                    cc_source = nearest
                    cc_borrowed = 1
                    cc_dist = round(dist, 0)
                    calc_bh = nearest  # gọi engine với HK mượn (Cc/e0/PC từ đó)

            # PA1 — H_fill từ thiết kế (đắp từ TN tới design)
            H_fill_m = max(0.0, design_elev - nat) + fill_h
            # §72 Task U — PA2: đất đắp 0.0 → TK, tải gây lún = γ × TN
            H_fill_pa2_m = max(0.0, nat - 0.0)
            # §72 Issue V #1: dùng γ_TB từ composition (không hardcode)
            q_pa2_kPa = round(GAMMA_FILL * H_fill_pa2_m, 2)

            try:
                # PA1
                base = calc_settlement_from_db(calc_bh, H_fill_m=H_fill_m,
                                                stress_scale=1.0)
                S_inf_cm = float(base.get("S_total_cm") or 0.0)
                # Cv TB từ lab (cm²/s) → m²/year (×3155.7 = 86400 × 365.25 / 1e4)
                cv_cm2s = con.execute("""
                    SELECT AVG(lt.Cv_cm2s) FROM lab_tests lt
                    JOIN boreholes b ON lt.borehole_id = b.id
                    WHERE b.name=? AND lt.Cv_cm2s IS NOT NULL AND lt.Cv_cm2s > 0
                """, (name,)).fetchone()[0]
                if cv_cm2s is None or cv_cm2s <= 0:
                    Cv = 1.0  # fallback bùn yếu
                else:
                    Cv = float(cv_cm2s) * 3155.7
                zone_params = {
                    "Cv_m2yr": Cv,
                    "Hdr_m": H_soft,
                    "drainage": "one_way",  # §72 Task X: đáy bùn thường kín, thoát 1 mặt
                }
                ts = calc_time_series(
                    S_total_cm=S_inf_cm,
                    method="no_treat",
                    zone_params=zone_params,
                    t_months_list=[t_years * 12.0],
                )
                S_15y_cm = float(ts[0]["S_cm"]) if ts else S_inf_cm
                U_15y = float(ts[0].get("U_pct", 100.0)) / 100.0 if ts else 1.0
                method = "Cc"
                note = ""
                # PA2 — re-run với H_fill_pa2_m (đắp từ 0.0 lên TN)
                if H_fill_pa2_m > 0.01:
                    base_pa2 = calc_settlement_from_db(
                        calc_bh, H_fill_m=H_fill_pa2_m, stress_scale=1.0)
                    S_inf_pa2_cm = float(base_pa2.get("S_total_cm") or 0.0)
                    ts_pa2 = calc_time_series(
                        S_total_cm=S_inf_pa2_cm,
                        method="no_treat",
                        zone_params=zone_params,
                        t_months_list=[t_years * 12.0],
                    )
                    S_15y_pa2_cm = float(ts_pa2[0]["S_cm"]) if ts_pa2 else S_inf_pa2_cm
                    U_15y_pa2 = (float(ts_pa2[0].get("U_pct", 100.0)) / 100.0
                                  if ts_pa2 else 1.0)
                else:
                    S_inf_pa2_cm = 0.0
                    S_15y_pa2_cm = 0.0
                    U_15y_pa2 = 0.0

                # §72 Task W — PA3a/b/c: dùng TK_max / TK_avg / TN_max của zone
                # Mỗi biến thể tính riêng H_fill (m fill chồng lên TN) → q × S1 + S2
                Es_sand = 20000.0  # kPa — đất cát/đắp đại diện cho S1
                S1_pa3 = {}; S2_pa3 = {}; S_tot_pa3 = {}; S_15y_pa3 = {}; q_pa3 = {}
                pa3_targets = {
                    "a": TK_max_zone,
                    "b": TK_avg_zone,
                    "c": TN_max_zone,
                }
                for key, target_elev in pa3_targets.items():
                    H_fill_pa3 = max(0.0, target_elev - nat)
                    q_v = round(GAMMA_FILL * H_fill_pa3, 2)
                    q_pa3[key] = q_v
                    if H_fill_pa3 < 0.01:
                        S1_pa3[key] = 0.0
                        S2_pa3[key] = 0.0
                        S_tot_pa3[key] = 0.0
                        S_15y_pa3[key] = 0.0
                        continue
                    # S1 = q × clay_top / Es_sand × 100 (cm) — lún tức thì lớp cát/đắp trên bùn
                    S1_v = q_v * (clay_top if clay_top else 0) / Es_sand * 100.0
                    # S2 = consolidation Terzaghi lớp bùn dưới tải q (qua calc_settlement_from_db)
                    try:
                        base_pa3 = calc_settlement_from_db(
                            calc_bh, H_fill_m=H_fill_pa3, stress_scale=1.0)
                        S2_v = float(base_pa3.get("S_total_cm") or 0.0)
                    except Exception:
                        S2_v = 0.0
                    S1_pa3[key] = round(S1_v, 2)
                    S2_pa3[key] = round(S2_v, 2)
                    S_tot_pa3[key] = round(S1_v + S2_v, 2)
                    # 15 năm: S1 tức thì + S2 × U(t)
                    ts_pa3 = calc_time_series(
                        S_total_cm=S2_v, method="no_treat",
                        zone_params=zone_params,
                        t_months_list=[t_years * 12.0],
                    )
                    S2_15y_v = float(ts_pa3[0]["S_cm"]) if ts_pa3 else S2_v
                    S_15y_pa3[key] = round(S1_v + S2_15y_v, 2)
            except Exception as e:
                S_inf_cm = None
                S_15y_cm = None
                U_15y = None
                Cv = None
                S_inf_pa2_cm = None
                S_15y_pa2_cm = None
                U_15y_pa2 = None
                S1_pa3 = {"a": None, "b": None, "c": None}
                S2_pa3 = {"a": None, "b": None, "c": None}
                S_tot_pa3 = {"a": None, "b": None, "c": None}
                S_15y_pa3 = {"a": None, "b": None, "c": None}
                q_pa3 = {"a": None, "b": None, "c": None}
                method = "ERR"
                note = f"{type(e).__name__}: {e}"

            con.execute("""
                INSERT OR REPLACE INTO cdm_zone_no_treat_predict
                (zone_code, bh_name, selected, H_soft_m, q_kPa, clay_top_m,
                 S_inf_cm, S_15y_cm, U_15y, Cv_avg_m2_year, method, note,
                 H_fill_pa2_m, q_pa2_kPa, S_inf_pa2_cm, S_15y_pa2_cm, U_15y_pa2,
                 q_pa3a_kPa, S1_pa3a_cm, S2_pa3a_cm, S_total_pa3a_cm, S_15y_pa3a_cm,
                 q_pa3b_kPa, S1_pa3b_cm, S2_pa3b_cm, S_total_pa3b_cm, S_15y_pa3b_cm,
                 q_pa3c_kPa, S1_pa3c_cm, S2_pa3c_cm, S_total_pa3c_cm, S_15y_pa3c_cm,
                 cc_source, cc_borrowed, cc_dist_m,
                 updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,
                        ?,?,?,?,?,
                        ?,?,?,?,?,
                        ?,?,?,
                        CURRENT_TIMESTAMP)
            """, (
                zone_code, name, sel, H_soft, q_kPa, clay_top,
                round(S_inf_cm, 2) if S_inf_cm is not None else None,
                round(S_15y_cm, 2) if S_15y_cm is not None else None,
                round(U_15y, 3) if U_15y is not None else None,
                round(Cv, 4) if Cv is not None else None,
                method, note,
                round(H_fill_pa2_m, 2),
                q_pa2_kPa,
                round(S_inf_pa2_cm, 2) if S_inf_pa2_cm is not None else None,
                round(S_15y_pa2_cm, 2) if S_15y_pa2_cm is not None else None,
                round(U_15y_pa2, 3) if U_15y_pa2 is not None else None,
                q_pa3.get("a"), S1_pa3.get("a"), S2_pa3.get("a"),
                S_tot_pa3.get("a"), S_15y_pa3.get("a"),
                q_pa3.get("b"), S1_pa3.get("b"), S2_pa3.get("b"),
                S_tot_pa3.get("b"), S_15y_pa3.get("b"),
                q_pa3.get("c"), S1_pa3.get("c"), S2_pa3.get("c"),
                S_tot_pa3.get("c"), S_15y_pa3.get("c"),
                cc_source, cc_borrowed, cc_dist,
            ))
            n_written += 1
        con.commit()
    return n_written


if __name__ == "__main__":
    DBs = [
        Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite"),
        Path("data/TTHC.sqlite"),
    ]
    ZONES = ["QTT", "BXN", "NHC", "KE_park", "KE_levee"]
    for db in DBs:
        if not db.exists():
            print(f"SKIP {db}")
            continue
        print(f"DB: {db.parent.name}")
        for z in ZONES:
            n = predict_zone(z, db_path=db)
            print(f"  {z:<10s}: {n} rows")
