"""
CDM column analysis per TCVN 9403:2012.
Formulas: Appendix B (bearing capacity), Appendix C (settlement).
Cross-checks against settlement_calc.py CDM branch.
"""

import math
import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "data" / "TTHC.sqlite"
_PARAMS_PATH = Path(__file__).parent.parent / "data" / "tcvn9403_params.json"

KG_CM2_TO_KPA = 98.0665


# ---------------------------------------------------------------------------
# Core CDM formulas (Appendix B & C, TCVN 9403:2012)
# ---------------------------------------------------------------------------

def calc_area_ratio(diameter_m: float, spacing_m: float, pattern: str = "triangular") -> float:
    """Tỷ lệ diện tích thay thế a = Ac/Aunit."""
    Ac = math.pi * diameter_m ** 2 / 4
    if pattern == "triangular":
        A_unit = math.sqrt(3) / 2 * spacing_m ** 2
    else:  # square
        A_unit = spacing_m ** 2
    return Ac / A_unit


def calc_Ec(Cc_col_kPa: float, factor: float = 75.0) -> float:
    """Mô đun biến dạng trụ xi măng.  Ec = factor × Cc_col (kPa).  factor ∈ [50,100]."""
    return factor * Cc_col_kPa


def calc_Es(Cu_kPa: float) -> float:
    """Mô đun biến dạng đất giữa trụ.  Es = 250 × Cu (kPa)."""
    return 250.0 * Cu_kPa


def calc_Cuu(Cu_soft_kPa: float, Cc_col_kPa: float, area_ratio: float) -> float:
    """Cường độ cắt tổ hợp — công thức B.1.
    Cuu = Cs×(1−a) + Cc×a
    Cs = Cu_soft, Cc = Cc_col = qu_field/2
    """
    return Cu_soft_kPa * (1.0 - area_ratio) + Cc_col_kPa * area_ratio


def calc_qu_field(qu_lab_kPa: float, ratio: float = 0.33) -> float:
    """Cường độ nở hông hiện trường.  qu_field = ratio × qu_lab.  ratio = 0.20–0.50."""
    return ratio * qu_lab_kPa


def calc_settlement_S1(
    q_kPa: float,
    H_m: float,
    area_ratio: float,
    Ec_kPa: float,
    Es_kPa: float,
) -> float:
    """Lún trong vùng gia cố CDM — công thức C.2.
    S1 = q×H / (a×Ec + (1−a)×Es)   →  m
    Returns S1 in cm.
    """
    composite_modulus = area_ratio * Ec_kPa + (1.0 - area_ratio) * Es_kPa
    if composite_modulus <= 0:
        return 0.0
    S1_m = q_kPa * H_m / composite_modulus
    return S1_m * 100.0  # → cm


def calc_settlement_reduction(area_ratio: float, Ec_kPa: float, Es_kPa: float) -> float:
    """Hệ số giảm lún CDM so với không xử lý (β = S_cdm / S_no_treat).
    β = Es / (a×Ec + (1−a)×Es)   — từ công thức C.2 so với S_untreated = q×H/Es
    """
    if Es_kPa <= 0:
        return 1.0
    composite_modulus = area_ratio * Ec_kPa + (1.0 - area_ratio) * Es_kPa
    return Es_kPa / composite_modulus


# ---------------------------------------------------------------------------
# Sức chịu tải cọc xi măng đất (CDM single column)
# ---------------------------------------------------------------------------

def calc_bearing_soil_ait(d_m: float, L_col_m: float, Cu_soil_kPa: float) -> dict:
    """Sức chịu tải cực hạn của 1 cọc CDM theo NỀN ĐẤT — phương pháp AIT.

        Q_ult,soil = Q_ma_sát_thành + Q_mũi
        Q_ma_sát   = π·d·L_col·Cu              (α=1, đất yếu)
        Q_mũi      = 9·Cu·A_c   với A_c = π·d²/4   (Nc = 9)

    Tương đương Q_ult,soil = (π·d·L_col + 2,25·π·d²)·Cu vì 9·A_c = 2,25·π·d².
    Cu_soil = cường độ kháng cắt SAU hiệu chỉnh Bjerrum (μ·Su). Đơn vị: d,L [m],
    Cu [kPa] → Q [kN].
    """
    import math
    A_c = math.pi * d_m ** 2 / 4.0                # tiết diện cọc (m²)
    Q_skin = math.pi * d_m * L_col_m * Cu_soil_kPa   # ma sát thành (kN)
    Q_tip  = 9.0 * Cu_soil_kPa * A_c                 # sức kháng mũi Nc=9 (kN)
    Q = Q_skin + Q_tip
    return {
        "Q_ult_soil_kN": round(Q, 1),
        "Q_skin_kN": round(Q_skin, 1),
        "Q_tip_kN": round(Q_tip, 1),
        "skin_area_m2": round(math.pi * d_m * L_col_m, 3),
        "tip_area_m2": round(2.25 * math.pi * d_m ** 2, 3),
        "A_c_m2": round(A_c, 4),
        "Nc": 9,
        "method": "AIT",
    }


