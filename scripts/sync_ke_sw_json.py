"""
sync_ke_sw_json.py — Đồng bộ data/ke_sw_202605_TTHC.json từ SQLite ke_sw_nt_detail.

Sau khi chạy `import_ke_spt.py` và `ke_sw_nt_calc.py`, JSON cũ vẫn còn note stale
như 'biên NT1 chỉ 0.3m' — script này cập nhật:
- pile_selection_summary.option_B.note (margin mới)
- boreholes[*].NT2_multilayer (Rs/Rp/RR/ratio mới với SPT)
- boreholes[*].NT1, NT2, margin_NT1 (status mới)
- NT2_multilayer_summary.method/phi_stat (đa phương pháp)
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).resolve().parent.parent
DB    = _ROOT / "data" / "TTHC.sqlite"
JSON_PATH = _ROOT / "data" / "ke_sw_202605_TTHC.json"


def main() -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    con  = sqlite3.connect(DB)
    cur  = con.cursor()

    # Đọc latest từ SQLite
    rows = {
        r[0].replace("KE-", ""): r
        for r in cur.execute("""
            SELECT bh_name, L_design_m, L_req_nt1_m, margin_nt1_m, nt1_result,
                   Rs_kN, Rs_clay_kN, Rs_sand_kN, Rp_kN, RR_kN, W_kN,
                   ratio_nt2, nt2_result, tip_symbol, tip_method, phi_stat
            FROM ke_sw_nt_detail ORDER BY bh_name
        """)
    }

    # Update boreholes[]
    for bh in data.get("boreholes", []):
        key = bh["name"]  # JSON dùng "HK10" không có prefix "KE-"
        if key not in rows:
            continue
        r = rows[key]
        bh["L_req_m"]       = round(r[2], 2)
        bh["margin_NT1_m"]  = round(r[3], 2)
        bh["NT1"]           = r[4]
        bh["NT2"]           = r[12]
        bh["W_pile_kN"]     = round(r[10], 1)
        bh["NT2_multilayer"] = {
            "Rs_kN":      round(r[5], 1),
            "Rs_clay_kN": round(r[6], 1) if r[6] is not None else None,
            "Rs_sand_kN": round(r[7], 1) if r[7] is not None else None,
            "Rp_kN":      round(r[8], 1),
            "RR_kN":      round(r[9], 1),
            "ratio":      round(r[11], 2),
            "tip_layer":  r[13],
            "tip_method": r[14],
            "phi_stat":   r[15],
        }

    # Update pile_selection_summary
    sum_ = data.setdefault("pile_selection_summary", {})
    if "HK10" in rows:
        margin_hk10 = rows["HK10"][3]
        opt_b = sum_.setdefault("option_B", {})
        opt_b["note"] = (
            f"Khu vực HK10 — NT1 với SW-840 biên {margin_hk10:+.2f} m "
            f"({rows['HK10'][4]}); cần SW-940 (L_max=30m) hoặc tăng L thiết kế"
        )

    # Max L_req hiện tại
    max_lreq = max((r[2] for r in rows.values()), default=0)
    sum_["max_L_req_m"] = round(max_lreq, 2)

    # NT1/NT2 controlling boreholes
    nt1_fail = [k for k, r in rows.items() if r[4] == "Không đạt"]
    if nt1_fail:
        sum_["controlling_borehole_NT1"] = nt1_fail[0]
    nt2_min_ratio = min(rows.values(), key=lambda r: r[11])
    sum_["controlling_borehole_NT2"] = nt2_min_ratio[0].replace("KE-", "")

    # Update method note
    nt2_sum = data.setdefault("NT2_multilayer_summary", {})
    nt2_sum["method"] = (
        "Đa phương pháp TCVN 11823-10:2017: "
        "α-method (Tomlinson 1980, sét, Điều 7.3.8.6.2, φ=0.35) + "
        "SPT-Meyerhof (cát, Điều 7.3.8.6.7, φ=0.30)"
    )
    nt2_sum["phi_stat"] = "dynamic (0.35 sét / 0.30 cát theo Bảng 9)"
    nt2_sum["spt_source"] = "data/ke_spt_data.json — N=N1+N2 (per user 2026-05-20)"
    nt2_sum["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    # Refresh results_by_borehole từ SQLite (hiển thị tất cả 12 HK nếu có)
    nt2_sum["results_by_borehole"] = [
        {
            "name":      bh_key,
            "pile":      data.get("boreholes", [{}])[0].get("recommended_pile", "SW-840"),
            "tip_layer": r[13],
            "tip_method": r[14],
            "Rs":        round(r[5], 1),
            "Rs_clay":   round(r[6], 1) if r[6] is not None else None,
            "Rs_sand":   round(r[7], 1) if r[7] is not None else None,
            "Rp":        round(r[8], 1),
            "RR":        round(r[9], 1),
            "W":         round(r[10], 1),
            "ratio":     round(r[11], 2),
            "phi_stat":  r[15],
            "pass":      r[12] == "Đạt",
        }
        for bh_key, r in sorted(rows.items())
    ]

    con.close()
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Đã cập nhật {JSON_PATH.relative_to(_ROOT)}")
    print(f"  - 7 HK cập nhật từ ke_sw_nt_detail")
    print(f"  - HK10 margin: {rows['HK10'][3]:+.2f}m ({rows['HK10'][4]})")
    print(f"  - max L_req: {max_lreq:.2f}m")


if __name__ == "__main__":
    main()
