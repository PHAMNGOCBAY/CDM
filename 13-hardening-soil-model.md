# 13 — Mô hình Hardening Soil (HS) trong PLAXIS 2D

## 13.1 Tổng quan (§6, Material Models Manual 2D)

| Đặc điểm | Nội dung |
|----------|---------|
| Loại | Đàn hồi-dẻo isotropic hardening |
| Cơ sở | Quan hệ hyperbolic (Kondner, 1963) + cap yield surface |
| Stiffness | **3 moduli độc lập**: E50, Eoed, Eur — đều phụ thuộc ứng suất |
| Ứng dụng đúng | Đất cát (m≈0.5), sét (m≈1.0), hố đào sâu, tải nền |
| Drainage | Drained, Undrained A, Undrained B |
| Ưu điểm so với MC | Quan hệ ứng suất-biến dạng hyperbolic; E tăng theo chiều sâu |
| Hạn chế | Không mô hình creep, không anisotropy; tính toán chậm hơn MC |

---

## 13.2 Thông số Nhập vào PLAXIS

### Thông số Thất bại (giống Mohr-Coulomb)

| Tham số | Ký hiệu | Đơn vị | Ghi chú |
|---------|---------|--------|---------|
| Góc ma sát hữu hiệu | `phi` (φ') | ° | 0 – 45° |
| Lực dính hữu hiệu | `c` | kN/m² | |
| Góc giãn nở | `psi` (ψ) | ° | Đặt 0 khi dùng Undrained A |

### Thông số Độ cứng Cơ bản (**bắt buộc**)

| Tham số | Ký hiệu | Đơn vị | Mô tả |
|---------|---------|--------|-------|
| Secant stiffness (triaxial) | `E50ref` | kN/m² | E tại 50% qf, tại pref |
| Tangent stiffness (oedometer) | `Eoedref` | kN/m² | E tại σ1=pref, lần đầu tải |
| Unloading/reloading stiffness | `Eurref` | kN/m² | Mặc định = **3 × E50ref** |
| Power stress-dependency | `m` | — | **0.5 (cát)**, **1.0 (sét mềm)** |

### Thông số Nâng cao (dùng mặc định nếu không có thí nghiệm)

| Tham số | Mặc định | Ghi chú |
|---------|---------|---------|
| `nu_ur` (νur) | **0.20** | Poisson khi dỡ/tái tải |
| `pref` | **100 kN/m²** | Áp suất tham chiếu |
| `K0nc` | **1 − sinφ** (Jaky) | K0 khi consolidation bình thường |
| `Rf` | **0.90** | Failure ratio qf/qa — giữ mặc định |

---

## 13.3 Các Công thức Cốt lõi

### Eq.[138] — E50 phụ thuộc ứng suất

$$E_{50} = E_{50}^{ref}\left(\frac{c\cos\varphi + |\sigma_3'|\sin\varphi}{c\cos\varphi + p_{ref}\sin\varphi}\right)^m$$

### Eq.[140] — Eur phụ thuộc ứng suất

$$E_{ur} = E_{ur}^{ref}\left(\frac{c\cos\varphi + |\sigma_3'|\sin\varphi}{c\cos\varphi + p_{ref}\sin\varphi}\right)^m$$

### Eq.[139] — Ứng suất lệch giới hạn (Mohr-Coulomb)

$$q_f = \frac{2\sin\varphi}{1-\sin\varphi}\left(c\cot\varphi + |\sigma_3'|\right)$$

### Quy đổi từ Cc / Cs (đất mềm — Eq.[153]-[155])

$$E_{oed}^{ref} = \frac{2.3(1+e_{init}) \cdot p_{ref}}{C_c}$$

$$E_{ur}^{ref} \approx \frac{2.3(1+e_{init})(1+\nu_{ur})(1-2\nu_{ur}) \cdot p_{ref}}{(1-\nu_{ur}) \cdot C_s \cdot K_0^{nc}}$$

$$E_{50}^{ref} = 1.25 \cdot E_{oed}^{ref} \quad \text{[Eq.155, mặc định cho đất mềm]}$$

---

## 13.4 Giá trị Điển hình Theo Loại Đất

| Loại đất | φ (°) | c (kN/m²) | E50ref (kN/m²) | Eoedref | Eurref | m |
|---------|-------|---------|--------------|---------|--------|---|
| Cát rời (N<10) | 28 | 1 | 10,000 | 8,000 | 30,000 | 0.5 |
| Cát vừa (N=15-30) | 32 | 1 | 25,000 | 25,000 | 75,000 | 0.5 |
| Cát chặt (N>30) | 36 | 1 | 50,000 | 50,000 | 150,000 | 0.5 |
| Sét mềm / bùn sét | 22 | 5 | 3,000 | 2,000 | 9,000 | 1.0 |
| Sét cứng (OCR>4) | 26 | 20 | 30,000 | 15,000 | 90,000 | 0.8 |

**Tỷ lệ thực hành:** `Eur ≈ 3·E50` và `Eoed ≈ E50` cho cát.

---

## 13.5 Lưu ý Drainage Type

| Trường hợp | Drainage |
|-----------|---------|
| Phân tích dài hạn (cát) | **Drained** |
| Phân tích ngắn hạn đất sét (có φ', c') | **Undrained A** |
| Phân tích với su đã biết | **Undrained B** |
| Không dùng | ~~Undrained C~~ |

> Khi dùng **Undrained A** với HS: đặt `psi = 0` — dilatancy trong điều kiện không thoát nước không có nghĩa vật lý.

---

## 13.6 OCR và POP — Trạng thái Cố kết Ban đầu

- **OCR** (Overconsolidation Ratio): tỷ lệ σ'c/σ'v hiện tại — OCR=1 là NC, OCR>1 là OC
- **POP** (Pre-Overburden Pressure): áp lực tiền cố kết bổ sung [kN/m²]

Hai thông số này xác định vị trí ban đầu của cap yield surface.

---

## 13.7 Sử dụng Script

```python
from scripts.hardening_soil_material import HSMaterial, DrainageType, compare_hs_materials

# --- Nhập trực tiếp ---
soil = HSMaterial(
    name="LOP_4",
    phi=22.0, c=9.0, psi=0.0,
    E50ref=8_000, Eoedref=6_000,
    m=1.0,
    gamma_unsat=17.5, gamma_sat=18.5,
    drainage=DrainageType.UNDRAINED_A,
    OCR=1.2,
)
soil.summary(sigma3_check=100)

# --- Preset nhanh ---
cat = HSMaterial.medium_dense_sand("CAT_DAP")
set_mem = HSMaterial.soft_clay("BUN_SET", phi=22, c=5)

# --- Từ thí nghiệm nén cố kết (Cc, Cs, e0) ---
bun = HSMaterial.from_oedometer("BUN_SET",
    Cc=0.8, Cs=0.08, einit=1.5,
    phi=22, c=5.0,
    gamma_unsat=14.5, gamma_sat=16.5)
bun.summary()

# --- Kiểm tra thông số ---
warns = soil.check()

# --- Bảng so sánh ---
compare_hs_materials([cat, set_mem, bun])

# --- Dict sẵn sàng cho PLAXIS API ---
params = soil.to_plaxis_dict()
# g_i.soilmat(**params)
```

Xem chi tiết tại [scripts/hardening_soil_material.py](scripts/hardening_soil_material.py).

---

## 13.8 Liên kết Tài liệu

| Vấn đề | Tài liệu |
|--------|---------|
| Linear Elastic (bê tông, CDM) | [12-linear-elastic-model.md](12-linear-elastic-model.md) |
| Mohr-Coulomb (đất đơn giản) | §3 Material Models Manual |
| Lỗi hội tụ khi dùng HS | [07-error-convergence.md](07-error-convergence.md) |
| Kết nối PLAXIS API | [01-plaxis-api-setup.md](01-plaxis-api-setup.md) |
