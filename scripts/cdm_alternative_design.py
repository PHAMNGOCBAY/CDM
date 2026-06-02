"""§72 Task 4+5 — Phương án thay thế CDM (alternative design schemes).

PA-A — Increase strength + reduce spacing để đạt ΔS=10cm
=========================================================
Cho mỗi HK + zone, sweep grid (q_u_kPa, spacing_m) tìm cấu hình thoả
mãn S_total ≤ ΔS_target (mặc định 10cm — cấp cao tốc gần mố cầu).

PA-B — Lc capped ≤ L_max → tìm (q_u, spacing)
==============================================
Cho constraint Lcoc ≤ L_max (vd 30m do hạn chế thiết bị thi công),
sweep (q_u, s) tìm cấu hình đạt ΔS_target.

Cost model: data/cost_model.json — q_u (vật liệu CDM) + density (số cọc/m²).

SQLite tables (idempotent):
- qtt_cdm_alternative_strength (PK: zone_code, bh_name, q_u_kPa, spacing_m, delta_S_cm)
- qtt_cdm_alternative_Lmax    (PK: zone_code, bh_name, L_max_m, delta_S_cm)
"""
from __future__ import annotations

import math
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from cdm_length_optimize import find_cdm_length  # type: ignore
from qtt_cdm_analysis import (  # type: ignore
    ZONE_DEFS,
    GWL_ELEV_QTT,
    get_zone_selected_hks,
    get_cdm_config,
    get_qtt_load_q,
    get_qtt_fill_total_thickness,
    soft_profile_from_db,
    _nearest_su_kpa,
    _SOFT_SYMBOLS_IP,
    _db_path,
)
from settlement_calc import bjerrum_mu, get_Ip_avg_for_bh  # type: ignore


# Sweep grids — đã tối giản để giảm số call find_cdm_length
QU_SWEEP_KPA   = [800.0, 1200.0, 1500.0, 2000.0, 3000.0]      # 5 mức
SPACING_SWEEP_M = [1.4, 1.6, 1.8]                              # 3 mức
L_STEP_FAST_M   = 1.0  # bước 1m cho sweep (so với 0.5m mặc định)


def _area_ratio(D_mm: float, s_m: float, pattern: str) -> float:
    """Tỷ lệ thay thế a = Ac/A_unit."""
    A_c = math.pi * (D_mm / 1000.0 / 2.0) ** 2
    if pattern == "triangular":
        A_unit = (s_m ** 2) * math.sqrt(3) / 2.0
    else:  # square
        A_unit = s_m ** 2
    return A_c / A_unit


def create_tables(db_path: Path | None = None) -> None:
    db = db_path or _db_path()
    with sqlite3.connect(db) as con:
        # PA-A
        con.execute("""
            CREATE TABLE IF NOT EXISTS qtt_cdm_alternative_strength (
                zone_code TEXT NOT NULL,
                bh_name TEXT NOT NULL,
                q_u_kPa REAL NOT NULL,
                spacing_m REAL NOT NULL,
                delta_S_cm REAL NOT NULL,
                a_ratio REAL,
                Ec_kPa REAL,
                p_optimal_m REAL,
                Lc_m REAL,
                tip_depth_m REAL,
                S1_cm REAL,
                S2_cm REAL,
                S_total_cm REAL,
                penetrates_full INTEGER,
                ok INTEGER,
                cost_rel REAL,
                selected INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (zone_code, bh_name, q_u_kPa, spacing_m, delta_S_cm)
            )
        """)
        # PA-B
        con.execute("""
            CREATE TABLE IF NOT EXISTS qtt_cdm_alternative_Lmax (
                zone_code TEXT NOT NULL,
                bh_name TEXT NOT NULL,
                L_max_m REAL NOT NULL,
                delta_S_cm REAL NOT NULL,
                q_u_opt_kPa REAL,
                spacing_opt_m REAL,
                a_ratio REAL,
                Ec_kPa REAL,
                p_optimal_m REAL,
                Lc_m REAL,
                tip_depth_m REAL,
                S1_cm REAL,
                S2_cm REAL,
                S_total_cm REAL,
                ok INTEGER,
                cost_rel REAL,
                selected INTEGER DEFAULT 1,
                note TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (zone_code, bh_name, L_max_m, delta_S_cm)
            )
        """)
        con.commit()


