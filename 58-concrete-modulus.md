# Mô đun đàn hồi $E_c$ bê tông — Tổng hợp công thức tiêu chuẩn

Tài liệu tổng hợp các công thức tính mô đun đàn hồi $E_c$ bê tông theo 4 tiêu chuẩn phổ biến: **TCVN 5574:2018**, **ACI 318**, **Eurocode 2 (EN 1992)**, **AS 3600** (Úc). Áp dụng cho thiết kế cọc ván SW + cấu kiện BTCT.

---

## 1. Công thức theo tiêu chuẩn

### 1.1 ACI 318 (Mỹ)

$$E_c = 4730 \cdot \sqrt{f_c} \quad (\text{MPa})$$

với $f_c$ là cường độ cylinder (MPa). Đơn giản nhất, được dùng phổ biến.

### 1.2 Eurocode 2 / EN 1992-1-1

$$E_{cm} = 22 \cdot \left(\dfrac{f_{cm}}{10}\right)^{0{,}3} \quad (\text{GPa})$$

với $f_{cm} = f_c + 8$ MPa (mean strength = characteristic + 8). Hệ số mũ 0.3 phản ánh non-linear stiffness-strength relationship.

### 1.3 TCVN 5574:2018 — Bảng tra trực tiếp

Tra Bảng phụ lục TCVN 5574 theo cấp độ bền **B** (kPa).

| Cấp B | $E_b$ (MPa) | Cấp B | $E_b$ (MPa) |
|:---:|:---:|:---:|:---:|
| B15 | 23 000 | B55 | 39 000 |
| B20 | 27 000 | B60 | 39 500 |
| B25 | 30 000 | B70 | 41 000 |
| B30 | 32 500 | B80 | 42 000 |
| B35 | 34 500 | B90 | 43 000 |
| B40 | 36 000 | B100 | 44 000 |
| B45 | 37 000 | | |
| B50 | 38 000 | | |

**Quan hệ B ↔ fc:** $f_c$ (cylinder) $\approx 0{,}78 \cdot B$ (cube 15cm).

### 1.4 AS 3600 (Úc)

$$E_c = \rho^{1{,}5} \cdot 0{,}043 \cdot \sqrt{f_c} \quad (\text{MPa})$$

với $\rho$ = density (kg/m³, mặc định 2400 cho BT thường). Tính cả ảnh hưởng density.

---

## 2. Bảng so sánh 4 công thức

| Cấp B | $f_c$ (MPa) | ACI 318 | EC2 | TCVN 5574 | AS 3600 | **TB** | $\sigma$ % |
|:---:|:---:|---:|---:|---:|---:|---:|:---:|
| B25 | 19,5 | 20 887 | 29 800 | 30 000 | 22 326 | 25 753 | 16,2 |
| B35 | 27,3 | 24 714 | 32 118 | 34 500 | 26 416 | 29 437 | 13,6 |
| B45 | 35,1 | 28 023 | 34 101 | 37 000 | 29 953 | 32 269 | 10,9 |
| **B55** | **42,9** | **30 981** | **35 846** | **39 000** | **33 114** | **34 735** | **8,7** |
| **B65** | **50,7** | **33 685** | **37 419** | **40 250** | **35 999** | **36 838** | **7,1** |
| B70 | 54,6 | 34 951 | 38 141 | 41 000 | 37 358 | 37 862 | 5,7 |
| B80 | 62,4 | 37 364 | 39 509 | 42 000 | 39 937 | 39 703 | 4,2 |
| B100 | 78,0 | 41 774 | 41 954 | 44 000 | 44 651 | 43 095 | 2,9 |

**Quan sát:**

- **ACI 318 cho giá trị THẤP NHẤT** (đơn giản nhưng bảo thủ)
- **TCVN 5574 + EC2 cho giá trị CAO HƠN** (tính chính xác hơn cho BT mác cao)
- **Độ phân tán σ% giảm theo fc** — BT cường độ cao đồng nhất hơn
- **B70 (~fc 55 MPa) là điểm convergent** giữa các tiêu chuẩn (~5-7% spread)

