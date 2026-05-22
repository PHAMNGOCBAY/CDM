# P4 — Frame 2D Nâng cao: Plan triển khai

> **Mục tiêu:** Mở rộng `wall_internal_force.py` (Winkler 1 cọc, 2 DOF/nút) lên solver **frame 2D đầy đủ** (3 DOF/nút, ma trận 6×6), hỗ trợ nhiều phần tử nối nhau (cọc + dầm mũ + neo + strut), connection releases, P-Delta, prestress neo.
>
> **Trạng thái:** Plan đang chờ review. Code chưa được viết.
>
> **Phạm vi local:** Module này **KHÔNG** đưa lên Streamlit Cloud — chỉ chạy local trên port 8504.

---

## 1. Scope — Làm gì / Không làm

### ✅ Sẽ làm

| # | Tính năng | Lý do cần |
|---|-----------|-----------|
| 1 | Frame 2D với 3 DOF/nút (u_x, u_y, θ_z), ma trận K 6×6 | Thay thế Winkler 1D, hỗ trợ tải dọc trục + lực ngang đồng thời |
| 2 | Beam element (Euler-Bernoulli) + Truss element (chỉ EA) | Cọc/dầm dùng beam; neo/strut/cáp dùng truss |
| 3 | Connection releases (pin/fixed) tại 2 đầu phần tử | Thực tế: nối cọc-dầm mũ thường pin, neo luôn pin |
| 4 | Winkler springs gắn vào node trong đất (kh, kv, optional kr) | Tận dụng `kh_clay_matlock`, `kh_sand_api` đã có |
| 5 | Prestress cho phần tử neo (lực căng ban đầu) | Tường vây neo thực tế luôn có prestress 200-500 kN/cáp |
| 6 | P-Delta (geometric stiffness K_g) tùy chọn | Cọc/cột chịu nén lớn → moment khuếch đại |
| 7 | Staged construction (deactivate/activate elements + BC theo pha) | Mô phỏng đào dần, lắp neo từng tầng |
| 8 | SQLite storage cho model + result (prefix `fem2d_frame_`) | Lưu/tải lại, JOIN với boreholes/sw_pile_catalog |
| 9 | Builder API cao cấp (`FrameBuilder`) cho bài toán tường cừ điển hình | User không phải tự định nghĩa từng node/element |
| 10 | Post-processing: diagrams M/V/N + deformed shape + plot via Plotly/Matplotlib | Verify trực quan |
| 11 | App Streamlit riêng `scripts/app_fem2d.py` port 8504 | Theo yêu cầu user |
| 12 | Verify với 5 test case analytical + 2 case Plaxis | Đảm bảo đúng |

### ❌ Sẽ KHÔNG làm trong P4 (để các phase sau)

| Tính năng | Lý do hoãn |
|-----------|-----------|
| Plane strain solid elements | Phase P1+P2 |
| Mohr-Coulomb plasticity | Phase P2 |
| Mesh tam giác/tứ giác 2D | Phase P1 |
| Cố kết Biot 2D | Phase P5 |
| Dynamic analysis (động đất) | Out of scope toàn dự án |
| 3D | Out of scope |
| Plate bending (2D solid plate) | Out of scope |

---

## 2. Cấu trúc thư mục mới

```
scripts/
  fem2d/                              ← package mới
    __init__.py                       ← export public API
    frame2d/
      __init__.py
      types.py                        ← @dataclass Node, Element, Load, FrameModel, FrameResult
      element_beam.py                 ← Ke 6×6 + consistent load + Kg (P-Delta)
      element_truss.py                ← Ke 4×4 cho thanh axial
      releases.py                     ← Áp dụng release tại 2 đầu phần tử
      assembler.py                    ← Lắp ráp K toàn cục + F + Winkler springs
      solver.py                       ← solve_static, solve_pdelta (iterative)
      builder.py                      ← FrameBuilder high-level API
      postprocess.py                  ← Diagrams + deformed shape (matplotlib + plotly)
      db.py                           ← Save/load to SQLite (prefix fem2d_frame_)
      verify.py                       ← Test case (cantilever, simply supported, portal frame)
  app_fem2d.py                        ← Streamlit app port 8504

data/
  TTHC.sqlite                         ← thêm 5 bảng fem2d_frame_* (KHÔNG tạo DB mới)

NN-fem2d-frame-architecture.md        ← tài liệu kỹ thuật chi tiết
start_fem2d.bat                       ← khởi động local port 8504
```

