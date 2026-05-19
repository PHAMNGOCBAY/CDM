"""project_db.py — Tạo và nạp TTHC.sqlite (cơ sở dữ liệu thống nhất 3 khu vực).

Schema:
  zones              — KE / BXN / NHC
  boreholes          — hố khoan (lab + trụ địa chất)
  layers             — địa tầng theo hố khoan
  spt_values         — SPT N-value theo chiều sâu
  vst_locations      — vị trí thí nghiệm cắt cánh (độc lập với boreholes)
  vane_shear_tests   — Su, S'u, St theo chiều sâu
  lab_tests          — chỉ tiêu cơ lý đất (w, γ, Atterberg, cắt, nén lún)
  cdm_tests          — CDM HK12 (qu, E50)

Usage:
  python scripts/project_db.py           # tạo + nạp toàn bộ
  python scripts/project_db.py --query   # demo query
  python scripts/project_db.py --reset   # xóa và tạo lại
"""
from __future__ import annotations
import json
import sqlite3
import sys
from pathlib import Path

ROOT    = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "TTHC.sqlite"

# ── JSON sources ───────────────────────────────────────────────────────────────
KE_PROFILE_JSON  = ROOT / "data" / "soil_profile_202605_TTHC.json"
KE_VS_JSON       = ROOT / "data" / "vane_shear_202605_TTHC.json"
KE_LAB_JSON      = ROOT / "data" / "lab_tests_202605_TTHC.json"
KE_CDM_JSON      = ROOT / "data" / "cdm_tests_202605_TTHC.json"

BXN_BH_JSON      = ROOT / "data" / "bxn_boreholes_202605_TTHC.json"
BXN_VS_JSON      = ROOT / "data" / "bxn_vane_shear_202605_TTHC.json"
BXN_LAB_JSON     = ROOT / "data" / "bxn_lab_tests_202605_TTHC.json"

NHC_VS_JSON      = ROOT / "data" / "nhc_vane_shear_202605_TTHC.json"
NHC_LAB_JSON     = ROOT / "data" / "nhc_lab_tests_202605_TTHC.json"

# ── DDL ───────────────────────────────────────────────────────────────────────
DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS zones (
    id       INTEGER PRIMARY KEY,
    code     TEXT UNIQUE NOT NULL,
    name_vi  TEXT NOT NULL,
    notes    TEXT
);

CREATE TABLE IF NOT EXISTS boreholes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id      INTEGER NOT NULL REFERENCES zones(id),
    name         TEXT UNIQUE NOT NULL,
    name_raw     TEXT,
    elevation_m  REAL,
    depth_m      REAL,
    date         TEXT,
    x_coord_m    REAL,
    y_coord_m    REAL,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS layers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    borehole_id  INTEGER NOT NULL REFERENCES boreholes(id) ON DELETE CASCADE,
    symbol       TEXT NOT NULL,
    description  TEXT,
    depth_top_m  REAL,
    depth_bot_m  REAL,
    thickness_m  REAL
);

CREATE TABLE IF NOT EXISTS spt_values (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    borehole_id  INTEGER NOT NULL REFERENCES boreholes(id) ON DELETE CASCADE,
    depth_m      REAL NOT NULL,
    elev_m       REAL,
    N1           INTEGER,
    N2           INTEGER,
    N3           INTEGER,
    N            INTEGER
);

CREATE TABLE IF NOT EXISTS vst_locations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id      INTEGER NOT NULL REFERENCES zones(id),
    name         TEXT UNIQUE NOT NULL,
    date         TEXT,
    Z_ground_m   REAL,
    vane_D_cm    REAL,
    vane_H_cm    REAL,
    K_m3         REAL,
    x_coord_m    REAL,
    y_coord_m    REAL
);

CREATE TABLE IF NOT EXISTS vane_shear_tests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vst_loc_id   INTEGER NOT NULL REFERENCES vst_locations(id) ON DELETE CASCADE,
    depth_m      REAL NOT NULL,
    elev_m       REAL,
    Su_kPa       REAL NOT NULL,
    Sp_kPa       REAL,
    St           REAL,
    note         TEXT
);

