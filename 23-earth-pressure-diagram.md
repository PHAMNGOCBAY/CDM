# 23 — Biểu đồ áp lực đất ngang — Active & Passive

Nguồn: TCVN 11823-3:2017 §10.5  
File tính: `scripts/earth_pressure.py` | Data: `data/earth_pressure.json`

---

## Quy ước — Thống nhất với tab GeoData

| Phía | Vị trí | Loại áp lực | Có đất đắp? | Màu |
|------|--------|------------|------------|-----|
| **Front** | **TRÁI** | **Active (Ka)** | **Có (fill)** | Đỏ / tomato |
| **Back**  | **PHẢI** | **Passive (Kp)** | Không | Xanh lá / mediumseagreen |

**Lý do:** Front = phía đắp cao, áp lực lớn hơn → đẩy cừ → Active.  
Back = phía hở/nước, đất chịu nén → cản cừ → Passive.

---

## Công thức áp lực đất chủ động — Active (Front/TRÁI)

$$\sigma_h^{active} = K_a \cdot \sigma_v' - 2c\sqrt{K_a} \quad [\text{kN/m}^2, \geq 0]$$

### Rankine (mặc định, tường thẳng δ=0)

$$K_a = \tan^2\!\left(45° - \frac{\varphi}{2}\right)$$

### Coulomb (tổng quát — Eq.25 TCVN 11823-3)

$$K_a = \frac{\sin^2(\theta+\varphi)}{\Gamma^2 \sin^2\theta \sin(\theta-\delta)}$$

---

## Công thức áp lực đất bị động — Passive (Back/PHẢI)

$$\sigma_h^{passive} = K_p \cdot \sigma_v' + 2c\sqrt{K_p} \quad [\text{kN/m}^2]$$

$$K_p = \tan^2\!\left(45° + \frac{\varphi}{2}\right) \quad \text{(Rankine)}$$

---

## Ứng suất đứng hữu hiệu σ'_v

| Điều kiện | Công thức |
|-----------|-----------|
| Trên mực nước | σ'_v += γ_moist × dz |
| Dưới mực nước | σ'_v += γ_sub × dz |
| Tải trọng mặt | σ'_v khởi đầu = q_s [kN/m²] |

---

## Lớp đất đắp (Fill) — Front side only

```
  top_elev = +2.7 m  ───────  SP Top
        ↑                    Fill zone (đất đắp)
  soil_level_front = 0.0 m   (γ_fill, φ_fill, c_fill)
        ↓
  natural front layers ...
```

Áp lực Active trong vùng fill dùng Ka của fill (φ_fill, c_fill).  
Bên dưới soil_level_front dùng Ka của từng lớp đất tự nhiên.

**Back side:** Không có fill. Passive bắt đầu từ soil_level_back xuống.

---

## Áp lực tổng hợp Net

$$\text{Net} = \sigma_h^{active} - \sigma_h^{passive}$$

| Dấu Net | Ý nghĩa | Biểu đồ |
|---------|---------|---------|
| > 0 (Active > Passive) | Vùng nguy hiểm — cừ có xu hướng trượt về Back | Bars sang PHẢI, màu đỏ |
| < 0 (Passive > Active) | Vùng ổn định — lực bị động giữ cừ | Bars sang TRÁI, màu xanh |

---

## Biểu đồ — 3 panel GEO5-style

```
┌─────────────────────┬─────────────────────┬─────────────────────┐
│  Active (Front) ◄   │     Net Pressure    │  Passive (Back)  ►  │
│  Ka×σv − 2c√Ka      │  Active − Passive   │  Kp×σv + 2c√Kp     │
│  (incl. fill hatch) │  + → PHẢI (danger) │  (từ soil_back)     │
│  bars → TRÁI        │  − → TRÁI (stable)  │  bars → PHẢI        │
│  màu: tomato        │  đỏ/xanh theo dấu   │  màu: green         │
│  F_active [kN/m]    │  F_net [kN/m]       │  F_passive [kN/m]   │
└─────────────────────┴─────────────────────┴─────────────────────┘
```

### Visualization — mũi tên quiver

Mỗi panel áp lực (Active / Passive / Net) vẽ thêm mũi tên ngang cách nhau **2 m** dọc chiều cao cừ:

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
| Màu | Theo panel (tomato / green / đỏ-xanh) |
| Chỉ vẽ khi | pressure > 0.5 kN/m² |

Cùng quy ước hướng với fill: Active → trái, Passive → phải, Net theo dấu.

---

## API — `scripts/earth_pressure.py`

| Hàm / Class | Mô tả |
|------------|-------|
| `EpGeometry(top_elev, pile_length, soil_level_front, soil_level_back, water_elev_front, water_elev_back, surcharge_front)` | Dataclass tham số hình học |
| `compute_active_front(geom, front_layers, fill, elevs, ka_method, delta_deg)` | Active σ_h + σ_v trên Front, bao gồm fill |
| `compute_passive_back(geom, back_layers, elevs, kp_method, delta_deg)` | Passive σ_h + σ_v trên Back |
| `resultant(elevs, pressure)` | (F [kN/m], z_app [m]) |
| `compute_all(geom, front_layers, back_layers, fill, ka_method, kp_method)` | Tính toàn bộ + vẽ biểu đồ, trả về dict |
| `plot_earth_pressure_diagram(geom, elevs, active_h, passive_h, ...)` | Figure matplotlib 3 panel |

### Dict kết quả `compute_all()`

```python
{
  "elevs", "active_h", "passive_h", "net_h",
  "sv_front", "sv_back",          # ứng suất đứng
  "F_active", "z_active",         # lực tổng hợp Active + cao độ
  "F_passive", "z_passive",       # lực tổng hợp Passive + cao độ
  "F_net", "z_net",               # lực Net + cao độ
  "fig",                          # matplotlib Figure
}
```

---

## Liên kết với các file khác

| File | Quan hệ |
|------|---------|
| `scripts/lateral_earth_pressure.py` | Cung cấp `ka_rankine`, `ka_coulomb`, `kp_rankine`, `SoilLayer` |
| `scripts/water_pressure.py` | Áp lực nước (cùng convention Front=TRÁI, Back=PHẢI) |
| `data/lateral_earth_pressure.json` | Formulas Ka, Kp, Bảng 20 delta — tham chiếu |
| `scripts/app_coc_tai_ngang.py` | session keys: `front_layers_df`, `back_layers_df`, `gamma_fill`, `phi_fill`, `c_fill` |
