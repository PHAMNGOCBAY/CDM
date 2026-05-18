# Lý Thuyết Tính Toán Cọc Đất Xi Măng (CDM)
## Căn cứ: TCVN 9403:2012 – Gia cố nền đất yếu – Phương pháp trụ đất xi măng

---

## 1. Thông Số Vật Liệu

### 1.1 Cường độ kháng cắt thiết kế

Cường độ nén nở hông của trụ CDM tại hiện trường lấy bằng:

```
qu,tk = qu,TN / FS
```

Trong đó:
- `qu,TN` : cường độ nén nở hông xác định từ thí nghiệm phòng (kPa)
- `FS`    : hệ số quy đổi phòng → hiện trường (thường FS = 2,0)
- `qu,tk` : cường độ nén nở hông thiết kế tại hiện trường (kPa)

Cường độ kháng cắt thiết kế:

```
Cc = qu,tk / 2    (kN/m²)
```

### 1.2 Mô đun đàn hồi trụ CDM

Theo TCVN 9403:2012 (Mục 3.3 và Phụ lục C):

```
Ec = 100 × Cc    (kN/m²)
```

### 1.3 Mô đun biến dạng đất nền

Mô đun biến dạng đất nền yếu tính theo sức kháng cắt không thoát nước:

```
Es = 250 × Cu    (kN/m²)
```

Trong đó `Cu` (hoặc `Su`) là sức kháng cắt không thoát nước trung bình của lớp đất yếu, xác định từ thí nghiệm cắt cánh hiện trường (VST) hoặc thí nghiệm UU trong phòng (kN/m²).

---

## 2. Tỷ Lệ Diện Tích Thay Thế

Tỷ lệ diện tích thay thế `a` là tỷ số diện tích mặt cắt ngang trụ CDM trên diện tích ô lưới bố trí.

### 2.1 Bố trí lưới tam giác (khuyến dùng)

```
         π × D²
a = ─────────────────
      2√3 × e²
```

### 2.2 Bố trí lưới vuông

```
       π × D²
a = ───────────
      4 × e²
```

Trong đó:
- `D` : đường kính trụ CDM (m)
- `e` : khoảng cách tâm-tâm giữa các trụ (m)
- `a` : tỷ lệ thay thế (không thứ nguyên; thường 0,15 ÷ 0,35)

---

## 3. Mô Đun Tương Đương Của Nền Gia Cố

Mô đun tương đương của khối nền được gia cố CDM (Phụ lục C – TCVN 9403:2012):

```
Etb = a × Ec + (1 − a) × Es    (kN/m²)
```

`Etb` phụ thuộc đồng thời vào chất lượng xi măng đất (Ec) và tính chất đất nền (Es). Khoảng cách trụ nhỏ hơn → `a` lớn hơn → `Etb` lớn hơn → độ lún nhỏ hơn.

---

## 4. Tính Toán Độ Lún (Phụ Lục C – TCVN 9403:2012)

### 4.1 Tổng độ lún nền gia cố

```
S = S₁ + S₂    (C.1)
```

### 4.2 Độ lún bản thân khối CDM (S₁)

```
S₁ = q × H / Etb × 100    (cm)    (C.2)
```

Trong đó:
- `q`  : tổng tải trọng tác dụng lên mặt nền (kN/m²)
- `H`  = `Lc` : chiều dài (chiều sâu) trụ CDM (m)
- `Etb`: mô đun tương đương (kN/m²)

### 4.3 Độ lún dưới mũi trụ (S₂)

`S₂` là độ lún của lớp đất bên dưới mũi trụ CDM.

Khi trụ CDM xuyên qua toàn bộ lớp đất yếu và cắm vào lớp đất tốt hơn, `S₂` có thể lấy bằng 0. Trong trường hợp này:

```
S = S₁    (cm)
```

### 4.4 Tải trọng thiết kế

Tổng tải trọng gây lún bao gồm:

