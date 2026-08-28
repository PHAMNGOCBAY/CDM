"""Dung hinh hoc + luoi cho kich ban 3.5 (kiem toan coc CDM that, GD5, Su=5000kPa)
BANG SALOME-MECA — lam moi hoan toan, KHONG dung lai luoi gmsh cu cua CalculiX.

Ly do lam lai: gmsh khong ho tro nhom-con long nhau tren cung 1 phan tu (da phat
hien 2026-08-28: gan them Physical Group con vao phan tu da co Physical Group cha
lam _read_mesh() doc TRUNG LAP phan tu — loi nghiem trong). Salome giai quyet tan
goc: dung geompy.MakePartition() cat hinh hoc THAT (khong chi tag), moi manh sau
partition la 1 solid RIENG BIET khong chong lan, gan nhom qua GroupOnGeom() an
toan tuyet doi.

Chay: "C:\\SALOME-MECA-2025\\v2025\\W64\\Python\\python3.exe" salome -t build_mesh.py
"""
import salome
salome.salome_init_without_session()

from salome.geom import geomBuilder
from salome.smesh import smeshBuilder
import SMESH

geompy = geomBuilder.New()
smesh = smeshBuilder.New()

# ================== THAM SO — dong bo voi cdm3d/params_io.build_default_params('KE') ==================
D_M = 0.8
SPACING_M = 1.8
N_X, N_Y = 3, 3
COL_Z_TOP, COL_Z_BOT = 0.8, -24.0
Z_LAYERS = [  # (ten, z_top, z_bot)
    ("dat_dap", 0.8, 0.0),
    ("dat_yeu", 0.0, -23.0),
    ("lop_cung", -23.0, -28.0),
]
DOMAIN_BUFFER_M = 3.6
FOOTPRINT_X = (N_X - 1) * SPACING_M + D_M
FOOTPRINT_Y = (N_Y - 1) * SPACING_M + D_M
X_MAX = FOOTPRINT_X / 2.0 + DOMAIN_BUFFER_M
X_MIN = -X_MAX
Y_MAX = FOOTPRINT_Y / 2.0 + DOMAIN_BUFFER_M
Y_MIN = -Y_MAX
EPS = 1e-4

MESH_SIZE_FAR = 2.0
MESH_SIZE_NEAR_COLUMN = 0.4

OUT_MED = r"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\codeaster_scenario35\geometrie\ke_scenario35.med"


def centers():
    x0 = -((N_X - 1) * SPACING_M) / 2.0
    y0 = -((N_Y - 1) * SPACING_M) / 2.0
    return [(x0 + i * SPACING_M, y0 + j * SPACING_M) for i in range(N_X) for j in range(N_Y)]


print("=== Dung hinh hoc ===")
solids = []
solid_tag = []  # song song voi solids: ('SOIL', layer_name) hoac ('COL', idx)

for name, z_top, z_bot in Z_LAYERS:
    h = z_top - z_bot
    box_neg = geompy.MakeBoxTwoPnt(
        geompy.MakeVertex(X_MIN, Y_MIN, z_bot), geompy.MakeVertex(0.0, Y_MAX, z_top)
    )
    box_pos = geompy.MakeBoxTwoPnt(
        geompy.MakeVertex(0.0, Y_MIN, z_bot), geompy.MakeVertex(X_MAX, Y_MAX, z_top)
    )
    solids += [box_neg, box_pos]
    solid_tag += [("SOIL", name), ("SOIL", name)]

vecz = geompy.MakeVectorDXDYDZ(0.0, 0.0, 1.0)
h_col = COL_Z_TOP - COL_Z_BOT
col_centers = centers()
for idx, (cx, cy) in enumerate(col_centers):
    pnt = geompy.MakeVertex(cx, cy, COL_Z_BOT)
    cyl = geompy.MakeCylinder(pnt, vecz, D_M / 2.0, h_col)
    solids.append(cyl)
    solid_tag.append(("COL", idx))

print(f"So solid dau vao: {len(solids)} (6 nua-lop-dat + {len(col_centers)} coc)")

partition = geompy.MakePartition(solids, [], [], [], geompy.ShapeType["SOLID"])
geompy.addToStudy(partition, "KE_partition")

sub_solids = geompy.SubShapeAll(partition, geompy.ShapeType["SOLID"])
print(f"So solid sau partition: {len(sub_solids)}")


def centroid(shape):
    cdg = geompy.MakeCDG(shape)
    return geompy.PointCoordinates(cdg)


def in_layer_z(z, z_top, z_bot):
    return (z_bot - EPS) <= z <= (z_top + EPS)


def in_column_xy(x, y, cx, cy):
    return (x - cx) ** 2 + (y - cy) ** 2 <= (D_M / 2.0 * 1.05) ** 2


# ================== Phan loai tung sub-solid: dat lop nao? co thuoc coc nao khong? ==================
soil_groups = {name: [] for name, _, _ in Z_LAYERS}
col_groups_by_row = {}  # x_rounded -> list of sub_solids
col_group_all = []

rows_x = sorted(set(round(cx, 6) for cx, cy in col_centers))
for rx in rows_x:
    col_groups_by_row[rx] = []

n_unclassified = 0
for sh in sub_solids:
    x, y, z = centroid(sh)
    is_col = False
    for cx, cy in col_centers:
        if in_column_xy(x, y, cx, cy):
            is_col = True
            break
    if is_col:
        col_group_all.append(sh)
        rx = min(rows_x, key=lambda r: abs(r - x))
        col_groups_by_row[rx].append(sh)
        continue
    matched = False
    for name, z_top, z_bot in Z_LAYERS:
        if in_layer_z(z, z_top, z_bot):
            soil_groups[name].append(sh)
            matched = True
            break
    if not matched:
        n_unclassified += 1

