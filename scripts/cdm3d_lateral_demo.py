"""cdm3d_lateral_demo — Xuat bieu do chuyen vi ngang Ux(z) tai vi tri co coc CDM,
tu ket qua giai doan thi cong + tai lech tam da giai (xem ccx_input.py, cot_forces.py).

Chay: python scripts/cdm3d_lateral_demo.py [zone_code] [stage_index]
  zone_code: KE/BXN/NHC (mac dinh KE)
  stage_index: -1 (giai doan cuoi, mac dinh) hoac 0..N (0=dummy, 1=GD0, 2=GD1, 3..=GD2..N)

Yeu cau: da chay results/cdm3d/<zone>.frd thanh cong (xem ccx_input.write_ccx_inp +
run_ccx.solve — mac dinh use_model_change=True nen luon co chuoi giai doan).
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

from cdm3d import column_forces, params_io, postprocess


def main(zone_code: str = "KE", stage_index: int = -1) -> None:
    params = params_io.build_default_params(zone_code)
    frd_path = _ROOT / "results" / "cdm3d" / f"{zone_code}_staged.frd"
    if not frd_path.exists():
        frd_path = _ROOT / "results" / "cdm3d" / f"{zone_code}.frd"
    if not frd_path.exists():
        raise FileNotFoundError(
            f"Khong tim thay {frd_path} — phai giai CalculiX truoc (xem "
            f"ccx_input.write_ccx_inp() + run_ccx.solve())."
        )

    vtus = postprocess.convert_frd_to_vtu_all_stages(frd_path)
    vtu = vtus[stage_index]
    print(f"[cdm3d] Dung giai doan {stage_index} / {len(vtus)}: {vtu.name}")

    z_top, z_bot = params.column.z_top, params.column.z_bot
    n_x, spacing = params.column.n_x, params.column.spacing_m
    x_edge = ((n_x - 1) * spacing) / 2.0

    columns = {
        f"Cot +X ({x_edge:.1f}, 0) - phia tai cao": (x_edge, 0.0),
        "Cot giua (0, 0)": (0.0, 0.0),
        f"Cot -X ({-x_edge:.1f}, 0) - phia tai thap": (-x_edge, 0.0),
    }
    profiles = {
        label: column_forces.extract_lateral_profile(vtu, xy, z_top, z_bot, n_levels=25)
        for label, xy in columns.items()
    }
    for label, prof in profiles.items():
        print(f"  {label}: Ux dinh={prof['ux_mm'][0]:.2f}mm, min={min(prof['ux_mm']):.2f}mm")

    out_png = _ROOT / "images" / f"cdm3d_{zone_code}_lateral_u_profile.png"
    column_forces.plot_lateral_profiles(
        profiles, out_png,
        title=f"Chuyen vi ngang Ux theo cao do — {zone_code}, giai doan {vtu.stem}",
    )
    print(f"[cdm3d] Da xuat bieu do: {out_png}")


if __name__ == "__main__":
    args = sys.argv[1:]
    zone = args[0] if len(args) > 0 else "KE"
    stage = int(args[1]) if len(args) > 1 else -1
    main(zone, stage)
