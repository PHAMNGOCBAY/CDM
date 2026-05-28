# Lý Thuyết Tính Toán Cọc Đất Xi Măng (CDM)

## Căn cứ: TCVN 9403:2012 – Gia cố nền đất yếu – Phương pháp trụ đất xi măng

---

## 1. Thông Số Vật Liệu

### 1.1 Cường độ kháng cắt thiết kế

Cường độ nén nở hông của trụ CDM tại hiện trường lấy bằng:

$$q_{u,tk} = \frac{q_{u,TN}}{FS}$$

Trong đó:
- $q_{u,TN}$: cường độ nén nở hông xác định từ thí nghiệm phòng (kPa)
- $FS$: hệ số quy đổi phòng → hiện trường (thường $FS = 2{,}0$)
- $q_{u,tk}$: cường độ nén nở hông thiết kế tại hiện trường (kPa)

Cường độ kháng cắt thiết kế:

$$C_c = \frac{q_{u,tk}}{2} \quad (\text{kN/m}^2)$$

### 1.2 Mô đun đàn hồi trụ CDM

Theo TCVN 9403:2012 (Mục 3.3 và Phụ lục C):

$$E_c = 100 \times C_c \quad (\text{kN/m}^2)$$

### 1.3 Mô đun biến dạng đất nền

Mô đun biến dạng đất nền yếu tính theo sức kháng cắt không thoát nước:

$$E_s = 250 \times C_u \quad (\text{kN/m}^2)$$

Trong đó $C_u$ (hoặc $S_u$) là sức kháng cắt không thoát nước trung bình của lớp đất yếu, xác định từ thí nghiệm cắt cánh hiện trường (VST) hoặc thí nghiệm UU trong phòng (kN/m²).

---

## 2. Tỷ Lệ Diện Tích Thay Thế

Tỷ lệ diện tích thay thế $a$ là tỷ số diện tích mặt cắt ngang trụ CDM trên diện tích ô lưới bố trí.

### 2.1 Bố trí lưới tam giác (khuyến dùng)

$$a = \frac{\pi D^2}{2\sqrt{3}\, e^2}$$

### 2.2 Bố trí lưới vuông

$$a = \frac{\pi D^2}{4\, e^2}$$

Trong đó:
- $D$: đường kính trụ CDM (m)
- $e$: khoảng cách tâm – tâm giữa các trụ (m)
- $a$: tỷ lệ thay thế (không thứ nguyên; thường $0{,}15 \div 0{,}35$)

---

## 3. Mô Đun Tương Đương Của Nền Gia Cố

Mô đun tương đương của khối nền được gia cố CDM (Phụ lục C – TCVN 9403:2012):

$$E_{tb} = a \cdot E_c + (1 - a) \cdot E_s \quad (\text{kN/m}^2)$$

$E_{tb}$ phụ thuộc đồng thời vào chất lượng xi măng đất ($E_c$) và tính chất đất nền ($E_s$). Khoảng cách trụ nhỏ hơn → $a$ lớn hơn → $E_{tb}$ lớn hơn → độ lún nhỏ hơn.

---

## 4. Tính Toán Độ Lún (Phụ Lục C – TCVN 9403:2012)

### 4.1 Tổng độ lún nền gia cố

$$S = S_1 + S_2 \qquad \text{(C.1)}$$

### 4.2 Độ lún bản thân khối CDM ($S_1$)

$$S_1 = \frac{q \times H}{E_{tb}} \times 100 \quad (\text{cm}) \qquad \text{(C.2)}$$

Trong đó:
- $q$: tổng tải trọng tác dụng lên mặt nền (kN/m²)
- $H = L_c$: chiều dài (chiều sâu) trụ CDM (m)
- $E_{tb}$: mô đun tương đương (kN/m²)

### 4.3 Độ lún dưới mũi trụ ($S_2$)

Khi trụ CDM xuyên qua toàn bộ lớp đất yếu và cắm vào lớp đất tốt hơn, $S_2$ lấy bằng 0:

$$S = S_1 \quad (\text{cm})$$

### 4.4 Tải trọng thiết kế

Tổng tải trọng gây lún bao gồm:

$$q = q_{gt} + h_{md} \cdot \gamma_{md} + h_{đắp} \cdot \gamma_{đắp} + h_{đệm} \cdot \gamma_{đệm} \quad (\text{kN/m}^2)$$

