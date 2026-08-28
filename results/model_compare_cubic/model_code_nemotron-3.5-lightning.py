import numpy as np
import matplotlib.pyplot as plt

# Ham so y = x^3 - 6x^2 + 11x - 6
def f(x):
    return x**3 - 6*x**2 + 11*x - 6

# Tat ca cac nghiem thuc cua phuong trinh
roots = [1, 2, 3]

# Khoang bien x tu -1 den 5
x = np.linspace(-1, 5, 400)
y = f(x)

# Tao do thi
plt.figure(figsize=(8, 5))
plt.plot(x, y, label=r'$y = x^3 - 6x^2 + 11x - 6$', color='darkblue')
plt.axhline(0, color='gray', linewidth=0.8, linestyle='--')  # truc toa do x
plt.axvline(0, color='gray', linewidth=0.8, linestyle='--')  # truc toa do y
plt.grid(True, which='both', linestyle=':', alpha=0.6)       # lưới

# Danh dau cac diem nghiem tren do thi
for r in roots:
    plt.scatter(r, f(r), color='red', s=90, zorder=5, edgecolor='k')  # diem nghiem
    plt.text(r, f(r) + 0.3, f' ({r}, 0)', fontsize=10, ha='center', color='red', fontweight='bold')

# Tieu de, nhan bang va chu thich truc
plt.title('Bieu do ham so y = x^3 - 6x^2 + 11x - 6')
plt.xlabel('x')
plt.ylabel('y')
plt.xlim(-1, 5)
plt.ylim(auto=True)  # tu dong chinh lep truc y theo gia tri ham
plt.legend()

# Luu anh ra file output.png
plt.savefig('output.png', dpi=300, bbox_inches='tight')

# Hien thi do thi (tu nguyen, khong huy lenh nay neu chi muon luu anh)
plt.show()