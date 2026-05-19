# TCVN 9403:2012 — Gia Cố Đất Nền Yếu bằng Phương Pháp Trụ Đất Xi Măng

**Ban hành:** BKHCN, 2012  
**Phạm vi:** Thiết kế, thi công, kiểm tra chất lượng trụ đất xi măng (CDM/deep mixing) trên nền đất yếu

---

## 1. Phạm vi và Định nghĩa (Điều 1–3)

**Phương pháp trộn sâu (Deep Mixing / CDM):**
- Trộn khô (dry mixing): bơm xi măng khô vào đất, trộn bằng cánh quay
- Trộn ướt (wet mixing): bơm vữa xi măng vào đất

**Ký hiệu quan trọng:**

| Ký hiệu | Ý nghĩa | Đơn vị |
|---|---|---|
| $q_u$ | Cường độ nén nở hông (unconfined compressive strength) | kPa |
| $C_c$ | Cường độ chịu cắt của trụ xi măng $= q_u/2$ | kPa |
| $C_s$ | Cường độ chịu cắt của đất xung quanh ($C_u$) | kPa |
| $a$ | Tỷ lệ diện tích thay thế $= nA_c/(BL)$ | — |
| $E_c$ | Mô đun biến dạng trụ xi măng | kPa |
| $E_s$ | Mô đun biến dạng đất giữa trụ | kPa |
| $C_{uu}$ | Cường độ cắt tổ hợp của khối gia cố | kPa |

---

## 2. Yêu cầu Khảo sát Địa chất (Điều 5)

### 2.1 Thí nghiệm tối thiểu

| Thí nghiệm | Tần suất | Mục đích |
|---|---|---|
| Cắt cánh hiện trường (VST) | Mỗi 1 m trong đất yếu | $C_u$ không thoát nước |
| Lấy mẫu nguyên dạng | Mỗi 1,5 m | w, LL, LP, ρ, $C_u$ |
| Thí nghiệm pH và hàm lượng hữu cơ | Đại diện mỗi lớp | Chọn loại xi măng, hàm lượng |
| SPT | Đỉnh và đáy lớp yếu | Phân tầng |

### 2.2 Thí nghiệm cột thử (Điều 5.4)

**Bắt buộc trước khi thi công đại trà:**
- Tối thiểu 3 cột thử với hàm lượng xi măng dự kiến
- Lấy mẫu kiểm tra $q_u$ sau 7, 14, 28 ngày
- Tỷ số $q_{u,field}/q_{u,lab} = 0{,}2$–$0{,}5$ (trung bình 0,3–0,4)

---

## 3. Yêu cầu Số Lượng Mẫu Kiểm Tra Chất Lượng (Bảng B.1)

| Quy mô dự án (số cột) | Mẫu phòng thí nghiệm/lớp | Thí nghiệm hiện trường |
|:---:|:---:|:---:|
| ≤ 100 | 2 | 5 |
| ≤ 500 | 5 | 10 |
| ≤ 1 000 | 10 | 30 |
| ≤ 2 000 | 15 | 50 |
| > 2 000 | 20 | 100 |

---

## 4. Công thức Thiết kế (Phụ lục B)

### 4.1 Tỷ lệ diện tích thay thế

$$a = \frac{n \cdot A_c}{B \times L}$$

Trong đó:
- $n$ — số cột trong nhóm (diện tích $B \times L$)
- $A_c = \pi D^2/4$ — diện tích tiết diện ngang mỗi cột (m²)
- Phạm vi thông dụng: $a = 0{,}15$–$0{,}35$

### 4.2 Cường độ cắt tổ hợp của khối (công thức B.1)

$$C_{uu} = C_s \cdot (1 - a) + C_c \cdot a$$

Trong đó:
- $C_s = C_u$ — cường độ cắt không thoát nước của đất yếu (kPa)
- $C_c = q_{u,field}/2$ — cường độ cắt của trụ tại hiện trường (kPa)

### 4.3 Mô đun biến dạng

$$E_c = (50 \div 100) \times C_{c,col} \quad (\text{kPa})$$

$$E_s = 250 \times C_u \quad (\text{kPa})$$

Trong đó $C_{c,col} = q_{u,design}/2$ là cường độ cắt thiết kế của trụ (kPa). Thông dụng: $E_c = 75 \times C_{c,col}$ (giá trị trung bình).

### 4.4 Hệ số phân bổ ứng suất

Ứng suất phân bổ vào trụ và đất xung quanh:

$$\frac{\sigma_c}{\sigma_s} = \frac{E_c}{E_s} \quad \text{(phương pháp đơn giản)}$$

$$\sigma_s = \frac{q \cdot (1 - a \cdot n_\sigma)}{1 - a} \quad \text{với } n_\sigma = \frac{E_c}{E_s} \text{ (hệ số tập trung ứng suất)}$$

---

## 5. Tính Lún (Phụ lục C)

### 5.1 Lún tổng

$$S = S_1 + S_2 \qquad \text{(C.1)}$$

### 5.2 Lún trong vùng gia cố (công thức C.2)

$$S_1 = \frac{q \cdot H}{a \cdot E_c + (1 - a) \cdot E_s}$$

Trong đó:
- $q$ — áp lực tải đắp tại đỉnh cột (kPa) $= \gamma_{fill} \times H_{fill}$
- $H$ — chiều sâu vùng gia cố (m)
- $E_c = (50$–$100) \times C_{c,col}$ (kPa)
- $E_s = 250 \times C_u$ (kPa)

### 5.3 Lún ngoài vùng gia cố ($S_2$)

Dùng phương pháp nén cố kết thông thường ($C_c/C_s$) cho các lớp đất dưới đáy trụ.

### 5.4 Hệ số giảm lún CDM

