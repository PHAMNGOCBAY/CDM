### 63. Phân tích CDM đa khu vực — BXN / NHC / KE_park / KE_levee

**File engine:** [scripts/qtt_cdm_analysis.py](scripts/qtt_cdm_analysis.py) — section "Multi-zone analysis"
**File Word:** [scripts/qtt_cdm_report.py](scripts/qtt_cdm_report.py) — `build_zone_decision_docx()`
**JSON config:** [data/cdm_multi_zone_config.json](data/cdm_multi_zone_config.json)
**SQLite:** `cdm_zone_design_results` (mới) — lưu Lc tối ưu per HK × ΔS
**UI:** [scripts/app_cdm.py](scripts/app_cdm.py) tab "Dự báo độ lún" — section "Phân tích CDM đa khu vực"

#### Mục tiêu

Mở rộng thuật toán QTT (§62) cho 4 zone khác, kế thừa toàn bộ logic + bổ sung **quy tắc đặc biệt cho khu vực kè**.

#### Định nghĩa zone (ZONE_DEFS)

| Zone | Mô tả | Tiền tố HK | Cao độ thiết kế | Quy tắc đặc biệt |
|---|---|---|---|---|
| **QTT** | Quảng Trường Trung Tâm | `ND-` | `qtt_elevation_points.elev_des_m` (per HK) | — (xem §62) |
| **BXN** | Bãi Đỗ Xe Ngầm | `BXN-CV-` | `tvtk_cdm_config.settlement_design_elev_m` (global = 2.70 m) | — |
| **NHC** | Nhà Hành Chính | `NHC-BH-` | global | — |
| **KE_park** | Công Viên (KE không trên tuyến kè) | `KE-HK` + `on_sw_alignment=0` | global | — |
| **KE_levee** | Bờ Kè (KE trên tuyến kè) | `KE-HK` + `on_sw_alignment=1` | global | **Force full penetration** (luôn xuyên hết bùn + ngàm 1m) |

#### Filter HK selected

```sql
SELECT t.bh_name FROM tvtk_bh_cdm t
JOIN boreholes b ON b.name = t.bh_name
[LEFT JOIN ke_sw_design k ON k.bh_name = t.bh_name]  -- chỉ KE_*
WHERE t.selected = 1
  AND t.H_soft_m > 0
  AND t.bh_name LIKE ?  -- tiền tố zone
  [AND k.on_sw_alignment = ?]  -- chỉ KE_park (=0) hoặc KE_levee (=1)
```

**Kết quả filter:**
- BXN: 9 HK (CV-HK1, 5, 6, 10, 12, 14, 15, 16, 17)
- NHC: 7 HK (BH-03, 05, 20, 25, 28, 34, 37)
- KE_park: 5 HK (HK1, 4, 5, 6, 12)
- KE_levee: 5 HK (HK2, 3, 7, 9, 10)
- QTT: 6 HK (ND-02..07)

#### Thuật toán phân nhánh

```python
if zone_code == "QTT":
    # Dùng grid 162 điểm + per-HK design elev (§62)
    return compute_cdm_lc_matrix(...)

elif zone_code in ("BXN", "NHC", "KE_park"):
    # Design elev = global từ tvtk_cdm_config
    # CDM_top_elev = design - 1.9m (Σh đắp)
    # Tìm Lc ngắn nhất s.t. S₁+S₂ ≤ ΔS (find_cdm_length)

elif zone_code == "KE_levee":
    # FORCE FULL: p = H_soft + L_ngam (mặc định 1.0 m)
    # Lc cố định, chỉ kiểm tra S_total có ≤ ΔS hay không
    # Gọi find_cdm_length(target=9999) để lấy full history, chọn p ≥ H_soft + L_ngam
```

#### Sự khác biệt KE_levee

| Tham số | KE_park (thường) | KE_levee (kè) |
|---|---|---|
| Lc thay đổi theo ΔS | Có — chọn ngắn nhất đạt | **Không** — Lc cố định |
| Penetrates_full | Tùy ΔS | **Luôn = True** |
| Tiêu chí đánh giá | Lc tối thiểu | S_total đạt ΔS hay không |
| Lý do | Tối ưu chi phí | An toàn cao (gần kè, tải đẩy ngang) |

#### Mượn Cc gần nhất (§15)

HK trong zone không có Cc → mượn HK CÙNG zone có Cc gần nhất (Euclidean E/N từ `boreholes`):

```sql
SELECT b.name, b.x_coord_m AS N, b.y_coord_m AS E
FROM boreholes b
JOIN lab_tests lt ON lt.borehole_id = b.id
WHERE b.name LIKE 'BXN-CV-%'  -- cùng zone
  AND lt.Cc IS NOT NULL AND lt.Cc > 0
  AND b.name != current_bh
GROUP BY b.id
```

#### Lc cap-zero

