# 18 — Sức Chịu Tải Cọc Đóng theo TCVN 11823-10:2017

**Tiêu chuẩn:** TCVN 11823-10:2017 — Thiết kế cầu đường bộ, Phần 10: Nền móng  
**Phạm vi:** Cọc đóng — phân tích tĩnh học theo đất nền (Điều 7.3.8.6)  
**Nguồn JSON:** [data/driven_pile_TCVN11823.json](data/driven_pile_TCVN11823.json)  
**Script:** [scripts/driven_pile_TCVN11823.py](scripts/driven_pile_TCVN11823.py)

---

## 18.1 Công thức Tổng quát (Điều 7.3.8.6.1)

$$R_R = \varphi_{sta} \cdot R_n \qquad \text{(Pt. 58)}$$

$$R_n = R_p + R_s \qquad \text{(Pt. 59)}$$

$$R_p = q_p \cdot A_p \qquad R_s = q_s \cdot A_s \qquad \text{(Pt. 60-61)}$$

| Ký hiệu | Ý nghĩa | Đơn vị |
|---------|---------|--------|
| $R_R$ | Sức kháng tính toán (có hệ số) | N |
| $\varphi_{sta}$ | Hệ số sức kháng — tra Bảng 9 theo phương pháp | — |
| $R_n$ | Sức kháng danh định | N |
| $R_p$ | Sức kháng chống mũi cọc | N |
| $R_s$ | Sức kháng ma sát thành bên | N |
| $q_p$ | Sức kháng chống mũi đơn vị | MPa |
| $q_s$ | Sức kháng ma sát đơn vị | MPa |
| $A_p$ | Diện tích mũi cọc | mm² |
| $A_s$ | Diện tích thành bên cọc = chu vi × chiều dài | mm² |

---

## 18.2 Phương pháp α — Đất Sét (Điều 7.3.8.6.2)

**Áp dụng:** Cọc đóng trong đất sét bão hòa — ứng suất tổng cộng.

$$q_s = \alpha \cdot S_u \qquad \text{(Pt. 62)}$$

$$q_p = 9 \cdot S_u \qquad \text{(Pt. 65)}$$

| Tham số | Giá trị |
|---------|--------|
| $S_u$ | Sức kháng cắt không thoát nước (MPa) |
| $\alpha$ | Hệ số kết dính — tra biểu đồ Tomlinson (1980), Hình 18 |

### Bảng tra $\alpha$ theo $S_u$ — Tomlinson (1980), Hình 18

| $S_u$ (kN/m²) | $S_u$ (MPa) | $\alpha$ |
|--------------|------------|---------|
| ≤ 25 | ≤ 0.025 | 1.00 |
| 50 | 0.050 | 0.92 |
| 75 | 0.075 | 0.75 |
| 100 | 0.100 | 0.60 |
| 150 | 0.150 | 0.50 |
| ≥ 200 | ≥ 0.200 | 0.40 |

> Nội suy tuyến tính cho các giá trị trung gian. Hàm `alpha_tomlinson(Su_MPa)` trong script thực hiện nội suy này.

**Hệ số sức kháng:** $\varphi_{sta} = 0.35$

---

## 18.3 Phương pháp β — Đất Sét (Điều 7.3.8.6.3)

**Áp dụng:** Cọc hình lăng trụ trong đất sét — ứng suất có hiệu.

$$q_s = \beta \cdot \sigma'_v \qquad \text{(Pt. 63)}$$

| Tham số | Giá trị |
|---------|--------|
| $\sigma'_v$ | Ứng suất có hiệu thẳng đứng (MPa) |
| $\beta$ | Tra biểu đồ Hình 19 (Esrig & Kirby 1979) theo OCR |

**Hệ số sức kháng:** $\varphi_{sta} = 0.25$

---

## 18.4 Phương pháp λ — Đất Sét (Điều 7.3.8.6.4)

**Áp dụng:** Cọc ống đóng trong đất sét.

