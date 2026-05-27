"""
tvtk_cdm_s1_calc.py — Tính lún S1 trong khối CDM (TCVN 9403 Phụ lục C §5.3) cho tất cả zone.

S1 = q × H / (a × Ec + (1-a) × Es)

- a   = tỷ lệ diện tích thay thế (từ D_mm, spacing_m, pattern trong tvtk_cdm_config)
- Ec  = Ec_factor × qu_kPa / 2
- Es  = 250 × cu  với cu = μ × Su_VST (hiệu chỉnh Bjerrum, TCCS 41 Phụ lục C.5)
        μ tra theo Ip lớp yếu (Bảng C.1); chỉ áp cho Su từ VST, KHÔNG áp cho Cu_UU lab.
- Cu_VST: trung bình VST của trạm gần nhất cùng zone, trong phạm vi H_soft

Priority Cu_VST:
  1. vst_locations.name = bh_name (KE zone — tên trùng khớp)
  2. VST station gần nhất cùng zone (BXN/NHC)
  3. Cu_UU trung bình từ lab_tests (fallback)

Chạy:
  python scripts/tvtk_cdm_s1_calc.py
"""

from __future__ import annotations
import sys, sqlite3, math, json
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

_ROOT = Path(__file__).parent.parent
_DB   = _ROOT / "data" / "TTHC.sqlite"

# Hệ số hiệu chỉnh Bjerrum μ (TCCS 41 Phụ lục C.5) — dùng chung từ settlement_calc
sys.path.insert(0, str(Path(__file__).parent))
from settlement_calc import bjerrum_mu  # noqa: E402

# Symbol lớp yếu để lấy Ip TB (theo lab_tests.symbol_tcvn, KHÁC layers.symbol)
_SOFT_SYMBOLS_IP = ("1", "1b", "CH", "MH", "CH-OH", "MH-OH")


# ──────────────────────────────────────────────────────────────────
# 1. HELPERS
# ──────────────────────────────────────────────────────────────────

def _area_ratio(D_mm: float, spacing_m: float, pattern: str) -> float:
    """Tỷ lệ diện tích thay thế a = Ac / A_đơn_vị."""
    D = D_mm / 1000.0
    r = D / 2.0
    if pattern == "triangle":
        return math.pi * r**2 / (spacing_m**2 * math.sqrt(3) / 2)
    # square (default)
    return math.pi * r**2 / spacing_m**2


def _zone_of(bh_name: str) -> str:
    for prefix in ("BXN", "NHC", "KE"):
        if bh_name.startswith(prefix):
            return prefix
    return "?"


def _ip_avg(con: sqlite3.Connection, bh_name: str) -> float | None:
    """Ip trung bình của lớp đất yếu trong HK (lab_tests.symbol_tcvn). None nếu không có."""
    ph = ",".join("?" * len(_SOFT_SYMBOLS_IP))
    r = con.execute(f"""
        SELECT AVG(lt.Ip) avg_ip, COUNT(lt.Ip) n
        FROM lab_tests lt JOIN boreholes b ON lt.borehole_id = b.id
        WHERE b.name = ? AND lt.Ip IS NOT NULL AND lt.Ip > 0
          AND lt.symbol_tcvn IN ({ph})
    """, (bh_name, *_SOFT_SYMBOLS_IP)).fetchone()
    if r and r["n"] and r["avg_ip"] is not None:
        return float(r["avg_ip"])
    return None


