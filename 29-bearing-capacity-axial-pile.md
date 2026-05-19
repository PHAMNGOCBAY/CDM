# 29 — Sức chịu tải cọc đóng — FHWA GEC-12 (axial_pile)

**Thư viện:** `axial_pile` (geotech-staff-engineer 4.6.0)  
**Tài liệu gốc:** FHWA GEC-12 (FHWA-NHI-16-009), Chapters 7–8  
**Phạm vi:** Cọc đóng thép/BTCT, tải dọc trục — Rs (ma sát bên) + Rp (sức kháng mũi)

---

## 1. Phương trình tổng quát

$$Q_{ult} = Q_s + Q_p = \sum f_s \cdot A_s + q_p \cdot A_p$$

| Ký hiệu | Định nghĩa | Đơn vị |
|---------|-----------|--------|
| $Q_s$ | Ma sát bên tổng | kN |
| $Q_p$ | Sức kháng mũi | kN |
| $f_s$ | Ứng suất ma sát đơn vị | kN/m² |
| $q_p$ | Ứng suất mũi cọc | kN/m² |
| $A_s$ | Diện tích xung quanh cọc | m² |
| $A_p$ | Diện tích mũi cọc | m² |

---

## 2. Cát — Phương pháp Nordlund (1963/1979)

Ma sát bên trong cát phụ thuộc vào **góc ma sát δ** giữa cọc và đất:

$$f_s = K \cdot \sigma'_v \cdot \sin(\delta)$$

Trong đó:
- $K$ = hệ số áp lực đất (tra biểu đồ FHWA theo φ và hình dạng cọc)
- $\sigma'_v$ = ứng suất hữu hiệu theo chiều sâu
- $\delta/\phi$ = 0.75–1.0 cho cọc thép; 0.65–0.80 cho BTCT

**Sức kháng mũi (cát):**

$$q_p = N_q^* \cdot \sigma'_{v,tip} \leq q_{p,max}$$

với $N_q^*$ tra từ bảng FHWA theo φ.

---

## 3. Sét — Phương pháp Tomlinson Alpha (1957)

$$f_s = \alpha \cdot S_u$$

Hệ số α tra theo:
- $S_u < 25$ kPa → α ≈ 1.0
- $25 \leq S_u \leq 75$ kPa → α giảm dần ≈ 0.5–0.9
- $S_u > 75$ kPa → α ≈ 0.4

**Sức kháng mũi (sét):**

$$q_p = 9 \cdot S_u$$

---

## 4. Phương pháp Beta — Effective Stress

Áp dụng cho cả cát và sét, tính theo ứng suất hữu hiệu:

$$f_s = \beta \cdot \sigma'_v$$

$$\beta = K_0 \cdot \tan\delta = (1 - \sin\phi) \cdot \tan(0.8\phi)$$

---

## 5. Hệ số an toàn

| Loại tải | Fs khuyến nghị |
|---------|---------------|
| Tải thường xuyên (FHWA) | 2.5 |
| Có kiểm tra động (PDA) | 2.0 |
| Có thí nghiệm tĩnh | 2.0 |

$$Q_a = Q_{ult} / F_s$$

---

## 6. So sánh FHWA vs TCVN 11823-10

| | FHWA GEC-12 | TCVN 11823-10:2017 |
|-|------------|-------------------|
| Cơ sở | Ứng suất hữu hiệu | Thí nghiệm hiện trường (CPT, SPT) |
| Cát | Nordlund | Không áp dụng (Rs=0 cát nhồi) |
| Sét | Tomlinson alpha | Alpha = 0.35 |
| Pháp lý VN | Tham khảo | **Bắt buộc** |

> **Lưu ý:** Kết quả FHWA dùng để **tham khảo và đối chiếu**. Thiết kế chính thức tại Việt Nam phải theo TCVN 11823-10.

---

## 7. Ví dụ — Cọc BTCT 350mm × 350mm, L = 15m

| Lớp | Chiều sâu | Loại đất | Qs (kN) | Phương pháp |
|-----|----------|---------|---------|------------|
| 1 | 0–5m | Cát φ=30° | 162 | Nordlund |
| 2 | 5–15m | Sét Su=50kPa | 455 | Tomlinson |

- **Q_ult** = 672.6 kN | **Q_tip** = 55.1 kN | **Q_allow (Fs=2.5)** = 269 kN

---

## Liên kết

- `data/bearing_capacity_axial_pile.json` — catalog tham số, schema đầu ra
- `scripts/bearing_capacity_tab.py` — module Streamlit
