"""Test TRUC TIEP mo hinh DEO (khong chay rieng buoc dan hoi) — 1 cot, DU 3 LOP
DAT THAT KE (params_io.build_default_params), lop DAT YEU dung
PressureIndependMultiYield voi MO DUN LAY TU THI NGHIEM NEN CO KET (oedometer)
THAT — theo yeu cau nguoi dung 2026-08-27 (KHONG dung Es=250*Su Mesri nua).

Nguon tham so:
- G_ref/B_ref: suy tu Eoed = TRUNG BINH lab_tests.E_kPa THAT (da tinh san moi mau
  theo cong thuc Eoed=(1+e0)/(a1-2 x 0.01), CLAUDE.md muc 11c) qua
  params_io.query_oedometer_avg("KE") — KHAC voi Es=3450 (Mesri, dang dung trong
  cdm3d_params.json cho nhanh Bonded/Contact) — day la nguon THI NGHIEM NEN CO
  KET THAT, khong phai tuong quan gian tiep tu Su.
- cohesi (Su): VAN tu VST that qua params_io.query_su_vst_avg() — oedometer
  KHONG do cuong do khang cat, khong the thay the Su.
- peakShearStra/frictionAng/refPress/pressDependCoe: GIA DINH nhu truoc (chua
  co thi nghiem/tra cuu du an rieng).

Tham so PressureIndependMultiYield tra cuu tu nguon CHINH THUC (khong doan):
https://opensees.berkeley.edu/OpenSees/manuals/usermanual/1558.htm
Cu phap: nDMaterial('PressureIndependMultiYield', matTag, nd, rho,
    refShearModul, refBulkModul, cohesi, peakShearStra, frictionAng,
    refPress, pressDependCoe, noYieldSurf)

QUY TAC BAT BUOC (xem skill /cdm3d-opensees): lay thong so qua
params_io.build_default_params(zone) + cac ham query_*_avg() — KHONG hardcode.
"""
import sys
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

import gmsh
import numpy as np
import openseespy.opensees as ops
import pyvista as pv
pv.OFF_SCREEN = True  # chay trong script/background, khong co man hinh hien thi —
                       # BAT BUOC truoc khi tao Plotter (vfo.plot_model/plot_deformedshape
                       # goi pl.screenshot() sau, se loi "Nothing to screenshot" neu thieu)
import vfo.vfo as vfo

from cdm3d import geometry, mesh_gmsh, params_io
from cdm3d.ccx_input import _read_mesh

params = params_io.build_default_params("KE")
params.column.n_x = 1
params.column.n_y = 1
soil_layers = params.soil_layers
column = params.column

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

ops.wipe()
ops.model('basic', '-ndm', 3, '-ndf', 3)

for i, (x, y, z) in enumerate(points, start=1):
    ops.node(i, float(x), float(y), float(z))

# --- Vat lieu ---
mat_tag_by_name = {}
tag_i = 1

# Lop dat yeu: PressureIndependMultiYield (deo, khong thoat nuoc, phi=0)
layer_yeu = next(l for l in soil_layers if l.name == "dat_yeu")
nu = layer_yeu.nu  # GIA DINH (0.35) — oedometer la thi nghiem 1D, KHONG do duoc nu

oedo = params_io.query_oedometer_avg("KE")
print("Thong so nen co ket THAT (KE, dat_yeu):")
for k, (avg, n) in oedo.items():
    print(f"  {k}: trung binh={avg}  (n={n} mau)")
E_kPa_oedo, n_e = oedo["E_kPa"]
if E_kPa_oedo is None:
    raise RuntimeError("Khong tim thay lab_tests.E_kPa cho KE — kiem tra lai SQLite.")
E = E_kPa_oedo
print(f"=> Dung Eoed THAT = {E:.1f} kPa (trung binh {n_e} mau oedometer) lam mo dun "
      f"dan hoi cho G_ref/B_ref — THAY cho Es={layer_yeu.E_kPa:.0f} kPa (Mesri, "
      f"dang dung trong cdm3d_params.json cho cac nhanh khac).")

