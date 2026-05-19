# 14 — Phạm vi Áp dụng Mô hình Đất PLAXIS 2D

## 14.1 Nguồn Tài liệu

**Tài liệu gốc:** Material Models Manual 2D 2024.2 — §1.2 On the use of different models, §1.3 Limitations  
**Script:** [scripts/model_selection_guide.py](scripts/model_selection_guide.py)

---

## 14.2 Bảng Xếp hạng Tổng hợp

| Mô hình | Lic | Lún SC | Lún Thời gian | Chuyển vị Ngang | Ổn định | Động lực |
|---------|-----|--------|--------------|-----------------|---------|---------|
| **HSsmall** | Basic | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **HS** | Basic | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **SS** | ADV | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ |
| **SSC** | ADV | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ |
| **MCC** | Basic | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ |
| **NGI-ADP** | ADV | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| **MC** | Basic | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **LE** | Basic | — | — | — | — | ⭐ |

*Lún SC = Lún sơ cấp; Lic = License cần thiết*

---

## 14.3 Bài toán A — Tính Lún (Settlement)

### A1. Lún Sơ cấp (Primary Consolidation)

**Khuyến nghị theo thứ tự:**

| Thứ tự | Mô hình | Khi nào dùng | Tham số then chốt |
|--------|---------|-------------|------------------|
| 1 | **HSsmall** | Cần độ chính xác cao nhất | E50, Eoed, Eur, m, G0ref, γ0.7 |
| 2 | **HS** | Phân tích tiêu chuẩn | E50, Eoed, Eur, m |
| 3 | **SS** | Đất mềm NC rất cao (Cc lớn) | λ*, κ* |
| 4 | **MC** | Phân tích tham khảo ban đầu | E, ν |

> **Tại sao HS > MC cho lún:** MC dùng E không đổi → lún tại vùng ứng suất cao bị đánh giá SAI. HS có E tăng theo ứng suất (power law, m≈0.5–1.0) → mô tả thực tế hơn.

> **Tại sao SS tốt cho sét bùn NC:** SS dùng λ* (modified compression index) trực tiếp từ thí nghiệm cố kết → mô tả đường nén NC chính xác hơn. Nhược điểm: không có phân biệt E50 ≠ Eoed ≠ Eur.

### A2. Lún Theo Thời gian — Lún Thứ cấp (Creep)

| Thứ tự | Mô hình | Lý do |
|--------|---------|-------|
| 1 | **SSC** | Duy nhất có tham số μ* (creep index) — mô phỏng trực tiếp |
| 2 | **HS/HSsmall** | Dùng cố kết nhiều pha (Consolidation phase) — không có creep thực |
| 3 | **SS** | Không có creep, chỉ dùng khi bỏ qua lún thứ cấp |

**Thông số SSC thêm so với SS:**

| Tham số | Ký hiệu | Ý nghĩa | Xác định từ |
|---------|---------|---------|------------|
| Modified creep index | μ* | Tốc độ lún thứ cấp | Oedometer (Cα): μ* = Cα / (ln10 × (1+e0)) |
| Tham chiếu thời gian | τc | Thời gian tham chiếu | = 1 ngày (mặc định) |

---

## 14.4 Bài toán B — Tính Chuyển vị Ngang (Lateral Displacement)

### B1. Tường chắn, Hố đào sâu — Lý do HSsmall vượt trội

**Cơ chế:** Khi đào đất, vùng đất phía sau tường TỪ TRẠNG THÁI BAN ĐẦU → trải qua chu kỳ:
1. Tải ban đầu (tự trọng) → nằm ở E50 domain
2. Giải phóng ứng suất khi đào → **UNLOADING** → phải dùng Eur
3. Vùng trước tường: nén lại khi neo căng → loading lại

Lỗi MC trong bài toán ngang:
- MC dùng 1 giá trị E cho cả loading + unloading → **Eur bị đánh giá THẤP** → chuyển vị ngang tính được NHỎ HƠN thực tế
- Thực tế: Eur ≈ 3×E50 (cát) đến 5×E50 (sét) → MC underestimate lateral stiffness upon unloading

**Tham số HSsmall bổ sung cho bài toán ngang:**

| Tham số | Ý nghĩa | Giá trị điển hình |
|---------|---------|-----------------|
| `G0ref` | Mô đun cắt ở biến dạng rất nhỏ | = 2–3 × Gurref (sét) |
| `γ0.7` | Biến dạng cắt tại G = 0.7×G0 | 1×10⁻⁴ – 2×10⁻⁴ (sét) |
| `Eurref` | **Quan trọng nhất** với hố đào | = 3×E50 (cát) đến 5×E50 (sét OC) |