def _nearest_vst_su(bh_name: str, bh_x: float, bh_y: float,
                    H_soft: float, zone: str, con: sqlite3.Connection
                    ) -> tuple[float | None, str]:
    """
    Trả về (avg_Su_kPa, source_label).
    Priority:
      1. vst_locations.name == bh_name (exact match — dùng cho KE)
      2. Trạm VST gần nhất cùng zone (BXN / NHC)
      3. Cu_UU trung bình từ lab_tests cùng borehole
      4. Cu_UU trung bình từ HK lab gần nhất cùng zone
    """
    # 1. Exact name match
    row = con.execute("""
        SELECT AVG(v.Su_kPa) avg_su
        FROM vane_shear_tests v
        JOIN vst_locations vl ON v.vst_loc_id = vl.id
        WHERE vl.name = ? AND v.Su_kPa > 0 AND v.depth_m <= ?
    """, (bh_name, H_soft)).fetchone()
    if row and row["avg_su"]:
        return float(row["avg_su"]), f"VST {bh_name}"

    # 2. Nearest VST station same zone (need coordinates)
    if bh_x is not None and bh_y is not None:
        vstlocs = con.execute("""
            SELECT vl.name, vl.x_coord_m, vl.y_coord_m,
                   AVG(v.Su_kPa) avg_su
            FROM vst_locations vl
            JOIN vane_shear_tests v ON v.vst_loc_id = vl.id
            WHERE vl.name LIKE ? AND v.Su_kPa > 0 AND v.depth_m <= ?
            GROUP BY vl.name
        """, (zone + "-%", H_soft)).fetchall()
        best_su, best_name, best_dist = None, None, float("inf")
        for vl in vstlocs:
            if vl["x_coord_m"] is None or vl["y_coord_m"] is None:
                continue
            d = math.hypot(float(vl["x_coord_m"]) - bh_x,
                           float(vl["y_coord_m"]) - bh_y)
            if d < best_dist:
                best_dist = d
                best_su   = float(vl["avg_su"])
                best_name = vl["name"]
        if best_su:
            return best_su, f"VST gần nhất: {best_name} (d={best_dist:.0f}m)"

    # 3. Cu_UU from own lab_tests
    bh_row = con.execute("SELECT id FROM boreholes WHERE name=?", (bh_name,)).fetchone()
    if bh_row:
        lab = con.execute("""
            SELECT AVG(Cu_UU_kPa) avg_cu
            FROM lab_tests
            WHERE borehole_id=? AND Cu_UU_kPa IS NOT NULL AND Cu_UU_kPa > 0
              AND depth_from_m <= ?
        """, (bh_row["id"], H_soft)).fetchone()
        if lab and lab["avg_cu"]:
            return float(lab["avg_cu"]), f"Cu_UU lab {bh_name}"

    # 4. Cu_UU nearest BH same zone
    bhs_zone = con.execute("""
        SELECT b.name, b.x_coord_m, b.y_coord_m, AVG(l.Cu_UU_kPa) avg_cu
        FROM boreholes b JOIN lab_tests l ON l.borehole_id=b.id
        WHERE b.name LIKE ? AND l.Cu_UU_kPa IS NOT NULL AND l.Cu_UU_kPa > 0
          AND b.name != ?
        GROUP BY b.name
    """, (zone + "-%", bh_name)).fetchall()
    if bhs_zone and bh_x is not None and bh_y is not None:
        best_cu, best_bhn, best_d = None, None, float("inf")
        for nb in bhs_zone:
            if nb["x_coord_m"] is None or nb["y_coord_m"] is None:
                continue
            d = math.hypot(float(nb["x_coord_m"]) - bh_x,
                           float(nb["y_coord_m"]) - bh_y)
            if d < best_d:
                best_d = d; best_cu = float(nb["avg_cu"]); best_bhn = nb["name"]
        if best_cu:
            return best_cu, f"Cu_UU lab gần nhất: {best_bhn} (d={best_d:.0f}m) [fallback]"

    return None, "không có dữ liệu VST / Cu_UU"


# ──────────────────────────────────────────────────────────────────
# 2. BATCH COMPUTE
# ──────────────────────────────────────────────────────────────────

