# 17 — Nhật ký Phiên làm việc

## 2026-05-18 — BXN Trụ địa chất + Bản đồ 3D + Tự động nạp Soil Layers

**Dự án:** Trung tâm Hành chính TP.HCM — 202605-TTHC

### Công việc đã hoàn thành

| # | Công việc | Kết quả | File |
|---|----------|---------|------|
| 1 | Đọc BXN-2.pdf (hình trụ 17 HK) qua Google Drive MCP | Tọa độ VN2000 + cao độ Z + 147 lớp đất + 567 SPT | — |
| 2 | Tạo `bxn_boreholes_202605_TTHC.json` | 17 HK đầy đủ, descriptions tiếng Việt có dấu | [data/bxn_boreholes_202605_TTHC.json](data/bxn_boreholes_202605_TTHC.json) |
| 3 | Thêm `import_bxn_boreholes()` vào project_db.py | Nạp layers + SPT vào TTHC.sqlite, cập nhật elevation/coords | [scripts/project_db.py](scripts/project_db.py) |
| 4 | Rebuild TTHC.sqlite | BXN 17 HK + 147 layers + 567 SPT; tổng 36 HK | [data/TTHC.sqlite](data/TTHC.sqlite) |
| 5 | Script tái tạo JSON trụ BXN | Có thể chạy lại từ PDF text bất kỳ lúc nào | [scripts/gen_bxn_boreholes_202605_TTHC.py](scripts/gen_bxn_boreholes_202605_TTHC.py) |
| 6 | Thêm bản đồ 3D HK vào tab Geo Data (Streamlit) | Plotly 3D, màu theo lớp đất, toggle zone | [scripts/app_coc_tai_ngang.py](scripts/app_coc_tai_ngang.py) |
| 7 | Import HK → Soil Layers tự động | Selectbox HK → preview → nút "Áp dụng" nạp vào session state | [scripts/app_coc_tai_ngang.py](scripts/app_coc_tai_ngang.py) |
| 8 | Nối đáy lớp bùn + đỉnh tường cừ trên 3D | Mesh3d Delaunay + mặt phẳng cam, có tắt/mở | [scripts/app_coc_tai_ngang.py](scripts/app_coc_tai_ngang.py) |

### Trạng thái TTHC.sqlite

```
zones:              3 (KE / BXN / NHC)
boreholes:         36  (12 KE + 17 BXN + 10 NHC — có tọa độ: 7 KE + 17 BXN)
layers:           237  (90 KE + 147 BXN)
spt_values:       567  (BXN — SPT mỗi 2m từ 2-70m)
vst_locations:     21  (12 KE + 5 BXN + 4 NHC)
vane_shear_tests: 208  (110 KE + 50 BXN + 48 NHC)
lab_tests:        642  (74 KE + 291 BXN + 277 NHC)
cdm_tests:         12  (KE-HK12)
```

### Còn thiếu
- NHC borehole logs: nguồn là DWG — cần xuất PDF
- BXN trụ ĐC: ngày khoan chưa có (PDF chỉ ghi `/ /2026`)

---

## 2026-05-13 — Địa chất TTHC + Thiết kế kè SW sơ bộ

**Dự án:** Trung tâm Hành chính TP.HCM — 202605-TTHC  
**Nguồn tài liệu:** `260512 CVTT-TTHC. Tru DC.pdf` (Google Drive ID: `1bDQuwmRGkcExnLeLoeSLSuU9riNTdNe_`)  
**Dữ liệu chi tiết:** [data/session_log.json](data/session_log.json)

---

### Công việc đã hoàn thành

