"""
slope_stability_tab.py — Tab: Ổn định mái dốc
Phương pháp: Giới hạn cân bằng (slope_stability — geotech-staff-engineer 4.6.0)
  - Fellenius, Bishop Simplified, Spencer, Morgenstern-Price

NGUYÊN TẮC (bất biến):
  Mọi cung trượt đều đi qua chân cừ (pile tip).
  R_i = sqrt(xc_i² + (yc_i − pile_tip_z)²) cho mỗi điểm lưới (xc_i, yc_i).
  Surface reach được tính tự động đủ lớn để toàn bộ lưới tìm kiếm hợp lệ.
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
    from slope_stability import SlopeGeometry, SlopeSoilLayer, analyze_slope
    _HAS_SLOPE = True
except ImportError:
    _HAS_SLOPE = False

_DEFAULT_SLOPE_LAYERS = pd.DataFrame({
    "Name":            ["Fill", "Clay", "Dense sand"],
    "Top Elev [m]":    [5.0,    3.0,    -2.0],
    "Bottom Elev [m]": [3.0,   -2.0,   -15.0],
    "γ [kN/m³]":       [18.0,  17.5,    19.5],
    "φ [°]":           [25.0,   5.0,    32.0],
    "c' [kN/m²]":      [5.0,    0.0,     0.0],
    "Su [kN/m²]":      [0.0,   30.0,     0.0],
    "Mode":            ["drained", "undrained", "drained"],
})

_METHODS = {
    "bishop":            "Bishop Simplified",
    "fellenius":         "Fellenius (Ordinary)",
    "spencer":           "Spencer",
    "morgenstern_price": "Morgenstern-Price",
}

_FS_MIN = {"bishop": 1.3, "fellenius": 1.25, "spencer": 1.3, "morgenstern_price": 1.3}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _geo_from_session() -> dict:
    return {
        "top_elev":         float(st.session_state.get("top_elev",         2.7)),
        "soil_level_front": float(st.session_state.get("soil_level_front", 0.0)),
        "soil_level_back":  float(st.session_state.get("soil_level_back",  0.0)),
        "pile_length":      float(st.session_state.get("L_m",             20.0)),
        "slope_ratio":      float(st.session_state.get("fill_slope_hv",   2.0)),
    }


def _pile_tip_z(geo: dict) -> float:
    return geo["top_elev"] - geo["pile_length"]


def _required_reach(xc_min: float, xc_max: float,
                    yc_min: float, yc_max: float,
                    pile_tip_z: float,
                    sf: float, margin: float = 1.3) -> float:
    """Reach tối thiểu để tất cả circles trong lưới cắt được mặt đất phẳng ở y=sf."""
    # Giao điểm xa nhất: |xc| + sqrt(R² − (yc−sf)²)
    worst = 0.0
    for xc in [xc_min, xc_max]:
        for yc in [yc_min, yc_max]:
            R_i = np.sqrt(xc**2 + (yc - pile_tip_z)**2)
            h   = yc - sf
            if R_i > abs(h):
                half_chord = np.sqrt(R_i**2 - h**2)
                worst = max(worst, abs(xc) + half_chord)
    return max(worst * margin, 40.0)


def _build_surface(geo: dict, slope_ratio: float, reach: float) -> list[tuple[float, float]]:
    """Mặt đất dạng ramp (fill slope 1:slope_ratio) với reach đủ lớn."""
    te, sf, sb = geo["top_elev"], geo["soil_level_front"], geo["soil_level_back"]
    fill_h  = te - sf
    slope_x = -(fill_h * slope_ratio) if fill_h > 0.05 else 0.0
    if fill_h > 0.05:
        return [(-reach, sf), (slope_x, sf), (0.0, te), (reach, sb)]
    return [(-reach, sf), (0.0, te), (reach, sb)]


def _auto_search_grid(geo: dict, slope_ratio: float = 2.0) -> dict:
    te, sf, L = geo["top_elev"], geo["soil_level_front"], geo["pile_length"]
    fill_h  = te - sf
    x_base  = -(fill_h * slope_ratio) if fill_h > 0.1 else 0.0
    return {
        "xc_min": round(x_base * 1.5, 1),
        "xc_max": round(L * 0.5,      1),
        "yc_min": round(te,            1),
        "yc_max": round(te + L,        1),
    }


def _layers_from_front_soil() -> pd.DataFrame:
    sand_df = st.session_state.get("front_sand_df")
    clay_df = st.session_state.get("front_clay_df")
    if sand_df is None and clay_df is None:
        return _DEFAULT_SLOPE_LAYERS.copy()
    pieces = []
    if sand_df is not None and not sand_df.empty:
        s = sand_df.copy(); s["_type"] = "Sand"; pieces.append(s)
    if clay_df is not None and not clay_df.empty:
        c = clay_df.copy(); c["_type"] = "Clay"; pieces.append(c)
    if not pieces:
        return _DEFAULT_SLOPE_LAYERS.copy()
    merged   = pd.concat(pieces, ignore_index=True)
    merged   = merged.sort_values("Layer Tip [m]", ascending=False).reset_index(drop=True)
    top_elev = float(st.session_state.get("top_elev", 2.7))
    prev_top = top_elev
    rows = []
    for i, row in merged.iterrows():
        tip     = float(row.get("Layer Tip [m]",         prev_top - 1.0))
        gamma   = float(row.get("Density Moist [kN/m3]", 18.0))
        phi     = float(row.get("Phi [Deg]",              0.0))
        c_prime = float(row.get("Cohesion [kN/m2]",       0.0))
        su      = float(row.get("Su [kN/m2]",             0.0))
        stype   = str(row.get("_type", "Sand"))
        mode    = "drained" if stype == "Sand" else "undrained"
        rows.append({
            "Name":            f"Layer {i+1} ({stype})",
            "Top Elev [m]":    prev_top,
            "Bottom Elev [m]": tip,
            "γ [kN/m³]":       gamma,
            "φ [°]":           phi,
            "c' [kN/m²]":      c_prime,
            "Su [kN/m²]":      su,
            "Mode":            mode,
        })
        prev_top = tip
    return pd.DataFrame(rows)


def _get_display_layers() -> list[dict]:
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
    merged   = pd.concat(pieces, ignore_index=True)
    merged   = merged.sort_values("Layer Tip [m]", ascending=False).reset_index(drop=True)
    top_elev = float(st.session_state.get("top_elev", 2.7))
    prev_top = top_elev
    layers = []
    for _, row in merged.iterrows():
        tip   = float(row.get("Layer Tip [m]",    prev_top - 1.0))
        stype = str(row.get("_type", "Sand"))
        layers.append({
            "top":  prev_top, "bot": tip, "type": stype,
            "phi":  float(row.get("Phi [Deg]",  0.0)),
            "su":   float(row.get("Su [kN/m2]", 0.0)),
        })
        prev_top = tip
    return layers


# ── Vẽ mặt cắt ────────────────────────────────────────────────────────────────

def _draw_slope_with_circle(geo: dict, slope_ratio: float = 2.0,
                             xc_mid: float = 0.0, yc_mid: float | None = None,
                             result=None) -> plt.Figure:
    """Vẽ mặt cắt kè + cung trượt qua chân cừ.

    result=None  → preview: cung tham khảo qua chân cừ tại (xc_mid, yc_mid)
    result=<obj> → cung tính toán (critical) + FOS
    """
    te       = geo["top_elev"]
    sf       = geo["soil_level_front"]
    sb       = geo["soil_level_back"]
    L        = geo["pile_length"]
    pile_tip = te - L
    fill_h   = te - sf
    slope_x  = -(fill_h * slope_ratio) if fill_h > 0.05 else 0.0

    disp_layers = _get_display_layers()
    y_min = (min(ly["bot"] for ly in disp_layers) - 1.0) if disp_layers else (pile_tip - 2.0)

    if result is not None:
        xc      = float(result.xc)
        yc      = float(result.yc)
        R_draw  = float(result.radius)
        fos_val = float(result.FOS)
        arc_color = "red" if fos_val < 1.3 else ("orange" if fos_val < 1.5 else "green")
        arc_label = f"Critical arc  FOS = {fos_val:.3f}  R = {R_draw:.1f} m"
        y_max = max(te + 5.0, yc + 2.0)
    else:
        # Preview: cung tham khảo qua chân cừ
        xc     = float(xc_mid)
        yc     = float(yc_mid) if yc_mid is not None else pile_tip + L
        R_draw = float(np.sqrt(xc**2 + (yc - pile_tip)**2))
        fos_val   = None
        arc_color = "crimson"
        arc_label = f"Preview arc (R through pile tip)  R = {R_draw:.1f} m"
        y_max = max(te + 5.0, yc + 2.0)

    reach = max(abs(slope_x) * 2.0, L * 2.0, abs(xc) + R_draw * 0.6, 25.0)
    span  = y_max - y_min

    fig, ax = plt.subplots(figsize=(10, 6), dpi=90)
    ax.set_facecolor("#f9f9f9")

    _LC = {"Sand": "#f5e6c8", "Clay": "#c8d4e8"}
    _LH = {"Sand": "..", "Clay": "//"}

    if disp_layers:
        for i, ly in enumerate(disp_layers):
            clr   = _LC.get(ly["type"], "#d4c9a8")
            hatch = _LH.get(ly["type"], "")
            ax.fill_between([-reach, reach], [ly["bot"]]*2, [ly["top"]]*2,
                            color=clr, alpha=0.55, hatch=hatch, lw=0.3, edgecolor="#888", zorder=1)
            mid_y = (ly["top"] + ly["bot"]) / 2
            lbl   = (f"{ly['type']} {i+1}  Su = {ly['su']:.0f} kPa"
                     if ly["type"] == "Clay"
                     else f"{ly['type']} {i+1}  φ = {ly['phi']:.0f}°")
            ax.text(0, mid_y, lbl, fontsize=8, ha="center", va="center",
                    color="#444", zorder=4, alpha=0.85)
    else:
        ax.fill_between([-reach, reach], [y_min]*2, [max(te, sf)]*2,
                        color="#d4c9a8", alpha=0.45, zorder=1)

    # Fill zone
    if fill_h > 0.05:
        fill_xs = [-reach, slope_x, 0.0]
        fill_ys = [sf, sf, te]
        ax.fill_between(fill_xs, [y_min]*3, fill_ys,
                        color="#c8a96e", alpha=0.40, hatch="\\\\",
                        lw=0.4, edgecolor="#a07040", zorder=2)
        ax.plot(fill_xs, fill_ys, color="saddlebrown", lw=2.2, zorder=8)
        ax.text(-reach * 0.55, (sf + te) / 2, "Fill",
                fontsize=8, color="#7a5020", ha="center", va="center",
                style="italic", zorder=5)
    else:
        ax.plot([-reach, 0], [sf]*2, color="saddlebrown", lw=2.2, zorder=8)

    ax.plot([0, reach], [sb]*2, color="saddlebrown", lw=2.2, ls="--", zorder=8)

    # GWT
    wl_f = float(st.session_state.get("water_level",      sf))
    wl_b = float(st.session_state.get("water_level_back", sb))
    for (x0, x1, wl, lbl) in [
        (-reach, -0.5,        wl_f, f"GWT {wl_f:.1f} m"),
        ( 0.5,   reach * 0.6, wl_b, f"GWT {wl_b:.1f} m"),
    ]:
        for dy, lw_w in [(-0.15, 0.7), (0.0, 1.5), (0.15, 0.7)]:
            ax.plot([x0, x1], [wl + dy]*2, color="#1a7fc4", lw=lw_w,
                    zorder=6, alpha=0.9 if dy == 0 else 0.5)
        ax.text(x1 + 0.4, wl, lbl, fontsize=7.5, color="#1a7fc4", va="center", zorder=7)

    # Cừ
    ax.plot([0, 0], [pile_tip, te], color="red", lw=5,
            solid_capstyle="butt", zorder=10, label="Sheet pile")
    ax.plot(0, pile_tip, "v", color="red", ms=11, zorder=11, markeredgewidth=2)
    ax.text(0.4, pile_tip - span * 0.02,
            f"Pile tip  {pile_tip:.2f} m",
            fontsize=8.5, color="red", va="top", zorder=12, fontweight="bold")

    # Cung tròn
    theta  = np.linspace(0, 2 * np.pi, 720)
    cx_all = xc + R_draw * np.cos(theta)
    cy_all = yc + R_draw * np.sin(theta)
    ax.plot(cx_all, cy_all, color="#cccccc", lw=0.9, ls="--", zorder=3, alpha=0.6)

    surf_arr = np.where(cx_all < 0.0, max(sf, te), sb)
    mask     = cy_all <= surf_arr
    cx_arc   = np.where(mask, cx_all, np.nan)
    cy_arc   = np.where(mask, cy_all, np.nan)
    ax.plot(cx_arc, cy_arc, color=arc_color, lw=2.8, zorder=9, label=arc_label)
    ax.plot(xc, yc, "+", color=arc_color, ms=14, mew=2.5, zorder=10)

    # Đường nối tâm → chân cừ
    ax.annotate("", xy=(0, pile_tip), xytext=(xc, yc),
                arrowprops=dict(arrowstyle="-|>", color=arc_color,
                                lw=1.2, ls="dashed"), zorder=7)
    ax.text((xc + 0) / 2 + 0.5, (yc + pile_tip) / 2,
            f"R = {R_draw:.1f} m",
            fontsize=8, color=arc_color, zorder=12)

    if fos_val is not None:
        ax.annotate(
            f"FOS = {fos_val:.3f}",
            xy=(xc, yc), xytext=(xc + reach * 0.12, yc + span * 0.10),
            fontsize=11, fontweight="bold", color=arc_color,
            arrowprops=dict(arrowstyle="->", color=arc_color, lw=1.5), zorder=13,
        )

    ax.text(-reach * 0.75, y_min + span * 0.04, "Front (Active)",
            fontsize=9, color="#666", style="italic")
    ax.text( reach * 0.30,  y_min + span * 0.04, "Back (Retained)",
            fontsize=9, color="#666", style="italic")

    ax.axvline(0, color="#aaa", lw=0.7, ls=":", zorder=2)
    ax.set_xlim(-reach, reach)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel("x (m)  —  wall at x = 0", fontsize=10)
    ax.set_ylabel("Elevation (m)", fontsize=10)
    title = (
        f"Critical slip circle  |  FOS = {fos_val:.3f}  |  "
        f"R = {R_draw:.1f} m  |  Center = ({xc:.2f}, {yc:.2f} m)"
        if fos_val is not None
        else f"Preview — slip arc through pile tip  (R = {R_draw:.1f} m)"
    )
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(True, alpha=0.18)
    plt.tight_layout()
    return fig


# ── Render ─────────────────────────────────────────────────────────────────────

def render_slope_stability_tab() -> None:
    if not _HAS_SLOPE:
        st.error("Thư viện `slope_stability` chưa được cài đặt.\n\n"
                 "```\npip install geotech-staff-engineer\n```")
        return

    st.markdown("### Slope Stability — Limit Equilibrium")
    st.caption("Bishop Simplified · Fellenius · Spencer · Morgenstern-Price")

    st.info(
        "**Nguyen tac:** Moi cung truot deu di qua chan cu (pile tip).  \n"
        "R_i = sqrt(xc_i² + (yc_i − z_tip)²) cho tung diem luoi.  \n"
        "Surface reach duoc tinh tu dong du lon de toan bo luoi hop le.",
        icon="📐",
    )

    geo = _geo_from_session()
    tz  = _pile_tip_z(geo)

    st.markdown("#### Geometry (from Geo Data)")
    g1, g2, g3, g4, g5 = st.columns(5)
    g1.metric("Pile Top [m]",    f"{geo['top_elev']:.2f}")
    g2.metric("Front Level [m]", f"{geo['soil_level_front']:.2f}")
    g3.metric("Back Level [m]",  f"{geo['soil_level_back']:.2f}")
    g4.metric("Pile Length [m]", f"{geo['pile_length']:.1f}")
    g5.metric("Pile Tip [m]",    f"{tz:.2f}")
    st.caption(f"Fill slope H:V = **{geo['slope_ratio']:.1f}** (from Geo Data)")

    st.divider()

    grid_defaults = _auto_search_grid(geo, geo["slope_ratio"])
    _has_result   = st.session_state.get("sl_result") is not None

    col_l, col_r = st.columns([1, 1.6], gap="large")

    with col_l:
        st.markdown("#### Search Grid — Center of Circle")
        st.caption(
            "Tim tam cung (xc, yc) trong luoi.  "
            "R_i = dist(center, pile tip) — cung luon qua chan cu."
        )
        c1, c2 = st.columns(2)
        xc_min = c1.number_input("xc_min [m]", value=grid_defaults["xc_min"],
                                  step=0.5, key="sl_xmin")
        xc_max = c2.number_input("xc_max [m]", value=grid_defaults["xc_max"],
                                  step=0.5, key="sl_xmax")
        yc_min = c1.number_input("yc_min [m]", value=grid_defaults["yc_min"],
                                  step=0.5, key="sl_ymin")
        yc_max = c2.number_input("yc_max [m]", value=grid_defaults["yc_max"],
                                  step=0.5, key="sl_ymax")
        nx = c1.number_input("nx grid", min_value=3, max_value=20, value=8,
                              step=1, key="sl_nx")
        ny = c2.number_input("ny grid", min_value=3, max_value=20, value=8,
                              step=1, key="sl_ny")

        # Hiển thị reach sẽ dùng
        _reach_est = _required_reach(float(xc_min), float(xc_max),
                                     float(yc_min), float(yc_max),
                                     tz, geo["soil_level_front"])
        st.caption(f"Surface reach (auto): **{_reach_est:.1f} m**  "
                   f"| Grid: {int(nx)}×{int(ny)} = {int(nx)*int(ny)} pts")

        method_sl = st.selectbox(
            "Plot method", list(_METHODS.keys()),
            format_func=lambda k: _METHODS[k], key="sl_method",
            help="Phuong phap hien thi bieu do. Tat ca 4 phuong phap deu duoc tinh.",
        )
        n_slices  = st.number_input("No. of slices", min_value=10, max_value=100,
                                     value=30, step=5, key="sl_nslices")
        surcharge = st.number_input("Surface surcharge [kN/m²]", min_value=0.0,
                                     value=0.0, step=5.0, key="sl_surcharge")
        kh        = st.number_input("Seismic coeff. kh", min_value=0.0, max_value=0.5,
                                     value=0.0, step=0.05, key="sl_kh",
                                     help="0 = static. >0 = horizontal seismic load.")

    with col_r:
        results_all_disp = st.session_state.get("sl_results_all", {})
        plot_entry       = results_all_disp.get(method_sl, {})
        plot_crit        = plot_entry.get("critical") if _has_result else None

        st.markdown(
            f"#### {_METHODS.get(method_sl, method_sl)}" if _has_result
            else "#### Cross-section Preview"
        )

        # Preview center = giữa lưới
        xc_prev = (float(xc_min) + float(xc_max)) / 2.0
        yc_prev = (float(yc_min) + float(yc_max)) / 2.0

        fig_slip = _draw_slope_with_circle(
            geo, geo["slope_ratio"],
            xc_mid=xc_prev, yc_mid=yc_prev,
            result=plot_crit,
        )
        st.pyplot(fig_slip, use_container_width=True)
        plt.close(fig_slip)

    # ── Soil Layers ───────────────────────────────────────────────────────────
    st.markdown("#### Soil Layers")
    sync_col, _ = st.columns([1, 3])
    if sync_col.button("Sync from Soil Layers tab", key="sl_sync_btn"):
        st.session_state["slope_soil_df"] = _layers_from_front_soil()
        st.success("Synced.")

    if "slope_soil_df" not in st.session_state:
        st.session_state["slope_soil_df"] = _layers_from_front_soil()

    with st.expander("Guide", expanded=False):
        st.markdown("""