### B2. Quy tắc Chọn mô hình theo Độ sâu Hố đào

| Độ sâu Hố đào | Mô hình Đất | Ghi chú |
|--------------|-------------|---------|
| < 5m (sơ bộ) | MC | Nhanh, cho giá trị ước tính |
| 5–15m (thiết kế) | **HS** | Yêu cầu tối thiểu cho thiết kế |
| > 15m (quan trọng) | **HSsmall** | Chuẩn mực cho hố đào sâu |
| Có neo nhiều lớp | **HSsmall** | Bắt buộc — Eur tại từng mức neo |

### B3. Mô hình Không nên dùng cho Bài toán Ngang

| Mô hình | Lý do không dùng |
|---------|----------------|
| SS | Không mô tả unloading stiffness đúng; hầu như không vượt MC |
| SSC | Như SS + xu hướng overestimate elastic range |
| MCC | Có thể cho ứng suất cắt không thực tế ở vùng OC |

---

## 14.5 Phạm vi Áp dụng theo Loại Đất

### Sét bùn (BUN SET) — Near NC

| Bài toán | Mô hình ưu tiên | Lý do |
|---------|----------------|-------|
| Lún sơ cấp | SS hoặc HS | λ* từ Cc trực tiếp (SS); HS tổng quát hơn |
| Lún thứ cấp | SSC | Duy nhất có creep |
| Hố đào cạnh | HS hoặc HSsmall | KHÔNG dùng SS cho bài toán này |
| Ổn định nền đắp | HS (Undrained A) hoặc NGI-ADP | |

### Cát (rời đến chặt)

| Bài toán | Mô hình ưu tiên |
|---------|----------------|
| Lún | HS (m≈0.5) |
| Tường cừ thép | HSsmall |
| Ổn định mái dốc | MC hoặc HS (Drained) |

### Đá gốc / CDM / Cọc BTCT

| Loại | Mô hình |
|------|---------|
| Đá gốc | LE (Drained) |
| CDM | LE (Drained) |
| Cọc / Tường BTCT | LE (Non-porous) — là phần tử Plate |

---

## 14.6 Sử dụng Script

```python
from scripts.model_selection_guide import recommend, print_model_table, ProblemType, SoilType

# In bảng tổng hợp tất cả mô hình
print_model_table()

# Gợi ý cho bài toán cụ thể
r = recommend(problem="lateral", soil="OC_clay")
r.print_report()

# Tất cả bài toán với sét bùn NC
for prob in ["settlement", "settlement_time", "lateral", "stability"]:
    r = recommend(prob, "NC_clay")
    r.print_report()

# Truy vấn thông tin mô hình
from scripts.model_selection_guide import MODELS
hs = MODELS["HS"]
print(hs.key_params)
print(hs.limitations)
```

---

## 14.7 Checklist Trước Khi Chọn Mô hình

**Bài toán lún:**
- [ ] Đất NC hay OC? (→ quyết định có cần λ*/κ* hay E50/Eoed)
- [ ] Có lún thứ cấp quan trọng không? (→ nếu có: SSC)
- [ ] Cần phân tích cố kết theo thời gian? (→ Consolidation phase, cần γsat, k)

**Bài toán chuyển vị ngang:**
- [ ] Hố đào sâu bao nhiêu? (> 5m: HS; > 15m: HSsmall)
- [ ] Có số liệu Eur từ thí nghiệm không? (nếu không: Eur = 3–5×E50)
- [ ] Có số liệu G0 từ CPT/seismic? (→ dùng HSsmall)
- [ ] Mô hình tường/cừ: Plate element với EA, EI đúng (xem [10-plate-properties.md](10-plate-properties.md))

---

## 14.8 Liên kết Tài liệu

| Mô hình | Script | Tài liệu |
|---------|--------|---------|
| Linear Elastic | [scripts/linear_elastic_material.py](scripts/linear_elastic_material.py) | [12-linear-elastic-model.md](12-linear-elastic-model.md) |
| Soft Soil (SS) | [scripts/soft_soil_material.py](scripts/soft_soil_material.py) | [13-soft-soil-model.md](13-soft-soil-model.md) |
| Plate properties | [scripts/plate_properties.py](scripts/plate_properties.py) | [10-plate-properties.md](10-plate-properties.md) |
| Cọc SW BETON6 | [scripts/sw_pile_database.py](scripts/sw_pile_database.py) | [11-sw-pile-database.md](11-sw-pile-database.md) |
