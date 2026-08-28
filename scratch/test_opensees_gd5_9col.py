"""Chay CHUOI TAI THAT GD2->GD5 (dap tang dan + lech tam + GD5 tai nua mien +X)
bang OpenSeesPy, lop dat yeu dung PressureIndependMultiYield voi Eoed/Su THAT
(xem test_opensees_plastic.py) — CHUA TUNG lam truoc day (cac test OpenSeesPy
truoc chi dung tai ngang diem gia lap, KHONG phai tai dung phan bo GD that).

Muc tieu: tim CO CHE VAT LY hop ly co the giai thich chenh lech voi quan trac
thuc te (Ux~80cm tai GD5) — KHONG ep tham so de khop dung so do (quyet dinh
nguoi dung 2026-08-27). Neu khong dat duoc bang co che hop ly, bao cao trung
thuc nhu da lam voi khao sat domain/Es truoc day (76-cdm3d-fem-gmsh-calculix.md muc 0).

DOMAIN_BUFFER_M: tham so co the tang de kiem tra lai gia thuyet domain cho
NHANH DEO (truoc day chi loai tru cho nhanh BONDED dan hoi — xem muc 0 tai lieu
chinh, chua kiem chung cho PressureIndependMultiYield).

Mo hinh nho (1 cot, n_x=n_y=1) TRUOC de kiem chung co che tai GD dung dan —
CHUA scale len 9 cot (production that) o script nay.
"""
import sys
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

import gmsh
import numpy as np
import openseespy.opensees as ops
import pyvista as pv
pv.OFF_SCREEN = True
import vfo.vfo as vfo

from cdm3d import geometry, mesh_gmsh, params_io
from cdm3d.ccx_input import _read_mesh, _node_tributary_area, _eccentric_pressure, validate_eccentricity
from cdm3d.progress_log import init_csv, append_row, plot_progress

# ============ THAM SO CO THE DIEU CHINH ============
ZONE = "KE"
N_X, N_Y = 3, 3                 # PRODUCTION THAT — 9 coc, chay SONG SONG voi ban
                                 # 1-coc (test_opensees_gd5.py) de khong mat thoi
                                 # gian cho tuan tu — se dung neu ban 1-coc bao loi.
DOMAIN_BUFFER_M = 3.6          # mac dinh production; TANG LEN (vd 10.0, 20.0) de kiem tra
                                # lai gia thuyet domain cho NHANH DEO (chua tung test)
# =====================================================

params = params_io.build_default_params(ZONE)
params.column.n_x = N_X
params.column.n_y = N_Y
params.domain_buffer_m = DOMAIN_BUFFER_M
soil_layers = params.soil_layers
column = params.column
print(f"domain_buffer_m={params.domain_buffer_m}  domain_x={params.domain_x_m():.2f}m  "
      f"n_x={N_X} n_y={N_Y}")

msh_path = ROOT / "scratch" / "test_ops_gd5_9col.msh"
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

# --- Vat lieu: dat_yeu = PressureIndependMultiYield voi Eoed/Su THAT (giong
# test_opensees_plastic.py) ---
layer_yeu = next(l for l in soil_layers if l.name == "dat_yeu")
nu = layer_yeu.nu
oedo = params_io.query_oedometer_avg(ZONE)
E_oed, n_e = oedo["E_kPa"]
if E_oed is None:
    raise RuntimeError(f"Khong co lab_tests.E_kPa that cho {ZONE}.")
G_ref = E_oed / (2.0 * (1.0 + nu))
B_ref = E_oed / (3.0 * (1.0 - 2.0 * nu))
rho_yeu = layer_yeu.gamma_kNm3 / 9.81
Su_kPa, n_vst = params_io.query_su_vst_avg(ZONE, layer_yeu.z_top, layer_yeu.z_bot)
if Su_kPa is None:
    raise RuntimeError(f"Khong co du lieu VST that cho {ZONE}.")
print(f"Eoed={E_oed:.1f}kPa (n={n_e})  Su={Su_kPa:.2f}kPa (n={n_vst})  "
      f"G_ref={G_ref:.1f}  B_ref={B_ref:.1f}")

ops.wipe()
ops.model('basic', '-ndm', 3, '-ndf', 3)
for i, (x, y, z) in enumerate(points, start=1):
    ops.node(i, float(x), float(y), float(z))

mat_tag_by_name = {}
tag_i = 1
ops.nDMaterial('PressureIndependMultiYield', tag_i, 3, rho_yeu,
               G_ref, B_ref, Su_kPa, 0.10, 0.0, 100.0, 0.0, 20)
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

ops.updateMaterialStage('-material', mat_tag_by_name["SOIL_dat_yeu"], '-stage', 1)

# --- Dien tich anh huong that (tributary area) TOP_SOIL + TOP_COLUMN ---
node_area = _node_tributary_area(msh_path, 1, ("TOP_SOIL", "TOP_COLUMN"))
top_idx = sorted(node_area.keys())
print(f"So nut chiu tai (TOP_SOIL+TOP_COLUMN): {len(top_idx)}")

B_x = params.domain_x_m()
B_y = params.domain_y_m()

