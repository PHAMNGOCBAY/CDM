"""
qtt_export_dxf.py — Xuất biểu đồ phân vùng CDM QTT ra file DXF.

Đọc:
  - cdm_qtt_grid_lc (162 điểm × 4 ΔS)
  - qtt_cdm_boundary (polygon ranh giới)
  - boreholes (ND-02..ND-06 với toạ độ E/N)

Ghi:
  Layers DXF:
    QTT_ZONE_P1..P4   — hatch SOLID + boundary mỗi vùng
    QTT_BOUNDARY      — polygon ranh giới QTT
    QTT_BOREHOLES     — kim cương + text label HK
    QTT_GRID_POINTS   — điểm grid (option)
    QTT_LEGEND        — bảng chú giải góc dưới-phải
    QTT_TITLE         — tiêu đề
"""
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import ezdxf
from ezdxf.enums import TextEntityAlignment
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

_DB_LOCAL = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
_DB_PROJ = Path(__file__).resolve().parents[1] / "data" / "TTHC.sqlite"


def _db_path() -> Path:
    return _DB_LOCAL if _DB_LOCAL.exists() else _DB_PROJ


# Màu DXF ACI (AutoCAD Color Index)
ZONE_COLORS_ACI = {
    1: 5,    # P1 — xanh dương
    2: 1,    # P2 — đỏ
    3: 3,    # P3 — xanh lá
    4: 30,   # P4 — cam
    5: 6,    # P5 — tím
    6: 4,    # P6 — xanh ngọc
}


def _quantile_zoning(lc_values: list[float], n_zones: int = 4) -> list[int]:
    """Quantile binning: chia điểm thành n_zones theo Lc tăng dần.
    Trả về assignment[i] in {1..n_zones} (1 = Lc nhỏ nhất).
    """
    if not lc_values:
        return []
    arr = np.array(lc_values)
    quantiles = np.quantile(arr, [k / n_zones for k in range(1, n_zones)])
    zones = []
    for v in arr:
        z = 1
        for q in quantiles:
            if v > q:
                z += 1
        zones.append(min(z, n_zones))
    return zones


def _load_qtt_data(delta_S_cm: int = 30, db_path: Optional[Path] = None) -> dict:
    db = db_path or _db_path()
    if not db.exists():
        raise FileNotFoundError(f"SQLite không tồn tại: {db}")
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        # grid Lc
        grid_rows = con.execute(
            "SELECT easting_m AS E, northing_m AS N, Lc_m, S_total_cm, ok "
            "FROM cdm_qtt_grid_lc WHERE delta_S_cm = ? "
            "ORDER BY northing_m, easting_m",
            (delta_S_cm,)
        ).fetchall()
        # boundary
        bd_rows = con.execute(
            "SELECT easting_m AS E, northing_m AS N FROM qtt_cdm_boundary "
            "ORDER BY vertex_order"
        ).fetchall()
        # boreholes — QTT ND-02..ND-07
        bh_rows = con.execute(
            "SELECT name, x_coord_m AS N, y_coord_m AS E "
            "FROM boreholes WHERE name LIKE 'ND-%'"
        ).fetchall()

    grid = [{"E": r["E"], "N": r["N"], "Lc": r["Lc_m"],
              "S": r["S_total_cm"], "ok": r["ok"]} for r in grid_rows]
    boundary = [(r["E"], r["N"]) for r in bd_rows]
    bhs = [{"name": r["name"], "E": r["E"], "N": r["N"]} for r in bh_rows]
    return {"grid": grid, "boundary": boundary, "bhs": bhs,
            "delta_S_cm": delta_S_cm}


def _make_diamond_block(doc, name: str = "QTT_BH_DIAMOND", size: float = 5.0):
    """Tạo block kim cương cho marker HK."""
    if name in doc.blocks:
        return doc.blocks[name]
    block = doc.blocks.new(name=name)
    s = size / 2
    pts = [(0, s), (s, 0), (0, -s), (-s, 0), (0, s)]
    block.add_lwpolyline(pts, close=True,
                         dxfattribs={"color": 7, "lineweight": 35})
    block.add_solid([(0, s), (s, 0), (0, -s), (-s, 0)],
                    dxfattribs={"color": 7})
    return block


