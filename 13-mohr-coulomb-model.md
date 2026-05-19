# 13 — Mô hình Mohr-Coulomb (MC) trong PLAXIS 2D

## 13.1 Tổng quan (§3.3 Material Models Manual)

**Linear Elastic Perfectly-Plastic + Mohr-Coulomb failure criterion.**

| Đặc điểm | Nội dung |
|----------|---------|
| Thông số cơ bản | 5 (E, ν + c, φ, ψ) |
| Ứng dụng | Phân tích sơ bộ, lớp đất đơn giản, cát, sét không quá nhạy |
| Giới hạn | Không kể độ phụ thuộc ứng suất, không phi tuyến trước phá hoại |
| Drainage | Drained, Undrained A/B/C, Non-porous |

---

## 13.2 Thông số Nhập vào PLAXIS

### Độ cứng

| Tham số | Ký hiệu | Đơn vị | Ghi chú |
|---------|---------|--------|---------|
| Young's modulus | `Eref` | kN/m² | **Bắt buộc** |
| Poisson's ratio | `nu` (ν) | — | **Bắt buộc** |
| *(Phụ — auto)* | `G` | kN/m² | G = E/[2(1+ν)]  Eq.[81] |
| *(Phụ — auto)* | `Eoed` | kN/m² | Eoed = (1−ν)E/[(1+ν)(1−2ν)]  Eq.[82] |

> Nhập G hoặc Eoed thay thế → PLAXIS tự cập nhật E (ν không đổi).

### Sức bền

