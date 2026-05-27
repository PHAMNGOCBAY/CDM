# -*- coding: utf-8 -*-
"""Cấu tạo tải trọng đắp trên nền CDM — TKCS (module tvtk_).

Lưu cấu tạo các lớp đắp phía trên cao độ thiết kế (áo đường, cát đắp, đệm cát)
làm NGUỒN CHÍNH để suy ra tải phân bố q = Σ(h_i · γ_i) [kPa].

Nguồn chính (single source of truth):
    SQLite  : bảng `tvtk_fill_composition` (computed/config — list các lớp)
    JSON    : `data/tvtk_cdm_202605_TTHC.json` → khối "fill_composition" (snapshot)

q và cao độ thiết kế đồng bộ vào `tvtk_cdm_config` (q_kPa, settlement_design_elev_m)
để các tính toán khác đọc nhất quán.

Đơn vị: h [m] · γ [kN/m³] · q [kPa = kN/m²].
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

# Cấu tạo mặc định TTHC (cao độ thiết kế = 2,70 m)
DESIGN_ELEV_M_DEFAULT: float = 2.70

# Mỗi lớp: (thứ tự, tên, h_m, gamma_kNm3)
FILL_LAYERS_DEFAULT: list[tuple[int, str, float, float]] = [
    (1, "Áo đường", 0.80, 24.00),
    (2, "He — cát đắp", 0.70, 18.00),
    (3, "Hse — đệm cát", 0.40, 22.50),
]


def _default_db_path() -> Path:
    """DB ưu tiên local (ngoài Drive) như app dùng, fallback data/ trong project."""
    local = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
    if local.exists():
        return local
    return Path(__file__).resolve().parent.parent / "data" / "TTHC.sqlite"


def create_fill_composition_table(db_path: Optional[Path] = None) -> None:
    """Tạo bảng (idempotent)."""
    db_path = Path(db_path) if db_path else _default_db_path()
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS tvtk_fill_composition (
                layer_order      INTEGER PRIMARY KEY,
                name             TEXT NOT NULL,
                h_m              REAL NOT NULL,
                gamma_kNm3       REAL NOT NULL,
                q_component_kPa  REAL NOT NULL,
                design_elev_m    REAL,
                updated_at       TEXT
            )
            """
        )
        con.commit()
    finally:
        con.close()


def compute_q_kPa(layers: list[tuple[int, str, float, float]]) -> float:
    """q = Σ(h_i · γ_i) [kPa]."""
    return round(sum(h * g for _, _, h, g in layers), 4)


def total_thickness_m(layers: list[tuple[int, str, float, float]]) -> float:
    return round(sum(h for _, _, h, _ in layers), 4)


def update_db_fill_composition(
    layers: Optional[list[tuple[int, str, float, float]]] = None,
    design_elev_m: float = DESIGN_ELEV_M_DEFAULT,
    db_path: Optional[Path] = None,
    sync_config: bool = True,
) -> dict:
    """Ghi cấu tạo lớp đắp vào SQLite (INSERT OR REPLACE, idempotent).

    sync_config=True: đồng bộ q_kPa + settlement_design_elev_m vào tvtk_cdm_config.
    Trả về dict tóm tắt {q_kPa, total_h_m, n_layers, design_elev_m, db_path}.
    """
    layers = layers or FILL_LAYERS_DEFAULT
    db_path = Path(db_path) if db_path else _default_db_path()
    create_fill_composition_table(db_path)

    q_total = compute_q_kPa(layers)
    h_total = total_thickness_m(layers)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    con = sqlite3.connect(db_path)
    try:
        # Xóa các lớp cũ không còn trong danh sách mới (tránh sót row thừa)
        keep = {o for o, _, _, _ in layers}
        existing = [r[0] for r in con.execute("SELECT layer_order FROM tvtk_fill_composition")]
        for o in existing:
            if o not in keep:
                con.execute("DELETE FROM tvtk_fill_composition WHERE layer_order=?", (o,))

        for order, name, h, g in layers:
            con.execute(
                """
                INSERT OR REPLACE INTO tvtk_fill_composition
                    (layer_order, name, h_m, gamma_kNm3, q_component_kPa, design_elev_m, updated_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (order, name, h, g, round(h * g, 4), design_elev_m, ts),
            )

        if sync_config:
            # tvtk_cdm_config là single-row config — cập nhật q + cao độ thiết kế
            con.execute(
                """
                UPDATE tvtk_cdm_config
                   SET q_kPa = ?, settlement_design_elev_m = ?, updated_at = ?
                 WHERE id = 1
                """,
                (q_total, design_elev_m, ts),
            )
        con.commit()
    finally:
        con.close()

    return {
        "q_kPa": q_total,
        "total_h_m": h_total,
        "n_layers": len(layers),
        "design_elev_m": design_elev_m,
        "db_path": str(db_path),
    }


def update_json_snapshot(
    layers: Optional[list[tuple[int, str, float, float]]] = None,
    design_elev_m: float = DESIGN_ELEV_M_DEFAULT,
    json_path: Optional[Path] = None,
) -> dict:
    """Ghi khối fill_composition vào JSON snapshot (debug/single-source)."""
    layers = layers or FILL_LAYERS_DEFAULT
    json_path = Path(json_path) if json_path else (
        Path(__file__).resolve().parent.parent / "data" / "tvtk_cdm_202605_TTHC.json"
    )
    data = json.loads(json_path.read_text(encoding="utf-8"))
    q_total = compute_q_kPa(layers)

    data["fill_composition"] = {
        "design_elev_m": design_elev_m,
        "layers": [
            {
                "order": o,
                "name": n,
                "h_m": h,
                "gamma_kNm3": g,
                "q_component_kPa": round(h * g, 4),
            }
            for o, n, h, g in layers
        ],
        "total_h_m": total_thickness_m(layers),
        "q_kPa": q_total,
        "_formula": "q = Σ(h_i · γ_i)",
    }
    # đồng bộ config block
    data.setdefault("config", {})["q_kPa"] = q_total
    data["config"]["settlement_design_elev_m"] = design_elev_m
    data.setdefault("_meta", {})["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return data["fill_composition"]


if __name__ == "__main__":
    # Cập nhật cả 2 DB (local đang chạy + data/ để commit/deploy) + JSON
    root = Path(__file__).resolve().parent.parent
    targets = [
        Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite"),
        root / "data" / "TTHC.sqlite",
    ]
    for db in targets:
        if db.exists():
            res = update_db_fill_composition(db_path=db)
            print(f"[DB] {db}\n     q={res['q_kPa']} kPa | Σh={res['total_h_m']} m | "
                  f"cao độ TK={res['design_elev_m']} m | {res['n_layers']} lớp")
        else:
            print(f"[SKIP] không thấy {db}")

    fc = update_json_snapshot()
    print(f"[JSON] fill_composition: q={fc['q_kPa']} kPa, Σh={fc['total_h_m']} m, "
          f"{len(fc['layers'])} lớp, cao độ TK={fc['design_elev_m']} m")
