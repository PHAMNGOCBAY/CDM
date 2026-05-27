### 35. Giới hạn Độ Lún Cố Kết Còn Lại ΔS — TCCS 41:2022 Bảng 1 (Điều 6.2.3)

**File engine:** `scripts/settlement_calc.py` — section 6b (cuối file trước DEMO)
**Reference:** [38-tccs41-nen-duong-dat-yeu.md](38-tccs41-nen-duong-dat-yeu.md) mục 3
**JSON:** `data/tccs41_params.json` → `tccs41_limits.residual_settlement_table`
**SQLite:** `tccs41_settlement_limits` (6 rows: cat1/cat2 × near_bridge/side_culvert/general)

#### Bảng 1 — Giới hạn ΔS cho phép còn lại (cm)

| Loại đường | Gần mố cầu | Hai bên cống | Đoạn thông thường |
|---|:---:|:---:|:---:|
| **cat1** — Cao tốc / ≥ 80 km/h / A1 | ≤ 10 | ≤ 20 | ≤ 30 |
| **cat2** — ≤ 60 km/h / A1 | ≤ 20 | ≤ 30 | ≤ 40 |

**Thời hạn t:** 15 năm (mặt đường mềm) · 30 năm (mặt đường cứng).
**Công thức (36):** $\Delta S = S_c \cdot (1 - U_t)$

#### Hàm public — `scripts/settlement_calc.py`

| Hàm | Vai trò |
| --- | --- |
| `create_tccs41_limits_table(db_path=None)` | Tạo bảng + populate 6 ô (idempotent, ON CONFLICT) |
| `get_allowable_residual_settlement(road_class_code, position_code, db_path=None)` | Trả về dict `{delta_S_cm_max, road_class_desc, position_desc, t_years_flexible, t_years_rigid}`. Auto-create bảng nếu chưa có. |
| `list_tccs41_limits(db_path=None)` | Liệt kê toàn bộ 6 ô — phục vụ UI |

**Code codes hợp lệ:**
- `road_class_code`: `'cat1'` · `'cat2'`
- `position_code`: `'near_bridge'` · `'side_culvert'` · `'general'`

#### Tích hợp UI — Tab `tvtk_prep` section 2 (bảng 3 PA)

Vị trí: `app_cdm.py` ~line 15796, ngay sau `#### Độ lún khối gia cố CDM theo 3 phương án chiều sâu`.

**Pattern:**

1. Lazy import `create_tccs41_limits_table` + `get_allowable_residual_settlement` (try/except → `_get_ds_limit = None` nếu fail)
2. ALTER TABLE `tvtk_cdm_config` ADD COLUMN `road_class_code TEXT DEFAULT 'cat1'`, `position_code TEXT DEFAULT 'general'` (try/except idempotent)
3. 2 selectbox: cấp đường + vị trí đoạn nền đắp → UPDATE `tvtk_cdm_config` ngay khi thay đổi
4. Metric "ΔS cho phép (cm)" + caption mô tả road_class + position + thời hạn t
5. Bổ sung 3 cột "Đạt PA1/PA2/PA3" vào `_s1_rows_e` (so sánh `S₁ ≤ ΔS_limit` → "Đạt"/"Không đạt")
6. Tổng hợp dưới bảng: số HK Đạt/Không đạt mỗi PA + caption ngưỡng ΔS

**Quy ước "Đạt"/"Không đạt":** `S₁ ≤ ΔS_limit` → "Đạt" (compliant); ngược lại "Không đạt".

**Lưu ý vật lý:** S₁ ở tab này là **lún đàn hồi tức thì của khối gia cố CDM** (TCVN 9403 Phụ lục C); ΔS theo TCCS 41 là **lún cố kết còn lại** sau t năm. Cọc CDM cắm tới lớp cứng nên lún cố kết phần dưới mũi cọc ≈ 0, do đó so sánh trực tiếp S₁ với ΔS_limit là cách đánh giá nhanh tính khả thi của 3 phương án chiều sâu.

---

### 36. Hiệu chỉnh Bjerrum cho Su (VST) — TCCS 41:2022 Phụ lục C.3.2 (Công thức C.5, Bảng C.1)

**Phạm vi:** Đối với các lớp đất tự nhiên yếu hoặc không yếu nằm dưới nền đắp — sử dụng kết quả VST, **cường độ kháng cắt TÍNH TOÁN** $c_u$ được xác định:

