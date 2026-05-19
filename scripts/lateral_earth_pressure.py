"""
Lateral earth pressure — TCVN 11823-3:2017 §10.5–10.6
Computes active/passive/at-rest pressure profiles and plots GEO5-style diagrams.

Units: kN, m, degrees throughout (converts internally as needed).
"""

from __future__ import annotations

import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Coefficient formulas
# ---------------------------------------------------------------------------

def k0_nc(phi_deg: float) -> float:
    """At-rest coefficient for NC soil. k0 = 1 - sin(phi). Eq.23."""
    return 1.0 - math.sin(math.radians(phi_deg))


def k0_oc(phi_deg: float, ocr: float) -> float:
    """At-rest coefficient for OC soil. k0_oc = k0_nc * sqrt(OCR). Eq.24."""
    return k0_nc(phi_deg) * math.sqrt(ocr)


def ka_rankine(phi_deg: float) -> float:
    """Active coefficient, Rankine (vertical wall, horizontal fill, delta=0)."""
    return math.tan(math.radians(45.0 - phi_deg / 2.0)) ** 2


def kp_rankine(phi_deg: float) -> float:
    """Passive coefficient, Rankine (vertical wall, horizontal fill, delta=0)."""
    return math.tan(math.radians(45.0 + phi_deg / 2.0)) ** 2


def ka_coulomb(
    phi_deg: float,
    delta_deg: float = 0.0,
    beta_deg: float = 0.0,
    theta_deg: float = 90.0,
) -> float:
    """Active coefficient, Coulomb. Eq.25 TCVN 11823-3.

    Args:
        phi_deg:   Soil friction angle [°]
        delta_deg: Wall-soil interface friction angle [°] (see Bang 20)
        beta_deg:  Backfill slope from horizontal [°] (0 = flat)
        theta_deg: Wall inclination from horizontal [°] (90 = vertical)
    """
    phi   = math.radians(phi_deg)
    delta = math.radians(delta_deg)
    beta  = math.radians(beta_deg)
    theta = math.radians(theta_deg)

    sin_pd = math.sin(phi + delta)
    sin_pb = math.sin(phi - beta)
    sin_td = math.sin(theta - delta)
    sin_tb = math.sin(theta + beta)

    if sin_td <= 0 or sin_tb <= 0:
        return ka_rankine(phi_deg)

    gamma = 1.0 + math.sqrt(sin_pd * sin_pb / (sin_td * sin_tb))
    num   = math.sin(theta + phi) ** 2
    den   = gamma ** 2 * math.sin(theta) ** 2 * sin_td
    return num / den


def ka_coulomb_passive(
    phi_deg: float,
    delta_deg: float = 0.0,
    beta_deg: float = 0.0,
    theta_deg: float = 90.0,
) -> float:
    """Passive coefficient via modified Coulomb (reversed geometry)."""
    phi   = math.radians(phi_deg)
    delta = math.radians(delta_deg)
    beta  = math.radians(beta_deg)
    theta = math.radians(theta_deg)

    sin_pd = math.sin(phi + delta)
    sin_pb = math.sin(phi + beta)
    sin_tp = math.sin(theta + delta)
    sin_tb = math.sin(theta - beta)

    if sin_tp <= 0 or sin_tb <= 0:
        return kp_rankine(phi_deg)

    gamma = 1.0 - math.sqrt(sin_pd * sin_pb / (sin_tp * sin_tb))
    if abs(gamma) < 1e-12:
        return kp_rankine(phi_deg)
    num = math.sin(theta - phi) ** 2
    den = gamma ** 2 * math.sin(theta) ** 2 * sin_tp
    return num / den


# ---------------------------------------------------------------------------
# Layer and geometry data classes
# ---------------------------------------------------------------------------

@dataclass
class SoilLayer:
    tip_elev: float       # elevation of layer bottom [m], positive up
    gamma:    float       # moist unit weight [kN/m³]
    gamma_sub: float      # submerged unit weight [kN/m³]
    phi:      float       # friction angle [°]
    c:        float = 0.0 # cohesion [kN/m²]
    delta:    float = 0.0 # interface friction [°] (Bang 20)


@dataclass
class Geometry:
    top_elev:         float         # pile top elevation [m]
    water_elev_front: float         # water table elevation, front side [m]
    water_elev_back:  float         # water table elevation, back side [m]
    pile_length:      float         # total pile length [m]
    surcharge_front:  float = 0.0   # uniform surcharge on front [kN/m²]
    surcharge_back:   float = 0.0   # uniform surcharge on back [kN/m²]


