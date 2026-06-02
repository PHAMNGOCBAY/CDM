"""Registry trung tâm của Formula — dict[id → Formula]."""
from __future__ import annotations
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from . import Formula

_REGISTRY: Dict[str, "Formula"] = {}


def register(f: "Formula") -> "Formula":
    if f.id in _REGISTRY:
        raise ValueError(f"Trùng FORMULA-ID: {f.id!r}")
    _REGISTRY[f.id] = f
    return f


def get(formula_id: str) -> "Formula":
    if formula_id not in _REGISTRY:
        raise KeyError(
            f"FORMULA-ID {formula_id!r} chưa đăng ký. "
            f"Đã có: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[formula_id]


def all_formulas() -> Dict[str, "Formula"]:
    """Bản sao của registry."""
    return dict(_REGISTRY)


def ids() -> List[str]:
    return sorted(_REGISTRY)


def _load_all_modules() -> None:
    """Import tất cả module formula để đăng ký vào registry."""
    from . import cdm, bearing  # noqa: F401
