"""
qtt_cdm_analysis.py — Phân tích giải pháp CDM cho khu vực QTT.

Mục tiêu:
- Cho mỗi HK ND × mỗi giới hạn ΔS (TCCS 41 Bảng 1): tìm chiều dài cọc CDM (Lc)
  ngắn nhất sao cho S_total = S1 + S2 ≤ ΔS.
- Hình học: cao độ đỉnh cọc CDM = cao độ thiết kế − Σ(bề dày các lớp đắp trên).
- Tải trọng q không đổi (40.8 kPa) — bằng trọng lượng các lớp đắp trên đỉnh CDM.
- HK thiếu mẫu Cc → mượn từ HK ND có Cc gần nhất (§15).

Khái niệm:
- p_optimal_m  : độ xuyên cọc vào lớp đất yếu (m) — output của find_cdm_length
- Lc_m         : chiều dài CỌC từ đỉnh CDM đến mũi = tip_depth − CDM_top_depth
                 (đo từ cao độ tự nhiên)
- excavation_m : phần đất đào để hạ mặt nền xuống đỉnh CDM
                 = max(0, nat − (design − Σh_lớp))
"""
from __future__ import annotations
import math
import sqlite3
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

from cdm_length_optimize import find_cdm_length, soft_profile_from_db  # noqa: E402
from settlement_calc import bjerrum_mu, get_Ip_avg_for_bh  # noqa: E402

_DB_DEFAULT = _ROOT / "data" / "TTHC.sqlite"
_SOFT_SYMBOLS_IP = ("1", "1b", "CH", "MH", "CH-OH", "MH-OH")


def _db_path() -> Path:
    local = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
    return local if local.exists() else _DB_DEFAULT


def get_gwl_elev_m(db_path: Optional[Path] = None) -> float:
    """§72 Issue V #3 — Cao độ MNN tuyệt đối từ tvtk_cdm_config.gwl_elev_m.

    Mặc định 0.0 (mốc Quốc gia) nếu cột chưa có hoặc giá trị NULL.
    Tự ALTER TABLE thêm cột (idempotent) lần đầu gọi.
    """
    p = Path(db_path) if db_path else _db_path()
    with sqlite3.connect(p) as con:
        try:
            con.execute(
                "ALTER TABLE tvtk_cdm_config ADD COLUMN gwl_elev_m REAL DEFAULT 0.0"
            )
            con.commit()
        except sqlite3.OperationalError:
            pass  # column exists
        row = con.execute(
            "SELECT gwl_elev_m FROM tvtk_cdm_config WHERE id=1"
        ).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


# §72 Issue V #3 — Module-level alias từ SQLite (KHÔNG hardcode 0.0)
GWL_ELEV_QTT = get_gwl_elev_m()


def get_qtt_fill_total_thickness(db_path: Optional[Path] = None) -> float:
    """Tổng chiều dày các lớp đắp từ tvtk_fill_composition (m)."""
    p = Path(db_path) if db_path else _db_path()
    with sqlite3.connect(p) as con:
        row = con.execute("SELECT SUM(h_m) FROM tvtk_fill_composition").fetchone()
    return float(row[0]) if row and row[0] is not None else 1.9


def get_qtt_load_q(db_path: Optional[Path] = None) -> float:
    """Tải phân bố q từ tvtk_cdm_config.q_kPa (kPa)."""
    p = Path(db_path) if db_path else _db_path()
    with sqlite3.connect(p) as con:
        row = con.execute("SELECT q_kPa FROM tvtk_cdm_config WHERE id=1").fetchone()
    return float(row[0]) if row and row[0] is not None else 40.8


def get_cdm_config(db_path: Optional[Path] = None) -> dict:
    """Đọc cấu hình CDM mặc định (D, s, pattern, k, qu)."""
    p = Path(db_path) if db_path else _db_path()
    with sqlite3.connect(p) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT D_mm, spacing_m, pattern, Ec_factor, qu_kPa "
            "FROM tvtk_cdm_config WHERE id=1"
        ).fetchone()
    return dict(row) if row else {
        "D_mm": 800.0, "spacing_m": 1.8, "pattern": "square",
        "Ec_factor": 100.0, "qu_kPa": 800.0,
    }


def _area_ratio(D_mm: float, s_m: float, pattern: str = "square") -> float:
    D = D_mm / 1000.0
    r = D / 2.0
    if pattern == "triangle":
        return math.pi * r * r / (s_m * s_m * math.sqrt(3) / 2.0)
    return math.pi * r * r / (s_m * s_m)


def _nearest_grid_design(bh_E: float, bh_N: float, db_path: Path) -> tuple[float, float]:
    """Trả về (elev_des_m, distance_m) từ qtt_elevation_points gần nhất."""
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("""
            SELECT elev_des_m,
                   ((easting_m - ?) * (easting_m - ?) +
                    (northing_m - ?) * (northing_m - ?)) AS d2
            FROM qtt_elevation_points
            WHERE elev_des_m IS NOT NULL
            ORDER BY d2 ASC LIMIT 1
        """, (bh_E, bh_E, bh_N, bh_N)).fetchone()
    if row is None:
        return 2.70, float("inf")
    return float(row["elev_des_m"]), float(row["d2"]) ** 0.5