def run_s1_batch(db_path: Path = _DB, verbose: bool = True) -> list[dict]:
    """Tính S1 cho tất cả HK selected=1, tất cả zone. Lưu vào tvtk_bh_cdm."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = []

    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row

        # Đọc config CDM
        cfg = con.execute("SELECT * FROM tvtk_cdm_config WHERE id=1").fetchone()
        if not cfg:
            print("Không tìm thấy tvtk_cdm_config — dừng.")
            return []

        D_mm      = float(cfg["D_mm"])
        spacing_m = float(cfg["spacing_m"])
        pattern   = cfg["pattern"] or "square"
        Ec_factor = float(cfg["Ec_factor"])
        qu_kPa    = float(cfg["qu_kPa"])
        q_kPa     = float(cfg["q_kPa"])

        a  = _area_ratio(D_mm, spacing_m, pattern)
        Ec = Ec_factor * qu_kPa / 2.0

        if verbose:
            print(f"CDM config: D={D_mm:.0f}mm  s={spacing_m}m  pattern={pattern}")
            print(f"  a={a:.4f}  Ec={Ec:,.0f}kPa  q={q_kPa}kPa")

        # Đọc tất cả HK selected với H_soft > 0
        bhs = con.execute("""
            SELECT t.bh_name, t.H_pa1_m, t.H_pa2_m, t.H_soft_m,
                   b.x_coord_m, b.y_coord_m
            FROM tvtk_bh_cdm t
            JOIN boreholes b ON b.name = t.bh_name
            WHERE t.selected = 1 AND t.H_soft_m > 0
            ORDER BY t.bh_name
        """).fetchall()

        for bh in bhs:
            bh_name = bh["bh_name"]
            H_soft  = float(bh["H_soft_m"])
            H_pa1   = float(bh["H_pa1_m"]) if bh["H_pa1_m"] is not None else 0.0
            H_pa2   = float(bh["H_pa2_m"]) if bh["H_pa2_m"] is not None else 0.0
            bh_x    = float(bh["x_coord_m"]) if bh["x_coord_m"] else None
            bh_y    = float(bh["y_coord_m"]) if bh["y_coord_m"] else None
            zone    = _zone_of(bh_name)

            Cu, source = _nearest_vst_su(bh_name, bh_x, bh_y, H_soft, zone, con)
            # Hiệu chỉnh Bjerrum: cu = μ·Su — CHỈ áp cho Su từ VST, KHÔNG áp cho Cu_UU lab
            ip_avg  = _ip_avg(con, bh_name)
            is_vst  = source.startswith("VST")
            mu      = bjerrum_mu(ip_avg) if (ip_avg and is_vst) else 1.0
            Cu_corr = (Cu * mu) if Cu else None
            Es = 250.0 * Cu_corr if Cu_corr else None

            def _s1(H: float) -> float | None:
                if not Es or H <= 0:
                    return None
                Ecomp = a * Ec + (1.0 - a) * Es
                return round(q_kPa * H / Ecomp * 100.0, 2)

            s1_1 = _s1(H_pa1)
            s1_2 = _s1(H_pa2)
            s1_3 = _s1(H_soft)

            con.execute("""
                INSERT INTO tvtk_bh_cdm
                    (bh_name, Ip_avg, bjerrum_mu, Cu_VST_avg_kPa, Cu_corrected_kPa,
                     Es_kPa, S1_pa1_cm, S1_pa2_cm, S1_pa3_cm, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(bh_name) DO UPDATE SET
                    Ip_avg           = excluded.Ip_avg,
                    bjerrum_mu       = excluded.bjerrum_mu,
                    Cu_VST_avg_kPa   = excluded.Cu_VST_avg_kPa,
                    Cu_corrected_kPa = excluded.Cu_corrected_kPa,
                    Es_kPa           = excluded.Es_kPa,
                    S1_pa1_cm        = excluded.S1_pa1_cm,
                    S1_pa2_cm        = excluded.S1_pa2_cm,
                    S1_pa3_cm        = excluded.S1_pa3_cm,
                    updated_at       = excluded.updated_at
            """, (bh_name, ip_avg, round(mu, 4), Cu, Cu_corr, Es, s1_1, s1_2, s1_3, now))

            results.append({
                "bh_name": bh_name,
                "Cu_kPa": round(Cu, 1) if Cu else None,
                "Ip_avg": round(ip_avg, 1) if ip_avg else None,
                "mu": round(mu, 3),
                "Cu_corr_kPa": round(Cu_corr, 1) if Cu_corr else None,
                "source": source,
                "S1_PA1": s1_1, "S1_PA2": s1_2, "S1_PA3": s1_3,
            })

            if verbose:
                cu_str = (f"Su={Cu:.1f}→cu={Cu_corr:.1f}kPa (μ={mu:.3f}, {source})"
                          if Cu else f"! {source}")
                print(f"  {bh_name}: {cu_str}  S1_PA1={s1_1}  S1_PA2={s1_2}  S1_PA3={s1_3}cm")

        con.commit()
        try:
            con.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            pass

    return results


# ──────────────────────────────────────────────────────────────────
# 3. MAIN
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Tính lún S1 trong khối gia cố CDM — tất cả zone ===")
    print(f"DB: {_DB}\n")

    res = run_s1_batch(verbose=True)
    print(f"\nHoàn thành: {len(res)} hố khoan đã tính S1.")

    # Tóm tắt per zone
    con2 = sqlite3.connect(_DB)
    con2.row_factory = sqlite3.Row
    for zone in ("KE", "BXN", "NHC"):
        rows = con2.execute("""
            SELECT
                ROUND(AVG(S1_pa1_cm),2) avg1, ROUND(MAX(S1_pa1_cm),2) max1,
                ROUND(AVG(S1_pa2_cm),2) avg2, ROUND(MAX(S1_pa2_cm),2) max2,
                ROUND(AVG(S1_pa3_cm),2) avg3, ROUND(MAX(S1_pa3_cm),2) max3,
                COUNT(*) n
            FROM tvtk_bh_cdm
            WHERE bh_name LIKE ? AND selected=1 AND H_soft_m > 0
              AND S1_pa1_cm IS NOT NULL
        """, (zone + "-%",)).fetchone()
        if rows and rows["n"]:
            print(f"\n  {zone} ({rows['n']} HK):")
            print(f"    PA1: avg={rows['avg1']}cm  max={rows['max1']}cm")
            print(f"    PA2: avg={rows['avg2']}cm  max={rows['max2']}cm")
            print(f"    PA3: avg={rows['avg3']}cm  max={rows['max3']}cm")
    con2.close()
