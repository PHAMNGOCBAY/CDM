"""cdm3d.contact_ccx_input — Gop 2 luoi doc lap (dat co lo + cot rieng, tu
contact_geometry.py) thanh 1 deck CalculiX co *CONTACT PAIR (ma sat Coulomb).

Da kiem chung thuc nghiem tren mo hinh nho (2026-08-27, xem
.claude/commands/cdm3d-contact.md muc "Ket qua kiem chung"):
  - Bang anh xa mat S1-S4 cho C3D4 lay tu ma nguon Fortran goc getnodel.f (KHONG
    doan): S1={cuc bo 1,3,2} S2={1,2,4} S3={2,3,4} S4={1,4,3}.
  - Quy uoc dependent/master: mat MEM HON + luoi THO HON (dat) = dependent (liet
    ke DAU trong *CONTACT PAIR); mat CUNG HON + luoi MIN HON (cot) = master.
  - Can khai bao ro K (PRESSURE-OVERCLOSURE) va stick slope (*FRICTION) — de mac
    dinh CalculiX se canh bao va tu chon gia tri suy tu do cung phan tu lan can.
  - Hoi tu can nhieu lan tu dong giam buoc tang tai (binh thuong cho contact+ma
    sat phi tuyen) — KHONG phai loi.

CHUA lam: chuoi giai doan kich hoat cot (*MODEL CHANGE GD0/GD1) — bo qua o phien
ban contact nay de giam do phuc tap chong chat (2 lop phi tuyen: MODEL CHANGE +
CONTACT chua tung test cung nhau). Cot duoc coi la DA TON TAI tu dau (da dong
cung), chi co cac giai doan tai GD2..N.
"""
from __future__ import annotations

from pathlib import Path

import meshio
import numpy as np

from .ccx_input import _eccentric_pressure, _node_tributary_area, validate_eccentricity
from .types import LoadStage, ModelParams

_G = 9.81
FACE_LOCAL = {1: (0, 2, 1), 2: (0, 1, 3), 3: (1, 2, 3), 4: (0, 3, 2)}

# Alpha Tomlinson (1980), Hinh 18, TCVN 11823-10:2017 Dieu 7.3.8.6.2 — LAY DUNG
# BANG DA DUOC DUNG TRONG DU AN (scripts/ke_sw_nt_calc.py, ma sat DUONG cho coc
# van SW) — dung LAI cho ma sat AM (chi doi chieu), KHONG tao bang moi.
_TOMLINSON_PTS: list[tuple[float, float]] = [
    (0.0, 1.00), (25.0, 1.00), (50.0, 0.92), (75.0, 0.75),
    (100.0, 0.60), (150.0, 0.50), (200.0, 0.40),
]


def _alpha_tomlinson(su_kPa: float) -> float:
    if su_kPa <= 0.0:
        return 0.0
    if su_kPa >= _TOMLINSON_PTS[-1][0]:
        return _TOMLINSON_PTS[-1][1]
    for (s0, a0), (s1, a1) in zip(_TOMLINSON_PTS, _TOMLINSON_PTS[1:]):
        if s0 <= su_kPa <= s1:
            return round(a0 + (su_kPa - s0) / (s1 - s0) * (a1 - a0), 4)
    return 1.0


def alpha_equivalent_mu(su_kPa: float, params: ModelParams, z_ref_m: float) -> dict:
    """Quy doi bam dinh alpha-method (Ca = alpha*Su, KHONG phu thuoc ung suat
    phap) sang he so ma sat Coulomb TUONG DUONG cho *FRICTION cua CalculiX —
    BAT BUOC phai xap xi the nay vi da xac minh (WebSearch + tai lieu chinh thuc
    feacluster.com/CalculiX 2026-08-27): CalculiX *FRICTION CHI ho tro Coulomb
    (tau = mu*p, ti le voi ap luc phap tuyen), KHONG co tham so "shear stress
    limit" doc lap nhu TAUMAX cua Abaqus.

    sigma'v(z_ref) dung ModelParams.sigma_v_eff_kPa() — tich phan gamma HIEU DUNG
    qua tung lop + xet muc nuoc ngam (params.water_table_elev), KHONG con don
    gian gamma*z 1 lop nhu ban dau (2026-08-27).

    mu_equiv = Ca / sigma'v(z_ref) — CHI DUNG TAI z_ref, khac voi mo hinh Coulomb
    that (mu KHONG doi theo do sau trong khi Ca/sigma'v THAY DOI theo do sau) —
    day la XAP XI, PHAI ghi ro trong ket qua, KHONG chinh xac o moi do sau."""
    alpha = _alpha_tomlinson(su_kPa)
    Ca_kPa = alpha * su_kPa
    sigma_v_kPa = params.sigma_v_eff_kPa(z_ref_m)
    mu_equiv = Ca_kPa / sigma_v_kPa if sigma_v_kPa > 0 else 0.0
    return {"alpha": alpha, "Ca_kPa": Ca_kPa, "sigma_v_ref_kPa": sigma_v_kPa,
            "mu_equiv": round(mu_equiv, 4),
            "warning": (f"mu_equiv={mu_equiv:.4f} suy tu Ca={Ca_kPa:.1f}kPa "
                        f"(alpha={alpha}, Su={su_kPa}kPa) / sigma'v_hieu_dung={sigma_v_kPa:.0f}kPa "
                        f"tai z_ref={z_ref_m}m (co xet MNN={params.water_table_elev}m) — "
                        f"XAP XI hang so, KHONG chinh xac o do sau khac (Ca thuc te "
                        f"KHONG doi theo do sau, con Coulomb ti le voi ap luc phap tuyen).")}


