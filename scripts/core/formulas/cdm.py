"""Công thức module CDM (Trụ đất xi măng) và tính lún cố kết TCCS 41 / TCVN 9403."""
from __future__ import annotations
import math
import sympy as sp

from . import Formula
from .registry import register
from .units import (
    q, H, H_i, a, k, C_c_col, E_c, E_s, E_oed, S_u, mu,
    e_0, C_c, C_s, sigma_v0, sigma_vf, P_C, a_12, KPA_PER_KGF_CM2,
)

# Undefined function rendering "log_{10}(x)" cho đẹp trong LaTeX
log10 = sp.Function(r"\log_{10}")

# ─── S1: Lún đàn hồi khối gia cố CDM ────────────────────────────────
S_1 = sp.Symbol("S_1")
s1 = register(Formula(
    id="cdm-s1",
    lhs=S_1,
    rhs=q * H / (a * E_c + (1 - a) * E_s),
    description="Lún đàn hồi tức thì của khối gia cố CDM (vùng đặt trụ)",
    standard="TCVN 9403:2012 Phụ lục C, công thức C.6",
    unit_lhs="m",
    unit_inputs={"q": "kPa", "H": "m", "a": "(0-1)", "E_c": "kPa", "E_s": "kPa"},
    numeric=lambda q_kPa, H_m, a, Ec_kPa, Es_kPa: (
        q_kPa * H_m / (a * Ec_kPa + (1 - a) * Es_kPa)
    ),
))


# ─── Ec: Mô đun đàn hồi trụ xi măng đất ─────────────────────────────
ec = register(Formula(
    id="cdm-ec",
    lhs=E_c,
    rhs=k * C_c_col,
    description="Mô đun đàn hồi trụ xi măng đất từ qu thiết kế (Cc_col = qu/2)",
    standard="TCVN 9403:2012 §B.5.1 — k thường lấy 75–100",
    unit_lhs="kPa",
    unit_inputs={"k": "-", "C_{c.col}": "kPa"},
    numeric=lambda k_factor, Cc_col_kPa: k_factor * Cc_col_kPa,
))


# ─── Es Bjerrum: Mô đun đất yếu hiệu chỉnh Bjerrum ──────────────────
es_bjerrum = register(Formula(
    id="es-bjerrum",
    lhs=E_s,
    rhs=250 * mu * S_u,
    description=(
        "Mô đun đàn hồi đất yếu, Su từ VST hiệu chỉnh Bjerrum (μ tra Bảng C.1 theo Ip). "
        "KHÔNG áp μ cho Cu_UU lab — chỉ cho Su VST."
    ),
    standard="Mesri & Olson 1974 + TCCS 41:2022 Phụ lục C.3.2 công thức C.5",
    unit_lhs="kPa",
    unit_inputs={"mu": "-", "S_u": "kPa"},
    numeric=lambda mu_val, Su_kPa: 250 * mu_val * Su_kPa,
))


# ─── S2 OC: Lún cố kết phân tố quá cố kết (σ'vf ≤ PC) ──────────────
S_OC = sp.Symbol("S_{i,OC}")
s2_oc = register(Formula(
    id="cdm-s2-oc",
    lhs=S_OC,
    rhs=H_i / (1 + e_0) * C_s * log10(sigma_vf / sigma_v0),
    description="Lún cố kết phân tố OC — tải mới không vượt quá áp lực tiền cố kết",
    standard="Terzaghi 1D — TCCS 41:2022 Phụ lục A",
    unit_lhs="m",
    unit_inputs={
        "H_i": "m", "e_0": "-", "C_s": "-",
        "sigma'_v0": "kPa", "sigma'_vf": "kPa",
    },
    numeric=lambda H_m, e0, Cs, sv0_kPa, svf_kPa: (
        H_m / (1 + e0) * Cs * math.log10(svf_kPa / sv0_kPa)
    ),
))


