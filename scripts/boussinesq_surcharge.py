"""
Boussinesq strip surcharge lateral pressure — TCVN 11823-3:2017 §10.6.2, Eq. 39.
Formula: Dph = (2p/pi) * [delta - sin(delta)*cos(delta + 2*alpha)]
Supports Front and Back sides independently.
Discretization: spacing=1.0 m (1 evaluation point per metre of pile length).
"""
from __future__ import annotations

import sys
import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SurchargeStrip:
    """One strip surcharge load on Front or Back side of the wall."""
    q: float            # intensity [kN/m²]
    a: float            # distance from wall face to near edge [m] (0 = at wall)
    w: float            # strip width [m] (>= 100 m ≈ semi-infinite)
    ref_surface: float  # elevation of load application surface [m]
    side: str = "Front" # "Front" or "Back"
    label: str = "Surcharge"
    color: str = "tomato"


@dataclass
class BoussiGeometry:
    """Pile/wall geometry for Boussinesq diagram."""
    top_elev: float = 2.7           # pile top elevation [m]
    pile_length: float = 20.0       # pile total length [m]
    soil_level_front: float = 0.0   # natural ground level — Front side [m]
    soil_level_back: float = 0.0    # natural ground level — Back side [m]

    @property
    def pile_tip_elev(self) -> float:
        return self.top_elev - self.pile_length


# ── Core formula ──────────────────────────────────────────────────────────────

def delta_ph_at_elev(
    elev: float,
    strip: SurchargeStrip,
    soil_surface: Optional[float] = None,
) -> float:
    """
    Boussinesq lateral pressure at elevation `elev` from one strip.
    Returns 0 if elev >= load surface (z <= 0).
    """
    ref = soil_surface if soil_surface is not None else strip.ref_surface
    z = ref - elev
    if z <= 0.0:
        return 0.0

    a, w = strip.a, strip.w
    beta1 = math.atan(a / z)
    beta2 = math.atan((a + w) / z)

    dph = (2.0 * strip.q / math.pi) * (
        (beta2 - beta1)
        - math.sin(beta2) * math.cos(beta2)
        + math.sin(beta1) * math.cos(beta1)
    )
    return max(dph, 0.0)


# ── Profile computation ────────────────────────────────────────────────────────

def _side_profile(
    strips: list[SurchargeStrip],
    elevs: np.ndarray,
    top: float,
    tip: float,
    soil_level: float,
) -> dict:
    """Compute pressure profile and resultant for one list of strips."""
    n = len(elevs)
    total = np.zeros(n)
    strip_pressures: dict[str, np.ndarray] = {}

    for strip in strips:
        arr = np.array([delta_ph_at_elev(e, strip, strip.ref_surface) for e in elevs])
        strip_pressures[strip.label] = arr
        total += arr

    F = float(np.trapz(total, -elevs))
    if F > 1e-6:
        z_app = float(np.trapz(total * elevs, -elevs)) / F
    else:
        z_app = soil_level

    return {
        "pressure": total,
        "strip_pressures": strip_pressures,
        "F": F,
        "z_app": z_app,
        "M_top": F * (z_app - top),
        "M_tip": F * (z_app - tip),
    }


def compute_all(
    geom: BoussiGeometry,
    strips: list[SurchargeStrip],
    spacing: float = 1.0,
) -> dict:
    """
    Full Boussinesq computation for all strips (Front + Back) + figure.

    spacing: evaluation point interval [m] (default 1.0 = 1 pt/m).

    Returns dict keys:
        elevs                          — elevation array [m]
        front_pressure, back_pressure  — Dph arrays [kN/m²]
        F_front, z_front, M_top_front, M_tip_front
        F_back,  z_back,  M_top_back,  M_tip_back
        F_net                          — F_front - F_back [kN/m]
        fig                            — matplotlib Figure
    """
    top = geom.top_elev
    tip = geom.pile_tip_elev
    n_pts = max(3, round(geom.pile_length / spacing) + 1)
    elevs = np.linspace(top, tip, n_pts)

    front_strips = [s for s in strips if s.side.lower() == "front"]
    back_strips  = [s for s in strips if s.side.lower() != "front"]

    f = _side_profile(front_strips, elevs, top, tip, geom.soil_level_front)
    b = _side_profile(back_strips,  elevs, top, tip, geom.soil_level_back)

    fig = _plot(geom, strips, elevs, f, b)

    return {
        "elevs": elevs,
        "front_pressure": f["pressure"],
        "back_pressure":  b["pressure"],
        "F_front": f["F"],   "z_front": f["z_app"],
        "M_top_front": f["M_top"], "M_tip_front": f["M_tip"],
        "F_back":  b["F"],   "z_back":  b["z_app"],
        "M_top_back":  b["M_top"], "M_tip_back":  b["M_tip"],
        "F_net": f["F"] - b["F"],
        "fig": fig,
    }


