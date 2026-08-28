"""Test mo hinh "Soft Soil" that trong OpenSeesPy: nDMaterial BoundingCamClay
(Borja et al. 2001) cho lop dat yeu — KHAC voi PressureIndependMultiYield dang
dung (Tresca khong thoat nuoc, khong co ung xu nen/no the tich kieu Cam-Clay).

Cu phap chinh thuc (khong doan, xem 76-cdm3d-fem-gmsh-calculix.md muc 9f):
https://openseespydoc.readthedocs.io/en/latest/src/BoundingCamClay.html
nDMaterial('BoundingCamClay', matTag, massDensity, C, bulkMod, OCR, mu_o, alpha,
           lambda, h, m)

Nguon tham so — TAT CA suy tu du lieu THAT KE (khong hardcode), theo yeu cau
nguoi dung 2026-08-27:
- lambda = Cc/ln(10), Cc that TB 16 mau lab_tests (params_io.query_oedometer_avg)
- kappa (dung noi bo de suy bulkMod, KHONG phai tham so truc tiep) = Cs/ln(10)
- bulkMod (K) = (1+e0)*sigma_v_eff_ref / kappa (dan hoi Cam-Clay chuan) tai
  z_ref = giua lop dat yeu, dung params.sigma_v_eff_kPa() (co xet MNN)
- mu_o (G) = 3K(1-2nu)/(2(1+nu)), nu=0.35 GIA DINH (oedometer khong do duoc nu)
- OCR: TINH TUNG MAU (PC_kPa / sigma_v_eff TAI DUNG DO SAU mau do, KHONG lay
  trung binh PC roi chia trung binh sigma_v) — phat hien quan trong: OCR giam
  dan theo do sau, tu ~2-3 (nong) xuong ~0.4-0.7 (sau) — lop yeu sau CHUA CO
  KET XONG (underconsolidated). Dung TRUNG BINH TOAN BO cho 1 gia tri dai dien
  (don gian hoa hien tai: 1 vat lieu hang so cho ca lop).
- M (qua C, XAP XI C~=M, CHUA xac nhan cong thuc Borja chinh xac — CANH BAO) =
  6*sin(phi')/(3-sin(phi')), phi'_CU_eff that TB 14 mau
- h=0 (KHONG hardening — QUYET DINH NGUOI DUNG 2026-08-27: khong co du lieu hieu
  chinh du an, h=0 trung thuc hon la muon so tu 1 vi du tai lieu OpenSees)
- m: khong dung khi h=0 (he so mu chi anh huong nhanh hardening, vo nghia khi h=0)
"""
import math
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

layer_yeu = next(l for l in soil_layers if l.name == "dat_yeu")
nu = layer_yeu.nu  # GIA DINH — oedometer khong do duoc

oedo = params_io.query_oedometer_avg("KE")
Cc, n_cc = oedo["Cc"]
Cs, n_cs = oedo["Cs"]
e0, n_e0 = oedo["e0"]
if None in (Cc, Cs, e0):
    raise RuntimeError("Thieu Cc/Cs/e0 that cho KE — kiem tra lai SQLite.")

lam = Cc / math.log(10)
kappa = Cs / math.log(10)

z_ref = (layer_yeu.z_top + layer_yeu.z_bot) / 2.0
sv_ref = params.sigma_v_eff_kPa(z_ref)
K_bulk = (1.0 + e0) * sv_ref / kappa
G_mu0 = 3.0 * K_bulk * (1.0 - 2.0 * nu) / (2.0 * (1.0 + nu))

# OCR: tinh TUNG MAU that (PC_kPa tai dung do sau, KHONG lay TB PC roi chia TB sv)
import sqlite3
_SOFT = ("CH", "MH", "CH-OH", "MH-OH")
con = sqlite3.connect(str(ROOT / "data" / "TTHC.sqlite"))
q = ",".join(f"'{s}'" for s in _SOFT)
cur = con.execute(f"""
    SELECT lt.PC_kPa, lt.depth_from_m, lt.depth_to_m
    FROM lab_tests lt JOIN boreholes b ON lt.borehole_id = b.id
    WHERE b.name LIKE 'KE-%' AND lt.symbol_tcvn IN ({q}) AND lt.PC_kPa IS NOT NULL
      AND lt.depth_from_m IS NOT NULL AND lt.depth_to_m IS NOT NULL
""")
ocr_samples = []
for pc, d_from, d_to in cur.fetchall():
    z_mid = -(d_from + d_to) / 2.0
    try:
        sv = params.sigma_v_eff_kPa(z_mid)
    except ValueError:
        continue
    if sv > 0:
        ocr_samples.append(pc / sv)
