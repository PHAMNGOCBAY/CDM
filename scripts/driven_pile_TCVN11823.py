"""Tinh suc chiu tai coc dong theo TCVN 11823-10:2017, Dieu 7.3.8.6.

Phuong phap phan tich tinh hoc theo dat nen:
  - Phuong phap alpha (set bao hoa) — Pt. 62, 65
  - Phuong phap beta  (set, ung suat co hieu) — Pt. 63
  - Phuong phap lambda (set, ong dac dong) — Pt. 64
  - Phuong phap SPT Meyerhof (cat, cat bot) — Pt. 68-70
  - Cong thuc tong quat: Rn = Rp + Rs, RR = phi * Rn — Pt. 58-61

Don vi: MPa, mm, N (theo TCVN 11823-10).
Nguon: data/driven_pile_TCVN11823.json
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

sys.stdout.reconfigure(encoding="utf-8")

_DATA = Path(__file__).parent.parent / "data" / "driven_pile_TCVN11823.json"

# ── He so suc khang (Bang 9) ─────────────────────────────────────────────────

PHI_STAT: dict[str, float] = {
    "alpha":     0.35,   # Phuong phap alpha — set
    "beta":      0.25,   # Phuong phap beta  — set
    "lambda":    0.40,   # Phuong phap lambda — set
    "nordlund":  0.45,   # Nordlund/Thurman  — cat
    "SPT":       0.30,   # SPT Meyerhof      — cat
    "CPT":       0.50,   # CPT Schmertmann   — cat/set
    "rock":      0.45,   # Mui coc tua tren da
}

# ── He so alpha Tomlinson (1980) — Hinh 18 ──────────────────────────────────
# Noi suy tuyen tinh tu bien do: Su (MPa) -> alpha
_ALPHA_SU  = [0.000, 0.025, 0.050, 0.075, 0.100, 0.150, 0.200]
_ALPHA_VAL = [1.000, 1.000, 0.920, 0.750, 0.600, 0.500, 0.400]


def alpha_tomlinson(Su_MPa: float) -> float:
    """He so ket dinh alpha theo bieu do Tomlinson (1980) — Hinh 18.

    Su_MPa: suc khang cat khong thoat nuoc (MPa).
    Tra bieu do: Su <= 0.025 MPa -> alpha = 1.0; Su >= 0.20 MPa -> alpha = 0.40.
    """
    if Su_MPa <= _ALPHA_SU[0]:
        return _ALPHA_VAL[0]
    if Su_MPa >= _ALPHA_SU[-1]:
        return _ALPHA_VAL[-1]
    for i in range(len(_ALPHA_SU) - 1):
        if _ALPHA_SU[i] <= Su_MPa <= _ALPHA_SU[i + 1]:
            t = (Su_MPa - _ALPHA_SU[i]) / (_ALPHA_SU[i + 1] - _ALPHA_SU[i])
            return _ALPHA_VAL[i] + t * (_ALPHA_VAL[i + 1] - _ALPHA_VAL[i])
    return _ALPHA_VAL[-1]


# ── Cac phuong phap tinh ma sat thanh ben qs (MPa) ──────────────────────────

def qs_alpha(Su_MPa: float, alpha: float | None = None) -> float:
    """Pt. 62: qs = alpha * Su (MPa) — Phuong phap alpha (set bao hoa).

    Su_MPa: suc khang cat khong thoat nuoc (MPa).
    alpha: neu None thi tu dong tinh theo Tomlinson (1980).
    """
    a = alpha if alpha is not None else alpha_tomlinson(Su_MPa)
    return a * Su_MPa


def qs_beta(beta: float, sigma_v_eff_MPa: float) -> float:
    """Pt. 63: qs = beta * sigma'v (MPa) — Phuong phap beta (ung suat co hieu).

    beta: tra bieu do Hinh 19 (Esrig & Kirby 1979) theo OCR.
    sigma_v_eff_MPa: ung suat co hieu thang dung (MPa).
    """
    return beta * sigma_v_eff_MPa


def qs_lambda(lam: float, sigma_v_eff_MPa: float, Su_MPa: float) -> float:
    """Pt. 64: qs = lambda * (sigma'v + 2*Su) (MPa) — Phuong phap lambda.

    lam: he so tra bieu do Hinh 20 (Vijayvergiya & Focht 1972).
    sigma_v_eff_MPa: ung suat co hieu thang dung (MPa).
    Su_MPa: suc khang cat khong thoat nuoc (MPa).
    """
    return lam * (sigma_v_eff_MPa + 2 * Su_MPa)


def qs_SPT_displacement(N160: float) -> float:
    """Pt. 69: qs = 0.0019 * N160 (MPa) — coc chiem cho (dac / hop kin).

    Ap dung cho cat, cat bot khong pha set.
    Coc chiem cho: mat cat dac, hop mui coc kin (beton duc san, coc ong bit day).
    """
    return 0.0019 * N160


def qs_SPT_nondisplacement(N160: float) -> float:
    """Pt. 70: qs = 0.00096 * N160 (MPa) — coc khong chiem cho (chu H, ong ho).

    Ap dung cho cat, cat bot khong pha set.
    """
    return 0.00096 * N160


# ── Suc khang mui coc qp (MPa) ───────────────────────────────────────────────

def qp_clay(Su_MPa: float) -> float:
    """Pt. 65: qp = 9 * Su (MPa) — mui coc trong dat set bao hoa (ung suat tong).

    Su_MPa: suc khang cat khong thoat nuoc cua dat set xung quanh mui coc (MPa).
    """
    return 9.0 * Su_MPa


def qp_SPT_sand(
    N160: float,
    D_mm: float,
    Db_mm: float,
    soil_type: Literal["sand", "silty_sand"] = "sand",
) -> float:
    """Pt. 68: qp = 0.038 * N160 * (Db/D) (MPa, <= lambda_q) — SPT Meyerhof.

    Ap dung cho cat, cat bot khong pha set.
    N160: so bua SPT hieu chinh (bua/300mm).
    D_mm: duong kinh/be rong coc (mm).
    Db_mm: chieu dai coc ngam trong tang dat chiu luc (mm).
    soil_type: 'sand' -> lambda_q = 3.2*N160; 'silty_sand' -> 1.8*N160.
    """
    if soil_type == "sand":
        lambda_q = 3.2 * N160          # 8 * 0.4 * N160
    else:
        lambda_q = 1.8 * N160          # 6 * 0.3 * N160
    qp = 0.038 * N160 * (Db_mm / D_mm)
    return min(qp, lambda_q)


# ── Suc khang tong hop coc don ───────────────────────────────────────────────

@dataclass
class LayerInput:
    """Mot lop dat doc theo than coc."""
    thickness_mm: float
    perimeter_mm: float
    qs_MPa: float


@dataclass
class PileCapacityResult:
    """Ket qua tinh suc chiu tai coc don."""
    method: str
    Rs_N:   float        # Suc khang ma sat thanh ben (N)
    Rp_N:   float        # Suc khang mui coc (N)
    Rn_N:   float        # Suc khang danh dinh (N)
    phi:    float        # He so suc khang (Bang 9)
    RR_N:   float        # Suc khang tinh toan (N)

    def print_summary(self) -> None:
        print(f"\n  Phuong phap : {self.method}")
        print(f"  phi_stat    : {self.phi}")
        print(f"  Rs          : {self.Rs_N/1e3:>10.1f} kN")
        print(f"  Rp          : {self.Rp_N/1e3:>10.1f} kN")
        print(f"  Rn          : {self.Rn_N/1e3:>10.1f} kN")
        print(f"  RR = phi*Rn : {self.RR_N/1e3:>10.1f} kN")


def pile_capacity(
    layers: list[LayerInput],
    Ap_mm2: float,
    qp_MPa: float,
    method: str,
) -> PileCapacityResult:
    """Tinh suc chiu tai coc don theo Pt. 58-61.

    layers: danh sach cac lop dat doc theo than coc.
    Ap_mm2: dien tich mui coc (mm^2).
    qp_MPa: suc khang mui don vi (MPa).
    method: ten phuong phap — dung de tra phi_stat tu PHI_STAT.
    """
    Rs = sum(lay.qs_MPa * lay.perimeter_mm * lay.thickness_mm for lay in layers)
    Rp = qp_MPa * Ap_mm2
    Rn = Rs + Rp
    phi = PHI_STAT.get(method, 0.0)
    return PileCapacityResult(
        method=method,
        Rs_N=Rs,
        Rp_N=Rp,
        Rn_N=Rn,
        phi=phi,
        RR_N=phi * Rn,
    )


# ── Vi du minh hoa ──────────────────────────────────────────────────────────

def _demo_alpha_method() -> None:
    """Demo: Coc BTCT 400x400mm, L=20m trong dat set.

    Dia tang don gian: 20m set bao hoa, Su = 15 kN/m2 = 0.015 MPa.
    """
    print("\n" + "=" * 60)
    print("  Vi du: Coc 400x400mm, L=20m, phuong phap alpha")
    print("=" * 60)

    D_mm        = 400.0
    L_mm        = 20_000.0
    perimeter   = 4 * D_mm          # mm — coc vuong
    Ap          = D_mm ** 2          # mm^2
    Su_MPa      = 0.015              # 15 kN/m2

    alpha = alpha_tomlinson(Su_MPa)
    qs    = qs_alpha(Su_MPa, alpha)
    qp    = qp_clay(Su_MPa)

    print(f"  Su        = {Su_MPa*1000:.1f} kN/m2  ({Su_MPa:.4f} MPa)")
    print(f"  alpha     = {alpha:.3f}  (Tomlinson 1980)")
    print(f"  qs        = {qs:.6f} MPa  = {qs*1000:.3f} kN/m2")
    print(f"  qp        = {qp:.6f} MPa  = {qp*1000:.3f} kN/m2")

    layers = [LayerInput(thickness_mm=L_mm, perimeter_mm=perimeter, qs_MPa=qs)]
    result = pile_capacity(layers, Ap_mm2=Ap, qp_MPa=qp, method="alpha")
    result.print_summary()


def _demo_SPT_method() -> None:
    """Demo: Coc ong BTLT 400mm, L=20m trong cat, N160=15 (bua/300mm).

    Dat: cat, N160 = 15, Db = 15m (chieu sau ngam trong tang cat chiu luc).
    """
    print("\n" + "=" * 60)
    print("  Vi du: Coc ong 400mm, L=20m trong cat, SPT N160=15")
    print("=" * 60)

    D_mm  = 400.0
    L_mm  = 20_000.0
    Db_mm = 15_000.0   # ngam 15m trong tang cat chiu luc
    N160  = 15.0
    perimeter = math.pi * D_mm

    qs = qs_SPT_displacement(N160)
    qp = qp_SPT_sand(N160, D_mm, Db_mm, soil_type="sand")
    Ap = math.pi * (D_mm / 2) ** 2

    print(f"  N160      = {N160:.0f} bua/300mm")
    print(f"  qs        = {qs:.6f} MPa  = {qs*1000:.3f} kN/m2")
    print(f"  qp        = {qp:.6f} MPa  = {qp*1000:.3f} kN/m2")

    layers = [LayerInput(thickness_mm=L_mm, perimeter_mm=perimeter, qs_MPa=qs)]
    result = pile_capacity(layers, Ap_mm2=Ap, qp_MPa=qp, method="SPT")
    result.print_summary()


if __name__ == "__main__":
    print("\nTCVN 11823-10:2017 — Suc chiu tai coc dong (Dieu 7.3.8.6)")
    _demo_alpha_method()
    _demo_SPT_method()
    print()
