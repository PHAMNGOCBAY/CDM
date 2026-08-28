"""Test doc lap: kiem chung co che *MODEL CHANGE (REMOVE/ADD cot CDM) + khoa nut mo coi
tren mo hinh NHO (1 cot, luoi tho) truoc khi tich hop vao ccx_input.py that.
"""
import sys
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

import gmsh
import numpy as np

from cdm3d import geometry, mesh_gmsh, ccx_input, run_ccx
from cdm3d.types import ColumnGroup, ModelParams, SoilLayer

# --- Mo hinh nho: 1 cot, mien nho, luoi tho ---
soil_layers = [
    SoilLayer("dat_dap", 0.8, 0.0, 19.0, 8000.0, 0.30, source="test"),
    SoilLayer("dat_yeu", 0.0, -5.0, 16.0, 3450.0, 0.35, source="test"),
    SoilLayer("lop_cung", -5.0, -7.0, 19.0, 27600.0, 0.35, source="test"),
]
column = ColumnGroup(D_m=0.8, spacing_m=1.8, n_x=1, n_y=1, z_top=0.8, z_bot=-6.0,
                      Ec_kPa=40000.0, nu_c=0.25, gamma_kNm3=18.0, source="test")
params = ModelParams(
    zone_code="TEST1COL", soil_layers=soil_layers, column=column,
    q_surcharge_kPa=0.0, domain_buffer_m=2.0,
    mesh_size_far_m=1.0, mesh_size_near_column_m=0.35, column_box_field_margin_m=0.5,
)

out_dir = ROOT / "scratch"
msh_path = out_dir / "test_mc.msh"

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

points, elements, elsets, nsets = ccx_input._read_mesh(msh_path, 1)
print("elsets:", {k: len(v) for k, v in elsets.items()})
print("nsets:", {k: len(v) for k, v in nsets.items()})

# --- Tim nut "mo coi": thuoc CDM_COLUMN nhung KHONG thuoc bat ky SOIL_* nao ---
def _nodes_of_elset(name):
    idx = elsets[name]
    return set(elements[idx].ravel().tolist())

col_nodes = _nodes_of_elset("CDM_COLUMN")
soil_nodes = set()
for name in elsets:
    if name.startswith("SOIL_"):
        soil_nodes |= _nodes_of_elset(name)
orphan_nodes = sorted(col_nodes - soil_nodes)
print(f"col_nodes={len(col_nodes)} soil_nodes={len(soil_nodes)} orphan={len(orphan_nodes)}")

# --- Ghi .inp thu cong: GD0 (REMOVE + khoa mo coi) -> GD1 (ADD + go khoa) ---
lines = ["** test model change", "*NODE, NSET=NALL"]
for i, (x, y, z) in enumerate(points, start=1):
    lines.append(f"{i}, {x:.6f}, {y:.6f}, {z:.6f}")

for name, idx in elsets.items():
    lines.append(f"*ELEMENT, TYPE=C3D4, ELSET={name}")
    for k in idx:
        nodes = elements[k] + 1
        lines.append(f"{k + 1}, " + ", ".join(str(n) for n in nodes))

for name in elsets:
    mat = f"MAT_{name}"
    if name == "CDM_COLUMN":
        E, nu, gamma = column.Ec_kPa, column.nu_c, column.gamma_kNm3
    else:
        layer = next(l for l in soil_layers if l.name == name.removeprefix("SOIL_"))
        E, nu, gamma = layer.E_kPa, layer.nu, layer.gamma_kNm3
    lines += [f"*MATERIAL, NAME={mat}", "*ELASTIC", f"{E:.3f}, {nu:.3f}",
              "*DENSITY", f"{gamma/9.81:.6f}",
              f"*SOLID SECTION, ELSET={name}, MATERIAL={mat}"]

for name, idx in nsets.items():
    lines.append(f"*NSET, NSET={name}")
    for cs in range(0, len(idx), 10):
        chunk = idx[cs:cs+10] + 1
        lines.append(", ".join(str(n) for n in chunk))

lines.append("*NSET, NSET=ORPHAN")
for cs in range(0, len(orphan_nodes), 10):
    chunk = [n + 1 for n in orphan_nodes[cs:cs+10]]
    lines.append(", ".join(str(n) for n in chunk))

perm_bc = ["*BOUNDARY", "BASE, 1, 3"]
for s in ("SIDE_XMIN",):
    if s in nsets: perm_bc.append(f"{s}, 1, 1")
for s in ("SIDE_XMAX",):
    if s in nsets: perm_bc.append(f"{s}, 1, 1")
for s in ("SIDE_YMIN",):
    if s in nsets: perm_bc.append(f"{s}, 2, 2")
for s in ("SIDE_YMAX",):
    if s in nsets: perm_bc.append(f"{s}, 2, 2")

lines += perm_bc

# GD0: remove column + lock orphan nodes
lines += [
    "*STEP, NLGEOM", "*STATIC",
    "*MODEL CHANGE, TYPE=ELEMENT, REMOVE",
    "CDM_COLUMN",
    "*BOUNDARY",
    "ORPHAN, 1, 3",
    "*NODE FILE", "U",
    "*END STEP",
]

# GD1: add column back (strain free) + release orphan lock (OP=NEW restates only permanent BC)
lines += [
    "*STEP, NLGEOM", "*STATIC",
    "*MODEL CHANGE, TYPE=ELEMENT, ADD",
    "CDM_COLUMN",
    "*BOUNDARY, OP=NEW",
] + perm_bc[1:] + [
    "*NODE FILE", "U",
    "*END STEP",
]

inp_path = out_dir / "test_mc.inp"
inp_path.write_text("\n".join(lines) + "\n", encoding="ascii", errors="replace")
print("wrote:", inp_path)

frd = run_ccx.solve(inp_path)
print("SOLVED OK ->", frd)