CREATE TABLE IF NOT EXISTS lab_tests (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    borehole_id      INTEGER NOT NULL REFERENCES boreholes(id) ON DELETE CASCADE,
    sample_id        TEXT NOT NULL,
    depth_from_m     REAL,
    depth_to_m       REAL,
    w_pct            REAL,
    gamma_kNm3       REAL,
    gamma_dry_kNm3   REAL,
    Gs               REAL,
    Sr_pct           REAL,
    n_pct            REAL,
    e0               REAL,
    wL_pct           REAL,
    wP_pct           REAL,
    Ip               REAL,
    IS_liq           REAL,
    phi_deg          REAL,
    c_kPa            REAL,
    a12_cm2kgf       REAL,
    E_kPa            REAL,
    Cc               REAL,
    Cs               REAL,
    Cu_UU_kPa        REAL,
    phi_UU_deg       REAL,
    symbol_tcvn      TEXT,
    description_vi   TEXT
);

CREATE TABLE IF NOT EXISTS cdm_tests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    borehole_id   INTEGER NOT NULL REFERENCES boreholes(id) ON DELETE CASCADE,
    group_id      TEXT    NOT NULL,
    test_id       TEXT    NOT NULL UNIQUE,
    cement_type   TEXT    NOT NULL,
    WC_ratio      REAL    NOT NULL,
    dosage_kgm3   REAL    NOT NULL,
    qu_R7_kPa     REAL    NOT NULL,
    E50_R7_MPa    REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bh_zone    ON boreholes(zone_id);
