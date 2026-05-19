"""
settlement_calc.py — Tính lún cố kết theo TCCS 41:2022/TCĐBVN

Công thức từ Điều 9, Phụ lục A, B, D.
Engine thuần Python — không phụ thuộc pandas/numpy để có thể gọi từ Streamlit.

Hàm public:
  calc_settlement_from_db(bh_name, H_fill_m, method, **kwargs) -> dict
  calc_time_series(params, t_months_list) -> list[dict]
  compare_methods(bh_name, H_fill_m, zone_params) -> list[dict]
  check_samples_vs_tccs41(zone_code) -> dict
"""

from __future__ import annotations
import math
import sqlite3
import json
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
_DB   = _ROOT / "data" / "TTHC.sqlite"
_CFG  = _ROOT / "data" / "tccs41_params.json"

GAMMA_W = 9.81          # kN/m³
CM2_S_TO_M2_YR = 3.1536e7 / 1e4   # 1 cm²/s = 3 153.6 m²/yr


# ──────────────────────────────────────────────────────────────────
# 1. ĐỌC DỮ LIỆU TỪ SQLite
# ──────────────────────────────────────────────────────────────────

def _db():
    return sqlite3.connect(_DB)


def load_consol_samples(bh_name: str) -> list[dict]:
    """Trả về danh sách mẫu nén cố kết của hố khoan, sắp xếp theo chiều sâu."""
    with _db() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT lt.depth_from_m, lt.depth_to_m,
                   lt.Cc, lt.Cs, lt.e0, lt.Cv_cm2s,
                   lt.k_cm_s, lt.PC_kPa, lt.gamma_kNm3, lt.w_pct
            FROM lab_tests lt
            JOIN boreholes b ON lt.borehole_id = b.id
            WHERE b.name = ?
              AND lt.Cc IS NOT NULL
            ORDER BY lt.depth_from_m
        """, (bh_name,)).fetchall()
    return [dict(r) for r in rows]


def load_all_lab_tests(bh_name: str) -> list[dict]:
    """Trả về tất cả mẫu lab (kể cả không có Cc) — dùng cho phân tích mẫu."""
    with _db() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT lt.depth_from_m, lt.depth_to_m,
                   lt.Cc, lt.Cs, lt.e0, lt.Cv_cm2s, lt.PC_kPa,
                   lt.gamma_kNm3, lt.phi_deg, lt.c_kPa, lt.Cu_UU_kPa
            FROM lab_tests lt
            JOIN boreholes b ON lt.borehole_id = b.id
            WHERE b.name = ?
            ORDER BY lt.depth_from_m
        """, (bh_name,)).fetchall()
    return [dict(r) for r in rows]


