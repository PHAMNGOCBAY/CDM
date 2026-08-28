import numpy as np
import matplotlib.pyplot as plt

# ==========================================
# 1. THÔNG SỐ ĐỊA KỸ THUẬT & ĐẶC TÍNH CỌC
# ==========================================
E = 30e6      # Mô đun đàn hồi của cọc bê tông (kPa)
D = 1.0       # Đường kính cọc (m)
I = np.pi * D**4 / 64  # Mô men quán tính tiết diện cọc (m^4)
k_s = 20000   # Hệ số nền của đất tự nhiên (kN/m^3)
k = k_s * D   # Độ cứng lò xo đất tương đương trên 1m dài (kN/m^2)

# Hệ số đặc trưng lambda của hệ cọc - đất nền
lam = (k / (4 * E * I))**0.25
alpha = 0.12  # Hệ số giảm lực dọc theo chiều sâu do ma sát hông cọc

# Chiều sâu khảo sát cọc (m)
z = np.linspace(0, 15, 250)

# ==========================================
# 2. KHAI BÁO GIÁ TRỊ NỘI LỰC ĐẦU CỌC (z=0)
# ==========================================
# Mô phỏng 3 hàng cọc dưới đài:
# - Cọc hàng sau (Trailing): Gần ta-luy đắp, chịu lực dọc cực lớn do tải trọng đất đè lên gót đài.
# - Cọc hàng trước (Leading): Chịu tải dọc nhỏ hơn nhưng gánh lực ngang và mô men uốn lớn nhất do tường chắn nghiêng.
piles_data = {
    "Cọc hàng trước (Leading)": {
        "V0": 130.0,   # Lực ngang đầu cọc (kN)
        "M0": -150.0,  # Mô men đầu cọc (kN.m)
        "N0": 550.0,   # Lực dọc đầu cọc (kN)
        "color": "#e63946",
        "style": "-"
    },
    "Cọc hàng giữa (Middle)": {
        "V0": 90.0,
        "M0": -90.0,
        "N0": 750.0,
        "color": "#457b9d",
        "style": "--"
    },
    "Cọc hàng sau (Trailing)": {
        "V0": 50.0,
        "M0": -40.0,
        "N0": 950.0,
        "color": "#1d3557",
        "style": "-."
    }
}

# ==========================================
# 3. HÀM TÍNH TOÁN NỘI LỰC THEO CHIỀU SÂU
# ==========================================
def calculate_moment(z, V0, M0, lam):
    """Tính toán mô men uốn M(z)"""
    return np.exp(-lam * z) * (M0 * np.cos(lam * z) + (M0 + V0 / lam) * np.sin(lam * z))

def calculate_shear(z, V0, M0, lam):
    """Tính toán lực cắt V(z)"""
    return np.exp(-lam * z) * (V0 * np.cos(lam * z) - (2 * lam * M0 + V0) * np.sin(lam * z))

def calculate_axial(z, N0, alpha):
    """Tính toán lực dọc N(z) có xét ma sát hông tiêu tán"""
    return N0 * np.exp(-alpha * z)

# ==========================================
# 4. TRỰC QUAN HÓA ĐỒ THỊ BẰNG MATPLOTLIB
# ==========================================
# Khởi tạo khung vẽ gồm 3 biểu đồ nằm song song
fig, axs = plt.subplots(1, 3, figsize=(16, 9), sharey=True)

for name, data in piles_data.items():
    V0, M0, N0 = data["V0"], data["M0"], data["N0"]
    col, style = data["color"], data["style"]
    
    # Tính toán mảng giá trị nội lực dọc theo thân cọc
    M_z = calculate_moment(z, V0, M0, lam)
    V_z = calculate_shear(z, V0, M0, lam)
    N_z = calculate_axial(z, N0, alpha)
    
    # 4.1. Biểu đồ Mô men uốn M(z)
    axs.plot(M_z, z, label=f"{name}", color=col, linestyle=style, linewidth=2.5)
    # Hiển thị giá trị số trực tiếp tại đầu cọc (z=0) kèm mũi tên chỉ thị
    axs.annotate(f"$M_0$: {M0:.0f} kN.m", 
                    xy=(M_z, z), 
                    xytext=(M_z - 35 if M0 < 0 else M_z + 15, z + 0.8),
                    arrowprops=dict(arrowstyle="->", color=col, lw=1.2),
                    fontsize=9, fontweight='bold', color=col)
    
    # 4.2. Biểu đồ Lực cắt V(z)
    axs.[1]plot(V_z, z, color=col, linestyle=style, linewidth=2.5)
    axs.[1]annotate(f"$V_0$: {V0:.0f} kN", 
                    xy=(V_z, z), 
                    xytext=(V_z + 10, z + 0.8),
                    arrowprops=dict(arrowstyle="->", color=col, lw=1.2),
                    fontsize=9, fontweight='bold', color=col)
    
    # 4.3. Biểu đồ Lực dọc N(z)
    axs.[2]plot(N_z, z, color=col, linestyle=style, linewidth=2.5)
    axs.[2]annotate(f"$N_0$: {N0:.0f} kN", 
                    xy=(N_z, z), 
                    xytext=(N_z - 120, z + 0.8),
                    arrowprops=dict(arrowstyle="->", color=col, lw=1.2),
                    fontsize=9, fontweight='bold', color=col)

# --- THIẾT LẬP GIAO DIỆN ĐỒ HỌA CHUYÊN NGHIỆP ---
# Đảo ngược trục Y để chiều sâu hướng xuống dưới đất
axs.invert_yaxis()

# Cấu hình Biểu đồ Mô men
axs.set_title("Biểu đồ Mô men uốn $M(z)$", fontsize=12, fontweight='bold', pad=12)
axs.set_xlabel("Mô men uốn (kN.m)", fontsize=11)
axs.set_ylabel("Chiều sâu thân cọc $z$ (m)", fontsize=11, fontweight='bold')
axs.grid(True, linestyle=':', alpha=0.6)
axs.axvline(0, color='black', linewidth=1.0, linestyle='-')
axs.legend(loc="lower left", fontsize=9)

# Cấu hình Biểu đồ Lực cắt
axs.[1]set_title("Biểu đồ Lực cắt $V(z)$", fontsize=12, fontweight='bold', pad=12)
axs.[1]set_xlabel("Lực cắt ngang (kN)", fontsize=11)
axs.[1]grid(True, linestyle=':', alpha=0.6)
axs.[1]axvline(0, color='black', linewidth=1.0, linestyle='-')

# Cấu hình Biểu đồ Lực dọc
axs.[2]set_title("Biểu đồ Lực dọc $N(z)$", fontsize=12, fontweight='bold', pad=12)
axs.[2]set_xlabel("Lực dọc thân cọc (kN)", fontsize=11)
axs.[2]grid(True, linestyle=':', alpha=0.6)
axs.[2]axvline(0, color='black', linewidth=1.0, linestyle='-')

# Tiêu đề chung cho toàn bộ bảng vẽ
plt.suptitle("PHÂN TÍCH NỘI LỰC ĐỒNG THỜI NHÓM CỌC DƯỚI ĐÀI MÓNG\n(Lý thuyết dầm trên nền đàn hồi Winkler chịu tải đa trục)", 
             fontsize=14, fontweight='bold', y=0.98, color='#1d3557')

plt.tight_layout()
plt.show()