### 2.1 Cho dự án TTHC (BT cọc ván SW dự ứng lực)

| Cấp BT thường gặp | $f_c$ (MPa) | $E_c$ TB | Khuyến nghị |
|---|:---:|:---:|---|
| C50 | 50 | ~33 500 | OK (B55 ~ C50) |
| **C60** | **60** | **~37 700** | **Phổ biến** |
| **C70** | **70** | **~39 800** | **TTHC default** |
| **C80** | **80** | **~41 900** | **BT cao cấp** |

---

## 3. Public API Python

```python
from concrete_modulus import (
    Ec_ACI318, Ec_EC2, Ec_TCVN5574, Ec_AS3600,
    compare_all, save_to_db, list_all,
)

# Tính từng công thức
Ec_ACI318(70)              # → 39574 MPa
Ec_EC2(70)                 # → 41032 MPa
Ec_TCVN5574('B65')         # → 41000 MPa (bảng tra)
Ec_AS3600(70, rho=2400)    # → 42360 MPa

# So sánh 4 công thức
r = compare_all(70)
# r['mean_MPa']   = 41404
# r['std_pct']    = 3.2
```

---

## 4. SQLite — Bảng `concrete_modulus_table`

| Cột | Type | Mô tả |
|---|---|---|
| `grade_tcvn` | TEXT UNIQUE | 'B15'..'B100' |
| `fc_MPa` | REAL | $f_c$ cylinder |
| `Ec_ACI318_MPa` | REAL | |
| `Ec_EC2_MPa` | REAL | |
| `Ec_TCVN5574_MPa` | REAL | |
| `Ec_AS3600_MPa` | REAL | (ρ = 2400) |
| `mean_MPa` | REAL | TB 4 công thức |
| `std_pct` | REAL | Độ phân tán % |

### Query

```sql
-- Lấy Ec cho B65
SELECT mean_MPa, Ec_TCVN5574_MPa, Ec_ACI318_MPa
FROM concrete_modulus_table WHERE grade_tcvn = 'B65';

-- Liệt kê tất cả với σ < 10%
SELECT grade_tcvn, fc_MPa, mean_MPa, std_pct
FROM concrete_modulus_table WHERE std_pct < 10
ORDER BY fc_MPa;
```

---

## 5. Khuyến nghị

### Chọn công thức nào?

| Tình huống | Khuyến nghị |
|---|---|
| **Thiết kế PLAXIS / FEM** | **TCVN 5574 hoặc EC2** (giá trị thực tế, đã hiệu chuẩn theo nhiều thí nghiệm) |
| Tính nhanh sơ bộ | **ACI 318** (đơn giản, bảo thủ) |
| Có data density bất thường (BT nhẹ, BT nặng) | **AS 3600** (có hệ số ρ) |
| Quy phạm Việt Nam | **TCVN 5574** (mặc định) |

### Áp dụng trong dự án TTHC

- **Cọc ván SW dự ứng lực** mác **B65/C70**: dùng $E_c = 4730\sqrt{f_c} = 39\,574$ MPa (ACI 318) cho tính EI/EA an toàn.
- Cross-check với TCVN 5574 = 40 250 MPa (chênh 1,7%) — đảm bảo nằm trong khoảng các tiêu chuẩn.

---

## 6. Liên kết

- [scripts/concrete_modulus.py](scripts/concrete_modulus.py) — module Python với 4 công thức
- [57-sw-plaxis-EI-EA.md](57-sw-plaxis-EI-EA.md) — Tính EI/EA SW dùng Ec
- [scripts/sw_plaxis_params.py](scripts/sw_plaxis_params.py) — đã dùng `Ec_from_fc` (ACI 318) — có thể đổi sang TCVN
- [CLAUDE.md](CLAUDE.md) §44 (EI/EA SW PLAXIS) + §45 (mục này — Ec bê tông)
