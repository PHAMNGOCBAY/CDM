# Tính lún cố kết $S_2$ khi cọc CDM KHÔNG hết lớp bùn

Khi cọc đất xi măng (CDM) **không cắm hết lớp đất yếu** (partial penetration), phần đất yếu CÒN LẠI dưới mũi cọc vẫn lún cố kết. Tài liệu này trình bày công thức tính $S_2$ theo TCVN 9403:2012 Phụ lục C + TCCS 41:2022 Điều 9 + lý thuyết Terzaghi 1943.

> **CẬP NHẬT 2026-05-28 — engine hiện hành là `settlement_calc.calc_s2_below_cdm`** (không phải `cdm_s2_partial.py` cũ). Engine mới phân loại theo BẢN CHẤT đất + tính lún tích lũy đến 15 năm — xem **Mục 11** (mục 3 dưới đây mô tả lý thuyết Terzaghi nền tảng, vẫn dùng cho lớp sét).

---

## 1. Hai trường hợp thiết kế

| Trường hợp | Điều kiện | $S_2$ |
|---|---|:---:|
| **A. Full penetration** | CDM cắm đến lớp cứng | **= 0** (đã dùng trong code hiện tại) |
| **B. Partial penetration** | CDM chưa hết lớp bùn → còn $H_{below}$ m bùn dưới mũi | **≠ 0, tính theo Terzaghi** |

**Ngưỡng:** Nếu $H_{below} > 0,5$ m → BẮT BUỘC tính $S_2$.

---

## 2. Tổng lún CDM

$$S_{\text{total}} = S_1 + S_2$$

| Thành phần | Công thức | Nguồn |
|---|---|---|
| $S_1$ — lún đàn hồi khối gia cố CDM | $S_1 = \dfrac{q \cdot H_{CDM}}{a \cdot E_c + (1-a) \cdot E_s}$ | TCVN 9403 Phụ lục C |
| **$S_2$ — lún cố kết dưới mũi cọc** | $\sum_i$ Terzaghi 1D | Mục 3 dưới |

---

## 3. Công thức $S_2$ — Terzaghi 1D cho từng phụ lớp

Chia lớp đất yếu dưới mũi cọc thành các phụ lớp $H_i$ (mặc định 1 m), tại midpoint:

### 3.1 NC (Normal Consolidated) — $\sigma'_{v0} \geq P_C$

$$S_i = H_i \cdot \dfrac{C_c}{1 + e_0} \cdot \log_{10}\!\dfrac{\sigma'_{vf}}{\sigma'_{v0}}$$

### 3.2 OC (Over Consolidated) — $\sigma'_{vf} \leq P_C$

$$S_i = H_i \cdot \dfrac{C_s}{1 + e_0} \cdot \log_{10}\!\dfrac{\sigma'_{vf}}{\sigma'_{v0}}$$

### 3.3 Cross $P_C$ — $\sigma'_{v0} < P_C < \sigma'_{vf}$

$$S_i = H_i \left[ \dfrac{C_s}{1+e_0} \log_{10}\!\dfrac{P_C}{\sigma'_{v0}} + \dfrac{C_c}{1+e_0} \log_{10}\!\dfrac{\sigma'_{vf}}{P_C} \right]$$

### Tổng

$$S_2 = \sum_{i=1}^{n} S_i$$

---

## 4. Phân bố ứng suất truyền dưới mũi cọc CDM

Có 2 mô hình thường dùng:

### 4.1 Infinite slab (kè dài, plain strain) — **MẶC ĐỊNH cho kè SW tuyến dài**

$$\Delta\sigma_z = q \quad \text{(không suy giảm theo chiều sâu)}$$

→ Bảo thủ, an toàn cho thiết kế.

### 4.2 Method 2:1 (Boussinesq xấp xỉ)

$$\Delta\sigma_z = q \cdot \dfrac{B \cdot L}{(B + z)(L + z)}$$

với $B, L$ = kích thước móng tải, $z$ = độ sâu dưới mũi cọc.

→ Dùng cho móng đơn / mố cầu hữu hạn.

---

## 5. Quy trình tính (per HK)