def _nearest_su_kpa(bh_name: str, soft_top: float, soft_bot: float,
                     db_path: Path) -> tuple[float, str]:
    """Trả về (Su_kPa_TB, source). Priority: VST của HK > VST lân cận > lab Cu_UU."""
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        # 1. VST cho chính HK
        r = con.execute("""
            SELECT AVG(v.Su_kPa) FROM vane_shear_tests v
            JOIN vst_locations vl ON v.vst_loc_id = vl.id
            WHERE vl.name = ? AND v.depth_m BETWEEN ? AND ?
        """, (bh_name, soft_top, soft_bot)).fetchone()
        if r and r[0] is not None and r[0] > 0:
            return float(r[0]), "VST"
        # 2. Lab Cu_UU trong lớp yếu
        r = con.execute("""
            SELECT AVG(lt.Cu_UU_kPa) FROM lab_tests lt
            JOIN boreholes b ON lt.borehole_id = b.id
            WHERE b.name = ? AND lt.Cu_UU_kPa > 0
              AND (lt.depth_from_m + lt.depth_to_m) / 2.0 BETWEEN ? AND ?
        """, (bh_name, soft_top, soft_bot)).fetchone()
        if r and r[0] is not None and r[0] > 0:
            return float(r[0]), "UU"
    return 11.0, "default"


