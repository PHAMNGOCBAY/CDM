"""
thuyvan_phuan_plots.py — Vẽ biểu đồ phân tích thủy văn trạm Phú An 1977–2024.

6 biểu đồ:
  1. Time series TB/Max/Min năm + xu thế linear
  2. Đỉnh triều tối đa annual (file summary so với max từ daily)
  3. Box plot phân bố MNTB theo 12 tháng (48 năm)
  4. Heatmap year × month (TB MNTB)
  5. Histogram tần suất MNTB ngày + percentiles
  6. Cumulative max + so sánh các thập kỷ

Output: data/thuyvan_phuan_analysis.png
"""
from __future__ import annotations

import sqlite3
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch

_ROOT = Path(__file__).parent.parent
_DB   = _ROOT / "data" / "TTHC.sqlite"


def load_data():
    """Load 3 datasets từ SQLite."""
    con = sqlite3.connect(_DB)
    con.row_factory = sqlite3.Row
    daily = con.execute("""
        SELECT year, month, day, iso_date, h_cm
        FROM thuyvan_daily ORDER BY iso_date
    """).fetchall()
    annual = con.execute("""
        SELECT year, avg_cm, max_cm, min_cm,
               monthly_avg_cm, monthly_max_cm, monthly_min_cm
        FROM thuyvan_annual_summary ORDER BY year
    """).fetchall()
    peaks = con.execute("""
        SELECT year, peak_cm FROM thuyvan_tidal_peaks ORDER BY year
    """).fetchall()
    return daily, annual, peaks


