# TCCS 41:2022/TCĐBVN — Khảo sát, Thiết kế Nền Đường Ô Tô Trên Nền Đất Yếu

**Ban hành:** Tổng cục Đường bộ Việt Nam, xuất bản lần 1 — 2022  
**Phạm vi:** Nền đường ô tô đắp trên nền đất yếu; khảo sát → thiết kế → kiểm tra thi công

---

## 1. Phân loại đất yếu (Điều 4.1)

| Loại | Chỉ số chảy B | Mô tả | Trạng thái chịu tải |
|------|:---:|---|---|
| I | 0,75 < B ≤ 1,0 | Đất yếu, cố kết ổn định | Thông thường, có thể dùng đắp bằng cơ học |
| II | 0,50 < B ≤ 0,75 | Cố kết không ổn định | Cần xử lý hoặc kiểm soát tiến độ |
| III | B = 0 | Bùn (chảy) | Phải xử lý toàn bộ |

**Xác định B:** $B = \dfrac{W - W_p}{W_L - W_p}$ theo TCVN 4197

**Đất yếu điển hình (Điều 3.3):**
- Cọc thoát nước thẳng đứng: $D_e = 2(a+b)/\pi$, thường $a=100$ mm, $b=5$ mm → $D_e \approx 66$ mm
- Bản thoát nước ngang (bấc thấm): kích cỡ tiêu chuẩn 100×5 mm
- Giếng cát: $D = 300$–600 mm

---

## 2. Yêu cầu khảo sát địa chất (Điều 5)

### 2.1 Bố trí khoan thăm dò — Điều 5.3.2

#### 5.3.2.1 Bước TKCS (lập dự án đầu tư)

Sau khi thăm dò sơ bộ phát hiện đất yếu → bố trí lỗ khoan trên tim tuyến khoảng cách **250 m đến 500 m**. Có thể bổ sung điểm thăm dò cắt cánh, xuyên để xác định phạm vi đất yếu.

#### 5.3.2.2 Bước BVTK (thiết kế kỹ thuật)

Khoan thăm dò mặt cắt địa chất công trình bằng lỗ khoan cách nhau **100 ÷ 150 m** trên tim tuyến (kể cả khối lượng đã khoan ở bước TKCS). Với đường cao tốc và đường ô tô cấp III trở lên (và tương đương): cách nhau **100 m**. Trường hợp đặc biệt có thể rút ngắn hơn.

Mặt cắt địa chất công trình vuông góc tim tuyến: ít nhất **3 lỗ khoan/mặt cắt**. Khoảng cách giữa các mặt cắt: **150 ÷ 300 m**.

- Nền đắp mới: 1 HK tim đường + 2 HK hai bên vai
- Nền đắp mở rộng: 1 HK giữa phần đường cũ + 1 HK vai ngoài mở rộng + 1 HK vai ngoài nền cũ
- Mỗi phân đoạn đất yếu: **tối thiểu 2 mặt cắt ngang địa chất đại diện**

#### Bảng tổng hợp giới hạn khoảng cách

| Bước thiết kế | Dọc tuyến (m) | Số HK/mặt cắt | Khoảng cách mặt cắt (m) |
| --- | :---: | :---: | :---: |
| TKCS (lập DAĐT) — 5.3.2.1 | 250–500 | 1 | — |
| BVTK — dọc tuyến — 5.3.2.2 | 100–150 | ≥ 3 | 150–300 |
| Cao tốc / cấp III trở lên | 100 | ≥ 3 | 150–300 |

#### Kiểm tra tự động trong app (scripts/borehole_spacing.py)

```python
from borehole_spacing import check_spacing_532, save_distances_to_db

# Kiểm tra danh sách HK vs BVTK
res = check_spacing_532(bhs, design_step="BVTK", same_zone_only=True)
# res["pairs"] → [{bh1, bh2, distance_m, status: "Đạt"/"Gần quá"/"Xa quá"}]
# res["summary"] → {n_pairs, n_ok, n_too_close, n_too_far, min_dist_m, max_dist_m}

# Lưu vào SQLite bảng borehole_distances
save_distances_to_db(bhs, design_step="BVTK")
```

**Kết quả dự án TTHC (BVTK, 100–150 m):** xem tab Địa chất → bảng khoảng cách hố khoan.

**Chiều sâu hố khoan:**

- Qua hết lớp đất yếu + ≥ 3 m vào lớp tốt (không nhỏ hơn 1 lần chiều cao đắp)