def _nearest_cc_hk(bh_E: float, bh_N: float, db_path: Path) -> tuple[Optional[str], float]:
    """Tìm HK ND-* gần nhất có ≥1 mẫu Cc. Trả về (name, distance_m)."""
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT b.name, b.x_coord_m AS N, b.y_coord_m AS E
            FROM boreholes b
            JOIN lab_tests lt ON lt.borehole_id = b.id
            WHERE b.name LIKE 'ND-%' AND lt.Cc IS NOT NULL AND lt.Cc > 0
            GROUP BY b.id
        """).fetchall()
    best = None
    best_d = float("inf")
    for r in rows:
        d = math.hypot(float(r["E"]) - bh_E, float(r["N"]) - bh_N)
        if d < best_d:
            best_d = d
            best = r["name"]
    return best, best_d


def compute_cdm_lc_matrix(
    delta_S_values_cm: tuple[float, ...] = (10.0, 15.0, 20.0, 25.0, 30.0, 40.0),
    db_path: Optional[Path] = None,
) -> dict:
    """Tính Lc tối ưu cho mỗi HK ND × mỗi giới hạn ΔS.

    Trả về dict:
      meta: {q_kPa, fill_thickness_m, D_mm, s_m, a, Ec_kPa, ...}
      hks:  list[{name, nat, design, cdm_top_depth_m, excavation_m,
                  cc_source, borrowed, mu, Su, Es, clay_top_m, H_soft_m,
                  by_dS: dict[ΔS] = {p_optimal_m, Lc_m, tip_depth_m,
                                      S1_cm, S2_cm, S_total_cm, ok, note}}]
    """
    db = Path(db_path) if db_path else _db_path()

    # Cấu hình chung
    cfg = get_cdm_config(db)
    q_kPa = get_qtt_load_q(db)
    fill_h = get_qtt_fill_total_thickness(db)
    D_mm = float(cfg["D_mm"])
    s_m = float(cfg["spacing_m"])
    pattern = cfg["pattern"]
    Ec_factor = float(cfg["Ec_factor"])
    qu_kPa = float(cfg["qu_kPa"])
    a = _area_ratio(D_mm, s_m, pattern)
    Ec_kPa = Ec_factor * qu_kPa / 2.0

    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        hks_q = con.execute("""
            SELECT name, elevation_m, x_coord_m AS N, y_coord_m AS E
            FROM boreholes WHERE name LIKE 'ND-%' ORDER BY name
        """).fetchall()

    out_hks: list[dict] = []
    for hk in hks_q:
        name = hk["name"]
        nat = float(hk["elevation_m"]) if hk["elevation_m"] is not None else None
        E = float(hk["E"]) if hk["E"] is not None else None
        N = float(hk["N"]) if hk["N"] is not None else None
        if nat is None or E is None or N is None:
            continue

        # Cao độ thiết kế nearest grid
        des, grid_d = _nearest_grid_design(E, N, db)
        cdm_top_elev = des - fill_h           # cao độ đỉnh CDM (m)
        cdm_top_depth = nat - cdm_top_elev    # độ sâu đỉnh CDM từ tự nhiên (m, có thể âm)
        excavation = max(0.0, cdm_top_depth)  # đào nếu CDM_top dưới tự nhiên

        # Lớp đất yếu của HK
        clay_top, H_soft = soft_profile_from_db(name, db)
        if clay_top is None:
            out_hks.append({
                "name": name, "nat": nat, "design": des,
                "cdm_top_depth_m": round(cdm_top_depth, 2),
                "excavation_m": round(excavation, 2),
                "note": "Không có dữ liệu lớp đất yếu",
                "by_dS": {dS: {"ok": False, "note": "no soft layer"}
                          for dS in delta_S_values_cm},
            })
            continue

        # Mượn HK có Cc nếu HK hiện tại không có
        with sqlite3.connect(db) as con:
            cc_n = con.execute("""
                SELECT COUNT(*) FROM lab_tests lt
                JOIN boreholes b ON lt.borehole_id = b.id
                WHERE b.name=? AND lt.Cc IS NOT NULL AND lt.Cc > 0
            """, (name,)).fetchone()[0]
        if cc_n > 0:
            cc_source = name
            borrowed = False
            cc_dist = 0.0
        else:
            cc_source, cc_dist = _nearest_cc_hk(E, N, db)
            borrowed = cc_source is not None

        # Ip TB cho μ (cho HK gốc của Su; mượn nếu cần)
        try:
            ip = get_Ip_avg_for_bh(name, _SOFT_SYMBOLS_IP, db_path=db)
        except Exception:
            ip = None
        if (ip is None or ip <= 0) and borrowed and cc_source:
            try:
                ip = get_Ip_avg_for_bh(cc_source, _SOFT_SYMBOLS_IP, db_path=db)
            except Exception:
                ip = None
        mu = bjerrum_mu(ip) if ip else 1.0

        Su, su_src = _nearest_su_kpa(name, clay_top, clay_top + H_soft, db)
        Es_kPa = 250.0 * mu * Su

        by_dS: dict[float, dict] = {}
        for dS in delta_S_values_cm:
            # find_cdm_length dùng bh_name để lấy lớp đất yếu + lab samples (Cc, e0, PC)
            # Khi HK thiếu Cc → mượn HK gần nhất → soft_profile từ HK gốc, Cc từ HK mượn
            bh_for_calc = cc_source if borrowed and cc_source else name
            try:
                r = find_cdm_length(
                    bh_for_calc, q_kPa=q_kPa, a=a, Ec_kPa=Ec_kPa,
                    Su_kPa=Su, target_dS_cm=dS,
                    h_clay_m=H_soft, clay_top_depth_m=clay_top,
                    L_step_m=0.5, mu=mu, t_years_residual=15.0, gwl_elev_m=GWL_ELEV_QTT,
                    db_path=db,
                )
                p_opt = r.get("p_optimal_m")
                tip = r.get("tip_depth_m")
                Lc = None
                if p_opt is not None and tip is not None:
                    # Lc = tip_depth - cdm_top_depth (đo từ tự nhiên)
                    Lc = round(tip - cdm_top_depth, 2)
                by_dS[dS] = {
                    "p_optimal_m": p_opt,
                    "Lc_m": Lc,
                    "tip_depth_m": tip,
                    "S1_cm": r.get("S1_cm"),
                    "S2_cm": r.get("S2_cm"),
                    "S_total_cm": r.get("S_total_cm"),
                    "ok": bool(r.get("ok")),
                    "penetrates_full": r.get("penetrates_full"),
                    "note": r.get("note") or "",
                }
            except Exception as e:
                by_dS[dS] = {"ok": False, "note": f"ERR {type(e).__name__}: {e}",
                             "Lc_m": None, "S_total_cm": None}

        out_hks.append({
            "name": name, "nat": round(nat, 2), "design": round(des, 2),
            "grid_dist_m": round(grid_d, 1),
            "cdm_top_elev": round(cdm_top_elev, 2),
            "cdm_top_depth_m": round(cdm_top_depth, 2),
            "excavation_m": round(excavation, 2),
            "cc_source": cc_source, "borrowed": borrowed,
            "cc_dist_m": round(cc_dist, 0),
            "Ip_avg": round(ip, 1) if ip else None,
            "mu": round(mu, 4),
            "Su_kPa": round(Su, 2), "Su_source": su_src,
            "cu_kPa": round(mu * Su, 2),
            "Es_kPa": round(Es_kPa, 0),
            "clay_top_m": round(clay_top, 2),
            "H_soft_m": round(H_soft, 2),
            "by_dS": by_dS,
        })

    return {
        "meta": {
            "q_kPa": q_kPa,
            "fill_thickness_m": fill_h,
            "D_mm": D_mm,
            "spacing_m": s_m,
            "pattern": pattern,
            "a": round(a, 4),
            "Ec_factor": Ec_factor,
            "qu_kPa": qu_kPa,
            "Ec_kPa": round(Ec_kPa, 0),
            "delta_S_values_cm": list(delta_S_values_cm),
        },
        "hks": out_hks,
    }


def compute_s_vs_p_curves(
    p_range_m: tuple[float, float] = (0.5, 30.0),
    p_step_m: float = 1.0,
    db_path: Optional[Path] = None,
) -> dict:
    """Tính S_total(p) cho mỗi HK ND, p chạy từ p_range[0] tới p_range[1].

    Dùng cho biểu đồ "S vs Lc" — quan sát đường cong S(p) so với 4 ngưỡng ΔS.
    """
    db = Path(db_path) if db_path else _db_path()
    cfg = get_cdm_config(db)
    q_kPa = get_qtt_load_q(db)
    fill_h = get_qtt_fill_total_thickness(db)
    D_mm = float(cfg["D_mm"])
    s_m = float(cfg["spacing_m"])
    pattern = cfg["pattern"]
    Ec_factor = float(cfg["Ec_factor"])
    qu_kPa = float(cfg["qu_kPa"])
    a = _area_ratio(D_mm, s_m, pattern)
    Ec_kPa = Ec_factor * qu_kPa / 2.0

    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        hks_q = con.execute("""
            SELECT name, elevation_m, x_coord_m AS N, y_coord_m AS E
            FROM boreholes WHERE name LIKE 'ND-%' ORDER BY name
        """).fetchall()

    curves: dict[str, dict] = {}
    p_list: list[float] = []
    p = p_range_m[0]
    while p <= p_range_m[1] + 1e-6:
        p_list.append(round(p, 2))
        p += p_step_m

    for hk in hks_q:
        name = hk["name"]
        nat = float(hk["elevation_m"])
        E, N = float(hk["E"]), float(hk["N"])
        des, _ = _nearest_grid_design(E, N, db)
        cdm_top_depth = nat - (des - fill_h)

        clay_top, H_soft = soft_profile_from_db(name, db)
        if clay_top is None:
            continue

        # Mượn nếu thiếu Cc
        with sqlite3.connect(db) as con:
            cc_n = con.execute("""
                SELECT COUNT(*) FROM lab_tests lt
                JOIN boreholes b ON lt.borehole_id = b.id
                WHERE b.name=? AND lt.Cc IS NOT NULL AND lt.Cc > 0
            """, (name,)).fetchone()[0]
        if cc_n > 0:
            bh_calc = name
            cc_source = name
        else:
            cc_source, _ = _nearest_cc_hk(E, N, db)
            bh_calc = cc_source or name

        try:
            ip = get_Ip_avg_for_bh(bh_calc, _SOFT_SYMBOLS_IP, db_path=db)
        except Exception:
            ip = None
        mu = bjerrum_mu(ip) if ip else 1.0
        Su, _ = _nearest_su_kpa(name, clay_top, clay_top + H_soft, db)

        # Gọi find_cdm_length với target_dS_cm rất lớn để lấy full history
        try:
            r = find_cdm_length(
                bh_calc, q_kPa=q_kPa, a=a, Ec_kPa=Ec_kPa,
                Su_kPa=Su, target_dS_cm=9999.0,
                h_clay_m=H_soft, clay_top_depth_m=clay_top,
                L_step_m=p_step_m, mu=mu, t_years_residual=15.0, gwl_elev_m=GWL_ELEV_QTT,
                db_path=db,
            )
            hist = r.get("history", [])
            pts = []
            for row in hist:
                p_m = float(row["p_m"])
                tip = clay_top + p_m
                Lc = round(tip - cdm_top_depth, 2)
                pts.append({
                    "p_m": p_m, "Lc_m": Lc, "tip_depth_m": round(tip, 2),
                    "S1_cm": row["S1_cm"], "S2_cm": row["S2_cm"],
                    "S_total_cm": row["S_total_cm"],
                })
            curves[name] = {
                "cc_source": cc_source, "borrowed": cc_source != name,
                "cdm_top_depth_m": round(cdm_top_depth, 2),
                "clay_top_m": round(clay_top, 2),
                "H_soft_m": round(H_soft, 2),
                "points": pts,
            }
        except Exception:
            curves[name] = {"cc_source": cc_source, "points": []}

    return {
        "meta": {"q_kPa": q_kPa, "a": round(a, 4), "Ec_kPa": round(Ec_kPa, 0),
                 "fill_thickness_m": fill_h, "D_mm": D_mm, "spacing_m": s_m},
        "curves": curves,
    }


# ─────────────────────────────────────────────────────────────────────────
# Phần mở rộng — Multi-zone analysis (BXN / NHC / KE)
# ─────────────────────────────────────────────────────────────────────────

# Định nghĩa các zone và quy tắc đặc biệt
ZONE_DEFS = {
    "QTT": {
        "description": "Quảng Trường Trung Tâm",
        "bh_prefix": "ND-",
        "design_elev_source": "grid_qtt_elevation_points",
        "force_full_penetration": False,
        "subzone_filter": None,
    },
    "BXN": {
        "description": "Bãi Đỗ Xe Ngầm",
        "bh_prefix": "BXN-CV-",
        "design_elev_source": "global_config",  # tvtk_cdm_config.settlement_design_elev_m
        "force_full_penetration": False,
        "subzone_filter": None,
    },
    "NHC": {
        "description": "Nhà Hành Chính",
        "bh_prefix": "NHC-BH-",
        "design_elev_source": "global_config",
        "force_full_penetration": False,
        "subzone_filter": None,
    },
    "KE_park": {
        "description": "Công Viên (KE không trên tuyến kè)",
        "bh_prefix": "KE-HK",
        "design_elev_source": "global_config",
        "force_full_penetration": False,
        "subzone_filter": ("on_sw_alignment", 0),  # ke_sw_design.on_sw_alignment = 0
    },
    "KE_levee": {
        "description": "Bờ Kè (KE trên tuyến kè) — luôn xuyên hết lớp bùn",
        "bh_prefix": "KE-HK",
        "design_elev_source": "global_config",
        "force_full_penetration": True,
        "L_ngam_m": 1.0,   # ngàm vào lớp tốt thêm 1m
        "subzone_filter": ("on_sw_alignment", 1),
    },
}


def get_zone_selected_hks(zone_code: str, db_path: Optional[Path] = None,
                          include_unselected: bool = True) -> list[dict]:
    """Trả về danh sách HK của zone (mặc định lấy TẤT CẢ — §72 Task 2).

    Filter:
      - tvtk_bh_cdm.H_soft_m > 0
      - bh_name LIKE ZONE_DEFS[zone].bh_prefix + '%'
      - Nếu zone có subzone_filter: thêm điều kiện từ ke_sw_design
      - include_unselected=True (mặc định): KHÔNG lọc selected=1, lấy tất cả HK
      - include_unselected=False: chỉ HK selected=1

    Returns mỗi row có thêm cột 'selected' (0/1) để UI phân biệt.
    """
    if zone_code not in ZONE_DEFS:
        return []
    zd = ZONE_DEFS[zone_code]
    db = Path(db_path) if db_path else _db_path()
    prefix = zd["bh_prefix"] + "%"
    subzone = zd.get("subzone_filter")
    sel_clause = "" if include_unselected else "AND t.selected = 1"
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        if subzone:
            col, val = subzone
            sql = f"""
                SELECT t.bh_name, t.H_soft_m, t.selected,
                       b.elevation_m AS nat, b.x_coord_m AS N, b.y_coord_m AS E
                FROM tvtk_bh_cdm t
                JOIN boreholes b ON b.name = t.bh_name
                JOIN ke_sw_design k ON k.bh_name = t.bh_name
                WHERE t.H_soft_m > 0
                  AND t.bh_name LIKE ?
                  AND k.{col} = ?
                  {sel_clause}
                ORDER BY t.bh_name
            """
            params = (prefix, val)
        else:
            sql = f"""
                SELECT t.bh_name, t.H_soft_m, t.selected,
                       b.elevation_m AS nat, b.x_coord_m AS N, b.y_coord_m AS E
                FROM tvtk_bh_cdm t
                JOIN boreholes b ON b.name = t.bh_name
                WHERE t.H_soft_m > 0
                  AND t.bh_name LIKE ?
                  {sel_clause}
                ORDER BY t.bh_name
            """
            params = (prefix,)
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def compute_zone_cdm_lc_matrix(
    zone_code: str,
    delta_S_values_cm: tuple[float, ...] = (10.0, 15.0, 20.0, 25.0, 30.0, 40.0),
    L_ngam_m_override: Optional[float] = None,
    db_path: Optional[Path] = None,
) -> dict:
    """Tính Lc tối ưu cho mỗi HK selected trong zone × mỗi ΔS.

    Logic phân nhánh:
      - QTT: dùng grid design elev (gọi compute_cdm_lc_matrix gốc)
      - BXN/NHC/KE_park: design elev từ tvtk_cdm_config (global)
      - KE_levee: force full penetration — Lc = H_soft + L_ngam, đánh giá S
    """
    if zone_code == "QTT":
        return compute_cdm_lc_matrix(delta_S_values_cm, db_path)
    if zone_code not in ZONE_DEFS:
        return {"meta": {}, "hks": []}

    zd = ZONE_DEFS[zone_code]
    force_full = zd.get("force_full_penetration", False)
    L_ngam = L_ngam_m_override if L_ngam_m_override is not None else zd.get("L_ngam_m", 1.0)
    db = Path(db_path) if db_path else _db_path()

    # Cấu hình chung
    cfg = get_cdm_config(db)
    q_kPa = get_qtt_load_q(db)
    fill_h = get_qtt_fill_total_thickness(db)
    D_mm = float(cfg["D_mm"])
    s_m = float(cfg["spacing_m"])
    pattern = cfg["pattern"]
    Ec_factor = float(cfg["Ec_factor"])
    qu_kPa = float(cfg["qu_kPa"])
    a = _area_ratio(D_mm, s_m, pattern)
    Ec_kPa = Ec_factor * qu_kPa / 2.0

    # Design elev global từ config
    with sqlite3.connect(db) as con:
        row = con.execute(
            "SELECT settlement_design_elev_m FROM tvtk_cdm_config WHERE id=1"
        ).fetchone()
    design_elev_global = float(row[0]) if row and row[0] is not None else 2.70

    hks = get_zone_selected_hks(zone_code, db)
    out_hks: list[dict] = []
    for hk in hks:
        name = hk["bh_name"]
        nat = float(hk["nat"]) if hk["nat"] is not None else 0.0
        E = float(hk["E"]) if hk["E"] is not None else None
        N = float(hk["N"]) if hk["N"] is not None else None
        des = design_elev_global
        cdm_top_elev = des - fill_h
        cdm_top_depth = nat - cdm_top_elev
        excavation = max(0.0, cdm_top_depth)

        clay_top, H_soft = soft_profile_from_db(name, db)
        if clay_top is None:
            out_hks.append({
                "name": name, "nat": nat, "design": des,
                "E": E, "N": N,
                "selected": int(hk.get("selected", 1) or 0),
                "cdm_top_elev": round(cdm_top_elev, 2),
                "cdm_top_depth_m": round(cdm_top_depth, 2),
                "excavation_m": round(excavation, 2),
                "H_soft_m": None,
                "note": "Không có dữ liệu lớp đất yếu",
                "by_dS": {dS: {"ok": False, "note": "no soft layer"}
                          for dS in delta_S_values_cm},
            })
            continue

        # Cc source — mượn HK gần nhất nếu thiếu
        with sqlite3.connect(db) as con:
            cc_n = con.execute("""
                SELECT COUNT(*) FROM lab_tests lt
                JOIN boreholes b ON lt.borehole_id = b.id
                WHERE b.name=? AND lt.Cc IS NOT NULL AND lt.Cc > 0
            """, (name,)).fetchone()[0]
        borrowed = False
        cc_source = name
        cc_dist = 0.0
        if cc_n == 0 and E is not None and N is not None:
            # Mượn HK gần nhất trong CÙNG zone có Cc
            with sqlite3.connect(db) as con:
                con.row_factory = sqlite3.Row
                rows = con.execute("""
                    SELECT b.name, b.x_coord_m AS N, b.y_coord_m AS E
                    FROM boreholes b
                    JOIN lab_tests lt ON lt.borehole_id = b.id
                    WHERE b.name LIKE ?
                      AND lt.Cc IS NOT NULL AND lt.Cc > 0
                      AND b.name != ?
                    GROUP BY b.id
                """, (zd["bh_prefix"] + "%", name)).fetchall()
            if rows:
                best_d = float("inf")
                for r in rows:
                    if r["E"] is None or r["N"] is None:
                        continue
                    d = math.hypot(float(r["E"]) - E, float(r["N"]) - N)
                    if d < best_d:
                        best_d = d
                        cc_source = r["name"]
                if best_d != float("inf"):
                    cc_dist = best_d
                    borrowed = True

        try:
            ip = get_Ip_avg_for_bh(name, _SOFT_SYMBOLS_IP, db_path=db)
        except Exception:
            ip = None
        if (ip is None or ip <= 0) and borrowed and cc_source:
            try:
                ip = get_Ip_avg_for_bh(cc_source, _SOFT_SYMBOLS_IP, db_path=db)
            except Exception:
                ip = None
        mu = bjerrum_mu(ip) if ip else 1.0

        Su, su_src = _nearest_su_kpa(name, clay_top, clay_top + H_soft, db)
        Es_kPa = 250.0 * mu * Su

        bh_for_calc = cc_source if borrowed else name

        by_dS: dict[float, dict] = {}
        for dS in delta_S_values_cm:
            try:
                if force_full:
                    # Buộc xuyên hết bùn → p = H_soft + L_ngam
                    # Gọi find_cdm_length với target rất nhỏ để buộc dùng full p,
                    # rồi chọn entry trong history có p ≥ H_soft + L_ngam
                    from cdm_length_optimize import find_cdm_length as _fcl
                    r_full = _fcl(
                        bh_for_calc, q_kPa=q_kPa, a=a, Ec_kPa=Ec_kPa,
                        Su_kPa=Su, target_dS_cm=9999.0,  # large for full history
                        h_clay_m=H_soft, clay_top_depth_m=clay_top,
                        L_step_m=0.5, mu=mu, t_years_residual=15.0, gwl_elev_m=GWL_ELEV_QTT,
                        db_path=db,
                    )
                    # Tìm entry p ≥ H_soft + L_ngam
                    p_target = H_soft + L_ngam
                    chosen = None
                    for h_entry in r_full.get("history", []):
                        if h_entry["p_m"] >= p_target - 1e-6:
                            chosen = h_entry
                            break
                    if chosen is None and r_full.get("history"):
                        chosen = r_full["history"][-1]
                    if chosen:
                        S_total = chosen["S_total_cm"]
                        ok = S_total <= dS + 1e-6
                        tip = clay_top + chosen["p_m"]
                        Lc = round(max(0.0, tip - cdm_top_depth), 2)
                        by_dS[dS] = {
                            "p_optimal_m": chosen["p_m"],
                            "Lc_m": Lc,
                            "tip_depth_m": tip,
                            "S1_cm": chosen["S1_cm"],
                            "S2_cm": chosen["S2_cm"],
                            "S_total_cm": S_total,
                            "ok": ok,
                            "penetrates_full": True,
                            "force_full": True,
                            "note": (f"Buộc xuyên hết bùn (kè) p={chosen['p_m']:.1f}m. "
                                     f"{'Đạt' if ok else 'Không đạt'} ΔS={dS:.0f}cm."),
                        }
                    else:
                        by_dS[dS] = {"ok": False, "Lc_m": None,
                                     "note": "Không đủ history để force-full"}
                else:
                    from cdm_length_optimize import find_cdm_length as _fcl
                    r = _fcl(
                        bh_for_calc, q_kPa=q_kPa, a=a, Ec_kPa=Ec_kPa,
                        Su_kPa=Su, target_dS_cm=dS,
                        h_clay_m=H_soft, clay_top_depth_m=clay_top,
                        L_step_m=0.5, mu=mu, t_years_residual=15.0, gwl_elev_m=GWL_ELEV_QTT,
                        db_path=db,
                    )
                    p_opt = r.get("p_optimal_m")
                    tip = r.get("tip_depth_m")
                    Lc = None
                    if p_opt is not None and tip is not None:
                        Lc = round(max(0.0, float(tip) - cdm_top_depth), 2)
                    by_dS[dS] = {
                        "p_optimal_m": p_opt,
                        "Lc_m": Lc,
                        "tip_depth_m": tip,
                        "S1_cm": r.get("S1_cm"),
                        "S2_cm": r.get("S2_cm"),
                        "S_total_cm": r.get("S_total_cm"),
                        "ok": bool(r.get("ok")),
                        "penetrates_full": r.get("penetrates_full"),
                        "force_full": False,
                        "note": r.get("note") or "",
                    }
            except Exception as e:
                by_dS[dS] = {"ok": False, "Lc_m": None,
                             "note": f"ERR {type(e).__name__}: {e}"}

        out_hks.append({
            "name": name, "nat": round(nat, 2), "design": round(des, 2),
            "E": E, "N": N,
            "selected": int(hk.get("selected", 1) or 0),
            "cdm_top_elev": round(cdm_top_elev, 2),
            "cdm_top_depth_m": round(cdm_top_depth, 2),
            "excavation_m": round(excavation, 2),
            "cc_source": cc_source, "borrowed": borrowed,
            "cc_dist_m": round(cc_dist, 0),
            "Ip_avg": round(ip, 1) if ip else None,
            "mu": round(mu, 4),
            "Su_kPa": round(Su, 2), "Su_source": su_src,
            "cu_kPa": round(mu * Su, 2),
            "Es_kPa": round(Es_kPa, 0),
            "clay_top_m": round(clay_top, 2),
            "H_soft_m": round(H_soft, 2),
            "by_dS": by_dS,
        })

    return {
        "meta": {
            "zone_code": zone_code,
            "zone_desc": zd["description"],
            "force_full_penetration": force_full,
            "L_ngam_m": L_ngam if force_full else None,
            "q_kPa": q_kPa,
            "fill_thickness_m": fill_h,
            "D_mm": D_mm,
            "spacing_m": s_m,
            "pattern": pattern,
            "a": round(a, 4),
            "Ec_factor": Ec_factor,
            "qu_kPa": qu_kPa,
            "Ec_kPa": round(Ec_kPa, 0),
            "design_elev_global_m": design_elev_global,
            "delta_S_values_cm": list(delta_S_values_cm),
        },
        "hks": out_hks,
    }


# ─────────────────────────────────────────────────────────────────────────
# Cũ — QTT-specific (đã có)
# ─────────────────────────────────────────────────────────────────────────

def load_smoothness_limits(db_path: Optional[Path] = None) -> list[dict]:
    """Đọc 20 giá trị Bảng E.1 từ tccs41_smoothness_limits."""
    p = Path(db_path) if db_path else _db_path()
    with sqlite3.connect(p) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT road_class_code, structure, speed_kmh, i_denominator
            FROM tccs41_smoothness_limits
            ORDER BY road_class_code, structure, speed_kmh
        """).fetchall()
    return [dict(r) for r in rows]


