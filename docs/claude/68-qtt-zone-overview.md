### 68. Zone QTT — Quảng Trường Trung Tâm

**Vị trí:** Phường An Khánh, Thành phố Thủ Đức, TP. Hồ Chí Minh
**Dự án:** Hạ tầng kỹ thuật Quảng Trường Trung Tâm thành phố
**Tiền tố toàn dự án:** `qtt_*` cho mọi file/bảng/script

---

#### 1. Phạm vi + ranh giới

| Hạng mục | Giá trị |
|---|---|
| Polygon ranh giới | 15 đỉnh, SQLite `qtt_cdm_boundary` |
| Grid tính toán | 162 điểm, SQLite `qtt_elevation_points` |
| Spacing ô grid | ~20 × 20 m (auto từ spacing TB) |
| Cao độ thiết kế | Biến thiên 2.70 – 3.07 m (per điểm) |
| Cao độ tự nhiên | Biến thiên 1.09 – 4.24 m (per điểm) |
| Hệ tọa độ | VN-2000 / TM-3 106° (EPSG:9210) |

---

#### 2. Hệ thống 6 hố khoan ND

| HK | Northing (m) | Easting (m) | Cao độ TN (m) | Tổng độ sâu (m) | H_soft (m) | Source DXF |
|:---:|:---:|:---:|:---:|:---:|:---:|---|
| ND-02 | 1,191,680.41 | 605,239.03 | 1.70 | – | 24.40 | – |
| ND-03 | 1,191,670.88 | 605,340.45 | 1.89 | – | 19.80 | – |
| ND-04 | 1,191,661.33 | 605,441.00 | 1.09 | – | 29.50 | – |
| ND-05 | 1,191,736.97 | 605,446.00 | 3.20 | – | 28.10 | – |
| ND-06 | 1,191,761.04 | 605,349.44 | 4.24 | – | 28.90 | – |
| **ND-07** | **1,191,785.15** | **605,252.89** | **3.47** | **36.00** | **30.20** | **QTT-HO KHOAN ND07.dxf** |

**Lưu ý:**
- Chỉ ND-07 đã import từ DXF gốc (2026-05-29). 5 HK còn lại cần parse khi có DXF.
- H_soft tính theo `SOFT_SYMBOLS = {'1', '1b', '2', 'XMD'}`.

---

#### 3. Quy tắc parse DXF QTT (single file/HK)

**Đường dẫn DXF gốc:**
```
G:\My Drive\202605-TRUNG TAM HCM\DIA CHAT\7. QUANG TRUONG TRUNG TAM\QTT-HO KHOAN NDxx.dxf
```

**Cấu trúc DXF:**

| Phần | Vị trí | Ghi chú |
|---|---|---|
| Tiêu đề HK | y ≈ 5 | Text "ND-XX" tại x≈84 |
| Page header | y ≈ -8 | "1/2", "ND-XX" |
| Northing | y ≈ -30.51, x∈[60,100] | float |
| Easting | y ≈ -35.15, x∈[60,100] | float |
| Cao độ TN | y ≈ -40.29, x∈[60,100] | float |
| Tổng độ sâu | y ≈ -30.51, x∈[100,130] | float |
| Engineer | y ≈ -35.97, -39.77, x≈156 | tên người đo |
| Cột số TT lớp | x ≈ 29.53 | 1, 2, 3, 4... |
| Cột chiều dày lớp | x ≈ 47.63 hoặc 48.17 | float |
| **Cột cao độ đáy lớp** | **x ≈ 37.30 hoặc 38.17** | float (có dấu âm) |
| Cột chiều dày-cộng-dồn | x ≈ 57.63 hoặc 58.17 | float |
| Mô tả lớp | MTEXT tại x≈86, y theo center | UTF-8 có dấu |
| SPT depth-range | TEXT "X.XX-X.XX" tại x∈[180,210] | mỗi 2m |
| SPT N values | 4 cột x = 154 / 159 / 164 / 169 | N1, N2, N3, Total |
| Depth axis labels | x ≈ 16, "0", "1", "2"... | integer |

**Scale Y:**
- **Page 1:** y = -68.79 ↔ depth 0; scale = 10 DXF/m
- **Page 2:** y = -415.79 ↔ depth 20; scale = 10 DXF/m
- SPT row Y dịch xuống dưới depth label ~23.32 DXF (xem `y_to_depth()`)

**Quy ước SPT:**
- 4 cột = N1 (prep), N2, N3, N_total_dxf
- N theo ASTM = **N2 + N3** (verify: N_total_dxf khớp N2+N3 trong toàn DXF)