def make_plots():
    daily, annual, peaks = load_data()
    years   = np.array([r["year"] for r in annual])
    avg_yr  = np.array([r["avg_cm"] for r in annual])
    max_yr  = np.array([r["max_cm"] for r in annual])
    min_yr  = np.array([r["min_cm"] for r in annual])

    h_arr   = np.array([r["h_cm"] for r in daily])
    m_arr   = np.array([r["month"] for r in daily])
    y_arr   = np.array([r["year"] for r in daily])

    # ── Figure 6 subplots ────────────────────────────────────────────────
    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(3, 2, hspace=0.40, wspace=0.22)

    # ─── (1) Time series TB/Max/Min năm + xu thế ──────────────────────────
    ax1 = fig.add_subplot(gs[0, :])
    ax1.fill_between(years, min_yr, max_yr, color="#90CAF9", alpha=0.30,
                     label="Min ↔ Max trong năm")
    ax1.plot(years, max_yr, "-^", color="#D32F2F", lw=1.5, ms=5,
             label="Max năm (đỉnh triều)")
    ax1.plot(years, avg_yr, "-o", color="#1565C0", lw=2.0, ms=5,
             label="TB năm")
    ax1.plot(years, min_yr, "-v", color="#2E7D32", lw=1.3, ms=4,
             label="Min năm (đáy ròng)")

    # Linear trend lines
    for arr, color, lbl in [(avg_yr, "#1565C0", "TB"),
                              (max_yr, "#D32F2F", "Max"),
                              (min_yr, "#2E7D32", "Min")]:
        a, b = np.polyfit(years, arr, 1)
        yfit = a * years + b
        ax1.plot(years, yfit, "--", color=color, lw=1.2, alpha=0.6)
        ax1.text(years[-1] + 0.3, yfit[-1], f"{a*10:+.1f}\ncm/10yr",
                 fontsize=8, color=color, va="center", fontweight="bold")

    ax1.set_title("Trạm Phú An — Mực nước trung bình ngày 1977–2024 (so với mốc cao độ Quốc gia)",
                  fontsize=13, fontweight="bold")
    ax1.set_xlabel("Năm")
    ax1.set_ylabel("Mực nước H (cm)")
    ax1.grid(True, ls=":", alpha=0.4)
    ax1.legend(loc="upper left", fontsize=9, ncol=4, framealpha=0.92)
    ax1.set_xlim(years[0] - 1, years[-1] + 4)
    ax1.axhline(0, color="#888", lw=0.6)

    # ─── (2) Đỉnh triều annual peaks ──────────────────────────────────────
    ax2 = fig.add_subplot(gs[1, 0])
    peak_years = np.array([r["year"] for r in peaks])
    peak_vals  = np.array([r["peak_cm"] for r in peaks])
    # Sort by year cho clarity
    srt = np.argsort(peak_years)
    peak_years, peak_vals = peak_years[srt], peak_vals[srt]

    bars = ax2.bar(peak_years, peak_vals, color="#D32F2F",
                    alpha=0.78, edgecolor="#a01010", lw=1.2)
    for bar, v in zip(bars, peak_vals):
        ax2.text(bar.get_x() + bar.get_width()/2, v + 1, f"{v}",
                 ha="center", fontsize=8, color="#a01010")
    # Add trend line
    if len(peak_years) > 2:
        a, b = np.polyfit(peak_years, peak_vals, 1)
        x_t = np.array([peak_years[0], peak_years[-1]])
        ax2.plot(x_t, a*x_t + b, "--", color="#a01010", lw=1.4,
                 label=f"Xu thế: {a*10:+.1f} cm/10yr")
    ax2.set_title("Đỉnh triều tối đa lịch sử (cm) — 13 năm tiêu biểu",
                  fontsize=11, fontweight="bold")
    ax2.set_xlabel("Năm")
    ax2.set_ylabel("Đỉnh triều (cm)")
    ax2.grid(True, ls=":", alpha=0.4, axis="y")
    ax2.legend(loc="upper left", fontsize=9)
    ax2.set_ylim(120, max(peak_vals) + 15)

    # ─── (3) Box plot theo tháng (48 năm) ─────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 1])
    months_data = [h_arr[m_arr == m] for m in range(1, 13)]
    bp = ax3.boxplot(months_data, patch_artist=True, showfliers=True,
                      flierprops=dict(marker="o", markersize=2,
                                       markerfacecolor="#999", alpha=0.4))
    # Color theo mùa: mùa khô (5-8) xanh, mùa lũ (10-12) đỏ
    season_colors = ["#FFCDD2"]*4 + ["#C8E6C9"]*5 + ["#FFCDD2"]*3
    for patch, color in zip(bp["boxes"], season_colors):
        patch.set_facecolor(color)
        patch.set_edgecolor("#444")
    for median in bp["medians"]:
        median.set_color("#000")
        median.set_linewidth(1.4)
    ax3.set_xticklabels(["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"])
    ax3.set_title("Phân bố MNTB theo tháng (1977–2024, n=48 năm)",
                  fontsize=11, fontweight="bold")
    ax3.set_xlabel("Tháng")
    ax3.set_ylabel("MNTB (cm)")
    ax3.axhline(0, color="#888", lw=0.6)
    ax3.grid(True, ls=":", alpha=0.4)
    ax3.legend([Patch(facecolor="#FFCDD2"), Patch(facecolor="#C8E6C9")],
               ["Mùa lũ / cao", "Mùa khô / thấp"],
               loc="upper left", fontsize=8)

    # ─── (4) Heatmap year × month (avg) ──────────────────────────────────
    ax4 = fig.add_subplot(gs[2, 0])
    # Tạo matrix 48 × 12
    Y = sorted(set(y_arr))
    n_y = len(Y)
    grid = np.full((n_y, 12), np.nan)
    for i, y in enumerate(Y):
        for m in range(1, 13):
            mask = (y_arr == y) & (m_arr == m)
            if mask.any():
                grid[i, m-1] = h_arr[mask].mean()
    # Diverging colormap
    cmap = LinearSegmentedColormap.from_list("rwb",
        ["#2E7D32", "#A5D6A7", "#FFF59D", "#FFAB91", "#D32F2F"])
    im = ax4.imshow(grid, aspect="auto", cmap=cmap,
                     vmin=-30, vmax=50, origin="lower",
                     extent=[0.5, 12.5, Y[0] - 0.5, Y[-1] + 0.5])
    ax4.set_xticks(range(1, 13))
    ax4.set_xticklabels(["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"],
                        fontsize=8)
    ax4.set_yticks([1977, 1985, 1995, 2005, 2015, 2024])
    ax4.set_title("Heatmap MNTB tháng × năm",
                  fontsize=11, fontweight="bold")
    ax4.set_xlabel("Tháng")
    ax4.set_ylabel("Năm")
    cbar = plt.colorbar(im, ax=ax4, label="MNTB (cm)", pad=0.02)

    # ─── (5) Histogram phân bố MNTB ngày + percentiles ───────────────────
    ax5 = fig.add_subplot(gs[2, 1])
    ax5.hist(h_arr, bins=70, color="#1565C0", alpha=0.65,
              edgecolor="white", lw=0.5)
    # Percentiles
    p5, p50, p95, p99 = np.percentile(h_arr, [5, 50, 95, 99])
    for p, lbl, col in [(p5, f"P5 = {p5:.0f}", "#2E7D32"),
                         (p50, f"P50 = {p50:.0f}", "#000"),
                         (p95, f"P95 = {p95:.0f}", "#FF6F00"),
                         (p99, f"P99 = {p99:.0f}", "#D32F2F")]:
        ax5.axvline(p, color=col, ls="--", lw=1.5, alpha=0.85)
        ax5.text(p, ax5.get_ylim()[1] * 0.92, lbl,
                  rotation=90, fontsize=8, color=col, va="top",
                  ha="right", fontweight="bold",
                  bbox=dict(facecolor="white", alpha=0.85,
                            edgecolor=col, lw=0.8, pad=2))
    ax5.set_title(f"Phân bố tần suất MNTB ngày (n={len(h_arr):,})",
                  fontsize=11, fontweight="bold")
    ax5.set_xlabel("MNTB (cm)")
    ax5.set_ylabel("Số ngày")
    ax5.grid(True, ls=":", alpha=0.4)
    ax5.axvline(0, color="#888", lw=0.6)

    # Title chung
    fig.suptitle(
        "PHÂN TÍCH THỦY VĂN — TRẠM PHÚ AN, SÔNG SÀI GÒN  |  1977–2024 (48 năm)",
        fontsize=15, fontweight="bold", y=0.995,
    )

    out = _ROOT / "data" / "thuyvan_phuan_analysis.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close(fig)

    # ── Figure 2: Cumulative max + decade comparison ─────────────────────
    fig2, ax = plt.subplots(figsize=(14, 6))
    decades = [(1977, 1989, "1977–1989", "#1565C0"),
               (1990, 1999, "1990–1999", "#558B2F"),
               (2000, 2009, "2000–2009", "#F9A825"),
               (2010, 2019, "2010–2019", "#EF6C00"),
               (2020, 2024, "2020–2024", "#C62828")]
    for y0, y1, lbl, col in decades:
        mask = (y_arr >= y0) & (y_arr <= y1)
        vals = h_arr[mask]
        if len(vals) == 0: continue
        # Histogram normalize
        ax.hist(vals, bins=60, color=col, alpha=0.40, density=True,
                 label=f"{lbl} (n={len(vals):,}, TB={vals.mean():.1f})",
                 histtype="stepfilled", edgecolor=col, lw=1.2)
    ax.set_title("So sánh phân bố MNTB theo thập kỷ — Trạm Phú An",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("MNTB (cm)")
    ax.set_ylabel("Mật độ xác suất")
    ax.legend(loc="upper right", fontsize=10, framealpha=0.92)
    ax.grid(True, ls=":", alpha=0.4)
    ax.axvline(0, color="#888", lw=0.6)
    fig2.tight_layout()
    out2 = _ROOT / "data" / "thuyvan_phuan_decades.png"
    fig2.savefig(out2, dpi=130, bbox_inches="tight")
    print(f"Saved: {out2}")
    plt.close(fig2)

    # Summary stats JSON
    stats = {
        "_meta": {
            "station":   "Phú An",
            "river":     "Sài Gòn",
            "period":    f"{int(years[0])}-{int(years[-1])}",
            "n_years":   int(len(years)),
            "n_records": int(len(h_arr)),
        },
        "overall": {
            "min_cm":  float(h_arr.min()),
            "max_cm":  float(h_arr.max()),
            "mean_cm": float(h_arr.mean()),
            "p5_cm":   float(p5),
            "p50_cm":  float(p50),
            "p95_cm":  float(p95),
            "p99_cm":  float(p99),
        },
        "trend": {
            "avg_cm_per_decade":  float(np.polyfit(years, avg_yr, 1)[0] * 10),
            "max_cm_per_decade":  float(np.polyfit(years, max_yr, 1)[0] * 10),
            "min_cm_per_decade":  float(np.polyfit(years, min_yr, 1)[0] * 10),
        },
        "decade_mean": {},
    }
    for y0, y1, lbl, _ in decades:
        mask = (y_arr >= y0) & (y_arr <= y1)
        if mask.any():
            stats["decade_mean"][lbl] = round(float(h_arr[mask].mean()), 2)
    out_json = _ROOT / "data" / "thuyvan_phuan_stats.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_json}")
    return stats


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    stats = make_plots()
    print()
    print("=== Thong ke tong hop ===")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