def calc_bearing_material(d_m: float, qu_col_kPa: float) -> dict:
    """Sức chịu tải theo VẬT LIỆU cọc: Q_ult,mat = qu_col·A_col, A_col = π·d²/4."""
    import math
    A_col = math.pi * d_m ** 2 / 4.0
    return {"Q_ult_material_kN": round(qu_col_kPa * A_col, 1),
            "A_col_m2": round(A_col, 4)}


def calc_cdm_pile_capacity(d_m: float, L_col_m: float, Cu_soil_kPa: float,
                           qu_col_kPa: float, FS: float = 2.5) -> dict:
    """Sức chịu tải thiết kế 1 cọc CDM = min(theo nền AIT, theo vật liệu)/FS."""
    soil = calc_bearing_soil_ait(d_m, L_col_m, Cu_soil_kPa)
    mat  = calc_bearing_material(d_m, qu_col_kPa)
    Q_ult = min(soil["Q_ult_soil_kN"], mat["Q_ult_material_kN"])
    governs = "nền đất" if soil["Q_ult_soil_kN"] <= mat["Q_ult_material_kN"] else "vật liệu"
    return {
        **soil, **mat,
        "Q_ult_min_kN": round(Q_ult, 1),
        "governs": governs,
        "FS": FS,
        "Q_allow_kN": round(Q_ult / FS, 1) if FS > 0 else None,
    }


# ---------------------------------------------------------------------------
# QC sample adequacy (Bảng B.1, TCVN 9403:2012)
# ---------------------------------------------------------------------------

_QC_TABLE = [
    (100,   2,  5),
    (500,   5,  10),
    (1000,  10, 30),
    (2000,  15, 50),
    (None,  20, 100),
]


def required_qc_samples(n_columns: int) -> dict:
    """Số mẫu thí nghiệm tối thiểu per Bảng B.1 TCVN 9403:2012."""
    for max_col, lab, field in _QC_TABLE:
        if max_col is None or n_columns <= max_col:
            return {"lab_samples_per_layer": lab, "field_tests": field}
    return {"lab_samples_per_layer": 20, "field_tests": 100}


