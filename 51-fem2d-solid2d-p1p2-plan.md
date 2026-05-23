# P1 + P2 — Plane Strain Solid 2D + Mohr-Coulomb: Plan chi tiết

> **Mục tiêu:** Triển khai mesh + solver plane strain 2D giống Plaxis với:
> - Mesh tam giác từ nhiều hố khoan dọc tuyến (cross-section 2D)
> - Material Linear Elastic + Mohr-Coulomb plasticity
> - Visualize mesh + stress/displacement contour + plastic zones
>
> **Mode:** LOCAL ONLY — không deploy Cloud (cùng giới hạn với P4)
>
> **Trạng thái:** Plan đang viết. Chưa code.
> **Ước lượng:** ~30 giờ coding (chia 5-7 session 4-6h)

---

## 1. Scope

### ✅ Sẽ làm

| # | Tính năng | Phase |
|---|----------|-------|
| 1 | Mesh tam giác từ N hố khoan dọc tuyến (interpolate lớp đất) | P1.1 |
| 2 | Material gán theo polygon (mỗi lớp 1 region) | P1.1 |
| 3 | Mesh quadratic (6-noded triangle) — tương đương Plaxis 6-node | P1.1 |
| 4 | Plane strain Linear Elastic solver | P1.2 |
| 5 | Visualize mesh + region colors (giống Plaxis Input) | P1.3 |
| 6 | Stress/displacement contour (giống Plaxis Output) | P1.3 |
| 7 | Deformed shape | P1.3 |
| 8 | Integrate vào app_fem2d.py (tab "Solid 2D") | P1.4 |
| 9 | Mohr-Coulomb return mapping algorithm | P2.1 |
| 10 | Newton-Raphson iterative solver + consistent tangent | P2.2 |
| 11 | Plastic zones visualization | P2.4 |
| 12 | Verify với Boussinesq + Meyerhof bearing capacity | P1.4, P2.3 |

### ❌ Không làm trong P1+P2

| Tính năng | Lý do |
|-----------|-------|
| Hardening Soil (HS), Cam Clay, Soft Soil | Quá phức tạp, để sau (P10+) |
| Mesh tự refine adaptive | Out of scope, dùng manual size |
| Anisotropy | Out of scope |
| Excavation/Staged construction trong solid 2D | P3+ (SRF) hoặc P5+ (Biot) |
| 3D | Out of scope |
| Dynamic (động đất) | Out of scope |

---

## 2. Cấu trúc thư mục mới

```
scripts/fem2d/solid2d/
    __init__.py
    mesh.py                           # P1.1 — mesh từ cross-section
    materials.py                      # P1.2 — MaterialLE, MaterialMC dataclasses
    elasticity.py                     # P1.2 — D matrix plane strain
    bc.py                             # P1.2 — Dirichlet/Neumann BC helpers
    solver_static.py                  # P1.2 — assemble K + solve LE
    postprocess.py                    # P1.3 — plot mesh + contour
    constitutive.py                   # P2.1 — MC return mapping
    solver_nonlinear.py               # P2.2 — Newton-Raphson + consistent tangent
    verify.py                         # P1.4 + P2.3 — test cases
    plaxis_compat.py                  # P2+ — convention/sign mapping
```

Mới ngoài fem2d/:
```
G:\My Drive\AI-SUC TAI COC THEO DAT NEN\
    51-fem2d-solid2d-p1p2-plan.md     # File này
    data/
        cross_section_definitions.json # Định nghĩa cross-section đã build
```

---

## 3. Dependencies — Thư viện cần cài

```powershell
& "C:\Users\bayng\AppData\Local\Programs\Python\Python312\python.exe" -m pip install `
    "gmsh>=4.13" `
    "pygmsh>=7.1" `
    "meshio>=5.3" `
    "scikit-fem>=8.0" `
    "pyvista>=0.44"