def _load_cfg() -> dict:
    with open(_CFG, encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────────────────────────
# 2. CÔNG THỨC CƠ BẢN
# ──────────────────────────────────────────────────────────────────

def calc_sigma_v0(depth_mid_m: float, gamma_sat: float,
                  gwt_depth_m: float = 0.0) -> float:
    """
    Ứng suất hữu hiệu ban đầu tại độ sâu depth_mid_m.
    Giả thiết: GWT tại gwt_depth_m, toàn bộ phía dưới bão hòa.
    """
    if depth_mid_m <= gwt_depth_m:
        return gamma_sat * depth_mid_m
    gamma_prime = gamma_sat - GAMMA_W
    sigma = gamma_sat * gwt_depth_m + gamma_prime * (depth_mid_m - gwt_depth_m)
    return max(sigma, 1.0)   # tránh log(0)


def calc_delta_sigma(H_fill_m: float, gamma_fill: float = 20.0) -> float:
    """
    Ứng suất tăng thêm do đắp (kPa).
    Dùng tải đều: Δσ = γ × H (theo TCCS41 Điều 9.1 cho B_fill >> H_soil).
    """
    return gamma_fill * H_fill_m


def calc_settlement_layer(H_i: float, e0: float, Cc: float, Cs: float,
                           sigma_v0: float, sigma_vf: float, PC: float) -> float:
    """
    Độ lún cố kết sơ cấp lớp i (m).
    Phụ lục A — TCCS 41:2022.
    """
    if sigma_vf <= sigma_v0 or H_i <= 0:
        return 0.0
    if e0 <= 0:
        e0 = 1.0
    if PC is None or PC <= 0:
        PC = sigma_v0 * 1.2   # giả thiết OCR=1.2 nếu không có PC

    if sigma_vf <= PC:
        # Quá cố kết hoàn toàn
        S = H_i * Cs / (1 + e0) * math.log10(sigma_vf / sigma_v0)
    elif sigma_v0 < PC:
        # Cắt qua áp lực tiền cố kết
        S = H_i * (
            Cs / (1 + e0) * math.log10(PC / sigma_v0) +
            Cc / (1 + e0) * math.log10(sigma_vf / PC)
        )
    else:
        # Bình thường cố kết
        S = H_i * Cc / (1 + e0) * math.log10(sigma_vf / sigma_v0)
    return max(S, 0.0)


def calc_Uv(Tv: float) -> float:
    """Độ cố kết phương đứng Uv từ nhân tố thời gian Tv (TCCS41 Điều 9.3)."""
    if Tv <= 0:
        return 0.0
    if Tv < 0.217:   # Uv < ~52.6%
        Uv = 2.0 * math.sqrt(Tv / math.pi)
    else:
        Uv = 1.0 - (8.0 / math.pi ** 2) * math.exp(-math.pi ** 2 * Tv / 4.0)
    return min(Uv, 0.9999)


def calc_Uh(Ch_m2yr: float, t_yr: float, de_m: float, dw_m: float,
             smear_ratio: float = 2.0, kh_ks: float = 3.0) -> float:
    """
    Độ cố kết phương ngang Uh — bấc thấm hoặc giếng cát.
    Công thức 38 TCCS41 Điều 7.5.1 (có smear).

    Ch_m2yr: hệ số cố kết ngang (m²/năm)
    de_m   : đường kính ảnh hưởng (m)
    dw_m   : đường kính bấc/giếng tương đương (m)
    """
    if de_m <= 0 or dw_m <= 0 or t_yr <= 0:
        return 0.0
    n = de_m / dw_m
    s = smear_ratio
    if s >= n:
        s = max(1.5, n / 2)
    Fn = math.log(n / s) + kh_ks * math.log(s) - 0.75
    if Fn <= 0.01:
        Fn = max(math.log(n) - 0.75, 0.01)
    Th = Ch_m2yr * t_yr / de_m ** 2
    Uh = 1.0 - math.exp(-8.0 * Th / Fn)
    return min(max(Uh, 0.0), 0.9999)


def calc_combined_U(Uv: float, Uh: float) -> float:
    """Độ cố kết kết hợp U = 1 − (1−Uv)(1−Uh) — TCCS41 công thức 38."""
    return 1.0 - (1.0 - Uv) * (1.0 - Uh)


def calc_cdm_stress_beta(zone_params: dict, area_ratio: Optional[float] = None) -> float:
    """
    Hệ số phân bổ ứng suất vào đất giữa cột CDM — TCVN 9403:2012 Phụ lục C.
    beta = Es / (a*Ec + (1-a)*Es)

    Ứng suất thực trong đất = Delta_sigma * beta.
    Khi Ec >> Es: beta → 0 (cột chịu gần hết tải → đất lún ít).
    Khi Ec = Es: beta = 1 (CDM không giúp gì về lún).
    """
    a   = area_ratio if area_ratio is not None else zone_params.get("cdm_area_ratio", 0.25)
    Cu  = zone_params.get("Cu_avg_kPa", 15.0)
    qu_lab = zone_params.get("cdm_qu_lab_kPa", 1000.0)
    f   = zone_params.get("cdm_field_lab_ratio", 0.33)
    Ef  = zone_params.get("cdm_Ec_factor", 75.0)
    Es  = 250.0 * Cu                 # Mesri: Es = 250 Cu
    Cc_col = f * qu_lab / 2.0        # Cc = qu_field/2
    Ec  = Ef * Cc_col                # Ec = (50-100)*Cc_col per TCVN 9403
    denom = a * Ec + (1.0 - a) * Es
    return min(Es / denom, 1.0) if denom > 0 else 1.0


# ──────────────────────────────────────────────────────────────────
# 3. TÍNH LÚN TỔNG TỪ DB
# ──────────────────────────────────────────────────────────────────

def calc_settlement_from_db(bh_name: str,
                             H_fill_m: float = 3.0,
                             gamma_fill: float = 20.0,
                             gwt_depth_m: float = 0.0,
                             fallback_zone_params: Optional[dict] = None,
                             stress_scale: float = 1.0,
                             ) -> dict:
    """
    stress_scale: nhân với Delta_sigma trước khi tính lún.
    = 1.0: không xử lý (mặc định)
    = beta (< 1): CDM — stress sharing theo TCVN 9403 C.2
    """
    """
    Tính tổng lún sơ cấp cho hố khoan từ dữ liệu lab_tests.

    Trả về:
      {
        'S_total_m': float,
        'S_total_cm': float,
        'layers': [{'depth_mid', 'H_i', 'sigma_v0', 'sigma_vf', 'PC', 'Si_cm', 'OC_status'}]
        'n_layers': int,
        'delta_sigma': float,
        'warning': str | None
      }
    """
    samples = load_consol_samples(bh_name)
    delta_sigma = calc_delta_sigma(H_fill_m, gamma_fill) * stress_scale

    if not samples and fallback_zone_params:
        return _calc_settlement_zone_avg(fallback_zone_params, H_fill_m, gamma_fill,
                                         gwt_depth_m, stress_scale=stress_scale)

    if not samples:
        return {
            "S_total_m": None, "S_total_cm": None, "layers": [],
            "n_layers": 0, "delta_sigma": delta_sigma,
            "warning": "Không có mẫu nén cố kết cho hố khoan này"
        }

    S_total = 0.0
    layers_out = []
    warning = None

    # Tính chiều dày đại diện theo boundary trung điểm giữa các mẫu
    # Mỗi mẫu đại diện cho vùng từ midpoint trên → midpoint dưới
    d_mids = [(s["depth_from_m"] + (s["depth_to_m"] or s["depth_from_m"] + 1.0)) / 2.0
              for s in samples]
    bounds = [0.0]
    for i in range(len(d_mids) - 1):
        bounds.append((d_mids[i] + d_mids[i + 1]) / 2.0)
    # Lớp cuối: kéo dài thêm khoảng cách giống lớp trước (hoặc 5m nếu chỉ 1 mẫu)
    last_gap = (d_mids[-1] - bounds[-1]) if len(d_mids) > 1 else 5.0
    bounds.append(min(d_mids[-1] + last_gap, d_mids[-1] + 10.0))

    for i, s in enumerate(samples):
        H_i   = bounds[i + 1] - bounds[i]
        d_mid = d_mids[i]

        gamma_sat = s["gamma_kNm3"] or 16.5
        Cc   = s["Cc"] or 0.48
        Cs   = s["Cs"] or (Cc * 0.18)
        e0   = s["e0"] or 1.5
        PC   = s["PC_kPa"]

        sigma_v0 = calc_sigma_v0(d_mid, gamma_sat, gwt_depth_m)
        sigma_vf = sigma_v0 + delta_sigma

        if PC is None:
            oc_status = "unknown"
            warning = "Một số mẫu thiếu PC_kPa — giả thiết gần NC"
            PC_use = sigma_v0 * 0.9
        else:
            PC_use = PC
            if sigma_vf <= PC_use:
                oc_status = "OC"
            elif sigma_v0 < PC_use:
                oc_status = "cross_PC"
            else:
                oc_status = "NC"

        Si = calc_settlement_layer(H_i, e0, Cc, Cs, sigma_v0, sigma_vf, PC_use)
        S_total += Si

        layers_out.append({
            "depth_mid_m":  round(d_mid, 1),
            "H_i_m":        round(H_i, 1),
            "sigma_v0_kPa": round(sigma_v0, 1),
            "sigma_vf_kPa": round(sigma_vf, 1),
            "PC_kPa":       round(PC_use, 1) if PC_use else None,
            "Cc": round(Cc, 3), "Cs": round(Cs, 4), "e0": round(e0, 3),
            "Si_cm":        round(Si * 100, 1),
            "OC_status":    oc_status,
        })

    return {
        "S_total_m":   round(S_total, 4),
        "S_total_cm":  round(S_total * 100, 1),
        "layers":      layers_out,
        "n_layers":    len(layers_out),
        "delta_sigma": round(delta_sigma, 1),
        "warning":     warning,
    }


def _calc_settlement_zone_avg(zone_params: dict, H_fill_m: float,
                               gamma_fill: float, gwt_depth_m: float,
                               stress_scale: float = 1.0) -> dict:
    """Tính lún dùng thông số trung bình của zone (khi không có mẫu cụ thể)."""
    delta_sigma = calc_delta_sigma(H_fill_m, gamma_fill) * stress_scale
    gamma_sat   = zone_params.get("gamma_sat_kNm3", 16.5)
    gamma_prime = gamma_sat - GAMMA_W
    Cc  = zone_params.get("Cc_avg", 0.48)
    Cs  = zone_params.get("Cs_avg", 0.09)
    e0  = zone_params.get("e0_avg", 1.50)
    PC  = zone_params.get("PC_avg_kPa", 80.0)
    d_range = zone_params.get("soft_clay_depth_m", [0, 30])
    # Chia lớp 2m
    layer_step = 2.0
    z = max(d_range[0], layer_step / 2)
    z_max = d_range[1]
    S_total = 0.0
    layers_out = []
    while z < z_max:
        H_i = min(layer_step, z_max - (z - layer_step / 2))
        sigma_v0 = gamma_sat * gwt_depth_m + gamma_prime * (z - gwt_depth_m) if z > gwt_depth_m else gamma_sat * z
        sigma_v0 = max(sigma_v0, 1.0)
        sigma_vf = sigma_v0 + delta_sigma
        Si = calc_settlement_layer(H_i, e0, Cc, Cs, sigma_v0, sigma_vf, PC)
        S_total += Si
        layers_out.append({
            "depth_mid_m": round(z, 1),
            "H_i_m": H_i,
            "sigma_v0_kPa": round(sigma_v0, 1),
            "sigma_vf_kPa": round(sigma_vf, 1),
            "PC_kPa": PC,
            "Cc": Cc, "Cs": Cs, "e0": e0,
            "Si_cm": round(Si * 100, 2),
            "OC_status": "NC" if sigma_v0 >= PC else ("cross_PC" if sigma_v0 < PC < sigma_vf else "OC"),
        })
        z += layer_step

    return {
        "S_total_m":   round(S_total, 4),
        "S_total_cm":  round(S_total * 100, 1),
        "layers":      layers_out,
        "n_layers":    len(layers_out),
        "delta_sigma": round(delta_sigma, 1),
        "warning":     "Dùng thông số trung bình zone (không có mẫu nén cố kết cụ thể)",
    }


# ──────────────────────────────────────────────────────────────────
# 4. TÍNH ĐỘ CỐ KẾT + LÚN THEO THỜI GIAN
# ──────────────────────────────────────────────────────────────────

def calc_time_series(S_total_cm: float,
                     method: str,
                     zone_params: dict,
                     t_months_list: list[float],
                     pvd_spacing_m: float = 1.2,
                     pvd_pattern: str = "triangular",
                     sd_diameter_mm: float = 400.0,
                     sd_spacing_m: float = 1.5,
                     ) -> list[dict]:
    """
    Tính S(t) cho từng phương án xử lý.

    method: 'no_treat' | 'pvd' | 'sand_drain' | 'cdm'
    S_total_cm: tổng lún THỰC TẾ của phương án (đã giảm theo CDM beta cho CDM,
                hoặc đúng bằng S_no_treat cho các phương án khác).

    Trả về: [{'t_months', 't_years', 'U_pct', 'S_cm'}]
    """
    Cv_m2yr = zone_params.get("Cv_m2yr", 138.7)
    Ch_cm2s = zone_params.get("Ch_cm2s", 6.6e-4)
    Ch_m2yr = Ch_cm2s * CM2_S_TO_M2_YR
    Hdr_m   = zone_params.get("Hdr_m", 15.0)
    drainage = zone_params.get("drainage", "two_way")
    Hdr_eff = Hdr_m / 2 if drainage == "two_way" else Hdr_m

    # S_effective = S_total_cm đã được caller điều chỉnh (CDM dùng stress-sharing)
    S_effective = S_total_cm

    result = []
    for t_m in t_months_list:
        t_yr = t_m / 12.0

        if method == "no_treat":
            Tv  = Cv_m2yr * t_yr / Hdr_eff ** 2
            Uv  = calc_Uv(Tv)
            Uh  = 0.0
            U   = Uv

        elif method == "pvd":
            Tv  = Cv_m2yr * t_yr / Hdr_eff ** 2
            Uv  = calc_Uv(Tv)
            de  = (1.05 if pvd_pattern == "triangular" else 1.13) * pvd_spacing_m
            dw  = 0.0668    # bấc thấm 100×5mm
            Uh  = calc_Uh(Ch_m2yr, t_yr, de, dw, smear_ratio=2.0, kh_ks=3.0)
            U   = calc_combined_U(Uv, Uh)

        elif method == "sand_drain":
            Tv  = Cv_m2yr * t_yr / Hdr_eff ** 2
            Uv  = calc_Uv(Tv)
            dw  = sd_diameter_mm / 1000.0
            de  = 1.05 * sd_spacing_m
            Uh  = calc_Uh(Ch_m2yr, t_yr, de, dw, smear_ratio=2.0, kh_ks=3.0)
            U   = calc_combined_U(Uv, Uh)

        elif method == "cdm":
            # CDM không thoát nước ngang; cố kết đứng trong vùng giữa các cột
            Tv  = Cv_m2yr * t_yr / Hdr_eff ** 2
            Uv  = calc_Uv(Tv)
            Uh  = 0.0
            U   = Uv

        else:
            U = 0.0

        S_t = S_effective * U
        result.append({
            "t_months":  t_m,
            "t_years":   round(t_yr, 2),
            "U_pct":     round(U * 100, 1),
            "S_cm":      round(S_t, 1),
            "Uv_pct":    round(calc_Uv(Cv_m2yr * t_yr / Hdr_eff ** 2) * 100, 1),
        })

    return result


# ──────────────────────────────────────────────────────────────────
# 5. SO SÁNH CÁC PHƯƠNG ÁN
# ──────────────────────────────────────────────────────────────────

def compare_methods(bh_name: str,
                    zone_code: str,
                    H_fill_m: float = 3.0,
                    gamma_fill: float = 20.0,
                    residual_limit_cm: float = 30.0,
                    t_construction_months: float = 6.0,
                    ) -> dict:
    """
    So sánh 5 phương án: no_treat, pvd_1.2, pvd_1.5, sand_drain, cdm.

    Trả về dict với:
      'S_total_cm': tổng lún tự nhiên
      'scenarios'  : [{'method', 'label', 'S_cm_at_construction',
                       'residual_cm', 'U_at_construction_pct',
                       't_90_months', 'feasible'}]
      'time_series': {'no_treat': [...], 'pvd': [...], ...}
    """
    cfg = _load_cfg()
    zone_params = cfg["zone_soil_params"].get(zone_code, cfg["zone_soil_params"]["NHC"])

    # Tính tổng lún từ mẫu DB
    result = calc_settlement_from_db(bh_name, H_fill_m, gamma_fill,
                                     fallback_zone_params=zone_params)
    S_total = result["S_total_cm"] or 80.0

    t_list = cfg["time_checkpoints_months"]
    scenarios_cfg = cfg["scenario_defaults"]

    scenarios_out = []
    time_series_out = {}

    # CDM: TCVN 9403 Phụ lục C — S1 đàn hồi khối gia cố + S2 bên dưới (=0 nếu CDM đến lớp cứng)
    cdm_area_ratio = zone_params.get("cdm_area_ratio", 0.25)
    cdm_beta       = calc_cdm_stress_beta(zone_params, cdm_area_ratio)
    _Cu_cdm   = zone_params.get("Cu_avg_kPa", 15.0)
    _qu_lab   = zone_params.get("cdm_qu_lab_kPa", 1000.0)
    _f_lab    = zone_params.get("cdm_field_lab_ratio", 0.33)
    _Ef       = zone_params.get("cdm_Ec_factor", 75.0)
    Es_cdm    = 250.0 * _Cu_cdm
    Ec_cdm    = _Ef * (_f_lab * _qu_lab / 2.0)
    _d_range  = zone_params.get("soft_clay_depth_m", [0, 30])
    H_soft_cdm = float(_d_range[1] - _d_range[0])
    _q_fill    = H_fill_m * gamma_fill
    _composite = cdm_area_ratio * Ec_cdm + (1.0 - cdm_area_ratio) * Es_cdm
    S_cdm_S1   = (_q_fill * H_soft_cdm / _composite) * 100.0 if _composite > 0 else S_total * 0.3
    S_cdm_S2   = 0.0  # CDM cắm đến lớp cứng — không có lún bên dưới cột
    S_cdm      = S_cdm_S1 + S_cdm_S2

    for sc in scenarios_cfg:
        method = sc["id"]
        label  = sc["label"]
        H_sur  = sc.get("H_surcharge_m", 0.0)
        pvd_s  = sc.get("pvd_spacing_m") or 1.2
        pvd_pat = sc.get("pvd_pattern", "triangular")
        sd_d   = sc.get("sd_diameter_mm") or 400.0
        sd_s   = sc.get("sd_spacing_m") or 1.5

        method_type = sc.get("method", "no_treat")

        if method_type == "cdm":
            # Lún CDM = S1 đàn hồi — xảy ra ngay lập tức (không phụ thuộc thời gian cố kết)
            ts = [{"t_months": t, "t_years": round(t / 12.0, 2),
                   "U_pct": 100.0, "S_cm": round(S_cdm, 1)}
                  for t in t_list]
            time_series_out[method] = ts
            U_constr = 100.0
            S_constr = round(S_cdm, 1)
            S_final  = round(S_cdm, 1)
            residual = 0.0
            t_90     = t_list[0]   # ngay tại điểm đầu tiên
        else:
            ts = calc_time_series(
                S_total, method_type, zone_params, t_list,
                pvd_spacing_m=pvd_s, pvd_pattern=pvd_pat,
                sd_diameter_mm=sd_d, sd_spacing_m=sd_s,
            )
            time_series_out[method] = ts

            t_idx = min(range(len(t_list)),
                        key=lambda i: abs(t_list[i] - t_construction_months))
            U_constr = ts[t_idx]["U_pct"]
            S_constr = ts[t_idx]["S_cm"]
            S_final  = ts[-1]["S_cm"]
            residual = max(S_final - S_constr, 0.0)
            t_90 = next((pt["t_months"] for pt in ts if pt["U_pct"] >= 90.0), None)

        scenarios_out.append({
            "method":            method,
            "label":             label,
            "S_total_cm":        round(S_final, 1),
            "S_at_constr_cm":    round(S_constr, 1),
            "U_at_constr_pct":   U_constr,
            "residual_cm":       round(residual, 1),
            "t_90_months":       t_90,
            "feasible":          residual <= residual_limit_cm,
            "H_surcharge_m":     H_sur,
            "cdm_beta":          round(cdm_beta, 3) if method_type == "cdm" else None,
        })

    return {
        "bh_name":            bh_name,
        "zone_code":          zone_code,
        "H_fill_m":           H_fill_m,
        "S_total_cm":         S_total,
        "S_detail":           result,
        "cdm_beta":           round(cdm_beta, 3),
        "cdm_area_ratio":     cdm_area_ratio,
        "cdm_S1_cm":          round(S_cdm_S1, 1),
        "cdm_S2_cm":          round(S_cdm_S2, 1),
        "cdm_Ec_kPa":         round(Ec_cdm, 0),
        "cdm_Es_kPa":         round(Es_cdm, 0),
        "cdm_composite_kPa":  round(_composite, 0),
        "residual_limit_cm":  residual_limit_cm,
        "t_construction_months": t_construction_months,
        "scenarios":          scenarios_out,
        "time_series":        time_series_out,
    }


# ──────────────────────────────────────────────────────────────────
# 6. KIỂM TRA SỐ LƯỢNG MẪU vs TCCS41 Điều 5.3.7
# ──────────────────────────────────────────────────────────────────

# Thông số cần kiểm tra: (cột DB, nhãn ngắn, mô tả, chỉ dùng cho lớp yếu?)
_PARAMS_537 = [
    ("Cc",        "Cc",    "He so nen",           True),
    ("Cs",        "Cs",    "He so no",             True),
    ("Cv_cm2s",   "Cv",    "He so co ket",         True),
    ("PC_kPa",    "PC",    "Ap luc tien co ket",   True),
    ("e0",        "e0",    "He so rong",            False),
    ("phi_deg",   "phi",   "Goc ma sat",            False),
    ("c_kPa",     "c",     "Luc dinh",              False),
    ("Cu_UU_kPa", "Cu",    "Suc cat UU",            False),
]

# Ký hiệu lớp đất yếu (USCS) — áp dụng yêu cầu n≥6 cho Cc/Cs/Cv/PC
_SOFT_SYMBOLS = {"CH", "CL", "MH", "ML", "CL-ML", "ML-CL",
                 "MH-OH", "CH-OH", "ML-OL"}

_MIN_SAMPLES_537 = 6  # Điều 5.3.7 TCCS 41:2022


def _std_dev(vals: list) -> float:
    """Độ lệch chuẩn mẫu δ = sqrt(Σ(Ai-Atb)²/(n-1))."""
    n = len(vals)
    if n < 2:
        return 0.0
    mean = sum(vals) / n
    return math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))


