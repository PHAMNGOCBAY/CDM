"""cdm3d.geometry — Dung hinh hoc 3D (khoi dat nhieu lop + nhom tru CDM hinh tru)
bang gmsh OpenCASCADE (OCC) kernel.

Quy uoc:
  - Truc X, Y: mat bang (m). Truc Z: cao do, duong len tren (m).
  - Goc toa do X=Y=0 dat tai tam nhom tru.
  - Sau fragment, moi lop dat / tru la 1 the tich (volume) rieng, dinh Physical Group
    theo ten de ccx_input.py map vat lieu + boundary.

Gmsh la thu vien co global state (khong can truyen "model object" giua ham) — luon
goi build_geometry() sau gmsh.initialize() va truoc gmsh.model.mesh.generate(3).
"""
from __future__ import annotations

import gmsh

from .types import ModelParams

PG_BASE = "BASE"
PG_SIDE_XMIN = "SIDE_XMIN"
PG_SIDE_XMAX = "SIDE_XMAX"
PG_SIDE_YMIN = "SIDE_YMIN"
PG_SIDE_YMAX = "SIDE_YMAX"
PG_TOP_SOIL = "TOP_SOIL"
PG_TOP_COLUMN = "TOP_COLUMN"


def column_centers(params: ModelParams) -> list[tuple[float, float]]:
    col = params.column
    x0 = -((col.n_x - 1) * col.spacing_m) / 2.0
    y0 = -((col.n_y - 1) * col.spacing_m) / 2.0
    return [
        (x0 + i * col.spacing_m, y0 + j * col.spacing_m)
        for i in range(col.n_x)
        for j in range(col.n_y)
    ]


def build_geometry(params: ModelParams) -> dict:
    """Tra ve dict cac physical group da tao: {name: (dim, list_of_tags_goc_truoc_fragment)}.
    Sau ham nay, goi gmsh.model.occ.synchronize() da duoc thuc hien noi bo.
    """
    gmsh.model.add(f"cdm3d_{params.zone_code}")
    occ = gmsh.model.occ

    # x_max luon doi xung theo domain_buffer_m (phia +X — phia CO tai khi
    # load_footprint="half_pos", vd GD5). x_min co the mo rong RIENG qua
    # domain_buffer_x_neg_m (phia -X, KHONG co tai) — bat doi xung neu duoc dat.
    half_footprint_x = params.footprint_x_m() / 2.0
    x_max = half_footprint_x + params.domain_buffer_m
    buf_x_neg = params.domain_buffer_x_neg_m if params.domain_buffer_x_neg_m is not None else params.domain_buffer_m
    x_min = -(half_footprint_x + buf_x_neg)
    dx = x_max - x_min
    dy = params.domain_y_m()
    y_min = -dy / 2.0

    soil_vol_tags: dict[str, int] = {}
    for layer in params.soil_layers:
        h = layer.z_top - layer.z_bot
        tag = occ.addBox(x_min, y_min, layer.z_bot, dx, dy, h)
        soil_vol_tags[layer.name] = tag

    centers = column_centers(params)
    r = params.column.D_m / 2.0
    h_col = params.column.z_top - params.column.z_bot
    column_tags = [
        occ.addCylinder(cx, cy, params.column.z_bot, 0, 0, h_col, r)
        for cx, cy in centers
    ]

    soil_dimtags = [(3, t) for t in soil_vol_tags.values()]
    column_dimtags = [(3, t) for t in column_tags]

    out_dimtags, out_map = occ.fragment(soil_dimtags, column_dimtags)
    occ.synchronize()

    # out_map[i] ung voi input dimtag thu i (soil truoc, column sau). Vi doan tru
    # nam TRON VEN trong khoi dat (khong cat qua bien), OCC fragment gan doan giao
    # nay cho CA HAI danh sach cha (soil VA column) — phai loai trung: doan nao da
    # thuoc column_children thi KHONG duoc tinh vao soil_children (khong thi mot
    # volume se bi gan 2 Physical Group, sai vat lieu khi xuat luoi).
    n_soil = len(soil_dimtags)
    column_children: list[int] = []
    for orig_idx in range(n_soil, n_soil + len(column_dimtags)):
        column_children += [t for (d, t) in out_map[orig_idx] if d == 3]
    column_children = sorted(set(column_children))
    column_set = set(column_children)

    soil_children: dict[str, list[int]] = {}
    for name, orig_idx in zip(soil_vol_tags.keys(), range(n_soil)):
        raw = [t for (d, t) in out_map[orig_idx] if d == 3]
        soil_children[name] = sorted(set(raw) - column_set)

    for name, tags in soil_children.items():
        pg = gmsh.model.addPhysicalGroup(3, sorted(set(tags)))
        gmsh.model.setPhysicalName(3, pg, f"SOIL_{name}")
    pg_col = gmsh.model.addPhysicalGroup(3, column_children)
    gmsh.model.setPhysicalName(3, pg_col, "CDM_COLUMN")

    _tag_boundary_surfaces(params, x_min, y_min, dx, dy)

    return {"soil": soil_children, "column": column_children}


