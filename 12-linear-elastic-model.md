# 12 — Mô hình Linear Elastic (LE) trong PLAXIS 2D

## 12.1 Tổng quan (§1.2.1 Material Models Manual)

| Đặc điểm | Nội dung |
|----------|---------|
| Cơ sở | Định luật Hooke đẳng hướng |
| Thông số | 2 (E và ν) |
| Giới hạn bền | **Không có** — ứng suất không bị chặn |
| Ứng dụng đúng | Tường BTCT, đá nguyên khối, CDM, cọc bê tông |
| Ứng dụng sai | Đất (hành vi phi tuyến mạnh) |
| Drainage type | Drained, Undrained A, Undrained C, **Non-porous** |

> Với kết cấu cứng (tường bê tông, cọc): chọn **Non-porous** để loại trừ áp lực nước lỗ rỗng khỏi phần tử.

---

## 12.2 Thông số Nhập vào PLAXIS

| Tham số | Ký hiệu | Đơn vị | Ghi chú |
|---------|---------|--------|---------|
| Young's modulus | `Eref` | kN/m² | **Bắt buộc** |
| Poisson's ratio | `nu` (ν) | — | **Bắt buộc** |
| Dung trọng không bão hòa | `gammaUnsat` | kN/m³ | |
| Dung trọng bão hòa | `gammaSat` | kN/m³ | |
| Stiffness increment theo độ sâu | `Einc` | kN/m²/m | Tùy chọn [Eq.33] |
| Cao độ tham chiếu cho Einc | `yref` | m (+lên) | Khi dùng Einc |

### Công thức phụ trợ — Eq.[31]

$$G = \frac{E}{2(1+\nu)} \quad K = \frac{E}{3(1-2\nu)} \quad E_{oed} = \frac{(1-\nu)E}{(1+\nu)(1-2\nu)}$$

> G, K, Eoed không nhập — PLAXIS tính tự động và hiển thị như thông số phụ.

### Độ cứng tuyến tính theo độ sâu — Eq.[33]

$$E(y) = E_{ref} + (y_{ref} - y) \cdot E_{inc} \quad \text{khi } y < y_{ref}$$

- Trên `yref`: E = Eref (không đổi)
- Dưới `yref`: E tăng theo chiều sâu

---

## 12.3 Giá trị Thực tế Thường Dùng

### Bê tông (ACI 318: Ec = 4,700√f'c MPa)

| f'c (MPa) | Ec (MPa) | **Ec (kN/m²) — nhập PLAXIS** | ν |
|-----------|---------|------------------------------|---|
| 25 | 23,500 | 23,500,000 | 0.20 |
| 30 | 25,743 | 25,743,000 | 0.20 |
| 40 | 29,725 | 29,725,000 | 0.20 |
| 60 | 36,401 | 36,401,000 | 0.15 |
| **70** | **43,628** | **43,628,130** | 0.15 |

### CDM (Cement Deep Mixing)

| Thông số | Giá trị điển hình |
|---------|-----------------|
| E (kN/m²) | 80,000 – 300,000 (= 80–300 MPa) |
| ν | 0.25 – 0.35 |
| Drainage | Drained |

*Dự án L=25M-HKT8-SW840: CDM E = 104,240 kN/m²*

### Đá gốc

| Loại đá | E (MPa) | ν |
|---------|---------|---|
| Đá vôi mềm | 5,000–20,000 | 0.25 |
| Đá granit cứng | 30,000–80,000 | 0.20 |

---

## 12.4 Lỗi Đơn Vị Phổ Biến

```python
# SAI — nhập MPa thẳng vào PLAXIS
E = 43_628   # kN/m² ← thực ra chỉ là 43.6 MPa, thiếu 1,000 lần!

# ĐÚNG — luôn nhân × 1,000
E_MPa   = 43_628.13
E_PLAXIS = E_MPa * 1_000   # = 43,628,130 kN/m²
```

---

## 12.5 Sử dụng Script

```python
from scripts.linear_elastic_material import LEMaterial, DrainageType, mpa_to_knm2

# --- Tường BTCT f'c=30MPa ---
wall = LEMaterial.concrete_wall("TuongBTCT", d_m=0.60, fc_MPa=30)
wall.summary()

# --- CDM (Cement Deep Mixing) ---
cdm = LEMaterial.cdm("CDM", E_kNm2=104_240, nu=0.30, gamma=17.0)
cdm.summary()

# --- Nhập trực tiếp ---
mat = LEMaterial(
    name="DaGoc",
    E_kNm2=mpa_to_knm2(500),   # 500 MPa → 500,000 kN/m²
    nu=0.25,
    gamma_unsat=25.0,
    gamma_sat=25.0,
    Einc_kNm2_per_m=50_000,
    yref_m=-10.0,
    drainage=DrainageType.DRAINED,
)
mat.summary()

# --- Dict sẵn sàng cho PLAXIS API ---
plaxis_params = mat.to_plaxis_dict()
# → {"MaterialName": "DaGoc", "SoilModel": "LinearElastic", ...}

# --- Bảng so sánh nhiều vật liệu ---
from scripts.linear_elastic_material import compare_le_materials
compare_le_materials([wall, cdm, mat])
```

Xem chi tiết tại [scripts/linear_elastic_material.py](scripts/linear_elastic_material.py).

---

## 12.6 Liên kết với Tài liệu Khác

| Vấn đề | Tài liệu |
|--------|---------|
| Tính EA, EI từ mặt cắt bê tông | [10-plate-properties.md](10-plate-properties.md) |
| Cọc ván bê tông SW (BETON 6) | [11-sw-pile-database.md](11-sw-pile-database.md) |
| Đọc thông số LE từ .p2dx | [09-p2dx-file-parsing.md](09-p2dx-file-parsing.md) |
