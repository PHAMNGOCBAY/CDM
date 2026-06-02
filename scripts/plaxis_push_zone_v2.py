"""
plaxis_push_zone_v2.py — Push 1 zone vào PLAXIS 2D với GLOBAL layers correct.

Khác plaxis_push_zone.py v1:
  - GLOBAL layers thay vì per-BH (PLAXIS 2D yêu cầu)
  - Union các symbol unique từ tất cả BH → N global layers
  - SoftSoil cho lớp 1, 1b; Mohr-Coulomb còn lại
  - Thêm fill layer FILL_dap_2.7m trên cao độ tự nhiên
  - Mỗi BH set Y_top, Y_bot per global layer theo CAO ĐỘ THẬT (không phải depth)
"""
from __future__ import annotations
import argparse
import math
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

from plaxis_connect import connect_input  # noqa: E402
from qtt_cdm_analysis import get_zone_selected_hks  # noqa: E402

_GAMMA_W = 9.81
_DB = _ROOT / "data" / "TTHC.sqlite"
_DB_LOCAL = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")

DESIGN_ELEV_FILL = 2.70
_SOFTSOIL_SYMBOLS = {"1", "1b", "XMD"}
_SAND_TCVN = {"SM", "SP", "SW", "SM-SC", "SC", "GW", "GP", "GM", "GC", "ML"}
_CLAY_TCVN = {"CH", "CL", "OH", "OL", "MH", "CH-OH", "MH-OH"}

# Material đất đắp (sand fill + áo đường, đầm chặt)
FILL_MAT = {
    "name": "FILL_dap_2.7m",
    "model": "Mohr-Coulomb",
    "drainage": "drained",
    "gamma_unsat": 18.0, "gamma_sat": 20.0,
    "nu": 0.30, "Eref": 25000.0, "cref": 1.0, "phi": 32.0, "psi": 2.0,
}


def _classify(symbol: str, lab_sym: str = "") -> str:
    if symbol in _SOFTSOIL_SYMBOLS:
        return "softsoil"
    if lab_sym in _SAND_TCVN:
        return "sand"
    if lab_sym in _CLAY_TCVN:
        return "clay"
    sym = (symbol or "").lower()
    if sym in ("f", "2a", "2b", "2c", "3a", "3b", "3c", "4",
               "5", "5a", "5b", "6", "7", "8"):
        return "sand"
    return "clay"


def _mat_clay(lab: dict) -> dict:
    gamma = float(lab.get("gamma") or 0) or 16.0
    Cu = float(lab.get("Cu") or 0)
    c_lab = float(lab.get("c") or 0)
    phi_lab = float(lab.get("phi") or 0)
    e0 = float(lab.get("e0") or 1.0)
    E_lab = float(lab.get("E") or 0)
    if Cu > 0:
        c, phi = Cu, 0.0
    elif c_lab > 0:
        c, phi = c_lab, max(phi_lab, 0.0)
    else:
        c, phi = 10.0, 0.0
    Eref = E_lab if E_lab > 0 else (250.0 * Cu if Cu > 0 else 2500.0)
    return {
        "model": "Mohr-Coulomb", "drainage": "undrainedb",
        "gamma_unsat": gamma, "gamma_sat": gamma + 1.0,
        "nu": 0.35, "Eref": Eref, "cref": c, "phi": phi, "psi": 0.0,
        "e_init": e0,
    }


def _mat_sand(lab: dict, N_spt: float | None) -> dict:
    gamma = float(lab.get("gamma") or 0) or 19.0
    c_lab = float(lab.get("c") or 0)
    phi_lab = float(lab.get("phi") or 0)
    if N_spt and N_spt > 0:
        phi = max(28.0, min(40.0, 27.0 + 0.3 * float(N_spt)))
        Eref = 2000.0 * float(N_spt)
    elif phi_lab > 0:
        phi, Eref = phi_lab, 20000.0
    else:
        phi, Eref = 30.0, 20000.0
    return {
        "model": "Mohr-Coulomb", "drainage": "drained",
        "gamma_unsat": gamma, "gamma_sat": gamma + 1.0,
        "nu": 0.30, "Eref": Eref, "cref": max(0.1, c_lab),
        "phi": phi, "psi": max(0.0, phi - 30.0),
    }


