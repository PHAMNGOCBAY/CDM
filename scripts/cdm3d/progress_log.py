"""cdm3d.progress_log — Ghi tien do tinh toan OpenSeesPy theo tung buoc tang tai
(giong duong cong tinh toan truc tiep cua PLAXIS "Calculation progress") va ve
bieu do BAT KY LUC NAO tu file CSV dang ghi do — khong can doi tien trinh chinh
chay xong. Dung cho cac phan tich lau (nhieu giai doan, nhieu buoc Newton) de
theo doi tien do thay vi doan qua CPU time.

Cach dung trong vong lap phan tich:
    from cdm3d.progress_log import append_row, plot_progress
    csv_path = Path("...").with_suffix(".progress.csv")
    init_csv(csv_path)
    global_step = 0
    for stage in stages:
        ... ops.load(...) ...
        for i in range(n_steps):
            ok = ops.analyze(1)
            global_step += 1
            ux = ops.nodeDisp(node_tag, 1) * 1000.0
            append_row(csv_path, global_step, stage.name, (i+1)/n_steps, ux, ok)

Ve bieu do tien do (co the goi trong 1 tien trinh KHAC, doc lap, trong khi
tien trinh chinh van dang chay):
    from cdm3d.progress_log import plot_progress
    plot_progress(csv_path, out_png)
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

_HEADER = ["global_step", "elapsed_s", "stage_name", "load_frac", "ux_mm", "ok"]


def init_csv(csv_path: Path) -> float:
    """Tao file CSV moi, tra ve moc thoi gian t0 (dung cho elapsed_s cua append_row)."""
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(_HEADER)
    return time.time()


def append_row(csv_path: Path, global_step: int, t0: float, stage_name: str,
                load_frac: float, ux_mm: float, ok: int) -> None:
    """Ghi 1 dong + flush + dong file NGAY — an toan doc duoc tu tien trinh
    khac bat ky luc nao (khong bi lock/corrupt do ghi do). elapsed_s = thoi
    gian THUC (giay) ke tu init_csv() — dung ve truc X thoi gian chay that,
    khong phai so buoc."""
    elapsed_s = time.time() - t0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([global_step, f"{elapsed_s:.2f}", stage_name, f"{load_frac:.4f}",
                    f"{ux_mm:.6f}", ok])
        f.flush()


def read_progress(csv_path: Path) -> list[dict]:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return []
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def plot_progress(csv_path: Path, out_png: Path, title: str = "") -> Path | None:
    """Ve duong cong Ux (mm) theo global_step, mau theo giai doan — kieu PLAXIS
    Calculation progress. Doc duoc NGAY CA KHI file CSV dang duoc ghi tiep (chi
    doc cac dong da flush xong). Tra ve None neu chua co du lieu."""
    rows = read_progress(csv_path)
    if not rows:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    stages = []
    for r in rows:
        if r["stage_name"] not in stages:
            stages.append(r["stage_name"])
    colors = plt.cm.tab10.colors

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, stage_name in enumerate(stages):
        xs = [float(r["elapsed_s"]) / 60.0 for r in rows if r["stage_name"] == stage_name]
        ys = [float(r["ux_mm"]) for r in rows if r["stage_name"] == stage_name]
        ax.plot(xs, ys, marker="o", markersize=3, color=colors[i % len(colors)], label=stage_name)

    ax.set_xlabel("Thời gian chạy thực (phút)")
    ax.set_ylabel("Chuyển vị ngang Ux tại đỉnh cọc (mm)")
    ax.set_title(title or "Tiến độ tính toán theo thời gian thực (kiểu PLAXIS)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    n_done = len(rows)
    last_ux = float(rows[-1]["ux_mm"])
    last_t = float(rows[-1]["elapsed_s"]) / 60.0
    ax.annotate(f"Đã chạy {last_t:.1f} phút — bước {n_done}: Ux={last_ux:.2f}mm",
                xy=(1, 1), xycoords="axes fraction",
                ha="right", va="bottom", fontsize=9, color="gray")
    fig.tight_layout()
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=120)
    plt.close(fig)
    return out_png
