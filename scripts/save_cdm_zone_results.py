"""
save_cdm_zone_results.py — Lưu kết quả Lc tối ưu per zone × HK × ΔS vào SQLite.

Table `cdm_zone_design_results` (§63 docs):
  PRIMARY KEY (zone_code, bh_name, delta_S_cm)
  Lc_m, tip_depth_m, p_optimal_m, S1_cm, S2_cm, S_total_cm,
  penetrates_full, force_full, cc_source, borrowed, ok

Chạy: `python scripts/save_cdm_zone_results.py`
→ Compute + INSERT OR REPLACE cho 4 zone × 4 ΔS = ~120 rows.
"""
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

from qtt_cdm_analysis import (  # noqa: E402
    compute_zone_cdm_lc_matrix, ZONE_DEFS,
    check_pairwise_smoothness, compute_s_vs_p_curves,
    compute_grid_lc,
)


def _db_path() -> Path:
    local = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
    return local if local.exists() else _ROOT / "data" / "TTHC.sqlite"


def create_table(db_path: Path | None = None) -> None:
    db = db_path or _db_path()
    with sqlite3.connect(db) as con:
        # Bảng 1: Lc tối ưu (đã có)
        con.execute("""
            CREATE TABLE IF NOT EXISTS cdm_zone_design_results (
                zone_code TEXT NOT NULL,
                bh_name TEXT NOT NULL,
                delta_S_cm REAL NOT NULL,
                Lc_m REAL,
                tip_depth_m REAL,
                p_optimal_m REAL,
                S1_cm REAL,
                S2_cm REAL,
                S_total_cm REAL,
                penetrates_full INTEGER,
                force_full INTEGER,
                cc_source TEXT,
                borrowed INTEGER,
                ok INTEGER,
                H_soft_m REAL,
                cdm_top_elev_m REAL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (zone_code, bh_name, delta_S_cm)
            )
        """)
        # ALTER TABLE — thêm cột selected (idempotent) — §72 Task 2
        try:
            con.execute(
                "ALTER TABLE cdm_zone_design_results "
                "ADD COLUMN selected INTEGER DEFAULT 1"
            )
        except sqlite3.OperationalError:
            pass  # column already exists
        # Bảng 2: smoothness pair-wise
        con.execute("""
            CREATE TABLE IF NOT EXISTS cdm_zone_smoothness_results (
                zone_code TEXT NOT NULL,
                delta_S_cm REAL NOT NULL,
                hk_i TEXT NOT NULL,
                hk_j TEXT NOT NULL,
                d_m REAL,
                dS_pair_m REAL,
                i_inv_actual REAL,
                S_i_cm REAL,
                S_j_cm REAL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (zone_code, delta_S_cm, hk_i, hk_j)
            )
        """)
        # Bảng 3: S(Lc) curves
        con.execute("""
            CREATE TABLE IF NOT EXISTS cdm_zone_s_lc_curves (
                zone_code TEXT NOT NULL,
                bh_name TEXT NOT NULL,
                p_m REAL NOT NULL,
                Lc_m REAL,
                tip_depth_m REAL,
                S1_cm REAL,
                S2_cm REAL,
                S_total_cm REAL,
                cc_source TEXT,
                borrowed INTEGER,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (zone_code, bh_name, p_m)
            )
        """)
        # Bảng 4: grid Lc 162 điểm QTT
        con.execute("""
            CREATE TABLE IF NOT EXISTS cdm_qtt_grid_lc (
                delta_S_cm REAL NOT NULL,
                easting_m REAL NOT NULL,
                northing_m REAL NOT NULL,
                elev_des_m REAL,
                elev_nat_m REAL,
                fill_m REAL,
                cdm_top_elev_m REAL,
                ref_hk TEXT,
                ref_dist_m REAL,
                Lc_m REAL,
                tip_depth_m REAL,
                S_total_cm REAL,
                ok INTEGER,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (delta_S_cm, easting_m, northing_m)
            )
        """)
        con.commit()


