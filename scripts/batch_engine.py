"""batch_engine.py — Callable calculation engines for batch/parametric runs.

Không import Streamlit. Nhận inputs dưới dạng plain dict + DataFrame.
Được gọi từ tab Compare → Batch Run loop.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Any

# ── Axial pile BC ──────────────────────────────────────────────────────────────

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


def run_bc(
    pile_width_m: float,
    pile_length_m: float,
    gwt_depth_from_top: float,
    soil_df: pd.DataFrame,          # columns: Depth Bottom [m], Soil Type,
                                    #   Unit Weight [kN/m³], Phi [°], Cohesion [kN/m²]
    tip_correction: float = 1.0,
    fos: float = 3.0,
    shape: str = "square",
) -> dict[str, Any]:
    """Tính Q_allow cho tất cả 4 phương pháp tại pile_length_m.

    Returns dict: {method: {Q_skin, Q_tip, Q_ult, Q_allow}} or {method: {error: str}}
    Trả thêm "best_Q_allow" = Q_allow của method "auto".
    """
    if not _HAS_AXIAL:
        return {"error": "axial_pile not installed"}

    df = soil_df.dropna(subset=["Depth Bottom [m]"]).copy()
    df = df.sort_values("Depth Bottom [m]").reset_index(drop=True)
    if df.empty:
        return {"error": "Empty soil profile"}

    depth_tops  = [0.0] + df["Depth Bottom [m]"].tolist()[:-1]
    thicknesses = [float(row["Depth Bottom [m]"]) - depth_tops[i]
                   for i, row in df.iterrows()]

    try:
        axial_layers = [
            AxialSoilLayer(
                thickness=max(0.1, thicknesses[i]),
                soil_type=str(row["Soil Type"]),
                unit_weight=float(row["Unit Weight [kN/m³]"]),
                friction_angle=float(row["Phi [°]"]),
                cohesion=float(row.get("Cohesion [kN/m²]", 0.0)),
                description=str(row.get("Description", "")),
            )
            for i, row in df.iterrows()
        ]
        sp_obj = AxialSoilProfile(layers=axial_layers, gwt_depth=gwt_depth_from_top)
        pile   = make_concrete_pile(width=pile_width_m, shape=shape)
    except Exception as e:
        return {"error": f"Profile build: {e}"}

    out: dict[str, Any] = {}
    for method in ("auto", "nordlund", "tomlinson", "beta"):
        try:
            ana = AxialPileAnalysis(
                pile=pile, soil=sp_obj,
                pile_length=pile_length_m,
                method=method, factor_of_safety=fos,
            )
            res = ana.compute()
            Q_tip_c = res.Q_tip * tip_correction
            Q_ult   = res.Q_skin + Q_tip_c
            out[method] = {
                "Q_skin":  round(float(res.Q_skin), 1),
                "Q_tip":   round(float(Q_tip_c),    1),
                "Q_ult":   round(float(Q_ult),       1),
                "Q_allow": round(float(Q_ult / fos), 1),
            }
        except Exception as e:
            out[method] = {"error": str(e)}

    auto_entry = out.get("auto", {})
    out["best_Q_allow"] = auto_entry.get("Q_allow") if "error" not in auto_entry else None
    return out


# ── Slope stability ────────────────────────────────────────────────────────────

try:
    from slope_stability import SlopeGeometry, SlopeSoilLayer, analyze_slope
    _HAS_SLOPE = True
except ImportError:
    _HAS_SLOPE = False


def run_slope(
    top_elev: float,
    soil_level_front: float,
    soil_level_back: float,
    pile_length: float,
    slope_ratio: float,
    slope_soil_df: pd.DataFrame,    # columns: Top Elev [m], Bottom Elev [m],
                                    #   γ [kN/m³], φ [°], c' [kN/m²], Su [kN/m²], Mode
    xc_min: float  = -12.0,
    xc_max: float  =  10.0,
    yc_min: float  =   5.0,
    yc_max: float  =  25.0,
    nx: int        =  6,
    ny: int        =  6,
    n_slices: int  =  30,
    surcharge: float = 0.0,
    kh: float       = 0.0,
) -> dict[str, Any]:
    """Tính FOS cho tất cả 4 phương pháp.

    Returns: {method: {FOS, xc, yc, R, stable}} or {method: {error: str}}
    Trả thêm "min_FOS" = FOS nhỏ nhất trong các phương pháp hợp lệ.
    """
    if not _HAS_SLOPE:
        return {"error": "slope_stability not installed"}

    pile_tip_z = top_elev - pile_length
    sf         = soil_level_front
    sb         = soil_level_back
    te         = top_elev
    fill_h     = te - sf
    slope_x    = -(fill_h * slope_ratio) if fill_h > 0.05 else 0.0

    # Reach tự động
    reach = _required_reach(xc_min, xc_max, yc_min, yc_max, pile_tip_z, sf)
    if fill_h > 0.05:
        surface_pts = [(-reach, sf), (slope_x, sf), (0.0, te), (reach, sb)]
    else:
        surface_pts = [(-reach, sf), (0.0, te), (reach, sb)]

    df = slope_soil_df.dropna(subset=["Top Elev [m]", "Bottom Elev [m]", "γ [kN/m³]"]).copy()
    if df.empty:
        return {"error": "Empty slope soil profile"}

    try:
        slope_layers = [
            SlopeSoilLayer(
                name=str(row.get("Name", f"L{i}")),
                top_elevation=float(row["Top Elev [m]"]),
                bottom_elevation=float(row["Bottom Elev [m]"]),
                gamma=float(row["γ [kN/m³]"]),
                phi=float(row.get("φ [°]",     0.0)),
                c_prime=float(row.get("c' [kN/m²]", 0.0)),
                cu=float(row.get("Su [kN/m²]", 0.0)),
                analysis_mode=str(row.get("Mode", "drained")),
            )
            for i, row in df.iterrows()
        ]
        geom = SlopeGeometry(
            surface_points=surface_pts,
            soil_layers=slope_layers,
            surcharge=surcharge,
            kh=kh,
        )
    except Exception as e:
        return {"error": f"Geometry build: {e}"}

    xc_vals = np.linspace(xc_min, xc_max, nx)
    yc_vals = np.linspace(yc_min, yc_max, ny)
    out: dict[str, Any] = {}

    for method in ("bishop", "fellenius", "spencer", "morgenstern_price"):
        best_FOS = float("inf")
        best_res = None
        for xci in xc_vals:
            for yci in yc_vals:
                R_i = float(np.sqrt(xci**2 + (yci - pile_tip_z)**2))
                if R_i < 1.0:
                    continue
                try:
                    res_i = analyze_slope(
                        geom, xc=xci, yc=yci, radius=R_i,
                        method=method, n_slices=n_slices,
                    )
                    if res_i.FOS < best_FOS:
                        best_FOS = res_i.FOS
                        best_res = res_i
                except Exception:
                    pass
        if best_res is not None:
            out[method] = {
                "FOS":    round(float(best_res.FOS), 4),
                "xc":     round(float(best_res.xc),     2),
                "yc":     round(float(best_res.yc),     2),
                "R":      round(float(best_res.radius), 2),
                "stable": bool(best_res.is_stable),
            }
        else:
            out[method] = {"error": "No valid circle — expand search grid"}

    valid_fos = [v["FOS"] for v in out.values() if "FOS" in v]
    out["min_FOS"] = round(min(valid_fos), 4) if valid_fos else None
    return out


# ── Batch parameter catalog ────────────────────────────────────────────────────

# (type, session_key_or_df_key, column_name, display_unit, needs_row_index)
PARAM_CATALOG: dict[str, tuple] = {
    # Scalars
    "Pile Length [m]":           ("scalar", "L_m",                None,                 "m",       False),
    "Pile Top Level [m]":        ("scalar", "top_elev",           None,                 "m",       False),
    "GWT Front [m]":             ("scalar", "water_level",        None,                 "m",       False),
    "GWT Back [m]":              ("scalar", "water_level_back",   None,                 "m",       False),
    "Fill Slope H:V":            ("scalar", "fill_slope_hv",      None,                 "",        False),
    "Fill Phi [°]":              ("scalar", "phi_fill",           None,                 "°",       False),
    "Fill Cohesion [kN/m²]":     ("scalar", "c_fill",            None,                 "kN/m²",   False),
    "BC FOS":                    ("scalar", "bc_fos",             None,                 "",        False),
    # Bearing capacity soil table
    "BC Soil Depth Bottom [m]":  ("df", "bc_soil_df", "Depth Bottom [m]",  "m",       True),
    "BC Soil Phi [°]":           ("df", "bc_soil_df", "Phi [°]",           "°",       True),
    "BC Soil Cohesion [kN/m²]":  ("df", "bc_soil_df", "Cohesion [kN/m²]", "kN/m²",   True),
    "BC Soil Unit Weight":       ("df", "bc_soil_df", "Unit Weight [kN/m³]","kN/m³",  True),
    # Front sand (p-y)
    "Sand Layer Tip [m]":        ("df", "front_sand_df", "Layer Tip [m]",  "m",       True),
    "Sand Phi [°]":              ("df", "front_sand_df", "Phi [Deg]",      "°",       True),
    "Sand Density [kN/m³]":      ("df", "front_sand_df", "Density Moist [kN/m3]","kN/m³", True),
    # Front clay (p-y)
    "Clay Layer Tip [m]":        ("df", "front_clay_df", "Layer Tip [m]",  "m",       True),
    "Clay Su [kN/m²]":           ("df", "front_clay_df", "Su [kN/m2]",    "kN/m²",   True),
    "Clay Density [kN/m³]":      ("df", "front_clay_df", "Density Moist [kN/m3]","kN/m³", True),
    # Slope stability soil table
    "Slope Layer Bot Elev [m]":  ("df", "slope_soil_df", "Bottom Elev [m]","m",       True),
    "Slope Layer Top Elev [m]":  ("df", "slope_soil_df", "Top Elev [m]",   "m",       True),
    "Slope Layer Phi [°]":       ("df", "slope_soil_df", "φ [°]",          "°",       True),
    "Slope Layer Su [kN/m²]":    ("df", "slope_soil_df", "Su [kN/m²]",    "kN/m²",   True),
    "Slope Layer Cohesion [kN/m²]": ("df","slope_soil_df","c' [kN/m²]",  "kN/m²",   True),
    "Slope Layer Thickness [m]": ("df_thickness", "slope_soil_df", None,   "m",       True),
}

PARAM_NAMES = list(PARAM_CATALOG.keys())


# ── Value parser ───────────────────────────────────────────────────────────────

def parse_values(s: str) -> list[float]:
    """Parse "1,2,3" or "start:stop:step" into list of floats."""
    s = s.strip()
    if not s:
        return []
    if ":" in s:
        parts = [float(x) for x in s.split(":")]
        if len(parts) == 2:
            start, stop = parts; step = 1.0
        elif len(parts) == 3:
            start, stop, step = parts
        else:
            raise ValueError(f"Format sai: dùng start:stop:step (VD: 15:25:2)")
        vals = list(np.arange(start, stop + step * 0.001, step))
        return [round(v, 6) for v in vals]
    return [float(x.strip()) for x in s.split(",") if x.strip()]


# ── Session override helpers ───────────────────────────────────────────────────

def apply_overrides(
    base_scalars: dict,
    base_dfs: dict[str, pd.DataFrame],
    overrides: list[dict],          # list of {param_name, row_idx, value}
) -> tuple[dict, dict[str, pd.DataFrame]]:
    """Tạo bản sao scalars + dfs với các overrides áp dụng."""
    scalars = dict(base_scalars)
    dfs     = {k: v.copy() for k, v in base_dfs.items()}

    for ov in overrides:
        pname = ov["param_name"]
        val   = float(ov["value"])
        if pname not in PARAM_CATALOG:
            continue
        ptype, key, col, unit, needs_row = PARAM_CATALOG[pname]

        if ptype == "scalar":
            scalars[key] = val

        elif ptype == "df":
            df = dfs.get(key)
            if df is None or df.empty:
                continue
            row_idx = int(ov.get("row_idx", 0))
            if row_idx < len(df) and col in df.columns:
                dfs[key] = dfs[key].copy()
                dfs[key].at[row_idx, col] = val

        elif ptype == "df_thickness":
            # Thay đổi chiều dày lớp: dịch chuyển Bottom Elev của lớp row_idx
            # và điều chỉnh Top Elev của lớp row_idx+1 theo
            df = dfs.get(key)
            if df is None or df.empty:
                continue
            row_idx = int(ov.get("row_idx", 0))
            if row_idx >= len(df):
                continue
            top_r = float(df.at[row_idx, "Top Elev [m]"])
            new_bot = top_r - val          # val = chiều dày mới
            dfs[key] = dfs[key].copy()
            dfs[key].at[row_idx, "Bottom Elev [m]"] = new_bot
            # Cập nhật Top Elev lớp tiếp theo
            if row_idx + 1 < len(df):
                dfs[key].at[row_idx + 1, "Top Elev [m]"] = new_bot

    return scalars, dfs


# ── Helpers nội bộ ────────────────────────────────────────────────────────────

def _required_reach(
    xc_min: float, xc_max: float,
    yc_min: float, yc_max: float,
    pile_tip_z: float, sf: float,
    margin: float = 1.3,
) -> float:
    worst = 0.0
    for xc in [xc_min, xc_max]:
        for yc in [yc_min, yc_max]:
            R_i = np.sqrt(xc**2 + (yc - pile_tip_z)**2)
            h   = yc - sf
            if R_i > abs(h):
                half_chord = np.sqrt(R_i**2 - h**2)
                worst = max(worst, abs(xc) + half_chord)
    return max(worst * margin, 40.0)
