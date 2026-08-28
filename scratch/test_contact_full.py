"""Test day du: mesh dat (co lo tru) va cot RIENG BIET (2 phien gmsh doc lap),
gop thanh 1 deck CalculiX, dinh nghia *CONTACT PAIR (ma sat mu=0.3), giai tai
ngang don gian, kiem tra hoi tu.
"""
import sys
from pathlib import Path

ROOT = Path(r"g:\My Drive\AI-SUC TAI COC THEO DAT NEN")
sys.path.insert(0, str(ROOT / "scripts"))

import gmsh
import meshio
import numpy as np

MU = 0.3
D = 0.8
R = D / 2
L_COL = 6.0   # chieu dai cot (m)
Z_TOP = 0.0
Z_BOT = -L_COL
DOMAIN = 4.0  # nua canh domain (tu -DOMAIN den +DOMAIN, x va y)
MESH_SIZE = 0.2

E_SOIL, NU_SOIL, GAMMA_SOIL = 3450.0, 0.35, 16.0
E_COL, NU_COL, GAMMA_COL = 40000.0, 0.25, 18.0

out_dir = ROOT / "scratch"


def mesh_soil():
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("soil")
    occ = gmsh.model.occ
    soil_tag = occ.addBox(-DOMAIN, -DOMAIN, Z_BOT - 1.0, 2 * DOMAIN, 2 * DOMAIN, L_COL + 1.0 + abs(Z_TOP))
    hole_tag = occ.addCylinder(0, 0, Z_BOT, 0, 0, L_COL, R)
    out_dimtags, _ = occ.cut([(3, soil_tag)], [(3, hole_tag)], removeTool=True)
    occ.synchronize()
    soil_vol = out_dimtags[0][1]

    # phan loai mat bien
    xlo, ylo, zlo, xhi, yhi, zhi = occ.getBoundingBox(3, soil_vol)
    eps = 1e-6
    base_tags, side_tags, hole_tags = [], [], []
    for dim, tag in gmsh.model.getEntities(2):
        bxlo, bylo, bzlo, bxhi, byhi, bzhi = occ.getBoundingBox(dim, tag)
        if abs(bzlo - zlo) < eps and abs(bzhi - zlo) < eps:
            base_tags.append(tag)
        elif (abs(bxlo - xlo) < eps and abs(bxhi - xlo) < eps) or \
             (abs(bxlo - xhi) < eps and abs(bxhi - xhi) < eps) or \
             (abs(bylo - ylo) < eps and abs(byhi - ylo) < eps) or \
             (abs(bylo - yhi) < eps and abs(byhi - yhi) < eps):
            side_tags.append(tag)
        else:
            area = occ.getMass(2, tag)
            expected_cyl_area = 2 * 3.14159265 * R * L_COL
            if area < expected_cyl_area * 1.5:
                hole_tags.append(tag)

    pg = gmsh.model.addPhysicalGroup(3, [soil_vol]); gmsh.model.setPhysicalName(3, pg, "SOIL")
    pg = gmsh.model.addPhysicalGroup(2, base_tags); gmsh.model.setPhysicalName(2, pg, "BASE")
    pg = gmsh.model.addPhysicalGroup(2, side_tags); gmsh.model.setPhysicalName(2, pg, "SIDE")
    pg = gmsh.model.addPhysicalGroup(2, hole_tags); gmsh.model.setPhysicalName(2, pg, "SOIL_INNER")

    gmsh.option.setNumber("Mesh.MeshSizeMin", MESH_SIZE * 0.6)
    gmsh.option.setNumber("Mesh.MeshSizeMax", MESH_SIZE * 2.5)
    gmsh.model.mesh.generate(3)
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.write(str(out_dir / "soil_only.msh"))
    stats = (len(gmsh.model.mesh.getNodes()[0]),)
    gmsh.finalize()
    return stats


def mesh_column():
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("col")
    occ = gmsh.model.occ
    col_tag = occ.addCylinder(0, 0, Z_BOT, 0, 0, L_COL, R)
    occ.synchronize()

    lateral_tags, top_tags, bot_tags = [], [], []
    for dim, tag in gmsh.model.getEntities(2):
        area = occ.getMass(2, tag)
        cap_area = 3.14159265 * R * R
        if area < cap_area * 1.5:
            zlo, zhi = occ.getBoundingBox(dim, tag)[2], occ.getBoundingBox(dim, tag)[5]
            (top_tags if zlo > (Z_TOP + Z_BOT) / 2 else bot_tags).append(tag)
        else:
            lateral_tags.append(tag)

    pg = gmsh.model.addPhysicalGroup(3, [col_tag]); gmsh.model.setPhysicalName(3, pg, "CDM_COLUMN")
    pg = gmsh.model.addPhysicalGroup(2, lateral_tags); gmsh.model.setPhysicalName(2, pg, "COL_LATERAL")
    pg = gmsh.model.addPhysicalGroup(2, top_tags); gmsh.model.setPhysicalName(2, pg, "COL_TOP")
    pg = gmsh.model.addPhysicalGroup(2, bot_tags); gmsh.model.setPhysicalName(2, pg, "COL_BOT")

    gmsh.option.setNumber("Mesh.MeshSizeMin", MESH_SIZE * 0.6)
    gmsh.option.setNumber("Mesh.MeshSizeMax", MESH_SIZE * 1.2)
    gmsh.model.mesh.generate(3)
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.write(str(out_dir / "col_only.msh"))
    stats = (len(gmsh.model.mesh.getNodes()[0]),)
    gmsh.finalize()
    return stats


