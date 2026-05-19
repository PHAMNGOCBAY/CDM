"""
bearing_capacity_tab.py — Tab: Sức chịu tải cọc đóng (tải dọc trục)
Phương pháp: FHWA GEC-12 (axial_pile — geotech-staff-engineer 4.6.0)
  - Nordlund: cát (cohesionless)
  - Tomlinson alpha: sét (cohesive)
  - Beta: cả hai loại
Run:  render_bearing_capacity_tab() được gọi từ app_coc_tai_ngang.py
"""
from __future__ import annotations
import json
import os
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.patches as mpatches
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st

try:
    from axial_pile import (
        AxialPileAnalysis,
        AxialSoilLayer,
        AxialSoilProfile,
        make_concrete_pile,
    )
    _HAS_AXIAL = True
except ImportError:
    _HAS_AXIAL = False

_LAYER_COLORS = ["#fff3cd", "#d1e7dd", "#cfe2ff", "#f8d7da", "#e2d9f3", "#fde2e4"]

_DEFAULT_SOIL_LAYERS = pd.DataFrame({
    "Depth Bottom [m]":    [5.0, 12.0, 20.0],
    "Soil Type":           ["cohesionless", "cohesive", "cohesionless"],
    "Unit Weight [kN/m³]": [19.0, 17.5, 19.5],
    "Phi [°]":             [30.0,  0.0, 32.0],
    "Cohesion [kN/m²]":   [ 0.0, 45.0,  0.0],
    "Description":         ["Sand medium dense", "Soft clay", "Dense sand"],
})

_METHODS = {
    "auto":      "Auto (Nordlund → cát, Tomlinson → sét)",
    "nordlund":  "Nordlund (cát mọi lớp)",
    "tomlinson": "Tomlinson alpha (sét mọi lớp)",
    "beta":      "Beta (effective stress — mọi loại đất)",
}

_CONCRETE_EC: dict[str, int] = {
    "f'c = 30 MPa": 26_561_000,
    "f'c = 40 MPa": 31_623_000,
    "f'c = 60 MPa": 38_730_000,
    "f'c = 70 MPa": 43_628_130,
}


# ── SW Pile catalog ───────────────────────────────────────────────────────────
# Chu vi chính xác từ §11.8 (11-sw-pile-database.md). Các loại khác dùng 2*(H+W).
_SW_PERIMETER_MM: dict[str, float] = {
    "SW-600A": 3724.4,
    "SW-600B": 3724.4,
    "SW-740":  4205.9,
    "SW-840":  4594.9,
}


def _load_sw_catalog() -> list[dict]:
    try:
        proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(proj, "data", "sw_pile_catalog.json"), encoding="utf-8") as f:
            return json.load(f)["piles"]
    except Exception:
        return []


_SW_PILES_JSON: list[dict] = _load_sw_catalog()

_SW_PILE_NAMES: list[str] = (
    list(dict.fromkeys(p["name"] for p in _SW_PILES_JSON))
    if _SW_PILES_JSON else [
        "SW-120", "SW-160", "SW-225", "SW-300",
        "SW-350A", "SW-350B", "SW-400A", "SW-400B",
        "SW-450A", "SW-450B", "SW-500A", "SW-500B",
        "SW-600A", "SW-600B", "SW-740", "SW-840",
        "SW-940", "SW-1100", "SW-1200",
    ]
)


def _sw_lookup(name: str) -> dict | None:
    """First pile entry by name from JSON catalog."""
    return next((p for p in _SW_PILES_JSON if p.get("name") == name), None)


def _sw_perimeter(name: str, H_mm: int, width_mm: int) -> tuple[float, bool]:
    """(perimeter_mm, is_exact). Exact values from §11.8, fallback = 2*(H+W)."""
    if name in _SW_PERIMETER_MM:
        return _SW_PERIMETER_MM[name], True
    return float(2 * (H_mm + width_mm)), False


# ── GeoData helpers ───────────────────────────────────────────────────────────

def _bc_geo_from_session() -> dict:
    return {
        "top_elev":         float(st.session_state.get("top_elev",          2.7)),
        "soil_level_front": float(st.session_state.get("soil_level_front",  0.0)),
        "soil_level_back":  float(st.session_state.get("soil_level_back",   0.0)),
        "pile_length":      float(st.session_state.get("L_m",              20.0)),
        "water_level":      float(st.session_state.get("water_level",      -1.0)),
        "water_level_back": float(st.session_state.get("water_level_back", -1.0)),
    }


def _bc_get_display_layers() -> list[dict]:
    """Lớp đất từ front_sand_df + front_clay_df (đồng bộ với Geo Data tab)."""
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
        tip   = float(row.get("Layer Tip [m]", prev_top - 1.0))
        stype = str(row.get("_type", "Sand"))
        layers.append({
            "top":  prev_top,
            "bot":  tip,
            "type": stype,
            "phi":  float(row.get("Phi [Deg]",  0.0)),
            "su":   float(row.get("Su [kN/m2]", 0.0)),
        })
        prev_top = tip
    return layers


# ── Hình vẽ ───────────────────────────────────────────────────────────────────

def _draw_bc_illustration(
    geo: dict,
    disp_layers: list[dict],
    pile_len_m: float,
    H_mm: int = 840,
    pile_name: str = "SW-840",
) -> plt.Figure:
    """GEO5-style: cọc trong mặt cắt địa tầng (từ GeoData)."""
    te       = geo["top_elev"]
    sf       = geo["soil_level_front"]
    sb       = geo["soil_level_back"]
    wl       = geo["water_level"]
    pile_tip = te - pile_len_m
    sf_top   = max(sf, te)
    reach    = max(pile_len_m * 0.22, 3.5)
    pile_hw  = min(H_mm / 1000 * 0.30, reach * 0.35)   # half-width of pile rect

    y_bot = (min(ly["bot"] for ly in disp_layers) - 0.5) if disp_layers else (pile_tip - 1.0)
    y_top = sf_top + max(pile_len_m * 0.06, 1.5)
    span  = y_top - y_bot

    fig, ax = plt.subplots(figsize=(4.5, 9), dpi=90)
    ax.set_facecolor("#f9f9f9")

    _LC = {"Sand": "#f5e6c8", "Clay": "#c8d4e8"}
    _LH = {"Sand": "..", "Clay": "//"}

    # Soil layers
    if disp_layers:
        for i, ly in enumerate(disp_layers):
            clr   = _LC.get(ly["type"], "#d4c9a8")
            hatch = _LH.get(ly["type"], "")
            ax.fill_between(
                [-reach, reach], [ly["bot"]]*2, [ly["top"]]*2,
                color=clr, alpha=0.55, hatch=hatch, lw=0.3, edgecolor="#888", zorder=1,
            )
            mid_y = (ly["top"] + ly["bot"]) / 2
            lbl   = (f"Su={ly['su']:.0f} kPa" if ly["type"] == "Clay"
                     else f"φ={ly['phi']:.0f}°")
            ax.text(reach * 0.55, mid_y, f"{ly['type']} {i+1}  {lbl}",
                    fontsize=8, ha="center", va="center", color="#444", zorder=4)
    else:
        ax.fill_between([-reach, reach], [y_bot]*2, [te]*2,
                        color="#d4c9a8", alpha=0.45, zorder=1)

    # Fill zone (Back: sb → te)
    if te > sb + 0.05:
        ax.fill_between(
            [-reach, reach], [sb]*2, [te]*2,
            color="#c8a96e", alpha=0.38, hatch="\\\\", lw=0.4, edgecolor="#a07040", zorder=2,
        )
        ax.text(reach * 0.55, (sb + te) / 2, "Fill",
                fontsize=8.5, color="#7a5020", ha="center", va="center",
                style="italic", zorder=5)

    # GWT (3 vạch GEO5)
    for dy, lw_w in [(-0.10, 0.7), (0.0, 1.5), (0.10, 0.7)]:
        ax.plot([-reach, reach], [wl + dy]*2,
                color="#1a7fc4", lw=lw_w, zorder=6,
                alpha=0.9 if dy == 0.0 else 0.5)
    ax.text(reach * 0.82, wl + span * 0.015,
            f"GWT {wl:.1f}m", fontsize=7.5, color="#1a7fc4", va="bottom", zorder=7)

    # Ground line
    ax.plot([-reach, reach], [sf]*2, color="saddlebrown", lw=2.2, zorder=8)
    if te > sf + 0.05:
        ax.plot([-reach, reach], [te]*2,
                color="saddlebrown", lw=1.2, ls=":", zorder=7, alpha=0.6)

    # Pile body
    ax.fill_between([-pile_hw, pile_hw], [pile_tip]*2, [te]*2,
                    color="steelblue", alpha=0.55, zorder=10)
    ax.plot([-pile_hw, pile_hw, pile_hw, -pile_hw, -pile_hw],
            [te, te, pile_tip, pile_tip, te],
            color="red", lw=2, zorder=11)
    ax.plot(0, pile_tip, "v", color="red", ms=9, zorder=12, markeredgewidth=2)

    # L annotation (double arrow)
    xarr = -reach * 0.68
    ax.annotate("", xy=(xarr, pile_tip), xytext=(xarr, te),
                arrowprops=dict(arrowstyle="<->", color="navy", lw=1.5), zorder=9)
    ax.text(xarr + reach * 0.08, (pile_tip + te) / 2,
            f"L = {pile_len_m:.1f} m",
            fontsize=9, color="navy", va="center", fontweight="bold", zorder=12)

    # Elevation labels
    ax.text(reach * 0.82, te + span * 0.01,
            f"Top {te:.2f}m", fontsize=7.5, color="navy", va="bottom", zorder=12)
    ax.text(reach * 0.82, pile_tip - span * 0.01,
            f"Tip {pile_tip:.2f}m", fontsize=7.5, color="red", va="top", zorder=12)

    ax.set_xlim(-reach, reach)
    ax.set_ylim(y_bot, y_top)
    ax.set_ylabel("Cao độ (m)", fontsize=10)
    ax.set_title(f"{pile_name}  |  H = {H_mm} mm  |  L = {pile_len_m:.1f} m",
                 fontsize=9.5, fontweight="bold")
    ax.set_xticks([])
    ax.grid(True, axis="y", alpha=0.2)
    fig.tight_layout()
    return fig


