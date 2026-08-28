"""So sanh CONG BANG toc do giai: CUNG 1 luoi that KE (1 cot, 3 lop that), CUNG
vat lieu DAN HOI TUYEN TINH (khong deo — de khong lam sai lech do CalculiX
trong du an nay CHUA tung chay mo hinh deo, chi OpenSeesPy moi co), CUNG tai
ngang diem 50kN tai TOP_COLUMN, CUNG dieu kien bien.

Do THOI GIAN GIAI THUC SU (khong tinh thoi gian dung luoi/ghi file — chi tinh
tu luc goi solver den luc co ket qua) cho ca 2:
  - CalculiX: thoi gian subprocess run_ccx.solve()
  - OpenSeesPy: thoi gian ops.analyze() (dung SuperLU, dung theo quy tac du an)
"""
import sys
import time
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

import gmsh
import numpy as np
import openseespy.opensees as ops

from cdm3d import geometry, mesh_gmsh, params_io, run_ccx
from cdm3d.ccx_input import _read_mesh

params = params_io.build_default_params("KE")
params.column.n_x = 1
params.column.n_y = 1
soil_layers = params.soil_layers
column = params.column

msh_path = ROOT / "scratch" / "test_fair_bench.msh"
gmsh.initialize()
gmsh.option.setNumber("General.Terminal", 0)
try:
    geometry.build_geometry(params)
    mesh_gmsh.generate_mesh(params, element_order=1)
    stats = mesh_gmsh.mesh_stats()
    print("mesh:", stats)
    mesh_gmsh.export_mesh(msh_path)
finally:
    gmsh.finalize()

points, elements, elsets, nsets = _read_mesh(msh_path, 1)
n_elem_total = sum(len(v) for v in elsets.values())
print(f"Tong so phan tu: {n_elem_total}, so nut: {len(points)}")

top_col_nodes = sorted(int(n) + 1 for n in nsets.get("TOP_COLUMN", []))
F_total = 50.0
F_per_node = F_total / len(top_col_nodes)

# ============ 1. CALCULIX ============
lines = ["** fair benchmark CalculiX", "*NODE, NSET=NALL"]
for i, (x, y, z) in enumerate(points, start=1):
    lines.append(f"{i}, {x:.6f}, {y:.6f}, {z:.6f}")
for name, idx in elsets.items():
    lines.append(f"*ELEMENT, TYPE=C3D4, ELSET={name}")
    for k in idx:
        nodes = elements[k] + 1
        lines.append(f"{k + 1}, " + ", ".join(str(n) for n in nodes))
for name in elsets:
    if name == "CDM_COLUMN":
        E, nu, gamma = column.Ec_kPa, column.nu_c, column.gamma_kNm3
    else:
        layer = next(l for l in soil_layers if l.name == name.removeprefix("SOIL_"))
        E, nu, gamma = layer.E_kPa, layer.nu, layer.gamma_kNm3
    mat = f"MAT_{name}"
    lines += [f"*MATERIAL, NAME={mat}", "*ELASTIC", f"{E:.3f}, {nu:.3f}",
              "*DENSITY", f"{gamma/9.81:.6f}", f"*SOLID SECTION, ELSET={name}, MATERIAL={mat}"]
def _write_nset(lines_, name, node_ids_0idx):
    lines_.append(f"*NSET, NSET={name}")
    ids = sorted(int(n) + 1 for n in node_ids_0idx)
    for cs in range(0, len(ids), 10):
        lines_.append(", ".join(str(n) for n in ids[cs:cs + 10]))

_write_nset(lines, "BASE", nsets["BASE"])
for s in ("SIDE_XMIN", "SIDE_XMAX", "SIDE_YMIN", "SIDE_YMAX"):
    if s in nsets:
        _write_nset(lines, s, nsets[s])

perm_bc = ["*BOUNDARY", "BASE, 1, 3"]
for s in ("SIDE_XMIN", "SIDE_XMAX"):
    if s in nsets:
        perm_bc.append(f"{s}, 1, 1")
for s in ("SIDE_YMIN", "SIDE_YMAX"):
    if s in nsets:
        perm_bc.append(f"{s}, 2, 2")
lines += perm_bc
lines += ["*STEP", "*STATIC", "*CLOAD"]
for n in top_col_nodes:
    lines.append(f"{n}, 1, {F_per_node:.6f}")