**KHÔNG** sửa `scripts/wall_internal_force.py` hay `scripts/winkler_np.py` — giữ nguyên cho compatibility. Module mới đặt trong `fem2d/frame2d/` hoàn toàn tách biệt.

---

## 3. Bảo vệ chống lên Cloud (4 lớp)

```bash
# Lớp 1: update_app.bat chỉ copy 4 file cụ thể — fem2d/ không có trong whitelist
# (không cần sửa gì)

# Lớp 2: cdm-deploy/.gitignore — thêm:
scripts/fem2d/
scripts/app_fem2d.py
start_fem2d.bat
data/fem2d_*.sqlite   # nếu user tạo DB riêng (hiện kế hoạch dùng chung TTHC.sqlite)

# Lớp 3: bảng fem2d_frame_* trong TTHC.sqlite — KHÔNG ảnh hưởng Cloud (DB chỉ đọc)

# Lớp 4: CLAUDE.md mục 14 — thêm scikit-fem, pygmsh, gmsh vào danh sách "local only"
```

---

## 4. Stack thư viện cần cài (Python 3.12 local)

```powershell
& "C:\Users\bayng\AppData\Local\Programs\Python\Python312\python.exe" -m pip install `
    "scikit-fem>=8.0" `
    "meshio>=5.3" `
    "pygmsh>=7.1" `
    "gmsh>=4.13" `
    "pyvista>=0.44"
```

**Ghi chú cài đặt:**

- `scikit-fem` thuần Python + NumPy, không binary. Wheel sẵn cho Python 3.12 Windows.
- `gmsh` có binary wheel ~50MB. Cài qua pip OK trên Windows.
- `pygmsh` wrap `gmsh` API — chỉ cần khi geometry phức tạp. Cho P4 chưa dùng (frame 1D), nhưng cài sẵn cho các phase sau.
- `meshio` đọc/ghi nhiều định dạng mesh (.msh, .vtk, .xdmf, .geo, .pvtu). Optional cho P4.
- `pyvista` cho 3D visualization — chưa cần cho P4 (Plotly đủ).

**Có thể chỉ cài tối thiểu cho P4:**

```powershell
& "C:\Users\bayng\AppData\Local\Programs\Python\Python312\python.exe" -m pip install scikit-fem
```

→ Nhưng tốt nhất cài full để các phase sau không phải cài lại.

---

## 5. API public dự kiến

### 5.1 Low-level (full control)

```python
from fem2d.frame2d import Node, BeamElement, TrussElement, NodalLoad, ElemDistLoad, FrameModel

nodes = [
    Node(id=0, x=0.0, y=2.5,  restraints=(False, False, False)),  # đỉnh tự do
    Node(id=1, x=0.0, y=1.5,  spring_kh=120.0),                   # lò xo Winkler
    Node(id=2, x=0.0, y=-26.5, restraints=(False, True, False)),  # đáy fix u_y
    Node(id=3, x=10.0, y=1.5, restraints=(True, True, True)),     # neo bond điểm cố định
]

elements = [
    BeamElement(id=0, node_i=0, node_j=1, EA=13_609_696.0, EI=930_822.0),
    BeamElement(id=1, node_i=1, node_j=2, EA=13_609_696.0, EI=930_822.0),
    TrussElement(id=2, node_i=1, node_j=3, EA=200_000.0, prestress_kN=300.0),
]

loads = [
    NodalLoad(node_id=0, Fx=15.0, M=0.0),
    ElemDistLoad(elem_id=0, w1=10.0, w2=30.0, direction="local_y"),
]

model = FrameModel(nodes=nodes, elements=elements, loads=loads)
result = model.solve(include_P_delta=True, max_iter=10, tol=1e-6)

