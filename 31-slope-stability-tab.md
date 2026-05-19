# 31 — Ổn Định Mái Dốc (Slope Stability Tab)

**Thư viện:** `geotech-staff-engineer` — module `slope_stability`  
**Tham chiếu:** Bishop (1955) · Spencer (1967) · Duncan et al. (2014)

> **AI workflow:** `data/slope_stability_tab.json` → `scripts/tab_slope_stability.py`

---

## 1. Phương pháp giới hạn cân bằng

### 1.1 Ordinary Method of Slices — Fellenius (1927)

$$F_s = \frac{\sum [c' \Delta l + (W\cos\alpha - u\Delta l)\tan\varphi']}{\sum W\sin\alpha}$$

- Bỏ qua lực giữa phiên → bảo lưu 5–20%
- Dùng để so sánh nhanh

### 1.2 Bishop Simplified (1955)

$$F_s = \frac{\sum \frac{c' b + (W - ub)\tan\varphi'}{m_\alpha}}{\sum W\sin\alpha}$$

với $m_\alpha = \cos\alpha + \frac{\sin\alpha \tan\varphi'}{F_s}$

- Lực giữa phiên nằm ngang (iE = 0)
- Sai số < 5% so với Spencer — **phổ biến nhất trong thực tế**
- Phương trình ngầm → giải lặp (hội tụ nhanh)

### 1.3 Spencer (1967)

- Thỏa mãn đồng thời cân bằng lực và moment
- Lực giữa phiên có góc nghiêng θ = const (tìm bằng lặp)
- Chính xác hơn Bishop, tiếp cận kết quả PLAXIS φ/c reduction

### 1.4 Morgenstern-Price

- Mở rộng Spencer với hàm lực giữa phiên f(x) tùy chỉnh
- Chính xác nhất trong các phương pháp giải tích

---

## 2. Hệ số an toàn yêu cầu

| Loại công trình | FoS tối thiểu | Tiêu chuẩn |
|-----------------|--------------|------------|
| Mái dốc thường xuyên | 1.50 | TCVN 9385:2012, EC7 |
| Đào tạm thời | 1.30 | Khi thi công ngắn hạn |
| Kết hợp động đất | 1.10 | Pseudo-static analysis |
| Mái dốc quan trọng | 1.50–2.00 | Theo mức độ rủi ro |

---

## 3. Tìm kiếm mặt trượt tới hạn

### 3.1 Grid Search (mặc định)

- Quét tâm vòng tròn trên lưới n×n điểm
- Tại mỗi tâm: tối ưu bán kính → FoS nhỏ nhất
- Đủ tốt cho hầu hết trường hợp thực tế

### 3.2 PSO (Particle Swarm Optimization)

- Tìm kiếm toàn cục trong không gian 3D (xc, yc, R)
- Chính xác hơn Grid Search, chậm hơn
- Dùng khi có lớp đất yếu hoặc hình học phức tạp

### 3.3 Manual (người dùng nhập xc, yc, R)

- Dùng khi biết trước vị trí mặt trượt khả năng (khảo sát)
- Cho phép so sánh nhiều phương pháp tại cùng mặt trượt

---

## 4. Xây dựng hình học mái dốc

```
         ← crest_width →
                          ___________
                         /           |
        slope_height    /            |
                       / slope_angle |
___toe_offset_________/              |
```

Trong tab: nhập `H`, `α`, `crest_width` → tự động tính `surface_points`:

```python
horiz = H / tan(alpha_deg)
surface_pts = [(0,0), (toe_offset,0),
               (toe_offset+horiz, H),
               (toe_offset+horiz+crest_width, H)]
```

---

## 5. Chế độ phân tích đất

| Điều kiện | Mode | Tham số dùng |
|-----------|------|-------------|
| Đất có thoát nước (cát, sỏi) | `drained` | φ', c' |
| Đất sét không thoát nước | `undrained` | cu (Su) |
| Đất sét thoát nước dài hạn | `drained` | φ', c_residual |

---

## 6. Biện pháp cải thiện FoS

| Biện pháp | Tăng FoS | Chi phí |
|-----------|----------|---------|
| Giảm góc mái (flatten) | Cao | Thấp |
| Thêm berme (bậc thang) | Trung bình | Thấp |
| Thoát nước bề mặt | Trung bình | Thấp |
| Neo đất (soil nails) | Cao | Trung bình |
| Cọc chống | Cao | Cao |
| Đắp gia tải chân mái | Trung bình | Thấp |

---

## 7. Sử dụng trong tab

```python
from tab_slope_stability import run_slope_stability, plot_slope

r = run_slope_stability(
    slope_height=8.0,
    slope_angle_deg=30.0,
    crest_width=10.0,
    layers_app=_get_front_layers(),
    method="bishop",
    search=True,
    n_circles=50,
)
# r["FOS"], r["xc"], r["yc"], r["R"], r["fos_check"]

fig = plot_slope(r)
```

---

## 8. Liên kết

| File | Vai trò |
|------|---------|
| `data/slope_stability_tab.json` | Thông số mặc định, yêu cầu FoS |
| `scripts/tab_slope_stability.py` | Engine tính + biểu đồ mặt cắt |
| `28-geotech-staff-engineer.md` | Tổng quan thư viện |
