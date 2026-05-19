"""
api_clay_matlock.py — Standalone helper cho mô hình đất sét API Clay (Matlock 1970)

Chức năng:
  1. py_curve_api_clay()    — Tính và vẽ đường cong p-y cho 1 chiều sâu
  2. pu_api_clay()          — Tính sức kháng cực hạn p_u theo API
  3. y50_api_clay()         — Tính y₅₀
  4. eps50_from_Su()        — Tra bảng ε₅₀ điển hình từ S_u
  5. demo_mixed_profile()   — Ví dụ profile Sand+Clay với openpile

Đơn vị: kN, m, kPa (= kN/m²)

Chạy:  python scripts/api_clay_matlock.py
"""
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# 1. p_u — Ultimate unit lateral resistance (Matlock 1970 / API)
# ---------------------------------------------------------------------------

def pu_api_clay(Su: float, D: float, z: float,
                gamma_sub: float = 8.0, J: float = 0.5) -> float:
    """Tính p_u [kN/m] theo Matlock (1970).

    Args:
        Su:        Sức chịu cắt không thoát nước [kN/m²]
        D:         Đường kính / bề rộng cọc [m]
        z:         Chiều sâu dưới mặt đất [m, dương]
        gamma_sub: Dung trọng đẩy nổi [kN/m³], default 8.0
        J:         Hệ số kinh nghiệm (0.25–0.50), default 0.50

    Returns:
        p_u [kN/m]
    """
    if Su <= 0 or D <= 0:
        return 0.0
    Np = min(3.0 + (gamma_sub / Su) * z + (J / D) * z, 9.0)
    return Np * Su * D


# ---------------------------------------------------------------------------
# 2. y₅₀ — Displacement at 50% ultimate resistance
# ---------------------------------------------------------------------------

def y50_api_clay(eps50: float, D: float) -> float:
    """y₅₀ = 2.5 · ε₅₀ · D  [m]"""
    return 2.5 * eps50 * D


# ---------------------------------------------------------------------------
# 3. p-y curve at a single depth
# ---------------------------------------------------------------------------