print(result.elem_forces[1])  # {N_kN, V_i_kN, V_j_kN, M_i_kNm, M_j_kNm}
print(result.node_disp[0])    # {ux_mm, uy_mm, rz_rad}
```

### 5.2 High-level (builder cho tường cừ điển hình)

```python
from fem2d.frame2d import FrameBuilder
from wall_internal_force import SoilLayer, build_lateral_load

fb = FrameBuilder(name="Tường cừ KE-HK10, 2 tầng neo", bh_name="KE-HK10")

# Cọc SW (1 hoặc nhiều đoạn dọc theo cao độ)
fb.add_sheet_pile_sw(pile_name="SW-840", top_elev=2.5, bot_elev=-26.5,
                     n_segments=60, fc_MPa=70.0)

# Neo
fb.add_ground_anchor(
    head_elev=1.5, length_free=8.0, length_bond=6.0, inclination_deg=20.0,
    cable_EA=200_000.0, prestress_kN=300.0,
)
fb.add_ground_anchor(
    head_elev=-2.5, length_free=10.0, length_bond=7.0, inclination_deg=25.0,
    cable_EA=250_000.0, prestress_kN=400.0,
)

# Winkler springs từ profile đất (tự động query SQLite hoặc nhận list)
layers = [SoilLayer("1b", thickness_m=8.0, Su_kPa=15.0, gamma_kNm3=15.0), ...]
fb.add_winkler_from_layers(layers, soil_top_elev=-2.0,
                            eps50=0.01, k_sand_kNm3=10_000.0)

# Tải phân bố từ áp lực đất (dùng lại engine wall_internal_force)
fb.add_lateral_load_from_earth_pressure(
    geom_top=2.5, soil_level_front=2.0, soil_level_back=-2.0,
    front_layers=[...], back_layers=[...],
    water_elev_front=-1.0, water_elev_back=-3.0,
    surcharge_front=20.0,
)

# Build + solve
model = fb.build()
result = model.solve(include_P_delta=True)

# Plot + save
fb.plot_results(result, mode="combined")  # M, V, N, deformed shape
fb.save_to_db(result, model_id_or_name="ke_hk10_2anchor_v1")
```

### 5.3 Staged construction

```python
phases = [
    {"name": "p0_initial",       "active_elements": [0, 1],  "loads": ["earth_initial"]},
    {"name": "p1_excavate_1m",   "active_elements": [0, 1],  "loads": ["earth_after_dig_1"]},
    {"name": "p2_install_anc1",  "active_elements": [0, 1, 2], "loads": ["earth_after_dig_1", "anc1_prestress"]},
    {"name": "p3_excavate_3m",   "active_elements": [0, 1, 2], "loads": ["earth_after_dig_3"]},
    {"name": "p4_install_anc2",  "active_elements": [0, 1, 2, 3], "loads": ["earth_after_dig_3", "anc2_prestress"]},
    {"name": "p5_final_dig",     "active_elements": [0, 1, 2, 3], "loads": ["earth_final"]},
]

