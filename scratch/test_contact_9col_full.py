"""Test contact CalculiX quy mo DAY DU (9 coc, 3 x 3, params KE that, domain_buffer
mac dinh 3.6m, chuoi tai GD2..GD5 that) — SAU KHI sua loi phan loai dia artifact
trong contact_geometry._tag_soil_boundary() (xem .claude/commands/cdm3d-contact.md
cap nhat 2026-08-27). 2 lan thu TRUOC KHI sua deu PHAN KY ("too many cutbacks").

KHONG doi n_x/n_y — dung dung params_io.build_default_params("KE") nguyen ban
(production that).
"""
import sys
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

from cdm3d import params_io, run_ccx
from cdm3d.contact_geometry import mesh_soil_with_holes, mesh_columns_standalone
from cdm3d.contact_ccx_input import write_ccx_inp_contact, alpha_equivalent_mu

params = params_io.build_default_params("KE")
print(f"n_x={params.column.n_x}, n_y={params.column.n_y}, domain_buffer_m={params.domain_buffer_m}")

out_dir = ROOT / "scratch"
soil_msh = out_dir / "test_9col_soil.msh"
col_msh = out_dir / "test_9col_col.msh"
inp_path = out_dir / "test_9col_full.inp"

print("--- Mesh dat (co 9 lo, 3 lop that) ---")
soil_stats = mesh_soil_with_holes(params, soil_msh)
print(soil_stats)

print("--- Mesh 9 coc (doc lap, chung 1 phien) ---")
col_stats = mesh_columns_standalone(params, col_msh)
print(col_stats)

z_ref = (params.soil_layers[1].z_top + params.soil_layers[1].z_bot) / 2.0
su_layer_yeu = params.soil_layers[1].E_kPa / 250.0
mu_info = alpha_equivalent_mu(su_layer_yeu, params, z_ref)
mu = mu_info["mu_equiv"]
print("mu_equiv info:", mu_info)

print(f"--- Ghi .inp (mu={mu:.4f}) ---")
write_ccx_inp_contact(soil_msh, col_msh, inp_path, params, mu=mu, job_name="test_9col_full")
print("wrote:", inp_path)

print("--- Giai CalculiX (mo hinh day du, co the mat nhieu thoi gian hon 1-coc) ---")
try:
    frd = run_ccx.solve(inp_path, timeout_s=3600)
    print("SOLVED OK ->", frd)
except Exception as e:
    print(f"KHONG HOI TU / LOI: {e}")
    raise