def get_smoothness_i_inv(
    road_class_code: str, structure: str, speed_kmh: int,
    db_path: Optional[Path] = None,
) -> Optional[int]:
    """Trả về i_denominator (vd 200 cho i=1/200). None nếu '—' / không quy định."""
    p = Path(db_path) if db_path else _db_path()
    with sqlite3.connect(p) as con:
        row = con.execute("""
            SELECT i_denominator FROM tccs41_smoothness_limits
            WHERE road_class_code=? AND structure=? AND speed_kmh=?
        """, (road_class_code, structure, speed_kmh)).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def check_pairwise_smoothness(
    hks_with_S: list[dict], i_inv_max: float,
) -> list[dict]:
    """Kiểm tra độ dốc dọc trên các cặp HK sau cố kết.

    hks_with_S: list[{name, E, N, S_cm}]
    i_inv_max: 1/i_max (vd 200 cho i ≤ 1/200). Cho phép tới 1/125 cho "vồng".

    Trả về list[{i, j, d_m, dS_m, i_inv_actual, ok}], pair (i,j) với i<j theo tên.
    """
    out: list[dict] = []
    n = len(hks_with_S)
    for ii in range(n):
        a = hks_with_S[ii]
        for jj in range(ii + 1, n):
            b = hks_with_S[jj]
            d = math.hypot(float(a["E"]) - float(b["E"]),
                            float(a["N"]) - float(b["N"]))
            if d <= 0:
                continue
            dS = abs(float(a["S_cm"]) - float(b["S_cm"])) / 100.0  # cm → m
            if dS < 1e-6:
                i_inv_act = float("inf")
                ok = True
            else:
                i_inv_act = d / dS  # i_actual = dS/d → 1/i_actual = d/dS
                ok = i_inv_act >= i_inv_max  # i ≤ i_max ↔ 1/i ≥ 1/i_max
            out.append({
                "i": a["name"], "j": b["name"],
                "d_m": round(d, 1),
                "dS_m": round(dS, 4),
                "i_inv_actual": (round(i_inv_act, 0)
                                  if i_inv_act != float("inf") else None),
                "i_inv_max": i_inv_max,
                "ok": ok,
            })
    return out