G_ref = E / (2.0 * (1.0 + nu))
B_ref = E / (3.0 * (1.0 - 2.0 * nu))
rho_yeu = layer_yeu.gamma_kNm3 / 9.81
# Su THAT tu cat canh hien truong (VST) khu vuc KE, uu tien dung theo CLAUDE.md
# muc 6 (VST > lab > gia dinh) — oedometer KHONG do cuong do khang cat.
Su_kPa, n_vst = params_io.query_su_vst_avg("KE", layer_yeu.z_top, layer_yeu.z_bot)
if Su_kPa is None:
    raise RuntimeError("Khong tim thay du lieu VST cho KE — kiem tra lai SQLite.")
print(f"Su that tu VST: {Su_kPa:.2f} kPa (trung binh {n_vst} mau, KE-*, "
      f"do sau {-layer_yeu.z_top:.1f}..{-layer_yeu.z_bot:.1f}m)")
peakShearStra = 0.10  # GIA DINH — gia tri dien hinh cho set theo bang tham khao
                       # chinh thuc OpenSees (soft/medium/stiff clay deu ~0.1)
frictionAng = 0.0     # dat set khong thoat nuoc: phi=0 (dung quy uoc du an, xem
                       # CLAUDE.md Bishop/Fellenius "c=Cu, phi=0")
refPress = 100.0      # kPa, mac dinh khuyen nghi chinh thuc
pressDependCoe = 0.0  # dat set: modulus KHONG phu thuoc ap suimport (mac dinh khuyen nghi)
noYieldSurf = 20

print(f"[dat_yeu] G_ref={G_ref:.1f} kPa, B_ref={B_ref:.1f} kPa, Su={Su_kPa:.2f} kPa, "
      f"peakShearStra={peakShearStra}, phi={frictionAng} deg")

ops.nDMaterial('PressureIndependMultiYield', tag_i, 3, rho_yeu,
               G_ref, B_ref, Su_kPa, peakShearStra, frictionAng,
               refPress, pressDependCoe, noYieldSurf)
mat_tag_by_name["SOIL_dat_yeu"] = tag_i
tag_i += 1

# Cac lop con lai: ElasticIsotropic (giu nguyen nhu test dan hoi)
for name in elsets:
    if name == "SOIL_dat_yeu":
        continue
    if name == "CDM_COLUMN":
        Em, num, gamma = column.Ec_kPa, column.nu_c, column.gamma_kNm3
    else:
        layer = next(l for l in soil_layers if l.name == name.removeprefix("SOIL_"))
        Em, num, gamma = layer.E_kPa, layer.nu, layer.gamma_kNm3
    ops.nDMaterial('ElasticIsotropic', tag_i, Em, num, gamma / 9.81)
    mat_tag_by_name[name] = tag_i
    tag_i += 1

elem_id = 1
for name, idx in elsets.items():
    matTag = mat_tag_by_name[name]
    for k in idx:
        nodes = [int(n) + 1 for n in elements[k]]
        ops.element('FourNodeTetrahedron', elem_id, *nodes, matTag)
        elem_id += 1

# --- Bien: gop truoc khi fix (giong ban vay OpenSeesPy dan hoi) ---
fix_map: dict[int, list[int]] = {}
def _accumulate(node_ids, dofs):
    for n in node_ids:
        tg = int(n) + 1
        cur = fix_map.setdefault(tg, [0, 0, 0])
        for i, d in enumerate(dofs):
            if d:
                cur[i] = 1

_accumulate(nsets["BASE"], (1, 1, 1))
_accumulate(nsets.get("SIDE_XMIN", []), (1, 0, 0))
_accumulate(nsets.get("SIDE_XMAX", []), (1, 0, 0))
_accumulate(nsets.get("SIDE_YMIN", []), (0, 1, 0))
_accumulate(nsets.get("SIDE_YMAX", []), (0, 1, 0))
for tg, dofs in fix_map.items():
    ops.fix(tg, *dofs)