```
q = q_giao_thông + h_mặt_đường × γ_mặt_đường
                 + h_đắp × γ_đắp
                 + h_đệm × γ_đệm    (kN/m²)
```

---

## 5. Kiểm Tra Sức Chịu Tải Trụ CDM

### 5.1 Phương pháp AIT (Phụ lục B – TCVN 9403:2012)

Sức chịu tải giới hạn của một trụ CDM:

```
Qult = Qmũi + Qthân    (kN)
```

**Sức chịu tải mũi trụ:**

```
Qmũi = 9 × Cc × Ac    (kN)
```

**Sức chịu tải do ma sát thân trụ:**

```
Qthân = π × D × Lc × Cu    (kN)
```

Trong đó:
- `Ac = π × D² / 4` : diện tích mặt cắt ngang trụ (m²)
- `9`  : hệ số sức chịu tải tại mũi (đất sét, điều kiện không thoát nước)
- `Cu` : sức kháng cắt không thoát nước trung bình dọc thân trụ (kN/m²)

**Sức chịu tải cho phép (FS = 2):**

```
Qa = Qult / FS    (kN)
```

### 5.2 Ứng suất tập trung lên đầu trụ

Khi nền hỗn hợp (trụ CDM + đất) chịu tải trọng phân bố đều `q`, ứng suất phân bổ lên đầu trụ CDM:

```
σ_col = (Ec / Etb) × q    (kN/m²)
```

**Lực nén lên một trụ CDM:**

```
Pcol = σ_col × Ac    (kN)
```

**Điều kiện đạt sức chịu tải:**

```
Pcol < Qa    →  Đạt
```

---

## 6. Kiểm Tra Chọc Thủng Lớp Đệm Xi Măng

> Căn cứ: Technical Manual of ALiCC Method for Soft Soil Improvement – Public Works Research Institute (Japan)

### 6.1 Thông số lớp đệm xi măng

| Ký hiệu | Mô tả | Giá trị điển hình |
|---------|-------|-----------------|
| `Hse` | Bề dày lớp đệm xi măng | 0,40 m |
| `He` | Chiều cao cát đắp trên đệm (= h_fill) | m |
| `quckse` | Cường độ kháng nén đệm xi măng | 600 kPa |
| `Fs` | Hệ số an toàn ứng suất cắt | 3 |
| `θ` | Góc đàn hồi dẻo – Plastic arch angle | 80° |
| `qa` | SCT đất nền vùng không gia cố | 0 kPa |

### 6.2 Ứng suất cắt cho phép

```
τase = quckse / (2 × Fs)    (kPa)
```

### 6.3 Chiều cao vùng vòm đất – kiểm tra điều kiện

```
Ho = (e − D) × tan(θ/2)    (m)
```

**Nếu Ho ≤ He → dùng Công thức (1):**

```
Vsoil = [(e−D)·e²/2 − π(e³−D³)/24 + (4−π)(√2−1)e³/24] × tan(θ)    (m³)
```

**Nếu Ho > He → dùng Công thức (2):**

```
Vsoil = He·e² − (1/3)·[π·(He/tan θ + D/2)²·(He + D/2·tan θ) − π·D/2·tan θ]    (m³)
```

### 6.4 Thể tích đệm xi măng tác dụng lên vùng không gia cố

```
VCGCXM = Hse·e² − (1/3)·[π·(Hse/tan θ + D/2)²·(Hse + D/2·tan θ) − π·D/2·tan θ]    (m³)
```

### 6.5 Áp lực thẳng đứng lên phần không gia cố

```
PSoil = [(Vsoil − VCGCXM)·γ_đắp + VCGCXM·γ_đệm] / (e² − π·D²/4)    (kPa)
```

### 6.6 Ứng suất cắt thực tế và điều kiện chọc thủng

```
τse = (PSoil − qa) × (e² − π·D²/4) / (π × D × Hse)    (kPa)
```

**Điều kiện đạt:**

```
τse ≤ τase    →  Đạt (không xảy ra chọc thủng)
```