Khi `tip_depth < cdm_top_depth` (clay_top nông hơn CDM_top), `Lc = max(0, ...)` để tránh số âm. Engine note rõ cho user.

#### 4 Bảng kết quả SQLite (đã lưu 2026-05-28)

Tất cả tự tạo khi gọi `scripts/save_cdm_zone_results.py::create_table()`. Lưu cả LOCAL DB (`C:\Users\bayng\TTHC_local\TTHC.sqlite`) lẫn PROJECT DB (`data/TTHC.sqlite`).

**1. `cdm_zone_design_results`** — Lc tối ưu per HK × ΔS (128 rows):
```sql
PRIMARY KEY (zone_code, bh_name, delta_S_cm)
cols: Lc_m, tip_depth_m, p_optimal_m, S1_cm, S2_cm, S_total_cm,
      penetrates_full, force_full, cc_source, borrowed, ok,
      H_soft_m, cdm_top_elev_m, updated_at
```

**2. `cdm_zone_smoothness_results`** — Cặp HK + chênh lún (257 rows):
```sql
PRIMARY KEY (zone_code, delta_S_cm, hk_i, hk_j)
cols: d_m, dS_pair_m, i_inv_actual, S_i_cm, S_j_cm, updated_at
```
- Tính theo i_inv_max = 125 (vồng cho phép tối đa). Query thực tế: lọc `i_inv_actual >= i_inv_user` để check pass/fail.

**3. `cdm_zone_s_lc_curves`** — S(p) sweep per HK (1075 rows):
```sql
PRIMARY KEY (zone_code, bh_name, p_m)
cols: Lc_m, tip_depth_m, S1_cm, S2_cm, S_total_cm,
      cc_source, borrowed, updated_at
```
- Quét p từ 0.5m → 35m bước 1m cho mỗi HK selected.

**4. `cdm_qtt_grid_lc`** — Grid Lc 162 điểm QTT × 4 ΔS (648 rows):
```sql
PRIMARY KEY (delta_S_cm, easting_m, northing_m)
cols: elev_des_m, elev_nat_m, fill_m, cdm_top_elev_m,
      ref_hk, ref_dist_m, Lc_m, tip_depth_m, S_total_cm, ok, updated_at
```

**Tổng cộng:** 128 + 257 + 1075 + 648 = **2108 rows** kết quả tính toán lưu vĩnh viễn trong SQLite.

#### Lệnh chạy save

```bash
python scripts/save_cdm_zone_results.py
# Auto save vào DB nào tồn tại (ưu tiên LOCAL)
```

#### UI — Section "Phân tích CDM đa khu vực"

Đặt sau section J (QTT) trong tab "Dự báo độ lún":

1. Radio chọn zone (BXN / NHC / KE_park / KE_levee)
2. Thông số dùng chung (q, D, s, a, Ec, design, Σh đắp, force_full)
3. Bảng tổng hợp Lc × ΔS cho mọi HK + trạng thái mũi
4. Selector tiêu chí (cấp đường × công trình × v × ΔS × vồng)
5. Check độ bằng phẳng pair-wise
6. Nút "Xuất báo cáo Word — {zone}"

#### Word — `build_zone_decision_docx(zone)`

7 mục báo cáo:
1. Thông số đầu vào (zone, q, D, s, a, Ec)
2. Tiêu chí thiết kế đã chọn
3. Lc tối ưu mỗi HK + heatmap + bar chart
4. Đường cong S(Lc) (nếu có curves_data)
5. Kiểm tra độ bằng phẳng pair-wise + scatter
6. Phân tích kỹ thuật trạng thái mũi cọc + profile σ'v0
7. Kết luận và Khuyến nghị

**Cho KE_levee:** trang bìa có note đặc biệt "Quy tắc kè — luôn xuyên hết bùn"; section 6 nhấn mạnh S₂ chỉ tính cho lớp dưới bùn → S nhỏ → đáp ứng nhanh ΔS.

#### Kết quả mẫu (q=40.8 kPa, D=800mm, s=1.8m)

| Zone | Số HK | Lc max ΔS=30cm | Số HK hết bùn (ΔS=30) |
|---|:---:|:---:|:---:|
| BXN | 9 | 17.09 m | 0/9 (đa số trong lớp bùn) |
| NHC | 7 | 26.61 m | 4/7 |
| KE_park | 5 | 16.96 m | 0/5 |
| **KE_levee** | 5 | 29.18 m (cố định) | **5/5** (force full) |
| QTT | 6 | 25.7 m | 1/6 |

#### Lệnh

```bash
# Tính engine standalone
python scripts/qtt_cdm_analysis.py

# Lưu vào SQLite
python scripts/save_cdm_zone_results.py  # tạo + save 4 zone × 4 ΔS

# Xuất Word 4 zone (offline)
python -c "from qtt_cdm_analysis import compute_zone_cdm_lc_matrix; ..."
```
