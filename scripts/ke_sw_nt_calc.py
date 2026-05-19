"""
ke_sw_nt_calc.py — Tính toán chi tiết NT1 / NT2 cọc ván SW kè KE
Tiêu chuẩn: TCVN 11823-10:2017, Điều 7.3.8.6.2 — phương pháp alpha (Tomlinson 1980)
"""

from __future__ import annotations
import json
import math
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

_ROOT   = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "data" / "TTHC.sqlite"
KE_JSON = _ROOT / "data" / "ke_sw_202605_TTHC.json"
SW_JSON = _ROOT / "data" / "sw_pile_catalog.json"

# ── Thông số thiết kế kè KE ──────────────────────────────────────────────────
TOP_KE_M         = 2.70   # cao độ đỉnh kè (m)
TIP_ELEV_M       = -26.30 # cao độ mũi cọc (m) — cắm vào lớp cứng
MIN_PEN_M        = 1.00   # ngàm tối thiểu dưới lớp bùn (m)
PHI_STAT         = 0.35   # hệ số sức kháng φ_stat (TCVN 11823-10, Bảng 9)

# ── Su và alpha theo lớp ─────────────────────────────────────────────────────
SU_BY_SYMBOL: dict[str, float] = {
    "1": 10.0, "1b": 20.0, "3": 35.0, "5": 75.0, "5b": 100.0, "XMD": 10.0,
}
# Lớp cát / san lấp: su = 0 (không tính ma sát bề mặt)
SAND_SYMBOLS = {"F", "2a", "2b", "2c", "4", "5a", "6", "7"}


def _alpha_tomlinson(su: float) -> float:
    """Hệ số dính alpha theo Tomlinson (1980) — TCVN 11823-10 cho đất sét."""
    if su <= 25.0:
        return 1.0
    if su >= 70.0:
        return 0.5
    return 1.0 - (su - 25.0) / (70.0 - 25.0) * 0.5


# ── Đọc catalog cọc ──────────────────────────────────────────────────────────
def _load_catalog(sw_json: Path = SW_JSON) -> dict[str, dict]:
    data = json.loads(sw_json.read_text(encoding="utf-8"))
    catalog: dict[str, dict] = {}
    seen: dict[str, dict] = {}
    for p in data["piles"]:
        name = p["name"]
        if name not in seen:
            seen[name] = p
            # Chu vi nội suy nếu null (SW-940)
            if p.get("perimeter_mm") is None:
                catalog[name] = {**p, "perimeter_mm": _interp_perimeter(p["H_mm"], data["piles"])}
            else:
                catalog[name] = p
    return catalog


def _interp_perimeter(H_mm: int, piles: list) -> float:
    """Nội suy chu vi từ 2 cọc lân cận có perimeter_mm đã biết."""
    known = [(p["H_mm"], p["perimeter_mm"])
             for p in piles if p.get("perimeter_mm") and p["H_mm"] != H_mm]
    known.sort()
    if len(known) < 2:
        return 0.0
    # Lấy cặp gần nhất
    below = [k for k in known if k[0] < H_mm]
    above = [k for k in known if k[0] > H_mm]
    if below and above:
        h1, p1 = below[-1]
        h2, p2 = above[0]
        return p1 + (H_mm - h1) / (h2 - h1) * (p2 - p1)
    if len(known) >= 2:
        h1, p1 = known[-2]; h2, p2 = known[-1]
        return p1 + (H_mm - h1) / (h2 - h1) * (p2 - p1)
    return 0.0


# ── Đọc địa tầng từ SQLite ───────────────────────────────────────────────────
def _load_layers(bh_name: str, db_path: Path = DB_PATH) -> list[tuple]:
    """Trả về [(depth_top, depth_bot, symbol), ...] từ bảng layers (JOIN boreholes)."""
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute(
        "SELECT l.depth_top_m, l.depth_bot_m, l.symbol "
        "FROM layers l JOIN boreholes b ON l.borehole_id = b.id "
        "WHERE b.name=? ORDER BY l.depth_top_m",
        (bh_name,)
    )
    rows = cur.fetchall()
    con.close()
    return [(r[0], r[1], r[2]) for r in rows if r[2] is not None]


