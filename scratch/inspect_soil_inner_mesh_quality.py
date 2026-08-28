"""Chuan doan RE TIEN (khong giai CalculiX) cho gia thuyet "seam": tam giac bien
tren mat SOIL_INNER (lo hinh tru trong dat) tai ranh gioi lop dat co the bi meo/
nho bat thuong vi _set_mesh_size_fields_soil() (contact_geometry.py:130-149) chi
dung field Box dong nhat theo XY quanh truc coc, KHONG tinh chinh rieng theo Z tai
cac cao do ranh gioi lop.

So sanh chat luong PHAN TU KHOI (tet, qualityName=minSICN — do vien nen, cang gan
0 cang meo/suy bien) giua nhom GAN ranh gioi lop (seam) vs nhom XA seam nhung van
GAN mat tru coc — ca 2 nhom deu lay tu 3D tet ke can mat SOIL_INNER.

Dung params KE that (1 coc, giu nguyen 3 lop that) — chi mesh, KHONG giai CalculiX.
"""
import sys
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
import gmsh

from cdm3d import params_io
from cdm3d.contact_geometry import mesh_soil_with_holes

params = params_io.build_default_params("KE")
params.column.n_x = 1
params.column.n_y = 1
params.domain_buffer_m = 3.0  # thu nho de mesh nhanh, van giu du 3 lop that

out_msh = ROOT / "scratch" / "diag_soil_1col_3layer.msh"
stats = mesh_soil_with_holes(params, out_msh)
print("mesh_soil_with_holes stats:", stats)

r_pile = params.column.D_m / 2.0
z_ground = 0.0
z_soft_bot = params.soil_layers[1].z_bot  # ranh gioi dat_yeu/lop_cung
seam_elevations = [z_ground, z_soft_bot]
print(f"r_pile={r_pile:.3f}m, seam_elevations={seam_elevations}")

# --- Mo phien gmsh MOI de doc lai file .msh vua xuat va tinh chat luong ---
gmsh.initialize()
gmsh.option.setNumber("General.Terminal", 0)
gmsh.open(str(out_msh))

node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
coord_by_tag = {int(t): (node_coords[3 * i], node_coords[3 * i + 1], node_coords[3 * i + 2])
                for i, t in enumerate(node_tags)}

# type 4 = tu dien 4 nut (C3D4)
tet_type = 4
tet_tags, tet_node_tags = gmsh.model.mesh.getElementsByType(tet_type)
tet_node_tags = np.array(tet_node_tags).reshape(-1, 4)
print(f"So tu dien: {len(tet_tags)}")

qualities = np.array(gmsh.model.mesh.getElementQualities(tet_tags, "minSICN"))

BAND_Z = 0.5      # m, coi la "gan seam" neu |z_centroid - z_seam| <= BAND_Z
NEAR_PILE_FACTOR = 1.2  # coi la "gan mat tru" neu ban kinh centroid <= r_pile * factor

near_seam_q, away_seam_near_pile_q = [], []
for k, nodes in enumerate(tet_node_tags):
    xs = np.array([coord_by_tag[n][0] for n in nodes])
    ys = np.array([coord_by_tag[n][1] for n in nodes])
    zs = np.array([coord_by_tag[n][2] for n in nodes])
    cx, cy, cz = xs.mean(), ys.mean(), zs.mean()
    r_centroid = (cx**2 + cy**2) ** 0.5  # tam coc dat tai (0,0) — xem column_centers/geometry
    if r_centroid > r_pile * NEAR_PILE_FACTOR * 2.5:
        continue  # bo qua tet o xa mat tru (khong lien quan gia thuyet seam)
    is_near_pile = r_centroid <= r_pile * NEAR_PILE_FACTOR
    is_near_seam = any(abs(cz - z_seam) <= BAND_Z for z_seam in seam_elevations)
    if is_near_pile and is_near_seam:
        near_seam_q.append(qualities[k])
    elif is_near_pile and not is_near_seam:
        away_seam_near_pile_q.append(qualities[k])

gmsh.finalize()

near_seam_q = np.array(near_seam_q)
away_seam_near_pile_q = np.array(away_seam_near_pile_q)

print(f"\nSo tu dien GAN mat tru + GAN seam:  n={len(near_seam_q)}")
if len(near_seam_q):
    print(f"  minSICN: min={near_seam_q.min():.4f}  mean={near_seam_q.mean():.4f}  "
          f"p5={np.percentile(near_seam_q, 5):.4f}")

print(f"\nSo tu dien GAN mat tru + XA seam:   n={len(away_seam_near_pile_q)}")
if len(away_seam_near_pile_q):
    print(f"  minSICN: min={away_seam_near_pile_q.min():.4f}  mean={away_seam_near_pile_q.mean():.4f}  "
          f"p5={np.percentile(away_seam_near_pile_q, 5):.4f}")

if len(near_seam_q) and len(away_seam_near_pile_q):
    ratio = near_seam_q.min() / away_seam_near_pile_q.min() if away_seam_near_pile_q.min() != 0 else float('nan')
    print(f"\nTy le min(seam)/min(xa seam) = {ratio:.3f}  (<<1 nghia la seam RO RANG meo hon)")
    print("minSICN cang gan 0 (hoac AM) cang suy bien/meo — gia tri < 0.1 thuong coi la kem, "
          "< 0 la phan tu suy bien/dao chieu (invalid).")
