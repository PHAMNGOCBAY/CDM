### 62. Thuật toán quyết định thiết kế CDM cho QTT — Tối ưu Lc + Độ bằng phẳng

**File engine:** [scripts/qtt_cdm_analysis.py](scripts/qtt_cdm_analysis.py)
**File Word:** [scripts/qtt_cdm_report.py](scripts/qtt_cdm_report.py)
**JSON config:** [data/qtt_cdm_criteria.json](data/qtt_cdm_criteria.json)
**SQLite:** `tccs41_settlement_limits` (6 ô ΔS) · `tccs41_smoothness_limits` (20 ô i) · `qtt_elevation_points` (162 điểm grid) · `qtt_cdm_boundary` (polygon ranh giới)
**UI:** [scripts/app_cdm.py](scripts/app_cdm.py) tab "Dự báo độ lún" zone QTT — section F-G-H-I-J

#### Mục tiêu

Tìm chiều dài cọc CDM (Lc) tối ưu cho mỗi hố khoan ND và mỗi điểm grid trong polygon QTT, thoả mãn ĐỒNG THỜI:

1. **Tiêu chí lún cố kết còn lại** ΔS ≤ giới hạn TCCS 41 Bảng 1 (Điều 6.2.3)
2. **Tiêu chí độ bằng phẳng** i ≤ giới hạn TCCS 41 Bảng E.1 (cho phép vồng 1/125)

Sau đó phân vùng thiết kế (zone) theo Lc và xuất báo cáo Word.

#### Đầu vào cố định (từ SQLite)

| Tham số | Nguồn | Giá trị |
|---|---|---|
| q (tải phân bố trên đỉnh CDM) | `tvtk_cdm_config.q_kPa` | 40.8 kPa |
| Σh đắp (Áo đường + He + Hse) | `tvtk_fill_composition` | 1.9 m |
| D (đường kính cọc) | `tvtk_cdm_config.D_mm` | 800 mm |
| s (khoảng cách) | `tvtk_cdm_config.spacing_m` | 1.8 m |
| pattern | `tvtk_cdm_config.pattern` | square |
| k (Ec_factor) | `tvtk_cdm_config.Ec_factor` | 100 |
| qu (cường độ thiết kế) | `tvtk_cdm_config.qu_kPa` | 800 kPa |
| Ec | tính: k × qu / 2 | 40 000 kPa |
| a (tỷ lệ thay thế) | tính: π(D/2)² / s² | 0.1551 |
| Cao độ thiết kế từng điểm | `qtt_elevation_points.elev_des_m` | biến thiên 2.70–3.07 m |
| Cao độ tự nhiên từng điểm | `qtt_elevation_points.elev_nat_m` | biến thiên 1.09–4.24 m |

**Cao độ đỉnh CDM** = cao độ thiết kế − Σh đắp = `elev_des_m − 1.9`.

#### Thuật toán

**Bước 1 — Tính Lc cho mỗi HK × mỗi ΔS** (`compute_cdm_lc_matrix`):

Cho HK i, mức ΔS ∈ {10, 20, 30, 40} cm:

```
nat_i        = boreholes.elevation_m
design_i     = qtt_elevation_points.elev_des_m (nearest grid)
cdm_top_i    = design_i − 1.9 m
clay_top_i   = layers.depth_top_m (min where symbol ∈ {1,1b,2,XMD})
H_soft_i     = Σ layer thickness của lớp yếu
Su_i, mu_i   = VST hoặc UU (priority §15); μ Bjerrum theo Ip
Es_i         = 250 × μ × Su

p_optimal    = find_cdm_length(bh_i, q=40.8, a=0.1551, Ec=40000,
                                Su=Su_i, target_dS=ΔS, mu=μ_i, ...)
                                    ↳ độ xuyên vào lớp yếu (m)
tip_depth_i  = clay_top_i + p_optimal
Lc_i(ΔS)     = tip_depth_i − (nat_i − cdm_top_i)
            = tip_depth_i − cdm_top_depth_i (từ tự nhiên)
```

`find_cdm_length` gọi `calc_s2_below_cdm` bên trong. **S₂ phân nhánh sét/cát** (memory `feedback-s2-branches-clay-sand`):

- Lớp **sét** (symbol NOT IN SAND_SYMBOLS_S2): Terzaghi 1D với Cc (OC/NC/cross-PC) hoặc Eoed fallback
- Lớp **cát** (symbol IN SAND_SYMBOLS_S2 = {F, 2a, 2b, 2c, 3a, 3b, 3c, 4, 5, 5a, 5b, 6, 7, 8}): $S_i = \dfrac{\Delta\sigma \cdot h_i}{E_s}$ với $E_s = \alpha_{sand} \cdot N_{SPT}$, $\alpha_{sand} = 2000$ kPa

Tiêu chí dừng chung: $\Delta\sigma / \sigma'_{v0} < 10\%$ (bước 2m phân tố).

HK không có Cc → mượn HK ND có Cc gần nhất theo Euclidean distance (§15).

**Bước 2 — Tra giới hạn độ bằng phẳng** (`get_smoothness_i_inv`):