# backward-compat alias used by old callers
def compute_profile(geom, strips, spacing=1.0):
    top = geom.top_elev
    tip = geom.pile_tip_elev
    n_pts = max(3, round(geom.pile_length / spacing) + 1)
    elevs = np.linspace(top, tip, n_pts)
    prof = _side_profile(strips, elevs, top, tip, geom.soil_level_front)
    prof["elevs"] = elevs
    return prof


# ── Figure ────────────────────────────────────────────────────────────────────

_C_FRONT = "#c0392b"   # firebrick-red for Front
_C_BACK  = "#2471a3"   # steel-blue for Back
_C_WALL  = "#5d6d7e"   # wall pile colour


def _plot(
    geom: BoussiGeometry,
    strips: list[SurchargeStrip],
    elevs: np.ndarray,
    f: dict,   # front profile
    b: dict,   # back profile
) -> plt.Figure:
    """
    3-panel figure: [Front Pressure | Wall + Arrows | Back Pressure]
    Left panel:   Front Dph polyline, x-axis inverted (wall on right).
    Middle panel: Pile + quiver arrows from both sides + polylines.
    Right panel:  Back Dph polyline, x-axis normal (wall on left).
    """
    front_p = f["pressure"]
    back_p  = b["pressure"]
    top  = geom.top_elev
    tip  = geom.pile_tip_elev
    slf  = geom.soil_level_front
    slb  = geom.soil_level_back
    y_bot = tip  - 0.5
    y_top = top  + 1.8

    fig = plt.figure(figsize=(13, 8))
    fig.suptitle(
        "Boussinesq Strip Surcharge — TCVN 11823-3:2017 §10.6.2 Eq.(39)",
        fontsize=11, fontweight="bold",
    )
    gs = gridspec.GridSpec(1, 3, width_ratios=[1, 0.75, 1], wspace=0.04, figure=fig)
    ax_F = fig.add_subplot(gs[0])
    ax_W = fig.add_subplot(gs[1], sharey=ax_F)
    ax_B = fig.add_subplot(gs[2], sharey=ax_F)

    # ── Common reference lines ────────────────────────────────────────────────
    for ax in (ax_F, ax_W, ax_B):
        ax.set_ylim(y_bot, y_top)
        ax.axhline(top, color="k", lw=1.2, ls=":", alpha=0.6)
        ax.axhline(tip, color="#777", lw=0.8, ls=":", alpha=0.5)
        ax.grid(True, alpha=0.25, ls=":")

    # ── LEFT panel — Front pressure ───────────────────────────────────────────
    _draw_pressure_panel(
        ax_F, elevs, front_p,
        [s for s in strips if s.side.lower() == "front"],
        color=_C_FRONT, side="Front",
        F=f["F"], z_app=f["z_app"],
        slf=slf, top=top, tip=tip,
        invert=True,
    )
    ax_F.set_ylabel("Cao do [m]", fontsize=9)
    ax_F.set_title("Front — Dph [kN/m²]", fontsize=9, color=_C_FRONT)

    # ── MIDDLE panel — Wall + arrows ──────────────────────────────────────────
    _draw_wall_panel(ax_W, geom, strips, elevs, front_p, back_p, f, b)
    ax_W.set_title("So do tuong/coc\nvoi mui ten tai trong", fontsize=8)
    plt.setp(ax_W.get_yticklabels(), visible=False)

    # ── RIGHT panel — Back pressure ───────────────────────────────────────────
    _draw_pressure_panel(
        ax_B, elevs, back_p,
        [s for s in strips if s.side.lower() != "front"],
        color=_C_BACK, side="Back",
        F=b["F"], z_app=b["z_app"],
        slf=slb, top=top, tip=tip,
        invert=False,
    )
    ax_B.set_title("Back — Dph [kN/m²]", fontsize=9, color=_C_BACK)
    plt.setp(ax_B.get_yticklabels(), visible=False)

    fig.text(0.5, 0.01,
             f"Front: F={f['F']:.1f} kN/m @ z={f['z_app']:.2f} m   |   "
             f"Back: F={b['F']:.1f} kN/m @ z={b['z_app']:.2f} m   |   "
             f"F_net={f['F']-b['F']:.1f} kN/m",
             ha="center", fontsize=9, color="dimgray")
    fig.subplots_adjust(bottom=0.08)
    return fig