### 2.2 Thí nghiệm tối thiểu per hố khoan (Điều 5.3.3 & Bảng 7.4.2)

| Thí nghiệm | Khoảng cách | Tiêu chuẩn | Mục đích |
|---|---|---|---|
| SPT | Mỗi 1–2 m (top 6 m: mỗi 1 m) | TCVN 9351 | Phân loại, sức chịu tải |
| Cắt cánh hiện trường (VST) | Mỗi **1 m** trong sét yếu | TCVN 9862 | Su không thoát nước |
| Lấy mẫu nguyên dạng | Mỗi **1,5–3 m** | TCVN 9437 | Thí nghiệm phòng |
| Nén cố kết | **Mỗi lớp** hoặc mỗi **3 m** nếu lớp dày | TCVN 4200 | Cc, Cs, Cv, PC |
| Cắt trực tiếp / ba trục | Mỗi lớp | TCVN 8868 | c, φ |
| Thí nghiệm thấm | Đại diện mỗi lớp | TCVN 8723 | k |

**Số mẫu nén cố kết tối thiểu (Bảng 7.4.2 diễn giải):**

| Chiều dày lớp đất yếu | Min mẫu/lớp/HK |
|---|:---:|
| < 3 m | 1 |
| 3–6 m | 2 |
| 6–15 m | 3–5 |
| > 15 m | ≥ 1 mẫu/3 m (làm tròn lên) |

### 2.3 Số liệu tối thiểu để xác định trị số tính toán (Điều 5.3.7)

**Quy tắc:** Đối với mỗi lớp đất yếu, mỗi chỉ tiêu đưa vào tính toán cần có **ít nhất 6 số liệu thí nghiệm**.

**Trị số tính toán:**

$$\Delta t = \Delta t_{tb} \pm \delta \qquad (2)$$

$$\delta = \sqrt{\frac{\sum (A_i - \Delta t_{tb})^2}{n - 1}} \qquad (3)$$

Trong đó:

- $\Delta t$ — trị số tính toán của chỉ tiêu
- $\Delta t_{tb}$ — trị số trung bình số học của các số liệu thí nghiệm
- $\delta$ — độ lệch chuẩn (standard deviation)
- $A_i$ — trị số của chỉ tiêu mỗi lần thí nghiệm
- $n$ — số lần thí nghiệm đối với mỗi chỉ tiêu

**Áp dụng:** Cần phân tích kỹ các điều kiện thực tế ảnh hưởng đến chất lượng mẫu trước khi thí nghiệm, kết hợp với kinh nghiệm chuyên gia địa kỹ thuật.

**Chỉ tiêu cần kiểm tra (lớp đất yếu CH/CL/MH/ML):**

| Chỉ tiêu | Ký hiệu | Dùng cho | Yêu cầu n |
|---|---|---|:---:|
| Hệ số nén | Cc | Tính lún OC/NC | ≥ 6 |
| Hệ số nở | Cs | Tính lún OC | ≥ 6 |
| Hệ số cố kết | Cv | Tính S(t) | ≥ 6 |
| Áp lực tiền cố kết | PC | Phân loại OC/NC | ≥ 6 |
| Góc ma sát | φ | Ổn định mái dốc | ≥ 6 |
| Lực dính | c | Ổn định mái dốc | ≥ 6 |

**Hệ số biến thiên tham khảo ($CV = \delta / \Delta t_{tb}$):**

| Chỉ tiêu | CV điển hình sét mềm | Nhận xét |
|---|:---:|---|
| Cc | 20–40% | Biến thiên cao — cần nhiều mẫu |
| Cv | 30–60% | Biến thiên rất cao |
| φ (UU) | 5–15% | Tương đối ổn định |
| c (UU) | 20–40% | Phụ thuộc trạng thái mẫu |

**Triển khai trong `settlement_calc.py`:**

```python
def check_samples_vs_tccs41(zone_code) -> dict:
    """
    Trả về per lớp đất (symbol_tcvn):
      layers[i]['params']['Cc'] = {
        'n': 6,            # số mẫu
        'mean': 0.530,     # Δtb
        'std': 0.153,      # δ
        'cv_pct': 28.8,    # hệ số biến thiên %
        'ok': True,        # n >= 6?
        'design_min': 0.377,  # Δtb - δ
        'design_max': 0.683,  # Δtb + δ
      }
    """
```

