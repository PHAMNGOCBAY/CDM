# 22 — Áp lực nước — Tính toán và Biểu đồ

Nguồn: TCVN 11823-3:2017 §10.5.1 + Terzaghi (1943) seepage approximation  
File tính: `scripts/water_pressure.py` | Data: `data/water_pressure.json`

---

## Hằng số

| Ký hiệu | Giá trị | Ghi chú |
|---------|---------|---------|
| γ_w | **9.81 kN/m³** | Tiêu chuẩn; dùng 10.0 kN/m³ nếu spec dự án yêu cầu |

---

## §10.5.1 — Áp lực thủy tĩnh

$$p_w(z) = \gamma_w \cdot \max\!\left(0,\ h_w - z\right)$$

- h_w = cao độ mực nước [m]  
- z = cao độ điểm tính [m] (dương hướng lên)  
- p_w = 0 khi điểm nằm trên mực nước

**Áp dụng:** Không có dòng thấm, hoặc mực nước Front = Back.

---

## Áp lực ngang tổng hợp (Net Water Pressure)

$$\Delta p_w = p_{Back} - p_{Front} \quad [\text{kN/m}^2]$$

- Dương = áp lực hướng từ Back sang Front (cùng chiều áp lực đất chủ động)
- Bằng 0 khi mực nước hai phía bằng nhau

**Lực tổng hợp:**

$$U = \int_{z_{tip}}^{z_{top}} \Delta p_w \, dz \quad [\text{kN/m}]$$

---

## Hiệu chỉnh thấm — Terzaghi Simplified

Khi mực nước Back > mực nước Front, nước chảy vòng quanh mũi cừ.

### Sơ đồ đường thấm

```
  Back (wl_back)          Front (wl_front)
      ───────               
        ↓ seepage down         ↑ seepage up
        ↓                      ↑
        ↓                      ↑
        →  →  →  →  →  →  →  ↑   (vòng qua mũi cừ)
```

### Tham số

| Ký hiệu | Công thức | Ý nghĩa |
|---------|----------|---------|
| Δh | water_elev_back − water_elev_front | Độ chênh mực nước [m] |
| d  | soil_level_front − bot_elev | Chiều sâu chôn cừ dưới mặt đào [m] |
| L_seep | 2d | Tổng chiều dài đường thấm [m] |
| i_avg | Δh / (2d) | Gradient thủy lực trung bình |

### Phía Back (dòng chảy xuống — áp lực giảm)

Tại cao độ `elev` bên **dưới mặt đào** (elev < soil_level_front):

$$p_{Back}(elev) = \gamma_w \cdot \left[(h_{back} - elev) - \frac{\Delta h}{2} \cdot \frac{d_{below}}{d}\right]$$

- d_below = soil_level_front − elev (độ sâu dưới mặt đào)
- Tổn thất cột nước tuyến tính từ 0 tại mặt đào đến Δh/2 tại mũi cừ

### Phía Front (dòng chảy lên — áp lực tăng)

Tại cao độ `elev` bên **dưới mặt đào**:

$$p_{Front}(elev) = \gamma_w \cdot \left[(h_{front} - elev) + \frac{\Delta h}{2} \cdot \frac{d_{below}}{d}\right]$$

- Áp lực Front tăng thêm Δh/2 tại mũi cừ so với thủy tĩnh thuần

> **Lưu ý:** Phương pháp Terzaghi chỉ là xấp xỉ (overestimates seepage path uniformity).  
> Phân tích chính xác dùng lưới thấm (flow net) hoặc phần mềm FEM.

---

## So sánh hai phương pháp

| Phương pháp | Áp lực ngang tổng hợp | Thiên về |
|-------------|----------------------|---------|
| Hydrostatic (thủy tĩnh) | γ_w × Δh (hằng số theo chiều sâu khi dưới cả hai WL) | An toàn (lớn hơn) |
| Seepage Terzaghi | Nhỏ hơn hydrostatic | Kinh tế hơn |

---

## Ứng suất hữu hiệu — Ảnh hưởng của thấm

| Vị trí | Công thức σ'_v | Ghi chú |
|--------|--------------|---------|
| Trên mực nước | γ_moist × z | Không ảnh hưởng |
| Dưới WL, dòng chảy xuống (Back) | γ_sub × z + i × γ_w × z | Tăng ứng suất hữu hiệu |
| Dưới WL, dòng chảy lên (Front) | γ_sub × z − i × γ_w × z | **Giảm** ứng suất hữu hiệu → nguy hiểm |

**Điều kiện heave thủy lực (hydraulic heave):**

