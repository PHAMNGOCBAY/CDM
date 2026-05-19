"""lab_data_db.py — Nạp dữ liệu thí nghiệm vào soil_profile_TTHC.sqlite.

Thêm 3 bảng:
  vane_shear_tests  — cắt cánh (BOKE-004): Su, S'u, St theo chiều sâu
  cdm_tests         — nén một trục CDM (BOKE-005): qu, E50 theo tổ hợp xi măng
  lab_tests         — thí nghiệm đất tổng hợp (BOKE-003): w, γ, Atterberg, cắt, nén lún

Usage:
  python scripts/lab_data_db.py          # nạp/cập nhật toàn bộ
  python scripts/lab_data_db.py --query  # demo query
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH   = ROOT / "data" / "soil_profile_TTHC.sqlite"
VS_JSON   = ROOT / "data" / "vane_shear_202605_TTHC.json"
CDM_JSON  = ROOT / "data" / "cdm_tests_202605_TTHC.json"
LAB_JSON  = ROOT / "data" / "lab_tests_202605_TTHC.json"

DDL_EXT = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vane_shear_tests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    borehole_id   INTEGER NOT NULL REFERENCES boreholes(id) ON DELETE CASCADE,
    depth_m       REAL    NOT NULL,
    elev_m        REAL,
    Su_kPa        REAL    NOT NULL,
    Sp_kPa        REAL,
    St            REAL,
    note          TEXT
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

CREATE TABLE IF NOT EXISTS lab_tests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    borehole_id   INTEGER NOT NULL REFERENCES boreholes(id) ON DELETE CASCADE,
    sample_id     TEXT    NOT NULL,
    depth_from_m  REAL    NOT NULL,
    depth_to_m    REAL    NOT NULL,
    w_pct         REAL,
    gamma_gcm3    REAL,
    gamma_dry_gcm3 REAL,
    Gs            REAL,
    e0            REAL,
    n_pct         REAL,
    Sr_pct        REAL,
    wL_pct        REAL,
    wP_pct        REAL,
    Ip            REAL,
    IS_liq        REAL,
    c_kgcm2       REAL,
    phi_deg       REAL,
    a12_cm2kg     REAL,
    E_kgcm2       REAL,
    Cc            REAL,
    Cs            REAL,
    symbol_tcvn   TEXT,
    description_vi TEXT
);

CREATE INDEX IF NOT EXISTS idx_vs_borehole ON vane_shear_tests(borehole_id);
CREATE INDEX IF NOT EXISTS idx_cdm_borehole ON cdm_tests(borehole_id);
CREATE INDEX IF NOT EXISTS idx_lab_borehole ON lab_tests(borehole_id);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("PRAGMA foreign_keys = ON;")
    return conn


def _bh_id(conn: sqlite3.Connection, name: str) -> int | None:
    row = conn.execute("SELECT id FROM boreholes WHERE name = ?", (name,)).fetchone()
    return row["id"] if row else None


def populate_vane_shear(conn: sqlite3.Connection) -> None:
    with open(VS_JSON, encoding="utf-8") as f:
        data = json.load(f)

    cur = conn.cursor()
    cur.execute("DELETE FROM vane_shear_tests")
    count = 0
    for bh in data["boreholes"]:
        bh_id = _bh_id(conn, bh["borehole"])
        if bh_id is None:
            print(f"  [WARN] {bh['borehole']} không có trong bảng boreholes — bỏ qua")
            continue
        for t in bh["tests"]:
            cur.execute(
                """INSERT INTO vane_shear_tests
                   (borehole_id, depth_m, elev_m, Su_kPa, Sp_kPa, St, note)
                   VALUES (?,?,?,?,?,?,?)""",
                (bh_id, t["depth_m"], t.get("elev_m"), t["Su_kPa"],
                 t.get("Sp_kPa"), t.get("St"), t.get("note")),
            )
            count += 1
    conn.commit()
    print(f"vane_shear_tests: {count} điểm")


def populate_cdm(conn: sqlite3.Connection) -> None:
    with open(CDM_JSON, encoding="utf-8") as f:
        data = json.load(f)

    cur = conn.cursor()
    cur.execute("DELETE FROM cdm_tests")
    bh_id = _bh_id(conn, data["borehole"])
    if bh_id is None:
        print(f"  [WARN] {data['borehole']} không tồn tại — bỏ qua CDM")
        return
    count = 0
    for grp in data["test_groups"]:
        for t in grp["tests"]:
            cur.execute(
                """INSERT INTO cdm_tests
                   (borehole_id, group_id, test_id, cement_type, WC_ratio,
                    dosage_kgm3, qu_R7_kPa, E50_R7_MPa)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (bh_id, grp["group_id"], t["test_id"], grp["cement_type"],
                 grp["WC_ratio"], t["dosage_kgm3"], t["qu_R7_kPa"], t["E50_R7_MPa"]),
            )
            count += 1
    conn.commit()
    print(f"cdm_tests: {count} tổ hợp")