**Kết quả dự án TTHC (2026-05-19):**

| Zone | Lớp yếu | Cc Đạt/Thiếu | Cs Đạt/Thiếu | Cv Đạt/Thiếu | PC Đạt/Thiếu |
| --- | :---: | :---: | :---: | :---: | :---: |
| NHC | 8 | 3/2 | 3/2 | 3/2 | 3/2 |
| BXN | — | — | — | — | — |
| KE | — | 0 mẫu Cc | — | — | — |

---

## 3. Tiêu chuẩn độ lún còn lại sau thi công (Bảng 1 — Điều 6.1)

| Loại đường | Đoạn gần mố cầu (m) | Đoạn hai bên cầu/cống chui | Đoạn thông thường |
|---|:---:|:---:|:---:|
| Cao tốc ≥ 80 km/h, tăng mặt cao A1 | **≤ 10 cm** | **≤ 20 cm** | **≤ 30 cm** |
| Đường cấp ≤ 60 km/h, tăng mặt cao A2 | **≤ 20 cm** | **≤ 30 cm** | **≤ 40 cm** |

**Tốc độ lún còn lại:** ≤ 2 cm/năm sau khi làm xong mặt đường

---

## 4. Công thức tính lún cố kết (Điều 9 + Phụ lục A)

### 4.1 Tổng lún cố kết sơ cấp

Mỗi lớp đất thí nghiệm nén cố kết:

**Trường hợp quá cố kết ($\sigma_{vf} \leq P_C$):**

$$S_i = \frac{C_s}{1 + e_0} \cdot H_i \cdot \log_{10}\frac{\sigma_{vf}}{\sigma_{v0}}$$

**Trường hợp cắt qua PC ($\sigma_{v0} < P_C < \sigma_{vf}$):**

$$S_i = H_i \left[ \frac{C_s}{1+e_0} \log_{10}\frac{P_C}{\sigma_{v0}} + \frac{C_c}{1+e_0} \log_{10}\frac{\sigma_{vf}}{P_C} \right]$$

**Trường hợp bình thường cố kết ($\sigma_{v0} \geq P_C$):**

$$S_i = \frac{C_c}{1 + e_0} \cdot H_i \cdot \log_{10}\frac{\sigma_{vf}}{\sigma_{v0}}$$

**Ký hiệu:**

| Ký hiệu | Ý nghĩa | Đơn vị |
|---|---|---|
| $H_i$ | Chiều dày lớp $i$ | m |
| $e_0$ | Hệ số rỗng ban đầu | — |
| $C_c$ | Chỉ số nén | — |
| $C_s$ | Chỉ số nở | — |
| $\sigma_{v0}$ | Ứng suất hữu hiệu ban đầu tại giữa lớp | kPa |
| $\sigma_{vf}$ | Ứng suất hữu hiệu cuối cùng $= \sigma_{v0} + \Delta\sigma$ | kPa |
| $P_C$ | Áp lực tiền cố kết | kPa |

**Ứng suất do đắp:** $\Delta\sigma = \gamma_{fill} \times H_{fill}$ (kPa) — dùng tải đều, không giảm theo chiều sâu nếu $B_{fill} \gg H_{soil}$

**Ứng suất hữu hiệu tự nhiên:** $\sigma_{v0} = \sum \gamma'_i \cdot \Delta z_i$ với $\gamma' = \gamma_{sat} - \gamma_w$

### 4.2 Trình tự tính lún sơ bộ TKCS — Điều 9.2.3 (vòng lặp)

Tải trọng đắp tác dụng lên nền bao gồm cả **phần đắp lún vào trong đất yếu** S — lúc đầu chưa biết S nên phải lặp:

**Bước 1 — Giả thiết $S_{gt}$ ban đầu:**

$$S_{gt} = (5 \div 10)\% \times H_{soft} \quad \text{[đất thường]}$$

$$S_{gt} = (20 \div 30)\% \times H_{soft} \quad \text{[than bùn lún nhiều]}$$

**Bước 2 — Chiều cao đắp hiệu dụng (kể phần lún vào):**

$$H'_{tk} = H_{fill} + S_{gt}$$

$$\Delta\sigma = \gamma_{fill} \times H'_{tk}$$

**Bước 3 — Tính $S_c$** dùng công thức $C_c/C_s$ (Phụ lục A) với $\Delta\sigma$ từ bước 2.

