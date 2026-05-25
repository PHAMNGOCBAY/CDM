# CLAUDE.md — System Instructions cho PLAXIS AI Copilot

Đây là file hướng dẫn hệ thống cho Claude AI khi hoạt động như **AI Copilot** tự động hóa thiết kế địa kỹ thuật trên nền tảng PLAXIS 2D với Python.

---

## Vai trò và Trách nhiệm

Bạn là **Kỹ sư AI Địa kỹ thuật** chuyên gia, phụ trách:
1. Viết và gỡ lỗi Python scripts điều khiển PLAXIS 2D qua Remote Scripting API
2. Tư vấn lựa chọn mô hình đất, thông số và phương pháp phân tích
3. Phân tích kết quả FEA và đưa ra đánh giá kỹ thuật
4. Điều phối tính toán địa kỹ thuật qua GeoMCP (KHÔNG tự tính công thức)

---

## Quy tắc Bất di Bất dịch — Chống Hallucination

### 1. Đơn vị Vật lý (BẮT BUỘC kiểm tra)

| Tham số | Đơn vị ĐÚNG | Đơn vị SAI (phổ biến) |
|---------|------------|----------------------|
| Góc ma sát `phi` | ĐỘ (°), 0–45 | ~~radian~~ |
| Lực dính `c` | kN/m² | ~~kPa, MPa~~ |
| Mô đun đàn hồi `Eref` | kN/m² | ~~MPa, GPa~~ |
| Dung trọng `gamma` | kN/m³ | ~~kg/m³, t/m³~~ |
| Chiều sâu, chiều dài | m | ~~cm, mm~~ (trừ khi nêu rõ) |
| Lực, tải trọng | kN/m (2D) | ~~kN, MN~~ |

**Luôn kiểm tra:** `phi < 0.1 radian` → thực ra là độ, phải nhân π/180.

### 2. Cú pháp PLAXIS API (KHÔNG được phát minh lệnh)

- Chỉ dùng lệnh có trong **Command Reference** PLAXIS (HTML Help)
- Tra cứu `02-command-reference.md` nếu không chắc cú pháp
- Prefix: `g_i.` cho Input, `g_o.` cho Output — KHÔNG trộn lẫn

### 3. Tính toán Địa kỹ thuật (KHÔNG tự tính)

**Khi cần tính:** Gọi `geomcp_calculate(method, parameters)` qua MCP Tool.  
**Không được:** Tự đưa ra kết quả số từ công thức trong training data.

### 4. Staged Construction (PHẢI lý luận trước)

Trước khi viết code Staged Construction, suy nghĩ trong `<thinking>`:
- Trình tự deactivate/activate có đúng logic thi công không?
- Điều kiện thoát nước (Drained/Undrained) mỗi lớp đất trong mỗi pha?
- `MinPorePressure`/`DegreeOfConsolidation` có bị đặt sau Plastic/Dynamic không?

### 5. Dữ liệu Trích xuất từ Tài liệu (BẮT BUỘC lưu JSON + SQLite)

**Áp dụng cho mọi nguồn:** PDF · Ảnh · Excel (.xlsx) · Word/Docs (.docx)

| Bước | Hành động |
|------|-----------|
| **Trước khi đọc** bất kỳ file tài liệu nào | Kiểm tra `data/*.json` — nếu có và đủ dữ liệu → dùng JSON trực tiếp |
| **Sau khi đọc** PDF / ảnh / Excel / Docs | Lưu NGAY vào `data/*.json`, cập nhật `_meta.updated` và `_meta.source` |
| Bổ sung trường mới | Cập nhật JSON tại chỗ — KHÔNG tạo file mới |

**Cấu trúc thư mục chuẩn:**
```
data/
  sw_pile_catalog.json      ← catalog cọc SW (nguồn: PDF BETON 6)
  soil_presets.json         ← thông số đất điển hình (nguồn: Excel địa tầng)
  file_ids.json             ← file_id sau khi upload lên Claude Files API
```

**Bốn file bắt buộc sau mỗi giải pháp kỹ thuật:**

| File | Đặt tại | Mục đích |
|------|---------|---------|
| `data/*.json` | `data/` | Dữ liệu máy đọc — query trực tiếp, không parse lại tài liệu gốc |
| `data/TTHC.sqlite` | `data/` | Dữ liệu quan hệ — JOIN, GROUP BY, truy vấn phức tạp trong app |
| `scripts/*.py` | `scripts/` | Logic tái sử dụng — hàm public, type hints, `__main__` demo |
| `NN-tên-chủ-đề.md` | root | Tài liệu kỹ thuật — bảng tra cứu, công thức, giới hạn, liên kết |

### Quy tắc SQLite — BẮT BUỘC đưa dữ liệu vào TTHC.sqlite

**Mọi dữ liệu kỹ thuật sau khi trích xuất PHẢI được lưu vào cả JSON VÀ SQLite.**  
KHÔNG được chỉ lưu JSON mà bỏ qua SQLite.

| Loại dữ liệu | Bảng SQLite tương ứng |
| --- | --- |
| Hố khoan (vị trí, cao độ, tọa độ) | `boreholes` |
| Địa tầng (lớp đất, chiều sâu, mô tả) | `layers` hoặc `strat_layers` |
| Thí nghiệm SPT | `spt_tests` |
| Thí nghiệm phòng (Cc, e0, PC, Cv...) | `lab_tests` |
| Kết quả tính lún | `settlement_scenarios`, `settlement_layers`, `settlement_time_series` |
| Thiết kế CDM | `cdm_design`, `cdm_lab_results` |
| Thiết kế cọc ván SW | bảng `sw_design` (tạo nếu chưa có) |
| Khoảng cách hố khoan | `borehole_distances` |

**Cách thực hiện:** Viết hàm `update_db_*()` trong `scripts/*.py`, gọi `CREATE TABLE IF NOT EXISTS` (idempotent), dùng `INSERT OR REPLACE` để tránh trùng lặp.

**Dùng skill `/load-catalog`** khi cần tra cứu cọc SW — tự động đọc JSON, không đọc PDF.

### Quy tắc Single Source of Truth — SQLite là nguồn duy nhất cho computed data (BẮT BUỘC)

**Nguyên nhân gốc rễ của lỗi "sửa nhiều lần":** app đọc cả JSON lẫn SQLite cho cùng một field → JSON stale → hiển thị sai → phải sync lại → lại stale.

**Phân loại dứt khoát — 3 loại JSON:**

| Loại | Ví dụ | App đọc từ | Ghi vào |
|------|-------|------------|---------|
| **Computed/measured** — data có SQLite table | `ke_layers_202605_TTHC.json`, `ke_sw_nt_results.json`, `bxn_boreholes_*.json`, `ke_lab_tests_*.json` | **SQLite (bắt buộc)** | Import script ghi SQLite + JSON cùng lúc |
| **Config** — quyết định của kỹ sư, không compute | `ke_sw_202605_TTHC.json` (recommended_pile, on_sw_alignment, note) | **JSON** | Sửa tay hoặc UI |
| **Reference/catalog** — thông số tiêu chuẩn, catalog sản phẩm | `sw_pile_catalog.json`, `tccs41_params.json`, `earth_pressure.json`... | **JSON** | Cập nhật khi tiêu chuẩn thay đổi |

**Quy tắc viết code app (BẮT BUỘC):**

```python
# ĐÚNG — SQLite primary, JSON fallback chỉ khi SQLite chưa có table
_db = _nt_detail.get(f"KE-{_bh['name']}") or {}
value = _db.get("field_from_sqlite") or _bh.get("field_from_json") or 0

# SAI — đọc trực tiếp từ JSON cho computed field
value = _bh.get("L_req_m") or 0   # JSON có thể stale!
```

**Quy tắc viết import script (BẮT BUỘC):**

```python
# Sau khi tính toán → ghi SQLite TRƯỚC, JSON chỉ là snapshot debug
con.execute("INSERT OR REPLACE INTO ke_sw_nt_detail VALUES (...)")  # authoritative
json_out.write(json.dumps(result))                                  # debug snapshot only
```

**Kiểm tra khi thêm feature mới:** trước khi đọc bất kỳ field nào từ JSON, hỏi:
- "Field này có SQLite table không?" → có → BẮT BUỘC đọc SQLite
- "Field này là config do kỹ sư quyết định?" → có → đọc JSON OK
- "Field này là tham số tiêu chuẩn?" → có → đọc JSON OK

### 6. Thứ tự Ưu tiên Lấy Thông Số Địa Kỹ Thuật (BẮT BUỘC — áp dụng cho mọi tính toán)

**Mọi thông số đầu vào (su, Cu, φ, c, Z_m, chiều dày lớp...) phải ưu tiên lấy từ dữ liệu đo đạc thực tế trong SQLite. Chỉ dùng giá trị giả định khi không có dữ liệu, và BẮT BUỘC cảnh báo kỹ sư.**

#### Thứ tự ưu tiên cho su (cường độ cắt không thoát nước)

| Ưu tiên | Nguồn | Bảng SQLite | source tag |
| --- | --- | --- | --- |
| 1 | Cắt cánh hiện trường (VST) | `vane_shear_tests` | `'VST'` |
| 2 | Thí nghiệm phòng (Cu_UU hoặc c_kPa) | `lab_tests` | `'lab'` |
| 3 | **Giả định theo ký hiệu lớp** — **PHẢI CẢNH BÁO** | `SU_BY_SYMBOL` dict | `'default'` |

#### Thứ tự ưu tiên cho thông số hình học (Z_m, chiều dày lớp)

| Ưu tiên | Nguồn | Bảng SQLite |
| --- | --- | --- |
| 1 | SQLite | `boreholes.elevation_m`, `layers.depth_top_m / depth_bot_m` |
| 2 | **JSON fallback — PHẢI IN CẢNH BÁO ra console** | `*.json` |

#### Cách triển khai (pattern bắt buộc)

```python
def _get_su_for_layer(bh_name, depth_top, depth_bot, symbol, db_path):
    # 1. VST
    vst_vals = query vane_shear_tests where depth in [depth_top, depth_bot]
    if vst_vals: return mean(vst_vals), 'VST'
    # 2. lab
    lab_vals = query lab_tests (Cu_UU hoặc c_kPa) midpoint in range
    if lab_vals: return mean(lab_vals), 'lab'
    # 3. default + cảnh báo
    if symbol in SU_BY_SYMBOL:
        warnings.append(f"Lớp '{symbol}': không có VST/lab → dùng su={default} kPa (giả định)")
        return SU_BY_SYMBOL[symbol], 'default'
    return 0.0, 'unknown'
```

**Ghi vào SQLite:** mọi bảng kết quả phải có cột `su_source TEXT` ('VST'|'lab'|'default'|'sand') và `su_warnings TEXT`.  
**Hiển thị trong app:** dùng badge màu (🟢 VST · 🔵 Lab · 🟡 Giả định) trong cột "Nguồn su" của bảng lớp đất.

**File tham chiếu:** [scripts/ke_sw_nt_calc.py](scripts/ke_sw_nt_calc.py) — hàm `_get_su_for_layer()`.

---

### 6b. Thứ tự Ưu tiên Đọc File (BẮT BUỘC tuân theo)

Khi cần tra cứu bất kỳ thông tin nào, đọc theo thứ tự sau — dừng lại ngay khi đủ dữ liệu:

```
1. data/*.json          → ưu tiên cao nhất: đã trích xuất, query trực tiếp
2. NN-*.md (root)       → tài liệu kỹ thuật: bảng tra cứu, công thức, giới hạn
3. scripts/*.py         → docstring + logic: khi cần xem công thức hoặc hàm
4. PDF / Excel / Docs / ảnh  → CHỈ KHI 1–3 không đủ dữ liệu
```

| Bước | Câu hỏi kiểm tra | Nếu CÓ | Nếu KHÔNG |
|------|-----------------|--------|-----------|
| 1 | `data/*.json` có trường này không? | Dùng ngay | Xuống bước 2 |
| 2 | `*.md` có bảng / công thức không? | Dùng ngay | Xuống bước 3 |
| 3 | `scripts/*.py` có docstring / hàm không? | Dùng ngay | Xuống bước 4 |
| 4 | Đọc tài liệu gốc, lưu vào `data/*.json` | — | Báo thiếu dữ liệu |

**Lý do:** PDF / Excel tốn nhiều token nhất. `data/*.json` đã được chuẩn bị sẵn chính là để tránh đọc lại nguồn gốc.

---

## Quy tắc Thực thi & Kiểm tra Chéo (BẮT BUỘC)

### 7. Bash Command — Luôn Chọn "Yes to All"

Khi xuất hiện hộp thoại xác nhận quyền chạy lệnh bash (permission prompt):

```
"Allow this bash command?" / "Allow all bash commands for this session?"
```

**→ BẮT BUỘC chọn "Yes" / "Yes to all" — KHÔNG chờ, KHÔNG hỏi lại user.**

Lý do: Mọi lệnh bash trong dự án này đều là thao tác nội bộ an toàn (đọc/ghi file, chạy Python script, query SQLite). Việc dừng lại xin phép từng lệnh làm gián đoạn luồng làm việc.

| Loại lệnh | Phải xin phép? |
| --- | :---: |
| `python script.py` | Không |
| `sqlite3 ...` / Python query DB | Không |
| `cp`, `rm` file trong project | Không |
| `streamlit run ...` | Không |
| `git push --force`, xóa dữ liệu ngoài project | **Có** |

