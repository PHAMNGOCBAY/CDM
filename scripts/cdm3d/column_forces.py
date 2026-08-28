"""cdm3d.column_forces — Trich xuat chuyen vi ngang + mo men uon TUONG DUONG doc
theo tung coc CDM tu ket qua FEM 3D (khong co san nhu phan tu beam — phai tu suy
tu truong chuyen vi/ung suat khoi lien tuc).

Xac nhan thuc nghiem (2026-08-27): truong 'S' trong .vtu (do ccx2paraview sinh tu
.frd CalculiX) co 6 thanh phan theo dung thu tu [XX, YY, ZZ, XY, YZ, ZX] (kiem tra
qua VTK component name, xem 76-cdm3d-fem-gmsh-calculix.md) — sigma_zz = S[:, 2].
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pyvista as pv

_SIGMA_ZZ_COL = 2  # S = [XX, YY, ZZ, XY, YZ, ZX] — da xac nhan qua VTK component name


def extract_lateral_profile(vtu_path: Path, column_xy: tuple[float, float],
                             z_top: float, z_bot: float, n_levels: int = 30) -> dict:
    """Noi suy chuyen vi U doc theo tam truc 1 coc (pyvista sample_over_line — khong
    can tim nut chinh xac, hoat dong voi bat ky duong thang nao trong khoi 3D).
    Chi dung y nghia vat ly cho cac giai doan CO TAI (GD2..N) — GD0/GD1 khong tai
    nen chuyen vi ~0, khong phan anh gi.

    Tra ve dict: elev (m, cao do that), ux_mm, uy_mm, u_lat_mm (=sqrt(ux^2+uy^2))."""
    grid = pv.read(str(vtu_path))
    if "U" not in grid.point_data:
        raise KeyError(f"Khong co truong 'U' trong {vtu_path}")

    x0, y0 = column_xy
    line = grid.sample_over_line((x0, y0, z_top), (x0, y0, z_bot), resolution=n_levels)
    valid = line.point_data.get("vtkValidPointMask")
    U = np.asarray(line.point_data["U"])
    elev = line.points[:, 2]

    n_bad = 0
    if valid is not None:
        valid = valid.astype(bool)
        n_bad = int((~valid).sum())
        if n_bad > 0:
            elev, U = elev[valid], U[valid]

    ux_mm = (U[:, 0] * 1000.0).tolist()
    uy_mm = (U[:, 1] * 1000.0).tolist()
    u_lat_mm = (np.sqrt(U[:, 0] ** 2 + U[:, 1] ** 2) * 1000.0).tolist()

    return {
        "elev": elev.tolist(), "ux_mm": ux_mm, "uy_mm": uy_mm, "u_lat_mm": u_lat_mm,
        "n_invalid_points": n_bad,
    }


def extract_moment_profile(vtu_path: Path, column_xy: tuple[float, float], D_m: float,
                            z_top: float, z_bot: float, n_levels: int = 20,
                            n_ring: int = 8, n_radius: int = 3,
                            min_points: int = 6) -> dict:
    """Suy mo men uon TUONG DUONG M(z) tu truong ung suat khoi lien tuc: tai moi
    cao do z, lay mau sigma_zz tren luoi diem (tam + cac vong tron ban kinh <= D/2),
    fit mat phang sigma_zz = s0 + kx*(x-x0) + ky*(y-y0) bang binh phuong toi thieu
    (numpy.linalg.lstsq — day la GIA THIET LY THUYET DAM Euler-Bernoulli ap cho khoi
    lien tuc, XAP XI KY THUAT — CHUA phan anh dung ung suat 3D that, be tap trung
    ung suat, hieu ung cat). Quy doi M = k * I, I = pi*D^4/64 (mat cat tron).

    Quy uoc: My_kNm (mo men quanh truc Y — gay boi ung suat bien thien theo x, tuc
    la truc gay boi TAI LECH TAM theo x — xem ccx_input.LoadStage.ecc_axis='x')
    va Mx_kNm (quanh truc X — bien thien theo y) — dau chi mang y nghia tuong doi,
    kY su can doi chieu voi quy uoc rieng khi dung ket qua.

    Canh bao: CHUA CO nguong Mcr cho coc CDM trong du lieu du an (khac coc van SW
    da co catalog Mcr) — ham nay CHI xuat gia tri M(z) tho, KHONG tu dat nguong
    Dat/Khong dat."""
    grid = pv.read(str(vtu_path))
    if "S" not in grid.point_data:
        raise KeyError(f"Khong co truong 'S' (ung suat) trong {vtu_path} — can *EL FILE S trong .inp")

    x0, y0 = column_xy
    r_max = D_m / 2.0
    I = np.pi * D_m ** 4 / 64.0
    z_levels = np.linspace(z_top, z_bot, n_levels)
    radii = np.linspace(r_max / n_radius, r_max, n_radius)
    angles = np.linspace(0.0, 2 * np.pi, n_ring, endpoint=False)

    out = {"z_depth": [], "elev": [], "Mx_kNm": [], "My_kNm": [], "n_points_used": [],
           "warnings": []}

    for z in z_levels:
        pts = [(x0, y0, z)]
        for r in radii:
            for a in angles:
                pts.append((x0 + r * np.cos(a), y0 + r * np.sin(a), z))
        pts_arr = np.array(pts)

        sampled = pv.PolyData(pts_arr).sample(grid)
        valid_mask = np.asarray(sampled.point_data.get("vtkValidPointMask", np.ones(len(pts_arr))))
        valid_mask = valid_mask.astype(bool)
        S = np.asarray(sampled.point_data["S"])[valid_mask]
        pts_valid = pts_arr[valid_mask]
        n_valid = int(valid_mask.sum())

        Mx, My = 0.0, 0.0
        if n_valid < min_points:
            out["warnings"].append(
                f"z={z:.2f}m: chi {n_valid} diem hop le (<{min_points}) — fit khong "
                f"tin cay, luoi quanh cot co the qua tho (khuyen nghi giam "
                f"mesh_size_near_column_m khi can ket qua chinh xac)."
            )
        else:
            sigma_zz = S[:, _SIGMA_ZZ_COL]
            xs = pts_valid[:, 0] - x0
            ys = pts_valid[:, 1] - y0
            A = np.column_stack([np.ones_like(xs), xs, ys])
            coef, *_ = np.linalg.lstsq(A, sigma_zz, rcond=None)
            _s0, kx, ky = coef
            My = kx * I  # mo men quanh truc Y — sinh boi bien thien sigma_zz theo x
            Mx = ky * I  # mo men quanh truc X — sinh boi bien thien sigma_zz theo y

        out["z_depth"].append(z_top - z)
        out["elev"].append(float(z))
        out["Mx_kNm"].append(float(Mx))
        out["My_kNm"].append(float(My))
        out["n_points_used"].append(n_valid)

    return out


def plot_lateral_profiles(profiles: dict[str, dict], out_png: Path,
                           title: str = "", value_key: str = "ux_mm",
                           xlabel: str = "Chuyen vi ngang Ux (mm)",
                           linestyles: dict[str, str] | None = None,
                           color_key: dict[str, int] | None = None) -> Path:
    """Ve bieu do chuyen vi ngang theo cao do cho 1 hoac nhieu coc (profiles: {nhan:
    dict tu extract_lateral_profile()}). Cao do THAT tren truc Y (khong dao nguoc) —
    dung quy uoc bieu do M/u da co cua module Winkler 2D trong du an
    (scripts/wall_internal_force.py + panel trong app_cdm.py).
    linestyles: {nhan: '-'|'--'|...} — dung de phan biet KICH BAN (vd goc vs gia
    dinh) khi cung 1 mau ung voi cung 1 VI TRI. color_key: {nhan: chi_so_mau} — ep
    2 nhan dung CHUNG 1 mau (vd cung vi tri, khac kich ban) thay vi tu dong theo
    thu tu dict."""
    fig, ax = plt.subplots(figsize=(7, 8.5))
    colors = plt.cm.tab10.colors
    for i, (label, prof) in enumerate(profiles.items()):
        c_idx = color_key[label] if color_key and label in color_key else i
        ls = linestyles[label] if linestyles and label in linestyles else "-"
        ax.plot(prof[value_key], prof["elev"], marker="o", ms=3, lw=1.6, ls=ls,
                color=colors[c_idx % len(colors)], label=label)
    ax.axvline(0, color="#888888", lw=0.8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Cao do (m)")
    ax.set_title(title or "Chuyen vi ngang theo cao do — coc CDM", fontsize=11, wrap=True)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=1)
    fig.tight_layout()

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png


def extract_axial_force_profile(vtu_path: Path, column_xy: tuple[float, float], D_m: float,
                                 z_top: float, z_bot: float, n_levels: int = 30,
                                 n_ring: int = 8, n_radius: int = 3) -> dict:
    """Luc doc truc Nz(z) TUONG DUONG trong coc — TRUNG BINH sigma_zz tren mat cat
    (KHONG fit gradient nhu extract_moment_profile — do do tin cay cao hon nhieu
    voi luoi hien tai, vi trung binh khong nhay cam voi so diem mau it nhu fit mat
    phang). Nz = sigma_zz_tb * A, A = pi*D^2/4. Quy uoc CalculiX/continuum: sigma
    NEN (compression) mang dau AM.

    Dung de kiem chung dinh tinh ma sat am (negative skin friction): neu Nz (nen)
    TANG dan theo do sau (tu dinh xuong) roi GIAM lai gan mui — dang "phinh" dac
    trung — la dau hieu dat lun nhieu hon coc dang "keo" coc xuong qua ma sat than
    (hoac tuong duong ve dong hoc trong mo hinh BONDED, vi khong co truot that)."""
    grid = pv.read(str(vtu_path))
    if "S" not in grid.point_data:
        raise KeyError(f"Khong co truong 'S' (ung suat) trong {vtu_path}")

    x0, y0 = column_xy
    r_max = D_m / 2.0
    A = np.pi * r_max ** 2
    z_levels = np.linspace(z_top, z_bot, n_levels)
    radii = np.linspace(r_max / n_radius, r_max, n_radius)
    angles = np.linspace(0.0, 2 * np.pi, n_ring, endpoint=False)

    out = {"z_depth": [], "elev": [], "sigma_zz_avg_kPa": [], "Nz_kN": [], "n_points_used": []}
    for z in z_levels:
        pts = [(x0, y0, z)]
        for r in radii:
            for a in angles:
                pts.append((x0 + r * np.cos(a), y0 + r * np.sin(a), z))
        sampled = pv.PolyData(np.array(pts)).sample(grid)
        valid = np.asarray(sampled.point_data.get("vtkValidPointMask", np.ones(len(pts)))).astype(bool)
        S = np.asarray(sampled.point_data["S"])[valid]
        n_valid = int(valid.sum())
        sigma_avg = float(S[:, _SIGMA_ZZ_COL].mean()) if n_valid > 0 else 0.0

        out["z_depth"].append(z_top - z)
        out["elev"].append(float(z))
        out["sigma_zz_avg_kPa"].append(sigma_avg)
        out["Nz_kN"].append(sigma_avg * A)
        out["n_points_used"].append(n_valid)

    return out


def plot_axial_force_profile(profiles: dict[str, dict], out_png: Path, title: str = "") -> Path:
    """Bieu do Nz(z) — cao do that tren truc Y, giong quy uoc plot_lateral_profiles.
    Nz am = nen (quy uoc CalculiX)."""
    fig, ax = plt.subplots(figsize=(6, 8.5))
    colors = plt.cm.tab10.colors
    for i, (label, prof) in enumerate(profiles.items()):
        ax.plot(prof["Nz_kN"], prof["elev"], marker="o", ms=3, lw=1.6,
                color=colors[i % len(colors)], label=label)
    ax.axvline(0, color="#888888", lw=0.8)
    ax.set_xlabel("Nz (kN) — am = nen")
    ax.set_ylabel("Cao do (m)")
    ax.set_title(title or "Luc doc truc tuong duong Nz(z) — coc CDM", fontsize=11, wrap=True)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png