**Bước 4 — Kiểm tra hội tụ:**

$$\text{Nếu } |S_c - S_{gt}| < \varepsilon \;\Rightarrow\; S_{final} = S_c \quad \text{(dừng)}$$

$$\text{Nếu không} \;\Rightarrow\; S_{gt} = S_c \quad \text{(quay bước 2)}$$

Giá trị $\varepsilon$ thực hành: 1 cm (TKCS), 0,1 cm (BVTC).

**Kết quả điển hình (NHC, $H_{fill}=3$ m, $H_{soft}=35$ m, $S_{gt,init}=7{,}5\%$):**

| Vòng | S_gt (cm) | H'_tk (m) | Δσ (kPa) | S_calc (cm) | Delta (cm) |
| --- | --- | --- | --- | --- | --- |
| 1 | 262,5 | 5,63 | 112,5 | 189,3 | 73,2 |
| 2 | 189,3 | 4,89 | 97,9 | 168,7 | 20,6 |
| 3 | 168,7 | 4,69 | 93,7 | 162,6 | 6,1 |
| 4 | 162,6 | 4,63 | 92,5 | 160,8 | 1,8 |
| 5 | 160,8 | 4,61 | 92,2 | 160,2 | 0,6 ✓ |

$S_{\text{không lặp}} = 107$ cm; **$S_{TKCS\,9.2.3} = 160$ cm (+50%)** — phần tăng do tải trọng đắp bổ sung bù lún.

**Triển khai trong `settlement_calc.py`:**

```python
def calc_settlement_iterative_9_2_3(bh_name, zone_code,
    H_fill_m=3.0, gamma_fill=20.0, S_gt_init_pct=7.5,
    tolerance_cm=1.0, max_iter=20) -> dict:
    # Trả về: S_ref_cm, S_final_cm, S_increase_pct, converged, n_iterations, iterations[{iter,S_gt,H_eff,Dsigma,S_calc,delta}]
```

---

## 5. Độ cố kết theo thời gian (Điều 9.3 + Phụ lục D)

### 5.1 Cố kết theo phương đứng

$$T_v = \frac{C_v \cdot t}{H_{dr}^2}$$

Trong đó $H_{dr} = H$ (thoát nước 1 phía) hoặc $H_{dr} = H/2$ (thoát nước 2 phía); $t$ tính bằng năm → $C_v$ cần đổi ra m²/năm (1 cm²/s ≈ 3,154×10³ m²/năm).

**Độ cố kết $U_v$:**

$$U_v \leq 60\%: \quad U_v = 2\sqrt{\frac{T_v}{\pi}}$$

$$U_v > 60\%: \quad U_v = 1 - \frac{8}{\pi^2} \exp\!\left(-\frac{\pi^2 T_v}{4}\right)$$

### 5.2 Cố kết theo phương ngang (bấc thấm / giếng cát) — Điều 7.5.1

$$T_h = \frac{C_h \cdot t}{d_e^2}$$

$$F(n) = \ln(n) - \frac{3}{4} \quad \text{(không xét smear)}$$

$$F(n) = \ln\!\frac{n}{s} + \frac{k_h}{k_s}\ln(s) - \frac{3}{4} \quad \text{(có smear, } s = d_s/d_w,\; k_h/k_s \approx 3\text{)}$$

$$U_h = 1 - \exp\!\left(\frac{-8\, T_h}{F(n)}\right)$$

| Ký hiệu | Ý nghĩa |
|---|---|
| $d_e$ | Đường kính ảnh hưởng (m): tam giác → $1{,}05s$; vuông → $1{,}13s$ |
| $d_w$ | Đường kính bấc thấm tương đương $= 2(a+b)/\pi \approx 0{,}066$ m |
| $s$ | Khoảng cách bấc thấm (m) |
| $n$ | $d_e/d_w$ |
| $C_h$ | Hệ số cố kết ngang (≈ $C_v$ hoặc $1{,}5$–$2 \times C_v$ với sét nhạy cảm) |

### 5.3 Độ cố kết kết hợp (Điều 9.4.2 — công thức 38)

$$U = 1 - (1 - U_v)(1 - U_h)$$

---

## 6. Các thông số thiết kế bấc thấm (Điều 7.6)

