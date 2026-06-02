"""
cdm_cushion_params.py — Thông số đệm cát-xi măng dự án TTHC + ALiCC engine.

Số liệu VERIFY từ hồ sơ TTHC bảng E.2 (user xác nhận 2026-05-29):
  q_uckse = 600 kPa
  Fs (chọc thủng) = 3.0
  τ_ase = q_uckse/(2·Fs) = 100 kPa
  θ = 80°

Hàm chính: check_alicc(Hse) → dict với τ_se, τ_ase, ratio, ok.
"""
from __future__ import annotations
import math
import sqlite3
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DB = _ROOT / "data" / "TTHC.sqlite"
_DB_LOCAL = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")

# ════════ HẰNG SỐ DỰ ÁN TTHC (verify từ hồ sơ) ════════
Q_UCKSE_KPA = 600.0          # cường độ kháng nén đệm cát-XM
FS_PUNCHING = 3.0            # hệ số an toàn cắt
TAU_ASE_KPA = 100.0          # ứng suất cắt cho phép = q_uckse/(2·Fs)
THETA_DEG = 80.0             # góc đàn hồi dẻo
GAMMA_HSE = 22.5             # dung trọng đệm (kN/m³)
GAMMA_HE = 18.0              # dung trọng cát He (kN/m³)
GAMMA_AOD = 24.0             # dung trọng áo đường (kN/m³)
H_AOD = 0.80                 # bề dày áo đường (cố định)
SIGMA_H_TOTAL = 1.90         # tổng chiều dày đắp (cố định)

# CDM geometry (verify từ tvtk_cdm_config)
D_CDM = 0.80                 # đường kính trụ
S_CDM = 1.80                 # khoảng cách tâm (lưới vuông)


def _db_path() -> Path:
    return _DB_LOCAL if _DB_LOCAL.exists() else _DB


def load_params_from_db(db_path: Path | None = None) -> dict:
    """Đọc params hiện tại từ SQLite (cdm_cushion_design_params)."""
    db = db_path or _db_path()
    if not db.exists():
        return {}
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT param_key, param_value FROM cdm_cushion_design_params"
            ).fetchall()
            return {r["param_key"]: r["param_value"] for r in rows}
        except sqlite3.OperationalError:
            return {}


def check_alicc(
    Hse: float,
    q_uckse: float = Q_UCKSE_KPA,
    Fs: float = FS_PUNCHING,
    theta_deg: float = THETA_DEG,
    D: float = D_CDM,
    s: float = S_CDM,
    gamma_he: float = GAMMA_HE,
    gamma_aod: float = GAMMA_AOD,
    gamma_hse: float = GAMMA_HSE,
    sigma_h: float = SIGMA_H_TOTAL,
    h_aod: float = H_AOD,
    q_a: float = 0.0,
) -> dict:
    """Kiểm tra chọc thủng đệm cát-XM theo ALiCC PWRI.

    γ_fill = TB trọng số của (áo đường + He) — đất đắp TRÊN đệm.
    Returns dict với τ_se, τ_ase, ratio, ok, và các trung gian.
    """
    He = sigma_h - h_aod - Hse           # cát He bù lại
    He_total = h_aod + He                # đất đắp trên đệm cho ALiCC
    # γ_fill = TB trọng số (áo đường + He)
    gamma_fill = (h_aod * gamma_aod + He * gamma_he) / He_total if He_total > 0 else gamma_he

    theta = math.radians(theta_deg)
    tan_t = math.tan(theta)
    tan_half = math.tan(theta / 2)
    H0 = (s - D) * tan_half

    # V_soil theo CT(1) hoặc CT(2)
    if H0 <= He_total:
        case = "CT(1)"
        V_soil = ((s - D) / 2 * s**2 - math.pi * (s**3 - D**3) / 24
                   + (4 - math.pi) * (math.sqrt(2) - 1) * s**3 / 24) * tan_t
    else:
        case = "CT(2)"
        r0 = He_total / tan_t + D / 2
        V_soil = (He_total * s**2
                   - (math.pi * r0**2 * (He_total + D / 2 * tan_t)
                      - math.pi * D / 2 * tan_t) / 3)

    # V_CGCXM (đệm)
    r_mat = Hse / tan_t + D / 2
    V_CGCXM = (Hse * s**2
                - (math.pi * r_mat**2 * (Hse + D / 2 * tan_t)
                   - math.pi * D / 2 * tan_t) / 3)

    A_unit = s**2 - math.pi * D**2 / 4
    P_soil = ((V_soil - V_CGCXM) * gamma_fill + V_CGCXM * gamma_hse) / A_unit
    tau_se = (P_soil - q_a) * A_unit / (math.pi * D * Hse)
    tau_ase = q_uckse / (2.0 * Fs)
    ratio = tau_se / tau_ase if tau_ase > 0 else float("inf")

    return {
        "Hse_m": Hse,
        "He_m": He,
        "He_total_m": He_total,
        "gamma_fill_TB": gamma_fill,
        "H0_m": H0,
        "case": case,
        "V_soil_m3": V_soil,
        "V_CGCXM_m3": V_CGCXM,
        "A_unit_m2": A_unit,
        "P_soil_kPa": P_soil,
        "tau_se_kPa": tau_se,
        "tau_ase_kPa": tau_ase,
        "ratio": ratio,
        "ok": ratio <= 1.0,
        "q_uckse_kPa": q_uckse,
        "Fs": Fs,
    }


def find_Hse_min(target_ratio: float = 1.0,
                  q_uckse: float = Q_UCKSE_KPA,
                  Fs: float = FS_PUNCHING,
                  Hse_lo: float = 0.10, Hse_hi: float = 2.0,
                  tol: float = 0.005) -> float:
    """Bisection tìm Hse min để τ_se/τ_ase ≤ target_ratio."""
    while Hse_hi - Hse_lo > tol:
        mid = (Hse_lo + Hse_hi) / 2
        r = check_alicc(mid, q_uckse=q_uckse, Fs=Fs)
        if r["ratio"] <= target_ratio:
            Hse_hi = mid
        else:
            Hse_lo = mid
    return round(Hse_hi, 3)


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

    print("=" * 60)
    print(f"ALiCC kiểm chọc thủng đệm cát-XM TTHC (số liệu hồ sơ E.2)")
    print(f"  q_uckse = {Q_UCKSE_KPA} kPa, Fs = {FS_PUNCHING}, θ = {THETA_DEG}°")
    print(f"  τ_ase = {TAU_ASE_KPA} kPa")
    print("=" * 60)
    print(f"{'Hse (m)':<10s}{'τ_se (kPa)':<14s}{'ratio':<10s}{'ok':<6s}")
    for Hse in [0.20, 0.30, 0.40, 0.48, 0.50, 0.60, 0.70]:
        r = check_alicc(Hse)
        mark = "Đạt" if r["ok"] else "KĐ"
        print(f"{Hse:<10.2f}{r['tau_se_kPa']:<14.1f}{r['ratio']:<10.3f}{mark:<6s}")
    print()
    Hse_min = find_Hse_min()
    print(f"Hse_min (ratio = 1.0): {Hse_min:.3f} m")
    print(f"Hse hiện tại = 0.40m → KHÔNG ĐẠT, cần tăng lên ≥ {Hse_min:.2f}m")