$$i_{cr} = \frac{\gamma_{sub}}{\gamma_w} = \frac{\gamma_{sat} - \gamma_w}{\gamma_w}$$

Khi i_avg ≥ i_cr → mất ổn định đáy hố đào (quick condition).

---

## Quy ước dấu và cao độ

| Đại lượng | Quy ước |
|-----------|---------|
| Cao độ | Dương hướng lên, datum = project datum |
| Mặc định đỉnh cừ | top_elev = **+2.7 m** |
| p_back | Luôn ≥ 0, tăng theo chiều sâu dưới WL Back |
| p_front | Luôn ≥ 0, tăng theo chiều sâu dưới WL Front |
| Δp_w = Net | Dương = hướng Front, âm = hướng Back |

---

## Biểu đồ GEO5-style — 3 panel

**Quy tắc thống nhất với tab GeoData: Front = TRÁI, Back = PHẢI.**

```
┌─────────────────┬─────────────────┬─────────────────┐
│ Front Water [◄] │  Back Water [►] │  Net Water [◄►] │
│ (trái − đào)    │  (phải − giữ)   │  Back − Front   │
│                 │                 │                 │
│  WL Front ─ ─   │   ─ ─ WL Back  │  dương → ◄      │
│    p_front [◄]  │   [►] p_back   │  (lực → Front)  │
│  Mặt đào ───    │  Mặt đào ───    │  Mặt đào ───    │
│                 │                 │                 │
│  [lực tổng hợp] │  [lực tổng hợp] │  [lực tổng hợp] │
└─────────────────┴─────────────────┴─────────────────┘
```

| Panel | Nội dung | Hướng bars | Màu |
|-------|----------|-----------|-----|
| 1 (trái) | Front Water Pressure | Sang trái ◄ | Xanh nhạt `#1a8cff` |
| 2 (giữa) | Back Water Pressure | Sang phải ► | Xanh đậm `steelblue` |
| 3 (phải) | Net = Back − Front | Dương → ◄ (đẩy về Front) | Theo dấu |

### Visualization — mũi tên quiver

Mỗi panel áp lực (Front / Back / Net) vẽ thêm mũi tên ngang cách nhau **2 m** dọc chiều cao cừ:

| Thuộc tính | Giá trị |
|-----------|---------|
| Loại | `ax.quiver` ngang (Δy = 0) |
| Khoảng cách | 2.0 m |
| Gốc mũi tên | x = 0 (đường zero) |
| Chiều dài | = giá trị áp lực (data coordinates) |
| `scale_units` | `"xy"` |
| `scale` | `1.0` |
| `angles` | `"xy"` |
| Alpha | 0.60 |
| Màu | Theo panel (`#1a8cff` Front / `steelblue` Back / theo dấu Net) |
| Chỉ vẽ khi | pressure > 0.5 kN/m² |

Cùng quy ước hướng với fill: Front → trái, Back → phải, Net dương → trái (hướng Front).

---

## API — `scripts/water_pressure.py`

| Hàm / Class | Mô tả |
|------------|-------|
| `WaterGeometry(top_elev, pile_length, soil_level_front, water_elev_front, water_elev_back)` | Dataclass tham số hình học |
| `build_elevation_grid(geom, n_pts=200)` | Lưới cao độ với các điểm gãy tại WL, mặt đào, mũi cừ |
| `hydrostatic_back(geom, elevs)` | p_back thủy tĩnh [kN/m²] |
| `hydrostatic_front(geom, elevs)` | p_front thủy tĩnh [kN/m²] |
| `seepage_back(geom, elevs)` | p_back sau hiệu chỉnh thấm Terzaghi |
| `seepage_front(geom, elevs)` | p_front sau hiệu chỉnh thấm Terzaghi |
| `net_water_pressure(p_back, p_front)` | Δp = p_back − p_front [kN/m²] |
| `resultant(elevs, pressure)` | (F [kN/m], z_app [m]) |
| `compute_all(geom, mode)` | Tính toàn bộ + vẽ biểu đồ, trả về dict |
| `plot_water_diagram(geom, elevs, p_back, p_front, p_net, ...)` | Figure matplotlib 3 panel |

---

## Liên kết với các file khác

| File | Liên quan |
|------|----------|
| `scripts/lateral_earth_pressure.py` | Sử dụng p_back/p_front làm đầu vào effective stress |
| `scripts/app_coc_tai_ngang.py` | water_elev_front, water_elev_back từ Geo Data tab |
| `data/lateral_earth_pressure.json` | Effective stress rule khi tính áp lực đất |
