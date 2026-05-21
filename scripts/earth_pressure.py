"""
Earth pressure diagram — Active (Front/LEFT) + Passive (Back/RIGHT)
TCVN 11823-3:2017 §10.5

Convention (thống nhất với tab GeoData):
  Front = LEFT  = Active  (Ka) — bao gồm lớp đất đắp (fill)
  Back  = RIGHT = Passive (Kp) — không có đất đắp

Units: kN, m, degrees. Elevation positive upward.
"""

from __future__ import annotations

import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
from dataclasses import dataclass

try:
    from lateral_earth_pressure import (
        ka_rankine, ka_coulomb, kp_rankine, ka_coulomb_passive, SoilLayer,
    )
except ImportError:
    def ka_rankine(phi_deg: float) -> float:
        return math.tan(math.radians(45.0 - phi_deg / 2.0)) ** 2

    def kp_rankine(phi_deg: float) -> float:
        return math.tan(math.radians(45.0 + phi_deg / 2.0)) ** 2

    def ka_coulomb(phi_deg, delta_deg=0.0, beta_deg=0.0, theta_deg=90.0):
        return ka_rankine(phi_deg)

    def ka_coulomb_passive(phi_deg, delta_deg=0.0, beta_deg=0.0, theta_deg=90.0):
        return kp_rankine(phi_deg)

    @dataclass
    class SoilLayer:
        tip_elev:  float
        gamma:     float
        gamma_sub: float
        phi:       float
        c:         float = 0.0
        delta:     float = 0.0


# ---------------------------------------------------------------------------
# Geometry dataclass
# ---------------------------------------------------------------------------

@dataclass
class EpGeometry:
    top_elev:          float = 2.7    # cao độ đỉnh cừ [m]
    pile_length:       float = 20.0   # chiều dài cừ [m]
    soil_level_front:  float = 0.0    # cao độ mặt đất Front (chân đất đắp) [m]
    soil_level_back:   float = 0.0    # cao độ mặt đất Back [m]
    water_elev_front:  float = -1.0   # mực nước Front [m]
    water_elev_back:   float = -1.0   # mực nước Back [m]
    surcharge_front:   float = 0.0    # tải trọng phân bố đỉnh cừ Front [kN/m²]

    @property
    def bot_elev(self) -> float:
        return self.top_elev - self.pile_length

    @property
    def fill_thickness(self) -> float:
        return max(0.0, self.top_elev - self.soil_level_front)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _eff_gamma(gamma: float, gamma_sub: float,
               e_top: float, e_bot: float, water_elev: float) -> float:
    """Dung trọng hữu hiệu trung bình cho đoạn [e_bot, e_top]."""
    dz = e_top - e_bot
    if dz <= 1e-9:
        return gamma
    wl = water_elev
    if wl >= e_top:            # hoàn toàn trên mực nước
        return gamma
    if wl <= e_bot:            # hoàn toàn dưới mực nước
        return gamma_sub
    dz_dry = e_top - wl
    dz_wet = wl - e_bot
    return (gamma * dz_dry + gamma_sub * dz_wet) / dz


def _layer_at(elev: float, ref_top: float, layers: list[SoilLayer]) -> SoilLayer | None:
    """Tìm lớp chứa cao độ elev (layers sắp xếp từ nông đến sâu).

    Trả None nếu elev nằm DƯỚI lớp đáy cùng — tránh fallback gây sai khi PA sau
    xử lý CDM (Front chỉ còn fill đến z_mat, dưới z_mat phải là 0).
    """
    cur_top = ref_top
    for lay in layers:
        if lay.tip_elev <= elev <= cur_top:
            return lay
        cur_top = lay.tip_elev
    return None   # không fallback — sigma_h = 0 dưới lớp đáy


