# Trắc dọc CDM + Bảng L_CDM + Cu tính toán trên biểu đồ VST

Tài liệu hợp nhất 3 cải tiến tính toán + biểu đồ liên quan đến cọc CDM và VST trong app_cdm.py — tab **Thống nhất đầu vào TVTK** (`tvtk_prep`) và tab **Cọc ván SW Kè** (`ke_sw`).

---

## 1. Bảng thống kê chiều dài cọc CDM — logic đào/đắp

**Vị trí app:** Tab `tvtk_prep` → Section 5 → `#### Thống kê chiều dài cọc CDM theo nguyên tắc thiết kế`
**Code:** [scripts/app_cdm.py](scripts/app_cdm.py) ~line 16700–16800

### Công thức gốc

$$L_{CDM} = z_{\text{top}} - z_{\text{tự nhiên}} + H_{\text{đất yếu}} + z_{\text{ngàm}}$$

trong đó:

| Ký hiệu | Ý nghĩa | Nguồn |
|---|---|---|
| $z_{\text{top}}$ | Cao độ đỉnh cọc CDM thiết kế | `tvtk_cdm_config.top_elev_m` (config) |
| $z_{\text{tự nhiên}}$ | Cao độ mặt đất tự nhiên tại HK | `boreholes.elevation_m` |
| $H_{\text{đất yếu}}$ | Tổng chiều dày lớp 1, 1b, 2, XMD | `SUM(layers WHERE symbol IN ('1','1b','2','XMD'))` |
| $z_{\text{ngàm}}$ | Ngàm vào lớp cứng | `tvtk_cdm_config.penetration_m` |

### Quy ước đào/đắp

$$\text{Đào} = z_{\text{tự nhiên}} - z_{\text{top}} \quad
\begin{cases}
> 0 & \text{đào bỏ đất trước khi thi công cọc} \\
< 0 & \text{đắp thêm lên đỉnh cọc} \\
= 0 & \text{đỉnh cọc trùng mặt đất tự nhiên}
\end{cases}$$

**Khi đào > 0** (giả định ngầm của công thức): phần đất yếu phía **TRÊN** đỉnh cọc CDM coi như đã bị đào bỏ, không cần xử lý → $L_{CDM} < H_{\text{đất yếu}}$ là **hợp lý**.

### Cảnh báo bắt buộc

Nếu `Đào > z_ngàm` → `st.warning()` hiển thị: "Có N hố khoan có chiều cao đào lớn hơn chiều sâu ngàm" → gợi ý xem lại `top_elev_m` cho phù hợp cao độ tự nhiên từng zone.

### Cấu trúc bảng (9 cột)

| Cột | Mô tả |
|---|---|
| Hố khoan | Tên HK (đầy đủ với prefix zone) |
| Khu vực | KE / BXN / NHC |
| Cao độ TN (m) | Cao độ tự nhiên |
| Đỉnh cọc TK (m) | `top_elev_m` từ config (chung 3 zone) |
| **Đào/Đắp (m)** | `+` đào, `−` đắp |
| H đất yếu (m) | $H_{\text{soft}}$ |
| **L (không đào) m** | $H_{\text{soft}} + z_{\text{ngàm}}$ — L tối thiểu nếu không đào |
| L CDM (m) | L theo công thức gốc |
| Ghi chú | "Đào X m / Đắp X m / Cảnh báo: đào > pen" |

### Bảng tổng hợp per zone

| Cột | Tính toán |
|---|---|
| Số HK | `len(zone_L)` |
| L min / TB / max (m) | min/mean/max của `L_CDM` |
| **L TB không đào (m)** | mean của `H_soft + pen` |

### Vấn đề thực tế phát hiện

Với `top_elev_m = 0.8` (chung 3 zone) — TẤT CẢ HK BXN (cao độ TB **+2.49 m**) đều cảnh báo "đào > pen" → khuyến nghị **thay đổi schema** cho phép `top_elev_m` riêng per zone (giống `design_elev_m` ở section 2).

---

## 2. Trắc dọc CDM 3 khu vực

**Vị trí app:** Tab `tvtk_prep` → Section 5 → `#### Trắc dọc CDM theo khu vực`
**Code:** [scripts/app_cdm.py](scripts/app_cdm.py) ~line 16800–16980
**Format:** 3 biểu đồ Plotly (KE / BXN / NHC), key `_tvtk_cdm_profile_<zone>`

### Trục tọa độ

- **X:** Chainage dọc tuyến (m) — từ PCA-SVD trên (x_coord_m, y_coord_m) per zone, bắt đầu từ 0
- **Y:** Cao độ tuyệt đối (m) — VN-2000

### 7 thành phần đồ họa

| # | Đối tượng | Style | Hover |
|---|---|---|---|
| 1 | Vùng tô đất đắp (`elev → des_elev`) | nâu nhạt mờ `rgba(210,180,100,0.22)` | — |
| 2 | Vùng tô phạm vi xử lý CDM (`top → bot_cdm`) | xanh dương mờ `rgba(30,120,200,0.16)` | — |
| 3 | Cột CDM mỗi HK (dọc) | `#1a6fbd` đứt mảnh | — |
| 4 | Mặt đất tự nhiên | `#7B3F00` line + marker tròn + text `<HK><br>+elev` | — |
| 5 | Cao độ thiết kế (đường ngang) | `#2ca02c` đứt | "Cao độ thiết kế: X m" |
| 6 | Đỉnh cọc CDM (đường ngang) | `#1a6fbd` đứt | "Đỉnh CDM: X m" |
| 7 | Đáy lớp đất yếu | `#e377c2` longdash + kim cương + text `+val` | "Đáy lớp yếu: X m / H_đất_yếu: Y m" |
| 8 | **Đáy cọc CDM** (đường chính) | `#d62728` lw 2.6 + ▼ cam `#ff7f0e` + text `<b>+val</b>` | "Đáy cọc CDM: X m / L_cọc: Y m / H_đất_yếu: Z m / Ngàm: W m" |