# ── NT1: Kiểm tra chiều dài xuyên qua lớp yếu ───────────────────────────────
def calc_nt1(
    bh_name: str,
    H_layer1_m: float,
    pile_name: str,
    L_design_m: float,
    top_ke: float = TOP_KE_M,
    min_pen: float = MIN_PEN_M,
) -> dict:
    """
    NT1: Cọc phải xuyên qua toàn bộ lớp bùn yếu (lớp 1) + ngàm min_pen.

    L_req = top_ke + H_layer1 + min_pen
          = H_layer1 + 3,70 m  (với top_ke=2,70 m, min_pen=1,0 m)
    """
    L_req  = top_ke + H_layer1_m + min_pen
    margin = L_design_m - L_req
    return {
        "bh_name":    bh_name,
        "pile_name":  pile_name,
        "L_design_m": L_design_m,
        "top_ke_m":   top_ke,
        "H_layer1_m": H_layer1_m,
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

    Chiều sâu mũi cọc tính từ mặt hố khoan (m):
        tip_depth = Z_m − tip_elev   (vì tip_elev âm)

    Phần đắp không tính Rs:
        fill_m = max(0, top_ke − Z_m)
    """
    # Kích thước cọc
    perimeter_m = pile["perimeter_mm"] / 1000.0
    Ap_m2       = pile["Atd_cm2"] * 1e-4          # cm² → m²
    TL_T        = pile["weight_T"]
    L_std       = pile["L_std_m"]
    w_per_m     = TL_T * 9.81 / L_std             # kN/m
    W_kN        = round(w_per_m * L_design_m, 1)

    fill_m      = round(max(0.0, top_ke - Z_m), 3)
    tip_depth   = round(Z_m - tip_elev, 3)         # độ sâu mũi cọc từ mặt HK

    layers_raw  = _load_layers(bh_name, db_path)

    rows = []
    Rs_total = 0.0
    tip_su      = 0.0
    tip_symbol  = ""

    for depth_top, depth_bot, symbol in layers_raw:
        eff_top = max(depth_top, 0.0)
        eff_bot = min(depth_bot, tip_depth)
        if eff_bot <= eff_top:
            continue
        L_lyr = round(eff_bot - eff_top, 3)
        su    = SU_BY_SYMBOL.get(symbol, 0.0)
        alpha = _alpha_tomlinson(su) if su > 0 else 0.0
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
            "alpha":       round(alpha, 3),
            "Rs_lyr_kN":   Rs_lyr,
        })

        # Lớp chứa mũi cọc
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

    dc = ke_data["design_conditions"]
    results = []

    for bh in ke_data["boreholes"]:
        if not bh.get("on_sw_alignment"):
            continue

        name       = bh["name"]
        db_name    = f"KE-{name}"
        Z_m        = bh["Z_m"]
        H_layer1   = bh["H_layer1_m"]
        rec_pile   = bh.get("recommended_pile", "SW-840")
        if rec_pile not in catalog:
            rec_pile = "SW-840"
        pile       = catalog[rec_pile]
        L_design   = float(bh.get("recommended_L_m") or 29.0)

        nt1 = calc_nt1(db_name, H_layer1, rec_pile, L_design)
        nt2 = calc_nt2_layers(db_name, Z_m, rec_pile, pile, L_design,
                               db_path=db_path)
        results.append({"nt1": nt1, "nt2": nt2, "bh_name": db_name,
                         "Z_m": Z_m, "H_layer1_m": H_layer1})

    return results


# ── SQLite: tạo bảng ─────────────────────────────────────────────────────────
def create_nt_tables(db_path: Path = DB_PATH) -> None:
    con = sqlite3.connect(str(db_path))
    con.executescript("""
        CREATE TABLE IF NOT EXISTS ke_sw_nt_detail (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project     TEXT    NOT NULL DEFAULT '202605-TTHC',
            zone        TEXT    NOT NULL DEFAULT 'KE',
            bh_name     TEXT    NOT NULL,
            pile_type   TEXT    NOT NULL,
            L_design_m  REAL    NOT NULL,
            Z_m         REAL,
            fill_m      REAL,
            L_soil_m    REAL,
            tip_depth_m REAL,
            L_req_nt1_m REAL,
            margin_nt1_m REAL,
            nt1_result  TEXT,
            Rs_kN       REAL,
            tip_symbol  TEXT,
            tip_su_kNm2 REAL,
            Rp_kN       REAL,
            RR_kN       REAL,
            W_kN        REAL,
            ratio_nt2   REAL,
            nt2_result  TEXT,
            created_at  TEXT,
            UNIQUE(bh_name, pile_type, L_design_m)
        );
    """)
    con.commit()
    con.close()


def save_nt_results(results: list[dict], db_path: Path = DB_PATH) -> None:
    """Lưu kết quả NT1+NT2 vào ke_sw_nt_detail và ke_sw_nt2_layers."""
    create_nt_tables(db_path)
    now = datetime.now().strftime("%Y-%m-%d")
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    for r in results:
        n1 = r["nt1"]
        n2 = r["nt2"]

        cur.execute("""
            INSERT OR REPLACE INTO ke_sw_nt_detail
            (project, zone, bh_name, pile_type, L_design_m, Z_m,
             fill_m, L_soil_m, tip_depth_m,
             L_req_nt1_m, margin_nt1_m, nt1_result,
             Rs_kN, tip_symbol, tip_su_kNm2, Rp_kN, RR_kN, W_kN, ratio_nt2, nt2_result,
             created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            "202605-TTHC", "KE",
            n1["bh_name"], n1["pile_name"], n1["L_design_m"], r["Z_m"],
            n2["fill_m"], n2["L_soil_m"], n2["tip_depth_m"],
            n1["L_req_m"], n1["margin_m"], n1["result"],
            n2["Rs_kN"], n2["tip_symbol"], n2["tip_su_kNm2"],
            n2["Rp_kN"], n2["RR_kN"], n2["W_kN"], n2["ratio"], n2["result"],
            now,
        ))

        # ke_sw_nt2_layers — tìm sw_design_id từ ke_sw_design
        cur.execute(
            "SELECT id FROM ke_sw_design WHERE bh_name=? AND pile_type=? AND L_design_m=?",
            (n1["bh_name"], n1["pile_name"], n1["L_design_m"])
        )
        row = cur.fetchone()
        if row:
            design_id = row[0]
            cur.execute("DELETE FROM ke_sw_nt2_layers WHERE sw_design_id=?", (design_id,))
            for i, lyr in enumerate(n2["layers"], start=1):
                cur.execute("""
                    INSERT INTO ke_sw_nt2_layers
                    (sw_design_id, layer_order, symbol, L_m, su_kPa, Rs_kN, note)
                    VALUES (?,?,?,?,?,?,?)
                """, (
                    design_id, i, lyr["symbol"],
                    lyr["L_lyr_m"], lyr["su_kNm2"], lyr["Rs_lyr_kN"],
                    f"depth {lyr['eff_top_m']:.2f}–{lyr['eff_bot_m']:.2f} m",
                ))

    con.commit()
    con.close()


