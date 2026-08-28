"""Co lap bien so: dung LAI CHINH XAC luoi 1-coc-3-lop that vua tao boi
test_contact_1col_3layer.py (khong mesh lai), nhung doi TAI DUNG SURCHARGE ->
TAI NGANG DIEM tai COL_TOP (giong het kieu tai da THANH CONG tren mo hinh nho
1-lop dong nhat truoc day, xem .claude/commands/cdm3d-contact.md).

Muc dich: neu HOI TU voi tai ngang nhung PHAN KY voi tai dung (nhu
test_contact_1col_3layer.py) tren CUNG 1 luoi 3 lop — xac nhan nguyen nhan la
LOAI TAI/huong tai (thieu ung suat nen ban dau duoi tai dung khi self-weight tat),
KHONG phai do 3 lop/seam ranh gioi lop.
"""
import sys
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

from cdm3d import params_io, run_ccx
from cdm3d.contact_ccx_input import write_ccx_inp_contact, alpha_equivalent_mu, _read_mesh_groups
from cdm3d.types import LoadStage

params = params_io.build_default_params("KE")
params.column.n_x = 1
params.column.n_y = 1
params.domain_buffer_m = 3.0

out_dir = ROOT / "scratch"
soil_msh = out_dir / "test_1col3layer_soil.msh"  # DUNG LAI, da tao boi script truoc
col_msh = out_dir / "test_1col3layer_col.msh"
inp_path = out_dir / "test_1col3layer_lateral.inp"

if not soil_msh.exists() or not col_msh.exists():
    raise FileNotFoundError("Chay scratch/test_contact_1col_3layer.py TRUOC de tao luoi dung chung.")

z_ref = (params.soil_layers[1].z_top + params.soil_layers[1].z_bot) / 2.0
su_layer_yeu = params.soil_layers[1].E_kPa / 250.0
mu_info = alpha_equivalent_mu(su_layer_yeu, params, z_ref)
mu = mu_info["mu_equiv"]
print("mu_equiv info:", mu_info)

# Stage "dummy" q=0 -> write_ccx_inp_contact van ghi 1 *STEP RONG (khong *CLOAD)
# vi q_avg_kPa=0 (xem contact_ccx_input.py dong 290: "if stage.q_avg_kPa > 0").
# QUAN TRONG (phat hien lan chay truoc): step RONG nay tu no da KHONG HOI TU vi
# average_force~0 (khong self-weight, khong tai) -> tieu chi hoi tu TUONG DOI
# (residual/average_force) suy bien khi mau so gan 0 — day la LOI GIA (do chinh
# ban script nay tao ra), khong lien quan gia thuyet dang test. PHAI XOA step
# rong nay khoi file truoc khi them step tai ngang, KHONG duoc de no chay.
params.stages = [LoadStage(name="dummy_zero", q_avg_kPa=0.0, eccentricity_m=0.0)]
write_ccx_inp_contact(soil_msh, col_msh, inp_path, params, mu=mu)

_DUMMY_STEP_BLOCK = "*STEP, NLGEOM\n*STATIC\n*NODE FILE\nU\n*EL FILE\nS, E\n*END STEP\n"
text = inp_path.read_text(encoding="ascii", errors="replace")
if _DUMMY_STEP_BLOCK not in text:
    raise RuntimeError("Khong tim thay dung block step rong de xoa — kiem tra lai "
                        "dinh dang *STEP do write_ccx_inp_contact sinh ra (co the da doi).")
text = text.replace(_DUMMY_STEP_BLOCK, "")
inp_path.write_text(text, encoding="ascii", errors="replace")
print("Da xoa step rong (dummy_zero) khoi .inp truoc khi them step tai ngang.")

# --- Them STEP rieng: tai ngang diem 50kN tai COL_TOP (giong test 1-lop da hoi tu) ---
soil = _read_mesh_groups(soil_msh)
col = _read_mesh_groups(col_msh)
n_soil = len(soil["points"])

top_col_nodes_1idx = sorted(int(n) + 1 + n_soil for n in set(col["tri"]["COL_TOP"].ravel().tolist()))
F_total = 50.0
F_per_node = F_total / len(top_col_nodes_1idx)
print(f"So nut COL_TOP: {len(top_col_nodes_1idx)}, F_per_node={F_per_node:.4f} kN")

lateral_step_lines = ["*STEP, NLGEOM", "*STATIC", "*CLOAD"]
for n in top_col_nodes_1idx:
    lateral_step_lines.append(f"{n}, 1, {F_per_node:.6f}")
lateral_step_lines += ["*NODE FILE", "U", "*EL FILE", "S, E", "*END STEP"]

with open(inp_path, "a", encoding="ascii", errors="replace") as f:
    f.write("\n".join(lateral_step_lines) + "\n")

print("wrote (co them step tai ngang):", inp_path)

print("--- Giai CalculiX ---")
try:
    frd = run_ccx.solve(inp_path, timeout_s=1800)
    print("SOLVED OK ->", frd)
except Exception as e:
    print(f"KHONG HOI TU / LOI: {e}")
    raise
