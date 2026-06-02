"""Run Wave 2 + Task M for all 5 zones (heavy compute, run in background).

Tasks:
- PA-A (cdm_alternative_design.compute_pa_a_for_zone) — 5 zones × 1 ΔS=10
- PA-B (compute_pa_b_for_zone) — 5 zones × 1 L_max=30 × 1 ΔS=30
- Task M: save_qtt_grid_lc — 6 ΔS × 162 grid (QTT only)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from cdm_alternative_design import (  # type: ignore
    compute_pa_a_for_zone, compute_pa_b_for_zone,
)
from save_cdm_zone_results import save_qtt_grid_lc  # type: ignore


def run_all() -> None:
    DBs = [Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite"),
           Path("data/TTHC.sqlite")]
    ZONES = ["QTT", "BXN", "NHC", "KE_park", "KE_levee"]
    print("=" * 60)
    print("Wave 2 + Task M — ALL ZONES")
    print("=" * 60)
    for db in DBs:
        if not db.exists():
            continue
        print(f"\nDB: {db.parent.name}")
        # Task M: grid_lc for QTT (6 ΔS)
        t0 = time.time()
        n = save_qtt_grid_lc(db_path=db)
        print(f"  Task M (QTT grid 6 ΔS): {n} rows in {time.time() - t0:.0f}s")

        for z in ZONES:
            print(f"\n  Zone {z}:")
            t0 = time.time()
            na = compute_pa_a_for_zone(z, delta_S_targets_cm=(10.0,), db_path=db)
            print(f"    PA-A (ΔS=10): {na} rows in {time.time() - t0:.0f}s")
            t0 = time.time()
            nb = compute_pa_b_for_zone(
                z, L_max_values_m=(30.0,),
                delta_S_targets_cm=(30.0,), db_path=db,
            )
            print(f"    PA-B (L=30,ΔS=30): {nb} rows in {time.time() - t0:.0f}s")
    print("\nDONE all 5 zones × 2 DBs")


if __name__ == "__main__":
    run_all()