print("Meshing soil...", mesh_soil())
print("Meshing column...", mesh_column())

# --- doc lai + gop ---
m_soil = meshio.read(str(out_dir / "soil_only.msh"))
m_col = meshio.read(str(out_dir / "col_only.msh"))

n_soil_nodes = len(m_soil.points)
print(f"soil nodes={n_soil_nodes}, col nodes={len(m_col.points)}")

all_points = np.vstack([m_soil.points, m_col.points])


def get_tetra_by_tag(m, tag_names):
    tag_to_name = {tag: name for name, (tag, dim) in m.field_data.items() if dim == 3}
    out = {}
    for i, block in enumerate(m.cells):
        if block.type != "tetra":
            continue
        tags = m.cell_data.get("gmsh:physical", [None] * len(m.cells))[i]
        for j in range(block.data.shape[0]):
            name = tag_to_name.get(int(tags[j]))
            if name in tag_names:
                out.setdefault(name, []).append(block.data[j])
    return {k: np.array(v) for k, v in out.items()}


def get_triangles_by_tag(m, tag_names):
    tag_to_name = {tag: name for name, (tag, dim) in m.field_data.items() if dim == 2}
    out = {}
    for i, block in enumerate(m.cells):
        if block.type != "triangle":
            continue
        tags = m.cell_data.get("gmsh:physical", [None] * len(m.cells))[i]
        for j in range(block.data.shape[0]):
            name = tag_to_name.get(int(tags[j]))
            if name in tag_names:
                out.setdefault(name, []).append(block.data[j])
    return {k: np.array(v) for k, v in out.items()}


soil_tetra = get_tetra_by_tag(m_soil, ["SOIL"])["SOIL"]
soil_faces = get_triangles_by_tag(m_soil, ["BASE", "SIDE", "SOIL_INNER"])
col_tetra = get_tetra_by_tag(m_col, ["CDM_COLUMN"])["CDM_COLUMN"]
col_faces = get_triangles_by_tag(m_col, ["COL_LATERAL", "COL_TOP"])

# offset node index cua cot
col_tetra_off = col_tetra + n_soil_nodes
col_faces_off = {k: v + n_soil_nodes for k, v in col_faces.items()}

print(f"soil tetra={len(soil_tetra)}, col tetra={len(col_tetra)}")
print(f"soil faces: {[(k,len(v)) for k,v in soil_faces.items()]}")
print(f"col faces: {[(k,len(v)) for k,v in col_faces.items()]}")


# --- xac dinh S-face cho *SURFACE (dung bang ifacet tu getnodel.f) ---
# S1={0,2,1} S2={0,1,3} S3={1,2,3} S4={0,3,2}  (0-indexed local vi tri trong element)
FACE_LOCAL = {1: (0, 2, 1), 2: (0, 1, 3), 3: (1, 2, 3), 4: (0, 3, 2)}


def find_surface_faces(all_tetra, target_face_nodes, elem_id_offset=0):
    """target_face_nodes: array (N,3) global node id cua tam giac bien.
    all_tetra: array (M,4) global node id cua tat ca tet (cung group voi bien).
    Tra ve list (elem_1indexed, 'S<k>')."""
    # index: node -> list elem indices co chua node do
    node_to_elems = {}
    for ei, tet in enumerate(all_tetra):
        for n in tet:
            node_to_elems.setdefault(int(n), []).append(ei)

    result = []
    for tri in target_face_nodes:
        tri_set = set(int(x) for x in tri)
        cand_elems = set()
        for n in tri:
            cand_elems.update(node_to_elems.get(int(n), []))
        found = False
        for ei in cand_elems:
            tet = all_tetra[ei]
            tet_set = set(int(x) for x in tet)
            if tri_set.issubset(tet_set):
                for face_id, (a, b, c) in FACE_LOCAL.items():
                    face_nodes = {int(tet[a]), int(tet[b]), int(tet[c])}
                    if face_nodes == tri_set:
                        result.append((ei + 1 + elem_id_offset, f"S{face_id}"))
                        found = True
                        break
                if found:
                    break
        if not found:
            raise ValueError(f"Khong tim thay tet chua mat {tri_set}")
    return result


