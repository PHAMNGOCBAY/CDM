import numpy as np
import matplotlib.pyplot as plt

# -------------------------------------------------
# 1️⃣  INSERT YOUR POLYNOMIAL COEFFICIENTS HERE
#    List from highest degree to constant term.
#    Example: x^5 - 4x^3 + 3x^2 - 1 = 0
#             -> coeffs = [1, 0, -4, 3, 0, -1]
# -------------------------------------------------
coeffs = [1, 0, -4, 3, 0, -1]   # <-- replace with your coefficients

# -------------------------------------------------
# 2️⃣  FIND ALL ROOTS (numpy.roots)
# -------------------------------------------------
all_roots = np.roots(coeffs)

# -------------------------------------------------
# 3️⃣  FILTER REAL ROOTS (imaginary part ≈ 0)
# -------------------------------------------------
tolerance = 1e-6
real_roots = sorted([r.real for r in all_roots if abs(r.imag) < tolerance])

# -------------------------------------------------
# 4️⃣  DISPLAY THE LIST OF REAL ROOTS
# -------------------------------------------------
print("Real roots found:", real_roots)

# -------------------------------------------------
# 5️⃣  OPTIONAL: PLOT THE POLYNOMIAL WITH ITS REAL ROOTS
# -------------------------------------------------
x = np.linspace(-3, 3, 2000)        # adjust interval if needed
y = np.polyval(coeffs, x)

plt.figure(figsize=(8, 5))
plt.plot(x, y, label=r"$f(x)$", color="darkblue")
plt.axhline(0, color="black", linewidth=0.8)

# Mark each real root
for r in real_roots:
    plt.axvline(r, color="red", linestyle="--",
                label=f"x = {r:.4f}")

plt.grid(True)
plt.legend()
plt.title("Polynomial and its real roots")
plt.xlabel("x")
plt.ylabel("f(x)")
plt.show()