# 11 — Cơ sở dữ liệu Cọc ván Bê tông SW (BETON 6)

## 11.1 Nguồn Dữ liệu

**Nhà sản xuất:** BETON 6  
**Tài liệu hình học:** `BENTO6-DAC TRUNG HINH HOC SW.pdf` — Atd, Itd, Yt, Yb  
**Tài liệu kỹ thuật:** `BENTO6-THONG SO KY THUAT SW.pdf` (Ver.2015) — width, height, thickness, n cáp, φ cáp, Mcr, trọng lượng, L tiêu chuẩn, **L min, L max**  
**Script:** [scripts/sw_pile_database.py](scripts/sw_pile_database.py)

---

## 11.2 Giải thích Ký hiệu

| Ký hiệu | Diễn giải | Đơn vị | Nguồn |
|---------|-----------|--------|-------|
| `H` (CAO) | Chiều cao mặt cắt cọc | mm | Kỹ thuật |
| `width` (RỘNG) | **Bề rộng cọc** — khoảng cách tim cọc khi chạm | mm | Kỹ thuật |
| `t` (DÀY) | Bề dày thành cọc | mm | Kỹ thuật |
| `n_strands` | Số sợi cáp dự ứng lực | — | Kỹ thuật |
| `phi_strand` | Đường kính sợi cáp | mm | Kỹ thuật |
| `Mcr` | Mô men kháng nứt (≥ giá trị) | T.m | Kỹ thuật |
| `weight` | Trọng lượng cọc tại chiều dài tiêu chuẩn | T/cọc | Kỹ thuật |
| `L_std` | Chiều dài tiêu chuẩn (catalog) — trọng lượng tương ứng cột TL | m | Kỹ thuật |
| `L_min` | Chiều dài tối thiểu có thể cung cấp | m | Kỹ thuật |
| `L_max` | Chiều dài tối đa có thể cung cấp | m | Kỹ thuật |
| `Atd` | Diện tích mặt cắt quy đổi (bê tông + cáp) | cm² | Hình học |
| `Yt` / `Yb` | Khoảng cách từ thớ trên/dưới đến trọng tâm | cm | Hình học |
| `Itd` | Mô men quán tính mặt cắt quy đổi | cm⁴ | Hình học |

> **Lưu ý:** `Atd` và `Itd` đã bao gồm đóng góp của cáp dự ứng lực quy đổi về bê tông. Không dùng A và I của bê tông thuần.

> **Bề rộng thực tế:** SW-120 đến SW-940 = **996 mm**, SW-1100 và SW-1200 = **1246 mm**. Đây là kích thước spacing chuẩn cho PLAXIS khi cọc chạm nhau.

---

## 11.3 Bảng Catalog Đầy đủ (22 loại) — v3 (cập nhật từ PDF Ver.2015)

