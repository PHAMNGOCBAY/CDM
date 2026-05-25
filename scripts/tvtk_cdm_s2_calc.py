"""
tvtk_cdm_s2_calc.py — Tính lún S2 dưới đáy cọc CDM cho 3 phương án chiều sâu.

TCVN 9403:2012 Phụ lục C §5.3:
  S = S1 + S2
  S1 = lún đàn hồi trong khối gia cố CDM
  S2 = lún cố kết các lớp đất yếu NẰM DƯỚI đáy cột CDM (Cc/Cs)

Phương án:
  PA1 = CDM qua lớp 1 (và các lớp always-soft liên tục từ mặt)
  PA2 = CDM qua lớp 1 + 1b (all always-soft)
  PA3 = CDM qua toàn bộ H_soft → S2 = 0

Chạy:
  python scripts/tvtk_cdm_s2_calc.py
"""

from __future__ import annotations
import sys, sqlite3, json
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

_ROOT = Path(__file__).parent.parent
_DB   = _ROOT / "data" / "TTHC.sqlite"

# Import settlement_calc từ cùng thư mục scripts/
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))
from settlement_calc import calc_s2_layers  # type: ignore[import]

_ALWAYS_SOFT = ("1", "1b", "XMD")
_CHECK_E0    = ("2", "2b", "3")
_E0_THRESH   = 1.0


# ──────────────────────────────────────────────────────────────────
# 1. ĐỌC / KHỞI TẠO BẢNG SQLite
# ──────────────────────────────────────────────────────────────────

