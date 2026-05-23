"""web/app8508.py — FastAPI app port 8508, layout giống Streamlit
Chạy: python -X utf8 -m uvicorn web.app8508:app --port 8508 --reload
"""
import sqlite3, json, math
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).parent.parent
DB   = ROOT / "data" / "TTHC.sqlite"

app = FastAPI(title="TTHC 8508")
app.mount("/static", StaticFiles(directory=str(ROOT / "web" / "static")), name="static")
templates = Jinja2Templates(directory=str(ROOT / "web" / "templates"))

def _db():
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    return con

# ── Pages ──────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="app.html")

# ── API: Địa chất ──────────────────────────────────────────────────────────────
@app.get("/api/boreholes")
async def api_boreholes(zone: Optional[str] = None):
    con = _db()
    q = """SELECT name, elevation_m, x_coord_m, y_coord_m,
               CASE WHEN name LIKE 'KE-%'  THEN 'KE'
                    WHEN name LIKE 'BXN-%' THEN 'BXN'
                    WHEN name LIKE 'NHC-%' THEN 'NHC'
                    WHEN name LIKE 'ND-%'  THEN 'QTT'
                    ELSE 'OTHER' END AS zone
           FROM boreholes WHERE x_coord_m > 1000000 ORDER BY name"""
    rows = con.execute(q).fetchall()
    con.close()
    bhs = [dict(r) for r in rows]
    if zone and zone != "all":
        bhs = [b for b in bhs if b["zone"] == zone]
    return JSONResponse({"boreholes": bhs})

@app.get("/api/borehole/{name}/layers")
async def api_layers(name: str):
    con = _db()
    bh = con.execute("SELECT id,elevation_m FROM boreholes WHERE name=?", (name,)).fetchone()
    if not bh:
        return JSONResponse({"layers": [], "spt": [], "vst": []})
    bid, elev = bh["id"], bh["elevation_m"] or 0
    layers = con.execute(
        "SELECT layer_no,symbol,description,depth_top_m,depth_bot_m FROM layers WHERE borehole_id=? ORDER BY depth_top_m",
        (bid,)).fetchall()
    spt = con.execute(
        "SELECT depth_m,N FROM spt_values WHERE borehole_id=? ORDER BY depth_m",
        (bid,)).fetchall()
    vst = con.execute(
        "SELECT depth_m, su_kPa FROM vane_shear_tests WHERE borehole_id=? ORDER BY depth_m",
        (bid,)).fetchall()
    con.close()
    return JSONResponse({
        "elevation_m": elev,
        "layers": [dict(r) for r in layers],
        "spt":    [dict(r) for r in spt],
        "vst":    [dict(r) for r in vst],
    })

# ── API: CDM tọa độ ────────────────────────────────────────────────────────────
@app.get("/api/cdm/toado")
async def api_cdm_toado(zone: Optional[str] = None):
    con = _db()
    q = "SELECT zone, point_name, northing_m, easting_m FROM cdm_toado"
    params = []
    if zone and zone != "all":
        q += " WHERE zone=?"; params.append(zone)
    rows = con.execute(q, params).fetchall()
    con.close()
    return JSONResponse({"n": len(rows),
        "points": [{"z":r[0],"n":r[1],"x":r[2],"y":r[3]} for r in rows]})

@app.get("/api/cdm/stats")
async def api_cdm_stats():
    con = _db()
    zone_rows = con.execute("""
        SELECT zone, COUNT(*) n_coc,
               ROUND(AVG(L_design_m),2) L_avg, ROUND(MIN(L_design_m),2) L_min,
               ROUND(MAX(L_design_m),2) L_max,
               ROUND(SUM(3.14159265/4*D_m*D_m*L_design_m),0) V_m3
        FROM cdm_thi_cong WHERE L_design_m IS NOT NULL GROUP BY zone ORDER BY zone""").fetchall()
    bh_rows = con.execute("""
        SELECT bh_dieu_hanh, zone, COUNT(*) n_coc,
               ROUND(AVG(L_design_m),2) L_avg,
               ROUND(SUM(3.14159265/4*D_m*D_m*L_design_m),0) V_m3
        FROM cdm_thi_cong WHERE L_design_m IS NOT NULL AND bh_dieu_hanh IS NOT NULL
        GROUP BY bh_dieu_hanh, zone ORDER BY zone, bh_dieu_hanh""").fetchall()
    status_rows = con.execute("""
        SELECT zone,status,COUNT(*) n FROM cdm_thi_cong GROUP BY zone,status ORDER BY zone,status""").fetchall()
    con.close()
    return JSONResponse({"by_zone":[dict(r) for r in zone_rows],
                         "by_bh":  [dict(r) for r in bh_rows],
                         "status": [dict(r) for r in status_rows]})

@app.get("/api/cdm/tien-do")
async def api_tien_do():
    con = _db()
    daily = con.execute("""
        SELECT ngay_thi_cong, zone, COUNT(*) n FROM cdm_thi_cong
        WHERE ngay_thi_cong IS NOT NULL AND status IN ('hoan_thanh','dang_thi_cong')
        GROUP BY ngay_thi_cong, zone ORDER BY ngay_thi_cong""").fetchall()
    todoi = con.execute("""
        SELECT to_doi, zone, COUNT(*) n,
               SUM(CASE WHEN status='hoan_thanh' THEN 1 ELSE 0 END) done
        FROM cdm_thi_cong WHERE to_doi IS NOT NULL GROUP BY to_doi,zone ORDER BY to_doi""").fetchall()
    con.close()
    return JSONResponse({"daily":[dict(r) for r in daily],
                         "todoi":[dict(r) for r in todoi]})

@app.get("/api/cdm/kiem-tra")
async def api_kiem_tra():
    con = _db()
    rows = con.execute("""
        SELECT zone,point_name,loai_tn,ngay_thu_nghiem,tuoi_ngay,
               do_sau_tu_dinh_m,z_sample_m,qu_kPa,qu_yc_kPa,dat_yeu_cau,
               ham_luong_xi_mang_pct,ghi_chu
        FROM cdm_kiem_tra ORDER BY zone,ngay_thu_nghiem,z_sample_m""").fetchall()
    con.close()
    return JSONResponse({"rows":[dict(r) for r in rows]})

@app.get("/api/ke-binhdo")
async def api_ke_binhdo():
    con = _db()
    try:
        rows = con.execute(
            "SELECT polyline_id,x_m,y_m FROM ke_binhdo_toadoke ORDER BY polyline_id,vertex_idx"
        ).fetchall()
    except Exception:
        rows = []
    con.close()
    polys: dict = {}
    for pid, x, y in rows:
        polys.setdefault(pid, []).append({"x": x, "y": y})
    return JSONResponse({"polylines": list(polys.values())})

@app.get("/api/settlement/compare")
async def api_settlement(bh_name: str = "BXN-CV-HK1", H_fill: float = 3.0):
    """Tính lún so sánh phương án — wrap settlement_calc.py"""
    try:
        import sys; sys.path.insert(0, str(ROOT / "scripts"))
        from settlement_calc import compare_methods
        result = compare_methods(bh_name, "BXN", H_fill)
        return JSONResponse({"ok": True, "result": result})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})
