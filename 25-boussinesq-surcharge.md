# 25 — Áp lực ngang Boussinesq: Tải dải phân bố (TCVN 11823-3:2017 §10.6.2)

Nguồn: TCVN 11823-3:2017 §10.6.2, Công thức (39) — Tường bị kim chế dịch chuyển.

---

## 1. Công thức cơ bản

### Công thức (39) — TCVN 11823-3:2017

```
Δph = (2p/π) × [δ − sinδ·cos(δ + 2α)]
```

**Dạng tương đương (β₁, β₂):**

```
Δph = (2p/π) × [(β₂ − β₁) − sinβ₂·cosβ₂ + sinβ₁·cosβ₁]
```

### Định nghĩa góc

| Góc | Công thức | Ý nghĩa |
|-----|-----------|---------|
| α | arctan(a/z) | Góc từ phương đứng đến mép GẦN của dải tải |
| δ | arctan((a+w)/z) − arctan(a/z) | Góc tổng ứng với chiều rộng dải tải |
| β₁ | α = arctan(a/z) | Góc đến mép gần |
| β₂ | α + δ = arctan((a+w)/z) | Góc đến mép xa |

### Tham số hình học

| Ký hiệu | Đơn vị | Ý nghĩa |
|---------|--------|---------|
| p | kN/m² | Cường độ tải trọng dải phân bố |
| a | m | Khoảng cách từ mặt tường đến mép GẦN của dải (a = 0: tải sát tường) |
| w | m | Chiều rộng dải tải (w ≥ 100 m ≈ tải vô hạn) |
| z | m | Chiều sâu từ mặt đất đặt tải (z = ref_surface − elev, z > 0) |
| ref_surface | m | Cao độ mặt đất đặt tải (thường = soil_level_front) |

---

## 2. Các trường hợp đặc biệt

### 2.1 Tải vô hạn đặt sát tường (a=0, w→∞)

```
α = 0, δ → π/2
Δph = (2p/π) × [π/2 − sin(π/2)·cos(π/2)] = (2p/π) × π/2 = p
```

**Kết quả:** Δph = p — áp lực ngang bằng đúng cường độ tải trọng.

Đây là trường hợp uniform surcharge → σh = k₀ × p (với k₀ = 1 cho tường bị kim chế).

### 2.2 Dải hữu hạn tại tường (a=0, w hữu hạn)

```
α = 0, δ = arctan(w/z)
Δph = (2p/π) × [δ − sinδ·cosδ] = (2p/π) × [δ − ½sin(2δ)]
```

Áp lực giảm dần theo chiều sâu z, đạt cực đại gần mặt đất.

### 2.3 Dải cách tường khoảng a > 0

```
Δph nhỏ hơn so với a=0 — ảnh hưởng giảm khi tải lùi ra xa tường
```

### 2.4 Cao độ trên mặt đặt tải (z ≤ 0)

```
Δph = 0
```

---

## 3. Convention Front / Back

| Side | Ý nghĩa | Màu biểu đồ |
|------|---------|-------------|
| **Front** | Mặt TRÁI tường — tải đẩy tường sang phải (cùng chiều Active) | Đỏ (firebrick) |
| **Back**  | Mặt PHẢI tường — tải đẩy tường sang trái (ngược chiều) | Xanh (steelblue) |

```
F_net = F_front − F_back   [kN/m]   (dương = tổng hợp về phía Back)
```

**ref_surface theo Side:**
- Side = Front → ref_surface = `soil_level_front − Depth`
- Side = Back  → ref_surface = `soil_level_back  − Depth`
- Depth = 0: mặt đặt tải tại mặt đất tự nhiên tương ứng

**Biểu đồ 3 panel:**
- Panel trái: Front Dph — polyline + dots, trục x đảo ngược (tường bên phải)
- Panel giữa: Sơ đồ tường — mũi tên quiver 1 mũi tên/m, polyline nối đuôi mũi tên
- Panel phải: Back Dph — polyline + dots, trục x bình thường (tường bên trái)

## 4. Ứng dụng cho đất đắp (fill surcharge)

Đất đắp (fill) trên nền tự nhiên tạo ra tải dải phân bố lên tường cừ/cọc bên dưới mặt đất tự nhiên (soil_level_front).

| Tham số | Giá trị | Ghi chú |
|---------|---------|---------|
| p (= q_fill) | γ_fill × H_fill [kN/m²] | Áp lực do đất đắp |
| a | 0 | Fill bắt đầu sát tường |
| w | Chiều rộng vùng đắp [m] | w = 50–100 m nếu đắp lan rộng |
| ref_surface | soil_level_front | Mặt đất tự nhiên phía Front |
| z | soil_level_front − elev | Chiều sâu tính từ mặt tự nhiên |

**Áp lực tác dụng từ** soil_level_front **đến mũi cọc** (phía dưới mặt đất tự nhiên).

