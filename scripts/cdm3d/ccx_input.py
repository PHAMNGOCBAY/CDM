"""cdm3d.ccx_input — Chuyen luoi gmsh (.msh) sang deck CalculiX (.inp) — chuoi
GIAI DOAN THI CONG (staged construction) + TAI LECH TAM.

Don vi nhat quan he kN-m-s (kPa = kN/m^2): khoi luong rieng = gamma_kNm3/9.81
(kN*s^2/m^4) de *DLOAD ,GRAV voi gia toc 9.81 m/s^2 cho dung trong luong ban than.

=== Chuoi giai doan (khi use_model_change=True, mac dinh) ===
  GD0 — San nen: *MODEL CHANGE REMOVE CDM_COLUMN + khoa tam *BOUNDARY cac nut
        "mo coi" (chi thuoc CDM_COLUMN, khong tiep giap dat) de tranh ma tran
        suy bien. KHONG tai.
  GD1 — Thi cong coc: *MODEL CHANGE ADD CDM_COLUMN (mac dinh STRAIN FREE — coc
        "sinh ra" khong ung suat) + go khoa (*BOUNDARY, OP=NEW chi liet ke lai
        dieu kien bien vinh vien BASE/SIDE_*). KHONG tai.
  GD2..N — Dap tung lop: params.stages (LoadStage) — tai q_avg_kPa + do lech
        tam eccentricity_m tang dan qua tung giai doan. Moi giai doan ghi lai
        TOAN BO gia tri *CLOAD hien hanh (khong dua vao co che cong don OP=MOD
        giua cac step — an toan, de kiem chung).

*MODEL CHANGE ADD=STRAIN FREE **bat buoc *STEP,NLGEOM** — da kiem chung thuc
nghiem bang ccx_static.exe that (loi neu thieu: "a strain-free addition of
elements ... is only possible for nonlinear calculations"), xem
scratch/test_model_change.py va 76-cdm3d-fem-gmsh-calculix.md.

Don gian hoa V1 khac (ghi ro trong 76-cdm3d-fem-gmsh-calculix.md):
  - Vat lieu dan hoi tuyen tinh mac dinh cho dat va tru CDM — CO THE bat
    *MOHR COULOMB cho tung elset qua tham so mohr_coulomb= cua write_ccx_inp()
    (them 2026-08-27, phi=psi=0 mac dinh => Tresca, khop quy uoc Su du an).
  - Lien ket tru-dat: BONDED (dung chung nut tai bien, khong co truot/tach lop).
  - Tai dap gia tai q: DA SUA 2026-08-27 — ghi qua *DLOAD ap luc mat CHUAN
    (P1-P4 tung mat phan tu C3D4, danh gia _eccentric_pressure() tai trong tam
    tung tam giac bien), KHONG con quy doi luc nut tap trung nhu truoc.
  - Trong luong ban than: dung *DLOAD ,GRAV (chinh xac, khong xap xi) — mac dinh
    TAT (xem write_ccx_inp docstring — ly do da kiem chung thuc te).
"""
from __future__ import annotations

from pathlib import Path

import meshio
import numpy as np

from .types import LoadStage, ModelParams

_G = 9.81  # m/s^2

_ELEM_TYPE_BY_ORDER = {1: ("tetra", "C3D4"), 2: ("tetra10", "C3D10")}
_FACE_TYPE_BY_ORDER = {1: "triangle", 2: "triangle6"}

# Anh xa mat cuc bo cho C3D4 (tu diem 4 nut) — lay tu ma nguon Fortran goc
# getnodel.f (KHONG doan, da kiem chung 2026-08-27 trong .claude/commands/cdm3d-contact.md).
# Da doi chieu voi *DLOAD Px (ccx_2.23.pdf muc 7.44, tetrahedral elements:
# Face1=1-2-3, Face2=1-4-2, Face3=2-4-3, Face4=3-4-1) — TRUNG KHOP HOAN TOAN
# ve tap nut voi S1-S4 (chi khac ten the: "P<k>" cho *DLOAD, "S<k>" cho
# *SURFACE/*CONTACT PAIR) — dung CHUNG 1 bang FACE_LOCAL cho ca 2 muc dich.
FACE_LOCAL = {1: (0, 2, 1), 2: (0, 1, 3), 3: (1, 2, 3), 4: (0, 3, 2)}


