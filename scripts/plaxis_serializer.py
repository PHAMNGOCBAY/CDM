"""
scripts/plaxis_serializer.py — Serialize PLAXIS model inputs từ SQLite ra JSON.

Mục đích: Knowledge persistence — script này thay vì cần PLAXIS GUI mở để debug
input, ta serialize toàn bộ "model recipe" (HK list + global layers + materials
+ Y geometry) ra JSON. Recipe có thể re-pushed sau lên PLAXIS bất kỳ máy nào.

Workflow:
  1. build_plaxis_model_recipe(zone_code) → dict (no PLAXIS connection)
  2. save_recipe_to_json(recipe, path) → file .json
  3. (optional) recreate trên máy khác: load_recipe + push_to_plaxis

Bảng SQLite mới: cdm_plaxis_model_recipes
  zone_code TEXT, recipe_json TEXT, n_bh INT, n_layers INT, n_materials INT,
  created_at TEXT, source_db TEXT
"""
from __future__ import annotations
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_ROOT = _HERE.parent
DB_LOCAL = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
DB_PROJ = _ROOT / "data" / "TTHC.sqlite"

SOFTSOIL_SYMBOLS = {"1", "1b", "XMD"}
SAND_SYMBOLS = {"F", "2a", "2b", "2c", "3a", "3b", "3c",
                 "4", "5", "5a", "5b", "6", "7", "8"}
DESIGN_ELEV_FILL = 2.7  # cao độ đỉnh đắp (Y dương lên)

ZONE_FILTERS = {
    "QTT": "name LIKE 'ND-%'",
    "BXN": "name LIKE 'BXN-CV-%'",
    "NHC": "name LIKE 'NHC-BH-%'",
    "KE_park": "name LIKE 'KE-HK%'",   # filter on_sw_alignment=0 trong join
    "KE_levee": "name LIKE 'KE-HK%'",  # filter on_sw_alignment=1
}


def _db_path() -> Path:
    return DB_LOCAL if DB_LOCAL.exists() else DB_PROJ


def _classify(symbol: str) -> str:
    if symbol in SOFTSOIL_SYMBOLS:
        return "SoftSoil"
    if symbol in SAND_SYMBOLS:
        return "MC_drained"
    return "MC_undrained"


def _fetch_selected_bhs(zone_code: str, db: Path) -> list[dict]:
    """Lấy HK selected của zone với toạ độ + cao độ tự nhiên."""
    base_filter = ZONE_FILTERS.get(zone_code)
    if not base_filter:
        raise ValueError(f"Unknown zone: {zone_code}")
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        if zone_code in ("KE_park", "KE_levee"):
            align_val = 0 if zone_code == "KE_park" else 1
            sql = f"""
                SELECT b.name, b.elevation_m AS nat_elev,
                       b.x_coord_m AS N, b.y_coord_m AS E
                FROM boreholes b
                JOIN tvtk_bh_cdm t ON t.bh_name = b.name
                JOIN ke_sw_design k ON k.bh_name = b.name
                WHERE t.selected = 1 AND t.H_soft_m > 0
                  AND b.{base_filter} AND k.on_sw_alignment = ?
                ORDER BY b.y_coord_m
            """
            rows = con.execute(sql, (align_val,)).fetchall()
        else:
            sql = f"""
                SELECT b.name, b.elevation_m AS nat_elev,
                       b.x_coord_m AS N, b.y_coord_m AS E
                FROM boreholes b
                JOIN tvtk_bh_cdm t ON t.bh_name = b.name
                WHERE t.selected = 1 AND t.H_soft_m > 0 AND b.{base_filter}
                ORDER BY b.y_coord_m
            """
            rows = con.execute(sql).fetchall()
        return [dict(r) for r in rows]


def _fetch_bh_layers(bh: str, db: Path) -> list[dict]:
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT symbol, depth_top_m, depth_bot_m, description
            FROM layers
            WHERE borehole_id = (SELECT id FROM boreholes WHERE name = ?)
            ORDER BY depth_top_m
        """, (bh,)).fetchall()
        return [dict(r) for r in rows]


def _fetch_bh_labs(bh: str, db: Path) -> list[dict]:
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT symbol_tcvn AS lab_sym, depth_from_m, depth_to_m,
                   gamma_kNm3, e0, Cc, Cs, PC_kPa, Cu_UU_kPa, c_kPa, phi_deg
            FROM lab_tests
            WHERE borehole_id = (SELECT id FROM boreholes WHERE name = ?)
        """, (bh,)).fetchall()
        return [dict(r) for r in rows]