### Tính toán

```
bot_soft  = elev - H_soft         # đáy lớp đất yếu
bot_cdm   = elev - H_soft - pen   # đáy cọc CDM
L_cdm     = top - bot_cdm
```

### Layout

- Height 560 px, margin (l=65, r=20, t=60, b=90)
- Legend ngang dưới (y=-0.18)
- Title: `<b>Trắc dọc CDM — <Zone></b> | N hố khoan | L_cọc: min ÷ max m (TB avg m)`
- Y-range: `[min(all_y) - 3, max(all_y) + 3.5]`

---

## 3. Cu tính toán trên biểu đồ VST tab Cọc ván SW Kè

**Vị trí app:** Tab `ke_sw` → Mục C / NT1+NT2 panels (per HK)
**Code:**
- Helper: [scripts/settlement_calc.py](scripts/settlement_calc.py) `build_mu_by_loc()` (public, có thể import lại từ app_cdm)
- Chart Plotly: [scripts/app_cdm.py](scripts/app_cdm.py) `_chart_su_profile()` ~line 2035–2230
- Chart Matplotlib: [scripts/app_cdm.py](scripts/app_cdm.py) `_chart_su_profile_mpl()` ~line 1864–1955

### Helper `build_mu_by_loc(loc_names)`

```python
from scripts.settlement_calc import build_mu_by_loc
# Trả về: {bh_name: {'Ip': float, 'mu': float}}
# Filter lớp yếu: symbol_tcvn IN ('1','1b','CH','MH','CH-OH','MH-OH')
```

### Trên biểu đồ Plotly `_chart_su_profile`

Param `show_cu_corrected: bool = True` (mặc định BẬT).

| Trace mới | Style | Hover |
|---|---|---|
| `Cu = μ·Su {loc}` | `#15803d` line 2.4 + diamond size 9 + text giá trị left | "Cu = μ·Su = X kPa / Su gốc: Y / μ = Z (Ip ≈ W)" |
| Vạch đứng `Cu_TB {loc}` | `#15803d` dashdot 1.5 | "Cu TB = X kPa / μ = Y / Ip = Z" |
| Annotation box | xanh lá nhạt + border | `<b>Cu_TB=X</b><br>μ=Y  Ip=Z` |

### Trên biểu đồ Matplotlib `_chart_su_profile_mpl`

| Plot mới | Style |
|---|---|
| Cu = μ·Su line | `#15803d` diamond marker, lw 1.8, ms 6 |
| `axvline` Cu_TB | linestyle `-.`, alpha 0.75 |
| Text annotation Cu_TB | box `#dcfce7` viền `#15803d` |

### Caller (không cần sửa — backward compat)

| Vị trí | Trace Cu tự động? |
|---|---|
| `app_cdm.py:4488` (Plotly tab Cọc ván SW Mục C) | CÓ |
| `app_cdm.py:4492` (MPL fallback) | CÓ |
| `app_cdm.py:9537` (MPL trong panel NT1/NT2 per HK) | CÓ |

---

## 4. Schema SQLite liên quan (không phát sinh bảng mới)

| Bảng | Cột dùng | Vai trò |
|---|---|---|
| `tvtk_cdm_config` | `top_elev_m`, `penetration_m` | Config đỉnh cọc + ngàm (chung 3 zone) |
| `tvtk_config` | `design_elev_m` per zone_code | Cao độ thiết kế từng zone |
| `tvtk_bh_cdm` | `H_soft_m`, `Ip_avg`, `bjerrum_mu`, `Cu_corrected_kPa` | Computed per HK |
| `boreholes` | `elevation_m`, `x_coord_m`, `y_coord_m` | Cao độ + tọa độ HK |
| `layers` | `symbol`, `depth_top_m`, `depth_bot_m` | Lớp yếu (1, 1b, 2, XMD) |
| `lab_tests` | `Ip`, `symbol_tcvn` | Ip cho công thức Bjerrum C.5 |
| `vane_shear_tests` + `vst_locations` | `depth_m`, `Su_kPa` | Su VST raw |

---

## 5. Liên kết

- [38-tccs41-nen-duong-dat-yeu.md](38-tccs41-nen-duong-dat-yeu.md) — Bjerrum C.5 + Bảng C.1, Bảng 1 ΔS
- [46-tccs41-phuluc-E-doan-chuyen-tiep.md](46-tccs41-phuluc-E-doan-chuyen-tiep.md) — Phụ lục E
- [CLAUDE.md](CLAUDE.md) §34 (TVTK CDM), §35 (ΔS), §36 (Bjerrum), §37 (Phụ lục E), §38 (trắc dọc + L_CDM + Cu VST)

---

## 6. Quy ước hiển thị

**Màu chuẩn cho Cu tính toán toàn dự án:** `#15803d` (xanh lá đậm).
**Marker chuẩn Cu:** diamond. **Style line Cu:** liền, width 2.2–2.6, ms 8–9.

**Caption bắt buộc khi vẽ Cu tính toán:**
> Cu = μ·Su theo TCCS 41 Phụ lục C.3.2 — Công thức C.5; μ nội suy từ Bảng C.1 theo $I_p$ TB của lớp đất yếu (lấy từ `lab_tests`).
