# 30 — Kè cọc bản consolle / có neo — USACE EM 1110-2-2504 (sheet_pile)

**Thư viện:** `sheet_pile` (geotech-staff-engineer 4.6.0)  
**Tài liệu gốc:** USACE EM 1110-2-2504 (CWALSHT methodology)  
**Phạm vi:** Tường cọc bản thép / BTCT — tính chiều sâu ngàm và moment max

---

## 1. Áp lực đất chủ động — Rankine

$$\sigma_a = K_a \cdot \gamma \cdot z - 2c\sqrt{K_a}$$

$$K_a = \tan^2\left(45° - \frac{\phi}{2}\right)$$

---

## 2. Áp lực đất bị động — Rankine

$$\sigma_p = K_p \cdot \gamma \cdot z + 2c\sqrt{K_p}$$

$$K_p = \tan^2\left(45° + \frac{\phi}{2}\right)$$

---

## 3. Tường consolle — Free Earth Support Method

Tường consolle chịu tải ngang qua áp lực đất chủ động (active) và kháng lại bởi áp lực bị động (passive) phía dưới đáy đào:

```
  ╔═══════╗  ← Đỉnh tường (+h)
  ║  FILL ║    Active pressure →
  ║  SOIL ║
──╠═══════╣── Đáy đào (0)
  ║       ║    ← Passive pressure
  ║       ║
  ╚═══════╝  ← Mũi tường
```

**Điều kiện cân bằng:**
$$\sum M_{tip} = 0 \Rightarrow \text{Tìm chiều sâu ngàm } d$$

$$\sum F_x = 0 \Rightarrow \text{Kiểm tra cân bằng ngang}$$

**Moment max:** tại điểm cắt lực cắt = 0

$$M_{max} = \text{Moment tại } z_0 \text{ nơi } V(z_0) = 0$$

---

## 4. Tường có neo — Free Earth Support (Anchored)

Thêm lực neo $T$ tại chiều sâu $z_a$:

$$T = \text{Resultant active} - \text{Resultant passive}$$

Moment max giảm đáng kể so với consolle → tiết kiệm vật liệu.

---

## 5. FOS bị động

USACE áp dụng giảm Kp bởi FOS:

$$K_{p,design} = K_p / FOS_{passive}$$

Thông thường: $FOS_{passive} = 1.5$

---

## 6. Ảnh hưởng mực nước ngầm

Áp lực nước làm giảm ứng suất hữu hiệu:

- Phía active: $\sigma'_v = \gamma_{above} \cdot z_{above} + \gamma' \cdot z_{below}$
- Áp lực nước thủy tĩnh cộng thêm vào tổng áp lực

---

## 7. Chọn tiết diện cọc bản

Moment tiêu chuẩn cho phép:

$$S_{req} = M_{max} / f_b$$

Trong đó $f_b$ = ứng suất uốn cho phép (thép: 0.6 $F_y$; BTCT: theo TCVN 5574)

---

## 8. Ví dụ — Kè consolle H_exc=3m, φ=30°, q=10 kN/m²

| Kết quả | Giá trị |
|--------|--------|
| Chiều sâu ngàm | ≈ 4.2 m |
| Tổng chiều dài tường | ≈ 7.2 m |
| M_max | ≈ 85 kNm/m |

---

## Liên kết

- `data/sheet_pile_cantilever.json` — tham số mặc định, API reference
- `scripts/sheet_pile_tab.py` — module Streamlit
- `scripts/earth_pressure.py` — Ka/Kp thủ công cho so sánh
