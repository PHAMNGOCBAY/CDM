# -*- coding: utf-8 -*-
"""Thống kê chỉ tiêu cơ lý các lớp đất — tất cả hố khoan, tất cả lớp đất.

Gom mẫu thí nghiệm phòng (lab_tests) theo (vùng + ký hiệu lớp địa tầng), bằng cách
ánh xạ mẫu vào lớp theo độ sâu trung điểm so với bảng `layers`. Tính trung bình (và
n mẫu) cho từng chỉ tiêu: dung trọng, lực dính, góc ma sát, Atterberg, và NÉN CỐ KẾT
(e0, Cc, Cs, PC, Cv, a1-2, qu, Cu).

API:
    stats_by_layer(zone_prefix=None)  -> list[dict] (mỗi lớp 1 dòng)
    save_stats(rows)                  -> lưu SQLite soil_param_layer_stats (LOCAL+PROJECT)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB = _ROOT / "data" / "TTHC.sqlite"
_DBS = [Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite"), _DEFAULT_DB]

ZONES = [("KE", "KE-%"), ("BXN", "BXN-%"), ("NHC", "NHC-%"), ("QTT", "ND-%")]

# (cột lab_tests, nhãn hiển thị, số chữ số)
FIELDS = [
    ("w_pct", "W (%)", 1),
    ("gamma_kNm3", "γ (kN/m³)", 2),
    ("gamma_dry_kNm3", "γ_k (kN/m³)", 2),
    ("e0", "e₀", 3),
    ("Sr_pct", "Sr (%)", 1),
    ("wL_pct", "W_L (%)", 1),
    ("wP_pct", "W_P (%)", 1),
    ("Ip", "I_p", 1),
    ("c_kPa", "c (kPa)", 1),
    ("phi_deg", "φ (°)", 1),
    ("Cu_UU_kPa", "Cu_UU (kPa)", 1),
    ("Cc", "Cc", 3),
    ("Cs", "Cs", 4),
    ("PC_kPa", "P_c (kPa)", 1),
    ("E_kPa", "E (kPa)", 0),
    ("Cv_cm2s", "Cv (cm²/s)", 6),
    ("a12_cm2kgf", "a₁₋₂ (cm²/kgf)", 4),
    ("qu_kPa", "qu (kPa)", 1),
]


def _zone_of(bh: str) -> str:
    for z, pfx in ZONES:
        if bh.startswith(pfx[:-1]):
            return z
    return "?"


# Override ký hiệu lớp: lớp xi măng đất nhân tạo (CXM/XMD) coi như nền tự nhiên bùn 1.
# (KE-HK8 6.7–22.4m là vị trí cọc thử CDM — số liệu thí nghiệm lấy theo lớp bùn 1 lân cận.)
SYMBOL_OVERRIDE = {("KE-HK8", "XMD"): "1"}


def stats_by_layer(zone_prefix: Optional[str] = None,
                   bh_names: Optional[list] = None,
                   db_path: Optional[Path] = None) -> list[dict]:
    """Thống kê theo (vùng, lớp). zone_prefix None = tất cả; bh_names = giới hạn danh sách HK.

    Áp dụng SYMBOL_OVERRIDE: lớp xi măng đất (XMD) của HK8 được tính như lớp bùn 1.
    """
    db = Path(db_path) if db_path else _DEFAULT_DB
    con = sqlite3.connect(str(db))
    cur = con.cursor()

    if bh_names:
        ph = ",".join("?" * len(bh_names))
        where_lay = f"WHERE b.name IN ({ph}) AND l.symbol IS NOT NULL"
        where_lab = f"WHERE b.name IN ({ph})"
        args = tuple(bh_names)
    elif zone_prefix:
        where_lay = "WHERE b.name LIKE ? AND l.symbol IS NOT NULL"
        where_lab = "WHERE b.name LIKE ?"
        args = (zone_prefix,)
    else:
        where_lay = "WHERE l.symbol IS NOT NULL"
        where_lab = ""
        args = ()

    layers = cur.execute(
        f"SELECT b.name, l.symbol, l.depth_top_m, l.depth_bot_m "
        f"FROM layers l JOIN boreholes b ON l.borehole_id=b.id {where_lay}", args,
    ).fetchall()

    cols = ",".join(f"l.{f}" for f, _, _ in FIELDS)
    lab_rows = cur.execute(
        f"SELECT b.name, (l.depth_from_m+COALESCE(l.depth_to_m,l.depth_from_m+1.0))/2.0, {cols} "
        f"FROM lab_tests l JOIN boreholes b ON l.borehole_id=b.id {where_lab}", args,
    ).fetchall()
    con.close()

    # index layers per bh (sorted) — áp override ký hiệu
    from collections import defaultdict
    bh_layers = defaultdict(list)
    for name, sym, dt, db_ in layers:
        sym = SYMBOL_OVERRIDE.get((name, sym), sym)
        bh_layers[name].append((dt, db_, sym))
    for k in bh_layers:
        bh_layers[k].sort()

    def _sym_at(bh, depth):
        for dt, db_, sym in bh_layers.get(bh, []):
            if dt is not None and db_ is not None and dt <= depth <= db_:
                return sym
        return None

    # accumulate: (zone, sym) -> {field: [values]}, bh set
    acc = defaultdict(lambda: defaultdict(list))
    bhset = defaultdict(set)
    for row in lab_rows:
        bh = row[0]; depth = row[1]
        sym = _sym_at(bh, depth)
        if sym is None:
            continue
        key = (_zone_of(bh), sym)
        bhset[key].add(bh)
        for i, (f, _, _) in enumerate(FIELDS):
            v = row[2 + i]
            if v is None or v == 0:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if fv != 0:
                acc[key][f].append(fv)

    out = []
    for (zone, sym), fields in sorted(acc.items(), key=lambda x: (x[0][0], _sym_key(x[0][1]))):
        rec = {"zone": zone, "symbol": sym, "n_bh": len(bhset[(zone, sym)])}
        nmax = 0
        for f, _, nd in FIELDS:
            vals = fields.get(f, [])
            rec[f] = round(sum(vals) / len(vals), nd) if vals else None
            rec[f + "_n"] = len(vals)
            nmax = max(nmax, len(vals))
        rec["n_samples"] = nmax
        out.append(rec)
    return out


def _sym_key(s: str):
    digits = "".join(c for c in s if c.isdigit())
    return (int(digits) if digits else 99, s)


def create_table(con: sqlite3.Connection) -> None:
    col_defs = ", ".join(f"{f} REAL" for f, _, _ in FIELDS)
    con.execute(
        f"CREATE TABLE IF NOT EXISTS soil_param_layer_stats ("
        f"zone TEXT, symbol TEXT, n_bh INTEGER, n_samples INTEGER, {col_defs}, "
        f"updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (zone, symbol))"
    )
    # migrate: thêm cột chỉ tiêu mới nếu bảng cũ chưa có
    for f, _, _ in FIELDS:
        try:
            con.execute(f"ALTER TABLE soil_param_layer_stats ADD COLUMN {f} REAL")
        except sqlite3.OperationalError:
            pass
    con.commit()


def save_stats(rows: list[dict]) -> None:
    fcols = [f for f, _, _ in FIELDS]
    for db in _DBS:
        if not db.parent.exists():
            continue
        con = sqlite3.connect(str(db))
        try:
            create_table(con)
            for r in rows:
                vals = [r["zone"], r["symbol"], r["n_bh"], r["n_samples"]] + [r.get(f) for f in fcols]
                ph = ",".join("?" * (4 + len(fcols)))
                con.execute(
                    f"INSERT OR REPLACE INTO soil_param_layer_stats "
                    f"(zone,symbol,n_bh,n_samples,{','.join(fcols)},updated_at) "
                    f"VALUES ({ph},CURRENT_TIMESTAMP)", vals)
            con.commit()
        finally:
            con.close()


def representative_params(db_path: Optional[Path] = None) -> dict:
    """Trả về dict {(zone, symbol): {field: avg}} — chỉ tiêu cơ lý TRUNG BÌNH theo lớp.

    Dùng làm bộ thông số THỐNG NHẤT cho mọi tính toán của các hố khoan trong vùng.
    """
    rows = stats_by_layer(None, None, db_path)
    out = {}
    for r in rows:
        out[(r["zone"], r["symbol"])] = {f: r.get(f) for f, _, _ in FIELDS}
    return out


def export_json(json_path: Optional[Path] = None, db_path: Optional[Path] = None) -> Path:
    """Xuất bộ chỉ tiêu trung bình theo lớp ra JSON (single source cho tính toán)."""
    import json
    rows = stats_by_layer(None, None, db_path)
    path = Path(json_path) if json_path else (_ROOT / "data" / "soil_param_layer_stats.json")
    data = {
        "_meta": {
            "desc": "Chỉ tiêu cơ lý TRUNG BÌNH theo lớp (vùng × ký hiệu) — dùng thống nhất "
                    "cho tính toán các hố khoan",
            "override": "KE-HK8 lớp XMD tính như lớp bùn 1",
            "fields": {f: lb for f, lb, _ in FIELDS},
        },
        "layers": rows,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _f(v, w=7):
    return f"{v:>{w}.2f}" if v is not None else f"{'-':>{w}}"


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    rows = stats_by_layer("KE-%")
    print(f"{'Lop':<6}{'nHK':>4}{'nmau':>5}{'gama':>7}{'c':>7}{'e0':>7}{'Cc':>7}{'PC':>7}")
    for r in rows:
        print(f"{r['symbol']:<6}{r['n_bh']:>4}{r['n_samples']:>5}"
              f"{_f(r['gamma_kNm3'])}{_f(r['c_kPa'])}{_f(r['e0'])}{_f(r['Cc'])}{_f(r['PC_kPa'])}")
    save_stats(stats_by_layer())  # tất cả vùng
    print("Da luu SQLite soil_param_layer_stats (tat ca vung).")