print("Tim S-face cho SOIL_INNER...")
soil_inner_sfaces = find_surface_faces(soil_tetra, soil_faces["SOIL_INNER"])
print(f"  -> {len(soil_inner_sfaces)} faces, vd: {soil_inner_sfaces[:3]}")

print("Tim S-face cho COL_LATERAL...")
col_lateral_sfaces = find_surface_faces(col_tetra, col_faces["COL_LATERAL"], elem_id_offset=len(soil_tetra))
print(f"  -> {len(col_lateral_sfaces)} faces, vd: {col_lateral_sfaces[:3]}")

print("OK - buoc tim S-face thanh cong.")

# --- ghi .inp ---
G = 9.81
lines = ["** test contact soil-column", "*NODE, NSET=NALL"]
for i, (x, y, z) in enumerate(all_points, start=1):
    lines.append(f"{i}, {x:.6f}, {y:.6f}, {z:.6f}")

lines.append("*ELEMENT, TYPE=C3D4, ELSET=SOIL")
for k, tet in enumerate(soil_tetra, start=1):
    nodes = tet + 1
    lines.append(f"{k}, " + ", ".join(str(n) for n in nodes))

lines.append("*ELEMENT, TYPE=C3D4, ELSET=CDM_COLUMN")
for k, tet in enumerate(col_tetra_off, start=1):
    nodes = tet + 1
    lines.append(f"{k + len(soil_tetra)}, " + ", ".join(str(n) for n in nodes))

lines += [
    "*MATERIAL, NAME=MAT_SOIL", "*ELASTIC", f"{E_SOIL:.3f}, {NU_SOIL:.3f}",
    "*DENSITY", f"{GAMMA_SOIL/G:.6f}", "*SOLID SECTION, ELSET=SOIL, MATERIAL=MAT_SOIL",
    "*MATERIAL, NAME=MAT_COLUMN", "*ELASTIC", f"{E_COL:.3f}, {NU_COL:.3f}",
    "*DENSITY", f"{GAMMA_COL/G:.6f}", "*SOLID SECTION, ELSET=CDM_COLUMN, MATERIAL=MAT_COLUMN",
]


def write_nset(name, node_ids_0idx, offset=0):
    lines.append(f"*NSET, NSET={name}")
    ids = np.unique(node_ids_0idx.ravel()) + 1 + offset
    for cs in range(0, len(ids), 10):
        lines.append(", ".join(str(n) for n in ids[cs:cs + 10]))


write_nset("BASE", soil_faces["BASE"])
write_nset("SIDE", soil_faces["SIDE"])
write_nset("COLTOP", col_faces["COL_TOP"], offset=n_soil_nodes)

lines.append("*SURFACE, NAME=SOIL_INNER, TYPE=ELEMENT")
for elem, face in soil_inner_sfaces:
    lines.append(f"{elem}, {face}")
lines.append("*SURFACE, NAME=COL_LATERAL, TYPE=ELEMENT")
for elem, face in col_lateral_sfaces:
    lines.append(f"{elem}, {face}")

lines += [
    "*SURFACE INTERACTION, NAME=SOIL_COL_INT",
    "*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=HARD",
    "*FRICTION",
    f"{MU}, 0.",
    "*CONTACT PAIR, INTERACTION=SOIL_COL_INT, TYPE=NODE TO SURFACE",
    "SOIL_INNER, COL_LATERAL",
]

lines += ["*BOUNDARY", "BASE, 1, 3", "SIDE, 1, 3"]

n_top = len(np.unique(col_faces["COL_TOP"].ravel()))
F_total_kN = 50.0  # tai ngang thu nghiem
F_per_node = F_total_kN / n_top
lines += ["*STEP, NLGEOM", "*STATIC", "*CLOAD"]
for n in np.unique(col_faces["COL_TOP"].ravel()) + 1 + n_soil_nodes:
    lines.append(f"{n}, 1, {F_per_node:.6f}")
lines += ["*NODE FILE", "U", "*EL FILE", "S, E", "*END STEP"]

inp_path = out_dir / "test_contact.inp"
inp_path.write_text("\n".join(lines) + "\n", encoding="ascii", errors="replace")
print("wrote", inp_path, inp_path.stat().st_size, "bytes")

sys.path.insert(0, str(ROOT / "scripts"))
from cdm3d import run_ccx
frd = run_ccx.solve(inp_path, timeout_s=600)
print("SOLVED ->", frd)