def check_qc_adequacy(n_columns: int, n_lab_actual: int, n_field_actual: int) -> dict:
    """So sánh số mẫu hiện có với yêu cầu Bảng B.1."""
    req = required_qc_samples(n_columns)
    return {
        "n_columns": n_columns,
        "required_lab": req["lab_samples_per_layer"],
        "required_field": req["field_tests"],
        "actual_lab": n_lab_actual,
        "actual_field": n_field_actual,
        "lab_ok": n_lab_actual >= req["lab_samples_per_layer"],
        "field_ok": n_field_actual >= req["field_tests"],
        "lab_gap": max(0, req["lab_samples_per_layer"] - n_lab_actual),
        "field_gap": max(0, req["field_tests"] - n_field_actual),
    }


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_conn(db_path: Path = _DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_cdm_lab_results(zone_code: str | None = None) -> list[dict]:
    """Lấy kết quả thí nghiệm nén mẫu CDM từ TTHC.sqlite."""
    conn = _get_conn()
    if zone_code:
        rows = conn.execute(
            "SELECT * FROM cdm_lab_results WHERE zone_code = ? ORDER BY cement_pct, age_days",
            (zone_code,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM cdm_lab_results ORDER BY zone_code, cement_pct, age_days"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_cdm_lab_result(
    zone_code: str,
    sample_id: str,
    soil_type: str,
    mixing_method: str,
    cement_pct: float,
    w_c_ratio: float | None,
    age_days: int,
    qu_kPa: float,
    notes: str = "",
) -> int:
    """Lưu kết quả thí nghiệm mẫu CDM vào TTHC.sqlite. Trả về rowid."""
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO cdm_lab_results
           (zone_code, sample_id, soil_type, mixing_method, cement_pct,
            w_c_ratio, age_days, qu_kPa, notes, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,datetime('now','localtime'))""",
        (zone_code, sample_id, soil_type, mixing_method,
         cement_pct, w_c_ratio, age_days, qu_kPa, notes),
    )
    conn.commit()
    rowid = cur.lastrowid or 0
    conn.close()
    return rowid


def get_cdm_design(zone_code: str | None = None) -> list[dict]:
    """Lấy kết quả thiết kế CDM từ TTHC.sqlite."""
    conn = _get_conn()
    if zone_code:
        rows = conn.execute(
            "SELECT * FROM cdm_design WHERE zone_code = ? ORDER BY id",
            (zone_code,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM cdm_design ORDER BY zone_code, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_cdm_design(
    zone_code: str,
    scenario_label: str,
    diameter_m: float,
    spacing_m: float,
    pattern: str,
    area_ratio: float,
    cement_pct: float,
    qu_lab_kPa: float,
    qu_field_kPa: float,
    Cc_col_kPa: float,
    Cu_soft_kPa: float,
    Ec_kPa: float,
    Es_kPa: float,
    Cuu_kPa: float,
    H_cdm_m: float,
    q_kPa: float,
    S1_cm: float,
    S_reduction: float,
) -> int:
    """Lưu kịch bản thiết kế CDM. Trả về rowid."""
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO cdm_design
           (zone_code, scenario_label, diameter_m, spacing_m, pattern,
            area_ratio, cement_pct, qu_lab_kPa, qu_field_kPa, Cc_col_kPa,
            Cu_soft_kPa, Ec_kPa, Es_kPa, Cuu_kPa, H_cdm_m, q_kPa,
            S1_cm, S_reduction, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))""",
        (zone_code, scenario_label, diameter_m, spacing_m, pattern,
         area_ratio, cement_pct, qu_lab_kPa, qu_field_kPa, Cc_col_kPa,
         Cu_soft_kPa, Ec_kPa, Es_kPa, Cuu_kPa, H_cdm_m, q_kPa,
         S1_cm, S_reduction),
    )
    conn.commit()
    rowid = cur.lastrowid or 0
    conn.close()
    return rowid


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def analyze_lab_results(zone_code: str | None = None) -> dict:
    """Thống kê qu theo hàm lượng xi măng và tuổi mẫu."""
    rows = get_cdm_lab_results(zone_code)
    if not rows:
        return {}

    from collections import defaultdict
    groups: dict[tuple, list[float]] = defaultdict(list)
    for r in rows:
        key = (r["cement_pct"], r["age_days"])
        groups[key].append(r["qu_kPa"])

    result = {}
    for (cement_pct, age_days), vals in sorted(groups.items()):
        key = f"{cement_pct}%XM_{age_days}d"
        result[key] = {
            "cement_pct": cement_pct,
            "age_days": age_days,
            "n": len(vals),
            "qu_mean_kPa": round(sum(vals) / len(vals), 1),
            "qu_min_kPa": round(min(vals), 1),
            "qu_max_kPa": round(max(vals), 1),
        }
    return result


def estimate_design_strength(
    qu_lab_kPa: float,
    ratio: float = 0.33,
    Ec_factor: float = 75.0,
) -> dict:
    """Tính chuỗi cường độ từ qu_lab đến Ec thiết kế."""
    qu_field = calc_qu_field(qu_lab_kPa, ratio)
    Cc_col = qu_field / 2.0
    Ec = calc_Ec(Cc_col, Ec_factor)
    return {
        "qu_lab_kPa": round(qu_lab_kPa, 1),
        "field_lab_ratio": ratio,
        "qu_field_kPa": round(qu_field, 1),
        "Cc_col_kPa": round(Cc_col, 1),
        "Ec_factor": Ec_factor,
        "Ec_kPa": round(Ec, 0),
    }


def full_cdm_design(
    zone_code: str,
    Cu_soft_kPa: float,
    H_soft_m: float,
    H_fill_m: float = 3.0,
    gamma_fill: float = 20.0,
    diameter_m: float = 0.6,
    spacing_m: float = 2.0,
    pattern: str = "triangular",
    cement_pct: float = 12.0,
    qu_lab_kPa: float = 400.0,
    field_lab_ratio: float = 0.33,
    Ec_factor: float = 75.0,
) -> dict:
    """Thiết kế đầy đủ CDM: tỷ lệ diện tích, cường độ, lún S1, hệ số giảm lún."""
    a = calc_area_ratio(diameter_m, spacing_m, pattern)
    strength = estimate_design_strength(qu_lab_kPa, field_lab_ratio, Ec_factor)
    Cc_col = strength["Cc_col_kPa"]
    Ec = strength["Ec_kPa"]
    Es = calc_Es(Cu_soft_kPa)
    Cuu = calc_Cuu(Cu_soft_kPa, Cc_col, a)
    q = gamma_fill * H_fill_m
    S1_cm = calc_settlement_S1(q, H_soft_m, a, Ec, Es)
    beta = calc_settlement_reduction(a, Ec, Es)

    return {
        "zone_code": zone_code,
        "diameter_m": diameter_m,
        "spacing_m": spacing_m,
        "pattern": pattern,
        "area_ratio": round(a, 4),
        "cement_pct": cement_pct,
        "qu_lab_kPa": qu_lab_kPa,
        "qu_field_kPa": strength["qu_field_kPa"],
        "Cc_col_kPa": round(Cc_col, 1),
        "Cu_soft_kPa": Cu_soft_kPa,
        "Ec_kPa": round(Ec, 0),
        "Es_kPa": round(Es, 0),
        "Cuu_kPa": round(Cuu, 1),
        "H_cdm_m": H_soft_m,
        "q_kPa": round(q, 1),
        "S1_cm": round(S1_cm, 1),
        "S_reduction": round(beta, 3),
        "S_reduction_pct": round((1.0 - beta) * 100, 1),
    }


# ---------------------------------------------------------------------------
# Schema creation (idempotent)
# ---------------------------------------------------------------------------

def create_cdm_tables(db_path: Path = _DB_PATH) -> None:
    """Tạo bảng cdm_design và cdm_lab_results nếu chưa có."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cdm_design (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_code       TEXT NOT NULL,
            scenario_label  TEXT,
            diameter_m      REAL,
            spacing_m       REAL,
            pattern         TEXT,
            area_ratio      REAL,
            cement_pct      REAL,
            qu_lab_kPa      REAL,
            qu_field_kPa    REAL,
            Cc_col_kPa      REAL,
            Cu_soft_kPa     REAL,
            Ec_kPa          REAL,
            Es_kPa          REAL,
            Cuu_kPa         REAL,
            H_cdm_m         REAL,
            q_kPa           REAL,
            S1_cm           REAL,
            S_reduction     REAL,
            created_at      TEXT
        );

        CREATE TABLE IF NOT EXISTS cdm_lab_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_code       TEXT NOT NULL,
            sample_id       TEXT,
            soil_type       TEXT,
            mixing_method   TEXT,
            cement_pct      REAL,
            w_c_ratio       REAL,
            age_days        INTEGER,
            qu_kPa          REAL,
            notes           TEXT,
            created_at      TEXT
        );
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# (Đã gỡ) crosscheck_settlement_calc — dùng hệ số giảm lún (1 − a×0.85) không có
# cơ sở vật lý (CLAUDE.md §28). Tính lún CDM chính thức = S1 (calc_settlement_S1,
# TCVN 9403 Phụ lục C) + S2 (settlement_calc.calc_s2_below_cdm). Không dùng lại
# công thức giảm lún tuyến tính này.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Tạo bảng
    create_cdm_tables()
    print("Tables created OK")

    # 2. Thiết kế mẫu — zone NHC
    import json
    params_path = Path(__file__).parent.parent / "data" / "tcvn9403_params.json"
    with open(params_path, encoding="utf-8") as f:
        params = json.load(f)

    zone_params = params["project_cdm_defaults"]
    result = full_cdm_design(
        zone_code="NHC",
        Cu_soft_kPa=16.0,
        H_soft_m=35.0,
        H_fill_m=3.0,
        diameter_m=zone_params["column_diameter_mm"] / 1000,
        spacing_m=zone_params["column_spacing_m"],
        cement_pct=zone_params["cement_content_pct"],
        qu_lab_kPa=zone_params["qu_lab_design_kPa"],
    )
    print("\n--- CDM Design (NHC) ---")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # 3. QC adequacy example
    qc = check_qc_adequacy(n_columns=800, n_lab_actual=8, n_field_actual=25)
    print("\n--- QC Adequacy (800 columns) ---")
    for k, v in qc.items():
        print(f"  {k}: {v}")

    # (4. Cross-check đã gỡ — xem ghi chú công thức 1−a×0.85 phía trên)