def check_samples_vs_tccs41(zone_code: str) -> dict:
    """
    Điều 5.3.7 TCCS 41:2022 — Mỗi lớp đất yếu, mỗi chỉ tiêu cần >= 6 mẫu.
    Trị số tính toán: Delta_t = Delta_tb +/- delta
      Delta_tb = trung binh so hoc
      delta    = do lech chuan mau: sqrt(sum(Ai-Atb)^2 / (n-1))

    Ket qua per layer (symbol_tcvn):
      'layers': [{
        'symbol', 'is_soft', 'n_total',
        'params': {label: {'n','mean','std','cv_pct','ok','design_min','design_max'}}
      }]
      'zone_summary': {tong hop dat/chua dat per tham so chinh}
    """
    with _db() as con:
        # Lay tat ca gia tri per mau
        rows = con.execute("""
            SELECT lt.symbol_tcvn, lt.Cc, lt.Cs, lt.Cv_cm2s, lt.PC_kPa,
                   lt.e0, lt.phi_deg, lt.c_kPa, lt.Cu_UU_kPa, lt.depth_from_m
            FROM lab_tests lt
            JOIN boreholes b ON lt.borehole_id=b.id
            JOIN zones z ON b.zone_id=z.id
            WHERE z.code=?
            ORDER BY lt.symbol_tcvn, lt.depth_from_m
        """, (zone_code,)).fetchall()

        n_vst_zone = (con.execute("""
            SELECT COUNT(v.id) FROM vane_shear_tests v
            JOIN vst_locations vl ON v.vst_loc_id=vl.id
            JOIN zones z ON vl.zone_id=z.id
            WHERE z.code=?
        """, (zone_code,)).fetchone() or [0])[0]

    # Group values by symbol
    col_names = ["symbol_tcvn", "Cc", "Cs", "Cv_cm2s", "PC_kPa",
                 "e0", "phi_deg", "c_kPa", "Cu_UU_kPa", "depth_from_m"]
    by_sym: dict = {}
    for r in rows:
        row = dict(zip(col_names, r))
        sym = row["symbol_tcvn"] or "(khong xac dinh)"
        by_sym.setdefault(sym, []).append(row)

    layers_out = []
    for sym, sample_list in sorted(by_sym.items()):
        is_soft = sym in _SOFT_SYMBOLS
        n_total = len(sample_list)
        params_out = {}

        for db_col, label, _desc, soft_only in _PARAMS_537:
            vals = [r[db_col] for r in sample_list if r[db_col] is not None]
            n = len(vals)
            if n == 0:
                params_out[label] = {"n": 0, "ok": None}
                continue
            mean = sum(vals) / n
            std  = _std_dev(vals)
            cv_pct = round(100 * std / mean, 1) if mean != 0 else 0.0
            # Chỉ áp yêu cầu n>=6 cho lớp đất yếu với thông số lún (soft_only)
            required = soft_only and is_soft
            ok = (n >= _MIN_SAMPLES_537) if required else None  # None = khong ap dung
            params_out[label] = {
                "n":           n,
                "mean":        round(mean, 4),
                "std":         round(std, 4),
                "cv_pct":      cv_pct,
                "ok":          ok,  # True/False/None
                "design_min":  round(mean - std, 4),
                "design_max":  round(mean + std, 4),
            }

        layers_out.append({
            "symbol":  sym,
            "is_soft": is_soft,
            "n_total": n_total,
            "params":  params_out,
        })

    # Tóm tắt zone: đếm lớp đất yếu đạt/chưa đạt n>=6 cho từng thông số lún chính
    lun_params = ["Cc", "Cs", "Cv", "PC"]
    zone_ok = {p: 0 for p in lun_params}
    zone_fail = {p: 0 for p in lun_params}
    for ly in layers_out:
        if not ly["is_soft"]:
            continue
        for p in lun_params:
            info = ly["params"].get(p, {})
            if info.get("ok") is True:
                zone_ok[p] += 1
            elif info.get("ok") is False:
                zone_fail[p] += 1

    n_soft = sum(1 for ly in layers_out if ly["is_soft"])

    return {
        "zone":        zone_code,
        "layers":      layers_out,
        "n_vst_zone":  n_vst_zone,
        "zone_summary": {
            "n_layers_total":  len(layers_out),
            "n_layers_soft":   n_soft,
            "min_samples_req": _MIN_SAMPLES_537,
            "params_ok":       zone_ok,
            "params_fail":     zone_fail,
        },
    }