```

**Tất cả CHỈ cài local**, KHÔNG copy vào `cdm-deploy/requirements.txt`.

| Package | Mục đích | Đã có chưa? |
|---|---|---|
| `gmsh` | Mesh generator binary | Cần cài |
| `pygmsh` | Python wrapper gmsh | Cần cài |
| `meshio` | Đọc/ghi mesh formats | Cần cài |
| `scikit-fem` | FEM solver pure NumPy | Cần cài |
| `pyvista` | 3D mesh viewer | Cần cài (optional) |
| `matplotlib` | 2D plot + tricontourf | ✓ |
| `numpy`, `scipy`, `shapely`, `pandas` | Đã có | ✓ |

---

## 4. P1.1 — Mesh 2D cross-section từ nhiều HK

### Input
- Zone code: `'KE'` | `'BXN'` | `'NHC'`
- Danh sách HK trên tuyến (hoặc auto-pick từ SQLite)
- Khoảng cách giữa các HK (m, từ tọa độ X,Y trong `boreholes` table)
- Cao độ mặt đất + đáy mesh (m)
- Target mesh size (m, default 0.5m)

### Pipeline

```
1. Query SQLite:
   SELECT bh.db_name, bh.x_coord_m, bh.y_coord_m, bh.elevation_m,
          l.depth_top_m, l.depth_bot_m, l.symbol_tcvn
   FROM boreholes bh
   JOIN layers l ON l.bh_name = bh.db_name
   WHERE bh.zone = ? ORDER BY along-track distance

2. Compute along-track distance (project HK xuống trục thẳng đứng nhất)
   → list (s_i, top_elev_i, [(d_top, d_bot, symbol), ...])  cho mỗi HK

3. Build "fence diagram": với mỗi cặp HK kế tiếp, tạo polygons cho từng lớp
   - Mỗi lớp = polygon (s_i, top_layer_i) → (s_{i+1}, top_layer_{i+1})
                  → (s_{i+1}, bot_layer_{i+1}) → (s_i, bot_layer_i)
   - Lớp khác symbol giữa 2 HK → tạo polygon transitional

4. pygmsh:
   geom = pygmsh.geo.Geometry()
   for layer_poly in polygons:
       geom.add_polygon(layer_poly.coords, mesh_size=target_h)
       geom.set_physical_group(layer_poly, name=symbol)
   mesh = geom.generate_mesh(order=2)  # 6-noded triangles

5. Output:
   - skfem.MeshTri (linear) hoặc MeshTri2 (quadratic)
   - subdomains: dict {symbol: list of element indices}
   - boundary_facets: dict {'top': [...], 'bottom': [...], 'left': [...], 'right': [...]}
```

### API public

```python
from fem2d.solid2d import build_cross_section_mesh, CrossSectionDef

cs = CrossSectionDef(
    name="KE-section1",
    zone="KE",
    bh_names=["KE-HK1", "KE-HK4", "KE-HK7", "KE-HK10"],
    auto_distances=True,           # tự tính từ tọa độ HK
    bottom_elev=-40.0,             # mesh đến độ sâu -40m
    target_mesh_size=0.5,          # 0.5m elements
    refine_zones=[                 # vùng cần mesh mịn hơn
        {"bbox": (50, -5, 60, -25), "size": 0.2},  # quanh tường cừ KE-HK7
    ],
)

mesh, subdomains = build_cross_section_mesh(cs, db_path="data/TTHC.sqlite")

# mesh.p: shape (2, n_nodes) — tọa độ nodes
# mesh.t: shape (3, n_elems) — connectivity (linear) hoặc (6, n_elems) cho quadratic
# subdomains: {'CL': np.ndarray, 'SC': ..., 'SP': ...}
```

### Files

| File | Lines (ước) | Mục đích |
|---|---|---|
| `solid2d/mesh.py` | ~400 | `build_cross_section_mesh()`, `CrossSectionDef`, helpers |
| `solid2d/__init__.py` | ~50 | Export |

**Thời gian: 6-8h**

---

## 5. P1.2 — Plane Strain Linear Elastic Solver

### Material model

```python
@dataclass
class MaterialLE:
    name: str          # symbol đất (vd "CL", "SC")
    E_kPa: float       # Young modulus
    nu: float          # Poisson ratio
    gamma_kNm3: float  # unit weight (cho self-weight load)
