"""cdm3d.params_io — Nap tham so mo hinh 3D tu data/cdm3d_params.json.

Uu tien du lieu du an (TCVN 9403 Phu luc C, khu vuc KE/BXN/NHC) hon la bia so.
Moi gia tri KHONG co nguon du lieu (VD: nu, gamma tru CDM, module lop cung)
duoc ghi ro 'assumed' trong ModelParams.warnings — hien warning ra console.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .types import ColumnGroup, LoadStage, ModelParams, SoilLayer

_ROOT = Path(__file__).resolve().parent.parent.parent
_PARAMS_JSON = _ROOT / "data" / "cdm3d_params.json"
_DB_PATH = _ROOT / "data" / "TTHC.sqlite"

# Ky hieu lop dat yeu theo lab_tests.symbol_tcvn — dung THONG NHAT voi quy uoc
# du an (CLAUDE.md muc 36/38: "1","1b","CH","MH","CH-OH","MH-OH" cho Ip trung
# binh Bjerrum) — o day chi lay nhom set/bun theo symbol_tcvn (lab_tests khong
# co symbol so La Ma "1"/"1b" nhu bang layers, chi co symbol_tcvn).
_SOFT_SOIL_SYMBOLS_TCVN = ("CH", "MH", "CH-OH", "MH-OH")


def _query_gamma_for_zone(zone_code: str, db_path: Path = _DB_PATH) -> tuple[float | None, int]:
    """Truy van gamma_kNm3 TRUNG BINH tu lab_tests (JOIN boreholes) cho lop dat
    yeu cua 1 zone — uu tien du lieu thi nghiem THAT theo dung thu tu uu tien
    CLAUDE.md muc 6b (SQLite truoc, JSON/gia dinh chi khi khong co). Tra ve
    (gamma_avg_kNm3, n_mau) — (None, 0) neu khong co du lieu."""
    if not db_path.exists():
        return None, 0
    con = sqlite3.connect(str(db_path))
    try:
        symbols_sql = ",".join(f"'{s}'" for s in _SOFT_SOIL_SYMBOLS_TCVN)
        cur = con.execute(f"""
            SELECT AVG(lt.gamma_kNm3), COUNT(*)
            FROM lab_tests lt
            JOIN boreholes b ON lt.borehole_id = b.id
            WHERE b.name LIKE ? AND lt.symbol_tcvn IN ({symbols_sql})
              AND lt.gamma_kNm3 IS NOT NULL
        """, (f"{zone_code}-%",))
        avg_gamma, n = cur.fetchone()
        return (round(avg_gamma, 3) if avg_gamma is not None else None), (n or 0)
    finally:
        con.close()


def query_su_vst_avg(zone_code: str, z_top: float, z_bot: float,
                      db_path: Path = _DB_PATH) -> tuple[float | None, int]:
    """Truy van Su_kPa TRUNG BINH tu vane_shear_tests (cat canh hien truong) cho
    1 zone trong khoang do sau [0, z_top-z_bot] — dung THEO DUNG thu tu uu tien
    CLAUDE.md muc 6 (VST > lab > gia dinh) cho suc khang cat khong thoat nuoc.
    depth_m trong vane_shear_tests la DO SAU (duong, tinh tu mat dat), khac quy
    uoc cao do am trong SoilLayer — chuyen doi truoc khi query. Tra ve
    (Su_avg_kPa, n_mau) — (None, 0) neu khong co du lieu.

    CANH BAO: Su thuc te TANG theo do sau (da xac nhan qua du lieu KE: ~7,9kPa o
    2,2m -> ~25,8kPa o 18,2m) — gia tri TRUNG BINH nay CHI phu hop khi model dung
    1 module E/Su HANG SO cho ca lop (dung gia dinh don gian hoa hien tai cua
    cdm3d, KHONG phai mo hinh depth-varying chinh xac hon)."""
    if not db_path.exists():
        return None, 0
    depth_top, depth_bot = -z_top, -z_bot  # cao do -> do sau (duong)
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute("""
            SELECT AVG(v.Su_kPa), COUNT(*)
            FROM vane_shear_tests v
            JOIN vst_locations vl ON v.vst_loc_id = vl.id
            WHERE vl.name LIKE ? AND v.depth_m BETWEEN ? AND ?
              AND v.Su_kPa IS NOT NULL
        """, (f"{zone_code}-%", depth_top, depth_bot))
        avg_su, n = cur.fetchone()
        return (round(avg_su, 3) if avg_su is not None else None), (n or 0)
    finally:
        con.close()


def query_oedometer_avg(zone_code: str, db_path: Path = _DB_PATH) -> dict:
    """Truy van TRUNG BINH cac thong so nen co ket (oedometer) that tu lab_tests
    cho lop dat yeu 1 zone (loc theo symbol_tcvn, GIONG _query_gamma_for_zone —
    KHONG loc theo do sau vi symbol_tcvn da du xac dinh lop): Cc, Cs, e0, PC_kPa,
    a12_cm2kgf, va E_kPa (da tinh san tung mau theo cong thuc du an Eoed =
    (1+e0)/(a1-2 x 0.01) — xem CLAUDE.md muc 11c). Dung E_kPa TRUNG BINH cac mau
    THAT lam mo dun dan hoi dai dien — KHONG suy tu tuong quan Mesri (Es=250*Su)
    khi da co so lieu nen co ket that (uu tien nguon thi nghiem truc tiep).

    Tra ve dict {field: (avg, n)} — (None, 0) cho field khong co du lieu."""
    fields = ["Cc", "Cs", "e0", "PC_kPa", "a12_cm2kgf", "E_kPa"]
    out = {f: (None, 0) for f in fields}
    if not db_path.exists():
        return out
    con = sqlite3.connect(str(db_path))
    try:
        symbols_sql = ",".join(f"'{s}'" for s in _SOFT_SOIL_SYMBOLS_TCVN)
        for f in fields:
            cur = con.execute(f"""
                SELECT AVG(lt.{f}), COUNT(lt.{f})
                FROM lab_tests lt
                JOIN boreholes b ON lt.borehole_id = b.id
                WHERE b.name LIKE ? AND lt.symbol_tcvn IN ({symbols_sql})
                  AND lt.{f} IS NOT NULL
            """, (f"{zone_code}-%",))
            avg, n = cur.fetchone()
            out[f] = (round(avg, 4) if avg is not None else None, n or 0)
        return out
    finally:
        con.close()


def build_default_params(zone_code: str = "KE") -> ModelParams:
    """Doc data/cdm3d_params.json (da seed tu tvtk_cdm_202605_TTHC.json) va dung
    mot Boundary xep chong 3 lop: dat dap - dat yeu (co tru CDM) - lop cung (mui tru).
    """
    cfg = json.loads(_PARAMS_JSON.read_text(encoding="utf-8"))
    zones = {z["zone_code"]: z for z in cfg["zones"]}
    if zone_code not in zones:
        raise ValueError(f"Khong co du lieu zone '{zone_code}' trong {_PARAMS_JSON.name}")
    z = zones[zone_code]
    warnings: list[str] = []

    D_m = cfg["config"]["D_mm"] / 1000.0
    s_m = cfg["config"]["spacing_m"]
    top_elev = cfg["config"]["top_elev_m"]
    penetration = cfg["config"]["penetration_m"]
    q_kPa = z["q_kPa"]
    H_soft = z["H_cdm_m"]
    Ec_kPa = z["Ec_kPa"]
    Es_kPa = z["Es_kPa"]  # module dat yeu tu nhien (Es = 250*Cu_VST, TCVN 9403 C)

    z_ground = 0.0  # cao do mat dat tu nhien lam moc quy chieu (m)
    z_fill_top = top_elev
    z_soft_bot = z_ground - H_soft
    z_col_tip = z_soft_bot - penetration

    # --- gia tri gia dinh (KHONG co trong SQLite/JSON du an) — canh bao ky su ---
    gamma_fill = cfg["assumed_defaults"]["gamma_fill_kNm3"]
    E_fill_kPa = cfg["assumed_defaults"]["E_fill_kPa"]
    nu_soil = cfg["assumed_defaults"]["nu_soil"]
    nu_fill = cfg["assumed_defaults"]["nu_fill"]
    nu_column = cfg["assumed_defaults"]["nu_column"]
    gamma_column = cfg["assumed_defaults"]["gamma_column_kNm3"]
    firm_stiffness_ratio = cfg["assumed_defaults"]["firm_layer_stiffness_ratio"]
    firm_extra_depth = cfg["assumed_defaults"]["firm_layer_extra_depth_m"]
    warnings.append(
        f"gamma_fill={gamma_fill} kN/m3, E_fill={E_fill_kPa} kPa: GIA DINH — "
        f"khong co trong tvtk_cdm_202605_TTHC.json, kiem tra lai truoc khi dung ket qua."
    )
    warnings.append(
        f"nu (dat yeu={nu_soil}, dat dap={nu_fill}, tru CDM={nu_column}): GIA DINH — "
        f"TCVN 9403 khong cho he so Poisson, dung gia tri dia ky thuat thong thuong."
    )
    warnings.append(
        f"gamma tru CDM={gamma_column} kN/m3: GIA DINH — chua co thi nghiem gamma vua tron xi mang."
    )
    E_firm_kPa = Es_kPa * firm_stiffness_ratio
    warnings.append(
        f"Lop cung duoi mui tru: E={E_firm_kPa:.0f} kPa = {firm_stiffness_ratio}x Es dat yeu — "
        f"GIA DINH (khong co khoan sau qua mui tru trong du lieu hien co)."
    )

    z_firm_bot = z_col_tip - firm_extra_depth

    gamma_soft, n_gamma = _query_gamma_for_zone(zone_code)
    if gamma_soft is not None:
        gamma_soft_source = f"lab_tests (n={n_gamma}, symbol_tcvn IN {_SOFT_SOIL_SYMBOLS_TCVN})"
    else:
        gamma_soft = 16.0
        gamma_soft_source = "assumed"
        warnings.append(
            f"gamma dat yeu={gamma_soft} kN/m3: GIA DINH — khong tim thay mau thi "
            f"nghiem trong lab_tests cho zone '{zone_code}' (symbol_tcvn IN "
            f"{_SOFT_SOIL_SYMBOLS_TCVN})."
        )

    soil_layers = [
        SoilLayer("dat_dap", z_fill_top, z_ground, gamma_fill, E_fill_kPa, nu_fill, source="assumed"),
        SoilLayer("dat_yeu", z_ground, z_soft_bot, gamma_soft, Es_kPa, nu_soil, source=gamma_soft_source),
        SoilLayer("lop_cung", z_soft_bot, z_firm_bot, 19.0, E_firm_kPa, nu_soil, source="assumed"),
    ]

    column = ColumnGroup(
        D_m=D_m, spacing_m=s_m, n_x=cfg["config"]["n_columns_x"], n_y=cfg["config"]["n_columns_y"],
        z_top=z_fill_top, z_bot=z_col_tip, Ec_kPa=Ec_kPa, nu_c=nu_column,
        gamma_kNm3=gamma_column, source="tvtk_cdm_json",
    )

    stages = _build_stages(cfg, q_kPa, warnings)

    # Muc nuoc ngam mac dinh = cao do dinh coc (z_fill_top) — theo yeu cau nguoi
    # dung (2026-08-27): toan bo dat yeu + lop cung nam DUOI MNN nay -> dung gamma
    # hieu dung (gamma') cho sigma'v (vd trong contact_ccx_input.alpha_equivalent_mu).
    # KHONG anh huong *DENSITY (van dung gamma_kNm3 tong, self-weight dang TAT).
    water_table_elev = z_fill_top
    warnings.append(
        f"Muc nuoc ngam = {water_table_elev}m (= cao do dinh coc, GIA DINH theo "
        f"yeu cau) — toan bo dat yeu+lop cung duoc coi la duoi MNN, dung gamma "
        f"hieu dung (gamma_sat - 9.81) cho tinh sigma'v. Kiem tra lai neu MNN "
        f"thuc te khac."
    )

    params = ModelParams(
        zone_code=zone_code, soil_layers=soil_layers, column=column,
        q_surcharge_kPa=q_kPa, stages=stages,
        domain_buffer_m=cfg["mesh"]["domain_buffer_m"],
        mesh_size_far_m=cfg["mesh"]["mesh_size_far_m"],
        mesh_size_near_column_m=cfg["mesh"]["mesh_size_near_column_m"],
        column_box_field_margin_m=cfg["mesh"]["column_box_field_margin_m"],
        water_table_elev=water_table_elev,
        warnings=warnings,
    )
    return params


def _build_stages(cfg: dict, q_final_kPa: float, warnings: list[str]) -> list[LoadStage]:
    """Doc data/cdm3d_params.json -> staged_construction (GD2..GDN — dap tang dan +
    lech tam tang dan). Neu JSON CHUA co khoa nay -> fallback 1 giai doan don, tai
    day du q_final_kPa, khong lech tam (giu tuong thich nguoc voi kich ban doi xung
    cu — ccx_input.write_ccx_inp() van luon ghi chuoi GD0(remove)->GD1(add)->GD2..N
    du chi co 1 giai doan tai)."""
    sc = cfg.get("staged_construction")
    if not sc or not sc.get("stages"):
        return [LoadStage(name="GD2 - Tai thiet ke", q_avg_kPa=q_final_kPa, eccentricity_m=0.0)]

    ecc_axis = sc.get("ecc_axis", "x")
    warnings.append(
        "Cac gia tri eccentricity_m trong staged_construction la GIA DINH minh hoa "
        "(chua co so lieu khao sat mai doc/tai lech tam thuc te) — PHAI ky su xac "
        "nhan truoc khi dung ket qua chuyen vi ngang/mo men."
    )
    return [
        LoadStage(
            name=s["name"],
            q_avg_kPa=s["q_fraction"] * q_final_kPa,
            eccentricity_m=s.get("eccentricity_m", 0.0),
            ecc_axis=ecc_axis,
            load_footprint=s.get("load_footprint", "full"),
        )
        for s in sc["stages"]
    ]


def print_warnings(params: ModelParams) -> None:
    if not params.warnings:
        return
    print(f"[cdm3d] {len(params.warnings)} canh bao gia tri gia dinh cho zone '{params.zone_code}':")
    for w in params.warnings:
        print(f"  - {w}")
