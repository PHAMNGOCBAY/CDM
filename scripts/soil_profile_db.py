"""soil_profile_db.py — SQLite library cho địa tầng dự án TTHC.

Schema:
  meta             — thông tin dự án (key/value)
  boreholes        — 12 hố khoan (3BOKECONGVIEN-HK1 … 3BOKECONGVIEN-HK12)
  layers           — lớp đất mỗi hố, có top_elev_m / bottom_elev_m tính sẵn
  design_principles — quy tắc thiết kế (Đỉnh L1, XMD=L1, ...)

Usage:
  python scripts/soil_profile_db.py          # tạo/cập nhật DB từ JSON
  python scripts/soil_profile_db.py --query  # demo query
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
DB_PATH   = ROOT / "data" / "soil_profile_TTHC.sqlite"
JSON_PATH = ROOT / "data" / "soil_profile_202605_TTHC.json"

# Boreholes nằm trên tuyến kè đứng (có tọa độ VN2000)
KE_ALIGNMENT = {
    "3BOKECONGVIEN-HK2", "3BOKECONGVIEN-HK3", "3BOKECONGVIEN-HK7",
    "3BOKECONGVIEN-HK8", "3BOKECONGVIEN-HK9", "3BOKECONGVIEN-HK10",
    "3BOKECONGVIEN-HK11",
}


# ── DDL ───────────────────────────────────────────────────────────────────────

DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS boreholes (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    name                      TEXT    NOT NULL UNIQUE,
    elevation_m               REAL    NOT NULL,
    depth_m                   REAL    NOT NULL,
    date                      TEXT,
    x_coord_m                 REAL,
    y_coord_m                 REAL,
    on_ke_alignment           INTEGER NOT NULL DEFAULT 0,   -- 1 nếu thuộc tuyến kè đứng
    note                      TEXT,
    l1_effective_thickness_m  REAL,   -- NULL nếu không có XMD trong vùng L1
    l1_effective_bottom_m     REAL    -- NULL nếu không có XMD trong vùng L1
);

CREATE TABLE IF NOT EXISTS layers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    borehole_id   INTEGER NOT NULL REFERENCES boreholes(id) ON DELETE CASCADE,
    layer_order   INTEGER NOT NULL,   -- 1-based, thứ tự từ trên xuống
    symbol        TEXT    NOT NULL,
    description   TEXT,
    thickness_m   REAL    NOT NULL,
    top_elev_m    REAL    NOT NULL,   -- cao độ đỉnh lớp
    bottom_elev_m REAL    NOT NULL,   -- cao độ đáy lớp
    is_xmd        INTEGER NOT NULL DEFAULT 0,  -- 1 nếu là lớp xi măng đất
    is_l1_zone    INTEGER NOT NULL DEFAULT 0   -- 1 nếu thuộc vùng L1 hiệu dụng
);

CREATE TABLE IF NOT EXISTS design_principles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    rule_text   TEXT NOT NULL,
    applies_to  TEXT NOT NULL DEFAULT 'all',  -- 'all' hoặc tên HK
    updated     TEXT
);

CREATE INDEX IF NOT EXISTS idx_layers_borehole ON layers(borehole_id);
CREATE INDEX IF NOT EXISTS idx_layers_symbol   ON layers(symbol);
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("PRAGMA foreign_keys = ON;")
    return conn


def _is_l1_zone(symbol: str, borehole_name: str, layer_order: int,
                hk_data: dict) -> int:
    """Trả 1 nếu lớp thuộc vùng L1 hiệu dụng.

    Quy tắc: symbol=='1' luôn là L1. Với HK8, XMD giữa hai lớp L1 cũng là L1.
    Cụ thể HK8: lớp 2(L1), lớp 3(XMD), lớp 4(L1-dưới-XMD) đều = 1.
    """
    if symbol == "1":
        return 1
    if borehole_name == "HK8" and symbol == "XMD":
        # XMD tại HK8 nằm trong vùng L1 hiệu dụng
        return 1
    return 0


# ── Populate ──────────────────────────────────────────────────────────────────

def populate_from_json(conn: sqlite3.Connection, data: dict) -> None:
    """Xóa và nạp lại toàn bộ dữ liệu từ dict JSON."""
    cur = conn.cursor()

    # meta
    cur.execute("DELETE FROM meta")
    m = data["_meta"]
    rows_meta = [
        ("project",       m.get("project", "")),
        ("source",        m.get("source", "")),
        ("source_drive_id", m.get("source_drive_id", "")),
        ("updated",       m.get("updated", "")),
        ("boreholes_count", str(m.get("boreholes", ""))),
        ("layer_symbols", json.dumps(m.get("layer_symbols", []), ensure_ascii=False)),
        ("notes",         m.get("notes", "")),
    ]
    cur.executemany("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", rows_meta)

    # boreholes + layers
    cur.execute("DELETE FROM layers")
    cur.execute("DELETE FROM boreholes")

    for bh in data["boreholes"]:
        name = bh["name"]
        cur.execute(
            """INSERT INTO boreholes
               (name, elevation_m, depth_m, date, x_coord_m, y_coord_m,
                on_ke_alignment, note, l1_effective_thickness_m, l1_effective_bottom_m)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                name,
                bh["elevation_m"],
                bh["depth_m"],
                bh.get("date"),
                bh.get("x_coord_m"),
                bh.get("y_coord_m"),
                1 if name in KE_ALIGNMENT else 0,
                bh.get("note"),
                bh.get("l1_effective_thickness_m"),
                bh.get("l1_effective_bottom_m"),
            ),
        )
        bh_id = cur.lastrowid
        elev = bh["elevation_m"]

        for order, lyr in enumerate(bh.get("layers", []), start=1):
            sym        = lyr["symbol"]
            thick      = lyr["thickness_m"]
            top_e      = round(elev - (sum(l["thickness_m"] for l in bh["layers"][:order-1])), 4)
            bot_e      = round(top_e - thick, 4)
            # Ưu tiên bottom_elev_m từ JSON nếu có (xác minh từ PDF)
            if "bottom_elev_m" in lyr:
                bot_e = lyr["bottom_elev_m"]

            cur.execute(
                """INSERT INTO layers
                   (borehole_id, layer_order, symbol, description,
                    thickness_m, top_elev_m, bottom_elev_m, is_xmd, is_l1_zone)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    bh_id, order, sym,
                    lyr.get("description", ""),
                    thick, top_e, bot_e,
                    1 if sym == "XMD" else 0,
                    _is_l1_zone(sym, name, order, bh),
                ),
            )

    # design_principles
    cur.execute("DELETE FROM design_principles")
    principles = [
        (
            "Đỉnh L1",
            "Đỉnh L1 = đáy lớp san lấp (F). Nếu hố khoan không có lớp F thì Đỉnh L1 = Z mặt đất.",
            "all",
            "2026-05-18",
        ),
        (
            "XMD tại HK08 là L1",
            "XMD tại HK08 là lớp L1 gốc đã được gia cố CDM. "
            "Khi tính chiều sâu cọc, KHÔNG trừ XMD. "
            "Vùng L1 hiệu dụng = L1(3.80m) + XMD(15.70m) + L1-dưới-XMD(4.60m) = 24.10 m; đáy = −24.42 m.",
            "HK8",
            "2026-05-18",
        ),
        (
            "NT1 — chiều sâu cọc tối thiểu",
            "L_req = H(L1 hiệu dụng) + 3.70 m. Với HK8: L_req = 24.10 + 3.70 = 27.80 m.",
            "all",
            "2026-05-18",
        ),
        (
            "NT2 — TCVN 11823-10:2017 alpha-method",
            "RR = phi_stat × (Rs + Rp) >= W_coc. "
            "Rs = alpha × su × C × L_dat_tu_nhien (bỏ qua đất đắp). "
            "Rp = 9 × su × Ap (Pt. 65). phi_stat = 0.35 (Bảng 9, alpha-method, cọc đóng). "
            "SW-840: Ap=310700 mm², C=4595 mm. SW-940: Ap=354400 mm², C=4984 mm (nội suy).",
            "all",
            "2026-05-18",
        ),
        (
            "XMD tại HK12",
            "XMD tại HK12 (11.00–23.90 m) là vùng xi măng đất nền cũ. "
            "Cần thiết kế cọc riêng cho HK12 — XMD cản trở đóng cọc.",
            "HK12",
            "2026-05-18",
        ),
    ]
    cur.executemany(
        "INSERT INTO design_principles(name, rule_text, applies_to, updated) VALUES(?,?,?,?)",
        principles,
    )

    conn.commit()
    print(f"Đã nạp {len(data['boreholes'])} hố khoan vào {DB_PATH}")


# ── Query helpers (public API) ─────────────────────────────────────────────────

def get_borehole(conn: sqlite3.Connection, name: str) -> dict | None:
    """Lấy metadata hố khoan theo tên."""
    row = conn.execute(
        "SELECT * FROM boreholes WHERE name = ?", (name,)
    ).fetchone()
    return dict(row) if row else None


def get_layers(conn: sqlite3.Connection, borehole_name: str) -> list[dict]:
    """Lấy danh sách lớp đất của một hố khoan."""
    rows = conn.execute(
        """SELECT l.* FROM layers l
           JOIN boreholes b ON b.id = l.borehole_id
           WHERE b.name = ? ORDER BY l.layer_order""",
        (borehole_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_l1_summary(conn: sqlite3.Connection) -> list[dict]:
    """Tổng hợp chiều dày và đáy vùng L1 hiệu dụng cho tất cả hố khoan."""
    rows = conn.execute(
        """SELECT b.name,
                  b.elevation_m,
                  b.on_ke_alignment,
                  COALESCE(b.l1_effective_thickness_m,
                           SUM(CASE WHEN l.is_l1_zone=1 THEN l.thickness_m ELSE 0 END)
                          ) AS l1_thick_m,
                  COALESCE(b.l1_effective_bottom_m,
                           MIN(CASE WHEN l.is_l1_zone=1 THEN l.bottom_elev_m ELSE NULL END)
                          ) AS l1_bottom_m
           FROM boreholes b
           LEFT JOIN layers l ON l.borehole_id = b.id
           GROUP BY b.id
           ORDER BY b.id"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_principle(conn: sqlite3.Connection, name: str) -> str | None:
    """Lấy rule_text theo tên quy tắc."""
    row = conn.execute(
        "SELECT rule_text FROM design_principles WHERE name = ?", (name,)
    ).fetchone()
    return row["rule_text"] if row else None


def ke_alignment_summary(conn: sqlite3.Connection) -> list[dict]:
    """Chỉ lấy 7 hố khoan tuyến kè đứng, đủ thông tin thiết kế."""
    rows = conn.execute(
        """SELECT b.name, b.elevation_m, b.depth_m, b.x_coord_m, b.y_coord_m,
                  COALESCE(b.l1_effective_thickness_m,
                           SUM(CASE WHEN l.is_l1_zone=1 THEN l.thickness_m ELSE 0 END)) AS l1_thick_m,
                  COALESCE(b.l1_effective_bottom_m,
                           MIN(CASE WHEN l.is_l1_zone=1 THEN l.bottom_elev_m ELSE NULL END)) AS l1_bot_m,
                  b.note
           FROM boreholes b
           LEFT JOIN layers l ON l.borehole_id = b.id
           WHERE b.on_ke_alignment = 1
           GROUP BY b.id ORDER BY b.id"""
    ).fetchall()
    return [dict(r) for r in rows]


# ── CLI ───────────────────────────────────────────────────────────────────────

def _demo_query(conn: sqlite3.Connection) -> None:
    print("\n=== Tóm tắt L1 tuyến kè ===")
    print(f"{'HK':<6} {'Z(m)':>6} {'L1(m)':>6} {'Đáy L1(m)':>10}  Tọa độ X / Y")
    print("-" * 65)
    for r in ke_alignment_summary(conn):
        coord = (
            f"{r['x_coord_m']:.3f} / {r['y_coord_m']:.3f}"
            if r["x_coord_m"] else "—"
        )
        note_mark = " *" if r["note"] else ""
        print(
            f"{r['name']:<6} {r['elevation_m']:>+6.2f} {r['l1_thick_m']:>6.1f}"
            f" {r['l1_bot_m']:>10.2f}  {coord}{note_mark}"
        )

    print("\n=== Quy tắc thiết kế ===")
    for row in conn.execute("SELECT name, applies_to FROM design_principles").fetchall():
        print(f"  [{row['applies_to']}] {row['name']}")


if __name__ == "__main__":
    import sys

    conn = _connect()
    conn.executescript(DDL)

    if "--query" in sys.argv:
        _demo_query(conn)
    else:
        with open(JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        conn.executescript(DDL)
        populate_from_json(conn, data)
        _demo_query(conn)

    conn.close()
