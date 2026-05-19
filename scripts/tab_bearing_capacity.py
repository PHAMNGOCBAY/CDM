"""
Helper module cho tab Bearing Capacity trong app_coc_tai_ngang.py.
Dùng geotech-staff-engineer bearing_capacity (Meyerhof / Vesic, FHWA GEC-6).

Import:
    from tab_bearing_capacity import run_bearing_capacity, plot_bearing_capacity
"""
from __future__ import annotations
from typing import Optional
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

try:
    from bearing_capacity import (
        BearingCapacityAnalysis, Footing,
        BearingSoilProfile, SoilLayer,
    )
    _HAS_BC = True
except ImportError:
    _HAS_BC = False


def available() -> bool:
    return _HAS_BC


def run_bearing_capacity(
    shape: str,
    B: float,
    L: float,
    D: float,
    gamma_soil: float,
    phi_deg: float,
    cohesion: float,
    gwt_depth: Optional[float],
    vertical_load: float = 0.0,
    load_inclination_deg: float = 0.0,
    fs: float = 3.0,
) -> dict:
    """Tinh suc chiu tai mong nong theo Meyerhof/Vesic.

    Parameters
    ----------
    shape : 'strip' | 'square' | 'rectangular' | 'circular'
    B     : chieu rong [m]
    L     : chieu dai [m] — chi dung khi rectangular
    D     : chieu sau dat mong [m]
    gamma_soil : dung trong dat [kN/m3]
    phi_deg    : goc ma sat trong [deg]
    cohesion   : luc dinh [kPa]
    gwt_depth  : chieu sau MNN tu mat dat [m]; None = khong co MNN
    vertical_load : tai trong dung [kN] — chi de tinh q_applied hien thi
    load_inclination_deg : goc nghieng tai [deg]
    fs    : he so an toan

    Returns
    -------
    dict chua ket qua + thong so dau vao
    """
    if not _HAS_BC:
        return {"error": "Thu vien bearing_capacity chua duoc cai dat."}

    footing = Footing(
        width=B,
        length=L if shape == "rectangular" else None,
        depth=D,
        shape=shape,
    )
    layer1 = SoilLayer(
        cohesion=cohesion,
        friction_angle=phi_deg,
        unit_weight=gamma_soil,
    )
    soil = BearingSoilProfile(layer1=layer1, gwt_depth=gwt_depth)
    analysis = BearingCapacityAnalysis(
        footing=footing,
        soil=soil,
        vertical_load=vertical_load,
        load_inclination=load_inclination_deg,
        factor_of_safety=fs,
        ngamma_method="vesic",
        factor_method="vesic",
    )
    result = analysis.compute()

    area = B * (L if shape == "rectangular" else B) if shape not in ("strip", "circular") else B
    q_applied = vertical_load / area if area > 0 and vertical_load > 0 else 0.0

    return {
        "shape": shape,
        "B": B, "L": L, "D": D,
        "gamma": gamma_soil, "phi": phi_deg, "c": cohesion,
        "gwt_depth": gwt_depth,
        "fs_input": fs,
        "q_ultimate":    round(result.q_ultimate,   2),
        "q_allowable":   round(result.q_allowable,  2),
        "q_net":         round(result.q_net,         2),
        "q_applied":     round(q_applied,            2),
        "factor_of_safety": round(result.factor_of_safety, 2),
        "Nc": round(result.Nc, 3),
        "Nq": round(result.Nq, 3),
        "Ngamma": round(result.Ngamma, 3),
        "term_cohesion":     round(result.term_cohesion,    2),
        "term_overburden":   round(result.term_overburden,  2),
        "term_selfweight":   round(result.term_selfweight,  2),
        "check_pass": q_applied <= result.q_allowable if q_applied > 0 else None,
    }


def plot_bearing_capacity(r: dict) -> plt.Figure:
    """Ve bieu do 2 panel: (1) phan ra 3 thanh phan q, (2) bang thong so."""
    fig, (ax_bar, ax_tab) = plt.subplots(1, 2, figsize=(10, 4.5),
                                          gridspec_kw={"width_ratios": [1.2, 1]})

    # ── Panel 1: stacked bar ─────────────────────────────────────────────────
    q_c = r.get("term_cohesion",   0.0)
    q_q = r.get("term_overburden", 0.0)
    q_g = r.get("term_selfweight", 0.0)
    q_u = r.get("q_ultimate",      0.0)

    colors = ["#e74c3c", "#3498db", "#2ecc71"]
    labels = [f"Cohesion  {q_c:.1f} kPa",
              f"Overburden  {q_q:.1f} kPa",
              f"Self-weight  {q_g:.1f} kPa"]
    bottoms = [0, q_c, q_c + q_q]
    vals    = [q_c, q_q, q_g]

    for val, bot, col, lbl in zip(vals, bottoms, colors, labels):
        ax_bar.bar(["q_ult"], val, bottom=bot, color=col, alpha=0.85,
                   label=lbl, width=0.5)

    ax_bar.axhline(r.get("q_allowable", 0), color="navy", lw=1.5, ls="--",
                   label=f"q_allow = {r.get('q_allowable',0):.1f} kPa  (FS={r.get('fs_input',3)})")
    if r.get("q_applied", 0) > 0:
        ax_bar.axhline(r["q_applied"], color="darkorange", lw=1.5, ls=":",
                       label=f"q_applied = {r['q_applied']:.1f} kPa")

    ax_bar.set_ylabel("Bearing Pressure [kPa]")
    ax_bar.set_title(f"q_ult = {q_u:.1f} kPa\n"
                     f"Footing {r.get('shape','?').capitalize()}  "
                     f"B={r.get('B')}m  D={r.get('D')}m")
    ax_bar.legend(fontsize=8, loc="upper right")
    ax_bar.set_facecolor("#f8f9fa")

    # ── Panel 2: parameter table ─────────────────────────────────────────────
    ax_tab.axis("off")
    rows = [
        ["Parameter", "Value"],
        ["B [m]",     f"{r.get('B')}"],
        ["D [m]",     f"{r.get('D')}"],
        ["phi [deg]", f"{r.get('phi')}"],
        ["c [kPa]",   f"{r.get('c')}"],
        ["gamma [kN/m³]", f"{r.get('gamma')}"],
        ["Nc", f"{r.get('Nc')}"],
        ["Nq", f"{r.get('Nq')}"],
        ["Ng", f"{r.get('Ngamma')}"],
        ["q_ult [kPa]",   f"{r.get('q_ultimate')}"],
        ["q_allow [kPa]", f"{r.get('q_allowable')}"],
        ["q_net [kPa]",   f"{r.get('q_net')}"],
    ]
    tbl = ax_tab.table(cellText=rows[1:], colLabels=rows[0],
                       loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1.2, 1.4)
    for (row_i, col_j), cell in tbl.get_celld().items():
        if row_i == 0:
            cell.set_facecolor("#2c3e50")
            cell.set_text_props(color="white", fontweight="bold")
        elif row_i % 2 == 0:
            cell.set_facecolor("#ecf0f1")

    ax_tab.set_title("Ket qua chi tiet", fontsize=9, fontweight="bold")

    plt.tight_layout()
    return fig
