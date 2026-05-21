"""
winkler_np.py — Solver Winkler p-y thuần NumPy (không phụ thuộc PyNite/anastruct).

Cài tại sao: PyNiteFEA và anastruct hay fail build trên Streamlit Cloud khi
Cloud nâng Python lên 3.14 (numpy/scipy chưa có wheel). NumPy luôn có sẵn.

Phương pháp: phương pháp ma trận độ cứng (direct stiffness) cho dầm Euler-Bernoulli
2 DOF/nút (chuyển vị ngang v + xoay θ), lò xo Winkler gắn vào DOF chuyển vị
tại mỗi nút.

API tương thích với `wall_internal_force.solve_pynite()` và `solve_pynite_dist()`:
  - Input: layers, pile (PileProps), L_m, H_kNm, M_kNm, N, eps50, k_sand_kNm3,
           cdm_thickness_m, cdm_factor, tip_fixity, top_pin
  - Output dict: {solver, u_top_mm, u_max_mm, M_max_kNm, Q_max_kN, Mcr_kNm,
                  EI_kNm2, D_mm, zs, ux, Ms, Qs, k_h}

Dùng lại `kh_profile`, `SoilLayer`, `PileProps`, `sw_pile_props` từ
wall_internal_force để khỏi định nghĩa trùng.
"""
from __future__ import annotations

import numpy as np

from wall_internal_force import kh_profile, SoilLayer, PileProps  # re-export


# ─────────────────────────────────────────────────────────────────────────────
# Ma trận độ cứng phần tử dầm Euler-Bernoulli (4×4)
# ─────────────────────────────────────────────────────────────────────────────

def _element_K(EI: float, Le: float) -> np.ndarray:
    """Ma trận độ cứng dầm 2D, DOFs [v_i, θ_i, v_j, θ_j]."""
    L2 = Le * Le
    L3 = L2 * Le
    return (EI / L3) * np.array([
        [12.0,    6.0 * Le,  -12.0,    6.0 * Le],
        [6.0 * Le, 4.0 * L2, -6.0 * Le, 2.0 * L2],
        [-12.0,  -6.0 * Le,   12.0,   -6.0 * Le],
        [6.0 * Le, 2.0 * L2, -6.0 * Le, 4.0 * L2],
    ])