| # | Công việc | Kết quả | File |
|---|----------|---------|------|
| 1 | Đọc PDF hình trụ hố khoan qua Google Drive MCP | 12 HK × đầy đủ lớp đất | — |
| 2 | Thống kê địa tầng 12 hố khoan HK1–HK12 | Bảng ký hiệu + mô tả + chiều dày | [15-soil-profile-202605-TTHC.md](15-soil-profile-202605-TTHC.md) |
| 3 | Lưu bộ 3 file địa tầng | JSON + MD + PY | xem §Bộ 3 file |
| 4 | Thiết kế kè SW: 2 nguyên tắc + lọc cọc | SW-840 L=29m toàn tuyến | [16-ke-sw-202605-TTHC.md](16-ke-sw-202605-TTHC.md) |
| 5 | Lưu bộ 3 file thiết kế kè | JSON + MD + PY | xem §Bộ 3 file |
| 6 | Làm rõ đơn vị TL(T) → kN | w_per_pile ≠ w_plaxis | [scripts/ke_sw_TTHC.py](scripts/ke_sw_TTHC.py) |
| 7 | Lưu memory + skill `/borehole-from-pdf` | Memory + command | `.claude/commands/` |
| 8 | Làm rõ đơn vị w_per_pile ≠ w_plaxis | Cập nhật JSON + script | [ke_sw_TTHC.py](scripts/ke_sw_TTHC.py) |
| 9 | Sinh báo cáo Word lựa chọn cọc SW | 8 mục, bảng màu, Times New Roman | [260513 BAO CAO LUA CHON COC SW-TTHC-HCM.docx](G:\My Drive\202605-TRUNG TAM HCM\KET CAU KE\260513 BAO CAO LUA CHON COC SW-TTHC-HCM.docx) |

---

### Kết quả Kỹ thuật Chính

#### Địa tầng (12 hố khoan)

| Thông số | Giá trị |
|---------|--------|
| Chiều sâu hố khoan | 36–85 m |
| Lớp sét chảy (Lớp 1) | 19.5–25.0 m |
| Hố khoan sâu nhất | HK1–HK4: 85 m |
| HK đặc biệt | HK12: lớp XMD (CDM) 11.0–23.9 m |

#### Thiết kế kè SW

| Thông số | Giá trị |
|---------|--------|
| Cao độ đỉnh kè | +2.70 m |
| L_req dao động | 23.2–28.7 m |
| Cọc đề xuất (toàn tuyến) | **SW-840, L = 29 m** |
| Cọc đề xuất HK10 | **SW-940, L = 29 m** (biên NT1 chỉ 0.3 m) |
| W_pile (SW-840, 29m) | 211.5 kN/cọc |
| NT2 RR (SW-840, HK1) | 419.9 kN ≥ W=211.5 kN — Dat (TCVN 11823-10, φ=0.35) |
| HK12 | Thiết kế riêng — XMD cản trở |

#### Lưu ý đơn vị quan trọng

```
TL catalog: đơn vị Tấn (T) — đổi sang kN: × 9.81

w_per_pile [kN/m/cọc] = TL × 9.81 / L_std     → W = w × L  (dùng NT2)
w_plaxis   [kN/m/m]   = w_per_pile / spacing    → input PLAXIS Plate

Ví dụ SW-840: 16.35T×9.81/22m = 7.29 kN/m/cọc
               7.29 / 0.996   = 7.32 kN/m/m  ← giá trị trong 11-sw-pile-database.md §11.4
```

---

### Bộ 3 File đã tạo phiên này

| Chủ đề | JSON | MD | PY |
|--------|------|----|----|
| Địa tầng TTHC | [soil_profile_202605_TTHC.json](data/soil_profile_202605_TTHC.json) | [15-soil-profile-202605-TTHC.md](15-soil-profile-202605-TTHC.md) | [soil_profile_TTHC.py](scripts/soil_profile_TTHC.py) |
| Kè SW TTHC | [ke_sw_202605_TTHC.json](data/ke_sw_202605_TTHC.json) | [16-ke-sw-202605-TTHC.md](16-ke-sw-202605-TTHC.md) | [ke_sw_TTHC.py](scripts/ke_sw_TTHC.py) |
| Nhật ký phiên | [session_log.json](data/session_log.json) | [17-session-log.md](17-session-log.md) | [project_check.py](scripts/project_check.py) |
| Báo cáo Word | — | [260513 BAO CAO LUA CHON COC SW-TTHC-HCM.docx](G:\My Drive\202605-TRUNG TAM HCM\KET CAU KE\) | [_gen_report_ke_sw_TTHC.py](scripts/_gen_report_ke_sw_TTHC.py) |

---

### Công việc Tiếp theo (Đề xuất)

