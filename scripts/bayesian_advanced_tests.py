import sqlite3
import pandas as pd
import pymc as pm
import arviz as az
import matplotlib.pyplot as plt
import numpy as np
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = "data/TTHC.sqlite"
ARTIFACT_DIR = r"C:\Users\TEMP.PNBAYBIMGIS.004\.gemini\antigravity-ide\brain\290a4454-77ed-4ab5-b447-a7bd1cce423c\scratch"

DRAWS = 2000
TUNE = 1000
CHAINS = 4

def run_mcmc_1d(data, var_name, prior_type="HalfNormal"):
    mean_val = np.mean(data)
    std_val = np.std(data) if len(data) > 1 else mean_val * 0.5
    
    with pm.Model() as model:
        if prior_type == "HalfNormal":
            mu = pm.HalfNormal(f"mu_{var_name}", sigma=max(mean_val*3, 10))
        elif prior_type == "Lognormal":
            mu_log = np.log(mean_val**2 / np.sqrt(std_val**2 + mean_val**2))
            sd_log = np.sqrt(np.log(1 + (std_val**2 / mean_val**2)))
            mu = pm.Lognormal(f"mu_{var_name}", mu=mu_log, sigma=sd_log)
        else:
            mu = pm.Normal(f"mu_{var_name}", mu=mean_val, sigma=max(std_val*3, 5))
            
        sigma = pm.Exponential(f"sigma_{var_name}", 1.0)
        obs = pm.Normal(f"obs_{var_name}", mu=mu, sigma=sigma, observed=data)
        
        trace = pm.sample(draws=DRAWS, tune=TUNE, chains=CHAINS, cores=1, progressbar=False, compute_convergence_checks=False)
        
    posterior = trace.posterior[f"mu_{var_name}"].values.flatten()
    design_val = np.percentile(posterior, 5)
    return trace, design_val, mean_val

def plot_posterior(trace, var_name, layer_symbol, test_type, unit, design_val, mean_val, ax):
    az.plot_posterior(trace, var_names=[f"mu_{var_name}"], ax=ax, kind='kde', hdi_prob=0.95, textsize=10)
    ax.set_title(f"Lớp {layer_symbol} - {var_name}\nDesign: {design_val:.3f} {unit}", color='blue')
    ax.axvline(design_val, color='red', linestyle='--', label=f'5% Design ({design_val:.3f})')
    ax.axvline(mean_val, color='green', linestyle='-', label=f'Mean ({mean_val:.3f})')
    ax.legend()

