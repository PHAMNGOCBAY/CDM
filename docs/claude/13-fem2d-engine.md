### 13b. Module FEM2D Frame Solver — LOCAL ONLY (P4, cập nhật 2026-05-21)

**File engine:** `scripts/fem2d/frame2d/` (package ~10 file, ~2500 dòng)
**App:** `scripts/app_fem2d.py` (Streamlit port 8504, KHÔNG deploy Cloud)
**Khởi động:** `start_fem2d.bat` (CMD độc lập)
**Plan chi tiết:** [50-fem2d-frame-p4-plan.md](50-fem2d-frame-p4-plan.md)

**Khả năng (P4 — Frame 2D nâng cao):**

- 3 DOF/node (u_X, u_Y, θ_z), ma trận K 6×6
- Beam Euler-Bernoulli + Truss element 2D (4 DOF, axial-only)
- Static condensation cho moment release (pin/hinge tại đầu phần tử)
- Winkler springs (k_h, k_v, k_r) — nhân với tributary length của node
- Prestress neo (truss element) — equivalent nodal forces
- P-Delta iterative (geometric stiffness K_g) — refinement loop
- Staged construction (active elements + extra restraints per phase)
- SQLite storage 5 bảng prefix `fem2d_frame_*` trong `TTHC.sqlite`
- FrameBuilder high-level API cho tường cừ + neo + Winkler + tải Active

**API public:**

```python
from fem2d.frame2d import (
    Node, BeamElement, TrussElement, NodalLoad, ElemDistLoad,  # types
    FrameBuilder,                                                # high-level
    solve, solve_phase,                                          # solver
    plot_diagrams, dataframe_node_disp, dataframe_elem_forces,   # post
    save_model, save_result, load_model_by_name, create_tables,  # DB
    run_verify_suite,                                            # verify
)
```

**Verify suite (5 analytical cases — pass với sai số máy):**

| # | Test case | Formula | Sai số |
| --- | --- | --- | --- |
| 1 | Cantilever | δ = PL³/(3EI) | 0.00e+00 |
| 2 | Simply supported uniform | M_max = wL²/8 | 0.00% |
| 3 | Portal frame | ΣR_X = -H_load | 0.00% |
| 4 | Beam + truss anchor | ΣR_Y = P_applied | 0.00% |
| 5 | Euler buckling (10 elem) | P_cr = π²EI/(4L²) | 0.001% |

**Quy ước Front/Back áp dụng (CLAUDE.md §20):**

- Front = trái = global_x dương; tải Active push cọc về phía +X
- Anchor end PHẢI đặt phía Back (X âm) để đảm bảo neo BỊ KÉO (N > 0)
- Nếu đặt sai phía (X dương), neo bị NÉN → thiết kế sai vật lý

**4 lớp bảo vệ chống lên Cloud (BẮT BUỘC kiểm tra trước commit):**

1. `update_app.bat` whitelist — chỉ copy 4 file (`app_cdm.py`, `wall_internal_force.py`, `sw_global_stability.py`, `TTHC.sqlite`). `fem2d/` KHÔNG có
2. `cdm-deploy/.gitignore` chặn: `scripts/fem2d/`, `scripts/app_fem2d.py`, `start_fem2d.bat`
3. SQLite chung TTHC.sqlite — Cloud chỉ đọc, không ảnh hưởng app khác
4. Port 8504 riêng (app_cdm.py port 8503) — chạy độc lập

### 13c. FEM2D Roadmap — Các Bước Chưa Thực Hiện

P4 đã DONE. Roadmap V1-V7 (tích hợp P4 vào app) + P1-P7 (phase mới: Plane Strain LE, Mohr-Coulomb, SRF, Biot, Plaxis I/O, Plate bending) tách ra file riêng để giảm context. Xem [50-fem2d-roadmap.md](50-fem2d-roadmap.md).

