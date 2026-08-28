"""Ap luc vua CO DINH P=2000 kPa (hang coc x=0, suot chieu dai) + tai GD5 that.
Tim Es (mo dun dan hoi lop dat yeu) de Ux tai dinh hang coc = 40cm — giam do
cung dat (chu KHONG doi tai) de kiem tra co che thu 2: dat yeu hon so voi gia
thiet co the lam tang chuyen vi ngang. Dung lai luoi da co (grout_row.msh) —
hinh hoc khong doi khi chi doi E.

Lop dat yeu dung *MOHR COULOMB (c_kPa=Su=5000, phi=psi=0 -> Tresca, theo yeu
cau nguoi dung) thay vi *ELASTIC thuan — Su=5000kPa RAT CAO (khong bind, thuan
tuy de dam bao dung dinh dang vat lieu MC nhat quan voi cac phan tich khac
trong du an) nen ket qua VAN xap xi dan hoi tuyen tinh (da kiem chung truoc
day o Su=500kPa: khong bind -> khop dan hoi gan nhu tuyet doi)."""
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
P_GROUT_KPA = 2000.0
SU_MC_KPA = 5000.0  # cohesion Mohr-Coulomb cho lop dat yeu (phi=psi=0, Tresca)
FIXED_NODE_Z = 0.8  # dinh coc, hang x=0 (idx=14 da xac dinh truoc, kiem tra lai bang toa do)


def build_params(Es_kPa):
    params = params_io.build_default_params(ZONE)
    gd5 = next(s for s in params.stages if s.name.startswith("GD5"))
    params.stages = [gd5]
    for layer in params.soil_layers:
        if layer.name == "dat_yeu":
            layer.E_kPa = Es_kPa
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


def solve_for_Es(Es_kPa, tag):
    params = build_params(Es_kPa)
    row_nodes, points = row_nodes_x0(params)
    fixed_node = row_nodes[np.argmin(np.abs(points[row_nodes, 2] - FIXED_NODE_Z))]

    inp_path = OUT / f"grout2mpa_Es{Es_kPa:.0f}.inp"
    ccx_input.write_ccx_inp(
        MSH, inp_path, params, use_model_change=False,
        mohr_coulomb={"SOIL_dat_yeu": {"c_kPa": SU_MC_KPA, "phi_deg": 0.0, "psi_deg": 0.0}},
    )

    D_m = params.column.D_m
    H_col = params.column.z_top - params.column.z_bot
    force_kN_total = P_GROUT_KPA * D_m * H_col * 3  # 3 tru/hang, dau +X (giong truoc)
    force_per_node = force_kN_total / len(row_nodes)

    text = inp_path.read_text(encoding="ascii", errors="replace")
    lines = text.splitlines()
    idx_nf = next(i for i, l in enumerate(lines) if l.strip() == "*NODE FILE")
    cload_lines = ["*CLOAD"] + [f"{int(n) + 1}, 1, {force_per_node:.6f}" for n in row_nodes]
    new_lines = lines[:idx_nf] + cload_lines + lines[idx_nf:]
    inp_final = OUT / f"grout2mpa_Es{Es_kPa:.0f}_load.inp"
    inp_final.write_text("\n".join(new_lines) + "\n", encoding="ascii", errors="replace")

    t0 = time.time()
    frd = run_ccx.solve(inp_final, timeout_s=1200)
    dt = time.time() - t0
    vtu = postprocess.convert_frd_to_vtu(frd)
    mesh = pv.read(vtu)
    Ux = float(mesh["U"][fixed_node, 0])
    print(f"[{tag}] Es={Es_kPa:.0f}kPa  SOLVED {dt:.2f}s  Ux(dinh hang x=0)={Ux*100:.3f} cm")
    return Ux, vtu


if __name__ == "__main__":
    results = {}
    for Es in (3450.0, 1200.0):
        ux, vtu = solve_for_Es(Es, f"Es={Es:.0f}")
        results[Es] = (ux, vtu)

    Es_a, Es_b = 3450.0, 1200.0
    ux_a, _ = results[Es_a]
    ux_b, _ = results[Es_b]
    # noi suy tuyen tinh theo 1/Es (gan dung tot cho he thong dan hoi 1 vat lieu doi)
    inv_a, inv_b = 1.0 / Es_a, 1.0 / Es_b
    slope = (ux_b - ux_a) / (inv_b - inv_a)
    target = 0.40
    inv_target = inv_a + (target - ux_a) / slope
    Es_target = 1.0 / inv_target
    print(f"\nNoi suy theo 1/Es: Es_target = {Es_target:.1f} kPa -> du kien Ux=40cm")

    ux_t, vtu_t = solve_for_Es(Es_target, "Es_target (kiem chung)")
    err_pct = (ux_t - target) / target * 100
    print(f"Kiem chung: Ux={ux_t*100:.3f} cm (muc tieu 40.0cm, sai lech {err_pct:+.2f}%)")

    import json
    out = {
        "P_grout_kPa": P_GROUT_KPA,
        "Es_real_kPa": Es_a, "Ux_at_Es_real_cm": ux_a * 100,
        "Es_probe_kPa": Es_b, "Ux_at_Es_probe_cm": ux_b * 100,
        "Es_target_kPa": Es_target, "Ux_target_cm": target * 100,
        "Ux_validated_cm": ux_t * 100, "error_pct": err_pct,
        "vtu_validated": str(results.get(Es_target, (None, vtu_t))[1] if Es_target in results else vtu_t),
    }
    (OUT / "grout2mpa_Es_sweep_result.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Da luu: {OUT / 'grout2mpa_Es_sweep_result.json'}")
