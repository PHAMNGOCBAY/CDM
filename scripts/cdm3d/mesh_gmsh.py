"""cdm3d.mesh_gmsh — Phat sinh luoi tu dien 3D (C3D4 — tuyen tinh bac 1) tu hinh hoc
da dung trong geometry.build_geometry(). Luoi min quanh tru CDM (Box field), thua dan
ra bien mo hinh de giam so phan tu ma van bat duoc tuong tac tru-dat gan cot.
"""
from __future__ import annotations

from pathlib import Path

import gmsh

from .geometry import column_centers
from .types import ModelParams


def set_mesh_size_fields(params: ModelParams) -> None:
    field = gmsh.model.mesh.field
    box_tags = []
    margin = params.column_box_field_margin_m
    half = params.column.D_m / 2.0 + margin
    for cx, cy in column_centers(params):
        t = field.add("Box")
        field.setNumber(t, "VIn", params.mesh_size_near_column_m)
        field.setNumber(t, "VOut", params.mesh_size_far_m)
        field.setNumber(t, "XMin", cx - half)
        field.setNumber(t, "XMax", cx + half)
        field.setNumber(t, "YMin", cy - half)
        field.setNumber(t, "YMax", cy + half)
        field.setNumber(t, "ZMin", params.z_domain_bot())
        field.setNumber(t, "ZMax", params.z_domain_top())
        field.setNumber(t, "Thickness", max(params.column.spacing_m - params.column.D_m, 0.5))
        box_tags.append(t)

    t_min = field.add("Min")
    field.setNumbers(t_min, "FieldsList", box_tags)
    field.setAsBackgroundMesh(t_min)

    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)


def generate_mesh(params: ModelParams, element_order: int = 1) -> None:
    """element_order=1 -> C3D4 (tu dien 4 nut); =2 -> C3D10 (tu dien 10 nut, chinh xac
    hon cho uon nhung nang tinh toan hon — CalculiX ho tro ca hai)."""
    set_mesh_size_fields(params)
    gmsh.model.mesh.generate(3)
    if element_order == 2:
        gmsh.model.mesh.setOrder(2)


def export_mesh(out_path: Path, fmt: str = "2.2") -> Path:
    """Ghi file .msh phien ban 2.2 (ASCII) — dinh dang meshio doc on dinh nhat de
    convert sang CalculiX .inp o buoc sau."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gmsh.option.setNumber("Mesh.MshFileVersion", float(fmt))
    gmsh.write(str(out_path))
    return out_path


def mesh_stats() -> dict:
    node_tags, _, _ = gmsh.model.mesh.getNodes()
    elem_types, elem_tags, _ = gmsh.model.mesh.getElements(3)
    n_elem = sum(len(t) for t in elem_tags)
    return {"n_nodes": len(node_tags), "n_elements_3d": n_elem}
