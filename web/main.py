"""web/main.py — FastAPI backend cho tthc.seapevn-tvtkhatang.com
Chạy: python -X utf8 -m uvicorn web.main:app --port 8503 --reload
"""
import sqlite3, json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).parent.parent
DB   = ROOT / "data" / "TTHC.sqlite"

app = FastAPI(title="TTHC Engineering")
app.mount("/static", StaticFiles(directory=str(ROOT / "web" / "static")), name="static")
templates = Jinja2Templates(directory=str(ROOT / "web" / "templates"))


def _db():
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    return con


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="cdm_map.html")


@app.get("/ban-do-cdm", response_class=HTMLResponse)
async def cdm_map(request: Request):
    return templates.TemplateResponse(request=request, name="cdm_map.html")


# ── API: CDM tọa độ ────────────────────────────────────────────────────────────

@app.get("/api/cdm/toado")
async def api_cdm_toado(zone: Optional[str] = None):
    """Trả về tọa độ cọc CDM. zone=KE|CONG_VIEN|all"""
    con = _db()
    q = "SELECT zone, point_name, northing_m, easting_m FROM cdm_toado"
    params = []
    if zone and zone != "all":
        q += " WHERE zone = ?"
        params.append(zone)
    rows = con.execute(q, params).fetchall()
    con.close()
    return JSONResponse({
        "n": len(rows),
        "points": [{"z": r[0], "n": r[1], "x": r[2], "y": r[3]} for r in rows],
    })


@app.get("/api/cdm/stats")
async def api_cdm_stats():
    """Thống kê khối lượng CDM per zone + per borehole."""
    con = _db()

    # Per zone
    zone_rows = con.execute("""
        SELECT zone,
               COUNT(*) AS n_coc,
               ROUND(AVG(L_design_m), 2) AS L_avg,
               ROUND(MIN(L_design_m), 2) AS L_min,
               ROUND(MAX(L_design_m), 2) AS L_max,
               ROUND(SUM(3.14159265/4 * D_m * D_m * L_design_m), 0) AS V_m3
        FROM cdm_thi_cong
        WHERE L_design_m IS NOT NULL
        GROUP BY zone
        ORDER BY zone
    """).fetchall()

    # Per borehole
    bh_rows = con.execute("""
        SELECT bh_dieu_hanh, zone,
               COUNT(*) AS n_coc,
               ROUND(AVG(L_design_m), 2) AS L_avg,
               ROUND(SUM(3.14159265/4 * D_m * D_m * L_design_m), 0) AS V_m3
        FROM cdm_thi_cong
        WHERE L_design_m IS NOT NULL AND bh_dieu_hanh IS NOT NULL
        GROUP BY bh_dieu_hanh, zone
        ORDER BY zone, bh_dieu_hanh
    """).fetchall()

    # Status distribution
    status_rows = con.execute("""
        SELECT zone, status, COUNT(*) AS n
        FROM cdm_thi_cong GROUP BY zone, status ORDER BY zone, status
    """).fetchall()

    con.close()
    return JSONResponse({
        "by_zone": [dict(r) for r in zone_rows],
        "by_bh":   [dict(r) for r in bh_rows],
        "status":  [dict(r) for r in status_rows],
    })


# ── API: Hố khoan ──────────────────────────────────────────────────────────────

@app.get("/api/boreholes")
async def api_boreholes(zone: Optional[str] = None):
    """Trả về vị trí và thông tin hố khoan."""
    con = _db()
    q = """
        SELECT name, elevation_m, x_coord_m, y_coord_m,
               CASE
                 WHEN name LIKE 'KE-%'     THEN 'KE'
                 WHEN name LIKE 'BXN-%'    THEN 'BXN'
                 WHEN name LIKE 'NHC-%'    THEN 'NHC'
                 WHEN name LIKE 'ND-%'     THEN 'QTT'
                 ELSE 'OTHER'
               END AS zone
        FROM boreholes
        WHERE x_coord_m > 1000000 AND y_coord_m IS NOT NULL
    """
    params = []
    if zone and zone != "all":
        q += " AND zone = ?"
        params.append(zone)
    q += " ORDER BY name"
    rows = con.execute(q, params).fetchall()
    con.close()
    return JSONResponse({
        "boreholes": [dict(r) for r in rows]
    })


# ── API: Ranh kè ───────────────────────────────────────────────────────────────

@app.get("/api/ke-binhdo")
async def api_ke_binhdo():
    """Trả về polyline ranh kè từ ke_binhdo_toadoke."""
    con = _db()
    try:
        rows = con.execute("""
            SELECT polyline_id, x_m, y_m
            FROM ke_binhdo_toadoke
            ORDER BY polyline_id, vertex_idx
        """).fetchall()
    except Exception:
        rows = []
    con.close()
    # Group by polyline_id
    polys: dict = {}
    for pid, x, y in rows:
        polys.setdefault(pid, []).append({"x": x, "y": y})
    return JSONResponse({"polylines": list(polys.values())})