**Mapping mô tả → symbol TCVN:**

| Pattern trong description | Symbol |
|---|:---:|
| "Đá san lấp", "đá đổ" | F |
| "Bùn sét... chảy" | 1 |
| "Sét pha... dẻo mềm" | 1b |
| "Sét pha... dẻo cứng" | 3 |
| "Cát..." | 5 (review thêm) |

---

#### 4. Files dự án QTT (chuẩn tiền tố)

**Python (`scripts/qtt_*.py`):**

| File | Vai trò |
|---|---|
| `qtt_zone_data.py` | Central loader — boreholes, layers, grid, boundary từ SQLite |
| `qtt_dxf_import.py` | Engine import DXF (tổng quát, không chỉ ND-07) |
| `qtt_cdm_analysis.py` | Thuật toán quyết định Lc CDM (§62) |
| `qtt_cdm_report.py` | Word docx builder (§62) |
| `qtt_export_dxf.py` | DXF zoning map (§66.2b) |
| `pages/qtt_page.py` | UI tab QTT (page id = "qtt") |

**JSON (`data/qtt_*.json`):**

| File | Nội dung |
|---|---|
| `qtt_zone_meta.json` | Metadata zone (vị trí, polygon, 6 HK summary) |
| `qtt_nd07_borehole.json` | Snapshot ND-07 (header + 4 layers + 16 SPT) |
| `qtt_cdm_criteria.json` | Tiêu chí thiết kế (cấp đường × công trình × v × ΔS) — §62 |

**SQLite tables (`qtt_*`):**

| Bảng | Hàng | Nguồn |
|---|:---:|---|
| `qtt_elevation_points` | 162 | Grid points |
| `qtt_cdm_boundary` | 15 | Polygon đỉnh ranh giới |
| `qtt_zone_summary` | 1 | Aggregate metadata zone |

**Bảng đa-zone có dữ liệu QTT (vẫn không có tiền tố qtt_):**

| Bảng | Hàng QTT | Mục đích |
|---|:---:|---|
| `boreholes` | 6 | Tất cả HK |
| `layers` | varies | Địa tầng |
| `spt_values` | 16 (ND-07) + ... | SPT |
| `tvtk_bh_cdm` | 6 | Selected HK cho CDM |
| `cdm_qtt_grid_lc` | 648 (4 ΔS × 162 grid) | Grid Lc per ΔS |
| `cdm_zone_design_results` | 24 (4 ΔS × 6 HK) | Lc per HK QTT |
| `cdm_zone_smoothness_results` | x | Cặp HK smoothness |
| `cdm_zone_s_lc_curves` | x | S(Lc) sweep |
| `cdm_plaxis_model_recipes` | 1 row 'QTT' | PLAXIS recipe |

**MD (`docs/claude/`):**

| File | Section |
|---|---|
| `68-qtt-zone-overview.md` (file này) | §68 — Zone metadata + parse rules |
| `62-qtt-cdm-decision-algorithm.md` | §62 — Thuật toán Lc QTT |
| `63-multi-zone-cdm-analysis.md` | §63 — QTT trong context 5 zone |

---

#### 5. UI Tab QTT — `pages/qtt_page.py`

**Page id:** `"qtt"` · **Nav label:** "Zone QTT"

**Cấu trúc 5 section trải phẳng:**

| Section | Nội dung |
|---|---|
| A | Tổng quan zone (vị trí, ranh giới, 6 HK trên bản đồ) |
| B | Bảng 6 HK + cao độ + H_soft + verdict source DXF |
| C | Polygon + grid 162 điểm (Plotly 2D + matplotlib) |
| D | Local stratigraphy viewer (chọn HK → hiển thị 4-5 lớp + SPT) |
| E | Import DXF mới (upload + parse + verify trước khi commit) |

---

#### 6. Lệnh thường dùng

```bash
# Import 1 HK QTT từ DXF
python scripts/qtt_dxf_import.py --bh ND-07 --dxf "G:\...\QTT-HO KHOAN ND07.dxf"

# Tính Lc + xuất Word
python scripts/qtt_cdm_analysis.py
python -c "from qtt_cdm_report import build_qtt_decision_docx; ..."

# Xuất DXF zoning map
python scripts/qtt_export_dxf.py

# Rebuild PLAXIS recipe
python -c "from plaxis_serializer import build_plaxis_model_recipe; build_plaxis_model_recipe('QTT')"
```
