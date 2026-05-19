"""
sheet_pile_tab.py — Tab: Kè cọc bản consolle / có neo
Phương pháp: USACE EM 1110-2-2504 (sheet_pile — geotech-staff-engineer 4.6.0)
  - analyze_cantilever: tính chiều sâu ngàm consolle
  - analyze_anchored:   tính chiều sâu ngàm + lực neo
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st

try:
    from sheet_pile import analyze_cantilever, analyze_anchored, WallSoilLayer
    _HAS_SP = True
except ImportError:
    _HAS_SP = False

_LAYER_COLORS = ["#fff3cd", "#d1e7dd", "#cfe2ff", "#f8d7da", "#e2d9f3"]


# ── Helpers: đọc dữ liệu từ session_state ────────────────────────────────────

def _sp_geo_from_session() -> dict:
    """Đọc thông số hình học từ Geo Data tab."""
    return {
        "top_elev":         float(st.session_state.get("top_elev",         2.7)),
        "soil_level_front": float(st.session_state.get("soil_level_front", 0.0)),
        "soil_level_back":  float(st.session_state.get("soil_level_back",  0.0)),
        "pile_length":      float(st.session_state.get("L_m",             20.0)),
        "water_level":      float(st.session_state.get("water_level",     -1.0)),
        "water_level_back": float(st.session_state.get("water_level_back",-1.0)),
    }


def _sp_get_display_layers() -> list[dict]:
    """Lớp đất để hiển thị mặt cắt — từ front_sand_df + front_clay_df."""
    sand_df = st.session_state.get("front_sand_df")
    clay_df = st.session_state.get("front_clay_df")
    if sand_df is None and clay_df is None:
        return []
    pieces = []
    if sand_df is not None and not sand_df.empty:
        s = sand_df.copy(); s["_type"] = "Sand"; pieces.append(s)
    if clay_df is not None and not clay_df.empty:
        c = clay_df.copy(); c["_type"] = "Clay"; pieces.append(c)
    if not pieces:
        return []
    merged = pd.concat(pieces, ignore_index=True)
    merged = merged.sort_values("Layer Tip [m]", ascending=False).reset_index(drop=True)
    top_elev = float(st.session_state.get("top_elev", 2.7))
    prev_top = top_elev
    layers = []
    for _, row in merged.iterrows():
        tip   = float(row.get("Layer Tip [m]",        prev_top - 1.0))
        stype = str(row.get("_type", "Sand"))
        layers.append({
            "top":  prev_top,
            "bot":  tip,
            "type": stype,
            "phi":  float(row.get("Phi [Deg]",   0.0)),
            "su":   float(row.get("Su [kN/m2]",  0.0)),
        })
        prev_top = tip
    return layers


def _sp_layers_from_soil() -> pd.DataFrame:
    """Chuyển front_sand_df + front_clay_df → Sheet Pile layer format."""
    sand_df = st.session_state.get("front_sand_df")
    clay_df = st.session_state.get("front_clay_df")
    pieces = []
    if sand_df is not None and not sand_df.empty:
        s = sand_df.copy(); s["_type"] = "Sand"; pieces.append(s)
    if clay_df is not None and not clay_df.empty:
        c = clay_df.copy(); c["_type"] = "Clay"; pieces.append(c)
    if not pieces:
        return _DEFAULT_SP_LAYERS.copy()

    merged = pd.concat(pieces, ignore_index=True)
    merged = merged.sort_values("Layer Tip [m]", ascending=False).reset_index(drop=True)
    top_elev = float(st.session_state.get("top_elev", 2.7))
    prev_top = top_elev
    rows = []
    for i, row in merged.iterrows():
        tip      = float(row.get("Layer Tip [m]",        prev_top - 1.0))
        gamma    = float(row.get("Density Moist [kN/m3]", 18.0))
        phi      = float(row.get("Phi [Deg]",              0.0))
        cohesion = float(row.get("Cohesion [kN/m2]",       0.0))
        su       = float(row.get("Su [kN/m2]",             0.0))
        stype    = str(row.get("_type", "Sand"))
        phi_eff  = 0.0 if stype == "Clay" else phi
        c_eff    = su  if stype == "Clay" else cohesion
        rows.append({
            "Thickness [m]":       max(0.1, round(prev_top - tip, 3)),
            "Unit Weight [kN/m³]": gamma,
            "Phi [°]":             phi_eff,
            "Cohesion [kN/m²]":    c_eff,
            "Description":         f"Layer {i+1} ({stype})",
        })
        prev_top = tip
    return pd.DataFrame(rows)


_DEFAULT_SP_LAYERS = pd.DataFrame({
    "Thickness [m]":        [6.0, 10.0],
    "Unit Weight [kN/m³]":  [18.0, 17.5],
    "Phi [°]":              [30.0, 5.0],
    "Cohesion [kN/m²]":     [0.0, 20.0],
    "Description":          ["Sand", "Soft clay"],
})


# ── Hình vẽ mặt cắt GEO5-style (preview & kết quả) ──────────────────────────

def _draw_sp_preview(
    geo: dict,
    exc_depth: float,
    gwt_active_depth: float,
    gwt_passive_depth: float,
    disp_layers: list[dict],
    result=None,
) -> plt.Figure:
    """Vẽ mặt cắt kè GEO5-style.

    result=None  → preview: hiển thị hình học + địa tầng
    result=<obj> → kết quả: thêm đường chiều sâu ngàm + Mmax
    """
    te       = geo["top_elev"]
    sf       = geo["soil_level_front"]
    sb       = geo["soil_level_back"]
    L        = geo["pile_length"]
    pile_tip = te - L
    sf_top   = max(sf, te)

    # GWT tuyệt đối
    # Active side = Back (Right, x>0): depth from soil_level_back
    # Passive side = Front (Left, x<0): depth from soil_level_front
    wl_back  = sb - gwt_active_depth
    wl_front = sf - gwt_passive_depth

    reach = max(L * 0.35, 7.0)

    if disp_layers:
        y_min = min(ly["bot"] for ly in disp_layers) - 0.5
    else:
        y_min = pile_tip - 1.0
    y_max = te + max(L * 0.06, 1.5)
    span  = y_max - y_min

    fig, ax = plt.subplots(figsize=(6, 9), dpi=90)
    ax.set_facecolor("#f9f9f9")

    _LC = {"Sand": "#f5e6c8", "Clay": "#c8d4e8"}
    _LH = {"Sand": "..", "Clay": "//"}

    # ── Lớp đất ──
    if disp_layers:
        for i, ly in enumerate(disp_layers):
            clr   = _LC.get(ly["type"], "#d4c9a8")
            hatch = _LH.get(ly["type"], "")
            # Back (right): tất cả các lớp
            ax.fill_between(
                [0, reach], [ly["bot"]]*2, [ly["top"]]*2,
                color=clr, alpha=0.55, hatch=hatch, lw=0.3, edgecolor="#888", zorder=1,
            )
            # Front (left): chỉ các lớp dưới mặt đào sf
            if ly["bot"] < sf:
                vis_top = min(ly["top"], sf)
                ax.fill_between(
                    [-reach, 0], [ly["bot"]]*2, [vis_top]*2,
                    color=clr, alpha=0.55, hatch=hatch, lw=0.3, edgecolor="#888", zorder=1,
                )
            # Nhãn lớp bên phải
            mid_y = (ly["top"] + ly["bot"]) / 2
            lbl   = (f"Su = {ly['su']:.0f} kPa"
                     if ly["type"] == "Clay"
                     else f"φ = {ly['phi']:.0f}°")
            ax.text(reach * 0.55, mid_y, f"{ly['type']} {i+1}  {lbl}",
                    fontsize=8, ha="center", va="center",
                    color="#444", zorder=4, alpha=0.85)
    else:
        ax.fill_between([-reach, 0], [y_min]*2, [sf]*2,  color="#d4c9a8", alpha=0.45, zorder=1)
        ax.fill_between([0, reach],  [y_min]*2, [te]*2,   color="#d4c9a8", alpha=0.45, zorder=1)

    # ── Fill zone (Back, từ sb → te) ──
    if te > sb + 0.05:
        ax.fill_between(
            [0, reach], [sb]*2, [te]*2,
            color="#c8a96e", alpha=0.50, hatch="\\\\",
            lw=0.4, edgecolor="#a07040", zorder=2,
        )
        ax.text(reach * 0.5, (sb + te) / 2, "Fill",
                fontsize=8.5, color="#7a5020", ha="center", va="center",
                style="italic", zorder=5)

    # ── Mực nước ngầm (3 vạch GEO5) ──
    for (x0, x1, wl, lbl) in [
        (-reach, -0.3, wl_front, f"GWT {wl_front:.1f} m"),
        ( 0.3,  reach, wl_back,  f"GWT {wl_back:.1f} m"),
    ]:
        for dy, lw_w in [(-0.12, 0.7), (0.0, 1.5), (0.12, 0.7)]:
            ax.plot([x0, x1], [wl + dy]*2, color="#1a7fc4", lw=lw_w, zorder=6,
                    alpha=0.9 if dy == 0.0 else 0.5)
        ax.text(x1 + 0.2, wl, lbl, fontsize=7.5, color="#1a7fc4", va="center", zorder=7)

    # ── Đường mặt đất ──
    ax.plot([-reach, 0], [sf]*2,     color="saddlebrown", lw=2.2, zorder=8)  # Front
    ax.plot([0, reach],  [sf_top]*2, color="saddlebrown", lw=2.2, zorder=8)  # Back
    if te > sb + 0.05:
        ax.plot([0, reach], [sb]*2, color="saddlebrown", lw=1.0, ls=":", zorder=7, alpha=0.55)

    # ── Cừ ──
    ax.plot([0, 0], [pile_tip, te], color="red", lw=6,
            solid_capstyle="butt", zorder=10, label="Sheet pile")
    ax.plot(0, pile_tip, "v", color="red", ms=10, zorder=11, markeredgewidth=2)
    ax.text(0.25, pile_tip - span * 0.018,
            f"Pile tip  {pile_tip:.2f} m",
            fontsize=8.5, color="red", va="top", zorder=12, fontweight="bold")

    # ── Chiều sâu đào H (mũi tên hai chiều) ──
    if te > sf + 0.05:
        ax.annotate("", xy=(-reach * 0.55, sf), xytext=(-reach * 0.55, te),
                    arrowprops=dict(arrowstyle="<->", color="navy", lw=1.5), zorder=8)
        ax.text(-reach * 0.50, (sf + te) / 2, f"H = {exc_depth:.1f} m",
                fontsize=9, color="navy", va="center", ha="left",
                fontweight="bold", zorder=12)

    # ── Kết quả: chiều sâu ngàm + Mmax ──
    if result is not None:
        embed      = result.embedment_depth
        embed_elev = sf - embed
        ax.axhline(embed_elev, color="#2ca02c", lw=1.8, ls="--", zorder=9,
                   label=f"Embed d = {embed:.2f} m")
        ax.text(-reach * 0.85, embed_elev + span * 0.012,
                f"d = {embed:.2f} m", fontsize=9, color="#2ca02c",
                fontweight="bold", zorder=12)
        # Mũi tên chiều sâu ngàm
        ax.annotate("", xy=(-reach * 0.55, embed_elev), xytext=(-reach * 0.55, sf),
                    arrowprops=dict(arrowstyle="<->", color="#2ca02c", lw=1.5), zorder=8)
        ax.text(-reach * 0.50, (sf + embed_elev) / 2, f"d = {embed:.2f} m",
                fontsize=8.5, color="#2ca02c", va="center", ha="left", zorder=12)
        # Mmax annotation
        Mmax = result.max_moment
        ax.text(-reach * 0.85, sf - embed * 0.45,
                f"Mmax\n= {Mmax:.0f} kNm/m",
                fontsize=8.5, color="darkorange",
                fontweight="bold", va="center", zorder=12,
                bbox=dict(boxstyle="round,pad=0.2", fc="#fff8e1", alpha=0.8))

    # ── Nhãn ──
    ax.text(-reach * 0.75, y_min + span * 0.03, "Front (Active)",
            fontsize=9, color="#666", style="italic")
    ax.text( reach * 0.20, y_min + span * 0.03, "Back (Retained)",
            fontsize=9, color="#666", style="italic")

    ax.axvline(0, color="#aaa", lw=0.7, ls=":", zorder=2)
    ax.set_xlim(-reach, reach)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel("x (m)  —  wall at x = 0", fontsize=10)
    ax.set_ylabel("Elevation (m)", fontsize=10)

    if result is None:
        title = f"Mặt cắt kè (preview)  |  H = {exc_depth:.1f} m  |  L = {L:.1f} m"
    else:
        title = (
            f"Mặt cắt kè  |  H = {exc_depth:.1f} m  |  "
            f"d = {result.embedment_depth:.2f} m  |  "
            f"Mmax = {result.max_moment:.0f} kNm/m"
        )
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.legend(fontsize=8.5, loc="upper right")
    ax.grid(True, alpha=0.18)
    plt.tight_layout()
    return fig


# ── Biểu đồ 4 panel (cao độ tuyệt đối) ─────────────────────────────────────

def _draw_wall_diagram_manual(
    result,
    excavation_depth: float | None,  # unused — result.excavation_depth is authoritative
    gwt_active: float | None,
    gwt_passive: float | None,
    surcharge: float,
    wall_type: str,
    sp_layers: list | None = None,
    fos_p: float = 1.5,
    method: str = "rankine",
    sp_geo: dict | None = None,
    EI_kNm2: float = 30_000.0,
) -> plt.Figure:
    """4 panel — y-axis = cao độ tuyệt đối (m):
    [Mặt cắt GEO5] [Áp lực đất & nước] [Moment] [Chuyển vị]
    """
    embed = result.embedment_depth
    total = result.total_wall_length
    H     = result.excavation_depth
    Mmax  = result.max_moment

    # ── Geometry ──────────────────────────────────────────────────────────────
    if sp_geo is None:
        sp_geo = {
            "top_elev": 2.7, "soil_level_front": 0.0, "soil_level_back": 0.0,
            "pile_length": total, "water_level": -1.0, "water_level_back": -1.0,
        }
    te       = float(sp_geo["top_elev"])
    sf       = float(sp_geo["soil_level_front"])
    sb       = float(sp_geo["soil_level_back"])
    pile_tip = te - total
    sf_top   = max(sf, te)

    # y-axis limits
    disp_layers = _sp_get_display_layers()
    y_bot = (min(ly["bot"] for ly in disp_layers) - 0.5) if disp_layers else (pile_tip - 1.0)
    y_top = sf_top + 1.8
    span  = y_top - y_bot

    # ── Tính áp lực (z = chiều sâu từ đỉnh cừ) ───────────────────────────────
    n      = 300
    z_arr  = np.linspace(0, total, n)
    elev   = te - z_arr          # cao độ tuyệt đối tương ứng
    dz     = z_arr[1] - z_arr[0]
    gw     = 9.81

    p_act = np.zeros(n)
    p_pas = np.zeros(n)

    if sp_layers:
        try:
            from sheet_pile.cantilever import (
                _cumulative_stress, _cumulative_stress_passive, _get_soil_at_depth,
                rankine_Ka, rankine_Kp, coulomb_Ka, coulomb_Kp,
                active_pressure, passive_pressure,
            )
            # layer boundaries for accurate discontinuities
            bnds, cz = [], 0.0
            for l in sp_layers[:-1]:
                cz += l.thickness
                if cz < total:
                    bnds.append(cz)
            if bnds:
                z_extra = np.sort(np.unique(np.concatenate(
                    [z_arr, bnds,
                     [b - 1e-5 for b in bnds],
                     [b + 1e-5 for b in bnds]]
                )))
                z_extra = z_extra[(z_extra >= 0) & (z_extra <= total)]
                # recompute on finer grid then interpolate
                pa_x = np.zeros_like(z_extra)
                pp_x = np.zeros_like(z_extra)
                for i, z in enumerate(z_extra):
                    lyr   = _get_soil_at_depth(z, sp_layers)
                    sig_v = surcharge + _cumulative_stress(z, sp_layers, gwt_active, gw)
                    Ka = rankine_Ka(lyr.friction_angle) if method == "rankine" else coulomb_Ka(lyr.friction_angle, 0, 0, 0)
                    Kp = rankine_Kp(lyr.friction_angle) if method == "rankine" else coulomb_Kp(lyr.friction_angle, 0, 0, 0)
                    u_a = gw * max(0.0, z - gwt_active) if gwt_active is not None else 0.0
                    pa_x[i] = active_pressure(1.0, sig_v, Ka, lyr.cohesion, 0.0) + u_a
                    if z >= H:
                        z_s    = z - H
                        sig_vp = _cumulative_stress_passive(z_s, H, sp_layers, gwt_passive, gw)
                        u_p    = gw * max(0.0, z - gwt_passive) if gwt_passive is not None else 0.0
                        pp_x[i] = passive_pressure(1.0, sig_vp, Kp / fos_p, lyr.cohesion) + u_p
                p_act = np.interp(z_arr, z_extra, pa_x)
                p_pas = np.interp(z_arr, z_extra, pp_x)
            else:
                for i, z in enumerate(z_arr):
                    lyr   = _get_soil_at_depth(z, sp_layers)
                    sig_v = surcharge + _cumulative_stress(z, sp_layers, gwt_active, gw)
                    Ka = rankine_Ka(lyr.friction_angle) if method == "rankine" else coulomb_Ka(lyr.friction_angle, 0, 0, 0)
                    Kp = rankine_Kp(lyr.friction_angle) if method == "rankine" else coulomb_Kp(lyr.friction_angle, 0, 0, 0)
                    u_a = gw * max(0.0, z - gwt_active) if gwt_active is not None else 0.0
                    p_act[i] = active_pressure(1.0, sig_v, Ka, lyr.cohesion, 0.0) + u_a
                    if z >= H:
                        z_s    = z - H
                        sig_vp = _cumulative_stress_passive(z_s, H, sp_layers, gwt_passive, gw)
                        u_p    = gw * max(0.0, z - gwt_passive) if gwt_passive is not None else 0.0
                        p_pas[i] = passive_pressure(1.0, sig_vp, Kp / fos_p, lyr.cohesion) + u_p
        except Exception:
            p_act = 0.333 * 18.0 * z_arr + surcharge * 0.333
            p_pas = (3.0 * 18.0 * np.maximum(0.0, z_arr - H)) / fos_p
    else:
        p_act = 0.333 * 18.0 * z_arr + surcharge * 0.333
        p_pas = (3.0 * 18.0 * np.maximum(0.0, z_arr - H)) / fos_p

    # ── Shear, Moment (tích phân số từ đỉnh, BC V=0 M=0 tại z=0) ─────────────
    p_net = p_act - p_pas
    V_arr = np.cumsum(p_net) * dz
    M_arr = np.cumsum(V_arr) * dz

    # ── Chuyển vị (double-integrate M, BC y=0 y'=0 tại z=L — chân cừ) ────────
    # theta(z) = -∫_z^L M(t)/EI dt
    cum_M   = np.cumsum(M_arr[::-1])[::-1] * dz
    theta   = -cum_M / EI_kNm2
    # y(z) = ∫_z^L theta(t) dt
    y_defl  = np.cumsum(theta[::-1])[::-1] * dz   # m
    y_mm    = y_defl * 1000.0                       # mm

    # ── Figure ────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(
        1, 4, figsize=(17, 9), sharey=True,
        gridspec_kw={"width_ratios": [1.6, 1, 1, 1]},
    )
    fig.suptitle(
        f"Kè cọc bản — {wall_type.upper()}  |  "
        f"H = {H:.1f} m  |  d = {embed:.2f} m  |  "
        f"Mmax = {Mmax:.0f} kNm/m  |  δmax = {abs(y_mm[0]):.1f} mm  "
        f"[EI = {EI_kNm2/1000:.0f}×10³ kNm²/m]",
        fontsize=10, fontweight="bold",
    )

    _LC = {"Sand": "#f5e6c8", "Clay": "#c8d4e8"}
    _LH = {"Sand": "..", "Clay": "//"}
    reach_p = 2.8

    # ─────────────────────────────────────────────────────────────────────────
    # Panel 1: Mặt cắt GEO5-style (cao độ tuyệt đối)
    # ─────────────────────────────────────────────────────────────────────────
    ax0 = axes[0]

    if disp_layers:
        for i, ly in enumerate(disp_layers):
            clr   = _LC.get(ly["type"], "#d4c9a8")
            hatch = _LH.get(ly["type"], "")
            # Back (right)
            ax0.fill_between(
                [0, reach_p], [ly["bot"]]*2, [ly["top"]]*2,
                color=clr, alpha=0.55, hatch=hatch, lw=0.3, edgecolor="#888", zorder=1,
            )
            # Front (left): below sf only
            if ly["bot"] < sf:
                vis_top = min(ly["top"], sf)
                ax0.fill_between(
                    [-reach_p, 0], [ly["bot"]]*2, [vis_top]*2,
                    color=clr, alpha=0.55, hatch=hatch, lw=0.3, edgecolor="#888", zorder=1,
                )
            # Layer label (right side)
            mid_y = (ly["top"] + ly["bot"]) / 2
            lbl   = (f"Su={ly['su']:.0f} kPa"
                     if ly["type"] == "Clay" else f"φ={ly['phi']:.0f}°")
            ax0.text(reach_p * 0.55, mid_y, f"{ly['type']} {i+1}  {lbl}",
                     fontsize=7.5, ha="center", va="center", color="#444", zorder=4)
    else:
        ax0.fill_between([-reach_p, 0], [y_bot]*2, [sf]*2,    color="#d4c9a8", alpha=0.45, zorder=1)
        ax0.fill_between([0, reach_p],  [y_bot]*2, [sf_top]*2, color="#d4c9a8", alpha=0.45, zorder=1)

    # Fill zone
    if te > sb + 0.05:
        ax0.fill_between(
            [0, reach_p], [sb]*2, [te]*2,
            color="#c8a96e", alpha=0.50, hatch="\\\\", lw=0.4, edgecolor="#a07040", zorder=2,
        )
        ax0.text(reach_p * 0.5, (sb + te) / 2, "Fill",
                 fontsize=8, color="#7a5020", ha="center", va="center", style="italic", zorder=5)

    # GWT (3 vạch GEO5)
    wl_back  = float(sp_geo.get("water_level_back", sf))
    wl_front = float(sp_geo.get("water_level", sf))
    for (x0, x1, wl) in [(-reach_p, -0.2, wl_front), (0.2, reach_p, wl_back)]:
        for dy, lw_w in [(-0.10, 0.7), (0.0, 1.5), (0.10, 0.7)]:
            ax0.plot([x0, x1], [wl + dy]*2, color="#1a7fc4", lw=lw_w, zorder=6,
                     alpha=0.9 if dy == 0 else 0.5)

    # Ground lines
    ax0.plot([-reach_p, 0], [sf]*2,     color="saddlebrown", lw=2.0, zorder=8)
    ax0.plot([0, reach_p],  [sf_top]*2, color="saddlebrown", lw=2.0, zorder=8)
    if te > sb + 0.05:
        ax0.plot([0, reach_p], [sb]*2, color="saddlebrown", lw=1.0, ls=":", zorder=7, alpha=0.55)

    # Surcharge arrows
    if surcharge > 0:
        for xq in np.linspace(-reach_p * 0.7, -0.3, 5):
            ax0.annotate("", xy=(xq, sf_top), xytext=(xq, sf_top + 0.8),
                         arrowprops=dict(arrowstyle="->", color="brown", lw=1.2))
        ax0.text(-reach_p * 0.4, sf_top + 0.95, f"q = {surcharge:.0f} kPa",
                 fontsize=8, color="brown", fontweight="bold", ha="center")

    # Wall
    ax0.fill_between([-0.15, 0.15], [pile_tip]*2, [te]*2,
                     color="steelblue", alpha=0.80, zorder=10)
    ax0.plot([0, 0], [pile_tip, te], color="red", lw=2.5,
             solid_capstyle="butt", zorder=11)
    ax0.plot(0, pile_tip, "v", color="red", ms=9, zorder=12)
    ax0.text(0.22, pile_tip - span * 0.015,
             f"Tip {pile_tip:.2f} m", fontsize=8, color="red",
             va="top", fontweight="bold", zorder=13)

    # H arrow (chiều sâu đào)
    xarr = -reach_p * 0.70
    if te > sf + 0.05:
        ax0.annotate("", xy=(xarr, sf), xytext=(xarr, te),
                     arrowprops=dict(arrowstyle="<->", color="navy", lw=1.5), zorder=8)
        ax0.text(xarr + 0.12, (sf + te) / 2, f"H={H:.1f}m",
                 fontsize=8.5, color="navy", va="center", fontweight="bold")

    # d arrow (chiều sâu ngàm)
    embed_elev = sf - embed
    ax0.axhline(embed_elev, color="#2ca02c", lw=1.3, ls="--", zorder=9)
    ax0.annotate("", xy=(xarr, embed_elev), xytext=(xarr, sf),
                 arrowprops=dict(arrowstyle="<->", color="#2ca02c", lw=1.5), zorder=8)
    ax0.text(xarr + 0.12, (sf + embed_elev) / 2, f"d={embed:.2f}m",
             fontsize=8.5, color="#2ca02c", va="center", fontweight="bold")

    ax0.axhline(sf,        color="sienna",  lw=1.2, ls="--", zorder=9, alpha=0.8)
    ax0.axhline(pile_tip,  color="dimgray", lw=0.8, zorder=7, alpha=0.5)
    ax0.axvline(0, color="#aaa", lw=0.7, ls=":", zorder=2)
    ax0.set_xlim(-reach_p, reach_p)
    ax0.set_xticks([])
    ax0.set_ylabel("Cao độ (m)", fontsize=10)
    ax0.set_title("Mặt cắt & Địa tầng", fontsize=10, fontweight="bold")
    ax0.grid(True, alpha=0.18, axis="y")
    ax0.text(-reach_p * 0.6, y_bot + span * 0.03, "Front", fontsize=8, color="#777", style="italic")
    ax0.text( reach_p * 0.2, y_bot + span * 0.03, "Back",  fontsize=8, color="#777", style="italic")

    # ─────────────────────────────────────────────────────────────────────────
    # Panel 2: Áp lực đất & nước (kPa) vs cao độ
    # ─────────────────────────────────────────────────────────────────────────
    ax1 = axes[1]
    ax1.fill_betweenx(elev, 0,     p_act, color="tomato",   alpha=0.45, label="Active (+u)")
    ax1.fill_betweenx(elev, 0,    -p_pas, color="seagreen", alpha=0.45, label="Passive/FOS (+u)")
    ax1.plot( p_act, elev, color="darkred",   lw=1.5)
    ax1.plot(-p_pas, elev, color="darkgreen", lw=1.5)
    ax1.axhline(sf,       color="sienna", lw=1.0, ls="--", alpha=0.7)
    ax1.axhline(pile_tip, color="dimgray", lw=0.7, alpha=0.5)
    ax1.axvline(0, color="k", lw=0.8)
    ax1.set_xlabel("Áp lực (kPa)", fontsize=9)
    ax1.set_title("Áp lực đất & nước", fontsize=10, fontweight="bold")
    ax1.legend(fontsize=8, loc="lower left")
    ax1.grid(True, alpha=0.22)

    # ─────────────────────────────────────────────────────────────────────────
    # Panel 3: Moment uốn (kNm/m) vs cao độ
    # ─────────────────────────────────────────────────────────────────────────
    ax2 = axes[2]
    ax2.fill_betweenx(elev, 0, M_arr, alpha=0.42, color="orange")
    ax2.plot(M_arr, elev, "darkorange", lw=2)
    # Mmax marker
    Mmax_elev = te - result.max_moment_depth
    ax2.axhline(Mmax_elev, color="red", lw=0.9, ls=":", alpha=0.7)
    ax2.annotate(
        f"Mmax\n{Mmax:.0f} kNm/m",
        xy=(max(M_arr), Mmax_elev),
        xytext=(max(M_arr) * 0.35, Mmax_elev - span * 0.08),
        fontsize=8, color="darkred", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="darkred", lw=1),
    )
    ax2.axhline(sf,       color="sienna",  lw=1.0, ls="--", alpha=0.7)
    ax2.axhline(pile_tip, color="dimgray", lw=0.7, alpha=0.5)
    ax2.axvline(0, color="k", lw=0.8)
    ax2.set_xlabel("Moment (kNm/m)", fontsize=9)
    ax2.set_title("Moment uốn", fontsize=10, fontweight="bold")
    ax2.grid(True, alpha=0.22)

    # ─────────────────────────────────────────────────────────────────────────
    # Panel 4: Chuyển vị ngang (mm) vs cao độ
    # ─────────────────────────────────────────────────────────────────────────
    ax3 = axes[3]
    ax3.fill_betweenx(elev, 0, y_mm, alpha=0.40, color="steelblue")
    ax3.plot(y_mm, elev, color="steelblue", lw=2)
    # δmax ở đỉnh cừ
    d_max = float(y_mm[0])
    ax3.plot(d_max, te, "o", color="purple", ms=7, zorder=6,
             label=f"δmax = {abs(d_max):.1f} mm")
    ax3.annotate(
        f"δmax\n{abs(d_max):.1f} mm",
        xy=(d_max, te),
        xytext=(d_max * 0.5, te + span * 0.04),
        fontsize=8, color="purple", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="purple", lw=1),
    )
    ax3.axhline(sf,       color="sienna",  lw=1.0, ls="--", alpha=0.7)
    ax3.axhline(pile_tip, color="dimgray", lw=0.7, alpha=0.5)
    ax3.axvline(0, color="k", lw=0.8)
    ax3.set_xlabel(f"Chuyển vị (mm)\nEI={EI_kNm2/1000:.0f}×10³ kNm²/m", fontsize=9)
    ax3.set_title("Chuyển vị ngang", fontsize=10, fontweight="bold")
    ax3.legend(fontsize=8, loc="lower left")
    ax3.grid(True, alpha=0.22)

    for ax in axes:
        ax.set_ylim(y_bot, y_top)

    fig.tight_layout()
    return fig


# ── Render ────────────────────────────────────────────────────────────────────

def render_sheet_pile_tab() -> None:
    """Streamlit tab body — Sheet Pile Design."""
    if not _HAS_SP:
        st.error("Thư viện `sheet_pile` chưa được cài đặt.\n\n"
                 "```\npip install geotech-staff-engineer\n```")
        return

    st.markdown("### Kè cọc bản — USACE EM 1110-2-2504 (sheet_pile)")
    st.caption("Consolle · Có neo | Rankine / Coulomb pressure · FOS passive reduction")

    # ── Geometry từ Geo Data ──────────────────────────────────────────────────
    sp_geo = _sp_geo_from_session()
    exc_default  = max(0.5, round(sp_geo["top_elev"] - sp_geo["soil_level_front"], 2))
    gwta_default = max(0.0, round(sp_geo["soil_level_back"]  - sp_geo["water_level_back"], 2))
    gwtp_default = max(0.0, round(sp_geo["soil_level_front"] - sp_geo["water_level"],      2))

    st.markdown("#### Geometry (from Geo Data)")
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Exc. Depth H",        f"{exc_default:.2f} m",
              help="top_elev − soil_level_front")
    g2.metric("Pile Length",          f"{sp_geo['pile_length']:.1f} m")
    g3.metric("GWT Active (back)",    f"{sp_geo['water_level_back']:.2f} m",
              help="Mực nước phía giữ đất (absolute)")
    g4.metric("GWT Passive (front)",  f"{sp_geo['water_level']:.2f} m",
              help="Mực nước phía đào (absolute)")
    st.divider()

    _has_result = st.session_state.get("sp_result") is not None
    disp_layers = _sp_get_display_layers()

    col_l, col_r = st.columns([1, 1.5], gap="large")

    # ── Cột trái: thông số đầu vào ────────────────────────────────────────────
    with col_l:
        st.markdown("#### Loại kè")
        wall_type = st.radio(
            "Kiểu tường", ["cantilever", "anchored"],
            horizontal=True, key="sp_type",
            format_func=lambda x: "Consolle" if x == "cantilever" else "Có neo",
        )
        st.markdown("#### Thông số hình học")
        exc_depth   = st.number_input("Chiều sâu đào H (m)", min_value=0.5, max_value=20.0,
                                       value=exc_default, step=0.5, key="sp_exc")
        surcharge   = st.number_input("Tải phân bố q (kN/m²)", min_value=0.0,
                                       value=10.0, step=5.0, key="sp_surcharge")
        gwt_active  = st.number_input(
            "MNN phía Active — depth from back surface (m)",
            min_value=0.0, value=gwta_default, step=0.5, key="sp_gwta",
            help="Chiều sâu từ mặt đất phía giữ (soil_level_back) xuống mực nước",
        )
        gwt_passive = st.number_input(
            "MNN phía Passive — depth from front surface (m)",
            min_value=0.0, value=gwtp_default, step=0.5, key="sp_gwtp",
            help="Chiều sâu từ mặt đáy đào (soil_level_front) xuống mực nước",
        )
        fos_p      = st.number_input("FOS passive", min_value=1.0, max_value=3.0,
                                      value=1.5, step=0.1, key="sp_fos")
        method_sp  = st.selectbox("Phương pháp áp lực", ["rankine", "coulomb"],
                                   key="sp_method")
        anchor_depth = None
        if wall_type == "anchored":
            anchor_depth = st.number_input(
                "Vị trí neo (m từ đỉnh tường)",
                min_value=0.1, max_value=float(max(0.2, exc_depth - 0.1)),
                value=min(1.0, exc_depth * 0.3),
                step=0.1, key="sp_anchor_depth",
            )

    # ── Cột phải: hình động ───────────────────────────────────────────────────
    with col_r:
        if not _has_result:
            st.markdown(f"#### Mặt cắt kè  —  H = {exc_depth:.1f} m")
            fig_prev = _draw_sp_preview(
                sp_geo, exc_depth,
                float(gwt_active), float(gwt_passive),
                disp_layers,
            )
            st.pyplot(fig_prev, use_container_width=True)
            plt.close(fig_prev)
        else:
            prm = st.session_state.get("sp_params", {})
            st.markdown(f"#### Kết quả — {prm.get('wall_type', 'cantilever').upper()}")
            fig_cs = _draw_sp_preview(
                sp_geo,
                prm.get("exc_depth",         float(exc_depth)),
                prm.get("gwt_active_depth",   float(gwt_active)),
                prm.get("gwt_passive_depth",  float(gwt_passive)),
                disp_layers,
                result=st.session_state["sp_result"],
            )
            st.pyplot(fig_cs, use_container_width=True)
            plt.close(fig_cs)

    # ── Lớp đất (full width) ─────────────────────────────────────────────────
    st.markdown("#### Lớp đất (từ trên xuống)")
    sync_col, _ = st.columns([1, 3])
    if sync_col.button("↻ Sync from Soil Layers tab", key="sp_sync_btn"):
        st.session_state["sp_soil_df"] = _sp_layers_from_soil()
        st.success("Soil layers synced.")

    if "sp_soil_df" not in st.session_state:
        st.session_state["sp_soil_df"] = _sp_layers_from_soil()

    sp_soil_df = st.data_editor(
        st.session_state["sp_soil_df"],
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Thickness [m]":       st.column_config.NumberColumn(min_value=0.1, step=0.5, format="%.1f"),
            "Unit Weight [kN/m³]": st.column_config.NumberColumn(min_value=10.0, max_value=25.0, format="%.1f"),
            "Phi [°]":             st.column_config.NumberColumn(min_value=0.0, max_value=45.0, format="%.1f"),
            "Cohesion [kN/m²]":    st.column_config.NumberColumn(min_value=0.0, format="%.1f"),
        },
        key="sp_soil_editor",
    )
    st.session_state["sp_soil_df"] = sp_soil_df

    # ── Nút ──────────────────────────────────────────────────────────────────
    btn_col, rst_col, _ = st.columns([1, 1, 3])
    calc  = btn_col.button("Calculate — Sheet Pile", type="primary", key="sp_calc_btn")
    reset = rst_col.button("Reset results", key="sp_reset_btn")

    if reset:
        st.session_state.pop("sp_result", None)
        st.session_state.pop("sp_params", None)
        st.rerun()

    if calc:
        df = sp_soil_df.dropna(subset=["Thickness [m]", "Unit Weight [kN/m³]"])
        if df.empty:
            st.error("Nhập ít nhất 1 lớp đất.")
            st.stop()

        with st.spinner("Đang tính toán..."):
            try:
                sp_layers = [
                    WallSoilLayer(
                        thickness=float(row["Thickness [m]"]),
                        unit_weight=float(row["Unit Weight [kN/m³]"]),
                        friction_angle=float(row["Phi [°]"]),
                        cohesion=float(row["Cohesion [kN/m²]"]),
                        description=str(row["Description"]) if "Description" in row.index else f"Lớp {i+1}",
                    )
                    for i, row in df.iterrows()
                ]
                gwt_a = float(gwt_active)  if gwt_active  > 0 else None
                gwt_p = float(gwt_passive + exc_depth) if gwt_passive >= 0 else None

                if wall_type == "cantilever":
                    result = analyze_cantilever(
                        excavation_depth=float(exc_depth),
                        soil_layers=sp_layers,
                        gwt_depth_active=gwt_a,
                        gwt_depth_passive=gwt_p,
                        surcharge=float(surcharge),
                        FOS_passive=float(fos_p),
                        pressure_method=method_sp,
                    )
                else:
                    result = analyze_anchored(
                        excavation_depth=float(exc_depth),
                        anchor_depth=float(anchor_depth),
                        soil_layers=sp_layers,
                        gwt_depth_active=gwt_a,
                        gwt_depth_passive=gwt_p,
                        surcharge=float(surcharge),
                        FOS_passive=float(fos_p),
                        pressure_method=method_sp,
                    )

                st.session_state["sp_result"] = result
                st.session_state["sp_params"]  = {
                    "exc_depth":          float(exc_depth),
                    "wall_type":          wall_type,
                    "gwt_a":              gwt_a,
                    "gwt_p":              gwt_p,
                    "gwt_active_depth":   float(gwt_active),
                    "gwt_passive_depth":  float(gwt_passive),
                    "surcharge":          float(surcharge),
                    "fos_p":              float(fos_p),
                    "method":             method_sp,
                    "sp_layers":          sp_layers,
                }
                st.rerun()

            except Exception as exc_e:
                st.error(f"Lỗi: {exc_e}")
                st.stop()

    # ── Kết quả metrics (full width) ─────────────────────────────────────────
    if _has_result:
        result = st.session_state["sp_result"]
        prm    = st.session_state.get("sp_params", {})

        st.divider()
        st.markdown("#### Results")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Chiều sâu ngàm d",   f"{result.embedment_depth:.2f} m")
        k2.metric("Tổng chiều dài",      f"{result.total_wall_length:.2f} m")
        k3.metric("Mmax",                f"{result.max_moment:.1f} kNm/m")
        ok_fos = result.FOS_passive >= 1.5
        k4.metric("FOS passive", f"{result.FOS_passive:.2f}",
                  "Dat" if ok_fos else "Khong dat",
                  delta_color="normal" if ok_fos else "inverse")
        if hasattr(result, "anchor_force") and result.anchor_force is not None:
            st.metric("Lực neo T", f"{result.anchor_force:.1f} kN/m")

        # 3-panel pressure + moment diagram
        with st.expander("Biểu đồ áp lực & moment", expanded=True):
            fig_sp = _draw_wall_diagram_manual(
                result,
                prm.get("exc_depth",  float(exc_depth)),
                prm.get("gwt_a"),
                prm.get("gwt_p"),
                prm.get("surcharge",  float(surcharge)),
                prm.get("wall_type",  "cantilever"),
                sp_layers=prm.get("sp_layers"),
                fos_p=prm.get("fos_p",   float(fos_p)),
                method=prm.get("method", method_sp),
                sp_geo=sp_geo,
            )
            st.pyplot(fig_sp, use_container_width=True)
            plt.close(fig_sp)

    st.divider()
    with st.expander("Theory — 30-sheet-pile-cantilever", expanded=False):
        _proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(_proj_dir, "30-sheet-pile-cantilever.md"),
                      "r", encoding="utf-8") as f:
                st.markdown(f.read())
        except FileNotFoundError:
            st.info("30-sheet-pile-cantilever not found")
