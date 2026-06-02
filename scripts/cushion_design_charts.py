"""
cushion_design_charts.py — Biểu đồ phân tích thiết kế lớp đệm cát-XM.

Dùng matplotlib (cho cả UI Streamlit lẫn embed Word docx).

Quy tắc:
  - KHÔNG dùng emoji
  - Tiếng Việt có dấu trong tất cả label/title
  - Luôn label giá trị số trên điểm dữ liệu (feedback rule 3)
  - "Đạt" xanh #2E7D32, "Không đạt" đỏ #C62828
"""
from __future__ import annotations
import math
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

from cdm_cushion_params import check_alicc

# ════════ STYLE CONSTANTS ════════
COLOR_OK = "#2E7D32"        # xanh - Đạt
COLOR_FAIL = "#C62828"      # đỏ - Không đạt
COLOR_THRESHOLD = "#F57C00" # cam - ngưỡng
COLOR_CURRENT = "#1565C0"   # xanh dương - hiện tại
COLOR_RECO = "#6A1B9A"      # tím - khuyến nghị
FONT_SZ_TITLE = 13
FONT_SZ_LABEL = 11
FONT_SZ_ANN = 9


def _setup_axes(ax, xlabel: str, ylabel: str, title: str = ""):
    ax.set_xlabel(xlabel, fontsize=FONT_SZ_LABEL)
    ax.set_ylabel(ylabel, fontsize=FONT_SZ_LABEL)
    if title:
        ax.set_title(title, fontsize=FONT_SZ_TITLE, fontweight="bold", pad=10)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


# ════════ CHART 1 — HEATMAP RATIO Hse × q_uckse ════════
def chart_heatmap_ratio(
    Hse_list=(0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70),
    qu_list=(500, 600, 700, 800, 900, 1000, 1100, 1200),
    Hse_current=0.40,
    qu_current=600,
) -> plt.Figure:
    """Heatmap ratio = τ_se/τ_ase với annotation số.
    Đỏ = không đạt (ratio > 1); xanh = đạt.
    """
    Hse_arr = list(Hse_list)
    qu_arr = list(qu_list)
    Z = np.zeros((len(Hse_arr), len(qu_arr)))
    for i, h in enumerate(Hse_arr):
        for j, q in enumerate(qu_arr):
            r = check_alicc(h, q_uckse=float(q))
            Z[i, j] = r["ratio"]

    cmap = LinearSegmentedColormap.from_list("rg", [
        "#1B5E20", "#66BB6A", "#FFF59D", "#EF5350", "#B71C1C",
    ])
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(Z, cmap=cmap, vmin=0.4, vmax=2.0, aspect="auto", origin="lower")

    for i in range(len(Hse_arr)):
        for j in range(len(qu_arr)):
            v = Z[i, j]
            color = "white" if v > 1.5 or v < 0.7 else "black"
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    fontsize=FONT_SZ_ANN, color=color, fontweight="bold")

    ax.set_xticks(range(len(qu_arr)))
    ax.set_xticklabels([f"{q}" for q in qu_arr])
    ax.set_yticks(range(len(Hse_arr)))
    ax.set_yticklabels([f"{h:.2f}" for h in Hse_arr])
    ax.set_xlabel("Cường độ kháng nén $q_{uckse}$ (kPa)", fontsize=FONT_SZ_LABEL)
    ax.set_ylabel("Bề dày đệm $H_{se}$ (m)", fontsize=FONT_SZ_LABEL)
    ax.set_title("Ma trận hệ số ratio = $\\tau_{se}/\\tau_{ase}$"
                 " — xanh: Đạt, đỏ: Không đạt",
                 fontsize=FONT_SZ_TITLE, fontweight="bold", pad=10)

    # Marker hiện tại
    if Hse_current in Hse_arr and qu_current in qu_arr:
        i = Hse_arr.index(Hse_current); j = qu_arr.index(qu_current)
        ax.scatter([j], [i], s=400, marker="o", facecolor="none",
                   edgecolor="#1565C0", linewidth=3, zorder=10,
                   label="Hiện tại")
        ax.legend(loc="upper right", framealpha=0.9, fontsize=10)

    cb = fig.colorbar(im, ax=ax, shrink=0.85)
    cb.set_label("ratio = $\\tau_{se}/\\tau_{ase}$", fontsize=FONT_SZ_LABEL)
    cb.ax.axhline(1.0, color="black", linewidth=2, linestyle="--")
    cb.ax.annotate("ngưỡng 1.0", xy=(1, 1.0), xytext=(2.0, 1.0),
                   fontsize=9, va="center")

    fig.tight_layout()
    return fig


