# 10 — Tính Đặc trưng Vật liệu Plate cho PLAXIS 2D

## 10.1 Công thức Nền tảng (PLAXIS Manual §6.4.2.1)

### Eq.[54] — Chiều dày Tương đương

$$d_{eq} = \sqrt{\frac{12 \cdot EI}{EA_1}}$$

- `d_eq` được PLAXIS tự động tính — **không nhập trực tiếp**
- Dùng để kiểm tra biến dạng cắt (xem 10.3)

### Eq.[55] — Độ cứng Cắt (Mindlin Beam Theory)

$$\text{Shear stiffness} = \frac{5 \cdot EA_1}{12(1 + \nu)}$$

- PLAXIS 2D dùng lý thuyết dầm Mindlin → kể đến biến dạng cắt
- Giả định mặt cắt chữ nhật đồng nhất

---

## 10.2 Thông số Nhập vào PLAXIS

| Tham số | Mô tả | Đơn vị | Ghi chú |
|---------|-------|--------|---------|
| `EA₁` | Độ cứng dọc trục in-plane | kN/m | Bắt buộc |
| `EA₂` | Độ cứng dọc trục out-of-plane | kN/m | = EA₁ nếu Isotropic |
| `EI` | Độ cứng uốn | kN·m²/m | Bắt buộc |
| `ν` | Hệ số Poisson | — | Xem 10.4 |
| `w` | Trọng lượng bản thân | kN/m/m | |
| `d` | Chiều dày tương đương | m | **PLAXIS tự tính** từ Eq.[54] |

### Quy đổi từ đặc trưng mặt cắt (E đã biết)

```
EA₁ = E × A/m       (A/m: diện tích quy đổi trên 1m dài tường)
EI  = E × I/m       (I/m: mô men quán tính quy đổi trên 1m dài)
```

**Với cừ thép:** E = 210,000 MPa = 210,000,000 kN/m²  
**Với BTCT:** E = 30,000 MPa = 30,000,000 kN/m²

---

## 10.3 Kiểm tra Biến dạng Cắt

> **PLAXIS Manual:** Đối với cừ thép (steel profile elements), `d_eq` phải nhỏ hơn ít nhất **10 lần** chiều dài plate để biến dạng cắt không đáng kể.

$$\frac{L}{d_{eq}} \geq 10$$

Nếu không đạt: shear deformation tính toán có thể **quá lớn** so với thực tế.

| Dự án SW840, L=25m | Giá trị |
|--------------------|---------|
| d_eq (SW840) | 0.765 m |
| L/d_eq | 25/0.765 = **32.7 ✓** |

---

## 10.4 Hệ số Poisson ν

| Loại kết cấu | ν khuyến nghị | Lý do |
|-------------|--------------|-------|
| Cừ thép, tường ván thép | **0** | Linh hoạt out-of-plane |
| Tường BTCT đặc | **0.15** | Kết cấu đặc thực sự |
| Cọc bê tông | **0.15** | |

---

## 10.5 Kết quả Dự án L=25M-HKT8-SW840

| Vật liệu | EA₁ (kN/m) | EI (kN·m²/m) | ν | d_eq (m) | Shear Stiff (kN/m) | L/d |
|---------|-----------|-------------|---|---------|-------------------|-----|
| SW840 | 10,335,000 | 504,100 | 0.0 | 0.765 | 4,306,250 | 32.7 ✓ |
| SW400 | 7,204,000 | 118,800 | 0.0 | 0.445 | 3,001,667 | 56.2 ✓ |
| tuong-tren | 19,700,000 | 591,000 | 0.2 | 0.600 | 6,840,278 | 41.7 ✓ |
| tuong-dung | 11,490,000 | 117,300 | 0.2 | 0.350 | 3,989,583 | 71.4 ✓ |
| tuongday | 16,420,000 | 342,000 | 0.2 | 0.500 | 5,701,389 | 50.0 ✓ |

---

## 10.6 Sử dụng Script

```python
from scripts.plate_properties import PlateSection, SteelSheetPile, ConcreteWall, compare_plates

# --- Từ thông số PLAXIS (đọc từ .p2dx) ---
p = PlateSection("SW840", EA1=10_335_000, EI=504_100, nu=0.0, w=4.371,
                 E_material=210_000_000)
p.summary(plate_length_m=25.0, is_steel_profile=True)

# --- Từ catalog cừ thép ---
sp = SteelSheetPile.from_section("SW840", A_cm2=413.0, I_cm4=201_638.0, spacing_m=0.840)
sp.summary(plate_length_m=25.0)

# --- Tường BTCT ---
wall = ConcreteWall("Tuong d=60cm", d_m=0.60, nu=0.15)
wall.summary(plate_length_m=5.0)

# --- So sánh bảng ---
compare_plates([p1, p2, p3], plate_length_m=25.0)
```

Xem chi tiết tại [scripts/plate_properties.py](scripts/plate_properties.py).

---

## 10.7 Bê tông Cọc — f'c = 70 MPa (Dự án L=25M-HKT8-SW840)

Từ tài liệu NSL (mục 2.2. Vật liệu — Bê tông cọc):

| Thông số | Giá trị tài liệu | Đơn vị tài liệu | Nhập PLAXIS | Đơn vị PLAXIS |
|---------|-----------------|----------------|-------------|--------------|
| f'c (cường độ nén) | 70.00 | MPa | — | — |
| fr (cường độ kéo khi uốn) | 5.27 | MPa | — | — |
| **Ec (mô đun đàn hồi)** | **43,628.13** | **MPa** | **43,628,130** | **kN/m²** |

```python
# Quy đổi đúng — không bao giờ nhập trực tiếp MPa vào PLAXIS
Ec_MPa   = 43_628.13
Ec_PLAXIS = Ec_MPa * 1_000   # = 43,628,130 kN/m²

# SAI lầm phổ biến:
# Ec_PLAXIS = 43_628   # kN/m² ← đây chỉ là 43.6 MPa, thiếu 1,000 lần!
```

---

## 10.8 Lưu ý Quan trọng

- `d_eq` của SW840 ≈ 0.765 m (lớn hơn chiều dày thực cừ thép) vì EI tính trên 1m dài tường không tương đương mặt cắt đặc.
- `E_equiv = EA₁/d_eq ≈ 13.5 MPa` — **không phải** mô đun thép 210 MPa, đây là E tương đương của lớp tường gộp trên 1m.
- Khi nhập PLAXIS: chỉ cần EA₁, EI, ν, w — PLAXIS tự tính d_eq và Shear stiffness.
