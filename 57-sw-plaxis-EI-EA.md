# Thông số $EI$, $EA$ cọc ván SW dự ứng lực — input PLAXIS 2D

Tài liệu tính toán các thông số đầu vào **Plate element trong PLAXIS 2D** cho 3 loại cọc ván SW dự ứng lực phổ biến: **SW-600B, SW-740, SW-840** với 4 cấp bê tông **C50, C60, C70, C80**.

---

## 1. Công thức tính

### 1.1 Mô đun đàn hồi bê tông (ACI 318)

$$E_c = 4730 \cdot \sqrt{f_c} \quad (\text{MPa})$$

với $f_c$ là cường độ cylinder bê tông (MPa).

| Cấp BT | $f_c$ (MPa) | Cấp TCVN | $E_c$ (MPa) |
|:---:|:---:|:---:|:---:|
| C50 | 50 | B45 | **33 446** |
| C60 | 60 | B55 | **36 638** |
| C70 | 70 | B65 | **39 574** |
| C80 | 80 | B75 | **42 306** |

### 1.2 Per cừ riêng (KHÔNG dùng cho PLAXIS plate)

$$EA_{\text{cừ}} = E_c \cdot A_{td} \quad (\text{kN})$$

$$EI_{\text{cừ}} = E_c \cdot I_{td} \quad (\text{kN·m}^2)$$

### 1.3 Per m wall length (DÙNG cho PLAXIS plate plain strain)

$$EA = \dfrac{EA_{\text{cừ}}}{w_{\text{cừ}}} \quad (\text{kN/m})$$

$$EI = \dfrac{EI_{\text{cừ}}}{w_{\text{cừ}}} \quad (\text{kN·m}^2/\text{m})$$

với $w_{\text{cừ}} = 0{,}996$ m (chiều rộng 1 cừ).

### 1.4 Chiều dày tương đương

$$d_{eq} = \sqrt{\dfrac{12 \cdot EI}{EA}} \quad (\text{m})$$

### 1.5 Trọng lượng

$$w_{\text{plate}} = \dfrac{W_{\text{cừ}} \cdot 9{,}81}{L_{std} \cdot w_{\text{cừ}}} \quad (\text{kN/m}^2)$$

### 1.6 Mô men dẻo / kháng nứt

$$M_p = \dfrac{M_{cr}}{w_{\text{cừ}}} \quad (\text{kN·m/m})$$

---

## 2. Bảng catalog 3 cọc

| Cọc | $H$ (mm) | $w$ (mm) | $t$ (mm) | $A_{td}$ (cm²) | $I_{td}$ (cm⁴) | $W$ (T) | $L_{std}$ (m) | $M_{cr}$ (T·m) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **SW-600B** | 600 | 996 | 130 | 2 288 | 797 396 | 11,0 | 20 | 35,0 |
| **SW-740** | 740 | 996 | 160 | 2 794 | 1 480 428 | 14,55 | 21 | 60,4 |
| **SW-840** | 840 | 996 | 160 | 3 107 | 2 125 017 | 16,35 | 22 | 77,1 |

---

## 3. Kết quả EI / EA / d_eq / w cho PLAXIS 2D

### 3.1 SW-600B (per m wall length)

| Cấp BT | $E_c$ (MPa) | $EA$ (kN/m) | $EI$ (kN·m²/m) | $d_{eq}$ (m) | $w$ (kN/m²) | $M_p$ (kN·m/m) |
|:---:|:---:|---:|---:|:---:|:---:|:---:|
| C50 | 33 446 | **7 683 212** | **267 769** | 0,6467 | 5,42 | 344,7 |
| C60 | 36 638 | **8 416 537** | **293 327** | 0,6467 | 5,42 | 344,7 |
| **C70** | **39 574** | **9 090 899** | **316 829** | **0,6467** | **5,42** | **344,7** |
| C80 | 42 306 | 9 718 580 | 338 704 | 0,6467 | 5,42 | 344,7 |

### 3.2 SW-740 (per m wall length)

| Cấp BT | $E_c$ (MPa) | $EA$ (kN/m) | $EI$ (kN·m²/m) | $d_{eq}$ (m) | $w$ (kN/m²) | $M_p$ (kN·m/m) |
|:---:|:---:|---:|---:|:---:|:---:|:---:|
| C50 | 33 446 | **9 382 384** | **497 135** | 0,7974 | 6,82 | 594,9 |
| C60 | 36 638 | **10 277 887** | **544 584** | 0,7974 | 6,82 | 594,9 |
| **C70** | **39 574** | **11 101 387** | **588 218** | **0,7974** | **6,82** | **594,9** |
| C80 | 42 306 | 11 867 881 | 628 831 | 0,7974 | 6,82 | 594,9 |

