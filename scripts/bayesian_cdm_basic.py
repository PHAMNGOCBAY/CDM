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
from numpyro.infer import MCMC, NUTS

numpyro.set_host_device_count(1)

DB_PATH = 'data/TTHC.sqlite'
ARTIFACT_DIR = r'C:\Users\TEMP.PNBAYBIMGIS.004\.gemini\antigravity-ide\brain\80c59965-b7c0-4963-8070-f72ffeed114c\scratch'

def normal_model(data=None, is_e50=False):
    # Basic Normal model
    if is_e50:
        mu = numpyro.sample('mu', dist.Normal(100, 100))
        sigma = numpyro.sample('sigma', dist.HalfNormal(50))
    else:
        mu = numpyro.sample('mu', dist.Normal(1000, 1000))
        sigma = numpyro.sample('sigma', dist.HalfNormal(500))
    numpyro.sample('obs', dist.Normal(mu, sigma), obs=data)

def run_analysis():
    conn = sqlite3.connect(DB_PATH)
    
    # 7-day data
    query7 = "SELECT dosage_kgm3 as dosage, qu_R7_kPa as qu, E50_R7_MPa as e50 FROM cdm_tests WHERE qu_R7_kPa IS NOT NULL OR E50_R7_MPa IS NOT NULL"
    df7 = pd.read_sql_query(query7, conn)
    
    # 28-day data
    query28 = "SELECT dosage_kgm3 as dosage, qu_kPa as qu, e50_MPa as e50 FROM cdm_specimens WHERE qu_kPa IS NOT NULL OR e50_MPa IS NOT NULL"
    df28 = pd.read_sql_query(query28, conn)
    
    conn.close()
    
    results = []
    samples_dict = {}
    
    for param in ['qu', 'e50']:
        for age, df in [(7, df7), (28, df28)]:
            dosages = df['dosage'].dropna().unique()
            dosages.sort()
            
            for dosage in dosages:
                df_dos = df[df['dosage'] == dosage].copy()
                df_dos = df_dos.dropna(subset=[param])
                data_vals = jnp.array(df_dos[param].values)
                n_samples = len(data_vals)
                
                if n_samples < 2:
                    continue
                    
                print(f"--- Running NumPyro for {param}, Age={age} days, Dosage={dosage} (n={n_samples}) ---")
                
                rng_key = jax.random.PRNGKey(42)
                def model_wrapper(data=None):
                    normal_model(data, is_e50=(param == 'e50'))
                
                kernel = NUTS(model_wrapper)
                mcmc = MCMC(kernel, num_warmup=1000, num_samples=3000, num_chains=1)
                mcmc.run(rng_key, data=data_vals)
                
                posterior = mcmc.get_samples()
                mu_samples = posterior['mu']
                samples_dict[(param, age, dosage)] = mu_samples
                
                p_mean = float(jnp.mean(mu_samples))
                p_des = float(jnp.percentile(mu_samples, 5.0))
                p_des_10 = float(jnp.percentile(mu_samples, 10.0))
                
                # Traditional stats
                t_mean = float(np.mean(data_vals))
                t_std = float(np.std(data_vals, ddof=1)) if n_samples > 1 else 0.0
                t_des = t_mean - 1.645 * t_std
                t_des_10 = t_mean - 1.282 * t_std
                
                results.append({
                    'Param': param, 'Age': age, 'Dosage': dosage, 'n': n_samples,
                    'Mean_Trad': t_mean, 'Des_Trad': t_des, 'Des_10_Trad': t_des_10,
                    'Mean_Bayes': p_mean, 'Des_Bayes': p_des, 'Des_10_Bayes': p_des_10
                })
                
                plt.figure(figsize=(8, 5))
                sns.histplot(mu_samples, kde=True, color='purple' if param == 'qu' else 'green', stat='density')
                plt.axvline(p_mean, color='black', linestyle='--', label=f'Mean (Bayes) = {p_mean:.1f}')
                plt.axvline(p_des, color='red', linestyle='-', label=f'Design 5% (Bayes) = {p_des:.1f}')
                plt.axvline(p_des_10, color='orange', linestyle='-.', label=f'Design 10% (Bayes) = {p_des_10:.1f}')
                plt.axvline(t_mean, color='blue', linestyle=':', label=f'Mean (Trad) = {t_mean:.1f}')
                plt.title(f'Posterior {param} (Age = {age} days, Dosage = {dosage})')
                unit = 'kPa' if param == 'qu' else 'MPa'
                plt.xlabel(f'{param} ({unit})')
                plt.legend()
                
                out_img = os.path.join(ARTIFACT_DIR, f"cdm_posterior_{param}_{age}d_{int(dosage)}.png")
                plt.savefig(out_img, dpi=100)
                plt.close()

    # Create Comparison Plots
    for param in ['qu', 'e50']:
        for age in [7, 28]:
            plt.figure(figsize=(10, 6))
            colors = {220.0: 'blue', 240.0: 'orange', 260.0: 'green'}
            for dosage in [220.0, 240.0, 260.0]:
                if (param, age, dosage) in samples_dict:
                    sns.kdeplot(samples_dict[(param, age, dosage)], fill=True, alpha=0.4, 
                                color=colors[dosage], label=f'Dosage {int(dosage)} kg/m3')
            plt.title(f'So sánh Hàm lượng Xi măng - Phân phối {param} tại {age} ngày')
            unit = 'kPa' if param == 'qu' else 'MPa'
            plt.xlabel(f'{param} ({unit})')
            plt.ylabel('Mật độ (Density)')
            plt.legend()
            out_img = os.path.join(ARTIFACT_DIR, f"cdm_comparison_{param}_{age}d.png")
            plt.savefig(out_img, dpi=100)
            plt.close()

    # Generate Markdown Summary
    md_out = r'C:\Users\TEMP.PNBAYBIMGIS.004\.gemini\antigravity-ide\brain\80c59965-b7c0-4963-8070-f72ffeed114c\cdm_basic_summary.md'
    with open(md_out, 'w', encoding='utf-8') as f:
        f.write("# Phân tích NumPyro độc lập cho mẫu 7 ngày và 28 ngày (qu & E50)\n\n")
        f.write("> **Bảng so sánh Truyền thống vs Bayesian:** Bảng dưới đây đối chiếu giá trị trung bình cộng (Mean Truyền thống) và công thức tính 5%, 10% so với phân phối hậu nghiệm Bayesian.\n\n")
        f.write("| Chỉ tiêu | Tuổi (ngày) | Hàm lượng | Số mẫu (n) | Mean (TT) | 5% (TT) | 10% (TT) | Mean (Bayes) | 5% (Bayes) | 10% (Bayes) |\n")
        f.write("|----------|-------------|-----------|------------|-----------|---------|----------|--------------|------------|-------------|\n")
        for res in results:
            f.write(f"| {res['Param']} | {res['Age']} | {res['Dosage']} | {res['n']} | {res['Mean_Trad']:.1f} | {res['Des_Trad']:.1f} | {res['Des_10_Trad']:.1f} | {res['Mean_Bayes']:.1f} | {res['Des_Bayes']:.1f} | {res['Des_10_Bayes']:.1f} |\n")
        
        f.write("\n## Biểu đồ So sánh Hàm lượng Xi măng\n")
        f.write("Các biểu đồ dưới đây đặt chồng phân phối Hậu nghiệm của 3 cấp hàm lượng xi măng (220, 240, 260) lên cùng một trục đồ thị để dễ dàng nhận thấy sự dịch chuyển cường độ sang phải khi tăng hàm lượng xi măng.\n\n")
        f.write("### So sánh Cường độ nén qu\n")
        
        def format_img(name):
            return os.path.join(ARTIFACT_DIR, name).replace("\\", "/")
            
        f.write(f"![So sánh qu 28 ngày]({format_img('cdm_comparison_qu_28d.png')})\n\n")
        f.write(f"![So sánh qu 7 ngày]({format_img('cdm_comparison_qu_7d.png')})\n\n")
        
        f.write("### So sánh Mô-đun biến dạng E50\n")
        f.write(f"![So sánh E50 28 ngày]({format_img('cdm_comparison_e50_28d.png')})\n\n")
        f.write(f"![So sánh E50 7 ngày]({format_img('cdm_comparison_e50_7d.png')})\n\n")

        f.write("\n## Biểu đồ Hậu nghiệm Chi tiết (Từng tổ mẫu)\n")
        for res in results:
            param = res['Param']
            age = res['Age']
            dosage = int(res['Dosage'])
            f.write(f"### {param} - Tuổi {age} ngày - Hàm lượng {dosage} kg/m3\n")
            img_name = f"cdm_posterior_{param}_{age}d_{dosage}.png"
            f.write(f"![Posterior]({format_img(img_name)})\n\n")

if __name__ == '__main__':
    run_analysis()
