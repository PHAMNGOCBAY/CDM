"""
Lateral Pile Analysis — SW Prestressed Concrete (BETON 6)
UI: GEO5-style tabs | form left | live diagram right | all labels in English
Engine: openpile 1.0.2, API p-y curves (1987)
Run:  streamlit run scripts/app_coc_tai_ngang.py
v4 — 2026-05-15
  - Natural ground lines (Front / Back) at user-defined elevations
  - Fill zone (Dat dap) hatched from pile top to ground if ground > top_elev
  - Independent Front / Back soil layer tables
  - Soil Layers tab split into "Layers in Front" + "Layers behind"
"""
import sys
import os
import json
import math
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import streamlit as st

try:
    import plotly.graph_objects as go
    _HAS_PLOTLY = True
except ImportError:
    _HAS_PLOTLY = False

_TTHC_DB = Path(__file__).parent.parent / "data" / "TTHC.sqlite"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

try:
    from water_pressure import WaterGeometry as _WaterGeom, compute_all as _wp_compute_all
    _HAS_WP = True
except ImportError:
    _HAS_WP = False

try:
    from earth_pressure import (
        EpGeometry as _EpGeom,
        SoilLayer as _EpSoilLayer,
        compute_all as _ep_compute_all,
    )
    _HAS_EP = True
except ImportError:
    _HAS_EP = False

try:
    from fill_lateral_force import (
        FillGeometry as _FillGeom,
        compute_all as _fill_compute_all,
    )
    _HAS_FILL = True
except ImportError:
    _HAS_FILL = False

try:
    from boussinesq_surcharge import (
        SurchargeStrip as _BStrip,
        BoussiGeometry as _BGeom,
        compute_all as _boussi_compute_all,
    )
    _HAS_BOUSSI = True
except ImportError:
    _HAS_BOUSSI = False

try:
    from bearing_capacity_tab import render_bearing_capacity_tab as _render_bc
    _HAS_BC_TAB = True
except ImportError:
    _HAS_BC_TAB = False

try:
    from sheet_pile_tab import render_sheet_pile_tab as _render_sp
    _HAS_SP_TAB = True
except ImportError:
    _HAS_SP_TAB = False

try:
    from slope_stability_tab import render_slope_stability_tab as _render_slope
    _HAS_SLOPE_TAB = True
except ImportError:
    _HAS_SLOPE_TAB = False

try:
    from variants_db import (
        init_db as _vdb_init,
        save_variant as _vdb_save,
        list_variants as _vdb_list,
        load_variant_inputs as _vdb_load_inputs,
        delete_variant as _vdb_delete,
    )
    _vdb_init()
    _HAS_VDB = True
except Exception:
    _HAS_VDB = False

try:
    from batch_engine import (
        run_bc       as _batch_run_bc,
        run_slope    as _batch_run_slope,
        parse_values as _batch_parse,
        apply_overrides as _batch_override,
        PARAM_NAMES  as _BATCH_PARAM_NAMES,
        PARAM_CATALOG as _BATCH_CATALOG,
    )
    _HAS_BATCH = True
except Exception:
    _HAS_BATCH = False

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_md(filename: str) -> str:
    try:
        with open(os.path.join(_PROJ_DIR, filename), "r", encoding="utf-8") as _f:
            return _f.read()
    except Exception:
        return f"*{filename} not found*"


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Lateral Pile Analysis",
    page_icon=None,
    layout="wide",
)
st.markdown("""
<style>
div[data-testid="stMainBlockContainer"] { padding-top: 0.4rem; }
div[data-testid="stMetricValue"] { font-size: 1.05rem; }
</style>""", unsafe_allow_html=True)

st.markdown("## Lateral Pile Analysis — SW Prestressed Concrete (BETON 6)")
st.caption("Method: FEM 1D  |  p-y curves API (1987)  |  openpile 1.0.2")

# ── Constants ─────────────────────────────────────────────────────────────────
LAYER_COLORS = ["#fff3cd", "#d1e7dd", "#cfe2ff", "#f8d7da", "#e2d9f3", "#fde2e4"]
HATCHES      = ["///", "...", "xxx", "---", "ooo", "+++"]
TM_TO_KNM    = 9.81

CONCRETE_GRADES = {
    "f'c = 30 MPa": {"fc": 30,  "Ec_MPa": 26561,  "Ec_kNm2": 26_561_000},
    "f'c = 40 MPa": {"fc": 40,  "Ec_MPa": 31623,  "Ec_kNm2": 31_623_000},
    "f'c = 60 MPa": {"fc": 60,  "Ec_MPa": 38730,  "Ec_kNm2": 38_730_000},
    "f'c = 70 MPa": {"fc": 70,  "Ec_MPa": 43628,  "Ec_kNm2": 43_628_130},
}

# ── SW Pile catalog (BETON 6) ─────────────────────────────────────────────────
SW_CATALOG = [
    dict(name="SW-120",  H=120,  t=60,  n=8,  phi_s=9.53,  Atd=548.0,   Itd=6_514,      Mcr=1.53,  wT=0.83,  Lmin=3,  Lmax=7,  width=996),
    dict(name="SW-160",  H=160,  t=80,  n=8,  phi_s=9.53,  Atd=723.0,   Itd=15_336,     Mcr=2.04,  wT=1.30,  Lmin=4,  Lmax=8,  width=996),
    dict(name="SW-225",  H=225,  t=100, n=8,  phi_s=11.10, Atd=954.0,   Itd=42_780,     Mcr=4.28,  wT=2.38,  Lmin=5,  Lmax=9,  width=996),
    dict(name="SW-300",  H=300,  t=110, n=10, phi_s=12.70, Atd=1168.0,  Itd=101_168,    Mcr=9.58,  wT=3.38,  Lmin=7,  Lmax=12, width=996),
    dict(name="SW-350A", H=350,  t=120, n=14, phi_s=12.70, Atd=1376.0,  Itd=162_003,    Mcr=16.31, wT=5.00,  Lmin=9,  Lmax=15, width=996),
    dict(name="SW-350B", H=350,  t=120, n=16, phi_s=12.70, Atd=1385.0,  Itd=162_756,    Mcr=17.33, wT=5.38,  Lmin=10, Lmax=15, width=996),
    dict(name="SW-400A", H=400,  t=120, n=16, phi_s=12.70, Atd=1543.0,  Itd=240_449,    Mcr=20.39, wT=6.28,  Lmin=10, Lmax=16, width=996),
    dict(name="SW-400B", H=400,  t=120, n=18, phi_s=12.70, Atd=1552.0,  Itd=240_449,    Mcr=23.45, wT=6.68,  Lmin=11, Lmax=16, width=996),
    dict(name="SW-450A", H=450,  t=120, n=18, phi_s=12.70, Atd=1787.0,  Itd=341_010,    Mcr=27.52, wT=7.65,  Lmin=11, Lmax=17, width=996),
    dict(name="SW-450B", H=450,  t=120, n=16, phi_s=15.24, Atd=1808.0,  Itd=348_089,    Mcr=31.60, wT=8.13,  Lmin=12, Lmax=17, width=996),
    dict(name="SW-500A", H=500,  t=120, n=16, phi_s=15.24, Atd=1885.0,  Itd=467_240,    Mcr=35.68, wT=8.13,  Lmin=12, Lmax=19, width=996),
    dict(name="SW-500B", H=500,  t=120, n=20, phi_s=15.24, Atd=1910.0,  Itd=469_288,    Mcr=40.77, wT=8.58,  Lmin=13, Lmax=20, width=996),
    dict(name="SW-600A", H=600,  t=120, n=20, phi_s=15.24, Atd=2262.0,  Itd=795_348,    Mcr=50.97, wT=10.38, Lmin=14, Lmax=22, width=996),
    dict(name="SW-600B", H=600,  t=120, n=24, phi_s=15.24, Atd=2288.0,  Itd=797_396,    Mcr=60.14, wT=10.88, Lmin=15, Lmax=24, width=996),
    dict(name="SW-740",  H=740,  t=160, n=20, phi_s=15.24, Atd=2794.0,  Itd=1_480_428,  Mcr=60.40, wT=14.55, Lmin=16, Lmax=28, width=996),
    dict(name="SW-840",  H=840,  t=160, n=22, phi_s=15.24, Atd=3107.0,  Itd=2_125_017,  Mcr=77.10, wT=16.35, Lmin=17, Lmax=29, width=996),
    dict(name="SW-940",  H=940,  t=160, n=24, phi_s=15.24, Atd=3544.0,  Itd=2_983_488,  Mcr=93.30, wT=18.31, Lmin=17, Lmax=30, width=996),
    dict(name="SW-1100", H=1100, t=200, n=28, phi_s=15.24, Atd=5327.0,  Itd=5_663_367,  Mcr=136.0, wT=25.80, Lmin=17, Lmax=32, width=1246),
    dict(name="SW-1200", H=1200, t=200, n=30, phi_s=15.24, Atd=5789.7,  Itd=7_318_551,  Mcr=158.0, wT=28.75, Lmin=17, Lmax=34, width=1246),
]
SW_NAMES = [p["name"] for p in SW_CATALOG]

def sw_by_name(name: str) -> dict:
    return next((p for p in SW_CATALOG if p["name"] == name), SW_CATALOG[15])

def sw_plaxis(pile: dict, Ec_kNm2: float) -> dict:
    sp    = pile["width"] / 1000
    A     = pile["Atd"] / 10_000
    I     = pile["Itd"] / 1e8
    L_std = 22 if pile["name"] == "SW-840" else pile.get("Lmin", 17) + 5
    EA1   = Ec_kNm2 * A / sp
    EI    = Ec_kNm2 * I / sp
    deq   = math.sqrt(12 * EI / EA1)
    w_kNm = pile["wT"] * 9.81 / L_std / sp
    return dict(EA1=EA1, EI=EI, d_eq=deq, w=w_kNm, Mcr_kNm=pile["Mcr"] * TM_TO_KNM)


# ── Session state defaults ────────────────────────────────────────────────────
# Two separate tables per model: Sand (Phi) and Clay (Su + eps50)
_DEFAULT_FRONT_SAND_DF = pd.DataFrame({
    "Layer Tip [m]":         [-5.0, -20.0],
    "Density Moist [kN/m3]": [18.0,  19.0],
    "Density Sub [kN/m3]":   [ 8.0,   9.0],
    "Phi [Deg]":             [28.0,  32.0],
    "Su [kN/m2]":            [ 0.0,   0.0],   # locked (grey)
    "eps50":                 [0.005, 0.005],   # locked (grey)
    "Delta [Deg]":           [ 0.0,   0.0],
    "Cohesion [kN/m2]":      [ 0.0,   0.0],
})

_DEFAULT_FRONT_CLAY_DF = pd.DataFrame({
    "Layer Tip [m]":         [-10.0],
    "Density Moist [kN/m3]": [ 17.0],
    "Density Sub [kN/m3]":   [  7.0],
    "Phi [Deg]":             [  0.0],   # locked (grey)
    "Su [kN/m2]":            [ 10.0],
    "eps50":                 [ 0.020],
    "Delta [Deg]":           [  0.0],
    "Cohesion [kN/m2]":      [ 10.0],
})

_DEFAULT_BACK_LAYERS = pd.DataFrame({
    "Soil Type":             ["Sand",  "Clay"],
    "Layer Tip [m]":         [-5.0,   -15.0],
    "Density Moist [kN/m3]": [18.0,    17.0],
    "Density Sub [kN/m3]":   [ 8.0,     7.0],
    "Phi [Deg]":             [28.0,     0.0],
    "Su [kN/m2]":            [ 0.0,    10.0],
    "eps50":                 [0.005,   0.020],
    "Delta [Deg]":           [ 0.0,     0.0],
    "Cohesion [kN/m2]":      [ 0.0,    10.0],
})


def _migrate_layers_df(df: pd.DataFrame) -> pd.DataFrame:
    """Add missing columns to old DataFrames loaded from session."""
    if "Soil Type" not in df.columns:
        df = df.copy()
        df.insert(0, "Soil Type", "Sand")
    if "Su [kN/m2]" not in df.columns:
        df["Su [kN/m2]"] = 0.0
    if "eps50" not in df.columns:
        df["eps50"] = 0.005
    return df


def _migrate_to_split(combined_df: pd.DataFrame):
    """Split old combined front_layers_df into (sand_df, clay_df)."""
    _SAND_COLS = ["Layer Tip [m]", "Density Moist [kN/m3]", "Density Sub [kN/m3]",
                  "Phi [Deg]", "Su [kN/m2]", "eps50", "Delta [Deg]", "Cohesion [kN/m2]"]
    combined_df = _migrate_layers_df(combined_df)
    mask_sand = combined_df["Soil Type"].astype(str).str.lower() == "sand"
    sand = combined_df[mask_sand][[c for c in _SAND_COLS if c in combined_df.columns]].reset_index(drop=True)
    clay = combined_df[~mask_sand][[c for c in _SAND_COLS if c in combined_df.columns]].reset_index(drop=True)
    if sand.empty: sand = _DEFAULT_FRONT_SAND_DF.copy()
    if clay.empty: clay = _DEFAULT_FRONT_CLAY_DF.copy()
    return sand, clay


# ── Init split front tables ───────────────────────────────────────────────────
if "front_sand_df" not in st.session_state or "front_clay_df" not in st.session_state:
    _src = (st.session_state.get("front_layers_df")
            or st.session_state.get("layers_df"))
    if _src is not None:
        st.session_state["front_sand_df"], st.session_state["front_clay_df"] = \
            _migrate_to_split(_src)
    else:
        st.session_state["front_sand_df"] = _DEFAULT_FRONT_SAND_DF.copy()
        st.session_state["front_clay_df"] = _DEFAULT_FRONT_CLAY_DF.copy()

if "back_layers_df" not in st.session_state:
    st.session_state["back_layers_df"] = _DEFAULT_BACK_LAYERS.copy()
else:
    st.session_state["back_layers_df"] = _migrate_layers_df(st.session_state["back_layers_df"])

if "forces_df" not in st.session_state:
    st.session_state["forces_df"] = pd.DataFrame({
        "Horiz. Component [kN/m]": [100.0],
        "Vert. Component [kN/m]":  [  0.0],
        "Depth [m]":               [  0.0],
    })

if "boussinesq_df" not in st.session_state:
    st.session_state["boussinesq_df"] = pd.DataFrame({
        "Side":               ["Front"],
        "Distance Wall [m]":  [2.0],
        "Width Surcharge [m]":[5.0],
        "Depth Surcharge [m]":[0.0],
        "Surcharge [kN/m2]":  [5.0],
    })
elif "Side" not in st.session_state["boussinesq_df"].columns:
    st.session_state["boussinesq_df"].insert(0, "Side", "Front")


# ── Project save / load ───────────────────────────────────────────────────────

_PROJ_DF_KEYS = [
    "front_sand_df", "front_clay_df", "back_layers_df",
    "forces_df", "boussinesq_df", "bc_soil_df",
]
_PROJ_SCALAR_KEYS = [
    "top_elev", "soil_level_front", "soil_level_back", "L_m",
    "water_level", "water_level_back",
    "gamma_fill", "phi_fill", "c_fill", "fill_slope_hv",
    "sel_pile", "sel_pile_idx", "concrete_grade",
    "bc_pile_shape", "bc_sw_pile_sel", "bc_pile_len", "bc_gwt",
    "bc_method", "bc_fos", "bc_q_target",
    "bc_dmin", "bc_dmax", "bc_dstep",
    "bc_Qw_settle", "bc_Cp_set", "bc_s_limit",
    "bc_compare_piles", "bc_comp_len",
]
_PROJ_RESULT_KEYS = [
    "bc_result", "bc_cvd", "bc_Q_tip_c", "bc_Q_ult_c", "bc_Q_allow_c",
    "bc_tip_corr", "bc_calc_perim", "bc_calc_Atd", "bc_calc_w_kNm",
    "bc_pile_name", "bc_all_methods", "bc_comp_results",
    "result", "layers_clipped", "calc_params",
    "dist_loads_stored", "incl_dist_stored",
]


def _project_to_json() -> bytes:
    data: dict = {"_version": 2}
    for k in _PROJ_SCALAR_KEYS:
        v = st.session_state.get(k)
        if v is None:
            continue
        if hasattr(v, "item"):      # numpy scalar → Python native
            v = v.item()
        if isinstance(v, list):
            v = [x.item() if hasattr(x, "item") else x for x in v]
        data[k] = v
    for k in _PROJ_DF_KEYS:
        df = st.session_state.get(k)
        if isinstance(df, pd.DataFrame):
            data[f"_df_{k}"] = df.to_dict("records")
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def _project_from_dict(data: dict) -> None:
    for k in _PROJ_SCALAR_KEYS:
        if k in data:
            st.session_state[k] = data[k]
    for k in _PROJ_DF_KEYS:
        dk = f"_df_{k}"
        if dk in data:
            st.session_state[k] = pd.DataFrame(data[dk])


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get(key, default):
    v = st.session_state.get(key, default)
    try:
        return type(default)(v)
    except Exception:
        return default


def _enforce_soil_model_constraints(df: pd.DataFrame) -> pd.DataFrame:
    """Auto-clear parameters that don't belong to the row's soil model.

    Sand rows → Su [kN/m2] = 0, eps50 = 0.005   (phi is used)
    Clay rows → Phi [Deg]  = 0                   (Su + eps50 are used)

    This prevents the user from accidentally carrying over stale values
    from a previously different soil type in the same row.
    """
    if df is None or df.empty or "Soil Type" not in df.columns:
        return df
    df = df.copy()
    mask_sand = df["Soil Type"].astype(str).str.strip().str.lower() == "sand"
    mask_clay = ~mask_sand
    if "Su [kN/m2]" in df.columns:
        df.loc[mask_sand, "Su [kN/m2]"] = 0.0
    if "eps50" in df.columns:
        df.loc[mask_sand, "eps50"] = 0.005
    if "Phi [Deg]" in df.columns:
        df.loc[mask_clay, "Phi [Deg]"] = 0.0
    return df

def _merge_front_layers_df() -> pd.DataFrame:
    """Merge front_sand_df + front_clay_df → single sorted DataFrame for downstream."""
    sand = st.session_state.get("front_sand_df", _DEFAULT_FRONT_SAND_DF).copy()
    clay = st.session_state.get("front_clay_df", _DEFAULT_FRONT_CLAY_DF).copy()
    sand["Soil Type"] = "Sand"
    sand["Su [kN/m2]"] = 0.0
    sand["eps50"] = 0.005
    clay["Soil Type"] = "Clay"
    clay["Phi [Deg]"] = 0.0
    merged = pd.concat([sand, clay], ignore_index=True)
    merged = merged.sort_values("Layer Tip [m]", ascending=False).reset_index(drop=True)
    return merged


def _get_front_layers():
    """Return [(name, z_top, z_bot, gamma, phi, soil_type, su, eps50), ...] merged & sorted."""
    df  = _merge_front_layers_df()
    top = _get("top_elev", 0.0)
    if df.empty:
        return []
    layers = []
    prev_top = top
    for i, row in df.iterrows():
        tip       = float(row.get("Layer Tip [m]", -5.0))
        gamma     = float(row.get("Density Moist [kN/m3]", 18.0))
        phi       = float(row.get("Phi [Deg]", 28.0))
        soil_type = str(row.get("Soil Type", "Sand"))
        su        = float(row.get("Su [kN/m2]", 0.0))
        eps50     = float(row.get("eps50", 0.02))
        layers.append((f"Layer {i+1}", prev_top, tip, gamma, phi, soil_type, su, eps50))
        prev_top = tip
    return layers

