# 48 — Ổn định tổng thể tường cừ SW + CDM (Mục E)

Tài liệu tổng hợp công thức 3 kiểm tra ổn định tổng thể tường cừ SW kết hợp xử lý nền CDM, áp dụng cho Kè Công Viên TTHC.

**Tiêu chuẩn áp dụng:**
- TCVN 4253:2012 — Móng cọc và kết cấu chắn đất
- USACE EM 1110-2-2504 — Design of sheet pile walls
- FHWA GEC-13 — Driven piles / soldier piles
- TCVN 9403:2012 Phụ lục C — Trụ đất xi măng

---

## 1. Kiểm tra trượt cung tròn — Bishop simplified

Cung trượt qua chân cừ + lớp đất phía sau, kiểm tra hệ số ổn định trượt mất cân bằng theo phương pháp Bishop đơn giản (effective stress).

### 1.1 Hệ số ổn định Fs

$$F_s = \dfrac{\displaystyle \sum_{i=1}^{n} \dfrac{c'_i \cdot b_i + (W_i - u_i \cdot b_i) \tan \varphi'_i}{m_{\alpha,i}}}{\displaystyle \sum_{i=1}^{n} W_i \sin \alpha_i}$$

$$m_{\alpha,i} = \cos \alpha_i + \dfrac{\sin \alpha_i \cdot \tan \varphi'_i}{F_s} \qquad \text{(C.1)}$$

### 1.2 Trọng lượng slice và áp lực lỗ rỗng

$$W_i = \gamma_i \cdot h_i \cdot b_i$$

$$u_i = \gamma_w \cdot \max(0,\ \text{MNN}_i - y_{\text{cir},i})$$

$$W_{\text{eff},i} = W_i - u_i \cdot b_i$$

**MNN tại slice i:**

$$\text{MNN}_i = \begin{cases} z_{w,\text{Front}} & \text{nếu } x_i < 0 \\ z_{w,\text{Back}} & \text{nếu } x_i \geq 0 \end{cases}$$

### 1.3 Hình học cung trượt

Tại slice i với tâm cung $(x_c, y_c)$, bán kính $R$:

$$y_{\text{cir},i} = y_c - \sqrt{R^2 - (x_i - x_c)^2}$$

$$\sin \alpha_i = -\dfrac{x_i - x_c}{R}, \quad \cos \alpha_i = \dfrac{\sqrt{R^2 - (x_i - x_c)^2}}{R}$$

### 1.4 Chia lát (slicing)

Mặc định **1 lát / 1m** trên chiều rộng cung trượt:

$$n_{\text{slice}} = \max\left(30,\ \lceil x_{\text{right}} - x_{\text{left}} \rceil\right)$$

### 1.5 Bảng ký hiệu

| Ký hiệu | Đơn vị | Mô tả |
|---|---|---|
| $W_i$ | kN/m | Trọng lượng slice i (tính theo $\gamma_{\text{full}}$, kể cả dưới MNN) |
| $u_i$ | kN/m² | Áp lực nước lỗ rỗng tại đáy slice |
| $b_i$ | m | Chiều rộng slice (≈ 1m) |
| $h_i$ | m | Chiều cao slice (từ mặt đất tới cung) |
| $c'_i$ | kN/m² | Lực dính hiệu dụng (sét: $c' = c$ undrained; cát: $c' = 0$) |
| $\varphi'_i$ | ° | Góc ma sát hiệu dụng |
| $\alpha_i$ | rad | Góc nghiêng tiếp tuyến đáy slice |
| $\gamma_i$ | kN/m³ | Dung trọng đất slice i (đầy đủ — KHÔNG dùng $\gamma_{\text{sub}}$ trong $W_i$) |
| $\gamma_w$ | 9.81 kN/m³ | Dung trọng nước |
| $x_c, y_c$ | m | Tọa độ tâm cung trượt |
| $R$ | m | Bán kính cung trượt |

### 1.6 Tiêu chuẩn

$$F_s \geq F_{s,\min} = 1{,}30 \quad \text{(TCVN 4253, USACE EM 1110-2-2504)}$$

### 1.7 Lưu ý quan trọng — Effective stress chuẩn

**Cách đúng:** Driving moment dùng $W$ đầy đủ (đất ngậm nước vẫn có khối lượng → tạo momen kéo trượt). Resisting moment dùng $(W - u \cdot b)$ (effective normal force theo Terzaghi).

**Cách SAI:** Dùng $\gamma_{\text{sub}}$ cho cả driving + resisting → giảm cả hai → $F_s$ bị thổi phồng giả tạo.

---

## 2. Kiểm tra lật quanh chân cừ — Overturning

Tổng momen giữ (passive + neo + ma sát) so với momen lật (active + nước + surcharge) quanh **điểm chân cừ**.

### 2.1 Hệ số ổn định Fs_lật

$$F_{s,\text{lật}} = \dfrac{M_p + M_{\text{neo}} + M_{\text{ma sát}}}{M_a + M_w + M_q}$$

### 2.2 Momen lật (Driving)

$$M_a = \int_{z_p}^{z_t} \sigma_h^{\text{active}}(z) \cdot (z - z_{\text{tip}}) \, dz \quad \text{(active từ Front)}$$

$$M_w = \int \Delta p_w(z) \cdot (z - z_{\text{tip}}) \, dz \quad \text{(chênh lệch nước F-B)}$$

$$M_q = q \cdot K_a \cdot H \cdot \dfrac{H}{2} \quad \text{(surcharge)}$$

### 2.3 Momen giữ (Resisting)

$$M_p = \int_{z_p}^{z_b} \sigma_h^{\text{passive}}(z) \cdot (z_{\text{tip}} - z) \, dz \quad \text{(passive từ Back)}$$

### 2.4 Áp lực đất theo Rankine

**Đất sét (undrained):**

$$\sigma_h^{\text{active}} = K_a \cdot \sigma'_v - 2 c \sqrt{K_a}$$

$$\sigma_h^{\text{passive}} = K_p \cdot \sigma'_v + 2 c \sqrt{K_p}$$

**Đất cát (cohesionless):**

$$\sigma_h^{\text{active}} = K_a \cdot \sigma'_v, \qquad \sigma_h^{\text{passive}} = K_p \cdot \sigma'_v$$

**Hệ số áp lực đất Rankine:**

$$K_a = \tan^2\left(45° - \dfrac{\varphi}{2}\right), \qquad K_p = \tan^2\left(45° + \dfrac{\varphi}{2}\right)$$

### 2.5 Ứng suất hiệu dụng theo độ sâu

$$\sigma'_v(z) = \sum_{i: z_i < z} \gamma_{\text{eff},i} \cdot \Delta z_i$$

$$\gamma_{\text{eff},i} = \begin{cases} \gamma_i & \text{nếu } z_i > \text{MNN} \\ \gamma_{\text{sub},i} = \gamma_i - \gamma_w & \text{nếu } z_i < \text{MNN} \end{cases}$$

### 2.6 Tiêu chuẩn

$$F_{s,\text{lật}} \geq 2{,}00$$

---

## 3. Kiểm tra xoay nhổ chân cừ — Toe Kick-out (Free Earth Support)

Cừ tựa trên 2 điểm: đỉnh (neo / dầm mũ) và đáy ngàm vào lớp tốt. Kiểm tra khả năng chống xoay tại chân.

### 3.1 Hệ số Fs_toe

$$F_{s,\text{toe}} = \dfrac{M_p^{\text{below tip}}}{M_a^{\text{above tip}}}$$

Với $M_a^{\text{above tip}}$ tính từ mặt đất Front xuống chân cừ, $M_p^{\text{below tip}}$ tính 1m dưới chân cừ vào lớp đất tốt.

### 3.2 Tiêu chuẩn

$$F_{s,\text{toe}} \geq 1{,}50$$

---

## 4. Khối CDM composite — TCVN 9403:2012 Phụ lục C

Khi cung trượt cắt qua vùng đất được gia cố CDM, dùng tham số composite cho khối hỗn hợp đất-cột:

### 4.1 Cường độ + thông số composite

$$c_{\text{comp}} = a \cdot c_{\text{col}} + (1 - a) \cdot c_{\text{soil}} \qquad \text{(C.2)}$$

$$\tan \varphi_{\text{comp}} = a \cdot \tan \varphi_{\text{col}} + (1 - a) \cdot \tan \varphi_{\text{soil}}$$

$$\gamma_{\text{comp}} = a \cdot \gamma_{\text{col}} + (1 - a) \cdot \gamma_{\text{soil}}$$

$$\gamma_{\text{sub,comp}} = a \cdot \gamma_{\text{sub,col}} + (1 - a) \cdot \gamma_{\text{sub,soil}}$$

### 4.2 Bảng ký hiệu

| Ký hiệu | Đơn vị | Mô tả |
|---|---|---|
| $a$ | – | Tỷ lệ diện tích thay thế = $A_{\text{col}} / A_{\text{đơn vị}}$ (mặc định 0.20) |
| $c_{\text{col}}$ | kN/m² | Cường độ chống cắt cột CDM = $q_u / 2$ (Su từ qu 28 ngày) |
| $q_u$ | kN/m² | Cường độ nén tự do mẫu CDM 28 ngày (lab) |
| $\varphi_{\text{col}}$ | ° | Góc ma sát cột CDM (mặc định 30°) |
| $\gamma_{\text{col}}$ | kN/m³ | Dung trọng cột CDM (mặc định 19 kN/m³) |
| $c_{\text{soil}}, \varphi_{\text{soil}}$ | | Cường độ + ma sát của đất nền giữa các cột |

### 4.3 Hình học khối CDM

Mặc định dự án:

$$z_{\text{top,CDM}} = Z_{\text{Front}} \quad \text{(đáy đất đắp = mặt đất tự nhiên)}$$

$$z_{\text{bot,CDM}} = Z_{\text{Front}} - H_1 - 1{,}0 \quad \text{(đáy lớp bùn + 1m vào lớp tốt)}$$

$$\text{Chiều dày CDM} = H_1 + 1{,}0 \text{ m}, \qquad \text{Chiều rộng mặc định} = 5 \text{ m (user override)}$$

---

## 5. Quy ước thông số đầu vào

### 5.1 Lấy thông số đất

| Tham số | Nguồn | Ưu tiên |
|---|---|---|
| $\gamma, \varphi, c$ đất nền | SQLite `lab_tests` của HK (avg theo `depth_from_m/depth_to_m`) | 1 |
| $Cu$ (sét) | SQLite `lab_tests.Cu_UU_kPa` của HK | 1 |
| $\gamma_{\text{sub}}$ | $\gamma - \gamma_w$, sàn 5 kN/m³ | 1 |
| Symbol phân loại | SQLite `layers.symbol`: Clay (1, XMD, 3, 5, 5A, 5B) vs Sand (F, 2A-C, 4, 6, 7) | 1 |
| Phía Front | Đầy đủ tất cả lớp + Fill | — |
| Phía Back | **Chỉ từ lớp bùn (1, XMD) trở xuống** (đã đào hết Fill / lớp trên) | — |

### 5.2 Fill (đất đắp Front)

Bộ chuẩn dự án (xem CLAUDE.md mục 6):

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| $\gamma_{\text{fill}}$ | 18.0 kN/m³ | Đất đắp chặt vừa |
| $\varphi_{\text{fill}}$ | 25° | Đất đắp chặt vừa |
| $c_{\text{fill}}$ | 0 kPa | Cát đắp — không có lực dính |
| $\gamma_{\text{sub,fill}}$ | 8.0 kN/m³ | $\gamma_{\text{sat}} - \gamma_w \approx 8$ |

---

## 6. Tóm tắt 3 kiểm tra + Tiêu chuẩn

| Kiểm tra | Công thức Fs | $F_{s,\min}$ | Tiêu chuẩn |
|---|---|---|---|
| (1) Trượt cung tròn | $F_s = \dfrac{\sum \dfrac{c b + (W - u b) \tan \varphi}{m_\alpha}}{\sum W \sin \alpha}$ | **1.30** | TCVN 4253, USACE EM 1110-2-2504 |
| (2) Lật quanh chân cừ | $F_{s,\text{lật}} = \dfrac{M_p + M_{\text{neo}}}{M_a + M_w + M_q}$ | **2.00** | FHWA GEC-13 |
| (3) Xoay nhổ chân (toe kick-out) | $F_{s,\text{toe}} = \dfrac{M_p^{\text{below tip}}}{M_a^{\text{above tip}}}$ | **1.50** | USACE EM 1110-2-2504 |

---

## 7. File tham chiếu

- Engine: [scripts/sw_global_stability.py](scripts/sw_global_stability.py)
- Áp dụng UI: [scripts/app_cdm.py](scripts/app_cdm.py) — Mục E "Ổn định tổng thể"
- Earth pressure: [scripts/earth_pressure.py](scripts/earth_pressure.py)
- CDM TCVN 9403: [scripts/cdm_column_calc.py](scripts/cdm_column_calc.py) + [39-tcvn9403-tru-dat-xi-mang.md](39-tcvn9403-tru-dat-xi-mang.md)
- Wall geometry: [scripts/wall_internal_force.py](scripts/wall_internal_force.py)