def _draw_pressure_panel(
    ax, elevs, pressure, strips_side,
    color, side, F, z_app, slf, top, tip, invert,
):
    """Polyline + arrows + dots for one side's pressure profile."""
    ax.axvline(0, color="k", lw=0.8)
    ax.axhline(slf, color="saddlebrown", lw=1.0, ls="--", alpha=0.7)
    ax.text(0.02, 0.98, f"soil_level = {slf:.2f} m",
            transform=ax.transAxes, fontsize=6.5, va="top", color="saddlebrown")

    if pressure.max() > 1e-3:
        # Light fill
        ax.fill_betweenx(elevs, 0, pressure, alpha=0.12, color=color)
        # Polyline (envelope)
        ax.plot(pressure, elevs, "-", color=color, lw=1.8)
        # Dots at 1m evaluation points
        ax.plot(pressure, elevs, "o", color=color, ms=2.5, alpha=0.6)
        # Horizontal arrows every 2 m (from zero toward pressure value)
        e_top_p, e_bot_p = float(elevs[0]), float(elevs[-1])
        n_arr = max(2, round((e_top_p - e_bot_p) / 2.0) + 1)
        arr_e = np.linspace(e_top_p, e_bot_p, n_arr)
        arr_v = np.interp(arr_e, elevs[::-1], pressure[::-1])
        mask = arr_v > 0.5
        if mask.any():
            ax.quiver(
                arr_v[mask], arr_e[mask],
                -arr_v[mask], np.zeros(mask.sum()),
                scale_units="xy", scale=1.0, angles="xy",
                color=color, alpha=0.65,
                width=0.005, headwidth=4, headlength=5, zorder=3,
            )

    if F > 1e-6:
        ax.axhline(z_app, color=color, lw=0.9, ls="--", alpha=0.8)
        ax.text(0.98, z_app, f" F={F:.0f} kN/m\n z={z_app:.2f} m",
                transform=ax.get_yaxis_transform(), fontsize=7.5,
                color=color, ha="right" if invert else "left",
                va="center")

    for strip in strips_side:
        lbl = f"{strip.label}: q={strip.q:.0f}, a={strip.a:.1f}, w={strip.w:.0f}"
        ax.text(0.99 if invert else 0.01, 0.01, lbl,
                transform=ax.transAxes, fontsize=6.5,
                ha="right" if invert else "left", va="bottom",
                color=color, alpha=0.85)

    ax.set_xlim(left=0)
    if invert:
        ax.invert_xaxis()
    ax.tick_params(axis="x", labelsize=7)