def _get_back_layers():
    """Return [(name, z_top, z_bot, gamma, phi, soil_type, su, eps50), ...] from back_layers_df.
    Layer 1 top = soil_level_back (natural ground behind wall).
    """
    df  = st.session_state.get("back_layers_df", pd.DataFrame())
    top = _get("soil_level_back", 0.0)
    if df.empty:
        return []
    layers = []
    prev_top = top
    for i, row in df.iterrows():
        tip        = float(row.get("Layer Tip [m]", -5.0))
        gamma      = float(row.get("Density Moist [kN/m3]", 18.0))
        phi        = float(row.get("Phi [Deg]", 28.0))
        soil_type  = str(row.get("Soil Type", "Sand"))
        su         = float(row.get("Su [kN/m2]", 0.0))
        eps50      = float(row.get("eps50", 0.02))
        layers.append((f"Back {i+1}", prev_top, tip, gamma, phi, soil_type, su, eps50))
        prev_top = tip
    return layers


def _df_to_ep_layers(df, ref_top: float) -> list:
    """Chuyển DataFrame lớp đất sang list _EpSoilLayer cho earth_pressure.py."""
    if not _HAS_EP or df is None or (hasattr(df, "empty") and df.empty):
        return []
    layers = []
    for _, row in df.iterrows():
        tip = float(row.get("Layer Tip [m]", ref_top - 1.0))
        gm  = float(row.get("Density Moist [kN/m3]", 18.0))
        gs  = float(row.get("Density Sub [kN/m3]", gm - 10.0))
        phi = float(row.get("Phi [Deg]", 25.0))
        c   = float(row.get("Cohesion [kN/m2]", 0.0))
        layers.append(_EpSoilLayer(tip_elev=tip, gamma=gm, gamma_sub=gs, phi=phi, c=c))
    return layers



def _head_load():
    df = st.session_state.get("forces_df", pd.DataFrame())
    if df.empty:
        return 0.0, 0.0
    row0  = df.iloc[0]
    H_kN  = float(row0.get("Horiz. Component [kN/m]", 0.0))
    return H_kN, 0.0


# ── Shared column config for soil layer tables ────────────────────────────────
def _layer_col_cfg(auto_sub: bool) -> dict:
    return {
        "Soil Type": st.column_config.SelectboxColumn(
            "Soil Type", options=["Sand", "Clay"], required=True, width=80,
            help="Sand → API p-y (API 1987, phi)  |  Clay → Matlock p-y (API 1974, Su, eps50)"),
        "Layer Tip [m]": st.column_config.NumberColumn(
            "Layer Tip [m]", format="%.3f", step=0.5, width=100,
            help="Elevation at bottom of this layer (negative = below surface)"),
        "Density Moist [kN/m3]": st.column_config.NumberColumn(
            "Density Moist\n[kN/m3]", format="%.3f",
            min_value=10.0, max_value=25.0, step=0.1, width=115),
        "Density Sub [kN/m3]": st.column_config.NumberColumn(
            "Density Sub\n[kN/m3]", format="%.3f",
            min_value=0.0, max_value=15.0, step=0.1, width=110,
            disabled=auto_sub),
        "Phi [Deg]": st.column_config.NumberColumn(
            "Phi [Deg]\n(Sand)", format="%.1f",
            min_value=0.0, max_value=45.0, step=1.0, width=85,
            help="Friction angle — used only when Soil Type = Sand"),
        "Su [kN/m2]": st.column_config.NumberColumn(
            "Su [kN/m²]\n(Clay)", format="%.1f",
            min_value=0.0, max_value=500.0, step=1.0, width=95,
            help="Undrained shear strength — used only when Soil Type = Clay"),
        "eps50": st.column_config.NumberColumn(
            "ε₅₀ (Clay)", format="%.4f",
            min_value=0.001, max_value=0.10, step=0.001, width=85,
            help="Strain at 50% failure: soft clay ≈ 0.02, medium ≈ 0.01, stiff ≈ 0.005"),
        "Delta [Deg]": st.column_config.NumberColumn(
            "Delta [Deg]", format="%.3f",
            min_value=0.0, step=1.0, width=80,
            help="Interface friction angle (future use)"),
        "Cohesion [kN/m2]": st.column_config.NumberColumn(
            "Cohesion\n[kN/m2]", format="%.3f",
            min_value=0.0, step=1.0, width=90),
    }


# ── Diagram: pile schematic (GEO5 style, v4) ──────────────────────────────────
def draw_pile_schematic(
    L_m, water_lvl, top_elev, H_kN, M_kNm, layers, bc_type,
    pile_H_mm=840,
    soil_lvl_front=None,
    soil_lvl_back=None,
    back_layers=None,
    gamma_fill=18.0,
    phi_fill=25.0,
    c_fill=5.0,
    water_lvl_back=None,
):
    bot  = top_elev - L_m
    ypad = max(L_m * 0.06, 0.8)

    y_top = top_elev + ypad * 2.2
    y_bot = bot - ypad * 1.2

    fig, ax = plt.subplots(figsize=(4.5, 5.5), dpi=90)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    ax.set_xlim(-5, 5)
    ax.set_ylim(y_bot, y_top)
    ax.set_ylabel("Elevation [m]", fontsize=9)
    ax.set_xticks([])
    ax.tick_params(axis="y", labelsize=8)
    for sp in ["top", "right", "bottom"]:
        ax.spines[sp].set_visible(False)

    # ═══ FILL ZONES (drawn first, behind everything) ═══
    _fill_label = f"Fill\nγ={gamma_fill:.0f} kN/m³\nφ={phi_fill:.0f}°  c={c_fill:.0f} kPa"

    # Front fill: bottom = soil_lvl_front, top = top_elev (when top_elev > soil_lvl_front)
    if soil_lvl_front is not None and top_elev > soil_lvl_front:
        ax.fill_between(
            [-4.8, 0], [soil_lvl_front, soil_lvl_front], [top_elev, top_elev],
            color="#c8a96e", alpha=0.35, hatch="\\\\", zorder=2,
            linewidth=0.5, edgecolor="#a07040",
        )
        mid_fill_f = (soil_lvl_front + top_elev) / 2
        ax.text(-2.4, mid_fill_f, _fill_label,
                fontsize=7, color="#7a5020", ha="center", va="center",
                style="italic", linespacing=1.4)


    # ═══ NATURAL GROUND LINES ═══
    # Front ground (left side)
    if soil_lvl_front is not None:
        ax.plot([-4.8, 0], [soil_lvl_front, soil_lvl_front],
                color="saddlebrown", lw=1.8, solid_capstyle="round", zorder=6)
        ax.text(-4.8, soil_lvl_front + ypad * 0.15, "Ground F",
                fontsize=8, color="saddlebrown", va="bottom", fontweight="bold")

    # Back ground (right side)
    if soil_lvl_back is not None:
        ax.plot([0, 4.8], [soil_lvl_back, soil_lvl_back],
                color="saddlebrown", lw=1.8, solid_capstyle="round", zorder=6)
        ax.text(0.2, soil_lvl_back + ypad * 0.15, "Ground B",
                fontsize=8, color="saddlebrown", va="bottom", fontweight="bold")

    # ═══ PILE: thick red vertical line (GEO5 style) ═══
    ax.plot([0, 0], [bot, top_elev], color="red", lw=3.5,
            solid_capstyle="butt", zorder=10)

    # ═══ SP TOP marker: hollow ▽ + dashed line ═══
    ax.plot([-4.8, 5], [top_elev, top_elev], color="#888", lw=1.0, ls="--", zorder=5)
    ax.plot([-0.25], [top_elev], "v", color="#444", ms=7, zorder=11,
            markerfacecolor="none", markeredgewidth=1.5)
    ax.text(-4.8, top_elev + ypad * 0.22, "SP Top",
            fontsize=9, color="#333", va="bottom")
    ax.text(0.25, top_elev + ypad * 0.05, f"{top_elev:.2f} m",
            fontsize=7.5, color="#555", va="bottom")

    # ═══ FRONT SOIL LAYER BOUNDARIES: golden hollow ▽ + dashed lines ═══
    for i, (nm, zt, zb, gm, ph, *_) in enumerate(layers):
        if i > 0:
            ax.plot([-4.8, 0], [zt, zt], color="goldenrod", lw=1.0, ls="--", zorder=5)
            ax.plot([-0.25], [zt], "v", color="goldenrod", ms=7, zorder=11,
                    markerfacecolor="none", markeredgewidth=1.5)
            ax.text(-4.8, zt + ypad * 0.12, f"Soil {i}",
                    fontsize=9, color="goldenrod", va="bottom")

    # ═══ BACK LAYER BOUNDARIES: dotted lines on right side ═══
    if back_layers:
        for i, (nm, zt, zb, gm, ph, *_) in enumerate(back_layers):
            if i > 0:
                ax.plot([0, 4.8], [zt, zt], color="goldenrod", lw=0.9, ls=":", zorder=4, alpha=0.8)
                ax.text(0.3, zt + ypad * 0.12, f"Back {i}",
                        fontsize=8, color="goldenrod", va="bottom", alpha=0.85)

    # Pile tip elevation
    ax.text(0.25, bot - ypad * 0.05, f"{bot:.2f} m",
            fontsize=7.5, color="#555", va="top")

    # ═══ WATER MARKERS (≡ two stacked lines) ═══
    w_gap = ypad * 0.18
    # Front water (left side)
    ax.plot([-4.2, -0.8], [water_lvl, water_lvl],
            color="steelblue", lw=2.0, zorder=7)
    ax.plot([-3.8, -1.1], [water_lvl - w_gap, water_lvl - w_gap],
            color="steelblue", lw=1.5, zorder=7)
    ax.text(-4.8, water_lvl + ypad * 0.15, f"Water F  {water_lvl:.2f} m",
            fontsize=8, color="steelblue")
    # Back water (right side)
    _wlb = water_lvl_back if water_lvl_back is not None else water_lvl
    ax.plot([0.8, 4.2], [_wlb, _wlb],
            color="steelblue", lw=2.0, zorder=7, ls="--")
    ax.plot([1.1, 3.8], [_wlb - w_gap, _wlb - w_gap],
            color="steelblue", lw=1.5, zorder=7, ls="--")
    ax.text(0.3, _wlb + ypad * 0.15, f"Water B  {_wlb:.2f} m",
            fontsize=8, color="steelblue")

    # ═══ BOUNDARY CONDITION ═══
    if bc_type == "Fixed":
        ax.plot([-0.6, 0.6], [bot, bot], color="#333", lw=1.8, zorder=8)
        for k in range(6):
            x0 = -0.40 + k * 0.16
            ax.plot([x0, x0 - 0.12], [bot, bot - ypad * 0.25],
                    color="#333", lw=0.8, zorder=7)
    elif bc_type == "Cantilever":
        ax.plot([0], [bot], "^", ms=12, color="#333", zorder=8,
                markerfacecolor="none", markeredgewidth=2.0)
        ax.plot([-0.5, 0.5], [bot - ypad * 0.12, bot - ypad * 0.12],
                "#333", lw=1.0, zorder=7)
    elif bc_type == "Free":
        ax.plot([-0.2, 0.2], [bot, bot], "#333", lw=1.5, ls=":", zorder=7)

    # ═══ FORCE ARROW ═══
    if abs(H_kN) > 1e-3:
        sign = 1 if H_kN > 0 else -1
        ax.annotate("",
            xy=(0, top_elev),
            xytext=(-sign * 2.8, top_elev),
            arrowprops=dict(
                arrowstyle="->, head_width=0.35, head_length=0.20",
                color="red", lw=2.2),
            zorder=12)
        ax.text(-sign * 1.4, top_elev + ypad * 0.50,
                f"H = {H_kN:.0f} kN",
                fontsize=9, color="red", ha="center", fontweight="bold")

    if abs(M_kNm) > 1e-3:
        ax.text(0.4, top_elev + ypad * 1.2, f"M = {M_kNm:.0f} kN.m",
                fontsize=8.5, color="darkorange", ha="left", fontweight="bold")

    # ═══ FRONT / BACK labels ═══
    ax.text(-4.0, y_bot + ypad * 0.4, "Front",
            fontsize=10, color="#666", style="italic")
    ax.text(1.5, y_bot + ypad * 0.4, "Back",
            fontsize=10, color="#666", style="italic")

    plt.tight_layout()
    return fig


def draw_section(pile: dict):
    """Draw SW pile cross-section schematic."""
    H   = pile["H"] / 1000
    t   = pile["t"] / 1000
    W   = pile["width"] / 1000
    fig, ax = plt.subplots(figsize=(4, 4))

    outer = mpatches.FancyBboxPatch((-W/2, -H/2), W, H,
        boxstyle="round,pad=0.002", ec="#333", fc="#bbb", lw=2, zorder=2)
    ax.add_patch(outer)

    inner_h = H - 2 * t
    inner_w = W - 2 * t
    if inner_h > 0 and inner_w > 0:
        inner = mpatches.FancyBboxPatch((-inner_w/2, -inner_h/2), inner_w, inner_h,
            boxstyle="round,pad=0.001", ec="#555", fc="white", lw=1, zorder=3)
        ax.add_patch(inner)

    ax.annotate("", xy=(W/2 + W*0.15, H/2), xytext=(W/2 + W*0.15, -H/2),
                arrowprops=dict(arrowstyle="<->", color="#333", lw=1.2))
    ax.text(W/2 + W*0.22, 0, f"H = {pile['H']} mm",
            fontsize=8, va="center", color="#333", rotation=90, ha="left")

    ax.annotate("", xy=(W/2, -H/2 - H*0.12), xytext=(-W/2, -H/2 - H*0.12),
                arrowprops=dict(arrowstyle="<->", color="#333", lw=1.2))
    ax.text(0, -H/2 - H*0.20, f"W = {pile['width']} mm",
            fontsize=8, ha="center", color="#333")

    ax.annotate("", xy=(-W/2, H/4), xytext=(-W/2 + t, H/4),
                arrowprops=dict(arrowstyle="<->", color="steelblue", lw=1.2))
    ax.text(-W/2 + t/2, H/4 + H*0.06,
            f"t={pile['t']}mm", fontsize=7.5, ha="center", color="steelblue")

    ax.set_xlim(-W * 1.5, W * 1.8)
    ax.set_ylim(-H * 1.45, H * 1.1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"{pile['name']} — BETON 6  (n={pile['n']} strands ⌀{pile['phi_s']} mm)",
                 fontsize=10, pad=8)
    plt.tight_layout()
    return fig


# ── 3D Borehole map ──────────────────────────────────────────────────────────
# Màu địa tầng: dùng thống nhất cho cả KE và BXN
_LAYER_COLORS: dict[str, str] = {
    "F":    "#9E9E9E",   # fill - xám
    "1":    "#81D4FA",   # sét chảy rất dẻo (KE L1) hoặc fill (BXN) - xanh nhạt
    "1b":   "#4FC3F7",   # xen kẹp sét-cát
    "2":    "#1565C0",   # sét chảy rất dẻo (BXN L2) - xanh đậm
    "2a":   "#66BB6A",   # cát sít xốp
    "2b":   "#FDD835",   # cát xốp
    "2c":   "#C5E1A5",   # cát-sét xốp
    "3":    "#8D6E63",   # sét dẻo cứng (KE)
    "3a":   "#A5D6A7",   # cát bụi xốp (BXN)
    "3b":   "#69B578",   # cát lẫn sét xốp-chặt vừa
    "3c":   "#43A047",   # cát lẫn sét (lớp 3c)
    "4":    "#5C85D6",   # sét dẻo mềm–dẻo cứng - xanh
    "5":    "#FFA726",   # cát chặt - cam
    "5a":   "#FB8C00",   # cát chặt 5a
    "5b":   "#E65100",   # cát chặt 5b
    "6":    "#6D4C41",   # sét cứng - nâu
    "7":    "#795548",   # cát lẫn sét chặt - nâu sáng
    "8":    "#BCAAA4",   # cát bụi chặt - be
    "TK6a": "#FFD54F",   # thấu kính 6a - vàng nhạt
    "TK6b": "#FFB300",   # thấu kính 6b - vàng đậm
    "XMD":  "#E91E63",   # xi măng đất CDM - hồng
}
_LAYER_DEFAULT_COLOR = "#EEEEEE"

_ZONE_MARKER: dict[str, str] = {"KE": "circle", "BXN": "square", "NHC": "diamond"}


@st.cache_data(ttl=300, show_spinner=False)
def _load_borehole_3d_data() -> tuple[list[dict], list[dict]]:
    """Đọc boreholes + layers từ TTHC.sqlite, trả về (boreholes, layers)."""
    if not _TTHC_DB.exists():
        return [], []
    conn = sqlite3.connect(_TTHC_DB)
    conn.row_factory = sqlite3.Row
    bhs = [dict(r) for r in conn.execute(
        "SELECT b.id, b.name, z.code zone, b.elevation_m, b.depth_m, "
        "b.x_coord_m, b.y_coord_m "
        "FROM boreholes b JOIN zones z ON z.id=b.zone_id "
        "WHERE b.x_coord_m IS NOT NULL "
        "ORDER BY z.id, b.name"
    ).fetchall()]
    ids = [b["id"] for b in bhs]
    if not ids:
        conn.close()
        return [], []
    ph = ",".join("?" * len(ids))
    lays = [dict(r) for r in conn.execute(
        f"SELECT borehole_id, symbol, description, depth_top_m, depth_bot_m "
        f"FROM layers WHERE borehole_id IN ({ph}) ORDER BY borehole_id, depth_top_m",
        ids
    ).fetchall()]
    conn.close()
    return bhs, lays


@st.cache_data(ttl=300, show_spinner=False)
def _load_clay_bottom() -> list[dict]:
    """Đáy lớp sét chảy rất dẻo (KE sym='1', BXN/NHC sym='2') cho mỗi HK có tọa độ."""
    if not _TTHC_DB.exists():
        return []
    conn = sqlite3.connect(_TTHC_DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("""
        SELECT b.name, z.code zone, b.elevation_m, b.x_coord_m, b.y_coord_m,
               ROUND(MAX(l.depth_bot_m), 3) clay_bot_depth,
               ROUND(b.elevation_m - MAX(l.depth_bot_m), 3) clay_bot_elev
        FROM boreholes b
        JOIN zones z ON z.id=b.zone_id
        JOIN layers l ON l.borehole_id=b.id
        WHERE b.x_coord_m IS NOT NULL
          AND ((z.code='KE' AND l.symbol='1')
            OR (z.code IN ('BXN','NHC') AND l.symbol='2'))
        GROUP BY b.id
        ORDER BY z.id, b.name
    """).fetchall()]
    conn.close()
    return rows