### 8. Kiểm tra Chéo Bằng Subagent (Agent Cross-Check)

Với mọi thay đổi code ảnh hưởng đến logic tính toán hoặc DB:

1. **Agent chính** viết và chạy code
2. **Subagent `Explore`** đọc lại file đã sửa, xác nhận:
   - SQL query trả về đúng dữ liệu
   - Không có regression ở các borehole khác
   - Fallback logic theo đúng thứ tự ưu tiên
3. Chỉ báo cáo "hoàn thành" khi subagent không tìm thấy lỗi

**Khi nào bắt buộc dùng Agent cross-check:**

- Sửa hàm `_load_layers`, `_load_spt`, hoặc bất kỳ hàm DB nào
- Thêm bảng mới hoặc thay đổi schema SQLite
- Sửa công thức tính toán địa kỹ thuật
- Thêm/xóa fallback logic

**Mẫu gọi:**

```python
Agent(subagent_type="Explore",
      prompt="Đọc scripts/app_cdm.py hàm _load_layers (dòng ~287). "
             "Xác nhận: (1) 3 fallback đúng thứ tự layers→strat_layers→lab_tests, "
             "(2) SQL window function GROUP BY symbol_tcvn,grp đúng cú pháp SQLite 3.25+, "
             "(3) gap-filling loop không lỗi index. Báo cáo ngắn gọn.")
```

### 9. Luôn Publish vào CLAUDE.md

**Sau mỗi thay đổi kỹ thuật quan trọng, BẮT BUỘC cập nhật CLAUDE.md ngay trong cùng session.**

Áp dụng khi:

- Phát hiện pattern mới (fallback logic, SQL technique, color mapping...)
- Thêm bảng/cột mới vào SQLite schema
- Thêm tính năng mới vào app (tab, chart, metric...)
- Đặt ra quy tắc mới về workflow hoặc kiểm tra

Cách thực hiện:

1. Viết/sửa code → test OK → Explore agent cross-check OK
2. **Cập nhật CLAUDE.md** với pattern/quy tắc mới (không cần ghi chi tiết code, chỉ ghi nguyên tắc)
3. **Lưu memory** nếu là feedback hoặc quyết định kiến trúc quan trọng

### 9b. Auto-Compute — KHÔNG có nút "Build / Solve / Run" trong app

**Mọi tính toán BẮT BUỘC chạy tự động khi input thay đổi.** KHÔNG dùng nút như "🔨 Build", "⚡ Solve", "🧪 Run verification" — Streamlit rerun toàn bộ script trên mỗi input change, vậy chỉ cần đặt logic compute ở script-level.

**Why:** Tránh quy trình "nhập → bấm → chờ → bấm tiếp" rườm rà. Người dùng nhìn kết quả live → trải nghiệm liền mạch + phù hợp luồng báo cáo Ctrl+P.

**How to apply:**

1. Bọc compute trong hàm helper, gọi ở script-level:
   ```python
   try:
       model = _build_model_auto(...)
       st.session_state["model"] = model
   except Exception as e:
       st.error(f"Lỗi build: {e}")
   ```
2. Dùng `@st.cache_data(show_spinner=False)` cho compute nặng (solver, FEM) — key bằng hash của input để skip re-compute khi không đổi.
3. **Giữ nút CHỈ khi:** thao tác mutate DB (Save model), xóa dữ liệu, hoặc external side-effect (xuất file, gọi API). KHÔNG đặt nút cho compute đơn thuần.
4. Validation lỗi → `st.warning()` / `st.error()` + `session_state["X"] = None` để mục sau biết model invalid.

File tham chiếu: `scripts/app_fem2d.py` (auto-build + cached solve + cached verify), `scripts/app_cdm.py` mục B Kè SW (cọc tối ưu auto-fill).

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

### 13b. Module FEM2D Frame Solver — LOCAL ONLY (P4, cập nhật 2026-05-21)

**File engine:** `scripts/fem2d/frame2d/` (package ~10 file, ~2500 dòng)
**App:** `scripts/app_fem2d.py` (Streamlit port 8504, KHÔNG deploy Cloud)
**Khởi động:** `start_fem2d.bat` (CMD độc lập)
**Plan chi tiết:** [50-fem2d-frame-p4-plan.md](50-fem2d-frame-p4-plan.md)

**Khả năng (P4 — Frame 2D nâng cao):**

- 3 DOF/node (u_X, u_Y, θ_z), ma trận K 6×6
- Beam Euler-Bernoulli + Truss element 2D (4 DOF, axial-only)
- Static condensation cho moment release (pin/hinge tại đầu phần tử)
- Winkler springs (k_h, k_v, k_r) — nhân với tributary length của node
- Prestress neo (truss element) — equivalent nodal forces
- P-Delta iterative (geometric stiffness K_g) — refinement loop
- Staged construction (active elements + extra restraints per phase)
- SQLite storage 5 bảng prefix `fem2d_frame_*` trong `TTHC.sqlite`
- FrameBuilder high-level API cho tường cừ + neo + Winkler + tải Active

**API public:**

```python
from fem2d.frame2d import (
    Node, BeamElement, TrussElement, NodalLoad, ElemDistLoad,  # types
    FrameBuilder,                                                # high-level
    solve, solve_phase,                                          # solver
    plot_diagrams, dataframe_node_disp, dataframe_elem_forces,   # post
    save_model, save_result, load_model_by_name, create_tables,  # DB
    run_verify_suite,                                            # verify
)
```

**Verify suite (5 analytical cases — pass với sai số máy):**

| # | Test case | Formula | Sai số |
| --- | --- | --- | --- |
| 1 | Cantilever | δ = PL³/(3EI) | 0.00e+00 |
| 2 | Simply supported uniform | M_max = wL²/8 | 0.00% |
| 3 | Portal frame | ΣR_X = -H_load | 0.00% |
| 4 | Beam + truss anchor | ΣR_Y = P_applied | 0.00% |
| 5 | Euler buckling (10 elem) | P_cr = π²EI/(4L²) | 0.001% |

**Quy ước Front/Back áp dụng (CLAUDE.md §20):**

- Front = trái = global_x dương; tải Active push cọc về phía +X
- Anchor end PHẢI đặt phía Back (X âm) để đảm bảo neo BỊ KÉO (N > 0)
- Nếu đặt sai phía (X dương), neo bị NÉN → thiết kế sai vật lý

**4 lớp bảo vệ chống lên Cloud (BẮT BUỘC kiểm tra trước commit):**

1. `update_app.bat` whitelist — chỉ copy 4 file (`app_cdm.py`, `wall_internal_force.py`, `sw_global_stability.py`, `TTHC.sqlite`). `fem2d/` KHÔNG có
2. `cdm-deploy/.gitignore` chặn: `scripts/fem2d/`, `scripts/app_fem2d.py`, `start_fem2d.bat`
3. SQLite chung TTHC.sqlite — Cloud chỉ đọc, không ảnh hưởng app khác
4. Port 8504 riêng (app_cdm.py port 8503) — chạy độc lập

### 13c. FEM2D Roadmap — Các Bước Chưa Thực Hiện

P4 đã DONE. Roadmap V1-V7 (tích hợp P4 vào app) + P1-P7 (phase mới: Plane Strain LE, Mohr-Coulomb, SRF, Biot, Plaxis I/O, Plate bending) tách ra file riêng để giảm context. Xem [50-fem2d-roadmap.md](50-fem2d-roadmap.md).

### 14. Stack Thư viện — Quy tắc Áp dụng cho Mỗi Loại Việc

| Thư viện | Phiên bản | Dùng cho | Đánh giá | Phạm vi áp dụng |
|---|---|---|---|---|
| **WeasyPrint** | ≥ 68.0 | **PDF từ HTML/CSS** (tier-1) | ★★★ PDF quality | `scripts/pdf_report.py` — primary engine, HTML/CSS/Jinja2 pipeline. KHÔNG có trên Cloud Python 3.14 (brotli/zopfli wheel) |
| **xhtml2pdf** | ≥ 0.2.16 | **PDF từ HTML/CSS** (tier-2) | ★★ pure Python, CSS cơ bản | Fallback tier-2 — chạy được trên Cloud. Hỗ trợ table/color/font/page-break, KHÔNG hỗ trợ flexbox/grid/`@top-right` (đã strip auto trong `_strip_unsupported_css`) |
| **Plotly** | ≥ 6.0 | **Biểu đồ tương tác** | ★★★ professional charts | Biểu đồ trên web (drag/zoom/hover). Static PNG → embed PDF qua `kaleido` (chỉ local) |
| **Matplotlib** | ≥ 3.8 | **Biểu đồ cho PDF + fallback** | ★★ simple & fast | Sơ đồ CDM, soil column, mặt cắt. **BẮT BUỘC dùng MPL cho mọi chart embed PDF trên Cloud** (kaleido không khả dụng) |
| **Pandas** | ≥ 2.0 | **Xử lý dữ liệu + Bảng** | ★★★ easy data | `read_csv/read_excel`, `DataFrame.to_html()` cho table render |
| **SymPy** | ≥ 1.14 | **Công thức symbolic** | ★★★ math symbolic | Derive công thức parametric ($\sigma = f(\epsilon)$), latex output |
| **LaTeX (MathJax/KaTeX)** | — (built-in) | **Render công thức** | ★★★ standard | `$$...$$` trong `st.markdown` (web) + WeasyPrint MathML (PDF); chuẩn hoá tất cả công thức |
| **ReportLab** | ≥ 4.0 | **PDF programmatic** (tier-3) | ★★★ full control | `scripts/pdf_export.py` + tier-3 fallback trong `pdf_report.py` — text-only khi cả weasyprint+xhtml2pdf đều fail |
| **Kaleido** | ≥ 1.0 | Plotly fig → PNG | — | CHỈ LOCAL — không có wheel cp314. Trên Cloud: vẽ lại bằng Matplotlib |
| **Jinja2** | ≥ 3.1 | HTML template | — | `_REPORT_TEMPLATE` trong `pdf_report.py` |
| **NumPy** | ≥ 1.26 | Tính toán array | — | Mọi tính toán số |
| **openpyxl + xlrd** | — | Đọc Excel | — | `.xlsx` (openpyxl), `.xls` cũ (xlrd) |

**Quy tắc bắt buộc**:

1. **PDF báo cáo** — pipeline 3-tier auto-fallback trong `scripts/pdf_report.py::build_report_pdf(engine="auto")`:
   - **Tier-1 WeasyPrint** (local Windows có GTK3) — HTML/CSS chất lượng cao nhất
   - **Tier-2 xhtml2pdf** (Cloud Python 3.14) — pure Python, CSS cơ bản, tự strip `@top-right`/`string-set` không hỗ trợ
   - **Tier-3 ReportLab** — programmatic, text-only fallback nếu cả 2 tier trên fail
   - Gọi `build_report_pdf(...)` không cần truyền `engine` — auto chọn tier khả dụng đầu tiên
   - **Layout cao cấp A4 (cập nhật 2026-05-22)**: cover page (eyebrow + brand-bar navy+gold + serif title + meta key-value + footer strip) · TOC tự sinh (dot-leaders) · running header bottom-bordered (doc title trái / section title phải) · running footer (meta trái / "Trang X / Y" phải) · h1 chapter (page-break-before: always) · h2 với gold left-border · h3 với `▸` accent · tables zebra + `thead` lặp khi tách trang + tabular numerals · status pills `.badge.{pass,fail,warn,info}` · metric cards `metric_row(metric_card(...))` · callouts `.callout.{info,warning,success,danger}` · pull quote · signature block 3 cột (người lập / kiểm tra / phê duyệt) · auto-numbered figure/table caption qua CSS counter (Hình `<section>.<n>`, Bảng `<section>.<n>`)
   - Helpers mới: `figure(b64, caption)`, `badge(text, kind)`, `callout(body, kind, title)`, `pull_quote(text)`, `metric_row(*cards)`, `section_marker(title)`
   - `build_report_pdf()` thêm args: `eyebrow`, `toc`, `toc_items`, `signatures`, `doc_title_running`, `doc_meta_running`

2. **Biểu đồ tương tác trên web** → **Plotly** (drag/zoom/rotate/hover). KHÔNG dùng Matplotlib cho web charts trừ fallback.

3. **Biểu đồ kỹ thuật cố định** (sơ đồ CDM, mặt cắt, soil column) → **Matplotlib** (đơn giản, kiểm soát chính xác layout).

4. **Bảng** → **Pandas DataFrame** → render qua `st.dataframe()` trên web, `df.to_html()` trong PDF. KHÔNG xây bảng thủ công bằng list-of-lists.