def _draw_wall_panel(ax, geom, strips, elevs, front_p, back_p, f, b):
    """Pile rectangle + quiver arrows + polylines + resultant arrows."""
    top  = geom.top_elev
    tip  = geom.pile_tip_elev
    slf  = geom.soil_level_front
    slb  = geom.soil_level_back
    y_bot = tip - 0.5
    y_top = top + 1.8
    wall_hw = 0.12   # half-width of pile in panel coords

    p_max = max(front_p.max(), back_p.max(), 1.0)
    MAX_LEN = 1.6    # max arrow length in data coords from wall face

    # Ground fills
    ax.fill_betweenx([tip, slf], -2.5, -wall_hw, color="#d4c9a8", alpha=0.35, zorder=0)
    ax.fill_betweenx([tip, slb],  wall_hw,  2.5, color="#d4c9a8", alpha=0.35, zorder=0)

    # Ground lines
    ax.axhline(slf, color="saddlebrown", lw=1.2, ls="--", alpha=0.8, xmax=0.5)
    ax.axhline(slb, color="saddlebrown", lw=1.2, ls="--", alpha=0.8, xmin=0.5)
    ax.text(-2.4, slf + 0.12, f"Front {slf:.1f}m", fontsize=6.5, color="saddlebrown", va="bottom")
    ax.text( 0.18, slb + 0.12, f"Back {slb:.1f}m",  fontsize=6.5, color="saddlebrown", va="bottom")

    # Pile rectangle
    ax.fill_betweenx([tip, top], -wall_hw, wall_hw,
                     color=_C_WALL, alpha=0.55, zorder=3)

    # ── Surcharge strip blocks (on appropriate side, at ref_surface) ──────────
    for strip in strips:
        ref = strip.ref_surface
        sign = -1 if strip.side.lower() == "front" else +1
        clr  = _C_FRONT if strip.side.lower() == "front" else _C_BACK
        x0 = sign * (wall_hw + 0.05)
        x1 = sign * (wall_hw + 0.5)
        ax.fill_betweenx([ref - 0.45, ref],
                         min(x0, x1), max(x0, x1),
                         color=clr, alpha=0.45, hatch="///", zorder=2)
        ax.text(x0, ref + 0.08, f"q={strip.q:.0f}\na={strip.a:.0f},w={strip.w:.0f}",
                fontsize=6, color=clr, ha="right" if sign < 0 else "left", va="bottom")

    # ── Quiver arrows ─────────────────────────────────────────────────────────
    front_len = front_p / p_max * MAX_LEN
    back_len  = back_p  / p_max * MAX_LEN

    # Front: arrows point RIGHT (→) from tail toward wall
    mask_f = front_p > 1e-3
    if mask_f.any():
        tail_x_f = -(wall_hw + front_len[mask_f])
        ax.quiver(
            tail_x_f, elevs[mask_f],
            front_len[mask_f], np.zeros(mask_f.sum()),
            scale_units="xy", scale=1.0, angles="xy",
            color=_C_FRONT, alpha=0.75,
            width=0.006, headwidth=4, headlength=5,
            zorder=4,
        )

    # Back: arrows point LEFT (←) from tail toward wall
    mask_b = back_p > 1e-3
    if mask_b.any():
        tail_x_b = wall_hw + back_len[mask_b]
        ax.quiver(
            tail_x_b, elevs[mask_b],
            -back_len[mask_b], np.zeros(mask_b.sum()),
            scale_units="xy", scale=1.0, angles="xy",
            color=_C_BACK, alpha=0.75,
            width=0.006, headwidth=4, headlength=5,
            zorder=4,
        )

    # ── Polylines connecting arrow tails (pressure envelopes) ─────────────────
    if front_p.max() > 1e-3:
        px_f = -(wall_hw + front_len)
        ax.plot(px_f, elevs, "-", color=_C_FRONT, lw=2.0, zorder=5, label="Front")

    if back_p.max() > 1e-3:
        px_b = wall_hw + back_len
        ax.plot(px_b, elevs, "-", color=_C_BACK, lw=2.0, zorder=5, label="Back")

    # ── Resultant arrows (large, on wall face) ────────────────────────────────
    F_f, z_f = f["F"], f["z_app"]
    F_b, z_b = b["F"], b["z_app"]

    if F_f > 1e-6:
        ax.annotate("", xy=(-wall_hw, z_f), xytext=(-wall_hw - 0.6, z_f),
                    arrowprops=dict(arrowstyle="-|>", color=_C_FRONT,
                                    lw=2.5, mutation_scale=18), zorder=6)
        ax.text(-wall_hw - 0.65, z_f, f"F={F_f:.0f}\nkN/m",
                fontsize=7, color=_C_FRONT, ha="right", va="center")

    if F_b > 1e-6:
        ax.annotate("", xy=(wall_hw, z_b), xytext=(wall_hw + 0.6, z_b),
                    arrowprops=dict(arrowstyle="-|>", color=_C_BACK,
                                    lw=2.5, mutation_scale=18), zorder=6)
        ax.text(wall_hw + 0.65, z_b, f"F={F_b:.0f}\nkN/m",
                fontsize=7, color=_C_BACK, ha="left", va="center")

    # Elevation labels
    for elev, lbl in [(top, f"Top {top:.2f}m"), (tip, f"Tip {tip:.2f}m")]:
        ax.plot([-wall_hw, wall_hw], [elev, elev], "k-", lw=1.5)
        ax.text(wall_hw + 0.05, elev, lbl, fontsize=6.5, va="center", color="#444")

    ax.set_xlim(-2.5, 2.5)
    ax.set_xticks([])


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    geom = BoussiGeometry(top_elev=2.7, pile_length=20.0,
                          soil_level_front=0.0, soil_level_back=0.0)

    strips = [
        SurchargeStrip(q=18.0 * 2.7, a=0.0, w=50.0, ref_surface=0.0,
                       side="Front", label="Fill Front", color="tomato"),
        SurchargeStrip(q=30.0, a=1.0, w=5.0, ref_surface=0.0,
                       side="Back", label="Load Back", color="steelblue"),
    ]

    res = compute_all(geom, strips, spacing=1.0)

    print("=" * 60)
    print("Boussinesq — TCVN 11823-3 §10.6.2 Eq.(39)")
    print("=" * 60)
    print(f"  n_pts = {len(res['elevs'])}  (1 pt/m)")
    print(f"  F_front = {res['F_front']:.2f} kN/m  @ z={res['z_front']:.3f} m")
    print(f"  F_back  = {res['F_back']:.2f} kN/m  @ z={res['z_back']:.3f} m")
    print(f"  F_net   = {res['F_net']:.2f} kN/m")

    res["fig"].savefig("boussinesq_surcharge_demo.png", dpi=150, bbox_inches="tight")
    print("  Saved: boussinesq_surcharge_demo.png")
    plt.show()
