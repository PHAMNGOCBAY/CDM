### 72. Roadmap QTT — 8 task mở rộng (2026-06-02)

**Phạm vi:** zone QTT (mở rộng cho 4 zone còn lại sau khi verify).
**Tracker:** file MD này là **single-source-of-truth** cho roadmap. Khi hoàn thành 1 task → tick `[x]` + ghi commit hash + ngày.
**Khởi tạo:** session 2026-06-02 (user feedback).

---

#### Task 1 — Bổ sung ΔS=15cm, ΔS=25cm vào tính Lc

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** mở rộng mảng `DELTA_S_VALUES` từ `[10, 20, 30, 40]` thành `[10, 15, 20, 25, 30, 40]` cho mọi engine + UI.
- **Files đụng:**
  - [scripts/save_cdm_zone_results.py](scripts/save_cdm_zone_results.py) — `save_zone()`
  - [scripts/qtt_cdm_analysis.py](scripts/qtt_cdm_analysis.py) — `compute_zone_cdm_lc_matrix()`
  - [scripts/pages/qtt_page.py](scripts/pages/qtt_page.py) — bảng/biểu đồ select ΔS
- **DB tác động:** `cdm_zone_design_results` thêm 2 ΔS × n_HK rows; `cdm_qtt_grid_lc` thêm 2 × 162 rows.
- **Verify:** hash LOCAL ↔ PROJECT khớp + JSON snapshot `data/s2_extension_<zone>.json` cập nhật.

#### Task 2 — Tính cho TẤT CẢ hố khoan (bỏ filter `selected`)

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** mọi engine bỏ điều kiện `WHERE tvtk_bh_cdm.selected = 1`. Hiển thị tất cả HK trong zone.
- **Lý do:** user muốn so sánh cả HK chưa được chọn (vd HK ngoài tuyến chính) để biết Lc tổng thể.
- **Files đụng:**
  - [scripts/qtt_cdm_analysis.py](scripts/qtt_cdm_analysis.py) — `_load_zone_boreholes()` bỏ filter
  - [scripts/save_cdm_zone_results.py](scripts/save_cdm_zone_results.py) — không filter
  - UI: thêm cột "Selected" để vẫn phân biệt HK trong/ngoài kế hoạch
- **Verify:** zone QTT trước 6 HK → sau ≥6 (nếu có HK ND khác chưa selected).

#### Task 3 — Trải phẳng UI (bỏ tabs/expander con)

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** mọi section A-Q trong `qtt_page.py` đặt **trực tiếp** trên trang, KHÔNG dùng `st.tabs()`, `st.expander()` (trừ help/citation).
- **Lý do:** dễ Ctrl+P in PDF + scroll liền mạch + báo cáo Word mirror UI dễ hơn.
- **Files đụng:** [scripts/pages/qtt_page.py](scripts/pages/qtt_page.py) toàn bộ.
- **Verify:** grep `st.tabs|st.expander` trong file → chỉ còn dạng help.

#### Task 4 — PA-A: Tăng q_u + giảm spacing s đạt ΔS=10cm

- [x] **Status:** completed engine + UI (2026-06-02). Chỉ QTT có data; 4 zones còn lại pending Task T.
- **Mục tiêu:** với mỗi HK + zone, tìm cặp `(q_u, s)` tối thiểu chi phí mà $S_{total} \le 10$ cm (cấp cao tốc gần mố cầu).
- **Sweep grid:** q_u ∈ {800, 1000, 1200, 1500, 2000} kPa × s ∈ {1.2, 1.4, 1.6, 1.8, 2.0} m.
- **Engine mới:** `scripts/cdm_alternative_strength.py` — hàm `find_alt_qu_spacing(bh, target_dS=10, ...)`.
- **DB mới:** `qtt_cdm_alternative_strength` (PK: zone_code, bh_name, q_u_kPa, spacing_m).
- **UI:** bảng + heatmap chi phí vs (q_u, s); highlight cell tối ưu.
- **Cost:** dùng [data/cost_model.json](data/cost_model.json) — `dem_cat_xm_per_kPa` + tính khối lượng cọc theo spacing.

