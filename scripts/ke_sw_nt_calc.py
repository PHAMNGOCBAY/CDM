"""
ke_sw_nt_calc.py — Tính toán chi tiết NT1 / NT2 cọc ván SW kè KE
Tiêu chuẩn: TCVN 11823-10:2017, Điều 7.3.8.6.2 — phương pháp alpha (Tomlinson 1980)

Nguyên tắc lấy số liệu (BẮT BUỘC):
  1. SQLite vane_shear_tests (Su_kPa trung bình trong lớp)  → source='VST'
  2. SQLite lab_tests (Cu_UU_kPa hoặc c_kPa trung bình)   → source='lab'
  3. SU_BY_SYMBOL mặc định — CẢNH BÁO kỹ sư               → source='default'
  4. Không xác định được (lớp lạ, cát)                     → source='sand'/'unknown'

Mọi thông số hình học (Z_m, H_layer1) cũng đọc từ SQLite; JSON chỉ dùng để
lấy tên cọc kiến nghị và danh sách HK trên tuyến.
"""

from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from datetime import datetime

_ROOT   = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "data" / "TTHC.sqlite"
KE_JSON = _ROOT / "data" / "ke_sw_202605_TTHC.json"
SW_JSON = _ROOT / "data" / "sw_pile_catalog.json"

# ── Hằng số thiết kế kè KE ───────────────────────────────────────────────────
TOP_KE_M   = 2.70    # cao độ đỉnh kè (m)
TIP_ELEV_M = -26.30  # cao độ mũi cọc yêu cầu (m)
MIN_PEN_M  = 1.00    # ngàm tối thiểu dưới đáy vùng mềm (m)
PHI_STAT   = 0.35    # hệ số sức kháng φ_stat (TCVN 11823-10, Bảng 9)

# Bảng dự phòng — chỉ dùng khi KHÔNG có dữ liệu thí nghiệm trong SQLite
SU_BY_SYMBOL: dict[str, float] = {
    "1": 10.0, "1b": 20.0, "3": 35.0,
    "5": 75.0, "5b": 100.0, "XMD": 10.0,
}
# Lớp cát/san lấp — dùng SPT-Meyerhof (TCVN 11823-10 Điều 7.3.8.6.7)
SAND_SYMBOLS = frozenset({"F", "2a", "2b", "2c", "4", "5a", "6", "7"})
# Lớp yếu xử lý — tính là vùng mềm trong NT1
SOFT_SYMBOLS = frozenset({"1", "XMD"})

# Cọc SW = cọc bê tông DUL chữ U lõi đặc → cọc CHIẾM CHỖ
SW_IS_DISPLACING = True

# Hệ số sức kháng theo phương pháp (TCVN 11823-10:2017 Bảng 9)
PHI_BY_METHOD = {
    "alpha":  0.35,  # Tomlinson 1987, Skempton 1951 — sét
    "beta":   0.25,  # Esrig & Kirby 1979 — sét
    "lambda": 0.40,  # Vijayvergiya & Focht 1972 — sét cọc ống
    "SPT":    0.30,  # Meyerhof — cát
}

# γ mặc định theo ký hiệu khi không có lab_tests (kN/m³)
GAMMA_DEFAULT_BY_SYMBOL: dict[str, float] = {
    "1": 15.0, "1b": 16.0, "XMD": 14.0,
    "2a": 18.0, "2b": 18.5, "2c": 19.0,
    "3":  18.0, "4":  19.0, "5":  19.0, "5a": 19.5, "5b": 19.5,
    "6":  20.0, "7":  20.0, "F":  17.0,
}
# Mực nước ngầm mặc định (m, hệ cao độ tuyệt đối)
WATER_TABLE_DEFAULT = -1.0
_GAMMA_W = 9.81


# ── Alpha Tomlinson (1980) — bảng Hình 18, TCVN 11823-10:2017 Điều 7.3.8.6.2 ─
# Nội suy tuyến tính theo 6 điểm trong Bảng tra (Mục 18.2, 18-driven-pile-TCVN11823.md)
_TOMLINSON_PTS: list[tuple[float, float]] = [
    (0.0,   1.00),
    (25.0,  1.00),
    (50.0,  0.92),
    (75.0,  0.75),
    (100.0, 0.60),
    (150.0, 0.50),
    (200.0, 0.40),
]

def _alpha_tomlinson(su: float) -> float:
    """Hệ số dính α — Tomlinson (1980), Hình 18, TCVN 11823-10:2017 Điều 7.3.8.6.2.
    Nội suy tuyến tính từ bảng 6 điểm.  α(su=0–25)=1.00, α(su≥200)=0.40.
    """
    if su <= 0.0:
        return 0.0
    if su >= _TOMLINSON_PTS[-1][0]:
        return _TOMLINSON_PTS[-1][1]
    for i in range(len(_TOMLINSON_PTS) - 1):
        s0, a0 = _TOMLINSON_PTS[i]
        s1, a1 = _TOMLINSON_PTS[i + 1]
        if s0 <= su <= s1:
            return round(a0 + (su - s0) / (s1 - s0) * (a1 - a0), 4)
    return 1.0


# ── γ + σ'v + N₁₆₀ helpers (cho SPT-Meyerhof) ────────────────────────────────
def _find_nearest_bh_with_data(
    bh_name: str, symbol: str, field: str,
    db_path: Path = DB_PATH,
    depth_top: float | None = None, depth_bot: float | None = None,
) -> tuple[float, str, float] | tuple[None, None, None]:
    """Tìm HK gần nhất cùng zone có giá trị `field` cho lớp.

    Phương án match:
    1. Nếu cung cấp `depth_top`+`depth_bot`: query lab_tests theo depth range
       (phù hợp khi `layers.symbol` khác `lab_tests.symbol_tcvn` USCS).
    2. Nếu không: query lab_tests.symbol_tcvn = symbol.

    field: tên cột trong lab_tests (vd 'gamma_kNm3', 'Cu_UU_kPa', 'c_kPa', 'Cc').
    Trả (value_avg, source_bh_name, distance_m) hoặc (None, None, None)."""
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    row = cur.execute(
        "SELECT b.x_coord_m, b.y_coord_m, z.code "
        "FROM boreholes b JOIN zones z ON b.zone_id=z.id WHERE b.name=?",
        (bh_name,),
    ).fetchone()
    if row is None or row[0] is None:
        con.close()
        return None, None, None
    x0, y0, zone = row

    if depth_top is not None and depth_bot is not None:
        # Match theo depth range — không phụ thuộc symbol mapping
        # Thử 3 mức tolerance tăng dần: exact, ±2m, ±5m
        rows = []
        for tol in (0.0, 2.0, 5.0):
            rows = cur.execute(
                f"""
                SELECT b.name, b.x_coord_m, b.y_coord_m, AVG(lt.{field}) v
                FROM lab_tests lt
                JOIN boreholes b ON lt.borehole_id=b.id
                JOIN zones z ON b.zone_id=z.id
                WHERE z.code=? AND b.name<>?
                  AND lt.{field} IS NOT NULL
                  AND b.x_coord_m IS NOT NULL
                  AND (lt.depth_from_m + lt.depth_to_m)/2.0 BETWEEN ? AND ?
                GROUP BY b.id
                """,
                (zone, bh_name, depth_top - tol, depth_bot + tol),
            ).fetchall()
            if rows:
                break
    else:
        # Match theo symbol TCVN
        rows = cur.execute(
            f"""
            SELECT b.name, b.x_coord_m, b.y_coord_m, AVG(lt.{field}) v
            FROM lab_tests lt
            JOIN boreholes b ON lt.borehole_id=b.id
            JOIN zones z ON b.zone_id=z.id
            WHERE z.code=? AND b.name<>?
              AND lt.symbol_tcvn=?
              AND lt.{field} IS NOT NULL
              AND b.x_coord_m IS NOT NULL
            GROUP BY b.id
            """,
            (zone, bh_name, symbol),
        ).fetchall()
    con.close()
    if not rows:
        return None, None, None
    candidates = sorted(
        ((((x - x0) ** 2 + (y - y0) ** 2) ** 0.5, nm, v) for nm, x, y, v in rows)
    )
    d, nm, v = candidates[0]
    return round(float(v), 3), nm, round(d, 1)


