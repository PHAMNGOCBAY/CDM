"""
cdm_cushion_bending.py — Kiểm toán uốn lớp đệm xi măng (CDM cushion).

Công thức kiểm toán lấy từ:
  G:\\...\\R14\\Bang tinh\\R14 Trinh\\C10\\KIEM TOAN LOP BTXM C10.xls
  Section IV — Kiểm toán khả năng chịu uốn

Mô men uốn M_max tính theo NHIỀU phương pháp đề xuất (file gốc dùng PLAXIS):
  M1: Dầm đơn giản nhịp thông thuỷ        (M = q·(s-D)²/8) — conservative
  M2: Dầm đơn giản nhịp đầy đủ            (M = q·s²/8) — most conservative
  M3: Bản tựa 4 góc (Timoshenko)          (M ≈ 0,045·q·s²)
  M4: Dầm Winkler vô hạn Hetenyi (uniform) (M = q/(4·β²))
  M5: Westergaard interior load            (M = P/(2π)·(1+μ)·ln(L/b) + ...)

Tiêu chuẩn kiểm tra: σ_b = M_max / Z_se ≤ σ_ba = 0,25·q_uckse / F_sem
"""
from __future__ import annotations
import math
from typing import Dict, List

# ════════ HẰNG SỐ MẶC ĐỊNH ════════
FSEM_DEFAULT = 1.2          # Hệ số an toàn cường độ kéo khi uốn (BTXM C10)
KV_SUBGRADE_KNM3 = 23.0     # Mô đun phản lực nền (kN/m³) — đất yếu, ref C10 file
ESOIL_KPA = 23.0            # Mô đun đất nền dưới đệm (kPa)
NU_POISSON = 0.15           # Hệ số Poisson đệm cát-XM (giả thiết)


def cushion_section_props(T_m: float, q_uckse_kPa: float,
                          Fsem: float = FSEM_DEFAULT) -> Dict:
    """Đặc trưng tiết diện đệm xi măng (per 1m strip dọc theo dầm).

    Theo file BTXM C10 (rows 116, 119, 122, 125):
      I_se = T³/12           (m⁴/m)
      Z_se = T²/6            (m³/m)
      E_se = 100 · q_uckse   (kPa)
      σ_ba = 0,25·q_uckse / F_sem  (kPa) — cường độ kéo khi uốn cho phép
    """
    Ise = T_m**3 / 12.0
    Zse = T_m**2 / 6.0
    Ese = 100.0 * q_uckse_kPa
    sigma_ba = 0.25 * q_uckse_kPa / Fsem
    return {
        "T_m": T_m,
        "Ise_m4_per_m": Ise,
        "Zse_m3_per_m": Zse,
        "Ese_kPa": Ese,
        "sigma_ba_kPa": sigma_ba,
        "Fsem": Fsem,
        "q_uckse_kPa": q_uckse_kPa,
    }


def hetenyi_beta(Kv_kNm3: float, Ese_kPa: float, Ise_m4_per_m: float,
                  b_m: float = 1.0) -> float:
    """β = ((k·b) / (4·E·I))^(1/4)  [m⁻¹]
    Đặc trưng liên kết của dầm trên nền đàn hồi Winkler (Hetenyi 1946).
    """
    k_eff = Kv_kNm3 * b_m
    return (k_eff / (4.0 * Ese_kPa * Ise_m4_per_m)) ** 0.25


def westergaard_radius_l(Ese_kPa: float, T_m: float, Kv_kNm3: float,
                          nu: float = NU_POISSON) -> float:
    """Radius of relative stiffness L (Westergaard) [m].
    L = (E·T³ / (12·(1-ν²)·k))^(1/4)
    """
    num = Ese_kPa * T_m**3
    den = 12.0 * (1.0 - nu**2) * Kv_kNm3
    return (num / den) ** 0.25


# ════════ 5 PHƯƠNG PHÁP TÍNH M_max ════════

def M1_simple_beam_clear_span(q_kPa: float, s_m: float, D_m: float) -> float:
    """M1: Dầm đơn giản nhịp thông thuỷ giữa 2 cọc (L = s − D).
    M_max = q · (s-D)² / 8  [kNm/m]
    Conservative — bỏ qua phần đệm phủ lên đầu cọc.
    """
    L = max(0.0, s_m - D_m)
    return q_kPa * L**2 / 8.0


def M2_simple_beam_full_span(q_kPa: float, s_m: float) -> float:
    """M2: Dầm đơn giản nhịp đầy đủ s.
    M_max = q · s² / 8  [kNm/m]
    MOST conservative — bỏ qua hoàn toàn ảnh hưởng đường kính cọc.
    """
    return q_kPa * s_m**2 / 8.0