def _cost_rel(q_u_kPa: float, spacing_m: float, Lc_m: float, D_mm: float,
              q_u_base: float = 800.0, s_base: float = 1.8) -> float:
    """Chi phí tương đối so với baseline (q_u=800, s=1.8m). Theo cost_model.json:
    - vật liệu cọc ∝ (q_u_kPa)  (đệm cát-XM gia tăng theo cường độ)
    - mật độ cọc ∝ 1/s²
    - thể tích ∝ Lc × π(D/2)²
    """
    mat_factor = q_u_kPa / q_u_base
    density_factor = (s_base / spacing_m) ** 2
    return round(mat_factor * density_factor * (Lc_m / 20.0), 3)


def compute_pa_a_for_zone(zone_code: str,
                            delta_S_targets_cm: tuple[float, ...] = (10.0, 15.0),
                            db_path: Path | None = None) -> int:
    """PA-A: sweep (q_u, spacing) cho từng HK × ΔS target. Lưu DB."""
    db = db_path or _db_path()
    create_tables(db)
    if zone_code not in ZONE_DEFS:
        return 0

    q_kPa = get_qtt_load_q(db)
    fill_h = get_qtt_fill_total_thickness(db)
    cfg = get_cdm_config(db)
    D_mm = float(cfg["D_mm"])
    pattern = cfg["pattern"]
    Ec_factor = float(cfg["Ec_factor"])
    gwl = GWL_ELEV_QTT if zone_code == "QTT" else 0.0

    hks = get_zone_selected_hks(zone_code, db_path=db, include_unselected=True)
    n_written = 0
    with sqlite3.connect(db) as con:
        for hk in hks:
            name = hk["bh_name"]
            sel = int(hk.get("selected", 1) or 0)
            clay_top, H_soft = soft_profile_from_db(name, db)
            if clay_top is None or H_soft <= 0:
                continue
            Ip = get_Ip_avg_for_bh(name, _SOFT_SYMBOLS_IP, db) or 0.0
            mu = bjerrum_mu(Ip) if Ip > 0 else 1.0
            Su, _ = _nearest_su_kpa(name, clay_top, clay_top + H_soft, db)
            if Su <= 0:
                continue

            for q_u in QU_SWEEP_KPA:
                Ec = Ec_factor * q_u / 2.0
                for s_m in SPACING_SWEEP_M:
                    a = _area_ratio(D_mm, s_m, pattern)
                    for dS in delta_S_targets_cm:
                        try:
                            r = find_cdm_length(
                                bh_name=name, q_kPa=q_kPa, a=a,
                                Ec_kPa=Ec, Su_kPa=Su, target_dS_cm=dS,
                                mu=mu, db_path=db, gwl_elev_m=gwl,
                                L_step_m=L_STEP_FAST_M,
                            )
                        except Exception:
                            continue
                        p_opt = r.get("p_optimal_m")
                        S1 = r.get("S1_cm") or 0
                        S2 = r.get("S2_cm") or 0
                        S_tot = r.get("S_total_cm") or 0
                        ok = bool(r.get("ok"))
                        tip = (clay_top + p_opt) if p_opt else None
                        Lc = (tip - max(0.0, hk["nat"] - (fill_h or 0.0))) if tip else None
                        cost = _cost_rel(q_u, s_m, Lc or 0, D_mm) if (ok and Lc) else None
                        con.execute("""
                            INSERT OR REPLACE INTO qtt_cdm_alternative_strength
                            (zone_code, bh_name, q_u_kPa, spacing_m, delta_S_cm,
                             a_ratio, Ec_kPa, p_optimal_m, Lc_m, tip_depth_m,
                             S1_cm, S2_cm, S_total_cm,
                             penetrates_full, ok, cost_rel, selected, updated_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)
                        """, (
                            zone_code, name, q_u, s_m, float(dS),
                            round(a, 4), round(Ec, 0),
                            p_opt, Lc, tip,
                            round(S1, 2), round(S2, 2), round(S_tot, 2),
                            1 if r.get("penetrates_full") else 0,
                            1 if ok else 0,
                            cost, sel,
                        ))
                        n_written += 1
        con.commit()
    return n_written