1. Xác định $H_{below}$ = chiều dày đất yếu còn lại dưới mũi cọc CDM
2. Chia thành phụ lớp $H_i$ (1 m mỗi cái)
3. Tại midpoint mỗi lớp:
   - $\sigma'_{v0,i}$ = $\sigma'_{v0,\text{mũi}} + \gamma' \cdot z_i$ (cộng dồn)
   - $\Delta\sigma_i$ = lấy từ phương pháp phân bố (4.1 hoặc 4.2)
   - $\sigma'_{vf,i} = \sigma'_{v0,i} + \Delta\sigma_i$
4. So sánh với $P_{C,i}$ → chọn công thức (NC / OC / cross_PC)
5. $S_2 = \sum S_i$

---

## 6. Ví dụ KE-HK1 (Demo trong code)

**Input:**
- $H_{soft} = 25$ m, $H_{CDM} = 20$ m → $H_{below} = 5$ m
- 5 phụ lớp 1 m, mỗi phụ lớp có $(C_c, C_s, e_0, P_C, \gamma_{sub})$
- $q = 60$ kPa (tải đắp 3 m × $\gamma_{fill}$ 20)
- $\sigma'_{v0,\text{mũi}} = 120$ kPa
- Phương pháp: `infinite_slab`

**Output từ `cdm_s2_partial.py`:**

| z mũi (m) | H | $\sigma'_{v0}$ | $\Delta\sigma$ | $\sigma'_{vf}$ | mode | $S_i$ (cm) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 0,5 | 1,0 | 123,1 | 60,0 | 183,1 | NC | 3,19 |
| 1,5 | 1,0 | 129,3 | 60,0 | 189,3 | NC | 3,00 |
| 2,5 | 1,0 | 135,7 | 60,0 | 195,7 | NC | 2,75 |
| 3,5 | 1,0 | 142,4 | 60,0 | 202,4 | NC | 2,51 |
| 4,5 | 1,0 | 149,4 | 60,0 | 209,4 | cross_PC | 2,32 |
| | | | | | **Tổng $S_2$** | **13,77** |

**Tổng:**

| Thành phần | (cm) |
|---|:---:|
| $S_1$ — đàn hồi khối CDM | 10,5 |
| **$S_2$ — cố kết dưới mũi** | **13,8** |
| **$S_{\text{total}}$** | **24,3** |

---

## 7. Public API Python

```python
from cdm_s2_partial import (
    calc_S2_partial,
    calc_total_settlement_cdm,
    stress_distribution_infinite_slab,
    stress_distribution_2to1,
    create_table,
)

# Tính S2 cho 5 phụ lớp dưới mũi cọc
r = calc_S2_partial(
    layers_below_tip=[{'H_m': 1.0, 'e0': 1.7, 'Cc': 0.5,
                        'Cs': 0.1, 'PC_kPa': 80,
                        'gamma_kNm3': 16, 'gamma_sub_kNm3': 6.19},
                       ...],
    q_kPa=60.0,
    method='infinite_slab',
    sigma_v0_top_kPa=120.0,
)
# r['S2_cm'] = 13.77

# Tổng S_total
tot = calc_total_settlement_cdm(
    S1_cm=10.5, layers_below_tip=[...],
    q_kPa=60.0, method='infinite_slab',
)
# tot['S_total_cm'] = 24.27
```

---

## 8. SQLite — Bảng `cdm_s2_partial_results`

| Cột | Mô tả |
|---|---|
| `zone_code`, `bh_name` | KE/BXN/NHC, tên HK |
| `S1_cm`, `S2_cm`, `S_total_cm` | Lún các thành phần |
| `method` | 'infinite_slab' / 'method_2to1' |
| `q_kPa` | Tải áp dụng |
| `n_layers`, `H_below_m` | Phụ lớp / chiều dày bên dưới |
| `detail_json` | Chi tiết từng phụ lớp (JSON) |

UNIQUE: `(zone_code, bh_name, method, q_kPa)`.

---

## 9. Khuyến nghị thiết kế