- [ ] Bổ sung su thực tế (UU/CU) từ thí nghiệm → xác nhận NT2 bằng GeoMCP
- [ ] Khảo sát bổ sung khu vực HK10 (Lớp 1 dày 25m, kiểm soát thiết kế)
- [ ] Thiết kế riêng HK12: xác nhận chiều sâu XMD, cọc rút ngắn hoặc phương án khác
- [ ] Phân tích PLAXIS 2D: mô hình hố đào / kè với cọc SW-840

---

### Skill và Memory đã lưu

| Loại | File | Nội dung |
|------|------|---------|
| Skill | [.claude/commands/borehole-from-pdf.md](.claude/commands/borehole-from-pdf.md) | 7 bước đọc PDF hố khoan → 3 file |
| Memory | `memory/project_TTHC.md` | File locations, drive ID, tóm tắt 12 HK |
| Memory | `memory/feedback_borehole_workflow.md` | Quy trình 3 file + naming convention |

---

## 2026-05-14 — NT2 cọc đóng TCVN 11823-10 + bộ 3 file sức chịu tải

**Dự án:** Trung tâm Hành chính TP.HCM — 202605-TTHC  
**Dữ liệu chi tiết:** [data/session_log.json](data/session_log.json)

---

### Công việc đã hoàn thành

| # | Công việc | Kết quả | File |
|---|----------|---------|------|
| 1 | Xóa emoji trong 3 file (ke_sw, 15, 16) | Thêm §Giải thích Ký hiệu | [16-ke-sw-202605-TTHC.md](16-ke-sw-202605-TTHC.md) |
| 2 | Nghiên cứu GeoMCP (arXiv:2603.01022) | Repo chưa public — lưu pending | `memory/project_pending_tasks.md` |
| 3 | Đọc TCVN 11823-10:2017 (141 trang) | Điều 7.3.8.6, Bảng 9 — via PyPDF2 | — |
| 4 | Tạo bộ 3 file cọc đóng TCVN | JSON + MD + PY | xem §Bộ 3 file |
| 5 | Cập nhật NT2: công thức TCVN 11823-10 | 3 quy tắc mới (xem §NT2) | 6 file cập nhật |
| 6 | Kiểm tra toàn bộ file liên quan | Sạch — không còn FS=2/Qa_geo | — |
| 7 | Xác nhận cọc SW = cọc đóng → TCVN áp dụng | phi_stat=0.35 đúng | — |

---

### Bộ 3 file mới tạo phiên này

| Chủ đề | JSON | MD | PY |
|--------|------|----|----|
| Cọc đóng TCVN 11823-10 | [driven_pile_TCVN11823.json](data/driven_pile_TCVN11823.json) | [18-driven-pile-TCVN11823.md](18-driven-pile-TCVN11823.md) | [driven_pile_TCVN11823.py](scripts/driven_pile_TCVN11823.py) |

---

### Quy tắc NT2 Mới (thay thế toàn bộ công thức cũ)

**Tiêu chuẩn:** TCVN 11823-10:2017, Điều 7.3.8.6.2 — α-method (cọc đóng, sét bão hòa)

$$RR = \phi_{stat} \times (R_s + R_p) \geq W_{cọc}$$

| Quy tắc | Chi tiết |
|---------|---------|
| Bỏ qua đất đắp | L_tn = L_total − (2.70 − Z_natural) — không tính Rs đoạn đắp |
| Gồm cả Rp | Rp = 9 × su × Ap (Pt. 65) — Ap = Atd_cm2 × 100 mm² |
| phi_stat = 0.35 | Bảng 9, α-method, cọc đóng — phi là HS an toàn LRFD, không nhân FS lên W_coc |

#### Kết quả NT2 phiên này (su = 10 kN/m², thận trọng)

| Cọc | Hố khoan | L_đắp (m) | L_tn (m) | RR (kN) | W (kN) | Tỷ số | Kết quả |
|-----|---------|----------|---------|--------|--------|-------|---------|
| SW-840 | HK1 (Z=−0.800) | 3.50 | 25.50 | 420 | 211.5 | 1.99 | Dat |
| SW-840 | HK9 (Z=−2.250, xấu nhất) | 4.95 | 24.05 | 397 | 211.5 | 1.87 | Dat |
| SW-940 | HK10 (Z=−0.381) | 3.08 | 25.92 | 463 | 226.5 | 2.05 | Dat |