| Thông số | Giá trị thông dụng |
|---|---|
| Kích thước bấc thấm | 100 × 5 mm |
| $d_w$ tương đương | $2(100+5)/\pi = $ **66,8 mm ≈ 0,067 m** |
| Sơ đồ lưới tam giác | $d_e = 1{,}05 \times s$ |
| Sơ đồ lưới vuông | $d_e = 1{,}13 \times s$ |
| Khoảng cách $s$ thông dụng | 1,0–1,5 m |
| Chiều sâu cắm bấc thấm | Hết lớp đất yếu hoặc đến lớp thoát nước |
| Lớp đệm cát | ≥ 0,5 m trên đỉnh bấc thấm |

---

## 7. Thiết kế giếng cát (Điều 7.7–7.8)

| Thông số | Giá trị |
|---|---|
| Đường kính giếng $D$ | 300–600 mm |
| Khoảng cách $s$ | $(2$–$3{,}5)D$ |
| Sơ đồ tam giác | $d_e = 1{,}05s$ |
| $n = d_e/D$ | 3,5–7 |
| $F(n) = \ln(n) - 3/4$ | 0,5–1,2 thông thường |

---

## 8. Điều kiện kiểm tra ổn định (Điều 6.2, Phụ lục C)

$$F \geq F_{min}$$

| Loại công trình | $F_{min}$ |
|---|:---:|
| Đường thông thường | 1,20 |
| Cao tốc, đường cấp cao | **1,40** |
| Giai đoạn thi công | 1,10 |

**Phương pháp Bishop (Phụ lục C — công thức C.1):**

$$K_s = \frac{\sum \left[ c'_i \cdot l_i + (W_i - u_i \cdot l_i)\tan\varphi'_i \right]}{\sum W_i \sin\alpha_i}$$

**Kiểm tra heave (Điều 7.2.2):**

$$\sigma'_{vz} \geq (1{,}2 \div 1{,}5) \times \sigma_{gz} \quad \text{tại đáy đất yếu}$$

---

## 9. Tải trọng đắp thiết kế (Điều 6.4)

$$W_t = K \times Q_i \quad \text{(tải trọng xe)}$$

$$h_0 = \frac{W_i}{\gamma \cdot B_r \cdot l} \quad \text{(chiều cao đắp tối thiểu không bị lún — Điều 8.4.4)}$$

---

## 10. So sánh các phương án xử lý nền (Mục 7)

| Phương án | Cơ chế | Ưu điểm | Nhược điểm |
|---|---|---|---|
| Không xử lý | Tự cố kết | Rẻ nhất | Thời gian dài, lún lớn |
| Bấc thấm (PVD) | Thoát nước ngang | Nhanh, phổ biến | Cần surcharge + thời gian |
| Giếng cát | Thoát nước ngang | Vật liệu địa phương | Hiệu quả kém hơn PVD |
| CDM | Cột xi măng đất | Khống chế lún tốt | Đắt, thi công phức tạp |
| Đắp trước (surcharge) | Tăng tải | Kết hợp với PVD | Cần mặt bằng |

---

## 11. Ký hiệu và đơn vị chuẩn

| Ký hiệu | Đơn vị | Mô tả |
|---|---|---|
| $C_c$ | — | Chỉ số nén (compression index) |
| $C_s$ | — | Chỉ số nở (swelling index) |
| $C_v$ | cm²/s hoặc m²/năm | Hệ số cố kết đứng |
| $C_h$ | cm²/s hoặc m²/năm | Hệ số cố kết ngang |
| $P_C$ | kPa | Áp lực tiền cố kết |
| $e_0$ | — | Hệ số rỗng ban đầu |
| $\gamma_{sat}$ | kN/m³ | Dung trọng bão hòa |
| $\gamma'$ | kN/m³ | Dung trọng đẩy nổi $= \gamma_{sat} - 9{,}81$ |
| $T_v$ | — | Nhân tố thời gian đứng |
| $T_h$ | — | Nhân tố thời gian ngang |
| $U$ | % | Độ cố kết |
| $S$ | m hoặc cm | Độ lún |
| $\Delta S$ | cm | Lún còn lại sau thi công |

---

## 12. Tham chiếu

- Tính toán lún: [scripts/settlement_calc.py](scripts/settlement_calc.py)
- Thông số mặc định: [data/tccs41_params.json](data/tccs41_params.json)
- Dữ liệu địa chất: [data/TTHC.sqlite](data/TTHC.sqlite) — bảng `lab_tests`, `strat_layers`
- So sánh phương án: Tab "Dự báo độ lún" trong app_cdm.py
