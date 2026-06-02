### 28. Module Tính Lún Nền — TCCS 41:2022

**File engine:** `scripts/settlement_calc.py` (thuần Python, không dùng pandas)  
**Thông số mặc định:** `data/tccs41_params.json`

#### Các hàm công khai

| Hàm | Mô tả |
|-----|-------|
| `calc_settlement_from_db(bh_name, H_fill_m, stress_scale=1.0)` | Tính tổng lún sơ cấp từ mẫu lab_tests |
| `calc_time_series(S_total_cm, method, zone_params, t_list)` | Tính S(t) cho từng phương án xử lý |
| `compare_methods(bh_name, zone_code, H_fill_m)` | So sánh 5 phương án: no_treat, pvd×2, sand_drain, cdm |
| `calc_cdm_stress_beta(zone_params)` | Hệ số phân bổ ứng suất CDM — TCVN 9403 Phụ lục C |
| `check_samples_vs_tccs41(zone_code)` | Kiểm tra số mẫu Cc so với yêu cầu TCCS41 |

#### Quy tắc CDM — BẮT BUỘC dùng công thức TCVN 9403 Phụ lục C

**KHÔNG** dùng: `reduction = 1 - a × 0.85` (không có cơ sở vật lý).  
**KHÔNG** dùng: `calc_settlement_from_db(..., stress_scale=beta)` cho tính S_CDM — sai bản chất vật lý.

**PHẢI** dùng S1 + S2 (trong `compare_methods()`):**

```python
# S = S1 + S2 (TCVN 9403 Phụ lục C)
S1 = q × H_soft / (a × Ec + (1-a) × Es)  # [m], nhân 100 → cm
S2 = calc_s2_below_cdm(bh_name, cdm_tip_depth_m)["S2_cm"]  # cm — LUÔN TÍNH
# Ec = 75 × (field_lab_ratio × qu_lab / 2)   (TCVN 9403 B.5.1)
# Es = 250 × Cu_avg                           (tương quan Mesri)
```

**S2 — Lún cố kết bên dưới mũi CDM (cập nhật 2026-05-28, BẮT BUỘC):**

`calc_s2_below_cdm()` luôn tính, kể cả khi CDM hết lớp bùn theo ký hiệu. Chỉ dừng khi Δσ/σ'v0 < 10%.

**PHÂN NHÁNH BẮT BUỘC theo loại đất** (memory `feedback-s2-branches-clay-sand`):

| Loại lớp | Điều kiện | Công thức |
|---|---|---|
| **Sét** | `symbol NOT IN SAND_SYMBOLS_S2` | Terzaghi 1D với Cc (phân nhánh OC/NC/cross-PC) hoặc Eoed fallback |
| **Cát** | `symbol IN SAND_SYMBOLS_S2` | $S_i = \dfrac{\Delta\sigma \cdot h_i}{E_s}$ với $E_s = \alpha_{sand} \cdot N_{SPT}$ |

`SAND_SYMBOLS_S2 = {"F", "2a", "2b", "2c", "3a", "3b", "3c", "4", "5", "5a", "5b", "6", "7", "8"}` · `alpha_sand_kPa = 2000.0` mặc định · Fallback `N ≈ 10` khi thiếu SPT trong phân tố.

**Thứ tự ưu tiên thông số mỗi phân tố 2m (CHỈ cho lớp sét):**

| Ưu tiên | Nguồn | Phương pháp tính Si |
| --- | --- | --- |
| 1 | `lab_tests.Cc` gần nhất (bên trên hoặc dưới) | **Terzaghi 1D** với logic OC/cross_PC/NC |
| 2 | `lab_tests.a12_cm2kgf` + `e0` gần nhất | **Eoed** = (1+e0)/a12 × 98.0665 kPa; Si = Δσ×H/Eoed |
| 3 | Không có TN nào trong HK | Cc fallback từ cùng zone hoặc toàn dự án (cảnh báo) |

Cho lớp **cát**: Es từ SPT (`spt_values.N`), không cần Cc/Eoed.

**Key trong return dict**: `"warnings"` (list[str], không phải `"warning"` singular).
**Layer output**: có thêm cột `"method"` = `'Cc'` | `'Eoed'` | `'SPT'` | `'default'`, `"a12"`, `"Eoed_kPa"`, `"N_SPT"`, `"Es_kPa"`.