def _material_for_name(name: str, params: ModelParams) -> tuple[float, float, float]:
    if name == "CDM_COLUMN":
        c = params.column
        return c.Ec_kPa, c.nu_c, c.gamma_kNm3
    layer_name = name.removeprefix("SOIL_")
    for layer in params.soil_layers:
        if layer.name == layer_name:
            return layer.E_kPa, layer.nu, layer.gamma_kNm3
    raise KeyError(f"Khong tim thay vat lieu cho '{name}'")


def _read_mesh_groups(msh_path: Path) -> dict:
    """Doc 1 file .msh doc lap -> points, tetra theo elset (3D), triangle theo
    nset (2D). KHAC ccx_input._read_mesh o cho KHONG can element_order (luon C3D4)
    va tra ve CA triangle connectivity (can cho *SURFACE, khong chi node membership)."""
    m = meshio.read(str(msh_path))
    tag_to_name3 = {tag: name for name, (tag, dim) in m.field_data.items() if dim == 3}
    tag_to_name2 = {tag: name for name, (tag, dim) in m.field_data.items() if dim == 2}

    tetra_by_name: dict[str, list] = {}
    tri_by_name: dict[str, list] = {}
    for i, block in enumerate(m.cells):
        tags = m.cell_data.get("gmsh:physical", [None] * len(m.cells))[i]
        if tags is None:
            continue
        if block.type == "tetra":
            for j in range(block.data.shape[0]):
                name = tag_to_name3.get(int(tags[j]))
                if name:
                    tetra_by_name.setdefault(name, []).append(block.data[j])
        elif block.type == "triangle":
            for j in range(block.data.shape[0]):
                name = tag_to_name2.get(int(tags[j]))
                if name:
                    tri_by_name.setdefault(name, []).append(block.data[j])

    tetra_by_name = {k: np.array(v) for k, v in tetra_by_name.items()}
    tri_by_name = {k: np.array(v) for k, v in tri_by_name.items()}
    return {"points": m.points, "tetra": tetra_by_name, "tri": tri_by_name}


def _find_s_faces(all_tetra: np.ndarray, target_faces: np.ndarray, elem_id_offset: int = 0) -> list[tuple[int, str]]:
    """Tim (elem_1indexed, 'S<k>') cho tung tam giac bien trong target_faces, tra
    ve dung thu tu. Xay index nut->phan tu de tim nhanh (khong duyet toan bo)."""
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
                        result.append((ei + 1 + elem_id_offset, f"S{face_id}"))
                        found = True
                        break
                if found:
                    break
        if not found:
            raise ValueError(f"Khong tim thay tet chua mat {tri_set}")
    return result


def _tri_area(points: np.ndarray, tri: np.ndarray) -> float:
    p0, p1, p2 = points[tri[0]], points[tri[1]], points[tri[2]]
    return 0.5 * float(np.linalg.norm(np.cross(p1 - p0, p2 - p0)))