def _get_gamma_for_layer(
    bh_name: str, depth_top: float, depth_bot: float,
    symbol: str, db_path: Path = DB_PATH,
) -> tuple[float, str]:
    """Trung bình γ (kN/m³) từ lab_tests trong [depth_top, depth_bot].
    Priority: (1) HK hiện tại lab → (2) HK gần nhất cùng zone có lab cho symbol →
    (3) GAMMA_DEFAULT_BY_SYMBOL (warning)."""
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute(
        "SELECT AVG(lt.gamma_kNm3) FROM lab_tests lt "
        "JOIN boreholes b ON lt.borehole_id=b.id "
        "WHERE b.name=? AND lt.gamma_kNm3 IS NOT NULL "
        "  AND (lt.depth_from_m + lt.depth_to_m)/2.0 >= ? "
        "  AND (lt.depth_from_m + lt.depth_to_m)/2.0 <= ?",
        (bh_name, depth_top, depth_bot),
    )
    row = cur.fetchone()
    con.close()
    if row and row[0] is not None:
        return round(float(row[0]), 2), "lab"
    # Fallback 1: HK gần nhất cùng zone có γ tại depth range tương ứng
    v, src_bh, dist = _find_nearest_bh_with_data(
        bh_name, symbol, "gamma_kNm3", db_path,
        depth_top=depth_top, depth_bot=depth_bot,
    )
    if v is not None:
        return round(v, 2), f"nearest:{src_bh}({dist:.0f}m)"
    # Fallback 2: hardcode mặc định
    return GAMMA_DEFAULT_BY_SYMBOL.get(symbol, 18.0), "default"


def _sigma_v_eff_at_depth(
    bh_name: str, depth_target: float,
    db_path: Path = DB_PATH,
    water_table_elev: float = WATER_TABLE_DEFAULT,
) -> float:
    """Ứng suất hiệu quả thẳng đứng σ'v (kPa) tại độ sâu depth_target (m từ cổ HK).
    Tích phân γ·dz qua các lớp; dưới MNN dùng γ' = γ − γw."""
    layers = _load_layers(bh_name, db_path)
    Z_top = _get_bh_Z_m(bh_name, db_path) or 0.0
    # Độ sâu MNN từ cổ HK (m, dương xuống dưới)
    depth_wt = Z_top - water_table_elev
    sigma = 0.0
    for dtop, dbot, sym in layers:
        if dtop >= depth_target:
            break
        dbot_eff = min(dbot, depth_target)
        L_total = dbot_eff - dtop
        if L_total <= 0:
            continue
        gamma, _ = _get_gamma_for_layer(bh_name, dtop, dbot, sym, db_path)
        # Chia lớp đôi nếu cắt qua MNN
        if dtop >= depth_wt:
            # Toàn bộ lớp dưới MNN → γ' = γ − γw
            sigma += max(gamma - _GAMMA_W, 0.0) * L_total
        elif dbot_eff <= depth_wt:
            # Toàn bộ lớp trên MNN → γ
            sigma += gamma * L_total
        else:
            # Cắt ngang: phần trên MNN dùng γ, phần dưới dùng γ'
            L_above = depth_wt - dtop
            L_below = dbot_eff - depth_wt
            sigma += gamma * L_above + max(gamma - _GAMMA_W, 0.0) * L_below
    return round(max(sigma, 0.0), 2)


def _get_N160_for_layer(
    bh_name: str, depth_top: float, depth_bot: float,
    db_path: Path = DB_PATH,
    water_table_elev: float = WATER_TABLE_DEFAULT,
) -> tuple[float | None, str]:
    """Trung bình N₁₆₀ trong [depth_top, depth_bot].
    Hiệu chỉnh CN = √(100/σ'v_kPa), clamp [0.5, 2.0] — TCVN 11823-10 Điều 4.6.2.4.
    Trả (N160_avg, source). source: 'SPT' | 'missing'."""
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute(
        "SELECT s.depth_m, s.N FROM spt_values s "
        "JOIN boreholes b ON s.borehole_id=b.id "
        "WHERE b.name=? AND s.depth_m >= ? AND s.depth_m <= ? "
        "  AND s.N IS NOT NULL AND s.N > 0",
        (bh_name, depth_top, depth_bot),
    )
    rows = cur.fetchall()
    con.close()
    if not rows:
        return None, "missing"
    N160_vals: list[float] = []
    for depth, N in rows:
        sigma_v = _sigma_v_eff_at_depth(bh_name, depth, db_path, water_table_elev)
        CN = (100.0 / sigma_v) ** 0.5 if sigma_v > 0 else 1.0
        CN = max(0.5, min(2.0, CN))
        N160_vals.append(float(N) * CN)
    return round(sum(N160_vals) / len(N160_vals), 1), "SPT"


# ── β-method (Esrig & Kirby 1979) — TCVN 11823-10 Điều 7.3.8.6.3 ─────────────
# Bảng tra β theo OCR (Esrig & Kirby 1979, Hình 19)
_BETA_PTS: list[tuple[float, float]] = [
    (1.0,  0.27),   # NC clay
    (2.0,  0.40),
    (4.0,  0.60),
    (8.0,  0.85),
    (16.0, 1.15),
]

def _beta_esrig_kirby(OCR: float) -> float:
    """Hệ số β theo OCR — Esrig & Kirby (1979), nội suy tuyến tính."""
    if OCR <= _BETA_PTS[0][0]:
        return _BETA_PTS[0][1]
    if OCR >= _BETA_PTS[-1][0]:
        return _BETA_PTS[-1][1]
    for i in range(len(_BETA_PTS) - 1):
        o0, b0 = _BETA_PTS[i]
        o1, b1 = _BETA_PTS[i + 1]
        if o0 <= OCR <= o1:
            return round(b0 + (OCR - o0) / (o1 - o0) * (b1 - b0), 4)
    return 0.27


# ── λ-method (Vijayvergiya & Focht 1972) — TCVN 11823-10 Điều 7.3.8.6.4 ──────
# Bảng tra λ theo chiều sâu cọc ngàm trong sét L (m), Hình 20
_LAMBDA_PTS: list[tuple[float, float]] = [
    (0.0,   0.50),
    (3.0,   0.36),
    (10.0,  0.27),
    (15.0,  0.22),
    (20.0,  0.17),
    (30.0,  0.14),
    (50.0,  0.12),
    (60.0,  0.12),
]

def _lambda_vijayvergiya_focht(L_clay_m: float) -> float:
    """Hệ số λ theo chiều dài cọc trong sét — Vijayvergiya & Focht (1972)."""
    if L_clay_m <= _LAMBDA_PTS[0][0]:
        return _LAMBDA_PTS[0][1]
    if L_clay_m >= _LAMBDA_PTS[-1][0]:
        return _LAMBDA_PTS[-1][1]
    for i in range(len(_LAMBDA_PTS) - 1):
        l0, v0 = _LAMBDA_PTS[i]
        l1, v1 = _LAMBDA_PTS[i + 1]
        if l0 <= L_clay_m <= l1:
            return round(v0 + (L_clay_m - l0) / (l1 - l0) * (v1 - v0), 4)
    return 0.12


# ── Công thức SPT-Meyerhof (TCVN 11823-10:2017 Điều 7.3.8.6.7) ───────────────
def _qs_spt_kPa(N160: float | None, displacing: bool = True) -> float:
    """qs (kPa) cho cát — Pt.69/70. qs[MPa] = 0.0019·N160 (chiếm chỗ) hoặc 0.00096 (không)."""
    if N160 is None or N160 <= 0:
        return 0.0
    return (1.9 if displacing else 0.96) * N160  # ×1000 đổi MPa→kPa


def _qp_spt_kPa(
    N160: float | None, Db_m: float, D_m: float,
    soil_type: str = "sand",
) -> float:
    """qp (kPa) cho cát — Pt.68: qp[MPa] = 0.038·N160·(Db/D), giới hạn λq.
    cát: λq = 3.2·N160 MPa = 3200·N160 kPa.
    cát bột: λq = 1.8·N160 MPa = 1800·N160 kPa."""
    if N160 is None or N160 <= 0 or D_m <= 0:
        return 0.0
    qp = 38.0 * N160 * (Db_m / D_m)        # ×1000 đổi MPa→kPa
    lambda_q = (1800.0 if soil_type == "silt_sand" else 3200.0) * N160
    return min(qp, lambda_q)


# ── Đọc catalog cọc ──────────────────────────────────────────────────────────
def _load_catalog(sw_json: Path = SW_JSON) -> dict[str, dict]:
    data = json.loads(sw_json.read_text(encoding="utf-8"))
    catalog: dict[str, dict] = {}
    seen: set[str] = set()
    for p in data["piles"]:
        name = p["name"]
        if name not in seen:
            seen.add(name)
            if p.get("perimeter_mm") is None:
                catalog[name] = {**p, "perimeter_mm": _interp_perimeter(p["H_mm"], data["piles"])}
            else:
                catalog[name] = p
    return catalog


