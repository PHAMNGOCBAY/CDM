"""Gia thuyet co che vat ly moi: ap luc vua (grout pressure) tac dung len 1
HANG COC (3 tru cung x, khac y) tren SUOT CHIEU DAI coc, cong don voi tai GD5
that (nua mien +X). Muc tieu: tim P (kPa) de Ux dat 80cm — bai toan NGUOC
(back-calculate do lon tai), KHONG phai ep tham so dat phi vat ly.

Vat lieu: DAN HOI THUAN (khong Mohr-Coulomb) — de tan dung tinh TUYEN TINH
(da xac nhan truoc do: nhan doi tai -> chuyen vi nhan dung 2 lan) -> chi can
2 diem (P=0 va P=P1) la du xac dinh duong thang, giai nguoc P_target, roi
GIAI LAI de kiem chung (khong ngoai suy mu quang).

Quy uoc luc tuong duong: 1 "hang coc" = 3 tru cung toa do x (khac y). Ap luc
vua P (kPa) tac dung len dien tich hinh chieu D x H_coc moi tru (bien don
gian pho bien khi quy tai ngang phan bo -> luc duong, giong cach quy doi da
dung cho suc khang ma sat than coc trong CLAUDE.md muc 11). Luc tong quy deu
cho tung nut coc trong hang (BAT BUOC ghi ro gia dinh nay khi bao cao)."""
import sys
import time
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

import gmsh
import numpy as np
import pyvista as pv

from cdm3d import ccx_input, geometry, mesh_gmsh, params_io, run_ccx, postprocess
from cdm3d.ccx_input import _read_mesh
from cdm3d.geometry import column_centers

pv.OFF_SCREEN = True
ZONE = "KE"
OUT = ROOT / "scratch"
OUT.mkdir(exist_ok=True)


def build_params():
    params = params_io.build_default_params(ZONE)
    gd5 = next(s for s in params.stages if s.name.startswith("GD5"))
    params.stages = [gd5]
    return params


def build_mesh(params, tag):
    msh_path = OUT / f"grout_{tag}.msh"
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        geometry.build_geometry(params)
        mesh_gmsh.generate_mesh(params, element_order=1)
        stats = mesh_gmsh.mesh_stats()
        print(f"[{tag}] mesh: {stats}")
        mesh_gmsh.export_mesh(msh_path)
    finally:
        gmsh.finalize()
    return msh_path


def row_node_groups(msh_path, params):
    """Tra ve dict {x_row: np.array(node_idx 0-indexed)} — nut CHI thuoc
    CDM_COLUMN, gom theo tam tru GAN NHAT (3 tru/hang, cung x)."""
    points, elements, elsets, nsets = _read_mesh(msh_path, 1)
    col_node_idx = np.unique(elements[elsets["CDM_COLUMN"]].ravel())
    pts_col = points[col_node_idx]
    centers = np.array(column_centers(params))  # (9,2)
    d2 = ((pts_col[:, None, 0] - centers[None, :, 0]) ** 2
          + (pts_col[:, None, 1] - centers[None, :, 1]) ** 2)
    nearest = d2.argmin(axis=1)
    node_row_x = centers[nearest, 0]
    rows_x = sorted(set(round(float(cx), 3) for cx, cy in centers.tolist()))
    return {rx: col_node_idx[np.abs(node_row_x - rx) < 1e-3] for rx in rows_x}, points


def write_inp(msh_path, params, tag, mohr_coulomb=None):
    inp_path = OUT / f"grout_{tag}.inp"
    ccx_input.write_ccx_inp(
        msh_path, inp_path, params, use_model_change=False, mohr_coulomb=mohr_coulomb,
    )
    return inp_path


def inject_cload(inp_path, node_ids_0idx, force_kN_total, dof, out_tag):
    """Them *CLOAD (luc nut) cho 1 hang coc vao DUY NHAT *STEP hien co (GD5-only,
    use_model_change=False -> chi 1 khoi *STEP...*END STEP). Chen truoc dong
    '*NODE FILE' dau tien."""
    text = inp_path.read_text(encoding="ascii", errors="replace")
    lines = text.splitlines()
    idx_nf = next(i for i, l in enumerate(lines) if l.strip() == "*NODE FILE")
    force_per_node = force_kN_total / len(node_ids_0idx)
    cload_lines = ["*CLOAD"] + [f"{int(n) + 1}, {dof}, {force_per_node:.6f}" for n in node_ids_0idx]
    new_lines = lines[:idx_nf] + cload_lines + lines[idx_nf:]
    out_path = inp_path.parent / f"{inp_path.stem}_{out_tag}.inp"
    out_path.write_text("\n".join(new_lines) + "\n", encoding="ascii", errors="replace")
    return out_path


