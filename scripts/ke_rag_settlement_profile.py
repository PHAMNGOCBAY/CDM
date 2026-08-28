"""
ke_rag_settlement_profile.py — Dự báo lún dọc tuyến Kè KE tại cao độ thiết kế cho trước.

Nguồn số liệu: SQLite (lab_tests, boreholes) — KHÔNG dùng ChromaDB để tính toán,
chỉ dùng ChromaDB/Gemma để viết nhận xét kỹ thuật DỰA TRÊN số liệu đã tính thật,
đúng quy tắc dự án "không tự tính công thức bằng LLM".

Dùng lại settlement_calc.calc_settlement_from_db() — không phát minh công thức mới.
"""
import os
import sys
import io
import sqlite3
import requests
import numpy as np
import matplotlib.pyplot as plt

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
import settlement_calc as sc

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'TTHC.sqlite')
DESIGN_ELEV_M = 2.7
OLLAMA_MODEL = "gemma4:26b"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'results', 'settlement_profile')


def get_ke_boreholes():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT name, x_coord_m, y_coord_m, elevation_m FROM boreholes "
        "WHERE name LIKE 'KE-%' AND x_coord_m IS NOT NULL ORDER BY name"
    ).fetchall()
    con.close()
    return rows


def compute_chainage(boreholes):
    """PCA-SVD: chiếu (x,y) lên trục chính của tuyến -> lý trình tăng dần (giống mục 22/38 CLAUDE.md)."""
    xy = np.array([[r[1], r[2]] for r in boreholes], dtype=float)
    xy_c = xy - xy.mean(axis=0)
    _, _, vt = np.linalg.svd(xy_c, full_matrices=False)
    chainage = xy_c @ vt[0]
    chainage -= chainage.min()
    return chainage


def main():
    boreholes = get_ke_boreholes()
    if not boreholes:
        print("Không tìm thấy hố khoan KE nào có tọa độ.")
        return

    chainage = compute_chainage(boreholes)
    order = np.argsort(chainage)

    results = []
    for idx in order:
        name, x, y, elev = boreholes[idx]
        H_fill = max(0.0, DESIGN_ELEV_M - elev)
        r = sc.calc_settlement_from_db(name, H_fill_m=H_fill)
        results.append({
            "name": name, "chainage_m": round(float(chainage[idx]), 1),
            "elevation_m": elev, "H_fill_m": round(H_fill, 2),
            "S_total_cm": r["S_total_cm"], "warning": r["warning"],
        })
        s_str = f"{r['S_total_cm']} cm" if r["S_total_cm"] is not None else "KHÔNG có mẫu"
        print(f"{name}: lý trình={chainage[idx]:6.1f}m  cao_độ_TN={elev:5.2f}m  "
              f"H_đắp={H_fill:4.2f}m  S_dự_báo={s_str}"
              + (f"  [{r['warning']}]" if r["warning"] else ""))

    os.makedirs(RESULTS_DIR, exist_ok=True)

    # ── Biểu đồ trắc dọc dự báo lún ──
    xs = [r["chainage_m"] for r in results]
    ys = [r["S_total_cm"] if r["S_total_cm"] is not None else 0.0 for r in results]
    names = [r["name"].replace("KE-", "") for r in results]
    has_data = [r["S_total_cm"] is not None for r in results]

    fig, ax = plt.subplots(figsize=(13, 5.5))
    ax.plot(xs, ys, marker='o', color='#D32F2F', linewidth=2, markersize=7, label='Độ lún dự báo (cm)')
    for x, y, n, ok in zip(xs, ys, names, has_data):
        label = n if ok else f"{n}\n(thiếu mẫu)"
        ax.annotate(label, (x, y), textcoords="offset points", xytext=(0, 10),
                    ha='center', fontsize=8, color='#333' if ok else '#999')
    ax.set_xlabel("Lý trình dọc tuyến (m)")
    ax.set_ylabel("Độ lún dự báo (cm)")
    ax.set_title(f"Trắc dọc dự báo độ lún — Kè Công viên (KE)\nCao độ thiết kế +{DESIGN_ELEV_M:.1f}m "
                 f"(tính từ dữ liệu thí nghiệm SQLite, không xử lý nền)")
    ax.grid(True, linestyle='--', alpha=0.4)
    ax.invert_yaxis()
    ax.legend(loc='lower right')
    fig.tight_layout()
    out_path = os.path.join(RESULTS_DIR, "trac_doc_du_bao_lun_KE.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"\nĐã xuất biểu đồ trắc dọc: {out_path}")

    # ── Gemma: CHỈ viết nhận xét dựa trên số liệu THẬT đã tính, không tự tính toán ──
    summary_lines = "\n".join(
        f"- {r['name']} (lý trình {r['chainage_m']}m): H_đắp={r['H_fill_m']}m, "
        f"S_dự_báo={r['S_total_cm'] if r['S_total_cm'] is not None else 'không có mẫu'} cm"
        for r in results
    )
    prompt = f"""Bạn là kỹ sư địa kỹ thuật. Dưới đây là KẾT QUẢ TÍNH LÚN THẬT (đã tính bằng công thức cố kết
TCCS41 từ dữ liệu thí nghiệm nén cố kết trong SQLite — không phải bạn tự tính) cho các hố khoan
dọc tuyến kè KE với cao độ thiết kế +{DESIGN_ELEV_M}m:

{summary_lines}

Hãy viết NHẬN XÉT KỸ THUẬT ngắn gọn (5-8 câu) về: hố khoan nào có lún dự báo lớn nhất/đáng lo
ngại nhất, xu hướng lún dọc tuyến, và khuyến nghị sơ bộ. CHỈ dựa trên số liệu trên, TUYỆT ĐỐI
KHÔNG bịa thêm số liệu mới hoặc tự tính lại."""

    try:
        # Model 26B có thể đã bị Ollama tự giải phóng khỏi VRAM sau vài phút không dùng
        # (keep_alive mặc định 5 phút) -> gọi "warm-up" nhẹ trước để ép nạp model,
        # tách riêng thời gian NẠP MODEL khỏi timeout của lần gọi thật bên dưới.
        print("\nĐang \"làm nóng\" model (nạp lại vào VRAM nếu đã bị giải phóng)...")
        try:
            requests.post("http://localhost:11434/api/generate",
                           json={"model": OLLAMA_MODEL, "prompt": "OK", "stream": False, "keep_alive": "30m"},
                           timeout=300)
        except requests.exceptions.RequestException:
            pass  # nếu warm-up cũng timeout thì để lần gọi thật bên dưới báo lỗi rõ ràng hơn

        resp = requests.post("http://localhost:11434/api/generate",
                              json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "keep_alive": "30m"},
                              timeout=300)
        if resp.status_code == 200:
            comment = resp.json().get("response", "")
            print("\n--- NHẬN XÉT TỪ GEMMA (dựa trên số liệu thật đã tính) ---")
            print(comment)
            with open(os.path.join(RESULTS_DIR, "nhan_xet_gemma.txt"), "w", encoding="utf-8") as f:
                f.write(comment)
        else:
            print(f"Lỗi Ollama: {resp.status_code} - {resp.text}")
    except requests.exceptions.RequestException as e:
        print(f"Không kết nối được Ollama: {e}")


if __name__ == "__main__":
    main()
