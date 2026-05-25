"""
soft_soil_calc.py — Tính thông số mô hình Soft Soil (PLAXIS) cho dự án TTHC.

Nguồn: PLAXIS Material Models Manual Chapter 10.
Tài liệu kỹ thuật: 56-soft-soil-model-plaxis.md

Công thức:
  λ* = Cc / (2.303 × (1+e0))
  κ* = 2×Cs / (2.303 × (1+e0))   [×2 = PLAXIS K0=1 convention]
  K0_nc = 1 − sin(φ')             [Jaky]
  M_approx = 3.0 − 2.8 × K0_nc   [Eq. 235]
  M_exact  = Eq. 234 (Brinkgreve 1994)
  OCR = PC / σ'v0  tại giữa lớp
  POP = PC − σ'v0

Thứ tự ưu tiên Cc/Cs:
  1. lab_tests HK hiện tại (AVG trong lớp)
  2. lab_tests HK gần nhất cùng zone + cùng symbol_tcvn
  3. Cs = 0.15 × Cc nếu không có Cs
  4. Không có Cc → bỏ qua lớp này (ghi None + warning)

PA2 per zone:
  bh_name = 'KE_PA2' / 'BXN_PA2' / 'NHC_PA2'
  Trung bình theo trọng số chiều dày tất cả HK selected trong zone.

Chạy:
  python scripts/soft_soil_calc.py
"""

from __future__ import annotations
import sys, sqlite3, math
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

_ROOT = Path(__file__).parent.parent
_DB   = _ROOT / "data" / "TTHC.sqlite"

_GWT_DEPTH_M = 0.0   # mực nước ngầm = mặt đất (z=0)
_GAMMA_W     = 10.0  # kN/m³
_NU_UR       = 0.15  # Poisson dỡ tải mặc định
_CS_CC_RATIO = 0.15  # Cs = 0.15 × Cc khi không đo

# Lớp đất yếu tham gia tính toán Soft Soil
_SOFT_SYMBOLS = frozenset(["1", "1b", "2", "2b", "XMD"])


# ──────────────────────────────────────────────────────────────────
# 1. DB HELPERS
# ──────────────────────────────────────────────────────────────────

