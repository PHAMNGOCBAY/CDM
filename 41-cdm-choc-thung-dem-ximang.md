# Kiểm tra chọc thủng lớp đệm xi măng — Phương pháp ALiCC (PWRI Japan)

## 1. Tổng quan phương pháp

Phương pháp **ALiCC** (Advanced Load Interaction with Composite Columns, PWRI Japan) kiểm tra khả năng lớp đệm xi măng truyền tải trọng từ nền đắp xuống các trụ CDM mà không bị chọc thủng.

**Điều kiện đạt:**

$$\tau_{se} \leq \tau_{ase}$$

---

## 2. Thông số đầu vào

| Ký hiệu | Tên thông số | Đơn vị |
|---------|-------------|--------|
| D | Đường kính trụ CDM | m |
| e | Khoảng cách tâm – tâm trụ (lưới vuông) | m |
| H_se | Bề dày lớp đệm xi măng | m |
| H_e | Chiều cao đất đắp trên đệm xi măng | m |
| q_uckse | Cường độ nén nở hông của đệm xi măng | kPa |
| F_s | Hệ số an toàn cắt | — |
| θ | Góc phân tán áp lực qua đệm xi măng | ° |
| γ_fill | Dung trọng đất đắp | kN/m³ |
| γ_mat | Dung trọng đệm xi măng | kN/m³ |
| q_a | Áp lực nước hoặc phụ tải bổ sung (nếu có) | kPa |

---

## 3. Ứng suất cắt cho phép

Cường độ cắt không thoát nước của đệm xi măng lấy bằng một nửa cường độ nén nở hông:

$$\tau_{ase} = \frac{q_{uckse}}{2 \cdot F_s}$$

---

## 4. Chiều cao vùng vòm đất

Vùng đất phía trên khoảng trống giữa các trụ tạo ra hiệu ứng vòm. Chiều cao vùng vòm:

$$H_o = (e - D) \cdot \tan\!\left(\frac{\theta}{2}\right)$$

Dựa vào so sánh H_o với H_e, chọn công thức tính thể tích:

- **CT(1): H_o ≤ H_e** — vòm đất hoàn toàn hình thành trong phạm vi nền đắp
- **CT(2): H_o > H_e** — nền đắp không đủ cao để hình thành vòm đầy đủ

---

## 5. Thể tích đất tác dụng lên đơn nguyên

### Trường hợp CT(1) — H_o ≤ H_e

$$V_{soil} = \left[\frac{e - D}{2} \cdot e^2 - \frac{\pi(e^3 - D^3)}{24} + \frac{(4-\pi)(\sqrt{2}-1)\,e^3}{24}\right] \cdot \tan\theta$$

### Trường hợp CT(2) — H_o > H_e

$$r_0 = \frac{H_e}{\tan\theta} + \frac{D}{2}$$

$$V_{soil} = H_e \cdot e^2 - \frac{1}{3}\left[\pi r_0^2 \left(H_e + \frac{D}{2}\tan\theta\right) - \pi \frac{D}{2}\tan\theta\right]$$

---

## 6. Thể tích đệm xi măng tác dụng

Tương tự CT(2), lấy H_se thay cho H_e:

$$r_{mat} = \frac{H_{se}}{\tan\theta} + \frac{D}{2}$$

$$V_{CGCXM} = H_{se} \cdot e^2 - \frac{1}{3}\left[\pi r_{mat}^2 \left(H_{se} + \frac{D}{2}\tan\theta\right) - \pi \frac{D}{2}\tan\theta\right]$$

---

## 7. Áp lực lên vùng không gia cố

Diện tích đơn nguyên (phần đất giữa các trụ):

$$A_{unit} = e^2 - \frac{\pi D^2}{4}$$

Áp lực thẳng đứng trung bình lên A_unit, tính từ tổng trọng lượng đất đắp và đệm xi măng trong vùng tác dụng:

$$P_{Soil} = \frac{(V_{soil} - V_{CGCXM}) \cdot \gamma_{fill} + V_{CGCXM} \cdot \gamma_{mat}}{A_{unit}}$$

> Phần thể tích V_CGCXM (đệm xi măng) dùng γ_mat vì vật liệu nặng hơn đất đắp.

---

## 8. Ứng suất cắt thực tế tại mặt chọc thủng

Lực cắt thực tế truyền qua chu vi tiếp xúc trụ – đệm xi măng (π·D·H_se):

$$\tau_{se} = \frac{(P_{Soil} - q_a) \cdot A_{unit}}{\pi \cdot D \cdot H_{se}}$$

Ý nghĩa: tổng lực thẳng đứng lên vùng không gia cố được truyền vào trụ CDM qua chu vi cắt của đệm xi măng.

---

## 9. Tiêu chuẩn đánh giá

| Điều kiện | Kết quả |
|-----------|---------|
| τ_se ≤ τ_ase | **Đạt** — đệm xi măng không bị chọc thủng |
| τ_se > τ_ase | **Không đạt** — cần tăng H_se hoặc tăng q_uckse |

**Biện pháp khắc phục khi không đạt:**

1. Tăng bề dày đệm xi măng H_se
2. Tăng hàm lượng xi măng để tăng q_uckse
3. Giảm khoảng cách trụ e (tăng mật độ CDM)
4. Giảm chiều cao nền đắp H_e (giảm tải)

---

## 10. Ghi chú về đơn vị và góc θ

- Tất cả chiều dài tính bằng **m**, áp lực/ứng suất bằng **kPa (kN/m²)**
- Góc θ nhập theo **độ (°)**, chương trình tự chuyển sang radian khi tính tan
- Giá trị θ điển hình: **60° – 80°** (thường dùng θ = 80° cho đệm xi măng chất lượng cao)
- F_s thường lấy **2,0 – 3,0**; mặc định F_s = 2,0 theo khuyến nghị ALiCC PWRI