---

### Thông số bổ sung từ catalog SW

| Loại cọc | Ap (mm²) | Chu vi (mm) | Ghi chú |
|---------|---------|------------|---------|
| SW-840 | 310,700 | 4,595 | Ap = Atd_cm2 × 100 |
| SW-940 | 354,400 | **4,984** | Chu vi nội suy — cần xác nhận catalog |

---

### Công việc Tiếp theo

- [ ] Bổ sung su thực tế (UU/CU) từ thí nghiệm → xác nhận NT2 bằng GeoMCP
- [ ] Xác nhận chu vi SW-940 (hiện = 4,984 mm nội suy, catalog ghi null)
- [ ] Tạo `scripts/hardening_soil_material.py` (gap từ phiên 13/05)
- [ ] Quyết định GeoMCP: Phương án A (liên hệ SINTEF) hoặc B (tự xây FastMCP)
- [ ] Thiết kế riêng HK12: xác nhận chiều sâu XMD, phương án cọc
- [ ] Phân tích PLAXIS 2D: mô hình kè với cọc SW-840

---

## 2026-05-14 (tiếp) — Thư Viện Python + Giao Diện Cọc Tải Ngang

### Công việc đã hoàn thành

| # | Công việc | Kết quả | File |
|---|----------|---------|------|
| 1 | Đọc THU VIEN PYTHON.docx từ Google Drive | Phân tích 4 nhóm thư viện | Drive ID: `1KqaNuU9zd4HBA5TLDXUiTEOi21JXf6wa` |
| 2 | Cài thư viện Python 3.12 | 13 thư viện — xem §Thư viện | `python -m pip install ...` |
| 3 | Tạo bộ 3 file cọc tải ngang | JSON + MD + PY | xem §Bộ 3 file |
| 4 | Debug openpile 1.0.x API | 5 điểm nhầm phổ biến | [19-thu-vien-python.md §19.8](19-thu-vien-python.md) |
| 5 | Tạo Jupyter notebook biểu đồ inline | 5 cell: nhập liệu → biểu đồ 3 panel | [notebooks/coc_tai_ngang_openpile.ipynb](notebooks/coc_tai_ngang_openpile.ipynb) |
| 6 | Tạo Streamlit app giao diện | Chạy tại `http://localhost:8501` | [scripts/app_coc_tai_ngang.py](scripts/app_coc_tai_ngang.py) |
| 7 | Sửa biểu đồ: bỏ `invert_yaxis()` | Âm xuống dưới, dương lên trên | — |
| 8 | Cho phép nhập lớp đất sâu hơn cọc | Tự clip cho openpile, hiển thị đủ | — |

### Thư viện đã cài (Python 3.12)

| Nhóm | Thư viện | Phiên bản |
|------|----------|-----------|
| Cọc tải ngang | openseespy, openpile | 1.0.2 |
| Hệ số nền | geolysis, geofound | 0.24.1, latest |
| Dầm đàn hồi | anastruct | latest |
| Dữ liệu địa chất | bedrock-ge, geopandas, shapely, pandera | 0.3.3, 1.1.3, 2.1.2, 0.31.1 |
| Nền tảng | numpy, scipy, matplotlib, pandas | 1.26.4, 1.17.1, 3.10.9, 2.3.3 |
| Giao diện | streamlit, ipykernel | latest |

### Bộ 3 file

| File | Mô tả |
|------|-------|
| [data/python_libs_geotechnical.json](data/python_libs_geotechnical.json) | Catalog thư viện + openpile gotchas + tools |
| [19-thu-vien-python.md](19-thu-vien-python.md) | Tài liệu kỹ thuật: lý thuyết p-y, Ks, Winkler, API đúng |
| [scripts/lateral_pile_demo.py](scripts/lateral_pile_demo.py) | Demo: Ks + openpile FEM + anastruct Winkler |

### Công cụ tính toán

| Công cụ | Chạy bằng |
|---------|-----------|
| Streamlit app (giao diện nhập số liệu) | `python -m streamlit run scripts/app_coc_tai_ngang.py` |
| Jupyter notebook (biểu đồ inline VSCode) | Mở `notebooks/coc_tai_ngang_openpile.ipynb`, kernel Python 3.12 |

