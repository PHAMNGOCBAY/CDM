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
# Lớp cát/san lấp — su = 0, không tính ma sát
SAND_SYMBOLS = frozenset({"F", "2a", "2b", "2c", "4", "5a", "6", "7"})
# Lớp yếu xử lý — tính là vùng mềm trong NT1
SOFT_SYMBOLS = frozenset({"1", "XMD"})


# ── Alpha Tomlinson (1980) ────────────────────────────────────────────────────
def _alpha_tomlinson(su: float) -> float:
    """Hệ số dính α — TCVN 11823-10, phương pháp alpha."""
    if su <= 25.0:
        return 1.0
    if su >= 70.0:
        return 0.5
    return 1.0 - (su - 25.0) / (70.0 - 25.0) * 0.5


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


def _get_H_layer1(bh_name: str, db_path: Path = DB_PATH) -> tuple[float, str]:
    """
    Chiều dày vùng mềm (lớp '1' + 'XMD') tính từ miệng hố khoan.
    Trả về (H_m, source) — source='SQLite' hoặc 'missing'.
    Lớp XMD được tính vào vùng mềm vì chưa đủ cứng để làm điểm tựa.
    """
    layers = _load_layers(bh_name, db_path)
    total = sum(
        (bot - top)
        for top, bot, sym in layers
        if sym in SOFT_SYMBOLS
    )
    if total > 0:
        return round(total, 3), "SQLite"
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

    # ── Ưu tiên 3: mặc định (cảnh báo) ──────────────────────────────────────
    default = SU_BY_SYMBOL.get(symbol)
    if default is not None:
        return default, "default"

    return 0.0, "unknown"