# ════════ CHART 2 — Đường cong tại Hse = 0.40m ════════
def chart_ratio_vs_quckse_fixed_Hse(
    Hse_fixed: float = 0.40,
    qu_range: Tuple[int, int] = (400, 1600),
) -> plt.Figure:
    """Đường ratio vs q_uckse khi Hse cố định."""
    qus = list(range(qu_range[0], qu_range[1] + 1, 25))
    ratios = []
    for q in qus:
        r = check_alicc(Hse_fixed, q_uckse=float(q))
        ratios.append(r["ratio"])

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(qus, ratios, "-", color=COLOR_CURRENT, linewidth=2.5,
            marker="o", markersize=5, markevery=4)

    # Đường ngưỡng 1.0
    ax.axhline(1.0, color=COLOR_THRESHOLD, linewidth=2, linestyle="--",
               label="Ngưỡng đạt (ratio = 1)")

    # Tô vùng đạt/không đạt
    ax.fill_between(qus, 0, 1.0, alpha=0.12, color=COLOR_OK)
    ax.fill_between(qus, 1.0, max(ratios)*1.1, alpha=0.10, color=COLOR_FAIL)

    # Tìm q_uckse_min
    q_min = None
    for q, r in zip(qus, ratios):
        if r <= 1.0:
            q_min = q; break
    if q_min:
        r_min = ratios[qus.index(q_min)]
        ax.scatter([q_min], [r_min], s=200, marker="*",
                   color=COLOR_RECO, zorder=10)
        ax.annotate(f"$q_{{uckse,min}}$ = {q_min} kPa",
                    xy=(q_min, r_min), xytext=(q_min + 80, r_min + 0.2),
                    fontsize=FONT_SZ_LABEL, fontweight="bold", color=COLOR_RECO,
                    arrowprops=dict(arrowstyle="->", color=COLOR_RECO))

    # Annotate điểm hiện tại q=600
    r_600 = ratios[qus.index(600)] if 600 in qus else None
    if r_600:
        ax.scatter([600], [r_600], s=150, marker="o",
                   color=COLOR_CURRENT, zorder=10)
        ax.annotate(f"Hiện tại: q=600\nratio={r_600:.2f}",
                    xy=(600, r_600), xytext=(450, r_600 + 0.3),
                    fontsize=FONT_SZ_LABEL, color=COLOR_CURRENT, fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=COLOR_CURRENT))

    # Annotate giá trị tại các mốc
    for q_mark in [600, 800, 1000, 1200, 1500]:
        if q_mark in qus:
            r_m = ratios[qus.index(q_mark)]
            ax.annotate(f"{r_m:.2f}", xy=(q_mark, r_m),
                        xytext=(0, -16 if r_m < 1.0 else 8),
                        textcoords="offset points",
                        ha="center", fontsize=FONT_SZ_ANN,
                        color="black", fontweight="bold")

    _setup_axes(ax, "Cường độ kháng nén $q_{uckse}$ (kPa)",
                "ratio = $\\tau_{se}/\\tau_{ase}$",
                f"Quan hệ ratio - $q_{{uckse}}$ tại $H_{{se}}$ = {Hse_fixed:.2f} m")
    ax.legend(loc="upper right", fontsize=FONT_SZ_LABEL)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    return fig


