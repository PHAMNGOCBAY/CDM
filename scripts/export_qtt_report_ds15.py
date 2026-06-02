"""§72 Task DD — Xuất báo cáo tính toán QTT cho ΔS=15 cm.

Sinh 2 file:
- DXF: `plaxis_out/QTT_ZoningMap_dS15.dxf` (phân vùng quantile + grid 162 điểm)
- DOCX: `plaxis_out/QTT_BaoCao_dS15cm.docx` (báo cáo Word đầy đủ chương)

Đọc dữ liệu từ SQLite (cdm_zone_design_results, cdm_qtt_grid_lc,
cdm_zone_smoothness_results, qtt_elevation_points).
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from qtt_export_dxf import export_qtt_zoning_dxf  # type: ignore
from qtt_cdm_report import build_qtt_decision_docx  # type: ignore


_DB_LOCAL = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
_DB_PROJ = Path(__file__).resolve().parents[1] / "data" / "TTHC.sqlite"
_OUT_DIR = Path(__file__).resolve().parents[1] / "plaxis_out"


def _db_path() -> Path:
    return _DB_LOCAL if _DB_LOCAL.exists() else _DB_PROJ


def export_report(delta_S_cm: int = 15) -> dict:
    """Sinh DXF + Word cho ΔS chỉ định. Trả về dict các path đã tạo."""
    db = _db_path()
    _OUT_DIR.mkdir(exist_ok=True)
    paths: dict = {}

    # ─── 1. DXF — phân vùng quantile + boundary + boreholes ───
    dxf_out = _OUT_DIR / f"QTT_ZoningMap_dS{delta_S_cm:02d}.dxf"
    print(f"[1/2] Đang xuất DXF: {dxf_out.name}...")
    res_dxf = export_qtt_zoning_dxf(
        out_path=dxf_out,
        delta_S_cm=delta_S_cm,
        n_zones=4,
        cell_size_m=None,
        show_grid_points=False,
        show_lc_values=True,
        db_path=db,
    )
    paths["dxf"] = dxf_out
    print(f"    OK — {res_dxf.get('n_points', 0)} grid points + "
          f"{res_dxf.get('n_boreholes', 0)} HK + 4 vùng")

    # ─── 2. DOCX — báo cáo đầy đủ ───
    docx_out = _OUT_DIR / f"QTT_BaoCao_dS{delta_S_cm:02d}cm.docx"
    print(f"[2/2] Đang xuất Word: {docx_out.name}...")

    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        lc_rows_raw = [dict(r) for r in con.execute(
            "SELECT * FROM cdm_zone_design_results "
            "WHERE zone_code='QTT' ORDER BY bh_name, delta_S_cm"
        ).fetchall()]
        # Reshape: list of rows → list of HK with by_dS dict (theo format builder)
        lc_matrix: list[dict] = []
        seen_bh: dict[str, dict] = {}
        for r in lc_rows_raw:
            bh = r["bh_name"]
            if bh not in seen_bh:
                seen_bh[bh] = {"name": bh,
                                "H_soft_m": r["H_soft_m"],
                                "cdm_top_elev": r["cdm_top_elev_m"],
                                "borrowed": bool(r.get("borrowed")),
                                "cc_source": r.get("cc_source"),
                                "by_dS": {}}
                lc_matrix.append(seen_bh[bh])
            seen_bh[bh]["by_dS"][float(r["delta_S_cm"])] = {
                "Lc_m": r["Lc_m"], "tip_depth_m": r["tip_depth_m"],
                "p_optimal_m": r["p_optimal_m"],
                "S1_cm": r["S1_cm"], "S2_cm": r["S2_cm"],
                "S_total_cm": r["S_total_cm"], "ok": bool(r["ok"]),
                "penetrates_full": bool(r["penetrates_full"]),
            }
        # Smoothness: rename hk_i→i, hk_j→j cho khớp format builder
        smooth_pairs = []
        for r in con.execute(
            "SELECT * FROM cdm_zone_smoothness_results "
            "WHERE zone_code='QTT' ORDER BY delta_S_cm, hk_i, hk_j"
        ).fetchall():
            d = dict(r)
            d["i"] = d.pop("hk_i", None)
            d["j"] = d.pop("hk_j", None)
            # Rename DB cols → builder format
            d["dS_m"] = d.pop("dS_pair_m", 0.0) or 0.0
            d["i_inv_max"] = 125  # mặc định ngưỡng kiểm tra
            d["ok"] = bool(d.get("i_inv_actual") and d["i_inv_actual"] >= 125)
            smooth_pairs.append(d)
        grid_points = [dict(r) for r in con.execute(
            "SELECT easting_m AS E, northing_m AS N, "
            "elev_des_m, elev_nat_m FROM qtt_elevation_points"
        ).fetchall()]
        bh_rows = [dict(r) for r in con.execute(
            "SELECT name, x_coord_m AS N, y_coord_m AS E, elevation_m "
            "FROM boreholes WHERE name LIKE 'ND-%' ORDER BY name"
        ).fetchall()]
        cfg = con.execute(
            "SELECT D_mm, spacing_m, pattern, Ec_factor, qu_kPa, q_kPa, "
            "       settlement_design_elev_m FROM tvtk_cdm_config WHERE id=1"
        ).fetchone()
        fill_h = con.execute(
            "SELECT SUM(h_m) FROM tvtk_fill_composition"
        ).fetchone()[0] or 1.9

    a_ratio = 3.14159 * (cfg["D_mm"] / 1000 / 2) ** 2 / cfg["spacing_m"] ** 2
    Ec_kPa = cfg["Ec_factor"] * cfg["qu_kPa"] / 2.0

    meta = {
        "zone": "QTT",
        "project": "Quảng Trường Trung Tâm TP.HCM (mã 202605-TTHC)",
        "location": "Phường An Khánh, TP. Thủ Đức",
        "co_name": "",
        "co_staff": "",
        "delta_S_values_cm": [float(delta_S_cm)],
        "q_kPa": cfg["q_kPa"],
        "fill_thickness_m": fill_h,
        "D_mm": cfg["D_mm"],
        "spacing_m": cfg["spacing_m"],
        "pattern": cfg["pattern"],
        "a": a_ratio,
        "Ec_factor": cfg["Ec_factor"],
        "qu_kPa": cfg["qu_kPa"],
        "Ec_kPa": Ec_kPa,
        "design_elev_global_m": cfg["settlement_design_elev_m"],
    }
    criteria = {
        "road_class": "cao_toc",
        "structure": "cau",
        "speed_kmh": 80,
        "position": "near_bridge",
        "dS_limit_cm": delta_S_cm,
        "design_dS_cm": float(delta_S_cm),
        "i_inv": 200,
        "i_inv_eff": 125,
        "i_inv_threshold": 125,
    }
    # Phân vùng quantile từ grid_lc ở mức ΔS chỉ định
    with sqlite3.connect(db) as _con_z:
        _con_z.row_factory = sqlite3.Row
        grid_lc_rows = [dict(r) for r in _con_z.execute(
            "SELECT Lc_m FROM cdm_qtt_grid_lc WHERE delta_S_cm=? "
            "AND Lc_m IS NOT NULL ORDER BY Lc_m",
            (float(delta_S_cm),)
        ).fetchall()]
    lcs = [r["Lc_m"] for r in grid_lc_rows if r["Lc_m"] is not None]
    zoning_stats = []
    bins: list[int] = []
    if lcs:
        n_zones = 4
        bins = [0] + [int(len(lcs) * k / n_zones)
                       for k in range(1, n_zones)] + [len(lcs)]
        for z in range(n_zones):
            sub = lcs[bins[z]:bins[z + 1]]
            if not sub:
                continue
            zoning_stats.append({
                "zone_id": z,
                "Lc_min": float(min(sub)),
                "Lc_max": float(max(sub)),
                "Lc_design": float(max(sub)),
                "n_points": len(sub),
                "area_m2": len(sub) * 400.0,  # 20×20 m cell
            })
    # Map mỗi grid point → zone bằng quantile assignment
    grid_assignment = {}
    if lcs:
        with sqlite3.connect(db) as _con_a:
            _con_a.row_factory = sqlite3.Row
            grid_full = _con_a.execute(
                "SELECT easting_m, northing_m, Lc_m FROM cdm_qtt_grid_lc "
                "WHERE delta_S_cm=? AND Lc_m IS NOT NULL",
                (float(delta_S_cm),),
            ).fetchall()
        breaks = [lcs[bins[k]] for k in range(1, len(bins) - 1)]
        for r in grid_full:
            lc_v = float(r["Lc_m"])
            z = 0
            for k, br in enumerate(breaks):
                if lc_v >= br:
                    z = k + 1
            grid_assignment[(float(r["easting_m"]),
                              float(r["northing_m"]))] = z
    zoning = {"n_zones": 4, "stats": zoning_stats,
              "assignment": grid_assignment}
    grid_meta = {"n_points": len(grid_points)}
    hks_with_S = []
    for r in lc_rows_raw:
        if r["delta_S_cm"] != delta_S_cm:
            continue
        bh = next((b for b in bh_rows if b["name"] == r["bh_name"]), None)
        if bh:
            hks_with_S.append({"name": r["bh_name"],
                                "E": bh["E"], "N": bh["N"],
                                "S_cm": r["S_total_cm"]})

    docx_bytes = build_qtt_decision_docx(
        meta=meta, lc_matrix=lc_matrix,
        criteria=criteria, smoothness_pairs=smooth_pairs,
        zoning=zoning, grid_meta=grid_meta,
        grid_points=grid_points, hks_with_S=hks_with_S,
    )
    docx_out.write_bytes(docx_bytes)
    paths["docx"] = docx_out
    print(f"    OK — {len(docx_bytes) / 1024:.1f} KB")
    return paths


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    print("=" * 60)
    print(f"§72 Task DD — Báo cáo QTT cho ΔS=15 cm")
    print(f"Bắt đầu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    paths = export_report(delta_S_cm=15)
    print()
    print("HOÀN THÀNH:")
    for kind, p in paths.items():
        sz = p.stat().st_size / 1024
        print(f"  {kind.upper():<5s}: {p}  ({sz:.1f} KB)")
