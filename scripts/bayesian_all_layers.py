import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import pymc as pm
import arviz as az
import matplotlib.pyplot as plt
import pytensor
pytensor.config.cxx = ""

# Sửa lỗi Unicode trên Windows console
sys.stdout.reconfigure(encoding='utf-8')

# Cấu hình đường dẫn
db_path = r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\data\TTHC.sqlite"
results_dir = r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\results"
images_dir = r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\images"
os.makedirs(results_dir, exist_ok=True)
os.makedirs(images_dir, exist_ok=True)

print("Đang truy vấn dữ liệu từ CSDL...")
conn = sqlite3.connect(db_path)
query = """
    SELECT 
        l.symbol as layer_symbol, 
        t.c_kPa, 
        t.phi_deg 
    FROM lab_tests t
    JOIN layers l ON t.borehole_id = l.borehole_id 
        AND ((t.depth_from_m + t.depth_to_m)/2.0 >= l.depth_top_m) 
        AND ((t.depth_from_m + t.depth_to_m)/2.0 <= l.depth_bot_m)
    WHERE t.c_kPa IS NOT NULL 
      AND t.phi_deg IS NOT NULL
"""
df = pd.read_sql_query(query, conn)
conn.close()

print(f"Tổng số mẫu thí nghiệm hợp lệ thu được: {len(df)}")

# Gom nhóm theo lớp đất
groups = df.groupby('layer_symbol')

results = []

print("Bắt đầu xử lý hàng loạt bằng PyMC...")
for layer_symbol, group in groups:
    n_samples = len(group)
    if n_samples < 5:
        print(f"Bỏ qua Lớp {layer_symbol} (chỉ có {n_samples} mẫu, không đủ cơ sở thống kê).")
        continue
    
    print(f"\n--- Đang phân tích Lớp {layer_symbol} (n={n_samples}) ---")
    
    c_data = group['c_kPa'].values
    phi_data = group['phi_deg'].values
    
    c_mean = np.mean(c_data)
    phi_mean = np.mean(phi_data)
    
    # Thiết lập tham số lấy mẫu
    # Máy đã cài g++ nên có thể đẩy số lượng mẫu lên cao để đảm bảo độ chính xác tối đa
    DRAWS = 2000
    TUNE = 1000
    CHAINS = 4
    
    with pm.Model() as soil_model:
        # Priors linh động dựa trên mean để hỗ trợ cả cát và sét
        mu_c = pm.HalfNormal("mu_c", sigma=max(20, c_mean*3)) 
        sigma_c = pm.Exponential("sigma_c", 1.0)
        
        mu_phi = pm.HalfNormal("mu_phi", sigma=max(30, phi_mean*2))
        sigma_phi = pm.Exponential("sigma_phi", 1.0)
        
        # Likelihood
        c_obs = pm.Normal("c_obs", mu=mu_c, sigma=sigma_c, observed=c_data)
        phi_obs = pm.Normal("phi_obs", mu=mu_phi, sigma=sigma_phi, observed=phi_data)
        
        # Lấy mẫu
        trace = pm.sample(
            draws=DRAWS, 
            tune=TUNE, 
            chains=CHAINS, 
            cores=1, 
            progressbar=False,
            compute_convergence_checks=False
        )
    
    # Trích xuất hậu nghiệm
    posterior_c = trace.posterior["mu_c"].values.flatten()
    posterior_phi = trace.posterior["mu_phi"].values.flatten()
    
    c_char = np.percentile(posterior_c, 5)
    phi_char = np.percentile(posterior_phi, 5)
    
    print(f" Lớp {layer_symbol}: c_mean = {c_mean:.2f} -> c_design = {c_char:.2f}")
    print(f" Lớp {layer_symbol}: phi_mean = {phi_mean:.2f} -> phi_design = {phi_char:.2f}")
    
    # Xuất plot 
    plt.style.use('default')
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    
    # Biểu đồ c
    az.plot_posterior(trace, var_names=["mu_c"], ax=axes[0], kind='kde', hdi_prob=0.95, textsize=10)
    axes[0].set_title(f"Lớp {layer_symbol} - Lực dính c\nDesign (5%): {c_char:.2f} kPa", color='blue')
    axes[0].axvline(c_char, color='red', linestyle='--', label=f'5% Design ({c_char:.2f})')
    axes[0].axvline(c_mean, color='green', linestyle='-', label=f'Geotech Mean ({c_mean:.2f})')
    axes[0].legend()
    
    # Biểu đồ phi
    az.plot_posterior(trace, var_names=["mu_phi"], ax=axes[1], kind='kde', hdi_prob=0.95, textsize=10)
    axes[1].set_title(f"Lớp {layer_symbol} - Góc ma sát phi\nDesign (5%): {phi_char:.2f}°", color='blue')
    axes[1].axvline(phi_char, color='red', linestyle='--', label=f'5% Design ({phi_char:.2f})')
    axes[1].axvline(phi_mean, color='green', linestyle='-', label=f'Geotech Mean ({phi_mean:.2f})')
    axes[1].legend()
    
    plt.tight_layout()
    plot_path = os.path.join(images_dir, f"soil_posterior_layer_{layer_symbol}.png")
    plt.savefig(plot_path, dpi=100)
    plt.close(fig)
    
    # Lưu kết quả
    results.append({
        "Lớp": layer_symbol,
        "Số mẫu (n)": n_samples,
        "c_mean (kPa)": round(c_mean, 2),
        "c_design (kPa)": round(c_char, 2),
        "Giảm c (%)": round((c_char - c_mean) / c_mean * 100, 1) if c_mean > 0 else 0,
        "phi_mean (độ)": round(phi_mean, 2),
        "phi_design (độ)": round(phi_char, 2),
        "Giảm phi (%)": round((phi_char - phi_mean) / phi_mean * 100, 1) if phi_mean > 0 else 0
    })

# Tạo báo cáo Markdown
df_res = pd.DataFrame(results)
# Sort by layer symbol
df_res = df_res.sort_values(by="Lớp")

md_path = os.path.join(results_dir, "bayesian_results_all.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write("# Tổng hợp Giá trị Thiết kế Cơ lý Đất (Phân vị 5% Bayes)\n\n")
    f.write("> Lọc từ CSDL `data/TTHC.sqlite` và phân tích tự động bằng mô hình NUTS (PyMC).\n")
    f.write("> **Ghi chú:** Máy đã được cài C++ compiler (`g++`) nên độ chính xác được đẩy lên tối đa (`draws=2000, tune=1000`).\n\n")
    
    # Convert DF to markdown table
    f.write(df_res.to_markdown(index=False))
    
    f.write("\n\n## Biểu đồ Hậu nghiệm\n\n")
    for row in results:
        sym = row["Lớp"]
        f.write(f"### Lớp {sym}\n")
        f.write(f"![Lớp {sym}](../images/soil_posterior_layer_{sym}.png)\n\n")

print(f"\nHOÀN TẤT! Đã xuất báo cáo tổng hợp tại: {md_path}")
