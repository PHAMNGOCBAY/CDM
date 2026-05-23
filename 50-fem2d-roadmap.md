# FEM2D Roadmap — Các Bước Chưa Thực Hiện

**Cập nhật 2026-05-21.** Tách ra từ CLAUDE.md §13c để giảm tải context.

**Phase P4 (Frame 2D) đã DONE.** Roadmap các phase còn lại:

## Mức ưu tiên ngay (test + tích hợp P4 vào workflow thực tế)

| Step | Mục đích | File / Action | Thời gian | Trạng thái |
| --- | --- | --- | --- | --- |
| V1 | Test verify suite trên Python 3.12 local | `python -m fem2d.frame2d.verify` | 5' | ⏸ Chờ user |
| V2 | Test `start_fem2d.bat` mở port 8504 | Double-click bat, mở http://localhost:8504 | 5' | ⏸ Chờ user |
| V3 | Verify Test 6 với Plaxis 2D — tường cừ KE-HK10 + 2 neo + đào | Build Plaxis model song song, so M_max/V_max/N_anchor; tolerance < 10% (linear vs MC) | 2h | ⏸ |
| V4 | Tích hợp FEM2D vào app_cdm.py như tab phụ "Frame 2D nâng cao" | Thêm page id `"fem2d"` trong sidebar (lazy import + try/except để Cloud không crash) | 2h | ⏸ |
| V5 | Lookup `sw_pile_catalog.json` trong FrameBuilder | Thêm hàm `add_sheet_pile_sw_by_name("SW-840", fc_MPa=70, ...)` tự lookup EA/EI từ JSON | 1h | ⏸ |
| V6 | Thêm `add_lateral_load_from_earth_pressure()` builder | Gọi `wall_internal_force.build_lateral_load()` tự động + áp lên beams | 2h | ⏸ |
| V7 | So sánh FEM2D Winkler với `winkler_np.solve_numpy_dist` (regression test) | Cùng case → kết quả M/u khác < 1% | 1h | ⏸ |

## Phase P1 — Plane Strain Linear Elastic (NỀN tảng cho P2/P3/P5)

| Mục | Chi tiết |
| --- | --- |
| **Mục tiêu** | Solver plane strain 2D đàn hồi, mesh tam giác/tứ giác, verify Boussinesq |
| **Dependencies** | `scikit-fem>=8.0`, `meshio>=5.3`, `pygmsh>=7.1`, `gmsh>=4.13` (binary wheel pip) |
| **Files mới** | `scripts/fem2d/solid2d/__init__.py`, `mesh.py`, `materials.py`, `elasticity.py`, `solver_static.py`, `bc.py`, `postprocess.py`, `verify.py` |
| **API public** | `Mesh, MaterialLE, solve_plane_strain(mesh, materials, bcs, loads)` |
| **Verify** | (1) Boussinesq tải tập trung trên bán không gian: σ_z(z) = 3P/(2π z²); (2) Tải đều trên rãnh: settlement = q·B·(1-ν²)/E·I_p; (3) Block đào sâu vs Plaxis |
| **Thời gian** | 8-12h coding |
| **Trạng thái** | ⏸ Chưa bắt đầu — cần user `pip install scikit-fem meshio pygmsh gmsh` |

## Phase P2 — Mohr-Coulomb Plasticity (sau P1)

| Mục | Chi tiết |
| --- | --- |
| **Mục tiêu** | Thêm plasticity Mohr-Coulomb cho solid 2D với Newton-Raphson + consistent tangent |
| **Dependencies** | Đã có từ P1 |
| **Files mới** | `scripts/fem2d/solid2d/constitutive.py` (MC return mapping), `solver_nonlinear.py` (Newton-Raphson), `verify_bearing.py` |
| **Lý thuyết** | Return mapping algorithm theo Souza Neto, Peric, Owen (2008). 2 cases: apex (c·cot(φ)) và regular (line on Mohr-Coulomb yield surface) |
| **Verify** | (1) Bearing capacity Meyerhof: q_u = c·N_c + γ·D·N_q + 0.5·γ·B·N_γ — sai số < 5%; (2) Block đào không chống vs Plaxis MC |
| **Thời gian** | 12-16h coding (plasticity phức tạp) |
| **Trạng thái** | ⏸ Chờ P1 done |

## Phase P3 — Strength Reduction Factor (mái dốc, sau P2)