#### Task 5 — PA-B: Lcoc ≤ 30m → tìm (q_u, s) tối ưu

- [x] **Status:** completed engine + UI (2026-06-02). Engine + UI ready, DB 0 rows — sweep pending Task T.
- **Mục tiêu:** với constraint Lcoc ≤ 30m (vd hạn chế thiết bị thi công), tìm `(q_u, s)` cho mỗi HK + zone đạt ΔS=30cm (cao tốc thông thường).
- **Engine mới:** `scripts/cdm_alternative_Lmax.py` — `find_alt_under_Lmax(bh, L_max=30, target_dS=30, ...)`.
- **DB mới:** `qtt_cdm_alternative_Lmax` (PK: zone_code, bh_name, L_max_m, delta_S_cm).
- **UI:** bảng (zone, HK, L_max, q_u_opt, s_opt, ΔS_đạt, chi phí) + biểu đồ Pareto.

#### Task 6 — Sơ đồ minh họa S1, S2, Lcoc

- [x] **Status:** completed (2026-06-02) — `scripts/cdm_schematic.py` + SVG `plaxis_out/schematic_S1_S2_Lcoc.svg`
- **Mục tiêu:** vẽ schematic matplotlib (SVG output) thể hiện:
  - Cọc CDM (Lcoc, D)
  - Khối gia cố CDM (S1 — lún đàn hồi mũi tên nén trong khối)
  - Lớp dưới mũi (S2_clay cố kết Terzaghi, S2_sand tức thời)
  - Mực nước ngầm + cao độ tự nhiên + cao độ thiết kế + tải q
- **Engine mới:** `scripts/cdm_schematic.py` — `draw_S1_S2_Lcoc(D, s, Lcoc, H_soft, H_S2, tip_in_clay)`.
- **Vị trí UI:** section L (S(t) 15 năm) thêm preview SVG trước biểu đồ; Word report section "Cơ sở lý thuyết".

#### Task 7 — Biểu đồ phân tích NGAY dưới mỗi bảng

- [x] **Status:** completed (2026-06-02) — helper `scripts/core/chart_after_table.py` + áp dụng B2/B3/O2
- **Mục tiêu:** mọi `_render_bold_table(df)` trong `qtt_page.py` phải kèm 1 biểu đồ phân tích (bar/line/heatmap) ngay sau, KHÔNG tách section.
- **Quy tắc:** bảng có cột số → bar chart hoặc heatmap; bảng có depth/elev → profile chart; bảng so sánh PA → grouped bar.
- **Helper mới:** `scripts/core/chart_after_table.py` — `auto_chart_for(df, kind="auto") -> plotly.Figure`.

#### Task 8 — Dự báo S_no_treatment per HK

- [x] **Status:** completed (2026-06-02) — `save_no_treat_predict.py` + UI B2 + mở rộng Task U/W/X/Y
- **Mục tiêu:** với mỗi HK, tính & hiển thị:
  - **S∞ (no treat)** — tổng lún cố kết theo chiều dày bùn (Cc/Cs/e0 lab), KHÔNG xử lý.
  - **S(15 năm, no treat)** — qua U(T) Terzaghi với Cv lab + H_drain = H_soft / 2 (cố kết 2 mặt).
- **Engine mở rộng:** [scripts/settlement_calc.py](scripts/settlement_calc.py) — đã có `calc_settlement_from_db` + `calc_time_series` cho no_treat.
- **DB mới:** `cdm_zone_no_treat_predict` (PK: zone_code, bh_name; cols: S_inf_cm, S_15y_cm, U_15y).
- **UI section mới:** vd "G2. Dự báo lún khi KHÔNG xử lý" trước section H so sánh các phương án.

---

#### Quy tắc cập nhật roadmap