def _aggregate_material(symbol: str, all_labs_for_symbol: list[dict]) -> dict:
    """Aggregate lab data for all BHs sharing this symbol → 1 representative material."""
    if not all_labs_for_symbol:
        return {
            "symbol": symbol, "model": _classify(symbol),
            "gamma_kNm3": 18.0, "Cu_kPa": 11.0, "phi_deg": 22.0,
            "Cc": 0.5, "e0": 1.5,
            "source": "DEFAULT (no lab data)",
        }
    def avg(field):
        vals = []
        for r in all_labs_for_symbol:
            v = r.get(field)
            if v is not None and v > 0:
                vals.append(v)
        return sum(vals) / len(vals) if vals else None

    return {
        "symbol": symbol, "model": _classify(symbol),
        "gamma_kNm3": avg("gamma_kNm3") or 18.0,
        "Cu_kPa": avg("Cu_UU_kPa") or avg("c_kPa") or 11.0,
        "phi_deg": avg("phi_deg") or 22.0,
        "Cc": avg("Cc") or 0.5,
        "e0": avg("e0") or 1.5,
        "PC_kPa": avg("PC_kPa"),
        "n_lab_samples": len(all_labs_for_symbol),
        "source": "Aggregated from lab_tests",
    }


def build_plaxis_model_recipe(
    zone_code: str,
    db_path: Optional[Path] = None,
) -> dict:
    """Build PLAXIS model recipe — JSON serializable, không kết nối PLAXIS.

    Returns dict:
      {
        zone_code, design_elev_fill_m, source_db, created_at,
        boreholes: [{name, nat_elev_m, E, N, layer_bottoms: {symbol: y_bot}}],
        global_layers: ["__FILL__", "1", "2a", ...],   # sort theo depth TB
        materials: {symbol: {model, gamma, Cu, phi, ...}},
        notes: [...]
      }
    """
    db = db_path or _db_path()
    if not db.exists():
        raise FileNotFoundError(f"SQLite not found: {db}")

    bhs = _fetch_selected_bhs(zone_code, db)
    if not bhs:
        raise ValueError(f"No selected BHs for zone {zone_code}")

    # Collect all (symbol, depth_TB) from all BHs
    all_layers = []
    bh_layer_map = {}
    for bh in bhs:
        bh_layers = _fetch_bh_layers(bh["name"], db)
        bh_layer_map[bh["name"]] = bh_layers
        for L in bh_layers:
            all_layers.append({
                "symbol": L["symbol"],
                "depth_TB": (L["depth_top_m"] + L["depth_bot_m"]) / 2,
            })

    # Global layer ordering: sort by mean depth across BHs
    symbol_depth = {}
    for L in all_layers:
        symbol_depth.setdefault(L["symbol"], []).append(L["depth_TB"])
    sorted_symbols = sorted(symbol_depth.keys(),
                             key=lambda s: sum(symbol_depth[s]) / len(symbol_depth[s]))

    global_layers = ["__FILL__"] + sorted_symbols

    # Materials per symbol (aggregate lab)
    materials = {}
    materials["__FILL__"] = {
        "symbol": "__FILL__", "model": "MC_drained",
        "gamma_kNm3": 18.0, "phi_deg": 32.0, "psi_deg": 2.0,
        "cRef_kPa": 1.0, "ERef_kPa": 25000.0, "nu": 0.30,
        "Identification": "FILL_dap_2.7m",
        "source": "Standard fill material",
    }
    for sym in sorted_symbols:
        # Aggregate labs of this symbol across all BHs
        all_labs_sym = []
        for bh in bhs:
            for lab in _fetch_bh_labs(bh["name"], db):
                if lab.get("lab_sym") == sym or sym in (lab.get("lab_sym") or ""):
                    all_labs_sym.append(lab)
        materials[sym] = _aggregate_material(sym, all_labs_sym)

    # Per-BH layer bottoms (in nat_elev coordinates)
    serializable_bhs = []
    for bh in bhs:
        bh_layers = bh_layer_map[bh["name"]]
        # For each global layer, find bottom y in this BH (or None if absent)
        nat_elev = bh["nat_elev"]
        layer_bottoms = {}
        layer_bottoms["__FILL__"] = nat_elev  # FILL bottom = nat surface
        for sym in sorted_symbols:
            match = next((L for L in bh_layers if L["symbol"] == sym), None)
            if match:
                layer_bottoms[sym] = nat_elev - match["depth_bot_m"]
            else:
                layer_bottoms[sym] = None  # absent in this BH
        serializable_bhs.append({
            "name": bh["name"], "nat_elev_m": nat_elev,
            "E": bh["E"], "N": bh["N"],
            "head_m": DESIGN_ELEV_FILL,
            "layer_bottoms_m": layer_bottoms,
        })

    return {
        "zone_code": zone_code,
        "design_elev_fill_m": DESIGN_ELEV_FILL,
        "source_db": str(db),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "n_boreholes": len(serializable_bhs),
        "n_global_layers": len(global_layers),
        "n_materials": len(materials),
        "boreholes": serializable_bhs,
        "global_layers": global_layers,
        "materials": materials,
        "notes": [
            "Recipe đầy đủ để re-create model PLAXIS không cần GUI mở.",
            "Y monotonic giảm xuống dưới (Y dương lên).",
            "Layer __FILL__ là layer 0 (đất đắp), Bottom = nat_elev.",
            "Per-BH: layer absent → bottom = bottom layer trên (zero thickness).",
            "Materials: SoftSoil cho lớp 1/1b/XMD, MC drained cho cát, MC undrained cho sét khác.",
        ],
    }