def save_zone(zone_code: str,
               delta_S_values_cm: tuple = (10.0, 15.0, 20.0, 25.0, 30.0, 40.0),
               db_path: Path | None = None) -> int:
    db = db_path or _db_path()
    res = compute_zone_cdm_lc_matrix(zone_code,
                                      delta_S_values_cm=delta_S_values_cm,
                                      db_path=db)
    n = 0
    with sqlite3.connect(db) as con:
        for h in res["hks"]:
            for dS, r in h.get("by_dS", {}).items():
                con.execute("""
                    INSERT OR REPLACE INTO cdm_zone_design_results
                    (zone_code, bh_name, delta_S_cm,
                     Lc_m, tip_depth_m, p_optimal_m,
                     S1_cm, S2_cm, S_total_cm,
                     penetrates_full, force_full,
                     cc_source, borrowed, ok,
                     H_soft_m, cdm_top_elev_m, selected,
                     updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                            CURRENT_TIMESTAMP)
                """, (
                    zone_code, h["name"], float(dS),
                    r.get("Lc_m"), r.get("tip_depth_m"),
                    r.get("p_optimal_m"),
                    r.get("S1_cm"), r.get("S2_cm"),
                    r.get("S_total_cm"),
                    1 if r.get("penetrates_full") else 0,
                    1 if r.get("force_full") else 0,
                    h.get("cc_source"),
                    1 if h.get("borrowed") else 0,
                    1 if r.get("ok") else 0,
                    h.get("H_soft_m"),
                    h.get("cdm_top_elev"),
                    int(h.get("selected", 1) or 0),
                ))
                n += 1
        con.commit()
    return n


def save_zone_smoothness(zone_code: str,
                          delta_S_values_cm: tuple = (10.0, 15.0, 20.0, 25.0, 30.0, 40.0),
                          db_path: Path | None = None) -> int:
    """Lưu smoothness pair-wise cho zone × ΔS — dùng i_inv_max=125 (loose)."""
    db = db_path or _db_path()
    res = compute_zone_cdm_lc_matrix(zone_code,
                                      delta_S_values_cm=delta_S_values_cm,
                                      db_path=db)
    n = 0
    with sqlite3.connect(db) as con:
        # Query coords cho QTT HK (vì QTT engine không trả E/N)
        con.row_factory = sqlite3.Row
        coords = {}
        for h in res["hks"]:
            E = h.get("E"); N = h.get("N")
            if E is None or N is None:
                row = con.execute(
                    "SELECT x_coord_m, y_coord_m FROM boreholes WHERE name=?",
                    (h["name"],),
                ).fetchone()
                if row:
                    coords[h["name"]] = (float(row["y_coord_m"]),
                                          float(row["x_coord_m"]))
            else:
                coords[h["name"]] = (float(E), float(N))
        con.row_factory = None
        for dS in delta_S_values_cm:
            hks_S = []
            for h in res["hks"]:
                r = h.get("by_dS", {}).get(dS, {})
                if not (r.get("ok") and r.get("S_total_cm") is not None):
                    continue
                if h["name"] not in coords:
                    continue
                E, N = coords[h["name"]]
                hks_S.append({
                    "name": h["name"], "E": E, "N": N,
                    "S_cm": float(r["S_total_cm"]),
                })
            if len(hks_S) < 2:
                continue
            # Tính i_inv tham chiếu rộng nhất (1/125 với vong)
            pairs = check_pairwise_smoothness(hks_S, 125.0)
            for p in pairs:
                # Lấy S_i, S_j từ hks_S
                _Si = next(h["S_cm"] for h in hks_S if h["name"] == p["i"])
                _Sj = next(h["S_cm"] for h in hks_S if h["name"] == p["j"])
                con.execute("""
                    INSERT OR REPLACE INTO cdm_zone_smoothness_results
                    (zone_code, delta_S_cm, hk_i, hk_j,
                     d_m, dS_pair_m, i_inv_actual,
                     S_i_cm, S_j_cm, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)
                """, (
                    zone_code, float(dS), p["i"], p["j"],
                    p["d_m"], p["dS_m"], p.get("i_inv_actual"),
                    _Si, _Sj,
                ))
                n += 1
        con.commit()
    return n


