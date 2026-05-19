"""
Áp lực nước — tính toán và biểu đồ GEO5-style
Hydrostatic + seepage (Terzaghi simplified) cho cọc ván / tường chắn.

Đơn vị: kN, m (cao độ dương hướng lên, γ_w = 9.81 kN/m³).
"""

from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
from dataclasses import dataclass


GAMMA_W = 9.81  # kN/m³


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class WaterGeometry:
    top_elev:          float          # cao độ đỉnh cừ [m]
    pile_length:       float          # chiều dài cừ [m]
    soil_level_front:  float          # cao độ mặt đất phía Front [m]
    water_elev_front:  float          # mực nước Front [m]
    water_elev_back:   float          # mực nước Back [m]
    gamma_w:           float = GAMMA_W

    @property
    def bot_elev(self) -> float:
        return self.top_elev - self.pile_length

    @property
    def embedment(self) -> float:
        """Chiều sâu chôn cừ dưới mặt đất đào Front [m]."""
        return max(0.0, self.soil_level_front - self.bot_elev)

    @property
    def head_diff(self) -> float:
        """Độ chênh mực nước Back − Front [m]."""
        return self.water_elev_back - self.water_elev_front


# ---------------------------------------------------------------------------
# Profile builders — trả về (elevs, pressure) cùng độ phân giải
# ---------------------------------------------------------------------------

