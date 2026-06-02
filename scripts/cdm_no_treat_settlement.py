# -*- coding: utf-8 -*-
"""Phương án: Lún nền CHƯA xử lý — tải gây lún = γ_đắp · (cao độ thiết kế − cao độ tự nhiên).

Cho từng hố khoan vùng CDM:
    H_đắp = max(0, CĐTK − CĐTN)         (m)
    q     = γ_đắp · H_đắp                (kN/m²)
    S     = tổng lún cố kết nền tự nhiên dưới tải q (chưa xử lý, stress_scale=1.0)

Tái dùng settlement_calc.calc_settlement_from_db (Terzaghi 1D, OC/NC/cross-PC + nhánh cát).
Lưu SQLite cdm_no_treat_design_settlement (LOCAL + PROJECT) — §64 rule 8.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
_DBS = [
    Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite"),
    _ROOT / "data" / "TTHC.sqlite",
]
_DEFAULT_DB = _ROOT / "data" / "TTHC.sqlite"

# Tiền tố hố khoan theo vùng
ZONE_PREFIX = {
    "KE (Bờ kè)": "KE-%",
    "BXN": "BXN-%",
    "NHC": "NHC-%",
    "QTT (ND)": "ND-%",
}

# Nhãn vùng đặc biệt: chỉ các hố khoan TRÊN TUYẾN CỪ (on_sw_alignment=1)
LEVEE_KEY = "KE — Bờ kè (tuyến cừ)"

# Override ký hiệu lớp: lớp xi măng đất nhân tạo (CXM/XMD) coi như nền tự nhiên bùn 1.
# (KE-HK8 6.7–22.4m là vị trí cọc thử CDM — thay bằng lớp bùn số 1.)
SYMBOL_OVERRIDE = {("KE-HK8", "XMD"): "1"}

# Hố khoan KHÔNG đưa vào tính toán bờ kè (vị trí đặc biệt — cọc thử CDM).
LEVEE_EXCLUDE = {"KE-HK8"}

# Cấu hình 6 vùng — hố khoan đại diện + cao độ tự nhiên + chiều dày đắp.
# NGUỒN: BCL (Ban chiến lược) — cao độ tự nhiên (m.ND) + chiều dày đắp cho sẵn.
# 2 giá trị chiều dày đắp: PA1 (phần xe chạy) và PA2 (phần vỉa hè).
ZONE_FILL_SOURCE = "BCL (Ban chiến lược)"
ZONE_FILL_CONFIG = [
    {"zone": "ZONE 1",     "bh": "KE-HK11", "CDTN": 1.80,  "H_fill_1": 1.10, "H_fill_2": 1.20},
    {"zone": "ZONE 2, 3",  "bh": "KE-HK9",  "CDTN": -2.20, "H_fill_1": 5.20, "H_fill_2": 5.20},
    {"zone": "ZONE 3",     "bh": "KE-HK10", "CDTN": -0.40, "H_fill_1": 3.30, "H_fill_2": 3.30},
    {"zone": "ZONE 4",     "bh": "KE-HK7",  "CDTN": -0.56, "H_fill_1": 3.50, "H_fill_2": 3.50},
    {"zone": "ZONE 5",     "bh": "KE-HK5",  "CDTN": 0.88,  "H_fill_1": 2.00, "H_fill_2": 2.10},
    {"zone": "ZONE 6",     "bh": "KE-HK2",  "CDTN": 1.20,  "H_fill_1": 1.70, "H_fill_2": 1.70},
]


def compute_zone_fill_settlement(
    which_fill: int = 1,
    gamma_fill: float = 18.0,
    gwt_elev_m: float = 0.0,
    B_load_m: Optional[float] = None,
    t_years: float = 15.0,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """Lún nền chưa xử lý cho 6 hố khoan đại diện (ZONE_FILL_CONFIG), dùng CHIỀU DÀY ĐẮP
    cho sẵn (q = γ·H_đắp), không suy từ cao độ thiết kế. which_fill = 1 (xe chạy) | 2 (vỉa hè).
    Tính trong vùng ảnh hưởng (§71) qua calc_s2_below_cdm(tip=0).
    """
    import settlement_calc as sc

    out = []
    fkey = "H_fill_2" if which_fill == 2 else "H_fill_1"
    for c in ZONE_FILL_CONFIG:
        H_fill = float(c[fkey])
        cdtn = float(c["CDTN"])
        q = gamma_fill * H_fill
        gwt_depth = max(0.0, cdtn - gwt_elev_m)
        warn = ""
        S_cm = S_15 = d_inf = 0.0
        n_sub = 0
        try:
            r = sc.calc_s2_below_cdm(
                c["bh"], cdm_tip_depth_m=0.0, q_kPa=q, gwt_depth_m=gwt_depth,
                stop_ratio=0.1, B_load_m=B_load_m, t_years_residual=t_years, db_path=db_path)
            S_cm = float(r.get("S2_cm") or 0.0)
            S_15 = float(r.get("S2_15yr_cm") or 0.0)
            d_inf = float(r.get("stop_depth_m") or 0.0)
            n_sub = int(r.get("n_layers") or 0)
            w = r.get("warnings") or r.get("warning")
            if w:
                warn = w if isinstance(w, str) else "; ".join(w)
        except Exception as e:  # noqa: BLE001
            warn = f"Lỗi tính: {e}"
        out.append({
            "zone": c["zone"], "bh": c["bh"], "CDTN_m": cdtn, "H_fill_m": round(H_fill, 2),
            "q_kPa": round(q, 1), "S_total_cm": round(S_cm, 1), "S_15yr_cm": round(S_15, 1),
            "d_influence_m": round(d_inf, 1), "n_sublayers": n_sub, "gwt_depth_m": round(gwt_depth, 2),
            "warning": warn,
        })
    return out


def levee_boreholes(db_path: Optional[Path] = None) -> list[str]:
    """Hố khoan trên tuyến cừ bờ kè (ke_sw_design.on_sw_alignment=1), trừ LEVEE_EXCLUDE."""
    db = Path(db_path) if db_path else _DEFAULT_DB
    con = sqlite3.connect(str(db))
    try:
        rows = con.execute(
            "SELECT bh_name FROM ke_sw_design WHERE on_sw_alignment=1"
        ).fetchall()
    finally:
        con.close()
    return sorted([r[0] for r in rows if r[0] not in LEVEE_EXCLUDE],
                  key=lambda n: int("".join(c for c in n if c.isdigit()) or 0))


def resolve_boreholes(zone_key: str, db_path: Optional[Path] = None) -> list[str]:
    """Danh sách hố khoan theo lựa chọn vùng (gồm trường hợp đặc biệt tuyến cừ)."""
    if zone_key == LEVEE_KEY:
        return levee_boreholes(db_path)
    return list_zone_boreholes(ZONE_PREFIX[zone_key], db_path)


@dataclass
class NoTreatRow:
    bh_name: str
    CDTN_m: float          # cao độ tự nhiên
    CDTK_m: float          # cao độ thiết kế
    H_fill_m: float        # bề dày đắp = CĐTK − CĐTN
    q_kPa: float           # tải gây lún
    S_total_cm: float      # tổng lún cố kết trong vùng ảnh hưởng (S∞)
    S_15yr_cm: float = 0.0  # lún đạt được sau 15 năm
    d_influence_m: float = 0.0   # đáy vùng ảnh hưởng (Δσ/σ'v0 < 10%)
    n_sublayers: int = 0
    gwt_depth_m: float = 0.0
    warning: str = ""


def list_zone_boreholes(prefix: str, db_path: Optional[Path] = None) -> list[str]:
    db = Path(db_path) if db_path else _DEFAULT_DB
    con = sqlite3.connect(str(db))
    try:
        rows = con.execute(
            "SELECT name FROM boreholes WHERE name LIKE ? ORDER BY name", (prefix,)
        ).fetchall()
    finally:
        con.close()
    # sắp theo số thứ tự nếu có
    def _key(n):
        digits = "".join(c for c in n if c.isdigit())
        return int(digits) if digits else 0
    return sorted([r[0] for r in rows], key=_key)


def compute_no_treat(
    bh_names: list[str],
    design_elev_m: float,
    gamma_fill: float = 18.0,
    gwt_elev_m: float = 0.0,
    B_load_m: Optional[float] = None,
    t_years: float = 15.0,
    db_path: Optional[Path] = None,
) -> list[NoTreatRow]:
    """Tính lún nền chưa xử lý với tải = γ·(CĐTK − CĐTN).

    Dùng engine §71 (calc_s2_below_cdm, tip=0 = tính từ mặt đất tự nhiên):
    chia phân tố 2m, tích phân tới ĐÁY VÙNG ẢNH HƯỞNG (Δσ/σ'v0 < 10%), mở rộng
    dưới hố khoan nếu cần, phân nhánh sét (Terzaghi OC/NC/cross) + cát (Es từ SPT).
    B_load_m=None → Δσ = q không đổi (1D, bảo thủ); >0 → phân tán Boussinesq dải.
    """
    import settlement_calc as sc

    db = Path(db_path) if db_path else _DEFAULT_DB
    con = sqlite3.connect(str(db))
    elev = dict(con.execute("SELECT name, elevation_m FROM boreholes").fetchall())
    con.close()

    out: list[NoTreatRow] = []
    for bh in bh_names:
        cdtn = elev.get(bh)
        if cdtn is None:
            out.append(NoTreatRow(bh, 0.0, design_elev_m, 0.0, 0.0, 0.0,
                                  warning="Không có cao độ tự nhiên"))
            continue
        H_fill = max(0.0, design_elev_m - cdtn)
        q = gamma_fill * H_fill
        gwt_depth = max(0.0, cdtn - gwt_elev_m)   # độ sâu MNN từ mặt đất tự nhiên
        warn = ""
        S_cm = S_15 = d_inf = 0.0
        n_sub = 0
        if H_fill <= 0:
            warn = "CĐTK ≤ CĐTN → không có tải đắp"
        else:
            try:
                r = sc.calc_s2_below_cdm(
                    bh, cdm_tip_depth_m=0.0, q_kPa=q, gwt_depth_m=gwt_depth,
                    stop_ratio=0.1, B_load_m=B_load_m, t_years_residual=t_years,
                    db_path=db)
                S_cm = float(r.get("S2_cm") or 0.0)
                S_15 = float(r.get("S2_15yr_cm") or 0.0)
                d_inf = float(r.get("stop_depth_m") or 0.0)
                n_sub = int(r.get("n_layers") or 0)
                w = r.get("warnings") or r.get("warning")
                if w:
                    warn = w if isinstance(w, str) else "; ".join(w)
            except Exception as e:  # noqa: BLE001
                warn = f"Lỗi tính: {e}"
        out.append(NoTreatRow(
            bh_name=bh, CDTN_m=round(cdtn, 3), CDTK_m=design_elev_m,
            H_fill_m=round(H_fill, 3), q_kPa=round(q, 2), S_total_cm=round(S_cm, 2),
            S_15yr_cm=round(S_15, 2), d_influence_m=round(d_inf, 1), n_sublayers=n_sub,
            gwt_depth_m=round(gwt_depth, 2), warning=warn))
    return out


def compute_no_treat_6zones(
    design_elev_m: float,
    gamma_fill: float = 18.0,
    gwt_elev_m: float = 0.0,
    B_load_m: Optional[float] = None,
    t_years: float = 15.0,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """Lún nền chưa xử lý gom theo 6 vùng CDM (bảng ke_cdm_zones — Bờ kè KE).

    Trả về list[{zone_no, zone_name, total_length_m, boreholes:[NoTreatRow],
                 S_max_cm, S_avg_cm, controlling_bh}] — Lún đại diện vùng = max các HK.
    """
    import json as _json

    db = Path(db_path) if db_path else _DEFAULT_DB
    con = sqlite3.connect(str(db))
    try:
        zrows = con.execute(
            "SELECT zone_no, zone_name, bh_list, total_length_m FROM ke_cdm_zones ORDER BY zone_no"
        ).fetchall()
    finally:
        con.close()

    # tính 1 lần cho toàn bộ HK xuất hiện trong 6 vùng
    all_bh: list[str] = []
    for _, _, bl, _ in zrows:
        all_bh += _json.loads(bl)
    all_bh = sorted(set(all_bh), key=lambda n: int("".join(c for c in n if c.isdigit()) or 0))
    res = {r.bh_name: r for r in compute_no_treat(
        all_bh, design_elev_m, gamma_fill, gwt_elev_m, B_load_m, t_years, db_path)}

    out = []
    for zno, zname, bl, tot in zrows:
        bhs = _json.loads(bl)
        rows = [res[b] for b in bhs if b in res]
        valid = [r for r in rows if r.S_total_cm > 0]
        smax = max((r.S_total_cm for r in valid), default=0.0)
        savg = (sum(r.S_total_cm for r in valid) / len(valid)) if valid else 0.0
        ctrl = next((r.bh_name for r in valid if r.S_total_cm == smax), "—")
        out.append({
            "zone_no": zno, "zone_name": zname, "total_length_m": tot,
            "boreholes": rows, "S_max_cm": round(smax, 1),
            "S_avg_cm": round(savg, 1), "controlling_bh": ctrl,
        })
    return out


def compute_qtt_no_treat(
    design_elev_m: float,
    gamma_fill: float = 18.0,
    gwt_elev_m: float = 0.0,
    B_load_m: Optional[float] = None,
    t_years: float = 15.0,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """Lún nền chưa xử lý cho hố khoan QTT (ND-*) — dùng SỐ LIỆU TỪNG HỐ;
    hố nào thiếu thí nghiệm nén (Cc) thì THAM KHẢO hố khoan GẦN NHẤT có Cc (§15).

    Tải gây lún q = γ·(CĐTK − CĐTN từng hố). Lún trong vùng ảnh hưởng (§71).
    """
    import math
    import settlement_calc as sc

    db = Path(db_path) if db_path else _DEFAULT_DB
    con = sqlite3.connect(str(db))
    try:
        bhs = con.execute(
            "SELECT b.name, b.elevation_m, b.x_coord_m, b.y_coord_m, "
            "(SELECT COUNT(*) FROM lab_tests l WHERE l.borehole_id=b.id "
            " AND l.Cc IS NOT NULL AND l.Cc>0) AS nCc "
            "FROM boreholes b WHERE b.name LIKE 'ND-%' ORDER BY b.name").fetchall()
    finally:
        con.close()

    have_cc = [b for b in bhs if (b[4] or 0) > 0]

    def _nearest(bx, by):
        best, bd = None, 1e18
        for nm, _e, x, y, _n in have_cc:
            if x is None or y is None:
                continue
            d = math.hypot((bx or 0) - x, (by or 0) - y)
            if d < bd:
                bd, best = d, nm
        return best, bd

    out = []
    for name, elev, x, y, nCc in bhs:
        cdtn = elev if elev is not None else 0.0
        H = max(0.0, design_elev_m - cdtn)
        q = gamma_fill * H
        gwt = max(0.0, cdtn - gwt_elev_m)
        if (nCc or 0) > 0:
            src, dist, borrowed = name, 0.0, ""
        else:
            src, dist = _nearest(x, y)
            borrowed = f"mượn {src} (d={dist:.0f}m)" if src else "không có hố tham khảo"
        S_cm = d_inf = 0.0
        n_sub = 0
        warn = ""
        if H <= 0:
            warn = "CĐTK ≤ CĐTN"
        elif src is None:
            warn = "Không có hố khoan nào có Cc để tham khảo"
        else:
            try:
                r = sc.calc_s2_below_cdm(src, cdm_tip_depth_m=0.0, q_kPa=q, gwt_depth_m=gwt,
                                        stop_ratio=0.1, B_load_m=B_load_m,
                                        t_years_residual=t_years, db_path=db)
                S_cm = float(r.get("S2_cm") or 0.0)
                d_inf = float(r.get("stop_depth_m") or 0.0)
                n_sub = int(r.get("n_layers") or 0)
            except Exception as e:  # noqa: BLE001
                warn = f"Lỗi tính: {e}"
        out.append({
            "bh": name, "CDTN_m": round(cdtn, 3), "H_fill_m": round(H, 2), "q_kPa": round(q, 1),
            "has_cc": (nCc or 0) > 0, "source_bh": src, "borrow_note": borrowed,
            "dist_m": round(dist, 1), "d_influence_m": round(d_inf, 1), "n_sublayers": n_sub,
            "S_total_cm": round(S_cm, 1), "warning": warn,
        })
    return out


def create_table(con: sqlite3.Connection) -> None:
    con.execute(
        """CREATE TABLE IF NOT EXISTS cdm_no_treat_design_settlement (
            zone TEXT, bh_name TEXT, CDTN_m REAL, CDTK_m REAL, H_fill_m REAL,
            gamma_fill REAL, q_kPa REAL, gwt_depth_m REAL, S_total_cm REAL,
            S_15yr_cm REAL, d_influence_m REAL, n_sublayers INTEGER,
            warning TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (zone, bh_name))"""
    )
    # migrate cột mới nếu bảng cũ đã tồn tại
    for col, typ in [("S_15yr_cm", "REAL"), ("d_influence_m", "REAL"), ("n_sublayers", "INTEGER")]:
        try:
            con.execute(f"ALTER TABLE cdm_no_treat_design_settlement ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass
    con.commit()


def save_results(zone: str, rows: list[NoTreatRow], gamma_fill: float) -> None:
    for db in _DBS:
        if not db.parent.exists():
            continue
        con = sqlite3.connect(str(db))
        try:
            create_table(con)
            for r in rows:
                con.execute(
                    "INSERT OR REPLACE INTO cdm_no_treat_design_settlement "
                    "(zone,bh_name,CDTN_m,CDTK_m,H_fill_m,gamma_fill,q_kPa,gwt_depth_m,"
                    "S_total_cm,S_15yr_cm,d_influence_m,n_sublayers,warning,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                    (zone, r.bh_name, r.CDTN_m, r.CDTK_m, r.H_fill_m, gamma_fill,
                     r.q_kPa, r.gwt_depth_m, r.S_total_cm, r.S_15yr_cm, r.d_influence_m,
                     r.n_sublayers, r.warning),
                )
            con.commit()
        finally:
            con.close()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    bhs = list_zone_boreholes("KE-%")
    res = compute_no_treat(bhs, design_elev_m=2.7, gamma_fill=18.0, gwt_elev_m=0.0)
    print(f"{'HK':<9}{'CDTN':>7}{'H_dap':>7}{'q':>8}{'S_inf':>9}{'S_15y':>9}{'d_anhh':>8}{'nlop':>5}")
    for r in res:
        print(f"{r.bh_name:<9}{r.CDTN_m:>7.2f}{r.H_fill_m:>7.2f}{r.q_kPa:>8.1f}"
              f"{r.S_total_cm:>9.1f}{r.S_15yr_cm:>9.1f}{r.d_influence_m:>8.1f}{r.n_sublayers:>5}  {r.warning}")
    save_results("KE (Bờ kè)", res, 18.0)
    print("Da luu SQLite (co cot vung anh huong).")