```

### Plane strain D matrix (3×3 cho stress = [σ_xx, σ_yy, τ_xy]):

```
D = E / ((1+ν)(1-2ν)) · [[1-ν, ν,   0    ],
                          [ν,   1-ν, 0    ],
                          [0,   0,   (1-2ν)/2]]
```

### Solver workflow

```python
from skfem import MeshTri, Basis, ElementTriP2, asm, condense, solve
from skfem.models.elasticity import linear_elasticity, linear_stress

basis = Basis(mesh, ElementTriP2())
K = asm(linear_elasticity(λ, μ), basis)   # với mỗi material subdomain riêng
F = asm(self_weight_load, basis)
# Apply BC: bottom fixed, sides roller
K_cond, F_cond, x_cond, _ = condense(K, F, D=dirichlet_dofs)
u = solve(K_cond, F_cond)
# Compute stress at gauss points
sigma = compute_stress_at_quadrature(u, basis, D_matrix_per_region)
```

### Files

| File | Lines | Mục đích |
|---|---|---|
| `solid2d/materials.py` | ~100 | MaterialLE, MaterialMC dataclass |
| `solid2d/elasticity.py` | ~150 | D matrix + asm wrappers |
| `solid2d/bc.py` | ~100 | Dirichlet/Neumann helpers |
| `solid2d/solver_static.py` | ~200 | solve_plane_strain_LE() main |

**Thời gian: 4-6h**

---

## 6. P1.3 — Visualization

### Plot 1: Mesh + region colors (giống Plaxis Input)

```python
def plot_mesh_regions(mesh, subdomains, materials):
    fig, ax = plt.subplots(figsize=(10, 7))
    for symbol, elems in subdomains.items():
        coords = mesh.p[:, mesh.t[:, elems]]
        color = MATERIAL_COLOR_MAP[symbol]
        ax.fill(coords[0], coords[1], color=color, alpha=0.5, label=symbol)
    # Vẽ outline mesh edges
    ax.triplot(mesh.p[0], mesh.p[1], mesh.t.T, color='k', lw=0.3)
```

### Plot 2: Stress contour (giống Plaxis Output)

```python
def plot_stress_contour(mesh, sigma, component='sigma_yy'):
    triang = matplotlib.tri.Triangulation(mesh.p[0], mesh.p[1], mesh.t.T)
    levels = np.linspace(sigma.min(), sigma.max(), 20)
    ax.tricontourf(triang, sigma, levels=levels, cmap='RdBu_r')
    ax.tricontour(triang, sigma, levels=levels, colors='k', linewidths=0.3)
    cbar.set_label(f'{component} (kPa)')
```

### Plot 3: Deformed mesh

```python
def plot_deformed(mesh, u, scale=100):
    p_def = mesh.p + scale * u.reshape(2, -1)
    ax.triplot(p_def[0], p_def[1], mesh.t.T, color='red', lw=0.5)
```

### Plot 4 (P2+): Plastic zones

```python
def plot_plastic_zones(mesh, plastic_indicator):
    # plastic_indicator: 0/1 per element
    plastic_elems = mesh.t[:, plastic_indicator > 0]
    ax.fill(...)  # red overlay for plastic elements
```

### Files

| File | Lines | Mục đích |
|---|---|---|
| `solid2d/postprocess.py` | ~300 | 4 plot functions + colormap |

**Thời gian: 3-4h**

---

## 7. P1.4 — App integration + Verify

### App `app_fem2d.py` extension

Thêm 2 mục mới vào layout phẳng (sau mục F Verify):

```markdown
## G. Solid 2D Mesh (Cross-section)
- Chọn zone (KE/BXN/NHC)
- Multi-select HK trên tuyến
- Slider mesh size + bottom elev
- Auto build mesh on input change → hiển thị mesh + colors regions