---

## 7. Ký Hiệu Tổng Hợp

### 7.1 Ký hiệu tính toán CDM (TCVN 9403:2012)

| Ký hiệu | Đơn vị | Mô tả |
|---------|--------|-------|
| D | m | Đường kính trụ CDM |
| e | m | Khoảng cách tâm-tâm |
| Lc | m | Chiều dài trụ CDM |
| qu,tk | kPa | Cường độ nén nở hông thiết kế hiện trường |
| Cc = qu,tk/2 | kN/m² | Cường độ kháng cắt thiết kế trụ CDM |
| Ec = 100·Cc | kN/m² | Mô đun đàn hồi trụ CDM |
| Cu (Su) | kN/m² | Sức kháng cắt không thoát nước đất nền |
| Es = 250·Cu | kN/m² | Mô đun biến dạng đất nền yếu |
| a | – | Tỷ lệ diện tích thay thế |
| Etb = a·Ec+(1-a)·Es | kN/m² | Mô đun tương đương nền gia cố |
| q | kN/m² | Tổng tải trọng tác dụng |
| S₁ = q·Lc/Etb | cm | Độ lún bản thân khối CDM |
| S₂ | cm | Độ lún dưới mũi trụ (= 0 khi trụ xuyên lớp bùn) |
| Qult | kN | Sức chịu tải giới hạn một trụ CDM |
| Qa = Qult/2 | kN | Sức chịu tải cho phép (FS = 2) |
| Pcol = σ_col·Ac | kN | Lực nén tác dụng lên một trụ CDM |

### 7.2 Ký hiệu kiểm tra chọc thủng (ALiCC – PWRI Japan)

| Ký hiệu | Đơn vị | Mô tả |
| ------- | ------ | ----- |
| Hse | m | Bề dày lớp đệm xi măng |
| He | m | Chiều cao lớp đắp phía trên đệm (= h_fill) |
| quckse | kPa | Cường độ kháng nén nở hông của đệm xi măng |
| Fs | – | Hệ số an toàn ứng suất cắt (thường = 3) |
| θ | ° | Góc vòm đất – Plastic arch angle (thường = 80°) |
| qa | kPa | Sức chịu tải đất nền vùng không gia cố (thường = 0) |
| τase = quckse/(2·Fs) | kPa | Ứng suất cắt cho phép của đệm xi măng |
| Ho = (e−D)·tan(θ/2) | m | Chiều cao vùng vòm đất |
| Vsoil | m³ | Thể tích đất đắp tác dụng lên ô lưới (CT1 hoặc CT2) |
| VCGCXM | m³ | Thể tích đệm xi măng phân bổ vào vùng không gia cố |
| PSoil | kPa | Áp lực thẳng đứng lên phần không gia cố |
| τse | kPa | Ứng suất cắt thực tế tại mặt tiếp xúc đệm – trụ |

---

## 8. Tiêu Chuẩn và Tài Liệu Tham Khảo

1. **TCVN 9403:2012** – Gia cố nền đất yếu – Phương pháp trụ đất xi măng. Bộ Xây dựng, 2012.
2. **TCVN 4200:2012** – Đất xây dựng – Phương pháp xác định tính nén lún trong phòng thí nghiệm.
3. **TCVN 8868:2011** – Thí nghiệm xác định sức kháng cắt không cố kết – không thoát nước của đất dính.
4. **Asian Institute of Technology (AIT)** – Design and Construction of Ground Improvement Works, 2002. (Cơ sở phương pháp tính sức chịu tải Phụ lục B – TCVN 9403:2012.)
5. **Terashi, M.** – The state of practice in deep mixing methods. Proc. 3rd Int. Conf. Grouting & Ground Treatment, 2003.
6. **Public Works Research Institute (PWRI), Japan** – Technical Manual of ALiCC Method for Soft Soil Improvement. (Cơ sở kiểm tra chọc thủng lớp đệm xi măng – Mục 6.)
