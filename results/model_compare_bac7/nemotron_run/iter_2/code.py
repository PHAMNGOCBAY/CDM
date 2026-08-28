import numpy as np
import matplotlib.pyplot as plt

# Đa thức: 2x^7 - 4x^5 + 3x^4 - x^2 + 5 = 0
coeffs = [2, 0, -4, 3, 0, -1, 0, 5]

# 1. Tìm tất cả nghiệm bằng numpy.roots
roots = np.roots(coeffs)

# 2. Lọc các nghiệm THUC (phần ao ≈ 0)
tolerance = 1e-6
real_roots = sorted([r.real for r in roots if abs(r.imag) < tolerance])

print("Danh sách nghiệm thực:", real_roots)

# 3. Vẽ đồ thị y = f(x) trong khoảng x ∈ [-2.2, 2.2], y ∈ [-30, 30]
x = np.linspace(-2.2, 2.2, 2000)
y = np.polyval(coeffs, x)

plt.figure(figsize=(8, 5))
plt.plot(x, y, label=r"$f(x) = 2x^7 - 4x^5 + 3x^4 - x^2 + 5$", color="darkblue")
plt.axhline(0, color="gray", linewidth=0.8)
plt.ylim(-30, 30)
plt.grid(True, alpha=0.3)

# 4. Danh dấu tất cả nghiệm thực tìm được
for r in real_roots:
    plt.plot(r, 0, "ro", markersize=6, zorder=5, label="Nghiệm thực" if r == real_roots[0] else "")

plt.title("Đồ thị đa thức và các nghiệm thực")
plt.xlabel("x")
plt.ylabel("f(x)")
plt.legend()
plt.tight_layout()

# 5. Lưu ảnh ra file output.png
plt.savefig("output.png", dpi=150)
plt.close()