**q cho S2 đọc từ config (cập nhật 2026-05-27):** `compare_methods` lấy `q_kPa` qua `_cfg_q_kPa()` (đọc `tvtk_cdm_config.q_kPa` — nguồn chính `tvtk_fill_composition`), KHÔNG hardcode 40.8 → tự cập nhật khi cấu tạo tải đắp thay đổi.

**Đã gỡ `crosscheck_settlement_calc` (cdm_column_calc.py):** hàm này chứa công thức giảm lún tuyến tính `1 − a×0.85` (không có cơ sở vật lý) — đã xóa, thay bằng comment. Tính lún CDM chính thức chỉ dùng S1 (`calc_settlement_S1`) + S2 (`calc_s2_below_cdm`).

#### Tối ưu chiều dài cọc CDM theo độ lún cho phép ΔS (cập nhật 2026-05-28)

**Engine:** [scripts/cdm_length_optimize.py](scripts/cdm_length_optimize.py) — `find_cdm_length()` + `area_ratio()` + `soft_profile_from_db()`.
**UI:** tab "Thông số CDM" (`page=="params"`), cột hình học — ô **"Ngàm vào đất tốt (m)" đã thay** bằng độ lún cho phép ΔS (TCCS 41).

Thiết kế ngược: cho ΔS cho phép (TCCS 41 Bảng 1, tra theo cấp đường + vị trí qua `get_allowable_residual_settlement`, **cho nhập tay đè**), lặp tăng độ xuyên cọc p (bước 0,5 m) tới khi $S_1+S_2 \le \Delta S$ → chọn cọc **NGẮN NHẤT** đạt.

- $S_1 = q \cdot p / (a E_c + (1-a) E_s) \times 100$ [cm] — p = độ xuyên (toàn bộ chiều dày gia cố)
- $S_2$ = `calc_s2_below_cdm(bh, clay_top + p, q)` — lún cố kết phần nén lún còn lại dưới mũi
- **Độ xuyên không giới hạn ở H_soft theo ký hiệu** — chạy tới đáy vùng nén lún (lab Cc thường sâu hơn lớp bùn ký hiệu). p_max = max(depth_bot) − đỉnh bùn.
- Cọc "trong lớp bùn" (mũi trong bùn, p < H_soft → S2>0) được phép; xuyên hết → S2≈0.
- Cache `@st.cache_data` qua wrapper `_cdm_length_for_settlement` (app_cdm.py). Set `cdm_Lc` + `cdm_L_ngam` (= max(0, p−H_soft)) sau khi lặp.
- Không đạt kể cả p_max → cảnh báo "giảm khoảng cách s / tăng qu".
- **Tải tính LÚN (S1, S2) = tải đắp tĩnh `q_static`, KHÔNG xét hoạt tải** (hoạt tải tần suất ngắn không gây cố kết). Tải tính **SỨC CHỊU TẢI** P_col = `q_total` (đắp + hoạt tải xe) vì cọc chịu trực tiếp hoạt tải. Hai loại tải tách riêng (không dùng chung), áp cho cả 3 loại lớp.
- **Es = 250·cu với cu = μ·Su (Bjerrum, TCCS 41 C.5)** — `find_cdm_length(mu=...)`; μ tra theo Ip lớp yếu của `cdm_bh` (`bjerrum_mu`+`get_Ip_avg_for_bh`), chỉ áp khi có Ip (VST), không có → μ=1. Cột c3 hiển thị Es = 250×cu tương ứng.

#### Sức chịu tải cọc CDM (1 cọc đơn) — AIT + vật liệu (cập nhật 2026-05-28)

**Tài liệu đầy đủ:** [60-cdm-suc-chiu-tai-coc.md](60-cdm-suc-chiu-tai-coc.md)
**Engine:** `cdm_column_calc.py` — `calc_bearing_soil_ait(d,L,Cu)` · `calc_bearing_material(d,qu)` · `calc_cdm_pile_capacity(...)`
**UI:** tab Thuyết minh TKCS, mục "Sức chịu tải cọc xi măng đất" · **SQLite:** `tvtk_cdm_bearing` (per HK)

