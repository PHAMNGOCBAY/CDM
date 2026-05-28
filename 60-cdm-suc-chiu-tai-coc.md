# Sức chịu tải cọc xi măng đất (CDM) — 1 cọc đơn

Sức chịu tải cọc CDM được kiểm tra theo **hai điều kiện** và lấy giá trị nhỏ hơn:
sức chịu tải theo **nền đất** (AIT) và theo **vật liệu cọc**. Sức chịu tải đất nền
là **một trong các điều kiện để chọn chiều dài cọc**.

**Engine:** [scripts/cdm_column_calc.py](scripts/cdm_column_calc.py) —
`calc_bearing_soil_ait()` · `calc_bearing_material()` · `calc_cdm_pile_capacity()`
**UI:** tab "Thuyết minh TKCS" — mục "Sức chịu tải cọc xi măng đất (1 cọc đơn)"
**SQLite:** `tvtk_cdm_bearing` (per HK)

---

## 1. Theo nền đất — phương pháp Viện Kỹ thuật Châu Á (AIT)

Sức chịu tải theo nền = **ma sát thành** + **sức kháng mũi**:

$$Q_{ult.soil} = Q_{\text{ma sát}} + Q_{\text{mũi}}$$

**Ma sát thành** (hệ số bám dính $\alpha = 1$ cho đất yếu):

$$Q_{\text{ma sát}} = \pi d\, L_{col}\, C_{u.soil}$$

**Sức kháng mũi** ($N_c = 9$, $A_c$ = tiết diện cọc):

$$Q_{\text{mũi}} = 9\, C_{u.soil}\, A_c, \qquad A_c = \frac{\pi d^2}{4}$$

Cộng lại tương đương dạng gọn $Q_{ult.soil} = \left(\pi d\, L_{col} + 2{,}25\,\pi d^2\right) C_{u.soil}$
vì $9\,A_c = 9\cdot\dfrac{\pi d^2}{4} = 2{,}25\,\pi d^2$.

$C_{u.soil}$ lấy **giá trị sau khi đã nhân hệ số Bjerrum** (cường độ kháng cắt tính toán):

$$C_{u.soil} = \mu \cdot S_{u}^{VST} \qquad \text{(TCCS 41 Phụ lục C.3.2 — Công thức C.5)}$$

với $\mu$ tra theo chỉ số dẻo $I_p$ (Bảng C.1) — xem [35-tccs41-limits-transition](docs/claude/35-tccs41-limits-transition.md).

---

## 2. Theo vật liệu cọc

$$Q_{ult.mat} = q_u \cdot A_{col}, \qquad A_{col} = \frac{\pi d^2}{4}$$

- $q_u$ — cường độ nén nở hông thiết kế của cọc xi măng đất (kPa).

---

## 3. Sức chịu tải cho phép

$$Q_a = \frac{\min\!\left(Q_{ult.soil},\; Q_{ult.mat}\right)}{FS}, \qquad FS = 2{,}5$$

Thành phần nhỏ hơn là **thành phần khống chế** (nền đất hoặc vật liệu).

---

## 4. Lực nén lên một cọc — tập trung ứng suất

Trong nền hỗn hợp, cọc cứng **hút ứng suất** theo tỷ số mô đun (giả thiết biến dạng
bằng nhau giữa cọc và đất):

$$\sigma_{col} = \frac{E_c}{E_{tb}}\, q_{\text{tổng}}$$

$$P_{col} = \sigma_{col} \cdot A_c, \qquad A_c = \frac{\pi d^2}{4}$$

- $\sigma_{col}$ — ứng suất tại đầu cọc (kPa).
- $E_c$ — mô đun biến dạng cọc; $E_{tb} = a\,E_c + (1-a)\,E_s$ — mô đun tổ hợp;
  $a$ — tỷ lệ diện tích thay thế; $E_s = 250\,C_u$ (Cu sau Bjerrum).
- $q_{\text{tổng}}$ — tải phân bố (có thể cộng hoạt tải).

**Điều kiện kiểm tra:** $P_{col} \le Q_a$.

(Lưu ý: cách này chính xác hơn $P_{col} = q\cdot s^2$ vì đất giữa cọc cùng chịu một
phần tải; $\sum$ lực = $\sigma_{col}A_c + \sigma_{soil}(A_{cell}-A_c) = q\cdot A_{cell}$.)

