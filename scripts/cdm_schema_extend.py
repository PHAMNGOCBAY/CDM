"""cdm_schema_extend.py
Tạo 2 bảng SQLite cho module thi công + thí nghiệm CDM và
pre-populate cdm_thi_cong từ cdm_toado + thông số thiết kế.

Chạy: python -X utf8 scripts/cdm_schema_extend.py
Idempotent — chạy nhiều lần không mất dữ liệu đã có.
"""
import sqlite3, math, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB   = ROOT / "data" / "TTHC.sqlite"

# ── Thông số thiết kế mặc định ─────────────────────────────────────────────
D_CDM       = 0.60   # đường kính cọc (m)
Z_TOP       = 0.80   # cao độ đỉnh cọc thiết kế (m)
PEN_BELOW   = 1.00   # ngàm dưới đáy lớp bùn (m)
XI_MANG_KG_M = 200  # lượng xi măng (kg/m cọc) — điền sau
TY_LE_NC    = 0.55  # w/c ratio mặc định

SOFT_SYM = ("'1'","'1b'","'XMD'","'2'","'2a'","'2b'","'2c'")

# ── DDL ────────────────────────────────────────────────────────────────────────
DDL_THI_CONG = """
CREATE TABLE IF NOT EXISTS cdm_thi_cong (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    toado_id            INTEGER,            -- FK → cdm_toado.id
    zone                TEXT NOT NULL,      -- CONG_VIEN / KE
    point_name          TEXT,
    northing_m          REAL,
    easting_m           REAL,

    -- Hố khoan điều hành + thông số thiết kế
    bh_dieu_hanh        TEXT,               -- tên HK gần nhất
    L_design_m          REAL,
    z_top_design_m      REAL,               -- cao độ đỉnh TK (m)
    z_tip_design_m      REAL,               -- cao độ mũi TK (m)
    D_m                 REAL,               -- đường kính (m)
    ham_luong_xi_mang   REAL,               -- lượng xi măng (kg/m)
    ty_le_nc            REAL,               -- tỷ lệ nước/xi măng

    -- Trạng thái thi công
    status              TEXT DEFAULT 'chua_thi_cong',
        -- chua_thi_cong | dang_thi_cong | hoan_thanh | khong_dat | tam_dung
    ngay_thi_cong       TEXT,               -- YYYY-MM-DD
    to_doi              TEXT,               -- tổ đội / nhà thầu
    may_thi_cong        TEXT,               -- tên máy / thiết bị

    -- Giá trị thực tế (cập nhật sau khi thi công)
    z_top_actual_m      REAL,
    z_tip_actual_m      REAL,
    L_actual_m          REAL,
    luong_xi_mang_kg    REAL,               -- tổng xi măng thực tế (kg)
    ap_luc_bom_bar      REAL,               -- áp lực bơm (bar)
    toc_do_khoan_m_ph   REAL,               -- tốc độ khoan (m/phút)
    toc_do_rut_m_ph     REAL,               -- tốc độ rút (m/phút)

    ghi_chu             TEXT,
    created_at          TEXT DEFAULT (datetime('now','localtime')),
    updated_at          TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE (toado_id)
)
"""

