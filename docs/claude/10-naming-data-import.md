### 10. Quy tắc Đặt tên Hố khoan (BẮT BUỘC toàn dự án)

Dự án có 3 khu vực (KE, BXN, NHC) — tên hố khoan phải luôn mang tiền tố khu vực.

| Ngữ cảnh | Tên dùng | Ví dụ |
|----------|---------|-------|
| SQLite / Python / JSON / báo cáo / bảng biểu | **`db_name`** = `ZONE-HKx` | `KE-HK1`, `NHC-BH-03` |
| Tra cứu PDF địa chất gốc | `pdf_name` | `3BOKECONGVIEN-HK1` |

**KHÔNG dùng `HK1` hay `BH-03` đơn lẻ** — gây nhầm lẫn giữa khu vực.

Mapping đầy đủ KE: `40-ke-borehole-name-mapping.md` + `data/ke_borehole_mapping.json` + `scripts/ke_borehole_mapping.py` + SQLite `borehole_name_mapping`.

Hàm tra cứu: `ke_borehole_mapping.db_name('HK8')` → `'KE-HK8'`

### 11. Quy tắc Đặt tên File, Script, Bảng SQLite theo Module

Mỗi module kỹ thuật dùng **tiền tố cố định** cho tất cả file JSON, Python, bảng SQLite và tài liệu MD liên quan — để phân biệt dữ liệu giữa các module trong cùng dự án.

| Module | Tiền tố | Ví dụ file/bảng |
| --- | --- | --- |
| Cọc ván SW — Kè KE | `ke_sw_` | `ke_sw_202605_TTHC.json`, `ke_sw_design`, `ke_sw_nt2_layers`, `ke_sw_winkler_results`, `16-ke-sw-*.md` |
| Hố khoan chung — Kè KE | `ke_` | `ke_borehole_mapping.json`, `ke_borehole_mapping.py`, `40-ke-borehole-*.md` |
| Trụ đất xi măng CDM | `cdm_` | `cdm_column_calc.py`, `tcvn9403_params.json`, `cdm_design`, `cdm_lab_results` |
| Tính lún nền | `settlement_` | `settlement_calc.py`, `settlement_scenarios`, `settlement_layers`, `settlement_time_series` |
| Khoảng cách hố khoan | `borehole_` | `borehole_spacing.py`, `borehole_distances` |
| Cọc ván SW — catalog chung | `sw_` | `sw_pile_catalog.json` |

**Quy tắc áp dụng:**

- File JSON trong `data/`: `ke_sw_*.json`, `ke_*.json`, `cdm_*.json`...
- Script Python trong `scripts/`: `ke_sw_*.py`, `ke_*.py`, `cdm_*.py`...
- Bảng SQLite trong `TTHC.sqlite`: `ke_sw_*`, `cdm_*`, `settlement_*`...
- Tài liệu MD ở root: `NN-ke-sw-*.md`, `NN-ke-*.md`, `NN-cdm-*.md`...

**KHÔNG** đặt tên chung chung như `sw_design` hay `pile_data` — thiếu tiền tố khu vực gây nhầm lẫn khi dự án mở rộng thêm khu vực BXN/NHC.

### 11b. KQTN BXN — Quy tắc Parse XLS "Full gui" (cập nhật 2026-05-22)

**Nguồn:** `BXN-3KQTN_BXN-TTHC KQTN Full gui-INPUT SQLTIE.xls` (sheet `M`, 17 hố CV-HK1..17, 360 mẫu)
**Script:** [scripts/bxn_lab_import.py](scripts/bxn_lab_import.py) — parse + ghi JSON + cập nhật SQLite (idempotent)
**Output:** `data/bxn_lab_tests_202605_TTHC.json` + SQLite `lab_tests`

**Trụ địa chất:** PDF `BXN-2-TRỤ_BXN-TTHC. Tru DC-inpu SQLITE.pdf` (68 pages, 17 HK × 4) → JSON `data/bxn_boreholes_202605_TTHC.json` (đã trích trước, không cần re-parse). Đồng bộ vào SQLite (`boreholes`, `layers`, `spt_values`) qua `scripts/project_db.py::import_bxn_boreholes()`. Vane shear: `bxn_vane_shear_202605_TTHC.json` (5 vị trí, 50 điểm) → `vst_locations` + `vane_shear_tests`.

### 11c. KQTN KE — Parser riêng vì XLS layout khác BXN (cập nhật 2026-05-22)

**Nguồn:** `KE-3 KQTN_260519 CV-TTHC HCM. KQTN Full INPUT SQLTIE.xls` (sheet `M`, 12 hố HK1..HK12, 206 mẫu)
**Script:** [scripts/ke_lab_import.py](scripts/ke_lab_import.py)
**Output:** `data/ke_lab_tests_202605_TTHC.json` + SQLite `lab_tests`

#### Column mapping KE-3 (KHÁC BXN-3, không dùng chung parser)

