# 28 — geotech-staff-engineer 4.6.0 — Phạm vi áp dụng các module

**Nguồn:** `__init__.py` inspection + import test 2026-05-16  
**Cài đặt:** `python -m pip install geotech-staff-engineer`  
**Lưu ý numpy:** Yêu cầu numpy>=2.0 nhưng chạy được với 1.26.4 (giữ tương thích openpile)

> **AI workflow:** Đọc file này → `data/geotech_staff_engineer.json` → `scripts/geotech_staff_engineer_demo.py`

---

## Tóm tắt nhanh — Bảng chọn module theo bài toán

| Bài toán | Module | Import |
|----------|--------|--------|
| Cọc đóng — tải dọc (FHWA) | `axial_pile` | `from axial_pile import AxialPileAnalysis` |
| Cọc khoan nhồi — tải dọc | `drilled_shaft` | `from drilled_shaft import DrillShaftAnalysis` |
| Cọc đóng — tải ngang (COM624P) | `lateral_pile` | `from lateral_pile import LateralPileAnalysis` |
| Cọc đóng — tải ngang (API p-y) | `openpile` (**đã tích hợp**) | `import openpile` + Streamlit |
| Nhóm cọc + cap cứng | `pile_group` | `from pile_group import analyze_vertical_group_simple` |
| Cố long âm (NSF) | `downdrag` | `from downdrag import DowndragAnalysis` |
| Phương trình sóng đóng cọc | `wave_equation` | `from wave_equation import generate_bearing_graph` |
| Móng nông — sức chịu tải | `bearing_capacity` | `from bearing_capacity import BearingCapacityAnalysis` |
| Móng nông — độ lún | `settlement` | `from settlement import SettlementAnalysis` |
| Kè cọc bản consolle | `sheet_pile` | `from sheet_pile import analyze_cantilever` |
| Kè cọc bản có neo | `sheet_pile` | `from sheet_pile import analyze_anchored` |
| Hố đào có chống/neo đa tầng | `soe` | `from soe import analyze_braced_excavation` |
| Tường chắn consolle / MSE | `retaining_walls` | `from retaining_walls import analyze_cantilever_wall` |
| Ổn định mái dốc | `slope_stability` | `from slope_stability import analyze_slope` |
| FEM 2D (Mohr-Coulomb, SRM) | `fem2d` | `from fem2d import analyze_slope_srm` |
| FDM 2D (FLAC-style) | `fdm2d` | `from fdm2d import analyze_gravity` |
| Xử lý nền — wick drain | `ground_improvement` | `from ground_improvement import analyze_wick_drains` |
| Động đất — Mononobe-Okabe | `seismic_geotech` | `from seismic_geotech import seismic_earth_pressure` |
| Hóa lỏng đất | `seismic_geotech` | `from seismic_geotech import evaluate_liquefaction` |
| Tải gió — tường độc lập | `wind_loads` | `from wind_loads import analyze_freestanding_wall_wind` |
| Báo cáo tính toán HTML/PDF | `calc_package` | `from calc_package import generate_calc_package` |
| Đọc bản vẽ DXF | `dxf_import` | `from dxf_import import build_slope_geometry` |
| Đọc PDF bản vẽ | `pdf_import` | `from pdf_import import extract_geometry_vision` |
| Đọc file AGS4 | `ags4_agent` | `from ags4_agent import read_ags4` |

---

## 1. Nhóm Cọc — Tải dọc trục

### 1.1 axial_pile — Cọc đóng (FHWA GEC-12)

```python
from axial_pile import AxialPileAnalysis, AxialSoilLayer, AxialSoilProfile
from axial_pile import make_pipe_pile, make_concrete_pile, make_h_pile
```

**Phương pháp:**
- Nordlund — cát rời (cohesionless)
- Tomlinson alpha-method — đất sét (cohesive)
- Beta effective-stress — mọi loại đất

**Tham chiếu:** FHWA GEC-12 (FHWA-NHI-16-009), Chapters 7–8

**Phạm vi áp dụng:** Cọc thép ống, cọc BTCT, cọc H — tính Rs + Rp theo FHWA

**So với dự án:** Đối chiếu với `scripts/ke_sw_TTHC.py` (TCVN 11823-10 alpha-method). Kết quả FHWA ≠ TCVN; dùng TCVN cho nghiệm thu dự án Việt Nam.

---

### 1.2 drilled_shaft — Cọc khoan nhồi (FHWA GEC-10)

```python
from drilled_shaft import DrillShaftAnalysis, DrillShaft, ShaftSoilLayer, ShaftSoilProfile
```