def compute_pa_b_for_zone(zone_code: str,
                            L_max_values_m: tuple[float, ...] = (25.0, 30.0, 35.0),
                            delta_S_targets_cm: tuple[float, ...] = (20.0, 30.0),
                            db_path: Path | None = None) -> int:
    """PA-B: với mỗi L_max + ΔS, tìm (q_u, s) tối ưu chi phí mà Lc ≤ L_max."""
    db = db_path or _db_path()
    create_tables(db)
    if zone_code not in ZONE_DEFS:
        return 0

    q_kPa = get_qtt_load_q(db)
    fill_h = get_qtt_fill_total_thickness(db)
    cfg = get_cdm_config(db)
    D_mm = float(cfg["D_mm"])
    pattern = cfg["pattern"]
    Ec_factor = float(cfg["Ec_factor"])
    gwl = GWL_ELEV_QTT if zone_code == "QTT" else 0.0

    hks = get_zone_selected_hks(zone_code, db_path=db, include_unselected=True)
    n_written = 0
    with sqlite3.connect(db) as con:
        for hk in hks:
            name = hk["bh_name"]
            sel = int(hk.get("selected", 1) or 0)
            clay_top, H_soft = soft_profile_from_db(name, db)
            if clay_top is None or H_soft <= 0:
                continue
            Ip = get_Ip_avg_for_bh(name, _SOFT_SYMBOLS_IP, db) or 0.0
            mu = bjerrum_mu(Ip) if Ip > 0 else 1.0
            Su, _ = _nearest_su_kpa(name, clay_top, clay_top + H_soft, db)
            if Su <= 0:
                continue

            for L_max in L_max_values_m:
                for dS in delta_S_targets_cm:
                    best = None  # (cost, q_u, s, r, Lc)
                    for q_u in QU_SWEEP_KPA:
                        Ec = Ec_factor * q_u / 2.0
                        for s_m in SPACING_SWEEP_M:
                            a = _area_ratio(D_mm, s_m, pattern)
                            try:
                                r = find_cdm_length(
                                    bh_name=name, q_kPa=q_kPa, a=a,
                                    Ec_kPa=Ec, Su_kPa=Su, target_dS_cm=dS,
                                    mu=mu, db_path=db, gwl_elev_m=gwl,
                                )
                            except Exception:
                                continue
                            if not r.get("ok"):
                                continue
                            p_opt = r.get("p_optimal_m")
                            tip = clay_top + p_opt
                            Lc = tip - max(0.0, hk["nat"] - (fill_h or 0.0))
                            if Lc > L_max:
                                continue
                            cost = _cost_rel(q_u, s_m, Lc, D_mm)
                            if best is None or cost < best[0]:
                                best = (cost, q_u, s_m, r, Lc, tip, a, Ec)
                    if best:
                        cost, q_u, s_m, r, Lc, tip, a, Ec = best
                        con.execute("""
                            INSERT OR REPLACE INTO qtt_cdm_alternative_Lmax
                            (zone_code, bh_name, L_max_m, delta_S_cm,
                             q_u_opt_kPa, spacing_opt_m, a_ratio, Ec_kPa,
                             p_optimal_m, Lc_m, tip_depth_m,
                             S1_cm, S2_cm, S_total_cm,
                             ok, cost_rel, selected, note, updated_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)
                        """, (
                            zone_code, name, float(L_max), float(dS),
                            q_u, s_m, round(a, 4), round(Ec, 0),
                            r.get("p_optimal_m"), round(Lc, 2), round(tip, 2),
                            r.get("S1_cm"), r.get("S2_cm"), r.get("S_total_cm"),
                            1, cost, sel, "optimal",
                        ))
                    else:
                        con.execute("""
                            INSERT OR REPLACE INTO qtt_cdm_alternative_Lmax
                            (zone_code, bh_name, L_max_m, delta_S_cm,
                             ok, selected, note, updated_at)
                            VALUES (?,?,?,?,?,?,?, CURRENT_TIMESTAMP)
                        """, (
                            zone_code, name, float(L_max), float(dS),
                            0, sel, f"Không có cấu hình đạt với Lc ≤ {L_max}m",
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
        print(f"DB: {db}")
        total_a = total_b = 0
        for z in ZONES:
            n_a = compute_pa_a_for_zone(z, db_path=db)
            n_b = compute_pa_b_for_zone(z, db_path=db)
            total_a += n_a; total_b += n_b
            print(f"  {z:<10s}: PA-A={n_a:4d}  PA-B={n_b:3d}")
        print(f"  TOTAL: PA-A={total_a}, PA-B={total_b}\n")
