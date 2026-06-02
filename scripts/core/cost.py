"""
scripts/core/cost.py — Helper chi phí vật liệu (đọc cost model từ JSON).

Single source of truth: data/cost_model.json
Mọi consumer (Word builder, chart, UI app) phải import từ đây thay vì hardcode.
"""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict

_ROOT = Path(__file__).resolve().parents[2]
_COST_FILE = _ROOT / "data" / "cost_model.json"


@lru_cache(maxsize=1)
def _load_cost_model() -> Dict:
    """Load cost model JSON — cached."""
    if not _COST_FILE.exists():
        raise FileNotFoundError(f"Cost model JSON không tồn tại: {_COST_FILE}")
    return json.loads(_COST_FILE.read_text(encoding="utf-8"))


def reload_cost_model() -> Dict:
    """Force reload (bỏ cache) — dùng sau khi sửa JSON."""
    _load_cost_model.cache_clear()
    return _load_cost_model()


def get_material(key: str) -> Dict:
    """Trả về dict vật liệu (cat_he, dem_cat_xm_base, ao_duong...)."""
    cm = _load_cost_model()
    if key not in cm["materials"]:
        raise KeyError(f"Vật liệu '{key}' không có. "
                       f"Có sẵn: {list(cm['materials'].keys())}")
    return cm["materials"][key]


def cushion_cost_per_m2(Hse_m: float, q_uckse_kPa: float) -> Dict:
    """Chi phí lớp đệm + cát He trên 1 m² mặt nền.

    Cấu tạo: He cát thường + Hse đệm cát-XM (q_uckse thay đổi → giá thay đổi)
    Ràng buộc: He + Hse = sigma_h_total

    Returns dict {cost_total_vnd, cost_He_vnd, cost_Hse_vnd, He_m, breakdown}
    """
    cm = _load_cost_model()
    sigma_h = cm["constraints"]["sigma_h_total_m"]
    He_m = max(0.0, sigma_h - Hse_m)

    cost_he_per_m3 = cm["materials"]["cat_he"]["unit_cost_vnd_per_m3"]
    cost_base_hse = cm["materials"]["dem_cat_xm_base"]["unit_cost_vnd_per_m3"]
    q_base = cm["materials"]["dem_cat_xm_base"]["q_uckse_base_kPa"]
    delta_per_kPa = cm["delta_costs"]["dem_cat_xm_per_kPa"]["value_vnd_per_m3_per_kPa"]

    # Chi phí He
    c_he = He_m * cost_he_per_m3
    # Chi phí Hse: đơn giá base + delta theo q_uckse
    unit_hse = cost_base_hse + (q_uckse_kPa - q_base) * delta_per_kPa
    c_hse = Hse_m * unit_hse

    return {
        "cost_total_vnd": c_he + c_hse,
        "cost_He_vnd": c_he,
        "cost_Hse_vnd": c_hse,
        "He_m": He_m,
        "Hse_m": Hse_m,
        "q_uckse_kPa": q_uckse_kPa,
        "unit_He_vnd_per_m3": cost_he_per_m3,
        "unit_Hse_vnd_per_m3": unit_hse,
    }


def cushion_cost_delta_pct(Hse_m: float, q_uckse_kPa: float,
                            Hse_base: float = 0.40,
                            q_uckse_base: float = 600.0) -> float:
    """Δ chi phí (%) so với cấu hình baseline (mặc định Hse=0.40m, q=600 kPa)."""
    c0 = cushion_cost_per_m2(Hse_base, q_uckse_base)["cost_total_vnd"]
    c1 = cushion_cost_per_m2(Hse_m, q_uckse_kPa)["cost_total_vnd"]
    return (c1 - c0) / c0 * 100.0 if c0 > 0 else 0.0


# ════════ DEMO ════════
if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 60)
    print("Cost model TTHC — verify")
    print("=" * 60)
    cm = _load_cost_model()
    print(f"Nguồn: data/cost_model.json (updated {cm['_meta']['updated']})")
    print()
    print(f"{'Hse':>6s} {'q':>6s} {'He':>6s} {'CP TB':>9s} {'Δ%':>7s}")
    print("-" * 40)
    for Hse, q in [(0.40, 600), (0.40, 800), (0.55, 600), (0.30, 1000)]:
        r = cushion_cost_per_m2(Hse, q)
        d = cushion_cost_delta_pct(Hse, q)
        print(f"{Hse:>6.2f} {q:>6.0f} {r['He_m']:>6.2f} "
              f"{r['cost_total_vnd']/1e6:>8.2f}M {d:>+6.1f}%")