def populate_lab(conn: sqlite3.Connection) -> None:
    with open(LAB_JSON, encoding="utf-8") as f:
        data = json.load(f)

    cur = conn.cursor()
    cur.execute("DELETE FROM lab_tests")
    count = 0
    for bh in data["boreholes"]:
        bh_id = _bh_id(conn, bh["borehole"])
        if bh_id is None:
            print(f"  [WARN] {bh['borehole']} không có trong boreholes — bỏ qua")
            continue
        for s in bh["samples"]:
            cur.execute(
                """INSERT INTO lab_tests
                   (borehole_id, sample_id, depth_from_m, depth_to_m,
                    w_pct, gamma_gcm3, gamma_dry_gcm3, Gs, e0, n_pct, Sr_pct,
                    wL_pct, wP_pct, Ip, IS_liq, c_kgcm2, phi_deg,
                    a12_cm2kg, E_kgcm2, Cc, Cs, symbol_tcvn, description_vi)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (bh_id, s["sample_id"], s["depth_from_m"], s["depth_to_m"],
                 s.get("w_pct"), s.get("gamma_gcm3"), s.get("gamma_dry_gcm3"),
                 s.get("Gs"), s.get("e0"), s.get("n_pct"), s.get("Sr_pct"),
                 s.get("wL_pct"), s.get("wP_pct"), s.get("Ip"), s.get("IS"),  # IS -> IS_liq col
                 s.get("c_kgcm2"), s.get("phi_deg"),
                 s.get("a12_cm2kg"), s.get("E_kgcm2"), s.get("Cc"), s.get("Cs"),
                 s.get("symbol_tcvn"), s.get("description_vi")),
            )
            count += 1
    conn.commit()
    print(f"lab_tests: {count} mẫu")


def _demo_query(conn: sqlite3.Connection) -> None:
    print("\n=== Su tuyến kè (HK2, HK7-HK11) theo chiều sâu ===")
    rows = conn.execute(
        """SELECT b.name, v.depth_m, v.Su_kPa, v.St
           FROM vane_shear_tests v JOIN boreholes b ON b.id = v.borehole_id
           WHERE b.on_ke_alignment = 1
           ORDER BY b.id, v.depth_m"""
    ).fetchall()
    for r in rows:
        print(f"  {r['name']:<25} {r['depth_m']:5.1f}m  Su={r['Su_kPa']:5.1f} kPa  St={r['St']}")

    print("\n=== CDM HK12 — tổng hợp qu_R7 ===")
    rows = conn.execute(
        """SELECT test_id, cement_type, dosage_kgm3, WC_ratio, qu_R7_kPa, E50_R7_MPa
           FROM cdm_tests ORDER BY qu_R7_kPa"""
    ).fetchall()
    for r in rows:
        print(f"  {r['test_id']:5s} {r['cement_type']:22s} {r['dosage_kgm3']:3.0f}kg N/X={r['WC_ratio']}  "
              f"qu={r['qu_R7_kPa']:6.1f}kPa  E50={r['E50_R7_MPa']:5.1f}MPa")

    print("\n=== Lớp L1 — thông số đất trung bình (lab_tests) ===")
    rows = conn.execute(
        """SELECT b.name, COUNT(*) n, AVG(w_pct) w, AVG(gamma_gcm3) gam,
                  AVG(wL_pct) wL, AVG(Ip) Ip,
                  AVG(c_kgcm2)*98.07 c_kPa, AVG(phi_deg) phi
           FROM lab_tests l JOIN boreholes b ON b.id = l.borehole_id
           WHERE l.symbol_tcvn IN ('CH','CH-MH')
           GROUP BY b.id ORDER BY b.id"""
    ).fetchall()
    print(f"  {'HK':<25} {'n':>3} {'w%':>6} {'γ':>6} {'wL':>5} {'Ip':>5} {'c(kPa)':>8} {'φ°':>5}")
    for r in rows:
        print(f"  {r['name']:<25} {r['n']:>3} {r['w'] or 0:>6.1f} {r['gam'] or 0:>6.3f} "
              f"{r['wL'] or 0:>5.1f} {r['Ip'] or 0:>5.1f} {r['c_kPa'] or 0:>8.1f} {r['phi'] or 0:>5.1f}")


if __name__ == "__main__":
    import sys
    conn = _connect()
    conn.executescript(DDL_EXT)

    if "--query" in sys.argv:
        _demo_query(conn)
    else:
        populate_vane_shear(conn)
        populate_cdm(conn)
        populate_lab(conn)
        _demo_query(conn)

    conn.close()