# PressureIndependMultiYield mac dinh khoi tao o "stage 0" (dan hoi TUYET DOI,
# theo tai lieu chinh thuc updateMaterialStage) — PHAI chuyen "stage 1" (deo)
# TRUOC khi ap tai muon quan sat deo, neu khong vat lieu se dan hoi VINH VIEN bat
# ke tai lon bao nhieu (da xac nhan thuc nghiem qua test_opensees_plastic_sweep.py:
# 4000kN van hoan toan tuyen tinh neu thieu buoc nay). Xem 76-...md muc 9c.
ops.updateMaterialStage('-material', mat_tag_by_name["SOIL_dat_yeu"], '-stage', 1)

# --- Tai ngang 50 kN tai TOP_COLUMN, chia deu (giong het ban dan hoi) ---
top_col_nodes = np.unique(nsets.get("TOP_COLUMN", np.array([])))
F_total = 50.0
F_per_node = F_total / max(len(top_col_nodes), 1)
ops.timeSeries('Linear', 1)
ops.pattern('Plain', 1, 1)
for n in top_col_nodes:
    ops.load(int(n) + 1, F_per_node, 0.0, 0.0)

ops.system('SuperLU')  # sparse solver thuc su — nhanh hon BandGeneral cho luoi lon (24k+ phan tu)
ops.numberer('RCM')
ops.constraints('Plain')
ops.test('NormDispIncr', 1.0e-6, 30, 0)
ops.algorithm('Newton')
ops.integrator('LoadControl', 0.05)  # buoc nho hon cho hoi tu phi tuyen
ops.analysis('Static')

# vfo (Visualization Framework for OpenSees, pip install vfo) — ghi database
# ket qua TRUOC khi analyze() (gan recorder chuyen vi/phan ung tu dong).
VFO_MODEL = "ke_dat_yeu_plastic"
VFO_CASE = "TaiNgang50kN"
vfo.createODB(model=VFO_MODEL, loadcase=VFO_CASE)

ok = ops.analyze(20)
print("analyze return code (0=OK):", ok)

if len(top_col_nodes) > 0:
    n0 = int(top_col_nodes[0]) + 1
    ux = ops.nodeDisp(n0, 1)
    print(f"Ux tai dinh cot (node {n0}) = {ux*1000:.4f} mm  (deo, PressureIndependMultiYield, "
          f"Eoed={E:.1f}kPa tu nen co ket that, Su={Su_kPa:.2f}kPa tu VST that)")
    # KHONG so sanh voi baseline dan hoi cu (5.2856mm) — baseline do dung E=3450
    # (Mesri) khac E o day (Eoed that) nen KHONG apples-to-apples. Theo yeu cau
    # nguoi dung: chay thang deo, khong chay lai dan hoi rieng cho bo du lieu nay.

n_base = int(list(nsets["BASE"])[0]) + 1
print(f"Ux tai BASE (node {n_base}) = {ops.nodeDisp(n_base, 1)*1000:.6f} mm (phai ~0)")

# --- Xuat anh bang vfo (khong can Jupyter, luu PNG truc tiep) ---
IMG_DIR = ROOT / "images"
IMG_DIR.mkdir(exist_ok=True)
vfo.plot_model(model=VFO_MODEL, show_nodes="no", setview="3D",
               filename=str(IMG_DIR / "vfo_ke_dat_yeu_plastic_model.png"))
vfo.plot_deformedshape(model=VFO_MODEL, loadcase=VFO_CASE, scale=300,
                        contour="x", setview="3D",
                        filename=str(IMG_DIR / "vfo_ke_dat_yeu_plastic_deformed.png"))
print("Da xuat anh vfo vao thu muc images/.")
