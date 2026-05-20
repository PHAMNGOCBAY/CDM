"""
fill_lateral_force.py — Áp lực ngang đất đắp → Lực tập trung tác dụng lên kè
Convention: Front = TRÁI, fill chỉ phía Front. TCVN 11823-3:2017 §10.5
"""
from __future__ import annotations
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dataclasses import dataclass

try:
    from lateral_earth_pressure import ka_rankine, ka_coulomb, SoilLayer
except ImportError:
    def ka_rankine(phi_deg: float) -> float:  # type: ignore[misc]
        return math.tan(math.pi / 4 - math.radians(phi_deg) / 2) ** 2

    def ka_coulomb(phi_deg: float, delta_deg: float = 0.0,  # type: ignore[misc]
                   beta_deg: float = 90.0, alpha_deg: float = 0.0) -> float:
        return ka_rankine(phi_deg)

    @dataclass
    class SoilLayer:  # type: ignore[no-redef]
        tip_elev: float
        gamma: float = 18.0
        gamma_sub: float = 8.0
        phi: float = 25.0
        c: float = 0.0


_GAMMA_W = 9.81  # kN/m³


@dataclass
class FillGeometry:
    top_elev: float = 2.7           # cao độ đỉnh cừ/kè (m)
    soil_level_front: float = 0.0   # mặt đất tự nhiên phía Front (m)
    pile_length: float = 20.0       # chiều dài tổng cọc/tường (m)
    water_elev_front: float = -1.0  # mực nước phía Front (m)
    gamma_fill: float = 18.0        # dung trọng moist đất đắp (kN/m³)
    phi_fill: float = 25.0          # góc ma sát đất đắp (°)
    c_fill: float = 0.0             # lực dính đất đắp (kN/m²)

    @property
    def H_fill(self) -> float:
        return max(0.0, self.top_elev - self.soil_level_front)

    @property
    def pile_tip_elev(self) -> float:
        return self.top_elev - self.pile_length

    @property
    def gamma_fill_sub(self) -> float:
        return self.gamma_fill - _GAMMA_W


def _gamma_eff_fill(geom: FillGeometry, elev: float) -> float:
    """Dung trọng hiệu quả đất đắp tại cao độ elev."""
    return geom.gamma_fill_sub if elev < geom.water_elev_front else geom.gamma_fill


def compute_fill_zone(
    geom: FillGeometry,
    ka_method: str = "rankine",
    delta_deg: float = 0.0,
    n_pts: int = 100,
) -> dict:
    """
    Tính áp lực Active trong vùng fill (top_elev → soil_level_front).
    Trả về: elevs, pressure, F_fill, z_fill, ka, pressure_top, pressure_bot
    """
    if geom.H_fill <= 0:
        z_ref = geom.soil_level_front
        return {"elevs": np.array([z_ref, z_ref]), "pressure": np.array([0.0, 0.0]),
                "F_fill": 0.0, "z_fill": z_ref,
                "ka": ka_rankine(geom.phi_fill),
                "pressure_top": 0.0, "pressure_bot": 0.0}

    ka = (ka_coulomb(geom.phi_fill, delta_deg) if ka_method == "coulomb"
          else ka_rankine(geom.phi_fill))
    sqrt_ka = math.sqrt(ka)

    elevs = np.linspace(geom.top_elev, geom.soil_level_front, n_pts)
    pressure = np.zeros(n_pts)
    sv = 0.0

    for i in range(1, n_pts):
        dz = abs(elevs[i - 1] - elevs[i])
        g_eff = _gamma_eff_fill(geom, (elevs[i - 1] + elevs[i]) / 2)
        sv += g_eff * dz
        pressure[i] = max(0.0, ka * sv - 2.0 * geom.c_fill * sqrt_ka)

    # Resultant: F = ∫ σ_h dh  (h = depth from top_elev, increasing downward)
    _trap = getattr(np, "trapezoid", None) or np.trapz   # numpy<2 trapz, ≥2 trapezoid
    F = float(_trap(pressure, x=-elevs))  # x=-elevs là chiều tăng dần

    if F > 0.0:
        moment = float(_trap(pressure * (geom.top_elev - elevs), x=-elevs))
        z_fill = geom.top_elev - moment / F
    else:
        z_fill = geom.soil_level_front + geom.H_fill / 3.0

    return {
        "ka": ka,
        "elevs": elevs,
        "pressure": pressure,
        "F_fill": F,
        "z_fill": z_fill,
        "pressure_top": float(pressure[0]),
        "pressure_bot": float(pressure[-1]),
    }


