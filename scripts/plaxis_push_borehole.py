"""
plaxis_push_borehole.py — Push 1 hố khoan từ SQLite vào PLAXIS 2D đang mở.

Pipeline:
  1. Đọc HK + layers + lab_tests TB per symbol từ SQLite
  2. Kết nối PLAXIS Input (port 10000)
  3. gotostructures → tạo Borehole tại x_in_plot (mặc định 0)
  4. Set head elevation = elevation_m của HK
  5. Cho mỗi lớp đất: tạo SoilLayer với thickness từ depth_bot - depth_top
  6. Cho mỗi symbol đất: tạo SoilMaterial Mohr-Coulomb với γ, c, φ, Eref, ν
  7. Assign SoilMaterial cho lớp tương ứng

Đơn vị PLAXIS (CLAUDE.md §1):
  - phi: degrees (0-45)
  - c, Eref: kN/m² (= kPa)
  - gamma: kN/m³

Chạy:
  $env:PLAXIS_PASSWORD = '+g=GW5R>A9WY?He7'
  python scripts/plaxis_push_borehole.py BXN-CV-HK1 [--x 0.0]
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

from plaxis_connect import connect_input  # noqa: E402


_GAMMA_W = 9.81
_DB = _ROOT / "data" / "TTHC.sqlite"
_DB_LOCAL = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")

# Cao độ thiết kế đắp (m) — từ tvtk_cdm_config.settlement_design_elev_m
DESIGN_ELEV_FILL = 2.70

# Symbols dùng Soft Soil model (lớp bùn yếu)
_SOFTSOIL_SYMBOLS = {"1", "1b", "XMD"}

# Material đất đắp (sand fill + áo đường)
FILL_MATERIAL = {
    "name": "FILL_dap_2.7m",
    "type": "MC",
    "drainage": "drained",
    "gamma_unsat": 18.0,
    "gamma_sat": 20.0,
    "nu": 0.30,
    "Eref": 25000.0,   # cát đầm chặt
    "cref": 1.0,
    "phi": 32.0,
    "psi": 2.0,
}


def _material_params_softsoil(lab: dict, depth_mid: float) -> dict:
    """Soft Soil model cho lớp bùn (symbol 1, 1b, XMD).

    Tham số:
      λ* = Cc / [2.303 × (1+e0)]   (modified compression index)
      κ* = Cs / [2.303 × (1+e0)]   (modified swelling, mặc định λ*/10)
      M  = 6 sinφ / (3 - sinφ)     (CSL slope p-q)
      OCR = 1.0 (NC mặc định, NCL cố kết bình thường)
    """
    import math
    gamma = float(lab.get("gamma") or 0) or 15.0
    e0 = float(lab.get("e0") or 0) or 1.5
    Cc = float(lab.get("Cc") or 0)
    Cs = float(lab.get("Cs") or 0)
    phi = float(lab.get("phi") or 0)
    Cu = float(lab.get("Cu") or 0)
    c_lab = float(lab.get("c") or 0)

    if Cc <= 0:
        # Fallback nếu không có Cc — sang MC undrained
        return _material_params_clay(lab, depth_mid)

    lambda_star = Cc / (2.303 * (1.0 + e0))
    kappa_star = (Cs / (2.303 * (1.0 + e0))) if Cs > 0 else max(lambda_star / 10.0, 1e-5)
    if phi <= 0:
        phi = 22.0   # bùn yếu mặc định
    M_csl = 6.0 * math.sin(math.radians(phi)) / (3.0 - math.sin(math.radians(phi)))
    cref = max(c_lab, Cu, 1.0)  # PLAXIS yêu cầu c > 0
    return {
        "type": "SoftSoil",
        "drainage": "undrainedb",
        "gamma_unsat": gamma if gamma > _GAMMA_W else 15.0,
        "gamma_sat": (gamma if gamma > _GAMMA_W else 15.0) + 0.5,
        "nuur": 0.15,
        "lambda_star": lambda_star,
        "kappa_star": kappa_star,
        "M_csl": M_csl,
        "OCR": 1.0,
        "POP": 0.0,
        "cref": cref,
        "phi": phi,
        "psi": 0.0,
        "e_init": e0,
    }


def _create_push_log_table(db_path: Path) -> None:
    """Tạo bảng cdm_plaxis_push_log (idempotent)."""
    with sqlite3.connect(db_path) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS cdm_plaxis_push_log (
                bh_name TEXT NOT NULL,
                zone_code TEXT,
                push_timestamp TEXT NOT NULL,
                plaxis_x REAL,
                plaxis_head_m REAL,
                n_layers INTEGER,
                n_materials_ok INTEGER,
                n_materials_total INTEGER,
                file_path TEXT,
                status TEXT,
                note TEXT,
                PRIMARY KEY (bh_name, push_timestamp)
            )
        """)
        con.commit()


