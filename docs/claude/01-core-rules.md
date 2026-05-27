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