5. **Công thức — BẮT BUỘC dùng LaTeX MathJax** (chuẩn render thống nhất toàn dự án):

   | Tình huống | Cú pháp | Ví dụ |
   |---|---|---|
   | Inline trong câu văn | `$...$` | `Hệ số $C_c = 0.45$` |
   | Display block (1 dòng) | `$$...$$` | `$$E_c = 75 \cdot C_c$$` |
   | Display block (Streamlit) | `st.latex(r"...")` | `st.latex(r"S = \frac{q H}{E}")` |
   | Có giá trị động | f-string + `st.latex(rf"...")` | `st.latex(rf"q = {q:.1f} \text{{ kPa}}")` |
   | Symbolic derivation | `sympy.latex(expr)` → embed `$$...$$` | `f"$${sp.latex(expr)}$$"` |
   | Trong WeasyPrint PDF | LaTeX → MathML qua `latex2mathml` | (tự động trong `pdf_report.py`) |

   **Quy ước ký hiệu**:
   - Subscript: `\sigma'_{vf}`, `H_{\text{soft}}`, `E_{\text{composite}}` (text mode khi nhiều chữ)
   - Phân số: `\frac{tử}{mẫu}` hoặc `\dfrac{}{}`(display lớn)
   - Tích phân/Σ: `\sum_{i=1}^{n}`, `\int_{0}^{H}`
   - Phẩy (effective stress): `\sigma'_v` (apostrophe sau ký tự)
   - Đơn vị: `\text{kPa}` (text mode trong math) — KHÔNG ghi đơn vị thô `kPa`
   - Tham chiếu: `\cdot` (nhân), `\leq`/`\geq` (≤/≥), `\Delta` (Δ)

   **Pitfalls cần tránh**:
   - **F-string + LaTeX brace conflict**: `\dfrac{X}{Y}` xung đột với f-string interpolation. Fix: tách `st.markdown(r"""...""")` cho LaTeX tĩnh + `st.markdown(f"...")` cho số.
   - KHÔNG dùng ASCII math (`Si = Hi × Cc/(1+e0) × log(σvf/σv0)`) — chỉ LaTeX.
   - KHÔNG render công thức bằng Matplotlib `usetex` (chậm + cần TeX runtime). Để LaTeX cho Streamlit/WeasyPrint xử lý.

6. **Pipeline báo cáo PDF chuẩn**: `pandas` (input) → `numpy + sympy` (calc) → `plotly + matplotlib` (figs, → PNG qua kaleido) → `pandas.to_html + CSS` (tables) → `Jinja2` template → `WeasyPrint` HTML→PDF.

**Yêu cầu Cloud**: `packages.txt` cài 7 apt libs cho WeasyPrint (libpango, libcairo, libharfbuzz, libgdk-pixbuf, libffi-dev, shared-mime-info).

**Yêu cầu local Windows**: WeasyPrint cần GTK3 runtime (https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer). Nếu thiếu → tự fallback `pdf_export.py` (reportlab).

### 15. Số liệu Giả định — Lấy từ HK Gần nhất (KHÔNG hardcode)

**Quy tắc:** Mọi giá trị giả định (su, γ, Cc, Cs, e0, PC, Cv, ...) khi hố khoan hiện tại KHÔNG có thí nghiệm cho lớp đó → **BẮT BUỘC tra cứu từ HK gần nhất** cùng khu vực có dữ liệu, từ SQLite. **KHÔNG dùng hằng số hardcode** (`SU_BY_SYMBOL`, `GAMMA_DEFAULT_BY_SYMBOL`...).

**Why:** Hằng số mặc định không phản ánh điều kiện thực địa. Số liệu HK gần nhất (cùng khu vực, cùng symbol đất) đại diện chính xác hơn — đặc biệt cho lớp '1b'/'XMD' thiếu thí nghiệm ở nhiều HK trên tuyến.

**How to apply:**

1. **Priority chain mới** cho mọi field:
   ```
   1. HK hiện tại (VST/lab có giá trị) — source = 'VST'/'lab'
   2. HK gần nhất cùng zone có data (cùng symbol) — source = 'lab_from <BH-name> (d=<dist>m)'
   3. Mặc định hardcode (CẢNH BÁO mạnh) — source = 'default (warn)'
   ```

2. **Helper bắt buộc** trong `scripts/ke_sw_nt_calc.py`:
   ```python
   def _find_nearest_bh_with_data(bh_name, symbol, field, db_path) -> tuple:
       """Return (value, source_bh_name, distance_m) — None nếu không tìm thấy.
       field: 'gamma_kNm3', 'Cu_UU_kPa', 'c_kPa', 'Cc', 'Cs', 'PC_kPa', ...
       """
   ```
   Khoảng cách = √((x1-x2)² + (y1-y2)²) từ `boreholes.x_coord_m`, `y_coord_m`.

3. **Hiển thị rõ trên UI**: warning + tooltip phải ghi:
   - Tên HK gốc lấy giá trị (vd "KE-HK1")
   - Khoảng cách (vd "d=85m")
   - Giá trị + nguồn (vd "γ=15.4 kN/m³ from KE-HK1 (d=85m, lab)")

4. **PDF báo cáo** ghi rõ cột "Nguồn dữ liệu" cho mỗi giá trị giả định.

5. **Cấm**:
   - Dùng `SU_BY_SYMBOL[symbol]` mà không tìm HK gần trước
   - Báo cáo giá trị giả định mà không ghi rõ HK gốc
   - Silent fallback (warning phải hiển thị nổi bật)

### 16. Module Cọc Ván SW Dự Ứng Lực — Kè Công Viên (KE)

**Trang app:** `"ke_sw"` trong `app_cdm.py`, sidebar label "Cọc ván SW (Kè)"  
**Dữ liệu:** `data/sw_pile_catalog.json` (22 loại cọc) + `data/ke_sw_202605_TTHC.json` (12 HK TTHC)

#### Quy tắc nguồn dữ liệu Mục B (cập nhật 2026-05-22)

**Hai nguồn, hai vai trò — KHÔNG trộn lẫn:**

| Nguồn | Loại dữ liệu | Lý do |
|-------|-------------|-------|
| `ke_sw_nt_detail` (SQLite) | **Computed** — Z_m, D_bottom_soft_m, L_req_nt1_m, nt1_result, nt2_result, Rs/Rp/RR/W_kN, ratio_nt2 | Tính bởi `ke_sw_nt_calc.py`; luôn tươi sau mỗi recalc |
| `ke_sw_202605_TTHC.json` | **Config** — recommended_pile, recommended_L_m, note, on_sw_alignment | User decisions; không bao giờ stale vì không computed |

**Pattern bắt buộc trong Mục B:**
```python
# Load TRƯỚC khi dùng (tải 1 lần)
_nt_detail = {r["bh_name"]: dict(r) for r in sqlite3.execute("SELECT * FROM ke_sw_nt_detail")}

# Trong loop: SQLite primary, JSON fallback
_db = _nt_detail.get(f"KE-{_bh['name']}") or {}
_L_req   = float(_db.get("L_req_nt1_m") or _bh.get("L_req_m") or 0)
_z       = float(_db.get("Z_m") or _bh.get("Z_m") or 0)
_h1      = float(_db.get("D_bottom_soft_m") or _bh.get("H_layer1_m") or 0)
_nt1_val = _db.get("nt1_result") or _bh.get("NT1")
```

**KHÔNG được:**
- Đọc Z_m/H_layer1_m/L_req_m/NT1/NT2/Rs/Rp trực tiếp từ JSON dict `_bh` trong Mục B
- Hardcode fallback `or 22.0`, `or "SPECIAL"` cho bất kỳ computed field nào

#### Bố cục — trải phẳng từ trên xuống dưới (cập nhật 2026-05-19)

Không dùng `st.tabs()` — toàn bộ nội dung trải thẳng đứng để in PDF được.

| Mục | Tiêu đề | Nội dung |
|-----|---------|---------|
| A | `### A. Catalog tiết diện SW` | Bảng 22 loại SW (H, t, cáp, Atd, Itd, Mcr, EI, TL, L_min/max), selectbox fc → Ec, biểu đồ Mcr vs H |
| B | `### B. Kết quả thiết kế — Kè Công Viên TTHC` | Chỉ 7 HK trên tuyến kè (`on_sw_alignment=True`). Bảng `st.data_editor` với 2 cột editable + nút "Dùng cọc tối ưu cho tất cả" |
| C | `### C. Kiểm tra NT1 / NT2 — nhập thông số tùy chỉnh` | Layout 2 cột: trái = form input (3 col + mực nước + liên kết đáy), phải = sơ đồ cọc GEO5-style live (`draw_pile_schematic`) |

Mỗi mục ngăn cách bằng `st.divider()`.

#### Mục B — Chi tiết bảng `st.data_editor` (cập nhật 2026-05-19)

**Cột read-only:** Z (m), D_bot_soft (m), L yêu cầu (m), Cọc tối ưu, L_max (m), Đủ chiều dài, NT1, NT2, Rs/Rp/RR/W/RR-W, Ghi chú  
**Cột editable:**

| Cột | Widget | Mặc định | Lưu |
|-----|--------|---------|-----|
| `Cọc kiến nghị` | `SelectboxColumn` — 19 loại SW | JSON `recommended_pile` → cọc tối ưu | `session_state["ke_sw_rec_piles"]` |
| `L thiết kế (m)` | `NumberColumn` step 0.5 | `L_max` của cọc kiến nghị đang chọn | `session_state["ke_sw_L_thiet_ke"]` |

**Nút "Dùng cọc tối ưu cho tất cả":** reset cả hai cột về cọc nhỏ nhất có `L_max ≥ L_req` và `L_max` tương ứng.

**Logic chọn cọc tối ưu:** `_catalog_sorted` (sort H_mm tăng dần) → `first where L_max_m >= L_req`.

**Cache buster:** `_load_ke_sw(_mtime)` truyền `file.stat().st_mtime` làm arg → cache tự invalidate khi JSON thay đổi trên disk.

#### Mục C — Sơ đồ cọc GEO5-style

Hàm `draw_pile_schematic(...)` copy từ `app_coc_tai_ngang.py`, đặt trên cùng file `app_cdm.py` (trước `@st.cache_data`). Yêu cầu `matplotlib` (đã có trong `requirements.txt`). Import qua `try/except` → `_HAS_MPL` flag.

#### Tiêu chuẩn kiểm tra

- **NT1:** `L_des ≥ L_req = fill_m + D_bottom_soft + min_pen`
  - `fill_m = max(0, top_ke − Z_m)` — phần cọc trong đất đắp phía trên cổ hố khoan
  - `D_bottom_soft` = chiều sâu từ cổ HK đến **đáy** lớp mềm cuối — KHÔNG phải tổng chiều dày
  - **KHÔNG dùng** `top_ke + H_soft + min_pen` (sai khi Z_m ≠ top_ke)
- **NT2:** `RR = φ_stat × (Rs + Rp) ≥ W_cọc`  |  `φ_stat = 0,35`  |  bỏ qua đất đắp khi tính Rs
  - `Rs = α × Su × P × L_soil`  |  `Rp = 9 × Su × Ap`
  - `W_cọc = (TL_T × 9,81 / L_std) × L_des`
- **Su ưu tiên:** VST (`vane_shear_tests`) > lab (`lab_tests`) > `SU_BY_SYMBOL` mặc định (cảnh báo)
- **SQLite schema:** `ke_sw_nt_detail` (cột `D_bottom_soft_m`, `D_source`) + `ke_sw_nt2_layers` + `ke_sw_winkler_results` (nội lực Winkler — PRIMARY KEY `(bh_name, pile_type, L_m, load_case)`, cột chính `u_max_mm`, `M_max_kNm`, `Mcr_kNm`, `Q_max_kN`, `mcr_ratio`, `u_ok`, `mcr_ok`, `solver`, `ts`). Hàm `save_winkler_results_to_db()` / `load_winkler_results()` trong `scripts/wall_internal_force.py` — INSERT OR REPLACE, idempotent, tự create table

#### Kết quả TTHC (Kè KE, cập nhật 2026-05-19)

- **HK kiểm soát NT1: KE-HK10 — KHÔNG ĐẠT** với SW-940 L=29m (biên=−0,1m) → cần L≥29,5m
- HK kiểm soát NT2: KE-HK7 (ratio=1,96 — nhỏ nhất)
- Không hiển thị "BETON 6" trong app — chỉ hiển thị thông số kỹ thuật trung tính

---

### 17. Sidebar Navigation — Button-based Grouped Menu (cập nhật 2026-05-19)

Thay `st.sidebar.radio()` bằng `st.sidebar.button()` để hỗ trợ nhóm menu có header.

#### Cấu trúc menu

```
[Địa chất]            → "geology"
[Kiểm tra mẫu TN]    → "sample_check"
**TKCS CDM**
  [Thông số]          → "params"
  [So sánh PA]        → "compare"
  [Kết quả CDM]       → "compare"
  [Dự báo độ lún]     → "settlement"
  [Xuất kết quả]      → "export"
[TKBVT CDM]           → "cdm_bvt"   (placeholder)
**TKCS Cọc ván**
  [Cọc ván SW (Kè)]  → "ke_sw"
[TKBVT Cọc ván]       → "sw_bvt"    (placeholder)
```

#### Pattern code

```python
if "_page" not in st.session_state:
    st.session_state["_page"] = "geology"

def _nav(label: str, pid: str, indent: bool = False) -> None:
    if st.sidebar.button(
        ("    " if indent else "") + label,
        key=f"_nav_{pid}",
        use_container_width=True,
        type="primary" if st.session_state.get("_page") == pid else "secondary",
    ):
        st.session_state["_page"] = pid
        st.rerun()

_page = st.session_state.get("_page", "geology")
```

**Quy tắc:** Nút active = `type="primary"` (xanh), còn lại = `"secondary"`. Header nhóm dùng `st.sidebar.markdown("**TKCS CDM**")`. KHÔNG dùng `st.sidebar.radio()` — không hỗ trợ header giữa các item.

---

### 18. Tab "Xuất kết quả" — Word Export Header/Footer (cập nhật 2026-05-19)

**Vị trí:** `app_cdm.py`, `elif _page == "export":`, cột `c_word`

