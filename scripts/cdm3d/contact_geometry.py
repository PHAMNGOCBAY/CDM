"""cdm3d.contact_geometry — Dung hinh hoc + luoi CHO MO HINH CONTACT (dat-coc
KHONG dung chung nut — khac voi geometry.py dung fragment() cho mo hinh bonded).

Da kiem chung thuc nghiem (2026-08-27, xem .claude/commands/cdm3d-contact.md):
occ.cut(removeTool=False) KHONG du — dat va cot van dung chung 1 surface entity.
CACH DUY NHAT hoat dong: mesh dat (co lo hinh tru, cut removeTool=True chi de tao
lo) va cot (hinh tru doc lap) trong 2 PHIEN gmsh HOAN TOAN TACH BIET, roi gop thu
cong (offset chi so nut) — xem contact_ccx_input.py.

9 cot khong cham nhau (khoang cach mep >= 1.0m > 0) nen mesh CHUNG 1 phien duoc,
khong can 9 phien rieng.
"""
from __future__ import annotations

import gmsh

from .geometry import column_centers
from .types import ModelParams

PI = 3.14159265358979


def mesh_soil_with_holes(params: ModelParams, out_msh) -> dict:
    """Phien gmsh 1: khoi dat 3 lop, co 9 lo hinh tru (KHONG chua cot). Tra ve
    thong ke luoi. Physical Group: SOIL_<layer> (x3), BASE, SIDE_*, TOP_SOIL,
    SOIL_INNER (tat ca mat lo hinh tru gop chung)."""
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add(f"cdm3d_contact_soil_{params.zone_code}")
    occ = gmsh.model.occ

    dx, dy = params.domain_x_m(), params.domain_y_m()
    x_min, y_min = -dx / 2.0, -dy / 2.0

    layer_tags = {}
    for layer in params.soil_layers:
        h = layer.z_top - layer.z_bot
        layer_tags[layer.name] = occ.addBox(x_min, y_min, layer.z_bot, dx, dy, h)

    layer_dimtags = [(3, t) for t in layer_tags.values()]
    frag_out, frag_map = occ.fragment(layer_dimtags[:1], layer_dimtags[1:])
    occ.synchronize()

    layer_children: dict[str, list[int]] = {}
    for name, orig_idx in zip(layer_tags.keys(), range(len(layer_dimtags))):
        layer_children[name] = sorted(set(t for d, t in frag_map[orig_idx] if d == 3))

    centers = column_centers(params)
    r = params.column.D_m / 2.0
    h_col = params.column.z_top - params.column.z_bot
    hole_tags = [occ.addCylinder(cx, cy, params.column.z_bot, 0, 0, h_col, r) for cx, cy in centers]

    all_soil_dimtags = [(3, t) for tags in layer_children.values() for t in tags]
    hole_dimtags = [(3, t) for t in hole_tags]
    cut_out, cut_map = occ.cut(all_soil_dimtags, hole_dimtags, removeTool=True)
    occ.synchronize()

    # cut_map[i] ung voi all_soil_dimtags[i] — anh xa lai ve layer_children moi
    soil_dimtag_to_orig_layer = {}
    idx = 0
    for name, tags in layer_children.items():
        for t in tags:
            soil_dimtag_to_orig_layer[idx] = name
            idx += 1
    # cut_map co them cac muc cho hole_dimtags (tool) o cuoi du removeTool=True —
    # CHI lay dung so muc dau tien tuong ung all_soil_dimtags (object).
    final_layer_vols: dict[str, list[int]] = {name: [] for name in layer_tags}
    for i in range(len(all_soil_dimtags)):
        name = soil_dimtag_to_orig_layer[i]
        final_layer_vols[name] += [t for d, t in cut_map[i] if d == 3]
    for name in final_layer_vols:
        final_layer_vols[name] = sorted(set(final_layer_vols[name]))

    for name, tags in final_layer_vols.items():
        pg = gmsh.model.addPhysicalGroup(3, tags)
        gmsh.model.setPhysicalName(3, pg, f"SOIL_{name}")

    _tag_soil_boundary(params, x_min, y_min, dx, dy)
    _set_mesh_size_fields_soil(params, centers)

    gmsh.model.mesh.generate(3)
    stats = {"n_nodes": len(gmsh.model.mesh.getNodes()[0])}
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.write(str(out_msh))
    gmsh.finalize()
    return stats


