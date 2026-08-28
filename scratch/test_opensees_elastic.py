"""Test: mo hinh 1 COT nhung DU 3 LOP DAT THAT KE (khong con so lieu toy/gia
lap) bang OpenSeesPy, VAT LIEU DAN HOI (ElasticIsotropic) truoc — de kiem chung
luoi/BC/tai dung TRUOC KHI bat PressureIndependMultiYield. Tai ngang don gian
tai dinh cot, so sanh dinh tinh voi CalculiX bonded.

QUY TAC BAT BUOC (rut ra 2026-08-27, xem skill /cdm3d-opensees): MOI test
OpenSeesPy PHAI lay thong so dat/coc qua params_io.build_default_params(zone)
(chi override n_x/n_y de thu nho quy mo neu can) — KHONG duoc hardcode
SoilLayer/ColumnGroup rieng, vi lam vay de lan lon so lieu that (Es) voi so
lieu bia (H lop, gamma, Su) trong CUNG 1 test, gay nham lan va ton cong chay
lai. Xem 76-cdm3d-fem-gmsh-calculix.md muc 9 lich su phat hien.
"""
import sys
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

import gmsh
import numpy as np
import openseespy.opensees as ops

from cdm3d import geometry, mesh_gmsh, params_io
from cdm3d.ccx_input import _read_mesh

params = params_io.build_default_params("KE")
params.column.n_x = 1
params.column.n_y = 1
soil_layers = params.soil_layers
column = params.column
print("Thong so dat that KE (dat_yeu):", next(l for l in soil_layers if l.name == "dat_yeu"))

msh_path = ROOT / "scratch" / "test_ops.msh"
gmsh.initialize()
gmsh.option.setNumber("General.Terminal", 0)
try:
    geometry.build_geometry(params)
    mesh_gmsh.generate_mesh(params, element_order=1)
    print("mesh:", mesh_gmsh.mesh_stats())
    mesh_gmsh.export_mesh(msh_path)
finally:
    gmsh.finalize()

points, elements, elsets, nsets = _read_mesh(msh_path, 1)
print("elsets:", {k: len(v) for k, v in elsets.items()})
print("nsets:", {k: len(v) for k, v in nsets.items()})

# --- OpenSeesPy model ---
ops.wipe()
ops.model('basic', '-ndm', 3, '-ndf', 3)

for i, (x, y, z) in enumerate(points, start=1):
    ops.node(i, float(x), float(y), float(z))

# vat lieu dan hoi cho tung elset
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

# Boundary: gop dieu kien tren MOI nut truoc khi goi ops.fix() (nut o canh/goc co
# the thuoc 2 mat bien cung luc -> KHONG duoc goi ops.fix() 2 lan cho cung 1 nut)
fix_map: dict[int, list[int]] = {}
def _accumulate(node_ids, dofs):
    for n in node_ids:
        tag = int(n) + 1
        cur = fix_map.setdefault(tag, [0, 0, 0])
        for i, d in enumerate(dofs):
            if d:
                cur[i] = 1

_accumulate(nsets["BASE"], (1, 1, 1))
_accumulate(nsets.get("SIDE_XMIN", []), (1, 0, 0))
_accumulate(nsets.get("SIDE_XMAX", []), (1, 0, 0))
_accumulate(nsets.get("SIDE_YMIN", []), (0, 1, 0))
_accumulate(nsets.get("SIDE_YMAX", []), (0, 1, 0))
for tag, dofs in fix_map.items():
    ops.fix(tag, *dofs)

# Tai ngang thu nghiem tai COL TOP (TOP_COLUMN) - 50 kN tong, chia deu, phuong X
top_col_nodes = np.unique(nsets.get("TOP_COLUMN", np.array([])))
F_total = 50.0
F_per_node = F_total / max(len(top_col_nodes), 1)
ops.timeSeries('Linear', 1)
ops.pattern('Plain', 1, 1)
for n in top_col_nodes:
    ops.load(int(n) + 1, F_per_node, 0.0, 0.0)

ops.system('SuperLU')  # sparse solver thuc su — nhanh hon BandSPD/BandGeneral cho luoi
                        # tu dien 3D khong cau truc (bang thong sau RCM van con lon)
ops.numberer('RCM')
ops.constraints('Plain')
ops.integrator('LoadControl', 0.1)
ops.algorithm('Linear')
ops.analysis('Static')
ok = ops.analyze(10)
print("analyze return code (0=OK):", ok)

# Chuyen vi tai dinh cot (node dau tien trong TOP_COLUMN)
if len(top_col_nodes) > 0:
    n0 = int(top_col_nodes[0]) + 1
    ux = ops.nodeDisp(n0, 1)
    print(f"Ux tai dinh cot (node {n0}) = {ux*1000:.4f} mm")

# Chuyen vi tai 1 nut day (BASE) - phai ~0
n_base = int(list(nsets["BASE"])[0]) + 1
print(f"Ux tai BASE (node {n_base}) = {ops.nodeDisp(n_base, 1)*1000:.6f} mm (phai ~0)")
