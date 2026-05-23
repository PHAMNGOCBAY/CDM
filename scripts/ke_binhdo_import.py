"""ke_binhdo_import.py
Parse file DXF bình đồ kè (LWPOLYLINE) → SQLite bảng ke_binhdo_toadoke + JSON.
Chạy: python scripts/ke_binhdo_import.py
"""
import json, sqlite3, sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    sys.exit("Cài ezdxf trước: pip install ezdxf")

ROOT   = Path(__file__).parent.parent
DB     = ROOT / "data" / "TTHC.sqlite"
DXF    = Path(r"G:\My Drive\202605-TRUNG TAM HCM\KET CAU KE\pnbay-tọa dobinhdoke.dxf")
JSON_OUT = ROOT / "data" / "ke_binhdo_toadoke_202605_TTHC.json"

# ── Parse DXF ─────────────────────────────────────────────────────────────────
def parse_dxf(path: Path) -> list[dict]:
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    records = []
    stt = 1
    for pl_id, ent in enumerate(msp.query("LWPOLYLINE"), start=1):
        layer  = ent.dxf.layer
        closed = int(ent.closed)
        pts    = list(ent.get_points("xy"))
        for v_idx, (x, y) in enumerate(pts):
            records.append({
                "stt":         stt,
                "polyline_id": pl_id,
                "vertex_idx":  v_idx,
                "x_m":         round(x, 6),
                "y_m":         round(y, 6),
                "layer":       layer,
                "closed":      closed,
            })
            stt += 1
    return records

# ── SQLite ────────────────────────────────────────────────────────────────────
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS ke_binhdo_toadoke (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stt         INTEGER NOT NULL,
    polyline_id INTEGER NOT NULL,
    vertex_idx  INTEGER NOT NULL,
    x_m         REAL    NOT NULL,
    y_m         REAL    NOT NULL,
    layer       TEXT,
    closed      INTEGER DEFAULT 0,
    source      TEXT    DEFAULT 'DXF_pnbay'
)
"""

def update_sqlite(records: list[dict], db: Path):
    con = sqlite3.connect(str(db))
    con.execute(CREATE_SQL)
    con.execute("DELETE FROM ke_binhdo_toadoke WHERE source='DXF_pnbay'")
    con.executemany(
        "INSERT INTO ke_binhdo_toadoke "
        "(stt, polyline_id, vertex_idx, x_m, y_m, layer, closed, source) "
        "VALUES (:stt,:polyline_id,:vertex_idx,:x_m,:y_m,:layer,:closed,'DXF_pnbay')",
        records,
    )
    con.commit()
    con.close()
    print(f"SQLite: {len(records)} rows → ke_binhdo_toadoke")

# ── JSON ──────────────────────────────────────────────────────────────────────
def update_json(records: list[dict], path: Path):
    out = {
        "_meta": {
            "source":   DXF.name,
            "updated":  __import__("datetime").date.today().isoformat(),
            "n_points": len(records),
            "n_polylines": records[-1]["polyline_id"] if records else 0,
        },
        "points": records,
    }
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON: {path.name}  ({len(records)} điểm)")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Đọc {DXF.name} ...")
    recs = parse_dxf(DXF)
    n_pl = recs[-1]["polyline_id"] if recs else 0
    print(f"  {n_pl} polyline, {len(recs)} điểm")
    update_sqlite(recs, DB)
    update_json(recs, JSON_OUT)
    print("Xong.")