1. **Mỗi lần user thêm task** → bổ sung mục mới ở cuối + entry trong "Lịch sử cập nhật" cuối file.
2. **Hoàn thành 1 task** → tick `[x]` + ghi commit hash + ngày.
3. **Bỏ task** → strikethrough + ghi lý do.
4. **Roadmap này KHÔNG được xóa** — chỉ append.
5. **Memory file** [feedback-persist-todos-longterm.md](../../memory/feedback-persist-todos-longterm.md) giữ rule áp dụng cho mọi todo mới.

---

#### Task M — Heatmap Lc 162 điểm grid QTT × 6 ΔS

- [~] **Status:** partial — UI auto-detect 6 ΔS đã làm; DB hiện chỉ 4 ΔS, ΔS=15/25 pending Task T. **Mở rộng Task BB** sẽ render 6 heatmap song song.
- **Mục tiêu:** re-compute `cdm_qtt_grid_lc` cho 6 mức ΔS (10/15/20/25/30/40 cm) thay vì 4 mức cũ. Mỗi mức = 162 điểm × Lc, tip_depth, S_total.
- **Files đụng:**
  - [scripts/save_cdm_zone_results.py](scripts/save_cdm_zone_results.py) — `save_qtt_grid_lc()` default 6 ΔS
  - [scripts/pages/qtt_page.py](scripts/pages/qtt_page.py) — section M heatmap thêm selector 6 ΔS
- **DB:** `cdm_qtt_grid_lc` 648 → 972 rows (162 × 6).
- **Verify:** heatmap render đủ 6 ΔS, mỗi heatmap có 162 cell.

#### Task Q — Word report Quyết định thiết kế CDM QTT cho 6 ΔS

- [x] **Status:** completed (2026-06-02) — `qtt_cdm_report.py` default 6 ΔS + UI multiselect
- **Mục tiêu:** mở rộng `qtt_cdm_report.build_qtt_decision_docx()` để xuất báo cáo cho mọi ΔS chọn (10/15/20/25 cm chi tiết). Mỗi mức ΔS có 1 chương riêng: bảng Lc per HK + heatmap + phân vùng + smoothness check.
- **Files đụng:**
  - [scripts/qtt_cdm_report.py](scripts/qtt_cdm_report.py) — `build_qtt_decision_docx(delta_S_list=[10,15,20,25])`
  - [scripts/pages/qtt_page.py](scripts/pages/qtt_page.py) — Q section: multiselect ΔS + nút xuất
- **DB:** đọc `cdm_zone_design_results`, `cdm_qtt_grid_lc`, `cdm_zone_smoothness_results`.
- **Verify:** Word docx sinh ra có 4 chương (10/15/20/25) hoặc theo selection.

#### Task T — Heavy compute on-demand (pending)

- [ ] **Status:** pending — chỉ chạy khi user yêu cầu, KHÔNG block UI hiện tại
- **Mục tiêu:** hoàn thành phần compute nặng còn lại sau khi UI sẵn sàng:
  - **PA-A/PA-B cho 4 zones còn lại** (BXN/NHC/KE_park/KE_levee) — ước tính ~30 min
    - Lệnh: `python scripts/cdm_alternative_design.py`
  - **Grid 162 × 6 ΔS** cho QTT (mở rộng cdm_qtt_grid_lc từ 4 → 6 ΔS) — ước tính ~20 min
    - Lệnh: `python -c "from save_cdm_zone_results import save_qtt_grid_lc; save_qtt_grid_lc()"`
- **Lý do delay:** sweep find_cdm_length × số combos × số zones rất nặng. Engine + UI đã ready — chạy on-demand khi user xác nhận.
- **Verify khi xong:**
  - `qtt_cdm_alternative_strength` có rows cho all 5 zones
  - `qtt_cdm_alternative_Lmax` có rows cho all 5 zones
  - `cdm_qtt_grid_lc` có 6 ΔS (15, 25 added)
- **UI tác động:** B2/O2/O3/M sẽ tự render đầy đủ khi data có.

#### Task CC — Phương án 2 phân vùng QTT theo tuyến/cặp HK