def compute_all(
    geom: FillGeometry,
    _natural_layers: list | None = None,
    ka_method: str = "rankine",
    delta_deg: float = 0.0,
) -> dict:
    """
    Tính lực ngang vùng fill (top_elev → soil_level_front) và vẽ biểu đồ.
    Surcharge do đất đắp lên lớp tự nhiên tính riêng ở tab Boussinesq.

    Trả về dict:
      F_fill_zone, z_fill_zone   — lực fill zone + cao độ tác dụng
      pressure_top, pressure_bot — áp lực tại đỉnh/đáy vùng fill [kN/m²]
      ka                         — hệ số áp lực chủ động
      M_about_soil_level         — moment về mặt đất tự nhiên [kN·m/m]
      M_about_pile_tip           — moment về mũi cọc [kN·m/m]
      fig                        — matplotlib Figure
    """
    fill_res = compute_fill_zone(geom, ka_method, delta_deg)

    F1, z1 = fill_res["F_fill"], fill_res["z_fill"]
    M_soil = F1 * (z1 - geom.soil_level_front)
    M_tip  = F1 * (z1 - geom.pile_tip_elev)

    fig = plot_fill_force_diagram(geom, fill_res)

    return {
        "F_fill_zone": F1,
        "z_fill_zone": z1,
        "pressure_top": fill_res["pressure_top"],
        "pressure_bot": fill_res["pressure_bot"],
        "ka": fill_res["ka"],
        "M_about_soil_level": M_soil,
        "M_about_pile_tip": M_tip,
        "fig": fig,
        # Phân bố áp lực để đưa vào openpile set_pointload
        "fill_elevs":    fill_res["elevs"].copy(),
        "fill_pressure": fill_res["pressure"].copy(),
    }


# ---------------------------------------------------------------------------
# Biểu đồ
# ---------------------------------------------------------------------------

def plot_fill_force_diagram(
    geom: FillGeometry,
    fill_res: dict,
) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(11, 8), layout="constrained")
    fig.suptitle("Lực ngang đất đắp → Lực tập trung tác dụng lên kè",
                 fontsize=11, fontweight="bold")

    _draw_pressure_panel(axes[0], geom, fill_res)
    _draw_ke_diagram(axes[1], geom, fill_res)

    return fig


def _y_lims(geom: FillGeometry) -> tuple[float, float]:
    margin = (geom.top_elev - geom.pile_tip_elev) * 0.08
    return geom.pile_tip_elev - margin, geom.top_elev + margin


