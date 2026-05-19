# 31 — Ổn định mái dốc — Giới hạn cân bằng (slope_stability)

**Thư viện:** `slope_stability` (geotech-staff-engineer 4.6.0)  
**Tài liệu gốc:** Duncan & Wright (2005); Bishop (1955); Spencer (1967)  
**Phạm vi:** Phân tích ổn định mái dốc đất, tìm mặt trượt nguy hiểm nhất

---

## 1. Phương pháp phân lát (Method of Slices)

Chia khối đất trượt thành **n lát cắt** thẳng đứng, mỗi lát có:
- Trọng lượng $W_i$
- Lực trên mặt trượt: $N_i$ (pháp tuyến), $T_i$ (tiếp tuyến)
- Lực liên lát: $E_i$, $X_i$

---

## 2. Fellenius — Ordinary Method of Slices (1927)

**Giả định:** Bỏ qua lực liên lát (E và X = 0)

$$FS = \frac{\sum [c' l_i + (W_i \cos\alpha_i - u_i l_i) \tan\phi']}{\sum W_i \sin\alpha_i}$$

**Ưu điểm:** Đơn giản, không lặp  
**Nhược điểm:** Kém chính xác khi mặt trượt sâu hoặc áp lực nước lớn (-15% so với Bishop)

---

## 3. Bishop Simplified (1955)

**Giả định:** Lực liên lát ngang = 0 (Xi = 0), có lực ngang Ei

$$FS = \frac{\sum \frac{1}{m_{\alpha i}} [c' b_i + (W_i - u_i b_i) \tan\phi']}{\sum W_i \sin\alpha_i}$$

$$m_{\alpha i} = \cos\alpha_i + \frac{\sin\alpha_i \tan\phi'}{FS}$$

**Lặp hội tụ**: Bắt đầu FS=1, cập nhật mαi đến khi hội tụ.  
**Khuyến nghị:** Phương pháp tiêu chuẩn cho mặt trượt tròn.

---

## 4. Spencer (1967)

**Giả định:** Lực liên lát nghiêng góc θ không đổi

Thỏa mãn **cân bằng lực** và **cân bằng moment** đồng thời → chính xác hơn Bishop.

$$FS_{force} = FS_{moment} \Rightarrow \text{Tìm FS và } \theta$$

---

## 5. Morgenstern-Price

**Tổng quát nhất** — lực liên lát nghiêng góc thay đổi theo hàm $\lambda f(x)$:

$$X_i = \lambda f(x_i) \cdot E_i$$

- Thỏa mãn tất cả điều kiện cân bằng
- Áp dụng cho mặt trượt tròn và không tròn

---

## 6. Tiêu chí ổn định

| Phương pháp | FS_min khuyến nghị |
|------------|-------------------|
| Fellenius | ≥ 1.25 |
| Bishop / Spencer | ≥ 1.3 (thường xuyên), ≥ 1.1 (động đất) |
| Morgenstern-Price | ≥ 1.3 |

**TCVN 4253-2012** (cảng biển): FS ≥ 1.3 (thường), ≥ 1.2 (thi công), ≥ 1.1 (động đất)

---

## 7. Tìm kiếm mặt trượt — Grid Search

Quét lưới tâm trượt (xc, yc) với bán kính tự động điều chỉnh:

```
for xc in linspace(xc_min, xc_max, nx):
    for yc in linspace(yc_min, yc_max, ny):
        R = auto_radius(xc, yc, surface)
        FS = bishop_fos(geom, xc, yc, R)
        track min(FS)
```

**PSO (Particle Swarm):** Tìm kiếm ngẫu nhiên thông minh hơn, dùng cho profile phức tạp.

---

## 8. Tải trọng động đất — Mononobe-Okabe

$$F_{seismic} = k_h \cdot W \quad (\text{tải ngang giả tĩnh})$$

Giảm FS so với điều kiện tĩnh.

---

## 9. Ví dụ — Mái đất Fill+Clay φ=15°, Su=25kPa

| Tham số | Giá trị |
|--------|--------|
| Geometry | Mái dốc 5:7 (H:V) |
| Phương pháp | Bishop |
| FOS tìm được | 1.423 |
| Trạng thái | Dat (>= 1.3) |

---

## 10. Nguyên tắc bất biến — Cung trượt qua chân cừ

**Áp dụng trong tab:** Mọi cung trượt phải đi qua chân cừ (pile tip).

$$R_i = \sqrt{x_{c,i}^2 + (y_{c,i} - z_{tip})^2}$$

- Với mỗi điểm lưới $(x_{c,i}, y_{c,i})$, bán kính $R_i$ được tính ngược từ khoảng cách đến chân cừ tại $(0, z_{tip})$.
- Không tự do tối ưu hóa $R$ — $R$ là giá trị cố định ứng với từng tâm lưới.
- `analyze_slope(geom, xc=xc_i, yc=yc_i, radius=R_i, method=m_key)`

### Tính reach tự động

Để tất cả circle trong lưới cắt được mặt đất phẳng tại $y = z_{sf}$:

```python
R_i = sqrt(xc_i² + (yc_i - pile_tip_z)²)
half_chord = sqrt(R_i² - (yc_i - sf)²)
reach_min = |xc_i| + half_chord
reach = max(reach_min * 1.3, 40.0)   # margin 30%
```

Hàm `_required_reach(xc_min, xc_max, yc_min, yc_max, pile_tip_z, sf)` quét 4 góc lưới và lấy max.

### Mặt đất dạng ramp (không dùng step)

```text
(-reach, sf) → (slope_x, sf) → (0, te) → (reach, sb)
```

- `slope_x = -(fill_h × slope_ratio)`  với `fill_h = top_elev - soil_level_front`
- Dùng ramp liên tục thay cho step thẳng đứng tại x=0 để tránh lỗi "does not intersect at 2 points"

### Nguồn dữ liệu slope H:V

- **Key:** `fill_slope_hv` trong session_state — nhập tại **Geo Data → Fill → Slope H:V**
- Tab Slope Stability chỉ đọc, không có input riêng
- Đọc qua `_geo_from_session()["slope_ratio"]`

---

## Liên kết

- `data/slope_stability.json` — tham số mặc định, schema
- `scripts/slope_stability_tab.py` — module Streamlit