# ════════ CHART 3 — Đường cong tại q_uckse cố định ════════
def chart_ratio_vs_Hse_fixed_quckse(
    qu_fixed: int = 600,
    Hse_range: Tuple[float, float] = (0.20, 1.00),
) -> plt.Figure:
    Hses = [round(0.20 + 0.02 * i, 2) for i in range(int((Hse_range[1]-Hse_range[0])/0.02) + 1)]
    ratios = []
    for h in Hses:
        r = check_alicc(h, q_uckse=float(qu_fixed))
        ratios.append(r["ratio"])

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(Hses, ratios, "-", color=COLOR_CURRENT, linewidth=2.5,
            marker="s", markersize=5, markevery=3)
    ax.axhline(1.0, color=COLOR_THRESHOLD, linewidth=2, linestyle="--",
               label="Ngưỡng đạt (ratio = 1)")
    ax.fill_between(Hses, 0, 1.0, alpha=0.12, color=COLOR_OK)
    ax.fill_between(Hses, 1.0, max(ratios)*1.1, alpha=0.10, color=COLOR_FAIL)

    # Hse_min
    h_min = None
    for h, r in zip(Hses, ratios):
        if r <= 1.0:
            h_min = h; break
    if h_min:
        r_min = ratios[Hses.index(h_min)]
        ax.scatter([h_min], [r_min], s=200, marker="*",
                   color=COLOR_RECO, zorder=10)
        ax.annotate(f"$H_{{se,min}}$ = {h_min:.2f} m",
                    xy=(h_min, r_min), xytext=(h_min + 0.10, r_min + 0.2),
                    fontsize=FONT_SZ_LABEL, fontweight="bold", color=COLOR_RECO,
                    arrowprops=dict(arrowstyle="->", color=COLOR_RECO))

    # Hiện tại 0.40
    if 0.40 in Hses:
        r_40 = ratios[Hses.index(0.40)]
        ax.scatter([0.40], [r_40], s=150, marker="o",
                   color=COLOR_CURRENT, zorder=10)
        ax.annotate(f"Hiện tại: $H_{{se}}$=0.40 m\nratio={r_40:.2f}",
                    xy=(0.40, r_40), xytext=(0.20, r_40 + 0.25),
                    fontsize=FONT_SZ_LABEL, color=COLOR_CURRENT, fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=COLOR_CURRENT))

    # Annotate giá trị
    for h_mark in [0.30, 0.40, 0.50, 0.60, 0.70]:
        if h_mark in Hses:
            r_m = ratios[Hses.index(h_mark)]
            ax.annotate(f"{r_m:.2f}", xy=(h_mark, r_m),
                        xytext=(0, -16 if r_m < 1.0 else 8),
                        textcoords="offset points",
                        ha="center", fontsize=FONT_SZ_ANN,
                        color="black", fontweight="bold")

    _setup_axes(ax, "Bề dày đệm $H_{se}$ (m)",
                "ratio = $\\tau_{se}/\\tau_{ase}$",
                f"Quan hệ ratio - $H_{{se}}$ tại $q_{{uckse}}$ = {qu_fixed} kPa")
    ax.legend(loc="upper right", fontsize=FONT_SZ_LABEL)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    return fig