def _draw_sw_cross_section(
    name: str, H_mm: int, t_mm: int, width_mm: int,
    n_strands: int, phi_strand_mm: float,
    Atd_cm2: float, perimeter_mm: float, perim_exact: bool,
) -> plt.Figure:
    """Mặt cắt ngang cọc SW (GEO5-style schematic)."""
    H = H_mm / 1000
    t = t_mm / 1000
    W = width_mm / 1000
    fig, ax = plt.subplots(figsize=(4.5, 4.2), dpi=90)

    outer = mpatches.FancyBboxPatch((-W / 2, -H / 2), W, H,
        boxstyle="round,pad=0.003", ec="#333", fc="#bbb", lw=2, zorder=2)
    ax.add_patch(outer)

    inner_h = H - 2 * t
    inner_w = W - 2 * t
    if inner_h > 0 and inner_w > 0:
        inner = mpatches.FancyBboxPatch((-inner_w / 2, -inner_h / 2), inner_w, inner_h,
            boxstyle="round,pad=0.001", ec="#555", fc="white", lw=1, zorder=3)
        ax.add_patch(inner)

    # Dimension arrows
    ax.annotate("", xy=(W / 2 + W * 0.18, H / 2), xytext=(W / 2 + W * 0.18, -H / 2),
                arrowprops=dict(arrowstyle="<->", color="#333", lw=1.2))
    ax.text(W / 2 + W * 0.26, 0, f"H = {H_mm} mm",
            fontsize=8, va="center", color="#333", rotation=90, ha="left")

    ax.annotate("", xy=(W / 2, -H / 2 - H * 0.15), xytext=(-W / 2, -H / 2 - H * 0.15),
                arrowprops=dict(arrowstyle="<->", color="#333", lw=1.2))
    ax.text(0, -H / 2 - H * 0.24, f"W = {width_mm} mm",
            fontsize=8, ha="center", color="#333")

    ax.annotate("", xy=(-W / 2, H / 4), xytext=(-W / 2 + t, H / 4),
                arrowprops=dict(arrowstyle="<->", color="steelblue", lw=1.2))
    ax.text(-W / 2 + t / 2, H / 4 + H * 0.07,
            f"t = {t_mm} mm", fontsize=7.5, ha="center", color="steelblue")

    # Properties table
    perim_note = "" if perim_exact else " *"
    props = (
        f"Atd = {Atd_cm2:.0f} cm²\n"
        f"Chu vi = {perimeter_mm:.0f} mm{perim_note}\n"
        f"{n_strands} sợi ⌀{phi_strand_mm:.2f} mm"
    )
    ax.text(W / 2 + W * 0.28, -H / 4, props,
            fontsize=7.5, va="center", ha="left", color="#333",
            bbox=dict(boxstyle="round,pad=0.3", fc="#fffbe8", ec="#ccc", alpha=0.9),
            zorder=5)

    ax.set_xlim(-W * 1.4, W * 1.9)
    ax.set_ylim(-H * 1.5, H * 1.1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"{name} — BETON 6  (n={n_strands} strands ⌀{phi_strand_mm} mm)",
                 fontsize=9.5, pad=8)
    fig.tight_layout()
    return fig


# ── Charts ────────────────────────────────────────────────────────────────────

def _plot_capacity_vs_depth(
    cvd: pd.DataFrame,
    Qa_target: float,
    pile_name: str,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 8))
    depths = cvd["depth_m"].values
    Qult   = cvd["Q_ultimate_kN"].values
    Qa     = cvd["Q_allowable_kN"].values

    ax.plot(Qult, depths, "r-o", ms=4, lw=2, label="Q_ult (kN)")
    ax.plot(Qa,   depths, "b--s", ms=4, lw=2, label="Q_allow (kN)")
    ax.axvline(Qa_target, color="orange", lw=1.5, ls="--",
               label=f"Q_target = {Qa_target:.0f} kN")

    idx_ok = np.where(Qa >= Qa_target)[0]
    if idx_ok.size > 0:
        d_req = depths[idx_ok[0]]
        ax.axhline(d_req, color="green", lw=1.2, ls=":",
                   label=f"L_req ≈ {d_req:.1f} m")
        ax.plot(Qa_target, d_req, "g*", ms=12, zorder=5)

    ax.set_xlabel("Sức chịu tải (kN)", fontsize=10)
    ax.set_ylabel("Chiều sâu mũi cọc (m)", fontsize=10)
    ax.set_title(f"Sức chịu tải cọc đóng — {pile_name}", fontsize=11, fontweight="bold")
    ax.invert_yaxis()
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def _plot_load_transfer(result, pile_name: str, pile_len: float) -> plt.Figure:
    bd = result.layer_breakdown
    if not bd:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No data", ha="center")
        return fig

    depths_top = [d["depth_top_m"]    for d in bd]
    depths_bot = [d["depth_bottom_m"] for d in bd]
    qs_vals    = [d["skin_friction_kN"] for d in bd]
    methods    = [d["method"]          for d in bd]
    soil_types = [d["soil_type"]       for d in bd]

    fig, axes = plt.subplots(1, 2, figsize=(10, 8), sharey=True)
    fig.suptitle(f"Phân bố tải — {pile_name}  L={pile_len:.1f} m",
                 fontsize=11, fontweight="bold")

    ax0 = axes[0]
    pile_w = 0.3
    ax0.add_patch(plt.Rectangle((-pile_w / 2, 0), pile_w, pile_len,
                                color="steelblue", alpha=0.55, zorder=3))
    ax0.text(0, -0.8, "Cọc đóng", fontsize=9, ha="center", color="steelblue")
    for i, (zt, zb, st_, mth) in enumerate(zip(depths_top, depths_bot, soil_types, methods)):
        clr = _LAYER_COLORS[i % len(_LAYER_COLORS)]
        ax0.add_patch(plt.Rectangle((-2.5, zt), 2.5 - pile_w / 2, zb - zt,
                                    color=clr, alpha=0.6, zorder=1))
        ax0.text(-1.3, (zt + zb) / 2, f"{st_[:4].upper()}\n{mth[:4]}",
                 fontsize=7, ha="center", va="center", color="#444")
    ax0.set_xlim(-3, 1.5)
    ax0.set_ylim(0, pile_len * 1.08)
    ax0.invert_yaxis()
    ax0.set_ylabel("Chiều sâu (m)", fontsize=10)
    ax0.set_title("Mặt cắt cọc", fontsize=10)
    ax0.set_xticks([])
    ax0.grid(True, alpha=0.2, axis="y")

    ax1 = axes[1]
    for i, (zt, zb, qs) in enumerate(zip(depths_top, depths_bot, qs_vals)):
        clr = _LAYER_COLORS[i % len(_LAYER_COLORS)]
        ax1.barh([(zt + zb) / 2], [qs], height=(zb - zt) * 0.85,
                 color=clr, edgecolor="#888", lw=0.7, zorder=2)
        ax1.text(qs + 5, (zt + zb) / 2, f"{qs:.0f} kN",
                 fontsize=8, va="center", color="#333")
    ax1.set_xlabel("Ma sát bên Qs (kN)", fontsize=10)
    ax1.set_title("Phân bố ma sát bên", fontsize=10)
    ax1.set_ylim(0, pile_len * 1.08)
    ax1.invert_yaxis()
    ax1.grid(True, alpha=0.3, axis="x")

    Qp = result.Q_tip
    ax1.annotate(f"Qp = {Qp:.0f} kN",
                 xy=(0, pile_len), xytext=(max(qs_vals) * 0.5, pile_len * 0.9),
                 fontsize=9, color="firebrick",
                 arrowprops=dict(arrowstyle="->", color="firebrick"))
    fig.tight_layout()
    return fig


# ── Settlement ────────────────────────────────────────────────────────────────