def write_ccx_inp_contact(soil_msh: Path, col_msh: Path, out_inp: Path, params: ModelParams,
                           mu: float = 0.3, contact_k_kPa_m: float | None = None,
                           stick_slope: float | None = None,
                           job_name: str | None = None) -> Path:
    soil_msh, col_msh, out_inp = Path(soil_msh), Path(col_msh), Path(out_inp)
    job_name = job_name or out_inp.stem

    soil = _read_mesh_groups(soil_msh)
    col = _read_mesh_groups(col_msh)
    n_soil = len(soil["points"])
    all_points = np.vstack([soil["points"], col["points"]])

    soil_elsets = {k: v for k, v in soil["tetra"].items() if k.startswith("SOIL_")}
    col_elsets = {"CDM_COLUMN": col["tetra"]["CDM_COLUMN"]}
    col_elsets_off = {k: v + n_soil for k, v in col_elsets.items()}

    # danh so phan tu toan cuc: soil truoc (theo thu tu elset), roi cot
    elem_ranges: dict[str, tuple[int, int]] = {}
    offset = 0
    ordered_soil = list(soil_elsets.items())
    for name, tetra in ordered_soil:
        elem_ranges[name] = (offset, offset + len(tetra))
        offset += len(tetra)
    n_soil_elem = offset
    ordered_col = list(col_elsets_off.items())
    for name, tetra in ordered_col:
        elem_ranges[name] = (offset, offset + len(tetra))
        offset += len(tetra)

    all_soil_tetra = np.vstack([t for _, t in ordered_soil])

    lines: list[str] = [f"** cdm3d CONTACT — {job_name} — sinh tu dong, xem scripts/cdm3d/contact_ccx_input.py",
                         f"** zone={params.zone_code}  mu={mu}  don vi: kN-m-s (kPa)"]

    lines.append("*NODE, NSET=NALL")
    for i, (x, y, z) in enumerate(all_points, start=1):
        lines.append(f"{i}, {x:.6f}, {y:.6f}, {z:.6f}")

    for name, tetra in ordered_soil:
        lo, hi = elem_ranges[name]
        lines.append(f"*ELEMENT, TYPE=C3D4, ELSET={name}")
        for k in range(len(tetra)):
            nodes = tetra[k] + 1
            lines.append(f"{lo + k + 1}, " + ", ".join(str(n) for n in nodes))
    for name, tetra in ordered_col:
        lo, hi = elem_ranges[name]
        lines.append(f"*ELEMENT, TYPE=C3D4, ELSET={name}")
        for k in range(len(tetra)):
            nodes = tetra[k] + 1
            lines.append(f"{lo + k + 1}, " + ", ".join(str(n) for n in nodes))

    for name in list(soil_elsets) + list(col_elsets):
        E_kPa, nu, gamma = _material_for_name(name, params)
        mat = f"MAT_{name}"
        lines += [f"*MATERIAL, NAME={mat}", "*ELASTIC", f"{E_kPa:.3f}, {nu:.3f}",
                  "*DENSITY", f"{gamma/_G:.6f}", f"*SOLID SECTION, ELSET={name}, MATERIAL={mat}"]

    def write_nset(nset_name: str, node_ids_0idx: np.ndarray, node_offset: int = 0):
        lines.append(f"*NSET, NSET={nset_name}")
        ids = np.unique(node_ids_0idx.ravel()) + 1 + node_offset
        for cs in range(0, len(ids), 10):
            lines.append(", ".join(str(n) for n in ids[cs:cs + 10]))

    write_nset("BASE", soil["tri"]["BASE"])
    for s in ("SIDE_XMIN", "SIDE_XMAX", "SIDE_YMIN", "SIDE_YMAX"):
        if s in soil["tri"]:
            write_nset(s, soil["tri"][s])
    write_nset("COLTOP", col["tri"]["COL_TOP"], node_offset=n_soil)

    lines += ["*SURFACE, NAME=SOIL_INNER, TYPE=ELEMENT"]
    soil_inner_sfaces = _find_s_faces(all_soil_tetra, soil["tri"]["SOIL_INNER"])
    for elem, face in soil_inner_sfaces:
        lines.append(f"{elem}, {face}")
    lines += ["*SURFACE, NAME=COL_LATERAL, TYPE=ELEMENT"]
    # QUAN TRONG: tim S-face bang mang tet CHUA offset (khop voi chi so nut trong
    # col["tri"], vi ban than luoi cot doc lap chua biet gi ve n_soil) — chi offset
    # SO PHAN TU (elem_id_offset) khi ghi ket qua, KHONG offset nut luc tim kiem.
    col_lateral_sfaces = _find_s_faces(col["tetra"]["CDM_COLUMN"], col["tri"]["COL_LATERAL"],
                                        elem_id_offset=n_soil_elem)
    for elem, face in col_lateral_sfaces:
        lines.append(f"{elem}, {face}")

    k_val = contact_k_kPa_m if contact_k_kPa_m is not None else params.column.Ec_kPa / (params.column.D_m * 0.05)
    slope_val = stick_slope if stick_slope is not None else k_val * 0.1
    lines += [
        "*SURFACE INTERACTION, NAME=SOIL_COL_INT",
        "*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=HARD",
        "*FRICTION",
        f"{mu}, {slope_val:.3f}",
        # ADJUST=<gap>: "dinh" cac nut slave co khe ho ban dau <= gap ve dung mat
        # master ngay khi bat dau giai — BAT BUOC vi 2 mat tru duoc mesh o 2 PHIEN
        # gmsh DOC LAP (soil hole vs column lateral), khac tessellation nen co khe
        # ho/chong lan cuc nho o muc do chia luoi (~mm) ngay ca khi hinh hoc danh
        # nghia GIONG HET nhau — da xac nhan thuc nghiem: khong co ADJUST, mo hinh
        # day du 9 cot PHAN KY nghiem trong (residual ~1e12, "too many cutbacks")
        # dung tai 1 nut nam CHINH XAC tren mat tru (r=D/2). Xem
        # 76-cdm3d-fem-gmsh-calculix.md muc 8 / .claude/commands/cdm3d-contact.md.
        f"*CONTACT PAIR, INTERACTION=SOIL_COL_INT, TYPE=NODE TO SURFACE, ADJUST=0.02",
        "SOIL_INNER, COL_LATERAL",
    ]

    perm_bc = ["BASE, 1, 3"]
    for s in ("SIDE_XMIN",):
        if s in soil["tri"]: perm_bc.append(f"{s}, 1, 1")
    for s in ("SIDE_XMAX",):
        if s in soil["tri"]: perm_bc.append(f"{s}, 1, 1")
    for s in ("SIDE_YMIN",):
        if s in soil["tri"]: perm_bc.append(f"{s}, 2, 2")
    for s in ("SIDE_YMAX",):
        if s in soil["tri"]: perm_bc.append(f"{s}, 2, 2")
    lines += ["*BOUNDARY"] + perm_bc

    # dien tich anh huong that: soil TOP_SOIL (tu luoi dat) + col COL_TOP (tu luoi cot)
    node_area_soil = _node_tributary_area(soil_msh, 1, ("TOP_SOIL",))
    node_area_col_raw = {}
    for tri in col["tri"]["COL_TOP"]:
        area = _tri_area(col["points"], tri) / 3.0
        for n in tri:
            node_area_col_raw[int(n)] = node_area_col_raw.get(int(n), 0.0) + area
    node_area_col = {n + n_soil: a for n, a in node_area_col_raw.items()}

    top_idx_soil = np.unique(soil["tri"]["TOP_SOIL"].ravel())
    top_idx_col = np.unique(col["tri"]["COL_TOP"].ravel()) + n_soil
    top_idx = np.concatenate([top_idx_soil, top_idx_col])
    node_area = {**node_area_soil, **node_area_col}

    B_x, B_y = params.domain_x_m(), params.domain_y_m()
    stages = params.stages or [LoadStage("GD2 - Tai thiet ke", params.q_surcharge_kPa, 0.0)]
    warnings = params.warnings

    for stage in stages:
        lines += ["*STEP, NLGEOM", "*STATIC"]
        if stage.q_avg_kPa > 0 and len(top_idx) > 0:
            B = B_x if stage.ecc_axis == "x" else B_y
            axis_col = 0 if stage.ecc_axis == "x" else 1
            lines.append("*CLOAD")
            if stage.load_footprint == "full":
                e_use, warn = validate_eccentricity(stage.eccentricity_m, B)
                if warn:
                    warnings.append(f"[{stage.name}] {warn}")
                for n in top_idx:
                    pos = all_points[n][axis_col]
                    q_i = _eccentric_pressure(pos, stage.q_avg_kPa, e_use, B)
                    F_i = q_i * node_area.get(int(n), 0.0)
                    lines.append(f"{n + 1}, 3, {-F_i:.6f}")
            else:
                sign = 1.0 if stage.load_footprint == "half_pos" else -1.0
                for n in top_idx:
                    pos = all_points[n][axis_col]
                    if sign * pos < 0:
                        continue
                    F_i = stage.q_avg_kPa * node_area.get(int(n), 0.0)
                    lines.append(f"{n + 1}, 3, {-F_i:.6f}")
        lines += ["*NODE FILE", "U", "*EL FILE", "S, E", "*END STEP"]

    out_inp.parent.mkdir(parents=True, exist_ok=True)
    out_inp.write_text("\n".join(lines) + "\n", encoding="ascii", errors="replace")
    return out_inp