def _log_push(bh_name: str, zone_code: str | None, x: float, head: float,
               n_layers: int, n_mat_ok: int, n_mat_total: int,
               file_path: str | None, status: str, note: str = "") -> None:
    """Ghi log push vào CẢ LOCAL + PROJECT DB."""
    from datetime import datetime
    ts = datetime.now().isoformat(timespec="seconds")
    for db in (_DB_LOCAL, _DB):
        if not db.exists() and db == _DB_LOCAL:
            continue
        try:
            _create_push_log_table(db)
            with sqlite3.connect(db) as con:
                con.execute("""
                    INSERT OR REPLACE INTO cdm_plaxis_push_log
                    (bh_name, zone_code, push_timestamp, plaxis_x, plaxis_head_m,
                     n_layers, n_materials_ok, n_materials_total,
                     file_path, status, note)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (bh_name, zone_code, ts, x, head,
                      n_layers, n_mat_ok, n_mat_total,
                      file_path, status, note))
                con.commit()
        except Exception:
            pass


# Soil type classification: sand vs clay theo symbol_tcvn lab
_SAND_TCVN = {"SM", "SP", "SW", "SM-SC", "SC", "GW", "GP", "GM", "GC",
              "ML"}  # ML = silt borderline, count as sand-like for elastic Es
_CLAY_TCVN = {"CH", "CL", "OH", "OL", "MH", "CH-OH", "MH-OH"}


def _classify_layer(layer_symbol: str, lab_avg: dict) -> str:
    """Quyết định 'sand' hay 'clay' cho layer.

    Ưu tiên: nếu có lab symbol_tcvn → dùng nó. Nếu không → fallback theo
    layer symbol số (1, 1b, 2, XMD = clay; F, 3a, 4, 5 = sand thường).
    """
    lab_sym = lab_avg.get("symbol_tcvn", "") if lab_avg else ""
    if lab_sym in _SAND_TCVN:
        return "sand"
    if lab_sym in _CLAY_TCVN:
        return "clay"
    # Fallback theo layer number symbol
    sym = (layer_symbol or "").lower()
    if sym in ("f", "2a", "2b", "2c", "3a", "3b", "3c", "4",
               "5", "5a", "5b", "6", "7", "8"):
        return "sand"
    return "clay"


def _fetch_borehole_data(bh_name: str, db_path: Path) -> dict:
    """Đọc hố khoan + layers + lab data per layer từ SQLite."""
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        b = con.execute(
            "SELECT name, elevation_m, x_coord_m, y_coord_m "
            "FROM boreholes WHERE name=?",
            (bh_name,),
        ).fetchone()
        if not b:
            raise ValueError(f"Không tìm thấy HK '{bh_name}'")

        layers = [dict(r) for r in con.execute(
            "SELECT symbol, depth_top_m, depth_bot_m "
            "FROM layers WHERE borehole_id=(SELECT id FROM boreholes WHERE name=?) "
            "ORDER BY depth_top_m",
            (bh_name,),
        ).fetchall()]

        # Lab TB cho mỗi layer (tính theo depth range)
        for L in layers:
            row = con.execute("""
                SELECT lt.symbol_tcvn,
                       AVG(lt.gamma_kNm3)   AS gamma,
                       AVG(lt.e0)            AS e0,
                       AVG(lt.Cu_UU_kPa)     AS Cu,
                       AVG(lt.c_kPa)         AS c,
                       AVG(lt.phi_deg)       AS phi,
                       AVG(lt.E_kPa)         AS E,
                       AVG(lt.Cc)            AS Cc,
                       COUNT(*)              AS n
                FROM lab_tests lt
                JOIN boreholes b ON lt.borehole_id = b.id
                WHERE b.name=?
                  AND (lt.depth_from_m + lt.depth_to_m)/2.0 BETWEEN ? AND ?
            """, (bh_name, L["depth_top_m"], L["depth_bot_m"])).fetchone()
            L["lab"] = dict(row) if row and row["n"] else {}

        # SPT TB cho mỗi layer
        for L in layers:
            row = con.execute("""
                SELECT AVG(N) AS N_avg, COUNT(*) AS n
                FROM spt_values
                WHERE borehole_id=(SELECT id FROM boreholes WHERE name=?)
                  AND depth_m BETWEEN ? AND ?
            """, (bh_name, L["depth_top_m"], L["depth_bot_m"])).fetchone()
            L["N_spt"] = row["N_avg"] if row and row["n"] else None

    return {
        "name": b["name"],
        "elev": float(b["elevation_m"] or 0),
        "x_coord": b["x_coord_m"],
        "y_coord": b["y_coord_m"],
        "layers": layers,
    }


def _material_params_clay(lab: dict, depth_mid: float) -> dict:
    """Mohr-Coulomb cho lớp sét."""
    gamma = float(lab.get("gamma") or 0) or 16.0
    e0 = float(lab.get("e0") or 0)
    Cu = float(lab.get("Cu") or 0)
    c_lab = float(lab.get("c") or 0)
    phi_lab = float(lab.get("phi") or 0)
    E_lab = float(lab.get("E") or 0)

    # MC undrained (φ=0) cho sét yếu: c = Cu, φ = 0
    # MC drained: c, φ từ trực tiếp shear
    # Dùng undrained vì lớp sét thường được tính undrained trong PLAXIS
    if Cu > 0:
        c = Cu
        phi = 0.0  # φ=0 trong undrained shear
    elif c_lab > 0:
        c = c_lab
        phi = phi_lab if phi_lab > 0 else 0.0
    else:
        c = 10.0  # fallback
        phi = 0.0
    # E từ Mesri: Es = 250 × Cu (kPa)
    if E_lab > 0:
        Eref = E_lab
    elif Cu > 0:
        Eref = 250.0 * Cu
    else:
        Eref = 2500.0  # fallback
    return {
        "type": "MC",
        "drainage": "undrainedb",  # Undrained B: c=Cu, φ=0
        "gamma_unsat": gamma if gamma > _GAMMA_W else gamma + _GAMMA_W * 0.0,
        "gamma_sat": gamma if gamma > _GAMMA_W else gamma + 2.0,
        "nu": 0.35,
        "Eref": Eref,
        "cref": c,
        "phi": phi,
        "psi": 0.0,
        "e_init": e0 if e0 > 0 else 1.0,
    }


def _material_params_sand(lab: dict, N_spt: float | None,
                          depth_mid: float) -> dict:
    """Mohr-Coulomb cho lớp cát."""
    gamma = float(lab.get("gamma") or 0) or 19.0
    c_lab = float(lab.get("c") or 0)
    phi_lab = float(lab.get("phi") or 0)
    # φ ước từ SPT N: φ ≈ 27 + 0.3·N (đơn giản)
    if N_spt and N_spt > 0:
        phi = max(28.0, min(40.0, 27.0 + 0.3 * float(N_spt)))
    elif phi_lab > 0:
        phi = phi_lab
    else:
        phi = 30.0
    # Es từ SPT: Es = α × N với α = 2000 kPa (TCVN)
    if N_spt and N_spt > 0:
        Eref = 2000.0 * float(N_spt)
    else:
        Eref = 20000.0  # fallback
    return {
        "type": "MC",
        "drainage": "drained",
        "gamma_unsat": gamma if gamma > _GAMMA_W else 18.0,
        "gamma_sat": (gamma if gamma > _GAMMA_W else 18.0) + 1.0,
        "nu": 0.30,
        "Eref": Eref,
        "cref": max(0.1, c_lab),  # PLAXIS yêu cầu c > 0 cho MC
        "phi": phi,
        "psi": max(0.0, phi - 30.0),
    }


def push_borehole_to_plaxis(bh_name: str, x_in_plot: float = 0.0,
                             dry_run: bool = False,
                             db_path: Path | None = None,
                             save_file: str | None = None,
                             zone_code: str | None = None,
                             reset_project: bool = True,
                             keep_connection: bool = False,
                             existing_session: tuple | None = None) -> dict:
    """Push 1 hố khoan vào PLAXIS 2D đang mở.

    dry_run=True       : chỉ in kế hoạch, không gọi PLAXIS.
    save_file          : đường dẫn .p2dx — gọi s_i.save(path) sau khi push.
    zone_code          : ghi vào log để track theo zone.
    reset_project=True : gọi s_i.new() trước khi push (xóa project hiện tại).
    keep_connection    : không close session — dùng cho batch push.
    existing_session   : (s_i, g_i) — tái sử dụng connection từ batch.
    """
    db = db_path or _DB
    bh_data = _fetch_borehole_data(bh_name, db)

    print(f"=== {bh_data['name']} ===")
    print(f"  Cao độ tự nhiên: {bh_data['elev']:.2f} m")
    print(f"  Tọa độ N,E    : ({bh_data['x_coord']}, {bh_data['y_coord']})")
    print(f"  Số lớp        : {len(bh_data['layers'])}")
    print()
    print("  Vật liệu dự kiến (MC):")

    materials_to_create = []  # list[{symbol, params, layer_top, layer_bot}]
    seen_symbols = set()
    for i, L in enumerate(bh_data["layers"]):
        depth_mid = (L["depth_top_m"] + L["depth_bot_m"]) / 2.0
        soil_type = _classify_layer(L["symbol"], L["lab"])
        if soil_type == "sand":
            params = _material_params_sand(L["lab"], L["N_spt"], depth_mid)
        else:
            params = _material_params_clay(L["lab"], depth_mid)

        # Đặt tên duy nhất per (zone_symbol_index) — để tránh đè khi 2 lớp cùng symbol
        mat_name = f"{bh_data['name']}_L{i+1}_{L['symbol']}"
        L["mat_name"] = mat_name
        L["soil_type"] = soil_type
        L["params"] = params
        materials_to_create.append({
            "name": mat_name,
            "symbol": L["symbol"],
            "soil_type": soil_type,
            "params": params,
            "depth_top": L["depth_top_m"],
            "depth_bot": L["depth_bot_m"],
        })
        print(f"    {mat_name:30s} ({soil_type:4s})  "
              f"γ={params['gamma_unsat']:.1f}  c={params['cref']:.1f}  "
              f"φ={params['phi']:.1f}°  E={params['Eref']:,.0f}")

    if dry_run:
        print()
        print("DRY RUN — không push lên PLAXIS")
        return {"materials": materials_to_create, "pushed": False}

    # Reuse session từ batch hoặc tạo mới
    if existing_session is not None:
        s_i, g_i = existing_session
        print("  Dùng existing session")
    else:
        print()
        print("Kết nối PLAXIS Input...")
        try:
            s_i, g_i = connect_input()
        except Exception as e:
            print(f"FAIL connect: {e}")
            _log_push(bh_name, zone_code, x_in_plot, bh_data["elev"],
                       0, 0, 0, save_file, "FAIL_CONNECT", str(e))
            return {"materials": materials_to_create, "pushed": False,
                    "error": str(e)}

    n_mat_ok = 0
    try:
        # 0. Project active check / reset
        if reset_project:
            try:
                print("  s_i.new() — reset project")
                s_i.new()
            except Exception as e:
                print(f"  s_i.new() FAIL: {e}")
        else:
            try:
                _ = g_i.SoilLayers
                print("  Reuse project hiện tại")
            except Exception:
                print("  Không có project active → s_i.new()")
                try:
                    s_i.new()
                except Exception as e:
                    print(f"  s_i.new() FAIL: {e}")
                    return {"materials": materials_to_create, "pushed": False,
                            "error": str(e)}

        # 1. Chuyển sang Structures mode (PLAXIS 2D 2024+ dùng gotosoil/gotostructures)
        for mode_fn in ("gotosoil", "gotostructures"):
            try:
                print(f"  {mode_fn}()")
                getattr(g_i, mode_fn)()
                break
            except Exception:
                continue

        # 2. Tạo borehole
        print(f"  borehole({x_in_plot})")
        bh = g_i.borehole(x_in_plot)

        # 3. Set head elevation
        head = bh_data["elev"]
        print(f"  set head = {head:.2f} m (cao độ tự nhiên)")
        try:
            bh.Head = head
        except Exception as e:
            print(f"    WARN: Set head failed: {e}")

        # 4. Tạo SoilLayer cho mỗi lớp
        print(f"  Tạo {len(bh_data['layers'])} SoilLayers")
        for i, L in enumerate(bh_data["layers"]):
            thickness = L["depth_bot_m"] - L["depth_top_m"]
            try:
                g_i.soillayer(bh, thickness)
                print(f"    L{i+1}: {L['symbol']:5s}  "
                      f"{L['depth_top_m']:5.1f}→{L['depth_bot_m']:5.1f}m  "
                      f"(dày {thickness:.2f}m)")
            except Exception as e:
                print(f"    L{i+1} FAIL: {e}")

        # 5. Tạo SoilMaterial cho mỗi lớp — giữ index để pair đúng với SoilLayer
        print(f"  Tạo {len(materials_to_create)} SoilMaterials (MC)")
        plaxis_materials = []  # list[(mat_object | None, mat_name)]
        for mat in materials_to_create:
            p = mat["params"]
            try:
                m = g_i.soilmat()
                m.SoilModel = "Mohr-Coulomb"
                m.Identification = mat["name"]
                m.gammaUnsat = p["gamma_unsat"]
                m.gammaSat = p["gamma_sat"]
                m.nu = p["nu"]
                m.Eref = p["Eref"]
                m.cref = p["cref"]
                m.phi = p["phi"]
                m.psi = p.get("psi", 0.0)
                m.DrainageType = p.get("drainage", "drained")
                plaxis_materials.append((m, mat["name"]))
                n_mat_ok += 1
                print(f"    OK: {mat['name']}")
            except Exception as e:
                plaxis_materials.append((None, mat["name"]))
                print(f"    {mat['name']} FAIL: {e}")

        # 6. Assign material to layers — pair theo INDEX
        try:
            soil_layers = list(g_i.SoilLayers)
            for i, sl in enumerate(soil_layers):
                if i >= len(plaxis_materials):
                    break
                m, mat_name = plaxis_materials[i]
                if m is None:
                    print(f"    Layer {i+1}: SKIP (material {mat_name} fail)")
                    continue
                try:
                    g_i.setmaterial(sl, m)
                    print(f"    Layer {i+1} ← {mat_name}")
                except Exception as e:
                    print(f"    Layer {i+1} assign FAIL: {e}")
        except Exception as e:
            print(f"  Soil assignment loop FAIL: {e}")

        # 7. Auto-save .p2dx — thử nhiều API method khác nhau
        saved_path = None
        if save_file:
            save_path = Path(save_file).resolve()
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_str = str(save_path)
            for method_name in ("save_project", "saveas", "save"):
                try:
                    fn = getattr(g_i, method_name, None)
                    if fn is None:
                        continue
                    print(f"  g_i.{method_name}({save_str})")
                    fn(save_str)
                    saved_path = save_str
                    print(f"  Đã lưu PLAXIS file: {saved_path}")
                    break
                except Exception as e:
                    print(f"  g_i.{method_name} FAIL: {e}")
            if not saved_path:
                # Fallback: raw command
                try:
                    print(f"  Fallback: s_i.call_commands(['save', ...])")
                    s_i.call_commands([f'save "{save_str}"'])
                    saved_path = save_str
                except Exception as e:
                    print(f"  Raw save FAIL: {e}")
                    print(f"  → Lưu thủ công trong PLAXIS GUI: File > Save As")

        # 8. Log vào SQLite
        status = ("OK" if n_mat_ok == len(materials_to_create)
                  else f"PARTIAL_{n_mat_ok}/{len(materials_to_create)}")
        _log_push(
            bh_name, zone_code, x_in_plot, bh_data["elev"],
            len(bh_data["layers"]), n_mat_ok, len(materials_to_create),
            saved_path, status,
        )

        print()
        print(f"Hoàn tất push: {n_mat_ok}/{len(materials_to_create)} materials, "
              f"{len(bh_data['layers'])} layers"
              + (f", saved {saved_path}" if saved_path else ""))
        return {
            "materials": materials_to_create,
            "pushed": True,
            "n_layers": len(bh_data["layers"]),
            "n_materials_ok": n_mat_ok,
            "saved_path": saved_path,
        }

    finally:
        if not keep_connection and existing_session is None:
            try:
                s_i.close()
            except Exception:
                pass


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    parser = argparse.ArgumentParser(description="Push 1 HK từ SQLite → PLAXIS 2D")
    parser.add_argument("bh_name", help="Tên hố khoan (vd BXN-CV-HK1, ND-02, KE-HK1)")
    parser.add_argument("--x", type=float, default=0.0,
                         help="Tọa độ x trong plot PLAXIS (mặc định 0)")
    parser.add_argument("--dry-run", action="store_true",
                         help="Chỉ in kế hoạch, không push")
    parser.add_argument("--save", type=str, default=None,
                         help="Đường dẫn .p2dx — auto-save sau push")
    parser.add_argument("--no-reset", action="store_true",
                         help="KHÔNG reset project (giữ HK hiện có)")
    args = parser.parse_args()
    push_borehole_to_plaxis(
        args.bh_name, x_in_plot=args.x,
        dry_run=args.dry_run,
        save_file=args.save,
        reset_project=not args.no_reset,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
