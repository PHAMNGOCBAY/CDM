"""Kiem toan coc CDM THAT (Ec=40000kPa, khong phai Ecmd=Es gia dinh) tai 5 muc
chuyen vi dinh coc muc tieu: 40/50/60/70/80cm — dung lai quan he tuyen tinh
P-Ux da xac lap (Ux_cm = 0,01333.P_kPa + 1,042, R2=1.000, hang coc x=0) de tinh
P vua can thiet, giai lai DONG BO voi Mohr-Coulomb (Su=5000kPa, khong bind) cho
nhat quan phuong phap voi kiem toan M/Q/N truoc do."""
import sys
import time
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
import pyvista as pv

from cdm3d import ccx_input, params_io, run_ccx, postprocess
from cdm3d.ccx_input import _read_mesh
from cdm3d.geometry import column_centers

pv.OFF_SCREEN = True
ZONE = "KE"
OUT = ROOT / "scratch"
MSH = OUT / "grout_row.msh"
SU_MC_KPA = 5000.0
D_m = 0.8
A_col = np.pi * (D_m / 2) ** 2
I_col = np.pi * (D_m / 2) ** 4 / 4

TARGETS_CM = {40: 2922.58, 50: 3672.77, 60: 4422.96, 70: 5173.14, 80: 5923.33}


def build_params():
    params = params_io.build_default_params(ZONE)  # Ec=40000 THAT, khong doi
    gd5 = next(s for s in params.stages if s.name.startswith("GD5"))
    params.stages = [gd5]
    return params


def row_nodes_x0(params):
    points, elements, elsets, nsets = _read_mesh(MSH, 1)
    col_node_idx = np.unique(elements[elsets["CDM_COLUMN"]].ravel())
    pts_col = points[col_node_idx]
    centers = np.array(column_centers(params))
    d2 = ((pts_col[:, None, 0] - centers[None, :, 0]) ** 2
          + (pts_col[:, None, 1] - centers[None, :, 1]) ** 2)
    nearest = d2.argmin(axis=1)
    node_row_x = centers[nearest, 0]
    mask = np.abs(node_row_x - 0.0) < 1e-3
    return col_node_idx[mask], points


def center_col_nodes(params):
    points, elements, elsets, nsets = _read_mesh(MSH, 1)
    col_node_idx = np.unique(elements[elsets["CDM_COLUMN"]].ravel())
    pts_col = points[col_node_idx]
    r = np.sqrt(pts_col[:, 0] ** 2 + pts_col[:, 1] ** 2)
    return col_node_idx[r <= (D_m / 2) * 1.08], points


def solve_one(Ux_target, P_kPa, params, row_nodes, cnodes, points):
    inp_path = OUT / f"kt_ux{Ux_target}.inp"
    ccx_input.write_ccx_inp(
        MSH, inp_path, params, use_model_change=False,
        mohr_coulomb={"SOIL_dat_yeu": {"c_kPa": SU_MC_KPA, "phi_deg": 0.0, "psi_deg": 0.0}},
    )
    H_col = params.column.z_top - params.column.z_bot
    force_kN_total = P_kPa * D_m * H_col * 3
    force_per_node = force_kN_total / len(row_nodes)

    text = inp_path.read_text(encoding="ascii", errors="replace")
    lines = text.splitlines()
    idx_nf = next(i for i, l in enumerate(lines) if l.strip() == "*NODE FILE")
    cload_lines = ["*CLOAD"] + [f"{int(n) + 1}, 1, {force_per_node:.6f}" for n in row_nodes]
    new_lines = lines[:idx_nf] + cload_lines + lines[idx_nf:]
    inp_final = OUT / f"kt_ux{Ux_target}_load.inp"
    inp_final.write_text("\n".join(new_lines) + "\n", encoding="ascii", errors="replace")

    t0 = time.time()
    frd = run_ccx.solve(inp_final, timeout_s=1200)
    dt = time.time() - t0
    vtu = postprocess.convert_frd_to_vtu(frd)
    m = pv.read(vtu)
    ux_head = float(m["U"][row_nodes[np.argmin(np.abs(points[row_nodes, 2] - 0.8))], 0])
    print(f"[Ux_target={Ux_target}cm] P={P_kPa:.1f}kPa SOLVED {dt:.2f}s  Ux_dinh_that={ux_head*100:.2f}cm")

    S = m["S"]
    sigma_zz = S[:, 2]
    z_all = points[cnodes, 2]
    z_bins = np.linspace(z_all.min(), z_all.max(), 60)
    z_mid = 0.5 * (z_bins[:-1] + z_bins[1:])
    binidx = np.digitize(z_all, z_bins) - 1
    N_arr = np.full(len(z_mid), np.nan)
    M_arr = np.full(len(z_mid), np.nan)
    for i in range(len(z_mid)):
        sel = cnodes[binidx == i]
        if len(sel) < 6:
            continue
        x_s, y_s, sz = points[sel, 0], points[sel, 1], sigma_zz[sel]
        Amat = np.column_stack([np.ones_like(x_s), x_s, y_s])
        coef, *_ = np.linalg.lstsq(Amat, sz, rcond=None)
        a, b, c = coef
        N_arr[i] = a * A_col
        M_arr[i] = b * I_col
    return dict(z=z_mid, N=N_arr, M=M_arr, ux_head_cm=ux_head * 100, vtu=str(vtu))


if __name__ == "__main__":
    params = build_params()
    row_nodes, points = row_nodes_x0(params)
    cnodes, _ = center_col_nodes(params)

    results = {}
    for ux_t, P in TARGETS_CM.items():
        results[ux_t] = solve_one(ux_t, P, params, row_nodes, cnodes, points)

    import json
    np.savez(OUT / "kiemtoan_50_80.npz",
              **{f"z{k}": v["z"] for k, v in results.items()},
              **{f"N{k}": v["N"] for k, v in results.items()},
              **{f"M{k}": v["M"] for k, v in results.items()})
    summary = {k: {"P_kPa": TARGETS_CM[k], "ux_head_cm": v["ux_head_cm"]} for k, v in results.items()}
    (OUT / "kiemtoan_50_80_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Da luu scratch/kiemtoan_50_80.npz + summary.json")
