import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

import jax
import jax.numpy as jnp
import numpyro
import numpyro.distributions as dist
from numpyro.infer import MCMC, NUTS, Predictive

numpyro.set_host_device_count(1)

DB_PATH = 'data/TTHC.sqlite'
ARTIFACT_DIR = r'C:\Users\TEMP.PNBAYBIMGIS.004\.gemini\antigravity-ide\brain\290a4454-77ed-4ab5-b447-a7bd1cce423c'

def get_data():
    conn = sqlite3.connect(DB_PATH)
    
    # 7-day data
    query7 = "SELECT dosage_kgm3 as dosage, qu_R7_kPa as qu, 7 as age FROM cdm_tests WHERE qu_R7_kPa IS NOT NULL"
    df7 = pd.read_sql_query(query7, conn)
    
    # 28-day data (from individual specimens)
    query28 = "SELECT dosage_kgm3 as dosage, qu_kPa as qu, 28 as age FROM cdm_specimens WHERE qu_kPa IS NOT NULL"
    df28 = pd.read_sql_query(query28, conn)
    
    conn.close()
    
    # Combine
    df = pd.concat([df7, df28], ignore_index=True)
    return df

def log_growth_model(age, qu=None):
    # qu(t) = a * ln(t) + b
    # Priors
    a = numpyro.sample('a', dist.Normal(200, 200))
    b = numpyro.sample('b', dist.Normal(500, 500))
    sigma = numpyro.sample('sigma', dist.HalfNormal(200))
    
    mu = a * jnp.log(age) + b
    numpyro.sample('obs', dist.Normal(mu, sigma), obs=qu)

def run_analysis():
    df = get_data()
    dosages = df['dosage'].dropna().unique()
    dosages.sort()
    
    results = []
    
    for dosage in dosages:
        print(f"\n--- Analyzing Dosage: {dosage} kg/m3 ---")
        df_dos = df[df['dosage'] == dosage].copy()
        
        if len(df_dos) < 2:
            print("Not enough data points.")
            continue
            
        ages = jnp.array(df_dos['age'].values)
        qus = jnp.array(df_dos['qu'].values)
        
        # Run NUTS
        rng_key = jax.random.PRNGKey(0)
        kernel = NUTS(log_growth_model)
        mcmc = MCMC(kernel, num_warmup=1000, num_samples=2000, num_chains=1)
        mcmc.run(rng_key, age=ages, qu=qus)
        
        mcmc.print_summary()
        samples = mcmc.get_samples()
        
        # Prediction at t=1..365
        t_pred = jnp.linspace(1, 365, 365)
        predictive = Predictive(log_growth_model, samples)
        pred_samples = predictive(jax.random.PRNGKey(1), age=t_pred)['obs']
        
        # Mean and percentiles
        qu_mean = jnp.mean(pred_samples, axis=0)
        qu_hpdi = jnp.percentile(pred_samples, jnp.array([2.5, 97.5]), axis=0) # 95% Confidence interval
        qu_design = jnp.percentile(pred_samples, 5.0, axis=0) # 5% lower bound for Design
        
        # Extracted 365-day values
        q365_mean = float(qu_mean[-1])
        q365_design = float(qu_design[-1])
        
        results.append({
            'Dosage': dosage,
            'qu_365_Mean': q365_mean,
            'qu_365_Design': q365_design,
            'Penalty(%)': (q365_design - q365_mean) / q365_mean * 100
        })
        
        # Plotting
        plt.figure(figsize=(10, 6))
        
        # Plot uncertainty band
        plt.fill_between(t_pred, qu_hpdi[0], qu_hpdi[1], color='blue', alpha=0.2, label='95% HDI')
        plt.plot(t_pred, qu_mean, color='blue', linewidth=2, label='Mean Prediction')
        plt.plot(t_pred, qu_design, color='red', linestyle='--', linewidth=2, label='Design Value (5%)')
        
        # Scatter actual data
        plt.scatter(df_dos['age'], df_dos['qu'], color='black', zorder=5, label='Actual Data (R7, R28)')
        
        plt.title(f"CDM Strength Development (Dosage = {dosage} kg/m3)")
        plt.xlabel("Age (days)")
        plt.ylabel("qu (kPa)")
        plt.xlim(0, 365)
        plt.grid(True, alpha=0.5)
        plt.legend()
        
        out_img = os.path.join(ARTIFACT_DIR, f"cdm_extrapolation_{int(dosage)}.png")
        plt.tight_layout()
        plt.savefig(out_img, dpi=100)
        plt.close()
        print(f"Saved plot: {out_img}")
        
    # Write summary markdown
    md_out = os.path.join(ARTIFACT_DIR, "cdm_bayesian_summary.md")
    with open(md_out, 'w', encoding='utf-8') as f:
        f.write("# Dự báo cường độ Xi măng đất ở 365 ngày\n\n")
        f.write("| Hàm lượng (kg/m3) | qu 365 (Mean) | qu 365 (Design 5%) | Mức độ phạt (Penalty) |\n")
        f.write("|-------------------|---------------|--------------------|-----------------------|\n")
        for res in results:
            f.write(f"| {res['Dosage']} | {res['qu_365_Mean']:.1f} | {res['qu_365_Design']:.1f} | {res['Penalty(%)']:.1f}% |\n")
        
        f.write("\n## Biểu đồ phát triển cường độ\n")
        for res in results:
            d = int(res["Dosage"])
            img_path = os.path.join(ARTIFACT_DIR, f"cdm_extrapolation_{d}.png").replace("\\\\", "/").replace("\\", "/")
            f.write(f"![Dosage {d}](file:///{img_path})\n")
    print(f"Saved markdown summary: {md_out}")

if __name__ == '__main__':
    run_analysis()