# ─── S2 NC: Lún cố kết phân tố cố kết bình thường (σ'v0 ≥ PC) ──────
S_NC = sp.Symbol("S_{i,NC}")
s2_nc = register(Formula(
    id="cdm-s2-nc",
    lhs=S_NC,
    rhs=H_i / (1 + e_0) * C_c * log10(sigma_vf / sigma_v0),
    description="Lún cố kết phân tố NC — đất cố kết bình thường (σ'v0 ≥ PC)",
    standard="Terzaghi 1D — TCCS 41:2022 Phụ lục A",
    unit_lhs="m",
    unit_inputs={
        "H_i": "m", "e_0": "-", "C_c": "-",
        "sigma'_v0": "kPa", "sigma'_vf": "kPa",
    },
    numeric=lambda H_m, e0, Cc, sv0_kPa, svf_kPa: (
        H_m / (1 + e0) * Cc * math.log10(svf_kPa / sv0_kPa)
    ),
))


# ─── S2 Cross PC: σ'v0 < PC < σ'vf — hai nhánh OC + NC ────────────
S_cross = sp.Symbol("S_{i,cross}")
s2_cross = register(Formula(
    id="cdm-s2-cross",
    lhs=S_cross,
    rhs=H_i / (1 + e_0) * (
        C_s * log10(P_C / sigma_v0)
        + C_c * log10(sigma_vf / P_C)
    ),
    description="Lún cố kết phân tố cross_PC — tải mới vượt qua áp lực tiền cố kết",
    standard="Terzaghi 1D — TCCS 41:2022 Phụ lục A",
    unit_lhs="m",
    unit_inputs={
        "H_i": "m", "e_0": "-", "C_c": "-", "C_s": "-",
        "sigma'_v0": "kPa", "sigma'_vf": "kPa", "P_C": "kPa",
    },
    numeric=lambda H_m, e0, Cc, Cs, sv0_kPa, svf_kPa, PC_kPa: (
        H_m / (1 + e0) * (
            Cs * math.log10(PC_kPa / sv0_kPa)
            + Cc * math.log10(svf_kPa / PC_kPa)
        )
    ),
))


# ─── Eoed alternative: khi không có Cc, dùng a1-2 ───────────────────
eoed = register(Formula(
    id="cdm-eoed-from-a12",
    lhs=E_oed,
    rhs=(1 + e_0) / a_12 * KPA_PER_KGF_CM2,
    description=(
        "Mô đun nén Oedometer từ hệ số nén a1-2 (cm²/kgf). "
        "Hằng số 98.0665 chuyển kgf/cm² sang kPa. Dùng khi mẫu không có Cc."
    ),
    standard="Định nghĩa Eoed = (1+e0)/a, dạng nén tiêu chuẩn",
    unit_lhs="kPa",
    unit_inputs={"e_0": "-", "a_{1-2}": "cm²/kgf"},
    numeric=lambda e0, a12_cm2kgf: (1 + e0) / a12_cm2kgf * 98.0665,
))


S_eoed = sp.Symbol("S_{i,Eoed}")
delta_sigma = sigma_vf - sigma_v0
s2_eoed = register(Formula(
    id="cdm-s2-eoed",
    lhs=S_eoed,
    rhs=delta_sigma * H_i / E_oed,
    description="Lún cố kết phân tố qua Eoed (khi không có Cc)",
    standard="TCCS 41:2022 Phụ lục A — dạng tuyến tính tương đương",
    unit_lhs="m",
    unit_inputs={
        "sigma'_v0": "kPa", "sigma'_vf": "kPa",
        "H_i": "m", "E_{oed}": "kPa",
    },
    numeric=lambda sv0_kPa, svf_kPa, H_m, Eoed_kPa: (
        (svf_kPa - sv0_kPa) * H_m / Eoed_kPa
    ),
))


# ─── μ Bjerrum: tra bảng C.1 theo Ip (procedural) ──────────────────
# Bảng C.1 — TCCS 41:2022 Phụ lục C
_BJERRUM_TABLE = [
    (10.0, 1.090),
    (20.0, 1.000),
    (30.0, 0.925),
    (40.0, 0.860),
    (50.0, 0.800),
    (60.0, 0.750),
    (70.0, 0.700),
]