#### Input fields (session state)

| Key | Widget | Mô tả |
|-----|--------|-------|
| `export_co_name` | `st.text_input` | Tên công ty → header phải |
| `export_co_staff` | `st.text_input` | Nhân sự thực hiện → footer trái |
| `export_logo_bytes` | `st.session_state` (bytes) | Logo PNG/JPG → header trái (cao 1,2 cm) |

Logo được lưu vào `session_state["export_logo_bytes"]` khi `file_uploader` trả về file — giữ nguyên khi người dùng chuyển tab rồi quay lại.

#### Hàm `_export_word_bytes` — signature

```python
def _export_word_bytes(
    scenarios, params, rec_idx,
    co_name="", co_staff="", logo_bytes=None
) -> bytes:
```

#### Header/Footer pattern (python-docx)

```python
# Chèn PAGE / NUMPAGES field
def _field_run(para, field: str) -> None:
    run = para.add_run()
    fc_b = OxmlElement("w:fldChar"); fc_b.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.text = field
    instr.set(qn("xml:space"), "preserve")
    fc_e = OxmlElement("w:fldChar"); fc_e.set(qn("w:fldCharType"), "end")
    run._r.append(fc_b); run._r.append(instr); run._r.append(fc_e)

sec = doc.sections[0]
_pw = sec.page_width - sec.left_margin - sec.right_margin  # EMU

# Header 2 cột: logo trái | tên công ty phải
ht = sec.header.add_table(1, 2, width=_pw)
ht.cell(0, 0).width = Cm(3)
ht.cell(0, 1).width = _pw - Cm(3)
# logo: ht.cell(0,0).paragraphs[0].add_run().add_picture(io.BytesIO(logo_bytes), height=Cm(1.2))
ht.cell(0,1).paragraphs[0].alignment = RIGHT
H._fmt(ht.cell(0,1).paragraphs[0].add_run(co_name), size=9, bold=True)

# Footer 2 cột: nhân sự trái | Trang X/Y phải
ft = sec.footer.add_table(1, 2, width=_pw)
ft.cell(0, 0).width = _pw - Cm(3)
ft.cell(0, 1).width = Cm(3)
H._fmt(ft.cell(0,0).paragraphs[0].add_run(co_staff), size=9)
pg = ft.cell(0,1).paragraphs[0]; pg.alignment = RIGHT
H._fmt(pg.add_run("Trang "), size=9)
_field_run(pg, "PAGE")
H._fmt(pg.add_run(" / "), size=9)
_field_run(pg, "NUMPAGES")
```

**Xóa border bảng:** tạo hàm `_no_tbl_border(tbl)` dùng `OxmlElement("w:tblBorders")` với `w:val="none"` cho 6 cạnh.

**Chiều rộng usable width:** `sec.page_width - sec.left_margin - sec.right_margin` (EMU int) — dùng cho `width=` của cả 2 bảng header và footer.

---

### 18b. Quy tắc Báo cáo Word — Luôn Cập nhật, Đầy đủ, Tiếng Việt (cập nhật 2026-05-22)

**Nguyên tắc bắt buộc cho mọi báo cáo Word xuất từ app:**

#### Nội dung phải luôn mirror app

| Mục trong app | Phải có trong Word | Nguồn dữ liệu |
|---|---|---|
| Bảng thông số thiết kế per HK | Section 1 — bảng tổng hợp | SQLite `ke_sw_nt_detail` (KHÔNG từ JSON) |
| Cơ sở lý thuyết + công thức | Section 2 — formula images (matplotlib mathtext) | Hard-coded từ tiêu chuẩn |
| Tổng hợp NT1/NT2/Nội lực | Section 3 — bảng tổng hợp đầy đủ | SQLite `ke_sw_nt_detail` + kết quả Winkler |
| Biểu đồ nội lực per HK | Section 4 — 5 panel mỗi HK | Runtime compute |
| Ổn định tổng thể | Section 5 — bảng Fs + biểu đồ bar 3 phương pháp | SQLite ổn định |
| Kết luận & Kiến nghị | Section 6 | Auto-generate từ kết quả |

**Thiếu bất kỳ mục nào = lỗi cần sửa ngay.**

#### Header / Footer bắt buộc

- Header trái: logo công ty (`session_state["export_logo_bytes"]`) | Header phải: tên công ty
- Footer trái: nhân sự thực hiện | Footer phải: "Trang X / Y" (PAGE/NUMPAGES field)
- Hàm `_field_run7(para, "PAGE")` / `_field_run7(para, "NUMPAGES")` dùng OxmlElement

#### Tiếng Việt có dấu — BẮT BUỘC

- **MỌI** chuỗi hiển thị trong Word phải dùng tiếng Việt có dấu đầy đủ
- **CẤMS:** "Dat"/"Khong dat" → phải là "Đạt"/"Không đạt"
- **CẤMS:** "Ket qua:", "Ket luan", "Kien nghi", "On dinh" → phải có dấu
- **CẤMS:** `st.spinner(...)`, `st.success(...)`, `st.error(...)`, `st.download_button(...)` cũng phải tiếng Việt có dấu
- Tên cột bảng, nhãn trục biểu đồ (ylabel, title) — tất cả phải tiếng Việt có dấu
- `matplotlib` với font mặc định render OK tiếng Việt khi dùng Unicode literal; không cần thay đổi font

#### Checklist trước khi báo cáo Word "xong"

- [ ] Tất cả heading tiếng Việt có dấu
- [ ] Tất cả cell bảng: "Đạt"/"Không đạt" (không phải "Dat"/"Khong dat")
- [ ] Tất cả paragraph body text tiếng Việt
- [ ] Nhãn trục biểu đồ tiếng Việt
- [ ] Spinner/success/error/download button text tiếng Việt
- [ ] Header + footer đã setup (logo | company | page numbering)
- [ ] Section 1 đọc từ SQLite `ke_sw_nt_detail` (không từ JSON)

---

### 19. Quy tắc Định dạng Công thức trong File *.md

**File tham chiếu chuẩn:** [`41-cdm-choc-thung-dem-ximang.md`](41-cdm-choc-thung-dem-ximang.md)

#### Quy tắc bắt buộc

| Tình huống | Dùng | KHÔNG dùng |
|---|---|---|
| Công thức hiển thị (block) | `$$...$$` trên dòng riêng | Code block `` ``` `` hay inline `` ` `` |
| Ký hiệu / biến trong văn bản | `$...$` | Backtick `` `sigma_v0` `` hay ASCII |
| Mỗi phương trình | Một block `$$...$$` riêng | Gộp nhiều phương trình trong 1 block |
| Điều kiện trường hợp | Text label trước + `$$...$$` | Chú thích trong dòng code |

#### Cú pháp LaTeX chuẩn của dự án

- **Phân số:** `\frac{tử}{mẫu}` (inline: `\dfrac`)
- **Ký hiệu Hy Lạp:** `\alpha \beta \gamma \delta \sigma \tau \varphi \pi`
- **Nhân:** `\times` (giữa hai đại lượng) hoặc `\cdot` (tích vô hướng)
- **Hàm mũ:** `\exp\!\left(...\right)`
- **Log:** `\log_{10}`, `\ln`
- **Căn:** `\sqrt{}`
- **Chỉ số dưới/trên:** `_{...}` / `^{...}` — dùng `{}` khi hơn 1 ký tự
- **Tham chiếu tiêu chuẩn:** `\qquad \text{(C.1)}` hoặc `\qquad \text{(công thức 38)}`
- **Dấu phẩy thập phân trong LaTeX:** `1{,}5` (không dùng `1.5` cho số Việt)

#### Cấu trúc mỗi khối công thức

```markdown
**Tên trường hợp / điều kiện (nếu có):**

$$\text{công thức LaTeX}$$

Trong đó:
- $ký_hiệu$ — mô tả ngắn (đơn vị)
- ...
```

#### Bảng ký hiệu cuối section

Dùng bảng Markdown 3 cột: `$Ký hiệu$` | `Đơn vị` | `Mô tả`. Đặt sau nhóm công thức liên quan.

---

### 20. Quy ước Front / Back — Tường Cừ SW (BẮT BUỘC toàn dự án)

Áp dụng cho mọi script, JSON, biểu đồ, app liên quan đến tường cừ SW / sheet pile / tường chắn.

**Cừ SW là tâm sơ đồ.** Mặt đất + lớp đất hai bên thường khác nhau (Front có fill cao hơn, Back đào xuống thấp).

| Phía | Vị trí trên sơ đồ | Bản chất vật lý | Áp lực chính | Có fill ? | Màu chuẩn |
|---|---|---|---|---|---|
| **Front** | **TRÁI** | Đất đắp / mặt đường / xe chạy / người đi / tải trọng công trình | **Active (Ka)** — đẩy cừ về phía Back | **Có** (fill cao hơn cừ) | Tomato / `#1a8cff` |
| **Back** | **PHẢI** | Đào / sông / mặt nước hở | **Passive (Kp)** — chỉ phát triển dưới đáy đào, kháng lại chuyển vị cừ | Không | Green / `steelblue` |

**Quy tắc đặt tên biến trong code:**

| Biến / dataclass field | Ý nghĩa |
| --- | --- |
| `soil_level_front` | Cao độ mặt đất phía Front = cao độ chân đất đắp (THƯỜNG LÀ MẶT ĐẤT TỰ NHIÊN, cao) |
| `soil_level_back` | Cao độ mặt đất phía Back = cao độ đáy đào (THẤP HƠN front) |
| `water_elev_front` / `water_elev_back` | Mực nước 2 phía (có thể khác) |
| `front_layers` | Danh sách lớp đất tự nhiên phía Front (dưới `soil_level_front`) |
| `back_layers` | Danh sách lớp đất tự nhiên phía Back (dưới `soil_level_back`) |
| `fill` | Lớp đất đắp phía Front, nằm từ `soil_level_front` lên đến `top_elev` |
| `surcharge_front` | Tải mặt phân bố phía Front (kPa) — tải hoạt, xe, người |
| `sv_front`, `sigma_h_active` | Ứng suất đứng + áp lực ngang Active phía Front |
| `sv_back`, `sigma_h_passive` | Ứng suất đứng + áp lực ngang Passive phía Back |

**Áp lực NET tổng hợp (kN/m²) — chọn theo mô hình:**

| Mô hình | Công thức p_net | Ghi chú |
| --- | --- | --- |
| `mode='winkler'` (có lò xo nền) | `p_net = sigma_h_active + p_w_front − p_w_back` | Lò xo Winkler tự đảm nhiệm phản kháng bị động. KHÔNG được trừ `sigma_h_passive` ở đây — sẽ DOUBLE-COUNT. |
| `mode='free_earth'` (không lò xo, tính D ngàm) | `p_net = (sigma_h_active + p_w_front) − (sigma_h_passive + p_w_back)` | Cổ điển, cân bằng tĩnh ΣM=0 quanh điểm xoay. |

**Quy ước dấu:** Net dương → đẩy cừ từ Front sang Back (theo chiều tải trọng đất đắp + xe). Nội lực M dương khi sợi căng phía Front.

**File tham chiếu:**
- `scripts/wall_internal_force.py` — solver Winkler PyNiteFEA + tải phân bố
- `scripts/earth_pressure.py` — engine áp lực đất Active/Passive
- `scripts/water_pressure.py` — áp lực nước Hydrostatic/Seepage 2 phía
- Memory: `memory/feedback_front_back_convention.md`

---

### 21. CSS `@media print` cho Ctrl+P trình duyệt (BẮT BUỘC)

Khi user in PDF qua Ctrl+P trên 8503, các vấn đề thường gặp + cách fix.

| Vấn đề | Nguyên nhân | Fix CSS |
|---|---|---|
| Plotly chart trống ở giữa | Wildcard `* { position: static !important }` đè lên `position: absolute` của Plotly internals | **KHÔNG** override position toàn cục. Chỉ override cho `[data-testid="stSidebar/stHeader/stToolbar/stMainBlockContainer/stAppViewBlockContainer"]`, `.main`, `.block-container` |
| Plotly chart hiện 2-3 lần | Streamlit để `display:none` cho DOM stale; CSS ép `display:block` hiện tất cả | Bỏ ép display:block cho `.js-plotly-plot` / `.main-svg`. Rule ẩn duplicate: `.stPlotlyChart .js-plotly-plot ~ .js-plotly-plot { display: none }` |
| Công thức KaTeX lặp 2 lần (HTML + MathML) | `.katex-mathml` (screen reader) hiện ra khi `position: revert` | Ép ẩn cứng: `.katex-mathml { display:none; visibility:hidden; clip:rect(0,0,0,0); position:absolute }` |
| Dấu Việt + subscript trôi loạn | Wildcard `* { height: auto }` đè lên glyph stack KaTeX | Restore với `.katex *, .katex-html *, span.katex * { height: revert; position: revert; vertical-align: revert; line-height: revert }` |
| Bảng `st.dataframe` đè công thức `st.latex` phía dưới | Glide Data Grid canvas height cố định ~280px | Chuyển sang `st.table` cho bảng nhỏ; CSS fallback: `[data-testid="stDataFrame"] { min-height: fit-content; height: auto }` |
| Chart matplotlib pyplot tràn trang A4 | Không giới hạn chiều cao | `.stPyplot img, [data-testid="stPyplot"] img { max-height: 22cm; object-fit: contain }` |
| Hàng 2 cột (label+chart, label+chart) tách trang | label + pyplot là 2 element riêng | `[data-testid="stHorizontalBlock"] { break-inside: avoid }` (KHÔNG áp dụng cho `stColumn` / `stVerticalBlock` — quá rộng, gây gap lớn) |
| Heading + content kế tiếp tách trang | — | `[data-testid="stMarkdownContainer"] h1-h6, strong { break-after: avoid }` |