def _consistent_load_linear(w1: float, w2: float, Le: float) -> np.ndarray:
    """Tải nút tương đương cho tải phân bố tuyến tính w1 → w2 dọc 1 phần tử.

    Áp dụng cho dầm Euler-Bernoulli với shape function Hermite bậc 3.
    Output: vector [F_v_i, M_θ_i, F_v_j, M_θ_j] (kN, kN·m).
    """
    L = Le
    L2 = L * L
    return np.array([
        L * (7.0 * w1 + 3.0 * w2) / 20.0,
        L2 * (3.0 * w1 + 2.0 * w2) / 60.0,
        L * (3.0 * w1 + 7.0 * w2) / 20.0,
        -L2 * (2.0 * w1 + 3.0 * w2) / 60.0,
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Lắp ráp hệ phương trình K·u = F + áp BC
# ─────────────────────────────────────────────────────────────────────────────

def _assemble(layers, pile: PileProps, L_m: float, N: int,
              eps50: float, k_sand_kNm3: float,
              cdm_thickness_m: float, cdm_factor: float,
              tip_fixity: str, top_pin: bool
              ) -> tuple[np.ndarray, np.ndarray, list[int], list[float],
                         list[float], float]:
    """Lắp ráp K toàn cục + F=0 + danh sách DOF bị khóa. Trả K, F, fixed_dofs, zs, k_h, dz."""
    EI = pile.EI_kNm2
    zs, k_h = kh_profile(layers, pile, L_m, N, eps50, k_sand_kNm3,
                         cdm_thickness_m, cdm_factor)
    dz = L_m / (N - 1)
    n_dof = 2 * N
    K = np.zeros((n_dof, n_dof))
    F = np.zeros(n_dof)

    Ke = _element_K(EI, dz)
    for i in range(N - 1):
        dofs = (2 * i, 2 * i + 1, 2 * (i + 1), 2 * (i + 1) + 1)
        for a in range(4):
            for b in range(4):
                K[dofs[a], dofs[b]] += Ke[a, b]

    # Lò xo Winkler (k_h * D * dz) gắn vào DOF chuyển vị mỗi nút
    for i in range(N):
        k_spring = k_h[i] * pile.D_m * dz
        K[2 * i, 2 * i] += k_spring

    # BC
    fixed = set()
    if top_pin:
        fixed.add(0)  # v at top = 0 (dầm mũ)
    if tip_fixity == "pinned":
        fixed.add(2 * (N - 1))
    elif tip_fixity == "fixed":
        fixed.add(2 * (N - 1))
        fixed.add(2 * (N - 1) + 1)
    return K, F, sorted(fixed), zs, k_h, dz


# ─────────────────────────────────────────────────────────────────────────────
# Trích kết quả từ vector u (chuyển vị + xoay tại các nút)
# ─────────────────────────────────────────────────────────────────────────────

def _extract(u: np.ndarray, pile: PileProps, zs: list[float],
             k_h: list[float], dz: float, name: str) -> dict:
    """Tính M, Q ở midspan mỗi phần tử (M = EI·κ, Q = EI·u''')."""
    N = len(zs)
    EI = pile.EI_kNm2
    ux_mm = [float(u[2 * i] * 1000.0) for i in range(N)]

    Le = dz
    L2 = Le * Le
    L3 = L2 * Le
    x = 0.5 * Le  # midspan
    N1_dd = -6.0 / L2 + 12.0 * x / L3
    N2_dd = -4.0 / Le + 6.0 * x / L2
    N3_dd = 6.0 / L2 - 12.0 * x / L3
    N4_dd = -2.0 / Le + 6.0 * x / L2
    N1_ddd = 12.0 / L3
    N2_ddd = 6.0 / L2
    N3_ddd = -12.0 / L3
    N4_ddd = 6.0 / L2

    Ms: list[float] = []
    Qs: list[float] = []
    for i in range(N - 1):
        vi, ti, vj, tj = u[2 * i], u[2 * i + 1], u[2 * (i + 1)], u[2 * (i + 1) + 1]
        kappa = N1_dd * vi + N2_dd * ti + N3_dd * vj + N4_dd * tj
        Ms.append(float(EI * kappa))
        Qs.append(float(EI * (N1_ddd * vi + N2_ddd * ti + N3_ddd * vj + N4_ddd * tj)))

    return {
        "solver": name,
        "u_top_mm": ux_mm[0],
        "u_max_mm": max(abs(v) for v in ux_mm),
        "M_max_kNm": max(abs(m) for m in Ms) if Ms else 0.0,
        "Q_max_kN": max(abs(q) for q in Qs) if Qs else 0.0,
        "Mcr_kNm": pile.Mcr_kNm,
        "EI_kNm2": pile.EI_kNm2,
        "D_mm": pile.D_m * 1000.0,
        "zs": list(zs),
        "ux": ux_mm,
        "Ms": Ms,
        "Qs": Qs,
        "k_h": list(k_h),
    }


def _solve_reduced(K: np.ndarray, F: np.ndarray, fixed: list[int]
                   ) -> np.ndarray | None:
    """Giải Kff · uf = Ff. Trả None nếu singular."""
    n = K.shape[0]
    free = [i for i in range(n) if i not in fixed]
    Kff = K[np.ix_(free, free)]
    Ff = F[free]
    try:
        uf = np.linalg.solve(Kff, Ff)
    except np.linalg.LinAlgError:
        return None
    u = np.zeros(n)
    for idx, d in enumerate(free):
        u[d] = uf[idx]
    return u


# ─────────────────────────────────────────────────────────────────────────────
# API công khai
# ─────────────────────────────────────────────────────────────────────────────

def solve_numpy(layers, pile: PileProps, L_m: float,
                H_kNm: float, M_kNm: float = 0.0,
                N: int = 60, eps50: float = 0.02,
                k_sand_kNm3: float = 10_000.0,
                cdm_thickness_m: float = 0.0, cdm_factor: float = 3.0,
                tip_fixity: str = "free", top_pin: bool = False) -> dict:
    """Winkler beam — tải tập trung H + M tại đỉnh cọc.

    API y hệt `wall_internal_force.solve_pynite`.
    """
    if pile.EI_kNm2 <= 0:
        return {"error": "EI=0"}
    K, F, fixed, zs, k_h, dz = _assemble(
        layers, pile, L_m, N, eps50, k_sand_kNm3,
        cdm_thickness_m, cdm_factor, tip_fixity, top_pin)
    # Tải tại đỉnh
    F[0] += float(H_kNm)
    F[1] += float(M_kNm)
    u = _solve_reduced(K, F, fixed)
    if u is None:
        return {"error": "NumPy solver: hệ phương trình singular"}
    return _extract(u, pile, zs, k_h, dz, "NumPy-conc")


def solve_numpy_dist(layers, pile: PileProps, L_m: float,
                     zs_load, p_load_kNm2,
                     N: int = 60, eps50: float = 0.02,
                     k_sand_kNm3: float = 10_000.0,
                     cdm_thickness_m: float = 0.0, cdm_factor: float = 3.0,
                     tip_fixity: str = "free",
                     load_method: str = "distributed",
                     top_pin: bool = False) -> dict:
    """Winkler beam — tải phân bố p(z) [kN/m²] dọc cừ.

    API y hệt `wall_internal_force.solve_pynite_dist`.
    Dấu p_load_kNm2 dương → đẩy cừ từ Front sang Back.
    """
    if pile.EI_kNm2 <= 0:
        return {"error": "EI=0"}
    K, F, fixed, zs, k_h, dz = _assemble(
        layers, pile, L_m, N, eps50, k_sand_kNm3,
        cdm_thickness_m, cdm_factor, tip_fixity, top_pin)
    # Nội suy tải về các nút
    p_at = np.interp(np.array(zs), zs_load, p_load_kNm2)

    if load_method == "distributed":
        # Tải nút tương đương cho mỗi phần tử
        for i in range(N - 1):
            w1, w2 = float(p_at[i]), float(p_at[i + 1])
            if abs(w1) < 1e-12 and abs(w2) < 1e-12:
                continue
            fe = _consistent_load_linear(w1, w2, dz)
            F[2 * i]         += fe[0]
            F[2 * i + 1]     += fe[1]
            F[2 * (i + 1)]   += fe[2]
            F[2 * (i + 1) + 1] += fe[3]
    else:
        # Lumped: tải nút tỉ lệ trapezoid
        for i in range(N):
            p_i = float(p_at[i])
            f_i = p_i * dz / 2.0 if (i == 0 or i == N - 1) else p_i * dz
            if abs(f_i) > 1e-12:
                F[2 * i] += f_i

    u = _solve_reduced(K, F, fixed)
    if u is None:
        return {"error": "NumPy solver: hệ phương trình singular"}
    res = _extract(u, pile, zs, k_h, dz, f"NumPy-{load_method}")
    res["p_load_kNm2"] = p_at.tolist()
    return res


# ─────────────────────────────────────────────────────────────────────────────
# Demo + tự kiểm tra (chạy `python winkler_np.py`)
# ─────────────────────────────────────────────────────────────────────────────

def _self_test() -> None:
    from wall_internal_force import sw_pile_props
    pile = sw_pile_props(H_mm=840, Itd_cm4=2_125_017, Mcr_Tm=77.1,
                          Atd_cm2=3107, fc_MPa=70.0, name="SW-840")
    layers = [SoilLayer("F", 2.0, gamma_kNm3=18.0),
              SoilLayer("1", 18.0, Su_kPa=11.0, gamma_kNm3=15.0),
              SoilLayer("2b", 10.0, gamma_kNm3=18.0)]

    r1 = solve_numpy(layers, pile, L_m=29.0, H_kNm=50.0, M_kNm=0.0,
                     N=60, top_pin=False)
    print("[conc-load]")
    print(f"  u_top  = {r1['u_top_mm']:.2f} mm")
    print(f"  u_max  = {r1['u_max_mm']:.2f} mm")
    print(f"  M_max  = {r1['M_max_kNm']:.1f} kN·m")
    print(f"  Q_max  = {r1['Q_max_kN']:.1f} kN")

    # Tải phân bố hình thang
    zs_load = [0.0, 5.0, 10.0, 20.0, 29.0]
    p_load = [0.0, 30.0, 25.0, 5.0, 0.0]
    r2 = solve_numpy_dist(layers, pile, L_m=29.0, zs_load=zs_load,
                          p_load_kNm2=p_load, N=60, top_pin=True)
    print("\n[dist-load]")
    print(f"  u_top  = {r2['u_top_mm']:.2f} mm")
    print(f"  u_max  = {r2['u_max_mm']:.2f} mm")
    print(f"  M_max  = {r2['M_max_kNm']:.1f} kN·m")
    print(f"  Q_max  = {r2['Q_max_kN']:.1f} kN")


if __name__ == "__main__":
    _self_test()