# ── Ghi JSON kết quả chi tiết ────────────────────────────────────────────────
def save_nt_json(results: list[dict], out_path: Path) -> None:
    payload = {
        "_meta": {
            "generated": datetime.now().strftime("%Y-%m-%d"),
            "standard":  "TCVN 11823-10:2017 Dieu 7.3.8.6.2 — alpha method (Tomlinson 1980)",
            "phi_stat":  PHI_STAT,
            "top_ke_m":  TOP_KE_M,
            "tip_elev_m": TIP_ELEV_M,
            "min_pen_m": MIN_PEN_M,
        },
        "boreholes": results,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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
    Trả về (nt1_result, nt2_result).
    """
    catalog = _load_catalog(sw_json_path)
    if pile_name not in catalog:
        pile_name = "SW-840"
    pile = catalog[pile_name]
    nt1 = calc_nt1(bh_name, H_layer1_m, pile_name, L_design_m)
    nt2 = calc_nt2_layers(bh_name, Z_m, pile_name, pile, L_design_m,
                           db_path=db_path)
    return nt1, nt2


# ── __main__: chạy và lưu ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Tính NT1/NT2 chi tiết cho 7 HK trên tuyến kè SW ...")
    results = calc_all_alignment_hks()

    print("\n── Kết quả ─────────────────────────────────────────────────────")
    for r in results:
        n1 = r["nt1"]; n2 = r["nt2"]
        print(
            f"  {r['bh_name']:12s}  "
            f"NT1: L_req={n1['L_req_m']:.1f}m margin={n1['margin_m']:+.1f}m [{n1['result']}]  "
            f"NT2: Rs={n2['Rs_kN']:.0f} Rp={n2['Rp_kN']:.0f} "
            f"RR={n2['RR_kN']:.0f} W={n2['W_kN']:.0f} ratio={n2['ratio']:.2f} [{n2['result']}]"
        )

    out_json = _ROOT / "data" / "ke_sw_nt_results.json"
    save_nt_json(results, out_json)
    print(f"\nLưu JSON: {out_json}")

    save_nt_results(results)
    print(f"Lưu SQLite: ke_sw_nt_detail + ke_sw_nt2_layers")
    print("Xong.")