def _interp_perimeter(H_mm: int, piles: list) -> float:
    known = sorted(
        [(p["H_mm"], p["perimeter_mm"]) for p in piles if p.get("perimeter_mm") and p["H_mm"] != H_mm]
    )
    if len(known) < 2:
        return 0.0
    below = [k for k in known if k[0] < H_mm]
    above = [k for k in known if k[0] > H_mm]
    if below and above:
        h1, p1 = below[-1]; h2, p2 = above[0]
    else:
        h1, p1 = known[-2]; h2, p2 = known[-1]
    return p1 + (H_mm - h1) / (h2 - h1) * (p2 - p1)


# ── Đọc địa tầng từ SQLite ───────────────────────────────────────────────────
def _load_layers(bh_name: str, db_path: Path = DB_PATH) -> list[tuple]:
    """Trả về [(depth_top, depth_bot, symbol), ...] từ bảng layers."""
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute(
        "SELECT l.depth_top_m, l.depth_bot_m, l.symbol "
        "FROM layers l JOIN boreholes b ON l.borehole_id = b.id "
        "WHERE b.name=? ORDER BY l.depth_top_m",
        (bh_name,),
    )
    rows = cur.fetchall()
    con.close()
    return [(r[0], r[1], r[2]) for r in rows if r[2] is not None]