| Tiêu chí | Khuyến nghị |
|---|---|
| Cọc CDM **hết lớp bùn** ($H_{below} = 0$) | $S_2 = 0$ — chỉ kiểm tra $S_1$ vs TCCS 41 Bảng 1 |
| Cọc CDM **không hết** ($H_{below} > 0,5$ m) | **PHẢI tính $S_2$** — tổng $S_{total} = S_1 + S_2$ |
| So với giới hạn ΔS TCCS 41 | $S_{total} \cdot (1 - U_t) \leq \Delta S_{\text{limit}}$ (Bảng 1) |
| $U_t$ tại thời điểm xong mặt đường | $\geq 90\%$ (TCCS 41 Điều 6.2.3) |

---

## 10. Liên kết

- [scripts/cdm_s2_partial.py](scripts/cdm_s2_partial.py) — module
- [data/cdm_s2_partial.json](data/cdm_s2_partial.json) — config
- [39-tcvn9403-tru-dat-xi-mang.md](39-tcvn9403-tru-dat-xi-mang.md) — TCVN 9403
- [38-tccs41-nen-duong-dat-yeu.md](38-tccs41-nen-duong-dat-yeu.md) — TCCS 41 + Bjerrum
- [scripts/settlement_calc.py](scripts/settlement_calc.py) — $S_1$ TCVN 9403 Phụ lục C
- CLAUDE.md mục 35 (ΔS TCCS 41) + 36 (Bjerrum)

---

## 11. Engine hiện hành — `calc_s2_below_cdm` (cập nhật 2026-05-28)

S2 dưới mũi cọc nay tính theo **bản chất từng phân tố** (phụ lớp 2 m), phân loại theo
ký hiệu lớp và hệ số rỗng $e_0$:

| Loại phân tố | Phương pháp tính $S_i$ |
|---|---|
| **Cát** (F, 2a–2c, 3a–c, 4, 5, 6, 7) | Lún tức thời đàn hồi: $S_i = \dfrac{\Delta\sigma \cdot H_i}{E_s}$, $E_s = \alpha\cdot N_{SPT}$ |
| **Sét mềm** $e_0 \ge 1$ (cố kết thường) | Terzaghi 1D với $C_c$ (mục 3) |
| **Sét cứng** $e_0 < 1$ (quá cố kết) | $E_{oed}$ từ $a_{1-2}$: $S_i = \dfrac{\Delta\sigma \cdot H_i}{E_{oed}}$, $E_{oed}=\dfrac{1+e_0}{a_{1-2}}\times 98{,}07$ |

**Phân bố $\Delta\sigma$:** Boussinesq tải dải (móng băng) bề rộng $B$:
$\Delta\sigma(z') = \dfrac{q}{\pi}(\alpha + \sin\alpha)$, $\alpha = 2\arctan\dfrac{B}{2z'}$ ($z'$ = độ sâu dưới mũi).
Tùy chọn tắt → $\Delta\sigma = q$ không đổi. Dừng tích lũy khi $\Delta\sigma/\sigma'_{v0} < 10\%$.

**Lún tích lũy đến 15 năm** (so với $\Delta S$ cho phép TCCS 41):
$$S_2 = \sum_i S_{2,i}\cdot U_i(t),\quad t=15\text{ năm}$$
- Cát + sét cứng $e_0<1$ (cố kết nhanh) → $U \approx 1$ → lấy **đủ** $S_i$.
- Sét mềm $e_0 \ge 1$ (cố kết chậm) → chỉ phần đã cố kết $S_i\cdot U(15\text{n})$, $U$ từ $C_v$ + thoát nước 2 mặt ($H_{dr}=H/2$).

**$C_u$ cho $E_s$ và sức chịu tải:** dùng giá trị SAU hiệu chỉnh Bjerrum ($\mu\cdot S_u$), KHÔNG dùng $S_u$ nguyên.

**Tùy chọn cộng hoạt tải:** $q$ tính S1+S2 có thể = tải đắp tĩnh + hoạt tải xe (checkbox trên UI).

**Tham chiếu:** [scripts/settlement_calc.py](scripts/settlement_calc.py) `calc_s2_below_cdm()` · [scripts/cdm_length_optimize.py](scripts/cdm_length_optimize.py) (chọn chiều dài cọc theo lún + sức chịu tải) · [60-cdm-suc-chiu-tai-coc.md](60-cdm-suc-chiu-tai-coc.md).