**Phương pháp:** Alpha (sét), Beta (cát), Rock socket (đá), End bearing

**Tham chiếu:** FHWA GEC-10 (FHWA-NHI-10-016), Brown et al. (2010/2018)

---

### 1.3 downdrag — Cố long âm (NSF)

```python
from downdrag import DowndragAnalysis, DowndragSoilLayer, DowndragSoilProfile
```

**Phương pháp:** Fellenius unified method — xác định neutral plane

**Kích hoạt:** Đắp nền (fill placement), hạ mực nước ngầm

**Đầu ra:** Độ sâu neutral plane, dragload, độ lún đầu cọc

---

### 1.4 wave_equation — Phương trình sóng đóng cọc

```python
from wave_equation import generate_bearing_graph, drivability_study, get_hammer, list_hammers
```

**Phương pháp:** Smith 1-D wave equation, explicit time integration

**Tham chiếu:** Smith (1960); FHWA GEC-12 Chap 12; WEAP87

**Tính năng:**
- Bearing graph: blow count vs Rult
- Drivability study: blow count theo chiều sâu
- Cơ sở dữ liệu búa: Vulcan, Delmag, ICE (có sẵn)

**Phạm vi áp dụng:** Kiểm tra đóng cọc SW trên nền đất TTHC — dự đoán blow count, ứng suất động đóng cọc

---

### 1.5 pile_group — Nhóm cọc

```python
from pile_group import analyze_vertical_group_simple, analyze_group_6dof
from pile_group import GroupPile, create_rectangular_layout, GroupLoad
from pile_group import converse_labarre, block_failure_capacity, p_multiplier
```

**Phương pháp:**
- Simplified elastic: Pi = V/n ± M·xi / Σ(xi²)
- 6-DOF stiffness matrix (cọc xiên)
- Hiệu quả nhóm: Converse-Labarre, Block failure, p-multipliers

---

## 2. Cọc — Tải ngang

### 2.1 lateral_pile — p-y COM624P / FHWA

```python
from lateral_pile import LateralPileAnalysis, Pile, SoilLayer, ReinforcedConcreteSection
```

**Phương pháp:** p-y curves theo COM624P (Wang & Reese, 1993), Jeanjean (2009) soft clay

**Tham chiếu:** FHWA-SA-91-048; FHWA GEC-13; Jeanjean (2009) OTC-20158

**So sánh với openpile:**

| | `lateral_pile` | `openpile` |
|-|---------------|-----------|
| Nguồn p-y | COM624P (FHWA-SA-91-048) | Matlock (1970) / API RP 2GEO |
| Solver | FDM | FEM Euler-Bernoulli + Timoshenko |
| Giao diện | Function-based | OOP (Pile, Layer, Model) |
| Tích hợp app | Chưa | Streamlit v6 sẵn có |
| Cọc BTCT có thép | ReinforcedConcreteSection | Không |

**Khuyến nghị:** Dùng openpile cho thiết kế cơ bản; dùng `lateral_pile` để đối chiếu phương pháp FHWA.

---

## 3. Móng nông + Độ lún

### 3.1 bearing_capacity — Sức chịu tải móng nông

```python
from bearing_capacity import BearingCapacityAnalysis, Footing, SoilLayer, BearingSoilProfile
```

**Phương pháp:** Meyerhof + Vesic — general bearing capacity equation

**Tham chiếu:** FHWA-SA-94-034 (CBEAR); FHWA GEC-6; FHWA Vol II Chap 8

**Tính năng:**
- Móng: strip, rectangular, square, circular
- Hệ số: tải nghiêng, đáy nghiêng, mặt đất dốc, lệch tâm (effective area)
- 2 lớp đất, mực nước ngầm tùy vị trí

---

### 3.2 settlement — Độ lún

```python
from settlement import SettlementAnalysis, ConsolidationLayer, SchmertmannLayer
from settlement import stress_at_depth, elastic_settlement, schmertmann_settlement
from settlement import time_factor, degree_of_consolidation, settlement_at_time
```

**Phương pháp:**
- Lún tức thời: Elastic method, Schmertmann (1978)
- Lún cố kết: Cc/Cr e-log(p), tổng nhiều lớp
- Tốc độ cố kết: Terzaghi 1-D — Tv, U, t
- Lún thứ cấp: C_alpha creep
- Phân bố ứng suất: 2:1, Boussinesq, Westergaard

---

## 4. Tường chắn + Hố đào

### 4.1 sheet_pile — Kè cọc bản

```python
from sheet_pile import analyze_cantilever, analyze_anchored, WallSoilLayer
from sheet_pile import rankine_Ka, rankine_Kp, coulomb_Ka, coulomb_Kp
from sheet_pile import active_pressure, passive_pressure, tension_crack_depth
```