print(f"Chua phan loai duoc: {n_unclassified} (phai =0)")
for name, shs in soil_groups.items():
    print(f"  SOIL_{name}: {len(shs)} sub-solid")
for rx, shs in col_groups_by_row.items():
    print(f"  CDM_COLUMN_ROW_X{rx}: {len(shs)} sub-solid")
print(f"  CDM_COLUMN (tong): {len(col_group_all)} sub-solid")

# ================== Mat ngoai: BASE / SIDE_* / TOP_SOIL(_NEGX/POSX) / TOP_COLUMN(_NEGX/POSX) ==================
all_faces = geompy.SubShapeAll(partition, geompy.ShapeType["FACE"])
print(f"So face: {len(all_faces)}")

face_groups = {
    "BASE": [], "SIDE_XMIN": [], "SIDE_XMAX": [], "SIDE_YMIN": [], "SIDE_YMAX": [],
    "TOP_SOIL_NEGX": [], "TOP_SOIL_POSX": [], "TOP_COLUMN_NEGX": [], "TOP_COLUMN_POSX": [],
}
Z_TOP_DOMAIN = Z_LAYERS[0][1]
Z_BOT_DOMAIN = Z_LAYERS[-1][2]
COL_TOP_AREA = 3.14159265 * (D_M / 2.0) ** 2

for f in all_faces:
    fx, fy, fz = centroid(f)
    area = geompy.BasicProperties(f)[1]
    bbox = geompy.BoundingBox(f)  # xmin,xmax,ymin,ymax,zmin,zmax
    xlo, xhi, ylo, yhi, zlo, zhi = bbox
    if abs(zlo - Z_BOT_DOMAIN) < EPS and abs(zhi - Z_BOT_DOMAIN) < EPS:
        face_groups["BASE"].append(f)
    elif abs(zlo - Z_TOP_DOMAIN) < EPS and abs(zhi - Z_TOP_DOMAIN) < EPS:
        is_col_top = area < 3.0 * COL_TOP_AREA
        side = "NEGX" if fx < 0 else "POSX"
        key = ("TOP_COLUMN_" if is_col_top else "TOP_SOIL_") + side
        face_groups[key].append(f)
    elif abs(xlo - X_MIN) < EPS and abs(xhi - X_MIN) < EPS:
        face_groups["SIDE_XMIN"].append(f)
    elif abs(xlo - X_MAX) < EPS and abs(xhi - X_MAX) < EPS:
        face_groups["SIDE_XMAX"].append(f)
    elif abs(ylo - Y_MIN) < EPS and abs(yhi - Y_MIN) < EPS:
        face_groups["SIDE_YMIN"].append(f)
    elif abs(ylo - Y_MAX) < EPS and abs(yhi - Y_MAX) < EPS:
        face_groups["SIDE_YMAX"].append(f)

for k, v in face_groups.items():
    print(f"  {k}: {len(v)} face")

# ================== Luoi (NETGEN 1D-2D-3D, kich thuoc thay doi gan coc) ==================
print("=== Dung luoi ===")
mesh = smesh.Mesh(partition, "KE_scenario35")
netgen_algo = mesh.Tetrahedron(algo=smeshBuilder.NETGEN_1D2D3D)
netgen_params = netgen_algo.Parameters()
netgen_params.SetMaxSize(MESH_SIZE_FAR)
netgen_params.SetMinSize(MESH_SIZE_NEAR_COLUMN)
netgen_params.SetOptimize(True)
netgen_params.SetFineness(smeshBuilder.Moderate)

# tinh chinh kich thuoc gan coc: gan Local Length nho cho cac face/edge cua coc
for sh in col_group_all:
    sub_mesh = mesh.Tetrahedron(algo=smeshBuilder.NETGEN_1D2D3D, geom=sh)
    p2 = sub_mesh.Parameters()
    p2.SetMaxSize(MESH_SIZE_NEAR_COLUMN)
    p2.SetMinSize(MESH_SIZE_NEAR_COLUMN * 0.5)
    p2.SetOptimize(True)

ok = mesh.Compute()
print(f"Compute mesh: {'OK' if ok else 'THAT BAI'}")
if not ok:
    raise RuntimeError("Khong the tao luoi — kiem tra log Salome.")

print(f"So nut: {mesh.NbNodes()}  so phan tu tetra: {mesh.NbTetras()}")

# ================== Nhom mesh — GroupOnGeom (an toan, KHONG chong lan) ==================
print("=== Tao nhom mesh ===")
for name, shs in soil_groups.items():
    if not shs:
        continue
    comp = geompy.MakeCompound(shs) if len(shs) > 1 else shs[0]
    mesh.GroupOnGeom(comp, f"SOIL_{name}", SMESH.VOLUME)

for rx, shs in col_groups_by_row.items():
    if not shs:
        continue
    comp = geompy.MakeCompound(shs) if len(shs) > 1 else shs[0]
    label = f"{rx:.3f}".rstrip("0").rstrip(".").replace("-", "m").replace(".", "p")
    if label in ("", "m"):
        label = "0"
    mesh.GroupOnGeom(comp, f"CDM_COLUMN_ROW_X{label}", SMESH.VOLUME)

if col_group_all:
    comp_all = geompy.MakeCompound(col_group_all)
    mesh.GroupOnGeom(comp_all, "CDM_COLUMN", SMESH.VOLUME)

for name, faces in face_groups.items():
    if not faces:
        continue
    comp = geompy.MakeCompound(faces) if len(faces) > 1 else faces[0]
    mesh.GroupOnGeom(comp, name, SMESH.FACE)

print("=== Xuat MED ===")
mesh.ExportMED(OUT_MED, 0)
print(f"Da ghi: {OUT_MED}")