def _draw_boreholes_3d(
    selected_zones: list[str],
    show_clay_bottom: bool = False,
    show_pile_top: bool = False,
    pile_top_z: float = 2.7,
) -> "go.Figure":
    from collections import defaultdict

    bhs, lays = _load_borehole_3d_data()
    bhs = [b for b in bhs if b["zone"] in selected_zones]
    bh_ids = {b["id"] for b in bhs}
    lays = [l for l in lays if l["borehole_id"] in bh_ids]

    fig = go.Figure()
    if not bhs:
        fig.update_layout(title="Không có dữ liệu tọa độ")
        return fig

    # ── Index layers by borehole_id ───────────────────────────────────────────
    lay_by_bh: dict[int, list[dict]] = defaultdict(list)
    for l in lays:
        lay_by_bh[l["borehole_id"]].append(l)

    # ── Tập hợp tất cả symbols để gộp legend ─────────────────────────────────
    all_syms: list[str] = []
    for l in lays:
        if l["symbol"] not in all_syms:
            all_syms.append(l["symbol"])

    # ── Trace cho từng symbol (1 legend entry / lớp) ─────────────────────────
    added_legends: set[str] = set()
    for sym in all_syms:
        color = _LAYER_COLORS.get(sym, _LAYER_DEFAULT_COLOR)
        xs: list = []
        ys: list = []
        zs: list = []
        texts: list = []
        for bh in bhs:
            for l in lay_by_bh[bh["id"]]:
                if l["symbol"] != sym:
                    continue
                z0 = bh["elevation_m"] - l["depth_top_m"]
                z1 = bh["elevation_m"] - l["depth_bot_m"]
                desc = l.get("description") or sym
                hover = (
                    f"<b>{bh['name']}</b><br>"
                    f"Lớp {sym}: {desc}<br>"
                    f"Sâu {l['depth_top_m']:.1f}–{l['depth_bot_m']:.1f} m<br>"
                    f"Cao độ {z0:.2f} → {z1:.2f} m"
                )
                xs += [bh["x_coord_m"], bh["x_coord_m"], None]
                ys += [bh["y_coord_m"], bh["y_coord_m"], None]
                zs += [z0, z1, None]
                texts += [hover, hover, None]

        show_leg = sym not in added_legends
        added_legends.add(sym)
        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode="lines",
            line=dict(color=color, width=10),
            name=f"Lớp {sym}",
            legendgroup=sym,
            showlegend=show_leg,
            hovertemplate="%{text}<extra></extra>",
            text=texts,
        ))

    # ── Labels tên hố khoan ───────────────────────────────────────────────────
    fig.add_trace(go.Scatter3d(
        x=[b["x_coord_m"] for b in bhs],
        y=[b["y_coord_m"] for b in bhs],
        z=[b["elevation_m"] + 3 for b in bhs],
        mode="text+markers",
        text=[b["name"].replace("BXN-CV-", "").replace("KE-", "") for b in bhs],
        textposition="top center",
        textfont=dict(size=9, color="#212121"),
        marker=dict(
            size=5,
            color=[{"KE": "#E53935", "BXN": "#1565C0", "NHC": "#2E7D32"}.get(b["zone"], "#333")
                   for b in bhs],
            symbol=[_ZONE_MARKER.get(b["zone"], "circle") for b in bhs],
        ),
        name="Vị trí HK",
        showlegend=True,
        hovertemplate="<b>%{text}</b><extra></extra>",
    ))

    # ── Đáy lớp bùn ──────────────────────────────────────────────────────────
    if show_clay_bottom:
        _clay = [c for c in _load_clay_bottom() if c["zone"] in selected_zones]
        if len(_clay) >= 3:
            cx = [c["x_coord_m"] for c in _clay]
            cy = [c["y_coord_m"] for c in _clay]
            cz = [c["clay_bot_elev"] for c in _clay]
            ct = [
                f"<b>{c['name']}</b><br>Đáy bùn sâu: {c['clay_bot_depth']:.1f} m<br>"
                f"Cao độ đáy: {c['clay_bot_elev']:.2f} m"
                for c in _clay
            ]
            # Mặt lưới nối đáy bùn (Delaunay trong mặt phẳng XY)
            fig.add_trace(go.Mesh3d(
                x=cx, y=cy, z=cz,
                delaunayaxis="z",
                intensity=cz,
                colorscale=[[0, "#0D47A1"], [0.5, "#42A5F5"], [1, "#BBDEFB"]],
                showscale=False,
                opacity=0.55,
                name="Đáy lớp bùn",
                legendgroup="clay_bottom",
                showlegend=True,
                hovertemplate="%{text}<extra></extra>",
                text=ct,
            ))
            # Đường viền mặt đáy bùn (Scatter3d markers)
            fig.add_trace(go.Scatter3d(
                x=cx, y=cy, z=cz,
                mode="markers",
                marker=dict(size=6, color="#0D47A1", symbol="diamond"),
                name="Điểm đáy bùn",
                legendgroup="clay_bottom",
                showlegend=False,
                hovertemplate="%{text}<extra></extra>",
                text=ct,
            ))
            # Cột dọc từ mặt đất xuống đáy bùn
            vx, vy, vz, vt = [], [], [], []
            for c in _clay:
                vx += [c["x_coord_m"], c["x_coord_m"], None]
                vy += [c["y_coord_m"], c["y_coord_m"], None]
                vz += [c["elevation_m"], c["clay_bot_elev"], None]
                lbl = (f"<b>{c['name']}</b><br>Bùn dày {c['clay_bot_depth']:.1f} m")
                vt += [lbl, lbl, None]
            fig.add_trace(go.Scatter3d(
                x=vx, y=vy, z=vz,
                mode="lines",
                line=dict(color="#1565C0", width=3, dash="dot"),
                name="Chiều dày bùn",
                legendgroup="clay_bottom",
                showlegend=False,
                hovertemplate="%{text}<extra></extra>",
                text=vt,
            ))

    # ── Mặt phẳng đỉnh tường cừ ──────────────────────────────────────────────
    if show_pile_top:
        all_x = [b["x_coord_m"] for b in bhs]
        all_y = [b["y_coord_m"] for b in bhs]
        pad = 20.0
        mx, Mx = min(all_x) - pad, max(all_x) + pad
        my, My = min(all_y) - pad, max(all_y) + pad
        z = pile_top_z
        fig.add_trace(go.Mesh3d(
            x=[mx, Mx, Mx, mx],
            y=[my, my, My, My],
            z=[z,  z,  z,  z],
            i=[0, 0],
            j=[1, 2],
            k=[2, 3],
            color="#FF8F00",
            opacity=0.28,
            name=f"Đỉnh cừ +{z:.2f} m",
            showlegend=True,
            flatshading=True,
            hovertemplate=f"Đỉnh tường cừ: <b>{z:.2f} m</b><extra></extra>",
        ))
        # Đường viền
        fig.add_trace(go.Scatter3d(
            x=[mx, Mx, Mx, mx, mx],
            y=[my, my, My, My, my],
            z=[z,  z,  z,  z,  z],
            mode="lines",
            line=dict(color="#E65100", width=3),
            name=f"Viền đỉnh cừ",
            showlegend=False,
        ))

    # ── Layout ────────────────────────────────────────────────────────────────
    all_x = [b["x_coord_m"] for b in bhs]
    all_y = [b["y_coord_m"] for b in bhs]
    span_x = max(all_x) - min(all_x) or 1
    span_y = max(all_y) - min(all_y) or 1
    max_z = max(b["elevation_m"] for b in bhs) + 5
    min_z = min(b["elevation_m"] - b["depth_m"] for b in bhs) - 2

    fig.update_layout(
        height=660,
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(
            x=1.01, y=0.95,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#ccc",
            borderwidth=1,
            font=dict(size=11),
        ),
        scene=dict(
            xaxis=dict(title="X — Easting (m)", tickformat=".0f"),
            yaxis=dict(title="Y — Northing (m)", tickformat=".0f"),
            zaxis=dict(title="Cao độ (m)", range=[min_z, max_z + 5]),
            aspectmode="manual",
            aspectratio=dict(
                x=span_x / max(span_x, span_y),
                y=span_y / max(span_x, span_y),
                z=0.35,
            ),
            camera=dict(eye=dict(x=1.4, y=-1.4, z=0.8)),
        ),
        paper_bgcolor="#FAFAFA",
    )
    return fig


# ── Import hố khoan → Soil Layers ────────────────────────────────────────────

# Mapping layer symbol → Soil Type cho openpile
_SYM_SOIL_TYPE: dict[str, str] = {
    # KE
    "F": "Sand", "1": "Clay", "1b": "Clay",
    "2a": "Sand", "2b": "Sand", "2c": "Sand",
    "3": "Clay",
    "4": "Sand", "5": "Sand", "5a": "Sand", "5b": "Sand",
    "6": "Clay", "7": "Sand", "XMD": "Clay",
    # BXN / NHC
    "2": "Clay", "3a": "Sand", "3b": "Sand", "3c": "Sand",
    "8": "Sand", "TK6a": "Sand", "TK6b": "Sand",
}


def _eps50_from_su(su: float) -> float:
    if su < 20:   return 0.020
    if su < 50:   return 0.015
    if su < 100:  return 0.010
    return 0.007


@st.cache_data(ttl=300, show_spinner=False)
def _query_boreholes_for_selector() -> list[dict]:
    """Tất cả boreholes trong TTHC.sqlite cho dropdown."""
    if not _TTHC_DB.exists():
        return []
    conn = sqlite3.connect(_TTHC_DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT b.id, b.name, z.code zone, b.elevation_m, b.depth_m "
        "FROM boreholes b JOIN zones z ON z.id=b.zone_id "
        "ORDER BY z.id, b.name"
    ).fetchall()]
    conn.close()
    return rows


@st.cache_data(ttl=300, show_spinner=False)
def _borehole_to_layer_dfs(bh_name: str) -> tuple[float | None, pd.DataFrame, pd.DataFrame]:
    """
    Convert borehole layers + lab_tests + vane_shear → (elevation_m, sand_df, clay_df).
    Layer Tip [m] = cao độ đáy lớp = elevation_m − depth_bot_m.
    Su cho lớp sét = trung bình VST cùng zone trong khoảng chiều sâu.
    """
    if not _TTHC_DB.exists():
        return None, _DEFAULT_FRONT_SAND_DF.copy(), _DEFAULT_FRONT_CLAY_DF.copy()

    conn = sqlite3.connect(_TTHC_DB)
    conn.row_factory = sqlite3.Row

    bh = conn.execute(
        "SELECT b.id, b.elevation_m, b.depth_m, b.zone_id "
        "FROM boreholes b WHERE b.name=?", (bh_name,)
    ).fetchone()
    if not bh:
        conn.close()
        return None, _DEFAULT_FRONT_SAND_DF.copy(), _DEFAULT_FRONT_CLAY_DF.copy()

    bh_id  = bh["id"]
    elev   = bh["elevation_m"]
    zone_id = bh["zone_id"]

    # ── Layers ───────────────────────────────────────────────────────────────
    layers_raw = [dict(r) for r in conn.execute(
        "SELECT symbol, description, depth_top_m, depth_bot_m "
        "FROM layers WHERE borehole_id=? ORDER BY depth_top_m",
        (bh_id,)
    ).fetchall()]

    # ── Lab tests (avg per layer) ─────────────────────────────────────────────
    lab_rows = [dict(r) for r in conn.execute(
        "SELECT depth_from_m, depth_to_m, gamma_kNm3, phi_deg, c_kPa "
        "FROM lab_tests WHERE borehole_id=?",
        (bh_id,)
    ).fetchall()]

    # ── VST cho zone (Su theo chiều sâu) ─────────────────────────────────────
    vst_rows = [dict(r) for r in conn.execute(
        "SELECT vs.depth_m, vs.Su_kPa "
        "FROM vane_shear_tests vs "
        "JOIN vst_locations vl ON vl.id=vs.vst_loc_id "
        "WHERE vl.zone_id=?",
        (zone_id,)
    ).fetchall()]
    conn.close()

    def _lab_avg(top: float, bot: float) -> dict:
        """Trung bình chỉ tiêu lab cho các mẫu nằm trong [top, bot]."""
        mid = (top + bot) / 2
        samples = [r for r in lab_rows
                   if r["depth_from_m"] is not None and r["depth_to_m"] is not None
                   and r["depth_from_m"] >= top - 2 and r["depth_to_m"] <= bot + 2]
        if not samples:
            samples = [r for r in lab_rows
                       if r["depth_from_m"] is not None
                       and abs((r["depth_from_m"] + (r["depth_to_m"] or r["depth_from_m"])) / 2 - mid) < 5]
        gammas = [r["gamma_kNm3"] for r in samples if r["gamma_kNm3"]]
        phis   = [r["phi_deg"]    for r in samples if r["phi_deg"] is not None and r["phi_deg"] > 0]
        cs     = [r["c_kPa"]      for r in samples if r["c_kPa"]  is not None and r["c_kPa"] >= 0]
        return {
            "gamma": round(sum(gammas) / len(gammas), 2) if gammas else None,
            "phi":   round(sum(phis)   / len(phis),   2) if phis   else None,
            "c":     round(sum(cs)     / len(cs),     2) if cs     else None,
        }

    def _vst_avg_su(top: float, bot: float) -> float | None:
        """Trung bình Su từ VST trong khoảng chiều sâu [top, bot] của zone."""
        pts = [r["Su_kPa"] for r in vst_rows
               if r["depth_m"] >= top and r["depth_m"] <= bot]
        if not pts:
            pts = [r["Su_kPa"] for r in vst_rows
                   if r["depth_m"] >= top - 2 and r["depth_m"] <= bot + 2]
        return round(sum(pts) / len(pts), 1) if pts else None

    # ── Gộp lớp liền kề cùng symbol ─────────────────────────────────────────
    merged: list[dict] = []
    for lay in layers_raw:
        sym = lay["symbol"]
        if merged and merged[-1]["symbol"] == sym:
            merged[-1]["depth_bot_m"] = lay["depth_bot_m"]
        else:
            merged.append(dict(lay))

    # ── Xây dựng rows cho sand / clay ────────────────────────────────────────
    sand_rows: list[dict] = []
    clay_rows: list[dict] = []

    for lay in merged:
        sym  = lay["symbol"]
        top  = lay["depth_top_m"]
        bot  = lay["depth_bot_m"]
        tip  = round(elev - bot, 3)           # cao độ đáy lớp (elevation)
        st_  = _SYM_SOIL_TYPE.get(sym, "Clay")
        lab  = _lab_avg(top, bot)
        gamma_m = lab["gamma"] or (16.0 if st_ == "Clay" else 18.0)
        gamma_s = round(gamma_m - 10.0, 2)

        if st_ == "Sand":
            phi = lab["phi"] or (28.0 if sym in ("5", "5a", "5b") else 22.0)
            c   = lab["c"]   or 0.0
            sand_rows.append({
                "Layer Tip [m]":         tip,
                "Density Moist [kN/m3]": gamma_m,
                "Density Sub [kN/m3]":   gamma_s,
                "Phi [Deg]":             round(phi, 1),
                "Su [kN/m2]":            0.0,
                "eps50":                 0.005,
                "Delta [Deg]":           0.0,
                "Cohesion [kN/m2]":      round(c, 1),
            })
        else:  # Clay
            su = _vst_avg_su(top, bot)
            if su is None:
                su = lab["c"] or 10.0      # fallback: dùng c nếu không có VST
            eps = _eps50_from_su(su)
            clay_rows.append({
                "Layer Tip [m]":         tip,
                "Density Moist [kN/m3]": gamma_m,
                "Density Sub [kN/m3]":   gamma_s,
                "Phi [Deg]":             0.0,
                "Su [kN/m2]":            su,
                "eps50":                 eps,
                "Delta [Deg]":           0.0,
                "Cohesion [kN/m2]":      round(lab["c"] or su, 1),
            })

    sand_df = (pd.DataFrame(sand_rows)
               .sort_values("Layer Tip [m]", ascending=False)
               .reset_index(drop=True)) if sand_rows else _DEFAULT_FRONT_SAND_DF.copy()
    clay_df = (pd.DataFrame(clay_rows)
               .sort_values("Layer Tip [m]", ascending=False)
               .reset_index(drop=True)) if clay_rows else _DEFAULT_FRONT_CLAY_DF.copy()
    return elev, sand_df, clay_df


# ══════════════════════════════════════════════════════════════════════════════
# NAVIGATION
# ══════════════════════════════════════════════════════════════════════════════
_PAGES = [
    "Geo Data",
    "Soil Layers",
    "Concentrated Forces",
    "Boussinesq",
    "Sheet Pile Section",
    "Bearing Capacity",
    "Sheet Pile Design",
    "Slope Stability",
    "P-y",
    "Compare",
]
st.sidebar.markdown("### Lateral Pile Analysis")

# ── Lưu / Mở / Tạo bài mới ───────────────────────────────────────────────────
_sb1, _sb2, _sb3 = st.sidebar.columns(3)

# Lưu bài — download JSON
_sb1.download_button(
    "Save",
    data=_project_to_json(),
    file_name="project.json",
    mime="application/json",
    use_container_width=True,
    key="btn_save_proj",
)

# Open — toggle panel
if _sb2.button("Open", use_container_width=True, key="btn_open_proj"):
    st.session_state["_open_panel"] = not st.session_state.get("_open_panel", False)

if st.session_state.get("_open_panel"):
    _uploaded = st.sidebar.file_uploader(
        "Select .json file",
        type=["json"],
        key="proj_uploader",
        label_visibility="collapsed",
    )
    if _uploaded is not None:
        try:
            _project_from_dict(json.loads(_uploaded.read().decode("utf-8")))
            st.session_state["_open_panel"] = False
            st.rerun()
        except Exception as _e_open:
            st.sidebar.error(f"Error: {_e_open}")

# New — clear all project data
if _sb3.button("New", use_container_width=True, key="btn_new_proj"):
    st.session_state["_confirm_new"] = True

if st.session_state.get("_confirm_new"):
    st.sidebar.warning("Clear all data — confirm?")
    _cn1, _cn2 = st.sidebar.columns(2)
    if _cn1.button("Confirm", key="btn_confirm_new", use_container_width=True):
        for _k in _PROJ_DF_KEYS + _PROJ_SCALAR_KEYS + _PROJ_RESULT_KEYS:
            st.session_state.pop(_k, None)
        st.session_state.pop("_confirm_new", None)
        st.rerun()
    if _cn2.button("Cancel", key="btn_cancel_new", use_container_width=True):
        st.session_state.pop("_confirm_new", None)
        st.rerun()

st.sidebar.divider()

# ── Save as Variant ───────────────────────────────────────────────────────────
if _HAS_VDB:
    with st.sidebar.expander("Save as Variant", expanded=False):
        _v_name = st.text_input("Name", placeholder="PA1 - SW940 L=20m",
                                key="_v_name")
        _v_note = st.text_input("Note", placeholder="optional",
                                key="_v_note")
        if st.button("Save Variant", use_container_width=True,
                     key="btn_save_variant", type="primary"):
            if not _v_name.strip():
                st.warning("Enter a variant name.")
            else:
                _v_inputs = {}
                for _k in _PROJ_SCALAR_KEYS:
                    _v = st.session_state.get(_k)
                    if _v is not None:
                        _v_inputs[_k] = _v.item() if hasattr(_v, "item") else _v
                _v_results = {_k: st.session_state.get(_k)
                              for _k in _PROJ_RESULT_KEYS
                              if st.session_state.get(_k) is not None}
                _new_id = _vdb_save(
                    name=_v_name.strip(),
                    description=_v_note.strip(),
                    inputs=_v_inputs,
                    results=_v_results,
                )
                st.success(f"Saved — ID {_new_id}")

st.sidebar.divider()

_page = st.sidebar.radio("", _PAGES, label_visibility="collapsed")


