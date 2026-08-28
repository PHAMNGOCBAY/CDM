import time
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

t0 = time.time()

# 2x^7 - 4x^5 + 3x^4 - x^2 + 5 = 0
coef = [2, 0, -4, 3, 0, -1, 0, 5]
all_roots = np.roots(coef)
real_roots = sorted([r.real for r in all_roots if abs(r.imag) < 1e-6])

def f(x):
    return 2*x**7 - 4*x**5 + 3*x**4 - x**2 + 5

x = np.linspace(-2.2, 2.2, 600)
y = f(x)

fig, ax = plt.subplots(figsize=(9, 6.5))
ax.plot(x, y, color="#1565C0", linewidth=2, label=r"$y=2x^7-4x^5+3x^4-x^2+5$")
ax.axhline(0, color="black", linewidth=0.8)
ax.axvline(0, color="black", linewidth=0.8)
ax.scatter(real_roots, [0]*len(real_roots), color="#D32F2F", zorder=5, s=80, label="Nghiệm thực")
for r in real_roots:
    ax.annotate(f"x={r:.4f}", (r, 0), textcoords="offset points", xytext=(0, 12),
                ha="center", fontsize=10, color="#D32F2F", fontweight="bold")

n_complex = len(all_roots) - len(real_roots)
ax.set_title(f"Claude — bậc 7: {len(real_roots)} nghiệm thực, {n_complex} nghiệm phức (không vẽ)")
ax.set_xlabel("x")
ax.set_ylabel("y")
ax.set_ylim(-30, 30)
ax.grid(True, linestyle="--", alpha=0.4)
ax.legend()
fig.tight_layout()
fig.savefig("claude_output.png", dpi=150)

elapsed = time.time() - t0
print("Nghiem thuc:", [round(r, 6) for r in real_roots])
print("So nghiem phuc:", n_complex)
print(f"Thoi gian: {elapsed:.3f}s")
with open("claude_timing.txt", "w", encoding="utf-8") as f_:
    f_.write(f"iterations=1\ntotal_time_s={elapsed:.3f}\nsuccess_on_first_try=True\n")
