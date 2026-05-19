# 42 — Tính toán Chi tiết NT1/NT2 Cọc ván SW Kè Công Viên (KE)

**Tiêu chuẩn áp dụng:** TCVN 11823-10:2017, Điều 7.3.8.6.2  
**Phương pháp:** Alpha (Tomlinson 1980) — sức kháng nhổ cọc bê tông trong đất dính  
**File engine:** [scripts/ke_sw_nt_calc.py](scripts/ke_sw_nt_calc.py)  
**Dữ liệu đầu ra:** [data/ke_sw_nt_results.json](data/ke_sw_nt_results.json)  
**SQLite:** bảng `ke_sw_nt_detail` + `ke_sw_nt2_layers`

---

## 1. Thông số Hình học Cố định

| Ký hiệu | Giá trị | Mô tả |
|---------|---------|-------|
| `top_ke` | $+2{,}70$ m | Cao độ đỉnh kè thiết kế |
| `tip_elev` | $-26{,}30$ m | Cao độ mũi cọc yêu cầu |
| `min_pen` | $1{,}00$ m | Xuyên qua lớp tốt tối thiểu (dưới lớp mềm cuối) |
| $\varphi_{stat}$ | $0{,}35$ | Hệ số kháng trở theo TCVN 11823-10 |
| $P$ | $2{,}856$ m | Chu vi tiết diện SW-840 (4 × 0,714 m) |
| $A_p$ | $0{,}3107$ m² | Diện tích mũi SW-840 (`Atd_cm2` = 3107 cm²) |

---

## 2. Nguyên tắc 1 (NT1) — Kiểm tra Chiều dài

### Công thức

$$L_{yc} = f_m + D_{bot,soft} + L_{pen,min}$$

Trong đó:
- $f_m = \max(0,\; top\_ke - Z_m)$ — chiều dài cọc trong đất đắp (m)
- $Z_m$ — cao độ mặt đất/cổ hố khoan (m)
- $D_{bot,soft}$ — chiều sâu từ cổ hố khoan đến **đáy lớp mềm cuối** ('1' hoặc 'XMD') (m)
- $L_{pen,min} = 1{,}00$ m — xuyên tối thiểu qua lớp tốt

### Điều kiện đạt

$$L_{TK} \geq L_{yc} \quad \Leftrightarrow \quad \text{Biên an toàn} = L_{TK} - L_{yc} \geq 0$$

**Lưu ý quan trọng:** $D_{bot,soft}$ là chiều sâu đến đáy lớp mềm — KHÔNG phải tổng chiều dày các lớp mềm.

---

## 3. Nguyên tắc 2 (NT2) — Sức kháng nhổ

### Công thức tổng quát (TCVN 11823-10:2017, Điều 7.3.8.6.2)

$$RR = \varphi_{stat} \times (R_s + R_p) \geq W_{cọc}$$

### Sức kháng thân cọc (Alpha method — Tomlinson 1980)

$$R_s = \sum_{i} \alpha_i \times s_{u,i} \times P \times L_i$$

Hàm số $\alpha$ theo $s_u$:

$$\alpha = \begin{cases}
1{,}00 & s_u \leq 25 \text{ kPa} \\
1{,}00 - \dfrac{s_u - 25}{45} \times 0{,}5 & 25 < s_u < 70 \text{ kPa} \\
0{,}50 & s_u \geq 70 \text{ kPa}
\end{cases}$$

### Sức kháng mũi cọc

$$R_p = 9 \times s_{u,\text{mũi}} \times A_p$$

### Trọng lượng cọc

$$W_{cọc} = \frac{TL \cdot 9{,}81}{L_{std}} \times L_{TK} \quad \text{(kN)}$$

Trong đó $TL$ (T) là khối lượng catalog cho chiều dài tiêu chuẩn $L_{std}$.

---

## 4. Thứ tự Ưu tiên Thông số $s_u$

| Ưu tiên | Nguồn | Bảng SQLite | Ghi chú |
|---------|-------|-------------|---------|
| 1 | VST (cắt cánh) | `vane_shear_tests` | Trung bình trong phạm vi lớp |
| 2 | Lab (Cu_UU / c) | `lab_tests` | Trung bình midpoint trong phạm vi lớp |
| 3 | Giả định theo ký hiệu | `SU_BY_SYMBOL` | **Cảnh báo cho kỹ sư** |

### Giá trị $s_u$ mặc định theo ký hiệu

| Ký hiệu lớp | $s_u$ (kPa) | Loại đất |
|-------------|------------|---------|
| `1` | 10 | Bùn sét yếu |
| `1b` | 20 | Sét yếu |
| `3` | 35 | Sét pha |
| `5` | 75 | Sét cứng |
| `5b` | 100 | Sét cứng đặc |
| `XMD` | 10 | Đất xử lý xi măng (đang thi công) |
| `F`, `2a`, `2b`, `2c`, `4`, `5a`, `6`, `7` | 0 | Cát/cuội/sỏi — $R_s = 0$ |