def find_lc_uniform_residual(
    target_S_cm: float,
    db_path: Optional[Path] = None,
) -> dict:
    """Tìm Lc cho mỗi HK ND sao cho S_residual = target_S (uniform → flatness auto).

    Tận dụng compute_cdm_lc_matrix với 1 mức ΔS = target.
    Trả về matrix theo cùng schema, chỉ có 1 ΔS column.
    """
    return compute_cdm_lc_matrix(
        delta_S_values_cm=(target_S_cm,),
        db_path=db_path,
    )


def compute_grid_lc(
    target_S_cm: float,
    db_path: Optional[Path] = None,
) -> dict:
    """Tính Lc yêu cầu tại MỖI điểm grid (162 điểm) cho 1 ΔS target.

    Phương pháp: cho mỗi grid point:
      1. Tìm HK ND gần nhất có Cc để mượn thông số đất
      2. Tính H_fill_local = grid.elev_des - grid.elev_nat (≥0)
      3. Tính CDM_top_depth_local từ tự nhiên của HK đại diện
      4. Gọi find_cdm_length với target_dS_cm = target_S_cm
      5. Lc_grid = tip_depth - CDM_top_depth (tính từ tự nhiên HK đại diện)

    Trả về {meta, points: [{E, N, elev_des, elev_nat, fill, Lc_m, ok, ref_hk, ...}]}.
    """
    db = Path(db_path) if db_path else _db_path()
    cfg = get_cdm_config(db)
    q_kPa = get_qtt_load_q(db)
    fill_h_cfg = get_qtt_fill_total_thickness(db)
    D_mm = float(cfg["D_mm"])
    s_m = float(cfg["spacing_m"])
    pattern = cfg["pattern"]
    Ec_factor = float(cfg["Ec_factor"])
    qu_kPa = float(cfg["qu_kPa"])
    a = _area_ratio(D_mm, s_m, pattern)
    Ec_kPa = Ec_factor * qu_kPa / 2.0

    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        grid_pts = con.execute("""
            SELECT easting_m, northing_m, elev_nat_m, elev_des_m
            FROM qtt_elevation_points
            WHERE elev_des_m IS NOT NULL AND elev_nat_m IS NOT NULL
        """).fetchall()
        cc_hks = con.execute("""
            SELECT b.name, b.elevation_m, b.x_coord_m AS N, b.y_coord_m AS E
            FROM boreholes b
            JOIN lab_tests lt ON lt.borehole_id = b.id
            WHERE b.name LIKE 'ND-%' AND lt.Cc IS NOT NULL AND lt.Cc > 0
            GROUP BY b.id
        """).fetchall()

    if not cc_hks:
        return {"meta": {}, "points": []}

    # Cache cho mỗi HK có Cc: soft_profile + Su + mu
    hk_cache: dict[str, dict] = {}
    for h in cc_hks:
        clay_top, H_soft = soft_profile_from_db(h["name"], db)
        if clay_top is None:
            continue
        Su, _ = _nearest_su_kpa(h["name"], clay_top, clay_top + H_soft, db)
        try:
            ip = get_Ip_avg_for_bh(h["name"], _SOFT_SYMBOLS_IP, db_path=db)
        except Exception:
            ip = None
        mu = bjerrum_mu(ip) if ip else 1.0
        hk_cache[h["name"]] = {
            "elev": float(h["elevation_m"]),
            "E": float(h["E"]), "N": float(h["N"]),
            "clay_top": clay_top, "H_soft": H_soft,
            "Su": Su, "mu": mu,
        }

    points_out: list[dict] = []
    for g in grid_pts:
        E_g = float(g["easting_m"])
        N_g = float(g["northing_m"])
        elev_des = float(g["elev_des_m"])
        elev_nat = float(g["elev_nat_m"])
        fill = max(0.0, elev_des - elev_nat)
        cdm_top_elev = elev_des - fill_h_cfg

        # HK Cc gần nhất
        ref_name = min(
            hk_cache.keys(),
            key=lambda n: (hk_cache[n]["E"] - E_g) ** 2
                          + (hk_cache[n]["N"] - N_g) ** 2,
        )
        ref = hk_cache[ref_name]
        ref_d = math.hypot(ref["E"] - E_g, ref["N"] - N_g)

        # Độ sâu CDM_top từ tự nhiên LOCAL (đo từ elev_nat của grid)
        # CDM_top_depth_from_local = elev_nat - cdm_top_elev
        cdm_top_depth_local = elev_nat - cdm_top_elev

        # Tính Lc với HK đại diện. clay_top theo HK đại diện (giữ profile),
        # nhưng tip_depth tính từ tự nhiên local
        try:
            r = find_cdm_length(
                ref_name, q_kPa=q_kPa, a=a, Ec_kPa=Ec_kPa,
                Su_kPa=ref["Su"], target_dS_cm=target_S_cm,
                h_clay_m=ref["H_soft"], clay_top_depth_m=ref["clay_top"],
                L_step_m=0.5, mu=ref["mu"], t_years_residual=15.0, gwl_elev_m=GWL_ELEV_QTT,
                db_path=db,
            )
            p_opt = r.get("p_optimal_m")
            tip = r.get("tip_depth_m")
            ok = bool(r.get("ok"))
            # Lc đo từ tự nhiên local (gần đúng — ref soil profile)
            Lc = (
                round(float(tip) - cdm_top_depth_local, 2)
                if tip is not None else None
            )
            S_total = r.get("S_total_cm")
        except Exception:
            Lc = None; ok = False; S_total = None; p_opt = None; tip = None

        points_out.append({
            "E": E_g, "N": N_g,
            "elev_des": elev_des, "elev_nat": elev_nat,
            "fill_m": round(fill, 2),
            "cdm_top_elev": round(cdm_top_elev, 2),
            "ref_hk": ref_name,
            "ref_dist_m": round(ref_d, 1),
            "Lc_m": Lc, "ok": ok,
            "S_total_cm": S_total,
            "tip_depth_m": tip,
        })

    return {
        "meta": {
            "target_S_cm": target_S_cm,
            "q_kPa": q_kPa, "a": round(a, 4), "Ec_kPa": round(Ec_kPa, 0),
            "fill_thickness_m": fill_h_cfg,
            "n_grid": len(points_out),
            "n_ref_hk": len(hk_cache),
        },
        "points": points_out,
    }