# ── TAB 1: GEO DATA ───────────────────────────────────────────────────────────
if _page == "Geo Data":

    # ── Chọn hố khoan → tự động nạp Soil Layers ──────────────────────────────
    _all_bhs = _query_boreholes_for_selector()
    if _all_bhs:
        with st.expander("Nhập số liệu từ hố khoan địa chất (TTHC)", expanded=True):
            _zones_avail = sorted({b["zone"] for b in _all_bhs})
            _sel_zone_imp = st.radio(
                "Khu vực",
                _zones_avail,
                horizontal=True,
                key="_imp_zone",
            )
            _bhs_zone = [b for b in _all_bhs if b["zone"] == _sel_zone_imp]
            _bh_names = [b["name"] for b in _bhs_zone]

            _imp_col1, _imp_col2 = st.columns([2, 1])
            _sel_bh_name = _imp_col1.selectbox(
                "Chọn hố khoan",
                _bh_names,
                key="_imp_bh_name",
                label_visibility="collapsed",
            )
            _sel_bh_meta = next((b for b in _bhs_zone if b["name"] == _sel_bh_name), None)
            if _sel_bh_meta:
                _imp_col2.caption(
                    f"Z = **{_sel_bh_meta['elevation_m']:.3f} m**  "
                    f"| Sâu **{_sel_bh_meta['depth_m']:.0f} m**"
                )

            # Preview layers
            _prev_elev, _prev_sand, _prev_clay = _borehole_to_layer_dfs(_sel_bh_name)
            _prev_all = pd.concat(
                [_prev_sand.assign(**{"Soil Type": "Sand"}),
                 _prev_clay.assign(**{"Soil Type": "Clay"})],
                ignore_index=True,
            ).sort_values("Layer Tip [m]", ascending=False).reset_index(drop=True)

            _disp_cols = ["Soil Type", "Layer Tip [m]", "Density Moist [kN/m3]",
                          "Phi [Deg]", "Su [kN/m2]", "Cohesion [kN/m2]"]
            st.dataframe(
                _prev_all[[c for c in _disp_cols if c in _prev_all.columns]],
                use_container_width=True,
                hide_index=True,
                height=min(38 * (len(_prev_all) + 1) + 4, 320),
            )

            if st.button(
                f"Ap dung '{_sel_bh_name}' vao Soil Layers",
                type="primary",
                key="_btn_import_bh",
                use_container_width=True,
            ):
                st.session_state["front_sand_df"] = _prev_sand.copy()
                st.session_state["front_clay_df"] = _prev_clay.copy()
                # Đồng bộ top_elev với cao độ mặt đất của hố khoan
                if _prev_elev is not None:
                    st.session_state["top_elev"] = float(_prev_elev)
                st.success(
                    f"Da nap {len(_prev_sand)} lop cat + {len(_prev_clay)} lop set "
                    f"tu {_sel_bh_name}. Xem tab Soil Layers."
                )
                st.rerun()

    st.divider()
    cf, cd = st.columns([1, 1.3], gap="large")
    with cf:
        st.markdown("#### Geometry")
        top_elev  = st.number_input("Pile Top Level [m]",
                                     value=2.7, step=0.5, format="%.3f", key="top_elev")
        soil_lvl_f = st.number_input("Soil Level in Front [m]",
                                      value=0.0, step=0.5, format="%.3f", key="soil_level_front")
        soil_lvl_b = st.number_input("Soil Level behind [m]",
                                      value=0.0, step=0.5, format="%.3f", key="soil_level_back")
        L_m        = st.number_input("Pile Length [m]",
                                      min_value=1.0, max_value=80.0,
                                      value=20.0, step=0.5, key="L_m")
        st.markdown("#### Water")
        wa, wb = st.columns(2)
        water_lvl   = wa.number_input("Water Level in Front [m]",
                                       min_value=-40.0, max_value=5.0,
                                       value=-1.0, step=0.5, format="%.3f", key="water_level")
        water_lvl_b = wb.number_input("Water Level behind [m]",
                                       min_value=-40.0, max_value=5.0,
                                       value=-1.0, step=0.5, format="%.3f", key="water_level_back")

        st.markdown("#### Fill (Dat dap)")
        _fill_front_h = max(0.0, round(_get("top_elev", 0.0) - _get("soil_level_front", 0.0), 3))
        st.caption(
            f"Fill Top = Pile Top Level = **{_get('top_elev', 0.0):.2f} m**  "
            f"| Fill Bottom = Soil Level in Front = **{_get('soil_level_front', 0.0):.2f} m**  "
            f"| Thickness: **{_fill_front_h:.2f} m**"
        )
        fa, fb, fc_, fd = st.columns(4)
        gamma_fill = fa.number_input("Density Fill\n[kN/m3]",
                                      min_value=10.0, max_value=25.0,
                                      value=18.0, step=0.5, format="%.1f", key="gamma_fill")
        phi_fill   = fb.number_input("Phi Fill\n[Deg]",
                                      min_value=0.0, max_value=45.0,
                                      value=25.0, step=1.0, format="%.1f", key="phi_fill")
        c_fill     = fc_.number_input("Cohesion Fill\n[kN/m2]",
                                       min_value=0.0, max_value=200.0,
                                       value=5.0, step=1.0, format="%.1f", key="c_fill")
        fd.number_input("Slope H:V\n(mai doc)",
                         min_value=0.5, max_value=5.0,
                         value=2.0, step=0.5, format="%.1f", key="fill_slope_hv",
                         help="Ti so ngang:dung cua mai dat dap (2.0 = mai 1:2)")

        st.markdown("#### Boundary")
        bc_type    = st.selectbox("Earth Support",
                                   ["Fixed", "Free", "Cantilever"], key="bc_type")

    with cd:
        fig1 = draw_pile_schematic(
            _get("L_m", 20.0), _get("water_level", -1.0),
            _get("top_elev", 0.0),
            0.0, 0.0,
            _get_front_layers(), st.session_state.get("bc_type", "Fixed"),
            soil_lvl_front=_get("soil_level_front", 0.0),
            soil_lvl_back=_get("soil_level_back", 0.0),
            back_layers=_get_back_layers(),
            gamma_fill=_get("gamma_fill", 18.0),
            phi_fill=_get("phi_fill", 25.0),
            c_fill=_get("c_fill", 5.0),
            water_lvl_back=_get("water_level_back", -1.0),
        )
        st.pyplot(fig1, use_container_width=True)
        plt.close()

    # ── 3D Borehole Map (TTHC.sqlite) ─────────────────────────────────────────
    if _HAS_PLOTLY and _TTHC_DB.exists():
        st.divider()
        st.markdown("#### Bản đồ 3D Hố khoan — Dự án TTHC")

        _bhs_all, _ = _load_borehole_3d_data()
        _avail_zones = sorted({b["zone"] for b in _bhs_all})

        # ── Hàng 1: chọn zone + lớp phủ ──────────────────────────────────────
        _ctrl_cols = st.columns([1, 1, 1, 1, 1, 1.6])

        _sel_zones = []
        for _ci, _zc in enumerate(_avail_zones):
            _color_map = {"KE": "🔴", "BXN": "🔵", "NHC": "🟢"}
            if _ctrl_cols[_ci].checkbox(
                f"{_color_map.get(_zc,'')} {_zc}",
                value=True,
                key=f"_3d_zone_{_zc}",
            ):
                _sel_zones.append(_zc)

        _show_clay = _ctrl_cols[len(_avail_zones)].checkbox(
            "Đáy lớp bùn",
            value=True,
            key="_3d_show_clay",
            help="Mặt lưới nối đáy lớp sét chảy (KE: Lớp 1 / BXN: Lớp 2)",
        )
        _show_pile_top = _ctrl_cols[len(_avail_zones) + 1].checkbox(
            "Đỉnh tường cừ",
            value=True,
            key="_3d_show_pile_top",
        )
        _pile_top_z = st.session_state.get("top_elev", 2.7)

        _bhs_sel = [b for b in _bhs_all if b["zone"] in _sel_zones]

        # caption tóm tắt + cao độ đỉnh cừ
        _clay_count = len([c for c in _load_clay_bottom() if c["zone"] in _sel_zones])
        _sum_txt = (
            f"{len(_bhs_sel)} HK có tọa độ  |  "
            f"{_clay_count} HK có đáy bùn  |  "
            f"Đỉnh cừ = **{_pile_top_z:.2f} m** *(lấy từ Pile Top Level)*"
        )
        st.caption(_sum_txt)

        if _sel_zones:
            _fig3d = _draw_boreholes_3d(
                _sel_zones,
                show_clay_bottom=_show_clay,
                show_pile_top=_show_pile_top,
                pile_top_z=_pile_top_z,
            )
            st.plotly_chart(_fig3d, use_container_width=True, config={"displayModeBar": True})

            # Bảng đáy bùn nếu đang hiện
            if _show_clay and _clay_count:
                with st.expander("Chiều dày lớp bùn theo hố khoan", expanded=False):
                    _clay_rows = [
                        {
                            "Hố khoan": c["name"],
                            "Zone": c["zone"],
                            "Z mặt đất (m)": round(c["elevation_m"], 3),
                            "Chiều dày bùn (m)": c["clay_bot_depth"],
                            "Cao độ đáy bùn (m)": c["clay_bot_elev"],
                        }
                        for c in _load_clay_bottom()
                        if c["zone"] in _sel_zones
                    ]
                    st.dataframe(pd.DataFrame(_clay_rows), use_container_width=True, hide_index=True)

            with st.expander("Danh sách hố khoan", expanded=False):
                _rows = [
                    {
                        "Tên": b["name"],
                        "Zone": b["zone"],
                        "Z (m)": round(b["elevation_m"], 3),
                        "Sâu (m)": b["depth_m"],
                        "X": round(b["x_coord_m"], 3),
                        "Y": round(b["y_coord_m"], 3),
                    }
                    for b in _bhs_sel
                ]
                st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Chọn ít nhất một khu vực để hiển thị.")
    elif not _HAS_PLOTLY:
        st.caption("Cài `plotly` để xem bản đồ 3D hố khoan.")


# ── TAB 2: SOIL LAYERS ────────────────────────────────────────────────────────
# CSS: blue left-border for editable containers, grey for locked notice
st.markdown("""
<style>
.sand-editor { border-left: 4px solid #f59e0b; padding-left: 8px; margin-bottom: 12px; }
.clay-editor { border-left: 4px solid #3b82f6; padding-left: 8px; margin-bottom: 12px; }
.locked-note { color: #888; font-size: 12px; font-style: italic; margin-top: 2px; }
</style>""", unsafe_allow_html=True)