# ──────────────────────────────────────────────────────────────────
# 7. DEMO
# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    bh = "NHC-BH-03"
    print(f"=== Tính lún cho {bh} ===")
    res = calc_settlement_from_db(bh, H_fill_m=3.0)
    print(f"S_total = {res['S_total_cm']} cm  (n_layers={res['n_layers']})")
    if res["warning"]:
        print(f"Canh bao: {res['warning']}")

    print("\n=== So sanh phuong an ===")
    cmp = compare_methods(bh, "NHC", H_fill_m=3.0)
    for sc in cmp["scenarios"]:
        t90 = f"{sc['t_90_months']} thang" if sc["t_90_months"] else ">20 nam"
        print(f"  {sc['label']:35s}  lun={sc['S_total_cm']:5.1f}cm  "
              f"du=({sc['residual_cm']:5.1f}cm)  t90={t90:15s}  "
              f"{'Dat' if sc['feasible'] else 'Khong dat'}")

    print("\n=== Kiem tra mau TCCS41 ===")
    chk = check_samples_vs_tccs41("NHC")
    s = chk["zone_summary"]
    print(f"  NHC: {s['n_pass']}/{s['n_boreholes']} ho khoan dat  "
          f"(thieu {s['total_Cc_gap']} mau Cc)")
    chk2 = check_samples_vs_tccs41("KE")
    s2 = chk2["zone_summary"]
    print(f"  KE:  {s2['n_pass']}/{s2['n_boreholes']} ho khoan dat  "
          f"(thieu {s2['total_Cc_gap']} mau Cc)")
