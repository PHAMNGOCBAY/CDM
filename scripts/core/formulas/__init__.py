"""
core.formulas — Single-source-of-truth cho công thức kỹ thuật toàn dự án.

Mỗi công thức định nghĩa MỘT LẦN ở đây dưới dạng SymPy expression + numeric callable.
Code Python import numeric callable (không hardcode lại biểu thức).
File MD đánh marker `<!-- AUTO-FORMULA: <id> -->...<!-- /AUTO-FORMULA -->`
→ chạy `python scripts/regen_docs.py` để tự render LaTeX vào MD.

Pattern:
    from core.formulas.cdm import s1_numeric
    S1 = s1_numeric(q_kPa=40.8, H_m=23.0, a=0.155, Ec_kPa=40000, Es_kPa=2800)

Validator: `python scripts/check_formula_sync.py` so sánh code ↔ registry ↔ MD,
block commit nếu drift.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional, Mapping
import sympy as sp


@dataclass(frozen=True)
class Formula:
    """Một công thức kỹ thuật đăng ký trong registry."""
    id: str
    description: str
    standard: str
    lhs: Optional[sp.Symbol] = None
    rhs: Optional[sp.Expr] = None
    unit_lhs: str = ""
    unit_inputs: Mapping[str, str] = field(default_factory=dict)
    numeric: Optional[Callable] = None
    latex_override: Optional[str] = None

    @property
    def latex(self) -> str:
        """LaTeX chuỗi không có dấu $."""
        if self.latex_override:
            return self.latex_override
        if self.lhs is None or self.rhs is None:
            raise ValueError(f"Formula {self.id!r} không có dạng symbolic.")
        return f"{sp.latex(self.lhs)} = {sp.latex(self.rhs)}"

    @property
    def latex_display(self) -> str:
        """Khối hiển thị $$...$$."""
        return f"$${self.latex}$$"

    def equation(self) -> sp.Eq:
        if self.lhs is None or self.rhs is None:
            raise ValueError(f"Formula {self.id!r} không có dạng symbolic.")
        return sp.Eq(self.lhs, self.rhs)

    def evaluate(self, **kwargs) -> float:
        """Gọi numeric callable với kwargs."""
        if self.numeric is None:
            raise ValueError(f"Formula {self.id!r} không có numeric callable.")
        return self.numeric(**kwargs)


# Re-export registry helpers
from .registry import register, get, all_formulas, ids  # noqa: E402,F401
