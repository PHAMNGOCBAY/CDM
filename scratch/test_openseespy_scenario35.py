"""Cross-check kich ban 3.5 (bao cao kiem toan coc CDM) bang OpenSeesPy TUAN
TU (khong OpenSeesMP — khong kha thi tren may nay, xem ghi chu phien lam viec).

Dung LAI CHINH XAC luoi tu diem gmsh (grout_row.msh) da dung cho CalculiX —
FourNodeTetrahedron trong OpenSeesPy doc duoc luoi nay truc tiep, KHONG can
luoi hex rieng.

Vat lieu:
  - dat_yeu: PressureIndependMultiYield (Su=5000kPa GIA DINH khong bind — giong
    het muc dich Mohr-Coulomb Su=5000 ben CalculiX, chi khac dang cong thuc).
  - dat_dap, lop_cung, CDM_COLUMN: ElasticIsotropic (Ec=40000kPa THAT cho coc).

Tai: GD5 that (luc nut tu dien_tich anh huong, q*node_area) + luc hang vua
tren hang coc x=0 (luc/nut deu, huong +X) — CUNG 5 muc P da dung ben CalculiX
(2922.58 / 3672.77 / 4422.96 / 5173.14 / 5923.33 kPa) de so sanh true CHINH
XAC cung 1 tai, khong ep khop chuyen vi rieng cho OpenSeesPy.
"""
import sys
import time
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
import openseespy.opensees as ops
import pyvista as pv

from cdm3d import params_io
from cdm3d.ccx_input import _read_mesh, _node_tributary_area
from cdm3d.geometry import column_centers

pv.OFF_SCREEN = True
ZONE = "KE"
MSH = ROOT / "scratch" / "grout_row.msh"
OUT = ROOT / "scratch"
SU_KPA = 5000.0
D_m = 0.8

P_LIST = {40: 2922.58, 50: 3672.77, 60: 4422.96, 70: 5173.14, 80: 5923.33}


