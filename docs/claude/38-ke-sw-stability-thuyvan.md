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

#### Public API (Python)

```python
from thuyvan_phuan_import import get_design_water_level, get_seasonal_water_levels

# Tra cứu mực nước TK
r = get_design_water_level('P95')                          # → +48 cm
r = get_design_water_level('P99', design_life_years=50)    # → +117 cm (cộng dự phòng)
r = get_design_water_level('peak_max')                     # → +177 cm (đỉnh triều 2019)

# Cases hợp lệ:
#   'P5', 'P50', 'P95', 'P99' (percentile)
#   'peak_max' (đỉnh triều annual max)
#   'max_historical' / 'min_historical' (MNTB ngày)
# Aliases: 'design_high'='P95', 'design_extreme'='P99', 'low_operation'='P5'

# MNTB theo 12 tháng (TB 48 năm)
seasonal = get_seasonal_water_levels()
# seasonal[11] → {avg_cm: +35.3, max_cm: +74, min_cm: -9, season: 'Lũ cao'}
```

**RISE_RATE_CM_PER_DECADE = 11.63** (constant module-level — xu thế từ Max năm).

---