# ════════ CHART 4 — So sánh 3 phương án (bar group) ════════
def chart_compare_options(options: List[Dict]) -> plt.Figure:
    """So sánh 3 phương án bằng grouped bar chart.
    options = [{label, Hse, q_uckse, ratio, cost_delta_pct}, ...]
    """
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    labels = [o["label"] for o in options]
    colors = [COLOR_RECO if i == 0 else COLOR_CURRENT for i in range(len(options))]

    # Subplot 1: ratio
    ax = axes[0]
    ratios = [o["ratio"] for o in options]
    bars = ax.bar(labels, ratios, color=colors, edgecolor="black", linewidth=1.2)
    ax.axhline(1.0, color=COLOR_THRESHOLD, linewidth=2, linestyle="--",
               label="Ngưỡng đạt (1.0)")
    for bar, r in zip(bars, ratios):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"{r:.2f}", ha="center", fontsize=FONT_SZ_LABEL,
                fontweight="bold")
    _setup_axes(ax, "Phương án", "ratio = $\\tau_{se}/\\tau_{ase}$",
                "Hệ số an toàn theo phương án")
    ax.set_ylim(0, max(ratios) * 1.25)
    ax.legend(fontsize=FONT_SZ_LABEL)
    ax.tick_params(axis="x", labelsize=10)

    # Subplot 2: cost delta
    ax = axes[1]
    costs = [o["cost_delta_pct"] for o in options]
    bars = ax.bar(labels, costs, color=colors, edgecolor="black", linewidth=1.2)
    ax.axhline(0, color="black", linewidth=1)
    for bar, c in zip(bars, costs):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2,
                h + (1 if h >= 0 else -2.5),
                f"{c:+.1f}%", ha="center", fontsize=FONT_SZ_LABEL,
                fontweight="bold",
                color=COLOR_OK if c < 15 else COLOR_FAIL)
    _setup_axes(ax, "Phương án", "Δ Chi phí (%)",
                "Chênh chi phí so với hiện trạng")
    ax.tick_params(axis="x", labelsize=10)

    fig.suptitle("So sánh các phương án thiết kế đệm cát-XM",
                 fontsize=FONT_SZ_TITLE + 1, fontweight="bold")
    fig.tight_layout()
    return fig