def solve_and_get_row_ux(inp_path, row_nodes_by_x, tag):
    t0 = time.time()
    frd_path = run_ccx.solve(inp_path, timeout_s=1200)
    dt = time.time() - t0
    print(f"[{tag}] SOLVED {dt:.2f}s -> {frd_path}")
    vtu_path = postprocess.convert_frd_to_vtu(frd_path)
    mesh = pv.read(vtu_path)
    U = mesh["U"]
    result = {}
    for rx, nodes in row_nodes_by_x.items():
        ux_row = U[nodes, 0]
        i_env = np.argmax(np.abs(ux_row))
        result[rx] = float(ux_row[i_env])
    return result, vtu_path


# ============================================================
# BUOC 1 — Mesh dung 1 lan (dung lai cho ca 3 lan giai — hinh hoc/luoi khong
# doi khi chi doi luc, tranh sinh luoi lai 3 lan ton thoi gian).
# ============================================================
params = build_params()
params_io.print_warnings(params)
msh_path = build_mesh(params, "row")
row_nodes_by_x, points = row_node_groups(msh_path, params)
for rx, nodes in row_nodes_by_x.items():
    print(f"hang x={rx:+.2f}m: {len(nodes)} nut coc")

D_m = params.column.D_m
H_col = params.column.z_top - params.column.z_bot
n_col_per_row = 3

# ============================================================
# BUOC 2 — Baseline (P=0, chi tai GD5 that) — dung lam diem (0, Ux0)
# ============================================================
inp_base = write_inp(msh_path, params, "base")
ux_base_by_row, vtu_base = solve_and_get_row_ux(inp_base, row_nodes_by_x, "P=0")
for rx, ux in ux_base_by_row.items():
    print(f"  baseline x={rx:+.2f}m: Ux_envelope = {ux*1000:.3f} mm")

x_target = max(ux_base_by_row, key=lambda k: abs(ux_base_by_row[k]))
sign = 1.0 if ux_base_by_row[x_target] >= 0 else -1.0
Ux0_m = ux_base_by_row[x_target]
huong_txt = "+X" if sign > 0 else "-X"
print(f"\n--> Hang muc tieu: x={x_target:+.2f}m (Ux0={Ux0_m*1000:.3f} mm, huong {huong_txt})")

row_nodes = row_nodes_by_x[x_target]

# ============================================================
# BUOC 3 — Diem thu 2: P1 = 300 kPa vua tren hang muc tieu, CUNG HUONG Ux0
# ============================================================
P1_kPa = 300.0
force1_kN = sign * P1_kPa * D_m * H_col * n_col_per_row
inp_p1 = inject_cload(inp_base, row_nodes, force1_kN, dof=1, out_tag="P1")
ux_p1_by_row, vtu_p1 = solve_and_get_row_ux(inp_p1, row_nodes_by_x, f"P={P1_kPa:.0f}kPa")
Ux1_m = ux_p1_by_row[x_target]
print(f"  P1={P1_kPa:.0f}kPa: Ux(hang muc tieu) = {Ux1_m*1000:.3f} mm")

# ============================================================
# BUOC 4 — Noi suy tuyen tinh (dan hoi) -> P_target cho |Ux|=0.80 m
# ============================================================
slope = (Ux1_m - Ux0_m) / P1_kPa  # m / kPa
Ux_target_m = sign * 0.80
P_target_kPa = (Ux_target_m - Ux0_m) / slope
print(f"\nSlope = {slope*1000:.5f} mm/kPa")
print(f"P_target (noi suy) = {P_target_kPa:.2f} kPa -> du kien Ux = {Ux_target_m*100:.1f} cm")

# ============================================================
# BUOC 5 — Giai kiem chung tai P_target
# ============================================================
force_t_kN = sign * P_target_kPa * D_m * H_col * n_col_per_row
inp_pt = inject_cload(inp_base, row_nodes, force_t_kN, dof=1, out_tag="Ptarget")
ux_pt_by_row, vtu_pt = solve_and_get_row_ux(inp_pt, row_nodes_by_x, f"P={P_target_kPa:.0f}kPa (kiem chung)")
Ux_pt_m = ux_pt_by_row[x_target]
err_pct = (Ux_pt_m - Ux_target_m) / Ux_target_m * 100
print(f"  Kiem chung: Ux = {Ux_pt_m*100:.2f} cm (muc tieu 80.0 cm, sai lech {err_pct:+.2f}%)")

import json
result_summary = {
    "x_target_row_m": x_target,
    "Ux0_mm_at_P0": Ux0_m * 1000,
    "P1_kPa": P1_kPa,
    "Ux1_mm": Ux1_m * 1000,
    "slope_mm_per_kPa": slope * 1000,
    "P_target_kPa": P_target_kPa,
    "Ux_target_cm": Ux_target_m * 100,
    "Ux_validated_cm": Ux_pt_m * 100,
    "error_pct": err_pct,
    "vtu_validated": str(vtu_pt),
    "D_m": D_m, "H_col_m": H_col, "n_col_per_row": n_col_per_row,
}
(OUT / "grout_pressure_result.json").write_text(json.dumps(result_summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nDa luu: {OUT / 'grout_pressure_result.json'}")
