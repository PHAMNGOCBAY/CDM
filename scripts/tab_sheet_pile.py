"""
Helper module cho tab Sheet Pile Design trong app_coc_tai_ngang.py.
Dung geotech-staff-engineer sheet_pile + soe (USACE EM 1110-2-2504).

Import:
    from tab_sheet_pile import run_cantilever, run_anchored, run_basal_heave, plot_sheet_pile_result
"""
from __future__ import annotations
from typing import Optional
import numpy as np
import matplotlib.pyplot as plt

try:
    from sheet_pile import (
        analyze_cantilever, analyze_anchored, WallSoilLayer,
        rankine_Ka, rankine_Kp, active_pressure, passive_pressure,
    )
    _HAS_SP = True
except ImportError:
    _HAS_SP = False

try:
    from soe import check_basal_heave_terzaghi, check_basal_heave_bjerrum_eide
    _HAS_SOE = True
except ImportError:
    _HAS_SOE = False


def available() -> bool:
    return _HAS_SP


def _to_wall_layers(layers: list) -> list:
    """Chuyen danh sach layer tu app (name,zt,zb,gamma,phi,stype,su,eps50)
    sang list WallSoilLayer, voi thickness = zt - zb."""
    out = []
    for item in layers:
        name, zt, zb, gamma, phi, stype, su, *_ = item
        thickness = abs(float(zt) - float(zb))
        if thickness < 0.01:
            continue
        # Set phi=0 cho clay (pure cohesive); su dung lam cohesion
        is_clay = str(stype).strip().lower() == "clay"
        out.append(WallSoilLayer(
            thickness=thickness,
            unit_weight=float(gamma),
            friction_angle=0.0 if is_clay else float(phi),
            cohesion=float(su) if is_clay else 0.0,
        ))
    return out


def run_cantilever(
    excavation_depth: float,
    front_layers: list,
    gwt_active: Optional[float] = None,
    gwt_passive: Optional[float] = None,
    surcharge: float = 0.0,
    fos_passive: float = 1.5,
) -> dict:
    """Phan tich tuong consolle theo Rankine.

    Parameters
    ----------
    excavation_depth : chieu sau dao [m]
    front_layers     : tu _get_front_layers() hoac _get_back_layers() cua app
    gwt_active       : chieu sau MNN phia chu dong [m], None = khong co
    gwt_passive      : chieu sau MNN phia bi dong [m], None = khong co
    surcharge        : tai phan bo mat dat [kPa]
    fos_passive      : he so an toan cho ap luc bi dong

    Returns
    -------
    dict: embedment_depth, total_wall_length, max_moment, max_moment_depth, FOS_passive, error
    """
    if not _HAS_SP:
        return {"error": "Thu vien sheet_pile chua duoc cai dat."}

    wl = _to_wall_layers(front_layers)
    if not wl:
        return {"error": "Khong co lop dat hop le."}

    try:
        r = analyze_cantilever(
            excavation_depth=excavation_depth,
            soil_layers=wl,
            gwt_depth_active=gwt_active,
            gwt_depth_passive=gwt_passive,
            surcharge=surcharge,
            FOS_passive=fos_passive,
        )
        return {
            "type": "cantilever",
            "excavation_depth": excavation_depth,
            "embedment_depth":   round(r.embedment_depth, 2),
            "total_wall_length": round(r.total_wall_length, 2),
            "max_moment":        round(r.max_moment, 1),
            "max_moment_depth":  round(r.max_moment_depth, 2),
            "FOS_passive":       round(r.FOS_passive, 2),
            "anchor_force":      None,
        }
    except Exception as e:
        return {"error": str(e)}


def run_anchored(
    excavation_depth: float,
    anchor_depth: float,
    front_layers: list,
    gwt_active: Optional[float] = None,
    gwt_passive: Optional[float] = None,
    surcharge: float = 0.0,
    fos_passive: float = 1.5,
) -> dict:
    """Phan tich tuong co neo.

    Parameters
    ----------
    anchor_depth : chieu sau neo tu mat dat phia chu dong [m]
    """
    if not _HAS_SP:
        return {"error": "Thu vien sheet_pile chua duoc cai dat."}

    wl = _to_wall_layers(front_layers)
    if not wl:
        return {"error": "Khong co lop dat hop le."}

    try:
        r = analyze_anchored(
            excavation_depth=excavation_depth,
            anchor_depth=anchor_depth,
            soil_layers=wl,
            gwt_depth_active=gwt_active,
            gwt_depth_passive=gwt_passive,
            surcharge=surcharge,
            FOS_passive=fos_passive,
        )
        anchor_force = getattr(r, "anchor_force", None)
        return {
            "type": "anchored",
            "excavation_depth": excavation_depth,
            "anchor_depth":      anchor_depth,
            "embedment_depth":   round(r.embedment_depth, 2),
            "total_wall_length": round(r.total_wall_length, 2),
            "max_moment":        round(r.max_moment, 1),
            "max_moment_depth":  round(r.max_moment_depth, 2),
            "FOS_passive":       round(r.FOS_passive, 2),
            "anchor_force":      round(anchor_force, 1) if anchor_force is not None else None,
        }
    except Exception as e:
        return {"error": str(e)}


