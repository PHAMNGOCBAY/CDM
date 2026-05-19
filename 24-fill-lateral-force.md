# 24 — Lực ngang đất đắp → Lực tập trung tác dụng lên kè

Nguồn: TCVN 11823-3:2017 §10.5  
File tính: `scripts/fill_lateral_force.py` | Data: `data/fill_lateral_force.json`

---

## Quy ước

| Phía | Vị trí | Đất đắp | Áp lực |
|------|--------|---------|--------|
| **Front** | **TRÁI** | **Có** | Active (Ka) — tạo lực ngang đẩy kè |
| Back | PHẢI | Không | Passive (Kp) — cản kè |

**Đất đắp (fill):** từ `soil_level_front` đến `top_elev` — chiều cao H_fill.

---

## Phân tích lực

Lực ngang từ đất đắp gồm 2 thành phần:

```
top_elev (+2.7 m) ────────────────────
          ↑                     ← F₁ (fill zone)
    H_fill = 2.7 m   [Đất đắp]
          ↓
soil_level_front (0.0 m) ─────────────
          ↓                     ← F₂ (surcharge Ka×q_fill)
    Lớp đất tự nhiên
          ↓
pile_tip_elev (-17.3 m) ──────────────
```

### F₁ — Lực trong vùng fill

$$\sigma_h(z) = K_a \cdot \sigma_v^\prime(z) - 2c_{fill}\sqrt{K_a} \quad [\geq 0]$$

$$\sigma_v^\prime(z) = \gamma_{fill}^{eff} \cdot h \quad (h = \text{chiều sâu từ top\_elev})$$

| Trường hợp | Công thức F₁ | Cao độ z₁ |
|-----------|-------------|----------|
| c=0, không ngập nước | $F_1 = \frac{1}{2} K_a \gamma_{fill} H_{fill}^2$ | $z_1 = soil\_level + H_{fill}/3$ |
| Tổng quát (tích phân số) | $F_1 = \int_{bottom}^{top} \sigma_h\, dz$ | $z_1 = top - \frac{\int \sigma_h (top-z)\, dz}{F_1}$ |

### F₂ — Lực surcharge trên lớp tự nhiên

Đất đắp tạo thêm tải trọng mặt **q_fill = γ_fill × H_fill** lên các lớp đất tự nhiên bên dưới:

$$\Delta\sigma_h^{(i)} = K_a^{(i)} \cdot q_{fill} \quad [\text{kN/m}^2, \text{đều trong mỗi lớp}]$$

$$F_2 = \sum_i K_a^{(i)} \cdot q_{fill} \cdot \Delta z_i \quad [\text{kN/m}]$$

**Cao độ z₂**: centroid của biểu đồ áp lực F₂ (thường gần giữa phần cọc dưới mặt đất).

### Lực tổng hợp

$$F_{fill} = F_1 + F_2 \quad [\text{kN/m}]$$

$$z_{fill} = \frac{F_1 z_1 + F_2 z_2}{F_1 + F_2} \quad [\text{m}]$$

---

## Moment kiểm tra

| Điểm tham chiếu | Công thức | Ý nghĩa |
|----------------|-----------|---------|
| Mặt đất (soil_level_front) | $M = F_1(z_1 - z_{sl}) + F_2(z_2 - z_{sl})$ | Kiểm tra ổn định lật sơ bộ |
| Mũi cọc (pile_tip) | $M = F_1(z_1 - z_{tip}) + F_2(z_2 - z_{tip})$ | Nội lực tại mũi cọc |

> z₁ > soil_level_front, z₂ < soil_level_front → cả hai F₁, F₂ đều gây moment lật về phía Back.

---

## Biểu đồ — 2 panel

```
┌──────────────────────┬──────────────────────────────┐
│  Áp lực ngang (kN/m²)│   Sơ đồ kè (mặt cắt)        │
│                       │                              │
│  ██ F₁ (fill zone)   │  [đất đắp hatch]  [CỪ]       │
│  ░░ F₂ (surcharge)   │   ←───── F₁                  │
│  ▲ điểm đặt F₁       │   ←──── F₂          F_fill ─►│
│                       │                              │
└──────────────────────┴──────────────────────────────┘
```

Panel trái: biểu đồ áp lực phân bố (tomato = fill zone, salmon = surcharge)  
Panel phải: sơ đồ kè với mũi tên lực tập trung F₁, F₂ (bên trái) và F_fill tổng (bên phải)

---

## Ứng dụng trong mô hình kết cấu

### Anastruct (dầm Winkler)