def _mat_softsoil(lab: dict) -> dict:
    gamma = float(lab.get("gamma") or 0) or 15.0
    e0 = float(lab.get("e0") or 0) or 1.5
    Cc = float(lab.get("Cc") or 0)
    Cs = float(lab.get("Cs") or 0)
    phi = float(lab.get("phi") or 0) or 22.0
    Cu = float(lab.get("Cu") or 0)
    c_lab = float(lab.get("c") or 0)
    if Cc <= 0:
        # Fallback MC nếu không có Cc
        return _mat_clay(lab)
    lambda_star = Cc / (2.303 * (1.0 + e0))
    kappa_star = (Cs / (2.303 * (1.0 + e0))) if Cs > 0 else max(lambda_star / 10.0, 1e-5)
    M_csl = 6.0 * math.sin(math.radians(phi)) / (3.0 - math.sin(math.radians(phi)))
    return {
        "model": "Soft Soil", "drainage": "undraineda",
        "gamma_unsat": gamma, "gamma_sat": gamma + 0.5,
        "nuur": 0.15, "lambda_star": lambda_star, "kappa_star": kappa_star,
        "M_csl": M_csl, "OCR": 1.0, "POP": 0.0,
        "cref": max(c_lab, Cu, 1.0), "phi": phi, "psi": 0.0,
        "e_init": e0,
    }


def _fetch_bh_layers(bh_name: str, db_path: Path) -> dict:
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        b = con.execute(
            "SELECT name, elevation_m, x_coord_m, y_coord_m FROM boreholes WHERE name=?",
            (bh_name,),
        ).fetchone()
        if not b:
            return {}
        layers = [dict(r) for r in con.execute(
            "SELECT symbol, depth_top_m, depth_bot_m FROM layers "
            "WHERE borehole_id=(SELECT id FROM boreholes WHERE name=?) "
            "ORDER BY depth_top_m", (bh_name,),
        ).fetchall()]
        # Lab data per layer
        for L in layers:
            lab = con.execute("""
                SELECT lt.symbol_tcvn,
                       AVG(lt.gamma_kNm3) AS gamma, AVG(lt.e0) AS e0,
                       AVG(lt.Cu_UU_kPa) AS Cu, AVG(lt.c_kPa) AS c,
                       AVG(lt.phi_deg) AS phi, AVG(lt.E_kPa) AS E,
                       AVG(lt.Cc) AS Cc, AVG(lt.Cs) AS Cs,
                       AVG(lt.PC_kPa) AS PC, COUNT(*) AS n
                FROM lab_tests lt JOIN boreholes b ON lt.borehole_id = b.id
                WHERE b.name=? AND (lt.depth_from_m + lt.depth_to_m)/2.0 BETWEEN ? AND ?
            """, (bh_name, L["depth_top_m"], L["depth_bot_m"])).fetchone()
            L["lab"] = dict(lab) if lab and lab["n"] else {}
            n_spt = con.execute("""
                SELECT AVG(N) AS N_avg, COUNT(*) AS n
                FROM spt_values
                WHERE borehole_id=(SELECT id FROM boreholes WHERE name=?)
                  AND depth_m BETWEEN ? AND ?
            """, (bh_name, L["depth_top_m"], L["depth_bot_m"])).fetchone()
            L["N_spt"] = n_spt["N_avg"] if n_spt and n_spt["n"] else None
    return {
        "name": b["name"],
        "elev": float(b["elevation_m"] or 0),
        "x_coord": b["x_coord_m"],
        "y_coord": b["y_coord_m"],
        "layers": layers,
    }