### 3.3 SW-840 (per m wall length)

| Cấp BT | $E_c$ (MPa) | $EA$ (kN/m) | $EI$ (kN·m²/m) | $d_{eq}$ (m) | $w$ (kN/m²) | $M_p$ (kN·m/m) |
|:---:|:---:|---:|---:|:---:|:---:|:---:|
| C50 | 33 446 | **10 433 453** | **713 591** | 0,9059 | 7,32 | 759,4 |
| C60 | 36 638 | **11 429 275** | **781 700** | 0,9059 | 7,32 | 759,4 |
| **C70** | **39 574** | **12 345 028** | **844 332** | **0,9059** | **7,32** | **759,4** |
| C80 | 42 306 | 13 197 390 | 902 629 | 0,9059 | 7,32 | 759,4 |

**Bôi đậm C70:** cấp khuyến nghị cho dự án TTHC (BT dự ứng lực phổ biến).

---

## 4. Hướng dẫn nhập PLAXIS 2D

### Material → Plate element (plain strain)

| Trường | Giá trị | Đơn vị |
|---|---|:---:|
| Material type | **Elastic** hoặc **Elastoplastic** | — |
| Identification | `SW-740_C70` (vd) | — |
| **EA** | Theo bảng cột "EA (kN/m)" | kN/m |
| **EI** | Theo bảng cột "EI (kN·m²/m)" | kN·m²/m |
| **d** | Theo bảng cột "d_eq" (PLAXIS tự cập nhật) | m |
| **w** | Theo bảng cột "w" | kN/m/m |
| **ν** (Poisson) | **0,18** (BT dự ứng lực) | — |
| **Mp** (Elastoplastic) | Theo bảng cột "Mp" | kN·m/m |
| Np (Elastoplastic, axial) | $\sigma_{adm} \cdot A_{td} / w_{cừ}$ | kN/m |

### Lưu ý quan trọng

- PLAXIS 2D plate giả định **plain strain** → **EA, EI per m wall length** (KHÔNG per 1 cừ).
- **Elastic:** nhập EA, EI, d, w, ν — tường ứng xử đàn hồi hoàn toàn.
- **Elastoplastic:** thêm Mp (mô men dẻo), Np (lực dọc dẻo) — cho phép mô phỏng hư hỏng cừ khi vượt giới hạn nứt.
- **d_eq** trong PLAXIS là chiều dày để hiển thị, không vào công thức — nhưng PLAXIS có thể tự tính lại nếu input.

---

## 5. Triển khai 4 layer

| Layer | File | Nội dung |
|---|---|---|
| **MD** | `57-sw-plaxis-EI-EA.md` (file này) | Công thức + bảng + hướng dẫn |
| **JSON** | `data/sw_plaxis_params.json` | 12 rows (3 cọc × 4 cấp BT) + metadata |
| **Python** | `scripts/sw_plaxis_params.py` | `Ec_from_fc`, `compute_plate_params`, `compute_all` + I/O |
| **SQLite** | `sw_plaxis_plate_params` (12 rows, UNIQUE pile+fc) | Bảng tra cứu nhanh |

### API Python

```python
from sw_plaxis_params import compute_plate_params, compute_all

# 1 case cụ thể
r = compute_plate_params('SW-740', fc_MPa=70)
# → {EA_per_m_kN_per_m: 11_101_387, EI_per_m_kNm2_per_m: 588_218, d_eq_m: 0.7974, ...}

# Tất cả 12 case
all_rows = compute_all()
```

### SQL query

```sql
SELECT pile, fc_label,
       EA_per_m_kN_per_m AS EA,
       EI_per_m_kNm2_per_m AS EI,
       d_eq_m AS d, w_kN_per_m2 AS w
FROM sw_plaxis_plate_params
WHERE pile = 'SW-740' AND fc_MPa = 70;
```

---

## 6. Liên kết

- [scripts/sw_plaxis_params.py](scripts/sw_plaxis_params.py) — module Python
- [data/sw_plaxis_params.json](data/sw_plaxis_params.json) — JSON output
- [data/sw_pile_catalog.json](data/sw_pile_catalog.json) — catalog gốc 22 cọc SW
- [16-ke-sw-202605-TTHC.md](16-ke-sw-202605-TTHC.md) — Mục B Kè SW
- [CLAUDE.md](CLAUDE.md) §16 (Mục A Catalog SW) + §44 (mục này)