def analyze_params(df, param_configs, test_name):
    print(f"\n--- Đang phân tích {test_name} ---")
    results = []
    
    for layer in df['symbol'].unique():
        layer_data = df[df['symbol'] == layer]
        if len(layer_data) < 3:
            print(f"Bỏ qua Lớp {layer} (chỉ có {len(layer_data)} mẫu).")
            continue
            
        print(f" Lớp {layer} (n={len(layer_data)}): ", end="")
        
        row_res = {"Test": test_name, "Lớp": layer, "n": len(layer_data)}
        
        # Calculate grid size for subplots
        n_params = len(param_configs)
        cols = min(3, n_params)
        rows = (n_params + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(cols*4, rows*3))
        if n_params == 1: axes = [axes]
        else: axes = axes.flatten()
        
        for i, (param_db, param_name, unit, prior_type) in enumerate(param_configs):
            valid_data = layer_data[param_db].dropna().values
            if len(valid_data) < 3:
                row_res[f"{param_name} Mean"] = "-"
                row_res[f"{param_name} Design"] = "-"
                row_res[f"{param_name} Penalty(%)"] = "-"
                if n_params > 1: axes[i].set_visible(False)
                continue
                
            trace, p_des, p_mean = run_mcmc_1d(valid_data, param_name, prior_type)
            print(f"{param_name}={p_mean:.2f}->{p_des:.2f} | ", end="")
            
            row_res[f"{param_name} Mean"] = round(p_mean, 3)
            row_res[f"{param_name} Design"] = round(p_des, 3)
            row_res[f"{param_name} Penalty(%)"] = round((p_des - p_mean) / max(p_mean, 0.0001) * 100, 1)
            
            ax = axes[i] if n_params > 1 else axes[0]
            plot_posterior(trace, param_name, layer, test_name, unit, p_des, p_mean, ax)
            
        print()
        plt.tight_layout()
        plt.savefig(os.path.join(ARTIFACT_DIR, f"soil_{test_name.replace(' ', '_')}_{layer}.png"), dpi=100)
        plt.close(fig)
        
        results.append(row_res)
        
    return pd.DataFrame(results)

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Consolidation
    query_cons = """
    SELECT l.symbol, lab.e0, lab.Cc, lab.Cs, lab.PC_kPa, lab.Cv_cm2s, lab.a12_cm2kgf
    FROM lab_tests lab JOIN layers l ON lab.borehole_id = l.borehole_id
    AND ((lab.depth_from_m + lab.depth_to_m)/2.0 BETWEEN l.depth_top_m AND l.depth_bot_m)
    """
    df_cons = pd.read_sql_query(query_cons, conn)
    params_cons = [
        ("e0", "e0", "-", "Normal"),
        ("Cc", "Cc", "-", "Lognormal"),
        ("Cs", "Cs", "-", "Lognormal"),
        ("PC_kPa", "Pc", "kPa", "HalfNormal"),
        ("Cv_cm2s", "Cv", "cm2/s", "Lognormal"),
        ("a12_cm2kgf", "a12", "cm2/kgf", "Lognormal")
    ]
    df_res_cons = analyze_params(df_cons, params_cons, "Consolidation")
    
    # 2. CU & UU
    query_shear = """
    SELECT l.symbol, lab.c_CU_eff_kPa, lab.phi_CU_eff_deg, lab.c_CU_kPa, lab.phi_CU_deg, lab.Cu_UU_kPa, lab.qu_kPa
    FROM lab_tests lab JOIN layers l ON lab.borehole_id = l.borehole_id
    AND ((lab.depth_from_m + lab.depth_to_m)/2.0 BETWEEN l.depth_top_m AND l.depth_bot_m)
    """
    df_shear = pd.read_sql_query(query_shear, conn)
    params_cu = [
        ("c_CU_eff_kPa", "c'_CU", "kPa", "HalfNormal"),
        ("phi_CU_eff_deg", "phi'_CU", "deg", "HalfNormal"),
        ("c_CU_kPa", "c_CU", "kPa", "HalfNormal"),
        ("phi_CU_deg", "phi_CU", "deg", "HalfNormal")
    ]
    df_res_cu = analyze_params(df_shear, params_cu, "CU_Test")
    
    params_uu = [
        ("Cu_UU_kPa", "Cu_UU", "kPa", "HalfNormal"),
        ("qu_kPa", "qu", "kPa", "HalfNormal")
    ]
    df_res_uu = analyze_params(df_shear, params_uu, "UU_and_qu")
    
    # 3. VST
    query_vst = """
    SELECT l.symbol, vst.Su_kPa, vst.Sp_kPa
    FROM vane_shear_tests vst
    JOIN vst_locations loc ON vst.vst_loc_id = loc.id
    JOIN boreholes b ON loc.name = b.name
    JOIN layers l ON b.id = l.borehole_id AND (vst.depth_m BETWEEN l.depth_top_m AND l.depth_bot_m)
    """
    df_vst = pd.read_sql_query(query_vst, conn)
    params_vst = [
        ("Su_kPa", "Su_VST", "kPa", "HalfNormal"),
        ("Sp_kPa", "Sp_VST", "kPa", "HalfNormal")
    ]
    df_res_vst = analyze_params(df_vst, params_vst, "VST")
    
    conn.close()
    
    md_path = os.path.join(ARTIFACT_DIR, "bayesian_advanced_results.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Tổng hợp Giá trị Thiết kế Cơ lý Nâng cao (Phân vị 5% Bayes)\n\n")
        f.write("> Lọc từ CSDL `data/TTHC.sqlite` và phân tích tự động bằng mô hình NUTS (PyMC).\n")
        
        sections = [
            ("1. Thí nghiệm Nén cố kết (Consolidation)", df_res_cons),
            ("2. Thí nghiệm Cắt CU", df_res_cu),
            ("3. Thí nghiệm Cắt UU và nén đơn qu", df_res_uu),
            ("4. Thí nghiệm Cắt cánh hiện trường (VST)", df_res_vst)
        ]
        
        for title, df in sections:
            f.write(f"## {title}\n")
            if not df.empty:
                f.write(df.to_markdown(index=False) + "\n\n")
            else:
                f.write("*Không có đủ dữ liệu để phân tích.*\n\n")
                
    print(f"\nHOÀN TẤT! Đã xuất báo cáo tổng hợp tại: {md_path}")