# ---------------------------------------------------------------------------
# Pressure profile computation
# ---------------------------------------------------------------------------

def _build_z_nodes(top: float, layers: list[SoilLayer]) -> np.ndarray:
    """Elevation nodes from top down to deepest layer tip."""
    elevs = [top] + [lay.tip_elev for lay in layers]
    return np.array(sorted(set(elevs), reverse=True))


def compute_active_profile(
    geom: Geometry,
    back_layers: list[SoilLayer],
    fill: SoilLayer | None = None,
    ka_method: str = "rankine",
    delta_deg: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Active earth pressure profile on the back (retained) side.

    Returns:
        elevs   [m]:   elevation array, top to bottom
        sigma_h [kN/m²]: lateral earth pressure (without water)
        water_p [kN/m²]: hydrostatic water pressure
    """
    top   = geom.top_elev
    wl    = geom.water_elev_back
    layers = back_layers if back_layers else []

    # Merge fill as top layer if present
    all_layers: list[SoilLayer] = []
    if fill is not None and fill.tip_elev < top:
        all_layers.append(SoilLayer(
            tip_elev=fill.tip_elev,
            gamma=fill.gamma,
            gamma_sub=fill.gamma_sub,
            phi=fill.phi,
            c=fill.c,
            delta=fill.delta,
        ))
    all_layers.extend(layers)
    if not all_layers:
        return np.array([top]), np.array([0.0]), np.array([0.0])

    # Build evaluation elevations
    layer_bounds = [top] + [lay.tip_elev for lay in all_layers]
    bot = all_layers[-1].tip_elev
    elevs = np.array(sorted(set(layer_bounds), reverse=True))

    sigma_v  = np.zeros(len(elevs))
    sigma_h  = np.zeros(len(elevs))
    water_p  = np.zeros(len(elevs))

    # Accumulate vertical stress downward
    prev_elev = top
    prev_sv   = geom.surcharge_back  # include uniform surcharge as initial overburden

    for i, elev in enumerate(elevs):
        # Find which layer this elevation belongs to
        lay = _layer_at(elev, top, all_layers)
        if lay is None:
            break

        dz = prev_elev - elev
        above_wt = max(0.0, min(dz, prev_elev - wl)) if prev_elev > wl else 0.0
        below_wt = dz - above_wt

        gamma_eff = lay.gamma * (above_wt / dz) + lay.gamma_sub * (below_wt / dz) if dz > 0 else lay.gamma

        sv = prev_sv + gamma_eff * dz
        sigma_v[i] = sv

        if ka_method == "coulomb":
            ka = ka_coulomb(lay.phi, delta_deg)
        else:
            ka = ka_rankine(lay.phi)

        sigma_h[i] = ka * sv - 2 * lay.c * math.sqrt(max(ka, 0.0))
        sigma_h[i] = max(0.0, sigma_h[i])  # tension cut-off

        prev_elev = elev
        prev_sv   = sv

    for i, elev in enumerate(elevs):
        water_p[i] = max(0.0, wl - elev) * 9.81

    return elevs, sigma_h, water_p


def compute_passive_profile(
    geom: Geometry,
    front_layers: list[SoilLayer],
    ka_method: str = "rankine",
    delta_deg: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Passive earth pressure profile on the front (excavation) side.

    Returns:
        elevs   [m]:   elevation array, top to bottom
        sigma_h [kN/m²]: passive pressure
        water_p [kN/m²]: hydrostatic water pressure
    """
    top   = geom.top_elev
    wl    = geom.water_elev_front
    layers = front_layers if front_layers else []

    if not layers:
        return np.array([top]), np.array([0.0]), np.array([0.0])

    layer_bounds = [top] + [lay.tip_elev for lay in layers]
    elevs = np.array(sorted(set(layer_bounds), reverse=True))

    sigma_h = np.zeros(len(elevs))
    water_p = np.zeros(len(elevs))

    prev_elev = top
    prev_sv   = geom.surcharge_front

    for i, elev in enumerate(elevs):
        lay = _layer_at(elev, top, layers)
        if lay is None:
            break

        dz = prev_elev - elev
        above_wt = max(0.0, min(prev_elev, wl) - elev) if wl > elev else 0.0
        below_wt = max(0.0, dz - above_wt)

        if dz > 0:
            gamma_eff = (lay.gamma * above_wt + lay.gamma_sub * below_wt) / dz
        else:
            gamma_eff = lay.gamma

        sv = prev_sv + gamma_eff * dz

        if ka_method == "coulomb":
            kp = ka_coulomb_passive(lay.phi, delta_deg)
        else:
            kp = kp_rankine(lay.phi)

        sigma_h[i] = kp * sv + 2 * lay.c * math.sqrt(max(kp, 0.0))
        water_p[i] = max(0.0, wl - elev) * 9.81

        prev_elev = elev
        prev_sv   = sv

    return elevs, sigma_h, water_p


def _layer_at(elev: float, top: float, layers: list[SoilLayer]) -> SoilLayer | None:
    """Return the layer that contains the given elevation."""
    cur_top = top
    for lay in layers:
        if lay.tip_elev <= elev <= cur_top:
            return lay
        cur_top = lay.tip_elev
    return layers[-1] if layers else None


def resultant(elevs: np.ndarray, pressure: np.ndarray) -> tuple[float, float]:
    """Resultant force and point of application elevation.

    Returns:
        F [kN/m]: resultant force (trapezoid integration)
        z_app [m]: elevation of application
    """
    F = 0.0
    Mz = 0.0
    for i in range(len(elevs) - 1):
        dz = abs(elevs[i] - elevs[i + 1])
        p_avg = (pressure[i] + pressure[i + 1]) / 2.0
        z_avg = (elevs[i] + elevs[i + 1]) / 2.0
        F  += p_avg * dz
        Mz += p_avg * dz * z_avg
    z_app = Mz / F if F > 1e-9 else elevs[-1]
    return F, z_app


# ---------------------------------------------------------------------------
# GEO5-style pressure diagram
# ---------------------------------------------------------------------------

def plot_pressure_diagram(
    geom: Geometry,
    active_elevs:  np.ndarray,
    active_h:      np.ndarray,
    active_water:  np.ndarray,
    passive_elevs: np.ndarray,
    passive_h:     np.ndarray,
    passive_water: np.ndarray,
    front_layers:  list[SoilLayer] | None = None,
    back_layers:   list[SoilLayer] | None = None,
    title: str = "Earth Pressure Diagram",
) -> plt.Figure:
    """GEO5-style horizontal-bar pressure diagram.

    Layout: 4 sub-plots side by side
      [Active Earth] | [Water Pressure] | [Passive Earth] | [Net Pressure]
    """
    fig, axes = plt.subplots(1, 4, figsize=(14, 7), sharey=True)
    fig.suptitle(title, fontsize=10, fontweight="bold")

    bot_elev = min(active_elevs[-1], passive_elevs[-1])
    top_elev = geom.top_elev
    y_range  = [bot_elev - 0.5, top_elev + 1.0]

    _plot_horizontal_bars(axes[0], active_elevs,  active_h,
                          "Active Earth Pressure\n[kN/m²]", "tomato", y_range,
                          positive_dir="left")
    _plot_horizontal_bars(axes[1], active_elevs,  active_water,
                          "Water Pressure (Back)\n[kN/m²]", "steelblue", y_range,
                          positive_dir="left")
    _plot_horizontal_bars(axes[2], passive_elevs, passive_h,
                          "Passive Earth Pressure\n[kN/m²]", "mediumseagreen", y_range,
                          positive_dir="right")

    # Net pressure = passive - active (interpolate to common grid)
    common_elevs = np.sort(np.unique(np.concatenate([active_elevs, passive_elevs])))[::-1]
    net_a = np.interp(common_elevs, active_elevs[::-1],  active_h[::-1])
    net_p = np.interp(common_elevs, passive_elevs[::-1], passive_h[::-1])
    net   = net_p - net_a

    pos_mask = net >= 0
    neg_mask = net < 0
    if pos_mask.any():
        _plot_horizontal_bars(axes[3],
                              common_elevs[pos_mask], net[pos_mask],
                              "Net Pressure\n[kN/m²]", "mediumseagreen", y_range,
                              positive_dir="right", label="Passive dominates")
    if neg_mask.any():
        _plot_horizontal_bars(axes[3],
                              common_elevs[neg_mask], np.abs(net[neg_mask]),
                              "", "tomato", y_range,
                              positive_dir="left", label="Active dominates")
    axes[3].set_title("Net Pressure\n[kN/m²]", fontsize=8)

    # Common y-axis decoration
    for ax in axes:
        ax.axhline(geom.top_elev, color="#888", lw=0.8, ls="--")
        ax.axhline(geom.water_elev_front, color="steelblue", lw=0.8, ls=":")
        if front_layers:
            for lay in front_layers:
                ax.axhline(lay.tip_elev, color="#bbb", lw=0.5, ls="--")
        if back_layers:
            for lay in back_layers:
                ax.axhline(lay.tip_elev, color="#ddd", lw=0.5, ls="--")
        ax.set_ylim(y_range)
        ax.yaxis.set_minor_locator(AutoMinorLocator())
        ax.tick_params(axis="both", labelsize=7)
        ax.grid(axis="y", lw=0.3, color="#eee")

    axes[0].set_ylabel("Elevation [m]", fontsize=8)
    fig.tight_layout()
    return fig


def _plot_horizontal_bars(
    ax: plt.Axes,
    elevs: np.ndarray,
    values: np.ndarray,
    title: str,
    color: str,
    y_range: list[float],
    positive_dir: str = "left",
    label: str = "",
) -> None:
    """Draw filled horizontal pressure bars."""
    if len(elevs) < 2:
        ax.set_title(title, fontsize=8)
        return

    sign = -1 if positive_dir == "left" else 1
    ax.fill_betweenx(elevs, 0, sign * values, color=color, alpha=0.35, label=label)
    ax.plot(sign * values, elevs, color=color, lw=1.2)
    ax.axvline(0, color="black", lw=0.8)

    # Label max value
    i_max = np.argmax(np.abs(values))
    if abs(values[i_max]) > 0.5:
        ax.text(sign * values[i_max], elevs[i_max],
                f" {values[i_max]:.1f}", fontsize=6, va="center",
                ha="left" if positive_dir == "right" else "right", color=color)

    ax.set_title(title, fontsize=8)
    if label:
        ax.legend(fontsize=6)


# ---------------------------------------------------------------------------
# Convenience: build layers from dict list (matches app_coc_tai_ngang format)
# ---------------------------------------------------------------------------

def layers_from_df_records(
    records: list[dict],
    top_elev: float,
    water_elev: float,
) -> list[SoilLayer]:
    """Convert st.data_editor rows → SoilLayer list.

    Expected keys per row: 'Layer Tip [m]', 'Density Moist [kN/m3]',
    'Density Sub [kN/m3]', 'Phi [Deg]', 'Cohesion [kN/m2]', 'Delta [Deg]'
    """
    layers = []
    for row in records:
        tip  = float(row.get("Layer Tip [m]", top_elev - 1.0))
        gm   = float(row.get("Density Moist [kN/m3]", 18.0))
        gs   = float(row.get("Density Sub [kN/m3]", gm - 10.0))
        phi  = float(row.get("Phi [Deg]", 25.0))
        c    = float(row.get("Cohesion [kN/m2]", 0.0))
        dlt  = float(row.get("Delta [Deg]", 0.0))
        layers.append(SoilLayer(tip_elev=tip, gamma=gm, gamma_sub=gs, phi=phi, c=c, delta=dlt))
    return layers


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    geom = Geometry(
        top_elev=2.7,
        water_elev_front=0.0,
        water_elev_back=0.0,
        pile_length=29.0,
    )

    back = [
        SoilLayer(tip_elev=-5.0,  gamma=18.0, gamma_sub=8.0,  phi=28.0, c=0.0),
        SoilLayer(tip_elev=-15.0, gamma=19.0, gamma_sub=9.0,  phi=30.0, c=5.0),
        SoilLayer(tip_elev=-26.3, gamma=20.0, gamma_sub=10.0, phi=32.0, c=0.0),
    ]
    front = [
        SoilLayer(tip_elev=0.0,   gamma=18.0, gamma_sub=8.0,  phi=28.0, c=0.0),
        SoilLayer(tip_elev=-10.0, gamma=19.0, gamma_sub=9.0,  phi=30.0, c=5.0),
        SoilLayer(tip_elev=-26.3, gamma=20.0, gamma_sub=10.0, phi=32.0, c=0.0),
    ]

    fill = SoilLayer(tip_elev=0.0, gamma=18.0, gamma_sub=8.0, phi=25.0, c=5.0)

    a_elevs, a_h, a_w = compute_active_profile(geom, back, fill=fill)
    p_elevs, p_h, p_w = compute_passive_profile(geom, front)

    Fa, za = resultant(a_elevs, a_h)
    Fp, zp = resultant(p_elevs, p_h)
    print(f"Active resultant:  F = {Fa:.1f} kN/m  at elev = {za:.2f} m")
    print(f"Passive resultant: F = {Fp:.1f} kN/m  at elev = {zp:.2f} m")

    fig = plot_pressure_diagram(
        geom,
        a_elevs, a_h, a_w,
        p_elevs, p_h, p_w,
        front_layers=front,
        back_layers=back,
        title="Lateral Earth Pressure — Demo (top_elev = 2.7 m)",
    )
    out = "lateral_pressure_demo.png"
    fig.savefig(out, dpi=110, bbox_inches="tight")
    print(f"Saved: {out}")