Lún CDM so với không xử lý:

$$\beta_{cdm} = \frac{S_{cdm}}{S_{no\text{-}treat}} = \frac{1}{a \cdot (E_c/E_s - 1) + 1}$$

Thông thường $\beta_{cdm} \approx 0{,}15$–$0{,}30$ (giảm 70–85%).

---

## 6. Tương quan Cường độ Hiện trường / Phòng thí nghiệm

$$q_{u,field} \approx (0{,}2 \div 0{,}5) \times q_{u,lab} \quad \Rightarrow \quad \text{dùng } 0{,}3\text{–}0{,}4 \text{ thiên về an toàn}$$

**Hình B.4 TCVN 9403:** Đường hồi quy $q_{u,field}$ vs $q_{u,lab}$ từ các dự án Việt Nam và Nhật.

**Khuyến nghị thiết kế:**
- Lấy $q_{u,design} = 0{,}33 \times q_{u,lab}$ (hệ số 3 về phía an toàn)
- Hoặc hiệu chỉnh theo kết quả cột thử tại chỗ

---

## 7. Thí nghiệm Phòng — Trộn Khô (Phụ lục D)

| Thông số | Giá trị |
|---|---|
| Khuôn đúc mẫu | $D = 50$ mm, $H = 100$ mm |
| Tuổi thí nghiệm | 3, 7, 14, 28, 90 ngày |
| Điều kiện bảo dưỡng | Nhiệt độ phòng, bọc nilon tránh mất nước |
| Thí nghiệm | Nén nở hông $q_u = F/A$ |

**Khối lượng đất khô trong khuôn:**

$$G_s = \rho_s \times V$$

$$\gamma_k = \frac{G_s}{V \cdot (1 + 0{,}01 \times w)}$$

Trong đó $\rho_s$ là khối lượng riêng hạt (g/cm³), $V$ là thể tích khuôn, $w$ là độ ẩm đất tự nhiên (%).

**Hàm lượng xi măng (cement content ratio):**

$$\alpha_c = \frac{m_{cement}}{m_{dry\text{-}soil}} \times 100\%$$

Thông dụng: $\alpha_c = 7$–$15\%$ cho đất sét yếu.

---

## 8. Thí nghiệm Phòng — Trộn Ướt (Phụ lục E)

| Thông số | Giá trị |
|---|---|
| Khuôn đúc mẫu | Lập phương 70,7 mm hoặc trụ $D=50$ mm, $H=100$ mm |
| Tỷ lệ nước/xi măng (W/C) | 0,6–1,0 (thông dụng 0,8) |
| Tuổi thí nghiệm | 7, 14, 28, 91 ngày |
| Bảo dưỡng | Ngâm nước, nhiệt độ 20±2°C |
| Thí nghiệm | $q_u = F/A$; nếu lập phương → đổi đơn vị |

---

## 9. Cường độ Tham chiếu (Bảng G.1) — $q_u$ (kG/cm² → kPa = ×98,07)

| Loại đất | Địa điểm | w (%) | Cu (kG/cm²) | qu 7%XM-28ngày | qu 7%XM-90ngày | qu 12%XM-28ngày | qu 12%XM-90ngày |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Sét pha | Hà Nội | 45 | 0,16 | 3,26 | 3,97 | 4,43 | 4,48 |
| Cát pha | Nam Hà | 41 | — | 2,24 | — | 3,21 | — |
| Sét pha xám đen hữu cơ | Hà Nội | 62 | 0,23 | — | — | 3,29 | 3,42 |
| Sét xám xanh hữu cơ | — | 35 | 0,23 | 3,00 | 4,28 | — | — |
| Sét pha | — | 52 | 0,10 | 0,61 | 0,66 | 2,13 | 2,50 |
| Sét xám xanh | Hà Nội | 51 | 0,10 | — | — | 2,39 | 2,55 |
| Sét pha đất | Hà Nội | 95 | 0,21 | — | — | 0,51 | 0,82 |
| Sét pha hữu cơ | — | 30 | 0,32 | 11,0 | 19,0 | — | — |
| Bùn sét hữu cơ | — | 74 | 0,39 | — | — | 1,22 | — |
| Bùn sét hữu cơ | Hải Dương | 36 | — | 6,18 | 6,50 | 9,13 | 9,53 |
| Cát pha | Hà Nội | 26 | — | 7,45 | 7,85 | — | 7,92 |
| Sét | Hải Dương | 50 | 0,28 | 1,63 | 1,85 | 3,01 | 3,95 |

**Ghi chú:** Đơn vị gốc kG/cm² → ×98,07 = kPa; ×10 = T/m²

---

## 10. Kiểm tra Ổn định Tổng thể (Điều 6.3)

Dùng phương pháp Bishop với cường độ cắt tổ hợp:

$$C_{uu} = C_s \cdot (1 - a) + C_c \cdot a$$

**Hệ số an toàn tối thiểu:**
- Thi công: $F_s \geq 1{,}10$
- Khai thác thông thường: $F_s \geq 1{,}20$
- Cao tốc / đường cấp I: $F_s \geq 1{,}40$ (theo TCCS 41:2022)

---

## 11. Tham chiếu

- Tính toán lún CDM: [scripts/cdm_column_calc.py](scripts/cdm_column_calc.py)
- Thông số mặc định: [data/tcvn9403_params.json](data/tcvn9403_params.json)
- Dữ liệu thí nghiệm: [data/TTHC.sqlite](data/TTHC.sqlite) — bảng `cdm_design`, `cdm_lab_results`
- So sánh với xử lý bấc thấm: [scripts/settlement_calc.py](scripts/settlement_calc.py) + [data/tccs41_params.json](data/tccs41_params.json)