### openpile 1.0.x — Điểm Nhầm Phổ Biến

```
wall_thickness → wt
soil_model     → lateral_model
weight         → bắt buộc (> 10 kN/m³)
Hx             → Py  (lực ngang)
global_disp    → deflection["Deflection [m]"]
BoundaryFixation tại mũi cọc — bắt buộc để hội tụ
Địa tầng phải phủ đủ chiều dài cọc — clip lớp cuối
```

### Công việc Tiếp theo

- [ ] Bổ sung mô hình đất sét (API clay / Matlock) vào Streamlit app
- [ ] Tích hợp tính Ks tự động từ φ/SPT vào sidebar
- [ ] Xác nhận chu vi SW-940 (catalog null, hiện nội suy = 4,984 mm)
- [ ] Tạo `scripts/hardening_soil_material.py`
- [ ] Quyết định GeoMCP

---

### Memory đã cập nhật phiên này

| File | Nội dung |
|------|---------|
| `memory/project_TTHC.md` | Cập nhật NT2 formula mới |
| `memory/project_pending_tasks.md` | Cập nhật trạng thái + thêm ghi chú |
| `memory/feedback_NT2_tcvn.md` | **Mới** — Quy tắc NT2 theo TCVN 11823-10 |

---

## 2026-05-14 (tiếp) — NT2 Đa lớp + Thiết kế lại chiều dài cọc SW

**Dự án:** Trung tâm Hành chính TP.HCM — 202605-TTHC

---

### Công việc đã hoàn thành

| # | Công việc | Kết quả | File |
|---|----------|---------|------|
| 1 | Thêm hàm `check_NT2_multilayer()` + `run_all_NT2_multilayer()` | Tính Rs đúng từng lớp, alpha Tomlinson | [ke_sw_TTHC.py](scripts/ke_sw_TTHC.py) |
| 2 | Thêm hàm `print_NT2_multilayer_table()` | In bảng so sánh 11 HK đầy đủ | [ke_sw_TTHC.py](scripts/ke_sw_TTHC.py) |
| 3 | Cập nhật JSON thiết kế kè | Sửa tip_layer, thêm NT2_multilayer mỗi HK + NT2_multilayer_summary | [ke_sw_202605_TTHC.json](data/ke_sw_202605_TTHC.json) |
| 4 | Cập nhật tài liệu kỹ thuật §16.5, §16.6 | Thay công thức cũ bằng đa lớp + bảng 11 HK | [16-ke-sw-202605-TTHC.md](16-ke-sw-202605-TTHC.md) |
| 5 | Xác nhận thiết kế cọc SW-840 L=29m toàn tuyến | Tất cả HK Dat (1.86–2.17) | — |

---

### Kết quả NT2 Đa lớp — L = 29 m

Alpha-method TCVN 11823-10, phi=0.35, su theo từng lớp thực tế:

| HK | Cọc | Lớp mũi | Rs (kN) | Rp (kN) | RR (kN) | W (kN) | Ti so | NT2 |
|----|-----|---------|--------|--------|--------|--------|-------|-----|
| HK1 | SW-840 | 1b | 1,241 | 56 | 454 | 211.4 | 2.15 | Dat |
| HK2 | SW-840 | 1b | 1,202 | 56 | 440 | 211.4 | 2.08 | Dat |
| HK3 | SW-840 | 2b | 1,218 | 0 | 426 | 211.4 | 2.02 | Dat |
| HK4 | SW-840 | 2b | 1,195 | 0 | 418 | 211.4 | 1.98 | Dat |
| HK5 | SW-840 | 2b | 1,218 | 0 | 426 | 211.4 | 2.02 | Dat |
| HK6 | SW-840 | 2b | 1,195 | 0 | 418 | 211.4 | 1.98 | Dat |
| HK7 | SW-840 | 2b | 1,241 | 0 | 434 | 211.4 | 2.05 | Dat |
| **HK8** | **SW-840** | **2b** | **1,126** | **0** | **394** | **211.4** | **1.86** | **Dat** |
| HK9 | SW-840 | 2b | 1,195 | 0 | 418 | 211.4 | 1.98 | Dat |
| HK10 | SW-940 | 1b | 1,338 | 64 | 490 | 226.5 | 2.17 | Dat |
| HK11 | SW-840 | 2b | 1,204 | 0 | 421 | 211.4 | 1.99 | Dat |