DDL_KIEM_TRA = """
CREATE TABLE IF NOT EXISTS cdm_kiem_tra (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    thi_cong_id         INTEGER,            -- FK → cdm_thi_cong.id
    zone                TEXT NOT NULL,
    point_name          TEXT,

    -- Thông tin mẫu
    loai_tn             TEXT NOT NULL,
        -- UCS (nén nở hông) | core (khoan lõi) | wet_grab | field_vane
    phuong_phap_lay_mau TEXT,               -- coring / khoan_lay_mau / wet_grab
    ngay_lay_mau        TEXT,               -- YYYY-MM-DD
    ngay_thu_nghiem     TEXT,               -- YYYY-MM-DD
    tuoi_ngay           INTEGER,            -- tuổi mẫu (ngày)

    -- Vị trí mẫu
    do_sau_tu_dinh_m    REAL,               -- độ sâu từ đỉnh cọc (m)
    z_sample_m          REAL,               -- cao độ lấy mẫu (m, tuyệt đối)

    -- Kết quả nén
    qu_kPa              REAL,               -- cường độ nén nở hông (kPa)
    qu_yc_kPa           REAL,               -- qu yêu cầu thiết kế (kPa)
    dat_yeu_cau         INTEGER,            -- 1=Đạt / 0=Không đạt / NULL=chưa đánh giá

    -- Thông số vật liệu
    ham_luong_xi_mang_pct REAL,             -- hàm lượng xi măng (%)
    ty_le_nc            REAL,               -- w/c thực tế mẫu

    ghi_chu             TEXT,
    created_at          TEXT DEFAULT (datetime('now','localtime'))
)
"""

DDL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cdm_tc_zone     ON cdm_thi_cong(zone)",
    "CREATE INDEX IF NOT EXISTS idx_cdm_tc_status   ON cdm_thi_cong(status)",
    "CREATE INDEX IF NOT EXISTS idx_cdm_tc_bh       ON cdm_thi_cong(bh_dieu_hanh)",
    "CREATE INDEX IF NOT EXISTS idx_cdm_tc_toado    ON cdm_thi_cong(toado_id)",
    "CREATE INDEX IF NOT EXISTS idx_cdm_kt_tc       ON cdm_kiem_tra(thi_cong_id)",
    "CREATE INDEX IF NOT EXISTS idx_cdm_kt_zone     ON cdm_kiem_tra(zone)",
    "CREATE INDEX IF NOT EXISTS idx_cdm_kt_loai     ON cdm_kiem_tra(loai_tn)",
    "CREATE INDEX IF NOT EXISTS idx_cdm_kt_ngay     ON cdm_kiem_tra(ngay_thu_nghiem)",
]