CREATE INDEX IF NOT EXISTS idx_lay_bh     ON layers(borehole_id);
CREATE INDEX IF NOT EXISTS idx_spt_bh     ON spt_values(borehole_id);
CREATE INDEX IF NOT EXISTS idx_vst_zone   ON vst_locations(zone_id);
CREATE INDEX IF NOT EXISTS idx_vs_vst     ON vane_shear_tests(vst_loc_id);
CREATE INDEX IF NOT EXISTS idx_lab_bh     ON lab_tests(borehole_id);
CREATE INDEX IF NOT EXISTS idx_cdm_bh     ON cdm_tests(borehole_id);
"""


# ── helpers ───────────────────────────────────────────────────────────────────
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _zone_id(conn: sqlite3.Connection, code: str) -> int:
    return conn.execute("SELECT id FROM zones WHERE code=?", (code,)).fetchone()["id"]


def _bh_id(conn: sqlite3.Connection, name: str) -> int | None:
    row = conn.execute("SELECT id FROM boreholes WHERE name=?", (name,)).fetchone()
    return row["id"] if row else None


def _upsert_bh(conn: sqlite3.Connection, zone_id: int, name: str,
               name_raw: str = None, elevation_m=None, depth_m=None,
               date: str = None, x=None, y=None, notes: str = None) -> int:
    existing = _bh_id(conn, name)
    if existing:
        return existing
    cur = conn.execute(
        "INSERT INTO boreholes(zone_id,name,name_raw,elevation_m,depth_m,date,x_coord_m,y_coord_m,notes) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (zone_id, name, name_raw, elevation_m, depth_m, date, x, y, notes)
    )
    return cur.lastrowid


def _ke_name(raw: str) -> str:
    """'3BOKECONGVIEN-HK3' → 'KE-HK3'"""
    return raw.replace("3BOKECONGVIEN-", "KE-")


# ── zones seed ────────────────────────────────────────────────────────────────
def seed_zones(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO zones(id,code,name_vi,notes) VALUES(?,?,?,?)",
        [
            (1, "KE",  "Kè Công Viên",    "12 hố khoan tuyến kè"),
            (2, "BXN", "Bãi Đỗ Xe Ngầm", "17 hố khoan (CV-HK1–HK17)"),
            (3, "NHC", "Nhà Hành Chính",  "BH-01…BH-44 (10 HK có KQTN)"),
        ]
    )
    conn.commit()


# ── KE zone ───────────────────────────────────────────────────────────────────
def import_ke_boreholes(conn: sqlite3.Connection) -> None:
    with open(KE_PROFILE_JSON, encoding="utf-8") as f:
        data = json.load(f)
    zone_id = _zone_id(conn, "KE")
    conn.execute("DELETE FROM layers WHERE borehole_id IN (SELECT id FROM boreholes WHERE zone_id=?)", (zone_id,))
    conn.execute("DELETE FROM boreholes WHERE zone_id=?", (zone_id,))
    count_bh = count_lay = 0
    for bh in data["boreholes"]:
        name = _ke_name(bh["name"])
        bh_id = _upsert_bh(
            conn, zone_id, name,
            name_raw=bh["name"],
            elevation_m=bh.get("elevation_m"),
            depth_m=bh.get("depth_m"),
            date=bh.get("date"),
            x=bh.get("x_coord_m"),
            y=bh.get("y_coord_m"),
        )
        count_bh += 1
        depth_top = 0.0
        for lay in bh.get("layers", []):
            thick = lay.get("thickness_m", 0)
            conn.execute(
                "INSERT INTO layers(borehole_id,symbol,description,depth_top_m,depth_bot_m,thickness_m) "
                "VALUES(?,?,?,?,?,?)",
                (bh_id, lay["symbol"], lay.get("description"), depth_top,
                 depth_top + thick, thick)
            )
            depth_top += thick
            count_lay += 1
    conn.commit()
    print(f"KE boreholes: {count_bh}  layers: {count_lay}")


def import_ke_vane_shear(conn: sqlite3.Connection) -> None:
    with open(KE_VS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    zone_id = _zone_id(conn, "KE")
    conn.execute("DELETE FROM vane_shear_tests WHERE vst_loc_id IN "
                 "(SELECT id FROM vst_locations WHERE zone_id=?)", (zone_id,))
    conn.execute("DELETE FROM vst_locations WHERE zone_id=?", (zone_id,))
    count_loc = count_t = 0
    for bh in data["boreholes"]:
        vst_name = _ke_name(bh["borehole"])
        cur = conn.execute(
            "INSERT INTO vst_locations(zone_id,name,date,Z_ground_m,vane_D_cm,vane_H_cm,K_m3) "
            "VALUES(?,?,?,?,?,?,?)",
            (zone_id, vst_name, bh.get("date"),
             bh.get("Z_ground_vane_m") or bh.get("Z_ground_json_m"),
             bh.get("vane_D_cm"), bh.get("vane_H_cm"), bh.get("K_m3"))
        )
        vst_id = cur.lastrowid
        count_loc += 1
        for t in bh.get("tests", []):
            conn.execute(
                "INSERT INTO vane_shear_tests(vst_loc_id,depth_m,elev_m,Su_kPa,Sp_kPa,St,note) "
                "VALUES(?,?,?,?,?,?,?)",
                (vst_id, t["depth_m"], t.get("elev_m"),
                 t["Su_kPa"], t.get("Sp_kPa"), t.get("St"), t.get("note"))
            )
            count_t += 1
    conn.commit()
    print(f"KE vane shear: {count_loc} vị trí  {count_t} điểm")


def import_ke_lab(conn: sqlite3.Connection) -> None:
    with open(KE_LAB_JSON, encoding="utf-8") as f:
        data = json.load(f)
    zone_id = _zone_id(conn, "KE")
    conn.execute("DELETE FROM lab_tests WHERE borehole_id IN "
                 "(SELECT id FROM boreholes WHERE zone_id=?)", (zone_id,))
    count = 0
    for bh in data["boreholes"]:
        name = _ke_name(bh["borehole"])
        bh_id = _upsert_bh(conn, zone_id, name, name_raw=bh["borehole"])
        for s in bh.get("samples", []):
            gw = s.get("gamma_gcm3")
            gd = s.get("gamma_dry_gcm3")
            c_raw = s.get("c_kgcm2")
            E_raw = s.get("E_kgcm2")
            a12_raw = s.get("a12_cm2kg")
            conn.execute(
                "INSERT INTO lab_tests(borehole_id,sample_id,depth_from_m,depth_to_m,"
                "w_pct,gamma_kNm3,gamma_dry_kNm3,Gs,Sr_pct,n_pct,e0,"
                "wL_pct,wP_pct,Ip,IS_liq,phi_deg,c_kPa,a12_cm2kgf,E_kPa,Cc,Cs,"
                "symbol_tcvn,description_vi) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bh_id, s.get("sample_id"), s.get("depth_from_m"), s.get("depth_to_m"),
                 s.get("w_pct"),
                 round(gw * 9.81, 3) if gw else None,
                 round(gd * 9.81, 3) if gd else None,
                 s.get("Gs"), s.get("Sr_pct"), s.get("n_pct"), s.get("e0"),
                 s.get("wL_pct"), s.get("wP_pct"), s.get("Ip"),
                 s.get("IS"),
                 s.get("phi_deg"),
                 round(c_raw * 98.0665, 3) if c_raw else None,
                 a12_raw,
                 round(E_raw * 98.0665, 1) if E_raw else None,
                 s.get("Cc"), s.get("Cs"),
                 s.get("symbol_tcvn"), s.get("description_vi"))
            )
            count += 1
    conn.commit()
    print(f"KE lab_tests: {count} mẫu")


def import_ke_cdm(conn: sqlite3.Connection) -> None:
    with open(KE_CDM_JSON, encoding="utf-8") as f:
        data = json.load(f)
    zone_id = _zone_id(conn, "KE")
    conn.execute("DELETE FROM cdm_tests WHERE borehole_id IN "
                 "(SELECT id FROM boreholes WHERE zone_id=?)", (zone_id,))
    bh_name = _ke_name(data["borehole"])
    bh_id = _upsert_bh(conn, zone_id, bh_name, name_raw=data["borehole"])
    count = 0
    for grp in data["test_groups"]:
        for t in grp["tests"]:
            conn.execute(
                "INSERT OR IGNORE INTO cdm_tests(borehole_id,group_id,test_id,cement_type,"
                "WC_ratio,dosage_kgm3,qu_R7_kPa,E50_R7_MPa) VALUES(?,?,?,?,?,?,?,?)",
                (bh_id, grp["group_id"], t["test_id"], grp["cement_type"],
                 grp["WC_ratio"], t["dosage_kgm3"], t["qu_R7_kPa"], t["E50_R7_MPa"])
            )
            count += 1
    conn.commit()
    print(f"KE cdm_tests: {count} tổ hợp")


# ── BXN zone ──────────────────────────────────────────────────────────────────
def import_bxn_boreholes(conn: sqlite3.Connection) -> None:
    with open(BXN_BH_JSON, encoding="utf-8") as f:
        data = json.load(f)
    zone_id = _zone_id(conn, "BXN")
    conn.execute("DELETE FROM spt_values WHERE borehole_id IN (SELECT id FROM boreholes WHERE zone_id=?)", (zone_id,))
    conn.execute("DELETE FROM layers WHERE borehole_id IN (SELECT id FROM boreholes WHERE zone_id=?)", (zone_id,))
    count_bh = count_lay = count_spt = 0
    for bh in data["boreholes"]:
        name = bh["name"]          # 'BXN-CV-HK1'
        raw  = bh["name_raw"]      # 'CV-HK1'
        bh_id = _bh_id(conn, name)
        if bh_id:
            conn.execute(
                "UPDATE boreholes SET name_raw=?,elevation_m=?,depth_m=?,date=?,"
                "x_coord_m=?,y_coord_m=? WHERE id=?",
                (raw, bh.get("elevation_m"), bh.get("depth_m"), bh.get("date"),
                 bh.get("x_coord_m"), bh.get("y_coord_m"), bh_id)
            )
        else:
            bh_id = _upsert_bh(
                conn, zone_id, name, name_raw=raw,
                elevation_m=bh.get("elevation_m"), depth_m=bh.get("depth_m"),
                date=bh.get("date"), x=bh.get("x_coord_m"), y=bh.get("y_coord_m"),
            )
        count_bh += 1
        for lay in bh.get("layers", []):
            thick = round(lay["depth_bot_m"] - lay["depth_top_m"], 3)
            conn.execute(
                "INSERT INTO layers(borehole_id,symbol,description,depth_top_m,depth_bot_m,thickness_m) "
                "VALUES(?,?,?,?,?,?)",
                (bh_id, lay["symbol"], lay.get("description"),
                 lay["depth_top_m"], lay["depth_bot_m"], thick)
            )
            count_lay += 1
        elev0 = bh.get("elevation_m")
        for s in bh.get("spt", []):
            elev = round(elev0 - s["depth_m"], 3) if elev0 is not None else None
            conn.execute(
                "INSERT INTO spt_values(borehole_id,depth_m,elev_m,N1,N2,N3,N) VALUES(?,?,?,?,?,?,?)",
                (bh_id, s["depth_m"], elev, s.get("N1"), s.get("N2"), s.get("N3"), s.get("N"))
            )
            count_spt += 1
    conn.commit()
    print(f"BXN boreholes: {count_bh}  layers: {count_lay}  SPT: {count_spt}")


def import_bxn_vane_shear(conn: sqlite3.Connection) -> None:
    with open(BXN_VS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    zone_id = _zone_id(conn, "BXN")
    conn.execute("DELETE FROM vane_shear_tests WHERE vst_loc_id IN "
                 "(SELECT id FROM vst_locations WHERE zone_id=?)", (zone_id,))
    conn.execute("DELETE FROM vst_locations WHERE zone_id=?", (zone_id,))
    count_loc = count_t = 0
    for loc in data["locations"]:
        cur = conn.execute(
            "INSERT INTO vst_locations(zone_id,name,date,Z_ground_m,vane_D_cm,vane_H_cm,K_m3,"
            "x_coord_m,y_coord_m) VALUES(?,?,?,?,?,?,?,?,?)",
            (zone_id, loc["name"], loc.get("date"), loc.get("Z_ground_m"),
             loc.get("vane_D_cm"), loc.get("vane_H_cm"), loc.get("K_m3"),
             loc.get("x_coord_m"), loc.get("y_coord_m"))
        )
        vst_id = cur.lastrowid
        count_loc += 1
        for t in loc.get("tests", []):
            conn.execute(
                "INSERT INTO vane_shear_tests(vst_loc_id,depth_m,elev_m,Su_kPa,Sp_kPa,St,note) "
                "VALUES(?,?,?,?,?,?,?)",
                (vst_id, t["depth_m"], t.get("elev_m"),
                 t["Su_kPa"], t.get("Sp_kPa"), t.get("St"), t.get("note"))
            )
            count_t += 1
    conn.commit()
    print(f"BXN vane shear: {count_loc} vị trí  {count_t} điểm")


def import_bxn_lab(conn: sqlite3.Connection) -> None:
    with open(BXN_LAB_JSON, encoding="utf-8") as f:
        data = json.load(f)
    zone_id = _zone_id(conn, "BXN")
    conn.execute("DELETE FROM lab_tests WHERE borehole_id IN "
                 "(SELECT id FROM boreholes WHERE zone_id=?)", (zone_id,))
    count = 0
    for bh in data["boreholes"]:
        raw_name = bh["borehole"]                 # 'CV-HK2'
        bh_name  = "BXN-" + raw_name              # 'BXN-CV-HK2'
        bh_id = _upsert_bh(conn, zone_id, bh_name, name_raw=raw_name)
        for s in bh.get("samples", []):
            conn.execute(
                "INSERT INTO lab_tests(borehole_id,sample_id,depth_from_m,depth_to_m,"
                "w_pct,gamma_kNm3,gamma_dry_kNm3,Gs,Sr_pct,n_pct,e0,"
                "wL_pct,wP_pct,Ip,IS_liq,phi_deg,c_kPa,a12_cm2kgf,E_kPa,Cc,Cs,"
                "Cu_UU_kPa,phi_UU_deg,symbol_tcvn,description_vi) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bh_id, s.get("sample_id"), s.get("depth_from_m"), s.get("depth_to_m"),
                 s.get("w_pct"), s.get("gamma_kNm3"), s.get("gamma_dry_kNm3"),
                 s.get("Gs"), s.get("Sr_pct"), s.get("n_pct"), s.get("e0"),
                 s.get("wL_pct"), s.get("wP_pct"), s.get("Ip"), s.get("IS_liq"),
                 s.get("phi_deg"), s.get("c_kPa"),
                 s.get("a12_kPa_inv_e2"),   # stored as a(100-200) ×10⁻² kPa⁻¹
                 s.get("E_kPa"),
                 s.get("Cc"), s.get("Cs"),
                 s.get("Cu_UU_kPa"), s.get("phi_UU_deg"),
                 s.get("symbol_tcvn"), s.get("description_vi"))
            )
            count += 1
    conn.commit()
    print(f"BXN lab_tests: {count} mẫu")


# ── NHC zone ──────────────────────────────────────────────────────────────────
def import_nhc_vane_shear(conn: sqlite3.Connection) -> None:
    with open(NHC_VS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    zone_id = _zone_id(conn, "NHC")
    conn.execute("DELETE FROM vane_shear_tests WHERE vst_loc_id IN "
                 "(SELECT id FROM vst_locations WHERE zone_id=?)", (zone_id,))
    conn.execute("DELETE FROM vst_locations WHERE zone_id=?", (zone_id,))
    count_loc = count_t = 0
    for loc in data["locations"]:
        cur = conn.execute(
            "INSERT INTO vst_locations(zone_id,name,date,Z_ground_m,vane_D_cm,vane_H_cm,K_m3,"
            "x_coord_m,y_coord_m) VALUES(?,?,?,?,?,?,?,?,?)",
            (zone_id, loc["name"], loc.get("date"), loc.get("Z_ground_m"),
             loc.get("vane_D_cm"), loc.get("vane_H_cm"), loc.get("K_m3"),
             loc.get("x_coord_m"), loc.get("y_coord_m"))
        )
        vst_id = cur.lastrowid
        count_loc += 1
        for t in loc.get("tests", []):
            conn.execute(
                "INSERT INTO vane_shear_tests(vst_loc_id,depth_m,elev_m,Su_kPa,Sp_kPa,St,note) "
                "VALUES(?,?,?,?,?,?,?)",
                (vst_id, t["depth_m"], t.get("elev_m"),
                 t["Su_kPa"], t.get("Sp_kPa"), t.get("St"), t.get("note"))
            )
            count_t += 1
    conn.commit()
    print(f"NHC vane shear: {count_loc} vị trí  {count_t} điểm")


def import_nhc_lab(conn: sqlite3.Connection) -> None:
    with open(NHC_LAB_JSON, encoding="utf-8") as f:
        data = json.load(f)
    zone_id = _zone_id(conn, "NHC")
    conn.execute("DELETE FROM lab_tests WHERE borehole_id IN "
                 "(SELECT id FROM boreholes WHERE zone_id=?)", (zone_id,))
    count = 0
    for bh in data["boreholes"]:
        raw_name = bh["borehole"]            # 'BH-01'
        bh_name  = "NHC-" + raw_name         # 'NHC-BH-01'
        bh_id = _upsert_bh(conn, zone_id, bh_name, name_raw=raw_name)
        for s in bh.get("samples", []):
            conn.execute(
                "INSERT INTO lab_tests(borehole_id,sample_id,depth_from_m,depth_to_m,"
                "w_pct,gamma_kNm3,gamma_dry_kNm3,Gs,Sr_pct,n_pct,e0,"
                "wL_pct,wP_pct,Ip,IS_liq,phi_deg,c_kPa,a12_cm2kgf,symbol_tcvn,description_vi) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bh_id, s.get("sample_id"), s.get("depth_from_m"), s.get("depth_to_m"),
                 s.get("w_pct"), s.get("gamma_kNm3"), s.get("gamma_dry_kNm3"),
                 s.get("Gs"), s.get("Sr_pct"), s.get("n_pct"), s.get("e0"),
                 s.get("wL_pct"), s.get("wP_pct"), s.get("Ip"), s.get("IS_liq"),
                 s.get("phi_deg"), s.get("c_kPa"),
                 s.get("a12_cm2kgf"),
                 s.get("symbol_tcvn"), s.get("description_vi"))
            )
            count += 1
    conn.commit()
    print(f"NHC lab_tests: {count} mẫu")


# ── demo query ────────────────────────────────────────────────────────────────
def demo_query(conn: sqlite3.Connection) -> None:
    print("\n=== Tổng quan 3 khu vực ===")
    rows = conn.execute(
        """SELECT z.code, z.name_vi,
                  COUNT(DISTINCT b.id) n_bh,
                  COUNT(DISTINCT v.id) n_vst,
                  COUNT(DISTINCT lt.id) n_lab,
                  COUNT(DISTINCT vs.id) n_vs
           FROM zones z
           LEFT JOIN boreholes b      ON b.zone_id = z.id
           LEFT JOIN vst_locations v  ON v.zone_id = z.id
           LEFT JOIN lab_tests lt     ON lt.borehole_id = b.id
           LEFT JOIN vane_shear_tests vs ON vs.vst_loc_id = v.id
           GROUP BY z.id ORDER BY z.id"""
    ).fetchall()
    print(f"  {'Zone':<5} {'Khu vực':<22} {'HK':>4} {'VST':>5} {'Lab':>6} {'VS điểm':>8}")
    for r in rows:
        print(f"  {r['code']:<5} {r['name_vi']:<22} {r['n_bh']:>4} {r['n_vst']:>5} {r['n_lab']:>6} {r['n_vs']:>8}")

    print("\n=== Su trung bình theo khu vực (lớp nông ≤15m) ===")
    rows = conn.execute(
        """SELECT z.code, COUNT(*) n, ROUND(AVG(vs.Su_kPa),1) avg_Su,
                  ROUND(MIN(vs.Su_kPa),1) min_Su, ROUND(MAX(vs.Su_kPa),1) max_Su
           FROM vane_shear_tests vs
           JOIN vst_locations vl ON vl.id = vs.vst_loc_id
           JOIN zones z ON z.id = vl.zone_id
           WHERE vs.depth_m <= 15
           GROUP BY z.code ORDER BY z.id"""
    ).fetchall()
    for r in rows:
        print(f"  [{r['code']}] n={r['n']:>3}  Su avg={r['avg_Su']:>5.1f}  "
              f"min={r['min_Su']:>5.1f}  max={r['max_Su']:>5.1f}  kPa")

    print("\n=== Lab — chỉ tiêu lớp mềm (symbol CH/MH-OH) trung bình ===")
    rows = conn.execute(
        """SELECT z.code, COUNT(*) n,
                  ROUND(AVG(l.w_pct),1) w,
                  ROUND(AVG(l.e0),3) e0,
                  ROUND(AVG(l.phi_deg),2) phi,
                  ROUND(AVG(l.c_kPa),2) c
           FROM lab_tests l
           JOIN boreholes b ON b.id = l.borehole_id
           JOIN zones z ON z.id = b.zone_id
           WHERE l.symbol_tcvn IN ('CH','MH','MH-OH','CH-OH')
             AND l.phi_deg IS NOT NULL
           GROUP BY z.code ORDER BY z.id"""
    ).fetchall()
    print(f"  {'Zone':<6} {'n':>4} {'w%':>7} {'e0':>7} {'phi°':>7} {'c kPa':>8}")
    for r in rows:
        print(f"  {r['code']:<6} {r['n']:>4} {r['w'] or 0:>7.1f} {r['e0'] or 0:>7.3f} "
              f"{r['phi'] or 0:>7.2f} {r['c'] or 0:>8.2f}")


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    reset = "--reset" in sys.argv
    query_only = "--query" in sys.argv

    if reset and DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Reset: đã xóa {DB_PATH.name}")

    conn = _connect()
    conn.executescript(DDL)

    if not query_only:
        print("Nạp dữ liệu...")
        seed_zones(conn)
        import_ke_boreholes(conn)
        import_ke_vane_shear(conn)
        import_ke_lab(conn)
        import_ke_cdm(conn)
        import_bxn_vane_shear(conn)
        import_bxn_lab(conn)
        import_bxn_boreholes(conn)
        import_nhc_vane_shear(conn)
        import_nhc_lab(conn)
        print("Hoàn thành.")

    demo_query(conn)
    conn.close()
