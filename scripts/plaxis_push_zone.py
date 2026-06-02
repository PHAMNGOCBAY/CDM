"""
plaxis_push_zone.py — Push nhiều HK của 1 zone vào PLAXIS 2D đang mở.

Pipeline:
  1. Đọc HK selected từ tvtk_bh_cdm cho zone
  2. Sắp theo Easting tăng dần
  3. Push từng HK với x_in_plot = scaled Easting (gốc = HK đầu tiên)
  4. Auto-save .p2dx
  5. Log vào cdm_plaxis_push_log

Chạy:
  $env:PLAXIS_PASSWORD = '...'
  python scripts/plaxis_push_zone.py BXN [--save out.p2dx] [--scale 1.0]
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

from plaxis_connect import connect_input  # noqa: E402
from plaxis_push_borehole import (  # noqa: E402
    push_borehole_to_plaxis, _DB, _log_push, _create_push_log_table, _DB_LOCAL,
)
from qtt_cdm_analysis import get_zone_selected_hks  # noqa: E402


def push_zone_to_plaxis(zone_code: str,
                         save_file: str | None = None,
                         scale_factor: float = 1.0,
                         max_hks: int | None = None,
                         db_path: Path | None = None) -> dict:
    """Push toàn bộ HK selected của 1 zone vào PLAXIS.

    scale_factor: nhân Easting để compress khoảng cách (vd 0.1 = 1/10).
                  Default 1.0 = giữ nguyên tỉ lệ thật.
    max_hks: chỉ push N HK đầu (cho debug).
    """
    db = db_path or _DB
    hks = get_zone_selected_hks(zone_code, db_path=db)
    if not hks:
        print(f"Zone {zone_code}: không có HK nào selected + H_soft > 0")
        return {"n_pushed": 0, "n_total": 0}

    # Sắp theo Easting (y_coord_m = Easting trong project §10)
    hks_sorted = sorted(
        [h for h in hks if h.get("E") is not None],
        key=lambda h: float(h["E"]),
    )
    if max_hks:
        hks_sorted = hks_sorted[:max_hks]

    E0 = float(hks_sorted[0]["E"])
    print(f"=== Zone {zone_code}: {len(hks_sorted)} HK selected ===")
    print(f"  Easting range: {E0:.0f} → {float(hks_sorted[-1]['E']):.0f}")
    print(f"  scale_factor : {scale_factor}")
    print()

    # Đảm bảo bảng log tồn tại ở 2 DB
    for d in (_DB_LOCAL, _DB):
        if d.exists() or d == _DB:
            try:
                _create_push_log_table(d)
            except Exception:
                pass

    # 1 connection cho cả batch
    print("Kết nối PLAXIS...")
    try:
        s_i, g_i = connect_input()
    except Exception as e:
        print(f"FAIL connect: {e}")
        return {"n_pushed": 0, "n_total": len(hks_sorted), "error": str(e)}

    print("  s_i.new() — clean project")
    try:
        s_i.new()
    except Exception as e:
        print(f"  s_i.new() FAIL: {e}")
        s_i.close()
        return {"n_pushed": 0, "n_total": len(hks_sorted), "error": str(e)}

    results = []
    n_ok = 0
    for i, hk in enumerate(hks_sorted):
        name = hk["bh_name"]
        E = float(hk["E"])
        x_plot = (E - E0) * scale_factor
        print()
        print(f"--- [{i+1}/{len(hks_sorted)}] {name} @ x={x_plot:.1f} ---")
        try:
            r = push_borehole_to_plaxis(
                name, x_in_plot=x_plot,
                zone_code=zone_code,
                reset_project=False,  # GIỮ project, push thêm BH mới
                existing_session=(s_i, g_i),
                keep_connection=True,
            )
            results.append({"bh": name, "x": x_plot, **r})
            if r.get("pushed") and r.get("n_materials_ok"):
                n_ok += 1
        except Exception as e:
            print(f"  ERR: {e}")
            results.append({"bh": name, "x": x_plot, "pushed": False,
                            "error": str(e)})

    # Auto-save — thử nhiều method
    saved_path = None
    if save_file:
        save_path = Path(save_file).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_str = str(save_path)
        print()
        print(f"Auto-save: {save_path}")
        for method_name in ("save_project", "saveas", "save"):
            try:
                fn = getattr(g_i, method_name, None)
                if fn is None:
                    continue
                print(f"  g_i.{method_name}(...)")
                fn(save_str)
                saved_path = save_str
                print(f"  OK")
                break
            except Exception as e:
                print(f"  g_i.{method_name} FAIL: {e}")
        if not saved_path:
            try:
                print(f"  Fallback: raw command")
                s_i.call_commands([f'save "{save_str}"'])
                saved_path = save_str
                print(f"  OK")
            except Exception as e:
                print(f"  Raw save FAIL: {e}")
                print(f"  → Lưu thủ công trong PLAXIS GUI: File > Save As")

    s_i.close()

    print()
    print("=" * 60)
    print(f"ZONE {zone_code}: {n_ok}/{len(hks_sorted)} HK push thành công")
    if saved_path:
        print(f"File: {saved_path}")
    print("=" * 60)

    # Log batch summary
    if saved_path:
        # Update saved_path cho mọi log entry trong batch này
        from datetime import datetime
        ts_recent = datetime.now().isoformat(timespec="seconds")[:10]  # date
        for d in (_DB_LOCAL, _DB):
            if not d.exists() and d == _DB_LOCAL:
                continue
            try:
                with sqlite3.connect(d) as con:
                    con.execute("""
                        UPDATE cdm_plaxis_push_log
                        SET file_path = ?
                        WHERE zone_code = ? AND push_timestamp LIKE ?
                          AND (file_path IS NULL OR file_path = '')
                    """, (saved_path, zone_code, f"{ts_recent}%"))
                    con.commit()
            except Exception:
                pass

    return {
        "n_pushed": n_ok,
        "n_total": len(hks_sorted),
        "saved_path": saved_path,
        "results": results,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    parser = argparse.ArgumentParser(
        description="Push toàn bộ HK selected của 1 zone vào PLAXIS 2D",
    )
    parser.add_argument(
        "zone_code",
        help="Zone (QTT, BXN, NHC, KE_park, KE_levee)",
    )
    parser.add_argument("--save", type=str, default=None,
                         help="Auto-save .p2dx sau khi push xong")
    parser.add_argument("--scale", type=float, default=1.0,
                         help="Hệ số scale Easting (mặc định 1.0)")
    parser.add_argument("--max", type=int, default=None,
                         help="Chỉ push N HK đầu (cho debug)")
    args = parser.parse_args()
    push_zone_to_plaxis(
        args.zone_code,
        save_file=args.save,
        scale_factor=args.scale,
        max_hks=args.max,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
