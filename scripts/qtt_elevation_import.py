"""
qtt_elevation_import.py
Parse DXF cao độ tự nhiên + thiết kế khu vực QTT,
lưu vào data/qtt_elevation_202605_TTHC.json và TTHC.sqlite (bảng qtt_elevation_points).

Nguồn:
  - QTT-MTEXT CAO DO TU NHIEN-RANH XULYNEN CDM.dxf  (layer C-TOPO-TEXT, z = cao độ tự nhiên)
  - QTT-MTEXT CAO DO THIET KE-RANH XULYNEN CDM.dxf   (layer C-TOPO-TEXT, z = cao độ thiết kế)
    kèm 1 LWPOLYLINE layer C-PROP-BNDY = ranh giới vùng xử lý nền CDM

Cách dùng:
  python scripts/qtt_elevation_import.py
"""

import json
import sqlite3
from pathlib import Path
import ezdxf

_ROOT  = Path(__file__).resolve().parent.parent
_DB    = _ROOT / "data" / "TTHC.sqlite"
_DATA  = _ROOT / "data"

_DXF_NAT = (
    Path(r"G:\My Drive\202605-TRUNG TAM HCM\QUANG TRUONG VI DAN")
    / "QTT-MTEXT CAO DO TU NHIEN-RANH XULYNEN CDM.dxf"
)
_DXF_DES = (
    Path(r"G:\My Drive\202605-TRUNG TAM HCM\QUANG TRUONG VI DAN")
    / "QTT-MTEXT CAO DO THIET KE-RANH XULYNEN CDM.dxf"
)


def _parse_mtext_elevations(dxf_path: Path) -> list[dict]:
    """Trả về list {easting, northing, elevation} từ layer C-TOPO-TEXT."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    pts = []
    for e in msp:
        if e.dxftype() == "MTEXT" and e.dxf.layer == "C-TOPO-TEXT":
            p = e.dxf.insert
            try:
                elev = float(e.plain_text().strip())
            except ValueError:
                elev = float(p.z)
            pts.append({"easting_m": round(p.x, 3), "northing_m": round(p.y, 3), "elevation_m": round(elev, 3)})
    return sorted(pts, key=lambda r: (r["easting_m"], r["northing_m"]))


def _parse_boundary(dxf_path: Path) -> list[list[float]]:
    """Trả về danh sách [[easting, northing], ...] từ LWPOLYLINE C-PROP-BNDY."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    for e in msp:
        if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "C-PROP-BNDY":
            return [[round(v[0], 3), round(v[1], 3)] for v in e.vertices()]
    return []


def build_combined(nat_pts: list[dict], des_pts: list[dict]) -> list[dict]:
    """Join by (easting, northing), thêm fill = design − natural."""
    des_map = {(r["easting_m"], r["northing_m"]): r["elevation_m"] for r in des_pts}
    out = []
    for r in nat_pts:
        key = (r["easting_m"], r["northing_m"])
        des_elev = des_map.get(key)
        fill = round(des_elev - r["elevation_m"], 3) if des_elev is not None else None
        out.append({
            "easting_m":   r["easting_m"],
            "northing_m":  r["northing_m"],
            "elev_nat_m":  r["elevation_m"],
            "elev_des_m":  des_elev,
            "fill_m":      fill,
        })
    return out


def save_json(pts: list[dict], boundary: list[list[float]]) -> Path:
    """Lưu JSON snapshot."""
    from datetime import date
    out = {
        "_meta": {
            "source_nat": _DXF_NAT.name,
            "source_des": _DXF_DES.name,
            "n_points":   len(pts),
            "grid_step_m": 20,
            "crs":        "VN-2000 / TM-3 106E (EPSG:9210)",
            "updated":    str(date.today()),
        },
        "boundary_cdm": boundary,
        "points": pts,
    }
    path = _DATA / "qtt_elevation_202605_TTHC.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_sqlite(pts: list[dict], boundary: list[list[float]]) -> None:
    """Upsert vào TTHC.sqlite."""
    con = sqlite3.connect(_DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS qtt_elevation_points (
            easting_m   REAL NOT NULL,
            northing_m  REAL NOT NULL,
            elev_nat_m  REAL,
            elev_des_m  REAL,
            fill_m      REAL,
            PRIMARY KEY (easting_m, northing_m)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS qtt_cdm_boundary (
            id          INTEGER PRIMARY KEY,
            easting_m   REAL,
            northing_m  REAL,
            vertex_order INTEGER
        )
    """)
    con.execute("DELETE FROM qtt_elevation_points")
    con.executemany(
        "INSERT OR REPLACE INTO qtt_elevation_points VALUES (:easting_m,:northing_m,:elev_nat_m,:elev_des_m,:fill_m)",
        pts,
    )
    con.execute("DELETE FROM qtt_cdm_boundary")
    con.executemany(
        "INSERT INTO qtt_cdm_boundary (easting_m, northing_m, vertex_order) VALUES (?,?,?)",
        [(v[0], v[1], i) for i, v in enumerate(boundary)],
    )
    con.commit()
    con.close()


def main() -> None:
    print("Đọc DXF cao độ tự nhiên …")
    nat_pts = _parse_mtext_elevations(_DXF_NAT)
    print(f"  → {len(nat_pts)} điểm, Z=[{min(r['elevation_m'] for r in nat_pts):.2f}…{max(r['elevation_m'] for r in nat_pts):.2f}] m")

    print("Đọc DXF cao độ thiết kế …")
    des_pts = _parse_mtext_elevations(_DXF_DES)
    print(f"  → {len(des_pts)} điểm, Z=[{min(r['elevation_m'] for r in des_pts):.2f}…{max(r['elevation_m'] for r in des_pts):.2f}] m")

    boundary = _parse_boundary(_DXF_DES)
    print(f"  → Ranh CDM: {len(boundary)} đỉnh")

    combined = build_combined(nat_pts, des_pts)
    fills = [r["fill_m"] for r in combined if r["fill_m"] is not None]
    print(f"Chênh cao (đắp+/đào-): min={min(fills):.2f} max={max(fills):.2f} TB={sum(fills)/len(fills):.2f} m")

    print("Lưu JSON …")
    jpath = save_json(combined, boundary)
    print(f"  → {jpath}")

    print("Lưu SQLite …")
    save_sqlite(combined, boundary)
    print(f"  → {_DB.name}: {len(combined)} dòng qtt_elevation_points, {len(boundary)} dòng qtt_cdm_boundary")
    print("Xong.")


if __name__ == "__main__":
    main()