$$q_s = \lambda \cdot (\sigma'_v + 2S_u) \qquad \text{(Pt. 64)}$$

| Tham số | Giá trị |
|---------|--------|
| $\sigma'_v$ | Ứng suất có hiệu thẳng đứng tại điểm giữa lớp (MPa) |
| $S_u$ | Sức kháng cắt không thoát nước (MPa) |
| $\lambda$ | Tra biểu đồ Hình 20 (Vijayvergiya & Focht 1972) |

**Hệ số sức kháng:** $\varphi_{sta} = 0.40$

---

## 18.5 Phương pháp SPT Meyerhof — Đất Rời (Điều 7.3.8.6.7)

**Áp dụng:** Cát, cát bột không pha sét.

### Sức kháng mũi cọc (Pt. 68)

$$q_p = 0.038 \cdot N_{160} \cdot \frac{D_b}{D} \leq \lambda_q \quad \text{(MPa)}$$

| Đất | $\lambda_q$ giới hạn |
|-----|---------------------|
| Cát | $8 \times 0.4 N_{160} = 3.2 N_{160}$ (MPa) |
| Cát bột không pha sét | $6 \times 0.3 N_{160} = 1.8 N_{160}$ (MPa) |

### Sức kháng ma sát thành bên

| Loại cọc | Công thức |
|---------|----------|
| Cọc **chiếm chỗ** (đặc, hộp kín) | $q_s = 0.0019 \cdot N_{160}$ (MPa) — Pt. 69 |
| Cọc **không chiếm chỗ** (chữ H, ống hở) | $q_s = 0.00096 \cdot N_{160}$ (MPa) — Pt. 70 |

| Tham số | Ý nghĩa |
|---------|--------|
| $N_{160}$ | Số búa SPT hiệu chỉnh theo áp lực tầng phủ (búa/300mm) — Điều 4.6.2.4 |
| $D$ | Đường kính hoặc bề rộng cọc (mm) |
| $D_b$ | Chiều dài cọc ngàm trong **tầng đất chịu lực** (mm) — không phải tổng chiều dài cọc |

> **Lưu ý quan trọng:** $D_b$ là chiều sâu xuyên vào tầng đất chịu lực (bearing stratum), không phải tổng chiều dài cọc. Với cọc xuyên qua nhiều lớp, $D_b$ chỉ tính từ đỉnh tầng chịu lực đến mũi cọc.

**Hệ số sức kháng:** $\varphi_{sta} = 0.30$

---

## 18.6 Phương pháp CPT Nottingham & Schmertmann (Điều 7.3.8.6.7)

**Áp dụng:** Cát, cát bột không pha sét.

### Sức kháng mũi cọc (Pt. 71)

$$q_p = \frac{q_{c1} + q_{c2}}{2} \quad \text{(MPa)}$$

- $q_{c1}$: Trung bình $q_c$ trong khoảng $0.7D$ đến $4.0D$ **dưới** mũi cọc (dùng quy tắc đường tối thiểu, chọn giá trị $q_{c1}$ nhỏ nhất)
- $q_{c2}$: Trung bình $q_c$ trong khoảng $8D$ **trên** mũi cọc (quy tắc đường tối thiểu)

### Sức kháng ma sát thành bên (Pt. 72)

$$R_s = K_{s,c} \left[ \sum_{i=1}^{N_1} f_{si} \cdot a_{si} \cdot h_i + \sum_{i=1}^{N_2} f_{si} \cdot a_{si} \cdot h_i \right] \quad \text{(N)}$$

- $K_{s,c}$: Hệ số chỉnh sửa — $K_c$ cho đất sét, $K_s$ cho cát — tra Hình 31
- Vùng $N_1$: từ mặt đất đến độ sâu $8D$; vùng $N_2$: từ $8D$ đến mũi cọc

**Hệ số sức kháng:** $\varphi_{sta} = 0.50$

---

## 18.7 Bảng 9 — Hệ số Sức kháng Cọc Đóng

### Phân tích tĩnh học (Bang 9, Dieu 5.5.2.3)

| Phương pháp | Đất | $\varphi_{sta}$ |
|------------|-----|----------------|
| α (Tomlinson 1987, Skempton 1951) | Sét và đất hỗn hợp | **0.35** |
| β (Esrig & Kirby 1979) | Sét và đất hỗn hợp | **0.25** |
| λ (Vijayvergiya & Focht 1972) | Sét và đất hỗn hợp | **0.40** |
| Nordlund/Thurman (Hannigan 2005) | Cát | **0.45** |
| SPT Meyerhof | Cát | **0.30** |
| CPT Schmertmann | Cát | **0.50** |
| Mũi cọc trên đá (Canada 1985) | Đá | **0.45** |

### Kiểm tra xác minh hiện trường — Hệ số $\varphi_{dyn}$

| Phương pháp kiểm tra | $\varphi_{dyn}$ |
|---------------------|----------------|
| Thử tải tĩnh + thử động (≥2 cọc, ≥2% tổng) | **0.80** |
| Thử tải tĩnh (≥1 cọc, không thử động) | **0.75** |
| Thử động 100% số cọc | **0.75** |
| Thử động tương hợp tín hiệu (≥2 cọc, ≥2%) | **0.65** |
| Phương trình sóng (có theo dõi búa tại hiện trường) | **0.50** |
| Công thức động FHWA Gate hiệu chỉnh (EOD) | **0.40** |
| Công thức ENR (New Engineering Record) — EOD | **0.10** |

---

## 18.8 Quy trình Thiết kế Tổng hợp

```
Bước 1: Xác định loại đất theo tuyến cọc (sét / cát / hỗn hợp)
Bước 2: Chọn phương pháp phân tích phù hợp theo dữ liệu thí nghiệm có
Bước 3: Chia địa tầng thành các lớp, tính qs cho từng lớp
Bước 4: Tính qp tại mũi cọc
Bước 5: Rs = SUM(qs_i * As_i);  Rp = qp * Ap;  Rn = Rs + Rp
Bước 6: Tra phi_stat theo Bảng 9
Bước 7: RR = phi_stat * Rn >= Pu (lực tính toán tác dụng lên cọc)
Bước 8: Xác nhận tại hiện trường → nâng phi lên phi_dyn (Bảng 9 phần trên)
```

---

## 18.9 Lưu ý Kỹ thuật Quan trọng

- **Đơn vị**: Tất cả công thức dùng MPa và mm. $q_s, q_p$ (MPa); $A_s, A_p$ (mm²); $R_n, R_R$ (N).
- **SPT hiệu chỉnh**: $N_{160}$ phải được hiệu chỉnh theo áp lực tầng phủ (Điều 4.6.2.4) — KHÔNG dùng N thô.
- **Db vs L**: $D_b$ = chiều sâu trong **tầng chịu lực**, không phải tổng L cọc. Cần xác định rõ top of bearing stratum.
- **Giới hạn SPT**: Không dùng công thức động khi $R_{ndr} > 2.5 \times 10^6$ N (Điều 7.3.8.5).
- **Nước ngầm**: Tính $\sigma'_v$ có xét mực nước ngầm (Điều 7.3.5).
- **Hóa mềm / nén chặt**: Đánh giá thay đổi sức kháng sau khi đóng cọc (Điều 7.3.4).
- **Xói**: Chiều sâu mũi cọc phải thỏa mãn sau xói thiết kế (Điều 7.3.6).

---

## 18.10 Giải thích Ký hiệu

| Ký hiệu | Ý nghĩa | Đơn vị |
|---------|---------|--------|
| $\varphi_{sta}$ | Hệ số sức kháng phân tích tĩnh (Bang 9) | — |
| $\varphi_{dyn}$ | Hệ số sức kháng xác minh hiện trường (Bang 9) | — |
| $q_s$ | Sức kháng ma sát đơn vị thành bên cọc | MPa |
| $q_p$ | Sức kháng chống mũi đơn vị | MPa |
| $R_n$ | Sức kháng danh định (nominal resistance) | N |
| $R_R$ | Sức kháng tính toán (factored resistance) | N |
| $S_u$ | Sức kháng cắt không thoát nước (undrained shear strength) | MPa |
| $\sigma'_v$ | Ứng suất có hiệu thẳng đứng | MPa |
| $\alpha$ | Hệ số kết dính (adhesion factor) — Tomlinson 1980 | — |
| $\beta$ | Hệ số ứng suất có hiệu — Esrig & Kirby 1979 | — |
| $\lambda$ | Hệ số thực nghiệm — Vijayvergiya & Focht 1972 | — |
| $N_{160}$ | Số búa SPT hiệu chỉnh (búa/300mm) | — |
| $D$ | Đường kính hoặc bề rộng cọc | mm |
| $D_b$ | Chiều sâu cọc ngàm trong tầng đất chịu lực | mm |
| $A_p$ | Diện tích mũi cọc | mm² |
| $A_s$ | Diện tích thành bên = chu vi × chiều dài đoạn | mm² |
| OCR | Tỷ số cố kết vượt trước (Overconsolidation Ratio) | — |
| EOD | End Of Driving — thời điểm kết thúc đóng cọc | — |
| BOR | Beginning Of Restrike — bắt đầu vỗ lại cọc | — |
| SPT | Standard Penetration Test — thí nghiệm xuyên tiêu chuẩn | — |
| CPT | Cone Penetration Test — thí nghiệm xuyên tĩnh | — |

---

## 18.11 Liên kết Tài liệu

| Vấn đề | Tài liệu |
|--------|---------|
| Địa tầng hố khoan TTHC | [data/TTHC.sqlite](data/TTHC.sqlite) — bảng `boreholes`, `layers`, `lab_tests`, `spt_tests` |
| Thiết kế kè SW TTHC | [16-ke-sw-202605-TTHC.md](16-ke-sw-202605-TTHC.md) |
| Catalog cọc SW BETON 6 | [11-sw-pile-database.md](11-sw-pile-database.md) |
| Mô hình đất Hardening Soil | [13-hardening-soil-model.md](13-hardening-soil-model.md) |
| Tham số PLAXIS Plate element | [10-plate-properties.md](10-plate-properties.md) |
| Dữ liệu JSON cọc đóng | [data/driven_pile_TCVN11823.json](data/driven_pile_TCVN11823.json) |