---

## 4. So sánh Boussinesq vs Ka

| Phương pháp | Công thức | Điều kiện áp dụng |
|-------------|-----------|------------------|
| Ka (chủ động) | Δσh = Ka × q_fill | Tường tự do dịch chuyển (active) |
| Boussinesq Eq.39 | Δph = (2p/π)[δ − sinδcos(δ+2α)] | Tường bị kim chế dịch chuyển (restrained, k₀) |

TCVN 11823-3 §10.5.4: áp lực đất chủ động dùng k_s = ka; áp lực đất tĩnh dùng k_s = k₀.

**Lưu ý:** Boussinesq cho Δph > Ka × q_fill vì tường bị kim chế → áp lực lớn hơn active condition.

---

## 5. Hợp lực và điểm đặt

```
F = ∫ Δph dz    [kN/m]  — tích phân từ ref_surface đến mũi cọc

M = ∫ Δph × (ref_surface − z) dz    [kN·m/m]  — moment về ref_surface

z_app = ref_surface − M/F    [m]  — cao độ điểm đặt hợp lực

M_top  = F × (z_app − top_elev)    [kN·m/m]  — moment về đỉnh cọc
M_tip  = F × z_app                 [kN·m/m]  — moment về mũi cọc (tham chiếu)
```

---

## 6. Nhiều dải tải (multiple strips)

Khi có nhiều dải tải chồng chất:

```
Δph_total(z) = Σᵢ Δph_i(z)
```

Tích phân và hợp lực tính trên tổng áp lực.

---

## 7. Sơ đồ hình học

```
      Tường/Cọc
         │
─────────┼──────────────────────── soil_level_front (ref_surface)
         │        ←a→    ←  w  →
         │        [████████████]  p [kN/m²]
         │
    z↓   │  Δph(z)◄────────────────
         │
         │
─────────┼──────────────────────── pile_tip_elev
```

---

## 8. API — `scripts/boussinesq_surcharge.py`

```python
from boussinesq_surcharge import (
    SurchargeStrip,
    BoussiGeometry,
    delta_ph_at_elev,
    compute_profile,
    compute_all,
    plot_boussinesq_diagram,
)

# Tải dải do đất đắp
strip_fill = SurchargeStrip(
    q=18.0 * 2.7,   # γ_fill × H_fill = 48.6 kN/m²
    a=0.0,           # sát tường
    w=50.0,          # đắp lan rộng 50 m
    ref_surface=0.0, # soil_level_front
    label="Fill surcharge"
)

geom = BoussiGeometry(
    top_elev=2.7,
    pile_length=20.0,
    soil_level_front=0.0,
)

result = compute_all(geom, [strip_fill])
print(f"F = {result['F']:.2f} kN/m  tại z_app = {result['z_app']:.3f} m")
fig = result["fig"]
```

### Hàm `delta_ph_at_elev(elev, strip, soil_surface)`

| Tham số | Kiểu | Mô tả |
|---------|------|-------|
| elev | float | Cao độ điểm tính [m] |
| strip | SurchargeStrip | Thông số dải tải |
| soil_surface | float | Cao độ mặt đặt tải (thường = ref_surface) |
| **return** | float | Δph [kN/m²], = 0 nếu elev ≥ soil_surface |

### Hàm `compute_profile(geom, strips, spacing=1.0)`

`spacing` — khoảng cách giữa hai điểm tính liên tiếp theo chiều sâu [m]. Mặc định 1.0 m (1 điểm/m).
`n_pts = max(3, round(pile_length / spacing) + 1)`

Trả về dict với keys: `elevs`, `pressure`, `strip_pressures`, `F`, `z_app`, `M_top`, `M_tip`.

### Hàm `compute_all(geom, strips, spacing=1.0)`

Trả về dict đầy đủ + `fig` (matplotlib Figure 2-panel).

---

## 9. Ví dụ tính toán

Thông số: γ_fill = 18 kN/m³, H_fill = 2.7 m → q_fill = 48.6 kN/m²

a = 0 m, w = 50 m, ref_surface = 0.0 m, top_elev = 2.7 m, L_pile = 20 m (tip = −17.3 m)

| z (m) | α (rad) | δ (rad) | Δph (kN/m²) |
|-------|---------|---------|-------------|
| 0.1 | 0.000 | 1.521 | 46.8 |
| 1.0 | 0.000 | 1.471 | 43.4 |
| 5.0 | 0.000 | 1.471 | 43.5 |
| 10.0 | 0.000 | 1.373 | 38.7 |
| 17.3 | 0.000 | 1.238 | 32.8 |

Hợp lực F ≈ 718 kN/m, điểm đặt z_app ≈ −7.5 m (cao độ).

*Lưu ý: Với a=0, w=50 m (rộng hơn nhiều so với chiều sâu), Δph ≈ 0.9×q → xấp xỉ uniform surcharge.*
