"""variants_db.py — SQLite helper: lưu trữ và so sánh nhiều phương án thiết kế.

DB file: data/variants.sqlite  (tự tạo nếu chưa có)
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DB_PATH = Path(__file__).parent.parent / "data" / "variants.sqlite"

# ── Schema ─────────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS variants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    created_at      TEXT    NOT NULL,
    description     TEXT,

    -- Key inputs (so sánh nhanh)
    pile_name       TEXT,
    pile_length     REAL,
    top_elev        REAL,

    -- Key results (cột riêng để vẽ biểu đồ so sánh)
    fos_bishop      REAL,
    fos_spencer     REAL,
    fos_fellenius   REAL,
    fos_mp          REAL,
    q_allow         REAL,
    head_defl_mm    REAL,
    max_moment      REAL,

    -- Snapshot đầy đủ
    inputs_json     TEXT,
    results_json    TEXT
);
"""


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_DDL)
        conn.commit()


# ── Helpers trích xuất kết quả ─────────────────────────────────────────────────

def _fos_from_results(results_json: dict, method: str) -> float | None:
    sl_all = results_json.get("sl_results_all", {})
    entry  = sl_all.get(method, {})
    crit   = entry.get("critical")
    if crit is None:
        return None
    try:
        return float(crit.FOS)
    except Exception:
        try:
            return float(crit["FOS"])
        except Exception:
            return None


def _extract_key_results(inputs: dict, results: dict) -> dict:
    """Trích xuất các KPI chính từ session_state results."""
    import numpy as np

    # Slope stability
    fos_bishop    = _fos_from_results(results, "bishop")
    fos_spencer   = _fos_from_results(results, "spencer")
    fos_fellenius = _fos_from_results(results, "fellenius")
    fos_mp        = _fos_from_results(results, "morgenstern_price")

    # Bearing capacity — dùng phương án "auto" nếu có, fallback sang bc_result
    q_allow: float | None = None
    bc_all = results.get("bc_all_methods", {})
    for m in ("auto", "nordlund", "tomlinson", "beta"):
        entry = bc_all.get(m, {})
        if "Q_allow" in entry:
            try:
                q_allow = float(entry["Q_allow"])
                break
            except Exception:
                pass
    if q_allow is None:
        bc_res = results.get("bc_result")
        if isinstance(bc_res, dict):
            q_allow = bc_res.get("Q_allow")

    # P-y deflection + moment
    head_defl_mm: float | None = None
    max_moment: float | None   = None
    py_res = results.get("result")
    if py_res is not None:
        try:
            defl = py_res.deflection
            head_defl_mm = float(defl[0]) * 1000.0
        except Exception:
            pass
        try:
            forces = py_res.forces
            max_moment = float(np.max(np.abs(forces[:, 2])))
        except Exception:
            pass

    return {
        "fos_bishop":    fos_bishop,
        "fos_spencer":   fos_spencer,
        "fos_fellenius": fos_fellenius,
        "fos_mp":        fos_mp,
        "q_allow":       q_allow,
        "head_defl_mm":  head_defl_mm,
        "max_moment":    max_moment,
    }


# ── CRUD ───────────────────────────────────────────────────────────────────────

def save_variant(
    name: str,
    description: str,
    inputs: dict,
    results: dict,
) -> int:
    """Lưu phương án mới. Trả về id."""
    init_db()
    kpi = _extract_key_results(inputs, results)

    inputs_json_str  = json.dumps(inputs,   ensure_ascii=False, default=str)
    results_json_str = json.dumps(
        {k: v for k, v in results.items() if _is_jsonable(v)},
        ensure_ascii=False, default=str,
    )

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO variants
              (name, created_at, description,
               pile_name, pile_length, top_elev,
               fos_bishop, fos_spencer, fos_fellenius, fos_mp,
               q_allow, head_defl_mm, max_moment,
               inputs_json, results_json)
            VALUES (?,?,?, ?,?,?, ?,?,?,?, ?,?,?, ?,?)
            """,
            (
                name.strip(),
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                description.strip(),
                inputs.get("sel_pile",  ""),
                inputs.get("L_m"),
                inputs.get("top_elev"),
                kpi["fos_bishop"],   kpi["fos_spencer"],
                kpi["fos_fellenius"], kpi["fos_mp"],
                kpi["q_allow"],      kpi["head_defl_mm"],
                kpi["max_moment"],
                inputs_json_str,
                results_json_str,
            ),
        )
        conn.commit()
        return cur.lastrowid


def list_variants() -> list[dict]:
    """Danh sách tất cả phương án (không có JSON blob), mới nhất trước."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT id, name, created_at, description,
                      pile_name, pile_length, top_elev,
                      fos_bishop, fos_spencer, fos_fellenius, fos_mp,
                      q_allow, head_defl_mm, max_moment
               FROM variants ORDER BY id DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def load_variant_inputs(variant_id: int) -> dict:
    """Trả về inputs dict để restore vào session_state."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT inputs_json FROM variants WHERE id=?", (variant_id,)
        ).fetchone()
    if row is None:
        return {}
    return json.loads(row["inputs_json"] or "{}")


def delete_variant(variant_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM variants WHERE id=?", (variant_id,))
        conn.commit()


def rename_variant(variant_id: int, name: str, description: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE variants SET name=?, description=? WHERE id=?",
            (name.strip(), description.strip(), variant_id),
        )
        conn.commit()


# ── Util ───────────────────────────────────────────────────────────────────────

def _is_jsonable(v: Any) -> bool:
    """Kiểm tra xem giá trị có thể JSON-serialize không."""
    try:
        json.dumps(v, default=str)
        return True
    except Exception:
        return False
