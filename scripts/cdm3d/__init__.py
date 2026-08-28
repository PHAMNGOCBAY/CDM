"""cdm3d — Mô hình 3D tương tác Trụ đất xi măng (CDM) - Đất nền.

Pipeline: Gmsh (phát sinh hình học + lưới) -> CalculiX ccx (giải FEM) -> PNG (hậu xử lý).

Package này **CHỈ chạy local** — không copy/push lên Streamlit Cloud (giống fem2d,
xem CLAUDE.md muc 13b). Ly do: phu thuoc gmsh/pyvista (naguon anh 3D nang) va
binary ngoai ccx.exe khong co tren Cloud.

Modules:
    geometry     — dung gmsh OpenCASCADE kernel: khoi dat + tru CDM hinh tru
    mesh_gmsh    — phat sinh luoi tu dien 3D (C3D4/C3D10), mesh size field quanh tru
    ccx_input    — meshio doc .msh -> ghi deck CalculiX .inp (vat lieu, bien, tai, step)
    run_ccx      — goi subprocess ccx.exe, tu tim binary qua env CDM3D_CCX_EXE / PATH
    postprocess  — render PNG 3D: luoi (truoc khi giai) va ket qua (.frd sau khi giai)

Don vi toan package: SI — m, kN, kPa (kN/m^2), kN/m^3, độ Celsius khong dung.
Xem 76-cdm3d-fem-gmsh-calculix.md de biet quy uoc hinh hoc + vat lieu + tai trong.
"""
from __future__ import annotations

__version__ = "0.1.0-scaffold"