VFO_MODEL, VFO_CASE = "ke_gd5_9col_staged", "GD_full"
vfo.createODB(model=VFO_MODEL, loadcase=VFO_CASE)

ops.system('UmfPack')  # 1,81x nhanh hon SuperLU o quy mo 9 coc that (172358 phan tu):
                        # 131,22s vs 237,90s/buoc — benchmark thuc do 2026-08-27
ops.numberer('RCM')
ops.constraints('Plain')
ops.test('NormDispIncr', 1.0e-6, 40, 0)
ops.algorithm('Newton')

PROGRESS_CSV = ROOT / "scratch" / "test_opensees_gd5_9col.progress.csv"
PROGRESS_PNG = ROOT / "images" / "gd5_9col_progress.png"
_T0 = init_csv(PROGRESS_CSV)
global_step = 0

top_col_nodes_for_log = np.unique(nsets.get("TOP_COLUMN", np.array([])))
_log_node = int(top_col_nodes_for_log[0]) + 1 if len(top_col_nodes_for_log) > 0 else None

results = []
prev_pattern_tag = None
for stage_i, stage in enumerate(params.stages, start=1):
    if prev_pattern_tag is not None:
        ops.remove('loadPattern', prev_pattern_tag)
    ops.timeSeries('Linear', stage_i)
    ops.pattern('Plain', stage_i, stage_i)
    prev_pattern_tag = stage_i

    axis_col = 0 if stage.ecc_axis == "x" else 1
    B = B_x if stage.ecc_axis == "x" else B_y
    n_loaded = 0
    if stage.load_footprint == "full":
        e_use, warn = validate_eccentricity(stage.eccentricity_m, B)
        if warn:
            print(f"[{stage.name}] CANH BAO: {warn}")
        for n in top_idx:
            pos = points[n][axis_col]
            q_i = _eccentric_pressure(pos, stage.q_avg_kPa, e_use, B)
            F_i = q_i * node_area[n]
            ops.load(n + 1, 0.0, 0.0, -F_i)
            n_loaded += 1
    else:
        sign = 1.0 if stage.load_footprint == "half_pos" else -1.0
        for n in top_idx:
            pos = points[n][axis_col]
            if sign * pos < 0:
                continue
            F_i = stage.q_avg_kPa * node_area[n]
            ops.load(n + 1, 0.0, 0.0, -F_i)
            n_loaded += 1

    N_SUBSTEPS = 20
    ops.integrator('LoadControl', 1.0 / N_SUBSTEPS)
    ops.analysis('Static')
    print(f"[{stage.name}] q={stage.q_avg_kPa:.2f}kPa footprint={stage.load_footprint} "
          f"ecc={stage.eccentricity_m}m n_nut_tai={n_loaded} — bat dau {N_SUBSTEPS} buoc...",
          flush=True)

    # Chay TUNG BUOC (khong goi analyze(20) 1 lan) — ghi tien do ngay sau moi
    # buoc de co the ve bieu do "duong cong tinh toan" BAT KY LUC NAO (kieu
    # PLAXIS Calculation progress), khong phai doi ca giai doan xong moi biet.
    ok = 0
    for sub_i in range(N_SUBSTEPS):
        ok = ops.analyze(1)
        global_step += 1
        ux_now = ops.nodeDisp(_log_node, 1) * 1000.0 if _log_node else float("nan")
        append_row(PROGRESS_CSV, global_step, _T0, stage.name, (sub_i + 1) / N_SUBSTEPS, ux_now, ok)
        if sub_i % 3 == 0 or sub_i == N_SUBSTEPS - 1:
            print(f"  buoc {sub_i+1}/{N_SUBSTEPS}: Ux={ux_now:.2f}mm return={ok}", flush=True)
            plot_progress(PROGRESS_CSV, PROGRESS_PNG,
                          title=f"GD5 9-cọc KE — đang chạy ({stage.name}, bước {global_step})")
        if ok != 0:
            print(f"  CANH BAO: khong hoi tu tai buoc {sub_i+1}, dung giai doan nay.", flush=True)
            break

    if _log_node is not None:
        ux = ops.nodeDisp(_log_node, 1)
        uz = ops.nodeDisp(_log_node, 3)
        print(f"  [{stage.name}] KET THUC: Ux dinh cot = {ux*1000:.2f} mm, Uz = {uz*1000:.2f} mm",
              flush=True)
        results.append((stage.name, ux * 1000.0, uz * 1000.0, ok))
        plot_progress(PROGRESS_CSV, PROGRESS_PNG, title=f"GD5 9-cọc KE — sau giai đoạn {stage.name}")

print("\n=== TONG HOP CAC GIAI DOAN ===")
for name, ux, uz, ok in results:
    print(f"{name:45s}  Ux={ux:8.2f}mm  Uz={uz:8.2f}mm  return={ok}")

IMG_DIR = ROOT / "images"
IMG_DIR.mkdir(exist_ok=True)
vfo.plot_deformedshape(model=VFO_MODEL, loadcase=VFO_CASE, scale=20, contour="x",
                        setview="3D", filename=str(IMG_DIR / "vfo_ke_gd5_9col_deformed"))
print("Da xuat anh vfo.")