def _draw_pressure_panel(ax: plt.Axes, geom: FillGeometry, fill_res: dict) -> None:
    y_bot, y_top = _y_lims(geom)

    # Vùng fill (màu nền)
    if geom.H_fill > 0:
        fill_patch = plt.Rectangle(
            (0, geom.soil_level_front),
            max(fill_res["pressure"]) * 1.3 + 2,
            geom.H_fill,
            facecolor="#ffe0b2", alpha=0.35, hatch="\\\\",
            edgecolor="sienna", linewidth=0.5, zorder=0,
        )
        ax.add_patch(fill_patch)

    # Áp lực vùng fill
    ef = fill_res["elevs"]
    pf = fill_res["pressure"]
    ax.fill_betweenx(ef, 0, pf, color="tomato", alpha=0.55,
                     label=f"F fill zone = {fill_res['F_fill']:.1f} kN/m")
    ax.plot(pf, ef, color="firebrick", lw=1.5)

    # Mũi tên minh họa áp lực phân bố (hướng sang phải → vào tường)
    if geom.H_fill > 0.2:
        n_arrows = max(3, round(geom.H_fill / 0.4))
        arr_e = np.linspace(geom.top_elev - 0.05, geom.soil_level_front + 0.05, n_arrows)
        arr_p = np.interp(arr_e, ef[::-1], pf[::-1])
        mask = arr_p > 0.3
        if mask.any():
            ax.quiver(
                np.zeros(mask.sum()), arr_e[mask],    # origin x=0 (tại tường)
                arr_p[mask], np.zeros(mask.sum()),     # hướng sang phải
                scale_units="xy", scale=1.0, angles="xy",
                color="firebrick", alpha=0.70,
                width=0.008, headwidth=4.5, headlength=5, zorder=5,
            )

    # Đường ngang tham chiếu
    ax.axhline(geom.top_elev, color="black", lw=2, label=f"Đỉnh cừ {geom.top_elev:.2f} m")
    ax.axhline(geom.soil_level_front, color="sienna", lw=1.5, linestyle="--",
               label=f"Mặt đất {geom.soil_level_front:.2f} m")
    ax.axhline(geom.pile_tip_elev, color="dimgray", lw=1.2)

    # Mực nước
    if y_bot < geom.water_elev_front < geom.top_elev:
        ax.axhline(geom.water_elev_front, color="#1a8cff", lw=1.5, linestyle=":")
        ax.text(0.5, geom.water_elev_front + 0.05, " WL front",
                fontsize=7.5, color="#1a8cff", va="bottom")

    # Điểm đặt F1
    F1, z1 = fill_res["F_fill"], fill_res["z_fill"]
    if F1 > 0:
        ax.plot(0, z1, "r^", ms=9, zorder=5)
        ax.axhline(z1, color="firebrick", lw=0.8, linestyle=":", alpha=0.7)
        ax.annotate(
            f"F = {F1:.1f} kN/m\nz = {z1:.2f} m",
            xy=(0, z1),
            xytext=(max(pf) * 0.4 + 3, z1 + geom.H_fill * 0.12),
            fontsize=8, color="firebrick",
            arrowprops=dict(arrowstyle="->", color="firebrick", lw=0.8),
        )

    # Nhãn cao độ trục y
    ax.text(-1.5, geom.top_elev + 0.08, f"+{geom.top_elev:.2f} m",
            fontsize=7.5, ha="right", va="bottom")
    ax.text(-1.5, geom.soil_level_front + 0.05, f"{geom.soil_level_front:.2f} m",
            fontsize=7.5, ha="right")
    ax.text(-1.5, geom.pile_tip_elev - 0.1, f"{geom.pile_tip_elev:.2f} m",
            fontsize=7.5, ha="right", va="top")

    ax.set_title("Biểu đồ áp lực ngang\nđất đắp (Front/Active)", fontsize=10, fontweight="bold")
    ax.set_xlabel("Áp lực (kN/m²)", fontsize=9)
    ax.set_ylabel("Cao độ (m)", fontsize=9)
    ax.set_xlim(left=-2.5)
    ax.set_ylim(y_bot, y_top)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7.5, loc="lower right")


