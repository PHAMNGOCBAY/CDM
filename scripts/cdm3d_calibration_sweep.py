"""cdm3d_calibration_sweep — Khao sat do nhay Ux_max (GD5) theo (a) domain_buffer_m
va (b) Es lop dat yeu, so sanh voi gia tri quan trac thuc te (~80cm) de tim nguyen
nhan chenh lech. Dung mo hinh BONDED (nhanh hon contact) + use_model_change=False
(bo qua GD-1/GD0/GD1, chi giai GD2..GD5 — ket qua GD5 cuoi cung tuong duong ve mat
vat ly vi mo hinh dan hoi tuyen tinh, khong phu thuoc lich su kich hoat).

Chay: python scripts/cdm3d_calibration_sweep.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

import gmsh
import matplotlib.pyplot as plt

from cdm3d import ccx_input, column_forces, geometry, mesh_gmsh, params_io, postprocess, run_ccx

OUT_DIR = _ROOT / "results" / "cdm3d" / "calib"
IMG_DIR = _ROOT / "images"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MEASURED_CM = 80.0


def run_case(job_name: str, domain_buffer_m: float | None, es_factor: float,
             ecdm_factor: float = 1.0) -> dict:
    t0 = time.time()
    params = params_io.build_default_params("KE")
    if domain_buffer_m is not None:
        params.domain_buffer_m = domain_buffer_m
    for layer in params.soil_layers:
        if layer.name == "dat_yeu":
            layer.E_kPa *= es_factor
    params.column.Ec_kPa *= ecdm_factor

    msh_path = OUT_DIR / f"{job_name}.msh"
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        geometry.build_geometry(params)
        mesh_gmsh.generate_mesh(params, element_order=1)
        n_nodes = mesh_gmsh.mesh_stats()["n_nodes"]
        mesh_gmsh.export_mesh(msh_path)
    finally:
        gmsh.finalize()

    inp_path = ccx_input.write_ccx_inp(msh_path, OUT_DIR / f"{job_name}.inp", params,
                                        use_model_change=False)
    frd_path = run_ccx.solve(inp_path, timeout_s=900)
    vtu_path = postprocess.convert_frd_to_vtu(frd_path)

    x_edge = ((params.column.n_x - 1) * params.column.spacing_m) / 2.0
    prof = column_forces.extract_lateral_profile(
        vtu_path, (x_edge, 0.0), params.column.z_top, params.column.z_bot, n_levels=25)
    ux_max_mm = max(abs(v) for v in prof["ux_mm"])

    dt = time.time() - t0
    print(f"[{job_name}] domain_buffer={params.domain_buffer_m}m Es={params.soil_layers[1].E_kPa:.0f}kPa "
          f"Ecdm={params.column.Ec_kPa:.0f}kPa n_nodes={n_nodes} Ux_max={ux_max_mm:.2f}mm "
          f"={ux_max_mm/10:.2f}cm ({dt:.0f}s)")
    return {"job": job_name, "domain_buffer_m": params.domain_buffer_m,
            "Es_kPa": params.soil_layers[1].E_kPa, "es_factor": es_factor,
            "Ec_kPa": params.column.Ec_kPa, "ecdm_factor": ecdm_factor,
            "n_nodes": n_nodes, "Ux_max_mm": ux_max_mm, "time_s": dt}


def plot_sweep(results: list[dict], x_key: str, x_label: str, out_png: Path, title: str,
               logx: bool = False) -> Path:
    xs = [r[x_key] for r in results]
    ys_cm = [r["Ux_max_mm"] / 10.0 for r in results]
    fig, ax = plt.subplots(figsize=(7, 5.5))
    ax.plot(xs, ys_cm, "o-", color="#1565C0", lw=2, ms=7, label="Mo hinh (GD5)")
    ax.axhline(MEASURED_CM, color="#D32F2F", ls="--", lw=1.8, label=f"Quan trac thuc te ({MEASURED_CM:.0f} cm)")
    if logx:
        ax.set_xscale("log")
    ax.set_xlabel(x_label)
    ax.set_ylabel("Ux_max tai tam cot (cm)")
    ax.set_title(title, fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png


def main() -> None:
    print("=== KHAO SAT 1: domain_buffer_m (Es giu nguyen) ===")
    domain_results = []
    for buf in (3.6, 7.0, 15.0, 30.0):
        r = run_case(f"KE_calib_dom{buf:.0f}", domain_buffer_m=buf, es_factor=1.0)
        domain_results.append(r)

    print("=== KHAO SAT 2: Es lop dat yeu (domain goc) ===")
    es_results = []
    for factor in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
        r = run_case(f"KE_calib_es{factor:.4f}", domain_buffer_m=3.6, es_factor=factor)
        es_results.append(r)

    print("=== KHAO SAT 3: Ecdm (domain + Es goc) ===")
    ecdm_results = []
    for factor in (1.0, 0.5, 0.25, 0.125, 0.0625):
        r = run_case(f"KE_calib_ecdm{factor:.4f}", domain_buffer_m=3.6, es_factor=1.0, ecdm_factor=factor)
        ecdm_results.append(r)

    print("=== KHAO SAT 4: KET HOP (domain tang + Es giam + Ecdm giam dong thoi) ===")
    combo_results = []
    combo_cases = [
        ("base", 3.6, 1.0, 1.0),
        ("mild", 7.0, 0.5, 0.5),
        ("moderate", 15.0, 0.25, 0.25),
        ("strong", 30.0, 0.1, 0.1),
        ("extreme", 30.0, 0.03, 0.03),
    ]
    for label, buf, esf, ecf in combo_cases:
        r = run_case(f"KE_calib_combo_{label}", domain_buffer_m=buf, es_factor=esf, ecdm_factor=ecf)
        r["label"] = label
        combo_results.append(r)

    p1 = plot_sweep(domain_results, "domain_buffer_m", "Domain buffer (m)",
                     IMG_DIR / "cdm3d_KE_calib_domain_sweep.png",
                     "Do nhay Ux_max theo kich thuoc mo hinh (domain_buffer_m)\nEs=3450 kPa (goc)")
    print("wrote", p1)

    p2 = plot_sweep(es_results, "Es_kPa", "Es lop dat yeu (kPa, thang log)",
                     IMG_DIR / "cdm3d_KE_calib_Es_sweep.png",
                     "Do nhay Ux_max theo Es lop dat yeu\ndomain_buffer=3.6m (goc)", logx=True)
    print("wrote", p2)

    p3 = plot_sweep(ecdm_results, "Ec_kPa", "Ecdm coc (kPa, thang log)",
                     IMG_DIR / "cdm3d_KE_calib_Ecdm_sweep.png",
                     "Do nhay Ux_max theo Ecdm coc\ndomain_buffer=3.6m, Es=3450kPa (goc)", logx=True)
    print("wrote", p3)

    # bieu do combo: truc x la so thu tu kich ban (khong phai 1 dai luong lien tuc)
    fig, ax = plt.subplots(figsize=(8, 5.5))
    labels = [r["label"] for r in combo_results]
    ys_cm = [r["Ux_max_mm"] / 10.0 for r in combo_results]
    ax.plot(range(len(labels)), ys_cm, "o-", color="#7B1FA2", lw=2, ms=8)
    ax.axhline(MEASURED_CM, color="#D32F2F", ls="--", lw=1.8, label=f"Quan trac thuc te ({MEASURED_CM:.0f} cm)")
    for i, r in enumerate(combo_results):
        ax.annotate(f"buf={r['domain_buffer_m']:.0f}m\nEs={r['Es_kPa']:.0f}\nEc={r['Ec_kPa']:.0f}",
                    (i, ys_cm[i]), textcoords="offset points", xytext=(0, 10), fontsize=7, ha="center")
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels)
    ax.set_ylabel("Ux_max tai tam cot (cm)")
    ax.set_title("Kich ban KET HOP: domain tang + Es giam + Ecdm giam dong thoi", fontsize=11)
    ax.grid(True, alpha=0.3); ax.legend()
    fig.tight_layout()
    p4 = IMG_DIR / "cdm3d_KE_calib_combo_sweep.png"
    fig.savefig(p4, dpi=150); plt.close(fig)
    print("wrote", p4)

    print("\n=== TOM TAT ===")
    for r in domain_results:
        print(f"  domain={r['domain_buffer_m']:.1f}m -> Ux_max={r['Ux_max_mm']/10:.2f}cm")
    for r in es_results:
        print(f"  Es={r['Es_kPa']:.0f}kPa (x{r['es_factor']}) -> Ux_max={r['Ux_max_mm']/10:.2f}cm")
    for r in ecdm_results:
        print(f"  Ecdm={r['Ec_kPa']:.0f}kPa (x{r['ecdm_factor']}) -> Ux_max={r['Ux_max_mm']/10:.2f}cm")
    for r in combo_results:
        print(f"  combo[{r['label']}] buf={r['domain_buffer_m']:.0f}m Es={r['Es_kPa']:.0f} Ec={r['Ec_kPa']:.0f} "
              f"-> Ux_max={r['Ux_max_mm']/10:.2f}cm")


if __name__ == "__main__":
    main()
