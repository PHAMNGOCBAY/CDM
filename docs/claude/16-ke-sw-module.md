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