def _compute_settlement(
    Q_w: float,
    Q_skin: float,
    Q_tip: float,
    L: float,
    Atd_m2: float,
    E_p: float,
    D: float,
    perimeter_m: float,
    Cp: float = 0.02,
    xi: float = 0.5,
) -> dict:
    """Das/Vesic (1977) — đơn cọc đóng chịu tải dọc trục.

    Q_w      : tải trọng làm việc [kN]
    Q_skin   : ma sát bên tổng cực hạn [kN]
    Q_tip    : sức kháng mũi cực hạn [kN]
    L        : chiều dài cọc [m]
    Atd_m2   : diện tích mặt cắt ngang thực tế [m²]
    E_p      : mô đun đàn hồi cọc [kN/m²]
    D        : chiều rộng/đường kính cọc [m]
    perimeter_m: chu vi cọc [m]
    Cp       : hệ số thực nghiệm (0.02 cát/cứng, 0.04 sét, 0.03 bụi)
    xi       : hệ số phân bố ma sát (0.5 đều, 0.67 parabol)
    """
    Q_ult = Q_skin + Q_tip
    if Q_ult <= 0 or Atd_m2 <= 0 or E_p <= 0:
        return {"se_mm": 0.0, "ssp_mm": 0.0, "sss_mm": 0.0, "total_mm": 0.0,
                "Q_wp_kN": 0.0, "Q_ws_kN": 0.0, "qp_ult_kPa": 0.0,
                "qwp_kPa": 0.0, "Cs": 0.0, "Cp": Cp, "xi": xi}

    Q_wp = Q_w * Q_tip  / Q_ult     # tải đến mũi [kN]
    Q_ws = Q_w * Q_skin / Q_ult     # tải phần ma sát [kN]

    # 1. Nén đàn hồi trục cọc
    se = (Q_wp + xi * Q_ws) * L / (Atd_m2 * E_p) * 1000   # mm

    # 2. Lún tại mũi — Das (2019) Eq.11.72: ssp = Cp × Qwp / (D × qp_ult)
    #    qp_ult = sức kháng đơn vị mũi cực hạn [kN/m²]
    qp_ult = Q_tip / Atd_m2   # [kN/m²]
    if qp_ult > 1.0 and D > 0:
        ssp = Cp * Q_wp / (D * qp_ult) * 1000   # mm
    else:
        ssp = 0.0

    # 3. Lún do ma sát bên — Das Eq.11.73: sss = Cs × [Qws/(pL×L×qp_ult)] × D
    Cs = Cp * (0.93 + 0.16 * (L / D) ** 0.5) if D > 0 else 0.0
    if perimeter_m * L * qp_ult > 0:
        sss = Cs * (Q_ws / (perimeter_m * L * qp_ult)) * D * 1000   # mm
    else:
        sss = 0.0

    qwp = Q_wp / Atd_m2   # ứng suất mũi làm việc [kN/m²]
    return {
        "se_mm":       round(se,     2),
        "ssp_mm":      round(ssp,    2),
        "sss_mm":      round(sss,    2),
        "total_mm":    round(se + ssp + sss, 2),
        "Q_wp_kN":     round(Q_wp,   1),
        "Q_ws_kN":     round(Q_ws,   1),
        "qwp_kPa":     round(qwp,    1),
        "qp_ult_kPa":  round(qp_ult, 1),
        "Cs":          round(Cs,     4),
        "Cp":          Cp,
        "xi":          xi,
    }


def _plot_settlement(settle: dict, pile_name: str, Q_w: float,
                     s_limit_mm: float = 25.0) -> plt.Figure:
    labels = ["Nén đàn hồi\ntrục cọc (sₑ)",
              "Lún mũi\n(s_sp)",
              "Lún ma sát\nbên (s_ss)",
              "Tổng (sₜ)"]
    vals   = [settle["se_mm"], settle["ssp_mm"], settle["sss_mm"], settle["total_mm"]]
    colors = ["#4472c4", "#ed7d31", "#a9d18e", "#c00000"]

    fig, ax = plt.subplots(figsize=(7, 4), dpi=90)
    bars = ax.bar(labels, vals, color=colors, edgecolor="#555", lw=0.8, alpha=0.85)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f"{v:.2f} mm", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.axhline(s_limit_mm, color="red", lw=1.0, ls="--", alpha=0.7,
               label=f"Giới hạn cho phép {s_limit_mm:.0f} mm")
    ax.set_ylabel("Độ lún (mm)", fontsize=10)
    ax.set_title(
        f"Dự báo độ lún cọc đơn — {pile_name}\n"
        f"Q_w = {Q_w:.0f} kN  |  Cp = {settle['Cp']}  |  ξ = {settle['xi']}"
        f"  (Das/Vesic 1977)",
        fontsize=9.5, fontweight="bold",
    )
    ax.set_ylim(0, max(vals + [0]) * 1.35 + 0.5)
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


# ── Multi-pile comparison ─────────────────────────────────────────────────────

def _run_pile_calc(
    pile_name: str,
    soil_df: pd.DataFrame,
    gwt_depth: float,
    method: str,
    fos: float,
    pile_len: float,
    d_min: float,
    d_max: float,
    d_step: float,
) -> dict | None:
    """Tính axial_pile cho 1 loại cọc SW. Trả về dict kết quả hoặc None nếu lỗi."""
    entry = _sw_lookup(pile_name)
    if not entry:
        return None
    H_mm_i     = int(entry["H_mm"])
    Atd_cm2_i  = float(entry["Atd_cm2"])
    w_mm_i     = int(entry["width_mm"])
    perim_i, _ = _sw_perimeter(pile_name, H_mm_i, w_mm_i)
    perim_m_i  = perim_i / 1000
    Atd_m2_i   = Atd_cm2_i / 10_000
    pile_w_i   = perim_m_i / 4
    tip_corr_i = Atd_m2_i / (pile_w_i ** 2)

    df = soil_df.dropna(subset=["Depth Bottom [m]", "Unit Weight [kN/m³]"])
    df = df.sort_values("Depth Bottom [m]").reset_index(drop=True)
    depth_tops  = [0.0] + df["Depth Bottom [m]"].tolist()[:-1]
    thicknesses = [row["Depth Bottom [m]"] - depth_tops[i] for i, row in df.iterrows()]
    axial_layers = [
        AxialSoilLayer(
            thickness=max(0.1, thicknesses[i]),
            soil_type=str(row["Soil Type"]),
            unit_weight=float(row["Unit Weight [kN/m³]"]),
            friction_angle=float(row["Phi [°]"]),
            cohesion=float(row["Cohesion [kN/m²]"]),
            description=str(row.get("Description", "")),
        )
        for i, row in df.iterrows()
    ]
    sp_obj = AxialSoilProfile(layers=axial_layers, gwt_depth=gwt_depth)
    pile   = make_concrete_pile(width=pile_w_i, shape="square")
    ana    = AxialPileAnalysis(pile=pile, soil=sp_obj, pile_length=pile_len,
                               method=method, factor_of_safety=fos)
    res    = ana.compute()

    Q_tip_c   = res.Q_tip * tip_corr_i
    Q_ult_c   = res.Q_skin + Q_tip_c
    Q_allow_c = Q_ult_c / fos

    # CVD
    n_pts = max(5, round((d_max - d_min) / d_step) + 1)
    try:
        cvd_raw = ana.capacity_vs_depth(depth_min=d_min, depth_max=d_max, n_points=n_pts)
        if isinstance(cvd_raw, list):
            cvd = pd.DataFrame(cvd_raw)
        elif isinstance(cvd_raw, pd.DataFrame):
            cvd = cvd_raw.copy()
        else:
            cvd = pd.DataFrame()
        if not cvd.empty:
            if "Q_allowable_kN" not in cvd.columns:
                cvd["Q_allowable_kN"] = cvd["Q_ultimate_kN"] / fos
            if tip_corr_i != 1.0 and "Q_skin_kN" in cvd.columns:
                q_tip_raw = cvd["Q_ultimate_kN"] - cvd["Q_skin_kN"]
                cvd["Q_ultimate_kN"] = cvd["Q_skin_kN"] + q_tip_raw * tip_corr_i
                cvd["Q_allowable_kN"] = cvd["Q_ultimate_kN"] / fos
    except Exception:
        cvd = pd.DataFrame()

    _wT_i   = float(entry.get("weight_T", 16.35))
    _Lstd_i = int(entry.get("L_std_m", 22))
    return {
        "pile_name":  pile_name,
        "H_mm":       H_mm_i,
        "Atd_cm2":    Atd_cm2_i,
        "perim_mm":   perim_i,
        "perim_m":    perim_m_i,
        "Atd_m2":     Atd_m2_i,
        "D":          H_mm_i / 1000,
        "w_kNm":      _wT_i * 9.81 / _Lstd_i,
        "Q_ult":      Q_ult_c,
        "Q_skin":     res.Q_skin,
        "Q_tip":      Q_tip_c,
        "Q_allow":    Q_allow_c,
        "tip_corr":   tip_corr_i,
        "cvd":        cvd,
        "result":     res,
    }


