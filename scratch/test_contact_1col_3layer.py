"""Buoc 2 ke hoach co lap contact CalculiX: 1 COC (thay vi 9) nhung GIU NGUYEN 3
lop dat THAT (dat_dap/dat_yeu/lop_cung, dung z-ranh gioi voi mo hinh KE day du) va
GIU NGUYEN chuoi tai GD2..GD5 that (params.stages tu params_io) — de co lap xem
phan ky quan sat o mo hinh 9 coc co xay ra CHI VOI 1 coc hay khong (loai tru gia
thuyet "tuong tac giua 9 coc" khoi nguyen nhan).

Mo hinh nho 1 lop dong nhat TRUOC DAY da hoi tu thanh cong (xem
.claude/commands/cdm3d-contact.md) — khac biet DUY NHAT o day la giu du 3 lop
that (co ranh gioi lop giao mat tru SOIL_INNER).

KHONG sua contact_geometry.py / contact_ccx_input.py o buoc nay — chi doi
ModelParams dau vao (n_x=n_y=1, domain_buffer_m thu nho de giai nhanh).
"""
import sys
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

from cdm3d import params_io, run_ccx
from cdm3d.contact_geometry import mesh_soil_with_holes, mesh_columns_standalone
from cdm3d.contact_ccx_input import write_ccx_inp_contact, alpha_equivalent_mu

params = params_io.build_default_params("KE")
params.column.n_x = 1
params.column.n_y = 1
params.domain_buffer_m = 3.0  # thu nho de giai nhanh, van giu du 3 lop that

out_dir = ROOT / "scratch"
soil_msh = out_dir / "test_1col3layer_soil.msh"
col_msh = out_dir / "test_1col3layer_col.msh"
inp_path = out_dir / "test_1col3layer.inp"

print("--- Mesh dat (co lo, 3 lop that) ---")
soil_stats = mesh_soil_with_holes(params, soil_msh)
print(soil_stats)

print("--- Mesh coc (doc lap) ---")
col_stats = mesh_columns_standalone(params, col_msh)
print(col_stats)

# mu tu alpha-Tomlinson (giong huong dan .claude/commands/cdm3d-contact.md muc 3,
# KHONG dung gia tri tuy y) — z_ref lay giua lop dat yeu de dai dien
z_ref = (params.soil_layers[1].z_top + params.soil_layers[1].z_bot) / 2.0
su_layer_yeu = params.soil_layers[1].E_kPa / 250.0  # Es = 250*Su (Mesri) — suy nguoc Su tu Es da co
mu_info = alpha_equivalent_mu(su_layer_yeu, params, z_ref)
print("mu_equiv info:", mu_info)
mu = mu_info["mu_equiv"]

print(f"--- Ghi .inp (mu={mu:.4f}) ---")
write_ccx_inp_contact(soil_msh, col_msh, inp_path, params, mu=mu, job_name="test_1col3layer")
print("wrote:", inp_path)

print("--- Giai CalculiX (co the mat vai phut, theo doi log) ---")
try:
    frd = run_ccx.solve(inp_path, timeout_s=1800)
    print("SOLVED OK ->", frd)
except Exception as e:
    print(f"KHONG HOI TU / LOI: {e}")
    raise
