"""cdm3d.postprocess — Xuat anh 3D *.png/*.gif tu luoi (truoc khi giai) va tu ket qua
CalculiX (sau khi giai, doc file .frd qua ccx2paraview -> .vtu -> pyvista).

Dung pyvista (VTK) de render offscreen. Neu may khong co GPU/driver OpenGL hop le,
ham se nem loi ro rang thay vi treo may — bao nguoi dung kiem tra driver.

PNG: 1 goc nhin isometric tinh. GIF: xoay 360 do quanh truc Z (thay ro cau truc
khong gian 3D — nhom tru + tuong tac voi dat — ma anh tinh khong the hien duoc).
"""
from __future__ import annotations

import re
from pathlib import Path

import meshio
import numpy as np
import pyvista as pv

_GROUP_COLORS = {
    "SOIL_dat_dap": ("#D2B48C", 0.35),
    "SOIL_dat_yeu": ("#8FA6C7", 0.30),
    "SOIL_lop_cung": ("#5B6B7A", 0.22),
    "CDM_COLUMN": ("#1565C0", 1.0),
}
_DEFAULT_COLOR = ("#AAAAAA", 0.3)


def _load_tetra_groups(msh_path: Path) -> tuple[np.ndarray, list[tuple[np.ndarray, str]]]:
    """Doc file .msh (gmsh) -> tra ve (points, [(cells_n4, group_name), ...])
    chi lay phan tu tetra bac 1 (4 nut) — bo qua tetra10 neu co (dung cho C3D10)."""
    m = meshio.read(str(msh_path))
    tag_to_name: dict[int, str] = {}
    for name, (tag, dim) in m.field_data.items():
        if dim == 3:
            tag_to_name[tag] = name

    groups: dict[str, list[np.ndarray]] = {}
    for i, block in enumerate(m.cells):
        if block.type != "tetra":
            continue
        tags = m.cell_data.get("gmsh:physical", [None] * len(m.cells))[i]
        if tags is None:
            continue
        for tag in np.unique(tags):
            name = tag_to_name.get(int(tag), f"tag_{tag}")
            mask = tags == tag
            groups.setdefault(name, []).append(block.data[mask])

    out = [(np.vstack(v), name) for name, v in groups.items()]
    return m.points, out


def _build_mesh_plotter(msh_path: Path, window_size: tuple[int, int]) -> pv.Plotter:
    """Dung chung cho render_mesh_png va render_mesh_gif — ve luoi theo nhom vat
    lieu (dat ban trong suot, tru CDM mau xanh dam), chua set camera/screenshot."""
    points, groups = _load_tetra_groups(Path(msh_path))
    if not groups:
        raise ValueError(f"Khong doc duoc nhom phan tu tetra nao tu {msh_path}")

    plotter = pv.Plotter(off_screen=True, window_size=list(window_size))
    plotter.set_background("white")

    for cells, name in groups:
        n_cells = cells.shape[0]
        conn = np.hstack([np.full((n_cells, 1), 4, dtype=np.int64), cells]).ravel()
        cell_types = np.full(n_cells, pv.CellType.TETRA, dtype=np.uint8)
        grid = pv.UnstructuredGrid(conn, cell_types, points)
        color, opacity = _GROUP_COLORS.get(name, _DEFAULT_COLOR)
        surf = grid.extract_surface(algorithm="dataset_surface")
        plotter.add_mesh(surf, color=color, opacity=opacity,
                          show_edges=(name == "CDM_COLUMN"), edge_color="#0d3d6b",
                          label=name)

    plotter.add_legend(bcolor="white")
    plotter.add_axes()
    return plotter