def _create_tables(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS tvtk_cdm_s2 (
            bh_name     TEXT NOT NULL,
            pa          TEXT NOT NULL,   -- 'PA1' | 'PA2' | 'PA3'
            H_cdm_m     REAL,            -- chiều sâu đáy cột CDM (từ miệng HK)
            H_below_m   REAL,            -- chiều dày đất yếu bên dưới CDM tip
            S2_cm       REAL,            -- lún S2 (cm)
            q_kPa       REAL,            -- tải trọng dùng để tính
            n_layers    INTEGER,         -- số lớp đóng góp vào S2
            has_fallback INTEGER DEFAULT 0,
            warnings    TEXT,            -- JSON array
            updated_at  TEXT,
            PRIMARY KEY (bh_name, pa)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS tvtk_cdm_s2_layers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            bh_name      TEXT NOT NULL,
            pa           TEXT NOT NULL,
            layer_idx    INTEGER,
            symbol       TEXT,
            depth_top_m  REAL,
            depth_bot_m  REAL,
            H_i_m        REAL,
            e0           REAL,
            Cc           REAL,
            Cs           REAL,
            PC_kPa       REAL,
            sigma_v0_kPa REAL,
            sigma_vf_kPa REAL,
            oc_status    TEXT,
            Si_cm        REAL,
            cc_source    TEXT,
            UNIQUE(bh_name, pa, layer_idx)
        )
    """)
    # Thêm cột S2 vào tvtk_bh_cdm (idempotent)
    for col in ("S2_pa1_cm", "S2_pa2_cm", "S2_pa3_cm"):
        try:
            con.execute(f"ALTER TABLE tvtk_bh_cdm ADD COLUMN {col} REAL")
        except sqlite3.OperationalError:
            pass  # already exists


# ──────────────────────────────────────────────────────────────────
# 2. TÍNH H_pa1 / H_pa2 CHO BXN / NHC (nếu chưa có)
# ──────────────────────────────────────────────────────────────────

def _compute_hpa(bh_id: int, con: sqlite3.Connection) -> tuple[float, float]:
    """
    Trả về (H_pa1_m, H_pa2_m):
      H_pa1_m = tổng chiều dày các lớp ALWAYS_SOFT (= PA1 boundary)
      H_pa2_m = H_pa1_m + tổng chiều dày lớp e₀>1.0 đầu tiên ngay sau always-soft
    """
    lyrs = con.execute("""
        SELECT symbol, depth_top_m, depth_bot_m,
               COALESCE(thickness_m, depth_bot_m - depth_top_m) thick
        FROM layers WHERE borehole_id=? ORDER BY depth_top_m
    """, (bh_id,)).fetchall()

    h_always = 0.0
    h_e0_first = 0.0  # chỉ nhóm e₀-soft đầu tiên ngay sau always-soft

    passed_always = False
    for l in lyrs:
        sym = l["symbol"]; tk = float(l["thick"] or 0)
        if tk <= 0:
            continue
        if sym in _ALWAYS_SOFT:
            h_always += tk
        else:
            # Sau khi qua always-soft: kiểm tra nhóm e₀-soft đầu tiên
            passed_always = True
            r = con.execute("""
                SELECT AVG(e0) avg_e0 FROM lab_tests
                WHERE borehole_id=? AND depth_from_m>=? AND depth_from_m<?
                  AND e0 IS NOT NULL AND e0 > 0
            """, (bh_id, float(l["depth_top_m"]), float(l["depth_bot_m"]))).fetchone()
            if r and r["avg_e0"] and r["avg_e0"] >= _E0_THRESH:
                h_e0_first += tk
            else:
                if passed_always and h_e0_first > 0:
                    break  # đã qua nhóm e₀-soft đầu tiên, dừng lại

    return round(h_always, 2), round(h_always + h_e0_first, 2)


# ──────────────────────────────────────────────────────────────────
# 3. BATCH COMPUTE
# ──────────────────────────────────────────────────────────────────

def run_s2_batch(db_path: Path = _DB, verbose: bool = True) -> list[dict]:
    """Tính S2 cho tất cả HK selected=1 × 3 PA. Lưu vào SQLite."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = []

    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        _create_tables(con)

        # Đọc cấu hình tải trọng
        cfg = con.execute(
            "SELECT q_kPa FROM tvtk_cdm_config WHERE id=1"
        ).fetchone()
        q_cdm = float(cfg["q_kPa"]) if cfg and cfg["q_kPa"] else 40.8

        # Đọc tất cả HK tham gia CDM
        bhs = con.execute("""
            SELECT t.bh_name, t.H_pa1_m, t.H_pa2_m, t.H_soft_m,
                   b.id bh_id, b.elevation_m
            FROM tvtk_bh_cdm t
            JOIN boreholes b ON b.name = t.bh_name
            WHERE t.selected = 1
        """).fetchall()

        for bh in bhs:
            bh_name  = bh["bh_name"]
            H_soft   = float(bh["H_soft_m"] or 0)

            if H_soft < 0.5:
                if verbose:
                    print(f"  {bh_name}: H_soft={H_soft}m — bỏ qua (không có đất yếu)")
                continue

            # H_pa1/H_pa2: dùng giá trị đã có hoặc tính lại
            H_pa1 = float(bh["H_pa1_m"]) if bh["H_pa1_m"] is not None else None
            H_pa2 = float(bh["H_pa2_m"]) if bh["H_pa2_m"] is not None else None
            if H_pa1 is None or H_pa2 is None:
                H_pa1, H_pa2 = _compute_hpa(bh["bh_id"], con)
                # Ghi lại vào tvtk_bh_cdm
                con.execute("""
                    UPDATE tvtk_bh_cdm SET H_pa1_m=?, H_pa2_m=?, updated_at=?
                    WHERE bh_name=?
                """, (H_pa1, H_pa2, now, bh_name))

            scenarios = {
                "PA1": H_pa1,
                "PA2": H_pa2,
                "PA3": H_soft,   # CDM đến hết đất yếu → S2=0
            }

            row_s2 = {}
            for pa, H_cdm in scenarios.items():
                res = calc_s2_layers(
                    bh_name  = bh_name,
                    H_cdm_m  = H_cdm,
                    H_soft_m = H_soft,
                    q_kPa    = q_cdm,
                    gwt_depth_m = 0.0,
                    db_path  = db_path,
                )
                S2   = res["S2_cm"]
                warn = res["warnings"]
                n_lay = len([l for l in res["layers"] if l.get("Si_cm", 0) > 0])
                has_fb = int(any("fallback" in l.get("cc_source","") for l in res["layers"]))

                # Ghi tvtk_cdm_s2
                con.execute("""
                    INSERT INTO tvtk_cdm_s2
                        (bh_name, pa, H_cdm_m, H_below_m, S2_cm, q_kPa,
                         n_layers, has_fallback, warnings, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(bh_name, pa) DO UPDATE SET
                        H_cdm_m=excluded.H_cdm_m, H_below_m=excluded.H_below_m,
                        S2_cm=excluded.S2_cm, q_kPa=excluded.q_kPa,
                        n_layers=excluded.n_layers, has_fallback=excluded.has_fallback,
                        warnings=excluded.warnings, updated_at=excluded.updated_at
                """, (bh_name, pa, H_cdm, res["H_below_m"], S2, q_cdm,
                      n_lay, has_fb, json.dumps(warn, ensure_ascii=False), now))

                # Ghi tvtk_cdm_s2_layers
                con.execute("DELETE FROM tvtk_cdm_s2_layers WHERE bh_name=? AND pa=?",
                            (bh_name, pa))
                for idx, lay in enumerate(res["layers"]):
                    con.execute("""
                        INSERT OR REPLACE INTO tvtk_cdm_s2_layers
                            (bh_name, pa, layer_idx, symbol,
                             depth_top_m, depth_bot_m, H_i_m,
                             e0, Cc, Cs, PC_kPa,
                             sigma_v0_kPa, sigma_vf_kPa, oc_status, Si_cm, cc_source)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (bh_name, pa, idx, lay["symbol"],
                          lay["depth_top_m"], lay["depth_bot_m"], lay["H_i_m"],
                          lay["e0"], lay["Cc"], lay["Cs"], lay["PC_kPa"],
                          lay["sigma_v0_kPa"], lay["sigma_vf_kPa"],
                          lay["oc_status"], lay["Si_cm"], lay["cc_source"]))

                row_s2[pa] = round(S2, 2)
                if verbose and (S2 > 0 or warn):
                    flag = "  [fallback]" if has_fb else ""
                    print(f"  {bh_name} {pa}: H_below={res['H_below_m']:.1f}m  "
                          f"S2={S2:.2f}cm{flag}")
                    for w in warn[:2]:
                        print(f"    ! {w}")

            # Cập nhật tvtk_bh_cdm
            con.execute("""
                UPDATE tvtk_bh_cdm
                SET S2_pa1_cm=?, S2_pa2_cm=?, S2_pa3_cm=0.0, updated_at=?
                WHERE bh_name=?
            """, (row_s2.get("PA1", 0), row_s2.get("PA2", 0), now, bh_name))

            results.append({"bh_name": bh_name,
                             "S2_PA1": row_s2.get("PA1"), "S2_PA2": row_s2.get("PA2")})

        try:
            con.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            pass  # DB có thể đang dùng bởi app — checkpoint sau

    return results


# ──────────────────────────────────────────────────────────────────
# 4. MAIN
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Tính lún S2 dưới đáy cọc CDM ===")
    print(f"DB: {_DB}")

    res = run_s2_batch(verbose=True)
    print(f"\nHoàn thành: {len(res)} hố khoan đã tính.")

    # Tóm tắt per zone
    import sqlite3 as _sq2
    con2 = _sq2.connect(_DB)
    con2.row_factory = _sq2.Row
    for zone in ("KE", "BXN", "NHC"):
        rows = con2.execute("""
            SELECT s.pa, COUNT(*) n,
                   ROUND(AVG(s.S2_cm),2) avg_S2,
                   ROUND(MAX(s.S2_cm),2) max_S2
            FROM tvtk_cdm_s2 s
            WHERE s.bh_name LIKE ? || '-%' AND s.S2_cm > 0
            GROUP BY s.pa ORDER BY s.pa
        """, (zone,)).fetchall()
        if rows:
            print(f"\n  {zone}:")
            for r in rows:
                print(f"    {r['pa']}: {r['n']} HK  avg={r['avg_S2']}cm  max={r['max_S2']}cm")
    con2.close()