def _find_element_faces(all_tetra: np.ndarray, target_faces: np.ndarray,
                         elem_id_offset: int = 0, label_prefix: str = "S") -> list[tuple[int, str]]:
    """Tim (elem_1indexed, '<label_prefix><k>') cho tung tam giac bien trong
    target_faces, tra ve dung thu tu. label_prefix='S' cho *SURFACE/*CONTACT
    PAIR, 'P' cho *DLOAD ap luc mat — CUNG 1 bang FACE_LOCAL (da xac nhan
    trung khop giua 2 quy uoc, xem ghi chu tren)."""
    node_to_elems: dict[int, list[int]] = {}
    for ei, tet in enumerate(all_tetra):
        for n in tet:
            node_to_elems.setdefault(int(n), []).append(ei)

    result = []
    for tri in target_faces:
        tri_set = set(int(x) for x in tri)
        cand = set()
        for n in tri:
            cand.update(node_to_elems.get(int(n), []))
        found = False
        for ei in cand:
            tet = all_tetra[ei]
            tet_set = set(int(x) for x in tet)
            if tri_set.issubset(tet_set):
                for face_id, (a, b, c) in FACE_LOCAL.items():
                    if {int(tet[a]), int(tet[b]), int(tet[c])} == tri_set:
                        result.append((ei + 1 + elem_id_offset, f"{label_prefix}{face_id}"))
                        found = True
                        break
                if found:
                    break
        if not found:
            raise ValueError(f"Khong tim thay tet chua mat {tri_set}")
    return result


def _read_boundary_triangles(msh_path: Path, order: int, group_names: tuple[str, ...]) -> np.ndarray:
    """Tra ve mang (N,3) chi so nut (0-indexed) cua tung tam giac bien thuoc 1
    hoac nhieu Physical Group be mat — dung cho *DLOAD ap luc mat theo tung
    phan tu (khac _node_tributary_area() chi tra ve dien tich gop theo nut)."""
    m = meshio.read(str(msh_path))
    tag_to_name: dict[int, str] = {}
    for name, (tag, dim) in m.field_data.items():
        if dim == 2:
            tag_to_name[tag] = name

    face_type = _FACE_TYPE_BY_ORDER[order]
    tris = []
    for i, block in enumerate(m.cells):
        if block.type != face_type:
            continue
        tags = m.cell_data.get("gmsh:physical", [None] * len(m.cells))[i]
        if tags is None:
            continue
        for j in range(block.data.shape[0]):
            name = tag_to_name.get(int(tags[j]))
            if name in group_names:
                tris.append(block.data[j][:3])
    return np.array(tris, dtype=int) if tris else np.empty((0, 3), dtype=int)