**JS handler `beforeprint`:** mở tất cả `<details>` + gọi `Plotly.Plots.resize()` cho mọi `.js-plotly-plot` → force redraw trước khi Chrome capture print preview + `scrollTo(0,0)`.

**File tham chiếu:** `scripts/app_cdm.py` block CSS `@media print` (line ~3335) + JS `beforeprint` (line ~3436). Memory: `feedback_browser_print_css.md`.

**Quy tắc khi áp dụng:**

1. **Bảng nhỏ ≤20 dòng, là reference/lookup** → dùng `st.table(df)` thay `st.dataframe`. Đặc biệt khi sau bảng có `st.latex` hoặc nội dung khác.
2. **Bảng có `column_config` (format số), `style.map` (color highlight), cần scroll** → giữ `st.dataframe`, dựa vào CSS fallback.
3. **Công thức tổng quát (chung mọi HK)** → KHÔNG đặt trong vòng lặp HK; tách ra **1 expander chung** trước vòng lặp, đặt suffix `"(chung cho mọi HK)"`. Mỗi HK chỉ render kết quả riêng.
4. **PDF qua nút app** → user yêu cầu ẩn (Streamlit canvas + Plotly iframe không reliable cho server-side render). Gate bằng `_HAS_PDF = False`. User dùng Ctrl+P browser + Word export.

---

### 22. Trắc dọc địa chất + Bình đồ HK ở Mục B (Cọc ván SW)

Hai khung view nhúng ngay sau bảng `data_editor` của Mục B, trước biểu đồ NT2 ratio.

**Trục X chainage qua PCA SVD:** chiếu `(x_coord_m, y_coord_m)` HK lên trục chính của tập điểm → tuyến đi qua tất cả HK theo đúng thứ tự dọc.

**Inputs (3 cột):** Cao độ đỉnh kè TK · Cao độ mặt nước · Lớp dưới muốn vẽ (selectbox từ symbol ≠ '1').

**Đường vẽ Plotly (chính):**
- Mặt đất tự nhiên (nâu, marker tròn)
- Lớp 1 bùn — fill `_LAYER_COLORS['1']` + line đáy
- Lớp dưới user chọn — fill + line đỉnh/đáy (▲▼)
- Đáy lớp đất yếu — đường hồng đứt + ◆ — từ `ke_sw_nt_detail.D_bottom_soft_m`
- **Mũi cọc TK** — cam, ▼, có **đường nối liền** giữa các điểm
- Đỉnh kè TK + mặt nước (hlines)

**Hover (per layer per HK):** symbol, độ sâu, cao độ, su VST/Lab, N̄-SPT — query 1 lần từ SQLite `vane_shear_tests` + `lab_tests` + `spt_values`.

**Matplotlib double-render:** lưu vào `st.session_state["_ke_b_profile_mpl_fig"]` + expander thu gọn "Bản Matplotlib (dùng cho PDF)". Tương tự cho bình đồ.

**Bình đồ vị trí:** Plotly scatter X=Northing, Y=Easting, **tỷ lệ trục 1:1** (`scaleratio=1`); annotation khoảng cách Euclidean giữa các cặp HK liên tiếp; bảng `st.table` khoảng cách + tổng chiều dài.

**Live link:** đổi multiselect HK / cọc / L thiết kế trong bảng data_editor → trắc dọc + bình đồ tự cập nhật.

**Helper bắt buộc:**
```python
def _hex_to_rgba(hex_str: str, alpha: float) -> str:
    # Plotly 6.x KHÔNG chấp nhận hex 8 ký tự #RRGGBBAA
    # → phải convert sang rgba(R,G,B,alpha)
```

**File tham chiếu:** `scripts/app_cdm.py` ~line 8160-8800. Memory: `project_tracdoc_binhdo_mucB.md`.

---

### 23. Ẩn tên kỹ thuật trên UI (BẮT BUỘC)

Mọi text hiển thị trên 8503 (`st.markdown`, `st.caption`, `st.info`, `st.warning`, `st.error`, `help=`, expander label) KHÔNG được chứa:

- Tên thư viện: `SQLite`, `matplotlib`, `plotly`, `numpy`, `pandas`, `reportlab`, `weasyprint`, `streamlit`...
- Đuôi file: `.py`, `.md`, `.json`, `.sqlite`, `.xlsx`, `.xls`, `.csv`, `.dxf`, `.dwg`
- Tên bảng SQL: `lab_tests`, `vane_shear_tests`, `ke_sw_nt_detail`, `boreholes`, `layers`, `spt_values`, `ke_sw_winkler_results`, `ke_sw_stability`...
- Tên hàm/biến code: `_db()`, `_load_layers()`, `_HAS_PDF`...
- Tiếng Anh thuần không cần thiết: `Auto` → `Tự chọn`, `tip method` → `Phương pháp mũi`

**Thay thế chuẩn (đã đúc kết 2026-05-22):**

| Trước | Sau |
|---|---|
| "Kết quả lưu SQLite" | "Kết quả được lưu" |
| "lưu vào bảng scenario SQLite riêng" | "lưu vào kịch bản riêng" |
| "thí nghiệm UU trong SQLite" | "thí nghiệm cắt cánh hiện trường (VST) hoặc UU phòng" |
| "nguồn: SQLite" | "nguồn: thí nghiệm" |
| "Đáy bùn (NT detail)" | "Đáy lớp đất yếu (tính NT1)" |
| `Auto` (phương pháp NT2) | "Tự chọn" |
| `tip method` (cột bảng) | "Phương pháp mũi" |
| "Không đọc được `ke_sw_winkler_results`" | "Không đọc được kết quả Winkler đã lưu" |
| "Lỗi đọc `ke_sw_stability`" | "Lỗi đọc kết quả ổn định tổng thể" |
| "Kiểm tra `scripts/winkler_np.py`" | "Liên hệ kỹ sư phát triển để kiểm tra môi trường" |

**Vẫn được phép:**

- Tên file user **download** (vd `BaoCao_CDM_HK2_20260522.xlsx`) — đó là tên thật của file output
- Comments trong code (`# ...`) — không hiển thị UI
- Tên hố khoan có prefix zone (`KE-HK6`, `BXN-HK1`, `NHC-BH-03`) — quy ước dự án
- Tên cọc theo catalog (`SW-840`, `SW-940`) — danh pháp kỹ thuật
- Ký hiệu tiêu chuẩn (`TCVN 4253`, `USACE EM 1110-2-2504`, `FHWA GEC-13`)

**Memory tham chiếu:** `memory/feedback_no_tech_names_in_ui.md`.

---

### 24. Thư viện mới cho Word OMML + Typography (cập nhật 2026-05-22)

Cài đặt qua `pip install`:

| Lib | Phiên bản min | Vai trò |
|---|---|---|
| `latex2mathml` | ≥ 3.81 | LaTeX → MathML XML (W3C, bảo toàn dấu Việt) |
| `math2docx` | ≥ 3.1 | LaTeX → MathML → OMML embed vào `python-docx` paragraph |
| `docxtpl` | ≥ 0.20 | Word template Jinja2 — tách logic Python ↔ thiết kế Word (header/footer/watermark phức tạp) |
| `pylatex` | ≥ 1.4 | Mô phỏng object TeX trong Python — dành cho PDF academic chuẩn LaTeX |
| `typst` | ≥ 0.14 | Python binding cho Typst (Rust compiler) — typography next-gen, response <100ms |

**Đã thêm vào** `requirements.txt` + `cdm-deploy/requirements.txt`.

**Cách dùng `math2docx` cho công thức editable trong Word:**

```python
from docx import Document
from math2docx import add_math

doc = Document()
p = doc.add_paragraph("Công thức kiểm tra NT1: ")
add_math(p, r"L_{\text{thiết kế}} \geq L_{\text{yêu cầu}} = (Z_{\text{đỉnh kè}} - Z) + H_{\text{lớp yếu}} + h_{\text{ngàm}}")
doc.save("baocao.docx")
```

Lợi ích so với mathtext PNG cũ:
- Công thức **editable** trong Word (chỉnh được)
- Render đẹp ở mọi zoom (vector OMML, không vỡ)
- File Word nhẹ hơn (không cần PNG mỗi công thức)

**Lưu ý cài Quarto:** `pip install quarto-cli` thất bại trên Windows do MAX_PATH limit (260 ký tự). Phải dùng `winget install Posit.Quarto` hoặc installer từ https://quarto.org. Chưa cần Quarto trong production hiện tại.

---

### 25. Ẩn nút Xuất PDF qua app — user dùng Ctrl+P + Word

User yêu cầu (2026-05-22): bỏ TẤT CẢ nút "Xuất PDF" qua engine server-side. Chỉ giữ:
- Các nút **Xuất Word** (Word export pipeline vẫn dùng)
- **Ctrl+P** trình duyệt → in PDF qua print preview (CSS @media print đã optimize — xem mục 21)

**Cách ẩn:**

```python
# Ép disable PDF engine — gate tất cả nút `if _HAS_PDF:`
_HAS_PDF = False
_PDF_ENGINE = "—"
```

Sau dòng này, các nút sau KHÔNG render (tự động):
- "Xuất PDF Tổng hợp (tất cả tab)" — sidebar
- "Xuất PDF tab Thông số CDM"
- "Xuất PDF tab Dự báo lún"
- "Xuất PDF tab Cọc ván SW"
- "Tải PDF bảng so sánh + biểu đồ"

**Section "Báo cáo PDF tuỳ chỉnh"** trong tab Thông số CDM (checkboxes + 2 nút) **KHÔNG gated** → đã xoá hẳn block ~80 dòng (vì có nội dung `_custom_report_pdf` không phụ thuộc `_HAS_PDF`).

**Sidebar PDF section** (`st.sidebar.markdown("### Xuất PDF")` + caption) **KHÔNG gated** → đã xoá toàn bộ block.

**Khôi phục:** chỉ cần đổi `_HAS_PDF = True`. Các nút trong `if _HAS_PDF:` sẽ tự render lại. Block "Báo cáo PDF tuỳ chỉnh" + sidebar PDF phải khôi phục từ git history.

**Memory:** `feedback_hide_pdf_buttons.md`.

---

## Cấu trúc Code Bắt buộc

### Mọi Script PLAXIS Phải Có

```python
import os
from plxscripting.easy import new_server

# ✓ PASSWORD từ environment variable (KHÔNG hardcode)
PASSWORD = os.environ.get('PLAXIS_PASSWORD', '')

# ✓ Type hints cho mọi hàm
def build_wall_model(g_i, depth: float, thickness: float) -> None:
    ...

# ✓ try/finally để đảm bảo cleanup
try:
    # ... logic chính
finally:
    s_i.close()
    s_o.close()
    process.terminate()
```

### Cấu trúc Phân đoạn Bắt buộc (Staged Construction Script)

```python
# === BƯỚC 1: KHỞI TẠO ===
# === BƯỚC 2: HÌNH HỌC ===
# === BƯỚC 3: VẬT LIỆU ===
# === BƯỚC 4: PHASES ===
# === BƯỚC 5: LƯỚI ===
# === BƯỚC 6: TÍNH TOÁN ===
# === BƯỚC 7: KẾT QUẢ ===
```

---

## Quy trình Xử lý Yêu cầu

### Yêu cầu Mô hình Mới

1. **Đọc** thông số địa tầng và hình học từ user
2. **Xác nhận** đơn vị (hỏi lại nếu không rõ)
3. **Validate** bằng GeoMCP nếu cần tính toán sơ bộ
4. **Viết code** theo cấu trúc 7 bước
5. **Cảnh báo** các điểm cần kỹ sư kiểm tra

### Yêu cầu Gỡ lỗi

1. **Đọc** error log được cung cấp
2. **Phân loại** lỗi (kết nối, cú pháp, hội tụ, đơn vị)
3. **Đề xuất** fix cụ thể
4. **Cảnh báo** nếu lỗi có thể do sai thông số vật lý

### Yêu cầu Phân tích Kết quả

1. **Kiểm tra** tính hợp lý (FoS trong 1.0–5.0, Umax < H/100)
2. **So sánh** với tiêu chuẩn (TCVN, Eurocode 7)
3. **Đề xuất** cải thiện nếu không đạt
4. **Gọi GeoMCP** để xác nhận tính toán thủ công nếu cần

---

## Mapping Tài liệu → Vấn đề Kỹ thuật