---

## 5. Chiều dài cọc tối thiểu theo sức chịu tải

Vì $Q_{ult.soil}$ tăng tuyến tính theo $L_{col}$, đặt $Q_{ult.soil}(L) = P_{col}\cdot FS$
(khi vật liệu đủ: $Q_{ult.mat} \ge P_{col}\cdot FS$) → giải ra chiều dài tối thiểu:

$$L_{col}^{min} = \frac{\dfrac{P_{col}\cdot FS}{C_{u.soil}} - 2{,}25\,\pi d^2}{\pi d}$$

Nếu $Q_{ult.mat} < P_{col}\cdot FS$ → **vật liệu khống chế**, tăng chiều dài không đủ,
phải tăng $q_u$ cọc hoặc giảm khoảng cách $s$.

**Chiều dài cọc thiết kế** lấy theo:

$$L_{\text{thiết kế}} = \max\!\left(L_{\text{theo lún}},\; L_{col}^{min}(\text{SCT}),\; L_{\text{hình học}}\right)$$

- $L_{\text{theo lún}}$ — đảm bảo $S_1 + S_2 \le \Delta S$ (TCCS 41).
- $L_{col}^{min}(\text{SCT})$ — đảm bảo $P_{col} \le Q_a$.
- $L_{\text{hình học}}$ — xuyên hết lớp đất yếu + ngàm vào lớp tốt.

---

## 6. Ví dụ (KE-HK2)

$d = 0{,}80$ m · $L_{col} = 26{,}2$ m · $C_{u.soil} = 11{,}20$ kPa (sau Bjerrum) ·
$q_u = 800$ kPa · $s = 1{,}8$ m · $q = 40{,}8$ kPa · $FS = 2{,}5$

| Đại lượng | Giá trị |
| --- | --- |
| $A_c = \pi d^2/4$ | 0,5027 m² |
| $Q_{\text{ma sát}} = \pi d L_{col}\,C_u$ | $65{,}848 \times 11{,}20 = $ 737,5 kN |
| $Q_{\text{mũi}} = 9\,C_u\,A_c$ | $9 \times 11{,}20 \times 0{,}5027 = $ 50,7 kN |
| $Q_{ult.soil}$ | $737{,}5 + 50{,}7 = $ **788,2 kN** |
| $Q_{ult.mat} = 800\times 0{,}5027$ | **402,1 kN** (khống chế) |
| $Q_a = \min/2{,}5$ | **160,8 kN** |
| $E_c = 100\cdot q_u/2$ | 40 000 kPa |
| $E_s = 250\,C_u$ | 2 800 kPa |
| $a$ (lưới vuông) | 0,155 |
| $E_{tb} = a E_c + (1-a) E_s$ | 8 571 kPa |
| $\sigma_{col} = (E_c/E_{tb})\,q$ | $(40000/8571)\times 40{,}8 = $ 190,4 kPa |
| $P_{col} = \sigma_{col}\,A_c$ | $190{,}4 \times 0{,}5027 = $ **95,7 kN** |
| Kiểm tra $P_{col} \le Q_a$ | 95,7 ≤ 160,8 → **Đạt** |
| $L_{col}^{min}$ (SCT) | ≈ 6,7 m |

---

## 7. Bảng ký hiệu

| Ký hiệu | Đơn vị | Mô tả |
| --- | --- | --- |
| $d$ | m | Đường kính cọc CDM |
| $L_{col}$ | m | Chiều dài cọc CDM |
| $C_{u.soil}$ | kPa | Cường độ kháng cắt không thoát nước của nền (sau Bjerrum, $=\mu S_u$) |
| $q_u$ | kPa | Cường độ nén nở hông thiết kế của cọc |
| $A_{col}$ | m² | Diện tích tiết diện cọc |
| $N_c$ | — | Hệ số sức chịu tải mũi (= 9) |
| $FS$ | — | Hệ số an toàn (= 2,5) |
| $q$ | kPa | Tải phân bố nền đắp |
| $s$ | m | Khoảng cách cọc |
| $P_{col}$ | kN | Tải trọng tác dụng lên một cọc |
| $Q_a$ | kN | Sức chịu tải cho phép một cọc |