| No | Tên | W (mm) | H (mm) | t (mm) | n cáp | φ cáp (mm) | Atd (cm²) | Itd (cm⁴) | Mcr (T.m) | TL (T) | L std (m) | L min (m) | L max (m) |
|----|-----|--------|--------|--------|-------|------------|-----------|-----------|-----------|--------|-----------|-----------|-----------|
| 1 | SW-120 | 996 | 120 | 60 | 8 | 9.53 | 548.0 | 6,514 | ≥1.53 | 0.83 | 5 | 3 | 7 |
| 2 | SW-120 | 996 | 120 | 60 | 10 | 9.00 | 556.0 | 6,544 | ≥1.53 | 0.83 | 5 | 3 | 7 |
| 3 | SW-160 | 996 | 160 | 80 | 8 | 9.53 | 723.0 | 15,336 | ≥2.04 | 1.30 | 6 | 4 | 8 |
| 4 | SW-160 | 996 | 160 | 80 | 8 | 9.00 | 727.0 | 15,389 | ≥2.04 | 1.30 | 6 | 4 | 8 |
| 5 | SW-225 | 996 | 225 | 100 | 8 | 11.10 | 954.0 | 42,780 | ≥4.28 | 2.38 | 8 | 5 | 9 |
| 6 | SW-225 | 996 | 225 | 100 | 8 | 10.70 | 959.0 | 43,003 | ≥4.28 | 2.38 | 8 | 5 | 9 |
| 7 | SW-300 | 996 | 300 | 110 | 10 | 12.70 | 1168.0 | 101,168 | ≥9.58 | 3.38 | 10 | 7 | 12 |
| 8 | SW-350A | 996 | 350 | 120 | 14 | 12.70 | 1376.0 | 162,003 | ≥16.31 | 5.00 | 13 | 9 | 15 |
| 9 | SW-350B | 996 | 350 | 120 | 16 | 12.70 | 1385.0 | 162,756 | ≥17.33 | 5.38 | 14 | 10 | 15 |
| 10 | SW-400A | 996 | 400 | 120 | 16 | 12.70 | 1543.0 | 240,449 | ≥20.39 | 6.28 | 15 | 10 | 16 |
| 11 | SW-400B | 996 | 400 | 120 | 18 | 12.70 | 1552.0 | 240,449 | ≥23.45 | 6.68 | 16 | 11 | 16 |
| 12 | SW-450A | 996 | 450 | 120 | 18 | 12.70 | 1787.0 | 341,010 | ≥27.52 | 7.65 | 16 | 11 | 17 |
| 13 | SW-450B | 996 | 450 | 120 | 16 | 15.24 | 1808.0 | 348,089 | ≥31.60 | 8.13 | 17 | 12 | 17 |
| 14 | SW-500A | 996 | 500 | 120 | 16 | 15.24 | 1885.0 | 467,240 | ≥35.68 | 8.13 | 17 | 12 | 19 |
| 15 | SW-500B | 996 | 500 | 120 | 20 | 15.24 | 1910.0 | 469,288 | ≥40.77 | 8.58 | 18 | 13 | 20 |
| 16 | SW-600A | 996 | 600 | 120 | 20 | 15.24 | 2262.0 | 795,348 | ≥50.97 | 10.38 | 19 | 14 | 22 |
| 17 | SW-600B | 996 | 600 | 120 | 24 | 15.24 | 2288.0 | 797,396 | ≥60.14 | 10.88 | 20 | 15 | 24 |
| 18 | SW-740 | 996 | 740 | 160 | 20 | 15.24 | 2794.0 | 1,480,428 | ≥60.40 | 14.55 | 21 | 16 | 28 |
| 19 | SW-840 | 996 | 840 | 160 | 22 | 15.24 | 3107.0 | 2,125,017 | ≥77.10 | 16.35 | 22 | 17 | 29 |
| 20 | SW-940 | 996 | 940 | 160 | 24 | 15.24 | 3544.0 | 2,983,488 | ≥93.30 | 18.31 | 23 | 17 | 30 |
| 21 | **SW-1100** | **1246** | 1100 | 200 | 28 | 15.24 | 5327.0 | 5,663,367 | ≥136.00 | 25.80 | 24 | 17 | 32 |
| 22 | **SW-1200** | **1246** | 1200 | 200 | 30 | 15.24 | 5789.7 | 7,318,551 | ≥158.00 | 28.75 | 25 | 17 | 34 |

*W = bề rộng cọc (RỘNG), H = chiều cao (CAO), t = bề dày thành (DÀY), TL = Trọng lượng tại L std*  
*Mcr = mô men kháng nứt (≥ giá trị); 1 T.m = 9.81 kN.m*  
*L std = chiều dài tiêu chuẩn catalog; L min / L max = khoảng cung cấp theo yêu cầu (nguồn: BETON 6 Ver.2015)*

---

## 11.4 Quy đổi sang Thông số PLAXIS 2D

### Công thức

```
spacing_m = width_mm / 1000    (mặc định: cọc chạm nhau)

A_per_m  = Atd [cm²] / 10,000  / spacing_m     → m²/m
I_per_m  = Itd [cm⁴] / 1e8     / spacing_m     → m⁴/m

EA₁ = Ec [kN/m²] × A_per_m    → kN/m
EI  = Ec [kN/m²] × I_per_m    → kN·m²/m
w   = weight_kN_per_m / spacing_m               → kN/m/m
```

- **spacing_m** = bề rộng cọc (width_mm) khi cọc chạm nhau: **0.996 m** (hầu hết), **1.246 m** (SW-1100/1200)
- **Ec** = mô đun đàn hồi bê tông cọc (kN/m²) — xem mục 11.5

### Ví dụ: SW-840, f'c=70 MPa, spacing = width = 0.996 m

