import sqlite3
import pandas as pd
import pymc as pm
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import time
import os
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Output dir
ARTIFACT_DIR = r"C:\Users\TEMP.PNBAYBIMGIS.004\.gemini\antigravity-ide\brain\290a4454-77ed-4ab5-b447-a7bd1cce423c\scratch"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

# 1. Fetch data
conn = sqlite3.connect("data/TTHC.sqlite")
query = """
    SELECT l.symbol, t.c_kPa, t.phi_deg
    FROM lab_tests t
    JOIN layers l ON t.borehole_id = l.borehole_id
    AND ((t.depth_from_m + t.depth_to_m)/2.0 BETWEEN l.depth_top_m AND l.depth_bot_m)
    WHERE l.symbol = '1'
"""
df = pd.read_sql_query(query, conn).dropna(subset=['c_kPa', 'phi_deg'])
conn.close()

print(f"Loaded {len(df)} samples for Layer 1")

# Normalize data for stable sampling
c_data = df['c_kPa'].values
phi_data = df['phi_deg'].values

def create_model():
    with pm.Model() as model:
        mu_c = pm.HalfNormal('mu_c', sigma=50)
        sigma_c = pm.HalfNormal('sigma_c', sigma=20)
        c_obs = pm.Normal('c_obs', mu=mu_c, sigma=sigma_c, observed=c_data)
        
        mu_phi = pm.HalfNormal('mu_phi', sigma=30)
        sigma_phi = pm.HalfNormal('sigma_phi', sigma=10)
        phi_obs = pm.Normal('phi_obs', mu=mu_phi, sigma=sigma_phi, observed=phi_data)
    return model

model = create_model()

def main():
    # 2. Sample using standard PyMC
    print("\n--- Bắt đầu lấy mẫu bằng PyMC gốc ---")
    start_time_pymc = time.time()
    with model:
        trace_pymc = pm.sample(draws=2000, tune=1000, chains=4, return_inferencedata=True, progressbar=False)
    time_pymc = time.time() - start_time_pymc
    print(f"Hoàn thành PyMC gốc trong: {time_pymc:.2f} giây")

    # 3. Sample using NumPyro backend
    print("\n--- Bắt đầu lấy mẫu bằng NumPyro ---")
    start_time_numpyro = time.time()
    with model:
        trace_numpyro = pm.sample(draws=2000, tune=1000, chains=4, nuts_sampler="numpyro", return_inferencedata=True, progressbar=False)
    time_numpyro = time.time() - start_time_numpyro
    print(f"Hoàn thành NumPyro trong: {time_numpyro:.2f} giây")

    # 4. Plot Comparison
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(f"So sánh PyMC gốc vs NumPyro (Lớp 1, N={len(df)})", fontsize=16)

    # Extract posteriors
    c_pymc = trace_pymc.posterior['mu_c'].values.flatten()
    c_numpyro = trace_numpyro.posterior['mu_c'].values.flatten()

    phi_pymc = trace_pymc.posterior['mu_phi'].values.flatten()
    phi_numpyro = trace_numpyro.posterior['mu_phi'].values.flatten()

    # Plot c
    sns.kdeplot(c_pymc, ax=axes[0], color='blue', label=f'PyMC (Time: {time_pymc:.2f}s)')
    sns.kdeplot(c_numpyro, ax=axes[0], color='orange', linestyle='--', label=f'NumPyro (Time: {time_numpyro:.2f}s)')
    axes[0].set_title("Phân phối hậu nghiệm Lực dính (c_kPa)")
    axes[0].set_xlabel("c (kPa)")
    axes[0].legend()

    # Plot phi
    sns.kdeplot(phi_pymc, ax=axes[1], color='blue', label='PyMC')
    sns.kdeplot(phi_numpyro, ax=axes[1], color='orange', linestyle='--', label='NumPyro')
    axes[1].set_title("Phân phối hậu nghiệm Góc ma sát (phi_deg)")
    axes[1].set_xlabel("phi (deg)")
    axes[1].legend()

    plt.tight_layout()
    out_path = os.path.join(ARTIFACT_DIR, "pymc_vs_numpyro.png")
    plt.savefig(out_path, dpi=300)
    print(f"\nĐã lưu biểu đồ so sánh tại: {out_path}")

if __name__ == '__main__':
    main()