def _tag_boundary_surfaces(params: ModelParams, x_min: float, y_min: float, dx: float, dy: float) -> None:
    """Phan loai cac mat bien ngoai (2D) theo bounding box: day/thanh/dinh."""
    x_max, y_max = x_min + dx, y_min + dy
    z_min, z_max = params.z_domain_bot(), params.z_domain_top()
    eps = 1e-6

    base_tags, top_soil_tags, top_col_tags = [], [], []
    side_tags = {PG_SIDE_XMIN: [], PG_SIDE_XMAX: [], PG_SIDE_YMIN: [], PG_SIDE_YMAX: []}
    for dim, tag in gmsh.model.getEntities(2):
        xlo, ylo, zlo, xhi, yhi, zhi = gmsh.model.occ.getBoundingBox(dim, tag)
        on_base = abs(zlo - z_min) < eps and abs(zhi - z_min) < eps
        on_top = abs(zlo - z_max) < eps and abs(zhi - z_max) < eps
        on_xmin = abs(xlo - x_min) < eps and abs(xhi - x_min) < eps
        on_xmax = abs(xlo - x_max) < eps and abs(xhi - x_max) < eps
        on_ymin = abs(ylo - y_min) < eps and abs(yhi - y_min) < eps
        on_ymax = abs(ylo - y_max) < eps and abs(yhi - y_max) < eps
        if on_base:
            base_tags.append(tag)
        elif on_top:
            # Phan biet dinh dat vs dinh tru bang DIEN TICH (KHONG dung tam bbox —
            # mat dinh dat la 1 mat phang nhieu lo tron (multiply-connected), tam
            # bbox cua no co the trung dung vi tri 1 tru khi luoi tru dat tai goc
            # (0,0), gay phan loai sai). Dien tich 1 dinh tru = pi*(D/2)^2.
            area = gmsh.model.occ.getMass(dim, tag)
            col_top_area = 3.14159265 * (params.column.D_m / 2.0) ** 2
            is_col_top = area < 3.0 * col_top_area
            (top_col_tags if is_col_top else top_soil_tags).append(tag)
        elif on_xmin:
            side_tags[PG_SIDE_XMIN].append(tag)
        elif on_xmax:
            side_tags[PG_SIDE_XMAX].append(tag)
        elif on_ymin:
            side_tags[PG_SIDE_YMIN].append(tag)
        elif on_ymax:
            side_tags[PG_SIDE_YMAX].append(tag)

    if base_tags:
        pg = gmsh.model.addPhysicalGroup(2, base_tags)
        gmsh.model.setPhysicalName(2, pg, PG_BASE)
    for name, tags in side_tags.items():
        if tags:
            pg = gmsh.model.addPhysicalGroup(2, tags)
            gmsh.model.setPhysicalName(2, pg, name)
    if top_soil_tags:
        pg = gmsh.model.addPhysicalGroup(2, top_soil_tags)
        gmsh.model.setPhysicalName(2, pg, PG_TOP_SOIL)
    if top_col_tags:
        pg = gmsh.model.addPhysicalGroup(2, top_col_tags)
        gmsh.model.setPhysicalName(2, pg, PG_TOP_COLUMN)