**Tham chiếu:** USACE EM 1110-2-2504; CWALSHT methodology

**Đầu ra:**
- Consolle: chiều sâu ngàm, moment max
- Có neo: lực neo, moment max

**So với dự án:** Đối chiếu với `scripts/earth_pressure.py` (Ka/Kp thủ công). `sheet_pile` tự động tính chiều sâu ngàm và nội lực.

---

### 4.2 soe — Hố đào có chống/neo đa tầng

```python
from soe import (analyze_braced_excavation, analyze_cantilever_excavation,
                 ExcavationGeometry, SOEWallLayer, SupportLevel,
                 check_basal_heave_terzaghi, check_basal_heave_bjerrum_eide,
                 check_bottom_blowout, check_piping,
                 select_sheet_pile, select_hp_section, check_flexural_demand)
```

**Tham chiếu:** Terzaghi & Peck (1967); FHWA GEC-4; USACE EM 1110-2-2504; AISC 16th Ed

**Phương pháp:** Terzaghi-Peck apparent earth pressure envelopes + tributary area

**Biểu đồ áp lực (Terzaghi-Peck):**
- Cát: hình thang cố định
- Sét mềm: phụ thuộc Ns = γH/Su
- Sét cứng: hình thang thu hẹp

**Kiểm tra ổn định:**
- Basal heave: Terzaghi (1943), Bjerrum-Eide (1956)
- Bottom blowout (đáy thủng)
- Piping (xói ngầm)

**Chọn tiết diện:** HP, sheet pile, W section theo AISC

**Phạm vi áp dụng (dự án TTHC):** Rất phù hợp với kè SW có chống hoặc neo đất. Thay thế tính thủ công; kiểm tra Fs heave tự động.

---

### 4.3 retaining_walls — Tường chắn consolle / MSE

```python
from retaining_walls import analyze_cantilever_wall, analyze_mse_wall
from retaining_walls import CantileverWallGeometry, MSEWallGeometry
```

**Kiểm tra:** Sliding, Overturning, Bearing

**Tham chiếu:** AASHTO LRFD Section 11; FHWA GEC-11 (MSE Walls)

---

## 5. Ổn định mái dốc

### 5.1 slope_stability — Giới hạn cân bằng

```python
from slope_stability import (analyze_slope, search_critical_surface,
                              SlopeGeometry, SlopeSoilLayer, SoilNail,
                              fellenius_fos, bishop_fos, spencer_fos, morgenstern_price_fos,
                              grid_search, search_pso, CircularSlipSurface)
```

**Phương pháp:**
- Fellenius (1927) — Ordinary Method of Slices
- Bishop Simplified (1955)
- Spencer (1967)
- Morgenstern-Price

**Tìm kiếm mặt trượt:** Grid, PSO (particle swarm), entry-exit, weak layer biased

**Mặt trượt:** Circular, Polyline (non-circular)

**Thêm:** Soil nails (SoilNail)

---

## 6. Phương pháp số FEM/FDM

### 6.1 fem2d — FEM 2D tùy chỉnh

```python
from fem2d import (analyze_gravity, analyze_foundation, analyze_slope_srm,
                   analyze_excavation, analyze_seepage, analyze_consolidation, analyze_staged)
```

**Phần tử:** CST (triangle 3-nút), Q4 (quad 4-nút), Euler-Bernoulli beam

**Vật liệu:** Linear elastic, Mohr-Coulomb, Hardening Soil

**Khả năng:** SRM slope stability, braced excavation + sheet pile, Biot consolidation, staged construction

**So với PLAXIS:** Dành cho giáo dục / kiểm chứng — không thay thế PLAXIS cho dự án thực tế.

---

### 6.2 fdm2d — FDM 2D (FLAC-style)

```python
from fdm2d import analyze_gravity, analyze_foundation
```

**Solver:** Explicit Lagrangian — không cần ma trận độ cứng toàn cục (như FLAC)

**Phần tử:** Quad zones + 4 sub-triangles (mixed discretization, Marti & Cundall 1982)

**Phạm vi:** Gravity loading, surface pressure — học thuật, so sánh thuật toán

---

## 7. Địa kỹ thuật động đất

### 7.1 seismic_geotech

```python
from seismic_geotech import (classify_site, site_coefficients,
                              mononobe_okabe_KAE, mononobe_okabe_KPE, seismic_earth_pressure,
                              evaluate_liquefaction, post_liquefaction_strength)
```

**Tham chiếu:** AASHTO LRFD §3/§11; Youd et al. (2001); Boulanger & Idriss (2014)