- Theo nền (AIT): $Q_{ult.soil}=(\pi d L + 2{,}25\pi d^2)\,C_{u.soil}$ — số hạng 2 = $N_c{=}9$·$A_{mũi}$. **$C_{u.soil}$ = cu SAU Bjerrum (μ·Su), KHÔNG dùng Su nguyên.**
- Theo vật liệu: $Q_{ult.mat}=q_u\cdot\pi d^2/4$. Cho phép $Q_a=\min/FS$, FS=2,5.
- **Lực nén 1 trụ theo tập trung ứng suất** (cọc cứng hút tải): $\sigma_{col}=\tfrac{E_c}{E_{tb}}q$, $P_{col}=\sigma_{col}\cdot A_c$ với $E_{tb}=aE_c+(1-a)E_s$, $E_s=250C_u$. Chính xác hơn $q\cdot s^2$ (đất chia sẻ tải). Kiểm tra $P_{col}\le Q_a$. Bảng lặp + mục SCT đều dùng cách này.
- **Sức chịu tải là 1 điều kiện chọn chiều dài:** $L_{col}^{min}=(P_{col}FS/C_u - 2{,}25\pi d^2)/(\pi d)$; chiều dài thiết kế = max(L theo lún, L theo SCT, L hình học).

**Kết quả mẫu (NHC-BH-01, CDM full penetration tip=35m):**

- S1 = 35,6 cm (đàn hồi khối gia cố)
- S2 = 8,7 cm (Eoed từ lớp CL bên dưới, a12≈0.14, 2 phân tố)
- S_CDM = S1 + S2 = **44,3 cm** (thay vì 35,6 cm khi bỏ S2)

**Time series CDM:** S1 xảy ra tức thì; S2 (cố kết) cũng tức thì vì lớp cứng thoát nước tốt → flat list `U=100%, S=S1+S2` từ t=0.  

`calc_cdm_stress_beta()` vẫn giữ lại để hiển thị biểu đồ ứng suất, không dùng cho tính S.

#### Chiều dày đại diện H_i

Mỗi mẫu đại diện cho vùng từ midpoint trên → midpoint dưới (ranh giới trung điểm).
**KHÔNG** dùng chiều dày mẫu thực (0,6 m) — sẽ cho S_total quá nhỏ.

#### Bảng SQLite cho module lún

| Bảng | Nội dung |
|------|----------|
| `settlement_scenarios` | Kịch bản tính toán (phương án, thông số đầu vào, S_total, residual) |
| `settlement_time_series` | S(t) theo thời gian cho từng kịch bản |
| `settlement_layers` | Chi tiết lún từng lớp (sigma_v0, sigma_vf, PC, Si_cm, OC_status) |

---

### 29. Module Trụ Đất Xi Măng CDM — TCVN 9403:2012

**File engine:** `scripts/cdm_column_calc.py`  
**Thông số mặc định:** `data/tcvn9403_params.json`  
**Tài liệu tra cứu:** [39-tcvn9403-tru-dat-xi-mang.md](39-tcvn9403-tru-dat-xi-mang.md)

#### Các hàm công khai

| Hàm | Mô tả |
|-----|-------|
| `calc_area_ratio(D, s, pattern)` | Tỷ lệ diện tích thay thế a = Ac/A_đơn_vị |
| `calc_Ec(Cc_col, factor=75)` | Mô đun biến dạng trụ: Ec = factor × Cc_col |
| `calc_Es(Cu)` | Mô đun biến dạng đất: Es = 250 × Cu |
| `calc_Cuu(Cu_soft, Cc_col, a)` | Cường độ cắt tổ hợp: Cuu = Cs(1-a) + Cc×a |
| `calc_settlement_S1(q, H, a, Ec, Es)` | Lún đàn hồi S1 = qH/(a×Ec+(1-a)×Es) |
| `calc_settlement_reduction(a, Ec, Es)` | Hệ số giảm lún β = Es/composite_modulus |
| `full_cdm_design(zone_code, Cu_soft, H_soft, ...)` | Thiết kế đầy đủ một kịch bản CDM |
| `check_qc_adequacy(n_cot, n_lab, n_field)` | Kiểm tra số mẫu QC vs Bảng B.1 TCVN 9403 |
| `analyze_lab_results(zone_code)` | Thống kê qu theo hàm lượng xi măng và tuổi mẫu |
| `create_cdm_tables()` | Tạo bảng SQLite (idempotent) |

#### Lưu ý cross-check quan trọng

