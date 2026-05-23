#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline_ke_sw.py — Pipeline tu dong khong can click chuot.

Chay 4 buoc lien tiep:
  1. Doc du lieu tuong chua tu TTHC.sqlite (ke_sw_nt_detail + ke_sw_nt2_layers)
  2. FEM2D Frame solver (FrameBuilder → solve → luu TTHC.sqlite)
  3. On dinh tong the Bishop (sw_global_stability.check_all — thuan Python)
  4. PLAXIS 2D Remote Scripting (auto-connect neu server dang chay)

Lenh chay:
  python scripts/pipeline_ke_sw.py --bh KE-HK10
  python scripts/pipeline_ke_sw.py --all
  python scripts/pipeline_ke_sw.py --bh KE-HK10 --fc 70 --skip-plaxis
  python scripts/pipeline_ke_sw.py --bh KE-HK10 --plaxis-host localhost --plaxis-port 10000
"""
from __future__ import annotations

import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(_sys.stderr, "reconfigure"):
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import json
import math
import socket
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# --- path setup -----------------------------------------------------------
_SCRIPTS = Path(__file__).resolve().parent
_ROOT    = _SCRIPTS.parent
_DB      = _ROOT / "data" / "TTHC.sqlite"
_CATALOG = _ROOT / "data" / "sw_pile_catalog.json"
sys.path.insert(0, str(_SCRIPTS))

_PLAXIS_EXE    = Path(r"C:\Program Files\Seequent\PLAXIS 2D 2024\Plaxis2DXInput.exe")
_GEOSTUDIO_EXE = Path(r"C:\Program Files\Seequent\GeoStudio 2025.1\Bin\GeoStudio.exe")

# ==========================================================================
# Data loading
# ==========================================================================

@dataclass
class WallDesign:
    bh_name:     str
    pile_type:   str
    Z_m:         float          # cao do co ho khoan
    fill_m:      float          # dat dap phia Front
    L_design_m:  float          # chieu dai co thiet ke
    EA_kN:        float
    EI_kNm2:      float
    Mcr_kNm:      float
    pile_width_m: float = 0.996
    layers:       list = field(default_factory=list)

    @property
    def top_y(self):
        return round(self.Z_m + self.fill_m, 3)

    @property
    def bot_y(self):
        return round(self.top_y - self.L_design_m, 3)


def _load_catalog() -> dict:
    if not _CATALOG.exists():
        return {}
    with open(_CATALOG, encoding="utf-8") as f:
        raw = json.load(f)
    return {p["name"]: p for p in raw.get("piles", [])}


def _kh_vesic(su_kPa: float, B_m: float, EI_kNm2: float) -> float:
    """Vesic (1961): kh = 0.65/B × (Es·B⁴/EI)^(1/12) × Es/(1−ν²).

    Es = 500·su (modulus khong thoat nuoc),  ν=0.5 → 1−ν²=0.75.
    Dung cho co nen dat set mem-deo (pile tren nen Winkler).
    """
    Es = 500.0 * max(float(su_kPa), 1.0)
    ratio = Es * (B_m ** 4) / EI_kNm2
    kh = (0.65 / B_m) * (ratio ** (1.0 / 12.0)) * Es / 0.75
    return max(round(kh, 0), 50.0)


def _compute_ea_ei(pile: dict, fc_MPa: float):
    Ec_kNm2 = 4700.0 * math.sqrt(fc_MPa) * 1000.0
    EA  = round(Ec_kNm2 * pile["Atd_cm2"] * 1e-4, 0)
    EI  = round(Ec_kNm2 * pile["Itd_cm4"] * 1e-8, 0)
    Mcr = round(pile.get("Mcr_Tm", 0.0) * 9.81, 1)  # T.m → kN.m
    return EA, EI, Mcr


def load_wall_design(bh_name: str, db_path: Path, fc_MPa: float = 70.0) -> WallDesign:
    catalog = _load_catalog()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    cur = conn.cursor()
    cur.execute(
        "SELECT bh_name, pile_type, L_design_m, Z_m, fill_m "
        "FROM ke_sw_nt_detail WHERE bh_name=? LIMIT 1",
        (bh_name,)
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"Khong tim thay {bh_name} trong ke_sw_nt_detail")

    pile_name = row["pile_type"]
    pile_cat  = catalog.get(pile_name, {})
    EA, EI, Mcr = _compute_ea_ei(pile_cat, fc_MPa) if pile_cat else (13_609_696.0, 930_822.0, 757.0)

    # Load layers (ke_sw_nt2_layers, join qua id)
    cur.execute(
        "SELECT kn.layer_order, kn.symbol, kn.L_m, kn.su_kPa, kn.gamma_kNm3 "
        "FROM ke_sw_nt2_layers kn "
        "JOIN ke_sw_nt_detail kd ON kn.sw_design_id = kd.id "
        "WHERE kd.bh_name=? ORDER BY kn.layer_order",
        (bh_name,)
    )
    layers_raw = [dict(r) for r in cur.fetchall()]
    conn.close()

    B_m = float(pile_cat.get("width_mm", 996)) / 1000.0 if pile_cat else 0.996
    wd = WallDesign(
        bh_name      = bh_name,
        pile_type    = pile_name,
        Z_m          = float(row["Z_m"]),
        fill_m       = float(row["fill_m"]),
        L_design_m   = float(row["L_design_m"]),
        EA_kN        = EA,
        EI_kNm2      = EI,
        Mcr_kNm      = Mcr,
        pile_width_m = B_m,
        layers       = layers_raw,
    )
    return wd


# ==========================================================================
# Step 2: FEM2D
# ==========================================================================

_SAND_SYMS = {"F", "2a", "2b", "2c", "4", "5a", "6", "7"}


def _build_earth_pressure_profile(
    wd: WallDesign,
    surcharge_kPa: float = 10.0,
    water_elev_front: float = -0.5,
    water_elev_back:  float = -0.5,
    back_excavation_m: float = 1.0,
    N: int = 300,
) -> tuple:
    """Ap luc ngang tong hop theo quy tac port 8503 (build_lateral_load).

    Su dung Rankine voi phi=0/c=su cho set, phi>0/c=0 cho cat.
    p_net = sigma_h_active + p_w_front - p_w_back  (mode='winkler').
    Ap dung tu top_y xuong bot_y (toan bo chieu dai coc).

    Returns (elevs_np, p_net_np) — numpy arrays giam dan theo cao do.
    """
    import numpy as np
    from wall_internal_force import WallGeometry, EarthLayer, build_lateral_load

    # Build EarthLayer tu layers data
    front_layers: list[EarthLayer] = []
    back_layers:  list[EarthLayer] = []
    elev = wd.Z_m
    for lay in wd.layers:
        L     = max(lay.get("L_m", 1.0) or 1.0, 0.01)
        sym   = str(lay.get("symbol", "1")).strip()
        su    = max(lay.get("su_kPa", 10.0) or 10.0, 1.0)
        gamma = lay.get("gamma_kNm3", 15.0) or 15.0
        g_sub = max(gamma - 9.81, 3.0)
        is_sand = sym in _SAND_SYMS
        phi = 30.0 if is_sand else 0.0
        c   = 0.0  if is_sand else su
        tip = round(elev - L, 3)
        front_layers.append(EarthLayer(tip_elev=tip, gamma=gamma, gamma_sub=g_sub, phi=phi, c=c))
        back_layers.append( EarthLayer(tip_elev=tip, gamma=gamma, gamma_sub=g_sub, phi=phi, c=c))
        elev = tip

    # Fill phia Front (dat dap bên trên Z_m)
    fill = EarthLayer(tip_elev=wd.Z_m, gamma=18.0, gamma_sub=8.0, phi=28.0, c=0.0)

    geom = WallGeometry(
        top_elev         = wd.top_y,
        pile_length      = wd.L_design_m,
        soil_level_front = wd.Z_m,
        soil_level_back  = wd.Z_m - back_excavation_m,
        water_elev_front = water_elev_front,
        water_elev_back  = water_elev_back,
        surcharge_front  = surcharge_kPa,
    )
    res = build_lateral_load(geom, front_layers, back_layers, fill=fill, N=N, mode="winkler")
    return res["elevs"], res["p_net"]


def _kh_matlock_per_layer(wd: WallDesign, eps50: float = 0.02, k_sand: float = 10_000.0) -> list:
    """Matlock (1970) kh cho tung lop dat (mid-depth), theo quy tac port 8503.

    D_m = 0.5 * pile_width  (CLAUDE.md: 0.5 chu vi cu, huong ve Back).
    Set: kh = Np*Su*D / (2.5*eps50*D) = Np*Su / (2.5*eps50).
    Cat: kh = k_sand * z.

    Returns list kh_kNm3 cho moi lop trong wd.layers.
    """
    from wall_internal_force import kh_clay_matlock, kh_sand_api

    D_m  = wd.pile_width_m * 0.5   # effective diameter phia Back
    elev = wd.Z_m
    kh_list = []
    for lay in wd.layers:
        L     = max(lay.get("L_m", 1.0) or 1.0, 0.01)
        su    = max(lay.get("su_kPa", 10.0) or 10.0, 1.0)
        gamma = lay.get("gamma_kNm3", 15.0) or 15.0
        sym   = str(lay.get("symbol", "1")).strip()
        mid_elev = elev - L / 2.0
        z_depth  = wd.top_y - mid_elev   # depth from pile top
        if sym in _SAND_SYMS:
            kh = kh_sand_api(z_depth, k_sand)
        else:
            kh = kh_clay_matlock(z_depth, D_m, su, gamma, eps50)
        kh_list.append(max(round(kh, 0), 50.0))
        elev = round(elev - L, 3)
    return kh_list


def run_fem2d_step(wd: WallDesign, db_path: Path,
                   n_seg: int = 30, inc_pdelta: bool = False,
                   n_anchors: int = 0, anchor_head_y: float = 1.5,
                   anchor_end_x: float = -10.0, anchor_end_y: float = -3.0,
                   anchor_EA: float = 200_000.0, anchor_pre: float = 300.0) -> dict:
    from fem2d.frame2d import (
        FrameBuilder, solve, create_tables, save_model, save_result
    )

    import numpy as np

    # Ap luc ngang theo quy tac port 8503: Rankine phi=0/c=su + nuoc + surcharge
    elevs_p, p_net = _build_earth_pressure_profile(wd)
    print(f"  Earth pressure (Rankine + nuoc): p_net_top={float(p_net[0]):.1f} kN/m², p_net_bot={float(p_net[-1]):.1f} kN/m²")

    # kh: Matlock (1970) cho set, API cho cat — D_m = 0.5 * pile_width
    kh_list = _kh_matlock_per_layer(wd)
    kh_avg = (
        sum(kh_list[i] * (wd.layers[i].get("L_m", 1) or 1) for i in range(len(kh_list)))
        / max(sum(lay.get("L_m", 1) or 1 for lay in wd.layers), 1.0)
    )

    fb = FrameBuilder(
        name     = f"{wd.bh_name.replace('-','_').lower()}_pipeline",
        bh_name  = wd.bh_name,
        pile_name= wd.pile_type,
    )
    fb.add_vertical_pile(
        top_y      = wd.top_y,
        bot_y      = wd.bot_y,
        n_segments = n_seg,
        EA         = wd.EA_kN,
        EI         = wd.EI_kNm2,
        fix_bot    = False,  # Winkler springs tu giu, khong can ngam day
        free_top   = True,
    )
    if n_anchors > 0:
        fb.add_ground_anchor(
            head_y       = anchor_head_y,
            anchor_end_x = anchor_end_x,
            anchor_end_y = anchor_end_y,
            EA           = anchor_EA,
            prestress_kN = anchor_pre,
        )

    # Winkler springs: Matlock (1970) per layer — D_m = 0.5 * pile_width
    print(f"  Matlock kh per layer (D_m={wd.pile_width_m*0.5:.3f} m):")
    n_w = 0
    elev = wd.Z_m
    for i, lay in enumerate(wd.layers):
        su    = lay.get("su_kPa", 10.0) or 10.0
        L     = max(lay.get("L_m", 1.0) or 1.0, 0.01)
        sym   = lay.get("symbol", "?")
        kh_l  = kh_list[i]
        top_l = elev
        bot_l = round(elev - L, 3)
        n = fb.add_winkler_layers(top_y=top_l, bot_y=bot_l, kh_kNm3=kh_l)
        n_w += n
        print(f"    [{sym}] su={su:.1f} kPa → kh={kh_l:.0f} kN/m³  ({top_l:.2f}→{bot_l:.2f} m, {n} nodes)")
        elev = bot_l

    # Tai phan bo: apply per-beam bang noi suy p_net tai dung vi tri node
    # Tranh bug add_distributed_load_segment bo qua beams bat nhanh key_elev boundary
    elevs_asc = elevs_p[::-1]   # tang dan (bot → top) cho np.interp
    pnet_asc  = p_net[::-1]
    n_l_total = 0
    for bid in fb._pile_beam_ids:
        beam = fb._beams[bid]
        ni   = fb._nodes[beam.node_i]
        nj   = fb._nodes[beam.node_j]
        y_top = max(ni.y, nj.y)
        y_bot = min(ni.y, nj.y)
        w_t = float(np.interp(y_top, elevs_asc, pnet_asc))
        w_b = float(np.interp(y_bot, elevs_asc, pnet_asc))
        n_l_total += fb.add_distributed_load_segment(
            top_y=y_top, bot_y=y_bot, w_top=w_t, w_bot=w_b, direction="global_x",
        )
    print(f"  Load per beam: {len(fb._pile_beam_ids)} beams, {n_l_total} beams co tai")
    model = fb.build()

    warnings = model.validate()
    for w in warnings:
        print(f"  [WARN] {w}")

    log: list[str] = []
    result = solve(model, include_P_delta=inc_pdelta, log=log)

    pr = result.last_phase
    u_top_mm = pr.node_disp[0][0] * 1000.0 if pr.node_disp else 0.0
    M_max = 0.0
    if pr.elem_forces_beam:
        M_max = max(
            abs(f["M_i"]) for f in pr.elem_forces_beam.values()
        )
        M_max = max(M_max, max(abs(f["M_j"]) for f in pr.elem_forces_beam.values()))

    N_anchor = 0.0
    if pr.elem_forces_truss:
        N_anchor = list(pr.elem_forces_truss.values())[0] if pr.elem_forces_truss else 0.0

    # Luu DB
    create_tables(str(db_path))
    model_id = save_model(model, str(db_path), overwrite=True)
    run_id   = save_result(model_id, result, str(db_path))

    print(f"  kh_avg     = {kh_avg:.0f} kN/m³ (Matlock, weighted by layer L)")
    return {
        "u_top_mm":      round(u_top_mm, 2),
        "M_max_kNm":     round(M_max, 2),
        "N_anchor_kN":   round(N_anchor, 2),
        "mcr_ratio":     round(M_max / wd.Mcr_kNm, 3) if wd.Mcr_kNm else None,
        "kh_avg_kNm3":   round(kh_avg, 0),
        "model_id":      model_id,
        "run_id":        run_id,
        "p_net_top":     round(float(p_net[0]), 1),
        "p_net_bot":     round(float(p_net[-1]), 1),
    }


# ==========================================================================
# Step 3: Bishop stability (sw_global_stability.py)
# ==========================================================================

def run_stability_step(wd: WallDesign,
                       excavation_depth: float = 1.0,
                       water_front: float = -0.5,
                       water_back:  float = -0.5,
                       surcharge:   float = 10.0) -> dict:
    from sw_global_stability import (
        WallGeometry, EarthLayer, PileProps, check_all,
    )

    geom = WallGeometry(
        top_elev         = wd.top_y,
        pile_length      = wd.L_design_m,
        soil_level_front = wd.Z_m,
        soil_level_back  = wd.Z_m - excavation_depth,
        water_elev_front = water_front,
        water_elev_back  = water_back,
        surcharge_front  = surcharge,
    )
    fill = EarthLayer(
        tip_elev  = wd.Z_m,
        gamma     = 18.0,
        gamma_sub = 8.0,
        phi       = 28.0,
        c         = 0.0,
    )

    # Build front + back layers tu ke_sw_nt2_layers
    elev = wd.Z_m
    front_layers: list = []
    back_layers: list  = []
    for lay in wd.layers:
        su    = lay.get("su_kPa", 10.0) or 10.0
        g     = lay.get("gamma_kNm3", 15.0) or 15.0
        L     = lay.get("L_m", 1.0) or 1.0
        g_sub = max(g - 9.81, 3.0)
        tip   = round(elev - L, 3)
        # Undrained: phi=0, c=su
        el = EarthLayer(tip_elev=tip, gamma=g, gamma_sub=g_sub, phi=0.0, c=su)
        front_layers.append(el)
        back_layers.append(el)
        elev = tip

    pile_props = PileProps(
        name     = wd.pile_type,
        D_m      = 0.996,       # width_mm = 996 mm
        EI_kNm2  = wd.EI_kNm2,
        Mcr_kNm  = wd.Mcr_kNm,
    )

    res = check_all(
        geom         = geom,
        front_layers = front_layers,
        back_layers  = back_layers,
        fill         = fill,
        pile         = pile_props,
        method       = "bishop",
    )
    def _r(v):
        return round(float(v), 3) if v is not None else None

    return {
        "global_slip_FoS": _r(res.Fs_global_slip),
        "overturning_FoS": _r(res.Fs_overturning),
        "toe_kickout_FoS": _r(res.Fs_toe_kickout),
        "all_pass":        res.all_pass,
        "summary":         res.summary(),
    }


# ==========================================================================
# Step 4: PLAXIS 2D Remote Scripting
# ==========================================================================

def _plaxis_server_alive(host: str = "localhost", port: int = 10000) -> bool:
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


def _try_launch_plaxis(wait_sec: int = 20) -> bool:
    if not _PLAXIS_EXE.exists():
        return False
    print(f"  Launching PLAXIS 2D: {_PLAXIS_EXE}")
    subprocess.Popen([str(_PLAXIS_EXE)])
    for i in range(wait_sec):
        time.sleep(1)
        if _plaxis_server_alive():
            print(f"  PLAXIS server ready after {i+1}s")
            return True
        if (i + 1) % 5 == 0:
            print(f"  Waiting for PLAXIS... ({i+1}/{wait_sec}s)")
    return False


def run_plaxis_step(wd: WallDesign,
                    host: str = "localhost", port_i: int = 10000,
                    auto_launch: bool = True) -> dict:
    import os
    try:
        from plxscripting.easy import new_server
    except ImportError:
        return {"status": "skip", "reason": "plxscripting not installed"}

    alive = _plaxis_server_alive(host, port_i)
    if not alive:
        if auto_launch:
            print("  PLAXIS server not running — attempting launch...")
            alive = _try_launch_plaxis()
        if not alive:
            return {
                "status": "skip",
                "reason": (
                    "PLAXIS Remote Scripting server not running. "
                    "Mo PLAXIS 2D → Expert → Remote Scripting → Start Server"
                ),
            }

    PASSWORD = os.environ.get("PLAXIS_PASSWORD", "")
    try:
        s_i, g_i = new_server(host, port_i, password=PASSWORD)
        s_o, g_o = new_server(host, port_i + 1, password=PASSWORD)
    except Exception as e:
        return {"status": "error", "reason": str(e)}

    try:
        g_i.new()

        # Vat lieu coc (Plate)
        mat = g_i.platemat()
        g_i.setproperties(
            mat,
            "MaterialName", f"SW_{wd.pile_type}_{wd.bh_name}",
            "EA1",          wd.EA_kN,
            "EI",           wd.EI_kNm2,
            "d",            0.0,
            "w",            0.0,
        )

        # Hinh hoc tuong cuu
        wall_line = g_i.line(
            (wd.top_y, 0.0),
            (wd.bot_y, 0.0),
        )
        plate = g_i.plate(wall_line[-1])
        g_i.setmaterial(plate[-1], mat)

        # Phase 0: Initial
        phase0 = g_i.InitialPhase
        phase0.Name.set("Phase_0_Initial")

        # Phase 1: Kich hoat coc
        phase1 = g_i.phase(phase0)
        phase1.Name.set("Phase_1_Wall")
        g_i.activate(plate, phase1)

        # Phase Safety: tinh FoS
        phase_sf = g_i.phase(phase1)
        phase_sf.Name.set("Phase_Safety")
        phase_sf.DeformCalcType.set("Phi/c reduction")

        g_i.calculate()

        # Lay ket qua Safety
        FoS = None
        try:
            FoS = round(float(g_o.phase(phase_sf.Name.value).Reached.SumMsf.value), 3)
        except Exception:
            pass

        return {
            "status":  "ok",
            "FoS_SRF": FoS,
            "phases":  ["Phase_0_Initial", "Phase_1_Wall", "Phase_Safety"],
        }

    except Exception as e:
        return {"status": "error", "reason": str(e)}


# ==========================================================================
# Main pipeline
# ==========================================================================

def run_pipeline(
    bh_name:     str,
    db_path:     Path  = _DB,
    fc_MPa:      float = 70.0,
    skip_plaxis: bool  = False,
    plaxis_host: str   = "localhost",
    plaxis_port: int   = 10000,
    auto_launch_plaxis: bool = True,
) -> dict:
    results = {"bh_name": bh_name, "fc_MPa": fc_MPa}
    sep = "─" * 60

    print(f"\n{sep}")
    print(f"PIPELINE: {bh_name}  (fc={fc_MPa} MPa)")
    print(sep)

    # Step 1: Load data
    print("\n[1/4] Doc du lieu tuong chua...")
    wd = load_wall_design(bh_name, db_path, fc_MPa)
    print(f"  Pile: {wd.pile_type}  L={wd.L_design_m} m")
    print(f"  top_y={wd.top_y:.2f} m  bot_y={wd.bot_y:.2f} m")
    print(f"  EA={wd.EA_kN:.0f} kN  EI={wd.EI_kNm2:.0f} kN.m2  Mcr={wd.Mcr_kNm:.1f} kN.m")
    print(f"  Layers: {len(wd.layers)} lop")
    results["wall_design"] = {
        "pile_type": wd.pile_type, "L_m": wd.L_design_m,
        "top_y": wd.top_y, "bot_y": wd.bot_y,
    }

    # Step 2: FEM2D
    print("\n[2/4] FEM2D Frame solver...")
    try:
        fem = run_fem2d_step(wd, db_path)
        print(f"  u_top      = {fem['u_top_mm']:.2f} mm")
        print(f"  M_max      = {fem['M_max_kNm']:.1f} kN.m  (Mcr={wd.Mcr_kNm:.1f})")
        if fem["mcr_ratio"] is not None:
            status = "Dat" if fem["mcr_ratio"] <= 1.0 else "KHONG DAT"
            print(f"  M/Mcr      = {fem['mcr_ratio']:.3f}  → {status}")
        print(f"  N_anchor   = {fem['N_anchor_kN']:.1f} kN")
        print(f"  kh_avg     = {fem['kh_avg_kNm3']:.0f} kN/m³ (Vesic)")
        print(f"  Saved → model_id={fem['model_id']}, run_id={fem['run_id']}")
        results["fem2d"] = fem
    except Exception as e:
        print(f"  LOI FEM2D: {e}")
        results["fem2d"] = {"error": str(e)}

    # Step 3: Bishop stability
    print("\n[3/4] On dinh tong the (Bishop)...")
    try:
        stab = run_stability_step(wd)
        print(f"  Global slip FoS  = {stab['global_slip_FoS']}")
        print(f"  Overturning  FoS = {stab['overturning_FoS']}")
        print(f"  Toe kickout  FoS = {stab['toe_kickout_FoS']}")
        verdict = "Dat" if stab["all_pass"] else "KHONG DAT"
        print(f"  Ket luan: {verdict}")
        results["stability"] = stab
    except Exception as e:
        print(f"  LOI Bishop: {e}")
        results["stability"] = {"error": str(e)}

    # Step 4: PLAXIS
    if skip_plaxis:
        print("\n[4/4] PLAXIS: bo qua (--skip-plaxis)")
        results["plaxis"] = {"status": "skipped"}
    else:
        print("\n[4/4] PLAXIS 2D Remote Scripting...")
        plax = run_plaxis_step(
            wd,
            host=plaxis_host, port_i=plaxis_port,
            auto_launch=auto_launch_plaxis,
        )
        if plax["status"] == "ok":
            print(f"  FoS (SRF) = {plax.get('FoS_SRF')}")
        elif plax["status"] == "skip":
            print(f"  Bo qua: {plax['reason']}")
        else:
            print(f"  Loi: {plax.get('reason')}")
        results["plaxis"] = plax

    # Summary
    print(f"\n{sep}")
    print(f"TOM TAT: {bh_name}")
    fem2d_r  = results.get("fem2d", {})
    stab_r   = results.get("stability", {})
    plax_r   = results.get("plaxis", {})
    print(f"  FEM2D  u_top={fem2d_r.get('u_top_mm','?')} mm  "
          f"M_max={fem2d_r.get('M_max_kNm','?')} kN.m")
    print(f"  Bishop FoS_slip={stab_r.get('global_slip_FoS','?')}  "
          f"FoS_OT={stab_r.get('overturning_FoS','?')}")
    if plax_r.get("status") == "ok":
        print(f"  PLAXIS FoS_SRF={plax_r.get('FoS_SRF','?')}")
    print(sep)

    return results


# ==========================================================================
# CLI entry point
# ==========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline tu dong: TTHC.sqlite → FEM2D → Bishop → PLAXIS 2D"
    )
    parser.add_argument("--bh",            default="KE-HK10",
                        help="Ten ho khoan, vd KE-HK10")
    parser.add_argument("--all",           action="store_true",
                        help="Chay tat ca HK tren tuyen ke (7 HK)")
    parser.add_argument("--fc",            type=float, default=70.0,
                        help="Cuong do be tong coc (MPa), mac dinh 70")
    parser.add_argument("--skip-plaxis",   action="store_true",
                        help="Bo qua buoc PLAXIS")
    parser.add_argument("--plaxis-host",   default="localhost")
    parser.add_argument("--plaxis-port",   type=int, default=10000)
    parser.add_argument("--no-auto-launch",action="store_true",
                        help="Khong tu dong mo PLAXIS neu chua chay")
    parser.add_argument("--db",            default=str(_DB),
                        help="Duong dan TTHC.sqlite")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"LOI: Khong tim thay DB: {db_path}")
        sys.exit(1)

    if args.all:
        # Load danh sach tu DB
        conn = sqlite3.connect(str(db_path))
        cur  = conn.cursor()
        cur.execute("SELECT DISTINCT bh_name FROM ke_sw_nt_detail ORDER BY bh_name")
        bh_list = [r[0] for r in cur.fetchall()]
        conn.close()
        print(f"Chay pipeline cho {len(bh_list)} HK: {bh_list}")
    else:
        bh_list = [args.bh]

    all_results = {}
    for bh in bh_list:
        try:
            r = run_pipeline(
                bh_name            = bh,
                db_path            = db_path,
                fc_MPa             = args.fc,
                skip_plaxis        = args.skip_plaxis,
                plaxis_host        = args.plaxis_host,
                plaxis_port        = args.plaxis_port,
                auto_launch_plaxis = not args.no_auto_launch,
            )
            all_results[bh] = r
        except Exception as e:
            print(f"\nLOI pipeline {bh}: {e}")
            import traceback; traceback.print_exc()
            all_results[bh] = {"error": str(e)}

    if len(bh_list) > 1:
        print("\n" + "=" * 60)
        print("TONG HOP TAT CA HK")
        print("=" * 60)
        for bh, r in all_results.items():
            fem  = r.get("fem2d", {})
            stab = r.get("stability", {})
            print(
                f"{bh:12s}  M={fem.get('M_max_kNm','?'):>7} kN.m  "
                f"FoS={stab.get('global_slip_FoS','?')}"
            )


if __name__ == "__main__":
    main()