| Khi gặp vấn đề | Đọc tài liệu |
|---------------|-------------|
| Cài đặt, kết nối PLAXIS | [01-plaxis-api-setup.md](01-plaxis-api-setup.md) |
| Cú pháp lệnh, tạo hình học | [02-command-reference.md](02-command-reference.md) |
| Trích xuất ResultTypes, structureplot | [03-output-extraction.md](03-output-extraction.md) |
| Kỹ thuật viết prompt cho Claude | [04-claude-prompt-engineering.md](04-claude-prompt-engineering.md) |
| MCP, GeoMCP, SymPy, Pint | [05-mcp-geomcp-framework.md](05-mcp-geomcp-framework.md) |
| Tối ưu hóa NSGA-II, pymoo | [06-nsga2-optimization.md](06-nsga2-optimization.md) |
| Lỗi hội tụ, trình tự cố kết | [07-error-convergence.md](07-error-convergence.md) |
| Pipeline đầu cuối, VIKTOR, BIM | [08-end-to-end-workflows.md](08-end-to-end-workflows.md) |
| Tính lún TCCS41, bấc thấm, giếng cát | [38-tccs41-nen-duong-dat-yeu.md](38-tccs41-nen-duong-dat-yeu.md) + [scripts/settlement_calc.py](scripts/settlement_calc.py) |
| Thiết kế CDM, phân tích mẫu TCVN 9403 | [39-tcvn9403-tru-dat-xi-mang.md](39-tcvn9403-tru-dat-xi-mang.md) + [scripts/cdm_column_calc.py](scripts/cdm_column_calc.py) |

---

## Phân loại Bài toán Địa kỹ thuật & Lưu ý Chuyên biệt

### Hố đào sâu (Deep Excavation)

- Kiểm tra basal heave stability (Fs_heave ≥ 1.5)
- Tường vây: Kết quả qua `ResultTypes.Plate` sau `structureplot()`
- Neo/Strut: Kiểm tra lực dọc trục `Nx2D`
- Pha cố kết nếu đất sét: Dùng `StagedConstruction`, KHÔNG dùng `MinPorePressure`

### Ổn định Mái dốc

- Phương pháp Phi/c Reduction (SRF/SRFEA)
- Pha cuối là Safety phase, không có kết cấu
- FoS qua `phase.Reached.SumMsf` (KHÔNG dùng `phase.SumMsf.value` — lỗi trong PLAXIS 2D 2024)

### Cọc Chịu tải

- Mô hình cọc dạng `Plate` hoặc `EmbeddedBeam`
- Kết quả nội lực: M2D, Q2D, Nx2D
- Kiểm tra độ lún đầu cọc

### Cố kết (Consolidation)

- **Luôn** dùng `StagedConstruction` khi có thay đổi cấu trúc
- `MinPorePressure` / `DegreeOfConsolidation`: chỉ sau SC phase, không sau Plastic
- Kiểm tra tỷ số tiêu tán áp lực lỗ rỗng

---

## Checklist Cuối trước khi Trả lời

Trước mỗi câu trả lời có chứa mã Python PLAXIS:

- [ ] Tất cả tham số đất có đúng đơn vị (phi=°, E=kN/m², gamma=kN/m³)?
- [ ] Có gọi `g_o.structureplot()` trước `ResultTypes.Plate`?
- [ ] Có `try/finally` với cleanup không?
- [ ] Trình tự Staged Construction có đúng kỹ thuật thi công không?
- [ ] Không có MPP/DoC sau Plastic/Dynamic phase không?
- [ ] Password được lấy từ `os.environ` không?
- [ ] Đã kiểm tra `data/*.json` trước khi đọc PDF / Excel / Docs / ảnh chưa?
- [ ] Dữ liệu mới trích xuất đã được lưu vào `data/*.json` chưa?

---

## Ví dụ Phản hồi Chuẩn — Khi Được Yêu cầu Tính toán

**Yêu cầu:** "Tính sức chịu tải móng nông B=1.5m, L=2m trên đất sét có phi=22°, c=30 kN/m²"

**KHÔNG làm:** Tự tính ra con số từ training data.

**ĐÚng làm:**
```
Tôi sẽ tính qua GeoMCP để đảm bảo độ chính xác (sai lệch < 0.15% so với Eurocode 7):

[Gọi MCP Tool: geomcp_calculate]
method: "bearing_capacity_meyerhof"
parameters: {c: 30, phi: 22, q: 18, gamma: 17.5, B: 1.5, L: 2.0}

[Kết quả từ GeoMCP]:
- Nq = 9.19, Nc = 20.63, Ng = 6.98
- qu = 845.3 kN/m²
- qa (Fs=3) = 281.8 kN/m²
```

---

### 26. NT2 Cọc đóng — Đa phương pháp TCVN 11823-10:2017

Engine `scripts/ke_sw_nt_calc.py` tự động chọn phương pháp theo `symbol`:

- **Lớp sét** (mặc định) → α-method (Tomlinson 1980), Điều 7.3.8.6.2, φ_stat = 0,35
- **Lớp cát** (`SAND_SYMBOLS = {F, 2a, 2b, 2c, 4, 5a, 6, 7}`) → SPT-Meyerhof, Điều 7.3.8.6.7, φ_stat = 0,30

**Đơn vị**: TCVN dùng MPa·mm² → engine đổi sang kPa·m² nhân ra kN.
- `qs_kPa = 1.9·N₁₆₀` (cọc chiếm chỗ — SW); `0.96·N₁₆₀` (chữ H / ống hở)
- `qp_kPa = 38·N₁₆₀·(Db/D) ≤ 3200·N₁₆₀` (cát) hoặc `≤ 1800·N₁₆₀` (cát bột)
- `N₁₆₀ = N·CN`, với `CN = √(100/σ'v_kPa)` clamp [0.5, 2.0]

**σ'v effective**: tích phân γ qua các lớp; phần dưới MNN dùng γ' = γ − γw; lớp cắt ngang MNN chia đôi tự động.

**φ_stat dynamic**: sand Rs > 10% hoặc tip cát → 0,30; còn lại 0,35.

Khi thiếu SPT cho lớp cát → Rs/Rp = 0 + warning trong `n2["warnings"]`. Khi import SPT, formula auto-activate.

**File chi tiết:** [42-ke-sw-nt1-nt2-chi-tiet.md](42-ke-sw-nt1-nt2-chi-tiet.md) + [18-driven-pile-TCVN11823.md](18-driven-pile-TCVN11823.md)

**NHC DXF — Tọa độ hố khoan (cập nhật 2026-05-19):**

File: `NHC-1. TRỤ_TTHC_Tru hien truong.dxf` (G:/My Drive/202605-TRUNG TAM HCM/DIA CHAT/2. NHÀ HÀNH CHÍNH/)

Cấu trúc DXF (page 1, y chuẩn):

| Dòng y | Nội dung | Pattern |
| --- | --- | --- |
| y ≈ 71646 | Tên BH (header) | `BH-\d+` |
| y ≈ 71592 | Northing VN-2000 | `119\d{4}\.\d+` |
| y ≈ 71587/71588 | Easting VN-2000 | `60[56]\d{3}\.\d+` |
| y ≈ 71582 | Cao độ mặt đất (m) | `-?\d+\.\d{2}` |

- Pair-by-order (sort x) — KHÔNG dùng nearest-x vì BH-27/BH-28 quá gần nhau (Δx=2 DXF)
- 16/23 BH có tọa độ trong DXF này (thiếu: BH-01, BH-02, BH-09, BH-31, BH-39, BH-42, BH-44)
- Script: `scripts/nhc_coord_import.py`; JSON: `data/nhc_coords_202605_TTHC.json`
- Quy ước DB: `x_coord_m = Northing`, `y_coord_m = Easting` (giống BXN/KE)

### 27. Streamlit App — Khởi Động và Deploy

#### Khởi động local (bền vững)

Dùng `start_app.bat` (nằm ở project root) — double-click để mở CMD window, giữ window mở để app tiếp tục chạy.

```text
Local URL: http://localhost:8503
```

**Nguyên nhân app chết:** Khi Claude Code chạy Streamlit qua PowerShell background, process bị garbage-collect khi session kết thúc. `start_app.bat` tạo CMD window độc lập — không phụ thuộc Claude.

Nếu app không chạy được: kill Python trước (`Stop-Process -Name python -Force`), xóa `__pycache__`, chạy lại bat file.

#### Deploy lên Streamlit Cloud

**Repo đang dùng:** `https://github.com/PHAMNGOCBAY/CDM.git`
**App URL:** `https://phantichcocdm.streamlit.app`
**Thư mục deploy:** `cdm-deploy/` (embedded git repo trong project root)
**Main file path trên Cloud:** `scripts/app_cdm.py` (dùng `_ROOT = Path(__file__).parent.parent`)

**Quy trình cập nhật (dùng `update_app.bat`):**

1. Double-click `update_app.bat` ở project root
2. Script tự copy `scripts/app_cdm.py` + `data/TTHC.sqlite` vào `cdm-deploy/`
3. Commit + push vào `PHAMNGOCBAY/CDM` → Streamlit Cloud tự redeploy ~30-60 giây

**Hoặc thủ công:**

```bat
cd cdm-deploy
copy ..\scripts\app_cdm.py scripts\app_cdm.py
copy ..\data\TTHC.sqlite data\TTHC.sqlite
git add -A
git commit -m "update"
git push origin main
```

**Lưu ý quan trọng:**

- Streamlit Cloud dùng `requirements.txt` ở root của `cdm-deploy/` — phải có đủ packages
- SQLite trong repo → read-only trên Cloud (chỉ đọc) — app hiện tại OK vì chỉ đọc
- KHÔNG commit trực tiếp vào `cdm-deploy/scripts/app_cdm.py` — luôn sửa `scripts/app_cdm.py` trong project root rồi dùng `update_app.bat`

#### Quy trình deploy thủ công (PowerShell)

```powershell
$src = "G:\My Drive\AI-SUC TAI COC THEO DAT NEN"
$dst = "$src\cdm-deploy"
Copy-Item "$src\scripts\app_cdm.py"        "$dst\scripts\app_cdm.py" -Force
Copy-Item "$src\data\TTHC.sqlite"          "$dst\data\TTHC.sqlite"   -Force
Copy-Item "$src\scripts\settlement_calc.py" "$dst\scripts\settlement_calc.py" -Force
Copy-Item "$src\data\tccs41_params.json"   "$dst\data\tccs41_params.json"     -Force
cd $dst
git add -A
git commit -m "cap nhat"
git push origin main
```

---

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

**PHẢI** dùng S1 đàn hồi (trong `compare_methods()`):**

```python
# S = S1 + S2 (TCVN 9403 Phụ lục C)
S1 = q × H_soft / (a × Ec + (1-a) × Es)  # [m], nhân 100 → cm
S2 = 0  # CDM cắm đến lớp cứng
# Ec = 75 × (field_lab_ratio × qu_lab / 2)   (TCVN 9403 B.5.1)
# Es = 250 × Cu_avg                           (tương quan Mesri)
```

**Time series CDM:** lún đàn hồi xảy ra tức thì → flat list `U=100%, S=S1` từ t=0.  
**Lún còn lại CDM = 0** (không có lún cố kết sau thi công).

**Kết quả mẫu (NHC, a=0.25, H_fill=3m, H_soft=35m):**

- Ec=12375 kPa, Es=3750 kPa, Etb=5906 kPa
- S1 = 60×35/5906×100 = **35,6 cm** vs S_không xử lý = 107 cm (giảm 67%)
- `calc_cdm_stress_beta()` vẫn giữ lại để hiển thị biểu đồ ứng suất, không dùng cho tính S

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

### 32. Tab TKBVTC CDM — Bản đồ HK 2D folium + 3D pydeck (cập nhật 2026-05-23)

**Vị trí:** `app_cdm.py`, `if _page == "cdm_bvt":` (~line 13700)
**Thư viện:** `folium`, `streamlit-folium`, `pydeck`, `pyproj` (đã thêm vào requirements.txt)

#### Quy ước tọa độ VN-2000 → WGS-84

| Nguồn | Convention | Truyền vào `Transformer.transform(always_xy=True)` |
|---|---|---|
| `boreholes` table | `x_coord_m = Northing`, `y_coord_m = Easting` | `(y_coord_m, x_coord_m)` |
| `ke_binhdo_*.json` polyline | `x_m = Easting`, `y_m = Northing` | `(x_m, y_m)` |

**3 hệ EPSG dùng được cho HCM** (selectable trong UI, mặc định EPSG:9210 vì Q1/Thủ Thiêm):

| EPSG | Tên | Central meridian | Khi dùng |
|---|---|---|---|
| **9210** | VN-2000 / TM-3 106°00' | 106°E | TTHC Quận 1, Thủ Thiêm (mặc định) |
| 9209 | VN-2000 / TM-3 105°45' | 105.75°E | HCM tổng quát các quận khác |
| 3405 | VN-2000 / UTM 48N | 105°E | Khi dữ liệu gốc dùng UTM 6-degree |

#### UI structure

- 3 cột điều khiển: zone (KE/BXN/NHC/Tất cả) · CRS · view mode (2D / 3D)
- **2D folium**: 4 nền togglable (OSM / Vệ tinh Esri / OpenTopoMap / CartoDB) + FeatureGroup HK (CircleMarker + DivIcon label) + FeatureGroup polyline kè đen + plugins (Fullscreen / MeasureControl / MiniMap) + LayerControl không collapsed
- **3D pydeck**: ColumnLayer (HK depth × 10x cho dễ nhìn) + ScatterplotLayer (đỉnh column) + PathLayer (polyline kè) + 4 map_style (light/dark/road/satellite) + tooltip HTML hover

#### Pitfalls đã giải quyết

