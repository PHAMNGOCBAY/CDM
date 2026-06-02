### 73. Roadmap — Trang "6 vùng CDM" (Bờ kè KE)

**Phạm vi:** trang `params` (đã đổi nhãn "Thiết kế CDM" → "6 vùng CDM"), khu vực Bờ kè KE.
**Nguồn phân vùng:** SQLite `ke_cdm_zones` (6 vùng) + `ke_cdm_zone_boreholes` (18 dòng, 12 HK riêng biệt) — xem [data/ke_cdm_zoning_6zones.json](../../data/ke_cdm_zoning_6zones.json) + [scripts/ke_cdm_zoning_save.py](../../scripts/ke_cdm_zoning_save.py).
**Khởi tạo:** 2026-06-02 (user feedback).

---

#### Phân vùng 6 vùng (tham chiếu)

| Vùng | Hố khoan | Tổng dài (m) |
|:---:|---|:---:|
| 1 | KE-HK1, KE-HK11, KE-HK10 | 378.9 |
| 2 | KE-HK11, KE-HK10, KE-HK9 | 320.6 |
| 3 | KE-HK10, KE-HK9, KE-HK8 | 317.2 |
| 4 | KE-HK7, KE-HK6, KE-HK12 | 325.1 |
| 5 | KE-HK1, KE-HK2, KE-HK3 | 287.5 |
| 6 | KE-HK3, KE-HK4, KE-HK5 | 298.7 |

12 HK riêng biệt: KE-HK1..KE-HK12.

---

#### Task 1 — Lọc HK theo 6 vùng trong "Áp địa chất từ hố khoan"

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** trang "6 vùng CDM", mục "Áp địa chất từ hố khoan" — selectbox/danh sách hố khoan CHỈ hiển thị HK thuộc 6 vùng (12 HK từ `ke_cdm_zone_boreholes`). Ẩn HK ngoài 6 vùng.
- **Files đụng:** [scripts/app_cdm.py](../../scripts/app_cdm.py) — helper `_load_6zone_hk_set()`; selectbox "Hố khoan áp" lọc `_ap_bhs` theo tập 6 vùng (zone khác giữ nguyên).
- **DB đọc:** `ke_cdm_zone_boreholes` (bh_name DISTINCT), `ke_cdm_zones`.
- **Verify:** dropdown chỉ còn 12 HK KE; zone khác (BXN/NHC/QTT) không bị ảnh hưởng (fallback giữ list gốc).

#### Task 2 — Auto tính chi tiết CDM cho từng HK trong 6 vùng

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** tự động hiển thị chi tiết CDM (Lc, S1, S2, S tổng, trạng thái mũi, đạt ΔS) cho TẤT CẢ HK trong 6 vùng, GOM theo 6 vùng — KHÔNG chọn thủ công. Auto-compute §9b (không nút Build/Solve). Có selector ΔS (10/15/20/25/30/40 cm).
- **Files đụng:** [scripts/app_cdm.py](../../scripts/app_cdm.py) — helper `_load_6zone_layout()`, `_load_cdm_detail_ke()`; section "Kết quả chi tiết theo 6 vùng CDM" (bảng + bar chart Lc/S tổng per vùng + ngưỡng ΔS).
- **DB:** đọc kết quả đã tính sẵn `cdm_zone_design_results` (zone KE_*) JOIN `ke_cdm_zone_boreholes` — KHÔNG tính lại nặng (tận dụng 198 rows có sẵn).
- **Verify:** mở trang → 6 vùng × HK hiển thị ngay; 11/12 HK có kết quả; KE-HK11 báo "Thiếu dữ liệu" (H_soft NULL).
- **Tồn đọng:** KE-HK11 chưa có H_soft trong `tvtk_bh_cdm` → cần bổ sung địa tầng lớp yếu để tính CDM.

---

#### Task 3 — Engine bản tính chi tiết per HK (theo mẫu điển hình)

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** engine sinh dict đầy đủ 5 phần (thông số · S1 khối · S2 cố kết per-layer · lún theo thời gian · sức chịu tải · đệm ALiCC) cho từng HK — 1 nguồn cho UI + Word (Rule 6).
- **Files:** [scripts/cdm_detail_report.py](../../scripts/cdm_detail_report.py) — `build_hk_detail()`, `build_6zone_detail()`.
- **Nguồn mẫu:** [data/cdm_report_template_dienhinh.json](../../data/cdm_report_template_dienhinh.json) (từ PDF mẫu RXT 9 trang).
- **Headline parity:** đọc tip/Lc/S1/S2 từ `cdm_zone_design_results` (khớp bảng tổng hợp); per-layer recompute để trình bày. HK không có sẵn → fallback `find_cdm_length`.
- **Verify:** KE-HK10 (kè, force full) Lc=29.18/S1=13.12/S2=6.0/S=19.12 khớp bảng; KE-HK1/4/11 ra đủ.

#### Task 4 — UI section chi tiết per HK (gom 6 vùng)

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** section "Bản tính chi tiết từng hố khoan" trong trang 6 vùng CDM — selector ΔS, gom 6 vùng, mỗi HK render 5 phần (bảng + biểu đồ Si + lún-thời gian), badge Đạt/KĐ. Auto-compute §9b, dedupe HK biên.
- **Files:** [scripts/app_cdm.py](../../scripts/app_cdm.py) — `_load_6zone_full_detail()`, `_render_cdm_hk_detail()`, `_badge_md()`.

#### Task 5 — Word builder báo cáo chi tiết

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** xuất Word .docx theo mẫu: trang bìa + tổng hợp 6 vùng + mỗi HK 5 phần (bảng + biểu đồ lún-thời gian nhúng PNG). Header/footer + trang X/Y, tiếng Việt có dấu, header bảng bold, body 12pt, không emoji.
- **Files:** [scripts/cdm_detail_report_word.py](../../scripts/cdm_detail_report_word.py) — `build_6zone_detail_docx()`; nút tải trong UI (cache theo ΔS).
- **Verify:** `BanTinhCDM_6Vung_dS30.docx` 368KB, 73 bảng, 12 HK, biểu đồ nhúng OK.

---

#### Lịch sử cập nhật

| Ngày | Hành động | Số task |
|---|---|---|
| 2026-06-02 | Khởi tạo roadmap trang "6 vùng CDM" — lọc HK + auto tính từng HK | +2 → 2 |
| 2026-06-02 | Task 1 + 2 done — lọc selectbox 6 vùng + section kết quả gom theo 6 vùng (ΔS selector, bảng + bar chart) | 2 done |
| 2026-06-02 | Đọc PDF mẫu điển hình → lưu template JSON; thêm Task 3-5 (engine + UI + Word chi tiết per HK) | +3 → 5 |
| 2026-06-02 | Task 3-5 done — engine cdm_detail_report + UI section chi tiết + Word builder (368KB, 12 HK) | 5 done |