# ════════ CHART 5 — Sơ đồ ALiCC (cơ chế vòm + chọc thủng) ════════
def chart_alicc_schematic(D: float = 0.8, s: float = 1.8,
                           Hse: float = 0.40, He: float = 0.70,
                           h_aod: float = 0.80, theta_deg: float = 80.0) -> plt.Figure:
    """Sơ đồ minh hoạ cơ chế truyền tải qua vòm đất + chọc thủng đệm XM."""
    fig, ax = plt.subplots(figsize=(11, 7))
    H = h_aod + He + Hse
    L_view = s * 1.2

    # Mặt cắt 2 cọc
    x_col1, x_col2 = 0.0, s
    # Cao độ
    z_cdm_top = 0.0
    z_hse_top = Hse
    z_he_top = Hse + He
    z_top = Hse + He + h_aod

    # Tô lớp
    layers = [
        (z_cdm_top, z_hse_top, "#A1887F", "Đệm cát-XM $H_{se}$"),
        (z_hse_top, z_he_top,  "#FFE082", "Cát He"),
        (z_he_top,  z_top,     "#9E9E9E", "Áo đường"),
    ]
    for z0, z1, color, label in layers:
        ax.fill_between([-L_view*0.1, s + L_view*0.1], z0, z1,
                        color=color, alpha=0.6, edgecolor="black",
                        linewidth=0.7, zorder=1)

    # Cọc CDM
    for xc in (x_col1, x_col2):
        rect = mpatches.Rectangle((xc - D/2, -1.5), D, 1.5 + z_cdm_top,
                                   facecolor="#1565C0", edgecolor="black",
                                   linewidth=1.0, alpha=0.85, zorder=3)
        ax.add_patch(rect)
        ax.text(xc, -1.7, "Cọc CDM", ha="center", fontsize=FONT_SZ_ANN,
                fontweight="bold", color="#1565C0")

    # Vòm đất (cone)
    theta = math.radians(theta_deg)
    z_apex = z_he_top  # đỉnh vòm
    H0 = (s - D) * math.tan(theta/2)
    z_apex_actual = z_hse_top + min(H0, He)
    # Tam giác vòm giữa 2 cọc
    triangle = plt.Polygon([
        (x_col1 + D/2, z_hse_top),
        (x_col2 - D/2, z_hse_top),
        (s/2, z_apex_actual),
    ], facecolor="#FFCC80", alpha=0.4, edgecolor="#E65100",
       linewidth=1.5, linestyle="--", zorder=2)
    ax.add_patch(triangle)
    ax.text(s/2, z_apex_actual + 0.05, "Vòm đất\n(arching)",
            ha="center", fontsize=FONT_SZ_ANN, color="#E65100",
            fontweight="bold")

    # Mũi tên tải
    for x_arr in np.linspace(0.1, s - 0.1, 6):
        ax.annotate("", xy=(x_arr, z_top - 0.02), xytext=(x_arr, z_top + 0.25),
                    arrowprops=dict(arrowstyle="->", color="#D32F2F", lw=1.5))
    ax.text(s/2, z_top + 0.35, "Tải đắp + hoạt tải",
            ha="center", fontsize=FONT_SZ_LABEL, color="#D32F2F", fontweight="bold")

    # Mũi tên chọc thủng (45°)
    for xc in (x_col1, x_col2):
        # Vùng chọc thủng vòng quanh cọc
        circle = mpatches.Wedge((xc, z_hse_top + Hse/2), D/2 + Hse*0.3,
                                 0, 360, width=0.05,
                                 facecolor="#E91E63", alpha=0.5, zorder=4)
        ax.add_patch(circle)
    ax.text(0.05, z_hse_top + Hse/2 + 0.12,
            "Mặt phá hoại\nchọc thủng",
            fontsize=FONT_SZ_ANN, color="#AD1457", fontweight="bold")

    # Kích thước
    ax.annotate("", xy=(x_col1 - 0.4, -1.5), xytext=(x_col1 - 0.4, z_top),
                arrowprops=dict(arrowstyle="<->", color="black", lw=1))
    ax.text(x_col1 - 0.55, z_top/2, "H = $h_{aod} + H_e + H_{se}$",
            rotation=90, va="center", ha="center", fontsize=FONT_SZ_ANN)
    ax.annotate("", xy=(x_col1, -1.7 - 0.5), xytext=(x_col2, -1.7 - 0.5),
                arrowprops=dict(arrowstyle="<->", color="black", lw=1))
    ax.text(s/2, -1.7 - 0.7, f"s = {s} m (khoảng cách cọc)",
            ha="center", fontsize=FONT_SZ_ANN)

    # Annotate Hse
    ax.annotate("", xy=(s + 0.3, z_cdm_top), xytext=(s + 0.3, z_hse_top),
                arrowprops=dict(arrowstyle="<->", color="#5D4037", lw=1.2))
    ax.text(s + 0.45, Hse/2, f"$H_{{se}}$ = {Hse:.2f} m",
            va="center", fontsize=FONT_SZ_ANN, fontweight="bold", color="#5D4037")

    ax.set_xlim(-1.0, s + 1.2)
    ax.set_ylim(-2.5, z_top + 0.8)
    ax.set_aspect("equal")
    ax.set_title("Sơ đồ cơ chế truyền tải qua đệm cát-XM (ALiCC PWRI)",
                 fontsize=FONT_SZ_TITLE, fontweight="bold", pad=12)
    ax.set_xlabel("Toạ độ ngang (m)", fontsize=FONT_SZ_LABEL)
    ax.set_ylabel("Cao độ (m)", fontsize=FONT_SZ_LABEL)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.tight_layout()
    return fig