def _tag_soil_boundary(params: ModelParams, x_min: float, y_min: float, dx: float, dy: float) -> None:
    """Phan loai mat bien 2D cua khoi dat (sau fragment 3 lop + cut lo tru).

    Phat hien 2026-08-27 (xem .claude/commands/cdm3d-contact.md — cap nhat cung
    ngay): occ.fragment() 3 lop TRUOC roi occ.cut() lo tru chung SAU (dong 41, 55)
    de lai TAN DU (artifact) — cac mat phang NGANG (dia tron, ban kinh = ban kinh
    lo) tai DUNG cao do ranh gioi lop noi bo (vd z=0, z=-23 cho KE) LOT VAO nhom
    "mat trong" (truoc day gop het vao SOIL_INNER cung mat tru that). Cac dia nay
    KHONG phai mat tru (phap tuyen doc, khong ngang) va KHONG phai day lo that
    (z != column.z_bot) — neu de lot vao SOIL_INNER, CalculiX co gang chieu (project)
    nut tren dia (o giua/tam lo, khong nam tren mat tru) len mat master COL_LATERAL
    (thuan hinh tru) -> quan he hinh hoc vo nghia -> phan ky khi co tai (da kiem
    chung thuc nghiem: 1 coc 3 lop + tai NGANG hoi tu binh thuong, nhung + tai
    DUNG surcharge phan ky bung no ngay increment 1 — chi khac o cac dia artifact
    nay bi kich hoat manh hon duoi tai lam coc lun).

    Phan loai bang BOUNDING BOX (cap OCC face, TRUOC mesh):
    - Mat PHANG (zlo~zhi, tuc la dia ngang): kiem tra z co khop `column.z_bot`
      (day lo THAT = mui coc) khong. Neu dung -> tag rieng "SOIL_TIP" (danh cho
      contact PAIR RIENG voi COL_BOT sau nay, KHONG gop vao SOIL_INNER — sai khac
      ban chat vat ly, day la bearing khong phai ma sat than). Neu SAI (khop mot
      ranh gioi lop noi bo nao khac) -> ARTIFACT, KHONG tag (bo qua hoan toan,
      khong anh huong do cung phan tu, chi khong tham gia contact).
    - Mat KHONG phang (zlo != zhi, tuc la mat tru that, trai theo chieu cao coc):
      tag "SOIL_INNER" nhu cu.
    """
    x_max, y_max = x_min + dx, y_min + dy
    z_min, z_max = params.z_domain_bot(), params.z_domain_top()
    z_col_bot = params.column.z_bot
    eps = 1e-6

    base_tags, top_tags, inner_tags, tip_tags = [], [], [], []
    side_tags = {"SIDE_XMIN": [], "SIDE_XMAX": [], "SIDE_YMIN": [], "SIDE_YMAX": []}
    n_artifact = 0
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
            top_tags.append(tag)
        elif on_xmin:
            side_tags["SIDE_XMIN"].append(tag)
        elif on_xmax:
            side_tags["SIDE_XMAX"].append(tag)
        elif on_ymin:
            side_tags["SIDE_YMIN"].append(tag)
        elif on_ymax:
            side_tags["SIDE_YMAX"].append(tag)
        else:
            is_flat = abs(zhi - zlo) < eps
            if is_flat:
                if abs(zlo - z_col_bot) < eps:
                    tip_tags.append(tag)  # day lo that = mui coc
                else:
                    n_artifact += 1  # dia artifact tai ranh gioi lop noi bo — bo qua
            else:
                inner_tags.append(tag)  # mat tru that

    if base_tags:
        pg = gmsh.model.addPhysicalGroup(2, base_tags); gmsh.model.setPhysicalName(2, pg, "BASE")
    for name, tags in side_tags.items():
        if tags:
            pg = gmsh.model.addPhysicalGroup(2, tags); gmsh.model.setPhysicalName(2, pg, name)
    if top_tags:
        pg = gmsh.model.addPhysicalGroup(2, top_tags); gmsh.model.setPhysicalName(2, pg, "TOP_SOIL")
    if inner_tags:
        pg = gmsh.model.addPhysicalGroup(2, inner_tags); gmsh.model.setPhysicalName(2, pg, "SOIL_INNER")
    if tip_tags:
        pg = gmsh.model.addPhysicalGroup(2, tip_tags); gmsh.model.setPhysicalName(2, pg, "SOIL_TIP")
    if n_artifact:
        print(f"[contact_geometry] Da loai {n_artifact} mat dia artifact (ranh gioi "
              f"lop noi bo giao lo tru, tan du boolean OCC) khoi SOIL_INNER/SOIL_TIP.")


