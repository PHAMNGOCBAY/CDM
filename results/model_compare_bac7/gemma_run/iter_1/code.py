import numpy as np
import matplotlib.pyplot as plt

def solve_polynomial():
    # 1. Thiet lap he so cua da thuc: 2x^7 + 0x^6 - 4x^5 + 3x^4 + 0x^3 - 1x^2 + 0x + 5
    # Tuong ung voi: [2, 0, -4, 3, 0, -1, 0, 5]
    coeffs = [2, 0, -4, 3, 0, -1, 0, 5]
    
    # Tim tat ca cac nghiem (bao gom ca nghiem phuc) bang numpy.roots
    all_roots = np.roots(coeffs)
    
    # 2. Loc ra cac nghiem THUC voi sai so 1e-6
    # Kiem tra phan ao (imaginary part) co gan bang 0 hay khong
    real_roots = all_roots[np.abs(all_roots.imag) < 1e-6].real
    
    # Tinh so luong nghiem phuc de thong bao
    complex_roots_count = len(all_roots) - len(real_roots)
    real_roots_count = len(real_roots)

    print(f"Tat ca cac nghiem tim duoc: {all_roots}")
    print(f"Nghiem thuc: {real_roots}")
    print(f"So luong nghiem thuc: {real_roots_count}")
    print(f"So luong nghiem phuc: {complex_roots_count}")

    # 3. Thiet lap do thi de ve ham so y = f(x)
    # Dung numpy.poly1d de tao ham tu he so
    poly = np.poly1d(coeffs)
    
    x_vals = np.linspace(-2.2, 2.2, 1000)
    y_vals = poly(x_vals)

    # 4. Ve do thi
    plt.figure(figsize=(10, 7))
    plt.plot(x_vals, y_vals, label='f(x) = 2x^7 - 4x^5 + 3x^4 - x^2 + 5', color='blue', linewidth=2)
    
    # Ve truc x va truc y de truc quan
    plt.axhline(0, color='black', linewidth=1) # Truc hoanh
    plt.axvline(0, color='black', linewidth=1) # Truc tung
    
    # 5. Danh dau cac nghiem thuc tim duoc bang cac diem do (red dots)
    if len(real_roots) > 0:
        plt.scatter(real_roots, np.zeros_like(real_roots), color='red', s=100, zorder=5, label='Nghiem thuc')

    # Thiet lap gioi han truc y tu -30 den 30 theo yeu cau
    plt.ylim(-30, 30)
    plt.xlim(-2.2, 2.2)

    # Thiet lap tieu de, loai, chu thich
    plt.title('Do thi ham so bac 7 va cac nghiem thuc', fontsize=14)
    plt.xlabel('x', fontsize=12)
    plt.ylabel('y', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Thong tin text hien thi tren do thi
    info_text = f'So nghiem thuc: {real_roots_count}\nSo nghiem phuc: {complex_roots_count}'
    plt.text(0.05, 25, info_text, fontsize=12, bbox=dict(facecolor='white', alpha=0.8))
    
    plt.legend(loc='upper right')

    # 6. Luu anh ra file
    plt.savefig('output.png')
    print("\nDa luu do thi vao file 'output.png'")
    plt.show()

if __name__ == "__main__":
    solve_polynomial()