- **Top / Bottom Elev**: absolute elevation (m), positive up
- **Mode**: `drained` dung phi + c',  `undrained` dung Su
- Click **Sync** de tai lai tu tab Soil Layers
        """)

    sl_df = st.data_editor(
        st.session_state["slope_soil_df"],
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Name":            st.column_config.TextColumn(),
            "Top Elev [m]":    st.column_config.NumberColumn(format="%.1f"),
            "Bottom Elev [m]": st.column_config.NumberColumn(format="%.1f"),
            "γ [kN/m³]":       st.column_config.NumberColumn(min_value=10.0, max_value=25.0, format="%.1f"),
            "φ [°]":           st.column_config.NumberColumn(min_value=0.0, max_value=45.0, format="%.1f"),
            "c' [kN/m²]":      st.column_config.NumberColumn(min_value=0.0, format="%.1f"),
            "Su [kN/m²]":      st.column_config.NumberColumn(min_value=0.0, format="%.1f"),
            "Mode":            st.column_config.SelectboxColumn(options=["drained", "undrained"]),
        },
        key="sl_soil_editor",
    )
    st.session_state["slope_soil_df"] = sl_df

    btn_col, rst_col, _ = st.columns([1, 1, 3])
    calc  = btn_col.button("Calculate — Slope Stability", type="primary", key="sl_calc_btn")
    reset = rst_col.button("Reset results", key="sl_reset_btn")

    if reset:
        st.session_state.pop("sl_result",      None)
        st.session_state.pop("sl_results_all", None)
        st.rerun()

    if calc:
        df = sl_df.dropna(subset=["Top Elev [m]", "Bottom Elev [m]", "γ [kN/m³]"])
        if df.empty:
            st.error("Enter at least 1 soil layer.")
            st.stop()

        slope_layers = [
            SlopeSoilLayer(
                name=str(row["Name"]),
                top_elevation=float(row["Top Elev [m]"]),
                bottom_elevation=float(row["Bottom Elev [m]"]),
                gamma=float(row["γ [kN/m³]"]),
                phi=float(row["φ [°]"]),
                c_prime=float(row["c' [kN/m²]"]),
                cu=float(row["Su [kN/m²]"]),
                analysis_mode=str(row["Mode"]),
            )
            for _, row in df.iterrows()
        ]

        # Tính reach tự động
        reach_calc = _required_reach(
            float(xc_min), float(xc_max),
            float(yc_min), float(yc_max),
            tz, geo["soil_level_front"],
        )
        surface_pts = _build_surface(geo, geo["slope_ratio"], reach_calc)

        geom = SlopeGeometry(
            surface_points=surface_pts,
            soil_layers=slope_layers,
            surcharge=float(surcharge),
            kh=float(kh),
        )

        xc_vals   = np.linspace(float(xc_min), float(xc_max), int(nx))
        yc_vals   = np.linspace(float(yc_min), float(yc_max), int(ny))
        total_pts = int(nx) * int(ny)

        results_all = {}
        prog        = st.progress(0, text="Running methods...")
        method_keys = list(_METHODS.keys())

        for idx, m_key in enumerate(method_keys):
            prog.progress(
                int(idx / len(method_keys) * 100),
                text=f"[{idx+1}/{len(method_keys)}] {_METHODS[m_key]}  "
                     f"({total_pts} pts — R qua chan cu)...",
            )
            best_FOS_m = float("inf")
            best_res_m = None
            for xc_i in xc_vals:
                for yc_i in yc_vals:
                    R_i = float(np.sqrt(xc_i**2 + (yc_i - tz)**2))
                    if R_i < 1.0:
                        continue
                    try:
                        res_i = analyze_slope(
                            geom, xc=xc_i, yc=yc_i, radius=R_i,
                            method=m_key, n_slices=int(n_slices),
                        )
                        if res_i.FOS < best_FOS_m:
                            best_FOS_m = res_i.FOS
                            best_res_m = res_i
                    except Exception:
                        pass
            if best_res_m is not None:
                results_all[m_key] = {"critical": best_res_m}
            else:
                results_all[m_key] = {"error": "No valid circle — thu mo rong luoi tim kiem"}

        prog.progress(100, text="Done.")

        valid = {k: v for k, v in results_all.items() if "critical" in v}
        if valid:
            best_k = min(valid, key=lambda k: valid[k]["critical"].FOS)
            st.session_state["sl_result"] = valid[best_k]["critical"]
        else:
            st.error(
                "Khong tim thay cung hop le.  \n"
                "Thu tang xc_max / yc_max de mo rong vung tim kiem."
            )
        st.session_state["sl_results_all"] = results_all
        st.rerun()

    # ── Kết quả 4 phương pháp ─────────────────────────────────────────────────
    if _has_result:
        results_all = st.session_state.get("sl_results_all", {})
        best_crit   = st.session_state["sl_result"]

        st.divider()
        st.markdown("#### Results — All Methods")
        m_cols = st.columns(len(_METHODS))
        for i, (m_key, m_name) in enumerate(_METHODS.items()):
            entry = results_all.get(m_key, {})
            if "critical" in entry:
                FOS_m   = entry["critical"].FOS
                fos_req = _FS_MIN.get(m_key, 1.3)
                ok      = entry["critical"].is_stable and FOS_m >= fos_req
                is_best = abs(FOS_m - best_crit.FOS) < 1e-6
                label   = f"{m_name} ★" if is_best else m_name
                m_cols[i].metric(
                    label, f"FOS = {FOS_m:.3f}",
                    "Dat" if ok else "Khong dat",
                    delta_color="normal" if ok else "inverse",
                )
            elif "error" in entry:
                m_cols[i].metric(m_name, "Error", entry["error"][:40])
            else:
                m_cols[i].metric(m_name, "—")

        st.caption(
            f"★ = critical (min FOS)  |  "
            f"Center ({best_crit.xc:.2f}, {best_crit.yc:.2f})  |  "
            f"R = {best_crit.radius:.2f} m  |  "
            f"R qua chan cu tai z = {tz:.2f} m  |  "
            f"Plot: {_METHODS.get(method_sl, method_sl)}"
        )

        with st.expander("Result details", expanded=False):
            st.code(best_crit.summary(), language="text")

    st.divider()
    with st.expander("Theory — 31-slope-stability", expanded=False):
        _proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(_proj_dir, "31-slope-stability.md"),
                      "r", encoding="utf-8") as f:
                st.markdown(f.read())
        except FileNotFoundError:
            st.info("31-slope-stability not found")
