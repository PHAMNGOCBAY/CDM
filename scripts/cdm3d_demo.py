"""cdm3d_demo — Chay toan bo pipeline mo hinh 3D CDM-dat nen: Gmsh (hinh hoc + luoi)
-> CalculiX (giai, neu co ccx.exe) -> PNG + GIF (anh 3D luoi + anh ket qua).

Chay: python scripts/cdm3d_demo.py [zone_code]   (mac dinh zone_code=KE)

Ket qua ghi vao:
  results/cdm3d/<zone>.msh / .inp / .frd / .vtu
  images/cdm3d_<zone>_mesh_3d.png|.gif       (luon co — khong can ccx.exe)
  images/cdm3d_<zone>_result_U_3d.png|.gif   (chi co neu da giai CalculiX thanh cong)

GIF xoay 360 do quanh truc Z (24 khung hinh, 10 fps) — de thay ro cau truc khong
gian 3D (nhom tru + tuong tac voi dat) ma anh PNG tinh mot goc nhin khong the hien
duoc. Ton them ~15-30s render moi file — co the tat bang --no-gif.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

import gmsh

from cdm3d import ccx_input, geometry, mesh_gmsh, params_io, postprocess, run_ccx


def main(zone_code: str = "KE", export_gif: bool = True) -> None:
    out_dir = _ROOT / "results" / "cdm3d"
    images_dir = _ROOT / "images"

    # === BUOC 1: THAM SO ===
    params = params_io.build_default_params(zone_code)
    params_io.print_warnings(params)

    # === BUOC 2: HINH HOC + BUOC 3: LUOI (Gmsh) ===
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        geometry.build_geometry(params)
        mesh_gmsh.generate_mesh(params, element_order=1)
        stats = mesh_gmsh.mesh_stats()
        print(f"[cdm3d] Luoi: {stats['n_nodes']} nut, {stats['n_elements_3d']} phan tu 3D")
        msh_path = mesh_gmsh.export_mesh(out_dir / f"{zone_code}.msh")
    finally:
        gmsh.finalize()

    # === BUOC 4: ANH 3D LUOI (luon xuat duoc, khong can solver) ===
    mesh_png = postprocess.render_mesh_png(msh_path, images_dir / f"cdm3d_{zone_code}_mesh_3d.png")
    print(f"[cdm3d] Da xuat anh luoi 3D: {mesh_png}")
    if export_gif:
        mesh_gif = postprocess.render_mesh_gif(msh_path, images_dir / f"cdm3d_{zone_code}_mesh_3d.gif")
        print(f"[cdm3d] Da xuat GIF xoay luoi 3D: {mesh_gif}")

    # === BUOC 5: SINH FILE DAU VAO CALCULIX ===
    inp_path = ccx_input.write_ccx_inp(msh_path, out_dir / f"{zone_code}.inp", params)
    print(f"[cdm3d] Da sinh file dau vao CalculiX: {inp_path}")

    # === BUOC 6: GIAI (CHI KHI CO ccx.exe) ===
    try:
        frd_path = run_ccx.solve(inp_path)
        print(f"[cdm3d] Da giai xong: {frd_path}")
    except run_ccx.CcxNotFoundError as e:
        print(f"[cdm3d] BO QUA buoc giai — {e}")
        return
    except RuntimeError as e:
        print(f"[cdm3d] LOI khi giai CalculiX — {e}")
        return

    # === BUOC 7: ANH 3D KET QUA ===
    vtu_path = postprocess.convert_frd_to_vtu(frd_path)
    result_png = postprocess.render_results_png(
        vtu_path, images_dir / f"cdm3d_{zone_code}_result_U_3d.png",
        field="U", warp_factor=20.0,
    )
    print(f"[cdm3d] Da xuat anh ket qua 3D: {result_png}")
    if export_gif:
        result_gif = postprocess.render_results_gif(
            vtu_path, images_dir / f"cdm3d_{zone_code}_result_U_3d.gif",
            field="U", warp_factor=20.0,
        )
        print(f"[cdm3d] Da xuat GIF xoay ket qua 3D: {result_gif}")


if __name__ == "__main__":
    args = sys.argv[1:]
    no_gif = "--no-gif" in args
    positional = [a for a in args if not a.startswith("--")]
    zone = positional[0] if positional else "KE"
    main(zone, export_gif=not no_gif)