| Col | KE-3 | BXN-3 | Ghi chú |
| --- | --- | --- | --- |
| 18, 19, 20 | γ, γ_dry, **γ_sub g/cm³** | γ, γ_dry, γ_sub **kN/m³** | KE: × 9.81 cho γ_sub. BXN: KHÔNG nhân (đã ở kN/m³) |
| 21 | Gs | Gs | giống |
| 22 | **e0** | Sr% | KE đảo thứ tự |
| 23 | n% | n% | |
| 24 | **Sr%** | e0 | |
| 25, 26, 27, 28 | wL, wP, Ip, IS | sand emin/emax/ad/aw | KE: Atterberg ngay sau Sr |
| 29-32 | sand emax/emin/ad/aw | Atterberg | đảo |
| 38 | **c shear (kgf/cm²)** | φ shear deg | KE: c trước |
| 39 | **φ shear deg** | φ shear min | |
| 40 | **φ shear min** | c shear | KE: deg+min split |
| 41 | a1-2 cm²/kgf | a1-2 cm²/kgf | giống |
| 42, 43 | **c UU, φ UU (DDMM)** | PC, Cc | DDMM integer trong 1 cell |
| 44, 45 | **c CU, φ CU (DDMM)** | Cs, cv | |
| 46, 47 | **c'_CU, φ'_CU (DDMM)** | k, mv | effective stress |
| 48-53 | **PC, Cc, Cs, cv, kv, mv** | c CU, φ CU... | oedometer dồn cuối |
| 53 | mv | φ UU "d°m'" | BXN: chuỗi, KE: số mv |
| 54, 55 | symbol, description | giống | |

#### Quy tắc parse φ riêng

| Cột | Kiểu lưu | Cách đọc |
| --- | --- | --- |
| φ shear (col 39 + 40) | 2 cell: deg + min | `d + m/60` (giống BXN cắt phẳng) |
| φ UU (col 43), φ CU (col 45), φ'_CU (col 47) | 1 cell **DDMM integer** | `v // 100 + (v % 100)/60` |

Ví dụ: 339 → 3°39' = 3.65° ; 1612 → 16°12' = 16.2° ; 2458 → 24°58' = 24.97°.

**File legacy `data/lab_tests_202605_TTHC.json` đã xóa** — thay bằng `ke_lab_tests_202605_TTHC.json` theo §11.

**Trụ ĐC + cắt cánh + CDM KE:** PDF `KE-2`, `KE-4`, `KE-5` đã được trích xuất sang JSON (2026-05-18). Không re-parse trừ khi PDF đổi nội dung. SQLite có đầy đủ: `boreholes`(12) + `layers`(91) + `spt_values`(248) + `vst_locations`(12)/`vane_shear_tests`(110) + `cdm_tests`(12).

#### Column mapping (header bắt đầu row 4, data row 11)

| Col | Trường | Đơn vị XLS | Chuyển đổi |
| --- | --- | --- | --- |
| 1 | Borehole | `CV-HKx` | DB name = `BXN-` + raw |
| 3, 4 | depth_from, depth_to | m | giữ nguyên |
| 18, 19 | γ, γ_dry | **g/cm³** | × 9.81 → kN/m³ |
| 20 | **γ_sub (đẩy nổi)** | **đã ở kN/m³** | KHÔNG nhân 9.81 (XLS đã lưu γ_sat − γ_w) |
| 38, 39 | φ direct shear | deg + min (2 ô) | d + m/60 |
| 40 | c direct shear | kgf/cm² | × 100 → kPa |
| 41 | a1-2 | cm²/kgf (raw) | giữ raw, ghi là `a12_kPa_inv_e2` |
| 42 | PC | kgf/cm² | × 100 → kPa |
| 45 | cv | × 10⁻³ cm²/s | × 1e-3 |
| 46 | k | × 10⁻⁷ cm/s | × 1e-7 |
| 52 | c UU | kgf/cm² | × 100 → kPa (`Cu_UU_kPa`) |
| 53 | φ UU | chuỗi `"d°m'"` | regex `(\d+)°(\d+)'` → d + m/60 |

**E_kPa**: tính lại bằng công thức Eoed = (1+e0) / (a12 × 0.01) — khác giá trị E_kPa cũ trong JSON (formula cũ không rõ).

**SQLite update**: DELETE `lab_tests` cho `borehole_id` thuộc `BXN-CV-%`, INSERT lại. Giữ nguyên `BXN-HK2`, `BXN-HK3` (50+50 mẫu, khảo sát cũ khác nguồn).

### 12. DXF Import — Quy tắc Parsing theo Zone

| Zone | Tên BH trong DXF | Regex | SPT blow counts | N_value |
|------|-----------------|-------|-----------------|---------|
| NHC | `BH-03`, `BH-05`... | `^BH-\d+$` | 3 cột (N1,N2,N3) sorted+dedup | N2+N3 |
| KE | `HK1`..`HK12` | `^HK\d+$` | **4 cột**: N_prep(skip),N1,N2,N3 ordered by x | **N1+N2** (user 2026-05-20) |

**KE DXF đặc điểm:**
- Scale: 10 DXF/m (y giảm khi depth tăng), nhiều trang xếp dọc với page gap ~117 DXF
- Không có depth tick column chuẩn → dùng SPT interval y positions làm calibration
- Layer depths: float ở x_col−35..x_col−5 (giá trị = độ sâu thực, không cần filter depth_y)
- Descriptions: match MTEXT qua SPT-based depth_map (xử lý multi-page bằng scale≈10 filter)

**File tham chiếu:** [37-ke-borehole-spt-import.md](37-ke-borehole-spt-import.md) + [45-ke-spt-import.md](45-ke-spt-import.md)

**KE SPT (cập nhật 2026-05-20):** dùng file `KE-1. TRỤ_260512 CVTT-TTHC. Tru DC.dxf` (file mới, không phải `BOKE-1...` cũ). Import qua `scripts/import_ke_spt.py`, lưu vào `spt_values`. Convention N: user yêu cầu `N = N1 + N2` (sum cột 2+3, KHÁC chuẩn ASTM N=N2+N3). JSON lưu cả 2 (`N` user + `N_astm` chuẩn). Có 248 readings cho 12 HK.

