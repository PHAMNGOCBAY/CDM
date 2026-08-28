"""Test CalculiX voi lop dat yeu dung *MOHR COULOMB (phi=psi=0 -> Tresca, c=Su
that tu VST) thay *ELASTIC thuan — LAN DAU trong du an (truoc day chi co dan
hoi tuyen tinh, xem ccx_input.py dong 25). Mo hinh NHO (1 coc) TRUOC de kiem
chung co che + hoi tu, truoc khi scale len 9 coc production.

Cu phap *MOHR COULOMB da tra cuu chinh thuc tu ccx_2.23.pdf muc 7.90-7.91
(khong doan) — xem docstring write_ccx_inp() moi trong ccx_input.py.
"""
import sys
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

import gmsh

from cdm3d import ccx_input, geometry, mesh_gmsh, params_io, run_ccx, postprocess

ZONE = "KE"
params = params_io.build_default_params(ZONE)
params.column.n_x = 1
params.column.n_y = 1
params_io.print_warnings(params)

layer_yeu = next(l for l in params.soil_layers if l.name == "dat_yeu")
Su_kPa, n_vst = params_io.query_su_vst_avg(ZONE, layer_yeu.z_top, layer_yeu.z_bot)
if Su_kPa is None:
    raise RuntimeError(f"Khong co du lieu VST that cho {ZONE}.")
print(f"Su that tu VST: {Su_kPa:.2f} kPa (n={n_vst}) -> dung lam cohesion Mohr-Coulomb")

out_dir = ROOT / "scratch"
msh_path = out_dir / "test_ccx_mc.msh"
gmsh.initialize()
gmsh.option.setNumber("General.Terminal", 0)
try:
    geometry.build_geometry(params)
    mesh_gmsh.generate_mesh(params, element_order=1)
    stats = mesh_gmsh.mesh_stats()
    print(f"mesh: {stats}")
    mesh_gmsh.export_mesh(msh_path)
finally:
    gmsh.finalize()

inp_path = out_dir / "test_ccx_mc_full.inp"
ccx_input.write_ccx_inp(
    msh_path, inp_path, params,
    mohr_coulomb={"SOIL_dat_yeu": {"c_kPa": Su_kPa, "phi_deg": 0.0, "psi_deg": 0.0}},
    # use_model_change=True (MAC DINH) — kich ban PRODUCTION day du: GD0(remove
    # cot)->GD1(add strain-free)->GD2..GD5, dung *DLOAD ap luc mat da sua.
    # Da xac nhan (2026-08-27) MODEL CHANGE KHONG phai nguyen nhan phan ky (test
    # truoc voi use_model_change=False van phan ky dung vi tri) — chay lai day
    # de xac nhan kich ban THAT khong co van de MOI phat sinh tu MODEL CHANGE.
)
print(f"wrote: {inp_path}")

import time
t0 = time.time()
frd_path = run_ccx.solve(inp_path, timeout_s=1800)
dt = time.time() - t0
print(f"SOLVED OK -> {frd_path}  (thoi gian: {dt:.2f}s)")

vtu_path = postprocess.convert_frd_to_vtu(frd_path)
import pyvista as pv
mesh = pv.read(vtu_path)
U = mesh["U"]
print(f"Ux max (toan mien): {U[:,0].max()*1000:.4f} mm")
print(f"Ux min (toan mien): {U[:,0].min()*1000:.4f} mm")
print(f"Uz max (lun, toan mien): {U[:,2].max()*1000:.4f} mm")
print(f"Uz min (lun, toan mien): {U[:,2].min()*1000:.4f} mm")