if _page == "Soil Layers":
    auto_sub = st.checkbox(
        "Automatic Density Submerged = Density Moist − 10.0",
        value=True, key="auto_sub"
    )
    st.caption(
        "Layer top is derived automatically from sorting by Layer Tip.  "
        "Front Layer 1 top = Pile Top Level.  |  Back Layer 1 top = Soil Level behind."
    )
    with st.expander("ℹ️  Soil model guide — Sand vs Clay", expanded=False):
        st.markdown("""
| Soil Type | p-y Model | Editable (🔵) | Locked (⬜) |
|-----------|-----------|--------------|-------------|
| **Sand** | API (1987) | Layer Tip, Density, **Phi [Deg]**, Delta, Cohesion | Su = 0, ε₅₀ = 0.005 |
| **Clay** | Matlock / API (1974) | Layer Tip, Density, **Su [kN/m²]**, **ε₅₀**, Delta, Cohesion | Phi = 0 |

- Mixed profiles: layers are **merged and sorted by Layer Tip** automatically.
- **Cohesion** → earth pressure diagram only, not p-y curves.
        """)

    cfl, cfb, cd2 = st.columns([1.1, 1.1, 0.9], gap="medium")

    # ── Layers in Front: TWO SEPARATE TABLES (Sand / Clay) ───────────────────
    with cfl:
        st.markdown("**Layers in Front**")

        # Column configs with disabled= for locked columns
        _COMMON_CFG = {
            "Layer Tip [m]": st.column_config.NumberColumn(
                "Layer Tip [m]", format="%.2f", step=0.5, width=95,
                help="Elevation at bottom of this layer (m, negative = below datum)"),
            "Density Moist [kN/m3]": st.column_config.NumberColumn(
                "Density Moist\n[kN/m3]", format="%.1f",
                min_value=10.0, max_value=25.0, step=0.5, width=110),
            "Density Sub [kN/m3]": st.column_config.NumberColumn(
                "Density Sub\n[kN/m3]", format="%.1f",
                min_value=0.0, max_value=15.0, step=0.5, width=110,
                disabled=auto_sub),
            "Delta [Deg]": st.column_config.NumberColumn(
                "Delta [Deg]", format="%.1f", min_value=0.0, step=1.0, width=80),
            "Cohesion [kN/m2]": st.column_config.NumberColumn(
                "Cohesion\n[kN/m2]", format="%.1f", min_value=0.0, step=1.0, width=90,
                help="Used for earth pressure diagram only"),
        }
        _SAND_CFG = {**_COMMON_CFG,
            "Phi [Deg]": st.column_config.NumberColumn(
                "Phi [Deg] 🔵", format="%.1f",
                min_value=0.0, max_value=45.0, step=1.0, width=90,
                help="Friction angle — active for Sand"),
            "Su [kN/m2]": st.column_config.NumberColumn(
                "Su [kN/m²] ⬜", format="%.1f",
                min_value=0.0, max_value=500.0, step=1.0, width=95),
            "eps50": st.column_config.NumberColumn(
                "ε₅₀ ⬜", format="%.4f",
                min_value=0.001, max_value=0.10, step=0.001, width=80),
        }
        _CLAY_CFG = {**_COMMON_CFG,
            "Phi [Deg]": st.column_config.NumberColumn(
                "Phi [Deg] ⬜", format="%.1f",
                min_value=0.0, max_value=45.0, step=1.0, width=90),
            "Su [kN/m2]": st.column_config.NumberColumn(
                "Su [kN/m²] 🔵", format="%.1f",
                min_value=0.0, max_value=500.0, step=1.0, width=95,
                help="Undrained shear strength — active for Clay"),
            "eps50": st.column_config.NumberColumn(
                "ε₅₀ 🔵", format="%.4f",
                min_value=0.001, max_value=0.10, step=0.001, width=80,
                help="Strain at 50% failure: soft 0.02 · medium 0.01 · stiff 0.005"),
        }

        # ── Sand table ──
        st.markdown('<div class="sand-editor">', unsafe_allow_html=True)
        st.markdown("🟡 **Sand Layers** — API p-y (1987)")
        wdf_sand = st.session_state["front_sand_df"].copy()
        if auto_sub:
            wdf_sand["Density Sub [kN/m3]"] = (wdf_sand["Density Moist [kN/m3]"] - 10.0).round(1)
        edf_sand = st.data_editor(
            wdf_sand,
            column_config=_SAND_CFG,
            disabled=["Su [kN/m2]", "eps50"],
            use_container_width=True, num_rows="dynamic",
            hide_index=True, key="front_sand_editor",
        )
        if auto_sub:
            edf_sand["Density Sub [kN/m3]"] = (edf_sand["Density Moist [kN/m3]"] - 10.0).round(1)
        edf_sand["Su [kN/m2]"] = 0.0
        edf_sand["eps50"] = 0.005
        st.session_state["front_sand_df"] = edf_sand
        st.markdown('<p class="locked-note">⬜ Su, ε₅₀ locked (grey) — not used for Sand p-y</p>',
                    unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Clay table ──
        st.markdown('<div class="clay-editor">', unsafe_allow_html=True)
        st.markdown("🔵 **Clay Layers** — Matlock p-y (API 1974)")
        wdf_clay = st.session_state["front_clay_df"].copy()
        if auto_sub:
            wdf_clay["Density Sub [kN/m3]"] = (wdf_clay["Density Moist [kN/m3]"] - 10.0).round(1)
        edf_clay = st.data_editor(
            wdf_clay,
            column_config=_CLAY_CFG,
            disabled=["Phi [Deg]"],
            use_container_width=True, num_rows="dynamic",
            hide_index=True, key="front_clay_editor",
        )
        if auto_sub:
            edf_clay["Density Sub [kN/m3]"] = (edf_clay["Density Moist [kN/m3]"] - 10.0).round(1)
        edf_clay["Phi [Deg]"] = 0.0
        st.session_state["front_clay_df"] = edf_clay
        st.markdown('<p class="locked-note">⬜ Phi locked (grey) — not used for Clay p-y</p>',
                    unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Update merged view for downstream (earth pressure, water pressure, etc.)
        st.session_state["front_layers_df"] = _merge_front_layers_df()

    # ── Layers behind ──
    with cfb:
        st.markdown("**Layers behind**")
        wdf_b = st.session_state["back_layers_df"].copy()
        if auto_sub:
            wdf_b["Density Sub [kN/m3]"] = (wdf_b["Density Moist [kN/m3]"] - 10.0).round(3)

        edf_b = st.data_editor(
            wdf_b, column_config=_layer_col_cfg(auto_sub),
            use_container_width=True, num_rows="dynamic",
            hide_index=True, key="back_layers_editor",
        )
        if auto_sub:
            edf_b["Density Sub [kN/m3]"] = (edf_b["Density Moist [kN/m3]"] - 10.0).round(3)
        edf_b = _enforce_soil_model_constraints(edf_b)
        st.session_state["back_layers_df"] = edf_b
        st.caption("Diagram only — not used in p-y calculation")

    # ── Diagram ──
    with cd2:
        _fl_now   = _get_front_layers()
        _bl_now   = _get_back_layers()
        _top2     = _get("top_elev", 0.0)
        _L2       = _get("L_m", 20.0)
        _wl2      = _get("water_level", -1.0)
        _wl2b     = _get("water_level_back", -1.0)
        _bot2     = _top2 - _L2
        _slb2     = _get("soil_level_back", 0.0)
        _slf2     = _get("soil_level_front", 0.0)
        ypad2     = max(_L2 * 0.08, 1.0)

        fig_s, ax_s = plt.subplots(figsize=(2.8, 7.5))
        ax_s.set_facecolor("white")
        ax_s.set_xlim(-3, 3)
        ax_s.set_ylim(_bot2 - ypad2 * 1.5, _top2 + ypad2 * 2.0)
        ax_s.set_xticks([])
        ax_s.set_ylabel("Elevation [m]", fontsize=9)
        ax_s.tick_params(axis="y", labelsize=8)
        for sp in ["top", "right", "bottom"]:
            ax_s.spines[sp].set_visible(False)

        # Fill zones: bottom=soil_level, top=top_elev (khi top_elev > soil_level)
        if _top2 > _slf2:
            ax_s.fill_between([-3, 0], [_slf2, _slf2], [_top2, _top2],
                              color="#c8a96e", alpha=0.35, hatch="\\\\",
                              linewidth=0.5, edgecolor="#a07040", zorder=1)
            ax_s.text(-1.5, (_slf2 + _top2) / 2, "Fill F",
                      fontsize=7, color="#7a5020", ha="center", va="center")

        # Front soil colored bands (left side: x -3 to -0.1)
        for i, (nm, zt, zb, gm, ph, stype, su_v, *_) in enumerate(_fl_now):
            mid = (zt + zb) / 2
            h   = abs(zt - zb)
            _is_clay = str(stype).strip().lower() == "clay"
            _band_color = LAYER_COLORS[i % len(LAYER_COLORS)] if not _is_clay else "#d6eaf8"
            ax_s.barh(mid, width=2.9, height=h, left=-3.0,
                      color=_band_color,
                      edgecolor="#aaa", lw=0.5, align="center",
                      hatch=HATCHES[i % len(HATCHES)], zorder=2)
            _lbl = f"Su={su_v:.0f} g={gm:.0f}" if _is_clay else f"φ={ph:.0f}° g={gm:.0f}"
            ax_s.text(-1.5, mid, _lbl,
                      ha="center", va="center", fontsize=6.0, color="#333")
            ax_s.plot([-3, 0], [zt, zt], color="goldenrod", lw=0.8, ls="--", zorder=3)
            ax_s.text(-2.9, zt + ypad2 * 0.12, f"Layer {i+1}",
                      fontsize=7, color="goldenrod", va="bottom")

        # Back soil colored bands (right side: x 0.1 to 3)
        for i, (nm, zt, zb, gm, ph, stype, su_v, *_) in enumerate(_bl_now):
            mid = (zt + zb) / 2
            h   = abs(zt - zb)
            _is_clay_b = str(stype).strip().lower() == "clay"
            _band_color_b = LAYER_COLORS[i % len(LAYER_COLORS)] if not _is_clay_b else "#d6eaf8"
            ax_s.barh(mid, width=2.9, height=h, left=0.1,
                      color=_band_color_b,
                      edgecolor="#aaa", lw=0.5, align="center",
                      hatch=HATCHES[i % len(HATCHES)], zorder=2, alpha=0.6)
            _lbl_b = f"Su={su_v:.0f} g={gm:.0f}" if _is_clay_b else f"φ={ph:.0f}° g={gm:.0f}"
            ax_s.text(1.55, mid, _lbl_b,
                      ha="center", va="center", fontsize=6.0, color="#555")
            ax_s.plot([0, 3], [zt, zt], color="goldenrod", lw=0.8, ls=":", zorder=3, alpha=0.7)

        # Natural ground lines
        ax_s.plot([-3, 0], [_slf2, _slf2], color="saddlebrown", lw=1.5, zorder=5)
        ax_s.text(-2.9, _slf2 + ypad2 * 0.15, "Ground F",
                  fontsize=7, color="saddlebrown", va="bottom", fontweight="bold")
        ax_s.plot([0, 3], [_slb2, _slb2], color="saddlebrown", lw=1.5, zorder=5)
        ax_s.text(0.15, _slb2 + ypad2 * 0.15, "Ground B",
                  fontsize=7, color="saddlebrown", va="bottom", fontweight="bold")

        # Pile: red vertical line
        ax_s.plot([0, 0], [_bot2, _top2], color="red", lw=3.0,
                  solid_capstyle="butt", zorder=10)

        # Water markers
        w_gap = ypad2 * 0.2
        # Front water (left side, solid)
        ax_s.plot([-2.8, -0.3], [_wl2, _wl2], color="steelblue", lw=1.8, zorder=7)
        ax_s.plot([-2.5, -0.5], [_wl2 - w_gap, _wl2 - w_gap],
                  color="steelblue", lw=1.3, zorder=7)
        ax_s.text(-2.9, _wl2 + ypad2 * 0.15, f"Water F  {_wl2:.2f}m",
                  fontsize=7, color="steelblue")
        # Back water (right side, dashed)
        ax_s.plot([0.3, 2.8], [_wl2b, _wl2b], color="steelblue", lw=1.8, zorder=7, ls="--")
        ax_s.plot([0.5, 2.5], [_wl2b - w_gap, _wl2b - w_gap],
                  color="steelblue", lw=1.3, zorder=7, ls="--")
        ax_s.text(0.2, _wl2b + ypad2 * 0.15, f"Water B  {_wl2b:.2f}m",
                  fontsize=7, color="steelblue")

        # SP Top marker
        ax_s.plot([-3, 3], [_top2, _top2], "#888", lw=0.8, ls="--", zorder=4)
        ax_s.text(-2.9, _top2 + ypad2 * 0.2, "SP Top", fontsize=7.5, color="#333")
        ax_s.text(0.15, _bot2 - ypad2 * 0.05, f"{_bot2:.1f} m",
                  fontsize=7, color="#555", va="top")

        # Side labels
        ax_s.text(-2.5, _bot2 - ypad2 * 0.8, "Front",
                  fontsize=8, color="#666", style="italic", ha="center")
        ax_s.text(1.5,  _bot2 - ypad2 * 0.8, "Back",
                  fontsize=8, color="#666", style="italic", ha="center")

        plt.tight_layout()
        st.pyplot(fig_s, use_container_width=True)
        plt.close()


# ── TAB 3: CONCENTRATED FORCES ────────────────────────────────────────────────
if _page == "Concentrated Forces":
    cf3, cd3 = st.columns([1, 1.3], gap="large")
    with cf3:
        st.markdown("**Concentrated Forces at Pile**")
        st.caption("Depth = 0 applies load at Pile Top Level (pile head).")

        st.markdown("---")
        st.markdown("*Head loads (quick input):*")
        ra, rb = st.columns(2)
        H_head = ra.number_input("H [kN]", value=100.0, step=10.0, key="H_head")
        M_head = rb.number_input("M [kN.m]", value=0.0, step=10.0, key="M_head")
        st.caption("H > 0: rightward  |  M > 0: counter-clockwise")
        st.markdown("---")
        st.markdown("*Force table (multiple point loads):*")

        fdf = st.data_editor(
            st.session_state["forces_df"],
            column_config={
                "Horiz. Component [kN/m]": st.column_config.NumberColumn(
                    "Horiz. Component\n[kN/m]", format="%.3f", step=1.0, width=130),
                "Vert. Component [kN/m]": st.column_config.NumberColumn(
                    "Vert. Component\n[kN/m]", format="%.3f", step=1.0, width=120),
                "Depth [m]": st.column_config.NumberColumn(
                    "Depth [m]", format="%.3f", step=0.5, width=80,
                    help="Depth below Pile Top Level (positive downward)"),
            },
            use_container_width=True, num_rows="dynamic",
            hide_index=True, key="forces_editor",
        )
        st.session_state["forces_df"] = fdf

    with cd3:
        _pile_H3 = sw_by_name(st.session_state.get("sel_pile", "SW-840"))["H"]
        fig3 = draw_pile_schematic(
            _get("L_m", 20.0), _get("water_level", -1.0),
            _get("top_elev", 0.0),
            _get("H_head", 100.0), _get("M_head", 0.0),
            _get_front_layers(), st.session_state.get("bc_type", "Fixed"), _pile_H3,
            soil_lvl_front=_get("soil_level_front", 0.0),
            soil_lvl_back=_get("soil_level_back", 0.0),
            back_layers=_get_back_layers(),
            gamma_fill=_get("gamma_fill", 18.0),
            phi_fill=_get("phi_fill", 25.0),
            c_fill=_get("c_fill", 5.0),
            water_lvl_back=_get("water_level_back", -1.0),
        )
        st.pyplot(fig3, use_container_width=True)
        plt.close()


# ── TAB 4: BOUSSINESQ ─────────────────────────────────────────────────────────
if _page == "Boussinesq":
    cb1, cb2 = st.columns([1, 1.6], gap="medium")
    with cb1:
        st.markdown("**Boussinesq Strip Surcharge — TCVN 11823-3 §10.6.2**")
        st.caption(
            "Nhap cac dai tai phan bo (strip surcharge) tren mat Front hoac Back. "
            "Depth Surcharge = do sau mat dat chiu tai so voi soil_level (0 = tai mat dat tu nhien)."
        )
        bdf = st.data_editor(
            st.session_state["boussinesq_df"],
            column_config={
                "Side": st.column_config.SelectboxColumn(
                    "Side", options=["Front", "Back"], required=True, width=70),
                "Distance Wall [m]":   st.column_config.NumberColumn(
                    "a — Dist Wall [m]", format="%.2f", step=0.5, min_value=0.0, width=120),
                "Width Surcharge [m]": st.column_config.NumberColumn(
                    "w — Width [m]",     format="%.1f", step=1.0, min_value=0.1, width=100),
                "Depth Surcharge [m]": st.column_config.NumberColumn(
                    "Depth [m]",         format="%.2f", step=0.5, width=90),
                "Surcharge [kN/m2]":   st.column_config.NumberColumn(
                    "q [kN/m²]",         format="%.1f", step=5.0, min_value=0.0, width=90),
            },
            use_container_width=True, num_rows="dynamic",
            hide_index=True, key="boussi_editor",
        )
        st.session_state["boussinesq_df"] = bdf

        # Quick result summary below editor
        if _HAS_BOUSSI and bdf is not None and not bdf.empty:
            _slf_b4 = _get("soil_level_front", 0.0)
            _slb_b4 = _get("soil_level_back",  0.0)
            _geom_b4 = _BGeom(
                top_elev=_get("top_elev", 2.7),
                pile_length=_get("L_m", 20.0),
                soil_level_front=_slf_b4,
                soil_level_back=_slb_b4,
            )
            _strips_b4 = []
            for _, _r in bdf.iterrows():
                _q4 = float(_r.get("Surcharge [kN/m2]", 0.0))
                if _q4 <= 0:
                    continue
                _side4 = str(_r.get("Side", "Front"))
                _slf_ref = _slf_b4 if _side4.lower() == "front" else _slb_b4
                _ref4  = _slf_ref - float(_r.get("Depth Surcharge [m]", 0.0))
                _strips_b4.append(_BStrip(
                    q=_q4,
                    a=float(_r.get("Distance Wall [m]", 0.0)),
                    w=float(_r.get("Width Surcharge [m]", 10.0)),
                    ref_surface=_ref4,
                    side=_side4,
                    label=f"{_side4} q={_q4:.0f}",
                ))
            if _strips_b4:
                _res_b4 = _boussi_compute_all(_geom_b4, _strips_b4, spacing=1.0)
                _sc1, _sc2, _sc3 = st.columns(3)
                _sc1.metric("F Front", f"{_res_b4['F_front']:.1f} kN/m",
                            f"z={_res_b4['z_front']:.2f} m")
                _sc2.metric("F Back",  f"{_res_b4['F_back']:.1f} kN/m",
                            f"z={_res_b4['z_back']:.2f} m")
                _sc3.metric("F Net",   f"{_res_b4['F_net']:.1f} kN/m")

    with cb2:
        if _HAS_BOUSSI and "bdf" in dir() and bdf is not None and not bdf.empty:
            try:
                if "_strips_b4" in dir() and _strips_b4:
                    st.pyplot(_res_b4["fig"], use_container_width=True)
                    plt.close(_res_b4["fig"])
                else:
                    raise ValueError("no strips")
            except Exception:
                _pile_H4b = sw_by_name(st.session_state.get("sel_pile", "SW-840"))["H"]
                _fig4b = draw_pile_schematic(
                    _get("L_m", 20.0), _get("water_level", -1.0),
                    _get("top_elev", 0.0), 0.0, 0.0,
                    _get_front_layers(), st.session_state.get("bc_type", "Fixed"), _pile_H4b,
                    soil_lvl_front=_get("soil_level_front", 0.0),
                    soil_lvl_back=_get("soil_level_back", 0.0),
                    back_layers=_get_back_layers(),
                    gamma_fill=_get("gamma_fill", 18.0),
                    phi_fill=_get("phi_fill", 25.0),
                    c_fill=_get("c_fill", 5.0),
                    water_lvl_back=_get("water_level_back", -1.0),
                )
                st.pyplot(_fig4b, use_container_width=True)
                plt.close()
        else:
            _pile_H4c = sw_by_name(st.session_state.get("sel_pile", "SW-840"))["H"]
            _fig4c = draw_pile_schematic(
                _get("L_m", 20.0), _get("water_level", -1.0),
                _get("top_elev", 0.0), 0.0, 0.0,
                _get_front_layers(), st.session_state.get("bc_type", "Fixed"), _pile_H4c,
                soil_lvl_front=_get("soil_level_front", 0.0),
                soil_lvl_back=_get("soil_level_back", 0.0),
                back_layers=_get_back_layers(),
                gamma_fill=_get("gamma_fill", 18.0),
                phi_fill=_get("phi_fill", 25.0),
                c_fill=_get("c_fill", 5.0),
                water_lvl_back=_get("water_level_back", -1.0),
            )
            st.pyplot(_fig4c, use_container_width=True)
            plt.close()


# ── TAB 5: SHEET PILE SECTION ─────────────────────────────────────────────────
if _page == "Sheet Pile Section":
    st.markdown("#### SW Pile")

    cat_df = pd.DataFrame([{
        "Name":         p["name"],
        "H [mm]":       p["H"],
        "t [mm]":       p["t"],
        "n strands":    p["n"],
        "phi [mm]":     p["phi_s"],
        "Atd [cm2]":    p["Atd"],
        "Itd [cm4]":    f"{p['Itd']:,}",
        "Mcr [T.m]":    f">={p['Mcr']:.2f}",
        "Weight [T]":   p["wT"],
        "L min [m]":    p["Lmin"],
        "L max [m]":    p["Lmax"],
        "Width [mm]":   p["width"],
    } for p in SW_CATALOG])

    sel_idx  = st.session_state.get("sel_pile_idx", 15)
    sel_name = st.selectbox(
        "Select pile type",
        options=SW_NAMES,
        index=sel_idx,
        key="sel_pile",
    )
    st.session_state["sel_pile_idx"] = SW_NAMES.index(sel_name)
    sel_pile = sw_by_name(sel_name)

    def _highlight(row):
        return ["background-color: #cce5ff; font-weight:bold"
                if row["Name"] == sel_name else "" for _ in row]

    st.dataframe(
        cat_df.style.apply(_highlight, axis=1),
        use_container_width=True,
        height=370,
        hide_index=True,
    )

    st.divider()
    cs1, cs2, cs3 = st.columns([1, 1, 1.3], gap="large")

    with cs1:
        st.markdown("**Concrete Grade**")
        grade_key = st.selectbox(
            "f'c", list(CONCRETE_GRADES.keys()),
            index=3, key="concrete_grade"
        )
        grade   = CONCRETE_GRADES[grade_key]
        Ec_kNm2 = grade["Ec_kNm2"]

        st.markdown(f"""
| Property | Value |
|----------|-------|
| f'c | {grade['fc']} MPa |
| Ec | {grade['Ec_MPa']:,} MPa |
| Ec | {Ec_kNm2/1e6:.3f} ×10⁶ kN/m² |
        """)

    with cs2:
        st.markdown("**Pile Length**")
        L_sel = st.number_input(
            f"Length [m]  ({sel_pile['Lmin']}..{sel_pile['Lmax']} m)",
            min_value=float(sel_pile["Lmin"]),
            max_value=float(sel_pile["Lmax"]),
            value=min(float(_get("L_m", 20.0)), float(sel_pile["Lmax"])),
            step=0.5, key="L_sel"
        )

        st.markdown("**Requested Safety**")
        safety = st.number_input("F_s", value=1.5, step=0.1, key="safety")

    with cs3:
        st.markdown("**PLAXIS Plate Parameters**")
        pp = sw_plaxis(sel_pile, Ec_kNm2)
        sp = sel_pile["width"] / 1000
        st.markdown(f"""
| Parameter | Value | Unit |
|-----------|-------|------|
| EA1 | {pp['EA1']:,.0f} | kN/m |
| EI | {pp['EI']:,.0f} | kN.m²/m |
| d_eq | {pp['d_eq']:.4f} | m |
| w | {pp['w']:.3f} | kN/m/m |
| Mcr | ≥ {pp['Mcr_kNm']:.1f} | kN.m |
| spacing | {sp:.3f} | m |
        """)

    st.divider()
    _, csec, _ = st.columns([1, 2, 1])
    with csec:
        fig_sec = draw_section(sel_pile)
        st.pyplot(fig_sec, use_container_width=True)
        plt.close()


# ── TAB 6: RESULTS ────────────────────────────────────────────────────────────
if _page == "P-y":
    with st.expander("Review Input Data", expanded=False):
        rr1, rr2 = st.columns(2)
        with rr1:
            _sn  = st.session_state.get("sel_pile", "SW-840")
            _L_r = _get("L_m", 20.0)
            st.markdown(f"""
| Parameter | Value |
|-----------|-------|
| Pile type | {_sn} |
| H | {sw_by_name(_sn)['H']} mm |
| t | {sw_by_name(_sn)['t']} mm |
| Pile Length | {_L_r} m |
| Water Level | {_get('water_level', -1.0)} m |
| Ground Front | {_get('soil_level_front', 0.0)} m |
| Ground Back | {_get('soil_level_back', 0.0)} m |
| H load | {_get('H_head', 100.0)} kN |
| M load | {_get('M_head', 0.0)} kN.m |
| Earth Support | {st.session_state.get('bc_type', 'Fixed')} |
| Concrete | {st.session_state.get('concrete_grade', "f'c = 70 MPa")} |
            """)
        with rr2:
            _lr = _get_front_layers()
            df_lay = pd.DataFrame(
                [
                    (nm, f"{zt:.2f}", f"{zb:.2f}", gm,
                     stype,
                     f"Su={su_v:.0f}" if str(stype).lower()=="clay" else f"φ={ph:.0f}°",
                     f"ε₅₀={e50:.3f}" if str(stype).lower()=="clay" else "—")
                    for nm, zt, zb, gm, ph, stype, su_v, e50 in _lr
                ],
                columns=["Layer", "Top [m]", "Tip [m]", "γ [kN/m3]", "Soil Type", "Strength", "ε₅₀"]
            )
            st.caption("Layers in Front (used for calculation)")
            st.dataframe(df_lay, use_container_width=True, hide_index=True)

    # ── Water Pressure Diagram ────────────────────────────────────────────────
    st.subheader("Water Pressure")
    _wp = None
    if _HAS_WP:
        _wp_mode = st.radio(
            "Calculation method",
            ["hydrostatic", "seepage"],
            horizontal=True,
            key="wp_mode",
            help="seepage = Terzaghi simplified (reduced net pressure due to flow path)",
        )
        _wg = _WaterGeom(
            top_elev         = _get("top_elev", 2.7),
            pile_length      = _get("L_m", 20.0),
            soil_level_front = _get("soil_level_front", 0.0),
            water_elev_front = _get("water_level", -1.0),
            water_elev_back  = _get("water_level_back", -1.0),
        )
        _fl_df  = st.session_state.get("front_layers_df", pd.DataFrame())
        _layerE = ([] if _fl_df is None or _fl_df.empty
                   else _fl_df["Layer Tip [m]"].dropna().tolist())
        _wp = _wp_compute_all(_wg, mode=_wp_mode, layer_elevs=_layerE)
        wpa, wpb, wpc = st.columns(3)
        wpa.metric("F Back",  f"{_wp['F_back']:.1f} kN/m",  f"z = {_wp['z_back']:.2f} m")
        wpb.metric("F Front", f"{_wp['F_front']:.1f} kN/m", f"z = {_wp['z_front']:.2f} m")
        wpc.metric("F Net",   f"{_wp['F_net']:.1f} kN/m",   f"z = {_wp['z_net']:.2f} m")
        st.pyplot(_wp["fig"], use_container_width=True)
        plt.close(_wp["fig"])
    else:
        st.info("water_pressure.py not found in scripts/")

    with st.expander("Theory — 22-water-pressure", expanded=False):
        st.markdown(_read_md("22-water-pressure.md"))

    st.divider()

    # ── Earth Pressure Diagram ─────────────────────────────────────────────────
    st.subheader("Earth Pressure")
    if _HAS_EP:
        _ep_ka = st.radio(
            "Ka / Kp method", ["rankine", "coulomb"],
            horizontal=True, key="ep_ka_method",
            help="Rankine: tường thẳng δ=0 | Coulomb: có ma sát tường δ (Bảng 20)",
        )
        _top_ep  = _get("top_elev", 2.7)
        _slb_ep  = _get("soil_level_back", 0.0)
        _ep_geom = _EpGeom(
            top_elev         = _top_ep,
            pile_length      = _get("L_m", 20.0),
            soil_level_front = _get("soil_level_front", 0.0),
            soil_level_back  = _slb_ep,
            water_elev_front = _get("water_level", -1.0),
            water_elev_back  = _get("water_level_back", -1.0),
            surcharge_front  = 0.0,
        )
        _fl_df2  = st.session_state.get("front_layers_df", pd.DataFrame())
        _bl_df2  = st.session_state.get("back_layers_df",  pd.DataFrame())
        _ep_fl   = _df_to_ep_layers(_fl_df2, _top_ep)
        _ep_bl   = _df_to_ep_layers(_bl_df2, _slb_ep)

        # Fill layer (đất đắp chỉ ở Front)
        _gf_ep  = _get("gamma_fill", 18.0)
        _ep_fill = _EpSoilLayer(
            tip_elev  = _get("soil_level_front", 0.0),
            gamma     = _gf_ep,
            gamma_sub = max(1.0, _gf_ep - 10.0),
            phi       = _get("phi_fill", 25.0),
            c         = _get("c_fill", 0.0),
        ) if _get("top_elev", 2.7) > _get("soil_level_front", 0.0) else None

        _ep = None
        if _ep_fl or _ep_bl:
            # Extract soil type lists for diagram labels
            _f_stypes = (_fl_df2["Soil Type"].tolist()
                         if _fl_df2 is not None and "Soil Type" in _fl_df2.columns else None)
            _f_sus    = (_fl_df2["Su [kN/m2]"].tolist()
                         if _fl_df2 is not None and "Su [kN/m2]" in _fl_df2.columns else None)
            _b_stypes = (_bl_df2["Soil Type"].tolist()
                         if _bl_df2 is not None and "Soil Type" in _bl_df2.columns else None)
            _b_sus    = (_bl_df2["Su [kN/m2]"].tolist()
                         if _bl_df2 is not None and "Su [kN/m2]" in _bl_df2.columns else None)
            _ep = _ep_compute_all(
                _ep_geom, _ep_fl, _ep_bl,
                fill=_ep_fill, ka_method=_ep_ka, kp_method=_ep_ka,
                front_soil_types=_f_stypes, front_sus=_f_sus,
                back_soil_types=_b_stypes,   back_sus=_b_sus,
            )
            epa, epb, epc = st.columns(3)
            epa.metric("F Active (Front)", f"{_ep['F_active']:.1f} kN/m",
                       f"z = {_ep['z_active']:.2f} m")
            epb.metric("F Passive (Back)", f"{_ep['F_passive']:.1f} kN/m",
                       f"z = {_ep['z_passive']:.2f} m")
            epc.metric("F Net (Active − Passive)", f"{_ep['F_net']:.1f} kN/m",
                       f"z = {_ep['z_net']:.2f} m")
            st.pyplot(_ep["fig"], use_container_width=True)
            plt.close(_ep["fig"])
        else:
            st.info("Nhập lớp đất ở tab Soil Layers trước.")
    else:
        st.info("earth_pressure.py not found in scripts/")

    with st.expander("Theory — 23-earth-pressure-diagram", expanded=False):
        st.markdown(_read_md("23-earth-pressure-diagram.md"))

    st.divider()

    # ── Fill Lateral Force ─────────────────────────────────────────────────────
    st.subheader("Fill Lateral Force — Dat dap → Luc tap trung")
    if _HAS_FILL:
        _fill_ka = st.radio(
            "Ka method (fill)",
            ["rankine", "coulomb"],
            horizontal=True,
            key="fill_ka_method",
        )
        _fill_geom = _FillGeom(
            top_elev         = _get("top_elev", 2.7),
            soil_level_front = _get("soil_level_front", 0.0),
            pile_length      = _get("L_m", 20.0),
            water_elev_front = _get("water_level", -1.0),
            gamma_fill       = _get("gamma_fill", 18.0),
            phi_fill         = _get("phi_fill", 25.0),
            c_fill           = _get("c_fill", 0.0),
        )
        _fill_res = _fill_compute_all(_fill_geom, ka_method=_fill_ka)
        fla, flb = st.columns(2)
        fla.metric("F — Fill Zone",
                   f"{_fill_res['F_fill_zone']:.1f} kN/m",
                   f"z = {_fill_res['z_fill_zone']:.2f} m")
        flb.metric("Ka (fill)",
                   f"{_fill_res['ka']:.4f}",
                   f"H_fill = {_fill_geom.H_fill:.2f} m")
        _flm1, _flm2 = st.columns(2)
        _flm1.caption(
            f"M about soil level = **{_fill_res['M_about_soil_level']:.1f} kN·m/m**"
        )
        _flm2.caption(
            f"M about pile tip = **{_fill_res['M_about_pile_tip']:.1f} kN·m/m**"
        )
        st.pyplot(_fill_res["fig"], use_container_width=True)
        plt.close(_fill_res["fig"])
    else:
        st.info("fill_lateral_force.py not found in scripts/")

    with st.expander("Theory — 24-fill-lateral-force", expanded=False):
        st.markdown(_read_md("24-fill-lateral-force.md"))

    # ── Boussinesq Surcharge ───────────────────────────────────────────────
    st.subheader("Boussinesq Surcharge — TCVN 11823-3 §10.6.2 Eq.(39)")
    if _HAS_BOUSSI:
        _bdf_r = st.session_state.get("boussinesq_df", pd.DataFrame())
        if _bdf_r is not None and not _bdf_r.empty:
            _slf_r = _get("soil_level_front", 0.0)
            _slb_r = _get("soil_level_back",  0.0)
            _boussi_geom = _BGeom(
                top_elev         = _get("top_elev", 2.7),
                pile_length      = _get("L_m", 20.0),
                soil_level_front = _slf_r,
                soil_level_back  = _slb_r,
            )
            _strips_r: list = []
            for _, _row in _bdf_r.iterrows():
                _q = float(_row.get("Surcharge [kN/m2]", 0.0))
                if _q <= 0:
                    continue
                _side_r = str(_row.get("Side", "Front"))
                _slf_ref_r = _slf_r if _side_r.lower() == "front" else _slb_r
                _ref_r = _slf_ref_r - float(_row.get("Depth Surcharge [m]", 0.0))
                _strips_r.append(_BStrip(
                    q=_q,
                    a=float(_row.get("Distance Wall [m]", 0.0)),
                    w=float(_row.get("Width Surcharge [m]", 10.0)),
                    ref_surface=_ref_r,
                    side=_side_r,
                    label=f"{_side_r} q={_q:.0f}",
                ))
            _boussi_res = None
            if _strips_r:
                _boussi_res = _boussi_compute_all(_boussi_geom, _strips_r, spacing=1.0)
                _bca, _bcb, _bcc, _bcd = st.columns(4)
                _bca.metric("F Front",
                            f"{_boussi_res['F_front']:.1f} kN/m",
                            f"z={_boussi_res['z_front']:.2f} m")
                _bcb.metric("F Back",
                            f"{_boussi_res['F_back']:.1f} kN/m",
                            f"z={_boussi_res['z_back']:.2f} m")
                _bcc.metric("F Net (Front−Back)",
                            f"{_boussi_res['F_net']:.1f} kN/m")
                _bcd.metric("n_pts", f"{len(_boussi_res['elevs'])}",
                            f"spacing 1 m")
                _bm1, _bm2 = st.columns(2)
                _bm1.caption(
                    f"M_top Front={_boussi_res['M_top_front']:.1f}  "
                    f"M_tip Front={_boussi_res['M_tip_front']:.1f} kN·m/m"
                )
                _bm2.caption(
                    f"M_top Back={_boussi_res['M_top_back']:.1f}  "
                    f"M_tip Back={_boussi_res['M_tip_back']:.1f} kN·m/m"
                )
                st.pyplot(_boussi_res["fig"], use_container_width=True)
                plt.close(_boussi_res["fig"])
            else:
                st.info("Tat ca tai trong q = 0 — nhap gia tri q > 0 trong tab Boussinesq.")
        else:
            st.info("Chua co du lieu tai trong — nhap trong tab Boussinesq.")
    else:
        st.info("boussinesq_surcharge.py not found in scripts/")

    with st.expander("Theory — 25-boussinesq-surcharge", expanded=False):
        st.markdown(_read_md("25-boussinesq-surcharge.md"))

    st.divider()

    # ── Capture pressure arrays để đưa vào model (trước nút Calculate) ────────
    _dist_loads: dict = {}
    if _ep is not None:
        _dist_loads["ep"] = {"elevs": _ep["elevs"].copy(),
                              "net_h": _ep["net_h"].copy()}
    if _wp is not None:
        _dist_loads["wp"] = {"elevs": _wp["elevs"].copy(),
                              "p_net": _wp["p_net"].copy()}
    if _boussi_res is not None:
        _dist_loads["bq"] = {"elevs": _boussi_res["elevs"].copy(),
                              "front_p": _boussi_res["front_pressure"].copy(),
                              "back_p":  _boussi_res["back_pressure"].copy()}
    # Fill lateral force — áp lực ngang đất đắp (zone: top_elev → soil_level_front)
    if _HAS_FILL and "_fill_res" in dir() and _fill_res is not None:
        _fev = _fill_res.get("fill_elevs")
        _fpr = _fill_res.get("fill_pressure")
        if _fev is not None and _fpr is not None and len(_fev) > 1:
            _dist_loads["fill"] = {
                "elevs":    _fev.copy(),
                "pressure": _fpr.copy(),
            }

    _incl_dist = st.checkbox(
        "Bao gom tai trong phan bo vao mo hinh (earth, water, Boussinesq, fill)",
        value=True,
        help=(
            "Chia ap luc phan bo (dat, nuoc, Boussinesq, dat dap) thanh luc tap trung "
            "1 m / diem theo chieu cao coc va dua vao mo hinh openpile.\n\n"
            "Quy uoc dau: Py duong = huong tu Front sang Back "
            "(cung chieu ap luc dat chu dong).\n"
            "Fill: ap luc dat dap vung top_elev → soil_level_front, sign = +1 (cung chieu active)."
        ),
    )

    calc_btn = st.button("Calculate", type="primary")

    if calc_btn:
        _L_r    = _get("L_m", 20.0)
        _wl_r   = _get("water_level", -1.0)
        _top_r  = _get("top_elev", 2.7)
        _H_r    = _get("H_head", 100.0)
        _M_r    = _get("M_head", 0.0)
        _sn     = st.session_state.get("sel_pile", "SW-840")
        _sp     = sw_by_name(_sn)
        _grade  = CONCRETE_GRADES.get(
            st.session_state.get("concrete_grade", "f'c = 70 MPa"),
            CONCRETE_GRADES["f'c = 70 MPa"]
        )
        _layers_r = _get_front_layers()

        # Clip layers to pile length
        layers_clipped = []
        bot_elev = _top_r - _L_r
        for nm, zt, zb, gm, ph, stype, su_v, e50 in _layers_r:
            if zt <= bot_elev:
                break
            zb_clip = max(zb, bot_elev)
            layers_clipped.append((nm, zt, zb_clip, gm, ph, stype, su_v, e50))
        if layers_clipped:
            last = layers_clipped[-1]
            if last[2] > bot_elev:
                layers_clipped[-1] = (last[0], last[1], bot_elev, last[3], last[4],
                                      last[5], last[6], last[7])

        if not layers_clipped:
            st.error("No soil layers cover the pile embedment. Check Layer Tip values.")
            st.stop()

        D_eq  = _sp["H"] / 1000
        t_eq  = _sp["t"] / 1000

        with st.spinner("Calculating..."):
            try:
                from openpile.construct import (
                    Pile, SoilProfile, Layer, Model, BoundaryFixation,
                )
                from openpile.soilmodels import API_sand, API_clay
                from openpile.winkler import winkler

                def _lateral_model(stype, ph, su_v, e50):
                    """Return the correct openpile lateral model for each layer."""
                    if stype.strip().lower() == "clay":
                        _su  = max(su_v, 0.1)   # API_clay requires Su > 0
                        _e50 = max(e50, 0.001)
                        return API_clay(Su=_su, eps50=_e50, kind="static", J=0.5)
                    else:
                        _phi = max(ph, 1.0)      # API_sand requires phi > 0
                        return API_sand(phi=_phi, kind="static")

                pile_op = Pile.create_tubular(
                    name=_sn,
                    top_elevation=_top_r,
                    bottom_elevation=bot_elev,
                    diameter=D_eq,
                    wt=t_eq,
                    material="Concrete",
                )
                _sp_top = layers_clipped[0][1]   # first layer top (= soil surface)
                sp_op = SoilProfile(
                    name="Soil Profile",
                    top_elevation=_sp_top,
                    water_line=_wl_r,
                    layers=[
                        Layer(name=nm, top=zt, bottom=zb,
                              weight=gm,
                              lateral_model=_lateral_model(stype, ph, su_v, e50))
                        for nm, zt, zb, gm, ph, stype, su_v, e50 in layers_clipped
                    ],
                )
                bc = [BoundaryFixation(elevation=bot_elev, x=True, y=True, z=True)]
                # Precompute 1m-grid midpoints so set_pointload finds mesh nodes
                _n_main = max(2, round(abs(_top_r - bot_elev)) + 1)
                _pts_main = np.linspace(_top_r, bot_elev, _n_main)
                _x2mesh_main = [float((_pts_main[k] + _pts_main[k+1]) / 2.0)
                                for k in range(len(_pts_main) - 1)]
                model = Model(name="run", pile=pile_op, soil=sp_op,
                              boundary_conditions=bc, x2mesh=_x2mesh_main)
                if abs(_H_r) > 1e-3:
                    model.set_pointload(elevation=_top_r, Py=_H_r)
                if abs(_M_r) > 1e-3:
                    model.set_pointload(elevation=_top_r, Mx=_M_r)

                # ── Distributed lateral loads → luc tap trung 1m/diem ────────
                _dbg_loads: list[tuple] = []   # (source, elev, Py) for debug

                def _apply_dist_load(mdl, elevs, pressure, sign,
                                     e_top, e_bot, src_name, min_F=0.05):
                    """Chia ap luc phan bo thanh luc tap trung 1m.
                    Trapezoid tren moi doan 1m, ap dung set_pointload tai midpoint.
                    sign: +1 → Py duong (cung chieu ap luc dat chu dong).
                    """
                    n = max(2, round(abs(e_top - e_bot)) + 1)
                    pts = np.linspace(e_top, e_bot, n)
                    ev_asc = np.sort(elevs)
                    pr_asc = pressure[np.argsort(elevs)]
                    for k in range(len(pts) - 1):
                        e_hi, e_lo = pts[k], pts[k + 1]
                        mid = (e_hi + e_lo) / 2.0
                        dz  = abs(e_hi - e_lo)
                        p_hi = float(np.interp(e_hi, ev_asc, pr_asc))
                        p_lo = float(np.interp(e_lo, ev_asc, pr_asc))
                        F_i  = sign * (p_hi + p_lo) / 2.0 * dz  # kN/m
                        if abs(F_i) >= min_F:
                            mdl.set_pointload(elevation=mid, Py=F_i)
                            _dbg_loads.append((src_name, mid, F_i))

                if _incl_dist and _dist_loads:
                    # 1. Net earth pressure (active − passive)
                    #    active pushes toward Front → Py positive → sign = +1
                    if "ep" in _dist_loads:
                        _d = _dist_loads["ep"]
                        _apply_dist_load(model, _d["elevs"], _d["net_h"],
                                         +1, _top_r, bot_elev, "earth")

                    # 2. Net water pressure (p_back − p_front, positive = toward Front)
                    #    same direction as active → sign = +1
                    if "wp" in _dist_loads:
                        _d = _dist_loads["wp"]
                        _apply_dist_load(model, _d["elevs"], _d["p_net"],
                                         +1, _top_r, bot_elev, "water")

                    # 3. Boussinesq net (front_p − back_p)
                    #    front_p pushes pile toward Back → sign = −1
                    if "bq" in _dist_loads:
                        _d = _dist_loads["bq"]
                        _bq_net = _d["front_p"] - _d["back_p"]
                        _apply_dist_load(model, _d["elevs"], _bq_net,
                                         -1, _top_r, bot_elev, "bouss")

                    # 4. Fill lateral force (đất đắp, zone trên mặt đất tự nhiên)
                    #    Áp lực đất đắp đẩy tường từ Front → sign = +1
                    if "fill" in _dist_loads:
                        _d = _dist_loads["fill"]
                        _apply_dist_load(model, _d["elevs"], _d["pressure"],
                                         +1, _top_r, bot_elev, "fill")

                with st.expander("Debug — Distributed loads applied", expanded=False):
                    _dl_keys = list(_dist_loads.keys())
                    st.caption(
                        f"_dist_loads keys: {_dl_keys} | "
                        f"_incl_dist: {_incl_dist} | "
                        f"pointloads applied: {len(_dbg_loads)}"
                    )
                    if _dbg_loads:
                        import pandas as _pd2
                        _dbg_df = _pd2.DataFrame(
                            _dbg_loads, columns=["Source", "Elevation [m]", "Py [kN/m]"]
                        )
                        _grp = _dbg_df.groupby("Source")["Py [kN/m]"].sum().reset_index()
                        _grp.columns = ["Source", "Total Py [kN/m]"]
                        st.dataframe(_grp, use_container_width=True, hide_index=True)
                    else:
                        st.caption("No distributed point loads were applied.")

                result = winkler(model)
                st.session_state["result"]         = result
                st.session_state["layers_clipped"] = layers_clipped
                st.session_state["calc_params"]    = {
                    "pile": _sn, "L_m": _L_r, "H": _H_r, "M": _M_r,
                    "water": _wl_r, "top": _top_r,
                    "Mcr_kNm": sw_plaxis(_sp, _grade["Ec_kNm2"])["Mcr_kNm"],
                }
                # Lưu distributed loads để dùng trong component analysis
                st.session_state["dist_loads_stored"] = {
                    k: {kk: (vv.copy() if isinstance(vv, np.ndarray) else vv)
                        for kk, vv in v.items()}
                    for k, v in _dist_loads.items()
                }
                st.session_state["incl_dist_stored"] = _incl_dist
                st.success("Calculation converged.")
            except Exception as exc:
                st.error(f"Calculation error: {exc}")
                st.stop()

    # Show results
    if st.session_state.get("result") is not None:
        result         = st.session_state["result"]
        params         = st.session_state.get("calc_params", {})
        layers_clipped = st.session_state.get("layers_clipped", [])

        elev   = result.deflection["Elevation [m]"].values
        y_mm   = result.deflection["Deflection [m]"].values * 1000
        fdf_r  = result.forces.drop_duplicates(subset="Elevation [m]", keep="first")
        elev_f = fdf_r["Elevation [m]"].values
        V_arr  = fdf_r["V [kN]"].values
        M_arr  = fdf_r["M [kNm]"].values

        y_head = y_mm[0]
        y_max  = np.nanmax(np.abs(y_mm))
        V_max  = np.nanmax(np.abs(V_arr))
        M_max  = np.nanmax(np.abs(M_arr))
        z_Vmax = elev_f[np.nanargmax(np.abs(V_arr))]
        z_Mmax = elev_f[np.nanargmax(np.abs(M_arr))]
        Mcr    = params.get("Mcr_kNm", 0)

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Head deflection", f"{y_head:.3f} mm")
        k2.metric("Max deflection",  f"{y_max:.3f} mm")
        k3.metric(f"M_max  (elev={z_Mmax:.1f}m)", f"{M_max:.1f} kN.m")
        k4.metric(f"V_max  (elev={z_Vmax:.1f}m)", f"{V_max:.1f} kN")
        k5.metric(
            "M_max / Mcr",
            f"{M_max/Mcr:.2f}" if Mcr > 0 else "—",
            delta="OK" if Mcr > 0 and M_max < Mcr else ("CRACK" if Mcr > 0 else ""),
            delta_color="normal" if Mcr > 0 and M_max < Mcr else "inverse",
        )
        st.divider()

        _L_p   = params.get("L_m", 20.0)
        _wl_p  = params.get("water", -1.0)
        _top_p = params.get("top", 0.0)
        _bot_p = _top_p - _L_p

        fig, axes = plt.subplots(1, 3, figsize=(12, 8), sharey=True)
        fig.suptitle(
            f"{params.get('pile')}  L={_L_p}m  |  "
            f"H={params.get('H')} kN  M={params.get('M')} kN.m",
            fontsize=11, fontweight="bold",
        )

        def _bg(ax):
            # soil layer colour bands
            for i, (nm, zt, zb, gm, ph, *_) in enumerate(layers_clipped):
                ax.axhspan(zt, zb, alpha=0.15, color=LAYER_COLORS[i % len(LAYER_COLORS)])
            # above-ground zone (top_elev → soil surface): light grey shading
            _soil_surf = layers_clipped[0][1] if layers_clipped else _top_p
            if _soil_surf < _top_p:
                ax.axhspan(_soil_surf, _top_p, alpha=0.07, color="#888888")
            # water level
            if _bot_p < _wl_p < _top_p:
                ax.axhline(_wl_p, color="steelblue", lw=1.2, ls="--", alpha=0.6,
                           label=f"WL {_wl_p:.1f} m")
            # pile top (đỉnh cừ)
            ax.axhline(_top_p, color="#333", lw=1.2, ls="--", alpha=0.7)
            ax.text(0.01, _top_p, f" +{_top_p:.2f} m (đỉnh)", fontsize=6.5,
                    color="#333", va="bottom", transform=ax.get_yaxis_transform())
            # soil surface
            if _soil_surf < _top_p:
                ax.axhline(_soil_surf, color="#8B6914", lw=0.9, ls="--", alpha=0.6)
                ax.text(0.01, _soil_surf, f" {_soil_surf:.2f} m (đất tự nhiên)",
                        fontsize=6, color="#8B6914", va="bottom",
                        transform=ax.get_yaxis_transform())
            # pile tip (mũi cừ)
            ax.axhline(_bot_p, color="#444", lw=1.0, ls="-", alpha=0.6)
            ax.text(0.99, _bot_p, f"{_bot_p:.2f} m (mũi) ", fontsize=6.5,
                    color="#444", va="top", ha="right",
                    transform=ax.get_yaxis_transform())
            # y-axis: strictly from pile tip to pile top, fixed 2% margin
            _margin = _L_p * 0.02
            ax.set_ylim(_bot_p - _margin, _top_p + _margin)
            ax.axvline(0, color="k", lw=0.7)

        ax = axes[0]
        _bg(ax)
        ax.plot(y_mm, elev, "b-o", ms=2.5, lw=1.5)
        ax.fill_betweenx(elev, 0, y_mm, where=y_mm > 0, alpha=0.12, color="blue")
        ax.fill_betweenx(elev, 0, y_mm, where=y_mm < 0, alpha=0.12, color="red")
        ax.set_xlabel("Deflection y [mm]")
        ax.set_ylabel("Elevation [m]")
        ax.set_title("Lateral Deflection")
        ax.annotate(f"{y_head:.2f} mm", xy=(y_head, _top_p),
                    xytext=(y_head * 0.35, _top_p - 2.0),
                    arrowprops=dict(arrowstyle="->", color="navy"),
                    color="navy", fontsize=8)

        ax = axes[1]
        _bg(ax)
        ax.plot(V_arr, elev_f, "g-o", ms=2.5, lw=1.5)
        ax.fill_betweenx(elev_f, 0, V_arr, alpha=0.12, color="green")
        ax.set_xlabel("Shear Force V [kN]")
        ax.set_title("Shear Force")
        idx_v = np.nanargmax(np.abs(V_arr))
        ax.annotate(f"{V_max:.1f} kN\nelev={z_Vmax:.1f}m",
                    xy=(V_arr[idx_v], elev_f[idx_v]),
                    xytext=(V_arr[idx_v] * 0.3, elev_f[idx_v] + 1.5),
                    arrowprops=dict(arrowstyle="->", color="darkgreen"),
                    color="darkgreen", fontsize=8)

        ax = axes[2]
        _bg(ax)
        ax.plot(M_arr, elev_f, "r-o", ms=2.5, lw=1.5)
        ax.fill_betweenx(elev_f, 0, M_arr, alpha=0.12, color="red")
        if Mcr > 0:
            ax.axvline(Mcr, color="orange", lw=1.2, ls="--", alpha=0.8)
            ax.axvline(-Mcr, color="orange", lw=1.2, ls="--", alpha=0.8)
            ax.text(Mcr * 0.9, _bot_p + 0.5, f"Mcr={Mcr:.0f}",
                    fontsize=7, color="darkorange", ha="right")
        ax.set_xlabel("Bending Moment M [kN.m]")
        ax.set_title("Bending Moment")
        idx_m = np.nanargmax(np.abs(M_arr))
        ax.annotate(f"{M_max:.1f} kN.m\nelev={z_Mmax:.1f}m",
                    xy=(M_arr[idx_m], elev_f[idx_m]),
                    xytext=(M_arr[idx_m] * 0.3, elev_f[idx_m] + 1.5),
                    arrowprops=dict(arrowstyle="->", color="darkred"),
                    color="darkred", fontsize=8)

        for nm, zt, zb, gm, ph, stype, su_v, *_ in layers_clipped:
            _is_c = str(stype).strip().lower() == "clay"
            _lbl  = f" {nm}  Su={su_v:.0f}" if _is_c else f" {nm}  φ={ph:.0f}°"
            axes[0].text(0, (zt+zb)/2, _lbl, fontsize=6.5, color="#555", va="center")

        plt.tight_layout()
        st.pyplot(fig)
        plt.close()

        st.divider()
        st.subheader("Detailed Results")
        df_out = pd.DataFrame({"Elevation [m]": elev,
                                "Deflection [mm]": np.round(y_mm, 4)})
        df_frc = pd.DataFrame({"Elevation [m]": elev_f,
                                "Shear V [kN]": np.round(V_arr, 2),
                                "Moment M [kN.m]": np.round(M_arr, 2)})
        df_full = (pd.merge(df_out, df_frc, on="Elevation [m]", how="outer")
                   .sort_values("Elevation [m]", ascending=False)
                   .reset_index(drop=True))
        st.dataframe(df_full, use_container_width=True, height=350)

        csv = df_full.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "Export CSV", data=csv,
            file_name=f"{params.get('pile')}_L{_L_p}_H{params.get('H')}.csv",
            mime="text/csv",
        )

        # ── Component Analysis ────────────────────────────────────────────────────
        _dl2   = st.session_state.get("dist_loads_stored", {})
        _incl2 = st.session_state.get("incl_dist_stored", False)

        if _incl2 and _dl2:
            st.divider()
            st.subheader("Phan tich tung thanh phan tai trong")
            st.caption(
                "Chay rieng tung thanh phan tai trong tren cung mo hinh dat — "
                "so sanh dong gop cua moi loai vao chuyen vi / luc cat / moment."
            )

            try:
                from openpile.construct import (
                    Pile as _Pile2, SoilProfile as _SP2,
                    Layer as _Layer2, Model as _Model2,
                    BoundaryFixation as _BF2,
                )
                from openpile.soilmodels import API_sand as _Sand2, API_clay as _Clay2
                from openpile.winkler import winkler as _wk2

                _sn2  = params["pile"]
                _sp2  = sw_by_name(_sn2)
                _D2   = _sp2["H"] / 1000
                _t2   = _sp2["t"] / 1000
                _H2   = params.get("H", 0.0)
                _M2   = params.get("M", 0.0)
                _Mcr2 = params.get("Mcr_kNm", 0)

                def _lat2(stype, ph, su_v, e50):
                    if str(stype).strip().lower() == "clay":
                        return _Clay2(Su=max(su_v, 0.1), eps50=max(e50, 0.001),
                                      kind="static", J=0.5)
                    return _Sand2(phi=max(ph, 1.0), kind="static")

                # Precompute 1m-interval grid + midpoints (phải có trước _new_model2)
                _GRID2 = np.linspace(_top_p, _bot_p,
                                     max(2, round(abs(_top_p - _bot_p)) + 1))
                _MIDS2 = [float((_GRID2[k] + _GRID2[k+1]) / 2.0)
                          for k in range(len(_GRID2) - 1)]

                def _new_model2():
                    pile2 = _Pile2.create_tubular(
                        name=_sn2, top_elevation=_top_p, bottom_elevation=_bot_p,
                        diameter=_D2, wt=_t2, material="Concrete",
                    )
                    _sp2_top = layers_clipped[0][1]   # first layer top = soil surface
                    sp2 = _SP2(
                        name="SP", top_elevation=_sp2_top, water_line=_wl_p,
                        layers=[
                            _Layer2(name=nm, top=zt, bottom=zb, weight=gm,
                                    lateral_model=_lat2(stype, ph, su_v, e50))
                            for nm, zt, zb, gm, ph, stype, su_v, e50 in layers_clipped
                        ],
                    )
                    bc2 = [_BF2(elevation=_bot_p, x=True, y=True, z=True)]
                    # x2mesh đảm bảo tất cả midpoint elevations là mesh nodes
                    return _Model2(name="c", pile=pile2, soil=sp2,
                                   boundary_conditions=bc2, x2mesh=_MIDS2)

                def _interp2(elevs_raw, vals_raw, sign):
                    ev = np.sort(elevs_raw)
                    vv = vals_raw[np.argsort(elevs_raw)]
                    out = []
                    for k in range(len(_GRID2) - 1):
                        e_hi, e_lo = _GRID2[k], _GRID2[k + 1]
                        mid = (e_hi + e_lo) / 2.0
                        dz  = abs(e_hi - e_lo)
                        F   = sign * (float(np.interp(e_hi, ev, vv)) +
                                      float(np.interp(e_lo, ev, vv))) / 2.0 * dz
                        if abs(F) >= 0.05:
                            out.append((mid, F))
                    return out

                _lds_ep = (_interp2(_dl2["ep"]["elevs"], _dl2["ep"]["net_h"], +1)
                           if "ep" in _dl2 else [])
                _lds_wp = (_interp2(_dl2["wp"]["elevs"], _dl2["wp"]["p_net"], +1)
                           if "wp" in _dl2 else [])
                _lds_bq = (_interp2(
                               _dl2["bq"]["elevs"],
                               _dl2["bq"]["front_p"] - _dl2["bq"]["back_p"], -1)
                           if "bq" in _dl2 else [])
                _lds_fill = (_interp2(_dl2["fill"]["elevs"], _dl2["fill"]["pressure"], +1)
                             if "fill" in _dl2 else [])

                def _run2(head_H, head_M, load_lists):
                    mdl = _new_model2()
                    if abs(head_H) > 1e-3:
                        mdl.set_pointload(elevation=_top_p, Py=head_H)
                    if abs(head_M) > 1e-3:
                        mdl.set_pointload(elevation=_top_p, Mx=head_M)
                    for llist in load_lists:
                        for mid, F in llist:
                            mdl.set_pointload(elevation=mid, Py=F)
                    r = _wk2(mdl)
                    e_y = r.deflection["Elevation [m]"].values
                    y_m = r.deflection["Deflection [m]"].values * 1000
                    fdf = r.forces.drop_duplicates("Elevation [m]", keep="first")
                    return e_y, y_m, fdf["Elevation [m]"].values, \
                           fdf["V [kN]"].values, fdf["M [kNm]"].values

                def _has_finite(arr):
                    return arr.size > 0 and np.any(np.isfinite(arr))

                def _safe_x(val, fallback=0.5):
                    """Trả về val nếu finite, ngược lại fallback."""
                    return float(val) if np.isfinite(val) else fallback

                def _plot3(e_y, y_m, e_f, V_a, M_a, color, title):
                    fig3, ax3 = plt.subplots(1, 3, figsize=(11, 6), sharey=True)
                    fig3.suptitle(title, fontsize=10, fontweight="bold")
                    for _ax in ax3:
                        _bg(_ax)

                    # ── Deflection ──────────────────────────────────────────
                    _y_fin = y_m[np.isfinite(y_m)] if y_m.size else np.array([])
                    ax3[0].plot(y_m, e_y, color=color, lw=1.5, marker="o", ms=2)
                    ax3[0].fill_betweenx(e_y, 0, np.where(np.isfinite(y_m), y_m, 0),
                                         alpha=0.13, color=color)
                    ax3[0].set_xlabel("y [mm]"); ax3[0].set_ylabel("Elevation [m]")
                    ax3[0].set_title("Chuyen vi ngang")
                    if _y_fin.size and np.isfinite(y_m[0]):
                        _xh = _safe_x(y_m[0] * 0.35, 0.5)
                        ax3[0].annotate(
                            f"{y_m[0]:.2f} mm",
                            xy=(y_m[0], e_y[0]),
                            xytext=(_xh if _xh != 0 else 0.5, e_y[0] - 2.0),
                            arrowprops=dict(arrowstyle="->", color=color),
                            color=color, fontsize=8,
                        )

                    # ── Shear ───────────────────────────────────────────────
                    ax3[1].plot(V_a, e_f, color=color, lw=1.5, marker="o", ms=2)
                    ax3[1].fill_betweenx(e_f, 0, np.where(np.isfinite(V_a), V_a, 0),
                                         alpha=0.13, color=color)
                    ax3[1].set_xlabel("V [kN]"); ax3[1].set_title("Luc cat")
                    if _has_finite(V_a):
                        iv = int(np.nanargmax(np.abs(np.where(np.isfinite(V_a), V_a, 0))))
                        _xv = _safe_x(V_a[iv] * 0.3, 1.0)
                        ax3[1].annotate(
                            f"{V_a[iv]:.1f} kN\nelev={e_f[iv]:.1f}m",
                            xy=(V_a[iv], e_f[iv]),
                            xytext=(_xv if _xv != 0 else 1.0, e_f[iv] + 1.5),
                            arrowprops=dict(arrowstyle="->", color=color),
                            color=color, fontsize=8,
                        )

                    # ── Moment ──────────────────────────────────────────────
                    ax3[2].plot(M_a, e_f, color=color, lw=1.5, marker="o", ms=2)
                    ax3[2].fill_betweenx(e_f, 0, np.where(np.isfinite(M_a), M_a, 0),
                                         alpha=0.13, color=color)
                    ax3[2].set_xlabel("M [kN.m]"); ax3[2].set_title("Moment uon")
                    if _Mcr2 > 0:
                        for _s in [1, -1]:
                            ax3[2].axvline(_s * _Mcr2, color="orange",
                                           lw=1.2, ls="--", alpha=0.7)
                        ax3[2].text(_Mcr2 * 0.9, _bot_p + 0.5,
                                    f"Mcr={_Mcr2:.0f}", fontsize=7,
                                    color="darkorange", ha="right")
                    if _has_finite(M_a):
                        im = int(np.nanargmax(np.abs(np.where(np.isfinite(M_a), M_a, 0))))
                        _xm = _safe_x(M_a[im] * 0.3, 1.0)
                        ax3[2].annotate(
                            f"{M_a[im]:.1f} kN.m\nelev={e_f[im]:.1f}m",
                            xy=(M_a[im], e_f[im]),
                            xytext=(_xm if _xm != 0 else 1.0, e_f[im] + 1.5),
                            arrowprops=dict(arrowstyle="->", color=color),
                            color=color, fontsize=8,
                        )
                    plt.tight_layout()
                    return fig3

                # Định nghĩa từng thành phần
                _COMPS = [
                    ("H + M tap trung dau coc",
                     _H2, _M2, [],
                     "#555555", "26-api-clay-matlock.md"),
                    ("Ap luc dat phan bo (earth net)",
                     0.0, 0.0, [_lds_ep],
                     "#e74c3c", "23-earth-pressure-diagram.md"),
                    ("Ap luc nuoc phan bo (water net)",
                     0.0, 0.0, [_lds_wp],
                     "#1a8cff", "22-water-pressure.md"),
                    ("Boussinesq phan bo",
                     0.0, 0.0, [_lds_bq],
                     "#9c27b0", "25-boussinesq-surcharge.md"),
                    ("Dat dap (fill lateral force)",
                     0.0, 0.0, [_lds_fill],
                     "#e67e22", "24-fill-lateral-force.md"),
                ]

                with st.spinner("Dang tinh toan tung thanh phan..."):
                    for _label, _hH, _hM, _lls, _clr, _mdfile in _COMPS:
                        # Bỏ qua thành phần không có tải
                        _has_load = (abs(_hH) > 1e-3 or abs(_hM) > 1e-3
                                     or any(len(ll) > 0 for ll in _lls))
                        if not _has_load:
                            continue
                        try:
                            _ey2, _ym2, _ef2, _V2, _M2r = _run2(_hH, _hM, _lls)
                        except Exception as _e_comp:
                            st.warning(f"{_label}: loi tinh toan — {_e_comp}")
                            continue
                        with st.expander(f"[{_label}]", expanded=True):
                            _f3 = _plot3(_ey2, _ym2, _ef2, _V2, _M2r, _clr, _label)
                            st.pyplot(_f3, use_container_width=True)
                            plt.close(_f3)
                            with st.expander(f"Theory — {_mdfile.removesuffix('.md')}", expanded=False):
                                st.markdown(_read_md(_mdfile))

                    # Tổng hợp — toàn bộ tải
                    try:
                        _eyT, _ymT, _efT, _VT, _MT = _run2(
                            _H2, _M2, [_lds_ep, _lds_wp, _lds_bq, _lds_fill])
                        with st.expander(
                            "TONG HOP — H+M + earth + water + Boussinesq + fill",
                            expanded=True,
                        ):
                            _fT = _plot3(_eyT, _ymT, _efT, _VT, _MT,
                                         "#1a1a2e", "Tong hop tat ca tai trong")
                            st.pyplot(_fT, use_container_width=True)
                            plt.close(_fT)
                            with st.expander("Theory — 27-py-component-analysis",
                                             expanded=False):
                                st.markdown(_read_md("27-py-component-analysis.md"))
                    except Exception as _e_tot:
                        st.warning(f"Tong hop: loi tinh toan — {_e_tot}")

            except Exception as _exc_comp:
                st.error(f"Component analysis error: {_exc_comp}")


# ── TAB 7: BEARING CAPACITY ───────────────────────────────────────────────────
if _page == "Bearing Capacity":
    if _HAS_BC_TAB:
        _render_bc()
    else:
        st.error(
            "Module `bearing_capacity_tab.py` not found in scripts/.\n\n"
            "Make sure `geotech-staff-engineer` is installed:\n```\n"
            "pip install geotech-staff-engineer\n```"
        )


# ── TAB 8: SHEET PILE ─────────────────────────────────────────────────────────
if _page == "Sheet Pile Design":
    if _HAS_SP_TAB:
        _render_sp()
    else:
        st.error(
            "Module `sheet_pile_tab.py` not found in scripts/.\n\n"
            "Make sure `geotech-staff-engineer` is installed:\n```\n"
            "pip install geotech-staff-engineer\n```"
        )


# ── TAB 9: SLOPE STABILITY ────────────────────────────────────────────────────
if _page == "Slope Stability":
    if _HAS_SLOPE_TAB:
        _render_slope()
    else:
        st.error(
            "Module `slope_stability_tab.py` not found in scripts/.\n\n"
            "Make sure `geotech-staff-engineer` is installed:\n```\n"
            "pip install geotech-staff-engineer\n```"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB COMPARE — So sánh nhiều phương án
# ══════════════════════════════════════════════════════════════════════════════
if _page == "Compare":
    st.markdown("### Compare Design Variants")

    if not _HAS_VDB:
        st.error("variants_db module not available.")
        st.stop()

    _all_variants = _vdb_list()

    if not _all_variants:
        st.info("No variants saved yet.  \nGo to any tab, run calculations, then use **Save as Variant** in the sidebar.")
        st.stop()

    # ── Bảng tổng hợp ─────────────────────────────────────────────────────────
    _COLS_DISP = {
        "id":           "ID",
        "name":         "Name",
        "created_at":   "Saved",
        "pile_name":    "Pile",
        "pile_length":  "L [m]",
        "fos_bishop":   "FOS Bishop",
        "fos_spencer":  "FOS Spencer",
        "fos_fellenius":"FOS Fell.",
        "fos_mp":       "FOS M-P",
        "q_allow":      "Q_allow [kN]",
        "head_defl_mm": "Defl [mm]",
        "max_moment":   "M_max [kN.m]",
        "description":  "Note",
    }

    _df_all = pd.DataFrame(_all_variants)[list(_COLS_DISP.keys())]
    _df_all = _df_all.rename(columns=_COLS_DISP)

    # Format số
    for _fc in ["FOS Bishop", "FOS Spencer", "FOS Fell.", "FOS M-P"]:
        if _fc in _df_all.columns:
            _df_all[_fc] = _df_all[_fc].apply(
                lambda x: f"{x:.3f}" if pd.notna(x) else "—"
            )
    for _fc in ["Q_allow [kN]", "Defl [mm]", "M_max [kN.m]"]:
        if _fc in _df_all.columns:
            _df_all[_fc] = _df_all[_fc].apply(
                lambda x: f"{x:.1f}" if pd.notna(x) else "—"
            )

    st.dataframe(_df_all, use_container_width=True, hide_index=True)

    st.divider()

    # ── Chọn variants để so sánh biểu đồ ────────────────────────────────────
    _id_options = [f"[{v['id']}] {v['name']}" for v in _all_variants]
    _selected_labels = st.multiselect(
        "Select variants to compare (2+)",
        options=_id_options,
        default=_id_options[:min(4, len(_id_options))],
        key="cmp_sel",
    )

    _selected_ids = [int(s.split("]")[0][1:]) for s in _selected_labels]
    _sel_variants  = [v for v in _all_variants if v["id"] in _selected_ids]

    if len(_sel_variants) >= 2:
        _labels = [f"[{v['id']}] {v['name']}" for v in _sel_variants]

        # ── Bar charts ────────────────────────────────────────────────────────
        _FOS_METHODS = [
            ("fos_bishop",    "Bishop",    1.3,  "#2196F3"),
            ("fos_spencer",   "Spencer",   1.3,  "#9C27B0"),
            ("fos_fellenius", "Fellenius", 1.25, "#FF9800"),
            ("fos_mp",        "M-Price",   1.3,  "#4CAF50"),
        ]

        fig_cmp, axes = plt.subplots(1, 3, figsize=(15, 5), dpi=90)
        fig_cmp.suptitle("Variant Comparison", fontsize=13, fontweight="bold")

        x = np.arange(len(_sel_variants))
        w = 0.18

        # Panel 1 — FOS (4 methods, grouped bars)
        ax0 = axes[0]
        for i, (key, lbl, fos_req, clr) in enumerate(_FOS_METHODS):
            vals = []
            for v in _sel_variants:
                raw = v.get(key)
                vals.append(float(raw) if raw is not None else 0.0)
            bars = ax0.bar(x + i * w, vals, width=w, label=lbl,
                           color=clr, alpha=0.80, edgecolor="white", linewidth=0.5)
            # Mark bars below minimum
            for bar, val, req in zip(bars, vals, [fos_req] * len(vals)):
                if 0 < val < req:
                    bar.set_edgecolor("red")
                    bar.set_linewidth(2)
        ax0.axhline(1.3, color="red", lw=1.2, ls="--", label="FS = 1.3")
        ax0.set_xticks(x + w * 1.5)
        ax0.set_xticklabels([f"[{v['id']}]" for v in _sel_variants], fontsize=8)
        ax0.set_ylabel("FOS")
        ax0.set_title("Slope Stability FOS")
        ax0.legend(fontsize=7, ncol=2)
        ax0.set_ylim(bottom=0)
        ax0.grid(axis="y", alpha=0.3)

        # Panel 2 — Q_allow
        ax1 = axes[1]
        q_vals = [float(v["q_allow"]) if v.get("q_allow") is not None else 0.0
                  for v in _sel_variants]
        _bar_colors = ["#1976D2" if qv > 0 else "#ccc" for qv in q_vals]
        ax1.bar(x, q_vals, color=_bar_colors, alpha=0.85, edgecolor="white")
        ax1.set_xticks(x)
        ax1.set_xticklabels([f"[{v['id']}]" for v in _sel_variants], fontsize=8)
        ax1.set_ylabel("Q_allow [kN]")
        ax1.set_title("Bearing Capacity Q_allow")
        ax1.set_ylim(bottom=0)
        ax1.grid(axis="y", alpha=0.3)
        for xi, qv in zip(x, q_vals):
            if qv > 0:
                ax1.text(xi, qv + max(q_vals) * 0.01, f"{qv:.0f}",
                         ha="center", va="bottom", fontsize=8)

        # Panel 3 — Head deflection + Max moment (twin axis)
        ax2  = axes[2]
        ax2b = ax2.twinx()
        d_vals = [float(v["head_defl_mm"]) if v.get("head_defl_mm") is not None else 0.0
                  for v in _sel_variants]
        m_vals = [float(v["max_moment"]) if v.get("max_moment") is not None else 0.0
                  for v in _sel_variants]
        _wd = 0.35
        ax2.bar(x - _wd / 2, d_vals, width=_wd, color="#E91E63", alpha=0.80,
                label="Defl [mm]", edgecolor="white")
        ax2b.bar(x + _wd / 2, m_vals, width=_wd, color="#FF9800", alpha=0.80,
                 label="M_max [kN.m]", edgecolor="white")
        ax2.set_xticks(x)
        ax2.set_xticklabels([f"[{v['id']}]" for v in _sel_variants], fontsize=8)
        ax2.set_ylabel("Head deflection [mm]", color="#E91E63")
        ax2b.set_ylabel("M_max [kN.m]",        color="#FF9800")
        ax2.set_title("P-y Results")
        ax2.set_ylim(bottom=0)
        ax2b.set_ylim(bottom=0)
        ax2.grid(axis="y", alpha=0.3)
        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2b.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper right")

        # X-axis labels legend
        for _ax in axes:
            _ax.set_xlabel(
                "  ".join([f"[{v['id']}] {v['name'][:18]}" for v in _sel_variants]),
                fontsize=7, color="#555",
            )

        plt.tight_layout()
        st.pyplot(fig_cmp, use_container_width=True)
        plt.close(fig_cmp)

    elif len(_sel_variants) == 1:
        st.info("Select at least 2 variants to compare.")

    st.divider()

    # ── Load / Delete per variant ─────────────────────────────────────────────
    st.markdown("#### Manage Variants")
    for _v in _all_variants:
        _vc1, _vc2, _vc3, _vc4 = st.columns([3, 1, 1, 1])
        _vc1.markdown(
            f"**[{_v['id']}] {_v['name']}**  "
            f"<span style='color:#888;font-size:12px'>{_v['created_at']} | "
            f"{_v['pile_name'] or '—'} L={_v['pile_length'] or '—'} m</span>",
            unsafe_allow_html=True,
        )
        if _v.get("description"):
            _vc1.caption(_v["description"])

        if _vc2.button("Load", key=f"vload_{_v['id']}", use_container_width=True):
            _restored = _vdb_load_inputs(_v["id"])
            if _restored:
                for _rk, _rv in _restored.items():
                    st.session_state[_rk] = _rv
                st.success(f"Loaded variant [{_v['id']}] — switch to Geo Data to review.")
                st.rerun()

        if _vc3.button("Delete", key=f"vdel_{_v['id']}", use_container_width=True):
            st.session_state[f"_vdel_confirm_{_v['id']}"] = True

        if st.session_state.get(f"_vdel_confirm_{_v['id']}"):
            _vc4.warning("Delete?")
            _vd1, _vd2 = st.columns(2)
            if _vd1.button("Yes", key=f"vdel_yes_{_v['id']}", use_container_width=True):
                _vdb_delete(_v["id"])
                st.session_state.pop(f"_vdel_confirm_{_v['id']}", None)
                st.rerun()
            if _vd2.button("No", key=f"vdel_no_{_v['id']}", use_container_width=True):
                st.session_state.pop(f"_vdel_confirm_{_v['id']}", None)
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # BATCH RUN — Quét nhiều tham số
    # ══════════════════════════════════════════════════════════════════════════
    st.divider()
    st.markdown("### Batch Run — Multi-Parameter Sweep")

    if not _HAS_BATCH:
        st.warning("batch_engine.py not available.")
    else:
        with st.expander("How to define values", expanded=False):
            st.markdown("""
| Format | Ví dụ | Kết quả |
|--------|-------|---------|
| Danh sách | `15, 17, 20, 23` | [15, 17, 20, 23] |
| Range start:stop:step | `15:25:2` | [15, 17, 19, 21, 23, 25] |
| Giá trị đơn | `20` | [20] |

**Row index**: đánh số từ 0 (lớp đất đầu tiên = 0).
**Slope Layer Thickness**: nhập chiều dày mới, tự động dịch Bottom Elev + Top Elev lớp tiếp theo.
            """)

        # ── Bảng tham số ──────────────────────────────────────────────────────
        _batch_default = pd.DataFrame({
            "Parameter": [_BATCH_PARAM_NAMES[0], _BATCH_PARAM_NAMES[0]],
            "Row":       [0, 0],
            "Values":    ["", ""],
        })
        if "batch_param_df" not in st.session_state:
            st.session_state["batch_param_df"] = _batch_default.copy()

        st.markdown("#### Parameter Table")
        st.caption("Thêm/xóa hàng tự do. Mỗi hàng = 1 tham số cần quét.")

        _bp_df = st.data_editor(
            st.session_state["batch_param_df"],
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Parameter": st.column_config.SelectboxColumn(
                    "Parameter", options=_BATCH_PARAM_NAMES, required=True,
                ),
                "Row": st.column_config.NumberColumn(
                    "Row index", min_value=0, max_value=20,
                    step=1, default=0,
                    help="0 = lớp đầu tiên. Chỉ dùng cho tham số đất.",
                ),
                "Values": st.column_config.TextColumn(
                    "Values  (VD: 15,17,20  hoặc  15:25:2)",
                    width="large",
                ),
            },
            key="batch_param_editor",
        )
        st.session_state["batch_param_df"] = _bp_df

        # ── Cấu hình run ──────────────────────────────────────────────────────
        _bc1, _bc2, _bc3 = st.columns(3)
        _batch_mode = _bc1.radio(
            "Combination mode",
            ["Grid (all combos)", "Sequential (same index)"],
            key="batch_mode",
            help="Grid: N₁×N₂×...×Nₙ runs. Sequential: zip theo chỉ số.",
        )
        _batch_calcs = _bc2.multiselect(
            "Calculations",
            ["Bearing Capacity", "Slope Stability"],
            default=["Bearing Capacity", "Slope Stability"],
            key="batch_calcs",
        )
        _batch_prefix = _bc3.text_input(
            "Variant name prefix",
            value="Batch", key="batch_prefix",
            help="Tên phương án = prefix + [param=val, ...]",
        )

        # ── Xem trước số lượt chạy ────────────────────────────────────────────
        _valid_rows = _bp_df.dropna(subset=["Parameter", "Values"])
        _valid_rows = _valid_rows[_valid_rows["Values"].str.strip() != ""]
        _run_counts = []
        _parse_errors = []
        for _, _pr in _valid_rows.iterrows():
            try:
                _vals = _batch_parse(str(_pr["Values"]))
                _run_counts.append(len(_vals))
            except Exception as _pe:
                _parse_errors.append(f"Row '{_pr['Parameter']}': {_pe}")
                _run_counts.append(0)

        if _parse_errors:
            for _pe in _parse_errors:
                st.error(_pe)

        if _run_counts:
            import math as _math
            if "Grid" in _batch_mode:
                _total_runs = _math.prod(_run_counts) if _run_counts else 0
                st.info(f"Grid: {' × '.join(str(n) for n in _run_counts)} = **{_total_runs} runs**")
            else:
                _total_runs = max(_run_counts) if _run_counts else 0
                st.info(f"Sequential: **{_total_runs} runs** (zip, shorter lists use last value)")

        # ── Run button ────────────────────────────────────────────────────────
        if st.button("Run Batch", type="primary", key="btn_batch_run",
                     disabled=not bool(_valid_rows.shape[0] and not _parse_errors)):

            # Lấy base session values
            _base_scalars: dict = {}
            for _k in _PROJ_SCALAR_KEYS:
                _v = st.session_state.get(_k)
                if _v is not None:
                    _base_scalars[_k] = _v.item() if hasattr(_v, "item") else _v

            _DF_KEYS_BATCH = ["bc_soil_df", "front_sand_df", "front_clay_df",
                              "back_layers_df", "slope_soil_df"]
            _base_dfs: dict = {
                _k: st.session_state.get(_k, pd.DataFrame()).copy()
                for _k in _DF_KEYS_BATCH
            }

            # Parse all param rows
            _param_specs = []
            for _, _pr in _valid_rows.iterrows():
                _param_specs.append({
                    "param_name": str(_pr["Parameter"]),
                    "row_idx":    int(_pr["Row"]) if pd.notna(_pr["Row"]) else 0,
                    "values":     _batch_parse(str(_pr["Values"])),
                })

            # Tạo combinations
            import itertools as _itertools
            if "Grid" in _batch_mode:
                _combos = list(_itertools.product(*[p["values"] for p in _param_specs]))
            else:
                # zip_longest với last value padding
                _lists = [p["values"] for p in _param_specs]
                _max_len = max(len(l) for l in _lists)
                _padded = [l + [l[-1]] * (_max_len - len(l)) for l in _lists]
                _combos = list(zip(*_padded))

            _total = len(_combos)
            _prog  = st.progress(0, text=f"0 / {_total} runs...")
            _batch_results = []

            for _ci, _combo in enumerate(_combos):
                # Tạo override list cho combo này
                _overrides = [
                    {"param_name": _param_specs[_pi]["param_name"],
                     "row_idx":    _param_specs[_pi]["row_idx"],
                     "value":      _combo[_pi]}
                    for _pi in range(len(_param_specs))
                ]

                # Tên phương án
                _short = ", ".join(
                    f"{_ov['param_name'].split('[')[0].strip()[:12]}={_ov['value']:.2g}"
                    for _ov in _overrides
                )
                _v_name = f"{_batch_prefix.strip()} [{_short}]"[:80]

                # Áp dụng overrides
                _sc, _dfs = _batch_override(_base_scalars, _base_dfs, _overrides)

                _run_res: dict = {}

                # ── Bearing Capacity ──────────────────────────────────────────
                if "Bearing Capacity" in _batch_calcs:
                    try:
                        _pile_name = _sc.get("sel_pile", "SW-840")
                        _pile_info = next(
                            (p for p in SW_CATALOG if p["name"] == _pile_name), None
                        )
                        if _pile_info:
                            _pw_m  = _pile_info["H"] / 1000.0
                            _Atd   = _pile_info.get("Atd", _pw_m**2 * 10000)
                            _tip_c = (_Atd / 10000) / (_pw_m**2)
                        else:
                            _pw_m  = float(_sc.get("bc_pile_len", 0.84))
                            _tip_c = 1.0
                        _bc_df  = _dfs.get("bc_soil_df", pd.DataFrame())
                        _wl     = float(_sc.get("water_level", -1.0))
                        _te     = float(_sc.get("top_elev", 2.7))
                        _gwt_d  = max(0.0, _te - _wl)
                        _bc_res = _batch_run_bc(
                            pile_width_m=_pw_m,
                            pile_length_m=float(_sc.get("L_m", 20.0)),
                            gwt_depth_from_top=_gwt_d,
                            soil_df=_bc_df,
                            tip_correction=_tip_c,
                            fos=float(_sc.get("bc_fos", 3.0)),
                        )
                        _run_res["bc"] = _bc_res
                    except Exception as _e_bc:
                        _run_res["bc"] = {"error": str(_e_bc)}

                # ── Slope Stability ───────────────────────────────────────────
                if "Slope Stability" in _batch_calcs:
                    try:
                        _sl_df = _dfs.get("slope_soil_df",
                                          st.session_state.get("slope_soil_df", pd.DataFrame()))
                        _sl_res = _batch_run_slope(
                            top_elev=float(_sc.get("top_elev", 2.7)),
                            soil_level_front=float(_sc.get("soil_level_front", 0.0)),
                            soil_level_back=float(_sc.get("soil_level_back", 0.0)),
                            pile_length=float(_sc.get("L_m", 20.0)),
                            slope_ratio=float(_sc.get("fill_slope_hv", 2.0)),
                            slope_soil_df=_sl_df,
                            xc_min=float(st.session_state.get("sl_xmin", -12.0)),
                            xc_max=float(st.session_state.get("sl_xmax",  10.0)),
                            yc_min=float(st.session_state.get("sl_ymin",   5.0)),
                            yc_max=float(st.session_state.get("sl_ymax",  25.0)),
                            nx=int(st.session_state.get("sl_nx", 6)),
                            ny=int(st.session_state.get("sl_ny", 6)),
                            n_slices=int(st.session_state.get("sl_nslices", 30)),
                        )
                        _run_res["slope"] = _sl_res
                    except Exception as _e_sl:
                        _run_res["slope"] = {"error": str(_e_sl)}

                # ── Lưu variant ───────────────────────────────────────��───────
                _v_results: dict = {}
                _bc_entry = _run_res.get("bc", {})
                _sl_entry = _run_res.get("slope", {})

                # Ghi vào _v_results theo format variants_db.save_variant cần
                if _bc_entry and "error" not in _bc_entry:
                    _auto = _bc_entry.get("auto", {})
                    if "Q_allow" in _auto:
                        _v_results["bc_all_methods"] = {
                            m: {"Q_allow": _bc_entry[m].get("Q_allow")}
                            for m in ("auto", "nordlund", "tomlinson", "beta")
                            if m in _bc_entry and "error" not in _bc_entry[m]
                        }
                if _sl_entry and "error" not in _sl_entry:
                    _v_results["sl_results_all"] = {
                        m: {"critical": type("_R", (), {
                            "FOS": _sl_entry[m]["FOS"],
                            "xc":  _sl_entry[m]["xc"],
                            "yc":  _sl_entry[m]["yc"],
                        })()}
                        for m in ("bishop","fellenius","spencer","morgenstern_price")
                        if m in _sl_entry and "FOS" in _sl_entry[m]
                    }

                _saved_id = _vdb_save(
                    name=_v_name,
                    description=", ".join(
                        f"{_ov['param_name']}={_ov['value']:.4g}" for _ov in _overrides
                    ),
                    inputs=_sc,
                    results=_v_results,
                )

                # Lưu summary cho bảng preview
                _summary = {"ID": _saved_id, "Name": _v_name}
                if _bc_entry and "best_Q_allow" in _bc_entry:
                    _summary["Q_allow [kN]"] = _bc_entry.get("best_Q_allow")
                if _sl_entry and "min_FOS" in _sl_entry:
                    _summary["min FOS"] = _sl_entry.get("min_FOS")
                _batch_results.append(_summary)

                _prog.progress(
                    int((_ci + 1) / _total * 100),
                    text=f"{_ci+1} / {_total}  —  {_v_name[:50]}",
                )

            _prog.progress(100, text=f"Done — {_total} variants saved.")
            st.session_state["batch_last_results"] = _batch_results
            st.rerun()

        # ── Preview kết quả batch vừa chạy ───────────────────────────────────
        if st.session_state.get("batch_last_results"):
            st.markdown("#### Last Batch Results")
            _br_df = pd.DataFrame(st.session_state["batch_last_results"])
            st.dataframe(_br_df, use_container_width=True, hide_index=True)
            if st.button("Clear preview", key="btn_clear_batch_preview"):
                st.session_state.pop("batch_last_results", None)
                st.rerun()