def _read_mesh(msh_path: Path, order: int) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Tra ve (points [1-indexed ghi rieng], elements[N,nnode] 0-indexed, elsets theo
    Physical Group 3D {name: elem_local_idx}, nsets theo Physical Group 2D {name: node_idx (0-indexed)}."""
    m = meshio.read(str(msh_path))
    meshio_type, _ = _ELEM_TYPE_BY_ORDER[order]

    tag_to_name: dict[int, tuple[str, int]] = {}
    for name, (tag, dim) in m.field_data.items():
        tag_to_name[tag] = (name, dim)

    elem_chunks, elem_tags_chunks = [], []
    offset = 0
    elset_ranges: dict[str, list[int]] = {}
    for i, block in enumerate(m.cells):
        if block.type != meshio_type:
            continue
        tags = m.cell_data.get("gmsh:physical", [None] * len(m.cells))[i]
        elem_chunks.append(block.data)
        n = block.data.shape[0]
        for j in range(n):
            tag = int(tags[j]) if tags is not None else -1
            name, dim = tag_to_name.get(tag, (f"tag_{tag}", 3))
            if dim == 3:
                elset_ranges.setdefault(name, []).append(offset + j)
        offset += n
    elements = np.vstack(elem_chunks) if elem_chunks else np.empty((0, 4), dtype=int)
    elsets = {k: np.array(v, dtype=int) for k, v in elset_ranges.items()}

    face_type = _FACE_TYPE_BY_ORDER[order]
    nset_ranges: dict[str, set[int]] = {}
    for i, block in enumerate(m.cells):
        if block.type != face_type:
            continue
        tags = m.cell_data.get("gmsh:physical", [None] * len(m.cells))[i]
        if tags is None:
            continue
        for j in range(block.data.shape[0]):
            name, dim = tag_to_name.get(int(tags[j]), (None, None))
            if name is not None and dim == 2:
                nset_ranges.setdefault(name, set()).update(block.data[j].tolist())
    nsets = {k: np.array(sorted(v), dtype=int) for k, v in nset_ranges.items()}

    return m.points, elements, elsets, nsets


def _node_tributary_area(msh_path: Path, order: int, group_names: tuple[str, ...]) -> dict[int, float]:
    """Dien tich anh huong (tributary area) THAT cho tung nut tren 1 hoac nhieu
    Physical Group be mat (tam giac), = tong (dien_tich_tam_giac/3) qua moi tam
    giac ke can. BAT BUOC dung cho tai lech tam — luoi quanh cot day dac hon
    nhieu vung xa (Box mesh size field), neu chia deu dien_tich/so_nut se "pha
    loang" do lech tam thuc te (da kiem chung: cau hinh e=0.7m chi con e_thuc~0.12m
    neu chia deu — sai ~83%)."""
    m = meshio.read(str(msh_path))
    tag_to_name: dict[int, str] = {}
    for name, (tag, dim) in m.field_data.items():
        if dim == 2:
            tag_to_name[tag] = name

    face_type = _FACE_TYPE_BY_ORDER[order]
    areas: dict[int, float] = {}
    for i, block in enumerate(m.cells):
        if block.type != face_type:
            continue
        tags = m.cell_data.get("gmsh:physical", [None] * len(m.cells))[i]
        if tags is None:
            continue
        for j in range(block.data.shape[0]):
            name = tag_to_name.get(int(tags[j]))
            if name not in group_names:
                continue
            n0, n1, n2 = block.data[j][:3]
            p0, p1, p2 = m.points[n0], m.points[n1], m.points[n2]
            tri_area = 0.5 * float(np.linalg.norm(np.cross(p1 - p0, p2 - p0)))
            share = tri_area / 3.0
            for n in (n0, n1, n2):
                areas[int(n)] = areas.get(int(n), 0.0) + share
    return areas


def _material_for_elset(name: str, params: ModelParams) -> tuple[float, float, float]:
    """Tra ve (E_kPa, nu, gamma_kNm3) cho 1 elset theo ten Physical Group."""
    if name == "CDM_COLUMN":
        c = params.column
        return c.Ec_kPa, c.nu_c, c.gamma_kNm3
    layer_name = name.removeprefix("SOIL_")
    for layer in params.soil_layers:
        if layer.name == layer_name:
            return layer.E_kPa, layer.nu, layer.gamma_kNm3
    raise KeyError(f"Khong tim thay vat lieu cho elset '{name}'")


def _orphan_column_nodes(elements: np.ndarray, elsets: dict[str, np.ndarray]) -> np.ndarray:
    """Nut CHI thuoc CDM_COLUMN, KHONG tiep giap bat ky SOIL_* nao — se mat het do
    cung khi cot bi *MODEL CHANGE REMOVE, gay ma tran do cung toan cuc suy bien
    (loi pivot) neu khong khoa tam. Da kiem chung thuc nghiem bang ccx_static.exe
    (scratch/test_model_change.py, mo hinh 1 cot: 224 nut thuoc cot, 25 nut mo coi)."""
    if "CDM_COLUMN" not in elsets:
        return np.empty(0, dtype=int)
    col_nodes = set(elements[elsets["CDM_COLUMN"]].ravel().tolist())
    soil_nodes: set[int] = set()
    for name, idx in elsets.items():
        if name.startswith("SOIL_"):
            soil_nodes.update(elements[idx].ravel().tolist())
    return np.array(sorted(col_nodes - soil_nodes), dtype=int)


def validate_eccentricity(e_m: float, B_m: float) -> tuple[float, str | None]:
    """Quy tac loi giua (kern) mong lech tam: |e| <= B/6, neu khong ap luc 1 mep
    se am (dat chiu keo — vo ly vat ly). Vuot han -> clamp ve B/6, tra canh bao."""
    limit = B_m / 6.0
    if abs(e_m) > limit:
        sign = 1.0 if e_m >= 0 else -1.0
        warn = (f"eccentricity_m={e_m:.3f} vuot qua gioi han loi giua B/6={limit:.3f} "
                f"(B={B_m:.2f}m) — se sinh ap luc am (dat chiu keo, vo ly vat ly). "
                f"Da CLAMP ve {sign * limit:.3f}.")
        return sign * limit, warn
    return e_m, None


def _eccentric_pressure(pos: float, q_avg_kPa: float, e_m: float, B_m: float) -> float:
    """Ung suat day mong lech tam (sigma = N/A + M*x/I, M=P*e, I=L*B^3/12):
    q(pos) = q_avg * (1 + 12*e*pos / B^2). He so 12 (KHONG phai 6) vi day la HAM
    TONG QUAT theo pos — he so 6 chi dung khi danh gia TAI MEP (pos=B/2), la cong
    thuc "q_max/min = q_avg*(1 +/- 6e/B)" quen thuoc trong sach giao khoa. Da kiem
    chung bang tich phan: dung he so 12 thi hop luc ∫q(x)x dA / ∫q(x) dA = e dung
    boi 100% (he so 6 se cho ket qua chi bang mot nua e — da phat hien thuc te khi
    kiem tra tong hop luc luc dau trien khai).
    pos = toa do (x hoac y) tinh TU TAM (khoi tam nhom tru dat tai goc toa do —
    xem geometry.column_centers()), KHONG phai toa do tuyet doi."""
    return q_avg_kPa * (1.0 + 12.0 * e_m * pos / (B_m ** 2))


def _write_load_step(lines: list[str], stage: LoadStage, points: np.ndarray,
                      elements: np.ndarray, boundary_tris: np.ndarray,
                      B_x: float, B_y: float, include_self_weight: bool,
                      elsets: dict[str, np.ndarray], nlgeom: bool,
                      warnings: list[str]) -> None:
    """Tai dap ghi qua *DLOAD ap luc mat CHUAN (P1-P4 tren tung mat phan tu
    C3D4, KHONG con quy doi thanh luc nut tap trung — sua 2026-08-27 theo yeu
    cau: 'phai ap luc mat *DLOAD chuan'). Ap luc lech tam _eccentric_pressure()
    danh gia tai TRONG TAM tung tam giac bien (khong phai tung nut) — chinh
    xac hon ve mat vat ly (1 gia tri ap luc DONG DEU tren ca mat phan tu, dung
    ban chat *DLOAD Px cua CalculiX, khong the khai bao gradient trong 1 mat)."""
    lines.append("*STEP, NLGEOM" if nlgeom else "*STEP")
    lines.append("*STATIC")

    dload_lines: list[str] = []
    if include_self_weight:
        for name in elsets:
            dload_lines.append(f"{name}, GRAV, {_G:.3f}, 0., 0., -1.")

    if stage.q_avg_kPa > 0 and len(boundary_tris) == 0:
        warnings.append(
            f"[{stage.name}] q_avg_kPa={stage.q_avg_kPa} > 0 nhung khong co tam "
            f"giac bien TOP_SOIL/TOP_COLUMN — KHONG ghi *DLOAD, giai doan nay se "
            f"giai voi tai = 0 mot cach am tham. Kiem tra lai geometry.py da tao "
            f"Physical Group TOP_SOIL/TOP_COLUMN chua."
        )
    if stage.q_avg_kPa > 0 and len(boundary_tris) > 0:
        B = B_x if stage.ecc_axis == "x" else B_y
        axis_col = 0 if stage.ecc_axis == "x" else 1
        face_labels = _find_element_faces(elements, boundary_tris, label_prefix="P")

        if stage.load_footprint == "full":
            e_use, warn = validate_eccentricity(stage.eccentricity_m, B)
            if warn:
                warnings.append(f"[{stage.name}] {warn}")
            for tri, (elem_id, label) in zip(boundary_tris, face_labels):
                centroid = points[tri].mean(axis=0)  # da tam o goc toa do (0,0) — xem geometry.py
                pos = centroid[axis_col]
                q_i = _eccentric_pressure(pos, stage.q_avg_kPa, e_use, B)
                dload_lines.append(f"{elem_id}, {label}, {q_i:.6f}")
        else:
            # 'half_pos'/'half_neg' — tai UNIFORM q_avg_kPa CHI tren 1 nua domain
            # (bac thang, khong phai gradient) — dung khi tai thiet ke chi dap 1
            # vung gioi han, KHONG dap ra het vung dem tinh toan.
            sign = 1.0 if stage.load_footprint == "half_pos" else -1.0
            n_loaded = 0
            for tri, (elem_id, label) in zip(boundary_tris, face_labels):
                centroid = points[tri].mean(axis=0)
                pos = centroid[axis_col]
                if sign * pos < 0:
                    continue  # ngoai vung tai — khong ghi dong *DLOAD (mac dinh 0)
                dload_lines.append(f"{elem_id}, {label}, {stage.q_avg_kPa:.6f}")
                n_loaded += 1
            if n_loaded == 0:
                warnings.append(
                    f"[{stage.name}] load_footprint='{stage.load_footprint}' nhung "
                    f"KHONG co mat nao trong vung tai (kiem tra ecc_axis/domain)."
                )

    if dload_lines:
        lines.append("*DLOAD")
        lines.extend(dload_lines)

    lines += ["*NODE FILE", "U", "*EL FILE", "S, E", "*END STEP"]


def write_ccx_inp(msh_path: Path, out_inp: Path, params: ModelParams,
                   element_order: int = 1, job_name: str | None = None,
                   include_self_weight: bool = False,
                   use_model_change: bool = True,
                   mohr_coulomb: dict[str, dict] | None = None) -> Path:
    """mohr_coulomb: {ten_elset: {"c_kPa": float, "phi_deg": float = 0.0,
    "psi_deg": float = 0.0}} — cac elset (vd "SOIL_dat_yeu") duoc liet ke se
    dung *MOHR COULOMB thay vi thuan *ELASTIC (van giu *ELASTIC ben duoi, BAT
    BUOC theo tai lieu CalculiX). phi=psi=0 (mac dinh) => quy ve dung Tresca,
    khop quy uoc du an cho set khong thoat nuoc (c=Su, phi=0 — CLAUDE.md
    Bishop/Fellenius). Cu phap tra cuu chinh thuc: ccx_2.23.pdf muc 7.90-7.91."""
    """include_self_weight=False (mac dinh): KHONG dat *DLOAD GRAV — vi CHUA co buoc
    khoi tao ung suat geostatic (K0), ap trong luong ban than tu trang thai ung suat=0
    se cho chuyen vi dan hoi RAT LON va SAI (da kiem chung: E=3450 kPa, gamma=16,
    H=23m -> S ~ gamma*H^2/(2E) ~ 1.2 m, hoan toan khong thuc te). Bo GRAV -> chuyen
    vi tinh duoc la LUN DO RIENG TAI TRONG DAP q GAY RA — dai luong co the so sanh
    truc tiep voi cong thuc S1 TCVN 9403 Phu luc C da co san (vd zone KE ~10.3 cm).

    use_model_change=True (mac dinh): coc CDM duoc kich hoat dung giai doan thi
    cong qua GD0(remove)->GD1(add strain-free) truoc khi dap tai GD2..N — xem
    docstring dau file. False: coc ton tai xuyen suot ngay tu dau (kich ban don
    gian cu, khong staged), moi giai doan trong params.stages van duoc giai tuan
    tu nhung khong co *MODEL CHANGE/*BOUNDARY OP=NEW.
    """
    msh_path, out_inp = Path(msh_path), Path(out_inp)
    _, elem_type = _ELEM_TYPE_BY_ORDER[element_order]
    points, elements, elsets, nsets = _read_mesh(msh_path, element_order)
    job_name = job_name or out_inp.stem

    lines: list[str] = [f"** cdm3d — {job_name} — sinh tu dong, xem scripts/cdm3d/ccx_input.py",
                         f"** zone={params.zone_code}  element={elem_type}  don vi: kN-m-s (kPa)"]

    lines.append("*NODE, NSET=NALL")
    for i, (x, y, z) in enumerate(points, start=1):
        lines.append(f"{i}, {x:.6f}, {y:.6f}, {z:.6f}")

    for name, idx in elsets.items():
        lines.append(f"*ELEMENT, TYPE={elem_type}, ELSET={name}")
        for k in idx:
            nodes = elements[k] + 1  # CalculiX 1-indexed
            lines.append(f"{k + 1}, " + ", ".join(str(n) for n in nodes))

    mohr_coulomb = mohr_coulomb or {}
    for name in elsets:
        E_kPa, nu, gamma = _material_for_elset(name, params)
        mat = f"MAT_{name}"
        rho = gamma / _G
        lines += [
            f"*MATERIAL, NAME={mat}",
            "*ELASTIC",
            f"{E_kPa:.3f}, {nu:.3f}",
        ]
        if name in mohr_coulomb:
            mc = mohr_coulomb[name]
            c_kPa = mc["c_kPa"]
            phi_deg = mc.get("phi_deg", 0.0)
            psi_deg = mc.get("psi_deg", 0.0)
            lines += [
                "*MOHR COULOMB",
                f"{phi_deg:.3f}, {psi_deg:.3f}, 293.",
                "*MOHR COULOMB HARDENING",
                f"{c_kPa:.3f}, 0., 293.",
            ]
        lines += [
            "*DENSITY",
            f"{rho:.6f}",
            f"*SOLID SECTION, ELSET={name}, MATERIAL={mat}",
        ]

    for name, idx in nsets.items():
        lines.append(f"*NSET, NSET={name}")
        for chunk_start in range(0, len(idx), 10):
            chunk = idx[chunk_start:chunk_start + 10] + 1
            lines.append(", ".join(str(n) for n in chunk))

    if "BASE" not in nsets:
        raise ValueError(
            "Khong tim thay NSET 'BASE' (day mo hinh) trong luoi — kiem tra lai "
            "geometry.build_geometry() da tao Physical Group BASE chua truoc khi "
            "ghi *BOUNDARY (neu thieu, CalculiX se bao loi fatal khi doc file .inp)."
        )
    perm_bc = ["BASE, 1, 3"]
    if "SIDE_XMIN" in nsets:
        perm_bc.append("SIDE_XMIN, 1, 1")
    if "SIDE_XMAX" in nsets:
        perm_bc.append("SIDE_XMAX, 1, 1")
    if "SIDE_YMIN" in nsets:
        perm_bc.append("SIDE_YMIN, 2, 2")
    if "SIDE_YMAX" in nsets:
        perm_bc.append("SIDE_YMAX, 2, 2")
    lines += ["*BOUNDARY"] + perm_bc

    has_column = "CDM_COLUMN" in elsets
    do_model_change = use_model_change and has_column

    if do_model_change:
        orphan = _orphan_column_nodes(elements, elsets)
        if len(orphan) > 0:
            lines.append("*NSET, NSET=ORPHAN")
            for cs in range(0, len(orphan), 10):
                chunk = orphan[cs:cs + 10] + 1
                lines.append(", ".join(str(n) for n in chunk))

        # GD(-1) — buoc "dummy" TOAN BO phan tu active, KHONG *MODEL CHANGE, khong
        # tai. BAT BUOC: da kiem chung thuc nghiem — .frd chi ghi 1 lan duy nhat
        # mesh/element definition (khong ghi lai moi buoc), lay theo tap phan tu
        # ACTIVE cua buoc DAU TIEN trong file. Neu GD0 (REMOVE cot) la buoc dau
        # tien, cot se bi loai VINH VIEN khoi .frd — ke ca sau khi GD1 ADD lai —
        # vi mesh block da "dong bang" thieu cot ngay tu dau (da thu that: mesh
        # block chi con 150270/172358 phan tu, dung bang tong SOIL_*, thieu dung
        # 22088 phan tu CDM_COLUMN). Xem scratch test + 76-cdm3d-fem-gmsh-calculix.md.
        lines += ["*STEP", "*STATIC", "*NODE FILE", "U", "*END STEP"]

        # GD0 — San nen: bo cot, khoa tam nut mo coi
        lines += ["*STEP, NLGEOM", "*STATIC",
                  "*MODEL CHANGE, TYPE=ELEMENT, REMOVE", "CDM_COLUMN"]
        if len(orphan) > 0:
            lines += ["*BOUNDARY", "ORPHAN, 1, 3"]
        lines += ["*NODE FILE", "U", "*END STEP"]

        # GD1 — Thi cong coc (sinh khong ung suat), go khoa tam
        lines += ["*STEP, NLGEOM", "*STATIC",
                  "*MODEL CHANGE, TYPE=ELEMENT, ADD", "CDM_COLUMN",
                  "*BOUNDARY, OP=NEW"] + perm_bc + ["*NODE FILE", "U", "*END STEP"]

    # GD2..N — dap tang dan (params.stages), giu tuong thich nguoc qua fallback
    stages = params.stages or [LoadStage("GD2 - Tai thiet ke", params.q_surcharge_kPa, 0.0)]
    # Tam giac bien THAT (khong phai chi so nut gop) — dung cho *DLOAD ap luc
    # mat theo tung phan tu (thay the hoan toan *CLOAD luc nut tap trung cu).
    boundary_tris = _read_boundary_triangles(msh_path, element_order, ("TOP_SOIL", "TOP_COLUMN"))
    B_x, B_y = params.domain_x_m(), params.domain_y_m()

    # GD2..N dung CUNG che do NLGEOM voi GD0/GD1 (du ban than khong co *MODEL
    # CHANGE) — de nhat quan xuyen suot 1 phan tich (tranh doi che do giua cac
    # *STEP lien tiep, chua kiem chung CalculiX co cho phep tin cay hay khong).
    for stage in stages:
        _write_load_step(lines, stage, points, elements, boundary_tris, B_x, B_y,
                          include_self_weight, elsets, do_model_change, params.warnings)

    out_inp.parent.mkdir(parents=True, exist_ok=True)
    out_inp.write_text("\n".join(lines) + "\n", encoding="ascii", errors="replace")
    return out_inp