lines += ["*NODE FILE", "U", "*END STEP"]
inp_path = ROOT / "scratch" / "test_fair_bench.inp"
inp_path.write_text("\n".join(lines) + "\n", encoding="ascii", errors="replace")

t0 = time.time()
frd = run_ccx.solve(inp_path, timeout_s=600)
t_ccx = time.time() - t0
print(f"\n[CalculiX] thoi gian giai = {t_ccx:.3f} s")

from cdm3d.postprocess import convert_frd_to_vtu
import pyvista as pv
vtu = convert_frd_to_vtu(frd)
mesh = pv.read(vtu)
U = mesh["U"]
top_xyz = points[top_col_nodes[0] - 1]
d = np.linalg.norm(mesh.points - top_xyz, axis=1)
i_top = int(np.argmin(d))
assert d[i_top] < 1e-6
ux_ccx = U[i_top, 0] * 1000.0
print(f"[CalculiX] Ux dinh cot = {ux_ccx:.4f} mm")

# ============ 2. OPENSEESPY ============
ops.wipe()
ops.model('basic', '-ndm', 3, '-ndf', 3)
for i, (x, y, z) in enumerate(points, start=1):
    ops.node(i, float(x), float(y), float(z))
mat_tag_by_name = {}
for tag_i, name in enumerate(elsets, start=1):
    if name == "CDM_COLUMN":
        E, nu, gamma = column.Ec_kPa, column.nu_c, column.gamma_kNm3
    else:
        layer = next(l for l in soil_layers if l.name == name.removeprefix("SOIL_"))
        E, nu, gamma = layer.E_kPa, layer.nu, layer.gamma_kNm3
    ops.nDMaterial('ElasticIsotropic', tag_i, E, nu, gamma / 9.81)
    mat_tag_by_name[name] = tag_i
elem_id = 1
for name, idx in elsets.items():
    matTag = mat_tag_by_name[name]
    for k in idx:
        nodes = [int(n) + 1 for n in elements[k]]
        ops.element('FourNodeTetrahedron', elem_id, *nodes, matTag)
        elem_id += 1
fix_map: dict[int, list[int]] = {}
def _accumulate(node_ids, dofs):
    for n in node_ids:
        tag = int(n) + 1
        cur = fix_map.setdefault(tag, [0, 0, 0])
        for i, d_ in enumerate(dofs):
            if d_:
                cur[i] = 1
_accumulate(nsets["BASE"], (1, 1, 1))
_accumulate(nsets.get("SIDE_XMIN", []), (1, 0, 0))
_accumulate(nsets.get("SIDE_XMAX", []), (1, 0, 0))
_accumulate(nsets.get("SIDE_YMIN", []), (0, 1, 0))
_accumulate(nsets.get("SIDE_YMAX", []), (0, 1, 0))
for tag, dofs in fix_map.items():
    ops.fix(tag, *dofs)
ops.timeSeries('Linear', 1)
ops.pattern('Plain', 1, 1)
for n0 in top_col_nodes:
    ops.load(n0, F_per_node, 0.0, 0.0)
ops.system('SuperLU')
ops.numberer('RCM')
ops.constraints('Plain')
ops.integrator('LoadControl', 1.0)
ops.algorithm('Linear')
ops.analysis('Static')

t0 = time.time()
ok = ops.analyze(1)
t_ops = time.time() - t0
print(f"\n[OpenSeesPy] thoi gian giai = {t_ops:.3f} s  (return={ok})")
ux_ops = ops.nodeDisp(top_col_nodes[0], 1) * 1000.0
print(f"[OpenSeesPy] Ux dinh cot = {ux_ops:.4f} mm")

print(f"\n=== KET LUAN ===")
print(f"So phan tu: {n_elem_total}")
print(f"CalculiX:   {t_ccx:.3f} s   Ux={ux_ccx:.4f} mm")
print(f"OpenSeesPy: {t_ops:.3f} s   Ux={ux_ops:.4f} mm")
print(f"Sai lech Ux: {abs(ux_ccx-ux_ops):.6f} mm ({abs(ux_ccx-ux_ops)/ux_ccx*100:.4f}%)")
ratio = t_ccx / t_ops if t_ops > 0 else float('inf')
faster = "OpenSeesPy" if t_ops < t_ccx else "CalculiX"
print(f"{faster} nhanh hon {max(ratio, 1/ratio):.2f} lan")
