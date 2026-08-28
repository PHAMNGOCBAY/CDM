"""
plot_download_progress.py — Vẽ lại biểu đồ tiến độ tải model từ file CSV log.
Gọi lại mỗi khi có điểm dữ liệu mới -> file PNG luôn là bản mới nhất ("biểu đồ động"
theo kiểu tự cập nhật trên đĩa, không phải cửa sổ auto-refresh trên màn hình).

Dùng: python plot_download_progress.py <đường_dẫn_csv> <đường_dẫn_png_output> [tổng_dung_lượng_MB]
CSV có cột: epoch_s,pct,mb,speed_kbs (không có header). Cột đầu là mốc thời gian TUYỆT ĐỐI
(epoch giây) — không phải "số giây kể từ lúc script chạy" — để dù Monitor bị dừng/khởi động
lại nhiều lần, trục thời gian trên biểu đồ vẫn liên tục, không bị nhảy lùi về 0.
"""
import sys
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    if len(sys.argv) < 3:
        print("Cần: csv_path png_path [total_mb]")
        return
    csv_path = sys.argv[1]
    png_path = sys.argv[2]
    total_mb = float(sys.argv[3]) if len(sys.argv) > 3 else 25500.0

    rows = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            for line in csv.reader(f):
                if len(line) < 4:
                    continue
                rows.append((float(line[0]), float(line[1]), float(line[2]), float(line[3])))
    except FileNotFoundError:
        print("Chưa có dữ liệu.")
        return

    if not rows:
        return

    t0 = min(r[0] for r in rows)
    t = [(r[0] - t0) / 60.0 for r in rows]   # phút, tương đối so với điểm đầu tiên từng ghi
    pct = [r[1] for r in rows]
    mb = [r[2] for r in rows]
    speed_mbs = [r[3] / 1024.0 for r in rows]  # KB/s -> MB/s

    # Thưa bớt nhãn nếu có nhiều điểm, tránh chữ đè lên nhau; luôn label điểm cuối.
    n = len(t)
    step = max(1, n // 15)
    label_idx = set(range(0, n, step))
    label_idx.add(n - 1)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True)

    ax1.plot(t, pct, color="#1565C0", linewidth=2, marker="o", markersize=3)
    for i in label_idx:
        is_last = (i == n - 1)
        ax1.annotate(f"{pct[i]:.2f}%", (t[i], pct[i]),
                     textcoords="offset points", xytext=(0, 8), ha="center",
                     fontsize=9 if is_last else 7.5,
                     fontweight="bold" if is_last else "normal",
                     color="#0D47A1" if is_last else "#5A5A5A")
    ax1.set_ylabel("Tiến độ (%)")
    ax1.set_ylim(0, 108)
    ax1.set_title(f"Tiến độ tải model — hiện tại: {pct[-1]:.2f}% (~{mb[-1]:.0f} / {total_mb:.0f} MB)")
    ax1.grid(True, linestyle="--", alpha=0.4)

    ax2.plot(t, speed_mbs, color="#D32F2F", linewidth=1.5)
    ax2.fill_between(t, speed_mbs, color="#D32F2F", alpha=0.15)
    for i in label_idx:
        is_last = (i == n - 1)
        ax2.annotate(f"{speed_mbs[i]:.1f}", (t[i], speed_mbs[i]),
                     textcoords="offset points", xytext=(0, 8), ha="center",
                     fontsize=9 if is_last else 7.5,
                     fontweight="bold" if is_last else "normal",
                     color="#B71C1C" if is_last else "#8A8A8A")
    ax2.set_ylabel("Tốc độ (MB/s)")
    ax2.set_xlabel("Thời gian (phút)")
    ax2.set_title(f"Tốc độ tải hiện tại: {speed_mbs[-1]:.2f} MB/s "
                  f"(trung bình: {sum(speed_mbs)/len(speed_mbs):.2f} MB/s)")
    ax2.set_ylim(0, max(speed_mbs) * 1.2 + 1)
    ax2.grid(True, linestyle="--", alpha=0.4)

    fig.tight_layout()
    fig.savefig(png_path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