Trong đó $q_{gt}$ là hoạt tải giao thông, $h$ là chiều dày từng lớp, $\gamma$ là dung trọng tương ứng.

---

## 5. Kiểm Tra Sức Chịu Tải Trụ CDM

### 5.1 Phương pháp AIT (Phụ lục B – TCVN 9403:2012)

Sức chịu tải giới hạn của một trụ CDM:

$$Q_{ult} = Q_{mũi} + Q_{thân} \quad (\text{kN})$$

**Sức chịu tải mũi trụ:**

$$Q_{mũi} = 9 \times C_u \times A_c \quad (\text{kN})$$

**Sức chịu tải do ma sát thân trụ:**

$$Q_{thân} = \pi \times D \times L_c \times C_u \quad (\text{kN})$$

Trong đó $A_c = \dfrac{\pi D^2}{4}$ là diện tích mặt cắt ngang trụ (m²); hệ số $N_c = 9$ cho đất sét điều kiện không thoát nước. **$C_u$ lấy giá trị SAU hiệu chỉnh Bjerrum** ($C_u = \mu\cdot S_u$, TCCS 41 Phụ lục C.5) — dùng chung cho cả mũi và ma sát thân, KHÔNG dùng cường độ cọc $C_c$ cho sức kháng mũi.

**Sức chịu tải cho phép ($FS = 2{,}5$):**

$$Q_a = \frac{\min(Q_{ult.\text{nền}},\ Q_{ult.\text{vật liệu}})}{FS} \quad (\text{kN})$$

với $Q_{ult.\text{vật liệu}} = q_u \cdot A_c$ (khống chế theo vật liệu cọc). Chi tiết: [60-cdm-suc-chiu-tai-coc.md](60-cdm-suc-chiu-tai-coc.md).

### 5.2 Ứng suất tập trung lên đầu trụ

Khi nền hỗn hợp (trụ CDM + đất) chịu tải trọng phân bố đều $q$, ứng suất phân bổ lên đầu trụ CDM:

$$\sigma_{col} = \frac{E_c}{E_{tb}} \times q \quad (\text{kN/m}^2)$$

**Lực nén lên một trụ CDM:**

$$P_{col} = \sigma_{col} \times A_c \quad (\text{kN})$$

**Điều kiện đạt sức chịu tải:**

$$P_{col} < Q_a \quad \Rightarrow \quad \text{Đạt}$$

---

## 6. Kiểm Tra Chọc Thủng Lớp Đệm Xi Măng

> Căn cứ: Technical Manual of ALiCC Method for Soft Soil Improvement – PWRI Japan

### 6.1 Ứng suất cắt cho phép

$$\tau_{ase} = \frac{q_{uckse}}{2 \cdot F_s} \quad (\text{kPa})$$

### 6.2 Chiều cao vùng vòm đất

$$H_o = (e - D) \cdot \tan\!\left(\frac{\theta}{2}\right) \quad (\text{m})$$

**Trường hợp CT(1) — $H_o \leq H_e$:**

$$V_{soil} = \left[\frac{(e-D) \cdot e^2}{2} - \frac{\pi(e^3-D^3)}{24} + \frac{(4-\pi)(\sqrt{2}-1)\,e^3}{24}\right] \cdot \tan\theta \quad (\text{m}^3)$$

**Trường hợp CT(2) — $H_o > H_e$:**

$$V_{soil} = H_e \cdot e^2 - \frac{1}{3}\left[\pi r_0^2\!\left(H_e + \frac{D}{2}\tan\theta\right) - \pi\frac{D}{2}\tan\theta\right] \quad (\text{m}^3)$$

với $r_0 = \dfrac{H_e}{\tan\theta} + \dfrac{D}{2}$.

### 6.3 Thể tích đệm xi măng tác dụng

$$V_{CGCXM} = H_{se} \cdot e^2 - \frac{1}{3}\left[\pi r_{mat}^2\!\left(H_{se} + \frac{D}{2}\tan\theta\right) - \pi\frac{D}{2}\tan\theta\right] \quad (\text{m}^3)$$

với $r_{mat} = \dfrac{H_{se}}{\tan\theta} + \dfrac{D}{2}$.

### 6.4 Áp lực và ứng suất cắt thực tế

$$A_{unit} = e^2 - \frac{\pi D^2}{4}$$

$$P_{Soil} = \frac{(V_{soil} - V_{CGCXM}) \cdot \gamma_{fill} + V_{CGCXM} \cdot \gamma_{mat}}{A_{unit}} \quad (\text{kPa})$$