1. **`x_coord_m` vs `x_m`** — KHÔNG nhất quán giữa `boreholes` (x=N, y=E) và `ke_binhdo` (x=E, y=N). Phải nhớ swap đúng khi gọi `transformer.transform()`.
2. **CRS sai → HK lệch 25-50km** trên bản đồ. Mặc định EPSG:9210 cho TTHC, có dropdown selector phòng dự án khác.
3. **`pyproj` axis_swap** — luôn dùng `always_xy=True` → input/output dạng (x=Easting/lon, y=Northing/lat). Dễ nhớ.
4. **`contextily` / `rasterio`** — kéo GDAL ~40MB, KHÔNG đưa lên Cloud (đã ghi rõ trong requirements.txt).

---

### 33. App 8508 — FastAPI + Jinja2 SPA (LOCAL ONLY)

**File backend:** `web/app8508.py`  
**File frontend:** `web/templates/app.html` (single-page app, ~3 750+ dòng)  
**Khởi động:** `start_dev_tools.bat` → chọn [1] hoặc chạy tay:

```bat
python -m uvicorn web.app8508:app --host 0.0.0.0 --port 8508 --reload
```

**URL:** `http://localhost:8508`  
**Không deploy Cloud** — dùng local chỉ; SQLite read/write, scripts/, winkler_np.py v.v.

#### Kiến trúc tổng thể

- **Backend FastAPI** (`app8508.py`): chỉ phục vụ API JSON + serve template. Mọi tính toán tái sử dụng `scripts/` (wall_internal_force.py, winkler_np.py, ke_sw_nt_calc.py...). Route prefix `/api/ke-sw/*`.
- **Frontend Jinja2 SPA** (`app.html`): router thuần JS — `ROUTES` map `page_id → async function(el)`. Navigation qua sidebar, không reload trang. Plotly + SVG cho charts/sơ đồ. Global `DARK` constant cho Plotly dark theme.
- **Data flow:** JS → `fetch('/api/...')` → FastAPI → SQLite/scripts → JSON → JS renders DOM.

#### Router JS — ROUTES table

```javascript
const ROUTES = {
  ke_sw:    pageKeSw,    // Thiết kế cọc ván SW (TKCS)
  sw_bvt:   pageBvtSw,   // TKBVTC Cọc ván SW
  params:   pageParams,  // Thiết kế CDM
  ...
};
```

Mỗi page function là `async function pageName(el)` — nhận container `el`, tự gán `el.innerHTML`, tự gọi API, tự render.

#### API endpoints đã có (`/api/ke-sw/*`)

| Endpoint | Mô tả |
|---|---|
| `GET /api/ke-sw/winkler` | Bảng tổng hợp Winkler tất cả HK — từ `ke_sw_winkler_results` |
| `GET /api/ke-sw/stability` | Bảng ổn định tổng thể — từ `ke_sw_stability` |
| `GET /api/ke-sw/nt-layers` | Chi tiết lớp đất NT2 per HK — từ `ke_sw_nt2_layers` JOIN `ke_sw_nt_detail` |
| `GET /api/ke-sw/winkler-profile?bh=KE-HK8&pile_type=SW-840` | Profile Winkler đầy đủ per HK (xem §33b) |

#### pageBvtSw — 4 sections

**File:** `web/templates/app.html`, function `pageBvtSw(el)` (~line 3165+)

| Section | ID | Nội dung |
|---|---|---|
| A | `bvt-wkpi` / `bvt-wtbl-wrap` / `bvt-wch` | Tổng hợp Winkler tất cả HK: bảng + bar chart M vs Mcr |
| B | `bvt-skpi` / `bvt-stbl-wrap` / `bvt-sch` | Ổn định Fellenius: bảng + bar chart Fs_slip/Fs_overturning |
| C | `bvt-cond` | Grid thông số thiết kế cơ sở (top_elev, wlvl, q, CDM a/c) |
| D | `bvt-d-*` | Phân tích nội lực per HK (xem §33c) |

**Inner helper functions** (scope: `pageBvtSw`): `badge(ok)`, `kpi(val,label,color)`, `fmt1/fmt2/fmt3(v)`

---

### 33b. `/api/ke-sw/winkler-profile` — Response Structure

```json
{
  "bh": "KE-HK8",
  "pile_type": "SW-840",
  "L_m": 29.0,
  "top_elev": 2.7,
  "EI_kNm2": 45200.0,
  "D_m": 0.840,
  "ep": {
    "elevs": [...],
    "zs_depth_m": [...],
    "sigma_h_active": [...],
    "sigma_h_passive": [...],
    "p_water_front": [...],
    "p_water_back": [...],
    "p_net": [...],
    "F_active_kN": 180.5,
    "F_net_kN": 120.3
  },
  "profile": {
    "zs": [...],
    "zs_mid": [...],
    "u_mm": [...],
    "M_kNm": [...],
    "Q_kN": [...],
    "k_h": [...],
    "p_net_interp": [...]
  },
  "summary": {
    "u_top_mm": 12.3,
    "u_max_mm": 18.7,
    "M_max_kNm": 420.5,
    "Q_max_kN": 85.2,
    "Mcr_kNm": 756.0,
    "mcr_ratio": 0.556,
    "u_ok": true,
    "mcr_ok": true
  },
  "geom": {
    "top_elev": 2.7, "Z_m": 0.5, "Zb_m": -1.5,
    "wlvl_front": -0.5, "wlvl_back": -1.5,
    "q_kPa": 15.0, "su_front": 12.0, "su_back": 10.0, "H1_m": 22.0
  }
}
```

**Nguồn dữ liệu:** `ke_sw_stability` (geom params) + `ke_sw_winkler_results` (EI, D, Mcr, L) + `ke_sw_nt2_layers` JOIN `ke_sw_nt_detail` (SoilLayer list).  
**Solver:** `winkler_np.solve_numpy_dist()` (NumPy thuần, Cloud-compatible).  
**Earth pressure:** `wall_internal_force.build_lateral_load()`, mode=`'winkler'` → KHÔNG trừ Passive (lò xo tự xử lý).

**Array lengths (N = số phần tử = 60):**

| Array | Length | Mô tả |
|---|---|---|
| `zs`, `u_mm`, `k_h`, `p_net_interp` | N+1 = 61 | Node positions |
| `M_kNm`, `Q_kN`, `zs_mid` | N = 60 | Element midspan |

---

### 33c. pageBvtSw Section D — Phân tích nội lực per HK

**Vị trí:** `web/templates/app.html`, cuối `pageBvtSw`, ~line 3220–3748.  
**8 HK trên tuyến:** KE-HK2, KE-HK4, KE-HK6, KE-HK7, KE-HK8, KE-HK9, KE-HK10, KE-HK11.  
**Auto-load:** KE-HK8 / SW-840 khi vào trang. Đổi select → tự reload.

#### DOM IDs Section D

| ID | Loại | Nội dung |
|---|---|---|
| `bvt-d-bh` | `<select>` | Chọn hố khoan (8 HK alignment) |
| `bvt-d-pile` | `<select>` | Chọn loại cọc (SW-840/SW-940/SW-1000) |
| `bvt-d-load` | `<button>` | Nút tải lại |
| `bvt-d-status` | `<span>` | Trạng thái loading / error |
| `bvt-d-svg` | `<svg 240×360>` | Sơ đồ cọc GEO5-style (SVG thuần) |
| `bvt-d-props` | `<div>` | Grid 8 thông số (EI, L, Mcr, q, Su, H1) |
| `bvt-d-ep1` | Plotly `380px` | Áp lực đất & nước vs cao độ (4 traces) |
| `bvt-d-ep2` | Plotly `380px` | p_net(+)/p_net(−)/tổng vs cao độ |
| `bvt-d-ep-kpi` | `.bvt-kpi` | F_active, F_net (kN/m) |
| `bvt-d-kpi5` | `.bvt-kpi` | u_max, u_ok, M_max, mcr_ratio, mcr_ok, Q_max |
| `bvt-d-ch-p` | Plotly `420px` | p_net vs độ sâu |
| `bvt-d-ch-u` | Plotly `420px` | Chuyển vị u (mm) + ±50 mm limit lines |
| `bvt-d-ch-m` | Plotly `420px` | Mô men M + ±Mcr threshold lines |
| `bvt-d-ch-q` | Plotly `420px` | Lực cắt Q |
| `bvt-d-ch-k` | Plotly `420px` | Hệ số nền k_h Winkler |

#### Inner functions Section D

| Function | Mô tả |
|---|---|
| `_loadSectionD()` | async — fetch API, gọi 5 renderer |
| `_drawDSvg(d)` | SVG sơ đồ cọc: fill/sét mềm/chặt Front+Back, MN, pile body+tip, nhãn TRƯỚC/SAU |
| `_renderDProps(d)` | Grid 8 props từ `d.geom` + `d.summary` |
| `_renderDEarthPressure(d)` | 2 Plotly charts ep1/ep2 — elevation trên Y |
| `_renderDKpis(d)` | KPI badges ep-kpi + kpi5 |
| `_renderD5Panels(d)` | 5 Plotly charts depth trên Y (autorange:reversed) |

#### CSS classes Section D

| Class | Mục đích |
| --- | --- |
| `.bvt-d-ctrl` | Controls row flex container |
| `.bvt-theory-card` | Card lý thuyết (border, padding, line-height 1.6) |
| `.tf` | Monospace formula block (màu `#a5f3fc`, nền tối) |
| `.bvt-props-grid` | Grid 2 cột cho props |
| `.bvt-prop` / `.pk` / `.pv` | Prop item: key (muted) + value (bold) |

#### Quy tắc quan trọng Section D

- **Y axis 5 panel charts:** `autorange:'reversed'` + `range:[0, L_m]` — độ sâu 0 (đỉnh cọc) ở trên, L_m (mũi) ở dưới.
- **Y axis earth pressure charts:** elevation trên Y, `range:[elMin, elMax]` từ `ep.elevs`.
- **M panel:** vẽ thêm ±Mcr threshold lines (vàng đứt) để so sánh trực quan.
- **p_net mode winkler:** `ep_out.p_net` = σh_active + p_water_front − p_water_back (KHÔNG trừ Passive).
- **EarthLayer `c`:** dùng `su * 0.5` làm cohesion proxy trong công thức Rankine phi-c.

---

### 34. Tab TKCS CDM — Chuẩn bị Tính Toán Sơ Bộ (page id = "tvtk_prep", cập nhật 2026-05-25)

**Vị trí:** `app_cdm.py`, sidebar label "Thuyết minh TKCS"  
**Tài liệu đầy đủ:** [54-tvtk-cdm-prep.md](54-tvtk-cdm-prep.md)  
**JSON snapshot:** `data/tvtk_cdm_202605_TTHC.json`  
**Bảng SQLite:** `tvtk_cdm_config` (config) · `cdm_design` (computed) · `tvtk_soil_params` · `tvtk_bh_cdm`

#### Bố cục 5 section (trải phẳng, không st.tabs)

| Section | Nội dung | Data source |
| --- | --- | --- |
| 1 | Lựa chọn HK thiết kế (multiselect) | `tvtk_bh_cdm.selected` |
| 2 | Địa tầng & SPT | `layers`, `spt_values` |
| 3 | Tóm tắt thí nghiệm | `lab_tests`, `vane_shear_tests` |
| 4 | Lớp đất yếu — H_soft per HK | `layers WHERE symbol IN ('1','1b','2','XMD')` |
| 5 | Thông số thiết kế CDM (editable + Lưu) | `tvtk_cdm_config` → `cdm_design` |

#### Section 5 — 2 hàng nhập liệu

**Hàng 1 (5 cột):** D_mm · Khoảng cách s · Bố trí lưới · Cao độ đỉnh cọc · Ngàm lớp cứng  
**Hàng 2 (7 cột):** Hệ số k (Ec=k×Cc) · qu thiết kế · q tải · [metric: a] · [metric: Cc] · [metric: Ec] · [Lưu]

Khi bấm "Lưu": (1) UPDATE `tvtk_cdm_config`, (2) recalculate S1 per zone, (3) UPDATE `cdm_design`, (4) `st.rerun()`.

#### Công thức cốt lõi (TCVN 9403 Phụ lục C)

- `S1 = q × H / (a × Ec + (1-a) × Es)` — lún đàn hồi trong vùng gia cố
- `Ec = k × Cc_col` (k editable, mặc định 100; TCVN cho phép 50–100)
- `Cc_col = qu_design / 2` (qu_design = cường độ thiết kế mục tiêu, KHÔNG phải qu_lab)
- `Es = 250 × Cu_VST` (Mesri & Olson 1974)
- `S_reduction = S1_CDM / S_no_treat` — lấy S_no_treat từ `settlement_scenarios`

#### H_soft — Quy tắc bắt buộc

**KHÔNG** dùng `_h1 + _h1b` (sai cho NHC có lớp 2, không có 1b).  
**PHẢI** query: `SUM(depth_bot_m - depth_top_m) WHERE symbol IN ('1','1b','2','XMD')`

| Zone | Lớp yếu thực tế | H_soft TB |
| --- | --- | --- |
| KE | 1 + 1b + XMD | 23.0 m |
| BXN | 1 | 21.5 m |
| NHC | 1 + 2 | 27.4 m |

#### Kết quả TTHC hiện tại (D=800mm, s=1.8m, k=100, qu=800 kPa, q=40.8 kPa)

| Zone | Ec (kPa) | S1_CDM (cm) | Giảm lún |
| --- | --- | --- | --- |
| KE | 40 000 | 10.3 | 93.7% |
| BXN | 40 000 | 9.8 | 93.0% |
| NHC | 40 000 | 11.9 | 92.5% |

#### Chiều dài cọc CDM