## H. Solid 2D Solve (Linear Elastic / MC)
- Toggle LE / MC
- Input material per region (auto từ JSON soil_presets, override được)
- Input tải đắp ở mặt đất + tải xe
- Auto solve → contour σ_yy, σ_xx, τ_xy, u, deformed
- Plastic zones (nếu MC)
```

### Verify cases P1

| # | Test | Analytical | Tolerance |
|---|------|-----------|-----------|
| 1 | Boussinesq tải tập trung P trên bán không gian đàn hồi | σ_z(z) = 3P/(2π·z²) | < 5% (mesh refinement dependent) |
| 2 | Tải đều q trên rãnh chữ nhật B×∞ | settlement = q·B(1-ν²)/E · I_p | < 3% |
| 3 | Block đào sâu vs Plaxis LE | Compare u_top, σ_at_base | < 10% (linear) |

### Files

| File | Lines | Mục đích |
|---|---|---|
| `solid2d/verify.py` | ~300 | 3 test cases analytical |
| `app_fem2d.py` (extend) | +400 | 2 mục G + H |

**Thời gian: 4-5h**

---

## 8. P2.1 — Mohr-Coulomb Return Mapping

### Yield function

```
F(σ) = (σ_1 - σ_3) - (σ_1 + σ_3)·sin(φ) - 2c·cos(φ) ≤ 0
```

### Return mapping algorithm (Souza Neto 2008, Ch. 8)

```python
def mc_return_mapping(sigma_trial, material):
    """
    Input: σ_trial (3-vector for plane strain), MaterialMC
    Output: σ_corrected, dλ, plastic_indicator, D_consistent (3x3)
    
    Steps:
    1. Compute principal stresses σ_1 > σ_2 > σ_3
    2. Check F(σ_trial) — nếu < 0: elastic, return σ_trial
    3. Try regular regime: σ_corrected on yield surface (line, not apex)
       - Solve for dλ: F(σ_trial - dλ·n) = 0
    4. Check valid (σ_1 > σ_2 > σ_3 after correction)
    5. If not valid: try apex/edge regimes
    6. Compute consistent tangent D_alg
    7. Return rotated back to (xx, yy, xy) coords
    """
```

### Files

| File | Lines | Mục đích |
|---|---|---|
| `solid2d/constitutive.py` | ~500 | MC return mapping + 4 stress regimes |
| `solid2d/principal_stress.py` | ~100 | Eigen decomposition 2x2 + sorting |

**Thời gian: 8-10h** (plasticity rất phức tạp)

---

## 9. P2.2 — Newton-Raphson nonlinear solver

### Loop

```python
def solve_mc_nonlinear(mesh, materials, bcs, loads, max_iter=20, tol=1e-4):
    u = np.zeros(n_dofs)
    sigma_history = np.zeros((3, n_gp))
    
    for step in load_steps:
        F_ext = compute_external_force(loads, step)
        for iter in range(max_iter):
            # Compute internal force + tangent
            F_int, K_tangent = assemble_internal(mesh, u, sigma_history, materials)
            R = F_ext - F_int
            if ||R|| < tol: break
            du = solve(K_tangent, R, bcs)
            u += du
            # Update stress at quadrature points
            sigma_history = update_stress(mesh, u, materials)
    
    return u, sigma_history, plastic_indicator