# ── Tính thông số thiết kế từ HK gần nhất ─────────────────────────────────────
def _build_design_params(con: sqlite3.Connection) -> dict[int, dict]:
    """toado_id → {bh, L, z_tip, z_top}"""
    # D_bottom_soft per BH: ke_sw_nt_detail ưu tiên, fallback layers
    ke_soft = dict(con.execute(
        "SELECT bh_name, D_bottom_soft_m FROM ke_sw_nt_detail "
        "WHERE D_bottom_soft_m IS NOT NULL"
    ).fetchall())
    sym_ph = ",".join(SOFT_SYM)
    lyr_soft = dict(con.execute(
        f"SELECT b.name, MAX(l.depth_bot_m) "
        f"FROM layers l JOIN boreholes b ON l.borehole_id=b.id "
        f"WHERE l.symbol IN ({sym_ph}) AND b.x_coord_m > 1000000 "
        f"GROUP BY b.name"
    ).fetchall())

    bh_all = con.execute(
        "SELECT name, elevation_m, x_coord_m, y_coord_m "
        "FROM boreholes WHERE x_coord_m > 1000000 AND y_coord_m IS NOT NULL"
    ).fetchall()

    # Tính L thiết kế per BH
    bh_design: dict[str, dict] = {}
    for bn, elev, xc, yc in bh_all:
        d_soft = ke_soft.get(bn) or lyr_soft.get(bn)
        if d_soft is None:
            continue
        z_tip = float(elev or 0) - d_soft - PEN_BELOW
        bh_design[bn] = {
            "bh": bn,
            "zone": ("KE" if bn.startswith("KE-") else
                     "BXN" if bn.startswith("BXN-") else "NHC"),
            "x": float(xc), "y": float(yc),
            "L": round(Z_TOP - z_tip, 2),
            "z_tip": round(z_tip, 2),
        }

    ke_bhs  = [v for v in bh_design.values() if v["zone"] == "KE"]
    bxn_bhs = [v for v in bh_design.values() if v["zone"] == "BXN"]

    # CDM piles from cdm_toado
    toado = con.execute(
        "SELECT id, zone, northing_m, easting_m FROM cdm_toado "
        "ORDER BY id"
    ).fetchall()

    def _nearest(nx, ey, bhs):
        best, best_d2 = bhs[0], math.inf
        for b in bhs:
            d2 = (b["x"] - nx)**2 + (b["y"] - ey)**2
            if d2 < best_d2:
                best, best_d2 = b, d2
        return best

    result: dict[int, dict] = {}
    for tid, zone, nx, ey in toado:
        pool = ke_bhs if zone == "KE" else bxn_bhs
        if not pool:
            continue
        bh = _nearest(nx, ey, pool)
        result[tid] = {
            "bh":    bh["bh"],
            "L":     bh["L"],
            "z_tip": bh["z_tip"],
        }
    return result

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    con = sqlite3.connect(str(DB))
    con.execute("PRAGMA journal_mode=WAL")

    print("Tạo bảng cdm_thi_cong ...")
    con.execute(DDL_THI_CONG)
    print("Tạo bảng cdm_kiem_tra ...")
    con.execute(DDL_KIEM_TRA)
    for idx in DDL_INDEXES:
        con.execute(idx)
    con.commit()

    # Pre-populate cdm_thi_cong (chỉ INSERT các toado_id chưa có)
    existing = {r[0] for r in con.execute(
        "SELECT toado_id FROM cdm_thi_cong"
    ).fetchall()}
    toado_all = con.execute(
        "SELECT id, zone, point_name, northing_m, easting_m FROM cdm_toado"
    ).fetchall()
    new_piles = [r for r in toado_all if r[0] not in existing]

    if not new_piles:
        print("cdm_thi_cong: tất cả cọc đã có — bỏ qua populate.")
    else:
        print(f"Tính thông số thiết kế cho {len(new_piles):,} cọc mới ...")
        design = _build_design_params(con)

        rows = []
        for tid, zone, pname, nx, ey in new_piles:
            d = design.get(tid, {})
            rows.append((
                tid, zone, pname, nx, ey,
                d.get("bh"),
                d.get("L"),
                Z_TOP,
                d.get("z_tip"),
                D_CDM,
                XI_MANG_KG_M,
                TY_LE_NC,
                "chua_thi_cong",
            ))

        con.executemany("""
            INSERT OR IGNORE INTO cdm_thi_cong
              (toado_id, zone, point_name, northing_m, easting_m,
               bh_dieu_hanh, L_design_m, z_top_design_m, z_tip_design_m,
               D_m, ham_luong_xi_mang, ty_le_nc, status)
            VALUES (?,?,?,?,?, ?,?,?,?,?,?,?,?)
        """, rows)
        con.commit()
        n_ins = len(rows)
        print(f"  Đã insert {n_ins:,} cọc vào cdm_thi_cong")

    # Thống kê
    for tbl in ("cdm_thi_cong", "cdm_kiem_tra"):
        cnt = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl}: {cnt:,} rows")

    # Status distribution
    print("\nPhân bố trạng thái thi công:")
    for st, n in con.execute(
        "SELECT status, COUNT(*) FROM cdm_thi_cong GROUP BY status"
    ).fetchall():
        print(f"  {st}: {n:,}")

    # L thiết kế summary per zone
    print("\nChiều dài thiết kế trung bình:")
    for zone, cnt, l_avg, l_min, l_max in con.execute("""
        SELECT zone, COUNT(*), ROUND(AVG(L_design_m),2),
               ROUND(MIN(L_design_m),2), ROUND(MAX(L_design_m),2)
        FROM cdm_thi_cong WHERE L_design_m IS NOT NULL
        GROUP BY zone
    """).fetchall():
        print(f"  {zone}: n={cnt:,}  L={l_avg}m  [{l_min}–{l_max}]")

    con.close()
    print("\nHoàn thành.")

if __name__ == "__main__":
    main()