def _draw_ke_diagram(
    ax: plt.Axes, geom: FillGeometry,
    fill_res: dict,
) -> None:
    y_bot, y_top = _y_lims(geom)
    wall_w = 0.25

    ax.set_facecolor("#f5f5f5")

    # Đất tự nhiên phía Front (dưới soil_level_front)
    ax.add_patch(plt.Rectangle(
        (-3.2, geom.pile_tip_elev),
        3.2 - wall_w / 2,
        max(0, geom.soil_level_front - geom.pile_tip_elev),
        color="#d4c9a8", alpha=0.4, zorder=1,
    ))

    # Vùng fill (hatch, phía Front)
    if geom.H_fill > 0:
        ax.add_patch(plt.Rectangle(
            (-3.2, geom.soil_level_front),
            3.2 - wall_w / 2,
            geom.H_fill,
            facecolor="#ffe0b2", alpha=0.45, hatch="\\\\",
            edgecolor="sienna", linewidth=0.8, zorder=2,
        ))
        ax.text(-1.7, (geom.top_elev + geom.soil_level_front) / 2,
                f"Đất đắp\nH={geom.H_fill:.2f} m\nγ={geom.gamma_fill:.0f} kN/m³\nφ={geom.phi_fill:.0f}°",
                fontsize=7.5, ha="center", va="center", color="sienna")

    # Tường cừ
    ax.add_patch(plt.Rectangle(
        (-wall_w / 2, geom.pile_tip_elev),
        wall_w,
        geom.pile_length,
        color="steelblue", alpha=0.55, zorder=3,
    ))
    ax.text(wall_w / 2 + 0.08, (geom.top_elev + geom.pile_tip_elev) / 2,
            "Kè / Cừ", fontsize=8, va="center", color="steelblue", rotation=90)

    # Đường ngang tham chiếu
    ax.axhline(geom.top_elev, color="black", lw=2, xmin=0.2, xmax=1.0)
    ax.axhline(geom.soil_level_front, color="sienna", lw=1.5, linestyle="--", xmin=0.0, xmax=0.88)
    ax.axhline(geom.pile_tip_elev, color="dimgray", lw=1, xmin=0.0, xmax=1.0)

    # Mực nước
    if y_bot < geom.water_elev_front < geom.top_elev:
        ax.axhline(geom.water_elev_front, color="#1a8cff", lw=1.5, linestyle=":",
                   xmin=0.0, xmax=0.85)

    # Mũi tên F (fill zone, phía trái tường)
    F1, z1 = fill_res["F_fill"], fill_res["z_fill"]
    if F1 > 0:
        len1 = 1.8
        ax.annotate("",
                    xy=(-wall_w / 2, z1),
                    xytext=(-wall_w / 2 - len1, z1),
                    arrowprops=dict(arrowstyle="-|>", color="firebrick", lw=2.2,
                                    mutation_scale=14))
        ax.text(-wall_w / 2 - len1 - 0.08, z1,
                f"F = {F1:.1f} kN/m\n(fill zone)\nz = {z1:.2f} m",
                fontsize=7.5, ha="right", va="center", color="firebrick")

    # Nhãn cao độ bên phải tường
    for elev, label in [
        (geom.top_elev, f"+{geom.top_elev:.2f} m (đỉnh)"),
        (geom.soil_level_front, f"{geom.soil_level_front:.2f} m (mặt đất)"),
        (geom.pile_tip_elev, f"{geom.pile_tip_elev:.2f} m (mũi)"),
    ]:
        ax.plot(wall_w / 2, elev, "_", color="black", ms=10, mew=1.5)
        ax.text(wall_w / 2 + 0.07, elev + (y_top - y_bot) * 0.008,
                label, fontsize=7.0, va="bottom", color="dimgray")

    ax.set_title("Sơ đồ kè — lực tập trung\ntừ đất đắp", fontsize=10, fontweight="bold")
    ax.set_xlim(-4.0, 4.0)
    ax.set_ylim(y_bot, y_top)
    ax.set_xticks([])
    ax.set_ylabel("Cao độ (m)", fontsize=9)
    ax.grid(True, alpha=0.2)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    geom = FillGeometry(
        top_elev=2.7,
        soil_level_front=0.0,
        pile_length=20.0,
        water_elev_front=-1.0,
        gamma_fill=18.0,
        phi_fill=25.0,
        c_fill=0.0,
    )

    natural_layers = [
        SoilLayer(tip_elev=-5.0,  gamma=15.5, gamma_sub=5.5,  phi=5.0,  c=10.0),
        SoilLayer(tip_elev=-12.0, gamma=17.0, gamma_sub=7.0,  phi=8.0,  c=15.0),
        SoilLayer(tip_elev=-17.3, gamma=19.0, gamma_sub=9.0,  phi=30.0, c=0.0),
    ]

    res = compute_all(geom, ka_method="rankine")

    print("=" * 50)
    print("KẾT QUẢ LỰC NGANG TỪ ĐẤT ĐẮP (vùng fill)")
    print("=" * 50)
    print(f"Ka (Rankine, phi={geom.phi_fill}°) = {res['ka']:.4f}")
    print(f"H_fill = {geom.H_fill:.2f} m")
    print()
    print(f"F fill zone = {res['F_fill_zone']:8.2f} kN/m  tai z = {res['z_fill_zone']:.3f} m")
    print()
    print(f"Moment ve mat dat ({geom.soil_level_front:.1f} m) = {res['M_about_soil_level']:8.2f} kN.m/m")
    print(f"Moment ve mui coc ({geom.pile_tip_elev:.1f} m)   = {res['M_about_pile_tip']:8.2f} kN.m/m")

    res["fig"].savefig("fill_lateral_force_demo.png", dpi=150, bbox_inches="tight")
    print()
    print("Saved: fill_lateral_force_demo.png")
