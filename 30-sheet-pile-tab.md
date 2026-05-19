# 30 — Thiết Kế Chiều Sâu Ngàm Cọc Bản (Sheet Pile Design Tab)

**Thư viện:** `geotech-staff-engineer` — module `sheet_pile` + `soe`  
**Tham chiếu:** USACE EM 1110-2-2504 · Terzaghi & Peck (1967) · CWALSHT methodology

> **AI workflow:** `data/sheet_pile_tab.json` → `scripts/tab_sheet_pile.py`

---

## 1. Nguyên lý tính chiều sâu ngàm

Cọc bản phải ngàm đủ sâu vào đất bên dưới mức đào để áp lực bị động phía dưới cân bằng áp lực chủ động phía trên.

### 1.1 Cọc consolle (cantilever)

Không có cấu kiện đỡ — toàn bộ lực cân bằng qua cơ cấu xoay trong đất:

```
Active →   | ← Passive
           |
H_dao ─────┤
           |  ← Passive (net)
    d ─────┤
```

- Chiều sâu ngàm `d` tính từ: tổng moment = 0 tại điểm xoay
- Thực tế: nhân `d` với 1.2–1.3 hoặc dùng FOS_passive = 1.5

### 1.2 Cọc có neo (anchored — Free Earth Support)

Neo tại độ sâu `z_a` từ mặt đất → giảm moment và chiều sâu ngàm:

- **Lực neo** = tổng lực ngang chủ động − bị động trong khu vực bên
- **Moment max** thường nằm giữa đáy đào và điểm không có lực cắt

---

## 2. Áp lực đất — Rankine (mặc định)

$$K_a = \tan^2\!\left(45 - \frac{\varphi}{2}\right)$$
$$K_p = \tan^2\!\left(45 + \frac{\varphi}{2}\right)$$

**Áp lực chủ động:**
$$\sigma_a = K_a \cdot \sigma'_v - 2c\sqrt{K_a}$$

**Áp lực bị động:**
$$\sigma_p = K_p \cdot \sigma'_v + 2c\sqrt{K_p}$$

### Bảng Ka / Kp theo φ

| φ (°) | Ka | Kp | Kp/Ka |
|-------|----|----|-------|
| 0 | 1.00 | 1.00 | 1.0 |
| 15 | 0.59 | 1.70 | 2.9 |
| 20 | 0.49 | 2.04 | 4.2 |
| 25 | 0.41 | 2.46 | 6.0 |
| 30 | 0.33 | 3.00 | 9.0 |
| 35 | 0.27 | 3.69 | 13.7 |

---

## 3. Kiểm tra ổn định đáy hố đào — Basal Heave

Áp dụng khi đất sét mềm (Su thấp, thi công trong đất không thoát nước):

### Terzaghi (1943)

$$F_s = \frac{5.14 \cdot c_u}{\gamma H + q_s}$$

### Bjerrum & Eide (1956)

$$F_s = \frac{N_c \cdot c_u}{\gamma H + q_s}$$

với Nc = f(H/B) — phụ thuộc tỉ lệ chiều sâu / chiều rộng hố đào:

| H/B | 1 | 2 | 4 | ∞ |
|-----|---|---|---|---|
| Nc  | 5.14 | 5.63 | 6.17 | 7.60 |

**Yêu cầu:** Fs ≥ 1.5 (tải thường xuyên), Fs ≥ 1.3 (tạm thời)

---

## 4. Chọn tiết diện cọc SW

Sau khi có M_max từ tính toán, kiểm tra cọc SW:

$$M_{max} \leq M_{cr}$$

Với Mcr của cọc SW tra bảng [data/sw_pile_catalog.json](data/sw_pile_catalog.json).

---

## 5. Sử dụng trong tab

```python
from tab_sheet_pile import run_cantilever, run_anchored, run_basal_heave

# Consolle
r = run_cantilever(
    excavation_depth=3.0,
    front_layers=_get_front_layers(),
    gwt_active=1.0,
    gwt_passive=5.0,
    surcharge=10.0,
    fos_passive=1.5,
)
# r["embedment_depth"], r["total_wall_length"], r["max_moment"]

# Có neo
r2 = run_anchored(
    excavation_depth=5.0,
    anchor_depth=1.0,
    front_layers=_get_front_layers(),
    fos_passive=1.5,
)
# r2["anchor_force"]

# Basal heave
h = run_basal_heave(H=5.0, cu=20.0, gamma=17.0, B=8.0)
# h["FOS"], h["passes"]
```

---

## 6. Quy ước dấu và convention

- Front = phía đào (chủ động) — cùng convention với biểu đồ áp lực đất
- Back = phía đất (bị động)
- Chiều sâu tính từ mặt đất phía chủ động (top_elev trong app)

---

## 7. Liên kết

| File | Vai trò |
|------|---------|
| `data/sheet_pile_tab.json` | Thông số mặc định, bảng Ka/Kp |
| `scripts/tab_sheet_pile.py` | Engine tính + sơ đồ |
| `23-earth-pressure-diagram.md` | Lý thuyết áp lực đất Ka/Kp |
| `22-water-pressure.md` | Áp lực nước |
