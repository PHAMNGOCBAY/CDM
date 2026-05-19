# Hệ thống AI Tính Sức Chịu Tải Cọc Theo Đất Nền

> Tài liệu kỹ thuật và công cụ Python tính toán sức chịu tải cọc ván bê tông SW (BETON 6) theo phương pháp địa kỹ thuật — tích hợp Claude AI Copilot.

---

## Mục lục Tài liệu

| File | Nội dung |
|------|----------|
| [CLAUDE.md](CLAUDE.md) | System instructions cho Claude AI Copilot — quy tắc đơn vị, ưu tiên đọc file |
| [11-sw-pile-database.md](11-sw-pile-database.md) | Catalog 22 loại cọc SW BETON 6: Atd, Itd, Mcr, L_min/max, chu vi mặt cắt |
| [10-plate-properties.md](10-plate-properties.md) | Tính EA₁, EI, d_eq, Shear stiffness cho Plate element PLAXIS |
| [12-linear-elastic-model.md](12-linear-elastic-model.md) | Mô hình Linear Elastic: Ec theo f'c, thông số bê tông / CDM / đá |
| [13-hardening-soil-model.md](13-hardening-soil-model.md) | Mô hình HS: E50ref, Eoedref, Eurref, m — cho phân tích đất nền cọc |
| [13-mohr-coulomb-model.md](13-mohr-coulomb-model.md) | Mô hình MC: E, ν, c, φ — sơ bộ nhanh |
| [13-soft-soil-model.md](13-soft-soil-model.md) | Mô hình SS: λ*, κ* — sét bùn TPHCM gần NC |
| [14-model-selection-guide.md](14-model-selection-guide.md) | Chọn mô hình đất phù hợp theo bài toán và loại đất |

---

## Dữ liệu JSON (Tra cứu Nhanh)

| File | Nội dung |
|------|----------|
| [data/sw_pile_catalog.json](data/sw_pile_catalog.json) | 22 loại cọc SW: width, H, t, Atd, Itd, Mcr, L_min/max, perimeter |
| [data/soil_presets.json](data/soil_presets.json) | Preset đất: HS (5 loại) + SS (3 lớp TPHCM) + MC (4 loại) |
| [data/structural_presets.json](data/structural_presets.json) | Preset kết cấu: BTCT f'c=30/40/60, CDM, đá gốc |

> **Quy tắc:** Đọc `data/*.json` trước — chỉ mở `.md` / `.py` / PDF khi JSON chưa đủ.

---

## Scripts Python

| File | Chức năng chính |
|------|----------------|
| [scripts/sw_pile_database.py](scripts/sw_pile_database.py) | `lookup()`, `lookup_first()`, `list_all()` — tra cứu + tính EA1/EI/w |
| [scripts/plate_properties.py](scripts/plate_properties.py) | `PlateSection`, `SteelSheetPile`, `ConcreteWall` — tính đặc trưng Plate |

---

## Tra cứu Nhanh — Cọc SW

### Ví dụ: SW-840, f'c = 70 MPa

```python
from scripts.sw_pile_database import lookup_first, EC_FC70_KNM2

pile = lookup_first("SW-840")
pile.summary(plate_length_m=25.0)
# EA1 = 13,609,696 kN/m
# EI  =    930,822 kN.m²/m
# w   =      7.32 kN/m/m
# Mcr ≥  756.7 kN.m
```

### Thông số PLAXIS 2D (spacing = width = 0.996 m)

| Thông số | SW-840 (f'c=70) | SW-600A (f'c=70) | SW-500B (f'c=70) |
|----------|-----------------|------------------|------------------|
| EA₁ (kN/m) | 13,609,696 | 9,862,751 | 8,333,946 |
| EI (kN.m²/m) | 930,822 | 346,649 | 204,521 |
| Mcr (kN.m) | 756.7 | 500.0 | 400.0 |
| L max (m) | 29 | 22 | 20 |

---

## Phương pháp Tính Sức Chịu Tải Cọc

### Theo Đất Nền (Geotechnical)

| Phương pháp | Áp dụng | Tham số cần có |
|-------------|---------|----------------|
| **α-method** (Tomlinson) | Sét không thoát nước | su theo chiều sâu |
| **β-method** | Cát, sét thoát nước | φ', K0, δ |
| **CPT** (Bustamante) | Mọi loại đất | qc, fs theo chiều sâu |
| **TCVN 10304:2014** | Tiêu chuẩn VN | Thí nghiệm SPT hoặc CPT |

### Theo Kết cấu (Structural)

```
P_allow ≤ min(Qa_địa_kỹ_thuật, Qa_kết_cấu)

Qa_kết_cấu = 0.25 × f'c × Atd   (cọc bê tông)
           = Mcr / e              (kiểm tra nứt khi lệch tâm)
```

---

## Lưu ý Khi Dùng PLAXIS 2D

- **spacing** = width_mm / 1000 khi cọc chạm nhau (SW-120→SW-940: 0.996 m; SW-1100/1200: 1.246 m)
- **EA₁** không phải EA — là stiffness per unit width (kN/m)
- **ν = 0.15** cho bê tông cọc (xem [10-plate-properties.md](10-plate-properties.md))
- **Mcr** kiểm tra M_max < Mcr để đảm bảo cọc không nứt

---

## Thứ tự Ưu tiên Đọc File

```
1. data/*.json          → tra cứu trực tiếp
2. *.md (tài liệu)      → bảng, công thức
3. scripts/*.py         → logic, hàm
4. PDF / Excel / ảnh    → chỉ khi 1-3 chưa đủ → lưu JSON sau khi đọc
```