def _build_grid(geom: EpGeometry,
                front_layers: list[SoilLayer],
                back_layers: list[SoilLayer],
                n: int = 250) -> np.ndarray:
    """Lưới cao độ với các điểm gãy tại ranh giới lớp, mực nước, mặt đất."""
    keys = sorted({
        geom.top_elev,
        geom.soil_level_front,
        geom.soil_level_back,
        geom.water_elev_front,
        geom.water_elev_back,
        geom.bot_elev,
        *[l.tip_elev for l in front_layers],
        *[l.tip_elev for l in back_layers],
    }, reverse=True)
    keys = [k for k in keys if geom.bot_elev <= k <= geom.top_elev]
    segs = []
    for i in range(len(keys) - 1):
        seg = np.linspace(keys[i], keys[i + 1], max(3, n // max(len(keys) - 1, 1)))
        segs.append(seg[:-1])
    segs.append(np.array([keys[-1]]))
    return np.concatenate(segs)


# ---------------------------------------------------------------------------
# Active pressure — Front (LEFT) side
# ---------------------------------------------------------------------------

def compute_active_front(
    geom: EpGeometry,
    front_layers: list[SoilLayer],
    fill: SoilLayer | None,
    elevs: np.ndarray,
    ka_method: str = "rankine",
    delta_deg: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Áp lực đất chủ động (Active) phía Front (TRÁI).

    Lớp đất đắp (fill) nằm từ soil_level_front lên đến top_elev.
    Bên dưới soil_level_front là các lớp đất tự nhiên (front_layers).

    Returns:
        sigma_h [kN/m²]: áp lực ngang chủ động
        sigma_v [kN/m²]: ứng suất đứng hữu hiệu
    """
    wl = geom.water_elev_front

    # Ghép fill vào đầu danh sách lớp
    all_layers: list[SoilLayer] = []
    if fill is not None and geom.fill_thickness > 0:
        fill_lay = SoilLayer(
            tip_elev=geom.soil_level_front,
            gamma=fill.gamma,
            gamma_sub=fill.gamma_sub,
            phi=fill.phi,
            c=fill.c,
        )
        all_layers.append(fill_lay)
    all_layers.extend(front_layers)

    sigma_h = np.zeros(len(elevs))
    sigma_v = np.zeros(len(elevs))

    prev_e = geom.top_elev
    sv = geom.surcharge_front   # tải trọng mặt

    for i, e in enumerate(elevs):
        lay = _layer_at(e, geom.top_elev, all_layers)
        if lay is None:
            prev_e = e
            continue

        dz = prev_e - e
        if dz > 0:
            sv += _eff_gamma(lay.gamma, lay.gamma_sub, prev_e, e, wl) * dz

        sigma_v[i] = sv

        if ka_method == "coulomb":
            ka = ka_coulomb(lay.phi, delta_deg)
        else:
            ka = ka_rankine(lay.phi)

        sh = ka * sv - 2.0 * lay.c * math.sqrt(max(ka, 0.0))
        sigma_h[i] = max(0.0, sh)   # cắt kéo

        prev_e = e

    return sigma_h, sigma_v


# ---------------------------------------------------------------------------
# Passive pressure — Back (RIGHT) side
# ---------------------------------------------------------------------------

def compute_passive_back(
    geom: EpGeometry,
    back_layers: list[SoilLayer],
    elevs: np.ndarray,
    kp_method: str = "rankine",
    delta_deg: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Áp lực đất bị động (Passive) phía Back (PHẢI).

    Không có áp lực bên trên soil_level_back (phần trên = hở / mặt nước).

    Returns:
        sigma_h [kN/m²]: áp lực ngang bị động
        sigma_v [kN/m²]: ứng suất đứng hữu hiệu
    """
    wl = geom.water_elev_back
    sigma_h = np.zeros(len(elevs))
    sigma_v = np.zeros(len(elevs))

    prev_e = geom.soil_level_back
    sv = 0.0

    for i, e in enumerate(elevs):
        if e > geom.soil_level_back:
            # Trên mặt đất Back: không có áp lực bị động
            prev_e = e
            continue

        lay = _layer_at(e, geom.soil_level_back, back_layers)
        if lay is None:
            prev_e = e
            continue

        dz = prev_e - e
        if dz > 0:
            sv += _eff_gamma(lay.gamma, lay.gamma_sub, prev_e, e, wl) * dz

        sigma_v[i] = sv

        if kp_method == "coulomb":
            kp = ka_coulomb_passive(lay.phi, delta_deg)
        else:
            kp = kp_rankine(lay.phi)

        sigma_h[i] = kp * sv + 2.0 * lay.c * math.sqrt(max(kp, 0.0))

        prev_e = e

    return sigma_h, sigma_v


# ---------------------------------------------------------------------------
# Resultant
# ---------------------------------------------------------------------------

def resultant(elevs: np.ndarray, pressure: np.ndarray) -> tuple[float, float]:
    """Lực tổng hợp và cao độ điểm đặt lực.

    Returns:
        F [kN/m], z_app [m]
    """
    F = 0.0
    Mz = 0.0
    for i in range(len(elevs) - 1):
        dz   = abs(elevs[i] - elevs[i + 1])
        pavg = (pressure[i] + pressure[i + 1]) / 2.0
        zavg = (elevs[i] + elevs[i + 1]) / 2.0
        F  += pavg * dz
        Mz += pavg * dz * zavg
    z_app = Mz / F if abs(F) > 1e-9 else elevs[-1]
    return F, z_app


# ---------------------------------------------------------------------------
# GEO5-style diagram — 3 panels
# ---------------------------------------------------------------------------

def plot_earth_pressure_diagram(
    geom: EpGeometry,
    elevs: np.ndarray,
    active_h: np.ndarray,
    passive_h: np.ndarray,
    front_layers: list[SoilLayer] | None = None,
    back_layers: list[SoilLayer] | None = None,
    fill: SoilLayer | None = None,
    title: str = "Earth Pressure Diagram",
    front_soil_types: list[str] | None = None,
    front_sus: list[float] | None = None,
    back_soil_types: list[str] | None = None,
    back_sus: list[float] | None = None,
) -> plt.Figure:
    """Biểu đồ áp lực đất GEO5-style — 3 panel.

    Quy tắc thống nhất với GeoData tab:
      Panel 1 [Front/TRÁI]:  Active (Ka) — bars sang TRÁI — màu đỏ/tomato
      Panel 2 [Net]:         Active − Passive; dương → bars sang PHẢI (nguy hiểm)
      Panel 3 [Back/PHẢI]:   Passive (Kp) — bars sang PHẢI — màu xanh lá

    front_soil_types / back_soil_types: list of 'Sand' or 'Clay' per layer (optional)
    front_sus / back_sus: undrained shear strength Su per clay layer (optional)
    """
    fig, axes = plt.subplots(1, 3, figsize=(11, 8), sharey=True,
                             layout="constrained")
    fig.suptitle(title, fontsize=10, fontweight="bold")

    bot = geom.bot_elev
    y_range = [bot - 0.5, geom.top_elev + 1.2]

    # --- Panel 1: Active — Front (TRÁI), bars sang TRÁI
    _draw_bars(axes[0], elevs, active_h, "tomato",
               "Active Earth Pressure\nFront [kN/m²]", direction="left")
    _add_fill_indicator(axes[0], geom, fill)

    # --- Panel 3: Passive — Back (PHẢI), bars sang PHẢI
    _draw_bars(axes[2], elevs, passive_h, "mediumseagreen",
               "Passive Earth Pressure\nBack [kN/m²]", direction="right")

    # --- Panel 2: Net = Active − Passive
    net = active_h - passive_h
    net_pos = np.where(net >= 0, net, 0.0)   # Active > Passive → nguy hiểm
    net_neg = np.where(net <  0, -net, 0.0)  # Passive > Active → ổn định
    if net_pos.max() > 0.5:
        _draw_bars(axes[1], elevs, net_pos, "tomato",
                   "Net Earth Pressure\n[kN/m²]", direction="right",
                   label="Active > Passive")
    if net_neg.max() > 0.5:
        _draw_bars(axes[1], elevs, net_neg, "mediumseagreen",
                   "Net Earth Pressure\n[kN/m²]", direction="left",
                   label="Passive > Active")
    axes[1].set_title("Net Pressure\n[kN/m²]", fontsize=8)

    # --- Resultants
    F_a, z_a = resultant(elevs, active_h)
    F_p, z_p = resultant(elevs, passive_h)
    F_n, z_n = resultant(elevs, np.abs(net))
    _annotate_resultant(axes[0], F_a, z_a, "left",  "tomato")
    _annotate_resultant(axes[2], F_p, z_p, "right", "mediumseagreen")
    _annotate_resultant(axes[1], F_n, z_n,
                        "right" if net.mean() >= 0 else "left",
                        "tomato" if net.mean() >= 0 else "mediumseagreen")

    # --- Reference lines
    ref_lines = [
        (geom.top_elev,         "#555",        "--", 0.8, f"SP Top  {geom.top_elev:.2f} m"),
        (geom.soil_level_front, "tomato",      "-.", 0.9, f"GND Front {geom.soil_level_front:.2f} m"),
        (geom.soil_level_back,  "mediumseagreen",":", 0.9, f"GND Back  {geom.soil_level_back:.2f} m"),
        (geom.water_elev_front, "#1a8cff",     ":",  1.0, f"WL Front  {geom.water_elev_front:.2f} m"),
        (geom.water_elev_back,  "steelblue",   "-.", 1.0, f"WL Back   {geom.water_elev_back:.2f} m"),
        (geom.bot_elev,         "#444",        "-",  0.8, f"Pile Tip  {geom.bot_elev:.2f} m"),
    ]
    for ax in axes:
        for elev, color, ls, lw, lbl in ref_lines:
            ax.axhline(elev, color=color, lw=lw, ls=ls, alpha=0.6)
        ax.set_ylim(y_range)
        ax.yaxis.set_minor_locator(AutoMinorLocator())
        ax.tick_params(axis="both", labelsize=7)
        ax.grid(axis="y", lw=0.3, color="#eee")
        ax.axvline(0, color="black", lw=0.8)

    # --- Layer boundaries (chỉ vẽ đường, bỏ label Sand/Clay vì gây rối)
    if front_layers:
        for lay in front_layers:
            axes[0].axhline(lay.tip_elev, color="#faa", lw=0.5, ls="--")
            axes[1].axhline(lay.tip_elev, color="#faa", lw=0.5, ls="--")

    if back_layers:
        for lay in back_layers:
            axes[2].axhline(lay.tip_elev, color="#afa", lw=0.5, ls="--")
            axes[1].axhline(lay.tip_elev, color="#cec", lw=0.5, ls="--")

    axes[0].set_ylabel("Elevation [m]", fontsize=8)

    # Legend ở panel 2
    handles = [plt.Line2D([0], [0], color=c, lw=lw, ls=ls, label=lbl)
               for _, c, ls, lw, lbl in ref_lines]
    axes[1].legend(handles=handles, fontsize=6, loc="lower right", framealpha=0.6)

    return fig


def _draw_pressure_arrows(
    ax: plt.Axes,
    elevs: np.ndarray,
    values: np.ndarray,
    color: str,
    sign: int,
    spacing: float = 2.0,
) -> None:
    """Horizontal quiver arrows every `spacing` metres — visualise pressure magnitude."""
    e_top, e_bot = float(elevs[0]), float(elevs[-1])
    n = max(2, round((e_top - e_bot) / spacing) + 1)
    arr_e = np.linspace(e_top, e_bot, n)
    arr_v = np.interp(arr_e, elevs[::-1], values[::-1])
    mask = arr_v > 0.5
    if not mask.any():
        return
    ax.quiver(
        -sign * arr_v[mask], arr_e[mask],
        sign * arr_v[mask], np.zeros(mask.sum()),
        scale_units="xy", scale=1.0, angles="xy",
        color=color, alpha=0.60,
        width=0.005, headwidth=4, headlength=5, zorder=3,
    )


def _draw_bars(ax: plt.Axes, elevs: np.ndarray, values: np.ndarray,
               color: str, title: str, direction: str = "left",
               label: str = "", arrow_spacing: float = 2.0) -> None:
    sign = -1 if direction == "left" else 1
    ax.fill_betweenx(elevs, 0, sign * values, color=color, alpha=0.18,
                     label=label or None)
    ax.plot(sign * values, elevs, color=color, lw=1.5)
    _draw_pressure_arrows(ax, elevs, values, color, -sign, arrow_spacing)
    if label:
        ax.legend(fontsize=6)
    ax.set_title(title, fontsize=8)
    i_max = int(np.argmax(values))
    if values[i_max] > 0.5:
        ax.text(sign * values[i_max], elevs[i_max],
                f" {values[i_max]:.1f}",
                fontsize=6.5, va="center",
                ha="left" if direction == "right" else "right",
                color=color, fontweight="bold")


def _add_fill_indicator(ax: plt.Axes, geom: EpGeometry,
                        fill: SoilLayer | None) -> None:
    """Vẽ vùng đất đắp (fill) trong panel Active bằng hatch.

    Label đặt ở góc phải-trên của vùng fill (right-aligned, padding nhỏ vào trong)
    để không đè lên biểu đồ áp lực và các annotation khác.
    """
    if fill is None or geom.fill_thickness <= 0:
        return
    ax.axhspan(geom.soil_level_front, geom.top_elev,
               color="sandybrown", alpha=0.18, hatch="\\\\", zorder=0)
    # Đặt label ở góc phải-trên, cách lề trên 5% chiều dày fill
    y_top = geom.top_elev - 0.05 * geom.fill_thickness
    ax.text(0.98, y_top,
            f"Đất đắp Front (Fill)\nγ={fill.gamma:.1f} kN/m³  "
            f"φ={fill.phi:.1f}°  c={fill.c:.1f} kPa",
            transform=ax.get_yaxis_transform(),
            fontsize=6, color="#8B4513",
            ha="right", va="top", style="italic", linespacing=1.3,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                       edgecolor="#c9a577", alpha=0.85, linewidth=0.5),
            zorder=11)


def _annotate_resultant(ax: plt.Axes, F: float, z: float,
                        direction: str, color: str) -> None:
    if abs(F) < 0.5:
        return
    x_lim = ax.get_xlim()
    x_pos = x_lim[0] * 0.55 if direction == "left" else x_lim[1] * 0.55
    ax.annotate(
        f"F = {abs(F):.1f} kN/m",
        xy=(0, z), xycoords="data",
        xytext=(x_pos, z),
        fontsize=6.5, color=color, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=color, lw=0.8),
        va="center",
    )


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def compute_all(
    geom: EpGeometry,
    front_layers: list[SoilLayer],
    back_layers: list[SoilLayer],
    fill: SoilLayer | None = None,
    ka_method: str = "rankine",
    kp_method: str = "rankine",
    delta_deg: float = 0.0,
    front_soil_types: list[str] | None = None,
    front_sus: list[float] | None = None,
    back_soil_types: list[str] | None = None,
    back_sus: list[float] | None = None,
) -> dict:
    """Tính toán đầy đủ + vẽ biểu đồ.

    Returns dict: elevs, active_h, passive_h, net_h,
                  F_active, z_active, F_passive, z_passive, F_net, z_net, fig
    """
    elevs = _build_grid(geom, front_layers, back_layers)

    active_h,  sv_front = compute_active_front(
        geom, front_layers, fill, elevs, ka_method, delta_deg)
    passive_h, sv_back  = compute_passive_back(
        geom, back_layers, elevs, kp_method, delta_deg)

    net_h = active_h - passive_h

    F_a, z_a = resultant(elevs, active_h)
    F_p, z_p = resultant(elevs, passive_h)
    F_n, z_n = resultant(elevs, np.abs(net_h))

    fig = plot_earth_pressure_diagram(
        geom, elevs, active_h, passive_h,
        front_layers=front_layers,
        back_layers=back_layers,
        fill=fill,
        title=(f"Earth Pressure  |  Ka={ka_method}  Kp={kp_method}"
               f"  |  top_elev={geom.top_elev:.1f} m"),
        front_soil_types=front_soil_types,
        front_sus=front_sus,
        back_soil_types=back_soil_types,
        back_sus=back_sus,
    )

    return {
        "elevs":    elevs,
        "active_h": active_h,
        "passive_h": passive_h,
        "net_h":    net_h,
        "sv_front": sv_front,
        "sv_back":  sv_back,
        "F_active":  F_a,  "z_active":  z_a,
        "F_passive": F_p,  "z_passive": z_p,
        "F_net":     F_n,  "z_net":     z_n,
        "fig":      fig,
    }


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    geom = EpGeometry(
        top_elev=2.7,
        pile_length=29.0,
        soil_level_front=0.0,
        soil_level_back=0.0,
        water_elev_front=0.0,
        water_elev_back=0.0,
        surcharge_front=0.0,
    )

    fill = SoilLayer(tip_elev=0.0, gamma=18.0, gamma_sub=8.0, phi=25.0, c=5.0)

    front_layers = [
        SoilLayer(tip_elev=-5.0,  gamma=18.0, gamma_sub=8.0,  phi=28.0, c=0.0),
        SoilLayer(tip_elev=-15.0, gamma=19.0, gamma_sub=9.0,  phi=30.0, c=5.0),
        SoilLayer(tip_elev=-26.3, gamma=20.0, gamma_sub=10.0, phi=32.0, c=0.0),
    ]
    back_layers = [
        SoilLayer(tip_elev=-5.0,  gamma=18.0, gamma_sub=8.0,  phi=28.0, c=0.0),
        SoilLayer(tip_elev=-15.0, gamma=19.0, gamma_sub=9.0,  phi=30.0, c=5.0),
        SoilLayer(tip_elev=-26.3, gamma=20.0, gamma_sub=10.0, phi=32.0, c=0.0),
    ]

    res = compute_all(geom, front_layers, back_layers, fill=fill)

    print(f"Active  (Front): F = {res['F_active']:.1f} kN/m  at z = {res['z_active']:.2f} m")
    print(f"Passive (Back):  F = {res['F_passive']:.1f} kN/m  at z = {res['z_passive']:.2f} m")
    print(f"Net (A-P):       F = {res['F_net']:.1f} kN/m  at z = {res['z_net']:.2f} m")

    out = "earth_pressure_demo.png"
    res["fig"].savefig(out, dpi=110, bbox_inches="tight")
    print(f"Saved: {out}")
