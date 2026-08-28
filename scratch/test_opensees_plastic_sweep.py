"""Quet F_total tang dan de xac nhan PressureIndependMultiYield THUC SU kich hoat
deo (khong chi lang le cu xu dan hoi o moi muc tai). Neu deo dung, Ux phai TANG
NHANH HON tuyen tinh (sieu tuyen tinh) khi tai vuot nguong gay chay dau tien —
khac voi dan hoi (Ux ty le TUYEN TINH voi tai).

Thong so lop dat yeu: THAT tu KE — Eoed tu thi nghiem nen co ket (oedometer,
params_io.query_oedometer_avg), Su tu VST (params_io.query_su_vst_avg) — xem
test_opensees_plastic.py va skill /cdm3d-opensees. KHONG chay rieng mo hinh dan
hoi de doi chieu (theo yeu cau nguoi dung 2026-08-27) — dung chinh diem tai NHO
NHAT trong dai quet lam moc quy chieu tuyen tinh tu suy (self-referential),
khong can mo phong dan hoi rieng.
"""
import sys
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
import openseespy.opensees as ops

from cdm3d import params_io
from cdm3d.ccx_input import _read_mesh

msh_path = ROOT / "scratch" / "test_ops.msh"
points, elements, elsets, nsets = _read_mesh(msh_path, 1)

params = params_io.build_default_params("KE")
params.column.n_x = 1
params.column.n_y = 1
soil_layers = params.soil_layers
column = params.column

layer_yeu = next(l for l in soil_layers if l.name == "dat_yeu")
nu = layer_yeu.nu  # GIA DINH — oedometer khong do duoc

E, n_e = params_io.query_oedometer_avg("KE")["E_kPa"]
if E is None:
    raise RuntimeError("Khong tim thay lab_tests.E_kPa cho KE.")
G_ref = E / (2.0 * (1.0 + nu))
B_ref = E / (3.0 * (1.0 - 2.0 * nu))
rho_yeu = layer_yeu.gamma_kNm3 / 9.81
Su_kPa, n_vst = params_io.query_su_vst_avg("KE", layer_yeu.z_top, layer_yeu.z_bot)
if Su_kPa is None:
    raise RuntimeError("Khong tim thay du lieu VST cho KE.")
print(f"Eoed that = {E:.1f} kPa (n={n_e} mau oedometer), Su that = {Su_kPa:.2f} kPa (n={n_vst} mau VST)")


def run_case(F_total: float) -> float:
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 3)
    for i, (x, y, z) in enumerate(points, start=1):
        ops.node(i, float(x), float(y), float(z))

    mat_tag_by_name = {}
    tag_i = 1
    ops.nDMaterial('PressureIndependMultiYield', tag_i, 3, rho_yeu,
                   G_ref, B_ref, Su_kPa, 0.10, 0.0, 100.0, 0.0, 20)  # tag_i=1 luon la SOIL_dat_yeu (khai bao dau tien)
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

    # PressureIndependMultiYield mac dinh khoi tao o "stage 0" (dan hoi tuyet doi,
    # theo tai lieu chinh thuc updateMaterialStage — xem 76-....md muc 9c) — PHAI
    # chuyen sang "stage 1" (deo) truoc khi ap tai muon quan sat deo, neu khong vat
    # lieu se cu xu dan hoi VINH VIEN bat ke tai lon bao nhieu (da xac nhan thuc
    # nghiem: 4000kN van tuyen tinh tuyet doi neu thieu buoc nay).
    ops.updateMaterialStage('-material', mat_tag_by_name["SOIL_dat_yeu"], '-stage', 1)

    top_col_nodes = np.unique(nsets.get("TOP_COLUMN", np.array([])))
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
    n_steps = 20
    ops.integrator('LoadControl', 1.0 / n_steps)
    ops.analysis('Static')
    ok = ops.analyze(n_steps)
    if ok != 0:
        return float('nan')
    n0 = int(top_col_nodes[0]) + 1
    return ops.nodeDisp(n0, 1) * 1000.0


print(f"Su (dat_yeu) = {Su_kPa:.2f} kPa, Eoed = {E:.1f} kPa — quet F_total de tim nguong deo")
loads = (50, 100, 200, 400, 800, 1200, 1600, 2000, 3000, 4000)
results = [run_case(F) for F in loads]

# Moc quy chieu TUYEN TINH TU SUY tu diem tai NHO NHAT (khong chay mo hinh dan
# hoi rieng) — gan dung F=50kN con trong mien gan-dan-hoi (chua vuot nguong chay).
ux_per_kn_ref = results[0] / loads[0]

print(f"{'F_total(kN)':>12} {'Ux_deo(mm)':>12} {'Ux_neu_tuyen_tinh(mm)':>22} {'ty_le':>8}")
for F, ux in zip(loads, results):
    ux_linear_ref = ux_per_kn_ref * F
    ratio = ux / ux_linear_ref if ux_linear_ref else float('nan')
    print(f"{F:>12.0f} {ux:>12.4f} {ux_linear_ref:>22.4f} {ratio:>8.3f}")