| Thông số | Giá trị |
|---------|---------|
| Ec | 43,628,130 kN/m² (= 43,628.13 MPa) |
| Atd | 3107 cm² = 0.3107 m² |
| Itd | 2,125,017 cm⁴ = 2.125017×10⁻² m⁴ |
| spacing | **0.996 m** (= pile width) |
| **EA₁** | **43,628,130 × 0.3107 / 0.996 = 13,609,699 kN/m** |
| **EI** | **43,628,130 × 2.125017e-2 / 0.996 = 930,828 kN·m²/m** |
| **w** | **(16.35T × 9.81) / 22m / 0.996 = 7.32 kN/m/m** |
| Mcr | ≥ 77.10 T.m = 756.4 kN.m |

> **Lưu ý quan trọng (v2):** Phiên bản trước dùng spacing=0.500m (giả định sai). Giá trị EA₁ và EI đã được cập nhật lại với spacing đúng = 0.996m.

---

## 11.5 Mô đun Đàn hồi Bê tông Cọc

| f'c (MPa) | Ec (MPa) | Ec (kN/m²) — nhập PLAXIS |
|-----------|---------|--------------------------|
| 30 | 26,561 | 26,561,000 |
| 40 | 31,623 | 31,623,000 |
| 60 | 38,730 | 38,730,000 |
| **70** | **43,628** | **43,628,130** |

> **Quy tắc đơn vị:** 1 MPa = 1,000 kN/m² — PLAXIS yêu cầu kN/m².

---

## 11.6 Sử dụng Script

```python
from scripts.sw_pile_database import lookup, lookup_first, list_all, EC_FC70_KNM2

# --- Tra cứu một loại cọc (spacing mặc định = width = 0.996m) ---
pile = lookup_first("SW-840")
pile.summary(plate_length_m=25.0)
# → EA1=13,609,699 kN/m, EI=930,828 kN.m2/m, Mcr>=77.10 T.m

# --- Tra cứu nhiều variant ---
for p in lookup("SW-400A") + lookup("SW-400B"):
    print(p.name, p.Atd_cm2, p.Itd_cm4, p.Mcr_Tm, p.weight_T)

# --- Tính PLAXIS inputs với spacing tùy chỉnh ---
pile = lookup_first("SW-840")
print(pile.EA1(Ec_kNm2=EC_FC70_KNM2))                  # spacing = width = 0.996m
print(pile.EA1(Ec_kNm2=EC_FC70_KNM2, spacing_m=1.200)) # spacing tùy chọn

# --- Trọng lượng cho PLAXIS (kN/m/m) ---
print(pile.w_plaxis())   # w = weight_kN/m / spacing

# --- In toàn bộ bảng catalog ---
list_all(Ec_kNm2=EC_FC70_KNM2)   # spacing = pile width tự động
```

---

## 11.7 Lưu ý Khi Dùng

- **Bề rộng thực:** SW-120 đến SW-940 = **996 mm**, SW-1100/SW-1200 = **1246 mm** — đây là spacing chuẩn khi cọc chạm nhau.
- **Spacing khác width:** nếu dùng khoảng cách khác (cọc không chạm), truyền `spacing_m=...` vào `EA1()`, `EI()`.
- **Các loại trùng tên** (SW-120, SW-160, SW-225): `lookup()` trả về list, `lookup_first()` lấy variant đầu tiên — kiểm tra `n_strands` và `phi_strand_mm` để chọn đúng.
- **ν = 0.15** cho bê tông (xem [10-plate-properties.md](10-plate-properties.md) §10.4).
- **Không nhập thẳng MPa vào PLAXIS** — luôn nhân ×1,000 để ra kN/m².
- **Mcr** là mô men kháng nứt (T.m); kiểm tra M_max từ PLAXIS < Mcr để đảm bảo cọc không nứt.

---

## 11.8 Chu vi Mặt cắt Ngang Giữa Cọc (Middle Segment Perimeter)

Chu vi tính theo hình học mặt cắt thực (GIỮA CỌC — Middle segment), dùng các kích thước H, t, i, j, e, a, b, c, d từ PDF hình học BETON 6 Ver.2015.

| Loại cọc SW | Chu vi (mm) |
|-------------|------------|
| SW-600A | 3,724.397 |
| SW-600B | 3,724.397 |
| SW-740 | 4,205.853 |
| SW-840 | 4,594.913 |

> **Ghi chú:** SW-600A và SW-600B có cùng kích thước hình học ngoài (H=600, t=120, W=996) nên chu vi bằng nhau. Sự khác biệt chỉ ở số lượng cáp DƯL (20 vs 24 sợi).