def push_zone_v2(zone_code: str, save_file: str | None = None,
                  scale_factor: float = 1.0, db_path: Path | None = None) -> dict:
    db = db_path or _DB
    hks_meta = get_zone_selected_hks(zone_code, db_path=db)
    if not hks_meta:
        print(f"Zone {zone_code}: no selected HK")
        return {}

    # Fetch all HK data
    hks_data = []
    for h in hks_meta:
        d = _fetch_bh_layers(h["bh_name"], db)
        if d and d.get("layers"):
            hks_data.append(d)
    if not hks_data:
        print(f"Zone {zone_code}: no HK with layer data")
        return {}

    hks_data = sorted(hks_data, key=lambda d: float(d.get("y_coord") or 0))
    E0 = float(hks_data[0]["y_coord"] or 0)

    print(f"=== Zone {zone_code}: {len(hks_data)} HK ===")
    print(f"  Cao độ thiết kế đắp: +{DESIGN_ELEV_FILL:.2f} m")
    print(f"  Easting range: {E0:.0f} → {float(hks_data[-1]['y_coord']):.0f}")
    print()

    # Step 1: Gom symbol unique + thứ tự (lớp đắp ở đầu, sau đó theo depth TB)
    symbol_depth_avg: dict[str, float] = {}
    symbol_lab_pool: dict[str, list[dict]] = {}
    for d in hks_data:
        for L in d["layers"]:
            s = L["symbol"]
            mid = (L["depth_top_m"] + L["depth_bot_m"]) / 2.0
            symbol_depth_avg[s] = symbol_depth_avg.get(s, mid) * 0.5 + mid * 0.5
            symbol_lab_pool.setdefault(s, []).append(L)

    # Sort symbols: FILL_dap đứng đầu, sau đó theo depth TB tăng dần
    sorted_symbols = sorted(symbol_depth_avg.keys(), key=lambda s: symbol_depth_avg[s])
    # Global layer list: [FILL, sym1, sym2, ...]
    global_layers = ["__FILL__"] + sorted_symbols
    print(f"  Global layers ({len(global_layers)}):")
    for i, s in enumerate(global_layers):
        if s == "__FILL__":
            print(f"    {i+1}. FILL_dap_2.7m  (đất đắp)")
        else:
            print(f"    {i+1}. {s}  (depth TB ≈ {symbol_depth_avg.get(s, 0):.1f}m)")
    print()

    # Step 2: Tính material cho mỗi global layer (TB từ pool)
    def _aggregate_lab(symbol: str) -> dict:
        labs = symbol_lab_pool.get(symbol, [])
        if not labs:
            return {}
        keys = ["gamma", "e0", "Cu", "c", "phi", "E", "Cc", "Cs", "PC"]
        n_total = sum(1 for L in labs if L.get("lab"))
        if n_total == 0:
            return {}
        out = {}
        for k in keys:
            vals = [float(L["lab"].get(k) or 0) for L in labs if L.get("lab") and L["lab"].get(k)]
            if vals:
                out[k] = sum(vals) / len(vals)
        # symbol_tcvn ưu tiên cái xuất hiện nhiều nhất
        syms = [L["lab"].get("symbol_tcvn") for L in labs if L.get("lab") and L["lab"].get("symbol_tcvn")]
        if syms:
            out["symbol_tcvn"] = max(set(syms), key=syms.count)
        # N_spt TB
        spts = [L.get("N_spt") for L in labs if L.get("N_spt")]
        if spts:
            out["N_spt"] = sum(spts) / len(spts)
        return out

    materials = {}  # symbol → mat params
    for s in global_layers:
        if s == "__FILL__":
            materials[s] = FILL_MAT
            continue
        lab_agg = _aggregate_lab(s)
        soil_type = _classify(s, lab_agg.get("symbol_tcvn", ""))
        if soil_type == "softsoil":
            m = _mat_softsoil(lab_agg)
        elif soil_type == "sand":
            m = _mat_sand(lab_agg, lab_agg.get("N_spt"))
        else:
            m = _mat_clay(lab_agg)
        m["_type"] = soil_type
        materials[s] = m

    print("  Materials per symbol:")
    for s in global_layers:
        m = materials[s]
        model = m.get("model", "?")
        gamma = m.get("gamma_unsat", 0)
        if s == "__FILL__":
            print(f"    FILL: {model}  γ={gamma:.1f}  φ=32  c=1  E=25000")
        elif model == "Soft Soil":
            print(f"    {s:5s}: {model}  γ={gamma:.1f}  λ*={m['lambda_star']:.4f}  κ*={m['kappa_star']:.4f}  M={m['M_csl']:.2f}  φ={m['phi']:.1f}")
        else:
            print(f"    {s:5s}: {model}  γ={gamma:.1f}  c={m['cref']:.1f}  φ={m['phi']:.1f}  E={m['Eref']:,.0f}  ({m['_type']})")
    print()

    # Step 3: Kết nối PLAXIS + push
    print("Kết nối PLAXIS...")
    s_i, g_i = connect_input()
    try:
        print("  s_i.new()")
        s_i.new()
        for fn in ("gotosoil", "gotostructures"):
            try:
                getattr(g_i, fn)()
                break
            except Exception:
                continue

        # 3a. Tạo borehole đầu tiên + N global layers
        first_d = hks_data[0]
        x0 = (float(first_d["y_coord"]) - E0) * scale_factor
        head0 = DESIGN_ELEV_FILL  # head = cao độ thiết kế (top of fill)
        print(f"  borehole({x0}) cho {first_d['name']}, Head = {head0}")
        bh0 = g_i.borehole(x0)
        try:
            bh0.Head = head0
        except Exception as e:
            print(f"    WARN: Head: {e}")

        # Tạo N global layers với placeholder thickness — sẽ set Y_top/Y_bot sau
        print(f"  Tạo {len(global_layers)} global SoilLayers")
        plaxis_layers = []
        for i, s in enumerate(global_layers):
            sl = g_i.soillayer(0)  # add to current BH (= first)
            plaxis_layers.append(sl)
        plaxis_global_layers = list(g_i.SoilLayers)

        # 3b. Tạo N materials + gán vào global layers
        print(f"  Tạo {len(global_layers)} materials")
        mat_objs = []
        for i, s in enumerate(global_layers):
            params = materials[s]
            try:
                m = g_i.soilmat()
                model_name = params.get("model", "Mohr-Coulomb")
                m.SoilModel = model_name
                if s == "__FILL__":
                    m.Identification = "FILL_dap_2.7m"
                else:
                    m.Identification = f"{zone_code}_{s}"
                m.gammaUnsat = params["gamma_unsat"]
                m.gammaSat = params["gamma_sat"]
                m.DrainageType = params.get("drainage", "drained")
                if model_name == "Soft Soil":
                    m.nuUR = params.get("nuur", 0.15)
                    m.lambdaModified = params["lambda_star"]
                    m.kappaModified = params["kappa_star"]
                    # M read-only — tự tính từ φ
                    m.OCR = params.get("OCR", 1.0)
                    m.POP = params.get("POP", 0.0)
                    m.cRef = params["cref"]
                    m.phi = params["phi"]
                else:
                    m.nu = params.get("nu", 0.3)
                    m.ERef = params["Eref"]
                    m.cRef = params["cref"]
                    m.phi = params["phi"]
                    # psi read-only khi drainage=undraineda/b — chỉ set khi drained
                    if params.get("drainage", "drained") == "drained":
                        try:
                            m.psi = params.get("psi", 0.0)
                        except Exception:
                            pass
                mat_objs.append(m)
                # Gán material cho global layer
                try:
                    g_i.setmaterial(plaxis_global_layers[i], m)
                    print(f"    Layer {i+1} ({s}): {model_name} OK")
                except Exception as e:
                    print(f"    Layer {i+1} ({s}) setmaterial FAIL: {e}")
            except Exception as e:
                mat_objs.append(None)
                print(f"    Layer {i+1} ({s}) material FAIL: {e}")

        # 3c. Set Bottom mỗi global layer (Top read-only, auto = Bottom layer trên)
        def _set_bh_layers(bh_idx: int, d: dict):
            """Set Y_bot mỗi global layer cho BH index.

            Quy ước Y giảm xuống dưới:
              Layer 0 (FILL): Top=Head=2.7, Bottom=nat_elev
              Layer i (>0): Top=Bot trên, Bottom=nat - depth_bot_symbol[i]
            Lớp KHÔNG có trong BH → Bottom = Bottom của lớp trên (zero thickness).
            """
            nat = d["elev"]
            fill_bot = nat  # FILL kết thúc ở mặt tự nhiên

            # Layer 0: FILL — chỉ set Bottom (Top auto = Head = 2.7)
            try:
                list(plaxis_global_layers[0].Zones)[bh_idx].Bottom = fill_bot
            except Exception as e:
                print(f"    Layer 0 (FILL) set Bottom fail: {e}")

            bh_symbol_depths = {L["symbol"]: (L["depth_top_m"], L["depth_bot_m"])
                                 for L in d["layers"]}
            current_y_bot = fill_bot
            for i, s in enumerate(global_layers[1:], start=1):
                if s in bh_symbol_depths:
                    _dtop, dbot = bh_symbol_depths[s]
                    y_bot = nat - dbot
                else:
                    # Lớp vắng — zero thickness, Bottom = Bottom lớp trên
                    y_bot = current_y_bot
                # Đảm bảo Bot không trên Bot lớp trên (PLAXIS yêu cầu monotonic giảm)
                y_bot = min(y_bot, current_y_bot)
                try:
                    list(plaxis_global_layers[i].Zones)[bh_idx].Bottom = y_bot
                except Exception as e:
                    print(f"    Layer {i+1} ({s}) set Bottom fail: {e}")
                current_y_bot = y_bot

        print(f"  Set Top/Bot BH[0] {first_d['name']}: nat={first_d['elev']:.2f}m")
        _set_bh_layers(0, first_d)

        # 3d. Thêm BH 2..N (chỉ tạo, KHÔNG gọi soillayer — dùng Zones có sẵn)
        for k, d in enumerate(hks_data[1:], start=1):
            x = (float(d["y_coord"]) - E0) * scale_factor
            print(f"  borehole({x:.1f}) cho BH[{k}] {d['name']}, nat={d['elev']:.2f}m")
            try:
                bh = g_i.borehole(x)
                try:
                    bh.Head = DESIGN_ELEV_FILL
                except Exception as e:
                    print(f"    Head fail: {e}")
                # Update plaxis_global_layers reference (Zones tự thêm zone mới cho BH)
                plaxis_global_layers = list(g_i.SoilLayers)
                _set_bh_layers(k, d)
            except Exception as e:
                print(f"    FAIL borehole: {e}")

        # 3e. Save
        saved_path = None
        if save_file:
            save_str = str(Path(save_file).resolve())
            Path(save_str).parent.mkdir(parents=True, exist_ok=True)
            print()
            print(f"Auto-save: {save_str}")
            for fn_name in ("save_project", "saveas", "save"):
                try:
                    fn = getattr(g_i, fn_name, None)
                    if fn is None:
                        continue
                    fn(save_str)
                    saved_path = save_str
                    print(f"  g_i.{fn_name}() OK")
                    break
                except Exception as e:
                    print(f"  g_i.{fn_name} FAIL: {e}")

        print()
        print("=" * 60)
        print(f"ZONE {zone_code}: push xong, {len(global_layers)} global layers, "
              f"{len(hks_data)} BHs")
        if saved_path:
            print(f"File: {saved_path}")
        print("=" * 60)
        return {
            "n_hks": len(hks_data), "n_global_layers": len(global_layers),
            "saved_path": saved_path, "global_layers": global_layers,
        }
    finally:
        try:
            s_i.close()
        except Exception:
            pass


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    parser = argparse.ArgumentParser()
    parser.add_argument("zone_code")
    parser.add_argument("--save", type=str, default=None)
    parser.add_argument("--scale", type=float, default=1.0)
    args = parser.parse_args()
    push_zone_v2(args.zone_code, save_file=args.save, scale_factor=args.scale)
    return 0


if __name__ == "__main__":
    sys.exit(main())
