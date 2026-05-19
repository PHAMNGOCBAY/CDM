"""
Helper module cho tab Slope Stability trong app_coc_tai_ngang.py.
Dung geotech-staff-engineer slope_stability (Bishop / Spencer / Morgenstern-Price).

Import:
    from tab_slope_stability import build_surface_points, run_slope_stability, plot_slope
"""
from __future__ import annotations
import math
from typing import Optional
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

try:
    from slope_stability import (
        analyze_slope, search_critical_surface,
        SlopeGeometry, SlopeSoilLayer,
    )
    _HAS_SS = True
except ImportError:
    _HAS_SS = False


def available() -> bool:
    return _HAS_SS


def build_surface_points(
    slope_height: float,
    slope_angle_deg: float,
    crest_width: float = 10.0,
    toe_offset: float = 5.0,
) -> list[tuple[float, float]]:
    """Tao list surface_points tu thong so hinh hoc mai doc.

    Tra ve [(x, y), ...] theo thu tu trai sang phai:
        (0, 0)  — chan mai (toe)
        (toe_offset, 0)
        (toe_offset + horiz, H)  — dinh mai (crest)
        (toe_offset + horiz + crest_width, H)  — sau dinh

    Parameters
    ----------
    slope_height    : chieu cao mai [m]
    slope_angle_deg : goc nghieng mat mai so voi phuong ngang [deg]
    crest_width     : chieu rong mat bang sau dinh [m]
    toe_offset      : khoang phang truoc chan mai [m]
    """
    horiz = slope_height / math.tan(math.radians(slope_angle_deg))
    pts = [
        (0.0,                              0.0),
        (toe_offset,                        0.0),
        (toe_offset + horiz,               slope_height),
        (toe_offset + horiz + crest_width, slope_height),
    ]
    return pts


def _build_geom(surface_pts, layers_app):
    """Tao SlopeGeometry tu surface_points va layers tu app.

    layers_app: [(name, zt, zb, gamma, phi, stype, su, eps50), ...]
    """
    if not _HAS_SS:
        return None, []

    # Xac dinh elevation range
    y_vals = [y for _, y in surface_pts]
    H_max = max(y_vals)

    ss_layers = []
    for i, item in enumerate(layers_app):
        name, zt, zb, gamma, phi, stype, su, *_ = item
        is_clay = str(stype).strip().lower() == "clay"
        # top_elevation va bottom_elevation la cao do tuyet doi (dung z cua app)
        # Nhung SlopeSoilLayer can theo toa do cua surface_points
        # Gia su dat lai: lop dau tien la tu H_max den 0, lop sau tiep tuc
        # Giu nguyen gia tri z tu app (elevation positive upward)
        ss_layers.append(SlopeSoilLayer(
            name=name,
            top_elevation=float(zt),
            bottom_elevation=float(zb),
            gamma=float(gamma),
            phi=0.0 if is_clay else float(phi),
            c_prime=0.0 if is_clay else 0.0,
            cu=float(su) if is_clay else 0.0,
            analysis_mode="undrained" if is_clay else "drained",
        ))

    if not ss_layers:
        # Mac dinh: 1 lop dat dong nhat
        ss_layers.append(SlopeSoilLayer(
            name="Soil", top_elevation=H_max, bottom_elevation=-H_max,
            gamma=18.0, phi=25.0, c_prime=5.0,
        ))

    geom = SlopeGeometry(surface_points=surface_pts, soil_layers=ss_layers)
    return geom, ss_layers