def run_basal_heave(
    H: float,
    cu: float,
    gamma: float,
    B: float = 0.0,
    q_surcharge: float = 0.0,
) -> dict:
    """Kiem tra on dinh day ho dao (basal heave) theo Terzaghi.

    Parameters
    ----------
    H           : chieu sau ho dao [m]
    cu          : suc chong cat khong thoat nuoc [kPa]
    gamma       : dung trong dat [kN/m3]
    B           : chieu rong ho dao [m]
    q_surcharge : tai phan bo mat dat [kPa]
    """
    if not _HAS_SOE:
        return {"error": "Thu vien soe chua duoc cai dat."}
    try:
        r = check_basal_heave_terzaghi(H=H, cu=cu, gamma=gamma,
                                        q_surcharge=q_surcharge, B=B)
        result = {
            "method": "Terzaghi (1943)",
            "FOS":          round(r.FOS, 2),
            "FOS_required": r.FOS_required,
            "passes":       r.passes,
        }
        try:
            r2 = check_basal_heave_bjerrum_eide(H=H, cu=cu, gamma=gamma,
                                                  q_surcharge=q_surcharge, B=B)
            result["FOS_bjerrum_eide"] = round(r2.FOS, 2)
            result["passes_bjerrum_eide"] = r2.passes
        except Exception:
            pass
        return result
    except Exception as e:
        return {"error": str(e)}


def plot_sheet_pile_result(r: dict) -> plt.Figure:
    """Ve so do tuong: ap luc dat + ket qua."""
    fig, ax = plt.subplots(figsize=(5, 7))
    ax.set_facecolor("#f8f9fa")

    exc = r.get("excavation_depth", 3.0)
    emb = r.get("embedment_depth",  2.0)
    L   = r.get("total_wall_length", exc + emb)
    M_max = r.get("max_moment", 0.0)
    z_M   = r.get("max_moment_depth", exc * 0.5)

    # Coc ban (tuong)
    ax.fill_betweenx([-L, 0], [-0.15, -0.15], [0.15, 0.15],
                     color="#7f8c8d", alpha=0.6, label="Wall")

    # Vung dao
    ax.fill_betweenx([0, -exc], [-3, -3], [0, 0],
                     color="#aed6f1", alpha=0.3, label="Excavation")
    ax.axhline(0, color="#2c3e50", lw=1.0, ls="-")     # mat dat truoc dao
    ax.axhline(-exc, color="#e74c3c", lw=1.5, ls="--",
               label=f"Excavation {exc} m")

    # Mui coc
    ax.axhline(-L, color="#2c3e50", lw=1.0, ls="-")
    ax.text(0.2, -L + 0.15, f"Tip  z={-L:.1f} m", fontsize=8, color="#2c3e50")

    # Ky hieu ngam
    ax.annotate("", xy=(0.5, -exc), xytext=(0.5, -L),
                arrowprops=dict(arrowstyle="<->", color="#c0392b", lw=1.5))
    ax.text(0.6, -(exc + emb / 2), f"Ngam\n{emb:.2f} m",
            fontsize=8, color="#c0392b", va="center")

    # Neo (neu co)
    anch_d = r.get("anchor_depth")
    anch_f = r.get("anchor_force")
    if anch_d is not None and anch_f is not None:
        ax.annotate("", xy=(0, -anch_d), xytext=(-2.5, -anch_d),
                    arrowprops=dict(arrowstyle="->", color="navy", lw=2))
        ax.text(-1.5, -anch_d - 0.3,
                f"Neo  {anch_f:.0f} kN/m", fontsize=8, color="navy")

    # Diem M_max
    ax.plot(0, -z_M, "r*", ms=10, label=f"M_max={M_max:.1f} kNm  z={z_M:.1f}m")

    ax.set_xlim(-3.5, 2.5)
    ax.set_xlabel("← Active  |  Passive →")
    ax.set_ylabel("Elevation from ground [m]")
    ax.set_title(f"Sheet Pile — {'Co neo' if r.get('type')=='anchored' else 'Consolle'}\n"
                 f"L_total={L:.2f} m   M_max={M_max:.1f} kN.m/m")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    return fig
