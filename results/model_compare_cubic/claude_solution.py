import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# x^3 - 6x^2 + 11x - 6 = (x-1)(x-2)(x-3)  ->  nghiem: 1, 2, 3
roots = [1, 2, 3]

x = np.linspace(-1, 5, 400)
y = x**3 - 6*x**2 + 11*x - 6

fig, ax = plt.subplots(figsize=(8, 6))
ax.plot(x, y, color="#1565C0", linewidth=2, label=r"$y = x^3 - 6x^2 + 11x - 6$")
ax.axhline(0, color="black", linewidth=0.8)
ax.axvline(0, color="black", linewidth=0.8)
ax.scatter(roots, [0, 0, 0], color="#D32F2F", zorder=5, s=70, label="Nghiệm")
for r in roots:
    ax.annotate(f"x={r}", (r, 0), textcoords="offset points", xytext=(0, 12),
                ha="center", fontsize=10, color="#D32F2F", fontweight="bold")

ax.set_title("Claude — Đồ thị $x^3-6x^2+11x-6=0$, nghiệm: 1, 2, 3")
ax.set_xlabel("x")
ax.set_ylabel("y")
ax.grid(True, linestyle="--", alpha=0.4)
ax.legend()
fig.tight_layout()
fig.savefig("claude_output.png", dpi=150)
print("Nghiem:", roots)
print("Da luu anh: claude_output.png")