# ── NT1: Kiểm tra chiều dài xuyên qua vùng mềm ──────────────────────────────
def calc_nt1(
    bh_name: str,
    H_layer1_m: float,
    pile_name: str,
    L_design_m: float,
    top_ke: float = TOP_KE_M,
    min_pen: float = MIN_PEN_M,
    H_source: str = "SQLite",
) -> dict:
    """
    NT1: L_req = top_ke + H_layer1 + min_pen
         Cọc đạt khi L_design ≥ L_req.
    """
    L_req  = top_ke + H_layer1_m + min_pen
    margin = L_design_m - L_req
    return {
        "bh_name":    bh_name,
        "pile_name":  pile_name,
        "L_design_m": L_design_m,
        "top_ke_m":   top_ke,
        "H_layer1_m": H_layer1_m,
        "H_source":   H_source,
        "min_pen_m":  min_pen,
        "L_req_m":    round(L_req, 2),
        "margin_m":   round(margin, 2),
        "result":     "Đạt" if margin >= 0 else "Không đạt",
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
    phi_stat: float = PHI_STAT,
    db_path: Path   = DB_PATH,
) -> dict:
    """
    NT2: RR = φ_stat × (Rs + Rp) ≥ W_cọc
    su mỗi lớp: ưu tiên VST → lab → mặc định (cảnh báo).
    """
    perimeter_m = pile["perimeter_mm"] / 1000.0
    Ap_m2       = pile["Atd_cm2"] * 1e-4
    TL_T        = pile["weight_T"]
    L_std       = pile["L_std_m"]
    w_per_m     = TL_T * 9.81 / L_std
    W_kN        = round(w_per_m * L_design_m, 1)

    fill_m    = round(max(0.0, top_ke - Z_m), 3)
    tip_depth = round(Z_m - tip_elev, 3)

    layers_raw = _load_layers(bh_name, db_path)
    rows: list[dict] = []
    Rs_total   = 0.0
    tip_su     = 0.0
    tip_symbol = ""
    warnings:  list[str] = []

    for depth_top, depth_bot, symbol in layers_raw:
        eff_top = max(depth_top, 0.0)
        eff_bot = min(depth_bot, tip_depth)
        if eff_bot <= eff_top:
            continue
        L_lyr = round(eff_bot - eff_top, 3)

        su, source = _get_su_for_layer(bh_name, depth_top, depth_bot, symbol, db_path)

        if source == "default":
            warnings.append(
                f"Lớp '{symbol}' ({depth_top:.1f}–{depth_bot:.1f} m): "
                f"không có VST/lab → dùng su={su:.0f} kPa (giả định theo ký hiệu)"
            )
        elif source == "unknown":
            warnings.append(
                f"Lớp '{symbol}' ({depth_top:.1f}–{depth_bot:.1f} m): "
                f"không xác định được su — bỏ qua ma sát"
            )

        alpha  = _alpha_tomlinson(su) if su > 0 else 0.0
        Rs_lyr = round(alpha * su * perimeter_m * L_lyr, 1)
        Rs_total += Rs_lyr

        rows.append({
            "symbol":      symbol,
            "depth_top_m": depth_top,
            "depth_bot_m": depth_bot,
            "eff_top_m":   round(eff_top, 2),
            "eff_bot_m":   round(eff_bot, 2),
            "L_lyr_m":     L_lyr,
            "su_kNm2":     su,
            "su_source":   source,
            "alpha":       round(alpha, 3),
            "Rs_lyr_kN":   Rs_lyr,
        })

        if depth_top <= tip_depth <= depth_bot:
            tip_su     = su
            tip_symbol = symbol

    Rs_total = round(Rs_total, 1)
    Rp_kN    = round(9.0 * tip_su * Ap_m2, 1) if tip_su > 0 else 0.0
    RR_kN    = round(phi_stat * (Rs_total + Rp_kN), 1)
    ratio    = round(RR_kN / W_kN, 2) if W_kN > 0 else 0.0

    return {
        "bh_name":     bh_name,
        "pile_name":   pile_name,
        "L_design_m":  L_design_m,
        "fill_m":      fill_m,
        "L_soil_m":    round(L_design_m - fill_m, 3),
        "tip_depth_m": tip_depth,
        "perimeter_m": round(perimeter_m, 4),
        "Ap_cm2":      pile["Atd_cm2"],
        "w_kNm":       round(w_per_m, 3),
        "W_kN":        W_kN,
        "layers":      rows,
        "Rs_kN":       Rs_total,
        "tip_symbol":  tip_symbol,
        "tip_su_kNm2": tip_su,
        "Rp_kN":       Rp_kN,
        "phi_stat":    phi_stat,
        "RR_kN":       RR_kN,
        "ratio":       ratio,
        "result":      "Đạt" if ratio >= 1.0 else "Không đạt",
        "warnings":    warnings,
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

        # ── H_layer1: ưu tiên SQLite, fallback JSON ──────────────────────────
        H_layer1, H_source = _get_H_layer1(db_name, db_path)
        if H_source == "missing":
            H_layer1 = bh["H_layer1_m"]
            H_source = "JSON (cảnh báo: lớp '1'/'XMD' không có trong SQLite.layers)"
            print(f"  [CẢNH BÁO] {db_name}: H_layer1 lấy từ JSON, không có layers trong SQLite")

        rec_pile = bh.get("recommended_pile", "SW-840")
        if rec_pile not in catalog:
            rec_pile = "SW-840"
        pile     = catalog[rec_pile]
        L_design = float(bh.get("recommended_L_m") or 29.0)

        nt1 = calc_nt1(db_name, H_layer1, rec_pile, L_design, H_source=H_source)
        nt2 = calc_nt2_layers(db_name, Z_m, rec_pile, pile, L_design, db_path=db_path)

        # In cảnh báo su mặc định
        if nt2["warnings"]:
            for w in nt2["warnings"]:
                print(f"  [CẢNH BÁO su] {db_name}: {w}")

        results.append({
            "bh_name":   db_name,
            "Z_m":       Z_m,
            "Z_source":  Z_source,
            "H_layer1_m": H_layer1,
            "H_source":  H_source,
            "nt1":       nt1,
            "nt2":       nt2,
        })

    return results


# ── SQLite: tạo / cập nhật bảng ──────────────────────────────────────────────
def create_nt_tables(db_path: Path = DB_PATH) -> None:
    con = sqlite3.connect(str(db_path))
    # DROP để đảm bảo schema mới (dữ liệu luôn được tái tạo từ tính toán)
    con.executescript("""
        DROP TABLE IF EXISTS ke_sw_nt_detail;
        DROP TABLE IF EXISTS ke_sw_nt2_layers;

        CREATE TABLE ke_sw_nt_detail (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            project      TEXT NOT NULL DEFAULT '202605-TTHC',
            zone         TEXT NOT NULL DEFAULT 'KE',
            bh_name      TEXT NOT NULL,
            pile_type    TEXT NOT NULL,
            L_design_m   REAL NOT NULL,
            Z_m          REAL,
            Z_source     TEXT,
            fill_m       REAL,
            L_soil_m     REAL,
            tip_depth_m  REAL,
            H_layer1_m   REAL,
            H_source     TEXT,
            L_req_nt1_m  REAL,
            margin_nt1_m REAL,
            nt1_result   TEXT,
            Rs_kN        REAL,
            tip_symbol   TEXT,
            tip_su_kNm2  REAL,
            Rp_kN        REAL,
            RR_kN        REAL,
            W_kN         REAL,
            ratio_nt2    REAL,
            nt2_result   TEXT,
            su_warnings  TEXT,
            created_at   TEXT,
            UNIQUE(bh_name, pile_type, L_design_m)
        );

        CREATE TABLE ke_sw_nt2_layers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            sw_design_id INTEGER NOT NULL,
            layer_order  INTEGER,
            symbol       TEXT,
            L_m          REAL,
            su_kPa       REAL,
            su_source    TEXT,
            alpha        REAL,
            Rs_kN        REAL,
            note         TEXT,
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
            INSERT INTO ke_sw_nt_detail
            (project, zone, bh_name, pile_type, L_design_m, Z_m, Z_source,
             fill_m, L_soil_m, tip_depth_m, H_layer1_m, H_source,
             L_req_nt1_m, margin_nt1_m, nt1_result,
             Rs_kN, tip_symbol, tip_su_kNm2, Rp_kN, RR_kN, W_kN,
             ratio_nt2, nt2_result, su_warnings, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            "202605-TTHC", "KE",
            n1["bh_name"], n1["pile_name"], n1["L_design_m"],
            r["Z_m"], r["Z_source"],
            n2["fill_m"], n2["L_soil_m"], n2["tip_depth_m"],
            n1["H_layer1_m"], r["H_source"],
            n1["L_req_m"], n1["margin_m"], n1["result"],
            n2["Rs_kN"], n2["tip_symbol"], n2["tip_su_kNm2"],
            n2["Rp_kN"], n2["RR_kN"], n2["W_kN"],
            n2["ratio"], n2["result"],
            warnings_txt, now,
        ))
        detail_id = cur.lastrowid

        for i, lyr in enumerate(n2["layers"], start=1):
            cur.execute("""
                INSERT INTO ke_sw_nt2_layers
                (sw_design_id, layer_order, symbol, L_m, su_kPa, su_source, alpha, Rs_kN, note)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                detail_id, i, lyr["symbol"],
                lyr["L_lyr_m"], lyr["su_kNm2"], lyr["su_source"],
                lyr["alpha"], lyr["Rs_lyr_kN"],
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


# ── Public helper cho app ─────────────────────────────────────────────────────
def calc_nt_for_bh(
    bh_name: str,
    Z_m: float,
    H_layer1_m: float,
    pile_name: str,
    L_design_m: float,
    db_path: Path = DB_PATH,
    sw_json_path: Path = SW_JSON,
) -> tuple[dict, dict]:
    """
    Tính NT1 + NT2 cho một HK với pile/L_design tùy chọn (dùng trong app).
    Z_m và H_layer1_m được ghi đè nếu có trong SQLite.
    """
    catalog = _load_catalog(sw_json_path)
    if pile_name not in catalog:
        pile_name = "SW-840"
    pile = catalog[pile_name]

    Z_db = _get_bh_Z_m(bh_name, db_path)
    if Z_db is not None:
        Z_m = Z_db

    H_db, _ = _get_H_layer1(bh_name, db_path)
    if H_db > 0:
        H_layer1_m = H_db

    nt1 = calc_nt1(bh_name, H_layer1_m, pile_name, L_design_m)
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
            f"H1={n1['H_layer1_m']:.1f}m[{r['H_source'][:3]}]  "
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