**Ho kiem soat: HK8 (ti so 1.86) — Lop 1 ngan (19.5m), mui vao cat 2b nen Rp=0.**

**Cai tien so voi tinh don gian hoa (su=10 toan bo):** Phuong phap da lop co Rs cao hon vi lop 1b (su=20) gop phan. HK8 tro nen ho kiem soat NT2 thay vi HK9 (ti so da lop > don gian hoa do phan but khac nhau).

---

### Ham da them vao scripts/ke_sw_TTHC.py

| Ham | Chuc nang |
|-----|----------|
| `_alpha_tomlinson(su_kNm2)` | Noi suy alpha Tomlinson (1980) tu su kN/m2 |
| `check_NT2_multilayer(...)` | NT2 da lop: Rs tung lop, Rp lop mui, RR |
| `run_all_NT2_multilayer(L=29)` | Chay toan bo 11 HK tu soil_profile JSON |
| `print_NT2_multilayer_table()` | In bang tong hop dang text |

### Hang so da them

| Hang so | Gia tri |
|---------|--------|
| `SU_PER_LAYER` | 1:10, 1b:20, 3:35, 5:75, 5b:100 (kN/m2) |
| `SAND_LAYERS` | F, 2a, 2b, 2c, 4, 5a, 6, 7, XMD → qs=0 |

---

### Cong viec Tiep theo

- [ ] Xac nhan chu vi SW-940 (hien = 4,984 mm noi suy, catalog ghi null)
- [ ] Bo sung su thuc te (UU/CU) → xac nhan NT2 bang GeoMCP
- [ ] Tao `scripts/hardening_soil_material.py` (gap tu phien 13/05)
- [ ] Thiet ke rieng HK12: XMD, phuong an coc
- [ ] Phan tich PLAXIS 2D: mo hinh ke voi coc SW-840

---

## 2026-05-15 — Áp lực nước + Áp lực đất ngang + Streamlit v4

**Dự án:** Công cụ phân tích cọc tải ngang  
**Dữ liệu chi tiết:** [data/session_log.json](data/session_log.json)

---

### Công việc đã hoàn thành

| # | Công việc | Kết quả | File |
|---|----------|---------|------|
| 1 | Tạo bộ 3 file TCVN 11823-3 áp lực đất ngang | Ka Rankine/Coulomb, Kp, k0 NC/OC, biểu đồ 4 panel GEO5 | xem §Bộ 3 file |
| 2 | Đổi mặc định `top_elev = 2.7 m` | Cao độ đỉnh cừ chuẩn dự án TTHC | [app_coc_tai_ngang.py](scripts/app_coc_tai_ngang.py) |
| 3 | Tạo bộ 3 file áp lực nước | Hydrostatic + Terzaghi seepage, biểu đồ 3 panel | xem §Bộ 3 file |
| 4 | Thêm biểu đồ áp lực nước vào tab Results | Radio hydrostatic/seepage, 3 panel GEO5-style | [app_coc_tai_ngang.py](scripts/app_coc_tai_ngang.py) |
| 5 | Thống nhất quy ước Front/Back | Front=TRÁI=Active+fill, Back=PHẢI=Passive — nhất quán GeoData tab | Lưu memory |
| 6 | Tạo bộ 3 file biểu đồ áp lực đất (Active/Passive) | Front=Active(Ka)+fill, Back=Passive(Kp), biểu đồ 3 panel | xem §Bộ 3 file |
| 7 | Thêm biểu đồ áp lực đất vào tab Results | Radio rankine/coulomb, fill zone hatch, 3 panel | [app_coc_tai_ngang.py](scripts/app_coc_tai_ngang.py) |
| 8 | Sửa lỗi JSON `data/session_log.json` | sessions array bị đóng sai sau phiên 2, 5 phiên bị ra ngoài mảng | [session_log.json](data/session_log.json) |

---

### Bộ 3 File đã tạo phiên này

