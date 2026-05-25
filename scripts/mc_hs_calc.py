"""
mc_hs_calc.py — Tính thông số mô hình Mohr-Coulomb (MC), Hardening Soil (HS)
và Linear Elastic (LE) cho dự án TTHC.

PLAXIS model assignment per giai đoạn thiết kế:
  TKCS  → MC (tất cả lớp) — failure criterion đủ dùng, đơn giản nhất.
  TKBVT → HS (lớp 2/3/4/5 — cát + sét cứng) + SS (lớp 1/1b soft clay, xem soft_soil_calc.py)
           + LE (XMD — TCVN 9403 cho phép mô hình đàn hồi tuyến tính).

Nguồn dữ liệu:
  lab_tests  → E (Eoed từ a12), Cu, phi, c, e0, gamma
  spt_values → N_SPT → E50_ref cho lớp cát
  vane_shear_tests → Su → E50_ref cho lớp sét

Công thức chính:
  MC:  Eoed = (1+e0) / (a12 × 0.01)  [kPa]   (a12 in cm²/kgf)
       E_ref ≈ Eoed × 1.15            [kPa]   (ν=0.35 correction: (1-2ν²)/(1-ν))
       E_ref_Cu = 250 × Cu            [kPa]   khi không có a12

  HS:  E50_ref  = 500 × Cu     (sét mềm)
               = 600 × Cu     (sét dẻo — lớp 2 stiff)
               = 300 × N60    (cát, kPa — N60 SPT)
       Eoed_ref = Eoed từ lab  hoặc  2/3 × E50_ref
       Eur_ref  = 3 × E50_ref (sét)   |  5 × E50_ref (cát)
       m        = 1.0 (sét mềm) | 0.8 (sét cứng) | 0.5 (cát)
       pref     = 100 kPa
       Rf       = 0.9

  LE:  E_cdm = k × (qu_design / 2)    [kPa]  (k=100 theo TCVN 9403)
       ν_le  = 0.25

Thứ tự ưu tiên E/Cu/phi:
  1. Lab chính HK (AVG depth-range match)
  2. VST gần nhất cùng zone (cho Cu)
  3. HK gần nhất cùng zone (nearest-BH fallback)
  4. Default an toàn (cảnh báo)

Chạy:
  python scripts/mc_hs_calc.py
"""

from __future__ import annotations
import sys, sqlite3, math
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

_ROOT = Path(__file__).parent.parent
_DB   = _ROOT / "data" / "TTHC.sqlite"

_GAMMA_W     = 10.0   # kN/m³
_GWT_DEPTH_M = 0.0    # mực nước ngầm = mặt đất
_PREF_KPA    = 100.0  # áp suất tham chiếu PLAXIS
_RF_DEFAULT  = 0.9    # failure ratio HS

# ── Phân loại lớp đất ──────────────────────────────────────────────
# Lớp cát (dùng SPT-based E, m=0.5)
_SAND_SYMBOLS  = frozenset(["2a", "2b", "2c", "3", "5a", "5b", "5c", "F"])
# Lớp sét mềm/bùn (dùng Cu-based E, m=1.0, SS model TKBVT)
_SOFT_SYMBOLS  = frozenset(["1", "1b"])
# Lớp XMD — Linear Elastic (TCVN 9403)
_LE_SYMBOLS    = frozenset(["XMD"])
# Lớp sét cứng / sét dẻo (m=0.8, HS model TKBVT)
_STIFF_SYMBOLS = frozenset(["2", "4", "4b"])
# Tất cả symbol cần MC (= tất cả trừ XMD)
_ALL_MC        = _SOFT_SYMBOLS | _SAND_SYMBOLS | _STIFF_SYMBOLS | frozenset(["6", "QTT"])

# ── Hệ số k cho LE (CDM trụ) ───────────────────────────────────────
_K_CDM  = 100      # Ec = k × (qu_design/2), TCVN 9403
_QU_CDM = 800.0    # qu thiết kế mặc định (kPa) — đọc từ tvtk_cdm_config nếu có
_NU_LE  = 0.25


# ══════════════════════════════════════════════════════════════════
# 1. DB HELPERS
# ══════════════════════════════════════════════════════════════════