def py_curve_api_clay(Su: float, D: float, z: float,
                      gamma_sub: float = 8.0,
                      eps50: float = 0.02, J: float = 0.5,
                      n_pts: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """Đường cong p-y cho đất sét (Matlock 1970) tại chiều sâu z.

    Returns:
        y_arr [m], p_arr [kN/m]
    """
    pu   = pu_api_clay(Su, D, z, gamma_sub, J)
    y50  = y50_api_clay(eps50, D)
    y_arr = np.linspace(0.0, 10.0 * y50, n_pts)
    p_arr = np.where(
        y_arr <= 8.0 * y50,
        0.5 * pu * (y_arr / y50) ** (1.0 / 3.0),
        pu
    )
    return y_arr, p_arr


# ---------------------------------------------------------------------------
# 4. ε₅₀ look-up from S_u
# ---------------------------------------------------------------------------

_EPS50_TABLE = [
    (12.0,   0.020),   # very soft / soft
    (25.0,   0.020),   # soft
    (50.0,   0.010),   # medium
    (100.0,  0.007),   # stiff
    (200.0,  0.005),   # very stiff
    (1e9,    0.004),   # hard
]


def eps50_from_Su(Su: float) -> float:
    """Tra bảng ε₅₀ điển hình theo S_u [kN/m²] (Matlock 1970)."""
    for su_limit, eps in _EPS50_TABLE:
        if Su <= su_limit:
            return eps
    return 0.004


# ---------------------------------------------------------------------------
# 5. Demo — Mixed Sand + Clay profile với openpile
# ---------------------------------------------------------------------------

def demo_mixed_profile():
    print("=" * 62)
    print("Demo: Mixed Sand-Clay profile | openpile API p-y")
    print("=" * 62)

    try:
        from openpile.construct import (
            Pile, SoilProfile, Layer, Model, BoundaryFixation,
        )
        from openpile.soilmodels import API_sand, API_clay
        from openpile.winkler import winkler

        # ── Cọc SW-840 (equivalent tubular) ──────────────────────────
        pile = Pile.create_tubular(
            name="SW-840",
            top_elevation=2.7,
            bottom_elevation=-17.3,
            diameter=0.840,
            wt=0.016,
            material="Concrete",
        )

        # ── Địa tầng: Sand → Clay → Sand ─────────────────────────────
        sp = SoilProfile(
            name="Mixed Sand-Clay",
            top_elevation=2.7,
            water_line=-1.0,
            layers=[
                # Sand layer: 2.7 → -5.0 m
                Layer(name="Sand phi28", top=2.7, bottom=-5.0,
                      weight=18.0,
                      lateral_model=API_sand(phi=28.0, kind="static")),
                # Clay layer: -5.0 → -10.0 m
                Layer(name="Soft clay Su10", top=-5.0, bottom=-10.0,
                      weight=17.0,
                      lateral_model=API_clay(Su=10.0, eps50=0.020,
                                             kind="static", J=0.5)),
                # Sand layer: -10.0 → -17.3 m
                Layer(name="Sand phi32", top=-10.0, bottom=-17.3,
                      weight=19.0,
                      lateral_model=API_sand(phi=32.0, kind="static")),
            ],
        )

        bc = [BoundaryFixation(elevation=-17.3, x=True, y=True, z=True)]
        model = Model(name="demo", pile=pile, soil=sp, boundary_conditions=bc)
        model.set_pointload(elevation=2.7, Py=100.0)  # H = 100 kN

        result   = winkler(model)
        y_head   = abs(result.deflection["Deflection [m]"].iloc[0]) * 1000
        M_max    = result.forces["M [kNm]"].abs().max()
        V_max    = result.forces["V [kN]"].abs().max()

        print(f"  Pile: SW-840  Top=2.7m  Tip=-17.3m  L=20m")
        print(f"  Profile: Sand(28°) / Clay(Su=10) / Sand(32°)")
        print(f"  Lateral load H = 100 kN at top")
        print()
        print(f"  Head deflection : {y_head:.3f} mm")
        print(f"  M_max           : {M_max:.1f} kN·m")
        print(f"  V_max           : {V_max:.1f} kN")

    except ImportError as e:
        print(f"  [SKIP] openpile not available: {e}")
    except Exception as e:
        print(f"  [ERROR] {e}")
    print()


# ---------------------------------------------------------------------------
# 6. Demo — p-y curves tại các chiều sâu khác nhau
# ---------------------------------------------------------------------------

def demo_py_curves():
    print("=" * 62)
    print("p-y Curves — API Clay (Matlock 1970)")
    print("=" * 62)

    D     = 0.840     # m
    Su    = 10.0      # kN/m²
    eps50 = 0.020
    gamma_sub = 7.0   # kN/m³
    depths = [1.0, 3.0, 5.0, 8.0]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    colors  = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

    for z, col in zip(depths, colors):
        y_arr, p_arr = py_curve_api_clay(Su, D, z, gamma_sub, eps50)
        pu = pu_api_clay(Su, D, z, gamma_sub)
        label = f"z = {z:.0f} m  (pᵤ = {pu:.1f} kN/m)"
        ax.plot(y_arr * 1000, p_arr, color=col, lw=1.8, label=label)

    ax.set_xlabel("Lateral displacement y [mm]")
    ax.set_ylabel("Soil resistance p [kN/m]")
    ax.set_title(f"API Clay p-y Curves | Sᵤ = {Su} kN/m²  ε₅₀ = {eps50}  D = {D} m")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.35)
    plt.tight_layout()

    out = "scripts/output_py_clay_curves.png"
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  p-y curves saved → {out}")
    print()


# ---------------------------------------------------------------------------
# 7. ε₅₀ look-up demo
# ---------------------------------------------------------------------------

def demo_eps50():
    print("=" * 62)
    print("ε₅₀ look-up (Matlock 1970)")
    print("=" * 62)
    test_su = [5, 15, 30, 70, 120, 250]
    print(f"  {'Su [kN/m²]':<14} {'eps50':>8}")
    print(f"  {'-'*24}")
    for su in test_su:
        e = eps50_from_Su(su)
        print(f"  {su:<14} {e:>8.3f}")
    print()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo_eps50()
    demo_py_curves()
    demo_mixed_profile()
    print("Done.")