| Chủ đề | JSON | MD | PY |
|--------|------|----|----|
| Áp lực đất ngang TCVN 11823-3 | [lateral_earth_pressure.json](data/lateral_earth_pressure.json) | [21-lateral-earth-pressure-TCVN11823.md](21-lateral-earth-pressure-TCVN11823.md) | [lateral_earth_pressure.py](scripts/lateral_earth_pressure.py) |
| Áp lực nước | [water_pressure.json](data/water_pressure.json) | [22-water-pressure.md](22-water-pressure.md) | [water_pressure.py](scripts/water_pressure.py) |
| Biểu đồ áp lực đất (Active/Passive) | [earth_pressure.json](data/earth_pressure.json) | [23-earth-pressure-diagram.md](23-earth-pressure-diagram.md) | [earth_pressure.py](scripts/earth_pressure.py) |

---

### Quy ước Front/Back (thống nhất toàn app)

| Phía | Vị trí | Loại áp lực | Đất đắp | Màu |
|------|--------|------------|---------|-----|
| **Front** | **TRÁI** | **Active (Ka)** | **Có (fill)** | Tomato / #1a8cff |
| **Back** | **PHẢI** | **Passive (Kp)** | Không | Green / steelblue |

**Áp lực Net:**
- Nước: Net = Back − Front; dương → bars TRÁI (đẩy cừ về Front)
- Đất: Net = Active − Passive; dương → bars PHẢI (Active > Passive, vùng nguy hiểm)

---

### Mô hình áp lực nước

| Mô hình | Mô tả | F_net điển hình |
|---------|-------|----------------|
| Hydrostatic | Áp lực thủy tĩnh đơn giản, mỗi phía độc lập | 732 kN/m |
| Terzaghi seepage | Path = 2d, tổn thất cột nước tuyến tính mỗi phía | 384 kN/m |

---

### Streamlit App v4 — Tính năng mới

| Tab | Tính năng |
|-----|-----------|
| Geo Data | Ground level Front/Back độc lập; Fill properties (γ, φ, c); Water Level Front/Back riêng |
| Results | Biểu đồ áp lực nước (radio hydrostatic/seepage) + Biểu đồ áp lực đất (radio rankine/coulomb) |

---

### Memory đã cập nhật phiên này

| File | Nội dung |
|------|---------|
| `memory/project_lateral_pile_tools.md` | Thêm bộ 3 file áp lực nước + áp lực đất, app v4 |
| `memory/feedback_front_back_convention.md` | **Mới** — Front=TRÁI=Active+fill, Back=PHẢI=Passive |

---

### Công việc Tiếp theo

- [ ] GeoMCP server: phương án A (SINTEF) hoặc B (tự xây FastMCP)
- [ ] `scripts/hardening_soil_material.py`
- [ ] Xác nhận chu vi SW-940 (catalog null, nội suy = 4,984 mm)
- [ ] Thêm mô hình đất sét (API clay/Matlock) vào Streamlit app
- [ ] Kiểm tra biểu đồ áp lực nước + đất trong app (user tự test)

---

## 2026-05-16 — Tích hợp API Clay (Matlock 1970) + Phân tích thành phần tải trọng

### Công việc đã hoàn thành

| # | Công việc | Kết quả | File |
|---|----------|---------|------|
| 1 | Thêm cột Soil Type (Sand/Clay), Su, eps50 vào bảng địa tầng | Selectbox + NumberColumn | `app_coc_tai_ngang.py` |
| 2 | Cập nhật engine Winkler: tự chọn API_sand / API_clay theo Soil Type | Tự động phân loại | `app_coc_tai_ngang.py` |
| 3 | Khóa ô không phù hợp: Su/eps50 xám cho Sand, Phi xám cho Clay | Tách `front_sand_df` / `front_clay_df` | `app_coc_tai_ngang.py` |
| 4 | Tạo bộ 3 file API Clay Matlock | JSON + MD + PY | `api_clay_matlock.*` · `26-*.md` |
| 5 | Phát hiện & sửa lỗi `set_pointload` bị lờ đi nếu không thuộc mesh | Pass `x2mesh` chứa midpoints vào model | `app_coc_tai_ngang.py` |
| 6 | Thêm biểu đồ Phân tích thành phần tải trọng (Component Analysis) | Tách H+M, Earth, Water, Boussinesq, Fill | `app_coc_tai_ngang.py` · `27-*.md` |
| 7 | Sửa lỗi dấu phản lực: Water sign +1 (đẩy Front), Boussinesq sign -1 (đẩy Back) | Nhất quán vật lý | `app_coc_tai_ngang.py` |