- [ ] **Status:** in_progress
- **Mục tiêu:** thêm phương án phân vùng thiết kế CDM thay thế (so sánh với phương án quantile hiện tại trong section O), dựa trên cấu trúc hình học HK ND.
- **Cấu trúc 6 HK ND QTT (cao độ tự nhiên):**

  | HK | Northing | Easting | TN (m) | H_soft |
  |---|---|---|:---:|:---:|
  | ND-02 | 1191680 | 605239 | 1.70 | 24.4 |
  | ND-03 | 1191670 | 605340 | 1.89 | 28.0 |
  | ND-04 | 1191661 | 605441 | 1.09 | 29.5 |
  | ND-05 | 1191736 | 605446 | 3.20 | 30.1 |
  | ND-06 | 1191761 | 605349 | 4.24 | 28.9 |
  | ND-07 | 1191785 | 605253 | 3.47 | 30.2 |

- **Phương án 2a — Phân vùng theo 2 tuyến song song (Northing strips):**
  - **Tuyến Nam** (N≈1191670): ND-02, ND-03, ND-04 — Northing thấp
  - **Tuyến Bắc** (N≈1191761): ND-05, ND-06, ND-07 — Northing cao
  - Lc thiết kế per tuyến = max(Lc của 3 HK trong tuyến) tại mỗi ΔS
- **Phương án 2b — Phân vùng theo 3 cặp HK cross-tuyến:**
  - **Cặp Tây (E≈605245):** ND-02 ↔ ND-07
  - **Cặp Giữa (E≈605345):** ND-03 ↔ ND-06
  - **Cặp Đông (E≈605443):** ND-04 ↔ ND-05
  - Lc thiết kế per cặp = max(Lc của 2 HK trong cặp)
- **Tính toán:**
  - Đọc `cdm_zone_design_results` cho 6 HK × 6 ΔS
  - Tổng hợp Lc theo nhóm (5 nhóm: 2 tuyến + 3 cặp)
  - So sánh với phân vùng quantile hiện tại (4 vùng P1-P4 từ Lc grid)
- **File đụng:**
  - [scripts/pages/qtt_page.py](scripts/pages/qtt_page.py) — section mới **O4** sau O3
  - Tùy chọn DB: bảng mới `qtt_alignment_zoning` để persist
- **Hiển thị:**
  - Bảng ma trận Lc thiết kế: nhóm × 6 ΔS (5 hàng × 6 cột)
  - Bản đồ tô màu polygon nhóm trên grid (2 màu cho 2a, 3 màu cho 2b)
  - So sánh chi phí tương đối với quantile zoning
- **Why:** phương án hình học (tuyến/cặp) dễ thi công hơn quantile (vùng bất quy tắc), kỹ sư dễ dùng.

---

#### Task BB — Heatmap Lc 162 grid cho TẤT CẢ ΔS cho phép (replicate section M)

- [ ] **Status:** pending — phụ thuộc Task T (cần data grid 6 ΔS)
- **Mục tiêu:** ở section M (Heatmap Lc 162 grid), thay vì chỉ 1 heatmap cho ΔS_chọn, render **6 heatmap song song** — mỗi ΔS cho phép TCCS 41 một biểu đồ riêng:
  - ΔS = 10 cm (cao tốc gần mố cầu)
  - ΔS = 15 cm (mới, cấp 2 gần mố)
  - ΔS = 20 cm (cao tốc gần cống / cấp 2 mố)
  - ΔS = 25 cm (mới)
  - ΔS = 30 cm (cao tốc thường / cấp 2 cống)
  - ΔS = 40 cm (cấp 2 thường)
- **Format mỗi heatmap (giống ảnh demo):**
  - Polygon ranh giới đen
  - 162 điểm grid hình vuông màu theo Lc
  - 6 HK ND-02..ND-07 marker kim cương trắng + label tên
  - Colorscale Turbo (xanh đậm → đỏ đậm, scale 12-24m như demo)
  - Aspect ratio 1:1 (Easting × Northing)
  - Title `Lc tối ưu 162 điểm grid — ΔS={dS}cm`