def save_zone_curves(zone_code: str,
                      p_range_m: tuple = (0.5, 35.0),
                      p_step_m: float = 1.0,
                      db_path: Path | None = None) -> int:
    """Lưu S(Lc) curves quét p cho mỗi HK trong zone.

    Vì compute_s_vs_p_curves chỉ dùng QTT (ND HK), cần áp dụng generic cho
    multi-zone. Dùng find_cdm_length history.
    """
    db = db_path or _db_path()
    # Lazy reuse compute_zone_cdm_lc_matrix với target lớn để lấy history
    from cdm_length_optimize import find_cdm_length
    from settlement_calc import bjerrum_mu, get_Ip_avg_for_bh
    from qtt_cdm_analysis import (
        _SOFT_SYMBOLS_IP, _nearest_su_kpa, get_cdm_config,
        get_qtt_load_q, get_qtt_fill_total_thickness, _area_ratio,
        get_zone_selected_hks, soft_profile_from_db,
    )
    import math

    cfg = get_cdm_config(db)
    q_kPa = get_qtt_load_q(db)
    fill_h = get_qtt_fill_total_thickness(db)
    D_mm = float(cfg["D_mm"])
    s_m = float(cfg["spacing_m"])
    a = _area_ratio(D_mm, s_m, cfg["pattern"])
    Ec_kPa = float(cfg["Ec_factor"]) * float(cfg["qu_kPa"]) / 2.0

    with sqlite3.connect(db) as con:
        row = con.execute(
            "SELECT settlement_design_elev_m FROM tvtk_cdm_config WHERE id=1"
        ).fetchone()
    design_elev = float(row[0]) if row and row[0] else 2.70

    hks = get_zone_selected_hks(zone_code, db_path=db)
    n = 0
    with sqlite3.connect(db) as con:
        for hk in hks:
            name = hk["bh_name"]
            nat = float(hk["nat"]) if hk["nat"] is not None else 0.0
            clay_top, H_soft = soft_profile_from_db(name, db)
            if clay_top is None:
                continue
            # Mượn Cc nếu thiếu
            cc_n = con.execute("""
                SELECT COUNT(*) FROM lab_tests lt
                JOIN boreholes b ON lt.borehole_id = b.id
                WHERE b.name=? AND lt.Cc IS NOT NULL AND lt.Cc > 0
            """, (name,)).fetchone()[0]
            bh_calc = name
            cc_source = name
            borrowed = 0
            if cc_n == 0 and hk["E"] is not None:
                con.row_factory = sqlite3.Row
                pfx = ZONE_DEFS[zone_code]["bh_prefix"] + "%"
                E, N = float(hk["E"]), float(hk["N"])
                rows_cc = con.execute("""
                    SELECT b.name, b.x_coord_m AS N, b.y_coord_m AS E
                    FROM boreholes b
                    JOIN lab_tests lt ON lt.borehole_id = b.id
                    WHERE b.name LIKE ?
                      AND lt.Cc IS NOT NULL AND lt.Cc > 0
                      AND b.name != ?
                    GROUP BY b.id
                """, (pfx, name)).fetchall()
                best_d = float("inf"); best_n = None
                for r in rows_cc:
                    if r["E"] is None or r["N"] is None:
                        continue
                    d = math.hypot(float(r["E"]) - E, float(r["N"]) - N)
                    if d < best_d:
                        best_d = d; best_n = r["name"]
                if best_n:
                    cc_source = best_n
                    bh_calc = best_n
                    borrowed = 1
                con.row_factory = None
            try:
                ip = get_Ip_avg_for_bh(bh_calc, _SOFT_SYMBOLS_IP, db_path=db)
            except Exception:
                ip = None
            mu = bjerrum_mu(ip) if ip else 1.0
            Su, _ = _nearest_su_kpa(name, clay_top, clay_top + H_soft, db)

            cdm_top_depth = nat - (design_elev - fill_h)
            # Lấy history full
            try:
                r = find_cdm_length(
                    bh_calc, q_kPa=q_kPa, a=a, Ec_kPa=Ec_kPa,
                    Su_kPa=Su, target_dS_cm=9999.0,
                    h_clay_m=H_soft, clay_top_depth_m=clay_top,
                    L_step_m=p_step_m, mu=mu, t_years_residual=15.0,
                    db_path=db,
                )
                for entry in r.get("history", []):
                    p_m = float(entry["p_m"])
                    if p_m < p_range_m[0] or p_m > p_range_m[1]:
                        continue
                    tip = clay_top + p_m
                    Lc = max(0.0, tip - cdm_top_depth)
                    con.execute("""
                        INSERT OR REPLACE INTO cdm_zone_s_lc_curves
                        (zone_code, bh_name, p_m, Lc_m, tip_depth_m,
                         S1_cm, S2_cm, S_total_cm, cc_source, borrowed,
                         updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)
                    """, (
                        zone_code, name, p_m, Lc, tip,
                        entry.get("S1_cm"), entry.get("S2_cm"),
                        entry.get("S_total_cm"), cc_source, borrowed,
                    ))
                    n += 1
            except Exception:
                continue
        con.commit()
    return n


