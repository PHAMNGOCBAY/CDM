"""So sanh doi chieu: CUNG mo hinh nho (1 cot, 3 lop), CUNG BC, CUNG tai ngang
50 kN tai TOP_COLUMN nhu scratch/test_opensees_elastic.py — nhung giai bang
CalculiX bonded (khong contact, khong model change) de kiem chung ket qua
OpenSeesPy dan hoi truoc khi tin tuong phan deo.
"""
import sys
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

from cdm3d import ccx_input, run_ccx
from cdm3d.types import ColumnGroup, ModelParams, SoilLayer

soil_layers = [
    SoilLayer("dat_dap", 0.8, 0.0, 19.0, 8000.0, 0.30, source="test"),
    SoilLayer("dat_yeu", 0.0, -5.0, 16.0, 3450.0, 0.35, source="test"),
    SoilLayer("lop_cung", -5.0, -7.0, 19.0, 27600.0, 0.35, source="test"),
]
column = ColumnGroup(D_m=0.8, spacing_m=1.8, n_x=1, n_y=1, z_top=0.8, z_bot=-6.0,
                      Ec_kPa=40000.0, nu_c=0.25, gamma_kNm3=18.0, source="test")
params = ModelParams(zone_code="OPS1", soil_layers=soil_layers, column=column,
                      q_surcharge_kPa=0.0, domain_buffer_m=2.0,
                      mesh_size_far_m=1.0, mesh_size_near_column_m=0.35,
                      column_box_field_margin_m=0.5)

out_dir = ROOT / "scratch"
msh_path = out_dir / "test_ops.msh"  # DUNG LAI CHINH XAC file .msh da xuat boi
# test_opensees_elastic.py — KHONG mesh lai (Explore cross-check 2026-08-27 phat
# hien mesh lai doc lap 2 lan la lo hong: khong co gi dam bao gmsh deterministic
# tra ve CUNG thu tu node/element giua 2 tien trinh Python khac nhau, du cung
# geometry+mesh size). Neu file khong ton tai -> bao loi ro rang thay vi tu mesh.
if not msh_path.exists():
    raise FileNotFoundError(
        f"{msh_path} chua ton tai — hay chay scratch/test_opensees_elastic.py "
        "TRUOC de xuat luoi dung chung, KHONG tu mesh lai o day (tranh rui ro "
        "gmsh non-deterministic giua 2 tien trinh)."
    )

points, elements, elsets, nsets = ccx_input._read_mesh(msh_path, 1)
print(f"[dung chung luoi] {msh_path.name}: n_nodes={len(points)}, "
      f"n_elements={sum(len(v) for v in elsets.values())}")

lines = ["** so sanh doi chieu dan hoi CalculiX vs OpenSeesPy", "*NODE, NSET=NALL"]
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

perm_bc = ["*BOUNDARY", "BASE, 1, 3"]
for s in ("SIDE_XMIN", "SIDE_XMAX"):
    if s in nsets:
        perm_bc.append(f"{s}, 1, 1")
for s in ("SIDE_YMIN", "SIDE_YMAX"):
    if s in nsets:
        perm_bc.append(f"{s}, 2, 2")
lines += perm_bc

top_col_nodes = sorted(int(n) + 1 for n in nsets.get("TOP_COLUMN", []))
F_total = 50.0
F_per_node = F_total / max(len(top_col_nodes), 1)

lines += ["*STEP", "*STATIC", "*CLOAD"]
for n in top_col_nodes:
    lines.append(f"{n}, 1, {F_per_node:.6f}")
lines += ["*NODE FILE", "U", "*END STEP"]

inp_path = out_dir / "test_ccx_compare.inp"
inp_path.write_text("\n".join(lines) + "\n", encoding="ascii", errors="replace")
print("wrote:", inp_path)

frd = run_ccx.solve(inp_path)
print("SOLVED OK ->", frd)

from cdm3d.postprocess import convert_frd_to_vtu
import pyvista as pv

vtu = convert_frd_to_vtu(frd)
mesh = pv.read(vtu)
U = mesh["U"]  # (n_nodes, 3)
node_ids = mesh.point_data.get("node_id") if "node_id" in mesh.point_data else None

# points o day la mesh.points (0-indexed theo thu tu doc file, KHONG chac trung
# thu tu voi 'points' goc) -> tim node gan toa do TOP_COLUMN / BASE bang khoang cach
top_xyz = points[top_col_nodes[0] - 1]
base_tag = sorted(int(n) + 1 for n in nsets["BASE"])[0]
base_xyz = points[base_tag - 1]

import numpy as np
d_top = np.linalg.norm(mesh.points - top_xyz, axis=1)
i_top = int(np.argmin(d_top))
d_base = np.linalg.norm(mesh.points - base_xyz, axis=1)
i_base = int(np.argmin(d_base))

# Explore cross-check (2026-08-27): PHAI assert khoang cach ~0, khong duoc am
# tham lay nham node neu VTU sap xep lai / co node trung toa do.
assert d_top[i_top] < 1e-6, f"Khong tim thay node TOP_COLUMN khop toa do trong VTU (d={d_top[i_top]})"
assert d_base[i_base] < 1e-6, f"Khong tim thay node BASE khop toa do trong VTU (d={d_base[i_base]})"

print(f"CalculiX Ux tai dinh cot (gan node {top_col_nodes[0]}) = {U[i_top,0]*1000:.4f} mm")
print(f"CalculiX Ux tai BASE (gan node {base_tag}) = {U[i_base,0]*1000:.6f} mm (phai ~0)")