- **Layout:** 2 cột × 3 hàng (6 heatmap) hoặc 3 cột × 2 hàng tùy không gian
- **File đụng:** [scripts/pages/qtt_page.py](scripts/pages/qtt_page.py) — section M (line ~1287)
- **Dep:** Task T phải chạy `save_qtt_grid_lc()` để có data ΔS=15 và 25 (~20 min compute)
- **Verify:** mỗi heatmap có 162 điểm vuông + 6 HK markers + polygon đen + colorbar Lc.

---

#### Task AA — Bảng thống kê S1 + S2 nền đã xử lý CDM, tất cả HK × tất cả ΔS

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** trong tab Zone QTT thêm bảng tổng hợp **S1 + S2** của nền **đã xử lý CDM** cho 6 HK × 6 ΔS = 36 ô. Đọc từ `cdm_zone_design_results` (đã có S1_cm, S2_cm).
- **Vị trí:** thêm section mới **B3** (ngay sau B2 Dự báo lún không xử lý) hoặc cuối K (đường cong) — đề xuất B3 để so sánh trực tiếp với B2 (no_treat) cùng cách hiển thị.
- **Hiển thị:** bảng wide-format:
  - Cột: HK | TN | H_soft | ΔS=10 (S1/S2/S_tot/Lc) | ΔS=15 (...) | ... | ΔS=40
  - Hoặc 3 bảng riêng: S1 matrix · S2 matrix · S_total matrix (6 HK × 6 ΔS)
- **Biểu đồ:**
  - Heatmap S_total per (HK, ΔS) — màu đỏ đậm = cao
  - Bar chart so sánh S1 vs S2 per HK tại ΔS thiết kế chọn
- **Source:** `cdm_zone_design_results.{S1_cm, S2_cm, S_total_cm, Lc_m, ok}`
- **File đụng:** [scripts/pages/qtt_page.py](scripts/pages/qtt_page.py) — thêm section B3
- **Verify:** 6 HK × 6 ΔS = 36 cell mỗi matrix; HK có Lc=0 (không đạt) → ô vàng/đỏ.

---