---

## 2026-05-16 (tiếp) — Thêm 3 Tab mới (Bearing, Sheet Pile, Slope) + Nâng cấp biểu đồ

### Công việc đã hoàn thành

| # | Công việc | Kết quả | File |
|---|----------|---------|------|
| 1 | Đổi tên tab `Results` → `P-y` | Phản ánh đúng bản chất Winkler | `app_coc_tai_ngang.py` |
| 2 | Thêm tab `Bearing Cap.` (Sức chịu tải cọc đóng dọc trục FHWA GEC-12) | Nordlund (cát), Tomlinson (sét), Beta | `bearing_capacity_tab.py` · `29-*.md` |
| 3 | Thêm tab `Sheet Pile` (Kè cọc bản consolle / có neo USACE EM 1110-2-2504) | Free Earth Support, Rankine/Coulomb | `sheet_pile_tab.py` · `30-*.md` |
| 4 | Thêm tab `Slope Stab.` (Ổn định mái dốc Giới hạn cân bằng Bishop/Spencer) | Grid search mặt trượt nguy hiểm nhất | `slope_stability_tab.py` · `31-*.md` |
| 5 | Tích hợp cả 3 tab mới vào Streamlit App (mở rộng lên 9 tabs) | Giao diện liền mạch | `app_coc_tai_ngang.py` |
| 6 | Sửa lỗi API `capacity_vs_depth` | Đúng tham số `depth_min, depth_max, n_points` | `bearing_capacity_tab.py` |
| 7 | **Nâng cấp biểu đồ Sheet Pile** | Hiển thị chính xác bước nhảy Ka, Kp qua từng địa tầng | `sheet_pile_tab.py` |
| 8 | Làm rõ sự khác biệt bản chất giữa biểu đồ đất tab P-y và tab Sheet Pile | Bài toán Winkler lò xo điểm vs Cân bằng tĩnh học tường | Xem giải thích chi tiết |

---

### Bộ 3 file tạo mới

| Tab | JSON | MD | PY |
|-----|------|----|----|
| **Bearing Cap.** | `data/bearing_capacity_axial_pile.json` | `29-bearing-capacity-axial-pile.md` | `scripts/bearing_capacity_tab.py` |
| **Sheet Pile** | `data/sheet_pile_cantilever.json` | `30-sheet-pile-cantilever.md` | `scripts/sheet_pile_tab.py` |
| **Slope Stab.** | `data/slope_stability.json` | `31-slope-stability.md` | `scripts/slope_stability_tab.py` |

---

### Giải thích Kỹ thuật: Biểu đồ P-y vs Sheet Pile

Sự khác nhau giữa biểu đồ áp lực ngang trong tab **P-y** và tab **Sheet Pile** là hoàn toàn chính xác về mặt cơ học nền móng:

1. **Tab P-y (Cọc chịu tải ngang)**: Mô phỏng nền đất bằng hệ lò xo phi tuyến p-y (Winkler). Biểu đồ áp lực đất ở đây là phân bố ngoại lực tác dụng lên thân cọc (Front chịu Active + Fill, Back chịu Passive).
2. **Tab Sheet Pile (Tường cọc bản)**: Giải bài toán cân bằng tĩnh học tổng thể (Free Earth Support) để tìm chiều sâu ngàm $D$. Tường cọc bản chịu áp lực chủ động (Active) ở phía hố đào và kháng lại bằng áp lực bị động (Passive) ở vùng ngàm bên dưới đáy đào.

Với lần nâng cấp mới nhất trong `sheet_pile_tab.py`, biểu đồ áp lực đất trong tab Sheet Pile đã tự động nhận diện và tính toán ứng suất hữu hiệu tích lũy qua từng lớp địa tầng, thể hiện rõ các **bước nhảy (step changes)** sắc nét của $K_a$ và $K_p$ ngay tại các ranh giới địa tầng.