def save_qtt_grid_lc(delta_S_values_cm: tuple = (10.0, 15.0, 20.0, 25.0, 30.0, 40.0),
                      db_path: Path | None = None) -> int:
    """Lưu grid Lc 162 điểm × ΔS cho QTT."""
    db = db_path or _db_path()
    n = 0
    with sqlite3.connect(db) as con:
        for dS in delta_S_values_cm:
            res = compute_grid_lc(target_S_cm=float(dS), db_path=db)
            for gp in res.get("points", []):
                con.execute("""
                    INSERT OR REPLACE INTO cdm_qtt_grid_lc
                    (delta_S_cm, easting_m, northing_m,
                     elev_des_m, elev_nat_m, fill_m,
                     cdm_top_elev_m, ref_hk, ref_dist_m,
                     Lc_m, tip_depth_m, S_total_cm, ok,
                     updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)
                """, (
                    float(dS), gp["E"], gp["N"],
                    gp.get("elev_des"), gp.get("elev_nat"), gp.get("fill_m"),
                    gp.get("cdm_top_elev"), gp.get("ref_hk"),
                    gp.get("ref_dist_m"), gp.get("Lc_m"),
                    gp.get("tip_depth_m"), gp.get("S_total_cm"),
                    1 if gp.get("ok") else 0,
                ))
                n += 1
        con.commit()
    return n


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    db = _db_path()
    print(f"DB: {db}")
    create_table(db)
    print()
    # 1. Lc tối ưu
    print("[1] Lc tối ưu per zone × HK × ΔS:")
    total_lc = 0
    for zc in ("QTT", "BXN", "NHC", "KE_park", "KE_levee"):
        if zc not in ZONE_DEFS:
            continue
        try:
            n = save_zone(zc, db_path=db)
            print(f"  {zc:10s}: {n} rows")
            total_lc += n
        except Exception as e:
            print(f"  {zc:10s}: ERR {type(e).__name__}: {e}")
    print(f"  TỔNG: {total_lc} rows cdm_zone_design_results")
    print()
    # 2. Smoothness pair-wise
    print("[2] Smoothness pair-wise per zone × ΔS:")
    total_sm = 0
    for zc in ("QTT", "BXN", "NHC", "KE_park", "KE_levee"):
        try:
            n = save_zone_smoothness(zc, db_path=db)
            print(f"  {zc:10s}: {n} pairs")
            total_sm += n
        except Exception as e:
            print(f"  {zc:10s}: ERR {type(e).__name__}: {e}")
    print(f"  TỔNG: {total_sm} rows cdm_zone_smoothness_results")
    print()
    # 3. S(Lc) curves
    print("[3] S(Lc) curves per zone × HK × p:")
    total_c = 0
    for zc in ("QTT", "BXN", "NHC", "KE_park", "KE_levee"):
        try:
            n = save_zone_curves(zc, db_path=db)
            print(f"  {zc:10s}: {n} points")
            total_c += n
        except Exception as e:
            print(f"  {zc:10s}: ERR {type(e).__name__}: {e}")
    print(f"  TỔNG: {total_c} rows cdm_zone_s_lc_curves")
    print()
    # 4. QTT grid Lc 162 × ΔS
    print("[4] QTT grid Lc 162 × ΔS:")
    try:
        n_grid = save_qtt_grid_lc(db_path=db)
        print(f"  QTT       : {n_grid} grid-rows")
    except Exception as e:
        print(f"  ERR: {e}")
        n_grid = 0
    print()
    print("=" * 60)
    print(f"TỔNG: Lc={total_lc} + Smoothness={total_sm} + "
          f"Curves={total_c} + Grid={n_grid}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