def _create_table(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS soft_soil_params (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            bh_name      TEXT NOT NULL,
            pa           TEXT NOT NULL DEFAULT 'BH',  -- 'BH' | 'PA2'
            symbol       TEXT NOT NULL,
            depth_top_m  REAL,
            depth_bot_m  REAL,
            H_i_m        REAL,
            e0           REAL,
            Cc           REAL,
            Cs           REAL,
            phi_deg      REAL,
            c_kPa        REAL,
            sigma_v0_kPa REAL,
            PC_kPa       REAL,
            OCR          REAL,
            POP_kPa      REAL,
            lambda_star  REAL,
            kappa_star   REAL,
            nu_ur        REAL DEFAULT 0.15,
            K0_nc        REAL,
            M            REAL,
            M_exact      REAL,
            cc_source    TEXT,
            phi_source   TEXT,
            Cs_inferred  INTEGER DEFAULT 0,
            updated_at   TEXT,
            notes        TEXT,
            UNIQUE(bh_name, pa, symbol)
        )
    """)


def _zone_of(bh_name: str) -> str:
    for prefix in ("KE", "BXN", "NHC"):
        if bh_name.startswith(prefix):
            return prefix
    return "?"


# ──────────────────────────────────────────────────────────────────
# 2. SOIL PARAMETER LOOKUP
# ──────────────────────────────────────────────────────────────────

def _get_lab_for_layer(
    bh_id: int, _symbol: str, depth_top: float, depth_bot: float,
    con: sqlite3.Connection
) -> dict | None:
    """
    Trung bình Cc, Cs, e0, phi_deg, c_kPa, PC_kPa từ lab_tests trong lớp.
    Match theo độ sâu (depth_from_m trong [depth_top, depth_bot)).
    """
    row = con.execute("""
        SELECT
            AVG(CASE WHEN Cc IS NOT NULL AND Cc > 0 THEN Cc END)                   avg_Cc,
            AVG(CASE WHEN Cs IS NOT NULL AND Cs > 0 THEN Cs END)                   avg_Cs,
            AVG(CASE WHEN e0 IS NOT NULL AND e0 > 0 THEN e0 END)                   avg_e0,
            AVG(CASE WHEN phi_deg IS NOT NULL AND phi_deg > 0 THEN phi_deg END)     avg_phi,
            AVG(CASE WHEN c_kPa IS NOT NULL AND c_kPa >= 0 THEN c_kPa END)         avg_c,
            AVG(CASE WHEN PC_kPa IS NOT NULL AND PC_kPa > 0 THEN PC_kPa END)       avg_PC,
            COUNT(*) n
        FROM lab_tests
        WHERE borehole_id = ?
          AND depth_from_m >= ? AND depth_from_m < ?
    """, (bh_id, depth_top, depth_bot)).fetchone()
    if not row or not row["n"]:
        return None
    return dict(row)


def _nearest_bh_lab(
    bh_name: str, bh_x: float | None, bh_y: float | None,
    zone: str, symbol: str, field: str, con: sqlite3.Connection,
) -> tuple[float | None, str]:
    """
    HK gần nhất cùng zone có dữ liệu `field` cho lớp tương ứng với `symbol`.
    Match bằng cách JOIN layers WHERE layers.symbol = symbol + lab depth in layer.
    Trả về (value, source_label).
    """
    if bh_x is None or bh_y is None:
        return None, "không có tọa độ"

    rows = con.execute(f"""
        SELECT b.name, b.x_coord_m, b.y_coord_m,
               AVG(l.{field}) avg_val
        FROM boreholes b
        JOIN layers ly ON ly.borehole_id = b.id AND ly.symbol = ?
        JOIN lab_tests l ON l.borehole_id = b.id
          AND l.depth_from_m >= ly.depth_top_m
          AND l.depth_from_m < ly.depth_bot_m
        WHERE b.name LIKE ? AND b.name != ?
          AND l.{field} IS NOT NULL AND l.{field} > 0
        GROUP BY b.name
    """, (symbol, zone + "-%", bh_name)).fetchall()

    best_val, best_name, best_dist = None, None, float("inf")
    for r in rows:
        if r["x_coord_m"] is None or r["y_coord_m"] is None:
            continue
        d = math.hypot(float(r["x_coord_m"]) - bh_x, float(r["y_coord_m"]) - bh_y)
        if d < best_dist:
            best_dist = d
            best_val  = float(r["avg_val"])
            best_name = r["name"]

    if best_val:
        return best_val, f"fallback:{best_name}(d={best_dist:.0f}m)"
    return None, "không tìm thấy HK gần"


# ──────────────────────────────────────────────────────────────────
# 3. SOFT SOIL FORMULAS
# ──────────────────────────────────────────────────────────────────

def _lambda_star(Cc: float, e0: float) -> float:
    return Cc / (2.303 * (1.0 + e0))


def _kappa_star(Cs: float, e0: float) -> float:
    return 2.0 * Cs / (2.303 * (1.0 + e0))


def _K0_nc(phi_deg: float) -> float:
    return 1.0 - math.sin(math.radians(phi_deg))


def _M_approx(K0_nc: float) -> float:
    return 3.0 - 2.8 * K0_nc


def _M_exact(K0_nc: float, nu_ur: float, lam: float, kap: float) -> float:
    """Eq. 234 Brinkgreve (1994) — nghiệm M từ K0_nc, νur, λ*/κ*."""
    if kap <= 0 or lam <= 0:
        return _M_approx(K0_nc)
    ratio = lam / kap
    num  = 3.0 * (3.0 - K0_nc)**2 * (1.0 - 2.0*nu_ur) * (ratio - 1.0)
    den  = (1.0 + 2.0*K0_nc)**2 * (1.0 - 2.0*nu_ur) * ratio - (3.0 - K0_nc) * (1.0 + nu_ur)
    if den <= 0:
        return _M_approx(K0_nc)
    M2 = num / den
    if M2 <= 0:
        return _M_approx(K0_nc)
    return math.sqrt(M2)


def _sigma_v0_at_mid(layers_above: list[dict], gamma_i: float, H_i: float,
                     gwt_depth_m: float = _GWT_DEPTH_M) -> float:
    """
    Ứng suất hữu hiệu thẳng đứng tại giữa lớp i.
    layers_above: list of {"depth_top_m", "depth_bot_m", "gamma_kNm3"} cho các lớp phía trên.
    gamma_i: dung trọng bão hoà lớp i.
    H_i: chiều dày lớp i.
    gwt_depth_m: độ sâu MNN (0 = mặt đất).
    """
    sigma = 0.0
    for lyr in layers_above:
        top_lyr = float(lyr["depth_top_m"])
        bot_lyr = float(lyr["depth_bot_m"])
        gamma   = float(lyr.get("gamma_kNm3") or 16.0)
        H       = bot_lyr - top_lyr
        if bot_lyr <= gwt_depth_m:
            sigma += gamma * H
        elif top_lyr >= gwt_depth_m:
            sigma += (gamma - _GAMMA_W) * H
        else:
            above_gwt = gwt_depth_m - top_lyr
            below_gwt = bot_lyr - gwt_depth_m
            sigma += gamma * above_gwt + (gamma - _GAMMA_W) * below_gwt

    # Nửa lớp i
    mid_top  = layers_above[-1]["depth_bot_m"] if layers_above else 0.0
    mid_bot  = mid_top + H_i
    mid_depth = (mid_top + mid_bot) / 2.0

    if mid_depth <= gwt_depth_m:
        sigma += gamma_i * H_i / 2.0
    elif mid_top >= gwt_depth_m:
        sigma += (gamma_i - _GAMMA_W) * H_i / 2.0
    else:
        above = gwt_depth_m - mid_top
        below = H_i / 2.0 - max(0, gwt_depth_m - mid_top)
        sigma += gamma_i * above + (gamma_i - _GAMMA_W) * below

    return max(sigma, 1.0)  # tránh chia cho 0


# ──────────────────────────────────────────────────────────────────
# 4. PER-BH COMPUTATION
# ──────────────────────────────────────────────────────────────────

def _compute_bh(bh_name: str, con: sqlite3.Connection,
                verbose: bool = True) -> list[dict]:
    """
    Tính thông số Soft Soil cho tất cả lớp mềm trong 1 HK.
    Trả về list[dict] — mỗi dict = 1 lớp.
    """
    zone = _zone_of(bh_name)
    bh_row = con.execute(
        "SELECT id, x_coord_m, y_coord_m, elevation_m FROM boreholes WHERE name=?",
        (bh_name,)
    ).fetchone()
    if not bh_row:
        return []

    bh_id = bh_row["id"]
    bh_x  = float(bh_row["x_coord_m"]) if bh_row["x_coord_m"] else None
    bh_y  = float(bh_row["y_coord_m"]) if bh_row["y_coord_m"] else None

    # Lấy tất cả lớp đất (kể cả không soft) để tính σ'v0
    all_lyrs = con.execute("""
        SELECT symbol, depth_top_m, depth_bot_m,
               COALESCE(thickness_m, depth_bot_m - depth_top_m) H_i,
               description
        FROM layers WHERE borehole_id=? ORDER BY depth_top_m
    """, (bh_id,)).fetchall()

    # Lấy dung trọng từ lab_tests per lớp
    def _avg_gamma(sym: str, top: float, bot: float) -> float:
        r = con.execute("""
            SELECT AVG(gamma_kNm3) FROM lab_tests
            WHERE borehole_id=? AND symbol_tcvn=?
              AND depth_from_m >= ? AND depth_from_m < ?
              AND gamma_kNm3 IS NOT NULL AND gamma_kNm3 > 0
        """, (bh_id, sym, top, bot)).fetchone()
        if r and r[0]:
            return float(r[0])
        return 16.0  # default safe

    results = []
    layers_above = []

    for lyr in all_lyrs:
        sym  = lyr["symbol"] or ""
        top  = float(lyr["depth_top_m"])
        bot  = float(lyr["depth_bot_m"])
        H_i  = float(lyr["H_i"] or (bot - top))
        if H_i <= 0:
            layers_above.append({"depth_top_m": top, "depth_bot_m": bot,
                                  "gamma_kNm3": 16.0})
            continue

        gamma_i = _avg_gamma(sym, top, bot)
        sigma_v0 = _sigma_v0_at_mid(layers_above, gamma_i, H_i)

        if sym not in _SOFT_SYMBOLS:
            layers_above.append({"depth_top_m": top, "depth_bot_m": bot,
                                  "gamma_kNm3": gamma_i})
            continue

        # ---------- Lớp mềm ----------
        warnings_list: list[str] = []

        # 1. Cc, Cs, e0, phi, c, PC từ chính HK
        lab = _get_lab_for_layer(bh_id, sym, top, bot, con)

        Cc     = float(lab["avg_Cc"])  if lab and lab["avg_Cc"]  else None
        Cs     = float(lab["avg_Cs"])  if lab and lab["avg_Cs"]  else None
        e0     = float(lab["avg_e0"])  if lab and lab["avg_e0"]  else None
        phi    = float(lab["avg_phi"]) if lab and lab["avg_phi"] else None
        c      = float(lab["avg_c"])   if lab and lab["avg_c"]   is not None else 0.0
        PC     = float(lab["avg_PC"])  if lab and lab["avg_PC"]  else None

        cc_source  = "lab"
        phi_source = "lab"

        # 2. Fallback Cc, e0, phi
        if Cc is None:
            Cc_fb, cc_src = _nearest_bh_lab(bh_name, bh_x, bh_y, zone, sym, "Cc", con)
            if Cc_fb:
                Cc = Cc_fb; cc_source = cc_src
                warnings_list.append(f"Lớp {sym}: Cc lấy từ {cc_src}")

        if e0 is None:
            e0_fb, _ = _nearest_bh_lab(bh_name, bh_x, bh_y, zone, sym, "e0", con)
            if e0_fb:
                e0 = e0_fb
            else:
                e0 = 1.0
                warnings_list.append(f"Lớp {sym}: e0 dùng mặc định 1.0")

        if phi is None:
            phi_fb, phi_src = _nearest_bh_lab(bh_name, bh_x, bh_y, zone, sym, "phi_deg", con)
            if phi_fb:
                phi = phi_fb; phi_source = phi_src
                warnings_list.append(f"Lớp {sym}: phi lấy từ {phi_src}")
            else:
                phi = 15.0
                phi_source = "default 15°"
                warnings_list.append(f"Lớp {sym}: phi dùng mặc định 15°")

        if c is None:
            c = 0.0

        # 3. Cs fallback
        Cs_inferred = 0
        if Cs is None and Cc is not None:
            Cs = _CS_CC_RATIO * Cc
            Cs_inferred = 1
            warnings_list.append(f"Lớp {sym}: Cs = 0.15×Cc = {Cs:.4f} (suy diễn)")

        # 4. PC fallback: nếu không có PC → dùng OCR = 1 (NC)
        if PC is None:
            PC = sigma_v0
            warnings_list.append(f"Lớp {sym}: PC không có → giả định NC (OCR=1)")

        # 5. Tính thông số Soft Soil
        if Cc is None:
            warnings_list.append(f"Lớp {sym}: KHÔNG có Cc — bỏ qua lớp này")
            layers_above.append({"depth_top_m": top, "depth_bot_m": bot, "gamma_kNm3": gamma_i})
            continue

        lam  = _lambda_star(Cc, e0)
        kap  = _kappa_star(Cs, e0) if Cs else None
        K0   = _K0_nc(phi)
        M_ap = _M_approx(K0)
        M_ex = _M_exact(K0, _NU_UR, lam, kap) if kap else M_ap
        OCR  = PC / sigma_v0
        POP  = PC - sigma_v0

        row = {
            "bh_name":     bh_name,
            "pa":          "BH",
            "symbol":      sym,
            "depth_top_m": round(top, 2),
            "depth_bot_m": round(bot, 2),
            "H_i_m":       round(H_i, 2),
            "e0":          round(e0, 3),
            "Cc":          round(Cc, 4),
            "Cs":          round(Cs, 4) if Cs else None,
            "phi_deg":     round(phi, 2),
            "c_kPa":       round(c, 2),
            "sigma_v0_kPa": round(sigma_v0, 2),
            "PC_kPa":      round(PC, 2),
            "OCR":         round(OCR, 3),
            "POP_kPa":     round(POP, 2),
            "lambda_star": round(lam, 5),
            "kappa_star":  round(kap, 5) if kap else None,
            "nu_ur":       _NU_UR,
            "K0_nc":       round(K0, 4),
            "M":           round(M_ap, 4),
            "M_exact":     round(M_ex, 4),
            "cc_source":   cc_source,
            "phi_source":  phi_source,
            "Cs_inferred": Cs_inferred,
            "notes":       " | ".join(warnings_list) if warnings_list else None,
        }
        results.append(row)

        if verbose:
            src_flag = f"[{cc_source}]" if cc_source != "lab" else ""
            kap_str = f"{kap:.4f}" if kap else "0.0000"
            print(f"    {sym:4s} z={top:.1f}-{bot:.1f}m  lam*={lam:.4f}  kap*={kap_str}"
                  f"  phi={phi:.1f}  OCR={OCR:.2f}  M={M_ap:.3f} {src_flag}")
            for w in warnings_list:
                print(f"      ! {w}")

        layers_above.append({"depth_top_m": top, "depth_bot_m": bot, "gamma_kNm3": gamma_i})

    return results


# ──────────────────────────────────────────────────────────────────
# 5. ZONE PA2 AGGREGATION
# ──────────────────────────────────────────────────────────────────

def _compute_pa2_zone(zone: str, rows_all: list[dict]) -> list[dict]:
    """
    Tổng hợp thông số Soft Soil đại diện cho zone (PA2).
    Trung bình theo trọng số chiều dày per symbol.
    """
    from collections import defaultdict
    by_sym: dict[str, list[dict]] = defaultdict(list)
    for r in rows_all:
        if _zone_of(r["bh_name"]) == zone:
            by_sym[r["symbol"]].append(r)

    pa2_rows = []
    bh_pa2 = f"{zone}_PA2"
    for sym, layers in by_sym.items():
        total_H = sum(r["H_i_m"] for r in layers if r["H_i_m"])
        if total_H <= 0:
            continue

        def _wavg(field: str) -> float | None:
            vals = [(r.get(field), r["H_i_m"]) for r in layers
                    if r.get(field) is not None]
            if not vals:
                return None
            return sum(v * h for v, h in vals) / sum(h for _, h in vals)

        e0   = _wavg("e0") or 1.0
        Cc   = _wavg("Cc")
        phi  = _wavg("phi_deg") or 15.0
        c    = _wavg("c_kPa") or 0.0
        PC   = _wavg("PC_kPa")
        sv0  = _wavg("sigma_v0_kPa") or 10.0

        if Cc is None:
            continue

        # Recalculate params from weighted-avg inputs
        Cs_val   = _wavg("Cs")
        lam      = _lambda_star(Cc, e0)
        kap      = _kappa_star(Cs_val, e0) if Cs_val else None
        K0       = _K0_nc(phi)
        M_ap     = _M_approx(K0)
        M_ex     = _M_exact(K0, _NU_UR, lam, kap) if kap else M_ap
        OCR      = (PC / sv0) if PC else 1.0
        POP      = (PC - sv0) if PC else 0.0
        Cs_inf   = 1 if any(r["Cs_inferred"] for r in layers) else 0

        pa2_rows.append({
            "bh_name":     bh_pa2,
            "pa":          "PA2",
            "symbol":      sym,
            "depth_top_m": round(min(r["depth_top_m"] for r in layers), 2),
            "depth_bot_m": round(max(r["depth_bot_m"] for r in layers), 2),
            "H_i_m":       round(total_H, 2),
            "e0":          round(e0, 3),
            "Cc":          round(Cc, 4),
            "Cs":          round(Cs_val, 4) if Cs_val else None,
            "phi_deg":     round(phi, 2),
            "c_kPa":       round(c, 2),
            "sigma_v0_kPa": round(sv0, 2),
            "PC_kPa":      round(PC, 2) if PC else None,
            "OCR":         round(OCR, 3),
            "POP_kPa":     round(POP, 2),
            "lambda_star": round(lam, 5),
            "kappa_star":  round(kap, 5) if kap else None,
            "nu_ur":       _NU_UR,
            "K0_nc":       round(K0, 4),
            "M":           round(M_ap, 4),
            "M_exact":     round(M_ex, 4),
            "cc_source":   "zone_avg",
            "phi_source":  "zone_avg",
            "Cs_inferred": Cs_inf,
            "notes":       f"PA2 đại diện zone {zone} — {len(layers)} lớp từ {len(set(r['bh_name'] for r in layers))} HK",
        })

    return pa2_rows


# ──────────────────────────────────────────────────────────────────
# 6. BATCH RUN + SAVE
# ──────────────────────────────────────────────────────────────────

def run_soft_soil_batch(db_path: Path = _DB, verbose: bool = True) -> list[dict]:
    """
    Tính thông số Soft Soil cho tất cả HK selected + PA2 per zone.
    Lưu vào bảng soft_soil_params.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_results: list[dict] = []

    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        _create_table(con)

        # Lấy danh sách HK selected
        bhs = con.execute("""
            SELECT t.bh_name
            FROM tvtk_bh_cdm t
            WHERE t.selected = 1 AND t.H_soft_m > 0
            ORDER BY t.bh_name
        """).fetchall()

        if verbose:
            print(f"=== Soft Soil batch: {len(bhs)} HK ===")

        for bh_row in bhs:
            bh_name = bh_row["bh_name"]
            if verbose:
                print(f"\n{bh_name}:")
            rows = _compute_bh(bh_name, con, verbose=verbose)
            for r in rows:
                r["updated_at"] = now
                con.execute("""
                    INSERT INTO soft_soil_params
                        (bh_name, pa, symbol,
                         depth_top_m, depth_bot_m, H_i_m,
                         e0, Cc, Cs, phi_deg, c_kPa,
                         sigma_v0_kPa, PC_kPa, OCR, POP_kPa,
                         lambda_star, kappa_star, nu_ur,
                         K0_nc, M, M_exact,
                         cc_source, phi_source, Cs_inferred,
                         updated_at, notes)
                    VALUES (:bh_name,:pa,:symbol,
                            :depth_top_m,:depth_bot_m,:H_i_m,
                            :e0,:Cc,:Cs,:phi_deg,:c_kPa,
                            :sigma_v0_kPa,:PC_kPa,:OCR,:POP_kPa,
                            :lambda_star,:kappa_star,:nu_ur,
                            :K0_nc,:M,:M_exact,
                            :cc_source,:phi_source,:Cs_inferred,
                            :updated_at,:notes)
                    ON CONFLICT(bh_name, pa, symbol) DO UPDATE SET
                        depth_top_m=excluded.depth_top_m,
                        depth_bot_m=excluded.depth_bot_m,
                        H_i_m=excluded.H_i_m,
                        e0=excluded.e0, Cc=excluded.Cc, Cs=excluded.Cs,
                        phi_deg=excluded.phi_deg, c_kPa=excluded.c_kPa,
                        sigma_v0_kPa=excluded.sigma_v0_kPa,
                        PC_kPa=excluded.PC_kPa, OCR=excluded.OCR,
                        POP_kPa=excluded.POP_kPa,
                        lambda_star=excluded.lambda_star,
                        kappa_star=excluded.kappa_star,
                        nu_ur=excluded.nu_ur,
                        K0_nc=excluded.K0_nc, M=excluded.M, M_exact=excluded.M_exact,
                        cc_source=excluded.cc_source,
                        phi_source=excluded.phi_source,
                        Cs_inferred=excluded.Cs_inferred,
                        updated_at=excluded.updated_at,
                        notes=excluded.notes
                """, r)
            all_results.extend(rows)

        # PA2 per zone
        for zone in ("KE", "BXN", "NHC"):
            zone_rows = _compute_pa2_zone(zone, all_results)
            if verbose and zone_rows:
                print(f"\n{zone}_PA2 ({len(zone_rows)} ký hiệu lớp):")
            for r in zone_rows:
                r["updated_at"] = now
                if verbose:
                    print(f"    {r['symbol']:4s} λ*={r['lambda_star']:.4f}  "
                          f"κ*={r.get('kappa_star') or 0:.4f}  "
                          f"φ={r['phi_deg']:.1f}°  OCR={r['OCR']:.2f}  M={r['M']:.3f}")
                con.execute("""
                    INSERT INTO soft_soil_params
                        (bh_name, pa, symbol,
                         depth_top_m, depth_bot_m, H_i_m,
                         e0, Cc, Cs, phi_deg, c_kPa,
                         sigma_v0_kPa, PC_kPa, OCR, POP_kPa,
                         lambda_star, kappa_star, nu_ur,
                         K0_nc, M, M_exact,
                         cc_source, phi_source, Cs_inferred,
                         updated_at, notes)
                    VALUES (:bh_name,:pa,:symbol,
                            :depth_top_m,:depth_bot_m,:H_i_m,
                            :e0,:Cc,:Cs,:phi_deg,:c_kPa,
                            :sigma_v0_kPa,:PC_kPa,:OCR,:POP_kPa,
                            :lambda_star,:kappa_star,:nu_ur,
                            :K0_nc,:M,:M_exact,
                            :cc_source,:phi_source,:Cs_inferred,
                            :updated_at,:notes)
                    ON CONFLICT(bh_name, pa, symbol) DO UPDATE SET
                        depth_top_m=excluded.depth_top_m,
                        depth_bot_m=excluded.depth_bot_m,
                        H_i_m=excluded.H_i_m,
                        e0=excluded.e0, Cc=excluded.Cc, Cs=excluded.Cs,
                        phi_deg=excluded.phi_deg, c_kPa=excluded.c_kPa,
                        sigma_v0_kPa=excluded.sigma_v0_kPa,
                        PC_kPa=excluded.PC_kPa, OCR=excluded.OCR,
                        POP_kPa=excluded.POP_kPa,
                        lambda_star=excluded.lambda_star,
                        kappa_star=excluded.kappa_star,
                        nu_ur=excluded.nu_ur,
                        K0_nc=excluded.K0_nc, M=excluded.M, M_exact=excluded.M_exact,
                        cc_source=excluded.cc_source,
                        phi_source=excluded.phi_source,
                        Cs_inferred=excluded.Cs_inferred,
                        updated_at=excluded.updated_at,
                        notes=excluded.notes
                """, r)
            all_results.extend(zone_rows)

        con.commit()
        try:
            con.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            pass

    return all_results


# ──────────────────────────────────────────────────────────────────
# 7. MAIN
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Tính thông số Soft Soil PLAXIS cho tất cả HK CDM ===")
    print(f"DB: {_DB}\n")

    results = run_soft_soil_batch(verbose=True)

    print(f"\nHoàn thành: {len(results)} lớp đã tính.")

    # Tóm tắt per zone
    con2 = sqlite3.connect(_DB)
    con2.row_factory = sqlite3.Row
    print("\n=== Tóm tắt PA2 per Zone ===")
    for zone in ("KE", "BXN", "NHC"):
        rows = con2.execute("""
            SELECT symbol,
                   ROUND(lambda_star, 4) lam,
                   ROUND(kappa_star,  4) kap,
                   ROUND(phi_deg,     1) phi,
                   ROUND(OCR,         2) ocr,
                   ROUND(M,           3) M,
                   H_i_m,
                   notes
            FROM soft_soil_params
            WHERE bh_name = ? AND pa = 'PA2'
            ORDER BY depth_top_m
        """, (f"{zone}_PA2",)).fetchall()
        if rows:
            print(f"\n  {zone} PA2:")
            print(f"  {'Lớp':6s} {'λ*':>8s} {'κ*':>8s} {'φ(°)':>6s} {'OCR':>6s} {'M':>6s}  H(m)")
            for r in rows:
                print(f"  {r['symbol']:6s} {r['lam']:8.4f} {r['kap']:8.4f} "
                      f"{r['phi']:6.1f} {r['ocr']:6.2f} {r['M']:6.3f}  {r['H_i_m']:.1f}")
    con2.close()
