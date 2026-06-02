"""§72 Task 6 — Sơ đồ minh họa S1, S2, Lcoc cho CDM.

Vẽ schematic 2D bằng matplotlib:
- Cao độ tự nhiên + cao độ thiết kế + tải q đắp
- Đất đắp (γ ~ 19 kN/m³)
- Cọc CDM (Lcoc, D) — cụm 2-3 cọc demo
- Khối gia cố composite (a × Ec + (1-a) × Es)
- Lớp đất yếu (bùn) trong vùng cọc + dưới mũi (H_S2)
- Lớp đất cứng/cát đáy
- Mực nước ngầm
- Mũi tên S1 trong khối gia cố (lún đàn hồi)
- Mũi tên S2 dưới mũi (cố kết Terzaghi)
- Mũi tên Lcoc dọc bên cọc

Quy tắc: KHÔNG emoji. Tiếng Việt có dấu. Label giá trị số trực tiếp.
"""
from __future__ import annotations

import io
from typing import Optional

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle


def draw_S1_S2_Lcoc(
    Lcoc_m: float = 18.0,
    D_m: float = 0.80,
    spacing_m: float = 1.80,
    H_fill_m: float = 1.90,
    H_clay_above_tip_m: float = 16.0,
    H_S2_clay_m: float = 5.0,
    H_stiff_below_m: float = 8.0,
    gwl_depth_m: float = 1.5,
    q_kPa: float = 40.8,
    S1_cm: float = 12.0,
    S2_cm: float = 8.0,
    a_ratio: float = 0.155,
    Ec_kPa: float = 40000,
    Es_kPa: float = 2860,
    bh_name: str = "ND-XX",
    figsize: tuple = (10.5, 9.0),
) -> plt.Figure:
    """Sơ đồ S1+S2+Lcoc. Returns matplotlib Figure."""
    fig, ax = plt.subplots(figsize=figsize)

    # Hệ trục: Y = cao độ giả định (đỉnh đắp = 0, đi xuống là âm)
    y_top_fill = 0.0
    y_nat = y_top_fill - H_fill_m
    y_clay_top = y_nat
    y_pile_tip = y_clay_top - (Lcoc_m - H_fill_m)
    y_clay_bot = y_pile_tip - H_S2_clay_m  # đáy lớp bùn dưới mũi
    y_stiff_bot = y_clay_bot - H_stiff_below_m
    y_gwl = y_top_fill - gwl_depth_m

    x_center = 0.0
    width = 4.5

    # --- Tầng đất ---
    # Đất đắp
    ax.add_patch(Rectangle((-width, y_nat), 2 * width, H_fill_m,
                            facecolor="#D2B48C", edgecolor="#8B4513",
                            linewidth=0.8, label="Đất đắp"))
    ax.text(-width + 0.15, y_top_fill - 0.4,
            f"ĐẤT ĐẮP (h={H_fill_m:.2f} m)",
            fontsize=10, weight="bold", color="#5D4037")
    # Lớp bùn (chung khối phía trong + ngoài cọc)
    ax.add_patch(Rectangle((-width, y_clay_bot), 2 * width,
                            y_clay_top - y_clay_bot,
                            facecolor="#A8B8B8", edgecolor="#666",
                            linewidth=0.8, alpha=0.5, label="Bùn yếu"))
    # Vùng GIA CỐ trong bùn (composite color)
    ax.add_patch(Rectangle((-width, y_pile_tip), 2 * width,
                            y_clay_top - y_pile_tip,
                            facecolor="#90C8E2", edgecolor="#1565C0",
                            linewidth=0.8, alpha=0.45, label="Khối gia cố"))
    # Lớp cứng đáy
    ax.add_patch(Rectangle((-width, y_stiff_bot), 2 * width,
                            y_clay_bot - y_stiff_bot,
                            facecolor="#F5DEB3", edgecolor="#8B7355",
                            linewidth=0.8, label="Cát/sét cứng"))

    # --- Mực nước ngầm ---
    ax.plot([-width, width], [y_gwl, y_gwl], color="#0066CC",
             linestyle="--", linewidth=1.6, label=f"MNN ({y_gwl - y_top_fill:+.1f} m)")
    # Tam giác MNN
    ax.plot([width - 0.3], [y_gwl], marker="v", color="#0066CC", markersize=10)

    # --- Cọc CDM (cụm 3 cọc demo) ---
    pile_xs = [-spacing_m, 0.0, spacing_m]
    for px in pile_xs:
        ax.add_patch(Rectangle((px - D_m / 2, y_pile_tip),
                                D_m, Lcoc_m,
                                facecolor="#1565C0", edgecolor="#0D47A1",
                                linewidth=1.0, zorder=5))

    # --- Tải đắp q ---
    n_arrows = 5
    arr_xs = [-width * 0.7 + i * (1.4 * width / (n_arrows - 1))
              for i in range(n_arrows)]
    for ax_x in arr_xs:
        ax.annotate("", xy=(ax_x, y_top_fill), xytext=(ax_x, y_top_fill + 1.0),
                    arrowprops=dict(arrowstyle="->", color="#C62828",
                                     lw=2))
    ax.text(0, y_top_fill + 1.4, f"q = {q_kPa:.1f} kPa (tải đắp tĩnh)",
             ha="center", fontsize=11, weight="bold", color="#C62828")

    # --- Mũi tên S1 (trong khối gia cố) ---
    x_arrow_S1 = -width + 0.7
    y_arrow_S1_top = y_clay_top - 0.3
    y_arrow_S1_bot = y_pile_tip + 0.3
    ax.annotate("", xy=(x_arrow_S1, y_arrow_S1_bot),
                xytext=(x_arrow_S1, y_arrow_S1_top),
                arrowprops=dict(arrowstyle="-|>", color="#2E7D32", lw=2.5,
                                 connectionstyle="arc3,rad=0"))
    ax.text(x_arrow_S1 - 0.25, (y_arrow_S1_top + y_arrow_S1_bot) / 2,
             f"$S_1$ = {S1_cm:.1f} cm\n(đàn hồi khối gia cố)",
             ha="right", va="center", fontsize=10, weight="bold",
             color="#2E7D32",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#E8F5E9",
                        edgecolor="#2E7D32"))

    # --- Mũi tên S2 (dưới mũi cọc) ---
    x_arrow_S2 = width - 0.7
    y_arrow_S2_top = y_pile_tip - 0.3
    y_arrow_S2_bot = y_clay_bot + 0.3
    ax.annotate("", xy=(x_arrow_S2, y_arrow_S2_bot),
                xytext=(x_arrow_S2, y_arrow_S2_top),
                arrowprops=dict(arrowstyle="-|>", color="#D32F2F", lw=2.5))
    ax.text(x_arrow_S2 + 0.25, (y_arrow_S2_top + y_arrow_S2_bot) / 2,
             f"$S_2$ = {S2_cm:.1f} cm\n(cố kết Terzaghi\ndưới mũi)",
             ha="left", va="center", fontsize=10, weight="bold",
             color="#D32F2F",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#FFEBEE",
                        edgecolor="#D32F2F"))

    # --- Mũi tên Lcoc dọc cọc trung tâm ---
    x_arrow_L = pile_xs[0] - 1.2
    ax.annotate("", xy=(x_arrow_L, y_pile_tip),
                xytext=(x_arrow_L, y_top_fill),
                arrowprops=dict(arrowstyle="<|-|>", color="#1565C0", lw=2))
    ax.text(x_arrow_L - 0.15, (y_top_fill + y_pile_tip) / 2,
             f"$L_{{coc}}$ = {Lcoc_m:.1f} m",
             ha="right", va="center", fontsize=11, weight="bold",
             color="#0D47A1", rotation=90)

    # --- Nhãn các đường mức ---
    ax.axhline(y_top_fill, color="#999", linewidth=0.6, linestyle=":")
    ax.text(width + 0.1, y_top_fill, "Đỉnh đắp", fontsize=9, va="center")
    ax.axhline(y_nat, color="#5D4037", linewidth=0.8, linestyle="--")
    ax.text(width + 0.1, y_nat, "Mặt đất TN", fontsize=9, va="center",
             color="#5D4037")
    ax.axhline(y_clay_top, color="#666", linewidth=0.6, linestyle=":")
    ax.axhline(y_pile_tip, color="#0D47A1", linewidth=1.2, linestyle="-")
    ax.text(width + 0.1, y_pile_tip, "Mũi cọc CDM", fontsize=9, va="center",
             color="#0D47A1", weight="bold")
    ax.axhline(y_clay_bot, color="#666", linewidth=0.6, linestyle="--")
    ax.text(width + 0.1, y_clay_bot, "Đáy lớp bùn", fontsize=9, va="center")

    # --- Thông số góc dưới-trái ---
    info_text = (
        f"Hố khoan: {bh_name}\n"
        f"D = {D_m * 1000:.0f} mm,  s = {spacing_m:.2f} m\n"
        f"a = {a_ratio:.3f}  ({a_ratio * 100:.1f}%)\n"
        f"$E_c$ = {Ec_kPa:,.0f} kPa\n"
        f"$E_s$ = {Es_kPa:,.0f} kPa\n"
        f"$S_{{total}} = S_1 + S_2$ = {S1_cm + S2_cm:.1f} cm"
    )
    ax.text(-width + 0.2, y_stiff_bot + 0.3, info_text,
             fontsize=9, va="bottom",
             bbox=dict(boxstyle="round,pad=0.5", facecolor="white",
                        edgecolor="#666", linewidth=0.8))

    # --- Title + style ---
    ax.set_title(f"Sơ đồ minh hoạ lún CDM — {bh_name}\n"
                  f"$S_1$ (đàn hồi khối gia cố) + $S_2$ (cố kết dưới mũi cọc)",
                  fontsize=12, weight="bold")
    ax.set_xlim(-width - 1.5, width + 1.8)
    ax.set_ylim(y_stiff_bot - 0.5, y_top_fill + 2.5)
    ax.set_xlabel("Khoảng cách ngang (m)")
    ax.set_ylabel("Cao độ (m, gốc = đỉnh đắp)")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)

    fig.tight_layout()
    return fig


def to_svg_bytes(fig) -> bytes:
    """Convert figure → SVG bytes."""
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    return buf.getvalue()


def to_png_bytes(fig, dpi: int = 150) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    return buf.getvalue()


if __name__ == "__main__":
    fig = draw_S1_S2_Lcoc(
        Lcoc_m=18.0, D_m=0.80, spacing_m=1.80,
        H_fill_m=1.90, H_clay_above_tip_m=16.0, H_S2_clay_m=5.0,
        H_stiff_below_m=8.0, gwl_depth_m=1.5, q_kPa=40.8,
        S1_cm=12.0, S2_cm=8.0,
        a_ratio=0.155, Ec_kPa=40000, Es_kPa=2860,
        bh_name="ND-07",
    )
    out = "plaxis_out/schematic_S1_S2_Lcoc.svg"
    with open(out, "wb") as f:
        f.write(to_svg_bytes(fig))
    print(f"Saved: {out}")