def export_qtt_zoning_dxf(
    out_path: Path,
    delta_S_cm: int = 30,
    n_zones: int = 4,
    cell_size_m: Optional[float] = None,
    show_grid_points: bool = False,
    show_lc_values: bool = False,
    db_path: Optional[Path] = None,
) -> dict:
    """Xuất file DXF phân vùng QTT.

    Args:
        out_path: đường dẫn xuất .dxf
        delta_S_cm: chọn mức ΔS (10, 20, 30, 40)
        n_zones: số vùng phân (mặc định 4 — quantile)
        cell_size_m: kích thước ô grid (None = auto từ spacing trung bình)
        show_grid_points: True → vẽ thêm điểm circle cho mỗi grid point
        show_lc_values: True → in giá trị Lc tại mỗi điểm
    """
    data = _load_qtt_data(delta_S_cm=delta_S_cm, db_path=db_path)
    grid = data["grid"]
    boundary = data["boundary"]
    bhs = data["bhs"]

    if not grid:
        raise ValueError(f"Không có dữ liệu grid cho ΔS = {delta_S_cm} cm")

    # Auto cell size — phỏng đoán từ khoảng cách trung bình giữa các điểm
    if cell_size_m is None:
        Es = sorted(set(p["E"] for p in grid))
        Ns = sorted(set(p["N"] for p in grid))
        dE = np.diff(Es).mean() if len(Es) > 1 else 25.0
        dN = np.diff(Ns).mean() if len(Ns) > 1 else 25.0
        cell_size_m = float(np.round((dE + dN) / 2, 1))

    half = cell_size_m / 2.0

    # Quantile-binning
    lcs = [p["Lc"] for p in grid]
    zones = _quantile_zoning(lcs, n_zones=n_zones)

    # Thống kê per zone (Lc max = design value)
    zone_stats = {}
    for z, p in zip(zones, grid):
        zone_stats.setdefault(z, []).append(p["Lc"])
    zone_design = {z: max(vs) for z, vs in zone_stats.items()}

    # ────── Tạo DXF document ──────
    doc = ezdxf.new(dxfversion="R2018", setup=True)
    doc.units = ezdxf.units.M  # mét

    # Layers
    for z in range(1, n_zones + 1):
        doc.layers.add(name=f"QTT_ZONE_P{z}",
                        color=ZONE_COLORS_ACI.get(z, 7))
    doc.layers.add(name="QTT_BOUNDARY", color=7, lineweight=50)
    doc.layers.add(name="QTT_BOREHOLES", color=7, lineweight=35)
    doc.layers.add(name="QTT_BH_LABEL", color=7)
    doc.layers.add(name="QTT_GRID_POINTS", color=8)
    doc.layers.add(name="QTT_LC_TEXT", color=8)
    doc.layers.add(name="QTT_LEGEND", color=7)
    doc.layers.add(name="QTT_TITLE", color=7)

    msp = doc.modelspace()
    _make_diamond_block(doc, size=cell_size_m * 0.5)

    # ────── 1. Polygon ranh giới ──────
    if boundary:
        # Đảm bảo closed
        pts = boundary[:]
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        msp.add_lwpolyline(pts, close=True,
                           dxfattribs={"layer": "QTT_BOUNDARY",
                                       "color": 7, "lineweight": 50})

    # ────── 2. Hatch cho từng vùng ──────
    for z, p in zip(zones, grid):
        E, N = p["E"], p["N"]
        # Ô vuông centered tại (E, N), size = cell_size_m
        cell_pts = [
            (E - half, N - half),
            (E + half, N - half),
            (E + half, N + half),
            (E - half, N + half),
        ]
        # Hatch SOLID + outline mảnh
        hatch = msp.add_hatch(color=ZONE_COLORS_ACI.get(z, 7),
                              dxfattribs={"layer": f"QTT_ZONE_P{z}"})
        hatch.paths.add_polyline_path(cell_pts, is_closed=True)
        # Outline (nhẹ)
        msp.add_lwpolyline(cell_pts + [cell_pts[0]],
                           dxfattribs={"layer": f"QTT_ZONE_P{z}",
                                       "color": 8})

        if show_lc_values:
            msp.add_text(
                f"{p['Lc']:.1f}",
                dxfattribs={"layer": "QTT_LC_TEXT",
                            "height": cell_size_m * 0.18,
                            "color": 0},
            ).set_placement((E, N), align=TextEntityAlignment.MIDDLE_CENTER)

        if show_grid_points:
            msp.add_circle(
                (E, N), radius=cell_size_m * 0.08,
                dxfattribs={"layer": "QTT_GRID_POINTS", "color": 8},
            )

    # ────── 3. Boreholes ──────
    bh_size = max(cell_size_m * 0.6, 3.0)
    _make_diamond_block(doc, name="QTT_BH_DIAMOND_FINAL", size=bh_size)
    for bh in bhs:
        msp.add_blockref("QTT_BH_DIAMOND_FINAL", (bh["E"], bh["N"]),
                         dxfattribs={"layer": "QTT_BOREHOLES"})
        msp.add_text(
            bh["name"],
            dxfattribs={"layer": "QTT_BH_LABEL",
                        "height": cell_size_m * 0.35,
                        "color": 7,
                        "style": "OpenSans"},
        ).set_placement(
            (bh["E"], bh["N"] + bh_size * 1.2),
            align=TextEntityAlignment.MIDDLE_CENTER,
        )

    # ────── 4. Tiêu đề ──────
    if grid:
        Es_all = [p["E"] for p in grid]
        Ns_all = [p["N"] for p in grid]
        E_min, E_max = min(Es_all), max(Es_all)
        N_min, N_max = min(Ns_all), max(Ns_all)
        msp.add_text(
            f"PHAN VUNG THIET KE CDM - QTT (Trung tam Hanh chinh TPHCM) - "
            f"{n_zones} vung theo Lc - dS = {delta_S_cm} cm",
            dxfattribs={"layer": "QTT_TITLE", "height": cell_size_m * 0.6,
                        "color": 7},
        ).set_placement(((E_min + E_max) / 2, N_max + cell_size_m * 2.0),
                        align=TextEntityAlignment.MIDDLE_CENTER)

        # ────── 5. Legend ──────
        leg_x = E_max + cell_size_m * 1.5
        leg_y = N_max
        msp.add_text(
            "CHU GIAI - Vung thiet ke",
            dxfattribs={"layer": "QTT_LEGEND", "height": cell_size_m * 0.4,
                        "color": 7},
        ).set_placement((leg_x, leg_y),
                        align=TextEntityAlignment.LEFT)
        leg_y -= cell_size_m * 1.0

        for z in sorted(zone_design.keys()):
            box = [
                (leg_x, leg_y - cell_size_m * 0.4),
                (leg_x + cell_size_m * 0.8, leg_y - cell_size_m * 0.4),
                (leg_x + cell_size_m * 0.8, leg_y + cell_size_m * 0.4),
                (leg_x, leg_y + cell_size_m * 0.4),
            ]
            hatch = msp.add_hatch(color=ZONE_COLORS_ACI.get(z, 7),
                                   dxfattribs={"layer": "QTT_LEGEND"})
            hatch.paths.add_polyline_path(box, is_closed=True)
            msp.add_lwpolyline(box + [box[0]],
                               dxfattribs={"layer": "QTT_LEGEND", "color": 7})
            n_cells = len(zone_stats[z])
            msp.add_text(
                f"P{z}: Lc = {zone_design[z]:.1f} m  ({n_cells} o)",
                dxfattribs={"layer": "QTT_LEGEND",
                            "height": cell_size_m * 0.32,
                            "color": 7},
            ).set_placement(
                (leg_x + cell_size_m * 1.1, leg_y),
                align=TextEntityAlignment.LEFT,
            )
            leg_y -= cell_size_m * 1.1

    # Save
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_path)
    return {
        "out_path": str(out_path),
        "n_grid_points": len(grid),
        "n_boreholes": len(bhs),
        "n_zones": n_zones,
        "cell_size_m": cell_size_m,
        "delta_S_cm": delta_S_cm,
        "zone_design_Lc_m": zone_design,
        "zone_n_cells": {z: len(zone_stats[z]) for z in zone_stats},
    }


# ════════ DEMO ════════
if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    out = Path("plaxis_out/QTT_ZoningMap_dS30.dxf")
    info = export_qtt_zoning_dxf(
        out_path=out,
        delta_S_cm=30,
        n_zones=4,
        show_grid_points=False,
        show_lc_values=True,
    )
    print("=" * 70)
    print("Đã xuất DXF phân vùng CDM QTT")
    print("=" * 70)
    print(f"File: {Path(info['out_path']).resolve()}")
    print(f"Số điểm grid: {info['n_grid_points']}")
    print(f"Số hố khoan: {info['n_boreholes']}")
    print(f"Số vùng: {info['n_zones']}")
    print(f"Kích thước ô: {info['cell_size_m']} m")
    print(f"ΔS cho phép: {info['delta_S_cm']} cm")
    print("Chiều dài CDM thiết kế theo vùng:")
    for z, lc in sorted(info["zone_design_Lc_m"].items()):
        n = info["zone_n_cells"][z]
        print(f"  P{z}: Lc = {lc:.1f} m ({n} ô)")
