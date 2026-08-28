import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import pymc as pm
import arviz as az
import matplotlib.pyplot as plt
import pytensor
import time

# Tắt trình biên dịch C++ để tránh lỗi g++ trên Windows
pytensor.config.cxx = ""
sys.stdout.reconfigure(encoding='utf-8')

# Cấu hình đường dẫn
db_path = r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\data\cdm_new.sqlite"
results_dir = r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\results"
images_dir = r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\images"
os.makedirs(results_dir, exist_ok=True)
os.makedirs(images_dir, exist_ok=True)

def main():
    print("Đang truy vấn dữ liệu từ CSDL...")
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM cdm_tests", conn)
    conn.close()

    # Chuẩn bị danh sách phân tích: Tổng hợp + Theo nhóm
    analysis_groups = [("Tổng thể", "Tất cả", df)]
    for (loai_xm, ham_luong), group in df.groupby(['loai_xi_mang', 'ham_luong']):
        analysis_groups.append((loai_xm, ham_luong, group))

    results = []

    print("Bắt đầu xử lý hàng loạt bằng PyMC + NumPyro...")
    for loai_xm, ham_luong, group in analysis_groups:
        n_samples = len(group)
        if n_samples < 5:
            print(f"Bỏ qua {loai_xm} - {ham_luong}kg/m3 (chỉ có {n_samples} mẫu).")
            continue
        
        print(f"\n--- Phân tích: {loai_xm} | Hàm lượng {ham_luong} kg/m3 (n={n_samples}) ---")
        
        qu_data = group['qu_kPa'].values
        e50_data = group['e50_MPa'].values
        
        qu_mean = np.mean(qu_data)
        e50_mean = np.mean(e50_data)
        
        # Thiết lập tham số lấy mẫu
        DRAWS = 2000
        TUNE = 1000
        CHAINS = 4 
        
        start_time = time.time()
        with pm.Model() as model:
            # Priors
            mu_qu = pm.HalfNormal("mu_qu", sigma=max(1000, qu_mean*3)) 
            sigma_qu = pm.Exponential("sigma_qu", 0.01)
            
            mu_e50 = pm.HalfNormal("mu_e50", sigma=max(100, e50_mean*3))
            sigma_e50 = pm.Exponential("sigma_e50", 0.1)
            
            # Likelihood
            qu_obs = pm.Normal("qu_obs", mu=mu_qu, sigma=sigma_qu, observed=qu_data)
            e50_obs = pm.Normal("e50_obs", mu=mu_e50, sigma=sigma_e50, observed=e50_data)
            
            # Lấy mẫu với NumPyro
            trace = pm.sample(
                draws=DRAWS, 
                tune=TUNE, 
                chains=CHAINS, 
                nuts_sampler="numpyro",
                progressbar=False
            )
        elapsed = time.time() - start_time
        print(f"  Hoàn thành lấy mẫu trong: {elapsed:.2f}s")
        
        # Trích xuất hậu nghiệm
        posterior_qu = trace.posterior["mu_qu"].values.flatten()
        posterior_e50 = trace.posterior["mu_e50"].values.flatten()
        
        qu_char_5 = np.percentile(posterior_qu, 5)
        e50_char_5 = np.percentile(posterior_e50, 5)
        
        # Plot qu
        plt.style.use('default')
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        
        az.plot_posterior(trace, var_names=["mu_qu"], ax=axes[0], kind='kde', hdi_prob=0.95, textsize=10)
        axes[0].set_title(f"qu (kPa)\n{loai_xm} - {ham_luong}kg/m3", color='blue')
        axes[0].axvline(qu_char_5, color='red', linestyle='--', label=f'5% Design ({qu_char_5:.1f})')
        axes[0].axvline(qu_mean, color='green', linestyle='-', label=f'Mean ({qu_mean:.1f})')
        axes[0].legend()
        
        # Plot e50
        az.plot_posterior(trace, var_names=["mu_e50"], ax=axes[1], kind='kde', hdi_prob=0.95, textsize=10)
        axes[1].set_title(f"E50 (MPa)\n{loai_xm} - {ham_luong}kg/m3", color='blue')
        axes[1].axvline(e50_char_5, color='red', linestyle='--', label=f'5% Design ({e50_char_5:.1f})')
        axes[1].axvline(e50_mean, color='green', linestyle='-', label=f'Mean ({e50_mean:.1f})')
        axes[1].legend()
        
        plt.tight_layout()
        safe_name = f"{loai_xm.replace(' ', '_').replace('(', '').replace(')', '')}_{str(ham_luong).replace(' ', '_')}_numpyro"
        plot_path = os.path.join(images_dir, f"posterior_cdm_{safe_name}.png")
        plt.savefig(plot_path, dpi=100)
        plt.close(fig)
        
        results.append({
            "Loại Xi Măng": loai_xm,
            "Hàm Lượng (kg/m3)": ham_luong,
            "Số mẫu (n)": n_samples,
            "qu Mean (kPa)": round(qu_mean, 1),
            "qu 5% Bayes (kPa)": round(qu_char_5, 1),
            "E50 Mean (MPa)": round(e50_mean, 1),
            "E50 5% Bayes (MPa)": round(e50_char_5, 1),
            "Thời gian lấy mẫu (s)": round(elapsed, 2)
        })

    # Tạo báo cáo Markdown
    df_res = pd.DataFrame(results)
    md_path = os.path.join(results_dir, "bayesian_cdm_numpyro_results.md")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Tổng hợp Giá trị Thiết kế Cơ lý CDM theo Loại Xi Măng (sử dụng NumPyro)\n\n")
        f.write("> Phân tích Bayesian sử dụng PyMC backend NumPyro (Phân vị 5% thiết kế).\n\n")
        f.write(df_res.to_markdown(index=False))
        
        f.write("\n\n## Biểu đồ Hậu nghiệm chi tiết\n\n")
        for row in results:
            safe_name = f"{row['Loại Xi Măng'].replace(' ', '_').replace('(', '').replace(')', '')}_{str(row['Hàm Lượng (kg/m3)']).replace(' ', '_')}_numpyro"
            f.write(f"### {row['Loại Xi Măng']} - {row['Hàm Lượng (kg/m3)']} kg/m3\n")
            f.write(f"![{safe_name}](../images/posterior_cdm_{safe_name}.png)\n\n")

    print(f"\nHOÀN TẤT! Đã xuất báo cáo tại: {md_path}")

if __name__ == '__main__':
    main()
