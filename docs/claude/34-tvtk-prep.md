### 34. Tab TKCS CDM — Chuẩn bị Tính Toán Sơ Bộ (page id = "tvtk_prep", cập nhật 2026-05-25)

**Vị trí:** `app_cdm.py`, sidebar label "Thuyết minh TKCS"  
**Tài liệu đầy đủ:** [54-tvtk-cdm-prep.md](54-tvtk-cdm-prep.md)  
**JSON snapshot:** `data/tvtk_cdm_202605_TTHC.json`  
**Bảng SQLite:** `tvtk_cdm_config` (config) · `cdm_design` (computed) · `tvtk_soil_params` · `tvtk_bh_cdm` · `tvtk_fill_composition` (cấu tạo tải đắp)

#### Cấu tạo tải trọng đắp — `tvtk_fill_composition` (nguồn chính của q, cập nhật 2026-05-27)

Tải phân bố `q_kPa` trong `tvtk_cdm_config` được suy ra từ cấu tạo các lớp đắp phía trên cao độ thiết kế, lưu làm **nguồn chính** trong bảng `tvtk_fill_composition` (list lớp) thay vì nhập số q rời.

$$q = \sum_i h_i \cdot \gamma_i \quad [\text{kPa}]$$

| Lớp | h (m) | γ (kN/m³) | q thành phần (kPa) |
| --- | :---: | :---: | :---: |
| Áo đường | 0,80 | 24,00 | 19,20 |
| He — cát đắp | 0,70 | 18,00 | 12,60 |
| Hse — đệm cát | 0,40 | 22,50 | 9,00 |
| **Tổng** (Σh=1,90 m) | | | **40,80** |

Cao độ thiết kế TTHC = **2,70 m** (`tvtk_cdm_config.settlement_design_elev_m`).

**Engine:** [scripts/tvtk_fill_composition.py](scripts/tvtk_fill_composition.py) — `update_db_fill_composition()` (idempotent INSERT OR REPLACE + xóa lớp thừa, `sync_config=True` đồng bộ `q_kPa`/`settlement_design_elev_m`) · `update_json_snapshot()` (khối `fill_composition` trong JSON). `__main__` ghi cả 2 DB (local `C:\Users\bayng\TTHC_local` + `data/`) + JSON.

**Schema `tvtk_fill_composition`:** `layer_order` (PK) · `name` · `h_m` · `gamma_kNm3` · `q_component_kPa` · `design_elev_m` · `updated_at`.

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