| Chức năng | Mô tả |
|----------|-------|
| `classify_site` | AASHTO/NEHRP site class từ Vs30, N-bar, su-bar |
| `seismic_earth_pressure` | Mononobe-Okabe KAE, KPE — áp lực đất khi có động đất |
| `evaluate_liquefaction` | Simplified triggering (Seed & Idriss / Youd et al.) |
| `post_liquefaction_strength` | Sức kháng cắt sau hóa lỏng |

---

### 7.2 wind_loads — Tải gió (ASCE 7-22)

```python
from wind_loads import analyze_freestanding_wall_wind, compute_velocity_pressure
```

**Tham chiếu:** ASCE 7-22 Chapters 26 & 29

**Đơn vị:** SI (m, m/s, Pa, kN)

---

## 8. Xử lý nền đất yếu

```python
from ground_improvement import (analyze_aggregate_piers, analyze_wick_drains,
                                 design_drain_spacing, analyze_surcharge_preloading,
                                 analyze_vibro_compaction, evaluate_feasibility)
```

| Phương pháp | Module |
|------------|--------|
| Cọc đá dăm (aggregate piers) | `analyze_aggregate_piers` |
| PVD wick drain | `analyze_wick_drains`, `design_drain_spacing` |
| Đắp gia tải (surcharge) | `analyze_surcharge_preloading` |
| Đầm chấn động (vibro) | `analyze_vibro_compaction` |
| Đánh giá khả thi | `evaluate_feasibility` |

**Tham chiếu:** FHWA NHI-06-019/020; Barron (1948); Hansbo (1981)

---

## 9. Tiện ích dữ liệu + CAD

| Module | Mục đích | Import |
|--------|----------|--------|
| `geotech_common` | Đổi đơn vị (SI↔US), SPT correlations, Ka/Kp từ phi | `from geotech_common.units import kPa_to_ksf` |
| `calc_package` | Xuất báo cáo tính toán HTML / LaTeX-PDF | `from calc_package import generate_calc_package` |
| `ags4_agent` | Đọc file AGS4 (chuẩn địa chất Anh) | `from ags4_agent import read_ags4` |
| `dxf_import` | Đọc bản vẽ DXF → slope/FEM geometry | `from dxf_import import build_slope_geometry` |
| `pdf_import` | Trích xuất hình học từ PDF bản vẽ | `from pdf_import import extract_geometry_vision` |
| `subsurface_characterization` | Tổng hợp dữ liệu khảo sát, vẽ mặt cắt, thống kê | `from subsurface_characterization import SiteModel` |

---

## 10. So sánh phương pháp — Bảng tham chiếu nhanh

### Cọc chịu tải ngang

| | openpile (đã tích hợp) | lateral_pile (GSE) |
|-|----------------------|-------------------|
| Chuẩn p-y | Matlock 1970 / API RP 2GEO | COM624P / FHWA-SA-91-048 |
| Soft clay mới nhất | Không | Jeanjean 2009 |
| Cọc BTCT có thép | Không | Có (ReinforcedConcreteSection) |
| Tích hợp Streamlit | Có (v6) | Chưa |

### Ổn định mái dốc

| | slope_stability (GSE) | fem2d (GSE) | PLAXIS |
|-|----------------------|------------|--------|
| Phương pháp | Giới hạn cân bằng | FEM + SRM | FEM + SRM |
| Độ chính xác | Tốt (Bishop/Spencer) | Khá | Tốt nhất |
| Tốc độ | Nhanh | Trung bình | Chậm |
| Chi phí | Miễn phí | Miễn phí | License |
| Khuyến nghị | Sơ bộ | Học thuật | Chính thức |

### Sức chịu tải cọc dọc

| | ke_sw_TTHC.py (TCVN) | axial_pile (FHWA) |
|-|----------------------|-------------------|
| Chuẩn | TCVN 11823-10:2017 | FHWA GEC-12 |
| Pháp lý VN | Bắt buộc | Tham khảo |
| Đất sét | Tomlinson alpha, phi=0.35 | Tomlinson alpha |
| Cát | Rs=0 | Nordlund |

---

## Liên kết

| File | Vai trò |
|------|---------|
| `data/geotech_staff_engineer.json` | Catalog đầy đủ — query trực tiếp |
| `scripts/geotech_staff_engineer_demo.py` | Demo các module quan trọng nhất |
| `data/python_libs_geotechnical.json` | Catalog thư viện khác (openpile, geolysis, …) |
| `19-thu-vien-python.md` | Tài liệu thư viện p-y, Ks, Winkler |