| Tham số | Ký hiệu | Đơn vị | Ghi chú |
|---------|---------|--------|---------|
| Lực dính | `cref` (c') | kN/m² | **Bắt buộc** — hoặc su khi phi=0 |
| Góc ma sát | `phi` (φ) | ° | **Bắt buộc** — dùng độ, KHÔNG radian |
| Góc giãn nở | `psi` (ψ) | ° | **Bắt buộc** — mặc định 0 |
| Tension cut-off | `TensionCutOff` | — | Mặc định **BẬT**, σt = 0 |

### Trọng lượng & Độ sâu

| Tham số | Đơn vị | Ghi chú |
|---------|--------|---------|
| `gammaUnsat` | kN/m³ | Dung trọng không bão hòa |
| `gammaSat` | kN/m³ | Dung trọng bão hòa |
| `Einc` | kN/m²/m | ΔE mỗi mét độ sâu — Eq.[85] |
| `cinc` | kN/m²/m | Δc (hoặc Δsu) mỗi mét — Eq.[86] |
| `yref` | m (+lên) | Cao độ tham chiếu cho Einc/cinc |

---

## 13.3 Công thức Chiều sâu-phụ thuộc

$$E(y) = E_{ref} + (y_{ref} - y) \cdot E_{inc} \quad [kN/m^2], \quad y < y_{ref} \quad \text{Eq.[85]}$$

$$c(y) = c_{ref} + (y_{ref} - y) \cdot c_{inc} \quad [kN/m^2], \quad y < y_{ref} \quad \text{Eq.[86]}$$

$$K_0^{nc} = \frac{\nu}{1 - \nu}$$

---

## 13.4 Chọn Drainage Type & Thông số Sức bền

| Tình huống | Drainage | c / phi | ψ |
|-----------|---------|---------|---|
| Phân tích dài hạn (đất cát, sỏi) | Drained | c', φ' | ≈φ−30 (cát dày) |
| Đất sét — phân tích hiệu quả | Undrained A | c', φ' | 0 |
| Đất sét — su trực tiếp (thứ cấp) | Undrained B | su, φ=0 | 0 |
| Đất sét — su kiểm soát hoàn toàn | Undrained C | su, φ=0 | 0 |
| Kết cấu (cứng, không thấm) | Non-porous | (không cần) | — |

> **Lưu ý Undrained A:** φ>0 với ν<0.35 → PLAXIS tự tính áp lực lỗ rỗng thặng dư.

---

## 13.5 Giá trị Khuyến nghị theo Loại Đất

### Đất sét / Bùn sét

| Thông số | Đất sét mềm | Đất sét cứng |
|---------|------------|-------------|
| E (kN/m²) | 1,000–5,000 | 10,000–30,000 |
| ν | 0.35 | 0.30 |
| c (kN/m²) | 5–20 | 20–100 |
| φ (°) | 18–25 | 20–28 |
| ψ (°) | 0 | 0 |
| γ_unsat (kN/m³) | 14–16 | 17–19 |
| γ_sat (kN/m³) | 15–17 | 18–20 |

### Cát / Cát sỏi

| Thông số | Cát rời | Cát chặt |
|---------|---------|---------|
| E (kN/m²) | 10,000–20,000 | 30,000–60,000 |
| ν | 0.30 | 0.25–0.30 |
| c (kN/m²) | 0–1 | 0–1 |
| φ (°) | 28–32 | 33–40 |
| ψ (°) | 0 | φ − 30 |
| γ_unsat (kN/m³) | 16–18 | 18–19 |
| γ_sat (kN/m³) | 19–20 | 20–21 |

### Quy tắc góc giãn nở ψ (§3.3.9)

- Đất sét: ψ = 0 (hầu hết)
- Cát thạch anh dày: ψ ≈ φ − 30°
- Khi φ < 30°: ψ = 0

---

## 13.6 Sai Lầm Phổ Biến

```python
# SAI — nhập radian thay vì độ
phi = 0.384   # ← thực ra là 0.384 radian ≈ 22°, cần kiểm tra!
# ĐÚNG
phi = 22      # độ — luôn dùng độ trong PLAXIS

# SAI — E nhập theo MPa
Eref = 20     # kN/m² ← thực ra chỉ là 0.02 kPa!
# ĐÚNG
Eref = 20_000  # kN/m² = 20 MPa

# SAI — ν quá lớn cho Undrained A/B
nu = 0.49     # → K0 = 0.98, không thực tế cho effective analysis
# ĐÚNG
nu = 0.35     # cho Undrained A (effective ν của khung hạt)

# Dấu hiệu nhận biết phi là radian:
# phi < 0.8 → thường là nhập nhầm radian, hỏi lại!
```

---

## 13.7 Sử dụng Script

```python
from scripts.mohr_coulomb_material import MCMaterial, DrainageType

# --- Đất sét mềm (Undrained A) ---
clay = MCMaterial.soft_clay(
    "BunSet", E=3000, nu=0.35, c=5, phi=22,
    gamma_unsat=15, gamma_sat=16,
    drainage=DrainageType.UNDRAINED_A,
)
clay.summary()

# --- Cát đắp (Drained) ---
sand = MCMaterial.dense_sand(
    "CatDap", E=20000, nu=0.30, phi=30,
    gamma_unsat=18, gamma_sat=20, c=1,
)
sand.summary()

# --- Đất sét với su tăng theo chiều sâu ---
su_clay = MCMaterial.undrained_su(
    "SetMeu", E=5000, su=20, su_inc=2.0, yref=0.0,
    gamma_unsat=16, gamma_sat=17,
)
su_clay.summary()

# --- Nhập thủ công đầy đủ ---
mat = MCMaterial(
    name="LOP4", E_kNm2=15000, nu=0.30,
    c_kNm2=9.0, phi_deg=22.0, psi_deg=0.0,
    gamma_unsat=17.0, gamma_sat=18.5,
    drainage=DrainageType.DRAINED,
    Einc_kNm2_per_m=500, yref_m=0.0,
)
print(mat.validate())        # kiểm tra cảnh báo
print(mat.K0_nc)             # K0 normal consolidation
print(mat.to_plaxis_dict())  # dict sẵn cho API

# --- So sánh nhiều lớp ---
from scripts.mohr_coulomb_material import compare_mc_materials
compare_mc_materials([clay, sand, su_clay, mat])
```

Xem chi tiết tại [scripts/mohr_coulomb_material.py](scripts/mohr_coulomb_material.py).

---

## 13.8 Liên kết với Tài liệu Khác

| Vấn đề | Tài liệu |
|--------|---------|
| Mô hình Linear Elastic | [12-linear-elastic-model.md](12-linear-elastic-model.md) |
| Trích xuất thông số đất từ .p2dx | [09-p2dx-file-parsing.md](09-p2dx-file-parsing.md) |
| Hội tụ, lỗi tính toán | [07-error-convergence.md](07-error-convergence.md) |