def run_slope_stability(
    slope_height: float,
    slope_angle_deg: float,
    crest_width: float = 10.0,
    toe_offset: float = 5.0,
    layers_app: list = None,
    method: str = "bishop",
    search: bool = True,
    n_circles: int = 50,
    xc: Optional[float] = None,
    yc: Optional[float] = None,
    R:  Optional[float] = None,
) -> dict:
    """Chay phan tich on dinh mai doc.

    Parameters
    ----------
    slope_height, slope_angle_deg, crest_width, toe_offset : hinh hoc mai doc
    layers_app : danh sach layer tu _get_front_layers() cua app
    method     : 'bishop' | 'spencer' | 'fellenius'
    search     : True = tu dong tim mat truot toi han (search_critical_surface)
                 False = dung xc/yc/R do nguoi dung cung cap
    n_circles  : so mat truot thu khi search=True
    xc, yc, R  : tam va ban kinh mat truot (khi search=False)

    Returns
    -------
    dict: FOS, method, xc, yc, R, surface_pts, error
    """
    if not _HAS_SS:
        return {"error": "Thu vien slope_stability chua duoc cai dat."}

    surface_pts = build_surface_points(slope_height, slope_angle_deg,
                                       crest_width, toe_offset)
    layers_app = layers_app or []
    geom, _ = _build_geom(surface_pts, layers_app)

    try:
        if search or xc is None:
            sr = search_critical_surface(geom=geom, method=method,
                                         n_circles=n_circles)
            best_xc = sr.xc
            best_yc = sr.yc
            best_R  = sr.radius
            fos     = sr.FOS
            slip_pts = getattr(sr, "slip_points", None)
        else:
            r = analyze_slope(geom=geom, xc=xc, yc=yc, radius=R,
                              method=method, compare_methods=True)
            best_xc = xc
            best_yc = yc
            best_R  = R
            fos     = r.FOS
            slip_pts = getattr(r, "slip_points", None)

        result = {
            "FOS": round(fos, 3),
            "method": method,
            "xc": round(best_xc, 2),
            "yc": round(best_yc, 2),
            "R":  round(best_R, 2),
            "surface_pts": surface_pts,
            "slip_pts": slip_pts,
            "fos_check": "Dat" if fos >= 1.5 else "Khong dat",
        }
        if not search and xc is not None:
            r_full = analyze_slope(geom=geom, xc=xc, yc=yc, radius=R,
                                   method=method, compare_methods=True)
            for attr in ("FOS_fellenius", "FOS_bishop", "FOS_spencer",
                         "FOS_morgenstern_price"):
                v = getattr(r_full, attr, None)
                if v is not None:
                    result[attr] = round(v, 3)
        return result

    except Exception as e:
        return {"error": str(e)}


def plot_slope(r: dict) -> plt.Figure:
    """Ve mat cat mai doc voi duong truot toi han va FoS."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_facecolor("#f0f4f8")

    surface_pts = r.get("surface_pts", [(0, 0), (5, 0), (19, 8), (29, 8)])
    xs = [p[0] for p in surface_pts]
    ys = [p[1] for p in surface_pts]

    # Mat dat
    ax.fill_between(xs, [-2] * len(xs), ys, color="#c8a96e", alpha=0.55,
                    label="Dat")
    ax.plot(xs, ys, "k-", lw=2.0, label="Mat cat")

    # Duong truot (vong tron)
    xc  = r.get("xc", 0)
    yc  = r.get("yc", 10)
    R   = r.get("R", 12)
    FOS = r.get("FOS", 0)

    slip_pts = r.get("slip_pts")
    if slip_pts:
        sx = [p[0] for p in slip_pts]
        sy = [p[1] for p in slip_pts]
        ax.plot(sx, sy, "r-", lw=2.0, label=f"Mat truot toi han  FoS={FOS:.3f}")
        ax.fill(sx, sy, alpha=0.06, color="red")
    else:
        # Phat mat vong tron don gian neu khong co slip_pts
        theta = np.linspace(0, 2 * math.pi, 200)
        cx = xc + R * np.cos(theta)
        cy = yc + R * np.sin(theta)
        # Chi ve phan ben duoi mat dat
        mask = cy <= np.interp(cx, xs, ys)
        if np.any(mask):
            ax.plot(cx[mask], cy[mask], "r-", lw=2.0,
                    label=f"Mat truot  FoS={FOS:.3f}")

    # FoS annotation
    fos_color = "#27ae60" if FOS >= 1.5 else "#e74c3c"
    ax.text(0.02, 0.97,
            f"FoS ({r.get('method','bishop').capitalize()}) = {FOS:.3f}\n"
            f"  [{r.get('fos_check','')}]  (YC >= 1.50)",
            transform=ax.transAxes,
            fontsize=11, fontweight="bold", color=fos_color,
            va="top", ha="left",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=fos_color, alpha=0.85))

    ax.set_xlabel("x [m]")
    ax.set_ylabel("Elevation [m]")
    ax.set_title("On dinh mai doc — phuong phap gioi han can bang")
    ax.legend(fontsize=9, loc="upper right")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    return fig
