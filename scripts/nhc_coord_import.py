"""
Import tọa độ VN-2000 hố khoan NHC từ DXF:
  G:/My Drive/202605-TRUNG TAM HCM/DIA CHAT/2. NHÀ HÀNH CHÍNH/
  NHC-1. TRỤ_TTHC_Tru hien truong.dxf

Quy ước DB (giống BXN/KE):
  x_coord_m = Northing (VN-2000, ~1191xxx)
  y_coord_m = Easting  (VN-2000, ~605xxx)

Hàm công khai:
  extract_nhc_coords(dxf_path)   → list[dict]
  save_coords_to_json(results, json_path)
  update_db_coords(results, db_path) → dict thống kê
"""
import re
import json
import sqlite3
from pathlib import Path

try:
    import ezdxf
except ImportError:
    raise ImportError("Cần cài: pip install ezdxf")

_HERE   = Path(__file__).parent
_DB     = _HERE.parent / "data" / "TTHC.sqlite"
_JSON   = _HERE.parent / "data" / "nhc_coords_202605_TTHC.json"
_DXF    = Path(r"G:\My Drive\202605-TRUNG TAM HCM\DIA CHAT\2. NHÀ HÀNH CHÍNH\NHC-1. TRỤ_TTHC_Tru hien truong.dxf")

# Dòng toạ độ trong DXF (page 1, y đủ cao để không bị lẫn)
_Y_HEADER   = 71646.0   # tên BH
_Y_NORTH    = 71592.0   # Northing
_Y_EAST_LO  = 71587.0   # Easting (BH-03, BH-05 — nhóm trái)
_Y_EAST_HI  = 71588.0   # Easting (nhóm phải)
_Y_ELEV     = 71582.0   # Cao độ mặt đất
_Y_TOL      = 2.0       # tolerance y


def _clean(txt: str) -> str:
    return re.sub(r"\\\w[^;]*;", "", txt).strip()


def extract_nhc_coords(dxf_path: Path = _DXF) -> list[dict]:
    """
    Trích xuất tọa độ BH từ DXF bằng pair-by-order (sort x).
    Trả về list[dict] với keys:
      bh_name_raw, bh_name_db, northing_m, easting_m, elevation_m
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    texts = []
    for e in msp:
        if e.dxftype() in ("TEXT", "MTEXT"):
            raw = e.dxf.text if e.dxftype() == "TEXT" else e.text
            txt = _clean(raw)
            pos = e.dxf.insert
            texts.append((txt, round(pos.x, 2), round(pos.y, 2)))

    def _collect(pattern: str, y_center: float) -> list[tuple]:
        return sorted(
            [(float(t) if re.fullmatch(r"-?\d+\.\d+", t) else t, x)
             for t, x, y in texts
             if abs(y - y_center) < _Y_TOL and re.fullmatch(pattern, t)],
            key=lambda r: r[1],
        )

    bh_names  = _collect(r"BH-\d+",          _Y_HEADER)
    northings = _collect(r"119\d{4}\.\d+",   _Y_NORTH)
    eastings  = sorted(
        [(float(t), x)
         for t, x, y in texts
         if (abs(y - _Y_EAST_LO) < _Y_TOL or abs(y - _Y_EAST_HI) < _Y_TOL)
         and re.fullmatch(r"60[56]\d{3}\.\d+", t)],
        key=lambda r: r[1],
    )
    elevations = _collect(r"-?\d+\.\d{2}",   _Y_ELEV)

    n = min(len(bh_names), len(northings), len(eastings))
    results = []
    for i in range(n):
        name_raw = bh_names[i][0]
        elev     = elevations[i][0] if i < len(elevations) else None
        results.append({
            "bh_name_raw": name_raw,
            "bh_name_db":  f"NHC-{name_raw}",
            "northing_m":  northings[i][0],
            "easting_m":   eastings[i][0],
            "elevation_m": float(elev) if elev is not None else None,
        })
    return results


def save_coords_to_json(results: list[dict], json_path: Path = _JSON) -> None:
    data = {
        "_meta": {
            "source":  "NHC-1. TRỤ_TTHC_Tru hien truong.dxf",
            "updated": "2026-05-19",
            "project": "202605-TTHC",
            "coord_system": "VN-2000 TP.HCM (CM=105°45', FE=500000)",
            "db_convention": "x_coord_m=Northing, y_coord_m=Easting (giống BXN/KE)",
            "n_boreholes": len(results),
        },
        "boreholes": results,
    }
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã lưu {len(results)} HK vào {json_path.name}")


def update_db_coords(
    results: list[dict],
    db_path: Path = _DB,
    update_elevation: bool = True,
) -> dict:
    """
    Cập nhật x_coord_m, y_coord_m (và elevation_m) cho các BH NHC trong SQLite.
    Trả về dict thống kê: {updated, not_found, already_had_coords}.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    stats = {"updated": 0, "not_found": 0, "already_had_coords": 0, "details": []}

    for r in results:
        bh_name = r["bh_name_db"]
        row = conn.execute(
            "SELECT id, x_coord_m, elevation_m FROM boreholes WHERE name=?", (bh_name,)
        ).fetchone()

        if row is None:
            stats["not_found"] += 1
            stats["details"].append(f"NOT FOUND: {bh_name}")
            continue

        had_coords = row["x_coord_m"] is not None
        if had_coords:
            stats["already_had_coords"] += 1

        if update_elevation and r["elevation_m"] is not None:
            conn.execute(
                "UPDATE boreholes SET x_coord_m=?, y_coord_m=?, elevation_m=? WHERE id=?",
                (r["northing_m"], r["easting_m"], r["elevation_m"], row["id"]),
            )
        else:
            conn.execute(
                "UPDATE boreholes SET x_coord_m=?, y_coord_m=? WHERE id=?",
                (r["northing_m"], r["easting_m"], row["id"]),
            )
        stats["updated"] += 1
        stats["details"].append(
            f"OK: {bh_name}  N={r['northing_m']:.3f}  E={r['easting_m']:.3f}"
            + (f"  elev={r['elevation_m']}" if r["elevation_m"] else "")
        )

    conn.commit()
    conn.close()
    return stats


if __name__ == "__main__":
    print("=== Trích xuất tọa độ NHC từ DXF ===")
    results = extract_nhc_coords()
    print(f"Trích xuất: {len(results)} hố khoan\n")
    for r in results:
        print(f"  {r['bh_name_db']:15}  N={r['northing_m']:.3f}  E={r['easting_m']:.3f}  elev={r['elevation_m']}")

    print("\n=== Lưu JSON ===")
    save_coords_to_json(results)

    print("\n=== Cập nhật SQLite ===")
    stats = update_db_coords(results)
    print(f"Cập nhật: {stats['updated']} | Không tìm thấy: {stats['not_found']} | Đã có coords: {stats['already_had_coords']}")
    for d in stats["details"]:
        print(f"  {d}")