def build_elevation_grid(geom: WaterGeometry, n_pts: int = 200) -> np.ndarray:
    """Lưới cao độ từ đỉnh cừ xuống mũi cừ, bổ sung các điểm gãy."""
    key = sorted({
        geom.top_elev,
        geom.water_elev_back,
        geom.water_elev_front,
        geom.soil_level_front,
        geom.bot_elev,
    }, reverse=True)
    # Điền đều giữa các điểm gãy
    segments = []
    for i in range(len(key) - 1):
        seg = np.linspace(key[i], key[i + 1], max(3, n_pts // (len(key) - 1)))
        segments.append(seg[:-1])
    segments.append(np.array([key[-1]]))
    return np.concatenate(segments)


def hydrostatic_back(geom: WaterGeometry, elevs: np.ndarray) -> np.ndarray:
    """Áp lực thủy tĩnh phía Back (mặt giữ đất) [kN/m²]."""
    return np.maximum(0.0, (geom.water_elev_back - elevs) * geom.gamma_w)


def hydrostatic_front(geom: WaterGeometry, elevs: np.ndarray) -> np.ndarray:
    """Áp lực thủy tĩnh phía Front (mặt đào) [kN/m²]."""
    return np.maximum(0.0, (geom.water_elev_front - elevs) * geom.gamma_w)


def seepage_back(geom: WaterGeometry, elevs: np.ndarray) -> np.ndarray:
    """Áp lực nước phía Back sau hiệu chỉnh thấm (Terzaghi simplified).

    Phía Back: dòng chảy đi xuống → áp lực giảm dần về mũi cừ.
    Chỉ áp dụng bên dưới mực nước Back và dưới mặt đất đào.
    """
    d = geom.embedment
    if d < 0.5 or geom.head_diff <= 0:
        return hydrostatic_back(geom, elevs)

    p = np.zeros(len(elevs))
    exc = geom.soil_level_front  # mặt đất đào

    for i, elev in enumerate(elevs):
        if elev >= geom.water_elev_back:
            p[i] = 0.0
        elif elev >= exc:
            # Trên mặt đào: thủy tĩnh thuần
            p[i] = (geom.water_elev_back - elev) * geom.gamma_w
        else:
            # Dưới mặt đào: tổn thất cột nước tuyến tính dọc theo đường thấm
            z_below = exc - elev          # độ sâu bên dưới mặt đào [m]
            frac = min(z_below / d, 1.0)  # tỉ lệ trên đường thấm phía Back
            head_loss = geom.head_diff / 2.0 * frac
            h = (geom.water_elev_back - elev) - head_loss
            p[i] = max(0.0, h * geom.gamma_w)

    return p


def seepage_front(geom: WaterGeometry, elevs: np.ndarray) -> np.ndarray:
    """Áp lực nước phía Front sau hiệu chỉnh thấm (Terzaghi simplified).

    Phía Front: dòng chảy đi lên → áp lực tăng dần từ mũi cừ lên mặt đào.
    """
    d = geom.embedment
    if d < 0.5 or geom.head_diff <= 0:
        return hydrostatic_front(geom, elevs)

    p = np.zeros(len(elevs))
    exc = geom.soil_level_front

    for i, elev in enumerate(elevs):
        if elev >= exc:
            p[i] = 0.0  # Trên mặt đào: không có nước phía Front
        else:
            z_below = exc - elev
            frac = min(z_below / d, 1.0)
            # Áp lực phía Front tăng từ 0 tại mặt đào, nhưng đã giảm so với thủy tĩnh
            head_gain = geom.head_diff / 2.0 * frac
            h = (geom.water_elev_front - elev) + head_gain
            p[i] = max(0.0, h * geom.gamma_w)

    return p


def net_water_pressure(p_back: np.ndarray, p_front: np.ndarray) -> np.ndarray:
    """Áp lực nước ngang tổng hợp = Back − Front [kN/m²].

    Dương = hướng từ Back sang Front (cùng chiều với áp lực đất chủ động).
    """
    return p_back - p_front


# ---------------------------------------------------------------------------
# Resultant
# ---------------------------------------------------------------------------

def resultant(elevs: np.ndarray, pressure: np.ndarray) -> tuple[float, float]:
    """Lực tổng hợp và cao độ điểm đặt lực.

    Returns:
        F [kN/m]: lực tổng hợp (tích phân hình thang)
        z_app [m]: cao độ điểm đặt lực
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

def plot_water_diagram(
    geom: WaterGeometry,
    elevs: np.ndarray,
    p_back: np.ndarray,
    p_front: np.ndarray,
    p_net: np.ndarray,
    layer_elevs: list[float] | None = None,
    title: str = "Water Pressure Diagram",
) -> plt.Figure:
    """Biểu đồ áp lực nước GEO5-style — 3 panel.

    Quy tắc thống nhất với tab GeoData:
      Panel 1 [Front — TRÁI]:  áp lực phía đào, bars sang TRÁI
      Panel 2 [Back  — PHẢI]:  áp lực phía giữ đất, bars sang PHẢI
      Panel 3 [Net]:           p_back − p_front; dương (Back>Front) → bars sang TRÁI
                                vì lực tổng hợp đẩy cừ về phía Front (trái)
    """
    fig, axes = plt.subplots(1, 3, figsize=(10, 7), sharey=True,
                             layout="constrained")
    fig.suptitle(title, fontsize=10, fontweight="bold")

    bot = geom.bot_elev
    top = geom.top_elev
    y_range = [bot - 0.5, top + 1.2]

    # --- Panel 1: Front water pressure — bên TRÁI, bars sang TRÁI
    _draw_bars(axes[0], elevs, p_front, "#1a8cff",
               title="Front Water Pressure\n[kN/m²]", direction="left")

    # --- Panel 2: Back water pressure — bên PHẢI, bars sang PHẢI
    _draw_bars(axes[1], elevs, p_back, "steelblue",
               title="Back Water Pressure\n[kN/m²]", direction="right")

    # --- Panel 3: Net = p_back − p_front
    # Dương (Back > Front): lực đẩy cừ về Front = sang TRÁI
    # Âm  (Front > Back):  lực đẩy cừ về Back  = sang PHẢI
    net_pos = np.where(p_net >= 0, p_net,  0.0)   # Back > Front
    net_neg = np.where(p_net <  0, -p_net, 0.0)   # Front > Back
    if net_pos.max() > 0.01:
        _draw_bars(axes[2], elevs, net_pos, "steelblue",
                   title="Net Water Pressure\n[kN/m²]", direction="left",
                   label="Back > Front")
    if net_neg.max() > 0.01:
        _draw_bars(axes[2], elevs, net_neg, "#1a8cff",
                   title="Net Water Pressure\n[kN/m²]", direction="right",
                   label="Front > Back")
    axes[2].set_title("Net Water Pressure\n[kN/m²]", fontsize=8)

    # --- Resultants (lực tổng hợp)
    F_back, z_back   = resultant(elevs, p_back)
    F_front, z_front = resultant(elevs, p_front)
    F_net,  z_net    = resultant(elevs, p_net)

    _annotate_resultant(axes[0], F_front, z_front, "left",  "#1a8cff")
    _annotate_resultant(axes[1], F_back,  z_back,  "right", "steelblue")
    _annotate_resultant(axes[2], F_net,   z_net,
                        "left" if F_net >= 0 else "right",
                        "steelblue" if F_net >= 0 else "#1a8cff")

    # --- Reference lines
    ref_lines = [
        (geom.top_elev,         "#555",      "--", 0.8, f"SP Top  {geom.top_elev:.2f} m"),
        (geom.water_elev_front, "#1a8cff",   "-.", 1.2, f"WL Front {geom.water_elev_front:.2f} m"),
        (geom.water_elev_back,  "steelblue", ":",  1.2, f"WL Back  {geom.water_elev_back:.2f} m"),
        (geom.soil_level_front, "#8B6914",   "--", 0.8, f"Exc.     {geom.soil_level_front:.2f} m"),
        (geom.bot_elev,         "#444",      "-",  0.8, f"Pile Tip {geom.bot_elev:.2f} m"),
    ]
    for ax in axes:
        for elev, color, ls, lw, lbl in ref_lines:
            ax.axhline(elev, color=color, lw=lw, ls=ls, alpha=0.7)
        if layer_elevs:
            for le in layer_elevs:
                ax.axhline(le, color="#bbb", lw=0.5, ls="--")
        ax.set_ylim(y_range)
        ax.yaxis.set_minor_locator(AutoMinorLocator())
        ax.tick_params(axis="both", labelsize=7)
        ax.grid(axis="y", lw=0.3, color="#eee")
        ax.axvline(0, color="black", lw=0.8)

    axes[0].set_ylabel("Elevation [m]", fontsize=8)

    # Legend ở panel 3
    legend_patches = [
        plt.Line2D([0], [0], color=c, lw=lw, ls=ls, label=lbl)
        for _, c, ls, lw, lbl in ref_lines
    ]
    axes[2].legend(handles=legend_patches, fontsize=6, loc="lower right",
                   framealpha=0.6)

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


def _draw_bars(
    ax: plt.Axes,
    elevs: np.ndarray,
    values: np.ndarray,
    color: str,
    title: str,
    direction: str = "left",
    label: str = "",
    arrow_spacing: float = 2.0,
) -> None:
    sign = -1 if direction == "left" else 1
    ax.fill_betweenx(elevs, 0, sign * values, color=color, alpha=0.18, label=label or None)
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


def _annotate_resultant(
    ax: plt.Axes,
    F: float,
    z: float,
    direction: str,
    color: str,
) -> None:
    if abs(F) < 0.1:
        return
    x_lim = ax.get_xlim()
    x_pos = x_lim[0] * 0.65 if direction == "left" else x_lim[1] * 0.65
    ax.annotate(
        f"U = {abs(F):.1f} kN/m",
        xy=(0, z), xycoords="data",
        xytext=(x_pos, z),
        fontsize=6.5, color=color, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=color, lw=0.8),
        va="center",
    )


# ---------------------------------------------------------------------------
# Convenience wrapper: tính cả hydrostatic và seepage, trả về dict kết quả
# ---------------------------------------------------------------------------

def compute_all(
    geom: WaterGeometry,
    mode: str = "hydrostatic",
    layer_elevs: list[float] | None = None,
) -> dict:
    """Tính toán đầy đủ và trả về dict kết quả.

    Args:
        geom:  WaterGeometry
        mode:  "hydrostatic" hoặc "seepage" (Terzaghi simplified)
        layer_elevs: cao độ ranh giới lớp đất (để vẽ đường kẻ trên biểu đồ)

    Returns dict gồm:
        elevs, p_back, p_front, p_net,
        F_back, z_back, F_front, z_front, F_net, z_net,
        fig (matplotlib Figure)
    """
    elevs = build_elevation_grid(geom)

    if mode == "seepage" and geom.head_diff > 0:
        p_back  = seepage_back(geom, elevs)
        p_front = seepage_front(geom, elevs)
        mode_label = "Seepage — Terzaghi Simplified"
    else:
        p_back  = hydrostatic_back(geom, elevs)
        p_front = hydrostatic_front(geom, elevs)
        mode_label = "Hydrostatic"

    p_net = net_water_pressure(p_back, p_front)

    F_back,  z_back  = resultant(elevs, p_back)
    F_front, z_front = resultant(elevs, p_front)
    F_net,   z_net   = resultant(elevs, np.abs(p_net))

    fig = plot_water_diagram(
        geom, elevs, p_back, p_front, p_net,
        layer_elevs=layer_elevs,
        title=f"Water Pressure — {mode_label}  "
              f"(WL Back={geom.water_elev_back:.2f} m, Front={geom.water_elev_front:.2f} m)",
    )

    return {
        "elevs": elevs,
        "p_back": p_back,
        "p_front": p_front,
        "p_net": p_net,
        "F_back": F_back,   "z_back": z_back,
        "F_front": F_front, "z_front": z_front,
        "F_net": F_net,     "z_net": z_net,
        "mode": mode_label,
        "fig": fig,
    }


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    geom = WaterGeometry(
        top_elev=2.7,
        pile_length=29.0,
        soil_level_front=0.0,
        water_elev_front=0.0,
        water_elev_back=2.7,
    )

    print(f"Head difference : {geom.head_diff:.2f} m")
    print(f"Embedment depth : {geom.embedment:.2f} m")
    print(f"Pile tip elev.  : {geom.bot_elev:.2f} m")
    print()

    for mode in ("hydrostatic", "seepage"):
        res = compute_all(geom, mode=mode)
        print(f"=== {res['mode']} ===")
        print(f"  F_back  = {res['F_back']:.1f} kN/m  at elev {res['z_back']:.2f} m")
        print(f"  F_front = {res['F_front']:.1f} kN/m  at elev {res['z_front']:.2f} m")
        print(f"  F_net   = {res['F_net']:.1f} kN/m  at elev {res['z_net']:.2f} m")
        out = f"water_pressure_{mode}_demo.png"
        res["fig"].savefig(out, dpi=110, bbox_inches="tight")
        print(f"  Saved: {out}")
        print()