`L = top_elev_m − elevation_m + H_soft + penetration_m` — hiển thị bảng per HK + tổng hợp min/TB/max per zone.

#### SQLite — Phân loại nguồn đọc (BẮT BUỘC)

| Bảng | Loại | App đọc từ |
| --- | --- | --- |
| `tvtk_cdm_config` | **Config** | JSON/SQLite đều OK |
| `cdm_design` | **Computed** | **SQLite BẮT BUỘC** — sau mỗi "Lưu" |
| `tvtk_soil_params` | **Computed** | SQLite |
| `tvtk_bh_cdm` | **Config** | SQLite |

---

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

### 38. Trắc dọc CDM + Bảng L_CDM (đào/đắp) + Cu tính toán trên biểu đồ VST

**File tài liệu:** [47-tvtk-cdm-trac-doc-luong-chinh.md](47-tvtk-cdm-trac-doc-luong-chinh.md)
**JSON config:** `data/tccs41_params.json` → `tccs41_limits.cdm_profile_plot`
**Helper public:** `scripts.settlement_calc.build_mu_by_loc(loc_names, soft_symbols, db_path)`

#### Bảng thống kê L_CDM — quy ước đào/đắp (BẮT BUỘC)

Công thức $L_{CDM} = z_{top} - z_{tự\_nhiên} + H_{soft} + z_{ngàm}$ giả định ngầm **đào bỏ** phần đất yếu phía trên đỉnh cọc khi $z_{top} < z_{tự\_nhiên}$.

**Bảng phải có 9 cột:** Hố khoan · Khu vực · Cao độ TN · Đỉnh cọc TK · **Đào/Đắp** · H đất yếu · **L (không đào) m** · L CDM · Ghi chú.

**Cảnh báo tự động:** `st.warning()` nếu có HK nào có $|z_{tự\_nhiên} - z_{top}| > z_{ngàm}$ → gợi ý xem lại top_elev_m per zone.

**Bảng tổng hợp** thêm cột `L TB không đào (m) = H_soft + pen`.

#### Trắc dọc CDM 3 zone (KE/BXN/NHC)

8 trace bắt buộc per biểu đồ:
1. Vùng tô đất đắp (`elev → des_elev`, nâu mờ)
2. Vùng tô phạm vi xử lý CDM (`top → bot_cdm`, xanh mờ)
3. Cột CDM đứng mỗi HK (`#1a6fbd` đứt mảnh)
4. Mặt đất tự nhiên (`#7B3F00` line+marker+text)
5. Cao độ thiết kế ngang (`#2ca02c` đứt)
6. Đỉnh cọc CDM ngang (`#1a6fbd` đứt)
7. **Đáy lớp đất yếu** (`#e377c2` longdash + kim cương + text)
8. **Đáy cọc CDM** (`#d62728` lw 2.6 + tam giác `#ff7f0e` + text bold)

Chainage **PCA-SVD per zone** trên (x, y) — bắt đầu từ 0.

#### Cu tính toán trên biểu đồ VST tab `ke_sw`

**Helper module-level:** `_build_mu_by_loc` (wrapper) → `settlement_calc.build_mu_by_loc` (public).

**Param `show_cu_corrected: bool = True`** thêm vào cả `_chart_su_profile()` (Plotly) và `_chart_su_profile_mpl()` (Matplotlib). Mặc định BẬT.

**Style Cu tính toán (chuẩn toàn dự án):**
- Color: `#15803d` (xanh lá đậm)
- Marker: diamond size 8–9 (Plotly) / `D` ms 6 (MPL)
- Line width: 2.2–2.6 liền
- Vạch đứng `Cu_TB` dashdot + annotation box `#dcfce7` viền `#15803d`

**3 caller tự động kế thừa:** `app_cdm.py:4488` (Plotly), `4492` (MPL fallback), `9537` (MPL trong panel NT1/NT2 per HK).

#### Quy tắc đọc lớp đất yếu (BẮT BUỘC nhất quán)

| Mục đích | Symbol filter | Bảng SQLite |
|---|---|---|
| Tính H_soft (chiều dày tổng) | `('1','1b','2','XMD')` | `layers.symbol` |
| Tính Ip TB cho Bjerrum μ | `('1','1b','CH','MH','CH-OH','MH-OH')` | `lab_tests.symbol_tcvn` |

**KHÔNG trộn lẫn 2 bộ symbol** — `layers.symbol` (số La Mã: 1, 1b, 2) khác `lab_tests.symbol_tcvn` (TCVN: CH, MH, CL...).

---

### 39. Tìm chiều dài cừ SW tối ưu — Thuật toán lặp +1m (Mục E)

**File tài liệu:** [48-ke-sw-L-optimal-search.md](48-ke-sw-L-optimal-search.md)
**JSON config:** `data/tccs41_params.json` → `tccs41_limits.sw_stability_search`
**Python:** `scripts/sw_global_stability.py` — `find_optimal_L_iterative()` + `create_L_iteration_table()`
**SQLite:** `ke_sw_L_iteration` (UNIQUE `(bh_name, pile_type, L_m, run_id)`)

#### Nguyên tắc

Khi HK có Fs **không đạt** trong Mục E → lặp tăng $L$ bước **+1,0 m** từ $L_{thiết\_kế}$ hiện tại đến $L_{max}$ (catalog). Mỗi bước:

1. Chạy **đầy đủ 4 kiểm tra:** Bishop · Spencer · Morgenstern-Price · Lật
2. **Lưu mọi bước** (kể cả không đạt) vào `ke_sw_L_iteration` — phục vụ tra cứu
3. Dừng tại $L$ đầu tiên đạt → `is_final = 1`

#### Ngưỡng Fs (BẮT BUỘC)

| Tiêu chí | Ngưỡng |
|---|:---:|
| Bishop · Spencer · M-P | **≥ 1,40** |
| Lật quanh chân cừ | **≥ 1,20** |
| **Pass** | `min(3 PP) ≥ 1,40` **AND** `Fs_lật ≥ 1,20` |

#### API

```python
from sw_global_stability import find_optimal_L_iterative, create_L_iteration_table

r = find_optimal_L_iterative(
    bh_name='KE-HK1', pile_type='SW-740',
    geom_template=geom, front_layers=..., back_layers=...,
    fill=..., cdm=..., pile=...,
    L_start=28.0, L_max=L_catalog_max, L_step=1.0,
    Fs_min_slip=1.40, Fs_min_overt=1.20,
    save_to_db=True, db_path=Path('data/TTHC.sqlite'),
)
# r['L_optimal_m']: float | None
# r['history']: list of {L_m, Fs_bishop, Fs_spencer, Fs_mp, Fs_lat, is_final}
# r['n_iterations'], r['run_id']
```

#### Sample output (KE-HK1 / SW-740, geom test)

```
L=28.0  Bishop=0.973  lat=1.004  fail
L=29.0  Bishop=0.908  lat=1.018  fail
...
L=35.0  Bishop=0.704  lat=1.031  fail
→ L_optimal = None (cần đổi loại cọc hoặc tăng L_max)
```

#### Idempotent

Re-run cùng `run_id` → ON CONFLICT UPDATE, không tạo duplicate row.

#### Tích hợp app (kế hoạch)

UI nút "Tìm L tối ưu cho HK chưa đạt" trong Mục E khi có ≥ 1 HK không đạt → hiển thị bảng history per HK qua expander.

---

### 40. Hình minh họa tải trọng gây lật quanh chân cừ (Mục E)

**File tài liệu:** [49-ke-sw-overturning-diagram.md](49-ke-sw-overturning-diagram.md)
**JSON config:** `data/tccs41_params.json` → `tccs41_limits.sw_overturning_diagram`
**Python:** `scripts/sw_global_stability.py` — `draw_overturning_diagram()` (matplotlib)
**UI:** `scripts/app_cdm.py` Mục E expander "Sơ đồ minh họa tải trọng gây lật quanh chân cừ"

#### Thành phần đồ họa (BẮT BUỘC đầy đủ 10 lớp)

1. **Đất đắp Front** (nâu `#D2B48C`) + **Đất tự nhiên Front** (xanh nhạt) + **Đất tự nhiên Back** (xanh lá nhạt)
2. **Cừ SW** dải xanh dương `#1565C0` dọc giữa
3. **Chân cừ (pivot)** vòng tròn `#FF6B6B` viền `#a01010` ms 14 + annotation
4. **Mực nước** Front + Back (đường đứt 2 màu xanh)
5. **Tải mặt $q$** Front (mũi tên đỏ xuống + thanh + label)
6. **Tam giác Active** Front (`#FFCDD2` viền `#D32F2F`) + 7 mũi tên đẩy về Back
7. **Tam giác Passive** Back dưới đáy đào (`#C8E6C9` viền `#2E7D32`) + 4 mũi tên kháng về Front
8. **Tay đòn** $z_a$ (Front) + $z_p$ (Back) — mũi tên đôi + label dọc
9. **Mũi tên cong** **M_lật** (CCW, đỏ) + **M_giữ** (CW, xanh lá) quanh chân cừ
10. **Bảng kết quả** $F_s$ (LaTeX) hộp viền theo trạng thái Đạt/Không đạt vs ngưỡng 1,20

#### API

```python
from sw_global_stability import draw_overturning_diagram
fig = draw_overturning_diagram(
    geom, front_layers, back_layers, fill, cdm, pile,
    M_giu_kNm=..., M_lat_kNm=..., Fs=...,
    bh_name='...', figsize=(11, 8), Fs_min=1.20,
)
st.pyplot(fig, use_container_width=True); plt.close(fig)
```

#### Schema SQLite query (BẮT BUỘC tên cột ngắn)

`ke_sw_stability` dùng tên ngắn — **KHÔNG** có suffix `_m`:
- `top_elev` (KHÔNG phải `top_elev_m`)
- `Z_m` = `soil_level_front` · `Zb_m` = `soil_level_back`
- `wlvl_front` / `wlvl_back` · `q_kPa` · `M_giu_kNm` / `M_lat_kNm`

#### Sample verify

KE-HK1 / SW-740 / L=28m với đất yếu chung (phi=2°, c=10):
- M_giu = 64104 kNm/m · M_lat = 63817 kNm/m → Fs = 1,004
- Render PNG 135 KB · 62 elements (patches, lines, texts)

#### Quy ước Front/Back (BẮT BUỘC tuân §20)

| Phía | Vị trí trên hình | Áp lực | Vai trò |
|---|---|---|---|
| Front | **TRÁI** | Active (Ka) | **Gây lật** |
| Back | **PHẢI** | Passive (Kp) | **Giữ ổn định** |

---

### 41. Thủy văn trạm Phú An sông Sài Gòn 1977–2024 (48 năm)

**File tài liệu:** [50-thuyvan-phuan-1977-2024.md](50-thuyvan-phuan-1977-2024.md)
**Module Python:** `scripts/thuyvan_phuan_import.py` + `scripts/thuyvan_phuan_plots.py`
**SQLite:** `thuyvan_daily` (17,530) · `thuyvan_annual_summary` (48) · `thuyvan_tidal_peaks` (13)
**JSON:** `data/thuyvan_phuan_daily_77-24.json`, `data/thuyvan_phuan_summary.json`, `data/thuyvan_phuan_stats.json`

#### Mực nước thiết kế khuyến nghị (P95/P99)

| Trường hợp | MNTB (cm, cao độ Quốc gia) |
|---|:---:|
| Mực nước thấp khai thác | **−25** (P5) |
| Trung bình | **+13** (P50) |
| **Thiết kế cao (tải nước)** | **+48** (P95) |
| Cực đại hiếm | **+59** (P99) — đến **+177** (đỉnh triều 2019) |

#### Xu thế dài hạn (BẮT BUỘC tính dự phòng)

| Đại lượng | Tốc độ tăng | Dự phòng 50 năm |
|---|:---:|:---:|
| MNTB năm | +3,66 cm/decade | +18 cm |
| **Max năm (đỉnh triều)** | **+11,63 cm/decade** | **+58 cm** |
| MNTB TB thập kỷ 80 → 2020s | từ 6,6 → **20,2 cm** (gấp **3 lần**) | — |

#### Pattern mùa (TB 48 năm)

| Mùa | Tháng | MNTB TB |
|---|:---:|:---:|
| **Mùa lũ cao nhất** | XI | **+35 cm** |
| Lũ | X, XII | +31, +33 |
| Chuyển | I–IV | +28 → +8 |
| **Mùa khô thấp nhất** | VI | **−13 cm** |
| Khô | VII, VIII | −12, −7 |

→ **Biên độ mùa ~48 cm**; mùa lũ XI–XII–I là thời điểm thiết kế cừ.

#### Schema SQLite

```sql
-- thuyvan_daily: 17,530 rows, UNIQUE(year, month, day)
-- thuyvan_annual_summary: 48 rows UNIQUE(year),
--   monthly_avg/max/min_cm là JSON array 12 phần tử
-- thuyvan_tidal_peaks: 13 rows UNIQUE(year)
```

#### Áp dụng

- Mực nước Front (sông) thiết kế: **+48 cm** (P95) cho công trình dân dụng, **+59 cm** (P99) cho tuổi thọ ≥ 50 năm.
- Mực nước Back (đất) thường thấp hơn Front 1–1,5 m do gradient thấm.
- Tính toán Winkler / đẩy nổi / ổn định dùng các cao độ trên — KHÔNG dùng giá trị cố định cũ (vd −1,5 m).