$$c_u^i = \mu \cdot S_u^i \qquad \text{(C.5, xem }\varphi=0\text{)}$$

**File engine:** `scripts/settlement_calc.py` — section 6a (trước section 6b)
**Reference:** [38-tccs41-nen-duong-dat-yeu.md](38-tccs41-nen-duong-dat-yeu.md) mục 3b
**JSON:** `data/tccs41_params.json` → `tccs41_limits.bjerrum_correction`

#### Bảng C.1 — μ theo Ip

| $I_p$ | 10 | 20 | 30 | 40 | 50 | 60 | 70 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| $\mu$ | 1,09 | 1,00 | 0,925 | 0,86 | 0,80 | 0,75 | 0,70 |

**Nội suy bậc nhất** giữa các khoảng; **clamp** đầu/cuối khi ngoài bảng.

#### Hàm public — `scripts/settlement_calc.py`

| Hàm | Vai trò |
| --- | --- |
| `bjerrum_mu(Ip)` | Trả về μ; clamp đầu/cuối; `Ip None/≤0` → 1.0 (safe default) |
| `apply_bjerrum_correction(Su_kPa, Ip)` | Dict `{Su_kPa, Ip, mu, Cu_kPa}` |
| `get_Ip_avg_for_bh(bh_name, soft_symbols, db_path)` | Query AVG(Ip) từ lab_tests cho HK |

#### SQLite — Cột mới trong `tvtk_bh_cdm`

| Cột | Vai trò |
| --- | --- |
| `Ip_avg` | Ip trung bình của HK (lớp yếu) |
| `bjerrum_mu` | μ tra bảng C.1 |
| `Cu_corrected_kPa` | $c_u = \mu \cdot S_u$ |

Pre-migrate trước commit (idempotent ALTER TABLE try/except trong app).

#### Áp dụng trong dự án

| Tính toán | Trước hiệu chỉnh | Sau hiệu chỉnh (BẮT BUỘC) |
|---|---|---|
| Mô đun đàn hồi đất yếu $E_s$ | $E_s = 250 \cdot S_u$ | $E_s = 250 \cdot c_u = 250 \cdot \mu \cdot S_u$ |
| Sức kháng ma sát thân cọc (sét) | $R_s = \alpha \cdot S_u \cdot P \cdot L$ | $R_s = \alpha \cdot c_u \cdot P \cdot L$ |
| Bishop/Fellenius lớp yếu | $c = S_u$, $\varphi = 0$ | $c = c_u$, $\varphi = 0$ |
| Tính lún cố kết (Cc, e₀, PC) | giữ nguyên | giữ nguyên (không liên quan) |

#### Tích hợp UI — Tab `tvtk_prep` section 2

**Bảng 3 PA** ([app_cdm.py:15783](scripts/app_cdm.py:15783)) thêm 4 cột mới:
- "Su VST (kPa)" (trước là "Cu (kPa)") · "Ip" · "μ (Bjerrum)" · "Cu = μ·Su (kPa)"

**Biểu đồ VST** ([app_cdm.py:16252](scripts/app_cdm.py:16252)) thêm:
- Trace `Cu = μ·Su (TCCS 41 C.5)` — màu xanh lá `#16a34a`, marker diamond, lines+markers
- Annotation hộp xanh lá hiển thị `Cu_TB` ở giữa lớp yếu (mũi tên + giá trị + μ + Ip)

**Soft symbols** mặc định: `("1", "1b", "CH", "MH", "CH-OH", "MH-OH")` — query Ip TB từ `lab_tests.Ip` theo `symbol_tcvn`.

**Fallback an toàn:** Nếu import `bjerrum_mu` fail → μ=1.0 → Cu=Su (giữ nguyên hành vi cũ, không vỡ app).

---

### 37. Đoạn chuyển tiếp Đường ↔ Cầu (Cống) — TCCS 41:2022 Phụ lục E

**File tài liệu:** [46-tccs41-phuluc-E-doan-chuyen-tiep.md](46-tccs41-phuluc-E-doan-chuyen-tiep.md)
**File engine:** `scripts/settlement_calc.py` — section 6c (cuối file trước DEMO)
**JSON:** `data/tccs41_params.json` → `tccs41_limits.appendix_E_transition_zone`
**SQLite:** `tccs41_smoothness_limits` (20 rows) · `tccs41_approach_slab` (3 rows)

#### Phạm vi áp dụng (E.3.2.1)