def _plot_comparison_cvd(pile_results: list[dict], Q_target: float) -> plt.Figure:
    """Q_ult và Q_allow vs chiều sâu — tất cả phương án trên cùng 2 trục."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 8), sharey=True)
    cmap   = plt.cm.tab10
    colors = [cmap(i / max(len(pile_results), 1)) for i in range(len(pile_results))]

    for res, clr in zip(pile_results, colors):
        cvd = res["cvd"]
        if cvd.empty:
            continue
        depths = cvd["depth_m"].values
        axes[0].plot(cvd["Q_ultimate_kN"].values,  depths, "-o",  ms=3, lw=1.8,
                     color=clr, label=res["pile_name"])
        axes[1].plot(cvd["Q_allowable_kN"].values, depths, "--s", ms=3, lw=1.8,
                     color=clr, label=res["pile_name"])

    axes[1].axvline(Q_target, color="orange", lw=2, ls="--",
                    label=f"Q_tk = {Q_target:.0f} kN", zorder=5)

    for ax, title, xlabel in [
        (axes[0], "Q_ultimate vs Chiều sâu",  "Q_ultimate (kN)"),
        (axes[1], "Q_allowable vs Chiều sâu", "Q_allowable (kN)"),
    ]:
        ax.set_xlabel(xlabel, fontsize=10)
        ax.set_ylabel("Chiều sâu mũi cọc (m)", fontsize=10)
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.invert_yaxis()
        ax.legend(fontsize=8, loc="lower right")
        ax.grid(True, alpha=0.3)

    fig.suptitle("So sánh sức chịu tải các phương án cọc SW",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    return fig


def _plot_comparison_bars(
    pile_results: list[dict],
    pile_len: float,
    Q_target: float,
) -> plt.Figure:
    """Bar chart so sánh Q_ult (skin+tip) và Q_allow tại chiều sâu thiết kế."""
    names    = [r["pile_name"] for r in pile_results]
    Q_sk     = np.array([r["Q_skin"]  for r in pile_results])
    Q_tp     = np.array([r["Q_tip"]   for r in pile_results])
    Q_al     = np.array([r["Q_allow"] for r in pile_results])
    Q_ul     = Q_sk + Q_tp
    x        = np.arange(len(names))
    w        = 0.5

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))

    # Panel 1 — stacked bars Q_skin + Q_tip
    ax0 = axes[0]
    ax0.bar(x, Q_sk, w, label="Q_skin", color="#4472c4", alpha=0.85)
    ax0.bar(x, Q_tp, w, bottom=Q_sk, label="Q_tip", color="#ed7d31", alpha=0.85)
    ax0.axhline(Q_target, color="orange", lw=2, ls="--",
                label=f"Q_tk = {Q_target:.0f} kN", zorder=5)
    for i, qu in enumerate(Q_ul):
        ax0.text(i, qu + max(Q_ul) * 0.01, f"{qu:.0f}", ha="center",
                 fontsize=8.5, fontweight="bold")
    ax0.set_xticks(x); ax0.set_xticklabels(names, rotation=25, ha="right")
    ax0.set_ylabel("Sức chịu tải (kN)", fontsize=10)
    ax0.set_title(f"Q_ultimate tại L = {pile_len:.1f} m", fontsize=10, fontweight="bold")
    ax0.legend(fontsize=8); ax0.grid(True, axis="y", alpha=0.3)

    # Panel 2 — Q_allowable với màu Dat/KDat
    ax1 = axes[1]
    clrs = ["#2ca02c" if qa >= Q_target else "#d62728" for qa in Q_al]
    ax1.bar(x, Q_al, w * 1.1, color=clrs, edgecolor="#555", lw=0.8, alpha=0.85)
    ax1.axhline(Q_target, color="orange", lw=2, ls="--",
                label=f"Q_tk = {Q_target:.0f} kN", zorder=5)
    for i, qa in enumerate(Q_al):
        verdict = "Dat" if qa >= Q_target else "KDat"
        ax1.text(i, qa + max(Q_al) * 0.01, f"{qa:.0f}\n({verdict})", ha="center",
                 fontsize=8.5, fontweight="bold",
                 color="#1a6620" if qa >= Q_target else "#8b0000")
    ax1.set_xticks(x); ax1.set_xticklabels(names, rotation=25, ha="right")
    ax1.set_ylabel("Q_allowable (kN)", fontsize=10)
    ax1.set_title(f"Q_allowable tại L = {pile_len:.1f} m", fontsize=10, fontweight="bold")
    ax1.legend(fontsize=8); ax1.grid(True, axis="y", alpha=0.3)

    fig.suptitle("So sánh sức chịu tải — phương án cọc SW",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    return fig


# ── All-methods comparison ───────────────────────────────────────────────────

_METHOD_LABELS: dict[str, str] = {
    "auto":      "Auto (Nordlund/Tomlinson)",
    "nordlund":  "Nordlund",
    "tomlinson": "Tomlinson alpha",
    "beta":      "Beta",
}
_METHOD_COLORS: dict[str, str] = {
    "auto":      "#1f77b4",
    "nordlund":  "#ff7f0e",
    "tomlinson": "#2ca02c",
    "beta":      "#d62728",
}
_METHOD_LS: dict[str, str] = {
    "auto": "-", "nordlund": "--", "tomlinson": "-.", "beta": ":",
}


def _plot_methods_comparison_cvd(
    methods_results: dict,
    Q_target: float,
    pile_name: str,
) -> plt.Figure:
    """Q_ult và Q_allow vs chiều sâu — 4 phương pháp trên cùng 2 trục."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 8), sharey=True)

    for mkey, mres in methods_results.items():
        if "error" in mres:
            continue
        cvd = mres.get("cvd")
        if cvd is None or (isinstance(cvd, pd.DataFrame) and cvd.empty):
            continue
        lbl    = _METHOD_LABELS.get(mkey, mkey)
        clr    = _METHOD_COLORS.get(mkey, "#888")
        ls     = _METHOD_LS.get(mkey, "-")
        depths = cvd["depth_m"].values
        axes[0].plot(cvd["Q_ultimate_kN"].values,  depths, lw=2, color=clr,
                     ls=ls, marker="o", ms=3, label=lbl)
        axes[1].plot(cvd["Q_allowable_kN"].values, depths, lw=2, color=clr,
                     ls=ls, marker="s", ms=3, label=lbl)

    for ax, xlabel, title in [
        (axes[0], "Q_ultimate (kN)",  "Q_ultimate vs Chiều sâu"),
        (axes[1], "Q_allowable (kN)", "Q_allowable vs Chiều sâu"),
    ]:
        ax.axvline(Q_target, color="orange", lw=2, ls="--",
                   label=f"Q_tk = {Q_target:.0f} kN", zorder=5)
        ax.set_xlabel(xlabel, fontsize=10)
        ax.set_ylabel("Chiều sâu mũi cọc (m)", fontsize=10)
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.invert_yaxis()
        ax.legend(fontsize=9, loc="lower right")
        ax.grid(True, alpha=0.3)

    fig.suptitle(f"So sánh phương pháp tính — {pile_name}",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    return fig


def _plot_methods_bar(
    methods_items: list,
    Q_target: float,
    pile_name: str,
    pile_len: float,
) -> plt.Figure:
    """Bar chart Q_skin+Q_tip và Q_allow tại chiều sâu thiết kế — 4 phương pháp."""
    keys   = [k for k, _ in methods_items]
    labels = [_METHOD_LABELS.get(k, k) for k in keys]
    Q_sk   = np.array([v["Q_skin"]  for _, v in methods_items])
    Q_tp   = np.array([v["Q_tip"]   for _, v in methods_items])
    Q_al   = np.array([v["Q_allow"] for _, v in methods_items])
    Q_ul   = Q_sk + Q_tp
    x      = np.arange(len(keys))
    w      = 0.5

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))

    ax0 = axes[0]
    ax0.bar(x, Q_sk, w, label="Q_skin", color="#4472c4", alpha=0.85)
    ax0.bar(x, Q_tp, w, bottom=Q_sk, label="Q_tip",  color="#ed7d31", alpha=0.85)
    ax0.axhline(Q_target, color="orange", lw=2, ls="--",
                label=f"Q_tk = {Q_target:.0f} kN", zorder=5)
    for i, qu in enumerate(Q_ul):
        ax0.text(i, qu + max(Q_ul) * 0.015, f"{qu:.0f}", ha="center",
                 fontsize=9, fontweight="bold")
    ax0.set_xticks(x)
    ax0.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
    ax0.set_ylabel("Sức chịu tải (kN)", fontsize=10)
    ax0.set_title(f"Q_ultimate tại L = {pile_len:.1f} m", fontsize=10, fontweight="bold")
    ax0.legend(fontsize=9); ax0.grid(True, axis="y", alpha=0.3)

    ax1 = axes[1]
    clrs = [_METHOD_COLORS.get(k, "#888") for k in keys]
    ax1.bar(x, Q_al, w * 1.1, color=clrs, edgecolor="#555", lw=0.8, alpha=0.85)
    ax1.axhline(Q_target, color="orange", lw=2, ls="--",
                label=f"Q_tk = {Q_target:.0f} kN", zorder=5)
    for i, (k, qa) in enumerate(zip(keys, Q_al)):
        verdict = "Dat" if qa >= Q_target else "KDat"
        ax1.text(i, qa + max(Q_al) * 0.015, f"{qa:.0f}\n({verdict})", ha="center",
                 fontsize=9, fontweight="bold",
                 color="#1a6620" if qa >= Q_target else "#8b0000")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
    ax1.set_ylabel("Q_allowable (kN)", fontsize=10)
    ax1.set_title(f"Q_allowable tại L = {pile_len:.1f} m", fontsize=10, fontweight="bold")
    ax1.legend(fontsize=9); ax1.grid(True, axis="y", alpha=0.3)

    fig.suptitle(f"So sánh phương pháp tính — {pile_name}",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    return fig


# ── Main render ───────────────────────────────────────────────────────────────

def render_bearing_capacity_tab() -> None:
    """Streamlit tab body — Sức chịu tải cọc đóng (axial_pile FHWA)."""
    if not _HAS_AXIAL:
        st.error("Thư viện `axial_pile` chưa được cài đặt.\n\n"
                 "```\npip install geotech-staff-engineer\n```")
        return

    st.markdown("### Sức chịu tải cọc đóng — FHWA GEC-12 (axial_pile)")
    st.caption("Nordlund (cát) · Tomlinson alpha (sét) · Beta (effective stress)")

    # ── Đọc SW pile từ Sheet Pile Section ────────────────────────────────────
    sw_name  = st.session_state.get("sel_pile", "SW-840")
    sw_pile  = _sw_lookup(sw_name)
    if sw_pile:
        H_mm        = int(sw_pile["H_mm"])
        t_mm        = int(sw_pile["t_mm"])
        width_mm    = int(sw_pile["width_mm"])
        Atd_cm2     = float(sw_pile["Atd_cm2"])
        Itd_cm4     = float(sw_pile["Itd_cm4"])
        weight_T    = float(sw_pile["weight_T"])
        L_std_m     = int(sw_pile.get("L_std_m", 22))
        n_strands   = int(sw_pile.get("n_strands", 20))
        phi_s_mm    = float(sw_pile.get("phi_strand_mm", 15.24))
        L_min_m     = int(sw_pile.get("L_min_m", 17))
        L_max_m     = int(sw_pile.get("L_max_m", 30))
        Mcr_Tm      = float(sw_pile.get("Mcr_Tm", 77.1))
    else:
        H_mm, t_mm, width_mm = 840, 160, 996
        Atd_cm2, Itd_cm4     = 3107.0, 2_125_017.0
        weight_T, L_std_m    = 16.35, 22
        n_strands, phi_s_mm  = 22, 15.24
        L_min_m, L_max_m     = 17, 29
        Mcr_Tm               = 77.1

    perim_mm, perim_exact = _sw_perimeter(sw_name, H_mm, width_mm)
    w_kNm   = weight_T * 9.81 / L_std_m      # trọng lượng đơn vị (kN/m)
    Atd_m2  = Atd_cm2 / 10_000               # m²

    # ── Info box (kết nối với Sheet Pile Section) ─────────────────────────────
    with st.container(border=True):
        st.caption("Thông tin cọc SW — từ tab **Sheet Pile Section**"
                   "  (chọn loại cọc khác tại thanh điều hướng bên trái)")
        ic1, ic2, ic3, ic4, ic5, ic6 = st.columns(6)
        ic1.metric("Loại cọc",    sw_name)
        ic2.metric("H × t (mm)", f"{H_mm} × {t_mm}")
        ic3.metric("Atd",        f"{Atd_cm2:.0f} cm²",
                   help="Diện tích mặt cắt quy đổi (bê tông + cáp DUL)")
        ic4.metric("Chu vi",
                   f"{perim_mm:.0f} mm" + ("" if perim_exact else " *"),
                   help="Dùng cho tính ma sát bên (NT2 / TCVN 11823-10)")
        ic5.metric("TL đơn vị",  f"{w_kNm:.2f} kN/m",
                   help=f"= {weight_T}T × 9.81 / {L_std_m}m")
        ic6.metric("L min–max",  f"{L_min_m}–{L_max_m} m")

    if not perim_exact:
        st.caption("* Chu vi gần đúng = 2(H+W). Giá trị chính xác chỉ có cho: "
                   "SW-600A/B, SW-740, SW-840 (xem §11.8 — 11-sw-pile-database.md).")

    st.divider()

    # ── Đọc geometry từ GeoData ───────────────────────────────────────────────
    geo         = _bc_geo_from_session()
    disp_layers = _bc_get_display_layers()

    # ── Hai cột chính ─────────────────────────────────────────────────────────
    col_inp, col_res = st.columns([1, 1.1], gap="large")

    with col_inp:
        st.markdown("#### Thông số cọc")
        pile_shape = st.selectbox(
            "Tiết diện",
            ["square", "circular", "sw_pile"],
            key="bc_pile_shape",
            format_func=lambda x: {
                "square":   "Hình chữ nhật / vuông",
                "circular": "Hình tròn",
                "sw_pile":  "Cọc ván SW (catalog BETON 6)",
            }[x],
        )

        # Biến tính toán — khởi tạo mặc định, ghi đè theo pile_shape
        pile_width_eff      = round(H_mm / 1000, 2)
        pile_shape_eff      = pile_shape if pile_shape != "sw_pile" else "square"
        tip_correction      = 1.0
        sw_bc_name          = sw_name
        bc_H_mm_fig         = H_mm
        bc_w_kNm_calc       = w_kNm
        bc_Atd_cm2_calc     = Atd_cm2
        bc_perim_mm_calc    = perim_mm
        bc_perim_exact_calc = perim_exact

        if pile_shape == "sw_pile":
            _default_idx = (
                _SW_PILE_NAMES.index(sw_name)
                if sw_name in _SW_PILE_NAMES else 15
            )
            sw_bc_name = st.selectbox(
                "Loại cọc SW", _SW_PILE_NAMES,
                index=_default_idx, key="bc_sw_pile_sel",
            )
            _entry = _sw_lookup(sw_bc_name)
            if _entry:
                bc_H_mm_fig     = int(_entry["H_mm"])
                bc_Atd_cm2_calc = float(_entry["Atd_cm2"])
                _wT             = float(_entry["weight_T"])
                _Lstd           = int(_entry.get("L_std_m", 22))
                bc_w_kNm_calc   = _wT * 9.81 / _Lstd
                _w_mm           = int(_entry["width_mm"])
            else:
                _w_mm = width_mm
            bc_perim_mm_calc, bc_perim_exact_calc = _sw_perimeter(
                sw_bc_name, bc_H_mm_fig, _w_mm,
            )
            _bc_perim_m  = bc_perim_mm_calc / 1000
            _bc_Atd_m2   = bc_Atd_cm2_calc / 10_000
            # Equivalent-square: width = perim/4 → axial_pile perimeter = 4×(perim/4) = perim (chính xác)
            pile_width_eff = _bc_perim_m / 4
            pile_shape_eff = "square"
            # Q_tip từ axial_pile dùng tip_area=(perim/4)²; Atd thực tế = _bc_Atd_m2
            tip_correction = _bc_Atd_m2 / (pile_width_eff ** 2)

            sc1, sc2 = st.columns(2)
            sc1.metric(
                "Chu vi tính toán",
                f"{bc_perim_mm_calc:.0f} mm",
                "chinh xac §11.8" if bc_perim_exact_calc else "gan dung 2(H+W)",
                help="Dùng tính ma sát bên: Qs = perimeter × f_s × L",
            )
            sc2.metric(
                "Atd tính toán",
                f"{bc_Atd_cm2_calc:.0f} cm²",
                help="Dùng tính sức kháng mũi: Qp = q_b × Atd",
            )
            if not bc_perim_exact_calc:
                st.caption(
                    "Chu vi gần đúng = 2(H+W). "
                    "Giá trị chính xác: SW-600A/B, SW-740, SW-840 (§11.8)."
                )
        else:
            pile_width_eff = st.number_input(
                "Kích thước cọc (m)  [cạnh / đường kính]",
                min_value=0.1, max_value=2.0,
                value=round(H_mm / 1000, 2),
                step=0.05, key="bc_pile_width",
                help=f"Mặc định = H của {sw_name} = {H_mm} mm",
            )
            pile_shape_eff = pile_shape

        pile_len = st.number_input(
            "Chiều dài cọc (m)", min_value=1.0, max_value=80.0,
            value=float(geo["pile_length"]),  # mặc định = L_m từ GeoData
            step=0.5, key="bc_pile_len",
        )
        gwt_depth = st.number_input(
            "Độ sâu mực nước ngầm (m)", min_value=0.0, max_value=50.0,
            value=max(0.0, round(geo["soil_level_front"] - geo["water_level"], 2)),
            step=0.5, key="bc_gwt",
        )
        method = st.selectbox(
            "Phương pháp tính", list(_METHODS.keys()),
            format_func=lambda k: _METHODS[k], key="bc_method",
        )
        fos = st.number_input(
            "Hệ số an toàn Fs", min_value=1.0, max_value=5.0,
            value=2.5, step=0.1, key="bc_fos",
        )
        Q_target = st.number_input(
            "Tải trọng thiết kế Q_tk (kN)", min_value=0.0, value=500.0,
            step=50.0, key="bc_q_target",
            help="Vẽ đường mục tiêu lên biểu đồ Q vs depth",
        )

        # Tự trọng cọc
        W_pile_kN = bc_w_kNm_calc * float(pile_len)
        st.info(
            f"**Tự trọng cọc** ({sw_bc_name}, L={pile_len:.1f}m): "
            f"**{W_pile_kN:.1f} kN**"
        )

        st.markdown("#### Phạm vi chiều sâu")
        d_min  = st.number_input("L_min (m)",  min_value=1.0, value=5.0,
                                  step=1.0, key="bc_dmin")
        d_max  = st.number_input("L_max (m)",  min_value=5.0, value=float(pile_len),
                                  step=1.0, key="bc_dmax")
        d_step = st.number_input("Bước (m)",   min_value=0.5, value=1.0,
                                  step=0.5, key="bc_dstep")

    # ── Cột phải: hình minh họa (luôn hiển thị) ──────────────────────────────
    with col_res:
        st.markdown("#### Minh họa mặt cắt cọc")
        st.caption("Lấy từ tab Geo Data — địa tầng + MNN + cao độ đỉnh/mũi cọc")
        fig_ill = _draw_bc_illustration(
            geo, disp_layers, float(pile_len), bc_H_mm_fig, sw_bc_name,
        )
        st.pyplot(fig_ill, use_container_width=True)
        plt.close(fig_ill)

        with st.expander("Mặt cắt ngang cọc SW (từ Sheet Pile Section)", expanded=False):
            fig_sec = _draw_sw_cross_section(
                sw_name, H_mm, t_mm, width_mm,
                n_strands, phi_s_mm, Atd_cm2, perim_mm, perim_exact,
            )
            st.pyplot(fig_sec, use_container_width=True)
            plt.close(fig_sec)
            # EI / EA1 reference
            grade_key = st.session_state.get("concrete_grade", "f'c = 70 MPa")
            Ec = _CONCRETE_EC.get(grade_key, 43_628_130)
            sp = width_mm / 1000
            EA1 = Ec * Atd_m2 / sp
            EI  = Ec * (Itd_cm4 / 1e8) / sp
            Mcr_kNm = Mcr_Tm * 9.81
            st.markdown(f"""
| Thông số PLAXIS | Giá trị |
|----------------|---------|
| Grade bê tông | {grade_key} |
| EA1 | {EA1:,.0f} kN/m |
| EI  | {EI:,.0f} kN·m²/m |
| Mcr | ≥ {Mcr_kNm:.0f} kN·m |
| spacing | {sp:.3f} m |
""")
            st.caption("Thay đổi Grade bê tông tại tab Sheet Pile Section.")

    # ── Bảng lớp đất ─────────────────────────────────────────────────────────
    st.markdown("#### Lớp đất (nhập từ trên xuống theo chiều sâu)")
    with st.expander("Hướng dẫn nhập lớp đất", expanded=False):
        st.markdown("""
- **Soil Type**: `cohesionless` = cát/bụi; `cohesive` = sét
- **Phi [°]**: góc ma sát — nhập 0 cho sét
- **Cohesion [kN/m²]**: lực dính Su — nhập 0 cho cát
- **Depth Bottom**: chiều sâu đáy lớp tính từ mặt đất (m, dương xuống dưới)
        """)

    if "bc_soil_df" not in st.session_state:
        st.session_state["bc_soil_df"] = _DEFAULT_SOIL_LAYERS.copy()

    bc_soil_df = st.data_editor(
        st.session_state["bc_soil_df"],
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Depth Bottom [m]":    st.column_config.NumberColumn(min_value=0.1, step=0.5, format="%.1f"),
            "Soil Type":           st.column_config.SelectboxColumn(options=["cohesionless", "cohesive"]),
            "Unit Weight [kN/m³]": st.column_config.NumberColumn(min_value=10.0, max_value=25.0, format="%.1f"),
            "Phi [°]":             st.column_config.NumberColumn(min_value=0.0, max_value=45.0, format="%.1f"),
            "Cohesion [kN/m²]":   st.column_config.NumberColumn(min_value=0.0, format="%.1f"),
            "Description":         st.column_config.TextColumn(),
        },
        key="bc_soil_editor",
    )
    st.session_state["bc_soil_df"] = bc_soil_df

    # ── Nút tính toán ─────────────────────────────────────────────────────────
    calc = st.button("Calculate — Bearing Capacity", type="primary",
                     key="bc_calc_btn")

    if calc:
        df = bc_soil_df.dropna(subset=["Depth Bottom [m]", "Unit Weight [kN/m³]"])
        if df.empty:
            st.error("Nhập ít nhất 1 lớp đất.")
            st.stop()

        df = df.sort_values("Depth Bottom [m]").reset_index(drop=True)
        depth_tops   = [0.0] + df["Depth Bottom [m]"].tolist()[:-1]
        thicknesses  = [
            row["Depth Bottom [m]"] - depth_tops[i]
            for i, row in df.iterrows()
        ]

        with st.spinner("Đang tính toán..."):
            try:
                axial_layers = []
                for i, row in df.iterrows():
                    axial_layers.append(AxialSoilLayer(
                        thickness=max(0.1, thicknesses[i]),
                        soil_type=str(row["Soil Type"]),
                        unit_weight=float(row["Unit Weight [kN/m³]"]),
                        friction_angle=float(row["Phi [°]"]),
                        cohesion=float(row["Cohesion [kN/m²]"]),
                        description=str(row.get("Description", "")),
                    ))

                sp_obj = AxialSoilProfile(layers=axial_layers, gwt_depth=gwt_depth)
                pile   = make_concrete_pile(width=pile_width_eff, shape=pile_shape_eff)
                ana    = AxialPileAnalysis(pile=pile, soil=sp_obj, pile_length=pile_len,
                                           method=method, factor_of_safety=fos)
                result = ana.compute()

                # Hiệu chỉnh Q_tip theo Atd thực tế (chỉ khi dùng sw_pile mode)
                # axial_pile tính tip_area = (perim/4)²; Atd thực tế = bc_Atd_cm2_calc/10000
                Q_tip_c   = result.Q_tip * tip_correction
                Q_ult_c   = result.Q_skin + Q_tip_c
                Q_allow_c = Q_ult_c / fos

                n_pts_cvd = max(5, round((d_max - d_min) / d_step) + 1)
                cvd_raw   = ana.capacity_vs_depth(
                    depth_min=float(d_min),
                    depth_max=float(d_max),
                    n_points=n_pts_cvd,
                )
                if isinstance(cvd_raw, list):
                    cvd = pd.DataFrame(cvd_raw)
                    if "Q_allowable_kN" not in cvd.columns:
                        cvd["Q_allowable_kN"] = cvd["Q_ultimate_kN"] / fos
                elif isinstance(cvd_raw, pd.DataFrame):
                    cvd = cvd_raw
                    if "Q_allowable_kN" not in cvd.columns:
                        cvd["Q_allowable_kN"] = cvd["Q_ultimate_kN"] / fos
                else:
                    rows = []
                    for d in [d_min + i * d_step for i in range(n_pts_cvd)]:
                        _a = AxialPileAnalysis(pile=pile, soil=sp_obj, pile_length=d,
                                               method=method, factor_of_safety=fos)
                        _r = _a.compute()
                        rows.append({
                            "depth_m":          d,
                            "Q_ultimate_kN":    _r.Q_ultimate,
                            "Q_skin_kN":        _r.Q_skin,
                            "Q_tip_kN":         _r.Q_tip,
                            "Q_allowable_kN":   _r.Q_allowable,
                        })
                    cvd = pd.DataFrame(rows)

                # Áp dụng hiệu chỉnh tip_correction vào CVD (cho biểu đồ Q vs depth)
                if tip_correction != 1.0 and not cvd.empty:
                    if "Q_skin_kN" in cvd.columns:
                        q_tip_raw = cvd["Q_ultimate_kN"] - cvd["Q_skin_kN"]
                        cvd = cvd.copy()
                        cvd["Q_ultimate_kN"]  = cvd["Q_skin_kN"] + q_tip_raw * tip_correction
                    elif "Q_tip_kN" in cvd.columns:
                        cvd = cvd.copy()
                        cvd["Q_tip_kN"]       *= tip_correction
                        cvd["Q_ultimate_kN"]   = cvd.get("Q_skin_kN", 0) + cvd["Q_tip_kN"]
                    cvd["Q_allowable_kN"] = cvd["Q_ultimate_kN"] / fos

                st.session_state["bc_result"]      = result
                st.session_state["bc_cvd"]         = cvd
                st.session_state["bc_Q_tip_c"]     = Q_tip_c
                st.session_state["bc_Q_ult_c"]     = Q_ult_c
                st.session_state["bc_Q_allow_c"]   = Q_allow_c
                st.session_state["bc_tip_corr"]    = tip_correction
                st.session_state["bc_calc_perim"]  = bc_perim_mm_calc
                st.session_state["bc_calc_Atd"]    = bc_Atd_cm2_calc
                st.session_state["bc_calc_w_kNm"]  = bc_w_kNm_calc
                st.session_state["bc_pile_name"]   = (
                    f"{sw_bc_name}  [Chu vi={bc_perim_mm_calc:.0f}mm, "
                    f"Atd={bc_Atd_cm2_calc:.0f}cm², L={pile_len:.1f}m]"
                    if pile_shape == "sw_pile" else
                    f"{pile_shape_eff} {pile_width_eff*1000:.0f}mm  |  L={pile_len:.1f}m"
                )

                # Tính song song tất cả 4 phương pháp
                _all_m: dict = {}
                for _mk in ["nordlund", "tomlinson", "beta", "auto"]:
                    try:
                        _ana_m = AxialPileAnalysis(
                            pile=pile, soil=sp_obj,
                            pile_length=pile_len,
                            method=_mk, factor_of_safety=fos,
                        )
                        _res_m = _ana_m.compute()
                        _Qt_m  = _res_m.Q_tip * tip_correction
                        _Qu_m  = _res_m.Q_skin + _Qt_m
                        _Qa_m  = _Qu_m / fos
                        try:
                            _cvd_raw_m = _ana_m.capacity_vs_depth(
                                depth_min=float(d_min),
                                depth_max=float(d_max),
                                n_points=n_pts_cvd,
                            )
                            if isinstance(_cvd_raw_m, list):
                                _cvd_m = pd.DataFrame(_cvd_raw_m)
                            elif isinstance(_cvd_raw_m, pd.DataFrame):
                                _cvd_m = _cvd_raw_m.copy()
                            else:
                                _cvd_m = pd.DataFrame()
                            if not _cvd_m.empty:
                                if "Q_allowable_kN" not in _cvd_m.columns:
                                    _cvd_m["Q_allowable_kN"] = (
                                        _cvd_m["Q_ultimate_kN"] / fos
                                    )
                                if tip_correction != 1.0 and "Q_skin_kN" in _cvd_m.columns:
                                    _qt_raw = _cvd_m["Q_ultimate_kN"] - _cvd_m["Q_skin_kN"]
                                    _cvd_m["Q_ultimate_kN"]  = (
                                        _cvd_m["Q_skin_kN"] + _qt_raw * tip_correction
                                    )
                                    _cvd_m["Q_allowable_kN"] = _cvd_m["Q_ultimate_kN"] / fos
                        except Exception:
                            _cvd_m = pd.DataFrame()
                        _all_m[_mk] = {
                            "Q_skin":  _res_m.Q_skin,
                            "Q_tip":   _Qt_m,
                            "Q_ult":   _Qu_m,
                            "Q_allow": _Qa_m,
                            "cvd":     _cvd_m,
                        }
                    except Exception as _em:
                        _all_m[_mk] = {"error": str(_em)}
                st.session_state["bc_all_methods"] = _all_m

                st.success("Tính toán hoàn tất")

            except Exception as exc:
                st.error(f"Lỗi: {exc}")
                st.stop()

    # ── Kết quả ───────────────────────────────────────────────────────────────
    if st.session_state.get("bc_result") is not None:
        result = st.session_state["bc_result"]
        cvd    = st.session_state["bc_cvd"]
        pname  = st.session_state.get("bc_pile_name", "")

        st.divider()
        st.markdown("#### Results")

        # Đọc giá trị đã hiệu chỉnh (lưu lúc tính toán)
        Q_tip_c   = st.session_state.get("bc_Q_tip_c",   result.Q_tip)
        Q_ult_c   = st.session_state.get("bc_Q_ult_c",   result.Q_ultimate)
        Q_allow_c = st.session_state.get("bc_Q_allow_c", result.Q_allowable)
        tip_corr  = st.session_state.get("bc_tip_corr",  1.0)
        c_perim   = st.session_state.get("bc_calc_perim", perim_mm)
        c_Atd     = st.session_state.get("bc_calc_Atd",   Atd_cm2)
        c_w_kNm   = st.session_state.get("bc_calc_w_kNm", w_kNm)

        if tip_corr != 1.0:
            st.info(
                f"Kết quả đã hiệu chỉnh theo Atd thực tế: "
                f"Atd = {c_Atd:.0f} cm²  |  Chu vi = {c_perim:.0f} mm  "
                f"(hệ số hiệu chỉnh Q_tip = {tip_corr:.3f})"
            )

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Q_ult",  f"{Q_ult_c:.0f} kN")
        k2.metric("Q_skin", f"{result.Q_skin:.0f} kN",
                  f"{result.Q_skin / Q_ult_c * 100:.0f}%")
        k3.metric("Q_tip",  f"{Q_tip_c:.0f} kN",
                  f"{Q_tip_c / Q_ult_c * 100:.0f}%")
        ok_fos = Q_allow_c >= Q_target
        k4.metric(f"Q_allow (Fs={result.factor_of_safety:.1f})",
                  f"{Q_allow_c:.0f} kN",
                  "Dat" if ok_fos else "Khong dat",
                  delta_color="normal" if ok_fos else "inverse")
        W_pile_res = c_w_kNm * float(pile_len)
        k5.metric("W tự trọng", f"{W_pile_res:.0f} kN",
                  help=f"Tự trọng {sw_bc_name} tại L={pile_len:.1f}m")

        # ── Hàng 1: Q vs Depth  |  Load Transfer ────────────────────────────────
        st.divider()
        st.markdown("##### Biểu đồ sức chịu tải")
        ch1, ch2 = st.columns(2, gap="medium")
        with ch1:
            st.markdown("**Q vs Depth**")
            fig_cvd = _plot_capacity_vs_depth(cvd, Q_target, pname)
            st.pyplot(fig_cvd, use_container_width=True)
            plt.close(fig_cvd)
        with ch2:
            st.markdown("**Phân bố tải (Load Transfer)**")
            fig_lt = _plot_load_transfer(result, pname, float(pile_len))
            st.pyplot(fig_lt, use_container_width=True)
            plt.close(fig_lt)

        # ── Hàng 2: Bảng lớp đất ─────────────────────────────────────────────
        st.divider()
        st.markdown("##### Bảng phân bố ma sát (Layer Data)")
        bd_df = pd.DataFrame(result.layer_breakdown)
        st.dataframe(bd_df, use_container_width=True, hide_index=True)
        st.caption(result.summary())

        # ── Hàng 3: NT2 ──────────────────────────────────────────────────────
        st.divider()
        st.markdown("##### NT2 — Kiểm tra sức chịu tải theo đất nền (TCVN 11823-10)")
        phi_nt2   = 0.35
        Rs_nom    = result.Q_skin
        Rp_nom    = st.session_state.get("bc_Q_tip_c", result.Q_tip)
        Rr        = phi_nt2 * (Rs_nom + Rp_nom)
        nt2_w_kNm = st.session_state.get("bc_calc_w_kNm", w_kNm)
        nt2_perim = st.session_state.get("bc_calc_perim",  perim_mm)
        nt2_Atd   = st.session_state.get("bc_calc_Atd",    Atd_cm2)
        W_kN      = nt2_w_kNm * float(pile_len)
        ok_nt2    = Rr >= W_kN

        n1, n2, n3, n4 = st.columns(4)
        n1.metric("Rs (FHWA skin)",       f"{Rs_nom:.0f} kN",
                  help="Q_skin từ FHWA — perimeter × f_s × L")
        n2.metric("Rp (hiệu chỉnh Atd)", f"{Rp_nom:.0f} kN",
                  help="Q_tip đã nhân hệ số hiệu chỉnh Atd thực tế")
        n3.metric("φ·(Rs+Rp)",  f"{Rr:.0f} kN",  f"φ = {phi_nt2}")
        n4.metric("W tự trọng", f"{W_kN:.0f} kN",
                  "Dat" if ok_nt2 else "Khong dat",
                  delta_color="normal" if ok_nt2 else "inverse")

        st.markdown(f"""
**Công thức:** RR = φ(Rs + Rp) ≥ W  (TCVN 11823-10)
RR = {phi_nt2} × ({Rs_nom:.0f} + {Rp_nom:.0f}) = **{Rr:.0f} kN**
W  = {nt2_w_kNm:.2f} × {pile_len:.1f} = **{W_kN:.0f} kN**
→ **{"Dat" if ok_nt2 else "Khong dat"}** (RR/W = {Rr/W_kN:.2f})
""")
        st.caption(
            f"Chu vi dùng tính = {nt2_perim:.0f} mm  |  "
            f"Atd dùng tính = {nt2_Atd:.0f} cm²  |  "
            "Q_tip đã hiệu chỉnh theo Atd thực tế của cọc SW."
        )

        # ── Hàng 4: Dự báo độ lún cọc đơn ───────────────────────────────────
        st.divider()
        st.markdown("##### Dự báo độ lún cọc đơn (Das/Vesic 1977)")
        sc_a, sc_b, sc_c, sc_d = st.columns(4)
        Q_w_set = sc_a.number_input(
            "Tải trọng làm việc Q_w (kN)",
            min_value=1.0, value=float(Q_target),
            step=50.0, key="bc_Qw_settle",
            help="Thường = Q_target hoặc Q_allow",
        )
        Cp_set = sc_b.selectbox(
            "Hệ số Cp (loại đất mũi cọc)",
            options=[0.02, 0.03, 0.04, 0.06],
            format_func=lambda v: {0.02:"0.02 — Cát chặt (driven)",
                                   0.03:"0.03 — Bụi (driven)",
                                   0.04:"0.04 — Sét trung (driven)",
                                   0.06:"0.06 — Sét mềm (driven)"}[v],
            index=0, key="bc_Cp_set",
        )
        s_limit = sc_c.number_input(
            "Độ lún giới hạn (mm)",
            min_value=1.0, max_value=200.0,
            value=25.0, step=5.0, key="bc_s_limit",
            help="TCVN 9362:2012 mục 4.6: ≤ 25 mm cho nhà dân dụng thông thường; "
                 "TCVN 11823 cầu: ≤ 38 mm; công trình đặc thù theo yêu cầu thiết kế",
        )
        grade_k  = st.session_state.get("concrete_grade", "f'c = 70 MPa")
        Ec_set   = _CONCRETE_EC.get(grade_k, 43_628_130)
        sc_d.metric("Ec cọc", f"{Ec_set/1e6:.1f} GPa",
                    help=f"Từ tab Sheet Pile Section: {grade_k}")

        _settle = _compute_settlement(
            Q_w       = float(Q_w_set),
            Q_skin    = result.Q_skin,
            Q_tip     = Q_tip_c,
            L         = float(pile_len),
            Atd_m2    = (c_Atd / 10_000),
            E_p       = float(Ec_set),
            D         = bc_H_mm_fig / 1000,
            perimeter_m = c_perim / 1000,
            Cp        = float(Cp_set),
            xi        = 0.5,
        )
        sa, sb, sc, sd = st.columns(4)
        sa.metric("sₑ  nén trục",      f"{_settle['se_mm']:.2f} mm")
        sb.metric("s_sp  lún mũi",     f"{_settle['ssp_mm']:.2f} mm")
        sc.metric("s_ss  lún ma sát",  f"{_settle['sss_mm']:.2f} mm")
        _ok_s = _settle["total_mm"] < float(s_limit)
        sd.metric("Tổng độ lún", f"{_settle['total_mm']:.2f} mm",
                  f"< {s_limit:.0f} mm" if _ok_s else f"> {s_limit:.0f} mm",
                  delta_color="normal" if _ok_s else "inverse")

        fig_set = _plot_settlement(_settle, pname, float(Q_w_set),
                                   s_limit_mm=float(s_limit))
        st.pyplot(fig_set, use_container_width=True)
        plt.close(fig_set)
        with st.expander("Thông số chi tiết (Das/Vesic 1977)", expanded=False):
            st.markdown(f"""
| Thông số | Giá trị |
|----------|---------|
| Q_wp (tải đến mũi) | {_settle['Q_wp_kN']:.1f} kN |
| Q_ws (tải phần ma sát) | {_settle['Q_ws_kN']:.1f} kN |
| qwp (ứng suất mũi làm việc) | {_settle['qwp_kPa']:.1f} kN/m² |
| Cp | {_settle['Cp']} |
| Cs | {_settle['Cs']:.4f} |
| ξ (phân bố ma sát) | {_settle['xi']} |
**Công thức:**
- sₑ = (Q_wp + ξ·Q_ws) × L / (Ap × Ep)
- s_sp = Cp × (qwp/pa) × D  ;  pa = 100 kN/m²
- s_ss = Cs × (q̄_ws / qwp) × D  ;  Cs = Cp(0.93 + 0.16√(L/D))
""")

        # ── Hàng 5: So sánh theo phương pháp tính ────────────────────────────
        if st.session_state.get("bc_all_methods"):
            _all_m = st.session_state["bc_all_methods"]
            st.divider()
            st.markdown("##### So sánh theo phương pháp tính")
            st.caption(
                "Cùng cọc, cùng địa chất — tính song song Nordlund, Tomlinson, Beta, Auto."
            )

            # Bảng tổng hợp
            _m_rows = []
            for _mk, _mr in _all_m.items():
                if "error" in _mr:
                    _m_rows.append({
                        "Phương pháp":   _METHOD_LABELS.get(_mk, _mk),
                        "Q_skin (kN)":   "—",
                        "Q_tip (kN)":    "—",
                        "Q_ult (kN)":    "—",
                        "Q_allow (kN)":  "—",
                        "Dat/KDat":      f"Loi: {_mr['error'][:60]}",
                    })
                else:
                    _ok_m = _mr["Q_allow"] >= Q_target
                    _m_rows.append({
                        "Phương pháp":   _METHOD_LABELS.get(_mk, _mk),
                        "Q_skin (kN)":   f"{_mr['Q_skin']:.0f}",
                        "Q_tip (kN)":    f"{_mr['Q_tip']:.0f}",
                        "Q_ult (kN)":    f"{_mr['Q_ult']:.0f}",
                        "Q_allow (kN)":  f"{_mr['Q_allow']:.0f}",
                        "Dat/KDat":      "Dat" if _ok_m else "Khong Dat",
                    })
            st.dataframe(
                pd.DataFrame(_m_rows),
                use_container_width=True, hide_index=True,
            )

            # Biểu đồ CVD tổng hợp 4 phương pháp
            _valid_m = {
                k: v for k, v in _all_m.items()
                if "error" not in v
                and not v.get("cvd", pd.DataFrame()).empty
            }
            if _valid_m:
                _fig_am = _plot_methods_comparison_cvd(_valid_m, Q_target, pname)
                st.pyplot(_fig_am, use_container_width=True)
                plt.close(_fig_am)

            # Biểu đồ bar Q_skin+Q_tip và Q_allow
            _m_bar_items = [(k, v) for k, v in _all_m.items() if "error" not in v]
            if _m_bar_items:
                _fig_mb = _plot_methods_bar(_m_bar_items, Q_target, pname, float(pile_len))
                st.pyplot(_fig_mb, use_container_width=True)
                plt.close(_fig_mb)

    # ── So sánh các phương án cọc SW ─────────────────────────────────────────
    st.divider()
    st.markdown("#### So sánh các phương án cọc SW")
    st.caption(
        "Tính toán song song nhiều loại cọc SW trên cùng bộ số liệu địa chất "
        "và hiển thị biểu đồ Q vs Depth riêng từng phương án + biểu đồ tổng hợp so sánh."
    )

    _all_names  = _SW_PILE_NAMES if _SW_PILE_NAMES else ["SW-840"]
    _default_sel = [sw_name] if sw_name in _all_names else [_all_names[0]]
    _sel_piles   = st.multiselect(
        "Chọn loại cọc SW để so sánh",
        options=_all_names,
        default=_default_sel,
        key="bc_compare_piles",
    )

    _comp_len = st.number_input(
        "Chiều dài cọc so sánh (m)",
        min_value=1.0, max_value=80.0,
        value=float(pile_len) if "bc_result" in st.session_state else 20.0,
        step=0.5, key="bc_comp_len",
        help="Chiều dài cố định dùng cho biểu đồ bar so sánh",
    )

    if st.button("Tính toán so sánh", key="bc_compare_btn",
                 disabled=(len(_sel_piles) == 0)):
        _cur_soil = st.session_state.get("bc_soil_df", bc_soil_df)
        _comp_results: list[dict] = []
        _errors: list[str] = []
        with st.spinner(f"Đang tính {len(_sel_piles)} phương án..."):
            for _pn in _sel_piles:
                try:
                    _r = _run_pile_calc(
                        pile_name=_pn,
                        soil_df=_cur_soil,
                        gwt_depth=float(gwt_depth),
                        method=str(method),
                        fos=float(fos),
                        pile_len=float(_comp_len),
                        d_min=float(d_min),
                        d_max=float(d_max),
                        d_step=float(d_step),
                    )
                    if _r:
                        _comp_results.append(_r)
                    else:
                        _errors.append(f"{_pn}: không tìm thấy trong catalog")
                except Exception as _ex:
                    _errors.append(f"{_pn}: {_ex}")
        if _errors:
            for _e in _errors:
                st.warning(_e)
        st.session_state["bc_comp_results"] = _comp_results

    if st.session_state.get("bc_comp_results"):
        _comp = st.session_state["bc_comp_results"]
        _pile_len_c = float(_comp_len)

        # Bảng tổng hợp
        _tbl_rows = []
        for _r in _comp:
            _W_c = _r["w_kNm"] * _pile_len_c
            _tbl_rows.append({
                "Loại cọc":         _r["pile_name"],
                "H (mm)":           _r["H_mm"],
                "Chu vi (mm)":      f"{_r['perim_mm']:.0f}",
                "Atd (cm²)":        f"{_r['Atd_cm2']:.0f}",
                "Q_skin (kN)":      f"{_r['Q_skin']:.0f}",
                "Q_tip (kN)":       f"{_r['Q_tip']:.0f}",
                "Q_ult (kN)":       f"{_r['Q_ult']:.0f}",
                "Q_allow (kN)":     f"{_r['Q_allow']:.0f}",
                "W cọc (kN)":       f"{_W_c:.0f}",
                "Dat/KDat":         "Dat" if _r["Q_allow"] >= Q_target else "Khong Dat",
            })
        st.markdown(f"**Kết quả tại L = {_pile_len_c:.1f} m  |  Fs = {fos:.1f}  |  Q_tk = {Q_target:.0f} kN**")
        st.dataframe(pd.DataFrame(_tbl_rows), use_container_width=True, hide_index=True)

        # Biểu đồ từng phương án riêng lẻ
        st.markdown("**Biểu đồ Q vs Depth từng phương án**")
        _n_res = len(_comp)
        _cols_per_row = min(3, _n_res)
        _rows_needed  = (_n_res + _cols_per_row - 1) // _cols_per_row
        _idx = 0
        for _ in range(_rows_needed):
            _c_list = st.columns(_cols_per_row, gap="small")
            for _col in _c_list:
                if _idx >= _n_res:
                    break
                _r  = _comp[_idx]
                _pn = _r["pile_name"]
                with _col:
                    st.caption(_pn)
                    if not _r["cvd"].empty:
                        _fig_i = _plot_capacity_vs_depth(_r["cvd"], Q_target, _pn)
                        st.pyplot(_fig_i, use_container_width=True)
                        plt.close(_fig_i)
                    else:
                        st.info(f"{_pn}: Không có CVD data")
                _idx += 1

        # Biểu đồ tổng hợp
        st.markdown("**Biểu đồ tổng hợp so sánh**")
        _valid = [r for r in _comp if not r["cvd"].empty]
        if len(_valid) >= 2:
            _fig_cmp_cvd = _plot_comparison_cvd(_valid, Q_target)
            st.pyplot(_fig_cmp_cvd, use_container_width=True)
            plt.close(_fig_cmp_cvd)

        _fig_cmp_bar = _plot_comparison_bars(_comp, _pile_len_c, Q_target)
        st.pyplot(_fig_cmp_bar, use_container_width=True)
        plt.close(_fig_cmp_bar)

    st.divider()
    with st.expander("Theory — 29-bearing-capacity-axial-pile", expanded=False):
        _proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(_proj_dir, "29-bearing-capacity-axial-pile.md"),
                      "r", encoding="utf-8") as f:
                st.markdown(f.read())
        except FileNotFoundError:
            st.info("29-bearing-capacity-axial-pile not found")