def _bjerrum_mu(Ip: float | None) -> float:
    """Tra μ theo Ip, nội suy bậc nhất; clamp đầu/cuối; Ip≤0/None → 1.0."""
    if Ip is None or Ip <= 0:
        return 1.0
    if Ip <= _BJERRUM_TABLE[0][0]:
        return _BJERRUM_TABLE[0][1]
    if Ip >= _BJERRUM_TABLE[-1][0]:
        return _BJERRUM_TABLE[-1][1]
    for (x1, y1), (x2, y2) in zip(_BJERRUM_TABLE, _BJERRUM_TABLE[1:]):
        if x1 <= Ip <= x2:
            return y1 + (y2 - y1) * (Ip - x1) / (x2 - x1)
    return 1.0


bjerrum = register(Formula(
    id="bjerrum-mu",
    description=(
        "Hệ số hiệu chỉnh Bjerrum μ cho Su VST, nội suy theo Ip từ Bảng C.1. "
        "Áp dụng: c_u = μ · S_u. Clamp đầu/cuối; Ip không có → μ=1.0."
    ),
    standard="TCCS 41:2022 Phụ lục C.3.2, Bảng C.1",
    unit_lhs="-",
    unit_inputs={"I_p": "%"},
    numeric=_bjerrum_mu,
    latex_override=(
        r"\mu = f(I_p) \quad "
        r"\text{tra Bảng C.1: } "
        r"I_p \in \{10,20,30,40,50,60,70\} "
        r"\to \mu \in \{1{,}09,\, 1{,}00,\, 0{,}925,\, 0{,}86,\, 0{,}80,\, 0{,}75,\, 0{,}70\}"
    ),
))


# Re-export numeric callables (tiện import)
def s1_numeric(q_kPa: float, H_m: float, a: float, Ec_kPa: float, Es_kPa: float) -> float:
    """S1 lún đàn hồi khối gia cố [m]."""
    return s1.numeric(q_kPa=q_kPa, H_m=H_m, a=a, Ec_kPa=Ec_kPa, Es_kPa=Es_kPa)


def ec_numeric(k_factor: float, Cc_col_kPa: float) -> float:
    """Ec = k × Cc_col [kPa]."""
    return ec.numeric(k_factor=k_factor, Cc_col_kPa=Cc_col_kPa)


def es_bjerrum_numeric(mu_val: float, Su_kPa: float) -> float:
    """Es = 250 × μ × Su [kPa]."""
    return es_bjerrum.numeric(mu_val=mu_val, Su_kPa=Su_kPa)


def s2_oc_numeric(H_m: float, e0: float, Cs: float, sv0_kPa: float, svf_kPa: float) -> float:
    return s2_oc.numeric(H_m=H_m, e0=e0, Cs=Cs, sv0_kPa=sv0_kPa, svf_kPa=svf_kPa)


def s2_nc_numeric(H_m: float, e0: float, Cc: float, sv0_kPa: float, svf_kPa: float) -> float:
    return s2_nc.numeric(H_m=H_m, e0=e0, Cc=Cc, sv0_kPa=sv0_kPa, svf_kPa=svf_kPa)


def s2_cross_numeric(
    H_m: float, e0: float, Cc: float, Cs: float,
    sv0_kPa: float, svf_kPa: float, PC_kPa: float,
) -> float:
    return s2_cross.numeric(
        H_m=H_m, e0=e0, Cc=Cc, Cs=Cs,
        sv0_kPa=sv0_kPa, svf_kPa=svf_kPa, PC_kPa=PC_kPa,
    )


def eoed_from_a12_numeric(e0: float, a12_cm2kgf: float) -> float:
    return eoed.numeric(e0=e0, a12_cm2kgf=a12_cm2kgf)


def s2_eoed_numeric(sv0_kPa: float, svf_kPa: float, H_m: float, Eoed_kPa: float) -> float:
    return s2_eoed.numeric(sv0_kPa=sv0_kPa, svf_kPa=svf_kPa, H_m=H_m, Eoed_kPa=Eoed_kPa)


def bjerrum_mu(Ip: float | None) -> float:
    return bjerrum.numeric(Ip)