#### Task Z — Fix KeyError section I (đổi schema bảng so sánh d_stop)

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** sau khi Task S đổi schema bảng (`'Độ sâu đáy ảnh hưởng (m)'` → `'d_stop 1D (m)'`), update logic caption đếm HK trong phạm vi.
- **Fix:** [scripts/pages/qtt_page.py:1026](scripts/pages/qtt_page.py#L1026) — đổi sang `r.get("d_stop 1D (m)")` + thêm count cho Boussinesq.

---

#### Task Y — Mượn Cc từ HK gần nhất (§15)

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** sửa B2 sao cho 6 HK đều có S∞ + S(15y) — không HK nào để trống.
- **Lý do trống:** ND-03 (0/15 mẫu Cc), ND-04 (0/17), ND-05 (0/15) thiếu thí nghiệm nén cố kết.
- **Fix:** engine `save_no_treat_predict.py` thêm helper `_bh_has_cc()` + `_nearest_cc_in_zone()`. Nếu HK không có Cc → mượn từ HK ND gần nhất CÙNG zone có Cc, dùng làm `calc_bh` cho `calc_settlement_from_db`.
- **Cột mới DB:** `cc_source`, `cc_borrowed` (0/1), `cc_dist_m`.
- **UI B2:** thêm cột "Cc nguồn" — text "ND-XX (mượn d=Ym)" cho HK mượn.
- **Verify QTT:** ND-03/04/05 đều mượn từ ND-06 (gần nhất 91/100/135m); cả 6 HK có giá trị lún không trống.

---

#### Task X — Sửa B2: thoát nước 1 mặt (đáy bùn kín)

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** sửa engine `save_no_treat_predict.py` từ `drainage="two_way"` thành `drainage="one_way"` cho cả PA1/PA2/PA3 — phản ánh thực tế đáy bùn QTT tiếp giáp lớp sét cứng (kín, không thoát nước).
- **Tác động:** $H_{drain} = H_{soft}$ (thay vì $H_{soft}/2$) → $T_v$ giảm 4× → $U(15y)$ giảm tương ứng
- **Verify QTT:**
  - ND-02: U_15y giảm ~47% → 22%
  - ND-06: U_15y giảm ~38% → 19%
- **File đụng:** [scripts/save_no_treat_predict.py](scripts/save_no_treat_predict.py) line 137; [scripts/pages/qtt_page.py](scripts/pages/qtt_page.py) caption B2
- **Nhất quán với §28** quy ước `double_drainage=False` (cố kết 1 mặt — đáy không thấm)

---

#### Task W — Phương án 3 (PA3) lấy cao độ TK hoặc TN của khu vực QTT

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** thêm phương án PA3 — dùng cao độ thiết kế TK hoặc cao độ tự nhiên TN **của khu vực QTT** (lấy max/avg/min toàn vùng) để áp tải lên nền chưa xử lý. Tính cả **S1** (lún cục bộ dưới tải) lẫn **S2** (lún cố kết phần bùn).
- **Biến thể PA3:**
  - **PA3a:** dùng TK_max (cao nhất trong vùng) — worst case
  - **PA3b:** dùng TK_avg (trung bình) — kịch bản trung
  - **PA3c:** dùng TN_max (TN cao nhất trong QTT) cho upper bound
- **Cấu trúc lún:** với mỗi phương án, tính S = S1 + S2
  - $S_1$: lún cục bộ dưới tải (nếu có khối gia cố giả định/đệm cát), KHÔNG xử lý thực → đặt S1=0 hoặc S1=lún tức thì lớp cát
  - $S_2$: lún cố kết lớp bùn dưới mặt nền
- **File đụng:**
  - [scripts/save_no_treat_predict.py](scripts/save_no_treat_predict.py) — thêm cột PA3a/b/c × (S∞, S15y, q, H_fill)
  - [scripts/pages/qtt_page.py](scripts/pages/qtt_page.py) — section B2 thêm cột PA3
- **Verify:**
  - TK_max QTT ≈ 4.02m, TK_avg ≈ 2.97m, TK_min ≈ 2.70m
  - TN_max ≈ 4.24m (ND-06), TN_avg ≈ 2.60m, TN_min ≈ 1.09m (ND-04)

---

#### Task U — Phương án 2 (PA2) tính lún nền chưa xử lý

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** thêm phương án so sánh khi tính lún nền CHƯA xử lý, song song với PA1 hiện tại trong section B2.
- **Giả định PA2:**
  - Đất đắp được san lấp **từ cao độ 0.0 → cao độ thiết kế** (TK ≈ +2.70m)
  - Tải gây lún cho nền chưa xử lý = từ cao độ 0.0 lên mặt tự nhiên (TN)
  - $q_{PA2} = \gamma_{fill} \cdot (TN - 0.0) = \gamma_{fill} \cdot TN$ (chỉ khi TN > 0)
  - vs **PA1 (cũ):** $q_{PA1} = \gamma_{fill} \cdot (TK - TN)$ — chỉ tính phần đắp mới từ TN lên TK
- **Tác động:**
  - PA2 → load lớn hơn cho HK có TN cao (ND-05 TN=3.2m, ND-06 TN=4.24m)
  - PA1 (cũ) → có thể âm (đào) cho HK có TN > TK
  - PA2 là **upper bound** — xét trường hợp ground tích lũy lịch sử
- **File đụng:**
  - [scripts/save_no_treat_predict.py](scripts/save_no_treat_predict.py) — thêm tính PA2 + cột H_fill_pa2_m, S_inf_pa2_cm, S_15y_pa2_cm, U_15y_pa2
  - [scripts/pages/qtt_page.py](scripts/pages/qtt_page.py) — section B2 thêm cột PA2 + biểu đồ song song
- **Verify:** PA2 cho ND-06 (TN=4.24m, γ=18) → q_PA2 ≈ 76 kPa, tải nặng nhất.

---

#### Task S — Δσ dưới mũi cọc CDM phân bố theo Boussinesq

- [x] **Status:** completed (2026-06-02)
- **Mục tiêu:** thêm phương án tính tải gây lún phạm vi dưới mũi cọc CDM theo **Boussinesq** (suy giảm theo độ sâu), so sánh với phương án hiện tại (1D, Δσ = q không đổi).
- **Cơ sở lý thuyết:** tải `q` lan truyền qua khối CDM xuống mũi cọc; bên dưới mũi, phân bố ứng suất theo bài toán Boussinesq cho diện chịu tải hình vuông B×B (B = spacing s, đại diện ô đơn vị / lưới CDM):

  $$\Delta\sigma(z) = q \cdot \dfrac{B^2}{(B+z)^2}$$ (2:1 method — Boussinesq giản hoá)

  hoặc closed-form Boussinesq cho ô hình vuông tại tâm (Newmark).
- **Vị trí code:**
  - `scripts/qtt_charts.py` — thêm helper `compute_dsigma_boussinesq(B_eq, q_kPa, z_array)` + tham số `mode='boussinesq'` cho `stress_chart_with_10pct`
  - `scripts/pages/qtt_page.py` section I — vẽ thêm trace Boussinesq + 1D, có legend phân biệt
- **Vẽ:**
  - Δσ_1D (cũ) — đường thẳng đứng tại x = 40.8 kPa (không đổi theo depth)
  - Δσ_Boussinesq (mới) — đường cong giảm từ q tại tip → 10%·σ'v0 tại d_stop
  - 6 biểu đồ per HK với cả 2 đường để so sánh
  - Bảng so sánh d_stop_1D vs d_stop_Boussinesq per HK (đáy vùng ảnh hưởng theo 2 phương án)
- **Why:** phương án 1D quá thiên về an toàn (Δσ không giảm → d_stop sâu hơn → S2 lớn hơn). Boussinesq sát thực tế: tải tỏa ra theo nón → ảnh hưởng nông hơn ở phạm vi rộng.
- **Verify:** ở z=0 (mũi), Δσ_Boussinesq = q (≈40.8 kPa); ở z=B (≈1.8m), Δσ_Boussinesq ≈ 0.25q.

---

#### Task P2-fix — Trắc dọc đáy cọc CDM (ΔS=30) — sửa nhãn che khuất

- [x] **Status:** completed (2026-06-02) — `qtt_charts.py::cdm_tip_profile()` annotation tách
- **Mục tiêu:** trên trắc dọc P2 (Lcoc per HK với ΔS=30), tên hố khoan và nhãn cao độ đỉnh CDM đang chồng lên nhau. Cần tách: tên HK ở dưới đáy cọc (annotation góc dưới), cao độ đỉnh CDM ở phía trên (annotation góc trên), thêm offset Y nếu chồng cùng X.
- **Files đụng:** [scripts/pages/qtt_page.py](scripts/pages/qtt_page.py) — section P2 hoặc qtt_charts.py nếu vẽ tại đó.
- **Verify:** screenshot trắc dọc P2 — không còn nhãn chồng.

#### Task R — Thay text cũ → "trong lớp bùn" (đã hoàn thành 2026-06-02)

- [x] **Status:** completed
- **Mục tiêu:** thay tất cả chuỗi nói cọc "không xuyên hết bùn" (text cũ gây hiểu nhầm là "nổi") thành **"trong lớp bùn"**.
- **Lý do:** cọc CDM không "nổi" — chỉ là mũi cọc nằm TRONG lớp bùn (chưa xuyên xuống lớp cứng).
- **Files đã sửa (7 file, 22 occurrences):**
  - docs/claude/72-qtt-roadmap.md (4)
  - scripts/pages/qtt_page.py (5)
  - scripts/cdm_length_optimize.py (1)
  - scripts/app_cdm.py (2)
  - docs/claude/28-settlement-cdm-spacing.md (1)
  - docs/claude/63-multi-zone-cdm-analysis.md (1)
  - scripts/qtt_cdm_report.py (8)

---

#### Task self-audit — Sau mỗi task hoàn thành, kiểm tra todo + audit

- [ ] **Status:** persistent rule (không tick complete)
- **Mục tiêu:** mỗi khi mark 1 task `completed`, lập tức:
  1. Đọc lại `docs/session-audit-2026-06-02.md` (file audit phiên hiện tại)
  2. Đối chiếu với TodoWrite + roadmap §72
  3. Tự động bắt đầu task pending kế tiếp theo thứ tự ưu tiên (Wave 1→2→3)
  4. Cập nhật audit MD với entry mới (lúc xong + lúc bắt đầu task kế)
- **Why:** tránh dừng giữa chừng do quên task; user feedback 2026-06-02.

---

#### Lịch sử cập nhật

| Ngày | Hành động | Số task |
|---|---|---|
| 2026-06-02 | Khởi tạo roadmap 8 task QTT (user feedback) | +8 → 8 |
| 2026-06-02 | Hoàn thành Task 1, 2, 8 (Wave 1) — 5 zones × 6 ΔS + S_no_treat | 3 done |
| 2026-06-02 | Hoàn thành Task 6 schematic SVG | 1 done |
| 2026-06-02 | Thêm Task M (grid 162 × 6 ΔS) + Task Q (Word report multi-ΔS) + self-audit rule | +3 → 11 |
| 2026-06-02 | Thêm Task P2-fix (nhãn che khuất) + Task R (replace text) | +2 → 13 |
| 2026-06-02 | Wave 1+2+3 hoàn thành — toàn bộ 13 task done (engine + UI ready) | 13 done |
| 2026-06-02 | Thêm Task S (Boussinesq Δσ dưới mũi CDM) + Task T (heavy compute on-demand) | +2 → 15 |
| 2026-06-02 | Task S done — `compute_dsigma_boussinesq` + chart I + bảng so sánh d_stop | 14 done |
| 2026-06-02 | Task U/W done — PA2 (0.0→TK) + PA3a/b/c (TK_max/TK_avg/TN_max QTT) | 16 done |
| 2026-06-02 | Task V done — audit 6 issues số liệu QTT không nhất quán | 17 done |
| 2026-06-02 | Task X done — sửa thoát nước 1 mặt (đáy bùn kín), đồng bộ §28 | 18 done |
| 2026-06-02 | Task Y done — mượn Cc từ HK gần nhất cho ND-03/04/05 (đều mượn ND-06) | 19 done |
| 2026-06-02 | Task Z done — fix KeyError section I (đổi 'd_stop 1D (m)') | 20 done |
| 2026-06-02 | Task AA done — section B3: 4 ma trận S1/S2/S_total/Lc × 6 HK × 6 ΔS + heatmap + bar | 21 done |
| 2026-06-02 | Task BB done — section M: 4-6 heatmap song song theo ΔS + auto-detect | 22 done |
| 2026-06-02 | Audit checkbox update — 22/25 task tick `[x]`; pending = T + 2 issues V | 22 done |
| 2026-06-02 | Issue V #1 fix — γ_fill=18 → γ_TB=21.47 từ tvtk_fill_composition (PA2/PA3 +19%) | — |
| 2026-06-02 | Issue V #3 fix — MNN cột tvtk_cdm_config.gwl_elev_m + get_gwl_elev_m() loader | — |
| 2026-06-02 | Task T background launched — Wave 2 5 zones + Grid 6 ΔS (~50 min) | running |
| 2026-06-02 | Task T HOÀN THÀNH 52 min — 972 grid 6 ΔS + 585 PA-A + 33 PA-B | done |
| 2026-06-02 | DB parity LOCAL ↔ PROJECT 100% (sync 90 rows chênh QTT ΔS=15) | done |
| 2026-06-02 | Task CC done — section O4: PA2a 2 tuyến + PA2b 3 cặp + 4 chart + 2 map | done |