```python
# F1: concentrated load tại z_fill_zone
beam.q_load(q=F1, node1=node_at_z1, node2=node_at_z1)

# F2: distributed load Ka×q_fill từ soil_level_front đến pile_tip
beam.q_load(q=Ka_avg * q_fill, node1=node_soil_level, node2=node_pile_tip)
```

### PLAXIS 2D

```python
# Tải trọng điểm (point load) tại cao độ z_total_fill
g_i.pointload(z_total_fill, F_total_fill)

# Hoặc tải phân bố trên đoạn tường:
# - Fill zone:    pressure profile từ earth_pressure.py
# - Surcharge:    uniform load Ka_avg × q_fill
```

### Mô hình đơn giản (kiểm tra tay)

```
F_fill = {F_total_fill} kN/m  tại z = {z_total_fill} m
→ Moment về dredge level (soil_level_front):
  M = F_fill × (z_total_fill - soil_level_front)
```

---

## API — `scripts/fill_lateral_force.py`

| Hàm / Class | Mô tả |
|------------|-------|
| `FillGeometry(top_elev, soil_level_front, pile_length, water_elev_front, gamma_fill, phi_fill, c_fill)` | Dataclass tham số |
| `compute_fill_zone(geom, ka_method, delta_deg)` | Áp lực + resultant F₁, z₁ trong vùng fill |
| `compute_surcharge_effect(geom, natural_layers, ka_method)` | Lực F₂, z₂ từ surcharge trên lớp tự nhiên |
| `resultant_combined(F1, z1, F2, z2)` | `(F_total, z_total)` |
| `compute_all(geom, natural_layers, ka_method)` | Tính đầy đủ + vẽ biểu đồ → dict |
| `plot_fill_force_diagram(geom, fill_res, sur_res, F_total, z_total)` | Figure matplotlib 2 panel |

### Dict kết quả `compute_all()`

```python
{
  "F_fill_zone": float,    # F₁ [kN/m]
  "z_fill_zone": float,    # z₁ [m]
  "pressure_top": float,   # σ_h tại đỉnh fill [kN/m²]
  "pressure_bot": float,   # σ_h tại đáy fill [kN/m²]
  "ka": float,             # hệ số áp lực đất chủ động
  "F_surcharge": float,    # F₂ [kN/m]
  "z_surcharge": float,    # z₂ [m]
  "q_fill": float,         # γ_fill × H_fill [kN/m²]
  "F_total_fill": float,   # F_fill = F₁ + F₂ [kN/m]
  "z_total_fill": float,   # cao độ tổng hợp [m]
  "M_about_soil_level": float,  # moment về mặt đất [kN·m/m]
  "M_about_pile_tip": float,    # moment về mũi cọc [kN·m/m]
  "fig": matplotlib.figure.Figure,
}
```

---

## Ví dụ tính tay (kiểm tra)

**Đầu vào:** top_elev=2.7 m, soil_level_front=0.0 m, pile_length=20 m  
γ_fill=18 kN/m³, φ_fill=25°, c_fill=0, nước WL=-1.0 m

**Ka Rankine:** Ka = tan²(45−25/2) = tan²(32.5°) = 0.406

**F₁ (fill zone, c=0, không ngập):**  
σ_h(top) = 0 | σ_h(bottom) = 0.406 × 18 × 2.7 = 19.7 kN/m²  
F₁ = 0.5 × 0.406 × 18 × 2.7² = **26.6 kN/m**  
z₁ = 0 + 2.7/3 = **0.90 m**

**F₂ (surcharge Ka×q_fill, lớp sét mềm φ=5°):**  
Ka_clay = tan²(42.5°) = 0.096 | q_fill = 18 × 2.7 = 48.6 kN/m²  
Δσ_h = 0.096 × 48.6 = 4.7 kN/m² (đều trên 17.3 m dưới mặt đất)  
F₂ ≈ 4.7 × 17.3 ≈ **81 kN/m** (trung bình Ka các lớp)

---

## Liên kết với các file khác

| File | Quan hệ |
|------|---------|
| `scripts/earth_pressure.py` | Tính Active+Passive đầy đủ — fill_lateral_force.py tách riêng phần đất đắp |
| `scripts/lateral_earth_pressure.py` | Cung cấp `ka_rankine`, `ka_coulomb`, `SoilLayer` |
| `scripts/app_coc_tai_ngang.py` | Session keys: `gamma_fill`, `phi_fill`, `c_fill`, `soil_level_front`, `top_elev` |
| `data/earth_pressure.json` | Convention Front=Active+fill, Back=Passive |