results = model.solve_staged(phases)
# results: list[FrameResult] — 1 kết quả mỗi pha
```

---

## 6. SQLite schema mới (5 bảng `fem2d_frame_*` trong `TTHC.sqlite`)

```sql
CREATE TABLE IF NOT EXISTS fem2d_frame_models (
    model_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    bh_name TEXT,                    -- FK boreholes(db_name)
    pile_name TEXT,                  -- FK sw_pile_catalog
    description TEXT,
    n_phases INTEGER DEFAULT 1,
    include_P_delta INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fem2d_frame_nodes (
    model_id INTEGER, node_id INTEGER,
    x_m REAL, y_m REAL,
    restraint_ux INTEGER, restraint_uy INTEGER, restraint_rz INTEGER,
    spring_kh_kNm_per_m REAL DEFAULT 0,
    spring_kv_kNm_per_m REAL DEFAULT 0,
    spring_kr_kNm_per_rad REAL DEFAULT 0,
    PRIMARY KEY (model_id, node_id),
    FOREIGN KEY (model_id) REFERENCES fem2d_frame_models(model_id)
);

CREATE TABLE IF NOT EXISTS fem2d_frame_elements (
    model_id INTEGER, elem_id INTEGER,
    node_i INTEGER, node_j INTEGER,
    elem_type TEXT,                  -- 'beam' | 'truss'
    role TEXT,                       -- 'pile' | 'wale' | 'anchor' | 'strut' | 'tie'
    EA_kN REAL, EI_kNm2 REAL,
    release_i_rz INTEGER DEFAULT 0,
    release_j_rz INTEGER DEFAULT 0,
    prestress_kN REAL DEFAULT 0,
    PRIMARY KEY (model_id, elem_id)
);

CREATE TABLE IF NOT EXISTS fem2d_frame_loads (
    model_id INTEGER, load_id INTEGER, phase_id INTEGER DEFAULT 0,
    load_type TEXT,                  -- 'nodal' | 'elem_dist' | 'elem_axial' | 'prestress'
    target_id INTEGER,
    fx_kN REAL DEFAULT 0, fy_kN REAL DEFAULT 0, m_kNm REAL DEFAULT 0,
    w1_kN_per_m REAL DEFAULT 0, w2_kN_per_m REAL DEFAULT 0,
    direction TEXT DEFAULT 'global_x',
    PRIMARY KEY (model_id, load_id, phase_id)
);

CREATE TABLE IF NOT EXISTS fem2d_frame_results_nodes (
    model_id INTEGER, run_id INTEGER, phase_id INTEGER DEFAULT 0, node_id INTEGER,
    ux_mm REAL, uy_mm REAL, rz_rad REAL,
    rx_kN REAL, ry_kN REAL, mz_kNm REAL,
    PRIMARY KEY (model_id, run_id, phase_id, node_id)
);

CREATE TABLE IF NOT EXISTS fem2d_frame_results_elements (
    model_id INTEGER, run_id INTEGER, phase_id INTEGER DEFAULT 0, elem_id INTEGER,
    N_kN REAL, V_i_kN REAL, V_j_kN REAL,
    M_i_kNm REAL, M_j_kNm REAL,
    max_M_kNm REAL, max_V_kN REAL,
    PRIMARY KEY (model_id, run_id, phase_id, elem_id)
);
```

---

## 7. Test cases verify

### Test 1: Dầm cantilever (basic beam)
- EI=1000 kN·m², L=5m, P=10 kN ở đầu tự do
- Analytical: δ_tip = PL³/(3·EI) = 10·125/3000 = **417 mm**
- Tolerance: <0.1%

### Test 2: Dầm 2 đầu khớp + tải phân bố đều
- EI=1000, L=10m, w=5 kN/m
- Analytical: M_max = wL²/8 = **62.5 kN·m** (giữa nhịp)
- δ_max = 5wL⁴/(384·EI) = **65.1 mm**
- Tolerance: <0.1%

### Test 3: Khung portal (frame) đơn giản
- 2 cột cao 4m + 1 dầm 6m, EI cột = EI dầm = 5000 kN·m²
- Tải ngang 20 kN ở đỉnh cột phải
- So với Mastan2/SAP2000 export (tôi tính bằng tay nếu cần)

### Test 4: Cọc + 1 tầng neo + tải phân bố
- Cọc SW-840, L=30m, đỉnh tự do
- Neo ngang tại đỉnh, EA=200_000, prestress=200 kN
- Tải phân bố Active 0→50 kPa
- So với `winkler_np.solve_numpy_dist` khi gỡ neo (set EA=0) → giá trị phải khớp

### Test 5: P-Delta — cột Euler buckling
- Cột thẳng đứng L=10m, EI=10_000, đáy ngàm, đỉnh tự do
- Áp lực P tăng dần đến P_cr_Euler = π²EI/(4L²) = 246.7 kN
- Eigenvalue của (K - λKg) = 0 → λ_min = 1.0 khi P = P_cr
- Tolerance: <2%

### Test 6: Verify với Plaxis (manual)
- Tường cừ KE-HK10 + 2 tầng neo + đào 4m + nước
- Chạy Plaxis 2D với Plate + Anchor + tải Active
- So sánh: M_max, V_max, displacement đỉnh, N_anchor
- Tolerance: <10% (vì Plaxis có plasticity, frame chỉ elastic)

### Test 7: So với SAP2000 / Robot (optional, nếu user có license)

---

## 8. UI Streamlit app_fem2d.py (port 8504)

### Layout sidebar

```
[Project Setup]
  - Tên model
  - Liên kết borehole (selectbox từ SQLite)
  - Liên kết SW pile (selectbox từ catalog)

[Geometry]
  - Top elev (m)
  - Bot elev (m)
  - n_segments

[Anchors]
  - Nút "+ Thêm neo" → form (head_elev, length, angle, EA, prestress)

[Loads]
  - Earth pressure (gọi build_lateral_load)
  - Surcharge (kPa)
  - Nodal loads (tùy chọn)

[Solver options]
  - ☐ P-Delta
  - ☐ Staged construction
  - max_iter, tol

[Actions]
  - Build model
  - Solve
  - Save to DB
  - Load from DB
```

### Main area

```
Tab 1: Geometry preview (Plotly schematic)
Tab 2: Mesh + DOF visualization
Tab 3: Results — diagrams M/V/N + deformed shape
Tab 4: Numerical results (DataFrames)
Tab 5: Export — JSON / CSV / PDF report
Tab 6: Compare với Winkler 1D (sanity check)
```

---

## 9. Roadmap chi tiết (8 step, ~10-15 giờ làm việc)

| Step | Nội dung | Thời gian | Output |
|------|----------|-----------|--------|
| S1 | Scaffold package `fem2d/frame2d/` + dataclasses + `__init__.py` | 30' | Import test pass |
| S2 | `element_beam.py` Ke 6×6 + consistent load + transformation matrix | 1.5h | Test 1+2 pass |
| S3 | `element_truss.py` Ke 4×4 + axial-only | 30' | Test verify analytical |
| S4 | `releases.py` + `assembler.py` lắp ráp K toàn cục | 2h | Test 3 (portal) pass |
| S5 | `solver.py` solve_static + Winkler springs | 1h | Test 4 (cọc+neo) pass với tolerance |
| S6 | P-Delta iterative (geometric stiffness Kg) | 1.5h | Test 5 (Euler) pass |
| S7 | `builder.py` FrameBuilder high-level API | 1.5h | Builder test với tường cừ KE-HK10 |
| S8 | `postprocess.py` + `db.py` + `verify.py` | 2h | Plot OK, DB save/load OK, 5 tests pass |
| S9 | `app_fem2d.py` Streamlit UI + `start_fem2d.bat` | 2-3h | Local app port 8504 chạy được |
| S10 | Update `cdm-deploy/.gitignore` + CLAUDE.md | 30' | Bảo vệ Cloud + document |

**Tổng:** ~12-15h coding, có thể chia làm 3-4 session.

---

## 10. Câu hỏi cần user xác nhận trước khi code

1. **SQLite location**: dùng chung `TTHC.sqlite` (đề xuất) hay tạo riêng `fem2d.sqlite`?
2. **Port app_fem2d.py**: 8504 OK hay đổi sang port khác? (8503 đang dùng cho app_cdm.py)
3. **Convention dấu**: M dương khi sợi căng ở Front (trái) — theo CLAUDE.md mục 20. OK?
4. **Beam theory**: Euler-Bernoulli (đề xuất) hay Timoshenko (cần thêm GA)? Cọc SW H<1m, L>20m → slender, Euler đủ.
5. **Solver linear**: `scipy.sparse.linalg.spsolve` (đề xuất) hay `numpy.linalg.solve` (dense, đủ cho frame nhỏ)?
6. **Verify với Plaxis**: bạn có muốn tôi viết script export geometry .geo cho Plaxis để bạn import + so sánh?
7. **Có cần module export sang DXF** cho việc kiểm tra với CAD không?

---

**Trạng thái:** Plan đã đầy đủ. Chờ user duyệt → tôi bắt đầu S1.