| Tình huống | Bắt buộc thiết kế chuyển tiếp? |
|---|---|
| Cầu/cống đường cấp V, VI | KHÔNG |
| Cống cấp I–IV có đất đắp trên đỉnh > 1,0 m | KHÔNG |
| Cầu/cống đường cao tốc | **CÓ** |
| Cầu đường cấp I–IV | **CÓ** |
| Cống cấp I–IV đất đắp < 1,0 m | **CÓ** |

#### Bảng E.1 — Độ bằng phẳng $i$ dọc tim đường

| Cấp đường | Công trình | v=40 | v=60 | v=80 | v=100 | v=120 |
|---|---|:---:|:---:|:---:|:---:|:---:|
| Cao tốc (TCVN 5729) | Cầu | — | 1/175 | 1/200 | 1/250 | 1/250 |
| Cao tốc | Cống | — | 1/150 | 1/150 | 1/150 | 1/150 |
| Cấp I–IV (TCVN 4054) | Cầu | 1/125 | 1/150 | 1/175 | 1/200 | 1/200 |
| Cấp I–IV | Cống | 1/125 | 1/125 | 1/150 | 1/150 | 1/150 |

Cho phép tạo "vồng" trước với độ dốc tối đa **1/125**.

#### Công thức E.1–E.4 — Chiều dài đoạn chuyển tiếp

| Công thức | Trường hợp | Biểu thức |
|---|---|---|
| E.1 | Tổng | $L_{ct} \geq L_1 + L_2$ |
| E.2 | Cầu | $L_1 \geq (\Delta S_f - \Delta S_c)/S$, min $= 3H + (3\div 5)$ m |
| E.3 | Cống | $L_1 \geq (\Delta S_f - \Delta S_{cg})/S$, min $= D + 2H$ |
| E.4 | Đoạn dài | $L_2 \geq (\Delta S_1 - \Delta S_f)/S$ |

**Hằng số:** $\Delta S_c$ (TCVN 11823) = 25,4 mm/100 năm; 3,8 mm/15 năm.

#### Bảng E.2 — Chiều dài bản quá độ

| Loại cầu | $L$ tham khảo |
|---|:---:|
| Cầu nhỏ | $\geq 5$ m |
| Cầu trung | 8 ÷ 12 m |
| Cầu lớn | 8 ÷ 12 m |

**Chiều dày:** $t \geq \max(L/20,\ 300\ \text{mm})$. Đặt sâu **700 mm** dưới mặt đường, dốc dọc 4–10%, **cốt thép 2 lớp**.

#### Hàm public — `scripts/settlement_calc.py`

| Hàm | Vai trò |
| --- | --- |
| `get_smoothness_limit(road_class_code, structure, speed_kmh)` | Tra Bảng E.1 — trả về `{denominator, i_value, i_text}` |
| `calc_transition_length(deltaSf_m, deltaS1_m, S_denominator, H_m, structure, D_m, deltaSc_m, deltaScg_m, extra_m)` | Tính $L_1, L_2, L_{ct}$ theo E.1–E.4. Auto chọn E.2 (cầu) hoặc E.3 (cống). Trả về `{L1_calc, L1_min, L1, L2, Lct, governs_L1, formula_id}` |
| `get_approach_slab_length(bridge_type_code)` | Tra Bảng E.2 — `'small' / 'medium' / 'large'` |
| `calc_approach_slab_thickness(L_m)` | $t = \max(L/20, 300\ \text{mm})$ — trả về `{t_m, governs}` |
| `create_appendix_E_tables(db_path)` | Tạo 2 bảng SQLite + populate (idempotent) |

**Mã code hợp lệ:**
- `road_class_code`: `'cao_toc'` · `'cap_I_IV'`
- `structure`: `'cau'` · `'cong'`
- `speed_kmh`: 40 / 60 / 80 / 100 / 120
- `bridge_type_code`: `'small'` · `'medium'` · `'large'`

#### Giải pháp xử lý đất yếu (E.4.2)

| Tham số | Giá trị |
|---|---|
| Chia đoạn nhỏ | 5 – 15 m |
| Cố kết tối thiểu trước thi công mố | **90%** |
| Bước giảm chiều sâu cọc (bậc thang) | 10 – 15% chiều dài |
| Khoảng cách cọc tăng dần | 1,2 – 1,5 lần |
| $H_{\max}$ không đất yếu | < 6 m |
| $H_{\max}$ có đất yếu | < 4 m |

---