---

## 5. Kết quả Tính toán

### 5.1 Tóm tắt NT1

| Hố khoan | Z_m (m) | D_bot_soft (m) | L_yc (m) | L_TK (m) | Biên (m) | NT1 |
|----------|---------|----------------|---------|---------|---------|-----|
| KE-HK2 | +2,030 | 22,1 | 23,8 | 29,0 | +5,2 | Đạt |
| KE-HK3 | +1,256 | 20,2 | 22,6 | 29,0 | +6,4 | Đạt |
| KE-HK7 | −0,561 | 21,0 | 25,3 | 29,0 | +3,7 | Đạt |
| KE-HK8 | +2,579 | 27,0 | 28,1 | 29,0 | +0,9 | Đạt |
| KE-HK9 | −2,250 | 21,0 | 26,9 | 29,0 | +2,0 | Đạt |
| KE-HK10 | −0,381 | 25,0 | 29,1 | 29,0 | **−0,1** | **Không đạt** |
| KE-HK11 | −0,220 | 24,2 | 28,1 | 29,0 | +0,9 | Đạt |

**KE-HK10 KHÔNG ĐẠT NT1** với L_TK = 29,0 m — cần tăng chiều dài thiết kế lên tối thiểu 29,5 m (dùng cọc SW-940).

### 5.2 Tóm tắt NT2

| Hố khoan | $R_s$ (kN) | $R_p$ (kN) | $RR$ (kN) | $W$ (kN) | $RR/W$ | NT2 |
|----------|----------|----------|---------|--------|-------|-----|
| KE-HK2 | 1233 | 46 | 448 | 211 | 2,12 | Đạt |
| KE-HK3 | 1473 | 0 | 516 | 211 | 2,44 | Đạt |
| KE-HK7 | 1187 | 0 | 415 | 211 | 1,96 | Đạt |
| KE-HK8 | 1692 | 0 | 592 | 211 | 2,80 | Đạt |
| KE-HK9 | 1532 | 0 | 536 | 211 | 2,54 | Đạt |
| KE-HK10 | 1724 | 64 | 626 | 226 | 2,76 | Đạt |
| KE-HK11 | 1649 | 0 | 577 | 211 | 2,73 | Đạt |

**HK kiểm soát NT2:** KE-HK7 (tỷ số RR/W nhỏ nhất = 1,96)

---

## 6. Cảnh báo — Su Giả định (cần bổ sung thí nghiệm)

| Hố khoan | Lớp | Chiều sâu | Su giả định |
|----------|-----|-----------|------------|
| KE-HK8 | XMD | 6,7–22,4 m | 10 kPa (theo ký hiệu) |
| KE-HK8 | 1b | 27,0–28,8 m | 20 kPa (theo ký hiệu) |
| KE-HK9 | 1b | 21,0–23,5 m | 20 kPa (theo ký hiệu) |
| KE-HK10 | 1b | 25,0–27,0 m | 20 kPa (theo ký hiệu) |
| KE-HK11 | 1b | 24,2–25,2 m | 20 kPa (theo ký hiệu) |

Các lớp trên không có kết quả VST hoặc thí nghiệm lab trong SQLite. Cần bổ sung để xác nhận.

---

## 7. Kiến nghị Chiều dài Cọc

| Hố khoan | Cọc | L kiến nghị (m) | Lý do |
|----------|-----|----------------|-------|
| KE-HK2 đến HK3, HK7–HK9, HK11 | SW-840 | 29,0 | Đạt cả NT1 và NT2 |
| KE-HK10 | SW-940 | **29,5** | NT1 không đạt với 29,0 m (biên = −0,1 m) |

---

## 8. Tham chiếu

- Engine tính toán: [scripts/ke_sw_nt_calc.py](scripts/ke_sw_nt_calc.py)
- Kết quả JSON: [data/ke_sw_nt_results.json](data/ke_sw_nt_results.json)
- Dữ liệu SQLite: `ke_sw_nt_detail`, `ke_sw_nt2_layers` trong [data/TTHC.sqlite](data/TTHC.sqlite)
- Catalog cọc: [data/sw_pile_catalog.json](data/sw_pile_catalog.json)
- Dữ liệu thiết kế KE: [data/ke_sw_202605_TTHC.json](data/ke_sw_202605_TTHC.json)
- Hiển thị trong app: trang "Cọc ván SW (Kè)", Mục B, expander "Chi tiết tính toán NT1/NT2"