# ════════ CHART 6 — Pareto: chi phí vs ratio ════════
def chart_pareto_cost_ratio(
    Hse_list=(0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70),
    qu_list=(500, 600, 700, 800, 900, 1000, 1100, 1200),
) -> plt.Figure:
    """Scatter cost vs ratio — chỉ điểm ĐẠT (ratio ≤ 1) tô xanh, không đạt tô đỏ.

    Chi phí lấy từ data/cost_model.json qua core.cost helper.
    """
    from core.cost import cushion_cost_delta_pct
    fig, ax = plt.subplots(figsize=(11, 6.5))

    pts_ok_x, pts_ok_y, pts_ok_lbl = [], [], []
    pts_fail_x, pts_fail_y, pts_fail_lbl = [], [], []
    for h in Hse_list:
        for q in qu_list:
            r = check_alicc(h, q_uckse=float(q))
            d_pct = cushion_cost_delta_pct(h, float(q))
            lbl = f"H={h:.2f}\nq={q}"
            if r["ok"]:
                pts_ok_x.append(d_pct); pts_ok_y.append(r["ratio"]); pts_ok_lbl.append(lbl)
            else:
                pts_fail_x.append(d_pct); pts_fail_y.append(r["ratio"]); pts_fail_lbl.append(lbl)

    ax.scatter(pts_fail_x, pts_fail_y, s=60, c=COLOR_FAIL, alpha=0.45,
               edgecolors="black", linewidth=0.5, label="Không đạt", zorder=2)
    ax.scatter(pts_ok_x, pts_ok_y, s=80, c=COLOR_OK, alpha=0.85,
               edgecolors="black", linewidth=0.7, label="Đạt", zorder=3)

    # Pareto front (ok points: minimum cost for each ratio bin)
    if pts_ok_x:
        pts_ok = sorted(zip(pts_ok_x, pts_ok_y, pts_ok_lbl))
        # find non-dominated (lower cost, lower ratio)
        pareto = []
        min_r = float("inf")
        for x, y, l in pts_ok:
            if y < min_r:
                pareto.append((x, y, l))
                min_r = y
        if len(pareto) >= 2:
            px = [p[0] for p in pareto]
            py = [p[1] for p in pareto]
            ax.plot(px, py, "--", color="#6A1B9A", linewidth=2.0,
                    label="Đường Pareto", zorder=4)
        # Annotate điểm rẻ nhất
        cheap = min(pts_ok, key=lambda p: p[0])
        ax.scatter([cheap[0]], [cheap[1]], s=300, marker="*",
                   color="#6A1B9A", zorder=10, edgecolors="black", linewidth=1)
        ax.annotate(f"Tối ưu chi phí\n{cheap[2]}",
                    xy=(cheap[0], cheap[1]), xytext=(cheap[0] + 8, cheap[1] - 0.15),
                    fontsize=FONT_SZ_LABEL, fontweight="bold", color="#6A1B9A",
                    arrowprops=dict(arrowstyle="->", color="#6A1B9A"))

    ax.axhline(1.0, color=COLOR_THRESHOLD, linewidth=2, linestyle="--",
               label="Ngưỡng đạt")
    ax.axvline(0, color="black", linewidth=1, alpha=0.5)
    _setup_axes(ax, "Δ Chi phí so với hiện tại (%)",
                "ratio = $\\tau_{se}/\\tau_{ase}$",
                "Pareto: chi phí - hệ số an toàn (72 phương án Hse × $q_{uckse}$)")
    ax.legend(loc="upper right", fontsize=FONT_SZ_LABEL, framealpha=0.95)
    fig.tight_layout()
    return fig


# ════════ DEMO ════════
if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for name, fn in [
        ("heatmap", lambda: chart_heatmap_ratio()),
        ("vs_quckse", lambda: chart_ratio_vs_quckse_fixed_Hse()),
        ("vs_Hse", lambda: chart_ratio_vs_Hse_fixed_quckse()),
        ("schematic", lambda: chart_alicc_schematic()),
        ("pareto", lambda: chart_pareto_cost_ratio()),
        ("compare", lambda: chart_compare_options([
            {"label": "A: Tăng q_uckse\nHse=0.40, q=800", "Hse": 0.40, "q_uckse": 800,
             "ratio": 0.94, "cost_delta_pct": 10.0},
            {"label": "B: Tăng Hse\nHse=0.55, q=600", "Hse": 0.55, "q_uckse": 600,
             "ratio": 0.92, "cost_delta_pct": 17.9},
            {"label": "Hiện tại\nHse=0.40, q=600", "Hse": 0.40, "q_uckse": 600,
             "ratio": 1.25, "cost_delta_pct": 0.0},
        ])),
    ]:
        fig = fn()
        fig.savefig(f"scratch/cushion_{name}.png", dpi=120, bbox_inches="tight")
        print(f"OK: scratch/cushion_{name}.png")
        import matplotlib.pyplot as plt
        plt.close(fig)