con.close()
if not ocr_samples:
    raise RuntimeError("Khong tinh duoc OCR tung mau — kiem tra lai du lieu PC_kPa/depth.")
OCR = float(np.mean(ocr_samples))
print(f"OCR tung mau (n={len(ocr_samples)}): TB={OCR:.3f} min={min(ocr_samples):.3f} "
      f"max={max(ocr_samples):.3f} — CANH BAO: giam manh theo do sau (xem docstring).")

# M tu phi'_CU_eff that (Roscoe/Schofield, TCT nen ba truc)
cur = con = sqlite3.connect(str(ROOT / "data" / "TTHC.sqlite"))
cur = con.execute(f"""
    SELECT AVG(lt.phi_CU_eff_deg), COUNT(*)
    FROM lab_tests lt JOIN boreholes b ON lt.borehole_id = b.id
    WHERE b.name LIKE 'KE-%' AND lt.symbol_tcvn IN ({q}) AND lt.phi_CU_eff_deg IS NOT NULL
""")
phi_eff, n_phi = cur.fetchone()
con.close()
if phi_eff is None:
    raise RuntimeError("Khong co phi_CU_eff_deg that cho KE.")
M_crit = 6.0 * math.sin(math.radians(phi_eff)) / (3.0 - math.sin(math.radians(phi_eff)))
C_ratio = M_crit  # XAP XI bac 1 — CHUA xac nhan cong thuc Borja C<->M chinh xac

h_hard = 0.0   # QUYET DINH NGUOI DUNG 2026-08-27: khong hardening (thieu du lieu hieu chinh)
m_hard = 0.0   # vo nghia khi h=0, dat 0 cho ro rang

print(f"lambda={lam:.4f}  kappa={kappa:.4f} (chi dung noi bo)  bulkMod={K_bulk:.1f} kPa  "
      f"mu_o={G_mu0:.1f} kPa  OCR={OCR:.3f}  phi'_eff={phi_eff:.2f}deg (n={n_phi})  "
      f"M={M_crit:.4f}  C~=M={C_ratio:.4f}  h={h_hard}  m={m_hard}")

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

ops.wipe()
ops.model('basic', '-ndm', 3, '-ndf', 3)
for i, (x, y, z) in enumerate(points, start=1):
    ops.node(i, float(x), float(y), float(z))

mat_tag_by_name = {}
tag_i = 1
ops.nDMaterial('BoundingCamClay', tag_i, layer_yeu.gamma_kNm3 / 9.81,
               C_ratio, K_bulk, OCR, G_mu0, 0.0, lam, h_hard, m_hard)
mat_tag_by_name["SOIL_dat_yeu"] = tag_i
tag_i += 1

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

# LUU Y: BoundingCamClay KHONG nam trong danh sach vat lieu can updateMaterialStage
# chinh thuc (PressureDependMultiYield/02, PressureIndependMultiYield,
# FluidSolidPorous) — KHONG goi updateMaterialStage o day. Neu ket qua bat
# thuong (hoan toan tuyen tinh bat ke tai), day la nghi van dau tien can kiem tra.

top_col_nodes = np.unique(nsets.get("TOP_COLUMN", np.array([])))
F_total = 50.0
F_per_node = F_total / max(len(top_col_nodes), 1)
ops.timeSeries('Linear', 1)
ops.pattern('Plain', 1, 1)
for n in top_col_nodes:
    ops.load(int(n) + 1, F_per_node, 0.0, 0.0)

ops.system('SuperLU')  # sparse solver thuc su — nhanh hon BandGeneral cho luoi lon
ops.numberer('RCM')
ops.constraints('Plain')
ops.test('NormDispIncr', 1.0e-6, 30, 0)
ops.algorithm('Newton')
ops.integrator('LoadControl', 0.05)
ops.analysis('Static')
ok = ops.analyze(20)
print("analyze return code (0=OK):", ok)

if len(top_col_nodes) > 0:
    n0 = int(top_col_nodes[0]) + 1
    ux = ops.nodeDisp(n0, 1)
    print(f"Ux tai dinh cot (node {n0}) = {ux*1000:.4f} mm  (BoundingCamClay, "
          f"lambda={lam:.3f}, OCR={OCR:.2f}, M~=C={M_crit:.3f}, h=0)")

n_base = int(list(nsets["BASE"])[0]) + 1
print(f"Ux tai BASE (node {n_base}) = {ops.nodeDisp(n_base, 1)*1000:.6f} mm (phai ~0)")