$$\tau_{se} = \frac{(P_{Soil} - q_a) \cdot A_{unit}}{\pi \cdot D \cdot H_{se}} \quad (\text{kPa})$$

**Điều kiện đạt:**

$$\tau_{se} \leq \tau_{ase} \quad \Rightarrow \quad \text{Đạt (không xảy ra chọc thủng)}$$

---

## 7. Ký Hiệu Tổng Hợp

### 7.1 Ký hiệu tính toán CDM (TCVN 9403:2012)

| Ký hiệu | Đơn vị | Mô tả |
|---------|--------|-------|
| $D$ | m | Đường kính trụ CDM |
| $e$ | m | Khoảng cách tâm – tâm |
| $L_c$ | m | Chiều dài trụ CDM |
| $q_{u,tk}$ | kPa | Cường độ nén nở hông thiết kế hiện trường |
| $C_c = q_{u,tk}/2$ | kN/m² | Cường độ kháng cắt thiết kế trụ CDM |
| $E_c = 100 C_c$ | kN/m² | Mô đun đàn hồi trụ CDM |
| $C_u \ (S_u)$ | kN/m² | Sức kháng cắt không thoát nước đất nền |
| $E_s = 250 C_u$ | kN/m² | Mô đun biến dạng đất nền yếu |
| $a$ | – | Tỷ lệ diện tích thay thế |
| $E_{tb} = aE_c+(1{-}a)E_s$ | kN/m² | Mô đun tương đương nền gia cố |
| $q$ | kN/m² | Tổng tải trọng tác dụng |
| $S_1 = qL_c/E_{tb} \times 100$ | cm | Độ lún bản thân khối CDM |
| $S_2$ | cm | Độ lún dưới mũi trụ ($= 0$ khi trụ xuyên lớp bùn) |
| $Q_{ult}$ | kN | Sức chịu tải giới hạn một trụ CDM (= mũi + thân) |
| $Q_a = \min(Q_{ult.nền}, Q_{ult.vl})/2{,}5$ | kN | Sức chịu tải cho phép ($FS = 2{,}5$) |
| $P_{col} = \sigma_{col} \cdot A_c$ | kN | Lực nén tác dụng lên một trụ CDM |

### 7.2 Ký hiệu kiểm tra chọc thủng (ALiCC – PWRI Japan)

| Ký hiệu | Đơn vị | Mô tả |
|---------|--------|-------|
| $H_{se}$ | m | Bề dày lớp đệm xi măng |
| $H_e$ | m | Chiều cao lớp đắp phía trên đệm |
| $q_{uckse}$ | kPa | Cường độ kháng nén nở hông đệm xi măng |
| $F_s$ | – | Hệ số an toàn ứng suất cắt (thường $= 3$) |
| $\theta$ | ° | Góc vòm đất – Plastic arch angle (thường $= 80°$) |
| $q_a$ | kPa | Sức chịu tải đất nền vùng không gia cố |
| $\tau_{ase}$ | kPa | Ứng suất cắt cho phép của đệm xi măng |
| $H_o$ | m | Chiều cao vùng vòm đất |
| $V_{soil}$ | m³ | Thể tích đất đắp tác dụng lên ô lưới |
| $V_{CGCXM}$ | m³ | Thể tích đệm xi măng phân bổ vào vùng không gia cố |
| $P_{Soil}$ | kPa | Áp lực thẳng đứng lên phần không gia cố |
| $\tau_{se}$ | kPa | Ứng suất cắt thực tế tại mặt tiếp xúc đệm – trụ |

---

## 8. Tiêu Chuẩn và Tài Liệu Tham Khảo

1. **TCVN 9403:2012** – Gia cố nền đất yếu – Phương pháp trụ đất xi măng. Bộ Xây dựng, 2012.
2. **TCVN 4200:2012** – Đất xây dựng – Phương pháp xác định tính nén lún trong phòng thí nghiệm.
3. **TCVN 8868:2011** – Thí nghiệm xác định sức kháng cắt không cố kết – không thoát nước của đất dính.
4. **Asian Institute of Technology (AIT)** – Design and Construction of Ground Improvement Works, 2002.
5. **Terashi, M.** – The state of practice in deep mixing methods. Proc. 3rd Int. Conf. Grouting & Ground Treatment, 2003.
6. **Public Works Research Institute (PWRI), Japan** – Technical Manual of ALiCC Method for Soft Soil Improvement.