```sql
SELECT i_denominator FROM tccs41_smoothness_limits
WHERE road_class_code = ? AND structure = ? AND speed_kmh = ?
```

Tra theo (cấp đường ∈ {cao_toc, cap_I_IV}) × (công trình ∈ {cau, cong}) × (v ∈ {40, 60, 80, 100, 120}). Trả về `i_inv` (mẫu số, vd 200 cho i=1/200).

Khi cho phép tạo vồng trước: `i_inv_effective = max(i_inv_table, 125)` (nới về 1/125).

**Bước 3 — Kiểm tra độ bằng phẳng pair-wise** (`check_pairwise_smoothness`):

Với mỗi cặp HK (i,j):

```
d_ij     = √((E_i − E_j)² + (N_i − N_j)²)        [m]
ΔS_ij    = |S_i − S_j| / 100                     [m, từ cm]
i_actual = ΔS_ij / d_ij                          [vd 0.005 = 1/200]
i_inv    = d_ij / ΔS_ij                          [vd 200]

ok       = i_actual ≤ i_max   ↔   i_inv ≥ i_inv_max
```

Tất cả cặp phải đạt mới coi là "khu vực đạt độ bằng phẳng".

**Bước 4 — Tính Lc grid** (`compute_grid_lc`):

Cho mỗi điểm grid (E, N) trong 162 điểm `qtt_elevation_points`:

```
ref_hk      = HK ND có Cc gần nhất (Euclidean E,N)
elev_des    = qtt_elevation_points.elev_des_m
elev_nat    = qtt_elevation_points.elev_nat_m
cdm_top     = elev_des − 1.9 m
cdm_top_depth_local = elev_nat − cdm_top

# Dùng soil profile của ref_hk (Cc, e0, PC, Su, μ)
Lc_grid     = find_cdm_length(ref_hk, q=40.8, ΔS_target, ...) → tip_depth
              − cdm_top_depth_local
```

Đây là **xấp xỉ kỹ thuật**: dùng soil profile của HK gần nhất nhưng tính từ cao độ tự nhiên LOCAL. Cho phép phân giải spatial Lc 162 điểm.

**Bước 5 — Phân vùng (zoning)** (`cluster_grid_into_zones`):

Quantile-based binning: chia n_zones nhóm theo Lc grid.

```python
Lcs = sorted([p.Lc_m for p in grid_points if p.ok])
breaks = [Lcs[int(n*k/n_zones)] for k in range(1, n_zones)]
# Mỗi vùng: Lc_design = max(Lcs trong vùng) — an toàn
```

#### Quy ước "đạt"

Một thiết kế (chọn cấp đường, công trình, v, ΔS, vồng) ĐẠT khi:

1. Mọi HK ND có Cc đều có Lc ≤ p_max (xuyên hết lớp yếu vẫn còn dư địa)
2. Mọi cặp HK đều thoả độ bằng phẳng sau cố kết
3. Có lời giải Lc cho mọi điểm grid trong polygon

#### Pareto trade-off

| ΔS chọn | Lc max | Khối lượng CDM | Cấp đường phù hợp |
|---|---|---|---|
| 10 cm | rất lớn (thường KĐ) | rất cao | Cao tốc gần mố cầu |
| 20 cm | ~30 m | cao | Cao tốc gần cống / cấp 2 gần mố |
| 30 cm | ~25 m | trung | Cao tốc thường / cấp 2 cống |
| 40 cm | ~17 m | thấp | Cấp 2 đoạn thông thường |

**Khuyến nghị mặc định cho QTT:** ΔS ≤ 30 cm (cao tốc đoạn thông thường) hoặc 40 cm (cấp 2 thông thường), với i ≤ 1/125 (cho phép vồng).

#### Output

1. **UI** (Streamlit) — section F-G-H-I-J:
   - F: selector tiêu chí
   - G: bảng smoothness pair-wise
   - H: heatmap Lc grid 162 điểm
   - I: bảng phân vùng + heatmap zone
   - J: nút xuất Word
2. **Word docx** — `build_qtt_decision_docx()`: 6 mục báo cáo
3. **JSON config** — `data/qtt_cdm_criteria.json` (định nghĩa các option chuẩn)
4. **SQLite** — không tạo bảng mới, đọc từ các bảng có sẵn

#### Files liên quan

- [scripts/qtt_cdm_analysis.py](scripts/qtt_cdm_analysis.py) — engine
- [scripts/qtt_cdm_report.py](scripts/qtt_cdm_report.py) — Word builder
- [scripts/cdm_length_optimize.py](scripts/cdm_length_optimize.py) — `find_cdm_length` core
- [scripts/settlement_calc.py](scripts/settlement_calc.py) — `bjerrum_mu`, `calc_s2_below_cdm`
- [scripts/core/formulas/cdm.py](scripts/core/formulas/cdm.py) — S1, S2, Ec, Es formulas (registry)
- [data/qtt_cdm_criteria.json](data/qtt_cdm_criteria.json) — option chuẩn (cấp/công trình/v/vồng)
