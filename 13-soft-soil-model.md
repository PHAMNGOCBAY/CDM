# 13 — Mô hình Soft Soil (SS) trong PLAXIS 2D

## 13.1 Tổng quan (§1.2.9 Material Models Manual)

| Đặc điểm | Nội dung |
|----------|---------|
| Cơ sở | Cam-Clay type (yield cap ellipse) |
| Thông số chính | λ*, κ*, ν_ur, φ, c, ψ |
| Ứng dụng đúng | Nén lún sơ cấp, sét bùn gần NC (bun set, peat) |
| Ứng dụng SAI | Hố đào, bài toán dỡ tải — **dùng HS model** |
| Drainage type | **Drained, Undrained A** (không có Undrained B, C) |
| Giấy phép | [ADV] — cần Advanced license |

> **Giới hạn quan trọng:** Soft Soil model bị hạn chế trong bài toán nén. Không phù hợp cho hố đào vì hầu như không vượt trội Mohr-Coulomb trong bài toán dỡ tải.

---

## 13.2 Thông số Nhập vào PLAXIS

### Thông số Độ cứng

| Tham số | Ký hiệu | Đơn vị | Mô tả |
|---------|---------|--------|-------|
| Modified compression index | `lambda*` (λ*) | — | Độ dốc đường nén trong không gian ε_v–ln(p') |
| Modified swelling index | `kappa*` (κ*) | — | Độ dốc đường nở trong không gian ε_v–ln(p') |
| Poisson's ratio (unload) | `nu_ur` | — | Hệ số Poisson khi dỡ tải (0.10–0.20) |

### Thông số Cường độ (Mohr-Coulomb)

| Tham số | Ký hiệu | Đơn vị | Ghi chú |
|---------|---------|--------|---------|
| Góc ma sát hữu hiệu | `phi` (φ') | ° | |
| Lực dính hữu hiệu | `c` | kN/m² | Rất nhỏ với sét bùn NC |
| Góc giãn nở | `psi` (ψ) | ° | = 0 với đất mềm |
| K0 bình thường cố kết | `K0nc` | — | = 1–sinφ' (Jaky, auto-tính) |

### Thông số Trạng thái Ban đầu

| Tham số | Ký hiệu | Đơn vị | Ghi chú |
|---------|---------|--------|---------|
| Tỷ số quá cố kết | `OCR` | — | = 1.0 cho NC, > 1 cho OC |
| Pre-overburden pressure | `POP` | kN/m² | Thay thế OCR |

---

## 13.3 Công thức Quy đổi

### Từ Thí nghiệm Cố kết (Cc, Cs, e0) — Eq.[134], [135]

$$\lambda^* = \frac{C_c}{\ln(10) \times (1+e_0)} = \frac{C_c}{2.303 \times (1+e_0)}$$

$$\kappa^* = \frac{C_s}{\ln(10) \times (1+e_0)} = \frac{C_s}{2.303 \times (1+e_0)}$$

### Từ Mô đun Cố kết Eoedref, Eurref — Eq.[134], [135]

$$\lambda^* = \frac{p_{ref}}{E_{oed}^{ref}} \quad \kappa^* = \frac{2 \cdot p_{ref}}{E_{ur}^{ref}}$$

*(pref = 100 kN/m² — áp suất tham chiếu)*

### Kiểm tra Tỷ số κ*/λ*

$$\frac{\kappa^*}{\lambda^*} \approx \frac{1}{5} \text{ đến } \frac{1}{3} \quad \text{(đất mềm điển hình)}$$

---

## 13.4 Giá trị Điển hình — Sét Bùn Tp.HCM

| Lớp đất | φ' (°) | c (kN/m²) | Cc | Cs | e0 | λ* | κ* | OCR |
|---------|--------|-----------|----|----|----|----|----|----|
| Lớp 1 Bùn sét (gần NC) | 15–18 | 3–8 | 0.50–0.80 | 0.06–0.12 | 1.20–2.00 | 0.08–0.14 | 0.010–0.025 | 1.0–1.2 |
| Lớp 2 Sét dẻo chảy | 18–22 | 5–12 | 0.30–0.50 | 0.04–0.08 | 0.90–1.40 | 0.06–0.10 | 0.010–0.018 | 1.1–1.5 |
| Lớp 5d Sét bùn | 16–20 | 5–10 | 0.40–0.65 | 0.05–0.10 | 1.10–1.70 | 0.08–0.12 | 0.012–0.022 | 1.0–1.3 |

---

## 13.5 Sử dụng Script

```python
from scripts.soft_soil_material import (
    SoftSoilMaterial, DrainageType,
    lambda_star, kappa_star, K0nc_jaky
)

# --- Từ oedometer ---
ss = SoftSoilMaterial.from_oedometer(
    name="LOP1_BUN_SET",
    Cc=0.60, Cs=0.08, e0=1.50,
    phi=18.0, c=5.0,
    gamma_unsat=15.0, gamma_sat=16.5,
    OCR=1.10,
)
ss.summary()

# --- Từ Eoed/Eur (không có Cc/Cs) ---
ss2 = SoftSoilMaterial.from_Eur_Eoed(
    name="LOP4",
    Eoed_ref=2_000, Eur_ref=10_000,
    phi=22.0, c=10.0,
    gamma_unsat=17.0, gamma_sat=18.5,
    OCR=1.20,
)

# --- Nhập trực tiếp ---
ss3 = SoftSoilMaterial(
    name="LOP5D",
    lambda_star=0.120, kappa_star=0.025,
    nu_ur=0.15, phi=20.0, c=8.0,
    gamma_unsat=16.0, gamma_sat=17.5,
    OCR=1.0,
)

# --- Dict cho PLAXIS API ---
params = ss.to_plaxis_dict()
# → {"SoilModel": "SoftSoil", "lambdaStar": 0.1042, "kappaStar": 0.0139, ...}

# --- Bảng so sánh ---
from scripts.soft_soil_material import compare_ss_materials
compare_ss_materials([ss, ss2, ss3])
```

Xem chi tiết tại [scripts/soft_soil_material.py](scripts/soft_soil_material.py).

---

## 13.6 Khi nào Chọn SS vs HS vs MC

| Tiêu chí | SS | HS | MC |
|---------|----|----|-----|
| Sét bùn NC, lún sơ cấp lớn | **Tốt nhất** | Tốt | Kém |
| Hố đào, dỡ tải | Không dùng | **Tốt nhất** | Chấp nhận |
| Phân tích ổn định (FoS) | Kém | Tốt | Tốt |
| Tốc độ tính toán | Trung bình | Chậm | Nhanh |
| Yêu cầu dữ liệu | Cc, Cs, e0 | E50, Eoed, Eur | E, φ, c |
| License | ADV | ADV | Basic |

---

## 13.7 Liên kết Tài liệu

| Vấn đề | Tài liệu |
|--------|---------|
| Linear Elastic model | [12-linear-elastic-model.md](12-linear-elastic-model.md) |
| Mô hình Mohr-Coulomb | *(xem §3 Material Models Manual)* |
| Trình tự Staged Construction (cố kết) | [07-error-convergence.md](07-error-convergence.md) |
| Đọc thông số đất từ .p2dx | [09-p2dx-file-parsing.md](09-p2dx-file-parsing.md) |