def _top_surface_mesh(msh_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Doc luoi tam giac be mat TOP_SOIL + TOP_COLUMN (khong phai chi node
    membership nhu nsets — can CONNECTIVITY de dung PolyData ve mat mau)."""
    m = meshio.read(str(msh_path))
    tag_to_name = {tag: name for name, (tag, dim) in m.field_data.items() if dim == 2}
    faces = []
    for i, block in enumerate(m.cells):
        if block.type != "triangle":
            continue
        tags = m.cell_data.get("gmsh:physical", [None] * len(m.cells))[i]
        if tags is None:
            continue
        for j in range(block.data.shape[0]):
            if tag_to_name.get(int(tags[j])) in ("TOP_SOIL", "TOP_COLUMN"):
                faces.append(block.data[j])
    return m.points, np.array(faces)


def render_load_png(msh_path: Path, params, stage, out_png: Path,
                     window_size: tuple[int, int] = (1600, 1200)) -> Path:
    """Ve tai trong q(x,y) TAC DUNG tren mat tren (mau theo cuong do kPa, thang mau
    YlOrRd) chong len khoi luoi dat/tru (ban trong suot) de de hinh dung vi tri va
    vung co/khong co tai. Dung LAI cong thuc trong ccx_input.py (khong tinh rieng)
    de dam bao nhat quan 100% voi tai thuc te da giai."""
    from . import ccx_input as _ccx

    msh_path = Path(msh_path)
    all_points, faces = _top_surface_mesh(msh_path)
    if faces.size == 0:
        raise ValueError(f"Khong tim thay tam giac TOP_SOIL/TOP_COLUMN trong {msh_path}")

    B_x, B_y = params.domain_x_m(), params.domain_y_m()
    axis_col = 0 if stage.ecc_axis == "x" else 1
    B = B_x if stage.ecc_axis == "x" else B_y
    pos = all_points[:, axis_col]

    if stage.load_footprint == "full":
        e_use, _ = _ccx.validate_eccentricity(stage.eccentricity_m, B)
        q = _ccx._eccentric_pressure(pos, stage.q_avg_kPa, e_use, B)
    else:
        sign = 1.0 if stage.load_footprint == "half_pos" else -1.0
        q = np.where(sign * pos >= 0, stage.q_avg_kPa, 0.0)

    n_faces = faces.shape[0]
    face_conn = np.hstack([np.full((n_faces, 1), 3, dtype=np.int64), faces]).ravel()
    load_surf = pv.PolyData(all_points, face_conn)
    load_surf["q_kPa"] = q

    plotter = _build_mesh_plotter(msh_path, window_size)
    plotter.add_mesh(load_surf, scalars="q_kPa", cmap="YlOrRd",
                      clim=(0.0, max(stage.q_avg_kPa * 1.05, float(q.max()), 1e-6)),
                      show_edges=False, opacity=0.95,
                      scalar_bar_args={"title": "q (kPa)"})

    plotter.camera_position = "iso"
    plotter.camera.azimuth += 25
    plotter.camera.elevation += 15
    plotter.enable_parallel_projection()
    plotter.add_text(f"Tai trong: {stage.name}\nq_avg={stage.q_avg_kPa:.1f} kPa, "
                      f"footprint={stage.load_footprint}, e={stage.eccentricity_m}m",
                      font_size=10, position="upper_left")

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plotter.screenshot(str(out_png))
    plotter.close()
    return out_png


def render_mesh_png(msh_path: Path, out_png: Path,
                     window_size: tuple[int, int] = (1600, 1200)) -> Path:
    """Ve luoi 3D theo nhom vat lieu, goc nhin isometric tinh, luu PNG."""
    plotter = _build_mesh_plotter(msh_path, window_size)
    plotter.camera_position = "iso"
    plotter.camera.azimuth += 25
    plotter.camera.elevation += 15
    plotter.enable_parallel_projection()

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plotter.screenshot(str(out_png))
    plotter.close()
    return out_png


def render_mesh_gif(msh_path: Path, out_gif: Path,
                     window_size: tuple[int, int] = (1200, 900),
                     n_points: int = 36, framerate: int = 12) -> Path:
    """Nhu render_mesh_png nhung xoay 360 do quanh truc Z, luu GIF."""
    plotter = _build_mesh_plotter(msh_path, window_size)
    plotter.camera_position = "iso"
    plotter.enable_parallel_projection()
    return _orbit_gif(plotter, out_gif, n_points=n_points, framerate=framerate)


def _orbit_gif(plotter: pv.Plotter, out_gif: Path, n_points: int = 36,
                framerate: int = 12) -> Path:
    """Sinh quy dao xoay 360 do quanh truc Z (viewup) quanh mo hinh dang co trong
    `plotter`, ghi tung khung hinh vao GIF. Dong plotter khi xong."""
    out_gif = Path(out_gif)
    out_gif.parent.mkdir(parents=True, exist_ok=True)
    b = plotter.bounds  # (xmin, xmax, ymin, ymax, zmin, zmax)
    shift = (b[5] - b[4]) / 2.0
    path = plotter.generate_orbital_path(n_points=n_points, shift=shift,
                                          factor=3.5, viewup=[0, 0, 1])
    plotter.open_gif(str(out_gif), fps=framerate)
    plotter.orbit_on_path(path, write_frames=True, viewup=[0, 0, 1])
    plotter.close()
    return out_gif


def _patch_ccx2paraview_principal_stress() -> None:
    """ccx2paraview (v3.2.0) dung np.linalg.eigvals (thuat toan tong quat) cho tensor
    UNG SUAT DOI XUNG — sai so lam tron co the sinh tri rieng PHUC (imaginary ~1e-15),
    lam sorted() bao TypeError 'complex' khong so sanh duoc (da gap thuc te khi chay
    KE.frd). Fix: doi sang np.linalg.eigvalsh (thuat toan danh rieng cho ma tran doi
    xung — luon tra ve so thuc). Vá tai runtime, KHONG sua file thu vien da cai."""
    from ccx2paraview import common as _c

    def _calc_principal_real(self, b):
        b1 = _c.NodalResultsBlock()
        b1.name = b.name + "_Principal"
        b1.components = ("Min", "Mid", "Max", "Worst")
        b1.ncomps = len(b1.components)
        b1.inc = b.inc
        b1.step = b.step
        for node_num in b.node_block.get_node_numbers():
            data = b.results[node_num]
            t_xx, t_yy, t_zz, t_xy, t_yz, t_xz = data[0], data[1], data[2], data[3], data[4], data[5]
            tensor = np.array([[t_xx, t_xy, t_xz], [t_xy, t_yy, t_yz], [t_xz, t_yz, t_zz]])
            eigenvalues = sorted(np.linalg.eigvalsh(tensor).tolist())
            if abs(eigenvalues[0]) > abs(eigenvalues[-1]):
                eigenvalues.append(eigenvalues[0])
            else:
                eigenvalues.append(eigenvalues[-1])
            b1.results[node_num] = eigenvalues
        b1.get_some_log()
        return b1

    _c.FRD.calculate_principal = _calc_principal_real


def convert_frd_to_vtu(frd_path: Path) -> Path:
    """Goi ccx2paraview de chuyen ket qua CalculiX (.frd) sang .vtu (ParaView/pyvista
    doc duoc). Yeu cau da chay xong ccx (xem run_ccx.py)."""
    _patch_ccx2paraview_principal_stress()
    from ccx2paraview import Converter

    frd_path = Path(frd_path)
    if not frd_path.exists():
        raise FileNotFoundError(
            f"Khong tim thay {frd_path} — phai chay CalculiX (run_ccx.solve) truoc."
        )
    Converter(str(frd_path), ["vtu"]).run()
    vtu_path = frd_path.with_suffix(".vtu")
    if not vtu_path.exists():
        # ccx2paraview co the xuat *_frd.vtu neu co nhieu step — lay file moi nhat
        candidates = _numbered_vtu_files(frd_path)
        if not candidates:
            raise FileNotFoundError(f"ccx2paraview khong sinh ra file .vtu cho {frd_path}")
        vtu_path = candidates[-1]
    return vtu_path


def _numbered_vtu_files(frd_path: Path) -> list[Path]:
    """Liet ke <stem>.<N>.vtu theo dung thu tu SO (khong phai chuoi — ".10" < ".2"
    theo alphabet se sai) — ccx2paraview dat ten nay khi .frd co nhieu buoc/*STEP."""
    numbered = []
    for p in frd_path.parent.glob(f"{frd_path.stem}.*.vtu"):
        m = re.fullmatch(rf"{re.escape(frd_path.stem)}\.(\d+)\.vtu", p.name)
        if m:
            numbered.append((int(m.group(1)), p))
    numbered.sort(key=lambda t: t[0])
    return [p for _, p in numbered]


def convert_frd_to_vtu_all_stages(frd_path: Path) -> list[Path]:
    """Nhu convert_frd_to_vtu() nhung tra ve TOAN BO danh sach .vtu theo dung thu
    tu giai doan thi cong (GD0, GD1, GD2..N — xem ccx_input.py docstring chuoi
    giai doan). Neu .frd chi co 1 buoc (khong staged), tra ve list 1 phan tu."""
    _patch_ccx2paraview_principal_stress()
    from ccx2paraview import Converter

    frd_path = Path(frd_path)
    if not frd_path.exists():
        raise FileNotFoundError(
            f"Khong tim thay {frd_path} — phai chay CalculiX (run_ccx.solve) truoc."
        )
    Converter(str(frd_path), ["vtu"]).run()

    single = frd_path.with_suffix(".vtu")
    if single.exists():
        return [single]

    numbered = _numbered_vtu_files(frd_path)
    if not numbered:
        raise FileNotFoundError(f"ccx2paraview khong sinh ra file .vtu nao cho {frd_path}")
    return numbered


def _build_results_plotter(vtu_path: Path, field: str, component: int | str,
                            warp_factor: float, window_size: tuple[int, int],
                            clim: tuple[float, float] | None = None) -> pv.Plotter:
    """Dung chung cho render_results_png va render_results_gif — chua set camera/
    screenshot. field: ten truong ('U' chuyen vi, 'S' ung suat...). warp_factor > 0:
    phong dai chuyen vi de thay ro dang bien dang. clim: co dinh thang mau (vd de
    so sanh nhieu giai doan tren cung 1 thang — xem render_all_stage_pngs); None =
    tu dong theo min/max cua file nay."""
    grid = pv.read(str(vtu_path))
    if field not in grid.point_data:
        available = list(grid.point_data.keys())
        raise KeyError(f"Khong co truong '{field}' trong ket qua — cac truong co: {available}")

    plot_grid = grid.warp_by_vector(field, factor=warp_factor) if warp_factor > 0 else grid

    plotter = pv.Plotter(off_screen=True, window_size=list(window_size))
    plotter.set_background("white")
    plotter.add_mesh(plot_grid, scalars=field, component=(None if component == "magnitude" else component),
                      cmap="turbo", clim=clim, show_edges=False, scalar_bar_args={"title": field})
    plotter.add_axes()
    return plotter


def render_results_png(vtu_path: Path, out_png: Path, field: str = "U",
                        component: int | str = "magnitude",
                        warp_factor: float = 0.0,
                        window_size: tuple[int, int] = (1600, 1200),
                        clim: tuple[float, float] | None = None) -> Path:
    """Ve ket qua FEM (chuyen vi/ung suat) tu file .vtu (xem convert_frd_to_vtu),
    goc nhin isometric tinh, luu PNG."""
    plotter = _build_results_plotter(vtu_path, field, component, warp_factor, window_size, clim)
    plotter.camera_position = "iso"
    plotter.enable_parallel_projection()

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plotter.screenshot(str(out_png))
    plotter.close()
    return out_png


def render_all_stage_pngs(vtu_paths: list[Path], stage_names: list[str], out_dir: Path,
                           zone_code: str, field: str = "U",
                           component: int | str = "magnitude",
                           warp_factor: float = 20.0,
                           window_size: tuple[int, int] = (1600, 1200),
                           shared_clim: bool = True) -> list[Path]:
    """Xuat 1 PNG cho MOI giai doan (GD0..GDN) — vtu_paths tu
    convert_frd_to_vtu_all_stages(), stage_names de dat ten file + tieu de.
    shared_clim=True (mac dinh): dung CHUNG 1 thang mau (lay min/max cua GIAI
    DOAN CUOI, thuong co gia tri lon nhat) cho tat ca anh — so sanh truc quan
    duoc muc do tien trien qua tung giai doan (giong tinh than clim co dinh cua
    render_results_gif). False: moi anh tu dong thang mau rieng (tuong phan ro
    hon trong tung anh nhung KHONG so sanh duoc giua cac giai doan)."""
    if len(vtu_paths) != len(stage_names):
        raise ValueError(
            f"So luong vtu_paths ({len(vtu_paths)}) khac stage_names ({len(stage_names)})"
        )

    clim = None
    if shared_clim:
        grid_last = pv.read(str(vtu_paths[-1]))
        data = np.asarray(grid_last.point_data[field])
        scalars = (np.linalg.norm(data, axis=1) if data.ndim > 1 and component == "magnitude"
                   else (data[:, component] if data.ndim > 1 else data))
        clim = (0.0, float(scalars.max()))

    out_dir = Path(out_dir)
    out_paths = []
    for i, (vtu_path, name) in enumerate(zip(vtu_paths, stage_names)):
        safe_name = name.split(" - ")[0].split(" ")[0].replace("/", "_")  # vd "GD0", "GD2"
        out_png = out_dir / f"cdm3d_{zone_code}_{safe_name}_{field}_3d.png"
        render_results_png(vtu_path, out_png, field=field, component=component,
                            warp_factor=warp_factor, window_size=window_size, clim=clim)
        out_paths.append(out_png)
    return out_paths


def render_results_gif(vtu_path: Path, out_gif: Path, field: str = "U",
                        component: int | str = "magnitude",
                        warp_factor: float = 20.0,
                        window_size: tuple[int, int] = (1200, 900),
                        n_frames: int = 30, framerate: int = 15,
                        hold_last_frames: int = 10) -> Path:
    """GIF 'tai tang dan' — camera CO DINH (KHONG xoay). Truong ket qua va do bien
    dang hinh hoc cung duoc nhan voi ty le tai frac = 0 -> 1 qua tung khung hinh
    (dung vi mo hinh dan hoi tuyen tinh -> chuyen vi ti le thuan voi tai). Ket qua:
    pho mau "sang dan" tu xanh dam (frac~0) den day du thang mau that (frac=1) —
    dung anh dong minh hoa lun hinh thanh, khong phai xoay hinh tinh."""
    grid = pv.read(str(vtu_path))
    if field not in grid.point_data:
        available = list(grid.point_data.keys())
        raise KeyError(f"Khong co truong '{field}' trong ket qua — cac truong co: {available}")

    vectors = np.asarray(grid.point_data[field])
    if vectors.ndim > 1:
        scalars_full = np.linalg.norm(vectors, axis=1) if component == "magnitude" else vectors[:, component]
    else:
        scalars_full = np.abs(vectors)
    clim = (0.0, float(scalars_full.max()))
    base_points = grid.points.copy()

    plot_grid = grid.copy()
    plotter = pv.Plotter(off_screen=True, window_size=list(window_size))
    plotter.set_background("white")
    plotter.add_mesh(plot_grid, scalars=field,
                      component=(None if component == "magnitude" else component),
                      cmap="turbo", clim=clim, show_edges=False,
                      scalar_bar_args={"title": field})
    plotter.add_axes()
    plotter.camera_position = "iso"
    plotter.enable_parallel_projection()

    out_gif = Path(out_gif)
    out_gif.parent.mkdir(parents=True, exist_ok=True)
    plotter.open_gif(str(out_gif), fps=framerate)

    for i in range(n_frames + 1):
        frac = i / n_frames
        if vectors.ndim > 1:
            plot_grid.points = base_points + warp_factor * frac * vectors[:, :3]
        plot_grid.point_data[field] = vectors * frac
        plotter.write_frame()
    for _ in range(hold_last_frames):  # dung lai o trang thai cuoi (tai 100%) de xem ro
        plotter.write_frame()

    plotter.close()
    return out_gif
