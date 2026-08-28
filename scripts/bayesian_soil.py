import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pymc as pm
import numpy as np
import arviz as az
import matplotlib.pyplot as plt
import pandas as pd

import sqlite3

# Artifact dir (to save plots)
artifact_dir = r"C:\Users\TEMP.PNBAYBIMGIS.004\.gemini\antigravity-ide\brain\290a4454-77ed-4ab5-b447-a7bd1cce423c\scratch"
os.makedirs(artifact_dir, exist_ok=True)

# 1. Dữ liệu thực tế từ SQLite data/TTHC.sqlite (Lớp đất yếu - sét/bụi dẻo/mềm)
db_path = r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\data\TTHC.sqlite"
conn = sqlite3.connect(db_path)
query = """
    SELECT c_kPa, phi_deg 
    FROM lab_tests 
    WHERE c_kPa IS NOT NULL 
      AND phi_deg IS NOT NULL 
      AND (description_vi LIKE '%dẻo%' OR description_vi LIKE '%mềm%' OR description_vi LIKE '%bùn%')
      AND c_kPa < 30
"""
df_lab = pd.read_sql_query(query, conn)
conn.close()

c_data = df_lab['c_kPa'].values
phi_data = df_lab['phi_deg'].values
n_samples = len(c_data)

c_mean_obs = np.mean(c_data)
phi_mean_obs = np.mean(phi_data)

print(f"Bắt đầu chạy mô hình phân tích Bayes cho tập dữ liệu thực tế (n={n_samples})")
print(f"Giá trị trung bình mẫu thực tế: c = {c_mean_obs:.2f} kPa, phi = {phi_mean_obs:.2f} độ")


# 2. Xây dựng mô hình Bayes với PyMC
with pm.Model() as soil_model:
    # 2.1 Priors (Niềm tin ban đầu - dựa vào preset data/soil_presets.json)
    # Khoảng giá trị cho c: [3, 8] theo preset, ta dùng HalfNormal hoặc TruncatedNormal mở rộng
    mu_c = pm.HalfNormal("mu_c", sigma=15) 
    sigma_c = pm.Exponential("sigma_c", 1.0)
    
    # Khoảng giá trị cho phi
    mu_phi = pm.HalfNormal("mu_phi", sigma=30)
    sigma_phi = pm.Exponential("sigma_phi", 1.0)
    
    # 2.2 Likelihood (Quan sát dữ liệu)
    c_obs = pm.Normal("c_obs", mu=mu_c, sigma=sigma_c, observed=c_data)
    phi_obs = pm.Normal("phi_obs", mu=mu_phi, sigma=sigma_phi, observed=phi_data)
    
    # 2.3 Lấy mẫu (MCMC)
    trace = pm.sample(draws=2000, tune=1000, chains=4, return_inferencedata=True, cores=1, progressbar=False)

# 3. Phân tích kết quả
print("\n--- KẾT QUẢ MCMC ---")
summary = az.summary(trace, round_to=3)
print(summary)

# Trích xuất phân phối hậu nghiệm của mu_c và mu_phi
posterior_c = trace.posterior["mu_c"].values.flatten()
posterior_phi = trace.posterior["mu_phi"].values.flatten()

# Tính giá trị đặc trưng (Characteristic Value) - Phân vị 5% (5th percentile) theo Eurocode 7
c_characteristic = np.percentile(posterior_c, 5)
phi_characteristic = np.percentile(posterior_phi, 5)

print("\n--- GIÁ TRỊ THIẾT KẾ CHO TÍNH TOÁN KÈ (Phân vị 5%) ---")
print(f"Lực dính c (design): {c_characteristic:.2f} kPa (Mean mẫu: {c_mean_obs:.2f})")
print(f"Góc ma sát phi (design): {phi_characteristic:.2f} độ (Mean mẫu: {phi_mean_obs:.2f})")

# 4. Xuất biểu đồ
plt.style.use('default')

# Biểu đồ phân phối hậu nghiệm
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
az.plot_posterior(trace, var_names=["mu_c"], ax=axes[0], kind='kde', hdi_prob=0.95, textsize=12)
axes[0].set_title(f"Phân phối hậu nghiệm của Lực dính c\nGiá trị thiết kế (5%): {c_characteristic:.2f} kPa", color='blue')
axes[0].axvline(c_characteristic, color='red', linestyle='--', label='5th percentile (Design)')
axes[0].legend()

az.plot_posterior(trace, var_names=["mu_phi"], ax=axes[1], kind='kde', hdi_prob=0.95, textsize=12)
axes[1].set_title(f"Phân phối hậu nghiệm của Góc ma sát phi\nGiá trị thiết kế (5%): {phi_characteristic:.2f}°", color='blue')
axes[1].axvline(phi_characteristic, color='red', linestyle='--', label='5th percentile (Design)')
axes[1].legend()

plt.tight_layout()
out_path_posterior = os.path.join(artifact_dir, "soil_posterior.png")
plt.savefig(out_path_posterior, dpi=150)
plt.close(fig)

# Biểu đồ Trace (kiểm tra sự hội tụ)
fig_trace = az.plot_trace(trace, var_names=["mu_c", "mu_phi"])
out_path_trace = os.path.join(artifact_dir, "soil_trace.png")
plt.savefig(out_path_trace, dpi=150)
plt.close(fig_trace.ravel()[0].figure)

print(f"\nĐã xuất biểu đồ tới: {out_path_posterior}")

# Ghi lại kết quả vắn tắt
with open(os.path.join(artifact_dir, "bayesian_results.txt"), "w", encoding="utf-8") as f:
    f.write(f"Kết quả phân tích Bayes cho Lớp 1 sét mềm:\n")
    f.write(f" - Giá trị trung bình mẫu (n={n_samples}): c = {c_mean_obs} kPa, phi = {phi_mean_obs} độ\n")
    f.write(f" - Giá trị thiết kế (5% HDI): c_design = {c_characteristic:.2f} kPa, phi_design = {phi_characteristic:.2f} độ\n")
