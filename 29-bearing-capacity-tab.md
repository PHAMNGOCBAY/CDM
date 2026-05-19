# 29 — Sức Chịu Tải Móng Nông (Bearing Capacity Tab)

**Thư viện:** `geotech-staff-engineer` — module `bearing_capacity`  
**Tham chiếu:** FHWA GEC-6 (FHWA-IF-02-054) · FHWA-SA-94-034 (CBEAR) · Meyerhof (1963) · Vesic (1973)

> **AI workflow:** `data/bearing_capacity_tab.json` → `scripts/tab_bearing_capacity.py`

---

## 1. Công thức tổng quát — Meyerhof (1963) / Vesic (1973)

$$q_{ult} = c \cdot N_c \cdot s_c \cdot d_c \cdot i_c
          + q \cdot N_q \cdot s_q \cdot d_q \cdot i_q
          + \tfrac{1}{2} \gamma \cdot B \cdot N_\gamma \cdot s_\gamma \cdot d_\gamma \cdot i_\gamma$$

| Ký hiệu | Ý nghĩa |
|---------|---------|
| c | Lực dính [kPa] |
| q = γ·D | Ứng suất phủ tại đáy móng [kPa] |
| γ | Dung trọng đất [kN/m³] |
| B | Chiều rộng móng [m] |
| Nc, Nq, Nγ | Hệ số sức chịu tải |
| sc, sq, sγ | Hệ số hình dạng |
| dc, dq, dγ | Hệ số chiều sâu |
| ic, iq, iγ | Hệ số tải nghiêng |

---

## 2. Hệ số sức chịu tải

$$N_q = e^{\pi \tan\varphi} \cdot \tan^2\!\left(45 + \frac{\varphi}{2}\right)$$

$$N_c = (N_q - 1) \cot\varphi \quad [\varphi=0: N_c = 5.14]$$

$$N_\gamma = 2(N_q + 1)\tan\varphi \quad \text{[Vesic]}$$

### Bảng tra nhanh Nc/Nq/Nγ

| φ (°) | Nc | Nq | Nγ |
|-------|----|----|----|
| 0 | 5.14 | 1.00 | 0.00 |
| 10 | 8.35 | 2.47 | 1.22 |
| 20 | 14.83 | 6.40 | 5.39 |
| 25 | 20.72 | 10.66 | 10.88 |
| 30 | 30.14 | 18.40 | 22.40 |
| 35 | 46.12 | 33.30 | 48.03 |
| 40 | 75.31 | 64.20 | 109.41 |

---

## 3. Hệ số hình dạng (Meyerhof)

| Hình dạng | sc | sq | sγ |
|-----------|----|----|-----|
| Strip (B/L → 0) | 1.0 | 1.0 | 1.0 |
| Rectangular | 1 + B/L·Nq/Nc | 1 + B/L·tanφ | 1 − 0.4·B/L |
| Square / Circular | 1 + Nq/Nc | 1 + tanφ | 0.6 |

---

## 4. Hệ số chiều sâu (Meyerhof)

Khi D/B ≤ 1:

$$d_c = 1 + 0.4 \frac{D}{B}, \quad
  d_q = 1 + 2\tan\varphi(1-\sin\varphi)^2\frac{D}{B}, \quad
  d_\gamma = 1.0$$

Khi D/B > 1: thay D/B bằng arctan(D/B) [radians].

---

## 5. Ảnh hưởng mực nước ngầm

| Vị trí MNN | Điều chỉnh |
|------------|-----------|
| Tại hoặc trên đáy móng | Dùng γ_sub = γ − γ_w trong thành phần Nγ |
| Tại đáy móng đến z = B | Nội suy tuyến tính γ_eff |
| Sâu hơn z = B | Không ảnh hưởng |

**Trong thư viện:** `BearingSoilProfile(layer1=..., gwt_depth=depth_m)`

---

## 6. Hệ số an toàn

$$q_{allow} = \frac{q_{ult}}{FS}$$

| Loại tải | FS tối thiểu |
|----------|-------------|
| Tải thường xuyên | 3.0 |
| Tải tạm thời | 2.0 |
| Tải động đất | 1.5 |

---

## 7. Sử dụng trong tab

```python
from tab_bearing_capacity import run_bearing_capacity, plot_bearing_capacity

r = run_bearing_capacity(
    shape="square",
    B=2.0, L=2.0, D=1.5,
    gamma_soil=18.0,
    phi_deg=28.0,
    cohesion=0.0,
    gwt_depth=None,
    fs=3.0,
)
# r["q_ultimate"], r["q_allowable"], r["Nc"], r["Nq"], r["Ngamma"]
fig = plot_bearing_capacity(r)
```

---

## 8. Liên kết

| File | Vai trò |
|------|---------|
| `data/bearing_capacity_tab.json` | Thông số mặc định, hệ số bảng tra |
| `scripts/tab_bearing_capacity.py` | Engine tính toán + biểu đồ |
| `28-geotech-staff-engineer.md` | Tổng quan thư viện |