def save_recipe_to_json(recipe: dict, out_path: Path) -> int:
    """Lưu recipe ra JSON file. Return file size in bytes."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(recipe, ensure_ascii=False, indent=2)
    out_path.write_text(txt, encoding="utf-8")
    return out_path.stat().st_size


def save_recipe_to_sqlite(recipe: dict, db: Path) -> None:
    """Lưu recipe vào bảng cdm_plaxis_model_recipes (cho audit + portability)."""
    with sqlite3.connect(db) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS cdm_plaxis_model_recipes (
                zone_code TEXT PRIMARY KEY,
                recipe_json TEXT,
                n_bh INTEGER,
                n_layers INTEGER,
                n_materials INTEGER,
                source_db TEXT,
                created_at TEXT
            )
        """)
        con.execute("""
            INSERT OR REPLACE INTO cdm_plaxis_model_recipes
            (zone_code, recipe_json, n_bh, n_layers, n_materials,
             source_db, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (
            recipe["zone_code"],
            json.dumps(recipe, ensure_ascii=False),
            recipe["n_boreholes"],
            recipe["n_global_layers"],
            recipe["n_materials"],
            recipe["source_db"],
            recipe["created_at"],
        ))
        con.commit()


def load_recipe_from_sqlite(zone_code: str, db: Optional[Path] = None) -> Optional[dict]:
    db = db or _db_path()
    with sqlite3.connect(db) as con:
        row = con.execute(
            "SELECT recipe_json FROM cdm_plaxis_model_recipes WHERE zone_code = ?",
            (zone_code,)
        ).fetchone()
        if row:
            return json.loads(row[0])
        return None


def load_recipe_from_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ════════ DEMO ════════
if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 65)
    print("PLAXIS Model Recipe Serializer — TTHC")
    print("=" * 65)

    zones = ["KE_levee", "QTT", "NHC", "BXN", "KE_park"]
    for zone in zones:
        try:
            recipe = build_plaxis_model_recipe(zone)
            json_path = _ROOT / "plaxis_out" / f"recipe_{zone}.json"
            sz = save_recipe_to_json(recipe, json_path)
            # Save to both DBs
            for db in (DB_LOCAL, DB_PROJ):
                if db.exists() or db == DB_PROJ:
                    save_recipe_to_sqlite(recipe, db)
            print(f"  [{zone:>10s}] {recipe['n_boreholes']:>2d} HK, "
                  f"{recipe['n_global_layers']:>2d} layers, "
                  f"{recipe['n_materials']:>2d} mats → "
                  f"{json_path.name} ({sz/1024:.1f} KB)")
        except Exception as e:
            print(f"  [{zone:>10s}] SKIP: {type(e).__name__}: {e}")

    print()
    print("Bảng SQLite: cdm_plaxis_model_recipes (LOCAL + PROJECT)")
    print(f"JSON files:  plaxis_out/recipe_*.json")