Hàm tính lún chính xác theo TCVN 9403 Phụ lục C là `calc_settlement_S1()` trong `cdm_column_calc.py` và logic tương đương trong `compare_methods()` của `settlement_calc.py`.

`calc_settlement_from_db(..., stress_scale=beta)` đo lún Cc cố kết (dùng cho no_treat/PVD/giếng cát) — **không dùng** cho CDM.

#### Bảng SQLite cho module CDM

| Bảng | Nội dung |
|------|----------|
| `cdm_design` | Kịch bản thiết kế (a, Ec, Es, S1, hệ số giảm lún) |
| `cdm_lab_results` | Kết quả thí nghiệm qu theo tuổi / hàm lượng xi măng / phương pháp trộn |

---

### 30. Tab "Lún Nền" trong App (page id = "settlement")

**Vị trí:** `app_cdm.py`, cuối file, điều kiện `if _page == "settlement":`

#### Cấu trúc giao diện

**Tab phụ 1 — So sánh phương án:**
- 3 cột điều khiển: chọn zone/hố khoan, H_fill, giới hạn lún, thời gian thi công
- Nút "Tính toán lún" → gọi `compare_methods()`
- 3 metric cards: Lún tự nhiên | CDM beta | CDM giảm lún %
- Bảng so sánh 5 phương án (màu xanh=Đạt, đỏ=Không đạt)
- Biểu đồ S(t) — đường cong lún theo thời gian
- **Biểu đồ ứng suất theo chiều sâu**: σ'v0 (xanh), σ'vf không xử lý (đỏ chấm), σ'vf CDM (cam đứt), PC (xanh lá) — nền màu theo vùng OC/cross_PC/NC
- Expander "Chi tiết lún từng lớp" — bảng layer data
- Expander "Lý thuyết tính lún" — giải thích công thức OC/NC/cross_PC + tại sao CDM lún tổng còn lớn

**Tab phụ 2 — Kiểm tra mẫu vs TCCS41:**
- 3 cột theo zone NHC/BXN/KE
- Metric: n_HK_đạt/n_HK_tổng, thiếu bao nhiêu mẫu Cc
- Bảng chi tiết per hố khoan (Cc có / Cc cần / thiếu / trạng thái)
- Bảng tổng hợp 3 zone

### 31. Module Khoảng Cách Hố Khoan — TCCS 41:2022 Điều 5.3.2

**File engine:** `scripts/borehole_spacing.py`  
**Tài liệu tra cứu:** mục 2.1 trong [38-tccs41-nen-duong-dat-yeu.md](38-tccs41-nen-duong-dat-yeu.md)  
**Bảng SQLite:** `borehole_distances`

#### Giới hạn khoảng cách theo bước thiết kế

| `design_step` | Dọc tuyến (m) | Ghi chú |
| --- | :---: | --- |
| `"LAPDA"` | 250–500 | Điều 5.3.2.1 — lập dự án đầu tư |
| `"BVTK"` | 100–150 | Điều 5.3.2.2 — dọc tuyến; cao tốc/cấp III: 100 m |
| `"BVTK_matcat"` | 150–300 | Khoảng cách giữa các mặt cắt ngang |

#### Hàm công khai

| Hàm | Mô tả |
| --- | --- |
| `calc_pairwise_distances(bhs)` | Tính tất cả cặp, sort theo distance_m |
| `check_spacing_532(bhs, design_step, same_zone_only)` | Kiểm tra vs tiêu chuẩn → dict với pairs + summary |
| `create_borehole_distances_table(db_path)` | Tạo bảng SQLite (idempotent) |
| `save_distances_to_db(bhs, design_step, db_path)` | Lưu kết quả vào SQLite |

#### Tab Địa chất — UI (cập nhật 2026-05-19)

- Layout 2 cột: 3D view (trái, height=420) | Bảng khoảng cách (phải)
- Selectbox "Bước thiết kế": BVTK / LAPDA
- Bảng cặp HK: màu xanh = Đạt, đỏ = Gần quá / Xa quá
- Selectbox "Chọn cặp HK để đo kích thước trên 3D" → vẽ đường cam + nhãn khoảng cách trên 3D
- `_draw_boreholes_3d(..., pair_highlight=(bh1, bh2, dist_m))` → thêm trace đường kích thước

**Kết quả TTHC (BVTK):** 36 đạt / 157 cặp; 85 gần quá (HK cùng khu vực), 36 xa quá.

---