```

### Convergence criteria

- `||R||_2 / ||F_ext||_2 < 1e-4` (relative)
- Or absolute tolerance `||R||_∞ < 1e-3` kN

### Files

| File | Lines | Mục đích |
|---|---|---|
| `solid2d/solver_nonlinear.py` | ~400 | Newton-Raphson loop, load stepping, line search |

**Thời gian: 5-6h**

---

## 10. P2.3 — Verify Meyerhof bearing capacity

### Setup
- Mặt đất rộng, footing đặt tại trung tâm
- Móng vuông (plane strain → móng dải) B=1m, D=1m
- Đất sét φ=0°, c=20 kPa, γ=18 kN/m³

### Analytical (Meyerhof)
```
q_u = c·N_c + γ·D·N_q + 0.5·γ·B·N_γ
với φ=0°: N_c=5.14, N_q=1, N_γ=0
q_u = 20·5.14 + 18·1·1 + 0 = 120.8 kPa
```

### FEM2D solve
- Tăng tải q ở bề mặt từ 0 → tới khi diverge
- Find q_u khi NR không converge sau max_iter
- Tolerance: < 5% so với Meyerhof

**Thời gian: 2-3h**

---

## 11. P2.4 — Tích hợp MC vào app

- Toggle "LE" / "MC" trong mục H
- Plot plastic zones (overlay đỏ)
- Plot stress paths tại điểm chọn (q-p diagram)
- Cảnh báo khi NR không converge (failure)

**Thời gian: 2-3h**

---

## 12. Tổng thời gian

| Phase | Mục | Thời gian |
|-------|-----|-----------|
| **P1** | Mesh + LE + Visualize + App | **17-23h** |
| - P1.1 | Mesh cross-section | 6-8h |
| - P1.2 | LE solver | 4-6h |
| - P1.3 | Visualization | 3-4h |
| - P1.4 | App integration + verify | 4-5h |
| **P2** | MC plasticity | **17-22h** |
| - P2.1 | MC return mapping | 8-10h |
| - P2.2 | Newton-Raphson | 5-6h |
| - P2.3 | Verify Meyerhof | 2-3h |
| - P2.4 | App MC tab | 2-3h |
| **Tổng** | | **34-45h** (~5-7 sessions 6-8h) |

---

## 13. Verify với Plaxis (manual)

Sau khi P1+P2 done, build 3 case song song trong Plaxis 2D và FEM2D:

| Case | Plaxis material | FEM2D | Compare |
|------|----------------|-------|---------|
| Bài toán Boussinesq | LE | LE | σ_z(z) |
| Móng vuông trên sét φ=0° | MC | MC | q_u (bearing) |
| Đào hố hẹp 5m sâu vs đất sét NC | MC | MC | u_top, σ tại đáy hố |

Tolerance < 10% (Plaxis 15-noded vs scikit-fem 6-noded).

---

## 14. Bảo vệ Cloud (cùng nguyên tắc P4)

1. `update_app.bat` whitelist — không copy `scripts/fem2d/solid2d/`
2. `cdm-deploy/.gitignore` đã có rule `scripts/fem2d/` → tự exclude
3. `app_fem2d.py` có try/except cho `from fem2d.solid2d import ...` → graceful fail trên Cloud
4. Bảng SQLite mới (nếu có): `fem2d_solid_*` (prefix theo CLAUDE.md §11)

---

## 15. Câu hỏi trước khi code

1. **Hố khoan dọc tuyến**: Lấy theo `zone='KE'` toàn bộ HK? Hay user chọn list cụ thể?
2. **Bottom elev mesh**: User input (vd -40m) hay auto = depth_bot_m max của HK + 5m?
3. **Mesh quadratic (6-node) hay linear (3-node)**: Quadratic chính xác hơn nhưng chậm gấp 2. Default = quadratic.
4. **Self-weight load (gamma): Tính từ JSON `soil_presets.json` hay user input thủ công?
5. **App layout**: Mục G+H thêm phía sau mục F? Hay làm app riêng `app_fem2d_solid.py` port 8505?

---

**Trạng thái:** Plan đầy đủ. Chờ user cài thư viện + duyệt scope → tôi bắt đầu P1.1.