def _create_table(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS plaxis_mc_hs_params (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            bh_name          TEXT NOT NULL,
            pa               TEXT NOT NULL DEFAULT 'BH',
            symbol           TEXT NOT NULL,
            depth_top_m      REAL,
            depth_bot_m      REAL,
            H_i_m            REAL,
            -- Trọng lượng
            gamma_unsat_kNm3 REAL,
            gamma_sat_kNm3   REAL,
            -- MC model (TKCS — tất cả lớp trừ XMD)
            E_ref_kPa        REAL,   -- Young's modulus ≈ Eoed
            nu_mc            REAL,
            c_kPa            REAL,
            phi_deg          REAL,
            psi_deg          REAL,
            K0_mc            REAL,   -- Jaky: 1-sin(phi')
            -- HS model (TKBVT — lớp cát + sét cứng)
            E50_ref_kPa      REAL,
            Eoed_ref_kPa     REAL,
            Eur_ref_kPa      REAL,
            m_hs             REAL,
            pref_kPa         REAL DEFAULT 100.0,
            Rf               REAL DEFAULT 0.9,
            K0_nc_hs         REAL,
            -- LE model (TKBVT — XMD CDM)
            E_cdm_kPa        REAL,
            nu_le            REAL,
            -- Nguồn dữ liệu
            E_source         TEXT,
            c_source         TEXT,
            phi_source       TEXT,
            gamma_source     TEXT,
            notes            TEXT,
            updated_at       TEXT,
            UNIQUE(bh_name, pa, symbol)
        )
    """)


def _zone_of(bh_name: str) -> str:
    for p in ("KE", "BXN", "NHC"):
        if bh_name.startswith(p):
            return p
    return "?"


def _connect(db_path: Path = _DB) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


# ══════════════════════════════════════════════════════════════════
# 2. PARAMETER LOOKUP
# ══════════════════════════════════════════════════════════════════

def _get_lab_for_layer(
    bh_id: int, depth_top: float, depth_bot: float,
    con: sqlite3.Connection,
) -> dict | None:
    """Trung bình các thông số lab trong khoảng độ sâu lớp."""
    row = con.execute("""
        SELECT
            AVG(CASE WHEN e0 > 0           THEN e0           END) avg_e0,
            AVG(CASE WHEN gamma_kNm3 > 0   THEN gamma_kNm3   END) avg_gamma,
            AVG(CASE WHEN a12_cm2kgf > 0   THEN a12_cm2kgf   END) avg_a12,
            AVG(CASE WHEN Cu_UU_kPa > 0    THEN Cu_UU_kPa    END) avg_Cu,
            AVG(CASE WHEN phi_deg > 0      THEN phi_deg       END) avg_phi,
            AVG(CASE WHEN c_kPa >= 0       THEN c_kPa         END) avg_c,
            COUNT(*) n
        FROM lab_tests
        WHERE borehole_id = ?
          AND depth_from_m >= ? AND depth_from_m < ?
    """, (bh_id, depth_top, depth_bot)).fetchone()
    if row and row["n"] and row["n"] > 0:
        return dict(row)
    return None


def _get_spt_for_layer(
    bh_id: int, depth_top: float, depth_bot: float,
    con: sqlite3.Connection,
) -> float | None:
    """N trung bình trong lớp từ spt_values (cột N)."""
    row = con.execute("""
        SELECT AVG(N) avg_N
        FROM spt_values
        WHERE borehole_id = ?
          AND depth_m >= ? AND depth_m < ?
          AND N IS NOT NULL AND N > 0
    """, (bh_id, depth_top, depth_bot)).fetchone()
    if row and row["avg_N"]:
        return float(row["avg_N"])
    return None


def _get_vst_for_layer(
    bh_x: float | None, bh_y: float | None,
    depth_top: float, depth_bot: float,
    zone: str, con: sqlite3.Connection,
    max_dist_m: float = 150.0,
) -> float | None:
    """
    Su trung bình trong lớp từ vane_shear_tests — join qua vst_locations theo tọa độ.
    Lấy tất cả VST cùng zone trong phạm vi max_dist_m.
    """
    if bh_x is None or bh_y is None:
        return None
    # vst_locations có x_coord_m, y_coord_m; join vane_shear_tests qua vst_loc_id
    rows = con.execute("""
        SELECT vl.x_coord_m, vl.y_coord_m, vt.depth_m, vt.Su_kPa
        FROM vst_locations vl
        JOIN vane_shear_tests vt ON vt.vst_loc_id = vl.id
        WHERE vl.name LIKE ?
          AND vt.depth_m >= ? AND vt.depth_m < ?
          AND vt.Su_kPa IS NOT NULL AND vt.Su_kPa > 0
    """, (zone + "-%", depth_top, depth_bot)).fetchall()

    vals = []
    for r in rows:
        if r["x_coord_m"] is None or r["y_coord_m"] is None:
            continue
        d = math.hypot(float(r["x_coord_m"]) - bh_x, float(r["y_coord_m"]) - bh_y)
        if d <= max_dist_m:
            vals.append(float(r["Su_kPa"]))
    return sum(vals) / len(vals) if vals else None


def _nearest_bh_field(
    bh_name: str, bh_x: float | None, bh_y: float | None,
    zone: str, symbol: str, field: str, con: sqlite3.Connection,
) -> tuple[float | None, str]:
    """HK gần nhất cùng zone có `field` cho cùng symbol (join layers → lab)."""
    if bh_x is None or bh_y is None:
        return None, "no_coords"
    rows = con.execute(f"""
        SELECT b.name, b.x_coord_m, b.y_coord_m,
               AVG(l.{field}) avg_val
        FROM boreholes b
        JOIN layers ly ON ly.borehole_id = b.id AND ly.symbol = ?
        JOIN lab_tests l ON l.borehole_id = b.id
          AND l.depth_from_m >= ly.depth_top_m
          AND l.depth_from_m <  ly.depth_bot_m
        WHERE b.name LIKE ? AND b.name != ?
          AND l.{field} IS NOT NULL AND l.{field} > 0
        GROUP BY b.name
    """, (symbol, zone + "-%", bh_name)).fetchall()

    best_val, best_name, best_dist = None, None, float("inf")
    for r in rows:
        if not r["x_coord_m"] or not r["y_coord_m"]:
            continue
        d = math.hypot(float(r["x_coord_m"]) - bh_x, float(r["y_coord_m"]) - bh_y)
        if d < best_dist:
            best_dist = d
            best_val  = float(r["avg_val"])
            best_name = r["name"]
    if best_val is not None:
        return best_val, f"fallback:{best_name}(d={best_dist:.0f}m)"
    return None, "not_found"


# ══════════════════════════════════════════════════════════════════
# 3. MC / HS / LE FORMULAS
# ══════════════════════════════════════════════════════════════════

def _Eoed_from_a12(a12_raw: float, e0: float) -> float:
    """
    Eoed (kPa) từ a12 (cm²/kgf, raw từ oedometer 1-2 kgf/cm²).
    a12_raw đã lưu trong lab_tests dưới tên a12_kPa_inv_e2 (raw, chưa nhân 0.01).
    Công thức: Eoed = (1+e0) / (a12 × 0.01)
    """
    if a12_raw <= 0:
        return 0.0
    return (1.0 + e0) / (a12_raw * 0.01)


def _E_from_Cu(Cu_kPa: float, factor: float = 250.0) -> float:
    """E_ref (kPa) từ Cu — Mesri-Olson correlation (mặc định 250×Cu cho sét mềm)."""
    return factor * Cu_kPa


def _E50_from_N(N60: float, factor: float = 300.0) -> float:
    """
    E50_ref (kPa) từ N60 — Bowles (1996) cho cát.
    factor: 200–500 × N, mặc định 300 (trung bình, bảo thủ).
    """
    return factor * N60


def _nu_by_symbol(symbol: str) -> float:
    """Poisson's ratio drained theo loại đất."""
    if symbol in _SOFT_SYMBOLS:
        return 0.35
    if symbol in _STIFF_SYMBOLS:
        return 0.30
    if symbol in _SAND_SYMBOLS:
        return 0.30
    return 0.30


def _psi_by_phi(phi_deg: float, symbol: str) -> float:
    """Góc giãn nở — 0 cho sét, phi-30 (≥0) cho cát chặt."""
    if symbol in _SOFT_SYMBOLS | _STIFF_SYMBOLS | _LE_SYMBOLS:
        return 0.0
    return max(0.0, phi_deg - 30.0)


def _m_by_symbol(symbol: str) -> float:
    """Power law m cho HS model."""
    if symbol in _SOFT_SYMBOLS:
        return 1.0
    if symbol in _STIFF_SYMBOLS:
        return 0.8
    if symbol in _SAND_SYMBOLS:
        return 0.5
    return 0.8


# ══════════════════════════════════════════════════════════════════
# 4. EFFECTIVE OVERBURDEN (cho K0)
# ══════════════════════════════════════════════════════════════════

def _sigma_v0_at_mid(
    layers_above: list[dict], gamma_i: float, H_i: float,
    gwt: float = _GWT_DEPTH_M,
) -> float:
    sigma = 0.0
    for lyr in layers_above:
        top = float(lyr["depth_top_m"])
        bot = float(lyr["depth_bot_m"])
        g   = float(lyr.get("gamma_kNm3") or 16.0)
        H   = bot - top
        if bot <= gwt:
            sigma += g * H
        elif top >= gwt:
            sigma += (g - _GAMMA_W) * H
        else:
            sigma += g * (gwt - top) + (g - _GAMMA_W) * (bot - gwt)
    # nửa lớp i
    mid_top = layers_above[-1]["depth_bot_m"] if layers_above else 0.0
    if mid_top >= gwt:
        sigma += (gamma_i - _GAMMA_W) * H_i / 2.0
    else:
        depth_mid = mid_top + H_i / 2.0
        if depth_mid <= gwt:
            sigma += gamma_i * H_i / 2.0
        else:
            sigma += gamma_i * (gwt - mid_top) + (gamma_i - _GAMMA_W) * (depth_mid - gwt)
    return max(sigma, 1.0)


# ══════════════════════════════════════════════════════════════════
# 5. PER-BH COMPUTATION
# ══════════════════════════════════════════════════════════════════

def _compute_bh(
    bh_name: str, con: sqlite3.Connection,
    qu_design_kPa: float = _QU_CDM, verbose: bool = True,
) -> list[dict]:
    """
    Tính MC + HS + LE params cho tất cả lớp của 1 HK.
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

    # Tất cả lớp (để tính σ'v0)
    all_lyrs = con.execute("""
        SELECT symbol, depth_top_m, depth_bot_m,
               COALESCE(thickness_m, depth_bot_m - depth_top_m) H_i
        FROM layers WHERE borehole_id=? ORDER BY depth_top_m
    """, (bh_id,)).fetchall()

    results      = []
    layers_above = []

    # Đọc qu_design từ tvtk_cdm_config nếu có
    try:
        cfg = con.execute(
            "SELECT qu_design_kPa FROM tvtk_cdm_config LIMIT 1"
        ).fetchone()
        if cfg and cfg[0]:
            qu_design_kPa = float(cfg[0])
    except Exception:
        pass

    for lyr in all_lyrs:
        sym = lyr["symbol"] or ""
        top = float(lyr["depth_top_m"])
        bot = float(lyr["depth_bot_m"])
        H_i = float(lyr["H_i"] or (bot - top))
        if H_i <= 0:
            layers_above.append({"depth_top_m": top, "depth_bot_m": bot,
                                  "gamma_kNm3": 16.0})
            continue

        # ── Lab data ──
        lab = _get_lab_for_layer(bh_id, top, bot, con)

        # Gamma
        gamma_raw = float(lab["avg_gamma"]) if lab and lab["avg_gamma"] else None
        gamma_i   = gamma_raw if gamma_raw and gamma_raw > 0 else 16.0
        gamma_src = "lab" if gamma_raw else "default(16.0)"

        # e0
        e0 = float(lab["avg_e0"]) if lab and lab["avg_e0"] else None
        if e0 is None:
            _, fb_src = _nearest_bh_field(bh_name, bh_x, bh_y, zone, sym, "e0", con)
            e0_fb, _ = _nearest_bh_field(bh_name, bh_x, bh_y, zone, sym, "e0", con)
            e0 = e0_fb or 1.0

        # phi, c — CU/UU lab, fallback HK gần nhất
        phi = float(lab["avg_phi"]) if lab and lab["avg_phi"] else None
        c   = float(lab["avg_c"])   if lab and lab["avg_c"] is not None else None
        phi_src = "lab"
        if phi is None:
            phi, phi_src = _nearest_bh_field(
                bh_name, bh_x, bh_y, zone, sym, "phi_deg", con)
        if c is None:
            c, _ = _nearest_bh_field(bh_name, bh_x, bh_y, zone, sym, "c_kPa", con)
        phi = float(phi) if phi else 0.0
        c   = float(c)   if c   else 0.0
        c_src = "lab" if (lab and lab["avg_c"] is not None) else "fallback/default"

        # a12 (compressibility, cm²/kgf)
        a12 = float(lab["avg_a12"]) if lab and lab["avg_a12"] else None

        # Cu từ UU hoặc VST
        Cu_lab  = float(lab["avg_Cu"]) if lab and lab["avg_Cu"] else None
        Cu_vst  = _get_vst_for_layer(bh_x, bh_y, top, bot, zone, con)
        Cu      = Cu_vst or Cu_lab      # VST ưu tiên
        Cu_src  = ("VST" if Cu_vst else ("lab_UU" if Cu_lab else "none"))

        # N_SPT
        N_spt = _get_spt_for_layer(bh_id, top, bot, con)

        notes_list: list[str] = []

        # ── LE (XMD) ──────────────────────────────────────────────
        if sym in _LE_SYMBOLS:
            E_cdm = _K_CDM * (qu_design_kPa / 2.0)
            rec = {
                "bh_name": bh_name, "pa": "BH", "symbol": sym,
                "depth_top_m": top, "depth_bot_m": bot, "H_i_m": H_i,
                "gamma_unsat_kNm3": gamma_i - _GAMMA_W,
                "gamma_sat_kNm3":   gamma_i,
                "E_ref_kPa": None, "nu_mc": None,
                "c_kPa": c, "phi_deg": phi, "psi_deg": 0.0, "K0_mc": None,
                "E50_ref_kPa": None, "Eoed_ref_kPa": None, "Eur_ref_kPa": None,
                "m_hs": None, "pref_kPa": None, "Rf": None, "K0_nc_hs": None,
                "E_cdm_kPa": round(E_cdm, 0),
                "nu_le": _NU_LE,
                "E_source": f"LE:k={_K_CDM}×qu/2(qu={qu_design_kPa:.0f}kPa)",
                "c_source": c_src, "phi_source": phi_src,
                "gamma_source": gamma_src,
                "notes": "; ".join(notes_list),
            }
            results.append(rec)
            layers_above.append({"depth_top_m": top, "depth_bot_m": bot,
                                  "gamma_kNm3": gamma_i})
            continue

        # ── Tính Eoed từ oedometer ──────────────────────────────
        Eoed = None
        E_src = "none"
        if a12 and a12 > 0 and e0 and e0 > 0:
            Eoed  = _Eoed_from_a12(a12, e0)
            E_src = f"lab_a12(e0={e0:.2f},a12={a12:.3f})"

        # ── MC E_ref ─────────────────────────────────────────────
        nu = _nu_by_symbol(sym)
        # Chuyển Eoed → E: E = Eoed × (1-2ν²)/(1-ν)
        # Xấp xỉ thực tế: E_ref ≈ Eoed × (1 - 2ν²)/(1-ν)
        conv = (1.0 - 2.0*nu**2) / (1.0 - nu) if nu < 1.0 else 1.0
        E_ref = None
        if Eoed and Eoed > 0:
            E_ref = Eoed * conv
            E_src = f"Eoed_lab(a12,e0)×{conv:.2f}"
        elif Cu and Cu > 0:
            factor = 250.0 if sym in _SOFT_SYMBOLS else 500.0
            E_ref  = _E_from_Cu(Cu, factor)
            E_src  = f"250×Cu({Cu_src},{Cu:.1f}kPa)"
        elif N_spt and N_spt > 0:
            E_ref  = _E50_from_N(N_spt, 300.0)
            E_src  = f"300×N_SPT({N_spt:.1f})"
        else:
            notes_list.append(f"Không có a12/Cu/N_SPT cho {sym}")

        K0 = 1.0 - math.sin(math.radians(phi)) if phi > 0 else 0.5
        psi = _psi_by_phi(phi, sym)

        # ── HS params ────────────────────────────────────────────
        E50  = None
        Eur  = None
        m_hs = _m_by_symbol(sym)
        K0nc = K0

        if sym in _SOFT_SYMBOLS:
            # Sét mềm: E50 = 500×Cu
            if Cu and Cu > 0:
                E50  = 500.0 * Cu
                Eur  = 3.0 * E50
            elif Eoed and Eoed > 0:
                E50  = Eoed * 0.8
                Eur  = 3.0 * E50

        elif sym in _STIFF_SYMBOLS:
            # Sét dẻo/cứng: E50 = 600×Cu
            if Cu and Cu > 0:
                E50  = 600.0 * Cu
                Eur  = 3.0 * E50
            elif Eoed and Eoed > 0:
                E50  = Eoed
                Eur  = 4.0 * E50

        elif sym in _SAND_SYMBOLS:
            # Cát: E50 = 300×N
            if N_spt and N_spt > 0:
                E50  = 300.0 * N_spt
                Eur  = 5.0 * E50
            elif Eoed and Eoed > 0:
                E50  = Eoed * 1.2
                Eur  = 5.0 * E50

        Eoed_hs = Eoed if (Eoed and Eoed > 0) else (E50 * 0.8 if E50 else None)

        rec = {
            "bh_name": bh_name, "pa": "BH", "symbol": sym,
            "depth_top_m": top, "depth_bot_m": bot, "H_i_m": H_i,
            "gamma_unsat_kNm3": round(gamma_i - _GAMMA_W, 2) if gamma_i > _GAMMA_W else round(gamma_i * 0.85, 2),
            "gamma_sat_kNm3":   round(gamma_i, 2),
            "E_ref_kPa":  round(E_ref, 0)    if E_ref  else None,
            "nu_mc":      round(nu, 2),
            "c_kPa":      round(c, 2),
            "phi_deg":    round(phi, 2),
            "psi_deg":    round(psi, 2),
            "K0_mc":      round(K0, 3),
            "E50_ref_kPa":  round(E50,      0) if E50      else None,
            "Eoed_ref_kPa": round(Eoed_hs,  0) if Eoed_hs  else None,
            "Eur_ref_kPa":  round(Eur,      0) if Eur       else None,
            "m_hs":       round(m_hs, 1),
            "pref_kPa":   _PREF_KPA,
            "Rf":         _RF_DEFAULT,
            "K0_nc_hs":   round(K0nc, 3),
            "E_cdm_kPa":  None,
            "nu_le":      None,
            "E_source":   E_src,
            "c_source":   c_src,
            "phi_source": phi_src,
            "gamma_source": gamma_src,
            "notes":      "; ".join(notes_list),
        }
        results.append(rec)
        layers_above.append({"depth_top_m": top, "depth_bot_m": bot,
                              "gamma_kNm3": gamma_i})

    if verbose:
        print(f"  {bh_name}: {len(results)} lớp")
    return results


# ══════════════════════════════════════════════════════════════════
# 6. PA2 — ZONE REPRESENTATIVE (weighted average by H_i)
# ══════════════════════════════════════════════════════════════════

def _compute_pa2_zone(
    zone: str, rows_all_bh: list[dict], verbose: bool = True,
) -> list[dict]:
    """
    PA2 per zone: trung bình theo trọng số chiều dày.
    rows_all_bh: danh sách tất cả rows MC/HS từ BH trong zone.
    """
    from collections import defaultdict
    by_sym: dict[str, list[dict]] = defaultdict(list)
    for r in rows_all_bh:
        by_sym[r["symbol"]].append(r)

    pa2_rows = []
    pa2_name = f"{zone}_PA2_MC"

    _num_fields = [
        "gamma_unsat_kNm3", "gamma_sat_kNm3",
        "E_ref_kPa", "nu_mc", "c_kPa", "phi_deg", "psi_deg", "K0_mc",
        "E50_ref_kPa", "Eoed_ref_kPa", "Eur_ref_kPa", "m_hs", "K0_nc_hs",
        "E_cdm_kPa",
    ]

    for sym, sym_rows in by_sym.items():
        total_H = sum(r["H_i_m"] for r in sym_rows if r["H_i_m"])
        if total_H <= 0:
            continue
        pa2 = {"bh_name": pa2_name, "pa": "PA2", "symbol": sym,
                "depth_top_m": None, "depth_bot_m": None, "H_i_m": total_H,
                "pref_kPa": _PREF_KPA, "Rf": _RF_DEFAULT,
                "nu_le": _NU_LE if sym in _LE_SYMBOLS else None,
                "E_source": f"PA2_wavg({len(sym_rows)}BH)",
                "c_source": "PA2", "phi_source": "PA2", "gamma_source": "PA2",
                "notes": f"PA2 zone {zone}, {len(sym_rows)} HK",
                }
        for f in _num_fields:
            vals  = [float(r[f]) for r in sym_rows if r.get(f) is not None]
            wts   = [float(r["H_i_m"]) for r in sym_rows if r.get(f) is not None]
            if vals:
                wavg = sum(v*w for v, w in zip(vals, wts)) / sum(wts)
                pa2[f] = round(wavg, 3)
            else:
                pa2[f] = None
        pa2_rows.append(pa2)

    if verbose:
        print(f"  PA2 {zone}: {len(pa2_rows)} symbols")
    return pa2_rows


# ══════════════════════════════════════════════════════════════════
# 7. BATCH RUN
# ══════════════════════════════════════════════════════════════════

def run_mc_hs_batch(db_path: Path = _DB, verbose: bool = True) -> int:
    """
    Tính MC + HS + LE params cho tất cả HK trong project.
    Upsert vào bảng plaxis_mc_hs_params.
    Trả về số lớp đã ghi.
    """
    con = _connect(db_path)
    _create_table(con)
    con.commit()

    # Tất cả HK có lớp đất (không kể HK meta)
    bhs = con.execute("""
        SELECT DISTINCT b.name
        FROM boreholes b
        JOIN layers l ON l.borehole_id = b.id
        ORDER BY b.name
    """).fetchall()

    ts = datetime.now().isoformat(timespec="seconds")

    # Per-zone rows để tính PA2
    zone_rows: dict[str, list[dict]] = {"KE": [], "BXN": [], "NHC": []}

    total_written = 0
    for bh in bhs:
        bh_name = bh["name"]
        rows = _compute_bh(bh_name, con, verbose=verbose)

        zone = _zone_of(bh_name)
        if zone in zone_rows:
            zone_rows[zone].extend(rows)

        for r in rows:
            con.execute("""
                INSERT INTO plaxis_mc_hs_params
                (bh_name, pa, symbol, depth_top_m, depth_bot_m, H_i_m,
                 gamma_unsat_kNm3, gamma_sat_kNm3,
                 E_ref_kPa, nu_mc, c_kPa, phi_deg, psi_deg, K0_mc,
                 E50_ref_kPa, Eoed_ref_kPa, Eur_ref_kPa, m_hs, pref_kPa, Rf, K0_nc_hs,
                 E_cdm_kPa, nu_le,
                 E_source, c_source, phi_source, gamma_source, notes, updated_at)
                VALUES
                (:bh_name, :pa, :symbol, :depth_top_m, :depth_bot_m, :H_i_m,
                 :gamma_unsat_kNm3, :gamma_sat_kNm3,
                 :E_ref_kPa, :nu_mc, :c_kPa, :phi_deg, :psi_deg, :K0_mc,
                 :E50_ref_kPa, :Eoed_ref_kPa, :Eur_ref_kPa, :m_hs, :pref_kPa, :Rf, :K0_nc_hs,
                 :E_cdm_kPa, :nu_le,
                 :E_source, :c_source, :phi_source, :gamma_source, :notes, :updated_at)
                ON CONFLICT(bh_name, pa, symbol) DO UPDATE SET
                  depth_top_m=excluded.depth_top_m, depth_bot_m=excluded.depth_bot_m,
                  H_i_m=excluded.H_i_m,
                  gamma_unsat_kNm3=excluded.gamma_unsat_kNm3,
                  gamma_sat_kNm3=excluded.gamma_sat_kNm3,
                  E_ref_kPa=excluded.E_ref_kPa, nu_mc=excluded.nu_mc,
                  c_kPa=excluded.c_kPa, phi_deg=excluded.phi_deg,
                  psi_deg=excluded.psi_deg, K0_mc=excluded.K0_mc,
                  E50_ref_kPa=excluded.E50_ref_kPa, Eoed_ref_kPa=excluded.Eoed_ref_kPa,
                  Eur_ref_kPa=excluded.Eur_ref_kPa, m_hs=excluded.m_hs,
                  pref_kPa=excluded.pref_kPa, Rf=excluded.Rf, K0_nc_hs=excluded.K0_nc_hs,
                  E_cdm_kPa=excluded.E_cdm_kPa, nu_le=excluded.nu_le,
                  E_source=excluded.E_source, c_source=excluded.c_source,
                  phi_source=excluded.phi_source, gamma_source=excluded.gamma_source,
                  notes=excluded.notes, updated_at=excluded.updated_at
            """, {**r, "updated_at": ts})
            total_written += 1

    con.commit()

    # PA2 per zone
    if verbose:
        print("\n── PA2 zone representatives ──")
    for zone, rows in zone_rows.items():
        if not rows:
            continue
        pa2_rows = _compute_pa2_zone(zone, rows, verbose=verbose)
        for r in pa2_rows:
            con.execute("""
                INSERT INTO plaxis_mc_hs_params
                (bh_name, pa, symbol, depth_top_m, depth_bot_m, H_i_m,
                 gamma_unsat_kNm3, gamma_sat_kNm3,
                 E_ref_kPa, nu_mc, c_kPa, phi_deg, psi_deg, K0_mc,
                 E50_ref_kPa, Eoed_ref_kPa, Eur_ref_kPa, m_hs, pref_kPa, Rf, K0_nc_hs,
                 E_cdm_kPa, nu_le,
                 E_source, c_source, phi_source, gamma_source, notes, updated_at)
                VALUES
                (:bh_name, :pa, :symbol, :depth_top_m, :depth_bot_m, :H_i_m,
                 :gamma_unsat_kNm3, :gamma_sat_kNm3,
                 :E_ref_kPa, :nu_mc, :c_kPa, :phi_deg, :psi_deg, :K0_mc,
                 :E50_ref_kPa, :Eoed_ref_kPa, :Eur_ref_kPa, :m_hs, :pref_kPa, :Rf, :K0_nc_hs,
                 :E_cdm_kPa, :nu_le,
                 :E_source, :c_source, :phi_source, :gamma_source, :notes, :updated_at)
                ON CONFLICT(bh_name, pa, symbol) DO UPDATE SET
                  H_i_m=excluded.H_i_m,
                  gamma_unsat_kNm3=excluded.gamma_unsat_kNm3,
                  gamma_sat_kNm3=excluded.gamma_sat_kNm3,
                  E_ref_kPa=excluded.E_ref_kPa, nu_mc=excluded.nu_mc,
                  c_kPa=excluded.c_kPa, phi_deg=excluded.phi_deg,
                  K0_mc=excluded.K0_mc,
                  E50_ref_kPa=excluded.E50_ref_kPa, Eoed_ref_kPa=excluded.Eoed_ref_kPa,
                  Eur_ref_kPa=excluded.Eur_ref_kPa, m_hs=excluded.m_hs,
                  K0_nc_hs=excluded.K0_nc_hs, E_cdm_kPa=excluded.E_cdm_kPa,
                  notes=excluded.notes, updated_at=excluded.updated_at
            """, {**r, "updated_at": ts})
            total_written += 1

    con.commit()
    con.close()

    if verbose:
        print(f"\nHoàn thành: {total_written} records ghi vào plaxis_mc_hs_params")
    return total_written


# ══════════════════════════════════════════════════════════════════
# 8. PUBLIC API
# ══════════════════════════════════════════════════════════════════

def create_mc_hs_table(db_path: Path = _DB) -> None:
    """Tạo bảng plaxis_mc_hs_params nếu chưa có (idempotent)."""
    con = _connect(db_path)
    _create_table(con)
    con.commit()
    con.close()


def get_mc_params(
    bh_name: str, symbol: str, db_path: Path = _DB
) -> dict | None:
    """Đọc MC params cho 1 HK + 1 lớp từ SQLite."""
    con = _connect(db_path)
    row = con.execute(
        "SELECT * FROM plaxis_mc_hs_params WHERE bh_name=? AND symbol=? AND pa='BH'",
        (bh_name, symbol)
    ).fetchone()
    con.close()
    return dict(row) if row else None


def get_pa2_params(
    zone: str, symbol: str, db_path: Path = _DB
) -> dict | None:
    """Đọc PA2 MC/HS params cho 1 zone + 1 lớp."""
    con = _connect(db_path)
    pa2_name = f"{zone}_PA2_MC"
    row = con.execute(
        "SELECT * FROM plaxis_mc_hs_params WHERE bh_name=? AND symbol=? AND pa='PA2'",
        (pa2_name, symbol)
    ).fetchone()
    con.close()
    return dict(row) if row else None


# ══════════════════════════════════════════════════════════════════
# 9. __main__
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch MC/HS/LE PLAXIS params")
    parser.add_argument("--db", default=str(_DB), help="Đường dẫn TTHC.sqlite")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    n = run_mc_hs_batch(Path(args.db), verbose=not args.quiet)
    print(f"\nTong: {n} records")
