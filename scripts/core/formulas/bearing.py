"""Công thức sức chịu tải cọc — NT2 α-method cho sét theo TCVN 11823-10:2017."""
from __future__ import annotations
import sympy as sp

from . import Formula
from .registry import register
from .units import alpha, c_u, P, L, A_p

# ─── NT2 Rs α-method: ma sát thân cọc trong sét ─────────────────────
R_s = sp.Symbol("R_s")
nt2_rs_alpha = register(Formula(
    id="nt2-rs-alpha",
    lhs=R_s,
    rhs=alpha * c_u * P * L,
    description=(
        "Sức kháng ma sát thân cọc đóng trong sét (α-method Tomlinson). "
        "c_u = μ·Su (Bjerrum). KHÔNG tính ma sát qua đất đắp."
    ),
    standard="TCVN 11823-10:2017 Điều 7.3.8.6.2; Tomlinson 1980",
    unit_lhs="kN",
    unit_inputs={"alpha": "-", "c_u": "kPa", "P": "m", "L": "m"},
    numeric=lambda alpha_val, cu_kPa, P_m, L_m: alpha_val * cu_kPa * P_m * L_m,
))


# ─── NT2 Rp: sức kháng mũi cọc trong sét (Nc = 9) ──────────────────
R_p = sp.Symbol("R_p")
nt2_rp_clay = register(Formula(
    id="nt2-rp-clay",
    lhs=R_p,
    rhs=9 * c_u * A_p,
    description="Sức kháng mũi cọc đóng trong sét — Nc = 9 (cọc sâu)",
    standard="TCVN 11823-10:2017 Điều 7.3.8.6.2; Skempton",
    unit_lhs="kN",
    unit_inputs={"c_u": "kPa", "A_p": "m²"},
    numeric=lambda cu_kPa, Ap_m2: 9 * cu_kPa * Ap_m2,
))


def nt2_rs_alpha_numeric(alpha_val: float, cu_kPa: float, P_m: float, L_m: float) -> float:
    """Rs = α·c_u·P·L [kN]."""
    return nt2_rs_alpha.numeric(alpha_val=alpha_val, cu_kPa=cu_kPa, P_m=P_m, L_m=L_m)


def nt2_rp_clay_numeric(cu_kPa: float, Ap_m2: float) -> float:
    """Rp = 9·c_u·A_p [kN]."""
    return nt2_rp_clay.numeric(cu_kPa=cu_kPa, Ap_m2=Ap_m2)