| Mục | Chi tiết |
| --- | --- |
| **Mục tiêu** | Tự động tính FoS mái dốc bằng φ/c reduction (giống Plaxis Safety phase) |
| **Dependencies** | P1 + P2 |
| **Files mới** | `scripts/fem2d/solid2d/srf.py`, `slip_surface.py` |
| **Lý thuyết** | Loop k = 1, 1.05, 1.1, ...: c_red = c/k, tan(φ_red) = tan(φ)/k. Khi solver không converge → đó là FoS. Slip surface từ deviatoric strain max |
| **Verify** | So với Bishop slip surface trong `sw_global_stability.py`: sai số FoS < 10% |
| **Thời gian** | 4-6h |
| **Trạng thái** | ⏸ Chờ P2 done |

## Phase P5 — Cố kết Biot 2D Coupled u-p (sau P1)

| Mục | Chi tiết |
| --- | --- |
| **Mục tiêu** | Cố kết 2D với coupled displacement-pore pressure (u, p) — giống Plaxis Consolidation phase |
| **Dependencies** | P1 (mesh + elasticity) |
| **Files mới** | `scripts/fem2d/solid2d/biot.py`, `time_stepping.py`, `bc_drainage.py` |
| **Lý thuyết** | Phương trình Biot 1941: K_uu·u + K_up·p = F; K_pu·u_dot + (S + Δt·K_pp)·p = F_q. Time stepping Crank-Nicolson |
| **Verify** | (1) Terzaghi 1D analytical: U(t) = 1 - 8/π² · Σ exp(-M²·T_v) — sai số < 5%; (2) Block 2D consolidation vs Plaxis |
| **Thời gian** | 10-14h coding |
| **Trạng thái** | ⏸ Chờ P1 done (độc lập với P2/P3) |

## Phase P6 — Tích hợp PLAXIS API (optional, sau tất cả)

| Mục | Chi tiết |
| --- | --- |
| **Mục tiêu** | Export FEM2D model sang .geo/.json cho Plaxis 2D import, ngược lại import kết quả Plaxis về so sánh |
| **Files mới** | `scripts/fem2d/io_plaxis.py`, `scripts/fem2d/io_dxf.py` |
| **Verify** | Round-trip FEM2D ↔ Plaxis ↔ FEM2D không mất thông tin |
| **Thời gian** | 6-8h |
| **Trạng thái** | ⏸ Optional — user chưa yêu cầu |

## Phase P7 — Plate Bending Element (optional, cho bài toán nền 3D đơn giản)

| Mục | Chi tiết |
| --- | --- |
| **Mục tiêu** | Mindlin/Kirchhoff plate bending — cho phân tích móng bè, sàn cứng |
| **Trạng thái** | ⏸ Out of scope hiện tại |

---

## Lệnh cài thư viện cho P1 (khi sẵn sàng triển khai)

```powershell
& "C:\Users\bayng\AppData\Local\Programs\Python\Python312\python.exe" -m pip install `
    "scikit-fem>=8.0" `
    "meshio>=5.3" `
    "pygmsh>=7.1" `
    "gmsh>=4.13"
```

**Lưu ý:** Tất cả 4 package này **CHỈ cài local**, KHÔNG thêm vào `cdm-deploy/requirements.txt`. CLAUDE.md mục 14 đã ghi rõ scikit-fem/pygmsh/gmsh là local-only.

## Workflow dependency

```
V1, V2: Test ngay              → có thể làm độc lập, < 10 phút
V3:     Verify Plaxis P4       → cần build Plaxis model thủ công, 2h
V4-V7:  Tích hợp P4 vào app    → 6h tổng

P1:     Plane strain LE        → cài scikit-fem + pygmsh trước
  ├── P2: Mohr-Coulomb         → cần P1
  │     └── P3: SRF mái dốc    → cần P2
  └── P5: Biot 2D              → cần P1, độc lập P2/P3

P6:     Plaxis I/O             → optional, làm khi cần
P7:     Plate bending          → optional, out-of-scope
```

## Decision tree — nên làm gì tiếp?

- **Nếu cần dùng FEM2D ngay cho dự án thực**: làm V1 → V3 → V4 → V5/V6 (P4 đủ cho tường cừ + neo)
- **Nếu muốn vượt khả năng Plaxis (custom plasticity/SRF)**: làm P1 → P2 → P3
- **Nếu muốn phân tích cố kết coupled**: làm P1 → P5
- **Nếu muốn integrate với Plaxis hiện tại**: làm P6
