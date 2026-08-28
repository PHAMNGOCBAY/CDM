"""Phuong an moi: Ecmd (mo dun coc CDM) = Es (mo dun dat yeu) — LOAI BO hieu
ung "coc cung ganh tai" da gay "tran" bao hoa ~37,3cm o phuong an truoc (coc
giu co dinh Ec=40000kPa trong khi dat mem dan). O day, MOI diem trong sweep,
Ec coc VA Es dat yeu CUNG BANG 1 gia tri (tuong duong coc mat do cung, "mem
hoa dong thoi" voi dat xung quanh — kich ban gioi han de kiem tra co phai
chinh su "cung tuong doi" cua coc la nguyen nhan gay tran).

Ap luc vua CO DINH P=1500 kPa (hang coc x=0, suot chieu dai coc) + tai GD5
that. Lop dat yeu dung *MOHR COULOMB (c_kPa=Su=5000, phi=psi=0 -> Tresca,
khong bind — giu format nhat quan voi cac phan tich truoc).

3 diem khao sat (hang coc x=0): dinh coc (z=+0.8m), cach dinh 5m (z=-4.2m),
cach dinh 10m (z=-9.2m)."""
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
MSH = OUT / "grout_row.msh"  # luoi da co tu phuong an truoc — hinh hoc khong doi
P_GROUT_KPA = 1500.0
SU_MC_KPA = 5000.0
Z_TOP = 0.8
DEPTHS_M = (0.0, 5.0, 10.0)  # cach dinh coc


def build_params(Es_kPa):
    params = params_io.build_default_params(ZONE)
    gd5 = next(s for s in params.stages if s.name.startswith("GD5"))
    params.stages = [gd5]
    for layer in params.soil_layers:
        if layer.name == "dat_yeu":
            layer.E_kPa = Es_kPa
    params.column.Ec_kPa = Es_kPa  # Ecmd = Es
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


def fixed_nodes_for_depths(row_nodes, points):
    out = {}
    for d in DEPTHS_M:
        z_target = Z_TOP - d
        i = row_nodes[np.argmin(np.abs(points[row_nodes, 2] - z_target))]
        out[d] = i
    return out


def solve_for_Es(Es_kPa, tag):
    params = build_params(Es_kPa)
    row_nodes, points = row_nodes_x0(params)
    fnodes = fixed_nodes_for_depths(row_nodes, points)

    inp_path = OUT / f"ecmd_Es{Es_kPa:.0f}.inp"
    ccx_input.write_ccx_inp(
        MSH, inp_path, params, use_model_change=False,
        mohr_coulomb={"SOIL_dat_yeu": {"c_kPa": SU_MC_KPA, "phi_deg": 0.0, "psi_deg": 0.0}},
    )

    D_m = params.column.D_m
    H_col = params.column.z_top - params.column.z_bot
    force_kN_total = P_GROUT_KPA * D_m * H_col * 3
    force_per_node = force_kN_total / len(row_nodes)

    text = inp_path.read_text(encoding="ascii", errors="replace")
    lines = text.splitlines()
    idx_nf = next(i for i, l in enumerate(lines) if l.strip() == "*NODE FILE")
    cload_lines = ["*CLOAD"] + [f"{int(n) + 1}, 1, {force_per_node:.6f}" for n in row_nodes]
    new_lines = lines[:idx_nf] + cload_lines + lines[idx_nf:]
    inp_final = OUT / f"ecmd_Es{Es_kPa:.0f}_load.inp"
    inp_final.write_text("\n".join(new_lines) + "\n", encoding="ascii", errors="replace")

    t0 = time.time()
    frd = run_ccx.solve(inp_final, timeout_s=1200)
    dt = time.time() - t0
    vtu = postprocess.convert_frd_to_vtu(frd)
    mesh = pv.read(vtu)
    U = mesh["U"]
    ux_by_depth = {d: float(U[n, 0]) for d, n in fnodes.items()}
    txt = "  ".join(f"z-{d:.0f}m: Ux={ux_by_depth[d]*100:.3f}cm" for d in DEPTHS_M)
    print(f"[{tag}] Es=Ecmd={Es_kPa:.0f}kPa  SOLVED {dt:.2f}s  {txt}")
    return ux_by_depth, vtu, fnodes


if __name__ == "__main__":
    ES_LIST = [3450.0, 1500.0, 800.0, 400.0, 200.0, 100.0]
    results = {}
    for Es in ES_LIST:
        try:
            ux_by_depth, vtu, fnodes = solve_for_Es(Es, f"Es={Es:.0f}")
            results[Es] = {"ux_by_depth": ux_by_depth, "vtu": str(vtu)}
        except Exception as e:
            print(f"[Es={Es:.0f}] KHONG HOI TU: {e}")
            results[Es] = {"error": str(e)}

    import json
    (OUT / "ecmd_eq_es_sweep_result.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDa luu: {OUT / 'ecmd_eq_es_sweep_result.json'}")