def _set_mesh_size_fields_soil(params: ModelParams, centers: list[tuple[float, float]]) -> None:
    field = gmsh.model.mesh.field
    box_tags = []
    margin = params.column_box_field_margin_m
    half = params.column.D_m / 2.0 + margin
    for cx, cy in centers:
        t = field.add("Box")
        field.setNumber(t, "VIn", params.mesh_size_near_column_m)
        field.setNumber(t, "VOut", params.mesh_size_far_m)
        field.setNumber(t, "XMin", cx - half); field.setNumber(t, "XMax", cx + half)
        field.setNumber(t, "YMin", cy - half); field.setNumber(t, "YMax", cy + half)
        field.setNumber(t, "ZMin", params.z_domain_bot()); field.setNumber(t, "ZMax", params.z_domain_top())
        field.setNumber(t, "Thickness", max(params.column.spacing_m - params.column.D_m, 0.5))
        box_tags.append(t)
    t_min = field.add("Min")
    field.setNumbers(t_min, "FieldsList", box_tags)
    field.setAsBackgroundMesh(t_min)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)


def mesh_columns_standalone(params: ModelParams, out_msh) -> dict:
    """Phien gmsh 2 (DOC LAP hoan toan voi phien 1): 9 cot hinh tru, KHONG cham
    nhau nen mesh chung 1 phien duoc. Physical Group: CDM_COLUMN (volume, gop 9
    cot), COL_LATERAL (mat ben, gop), COL_TOP, COL_BOT."""
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add(f"cdm3d_contact_col_{params.zone_code}")
    occ = gmsh.model.occ

    centers = column_centers(params)
    r = params.column.D_m / 2.0
    h_col = params.column.z_top - params.column.z_bot
    col_tags = [occ.addCylinder(cx, cy, params.column.z_bot, 0, 0, h_col, r) for cx, cy in centers]
    occ.synchronize()

    pg = gmsh.model.addPhysicalGroup(3, col_tags)
    gmsh.model.setPhysicalName(3, pg, "CDM_COLUMN")

    z_mid = (params.column.z_top + params.column.z_bot) / 2.0
    cap_area = PI * r * r
    lateral_tags, top_tags, bot_tags = [], [], []
    for dim, tag in gmsh.model.getEntities(2):
        area = occ.getMass(dim, tag)
        if area < cap_area * 1.5:
            zlo = occ.getBoundingBox(dim, tag)[2]
            (top_tags if zlo > z_mid else bot_tags).append(tag)
        else:
            lateral_tags.append(tag)

    pg = gmsh.model.addPhysicalGroup(2, lateral_tags); gmsh.model.setPhysicalName(2, pg, "COL_LATERAL")
    pg = gmsh.model.addPhysicalGroup(2, top_tags); gmsh.model.setPhysicalName(2, pg, "COL_TOP")
    pg = gmsh.model.addPhysicalGroup(2, bot_tags); gmsh.model.setPhysicalName(2, pg, "COL_BOT")

    gmsh.option.setNumber("Mesh.MeshSizeMin", params.mesh_size_near_column_m * 0.7)
    gmsh.option.setNumber("Mesh.MeshSizeMax", params.mesh_size_near_column_m * 1.4)
    gmsh.model.mesh.generate(3)
    stats = {"n_nodes": len(gmsh.model.mesh.getNodes()[0])}
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.write(str(out_msh))
    gmsh.finalize()
    return stats