def M3_plate_four_corners(q_kPa: float, s_m: float) -> float:
    """M3: Bản đệm tựa tại 4 đầu cọc (Timoshenko plate corner-supported).
    M_max ≈ 0,045 · q · s²  [kNm/m] — moment dương ở midspan.
    """
    return 0.045 * q_kPa * s_m**2


def M4_hetenyi_uniform(q_kPa: float, beta_m_inv: float) -> float:
    """M4: Dầm Winkler vô hạn dưới tải phân bố đều — Hetenyi.
    Trên đoạn dầm dài vô hạn chịu tải phân bố q, mô men cực đại:
      M_max = q / (4·β²)   [kNm/m]
    Đệm có liên kết với đất nền nên ngang hơn dầm đơn giản.
    """
    if beta_m_inv <= 0:
        return float("inf")
    return q_kPa / (4.0 * beta_m_inv**2)


def M5_westergaard_interior(P_kN: float, T_m: float, Ese_kPa: float,
                             Kv_kNm3: float, b_load_m: float,
                             nu: float = NU_POISSON) -> float:
    """M5: Westergaard interior load — bản BTXM trên nền Winkler.
    Tải trọng tập trung P (kN/m chiều rộng) phía trên đệm:
      L = (E·T³ / (12(1-ν²)·k))^(1/4)
      M_max = (P / (2π)) · (1+ν) · [ln(L/b) + 0,6159]
    """
    if P_kN <= 0:
        return 0.0
    L = westergaard_radius_l(Ese_kPa, T_m, Kv_kNm3, nu)
    b = max(0.01, b_load_m)
    if L <= b:
        L = b * 1.01
    return (P_kN / (2.0 * math.pi)) * (1.0 + nu) * (math.log(L / b) + 0.6159)


# ════════ TỔNG HỢP KIỂM TOÁN ════════

def check_bending(
    T_m: float,
    q_uckse_kPa: float,
    P_soil_kPa: float,
    s_m: float,
    D_m: float,
    Fsem: float = FSEM_DEFAULT,
    Kv_kNm3: float = KV_SUBGRADE_KNM3,
    nu: float = NU_POISSON,
) -> Dict:
    """Kiểm toán uốn lớp đệm xi măng đầy đủ — 5 phương pháp tính M_max.

    Args:
        T_m: bề dày đệm (= Hse)  [m]
        q_uckse_kPa: cường độ kháng nén thiết kế đệm  [kPa]
        P_soil_kPa: áp lực thẳng đứng tác dụng lên đệm (từ ALiCC punching)  [kPa]
        s_m: khoảng cách tâm cọc  [m]
        D_m: đường kính cọc CDM  [m]
        Fsem: hệ số an toàn cường độ kéo khi uốn (mặc định 1.2)
        Kv_kNm3: mô đun phản lực nền dưới đệm  [kN/m³]
        nu: hệ số Poisson đệm

    Returns: dict với:
        section: I_se, Z_se, E_se, σ_ba
        beta, L_west: tham số dầm Winkler / Westergaard
        methods: list[{name, M_kNm_per_m, sigma_b_kPa, ratio, ok}]
        recommended: M_max bảo thủ nhất + verdict
    """
    sec = cushion_section_props(T_m, q_uckse_kPa, Fsem)
    Ese = sec["Ese_kPa"]
    Ise = sec["Ise_m4_per_m"]
    Zse = sec["Zse_m3_per_m"]
    sigma_ba = sec["sigma_ba_kPa"]

    beta = hetenyi_beta(Kv_kNm3, Ese, Ise, b_m=1.0)
    L_west = westergaard_radius_l(Ese, T_m, Kv_kNm3, nu)

    # Tải tập trung tương đương cho M5 — quy về P=q·s (kN/m chiều rộng)
    P_eq_kN_per_m = P_soil_kPa * s_m
    b_load = D_m / 2  # bán kính tiếp xúc cọc

    methods_def = [
        ("M1: Dầm đơn giản nhịp s-D",
         M1_simple_beam_clear_span(P_soil_kPa, s_m, D_m)),
        ("M2: Dầm đơn giản nhịp s",
         M2_simple_beam_full_span(P_soil_kPa, s_m)),
        ("M3: Bản 4 góc (Timoshenko)",
         M3_plate_four_corners(P_soil_kPa, s_m)),
        ("M4: Hetenyi Winkler vô hạn",
         M4_hetenyi_uniform(P_soil_kPa, beta)),
        ("M5: Westergaard interior",
         M5_westergaard_interior(P_eq_kN_per_m, T_m, Ese, Kv_kNm3, b_load, nu)),
    ]

    methods = []
    for name, M in methods_def:
        sigma_b = M / Zse if Zse > 0 else float("inf")
        ratio = sigma_b / sigma_ba if sigma_ba > 0 else float("inf")
        methods.append({
            "name": name,
            "M_kNm_per_m": M,
            "sigma_b_kPa": sigma_b,
            "ratio": ratio,
            "ok": ratio <= 1.0,
        })

    # Recommended = max M (bảo thủ)
    M_design = max(m["M_kNm_per_m"] for m in methods)
    sigma_design = M_design / Zse if Zse > 0 else float("inf")
    ratio_design = sigma_design / sigma_ba

    return {
        "section": sec,
        "beta_m_inv": beta,
        "L_westergaard_m": L_west,
        "P_soil_kPa": P_soil_kPa,
        "P_eq_kN_per_m": P_eq_kN_per_m,
        "methods": methods,
        "M_design_kNm_per_m": M_design,
        "sigma_design_kPa": sigma_design,
        "ratio_design": ratio_design,
        "ok_design": ratio_design <= 1.0,
    }