def _get_bh_Z_m(bh_name: str, db_path: Path = DB_PATH) -> float | None:
    """Cao độ miệng hố khoan từ boreholes.elevation_m."""
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute("SELECT elevation_m FROM boreholes WHERE name=?", (bh_name,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else None


def _get_D_bottom_soft_by_spt(
    bh_name: str, db_path: Path = DB_PATH,
    N_threshold: int = 4, run_length: int = 2,
) -> tuple[float, str]:
    """Đáy vùng yếu theo SPT: depth cuối cùng có N<threshold TRƯỚC khi
    xuất hiện run_length readings liên tiếp có N≥threshold.

    Lý do dùng run_length=2: tránh nhận sai 1 reading soft đơn lẻ ở sâu
    (vd HK3 có N=1 ở 30m giữa lớp cứng N=10-28) là đáy vùng yếu.

    Threshold N<4 = đất yếu theo TCVN (Terzaghi soft clay)."""
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute(
        "SELECT s.depth_m, s.N FROM spt_values s "
        "JOIN boreholes b ON s.borehole_id=b.id "
        "WHERE b.name=? AND s.N IS NOT NULL ORDER BY s.depth_m",
        (bh_name,),
    )
    rows = cur.fetchall()
    con.close()
    if not rows:
        return 0.0, "missing"
    last_soft_depth = 0.0
    consecutive_hard = 0
    for depth, N in rows:
        if N < N_threshold:
            last_soft_depth = depth
            consecutive_hard = 0
        else:
            consecutive_hard += 1
            if consecutive_hard >= run_length:
                break  # đã thoát vùng yếu — bỏ qua isolated soft pockets sâu hơn
    if last_soft_depth > 0:
        return round(last_soft_depth, 3), "SPT"
    return 0.0, "missing"


def _get_D_bottom_soft(bh_name: str, db_path: Path = DB_PATH) -> tuple[float, str]:
    """
    Đáy vùng yếu = MAX(layer-symbol-based, SPT N<4 depth).
    NT1: L_req = fill_m + D_bottom_soft + min_pen.

    Logic 2 nguồn:
    - layer: max(depth_bot) của lớp ∈ SOFT_SYMBOLS ('1', 'XMD')
    - SPT: max depth có N < 4 (TCVN — đất yếu)
    Lấy max để bảo thủ. Source = 'layer+SPT' hoặc nguồn duy nhất có.
    """
    layers = _load_layers(bh_name, db_path)
    soft_bottoms = [bot for _, bot, sym in layers if sym in SOFT_SYMBOLS]
    d_layer = max(soft_bottoms) if soft_bottoms else 0.0
    d_spt, spt_src = _get_D_bottom_soft_by_spt(bh_name, db_path)

    if d_layer > 0 and d_spt > 0:
        d_final = max(d_layer, d_spt)
        src = f"layer={d_layer:.1f} | SPT={d_spt:.1f} → max"
        return round(d_final, 3), src
    if d_layer > 0:
        return round(d_layer, 3), "layer (no SPT)"
    if d_spt > 0:
        return round(d_spt, 3), "SPT (no soft layer marked)"
    return 0.0, "missing"


# ── Lấy su từ SQLite — ưu tiên VST → lab → mặc định ─────────────────────────
def _get_su_for_layer(
    bh_name: str,
    depth_top: float,
    depth_bot: float,
    symbol: str,
    db_path: Path = DB_PATH,
) -> tuple[float, str]:
    """
    Trả về (su_kPa, source).
    source: 'sand' | 'VST' | 'lab' | 'default' | 'unknown'

    Ưu tiên:
      1. VST trung bình trong khoảng [depth_top, depth_bot]
      2. lab_tests (Cu_UU_kPa ưu tiên, nếu null dùng c_kPa) trung bình
      3. SU_BY_SYMBOL mặc định — PHẢI cảnh báo kỹ sư
    """
    if symbol in SAND_SYMBOLS:
        return 0.0, "sand"

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    # ── Ưu tiên 1: VST ───────────────────────────────────────────────────────
    cur.execute(
        "SELECT t.Su_kPa FROM vane_shear_tests t "
        "JOIN vst_locations v ON t.vst_loc_id = v.id "
        "WHERE v.name=? AND t.depth_m >= ? AND t.depth_m <= ? AND t.Su_kPa > 0",
        (bh_name, depth_top, depth_bot),
    )
    vst_vals = [r[0] for r in cur.fetchall()]
    if vst_vals:
        con.close()
        return round(sum(vst_vals) / len(vst_vals), 1), "VST"

    # ── Ưu tiên 2: lab_tests ─────────────────────────────────────────────────
    cur.execute(
        "SELECT l.Cu_UU_kPa, l.c_kPa "
        "FROM lab_tests l JOIN boreholes b ON l.borehole_id = b.id "
        "WHERE b.name=? "
        "  AND (l.depth_from_m + l.depth_to_m) / 2.0 >= ? "
        "  AND (l.depth_from_m + l.depth_to_m) / 2.0 <= ? "
        "  AND (l.Cu_UU_kPa IS NOT NULL OR l.c_kPa IS NOT NULL)",
        (bh_name, depth_top, depth_bot),
    )
    lab_vals = []
    for cu_uu, c_kpa in cur.fetchall():
        v = cu_uu if cu_uu is not None else c_kpa
        if v is not None and v > 0:
            lab_vals.append(v)
    con.close()
    if lab_vals:
        return round(sum(lab_vals) / len(lab_vals), 1), "lab"

    # ── Ưu tiên 3: HK gần nhất cùng zone có VST/lab tại depth range ─────────
    # Thử Cu_UU trước, fallback c_kPa; match theo depth range (vì symbol
    # USCS trong lab_tests khác layer.symbol — CH/CL vs 1/1b/XMD)
    for fld in ("Cu_UU_kPa", "c_kPa"):
        v, src_bh, dist = _find_nearest_bh_with_data(
            bh_name, symbol, fld, db_path,
            depth_top=depth_top, depth_bot=depth_bot,
        )
        if v is not None and v > 0:
            return round(v, 1), f"nearest:{src_bh}({dist:.0f}m,{fld[:2]})"

    # ── Ưu tiên 4: mặc định hardcode (cảnh báo mạnh) ────────────────────────
    default = SU_BY_SYMBOL.get(symbol)
    if default is not None:
        return default, "default"

    return 0.0, "unknown"


# ── NT1: Kiểm tra chiều dài xuyên qua vùng mềm ──────────────────────────────
def calc_nt1(
    bh_name: str,
    Z_m: float,
    D_bottom_soft_m: float,
    pile_name: str,
    L_design_m: float,
    top_ke: float = TOP_KE_M,
    min_pen: float = MIN_PEN_M,
    D_source: str = "SQLite",
) -> dict:
    """
    NT1: L_req = fill_m + D_bottom_soft_m + min_pen
         fill_m = max(0, top_ke − Z_m)  (phần cọc trong đất đắp trên cổ HK)
         D_bottom_soft_m = chiều sâu từ cổ HK đến ĐÁY lớp mềm cuối cùng
         Cọc đạt khi L_design ≥ L_req.
    """
    fill_m = max(0.0, top_ke - Z_m)
    L_req  = fill_m + D_bottom_soft_m + min_pen
    margin = L_design_m - L_req
    return {
        "bh_name":          bh_name,
        "pile_name":        pile_name,
        "L_design_m":       L_design_m,
        "top_ke_m":         top_ke,
        "Z_m":              Z_m,
        "fill_m":           round(fill_m, 3),
        "D_bottom_soft_m":  D_bottom_soft_m,
        "D_source":         D_source,
        "min_pen_m":        min_pen,
        "L_req_m":          round(L_req, 2),
        "margin_m":         round(margin, 2),
        "result":           "Đạt" if margin >= 0 else "Không đạt",
    }


# ── NT2: Sức kháng nhổ theo từng lớp ────────────────────────────────────────
def calc_nt2_layers(
    bh_name: str,
    Z_m: float,
    pile_name: str,
    pile: dict,
    L_design_m: float,
    tip_elev: float = TIP_ELEV_M,
    top_ke: float   = TOP_KE_M,
    phi_stat: float | None = None,
    db_path: Path   = DB_PATH,
    water_table_elev: float = WATER_TABLE_DEFAULT,
) -> dict:
    """
    NT2: RR = φ_stat × (Rs + Rp) ≥ W_cọc
    - Lớp sét: α-method (Tomlinson 1980), su ưu tiên VST → lab → mặc định
    - Lớp cát: SPT-Meyerhof (TCVN 11823-10 Điều 7.3.8.6.7),
              N₁₆₀ hiệu chỉnh CN = √(100/σ'v), clamp [0.5, 2.0]
    - φ_stat: nếu phi_stat=None → tính động (sét dominant=0.35, cát dominant=0.30)
    """
    perimeter_m = pile["perimeter_mm"] / 1000.0
    Ap_m2       = pile["Atd_cm2"] * 1e-4
    D_m         = pile["H_mm"] / 1000.0           # bề rộng cọc — dùng cho qp_SPT
    TL_T        = pile["weight_T"]
    L_std       = pile["L_std_m"]
    w_per_m     = TL_T * 9.81 / L_std
    W_kN        = round(w_per_m * L_design_m, 1)

    fill_m    = round(max(0.0, top_ke - Z_m), 3)
    tip_depth = round(Z_m - tip_elev, 3)

    layers_raw = _load_layers(bh_name, db_path)
    rows: list[dict] = []
    Rs_total      = 0.0
    Rs_clay_total = 0.0
    Rs_sand_total = 0.0
    tip_su       = 0.0
    tip_N160     = None
    tip_symbol   = ""
    tip_method   = "alpha"
    tip_layer_top = 0.0
    warnings:  list[str] = []

    for depth_top, depth_bot, symbol in layers_raw:
        eff_top = max(depth_top, 0.0)
        eff_bot = min(depth_bot, tip_depth)
        if eff_bot <= eff_top:
            continue
        L_lyr = round(eff_bot - eff_top, 3)

        # γ + σ'v dùng cho mọi phương pháp (lưu vào row để debug)
        gamma_v, gamma_src = _get_gamma_for_layer(bh_name, depth_top, depth_bot, symbol, db_path)
        sigma_v = _sigma_v_eff_at_depth(
            bh_name, (depth_top + depth_bot) / 2.0, db_path, water_table_elev,
        )

        # ── SPT-Meyerhof cho cát ──────────────────────────────────────────────
        if symbol in SAND_SYMBOLS:
            N160, n_src = _get_N160_for_layer(
                bh_name, depth_top, depth_bot, db_path, water_table_elev,
            )
            qs_kPa = _qs_spt_kPa(N160, displacing=SW_IS_DISPLACING)
            Rs_lyr = round(qs_kPa * perimeter_m * L_lyr, 1)
            Rs_sand_total += Rs_lyr
            if n_src == "missing":
                warnings.append(
                    f"Lớp cát '{symbol}' ({depth_top:.1f}–{depth_bot:.1f} m): "
                    "không có SPT → bỏ qua ma sát thành bên"
                )
            rows.append({
                "symbol":          symbol,
                "depth_top_m":     depth_top,
                "depth_bot_m":     depth_bot,
                "eff_top_m":       round(eff_top, 2),
                "eff_bot_m":       round(eff_bot, 2),
                "L_lyr_m":         L_lyr,
                "su_kNm2":         0.0,
                "su_source":       n_src,
                "alpha":           0.0,
                "Rs_lyr_kN":       Rs_lyr,
                "method":          "SPT",
                "N160":            N160 if N160 is not None else 0.0,
                "sigma_v_eff_kPa": sigma_v,
                "gamma_kNm3":      gamma_v,
            })
            if depth_top <= tip_depth <= depth_bot:
                tip_N160     = N160
                tip_symbol   = symbol
                tip_method   = "SPT"
                tip_layer_top = depth_top
            continue

        # ── α-method cho sét (logic gốc) ──────────────────────────────────────
        su, source = _get_su_for_layer(bh_name, depth_top, depth_bot, symbol, db_path)
        if source.startswith("nearest:"):
            warnings.append(
                f"Lớp '{symbol}' ({depth_top:.1f}–{depth_bot:.1f} m): HK hiện tại không có VST/lab → "
                f"lấy su={su:.0f} kPa từ {source.replace('nearest:', '')}"
            )
        elif source == "default":
            warnings.append(
                f"Lớp '{symbol}' ({depth_top:.1f}–{depth_bot:.1f} m): "
                f"không có VST/lab cả khu vực → dùng su={su:.0f} kPa (hardcode theo ký hiệu — CẦN BỔ SUNG THÍ NGHIỆM)"
            )
        elif source == "unknown":
            warnings.append(
                f"Lớp '{symbol}' ({depth_top:.1f}–{depth_bot:.1f} m): "
                "không xác định được su — bỏ qua ma sát"
            )
        alpha  = _alpha_tomlinson(su) if su > 0 else 0.0
        Rs_lyr = round(alpha * su * perimeter_m * L_lyr, 1)
        Rs_clay_total += Rs_lyr
        rows.append({
            "symbol":          symbol,
            "depth_top_m":     depth_top,
            "depth_bot_m":     depth_bot,
            "eff_top_m":       round(eff_top, 2),
            "eff_bot_m":       round(eff_bot, 2),
            "L_lyr_m":         L_lyr,
            "su_kNm2":         su,
            "su_source":       source,
            "alpha":           round(alpha, 3),
            "Rs_lyr_kN":       Rs_lyr,
            "method":          "alpha",
            "N160":            None,
            "sigma_v_eff_kPa": sigma_v,
            "gamma_kNm3":      gamma_v,
        })
        if depth_top <= tip_depth <= depth_bot:
            tip_su        = su
            tip_symbol    = symbol
            tip_method    = "alpha"
            tip_layer_top = depth_top

    Rs_total = round(Rs_clay_total + Rs_sand_total, 1)

    # ── Rp tại mũi ────────────────────────────────────────────────────────────
    if tip_method == "SPT":
        if tip_N160 and tip_N160 > 0:
            Db_m   = max(tip_depth - tip_layer_top, 0.01)
            qp_kPa = _qp_spt_kPa(tip_N160, Db_m, D_m, soil_type="sand")
            Rp_kN  = round(qp_kPa * Ap_m2, 1)
        else:
            Rp_kN = 0.0
            warnings.append(
                f"Mũi cọc trong lớp cát '{tip_symbol}' nhưng không có SPT → Rp = 0"
            )
    else:
        Rp_kN = round(9.0 * tip_su * Ap_m2, 1) if tip_su > 0 else 0.0

    # ── φ_stat động ───────────────────────────────────────────────────────────
    if phi_stat is None:
        # Sand chiếm > 10% Rs → SPT dominant → φ=0.30
        sand_share = Rs_sand_total / Rs_total if Rs_total > 0 else 0.0
        if tip_method == "SPT" or sand_share > 0.10:
            phi_eff = PHI_BY_METHOD["SPT"]
            phi_basis = f"SPT dominant (sand Rs={sand_share*100:.0f}% / tip={tip_method})"
        else:
            phi_eff = PHI_BY_METHOD["alpha"]
            phi_basis = "α dominant (sét chiếm ưu thế)"
    else:
        phi_eff = phi_stat
        phi_basis = f"user-set {phi_stat}"

    RR_kN = round(phi_eff * (Rs_total + Rp_kN), 1)
    ratio = round(RR_kN / W_kN, 2) if W_kN > 0 else 0.0

    return {
        "bh_name":       bh_name,
        "pile_name":     pile_name,
        "L_design_m":    L_design_m,
        "fill_m":        fill_m,
        "L_soil_m":      round(L_design_m - fill_m, 3),
        "tip_depth_m":   tip_depth,
        "perimeter_m":   round(perimeter_m, 4),
        "Ap_cm2":        pile["Atd_cm2"],
        "D_m":           round(D_m, 3),
        "w_kNm":         round(w_per_m, 3),
        "W_kN":          W_kN,
        "layers":        rows,
        "Rs_clay_kN":    round(Rs_clay_total, 1),
        "Rs_sand_kN":    round(Rs_sand_total, 1),
        "Rs_kN":         Rs_total,
        "tip_symbol":    tip_symbol,
        "tip_method":    tip_method,
        "tip_su_kNm2":   tip_su,
        "tip_N160":      tip_N160,
        "Rp_kN":         Rp_kN,
        "phi_stat":      phi_eff,
        "phi_basis":     phi_basis,
        "RR_kN":         RR_kN,
        "ratio":         ratio,
        "result":        "Đạt" if ratio >= 1.0 else "Không đạt",
        "warnings":      warnings,
    }


# ── So sánh 4 phương pháp NT2 ───────────────────────────────────────────────
def calc_nt2_all_methods(
    bh_name: str, Z_m: float, pile_name: str, pile: dict, L_design_m: float,
    tip_elev: float = TIP_ELEV_M, top_ke: float = TOP_KE_M,
    db_path: Path = DB_PATH, water_table_elev: float = WATER_TABLE_DEFAULT,
) -> dict:
    """So sánh sức kháng NT2 theo 4 phương pháp TCVN 11823-10:2017.

    Trả về dict:
    {
      'auto':   {Rs, Rp, RR, ratio, phi}  -- hỗn hợp α(sét) + SPT(cát), φ động
      'alpha':  {...}  -- toàn bộ lớp dùng α-method (sét, Điều 7.3.8.6.2, φ=0.35)
      'beta':   {...}  -- β-method (Esrig & Kirby, Điều 7.3.8.6.3, φ=0.25)
      'lambda': {...}  -- λ-method (Vijayvergiya & Focht, Điều 7.3.8.6.4, φ=0.40)
      'SPT':    {...}  -- SPT-Meyerhof cho mọi lớp (Điều 7.3.8.6.7, φ=0.30)
      'common': {pile_name, L_design_m, W_kN, ...}
    }
    """
    perimeter_m = pile["perimeter_mm"] / 1000.0
    Ap_m2       = pile["Atd_cm2"] * 1e-4
    D_m         = pile["H_mm"] / 1000.0
    w_per_m     = pile["weight_T"] * 9.81 / pile["L_std_m"]
    W_kN        = round(w_per_m * L_design_m, 1)
    tip_depth   = round(Z_m - tip_elev, 3)
    fill_m      = round(max(0.0, top_ke - Z_m), 3)

    layers_raw = _load_layers(bh_name, db_path)

    # Pre-collect per-layer data (su, σ'v, N160, gamma, depth range)
    layer_data: list[dict] = []
    L_clay_total = 0.0
    sum_sigma_x_L = 0.0
    sum_su_x_L_clay = 0.0
    for dt, db_, sym in layers_raw:
        eff_top = max(dt, 0.0)
        eff_bot = min(db_, tip_depth)
        if eff_bot <= eff_top:
            continue
        L_lyr = eff_bot - eff_top
        mid   = (dt + db_) / 2.0
        sigma_v = _sigma_v_eff_at_depth(bh_name, mid, db_path, water_table_elev)
        gamma_v, _ = _get_gamma_for_layer(bh_name, dt, db_, sym, db_path)
        is_sand = sym in SAND_SYMBOLS

        if is_sand:
            su = 0.0; OCR = 1.0; PC = 0.0
            N160, _ = _get_N160_for_layer(bh_name, dt, db_, db_path, water_table_elev)
        else:
            su, _ = _get_su_for_layer(bh_name, dt, db_, sym, db_path)
            # PC từ lab_tests trung bình trong lớp
            con = sqlite3.connect(str(db_path))
            cur = con.cursor()
            row = cur.execute(
                "SELECT AVG(lt.PC_kPa) FROM lab_tests lt "
                "JOIN boreholes b ON lt.borehole_id=b.id "
                "WHERE b.name=? AND lt.PC_kPa IS NOT NULL "
                "  AND (lt.depth_from_m+lt.depth_to_m)/2 BETWEEN ? AND ?",
                (bh_name, dt, db_),
            ).fetchone()
            con.close()
            PC  = row[0] if row and row[0] else 0.0
            OCR = max(1.0, PC / sigma_v) if sigma_v > 0 else 1.0
            N160 = None
            L_clay_total += L_lyr
            sum_su_x_L_clay += su * L_lyr
            sum_sigma_x_L += sigma_v * L_lyr

        layer_data.append({
            "symbol": sym, "L": L_lyr, "is_sand": is_sand,
            "su": su, "sigma_v": sigma_v, "OCR": OCR, "PC": PC,
            "N160": N160, "gamma": gamma_v, "mid": mid,
            "is_tip": dt <= tip_depth <= db_,
        })

    # Su, σ'v trung bình của phần sét (cho λ-method)
    su_avg_clay    = sum_su_x_L_clay / L_clay_total if L_clay_total > 0 else 0.0
    sigma_avg_clay = sum_sigma_x_L / L_clay_total if L_clay_total > 0 else 0.0
    lambda_coef    = _lambda_vijayvergiya_focht(L_clay_total)

    def _calc_method(method: str) -> dict:
        """Tính Rs/Rp/RR cho 1 method (áp dụng cho tất cả lớp sét; sand giữ nguyên SPT)."""
        Rs_total = 0.0
        tip_qp_kPa = 0.0
        tip_method_used = "—"
        per_layer = []
        for L in layer_data:
            if L["is_sand"]:
                qs = _qs_spt_kPa(L["N160"], displacing=SW_IS_DISPLACING)
                Rs_lyr = qs * perimeter_m * L["L"]
                Rs_total += Rs_lyr
                if L["is_tip"]:
                    if L["N160"] and L["N160"] > 0:
                        tip_qp_kPa = _qp_spt_kPa(L["N160"], 1.0, D_m, "sand")  # Db ~ approximation
                    tip_method_used = "SPT"
                per_layer.append({"sym": L["symbol"], "L": round(L["L"],2),
                                  "qs": round(qs,1), "Rs": round(Rs_lyr,1), "m": "SPT"})
                continue
            # Sét — theo method được chọn
            su = L["su"]; sig = L["sigma_v"]; OCR = L["OCR"]
            if method == "alpha":
                alpha = _alpha_tomlinson(su) if su > 0 else 0.0
                qs = alpha * su
            elif method == "beta":
                beta = _beta_esrig_kirby(OCR)
                qs = beta * sig
            elif method == "lambda":
                qs = lambda_coef * (sigma_avg_clay + 2.0 * su_avg_clay)
            else:  # SPT applied to clay (non-standard but for completeness)
                qs = 0.0
            Rs_lyr = qs * perimeter_m * L["L"]
            Rs_total += Rs_lyr
            if L["is_tip"]:
                tip_qp_kPa = 9.0 * su   # qp sét = 9·Su
                tip_method_used = method
            per_layer.append({"sym": L["symbol"], "L": round(L["L"],2),
                              "qs": round(qs,1), "Rs": round(Rs_lyr,1), "m": method})

        Rp = tip_qp_kPa * Ap_m2
        phi = PHI_BY_METHOD.get(method, 0.35)
        RR = phi * (Rs_total + Rp)
        return {
            "method":    method,
            "phi_stat":  phi,
            "Rs_kN":     round(Rs_total, 1),
            "Rp_kN":     round(Rp, 1),
            "RR_kN":     round(RR, 1),
            "ratio":     round(RR / W_kN, 2) if W_kN > 0 else 0,
            "result":    "Đạt" if RR >= W_kN else "Không đạt",
            "tip_method": tip_method_used,
            "layers":    per_layer,
        }

    # AUTO = current calc_nt2_layers (mix α + SPT, φ động)
    auto = calc_nt2_layers(bh_name, Z_m, pile_name, pile, L_design_m,
                           tip_elev, top_ke, None, db_path, water_table_elev)

    return {
        "common": {
            "bh_name":    bh_name,
            "pile_name":  pile_name,
            "L_design_m": L_design_m,
            "W_kN":       W_kN,
            "perimeter_m": round(perimeter_m, 4),
            "D_m":        round(D_m, 3),
            "Ap_m2":      round(Ap_m2, 5),
            "tip_depth_m": tip_depth,
            "L_clay_total_m": round(L_clay_total, 2),
            "su_avg_clay_kPa":  round(su_avg_clay, 1),
            "sigma_avg_clay_kPa": round(sigma_avg_clay, 1),
            "lambda_coef": lambda_coef,
        },
        "auto":   {"Rs_kN": auto["Rs_kN"], "Rp_kN": auto["Rp_kN"],
                   "RR_kN": auto["RR_kN"], "ratio": auto["ratio"],
                   "phi_stat": auto["phi_stat"], "result": auto["result"],
                   "method": "auto (α + SPT)", "tip_method": auto["tip_method"]},
        "alpha":  _calc_method("alpha"),
        "beta":   _calc_method("beta"),
        "lambda": _calc_method("lambda"),
        "SPT":    _calc_method("SPT"),
    }


# ── Tính toàn bộ HK trên tuyến kè ───────────────────────────────────────────
def calc_all_alignment_hks(
    db_path:      Path = DB_PATH,
    ke_json_path: Path = KE_JSON,
    sw_json_path: Path = SW_JSON,
) -> list[dict]:
    """Tính NT1 + NT2 chi tiết cho 7 HK trên tuyến kè SW."""
    ke_data = json.loads(ke_json_path.read_text(encoding="utf-8"))
    catalog = _load_catalog(sw_json_path)
    results = []

    for bh in ke_data["boreholes"]:
        if not bh.get("on_sw_alignment"):
            continue

        name     = bh["name"]
        db_name  = f"KE-{name}"

        # ── Z_m: ưu tiên SQLite, fallback JSON ──────────────────────────────
        Z_m_db = _get_bh_Z_m(db_name, db_path)
        if Z_m_db is not None:
            Z_m = Z_m_db
            Z_source = "SQLite"
        else:
            Z_m = bh["Z_m"]
            Z_source = "JSON (cảnh báo: thiếu trong SQLite)"
            print(f"  [CẢNH BÁO] {db_name}: Z_m lấy từ JSON, không có trong SQLite.boreholes")

        # ── D_bottom_soft: ưu tiên SQLite, fallback JSON ─────────────────────
        D_bot, D_source = _get_D_bottom_soft(db_name, db_path)
        if D_source == "missing":
            D_bot = float(bh.get("H_layer1_m", 0.0))
            D_source = "JSON (cảnh báo: lớp '1'/'XMD' không có trong SQLite.layers)"
            print(f"  [CẢNH BÁO] {db_name}: D_bottom_soft lấy từ JSON, không có layers trong SQLite")

        rec_pile = bh.get("recommended_pile", "SW-840")
        if rec_pile not in catalog:
            rec_pile = "SW-840"
        pile     = catalog[rec_pile]
        L_design = float(bh.get("recommended_L_m") or 29.0)

        nt1 = calc_nt1(db_name, Z_m, D_bot, rec_pile, L_design, D_source=D_source)
        nt2 = calc_nt2_layers(db_name, Z_m, rec_pile, pile, L_design, db_path=db_path)

        # In cảnh báo su mặc định
        if nt2["warnings"]:
            for w in nt2["warnings"]:
                print(f"  [CẢNH BÁO su] {db_name}: {w}")

        results.append({
            "bh_name":          db_name,
            "Z_m":              Z_m,
            "Z_source":         Z_source,
            "D_bottom_soft_m":  D_bot,
            "D_source":         D_source,
            "nt1":              nt1,
            "nt2":              nt2,
        })

    return results


# ── SQLite: tạo / cập nhật bảng ──────────────────────────────────────────────
def create_nt_tables(db_path: Path = DB_PATH) -> None:
    """Tạo bảng ke_sw_nt_detail + ke_sw_nt2_layers (idempotent — KHÔNG DROP)."""
    con = sqlite3.connect(str(db_path), timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS ke_sw_nt_detail (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            project           TEXT NOT NULL DEFAULT '202605-TTHC',
            zone              TEXT NOT NULL DEFAULT 'KE',
            bh_name           TEXT NOT NULL,
            pile_type         TEXT NOT NULL,
            L_design_m        REAL NOT NULL,
            Z_m               REAL,
            Z_source          TEXT,
            fill_m            REAL,
            L_soil_m          REAL,
            tip_depth_m       REAL,
            D_bottom_soft_m   REAL,
            D_source          TEXT,
            L_req_nt1_m       REAL,
            margin_nt1_m      REAL,
            nt1_result        TEXT,
            Rs_kN             REAL,
            Rs_clay_kN        REAL,
            Rs_sand_kN        REAL,
            tip_symbol        TEXT,
            tip_method        TEXT,           -- 'alpha' | 'SPT'
            tip_su_kNm2       REAL,
            tip_N160          REAL,
            Rp_kN             REAL,
            phi_stat          REAL,           -- φ_stat hiệu dụng đã chọn
            phi_basis         TEXT,           -- lý do chọn φ
            RR_kN             REAL,
            W_kN              REAL,
            ratio_nt2         REAL,
            nt2_result        TEXT,
            su_warnings       TEXT,
            created_at        TEXT,
            UNIQUE(bh_name, pile_type, L_design_m)
        );

        CREATE TABLE IF NOT EXISTS ke_sw_nt2_layers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sw_design_id    INTEGER NOT NULL,
            layer_order     INTEGER,
            symbol          TEXT,
            L_m             REAL,
            su_kPa          REAL,
            su_source       TEXT,
            alpha           REAL,
            method          TEXT,           -- 'alpha' | 'SPT'
            N160            REAL,           -- SPT hiệu chỉnh (null nếu sét)
            sigma_v_eff_kPa REAL,           -- σ'v tại giữa lớp
            gamma_kNm3      REAL,           -- dung trọng dùng tính σ'v
            Rs_kN           REAL,
            note            TEXT,
            FOREIGN KEY (sw_design_id) REFERENCES ke_sw_nt_detail(id)
        );
    """)
    con.commit()
    con.close()


# ── Lưu kết quả vào SQLite ───────────────────────────────────────────────────
def save_nt_results(results: list[dict], db_path: Path = DB_PATH) -> None:
    create_nt_tables(db_path)
    now = datetime.now().strftime("%Y-%m-%d")
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    for r in results:
        n1 = r["nt1"]
        n2 = r["nt2"]
        warnings_txt = "; ".join(n2.get("warnings", [])) or None

        cur.execute("""
            INSERT OR REPLACE INTO ke_sw_nt_detail
            (project, zone, bh_name, pile_type, L_design_m, Z_m, Z_source,
             fill_m, L_soil_m, tip_depth_m, D_bottom_soft_m, D_source,
             L_req_nt1_m, margin_nt1_m, nt1_result,
             Rs_kN, Rs_clay_kN, Rs_sand_kN,
             tip_symbol, tip_method, tip_su_kNm2, tip_N160,
             Rp_kN, phi_stat, phi_basis, RR_kN, W_kN,
             ratio_nt2, nt2_result, su_warnings, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            "202605-TTHC", "KE",
            n1["bh_name"], n1["pile_name"], n1["L_design_m"],
            r["Z_m"], r["Z_source"],
            n2["fill_m"], n2["L_soil_m"], n2["tip_depth_m"],
            n1["D_bottom_soft_m"], r["D_source"],
            n1["L_req_m"], n1["margin_m"], n1["result"],
            n2["Rs_kN"], n2.get("Rs_clay_kN"), n2.get("Rs_sand_kN"),
            n2["tip_symbol"], n2.get("tip_method"),
            n2["tip_su_kNm2"], n2.get("tip_N160"),
            n2["Rp_kN"], n2["phi_stat"], n2.get("phi_basis"),
            n2["RR_kN"], n2["W_kN"],
            n2["ratio"], n2["result"],
            warnings_txt, now,
        ))
        detail_id = cur.lastrowid

        for i, lyr in enumerate(n2["layers"], start=1):
            cur.execute("""
                INSERT INTO ke_sw_nt2_layers
                (sw_design_id, layer_order, symbol, L_m, su_kPa, su_source,
                 alpha, method, N160, sigma_v_eff_kPa, gamma_kNm3, Rs_kN, note)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                detail_id, i, lyr["symbol"],
                lyr["L_lyr_m"], lyr["su_kNm2"], lyr["su_source"],
                lyr["alpha"], lyr.get("method", "alpha"),
                lyr.get("N160"), lyr.get("sigma_v_eff_kPa"),
                lyr.get("gamma_kNm3"),
                lyr["Rs_lyr_kN"],
                f"depth {lyr['eff_top_m']:.2f}–{lyr['eff_bot_m']:.2f} m",
            ))

    con.commit()
    con.close()


# ── Ghi JSON kết quả ─────────────────────────────────────────────────────────
def save_nt_json(results: list[dict], out_path: Path) -> None:
    payload = {
        "_meta": {
            "generated":  datetime.now().strftime("%Y-%m-%d"),
            "standard":   "TCVN 11823-10:2017 Dieu 7.3.8.6.2 — alpha method (Tomlinson 1980)",
            "phi_stat":   PHI_STAT,
            "top_ke_m":   TOP_KE_M,
            "tip_elev_m": TIP_ELEV_M,
            "min_pen_m":  MIN_PEN_M,
            "su_priority": "VST > lab_tests (Cu_UU / c_kPa) > SU_BY_SYMBOL (warn)",
        },
        "boreholes": results,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ── SQLite cache helpers — save/load per-HK results ──────────────────────────

def save_nt_detail_single(
    Z_m: float,
    Z_source: str,
    D_source: str,
    n1: dict,
    n2: dict,
    db_path: Path = DB_PATH,
) -> None:
    """Lưu kết quả NT1+NT2 của một HK vào ke_sw_nt_detail (INSERT OR REPLACE)."""
    create_nt_tables(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    warnings_txt = "; ".join(n2.get("warnings", [])) or None
    with sqlite3.connect(str(db_path), timeout=30) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("""
            INSERT OR REPLACE INTO ke_sw_nt_detail
            (project, zone, bh_name, pile_type, L_design_m, Z_m, Z_source,
             fill_m, L_soil_m, tip_depth_m, D_bottom_soft_m, D_source,
             L_req_nt1_m, margin_nt1_m, nt1_result,
             Rs_kN, Rs_clay_kN, Rs_sand_kN,
             tip_symbol, tip_method, tip_su_kNm2, tip_N160,
             Rp_kN, phi_stat, phi_basis, RR_kN, W_kN,
             ratio_nt2, nt2_result, su_warnings, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            "202605-TTHC", "KE",
            n1["bh_name"], n1["pile_name"], n1["L_design_m"],
            Z_m, Z_source,
            n2.get("fill_m"), n2.get("L_soil_m"), n2.get("tip_depth_m"),
            n1.get("D_bottom_soft_m"), D_source,
            n1["L_req_m"], n1["margin_m"], n1["result"],
            n2["Rs_kN"], n2.get("Rs_clay_kN"), n2.get("Rs_sand_kN"),
            n2["tip_symbol"], n2.get("tip_method"),
            n2.get("tip_su_kNm2"), n2.get("tip_N160"),
            n2["Rp_kN"], n2["phi_stat"], n2.get("phi_basis"),
            n2["RR_kN"], n2["W_kN"],
            n2["ratio"], n2["result"],
            warnings_txt, now,
        ))
        con.commit()


def load_nt_detail_from_db(
    bh_name: str,
    pile_type: str,
    L_m: float,
    db_path: Path = DB_PATH,
) -> dict | None:
    """Đọc kết quả NT1+NT2 từ ke_sw_nt_detail.
    Trả về dict tương thích với _calc_one_bh_nt trong app, hoặc None nếu chưa có.
    Không ghi DB trong load path — trả None nếu bảng chưa tồn tại.
    """
    try:
        with sqlite3.connect(str(db_path), timeout=10) as con:
            con.row_factory = sqlite3.Row
            row = con.execute("""
                SELECT * FROM ke_sw_nt_detail
                WHERE bh_name=? AND pile_type=? AND L_design_m=?
                ORDER BY created_at DESC LIMIT 1
            """, (bh_name, pile_type, float(L_m))).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    r = dict(row)
    return {
        "L_req_m":        r.get("L_req_nt1_m"),
        "NT1":            r.get("nt1_result"),
        "NT2":            r.get("nt2_result"),
        "W_pile_kN":      r.get("W_kN"),
        "NT2_multilayer": {
            "Rs_kN":      r.get("Rs_kN"),
            "Rp_kN":      r.get("Rp_kN"),
            "RR_kN":      r.get("RR_kN"),
            "ratio":      r.get("ratio_nt2"),
            "tip_layer":  r.get("tip_symbol"),
            "tip_method": r.get("tip_method"),
        },
        "_from_db": True,
    }


# ── Scenario table: lưu kết quả với Z tùy chỉnh (không ghi đè real data) ─────

def _create_nt_z_scenarios_table(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS ke_sw_nt_z_scenarios (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            bh_name       TEXT NOT NULL,
            pile_type     TEXT NOT NULL,
            L_design_m    REAL NOT NULL,
            z_m_input     REAL NOT NULL,
            L_req_nt1_m   REAL,
            margin_nt1_m  REAL,
            nt1_result    TEXT,
            fill_m        REAL,
            L_soil_m      REAL,
            Rs_kN         REAL,
            Rs_clay_kN    REAL,
            Rs_sand_kN    REAL,
            tip_symbol    TEXT,
            tip_method    TEXT,
            tip_su_kNm2   REAL,
            tip_N160      REAL,
            Rp_kN         REAL,
            phi_stat      REAL,
            phi_basis     TEXT,
            RR_kN         REAL,
            W_kN          REAL,
            ratio_nt2     REAL,
            nt2_result    TEXT,
            su_warnings   TEXT,
            created_at    TEXT,
            UNIQUE(bh_name, pile_type, L_design_m, z_m_input)
        );
    """)


def save_nt_z_scenario(
    z_m_input: float,
    n1: dict,
    n2: dict,
    db_path: Path = DB_PATH,
) -> None:
    """Lưu kết quả NT1+NT2 với Z giả định vào ke_sw_nt_z_scenarios.
    UNIQUE(bh_name, pile_type, L_design_m, z_m_input) — không ghi đè real data.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    warnings_txt = "; ".join(n2.get("warnings", [])) or None
    with sqlite3.connect(str(db_path), timeout=30) as con:
        con.execute("PRAGMA journal_mode=WAL")
        _create_nt_z_scenarios_table(con)
        con.execute("""
            INSERT OR REPLACE INTO ke_sw_nt_z_scenarios
            (bh_name, pile_type, L_design_m, z_m_input,
             L_req_nt1_m, margin_nt1_m, nt1_result,
             fill_m, L_soil_m,
             Rs_kN, Rs_clay_kN, Rs_sand_kN,
             tip_symbol, tip_method, tip_su_kNm2, tip_N160,
             Rp_kN, phi_stat, phi_basis, RR_kN, W_kN,
             ratio_nt2, nt2_result, su_warnings, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            n1["bh_name"], n1["pile_name"], n1["L_design_m"], float(z_m_input),
            n1["L_req_m"], n1["margin_m"], n1["result"],
            n2.get("fill_m"), n2.get("L_soil_m"),
            n2["Rs_kN"], n2.get("Rs_clay_kN"), n2.get("Rs_sand_kN"),
            n2["tip_symbol"], n2.get("tip_method"),
            n2.get("tip_su_kNm2"), n2.get("tip_N160"),
            n2["Rp_kN"], n2["phi_stat"], n2.get("phi_basis"),
            n2["RR_kN"], n2["W_kN"],
            n2["ratio"], n2["result"],
            warnings_txt, now,
        ))
        con.commit()


def load_nt_z_scenario(
    bh_name: str,
    pile_type: str,
    L_m: float,
    z_m_input: float,
    db_path: Path = DB_PATH,
) -> dict | None:
    """Đọc kết quả NT với Z tùy chỉnh từ ke_sw_nt_z_scenarios.
    Trả None nếu chưa tính cho combo (bh, pile, L, z_m_input) này.
    """
    try:
        with sqlite3.connect(str(db_path), timeout=10) as con:
            con.row_factory = sqlite3.Row
            row = con.execute("""
                SELECT * FROM ke_sw_nt_z_scenarios
                WHERE bh_name=? AND pile_type=? AND L_design_m=? AND z_m_input=?
                ORDER BY created_at DESC LIMIT 1
            """, (bh_name, pile_type, float(L_m), float(z_m_input))).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    r = dict(row)
    return {
        "L_req_m":        r.get("L_req_nt1_m"),
        "NT1":            r.get("nt1_result"),
        "NT2":            r.get("nt2_result"),
        "W_pile_kN":      r.get("W_kN"),
        "NT2_multilayer": {
            "Rs_kN":      r.get("Rs_kN"),
            "Rp_kN":      r.get("Rp_kN"),
            "RR_kN":      r.get("RR_kN"),
            "ratio":      r.get("ratio_nt2"),
            "tip_layer":  r.get("tip_symbol"),
            "tip_method": r.get("tip_method"),
        },
        "_from_db": True,
        "_z_scenario": True,
    }


def create_nt2_compare_table(db_path: Path = DB_PATH) -> None:
    """Tạo bảng ke_sw_nt2_compare (idempotent)."""
    with sqlite3.connect(str(db_path), timeout=30) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("""
        CREATE TABLE IF NOT EXISTS ke_sw_nt2_compare (
            bh_name          TEXT NOT NULL,
            pile_type        TEXT NOT NULL,
            L_m              REAL NOT NULL,
            method           TEXT NOT NULL,
            Rs_kN            REAL,
            Rp_kN            REAL,
            RR_kN            REAL,
            W_kN             REAL,
            ratio            REAL,
            phi_stat         REAL,
            result           TEXT,
            L_clay_total_m   REAL,
            su_avg_clay_kPa  REAL,
            sigma_avg_clay_kPa REAL,
            ts               TEXT NOT NULL,
            PRIMARY KEY (bh_name, pile_type, L_m, method)
        )
        """)
        # Migrate existing tables that lack the 3 common-data columns
        for _col, _type in (
            ("L_clay_total_m",      "REAL"),
            ("su_avg_clay_kPa",     "REAL"),
            ("sigma_avg_clay_kPa",  "REAL"),
        ):
            try:
                con.execute(f"ALTER TABLE ke_sw_nt2_compare ADD COLUMN {_col} {_type}")
            except Exception:
                pass  # column already exists
        con.commit()


def save_nt2_compare_to_db(
    bh_name: str,
    pile_type: str,
    L_m: float,
    all_result: dict,
    db_path: Path = DB_PATH,
) -> None:
    """Lưu kết quả 5 phương pháp NT2 vào ke_sw_nt2_compare (INSERT OR REPLACE)."""
    create_nt2_compare_table(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    common = all_result.get("common", {})
    W_kN             = common.get("W_kN", 0.0)
    L_clay_total_m   = common.get("L_clay_total_m")
    su_avg_clay_kPa  = common.get("su_avg_clay_kPa")
    sigma_avg_clay   = common.get("sigma_avg_clay_kPa")
    rows = []
    for method in ("auto", "alpha", "beta", "lambda", "SPT"):
        m = all_result.get(method, {})
        rows.append((
            bh_name, pile_type, float(L_m), method,
            m.get("Rs_kN"), m.get("Rp_kN"), m.get("RR_kN"),
            W_kN, m.get("ratio"), m.get("phi_stat"), m.get("result"),
            L_clay_total_m, su_avg_clay_kPa, sigma_avg_clay,
            now,
        ))
    with sqlite3.connect(str(db_path), timeout=30) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executemany("""
            INSERT OR REPLACE INTO ke_sw_nt2_compare
            (bh_name, pile_type, L_m, method,
             Rs_kN, Rp_kN, RR_kN, W_kN, ratio, phi_stat, result,
             L_clay_total_m, su_avg_clay_kPa, sigma_avg_clay_kPa, ts)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        con.commit()


def load_nt2_compare_from_db(
    bh_name: str,
    pile_type: str,
    L_m: float,
    db_path: Path = DB_PATH,
) -> dict | None:
    """Đọc 5 phương pháp NT2 từ ke_sw_nt2_compare.
    Trả về dict cùng format với calc_nt2_all_methods, hoặc None nếu chưa đủ.
    Không ghi DB (tránh lock trên Google Drive) — trả None nếu bảng chưa tồn tại.
    """
    try:
        with sqlite3.connect(str(db_path), timeout=10) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute("""
                SELECT * FROM ke_sw_nt2_compare
                WHERE bh_name=? AND pile_type=? AND L_m=?
            """, (bh_name, pile_type, float(L_m))).fetchall()
    except Exception:
        return None  # bảng chưa tồn tại hoặc DB bận — sẽ tính lại
    found = {dict(r)["method"]: dict(r) for r in rows}
    if not all(m in found for m in ("auto", "alpha", "beta", "lambda", "SPT")):
        return None
    _auto_row = found["auto"]
    out: dict = {"common": {
        "pile_name":           pile_type,
        "L_design_m":          float(L_m),
        "W_kN":                _auto_row.get("W_kN", 0.0),
        "L_clay_total_m":      _auto_row.get("L_clay_total_m", 0.0),
        "su_avg_clay_kPa":     _auto_row.get("su_avg_clay_kPa", 0.0),
        "sigma_avg_clay_kPa":  _auto_row.get("sigma_avg_clay_kPa", 0.0),
    }}
    for method in ("auto", "alpha", "beta", "lambda", "SPT"):
        r = found[method]
        out[method] = {
            "Rs_kN":    r.get("Rs_kN"),
            "Rp_kN":    r.get("Rp_kN"),
            "RR_kN":    r.get("RR_kN"),
            "ratio":    r.get("ratio"),
            "phi_stat": r.get("phi_stat"),
            "result":   r.get("result"),
        }
    return out


# ── Public helper cho app ─────────────────────────────────────────────────────
def calc_nt_for_bh(
    bh_name: str,
    Z_m: float,
    D_bottom_soft_m: float,
    pile_name: str,
    L_design_m: float,
    db_path: Path = DB_PATH,
    sw_json_path: Path = SW_JSON,
    prefer_input: bool = False,
) -> tuple[dict, dict]:
    """
    Tính NT1 + NT2 cho một HK với pile/L_design tùy chọn (dùng trong app).

    Mặc định: Z_m và D_bottom_soft_m được ghi đè bằng giá trị từ SQLite
              (đảm bảo nhất quán với dữ liệu khảo sát thực).

    Khi `prefer_input=True`: TÔN TRỌNG Z_m và D_bottom_soft_m do caller truyền vào,
                              KHÔNG đọc DB. Dùng cho kịch bản user chỉnh tay trong
                              UI (vd: bảng Mục B của app Kè SW cho phép edit Z + H1).
    """
    catalog = _load_catalog(sw_json_path)
    if pile_name not in catalog:
        pile_name = "SW-840"
    pile = catalog[pile_name]

    if not prefer_input:
        Z_db = _get_bh_Z_m(bh_name, db_path)
        if Z_db is not None:
            Z_m = Z_db

        D_db, _ = _get_D_bottom_soft(bh_name, db_path)
        if D_db > 0:
            D_bottom_soft_m = D_db

    nt1 = calc_nt1(bh_name, Z_m, D_bottom_soft_m, pile_name, L_design_m)
    nt2 = calc_nt2_layers(bh_name, Z_m, pile_name, pile, L_design_m, db_path=db_path)
    return nt1, nt2


# ── __main__ ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Tính NT1/NT2 chi tiết (số liệu từ SQLite) cho 7 HK trên tuyến kè SW ...\n")
    results = calc_all_alignment_hks()

    print("\n── Kết quả ─────────────────────────────────────────────────────────────")
    for r in results:
        n1 = r["nt1"]; n2 = r["nt2"]
        print(
            f"  {r['bh_name']:12s}  "
            f"Z={r['Z_m']:+.3f}m[{r['Z_source'][:3]}]  "
            f"D_bot={n1['D_bottom_soft_m']:.1f}m[{r['D_source'][:3]}]  "
            f"NT1:{n1['L_req_m']:.1f}m margin={n1['margin_m']:+.1f}m [{n1['result']}]  "
            f"NT2: Rs={n2['Rs_kN']:.0f} Rp={n2['Rp_kN']:.0f} "
            f"RR={n2['RR_kN']:.0f} W={n2['W_kN']:.0f} ratio={n2['ratio']:.2f} [{n2['result']}]"
        )
        if n2["warnings"]:
            for w in n2["warnings"]:
                print(f"    *** CẢNH BÁO: {w}")

    out_json = _ROOT / "data" / "ke_sw_nt_results.json"
    save_nt_json(results, out_json)
    save_nt_results(results)
    print(f"\nLưu JSON: {out_json}")
    print("Lưu SQLite: ke_sw_nt_detail + ke_sw_nt2_layers")
    print("Xong.")