def build_and_solve(P_kPa, tag):
    params = params_io.build_default_params(ZONE)
    gd5 = next(s for s in params.stages if s.name.startswith("GD5"))
    layer_yeu = next(l for l in params.soil_layers if l.name == "dat_yeu")
    nu = layer_yeu.nu
    Es = layer_yeu.E_kPa
    G_ref = Es / (2.0 * (1.0 + nu))
    B_ref = Es / (3.0 * (1.0 - 2.0 * nu))
    rho_yeu = layer_yeu.gamma_kNm3 / 9.81

    points, elements, elsets, nsets = _read_mesh(MSH, 1)

    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 3)
    for i, (x, y, z) in enumerate(points, start=1):
        ops.node(i, float(x), float(y), float(z))

    mat_tag = {}
    t = 1
    ops.nDMaterial('PressureIndependMultiYield', t, 3, rho_yeu, G_ref, B_ref,
                    SU_KPA, 0.10, 0.0, 100.0, 0.0, 20)
    mat_tag["SOIL_dat_yeu"] = t
    t += 1
    for name in elsets:
        if name == "SOIL_dat_yeu":
            continue
        if name == "CDM_COLUMN":
            Em, num, gamma = params.column.Ec_kPa, params.column.nu_c, params.column.gamma_kNm3
        else:
            layer = next(l for l in params.soil_layers if l.name == name.removeprefix("SOIL_"))
            Em, num, gamma = layer.E_kPa, layer.nu, layer.gamma_kNm3
        ops.nDMaterial('ElasticIsotropic', t, Em, num, gamma / 9.81)
        mat_tag[name] = t
        t += 1

    elem_id = 1
    elem_id_by_name = {}
    for name, idx in elsets.items():
        mt = mat_tag[name]
        ids = []
        for k in idx:
            nodes = [int(n) + 1 for n in elements[k]]
            ops.element('FourNodeTetrahedron', elem_id, *nodes, mt)
            ids.append(elem_id)
            elem_id += 1
        elem_id_by_name[name] = ids

    fix_map = {}
    def _acc(node_ids, dofs):
        for n in node_ids:
            tg = int(n) + 1
            cur = fix_map.setdefault(tg, [0, 0, 0])
            for i, d in enumerate(dofs):
                if d:
                    cur[i] = 1
    _acc(nsets["BASE"], (1, 1, 1))
    _acc(nsets.get("SIDE_XMIN", []), (1, 0, 0))
    _acc(nsets.get("SIDE_XMAX", []), (1, 0, 0))
    _acc(nsets.get("SIDE_YMIN", []), (0, 1, 0))
    _acc(nsets.get("SIDE_YMAX", []), (0, 1, 0))
    for tg, dofs in fix_map.items():
        ops.fix(tg, *dofs)

    ops.updateMaterialStage('-material', mat_tag["SOIL_dat_yeu"], '-stage', 1)

    node_area = _node_tributary_area(MSH, 1, ("TOP_SOIL", "TOP_COLUMN"))
    top_idx = sorted(node_area.keys())

    col_node_idx = np.unique(elements[elsets["CDM_COLUMN"]].ravel())
    pts_col = points[col_node_idx]
    centers = np.array(column_centers(params))
    d2 = ((pts_col[:, None, 0] - centers[None, :, 0]) ** 2
          + (pts_col[:, None, 1] - centers[None, :, 1]) ** 2)
    nearest = d2.argmin(axis=1)
    node_row_x = centers[nearest, 0]
    row_nodes = col_node_idx[np.abs(node_row_x - 0.0) < 1e-3]

    H_col = params.column.z_top - params.column.z_bot
    force_total = P_kPa * D_m * H_col * 3
    force_per_node = force_total / len(row_nodes)

    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    n_loaded = 0
    for n in top_idx:
        pos_x = points[n][0]
        q_i = gd5.q_avg_kPa if pos_x >= 0 else 0.0
        if q_i > 0:
            F_i = q_i * node_area[n]
            ops.load(n + 1, 0.0, 0.0, -F_i)
            n_loaded += 1
    for n in row_nodes:
        ops.load(int(n) + 1, force_per_node, 0.0, 0.0)

    ops.system('UmfPack')
    ops.numberer('RCM')
    ops.constraints('Plain')
    ops.test('NormDispIncr', 1.0e-6, 40, 0)
    ops.algorithm('Newton')
    N_SUB = 20
    ops.integrator('LoadControl', 1.0 / N_SUB)
    ops.analysis('Static')

    row_head_node = row_nodes[np.argmin(np.abs(points[row_nodes, 2] - 0.8))]
    t0 = time.time()
    ok_final = 0
    for i in range(N_SUB):
        ok = ops.analyze(1)
        ok_final = ok
        if ok != 0:
            print(f"  [{tag}] KHONG HOI TU tai buoc {i+1}/{N_SUB}")
            break
    dt = time.time() - t0

    U = np.zeros((len(points), 3))
    for i in range(len(points)):
        U[i] = ops.nodeDisp(i + 1)
    ux_head = U[row_head_node, 0]
    print(f"[{tag}] P={P_kPa:.1f}kPa  SOLVED {dt:.2f}s (ok={ok_final})  Ux_dinh={ux_head*100:.2f}cm")

    return dict(points=points, elements=elements, elsets=elsets, U=U,
                ux_head_cm=ux_head * 100, dt=dt, elem_id_by_name=elem_id_by_name,
                row_nodes=row_nodes)


if __name__ == "__main__":
    results = {}
    for ux_t, P in P_LIST.items():
        results[ux_t] = build_and_solve(P, f"Ux_target={ux_t}cm")

    print("\n=== TONG HOP OpenSeesPy (tuan tu) ===")
    for ux_t in P_LIST:
        print(f"Ux_target={ux_t}cm: Ux_OpenSeesPy={results[ux_t]['ux_head_cm']:.2f}cm  "
              f"thoi_gian={results[ux_t]['dt']:.2f}s")

    import pickle
    with open(OUT / "openseespy_scenario35_results.pkl", "wb") as f:
        pickle.dump({k: {kk: vv for kk, vv in v.items() if kk != 'elements'} for k, v in results.items()}, f)
    # luu elements + points 1 lan (giong nhau moi lan chay, khong doi theo P)
    np.savez(OUT / "openseespy_scenario35_mesh.npz",
             points=results[80]['points'], elements=results[80]['elements'])
    print("Da luu scratch/openseespy_scenario35_results.pkl + mesh.npz")
