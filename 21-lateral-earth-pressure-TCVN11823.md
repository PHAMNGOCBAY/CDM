# 21 — Áp lực đất ngang — TCVN 11823-3:2017

Nguồn: TCVN 11823-3:2017 Thiết kế cầu đường bộ — Phần 3: Tường chắn và tường chuyển tiếp  
File tính: `scripts/lateral_earth_pressure.py` | Data: `data/lateral_earth_pressure.json`

---

## §10.5.2 — Hệ số áp lực đất nghỉ k₀

| Điều kiện | Công thức | Ghi chú |
|-----------|-----------|---------|
| Đất NC (không cố kết thông thường) | k₀ = 1 − sin φ′ | Eq.23 |
| Đất OC (quá cố kết) | k₀ = (1 − sin φ′) × √OCR | Eq.24 |

---

## §10.5.3 — Hệ số áp lực đất chủ động kₐ

### Coulomb (tổng quát) — Eq.25

$$k_a = \frac{\sin^2(\theta + \varphi')}{\Gamma^2 \cdot \sin^2\theta \cdot \sin(\theta - \delta)}$$

$$\Gamma = 1 + \sqrt{\frac{\sin(\varphi' + \delta)\sin(\varphi' - \beta)}{\sin(\theta - \delta)\sin(\theta + \beta)}}$$

| Ký hiệu | Ý nghĩa | Đơn vị |
|---------|---------|--------|
| θ | Góc nghiêng tường so với phương ngang | ° (90° = tường thẳng đứng) |
| φ′ | Góc ma sát trong đất | ° |
| δ | Góc ma sát tiếp xúc tường–đất | ° (Bảng 20) |
| β | Góc nghiêng của mặt đất đắp | ° (0° = mặt phẳng ngang) |

### Rankine (đơn giản) — tường thẳng đứng, δ=0, β=0

$$k_a = \tan^2\!\left(45° - \frac{\varphi'}{2}\right)$$

---

## §10.5.4 — Hệ số áp lực bị động kₚ

### Rankine (đơn giản)

$$k_p = \tan^2\!\left(45° + \frac{\varphi'}{2}\right)$$

### Đất dính — Eq.27

$$p_p = k_p \cdot \gamma \cdot z + 2c\sqrt{k_p}$$

---

## §10.5 — Áp lực đất tại độ sâu z

$$\sigma_h = k \cdot \gamma \cdot z \quad [\text{kN/m}^2]$$

Trong đó k là kₐ, k₀, hoặc kₚ tùy trạng thái.

---

## §10.6.1 — Tải trọng phân bố đều (Uniform Surcharge) — Eq.38

$$\Delta p = k_s \cdot q_s$$

- kₛ = kₐ (tường tự do) hoặc k₀ (tường cứng)  
- qₛ = cường độ tải trọng phân bố [kN/m²]

---

## §10.6.4 — Tải trọng xe (Live Load) — Eq.45

$$\Delta p = k \cdot \gamma_s \cdot h_{eq}$$

- k = kₐ hoặc k₀  
- γₛ = dung trọng đất đắp [kN/m³]  
- h_eq = chiều cao đất đắp tương đương [m] — tra Bảng 22/23

### Bảng 22 — h_eq cho mố cầu

| Chiều cao tường [m] | h_eq [m] |
|--------------------|----------|
| 0.0 | 1.500 |
| 3.0 | 1.050 |
| 6.0 | 0.600 |
| 9.0 | 0.450 |

### Bảng 23 — h_eq cho tường chắn

| Chiều cao tường [m] | h_eq [m] |
|--------------------|----------|
| 0.0 | 1.200 |
| 1.5 | 1.200 |
| 3.0 | 0.900 |
| 6.0 | 0.600 |
| 9.0 | 0.450 |

---

## Bảng 20 — Góc ma sát δ cọc/tường bê tông đúc sẵn

| Loại đất | δ_min [°] | δ_max [°] |
|----------|-----------|-----------|
| Sỏi và sỏi có cát | 22 | 26 |
| Cát sạch và sỏi có silt | 17 | 22 |
| Cát pha bụi và bụi | 17 | 17 |
| Cát hạt nhỏ đến hạt vừa (sạch) | 17 | 22 |
| Bụi (dẻo thấp) | 14 | 14 |

---

## Quy ước dấu và hướng trục

| Đại lượng | Quy ước |
|-----------|---------|
| Độ sâu z | Dương từ đỉnh cừ xuống |
| Cao độ | Dương lên trên (đỉnh cừ = top_elev = +2.7 m) |
| σ_active | Dương = lực hướng vào cừ (từ phía Back) |
| σ_passive | Dương = lực hướng vào cừ (từ phía Front) |
| Áp lực nước | γ_w = 9.81 kN/m³ |

---

## Sơ đồ tính toán — Cừ bê tông dự ứng lực SW

```
         Back side          Front side
              |                  |
  top_elev +2.7m  ─── SP Top ───
              |                  |
  soil_back 0.0m  ─── Natural ── soil_front 0.0m
              |  [Earth Active]  |  [Earth Passive]
  water 0.0m  ─── Water Level ──
              |  [Water Press.]  |
              |                  |
              ▼                  ▼
           k_a×σ_v          k_p×σ_v + 2c√kp
```

---

## Liên kết code

| Hàm | Mô tả |
|-----|-------|
| `ka_rankine(phi)` | Rankine kₐ |
| `ka_coulomb(phi, delta, beta, theta)` | Coulomb kₐ (Eq.25) |
| `k0_nc(phi)` | At-rest k₀ (NC soil) |
| `kp_rankine(phi)` | Rankine kₚ |
| `compute_active_profile(geom, back_layers, fill)` | Mảng σ_h chủ động |
| `compute_passive_profile(geom, front_layers)` | Mảng σ_h bị động |
| `resultant(elevs, pressure)` | Lực tổng hợp và điểm đặt |
| `plot_pressure_diagram(...)` | Biểu đồ GEO5-style (4 panel) |
| `layers_from_df_records(records, top_elev, water_elev)` | Chuyển đổi từ st.data_editor |