def cluster_grid_into_zones(
    grid_points: list[dict], n_zones: int = 4,
) -> dict:
    """Phân vùng grid theo Lc thành n_zones nhóm bằng quantile.

    Trả về:
      bins: list[(Lc_low, Lc_high)] — n_zones khoảng
      assignment: dict[(E,N)] → zone_id (0..n_zones-1)
      stats: list[{zone_id, Lc_min, Lc_max, n_points, area_m2, Lc_design}]
    """
    Lcs = sorted(
        p["Lc_m"] for p in grid_points if p.get("Lc_m") is not None and p.get("ok")
    )
    if not Lcs:
        return {"bins": [], "assignment": {}, "stats": []}

    # Quantile breaks
    n = len(Lcs)
    breaks = [Lcs[int(n * k / n_zones)] for k in range(1, n_zones)]
    breaks = [Lcs[0]] + breaks + [Lcs[-1]]
    # Remove duplicate breaks
    breaks_unique = sorted(set(round(b, 1) for b in breaks))
    if len(breaks_unique) < 2:
        return {"bins": [(breaks[0], breaks[-1])],
                "assignment": {(p["E"], p["N"]): 0 for p in grid_points},
                "stats": [{"zone_id": 0,
                           "Lc_min": breaks[0], "Lc_max": breaks[-1],
                           "n_points": len(grid_points),
                           "Lc_design": breaks[-1]}]}
    bins = list(zip(breaks_unique[:-1], breaks_unique[1:]))

    assignment: dict[tuple, int] = {}
    for p in grid_points:
        Lc = p.get("Lc_m")
        if Lc is None or not p.get("ok"):
            continue
        z = 0
        for k, (lo, hi) in enumerate(bins):
            if Lc <= hi + 1e-6:
                z = k
                break
        else:
            z = len(bins) - 1
        assignment[(p["E"], p["N"])] = z

    # Stats per zone
    stats = []
    for k, (lo, hi) in enumerate(bins):
        pts_zone = [p for p in grid_points
                    if assignment.get((p["E"], p["N"])) == k]
        if not pts_zone:
            continue
        Lcs_z = [p["Lc_m"] for p in pts_zone]
        # Diện tích ≈ n_points × 20m × 20m (grid step)
        area = len(pts_zone) * 20 * 20
        stats.append({
            "zone_id": k,
            "Lc_min": round(min(Lcs_z), 1),
            "Lc_max": round(max(Lcs_z), 1),
            "n_points": len(pts_zone),
            "area_m2": area,
            # Lc thiết kế = max của vùng (an toàn)
            "Lc_design": round(max(Lcs_z), 1),
        })
    return {"bins": bins, "assignment": assignment, "stats": stats}


if __name__ == "__main__":
    import json
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

    print("=== compute_cdm_lc_matrix ===")
    res = compute_cdm_lc_matrix()
    print(f"Meta: q={res['meta']['q_kPa']}kPa  "
          f"D={res['meta']['D_mm']}mm s={res['meta']['spacing_m']}m  "
          f"a={res['meta']['a']:.4f}  Ec={res['meta']['Ec_kPa']:.0f}kPa  "
          f"fill_h={res['meta']['fill_thickness_m']}m")
    print()
    for h in res["hks"]:
        print(f"  {h['name']}: nat={h['nat']} des={h['design']} "
              f"CDM_top_depth={h['cdm_top_depth_m']}m exc={h['excavation_m']}m  "
              f"Cc_src={h['cc_source']}({'mượn' if h['borrowed'] else 'gốc'}) "
              f"μ={h['mu']} Su={h.get('Su_kPa')} Es={h.get('Es_kPa')}kPa")
        for dS, r in h["by_dS"].items():
            Lc = r.get("Lc_m"); S = r.get("S_total_cm")
            mark = "OK" if r.get("ok") else "FAIL"
            print(f"     ΔS={dS:.0f}cm: Lc={Lc}m  S={S}cm  [{mark}]")
        print()