# ════════ DEMO ════════
if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

    print("=" * 72)
    print("KIỂM TOÁN UỐN LỚP ĐỆM XI MĂNG — 5 phương pháp tính M_max")
    print("Công thức gốc: KIEM TOAN LOP BTXM C10.xls (R14)")
    print("=" * 72)

    # Test 1: Verify với file BTXM C10 (T=0.4, q_uckse=10000, P_soil=18.88)
    print("\n[A] Verify với file gốc — BTXM C10 (R14):")
    print(f"    T=0.4m, q_uckse=10000 kPa (BTXM C10), P_soil=18.88 kPa")
    r0 = check_bending(T_m=0.4, q_uckse_kPa=10000, P_soil_kPa=18.88,
                       s_m=1.3, D_m=0.6, Fsem=1.2, Kv_kNm3=23.0)
    print(f"    σ_ba (cường độ kéo cho phép) = {r0['section']['sigma_ba_kPa']:.1f} kPa")
    print(f"    Z_se = {r0['section']['Zse_m3_per_m']:.5f} m³/m")
    print(f"    β = {r0['beta_m_inv']:.3f} m⁻¹  ·  L_west = {r0['L_westergaard_m']:.3f} m")
    print(f"    Verify σ_ba file gốc = 2083.3 kPa → engine: {r0['section']['sigma_ba_kPa']:.1f} ✓"
          if abs(r0['section']['sigma_ba_kPa'] - 2083.3) < 0.5 else "    σ_ba MISMATCH!")
    print(f"    File gốc PLAXIS M_max=50.35 → σ_b=1888 kPa (ratio 0.91)")
    print(f"    {'Phương pháp':<35s}{'M(kNm/m)':>12s}{'σ_b(kPa)':>12s}{'ratio':>8s}{'OK':>5s}")
    for m in r0["methods"]:
        ok = "Đạt" if m["ok"] else "KĐ"
        print(f"    {m['name']:<35s}{m['M_kNm_per_m']:>12.2f}{m['sigma_b_kPa']:>12.1f}"
              f"{m['ratio']:>8.3f}{ok:>5s}")

    # Test 2: Áp dụng cho dự án TTHC (cement cushion 0.40m, q_uckse=600, P_soil=124.7 từ ALiCC)
    print("\n[B] Áp dụng dự án TTHC — đệm cát-XM Hse=0.40m, q_uckse=600 kPa:")
    print(f"    P_soil từ ALiCC = ~62 kPa (=P_soil 124.7 × diện tích / diện tích)")
    # Note: P_soil for bending = áp lực TRUNG BÌNH trên bề mặt đệm (giữa các cọc)
    # = (V_soil - V_CGCXM)*γ_TB + V_CGCXM*γ_hse, chia A_unit
    # ≈ 62 kPa cho TTHC config (s=1.8, D=0.8)
    P_soil_TTHC = 62.0  # placeholder — sẽ tính chính xác từ ALiCC engine
    for Hse_test, qu_test in [(0.40, 600), (0.40, 800), (0.50, 600), (0.55, 600)]:
        rr = check_bending(T_m=Hse_test, q_uckse_kPa=float(qu_test),
                           P_soil_kPa=P_soil_TTHC, s_m=1.8, D_m=0.8)
        m_des = rr["M_design_kNm_per_m"]; r_des = rr["ratio_design"]
        ok = "Đạt" if rr["ok_design"] else "KĐ"
        print(f"    Hse={Hse_test:.2f} qu={qu_test:>4d} → M_des={m_des:.2f} kNm/m, "
              f"ratio={r_des:.3f}, {ok}")
