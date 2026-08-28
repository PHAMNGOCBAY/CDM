# 76 — Mô hình 3D Trụ CDM – Đất nền (Gmsh + CalculiX)

Module `scripts/cdm3d/` — mô hình hoá tương tác 3D giữa nhóm trụ đất xi măng (CDM)
và đất nền xung quanh, dùng **Gmsh** (phát sinh hình học + lưới phần tử hữu hạn) và
**CalculiX** (giải FEM). Xuất ảnh minh hoạ 3D dạng `*.png`.

**Trạng thái (2026-08-27): PIPELINE HOÀN CHỈNH** — hình học/lưới/giải/hậu xử lý PNG+GIF
đều đã test thành công với CalculiX thật. **Đã bổ sung giai đoạn thi công (kích hoạt
cọc qua `*MODEL CHANGE`) + tải lệch tâm + trích xuất chuyển vị ngang theo cọc** — xem
mục 8. Solver có sẵn tại `C:\CalculiX\calculix_2.23_4win\ccx_static.exe` (bản tĩnh,
không phụ thuộc DLL ngoài).

---

## 0. Hiệu chỉnh mô hình theo số liệu quan trắc thực tế — ĐÃ CÓ KẾT LUẬN (2026-08-27)

**Vấn đề:** Quan trắc thực tế cho chuyển vị ngang cọc CDM ở GD5 ≈ **80 cm**. Mô
hình hiện tại (bonded, GD5) dự đoán chỉ ~4,4 mm tại tâm cọc — **chênh lệch ~180 lần**.

- [x] Giả thuyết 1: **domain quá nhỏ** — quét `domain_buffer_m` 3,6→30m (Es, Ecdm
      giữ nguyên): Ux_max = 0,44 → 0,53 → 0,42 → **0,29 cm** — **KHÔNG TĂNG, còn hơi
      GIẢM**. Domain hiện tại (3,6m) đã đủ hội tụ — **loại bỏ giả thuyết này**.
      Ảnh: `images/cdm3d_KE_calib_domain_sweep.png`
- [x] Giả thuyết 2: **Es lớp đất yếu chưa phù hợp** — quét Es 3450→108 kPa (giảm
      32 lần): Ux_max = 0,44 → 0,85 → 1,56 → 3,13 → 6,06 → **10,58 cm**. Xấp xỉ tỉ
      lệ nghịch với Es (đúng lý thuyết đàn hồi). Ngoại suy: cần Es ≈ **19 kPa**
      (tương đương Cu ≈ 0,08 kPa qua Es=250·Cu) để đạt 80cm — **hoàn toàn phi vật
      lý** (mềm hơn cả bùn sệt, không tồn tại trong thực tế địa kỹ thuật).
      Ảnh: `images/cdm3d_KE_calib_Es_sweep.png`
- [x] Giả thuyết phụ: **Ecdm** — quét Ecdm 40000→2500 kPa (giảm 16 lần): Ux_max
      hầu như KHÔNG đổi (0,44→0,30→0,33cm) — **không phải đòn bẩy đáng kể**.
      Ảnh: `images/cdm3d_KE_calib_Ecdm_sweep.png`
- [x] **Kịch bản kết hợp cực đoan** (domain=30m + Es giảm 33 lần + Ecdm giảm 33
      lần đồng thời — TẤT CẢ đều đã vượt ngưỡng hợp lý vật lý): Ux_max chỉ đạt
      **7,87 cm** — **vẫn thiếu ~10 lần** so với 80cm. Ảnh:
      `images/cdm3d_KE_calib_combo_sweep.png`

### Kết luận (KHÔNG ép tham số phi vật lý để khớp số đo — đúng tinh thần chống
hallucination của dự án)

**Không có tổ hợp domain/Es/Ecdm nào trong phạm vi vật lý hợp lý (thậm chí cả khi
đã cố tình đẩy ra ngoài phạm vi hợp lý) có thể tái tạo chuyển vị 80cm bằng mô hình
đàn hồi tuyến tính.** Nguyên nhân bản chất: đàn hồi tuyến tính luôn cho chuyển vị
**TỈ LỆ THUẬN** với 1/E — không có cơ chế "chảy dẻo" (chuyển vị tăng vọt phi tuyến
khi vượt ngưỡng sức chịu tải) mà đất thực tế có.

**Nguyên nhân khả dĩ nhất của 80cm đo thực tế:** đất nền đã **vượt sức chịu tải
thiết kế, xảy ra biến dạng dẻo/phá hoại cục bộ** (bearing capacity exceeded) — cơ
chế mà mô hình đàn hồi tuyến tính V1 **về bản chất không thể mô phỏng được, dù
chỉnh bất kỳ tham số nào**. Để mô phỏng đúng cần bổ sung **Mohr-Coulomb** (đã có
trong roadmap mục 7) — đây là bằng chứng số liệu cụ thể càng khẳng định tính cấp
thiết của hạng mục đó, không phải suy đoán chung chung nữa.

**Khuyến nghị:** không tiếp tục dò tham số đàn hồi để khớp 80cm (sẽ dẫn đến giá
trị input phi vật lý, gây hiểu lầm). Ưu tiên triển khai Mohr-Coulomb cho lớp đất
yếu nếu cần tái tạo đúng độ lớn chuyển vị quan trắc.

Script khảo sát: `scripts/cdm3d_calibration_sweep.py` (20 kịch bản, dùng mô hình
bonded để chạy nhanh — ~35-90s/kịch bản, không dùng contact vì chỉ cần so sánh
tương đối độ nhạy tham số).

## 1. Kiến trúc package

```
scripts/cdm3d/
  __init__.py       — docstring, LOCAL ONLY (không deploy Cloud — xem mục 6)
  types.py          — dataclass SoilLayer, ColumnGroup, ModelParams
  params_io.py      — nạp tham số từ data/cdm3d_params.json (ưu tiên dữ liệu dự án)
  geometry.py        — dựng hình học 3D bằng gmsh OpenCASCADE (OCC) kernel
  mesh_gmsh.py       — phát sinh lưới tứ diện (mesh size field quanh trụ)
  ccx_input.py       — meshio đọc .msh → ghi deck CalculiX .inp
  run_ccx.py         — subprocess gọi ccx.exe, tự tìm qua CDM3D_CCX_EXE / PATH
  postprocess.py     — xuất PNG 3D (lưới trước giải + kết quả sau giải)

scripts/cdm3d_demo.py  — script __main__ chạy toàn bộ pipeline 7 bước
data/cdm3d_params.json — config (D, spacing, pattern, tham số theo zone KE/BXN/NHC)
results/cdm3d/          — file sinh ra: <zone>.msh / .inp / .frd / .dat (không commit)
images/cdm3d_<zone>_*.png — ảnh 3D xuất ra (mesh + kết quả)
```

Chạy demo: `python scripts/cdm3d_demo.py KE` (hoặc `BXN` / `NHC`).

---

## 2. Quy ước hình học

- Trục X, Y: mặt bằng (m). Trục Z: cao độ, **dương hướng lên** (quy ước địa kỹ thuật,
  giống toàn dự án — xem CLAUDE.md mục 20 Front/Back).
- Gốc toạ độ X=Y=0 đặt tại tâm nhóm trụ (trụ giữa của lưới vuông n×n nằm đúng gốc
  khi n lẻ).
- 3 lớp xếp chồng liên tục theo Z (không hở):
  1. **`dat_dap`** — đất đắp, từ `top_elev_m` xuống cao độ mặt đất tự nhiên (z=0)
  2. **`dat_yeu`** — đất yếu tự nhiên chứa trụ CDM, dày `H_cdm_m` (từ `tvtk_cdm_202605_TTHC.json`)
  3. **`lop_cung`** — lớp cứng dưới mũi trụ, kéo dài thêm `firm_layer_extra_depth_m`
     (mặc định 4m) dưới mũi trụ để biên đáy không ảnh hưởng kết quả gần trụ
- Nhóm trụ: lưới vuông `n_x × n_y` (mặc định 3×3=9 trụ) — **kịch bản minh hoạ tương
  tác giữa các trụ lân cận**, không phải toàn bộ lưới trụ thực tế ngoài công trường.
- Biên mô hình: đệm `domain_buffer_m` (mặc định 3.6m) quanh mép nhóm trụ để giảm
  ảnh hưởng biên.

**Physical Groups (gmsh) sau khi fragment:**

| Tên | Loại | Ý nghĩa |
|---|---|---|
| `SOIL_dat_dap`, `SOIL_dat_yeu`, `SOIL_lop_cung` | Volume (3D) | vật liệu đất theo lớp |
| `CDM_COLUMN` | Volume (3D) | vật liệu trụ CDM (toàn bộ đoạn, kể cả bị cắt qua nhiều lớp) |
| `BASE` | Surface (2D) | đáy mô hình — ngàm cứng |
| `SIDE_XMIN/XMAX/YMIN/YMAX` | Surface (2D) | 4 mặt biên đứng — con lăn (chỉ khoá chuyển vị pháp tuyến) |
| `TOP_SOIL` | Surface (2D) | mặt đất trên cùng (trừ đỉnh trụ) — nơi đặt tải đắp |
| `TOP_COLUMN` | Surface (2D) | đỉnh các trụ CDM |

**Lưu ý kỹ thuật quan trọng đã gặp khi build:** phân loại `TOP_SOIL` vs `TOP_COLUMN`
KHÔNG được dùng tâm bounding-box (mặt `TOP_SOIL` là 1 mặt phẳng nhiều lỗ tròn —
multiply-connected — tâm bbox của nó có thể trùng đúng vị trí 1 trụ khi lưới trụ đặt
tại gốc toạ độ, gây phân loại sai hoàn toàn). Phải dùng **diện tích**
(`gmsh.model.occ.getMass(2, tag)`) — mặt đỉnh trụ có diện tích ≈ `π(D/2)²`, mặt đất
lớn hơn nhiều lần. Xem `geometry.py::_tag_boundary_surfaces()`.

---

## 3. Vật liệu và tải trọng — Đơn giản hoá V1 (BẮT BUỘC đọc trước khi dùng kết quả)

| Khía cạnh | Cách làm V1 (hiện tại) | Đơn giản hoá / giới hạn |
|---|---|---|
| Vật liệu | Đàn hồi tuyến tính (E, ν) cho cả đất và trụ | CHƯA có Mohr-Coulomb / phá hoại dẻo |
| Liên kết trụ-đất | Bonded (dùng chung nút tại biên) | KHÔNG mô phỏng trượt/tách lớp thân trụ |
| Trọng lượng bản thân | **TẮT mặc định** (`include_self_weight=False` trong `write_ccx_inp()`) | Xem cảnh báo quan trọng bên dưới — KHÔNG bật khi chưa có geostatic K0 |
| Tải đắp `q` (kPa) | Quy đổi lực nút tập trung, phân bố đều trên `TOP_SOIL ∪ TOP_COLUMN` | Xấp xỉ — CHƯA dùng `*DLOAD` áp lực mặt chuẩn theo từng mặt phần tử (S1–S4) |
| Ứng suất ban đầu (geostatic K0) | KHÔNG có bước khởi tạo | Kết quả chuyển vị là **tương đối** (lún gây thêm do tải), không phải trạng thái tuyệt đối tại chỗ |

**⚠️ CẢNH BÁO QUAN TRỌNG — đã kiểm chứng thực tế (2026-08-26):** bật
`include_self_weight=True` mà KHÔNG có bước khởi tạo geostatic K0 sẽ cho chuyển vị
**SAI HOÀN TOÀN** (đã test ra ~0,9 m tại đỉnh mô hình — vô lý). Nguyên nhân: áp toàn
bộ trọng lượng bản thân lên đất từ trạng thái ứng suất = 0 tương đương hỏi "đất lún
bao nhiêu nếu trọng lực đột ngột bật lên" — không phải câu hỏi kỹ thuật thực tế (đất
đã chịu trọng lượng bản thân từ hàng nghìn năm địa chất). Ước lượng tay xác nhận:
$S \approx \gamma H^2/(2E)$ — với lớp đất yếu KE ($\gamma=16$, $H=23$m, $E=3450$kPa)
→ $S\approx 1,2$ m, đúng bậc độ lớn với lỗi quan sát được.

**Mặc định đúng (`include_self_weight=False`):** chuyển vị tính được là **lún RIÊNG
DO TẢI ĐẮP `q` gây ra** — đại lượng có thể so sánh trực tiếp với công thức S1 TCVN
9403 Phụ lục C đã có trong dự án. Kết quả test zone KE: **lún đỉnh lớn nhất ≈ 19,8
cm** (ngay giữa nhóm trụ) so với $S_1$ 1D = 10,3 cm (`tvtk_cdm_202605_TTHC.json`).
Chênh lệch ~2 lần này **hợp lý về vật lý**: công thức 1D coi khối gia cố là 1 vật
liệu composite san đều ($a{\cdot}E_c+(1{-}a){\cdot}E_s$), che mất hiện tượng **lún
cục bộ đất giữa các trụ lớn hơn mức trung bình** (trụ cứng "gánh" tải, đất mềm xung
quanh lún nhiều hơn) — đây chính là giá trị mô hình 3D mang lại mà công thức 1D
không nắm bắt được.

**Nguồn tham số:**

| Tham số | Nguồn | Ghi chú |
|---|---|---|
| `D_mm`, `spacing_m`, `pattern`, `top_elev_m`, `penetration_m` | `data/tvtk_cdm_202605_TTHC.json` → `config` | TCVN 9403 Phụ lục C |
| `q_kPa`, `H_cdm_m`, `Ec_kPa`, `Es_kPa` theo zone | cùng file → `cdm_design[]` | Es = 250×Cu_VST (Mesri & Olson) |
| `gamma_fill_kNm3`, `E_fill_kPa`, `nu_*`, `gamma_column_kNm3`, `firm_layer_stiffness_ratio` | `data/cdm3d_params.json` → `assumed_defaults` | **GIẢ ĐỊNH — không có trong dữ liệu thí nghiệm dự án, PHẢI kỹ sư xác nhận trước khi dùng kết quả** |

Mọi giá trị giả định được in cảnh báo ra console khi chạy (`params_io.print_warnings()`),
đúng nguyên tắc CLAUDE.md mục 15.

---

## 4. CalculiX — đã cài, tự phát hiện

`ccx.exe` là **binary biên dịch sẵn** (Fortran/C), không cài được qua `pip install`
hay `conda install` trên Windows (khác với `gmsh`/`meshio`/`pyvista`/`ccx2paraview`
— các gói Python thuần đã cài sẵn trong `.venv`, chỉ đọc/ghi file & hậu xử lý, KHÔNG
tự giải FEM — xem giải thích chi tiết trong hội thoại 2026-08-26).

**Đã có sẵn trên máy:** `C:\CalculiX\calculix_2.23_4win\` (gói "CalculiX for Windows"
2.23 do rafal.brzegowy@yahoo.com biên dịch, nguồn: dhondt.de/ccx_2.23.src.tar.bz2).
4 biến thể exe, chọn **`ccx_static.exe`** (spooles+pastix TĨNH — không phụ thuộc DLL
ngoài; `ccx_dynamic.exe` cần `mkl_rt.2.dll` KHÔNG có sẵn trong gói → tránh dùng).

`run_ccx.find_ccx_exe()` tự tìm theo thứ tự: biến môi trường `CDM3D_CCX_EXE` → PATH
hệ thống → `C:\CalculiX\calculix_2.23_4win\ccx_static.exe` (hard-code trong
`_KNOWN_INSTALL_PATHS`). Không tìm thấy → báo lỗi rõ ràng (`CcxNotFoundError`),
KHÔNG lặng lẽ bỏ qua. Máy khác không có sẵn CalculiX ở đường dẫn trên: đặt
`$env:CDM3D_CCX_EXE = "duong/dan/ccx_static.exe"`.

### Lỗi đã gặp và fix — `ccx2paraview` v3.2.0 crash khi đổi `.frd` → `.vtu`

`ccx2paraview.common.FRD.calculate_principal()` dùng `np.linalg.eigvals()` (thuật
toán tổng quát) cho tensor ứng suất — vốn LUÔN ĐỐI XỨNG — sai số làm tròn dấu phẩy
động có thể sinh trị riêng phức ảo cực nhỏ (~1e-15), làm `sorted()` bị `TypeError:
'<' not supported between instances of 'complex' and 'complex'`. Đã vá tại runtime
bằng `postprocess._patch_ccx2paraview_principal_stress()` — đổi sang
`np.linalg.eigvalsh()` (thuật toán riêng cho ma trận đối xứng, luôn trả số thực).
KHÔNG sửa file trong `site-packages`. Gọi tự động mỗi lần `convert_frd_to_vtu()`.

---

## 8. Giai đoạn thi công (`*MODEL CHANGE`) + Tải lệch tâm + Chuyển vị ngang (2026-08-27)

Mặc định (`use_model_change=True` trong `ccx_input.write_ccx_inp()`), mọi lần giải
đều chạy chuỗi **6 bước tuần tự trong 1 file `.inp`** thay vì 1 bước tĩnh đơn:

| Bước | Nội dung | Tải |
|---|---|---|
| GD(-1) — dummy | **Toàn bộ** phần tử active, KHÔNG `*MODEL CHANGE` | Không |
| GD0 — San nền | `*MODEL CHANGE REMOVE CDM_COLUMN` + khoá tạm nút "mồ côi" | Không |
| GD1 — Thi công cọc | `*MODEL CHANGE ADD CDM_COLUMN` (STRAIN FREE) + gỡ khoá | Không |
| GD2..N | Đắp tăng dần (`params.stages` — `data/cdm3d_params.json → staged_construction`) | q + độ lệch tâm tăng dần |

### 8a. Lỗi đã gặp và fix — mesh `.frd` "đóng băng" thiếu cọc nếu REMOVE ở bước đầu

**Phát hiện qua thực nghiệm (không có trong tài liệu CalculiX):** file `.frd` chỉ ghi
**MỘT LẦN DUY NHẤT** khối định nghĩa lưới/phần tử (`2C`), không ghi lại mỗi bước. Nếu
`*MODEL CHANGE REMOVE CDM_COLUMN` xảy ra ở **bước đầu tiên** của phân tích, khối lưới
đó bị "đóng băng" theo tập phần tử active tại thời điểm ghi (thiếu cọc) — **VĨNH VIỄN
cho mọi bước sau, kể cả sau khi `ADD` lại cọc ở GD1**. Hậu quả: `ccx2paraview` đọc
được ít hơn số phần tử thật (đã bắt được: 150270 thay vì 172358, thiếu đúng 22088
phần tử `CDM_COLUMN`), khiến truy vấn nội suy dọc trục cọc (`sample_over_line`) trả
về **100% điểm không hợp lệ** (`vtkValidPointMask=0`) — chuyển vị đọc được là hằng số
sai (chỉ 1 điểm sống sót ở đúng z_bot).

**Fix:** thêm **bước GD(-1) "dummy"** — TOÀN BỘ phần tử active, không `*MODEL CHANGE`,
không tải — làm bước ĐẦU TIÊN trong file, TRƯỚC GD0. Đã xác nhận: khối lưới `.frd` sau
đó chứa đủ 172358 phần tử, `sample_over_line`/`sample()` (pyvista) hoạt động đúng ở
mọi giai đoạn sau. **Quy tắc chung cho mọi bài toán CalculiX dùng `*MODEL CHANGE
REMOVE` trong tương lai: KHÔNG BAO GIỜ để REMOVE là thao tác đầu tiên trong file —
luôn có 1 bước "mọi phần tử active" đứng trước.**

### 8b. Lỗi đã gặp và fix — `ADD=STRAIN FREE` cần `NLGEOM`

CalculiX báo lỗi rõ ràng khi thiếu: `*ERROR reading *MODEL CHANGE: a strain-free
addition of elements ... is only possible for nonlinear calculations`. Fix: mọi
`*STEP` có `*MODEL CHANGE` phải khai `*STEP, NLGEOM` (đã áp dụng cho toàn bộ 6 bước
để nhất quán, kể cả GD2..N tuy không có MODEL CHANGE).

### 8c. Nút "mồ côi" khi REMOVE cọc

Nút nằm **hoàn toàn bên trong** khối trụ (không tiếp giáp mặt bên với đất — mặt bên
này vẫn giữ nút qua phần tử đất) sẽ mất hết độ cứng liên kết khi cọc bị REMOVE → ma
trận độ cứng suy biến (lỗi pivot). `ccx_input._orphan_column_nodes()` tính tập
`(nút CDM_COLUMN) − (nút bất kỳ SOIL_*)`, khoá tạm 3 bậc tự do (`*BOUNDARY` trong GD0),
gỡ khoá ở GD1 qua `*BOUNDARY, OP=NEW` (liệt kê lại CHỈ điều kiện biên vĩnh viễn
BASE/SIDE_* — `OP=NEW` xoá TOÀN BỘ điều kiện biên bước trước, không phải cộng dồn).
Đã kiểm chứng: mô hình test 1 cọc (6248 phần tử) có 25/224 nút cọc là "mồ côi".

### 8d. Công thức tải lệch tâm — lỗi hệ số 6 vs 12

Công thức áp lực đáy móng lệch tâm **TỔNG QUÁT theo x** (không phải chỉ tại mép):

$$q(x) = q_{avg} \left(1 + \dfrac{12 \cdot e \cdot x}{B^2}\right) \qquad \text{(} x \text{ tính từ tâm hình học)}$$

**Lỗi đã gặp:** dùng nhầm hệ số 6 (từ công thức quen thuộc `q_max/min = q_avg(1±6e/B)`
— công thức đó chỉ đúng khi ĐÁNH GIÁ TẠI MÉP x=B/2, không phải hàm tổng quát). Hệ số
6 cho hợp lực tính ngược ra chỉ bằng **một nửa** độ lệch tâm cấu hình. Đã kiểm chứng
bằng tích phân số (`Σ(F·x)/ΣF` phải ≈ e): hệ số 12 cho sai số ~2,4% (do lưới không
hoàn toàn đối xứng), hệ số 6 cho sai số ~83%. Quy tắc lõi giữa (kern) `|e| ≤ B/6` vẫn
đúng nguyên (đó là điều kiện tại mép, không đổi).

**Lỗi thứ hai đã gặp:** chia đều `tributary_area = footprint_area / n_nút` — SAI vì
mật độ lưới quanh cọc dày hơn nhiều vùng xa (Box mesh size field), làm "pha loãng"
độ lệch tâm (chỉ còn ~17% giá trị cấu hình). Fix: `ccx_input._node_tributary_area()`
tính diện tích tam giác bề mặt THẬT (từ phần tử `triangle` trên `TOP_SOIL`/
`TOP_COLUMN`), chia đều 1/3 diện tích mỗi tam giác cho 3 đỉnh — tổng diện tích khớp
chính xác 100% với `footprint_area`.

### 8e. Trích xuất chuyển vị ngang theo cọc — `scripts/cdm3d/column_forces.py`

```python
from cdm3d import column_forces, postprocess

vtus = postprocess.convert_frd_to_vtu_all_stages(frd_path)  # 1 file .vtu / giai doan
prof = column_forces.extract_lateral_profile(vtus[-1], column_xy=(1.8, 0.0),
                                              z_top=0.8, z_bot=-24.0, n_levels=25)
# prof: {"elev": [...], "ux_mm": [...], "uy_mm": [...], "u_lat_mm": [...]}
column_forces.plot_lateral_profiles({"Cot +X": prof}, out_png, title="...")
```

Dùng `pyvista.sample_over_line()` (nội suy dọc đường thẳng bất kỳ trong khối 3D,
không cần tìm nút chính xác). Chạy: `python scripts/cdm3d_lateral_demo.py KE -1`.

**Kết quả mẫu (zone KE, GD4 — tải thiết kế q=40,8 kPa, lệch tâm e=1,2m):** đường cong
Ux(z) trơn tru, hợp lý về vật lý cho cả 3 cọc dọc trục lệch tâm (X):

| Cọc | Ux tại đỉnh (mm) | Ux nhỏ nhất (mm, ~elev −5..−8m) |
|---|---|---|
| +X (1.8, 0) — phía tải cao | +9,13 | −7,15 |
| Giữa (0, 0) | +7,14 | −7,21 |
| −X (−1.8, 0) — phía tải thấp | +4,54 | −6,05 |

Cọc gần phía tải cao dao động biên độ lớn nhất — đúng hiệu ứng tương tác cọc-đất do
lệch tâm mà mô hình 1D không nắm bắt được.

### 8g. Phương án tải chỉ đắp 1 nửa miền (`load_footprint`, 2026-08-27)

`LoadStage.load_footprint` (`"full"` mặc định | `"half_pos"` | `"half_neg"`) — khi
khác `"full"`, tải **UNIFORM = q_avg_kPa** chỉ áp trên **nửa domain** theo `ecc_axis`
(bậc thang, KHÔNG phải gradient tuyến tính như công thức lệch tâm) — dùng khi tải
thiết kế chỉ đắp một vùng giới hạn thực tế, KHÔNG đắp ra hết vùng đệm tính toán
(`domain_buffer_m`). Cấu hình: `data/cdm3d_params.json → staged_construction.stages[]
→ "load_footprint": "half_pos"` (bỏ qua `eccentricity_m` khi dùng field này). Đã thêm
`GD5 - Phương án tải chỉ đắp nửa miền +X` vào chuỗi mặc định zone KE.

Trích xuất chuyển vị ngang của **đất giữa 2 cọc** (không phải tại tâm cọc) dùng CÙNG
hàm `extract_lateral_profile()`, chỉ đổi toạ độ mẫu sang điểm giữa 2 cọc liền kề (vd
`(0.9, 0.0)` = giữa cọc `(0,0)` và `(1.8,0)`). Kết quả mẫu (GD5, zone KE): điểm TRONG
vùng tải (+X) có Ux đỉnh 4,08mm vs điểm NGOÀI vùng tải (−X) chỉ 2,93mm — chênh lệch
rõ do bậc thang tải tại x=0. Script: `python scripts/cdm3d_lateral_demo.py KE -1`
(sửa toạ độ mẫu trong script hoặc gọi trực tiếp `column_forces.extract_lateral_profile`
cho vị trí tuỳ ý).

### 8f. Mô men uốn tương đương — CHƯA đủ tin cậy với lưới hiện tại (việc chưa làm)

`column_forces.extract_moment_profile()` đã viết (tích phân σ_zz qua mặt cắt, fit
mặt phẳng bằng bình phương tối thiểu, M = k·I) nhưng **kết quả thử nghiệm nhiễu,
không đơn điệu theo độ sâu** (biên độ dưới 1 kNm, dao động ngẫu nhiên) — nghi ngờ do
lưới quanh cọc còn thô (`mesh_size_near_column_m=0.3m` so với D=0.8m chỉ ~2-3 phần tử
qua đường kính, không đủ để bắt gradient ứng suất tuyến tính đáng tin cậy dù số điểm
lấy mẫu nhiều). **Chưa kiểm chứng bằng bài toán biết trước đáp án** (công-xôn chịu
lực ngang đầu tự do, so với M(z)=F·(L−z)) — cần làm trước khi tin dùng kết quả M(z).
Khuyến nghị: giảm `mesh_size_near_column_m` xuống ~0,1-0,15m khi cần trích mô men.

### 8h. γ đất yếu từ SQLite + mực nước ngầm (2026-08-27)

**Trước:** `SoilLayer("dat_yeu", ..., 16.0, ...)` — γ=16 kN/m³ hard-code, không có
nguồn dữ liệu thật.

**Sau:** `params_io._query_gamma_for_zone()` truy vấn `lab_tests JOIN boreholes`
(symbol_tcvn IN CH/MH/CH-OH/MH-OH — cùng bộ ký hiệu đã dùng cho Ip Bjerrum ở mục
36/38 CLAUDE.md) → **γ = 15,291 kN/m³ (KE, n=87 mẫu thật)**. Fallback 16,0 + cảnh
báo nếu zone không có dữ liệu (tôn trọng thứ tự ưu tiên SQLite→giả định của
CLAUDE.md mục 6b).

**Mực nước ngầm** — `ModelParams.water_table_elev` (mặc định = cao độ đỉnh cọc,
theo yêu cầu người dùng — nghĩa là **toàn bộ đất yếu + lớp cứng nằm dưới MNN**).
Hàm mới:

| Hàm | Vai trò |
|---|---|
| `ModelParams.effective_gamma_at(z)` | γ' = γ_sat − 9,81 nếu z ≤ MNN, ngược lại γ_sat (dry/tự nhiên) |
| `ModelParams.sigma_v_eff_kPa(z)` | Tích phân γ hiệu dụng qua **nhiều lớp + điểm MNN** từ đỉnh domain xuống z — **KHÔNG còn** công thức 1 lớp `γ×z` đơn giản như bản đầu |

**Đã kiểm chứng bằng tích phân tay:** σ'v(z=−11,5m, KE) = 70,38 kPa = (0,8m đất
đắp × γ'=9,19) + (11,5m đất yếu × γ'=5,481) = 7,35 + 63,03 ✓ khớp chính xác qua
2 lớp.

**Hệ quả quan trọng — μ_equiv thay đổi đáng kể:** `alpha_equivalent_mu()` (mục 8
"Ma sát âm") giờ dùng `params.sigma_v_eff_kPa()` thay vì `gamma×z` — kết quả
μ_equiv tăng từ **0,075 → 0,196** (gần gấp 3) vì ứng suất **hiệu dụng** (có đẩy
nổi do MNN ở đỉnh) nhỏ hơn nhiều ứng suất **tổng** dùng trước đó. Bất kỳ lần giải
contact tiếp theo PHẢI dùng μ mới này, không dùng lại 0,075/0,3 cũ.

**KHÔNG ảnh hưởng** `*DENSITY` (dùng γ_sat nguyên, không trừ nước — đúng vì tự
trọng dùng cho lực trọng trường tổng, không phải ứng suất hiệu dụng) — vô hại vì
`include_self_weight=False` hiện tại vẫn tắt.

### 8i. Soft Soil model — ĐÃ NGHIÊN CỨU, KHÔNG KHẢ THI trong CalculiX chuẩn (2026-08-27)

Đã tra cứu kỹ (không suy đoán): CalculiX **không có sẵn** mô hình họ Cam-Clay
(Soft Soil, Modified Cam-Clay kiểu PLAXIS — có λ*, κ*, áp lực tiền cố kết). Duy
nhất tìm thấy **"DRUCKER-PRAGER"** như 1 **VÍ DỤ hướng dẫn** cách tự viết
`*USER MATERIAL` (cần biên dịch lại CalculiX bằng Fortran, cú pháp hằng số CHƯA
được công bố rõ ràng ở nguồn tra được) — **KHÔNG PHẢI** tính năng có sẵn trong
`ccx_static.exe` đang dùng.

**Kết luận:** triển khai Soft Soil thật đòi hỏi viết subroutine Fortran tùy biến
+ biên dịch lại CalculiX từ mã nguồn — vượt quy mô hợp lý của 1 hạng mục, cần coi
là dự án con riêng nếu thực sự cần (không phải bước tiếp theo tự nhiên sau Mohr-
Coulomb). **Không đề xuất theo hướng này** khi chưa có xác nhận rõ ràng hơn về
khả năng của CalculiX.

## 9. Nhánh song song OpenSeesPy — mô hình đất dẻo (2026-08-27, ĐANG TRIỂN KHAI)

**Lý do:** mục 0 đã kết luận đàn hồi tuyến tính (CalculiX) không thể tái tạo 80cm
quan trắc dù ép Es/Ecdm/domain đến mức phi vật lý — nguyên nhân nghi ngờ là đất đã
vượt sức chịu tải (cần mô hình dẻo). CalculiX không có sẵn Soft Soil/Mohr-Coulomb
mà không biên dịch lại Fortran (mục 8h/8i). Đã khảo sát 3 hướng mã nguồn mở có mô
hình đất dẻo sẵn có (OpenSeesPy, MFront+CalculiX, Code_Aster) — chọn **OpenSeesPy
làm hướng chính** (đã cài sẵn, rủi ro Windows thấp nhất, `FourNodeTetrahedron` khớp
CHÍNH XÁC lưới tứ diện gmsh đang dùng, có sẵn `PressureIndependMultiYield` — mô
hình dẻo đa mặt chảy THIẾT KẾ RIÊNG cho sét chịu tải không thoát nước, đúng bản
chất bài toán dự án đang dùng Su/α-method). MFront+CalculiX và Code_Aster giữ làm
phương án đối chiếu, không triển khai đầy đủ trừ khi cần kiểm chứng chéo.

**Nguyên tắc:** package mới `scripts/cdm3d_opensees/` chạy SONG SONG, KHÔNG thay
thế `scripts/cdm3d/` (CalculiX) — tái sử dụng 100% `geometry.py`, `mesh_gmsh.py`,
`params_io.py` hiện có (hình học/lưới/tham số Es/γ từ SQLite giữ nguyên).

### 9a. Kiểm chứng Bước 1 — mesh/BC/tải OpenSeesPy khớp CalculiX bonded (ĐẠT)

Trước khi bật `PressureIndependMultiYield`, đã dựng mô hình nhỏ (1 cọc, 3 lớp,
lưới thô — cùng hình học `test_model_change.py`) bằng **vật liệu đàn hồi tuyến
tính** (`ElasticIsotropic`) trong OpenSeesPy, tải ngang 50 kN chia đều tại
`TOP_COLUMN`, và so sánh trực tiếp với CalculiX bonded-elastic (cùng lưới, cùng
BC, cùng tải) — script tương ứng:

- `scratch/test_opensees_elastic.py` — OpenSeesPy: **Ux đỉnh cọc = 5,0211 mm**
- `scratch/test_ccx_elastic_compare.py` — CalculiX (bonded, `*CLOAD`): **Ux đỉnh
  cọc = 5,0210 mm**

**Sai lệch < 0,001mm (< 0,02%)** — xác nhận mesh (`_read_mesh` dùng lại từ
`ccx_input.py`), điều kiện biên, và cách chia tải nút đều dịch đúng từ pipeline
CalculiX sang OpenSeesPy. Điều kiện biên tại `BASE` = ~0mm ở cả 2 solver (đúng
như kỳ vọng ngàm đáy).

**Lưu ý API khác CalculiX — PHẢI gộp điều kiện biên trước khi gọi `ops.fix()`:**
nút góc/cạnh domain thường thuộc ĐỒNG THỜI 2 tập nút biên (VD `BASE` ∩
`SIDE_XMIN`). CalculiX `*BOUNDARY` cho phép khai báo lại cùng 1 nút nhiều lần
(ghi đè), nhưng `ops.fix()` của OpenSeesPy **báo lỗi cứng** (`OpenSeesError`) nếu
gọi 2 lần cho cùng 1 nút. Bắt buộc gộp bằng `dict[node_tag] -> [dx,dy,dz]` (lấy
`max()` từng DOF qua tất cả tập nút áp dụng) rồi mới gọi `ops.fix()` **đúng 1
lần** mỗi nút — xem `scratch/test_opensees_elastic.py` hàm `_accumulate()`.

**Cross-check (Explore subagent, CLAUDE.md §8) phát hiện 1 lỗ hổng ở lần chạy
đầu và đã sửa ngay:** 2 script ban đầu tự mesh lại độc lập (mỗi script gọi
`geometry.build_geometry`+`mesh_gmsh.generate_mesh` riêng) — không có gì đảm bảo
Gmsh trả về CÙNG thứ tự node/phần tử giữa 2 tiến trình Python khác nhau dù cùng
geometry+mesh size, nên độ khớp 4 chữ số thập phân ban đầu chỉ là "gợi ý", chưa
phải bằng chứng chặt. Đã sửa: `test_ccx_elastic_compare.py` giờ **bắt buộc dùng
lại đúng file `test_ops.msh`** đã xuất bởi `test_opensees_elastic.py` (báo lỗi rõ
ràng nếu file chưa tồn tại, không tự mesh lại), đồng thời thêm `assert` khoảng
cách Euclid ~0 khi so khớp node theo toạ độ (tránh âm thầm lấy nhầm node). Sau
khi sửa, kết quả KHÔNG đổi (5,0210mm) — xác nhận khớp là thật, không phải trùng hợp.

### 9c. Gotcha bắt buộc — `updateMaterialStage` (PDMY/PIMY luôn "stage 0" mặc định)

**Phát hiện qua thực nghiệm (2026-08-27), không có trong ví dụ nhanh nào đã đọc
trước đó:** `PressureIndependMultiYield` (và họ PDMY/PDMY02/FluidSolidPorous)
**khởi tạo mặc định ở "stage 0" — ĐÀN HỒI TUYỆT ĐỐI, KHÔNG BAO GIỜ CHẢY DẺO dù
tải lớn đến đâu** — cho đến khi gọi tường minh:

```python
ops.updateMaterialStage('-material', matTag, '-stage', 1)  # stage 1 = deo
```

**Đã xác nhận bug bằng thực nghiệm số** (`scratch/test_opensees_plastic_sweep.py`,
trước khi thêm dòng trên): quét `F_total` từ 50 → 4000 kN (gấp 80 lần) trên đất
Su=13,8 kPa — chuyển vị **HOÀN TOÀN TUYẾN TÍNH TUYỆT ĐỐI** ở mọi mức tải (kể cả
4000kN, chắc chắn vượt xa sức chịu tải thực), không có bất kỳ dấu hiệu chảy dẻo
nào — chứng tỏ vật liệu bị "khoá" ở stage 0 (đàn hồi) một cách âm thầm, KHÔNG có
cảnh báo hay lỗi nào từ OpenSeesPy.

**Sau khi thêm `updateMaterialStage(..., stage=1)`** (gọi sau khi định nghĩa
phần tử/vật liệu, TRƯỚC khi áp tải ngang cần quan sát dẻo): quét lại cùng dải tải
cho kết quả ĐÚNG kỳ vọng vật lý — tỷ lệ `Ux_dẻo / Ux_đàn_hồi_tương_ứng` tăng dần
theo tải (mềm dần khi tiến gần ngưỡng phá hoại):

| F_total (kN) | Ux dẻo (mm) | Ux nếu đàn hồi (mm) | Tỷ lệ |
|---:|---:|---:|---:|
| 50 | 5,04 | 5,02 | 1,003 |
| 400 | 41,4 | 40,2 | 1,030 |
| 1200 | 128,4 | 120,5 | 1,066 |
| 2000 | 219,3 | 200,8 | 1,092 |
| 4000 | 459,5 | 401,7 | **1,144** |

**Ý nghĩa:** xác nhận cơ chế dẻo hoạt động đúng bản chất vật lý (dẻo luôn mềm hơn
đàn hồi, chênh lệch tăng khi tải tiến gần phá hoại) — đạt yêu cầu kiểm tra định
tính của kế hoạch đã duyệt. Mức chênh lệch trong bài test nhỏ này (đến 14,4% ở
80 lần tải gốc) CHƯA phải bằng chứng cho việc tái tạo được 80cm quan trắc — đây
chỉ là mô hình đồ chơi 1 cọc/tải điểm để kiểm chứng cơ chế, KHÔNG phải mô hình
GD5 thực (9 cọc, tải đắp phân bố, hình học/Es/Su thật của dự án).

**Quy tắc bắt buộc áp dụng cho MỌI mô hình OpenSeesPy dùng PDMY/PIMY sau này:**
gọi `updateMaterialStage(stage=1)` cho từng `matTag` của lớp đất dẻo ngay sau khi
model đã có đủ phần tử/BC, trước bước phân tích có tải cần quan sát ứng xử dẻo.
Nếu có bước gia tải trọng lượng bản thân (self-weight) để thiết lập ứng suất ban
đầu K0 — GIỮ stage=0 trong bước đó, chỉ chuyển stage=1 SAU bước đó (dự án hiện
TẮT self-weight — xem mục 8f — nên chưa cần bước K0 riêng, chuyển thẳng stage=1
trước khi áp tải chính).

### 9d2. Chuyển từ số liệu đồ chơi sang số liệu THẬT KE (2026-08-27)

Phát hiện 2026-08-27: các test 9a-9c ban đầu dùng **lẫn lộn** số liệu thật (E=3450
kPa) với số liệu đồ chơi (H lớp yếu=5m thay vì 23m thật, γ làm tròn 16 thay vì
15,291, Su suy ngược từ Es/250 thay vì đo trực tiếp) — gây nhầm lẫn khi đối
chiếu. Đã sửa dứt điểm: tạo `params_io.query_su_vst_avg()` +
`params_io.query_oedometer_avg()`, toàn bộ 3 script test (`test_opensees_elastic.py`,
`test_opensees_plastic.py`, `test_opensees_plastic_sweep.py`) giờ dựng
`ModelParams` qua `params_io.build_default_params("KE")` (chỉ override
`n_x=n_y=1` để thu nhỏ quy mô) — quy tắc đầy đủ đã lưu skill `/cdm3d-opensees`.

**Phát hiện quan trọng — 2 nguồn suy môđun đàn hồi cho SAU KHÁC NHAU:**

| Nguồn | Công thức | Giá trị KE (dat_yeu) |
|---|---|---|
| Mesri (đang dùng cho nhánh Bonded/Contact, `cdm3d_params.json`) | `Es = 250·Su` | **3450 kPa** |
| Oedometer THẬT (`lab_tests.E_kPa`, đã tính sẵn `Eoed=(1+e0)/(a1-2·0,01)`) | trung bình 80 mẫu thật | **2704,3 kPa** |

Theo yêu cầu người dùng (2026-08-27): nhánh OpenSeesPy dẻo chuyển sang dùng
**Eoed thật** (không dùng Es Mesri nữa) cho `refShearModul`/`refBulkModul`, giữ
**Su thật từ VST** (12,94 kPa, TB 104 mẫu, KHÔNG suy ngược Es/250 nữa) cho
`cohesi`. Kết quả trên mô hình 1 cọc + đủ 3 lớp thật (H_soft=23m), tải ngang
50kN — so sánh 3 phiên bản:

| Phiên bản | E dùng (kPa) | Su dùng (kPa) | Ux (mm) |
|---|---|---|---|
| Đàn hồi, Es Mesri, H=23m thật | 3450 | — | 5,2856 |
| Dẻo, Es Mesri, H=23m thật | 3450 | 12,94 (VST) | 5,3046 |
| **Dẻo, Eoed thật, H=23m thật** | **2704,3** | **12,94 (VST)** | **5,4907** |

Theo yêu cầu người dùng: **không chạy lại bước đàn hồi riêng** cho bộ số liệu
Eoed — quy tắc 3 trong skill `/cdm3d-opensees` (bước đàn hồi chỉ cần kiểm chứng
1 lần cho mesh/BC/tải, không cần lặp lại mỗi khi đổi bộ số liệu đất).

### 9f. `BoundingCamClay` ("Soft Soil" thật) — CRASH tái lập ở quy mô lớn, KHÔNG dùng được (2026-08-27)

Theo yêu cầu người dùng, đã thử mô hình Cam-Clay thật trong OpenSees (khác hẳn
`PressureIndependMultiYield` — mô hình cắt Tresca không thoát nước đang dùng,
không có ứng xử nén/nở thể tích): `nDMaterial('BoundingCamClay', matTag,
massDensity, C, bulkMod, OCR, mu_o, alpha, lambda, h, m)` (Borja et al. 2001,
cú pháp xác nhận qua [openseespydoc](https://openseespydoc.readthedocs.io/en/latest/src/BoundingCamClay.html)).

**Tham số suy từ số liệu THẬT KE** (script `scratch/test_opensees_camclay.py`):

| Tham số | Nguồn | Giá trị |
|---|---|---|
| `lambda` | Cc/ln(10), Cc thật TB 16 mẫu=0,7234 | 0,3142 |
| `bulkMod` (K) | (1+e0)·σ'v_ref/κ, κ=Cs/ln(10) | 4863,7 kPa |
| `mu_o` (G) | 3K(1-2ν)/(2(1+ν)), ν=0,35 giả định | 1621,2 kPa |
| `OCR` | **TB per-sample** PC_kPa/σ'v_hiệu_dụng TẠI ĐÚNG ĐỘ SÂU (15 mẫu) | 1,012 |
| `C` (≈M) | 6sinφ'/(3-sinφ'), φ'_CU_eff thật TB 14 mẫu=23,32° | 0,912 |
| `h`, `m` | 0, 0 — quyết định người dùng (không hardening, không có số liệu hiệu chỉnh) | 0 |

**Phát hiện phụ quan trọng (độc lập, xứng đáng ghi riêng):** tính `OCR` ĐÚNG
theo từng mẫu (PC tại đúng độ sâu mẫu đó / σ'v tại đúng độ sâu đó) — KHÔNG lấy
trung bình PC rồi chia trung bình σ'v (2 cách cho kết quả rất khác: 0,924 sai
vs 1,012 đúng) — cho thấy lớp đất yếu KE **OCR giảm mạnh theo độ sâu**: gần mặt
hơi quá cố kết (OCR 2,1–3,3 ở 1,4–4m) nhưng từ ~8m trở xuống **CHƯA CỐ KẾT XONG**
(OCR 0,42–0,74 ở 15–28m) — dữ liệu thật chưa từng dùng trong phân tích Su/
α-method trước đây, có thể liên quan trực tiếp câu hỏi 80cm đang điều tra.

**KẾT QUẢ: CRASH (access violation / segfault), KHÔNG PHẢI lỗi hội tụ thông
thường.** Đã cô lập nguyên nhân qua 4 thực nghiệm có kiểm soát:

1. Mô hình 1 phần tử tứ diện, tham số ví dụ CHÍNH THỨC của tài liệu (OCR=1,5,
   h=5000): KHÔNG crash — chỉ "failed to converge, Norm: nan" (bình thường cho
   test 1 phần tử/tải kéo đơn giản, không phải bug).
2. Mô hình 1 phần tử, tham số ví dụ nhưng `h=0`: KHÔNG crash — giống (1).
3. Mô hình 1 phần tử, **đúng tham số THẬT KE** ở trên: KHÔNG crash — giống (1)/(2).
4. **Mô hình lưới thật đầy đủ** (17341 phần tử `dat_yeu`, cùng tham số như (3)),
   gọi `ops.analyze(1)` **VỚI TẢI = 0** (không có `*CLOAD`/`ops.load` nào cả):
   **CRASH NGAY LẬP TỨC** (`Windows fatal exception: access violation`,
   Python `faulthandler` xác nhận crash tại chính lệnh `ops.analyze()`).

**Kết luận:** crash **không liên quan** đến giá trị tham số (giống hệt tham số
không crash ở quy mô nhỏ), **không liên quan** độ lớn/hướng tải (crash cả khi
tải=0) — mà liên quan đến **QUY MÔ LƯỚI** (nhiều nghìn phần tử `FourNodeTetrahedron`
dùng `BoundingCamClay` đồng thời). Đây nhiều khả năng là **lỗi/giới hạn nội bộ
của bản triển khai C++ `BoundingCamClay`** khi số lượng phần tử/điểm tích phân
lớn (có thể liên quan quản lý mảng trạng thái nội bộ) — KHÔNG phải lỗi tham số
đầu vào của dự án. `PressureIndependMultiYield` chạy ổn định ở quy mô tương tự
(24294 phần tử) với cùng solver (`BandGeneral`+`RCM`+`Newton`), nên không phải
do solver/cấu hình phân tích.

**Khuyến nghị:** KHÔNG dùng `BoundingCamClay` cho mô hình quy mô dự án
(hàng nghìn đến hàng chục nghìn phần tử) trong build OpenSeesPy hiện tại —
nguy cơ crash cao, chưa xác định được ngưỡng số phần tử an toàn (chưa làm phép
nhị phân tìm ngưỡng, có thể làm thêm nếu cần dùng model này trong tương lai).
Giữ `PressureIndependMultiYield` (đã kiểm chứng ổn định, đúng bản chất undrained
Su-based của dự án) làm mô hình dẻo chính; số liệu OCR/λ/M vừa suy ra vẫn có giá
trị tham khảo độc lập cho việc hiểu bản chất đất KE (đặc biệt phát hiện
underconsolidation ở độ sâu), dù không dùng trực tiếp được trong OpenSeesPy.

### 9d. Việc tiếp theo (chưa làm)

- [x] ~~Bật `PressureIndependMultiYield` cho lớp đất yếu trên mô hình nhỏ~~ (2026-08-27)
- [x] ~~Xác nhận dẻo kích hoạt đúng (Ux dẻo > đàn hồi, tăng dần theo tải)~~ (2026-08-27)
- [x] ~~Thay số liệu đồ chơi bằng số liệu THẬT KE (Eoed oedometer + Su VST)~~ (2026-08-27, xem mục 9d2)
- [ ] **So sánh Ux GD5 dẻo vs đàn hồi trên mô hình THẬT 9 cọc — TẠM DỪNG, KHÔNG
      HOÀN THÀNH (2026-08-27), lý do THỜI GIAN, không phải lỗi kỹ thuật.**
      Đã viết đúng pattern tải GD2..GD5 thật (lệch tâm + half-footprint, tái
      dùng `_eccentric_pressure()`/`_node_tributary_area()` từ `ccx_input.py` —
      xem `/cdm3d-opensees` Quy tắc 11, script `scratch/test_opensees_gd5_9col.py`)
      và đã kiểm chứng khớp CalculiX ở quy mô 1 cọc, NHƯNG ở quy mô 9 cọc thật,
      mỗi bước tăng tải mất 4-6 phút và TĂNG DẦN — riêng GD2 (1/4 giai đoạn) ước
      tính 1,5-2 giờ, toàn bộ có thể mất nhiều giờ. Đã dừng theo yêu cầu người
      dùng. Nghi ngờ `SuperLU` (solver trực tiếp) tăng chi phí siêu tuyến tính
      theo quy mô 3D — CHƯA điều tra/xác nhận, CHƯA thử solver lặp hoặc giảm số
      bước tăng tải. Công cụ theo dõi tiến độ thời gian thực đã sẵn sàng
      (`scripts/cdm3d/progress_log.py`, kiểu PLAXIS Calculation progress) cho
      lần thử lại sau. KHÔNG ép `peakShearStra`/`frictionAng` để khớp đúng
      80cm nếu giá trị phi vật lý khi (nếu) chạy lại được.
- [x] ~~Benchmark công bằng CalculiX vs OpenSeesPy (cùng lưới, cùng vật liệu đàn
      hồi, cùng solver-class)~~ (2026-08-27) — **KHÔNG có bằng chứng OpenSeesPy
      chậm hơn CalculiX về bản chất**: 1,561s vs 1,754s (OpenSeesPy nhanh hơn
      1,12 lần), sai lệch kết quả 0,0001%. Mọi trường hợp "OpenSeesPy chậm"
      quan sát trong dự án là do chọn sai solver hoặc do bài toán dẻo nặng mà
      CalculiX trong dự án chưa từng được giao — xem `/cdm3d-opensees` Quy tắc 10.
- [x] ~~`SimpleContact3D`+`ContactMaterial3D` / `zeroLengthContact3D` trên mô hình
      nhỏ~~ (2026-08-27) — **KẾT LUẬN: KHÔNG KHẢ THI cho cọc CDM hình trụ tròn**,
      đã tra cứu nguồn chính thức và xác nhận:
      - `zeroLengthContact3D`: tham số `dir` chỉ nhận pháp tuyến **cố định theo 1
        trong 3 trục toàn cục X/Y/Z**, "assumed to be unchanged during analysis"
        ([OpenSeesWiki](https://opensees.berkeley.edu/wiki/index.php/ZeroLengthContact_Element))
        — mặt trụ tròn có pháp tuyến xuyên tâm đổi liên tục quanh chu vi, không thoả.
      - `SimpleContact3D`: mặt master **bắt buộc là mặt tứ giác** ("four master
        nodes which define a surface of a hexahedral element",
        [openseespydoc](https://openseespydoc.readthedocs.io/en/latest/src/SimpleContact3D.html))
        — lưới hiện tại 100% tứ diện, `mesh_gmsh.py` không có `recombine`/hex nào.
      - Chuyển mesh sang brick (`stdBrick`/`bbarBrick`/`SSPbrick`) để dùng
        `SimpleContact3D` đòi hỏi viết lại toàn bộ pipeline sinh lưới (transfinite/
        extrude có cấu trúc quanh hình trụ, khác hẳn `occ.addCylinder`+`fragment`
        hiện tại) — công sức lớn, và KHÔNG giải quyết vấn đề pháp tuyến của
        `zeroLengthContact3D` (do hình học cong, không phải do loại phần tử).
      - **Quyết định:** giữ đúng hình dạng cọc tròn thật, KHÔNG dùng contact
        OpenSeesPy — quay lại gỡ lỗi CalculiX `*CONTACT PAIR, TYPE=NODE TO
        SURFACE` (đã triển khai ở `scripts/cdm3d/contact_ccx_input.py`, không bị
        giới hạn trục cố định hay mặt quad) — xem `.claude/commands/cdm3d-contact.md`
        để tiếp tục điều tra giả thuyết "seam" ranh giới lớp đất.
- [ ] Scale lên 9 cọc, chạy GD5, so sánh Ux_max với 80cm
- [ ] Tạo `scripts/cdm3d_opensees/opensees_input.py` + `opensees_postprocess.py`
      chính thức (hiện đang thử nghiệm logic trong `scratch/test_opensees_*.py`)

## 5. Hậu xử lý — ảnh 3D PNG + GIF xoay 360°

| Hàm | Khi nào chạy được | Nội dung |
|---|---|---|
| `postprocess.render_mesh_png()` | Ngay sau khi có `.msh` — KHÔNG cần ccx.exe | Lưới 3D theo nhóm vật liệu: đất bán trong suốt (nâu/xanh xám), trụ CDM xanh dương đậm, 1 góc nhìn isometric tĩnh |
| `postprocess.render_mesh_gif()` | Ngay sau khi có `.msh` — KHÔNG cần ccx.exe | Camera xoay 360° quanh trục Z (24 khung hình, 10 fps) — thấy rõ cấu trúc không gian mà 1 góc nhìn tĩnh không thể hiện được (chưa có trường kết quả để hoạt hình màu) |
| `postprocess.convert_frd_to_vtu()` + `render_results_png()` | CHỈ sau khi giải CalculiX thành công | Trường chuyển vị `U` (hoặc ứng suất `S`) tô màu, tuỳ chọn phóng đại biến dạng (`warp_factor`), 1 góc nhìn tĩnh |
| `postprocess.convert_frd_to_vtu()` + `render_results_gif()` | CHỈ sau khi giải CalculiX thành công | **Camera CỐ ĐỊNH** (không xoay) — tải tăng dần 0→100% qua 30 khung hình: hình dạng biến dạng dần (`warp_factor`) VÀ phổ màu "sáng dần" từ xanh đậm lên đủ dải màu thật, khung cuối giữ lại lâu hơn (`hold_last_frames`) |

Render dùng `pyvista` (offscreen VTK) + `imageio` (ghi GIF, đã có sẵn qua pyvista).
`render_mesh_gif()` xoay camera (không có trường kết quả để hoạt hình). Riêng
`render_results_gif()` — theo yêu cầu người dùng — **KHÔNG xoay camera**, mà hoạt
hình hoá trường kết quả: nhân đồng thời cả vector chuyển vị (điều khiển hình dạng
biến dạng) và giá trị màu với hệ số tải `frac = 0 → 1` mỗi khung hình (hợp lệ vì mô
hình đàn hồi tuyến tính — chuyển vị tỉ lệ thuận với tải). Thang màu (`clim`) cố định
ở `(0, giá_trị_max_thật)` xuyên suốt để phổ màu không nhảy giữa các khung.

`scripts/cdm3d_demo.py` xuất cả 4 file (`_mesh_3d.png/.gif`, `_result_U_3d.png/.gif`)
mặc định. Tắt GIF (tiết kiệm ~15–30s/file) bằng cờ `--no-gif`:
`python scripts/cdm3d_demo.py KE --no-gif`.

Đã kiểm chứng chạy được trên máy hiện tại — zone KE: lưới 28818 nút/172358 phần tử
tứ diện, GIF 24 khung hình/10fps (~1.1–1.9 MB mỗi file).

---

## 6. LOCAL ONLY — không deploy Cloud

Giống `scripts/fem2d/` (CLAUDE.md mục 13b): package `cdm3d/` phụ thuộc `gmsh` +
`pyvista` (thư viện nặng, cần OpenGL) + binary ngoài `ccx.exe` — **không đưa lên
Streamlit Cloud**. Không thêm vào whitelist của `update_app.bat`.

---

## 7. Việc chưa làm (roadmap)

- [x] ~~Cài CalculiX, giải thành công~~ (2026-08-26 — `ccx_static.exe`)
- [x] ~~Fix bug `ccx2paraview` principal stress~~ (2026-08-26)
- [x] ~~Tắt self-weight mặc định (tránh lún sai do thiếu K0)~~ (2026-08-26)
- [x] ~~Giai đoạn thi công (`*MODEL CHANGE` kích hoạt cọc) + tải lệch tâm~~ (2026-08-27)
- [x] ~~Trích xuất chuyển vị ngang Ux/Uy theo cọc + biểu đồ~~ (2026-08-27)
- [ ] Mô men uốn tương đương — đã viết `extract_moment_profile()` nhưng kết quả còn
      nhiễu, cần kiểm chứng bằng bài toán công-xôn biết trước đáp án + lưới mịn hơn
      quanh cọc trước khi tin dùng (xem mục 8f)
- [ ] Bước khởi tạo ứng suất geostatic (K0) — để bật lại self-weight đúng cách
- [x] ~~Mohr-Coulomb cho lớp đất yếu~~ (2026-08-27 — `mohr_coulomb=` trong `write_ccx_inp()`, phi=psi=0 → Tresca)
- [x] ~~`*DLOAD` áp lực mặt chuẩn (P, S1–S4) thay lực nút tập trung xấp xỉ~~ (2026-08-27)
- [ ] Liên kết trụ-đất dạng tiếp xúc (contact) thay vì bonded hoàn toàn — kế hoạch
      chi tiết đã lưu tại `/cdm3d-contact` (`.claude/commands/cdm3d-contact.md`),
      lý do: đã quan sát thực nghiệm (2026-08-27) liên kết bonded hiện tại làm
      "san bằng" bớt chênh lệch chuyển vị đất/cọc lẽ ra phải có khi Ecdm ≠ Es
- [ ] **Nhánh Salome-Meca + Code_Aster (Cam-Clay)** — xem mục 10, CHƯA BẮT ĐẦU cài
      đặt, để dành phiên sau theo yêu cầu người dùng (2026-08-28)
- [ ] Đọc `E_fill_kPa`, `gamma trụ CDM` từ thí nghiệm thực tế khi có (thay giả định)

---

## 10. Nhánh khả thi mới — Salome-Meca + Code_Aster (Cam-Clay/Soft Soil) — CHƯA TRIỂN KHAI (2026-08-28)

### Bối cảnh dẫn tới nhánh này

Sau khi kiểm toán nội lực cọc CDM thật (Ec=40000kPa, mục kiểm toán riêng — xem
`BaoCao_KiemToan_CocCDM_MohrCoulomb_*.docx`) cho kết quả cọc nứt kéo rất sớm
(~7,6cm), người dùng hỏi liệu có đưa được mô hình đất "Soft Soil" (Cam-Clay hiệu
chỉnh, khác Mohr-Coulomb đang dùng) vào CalculiX không. Đã tra cứu **toàn bộ 835
trang** tài liệu CalculiX 2.23 chính thức (`ccx_2.23.pdf`, tìm từ khoá "cam clay",
"soft soil", "critical state", "modified cam") — **KHÔNG có kết quả nào**. CalculiX
chỉ có Mohr-Coulomb + Drucker-Prager (trang 651-652) cho vật liệu dẻo dạng đất/đá,
không có mô hình phụ thuộc lịch sử ứng suất/tiền cố kết (preconsolidation).

Đường duy nhất để có Cam-Clay THẬT trong CalculiX là `*USER MATERIAL` (UMAT) —
subroutine Fortran tự viết + biên dịch lại CalculiX từ mã nguồn (xác nhận cơ chế
này tồn tại qua 3 ví dụ UMAT có sẵn: `CIARLET_EL`, `UNDO_NLGEOM_LIN_EL`,
`IDEAL_GAS`, `umat_abaqusnl.f` — trang 259-263) — nhưng đây là công việc lập
trình + build toolchain nhiều ngày, không phải chỉnh input file.

Người dùng sau đó gợi ý **Salome Platform + Code_Aster** — đã tra cứu và xác nhận
đây là hướng **tốt hơn hẳn** hướng UMAT.

### Đã xác nhận (tra cứu tài liệu chính thức, KHÔNG đoán)

**Code_Aster có CAM_CLAY NATIVE** — xác nhận qua tài liệu chính thức
`U4.51.11 — Comportements non linéaires` (Code_Aster v14, mục 4.4.8.9):

> `'CAM_CLAY'` — Relation de comportement élasto-plastique pour des calculs en
> mécanique des sols normalement consolidés (Cf. [R7.01.14]). La partie élastique
> est non-linéaire. La partie plastique peut être durcissante ou adoucissante.

Khai báo qua `DEFI_MATERIAU` với từ khoá `CAM_CLAY` + `ELAS`. Cùng danh sách này
(mục 4.5.3.3 "Comportements mécaniques du squelette") còn có sẵn:
`MOHR_COULOMB`, `CJS`, `BARCELONE` (đất không bão hoà), `LAIGLE`, `DRUCK_PRAGER`,
`DRUCK_PRAG_N_A`, `HOEK_BROWN_EFF/TOT`, `HUJEUX` (đất chịu tải chu kỳ) —
**thư viện vật liệu địa kỹ thuật của Code_Aster phong phú hơn CalculiX rất nhiều.**

**Cài đặt Windows khả thi, không cần build từ mã nguồn** — xác nhận qua
`code-aster-windows.com` (SimulEase, cộng đồng duy trì bản Windows):

- Code_Aster: file cài `.msi`, double-click, **không cần quyền admin**.
- Salome-Meca: file nén, giải nén + chạy `run_salome.bat`.
- Đã kiểm chứng chạy trên Windows 10 (có thể cả 7/8/8.1).

**Tin quan trọng cho tiến độ nếu triển khai:**

1. Code_Aster đọc trực tiếp lưới gmsh qua `LIRE_MAILLAGE(FORMAT='GMSH')` —
   **có thể dùng lại nguyên `scratch/grout_row.msh`** đã dựng cho CalculiX,
   KHÔNG cần dựng lại hình học 9 cọc trong Salome.
2. Tham số Cam-Clay (λ — pente vierge, κ — pente decharge/recharge, M — pente
   droite critique, e0, pc0 — áp lực tiền cố kết) có thể suy ra từ dữ liệu nén cố
   kết **ĐÃ CÓ SẴN** trong SQLite `lab_tests` (cột `Cc`, `Cs`, `e0`, `PC_kPa` cho
   zone KE — xem CLAUDE.md mục 11c) qua quan hệ chuẩn λ≈Cc/ln(10), κ≈Cs/ln(10) —
   **CHƯA kiểm chứng công thức chuyển đổi này với tài liệu R7.01.14**, phải làm
   trước khi tin dùng số liệu.

### Ưu điểm bổ sung quan trọng (từ ghi chú `luu_y_code_aster.md`, đã kiểm chứng 1 claim trọng yếu)

- **File `.comm` là Python THẬT, không chỉ "giống Python"** — đã kiểm chứng qua
  tài liệu chính thức `U1.03.01 — Superviseur et langage de commande`: cú pháp
  file lệnh "phải tuân theo cú pháp Python", người dùng nâng cao "có thể dùng
  toàn bộ sức mạnh ngôn ngữ PYTHON trong file lệnh" — viết macro-lệnh riêng,
  chèn `for`/`if`, `import numpy`, đọc dữ liệu từ cấu trúc Code_Aster vào biến
  Python. **Hạ thấp đáng kể rào cản** so với đánh giá ban đầu ("học DSL mới") —
  gần với viết script Python có sẵn cấu trúc lệnh, không phải ngôn ngữ tách biệt.
- **Salome GEOM/SMESH script được 100% bằng Python + chạy batch (không cần GUI)**
  — có thể tự động hoá toàn bộ chuỗi dựng hình → chia lưới → giải → đọc kết quả
  HDF5 bằng 1 script Python duy nhất, không cần thao tác tay trên giao diện.
- **Contact bề mặt-bề mặt KHÔNG YÊU CẦU lưới trùng nút (non-matching meshes)** —
  đây là điểm **có thể giải quyết trực tiếp vấn đề "seam" đã bế tắc** ở nhánh
  CalculiX contact (`.claude/commands/cdm3d-contact.md`, mô hình đầy đủ 9 cọc
  phân kỳ nghi do tam giác biên méo tại ranh giới lớp đất giao mặt trụ) — Code_Aster
  tự tính hình học ép mặt vào nhau, chỉ cần khai báo cặp Master/Slave qua
  `DEFI_CONTACT` dựa trên Face Groups từ Salome, không cần lưới quanh cọc đủ mịn
  khớp lưới đất như CalculiX `*CONTACT PAIR, TYPE=NODE TO SURFACE` yêu cầu.
- **Năng lực động lực học mạnh** (nền tảng EDF — mô phỏng nhà máy điện hạt nhân):
  Modal, Harmonic, Transient Dynamic phi tuyến, có sẵn biên giảm chấn
  Lysmer-Kuhlemeyer chặn phản xạ sóng tại biên khối đất — liên quan nếu dự án
  sau này cần phân tích động/địa chấn (hiện tại chỉ khảo sát tĩnh GD5).

### Điểm yếu cần lưu ý

- **Không có mô hình hoá lỏng/suy giảm độ cứng chu kỳ sẵn có** kiểu
  `PressureIndependMultiYield`/`PDMY`/`PIMY` của OpenSeesPy — nếu sau này cần
  phân tích hoá lỏng đất dưới tải động đất, phải tự viết vật liệu qua **MFront**
  (công cụ sinh code vật liệu riêng, tích hợp được với Code_Aster) — một lớp
  công việc bổ sung nữa, chưa xét trong phạm vi hiện tại.
- **Tài liệu/cộng đồng chủ yếu tiếng Pháp** — tài liệu chính thức (U4.51.x,
  R7.01.x) và phần lớn diễn đàn hỗ trợ bằng tiếng Pháp, có thể chậm hơn khi tra
  lỗi so với hệ sinh thái tiếng Anh của CalculiX/OpenSees.

### Việc CẦN LÀM khi tiếp tục (học từ mô hình nhỏ-trước-khi-lớn đã áp dụng thành công cho nhánh Mohr-Coulomb CalculiX)

1. Tải + cài Code_Aster (`.msi`) + Salome-Meca (giải nén) từ code-aster-windows.com.
2. Đọc tài liệu tham chiếu `[R7.01.14]` (lý thuyết Cam-Clay trong Code_Aster) để
   xác nhận đúng công thức chuyển đổi Cc/Cs/e0/PC → λ/κ/M/e0/pc0 — KHÔNG suy đoán.
3. Viết file COMM đầu tiên cho mô hình NHỎ (1 cọc, đúng như quy trình đã dùng cho
   CalculiX Mohr-Coulomb `scratch/test_ccx_mohr_coulomb.py`): `LIRE_MAILLAGE` từ
   `.msh` có sẵn, `DEFI_MATERIAU(CAM_CLAY=...)`, `AFFE_CHAR_MECA`, `STAT_NON_LINE`.
4. Kiểm chứng hội tụ + kết quả hợp lý trước khi scale lên 9 cọc.
5. So sánh Ux/M/N với kết quả CalculiX Mohr-Coulomb đã có (mục kiểm toán
   `BaoCao_KiemToan_CocCDM_MohrCoulomb_*.docx`) — Cam-Clay dự kiến cho ứng xử
   dẻo mềm hoá thực tế hơn Mohr-Coulomb lý tưởng, có thể giải thích thêm phần
   chênh lệch với quan trắc 80cm.

### Cú pháp COMM đã xác minh (2026-08-28) — sẵn sàng viết script, chưa chạy được

Người dùng yêu cầu cross-check kịch bản 3.5 (kiểm toán cọc thật Ec=40000kPa,
GD5, Su=5000kPa) bằng Code_Aster. Đã tra cứu/xác minh đủ "công thức" dưới đây
qua **test case thật đã kiểm chứng** trong bộ cài `17.4/share/aster/tests/`
(KHÔNG đoán) — nhưng CHƯA viết/chạy script thật do hết ngân sách phiên làm việc.

**1. Đọc lưới gmsh trực tiếp — KHÔNG cần chuyển đổi:**

Lưới `grout_row.msh` là MSH format **2.2 ASCII** — đúng chuẩn Code_Aster đọc
được thẳng qua `LIRE_MAILLAGE(FORMAT="GMSH", UNITE=19)` (xác nhận qua
`cont007a.comm`). **KHÔNG dùng đường MED** — đã thử `meshio.write(..., 'med')`
và xác nhận **làm mất hoàn toàn tên Physical Group** (chỉ còn `med:nom` chung
chung) — path này KHÔNG dùng được.

**2. Liên kết file — cơ chế `.export`, KHÔNG phải `DEFI_FICHIER` cho mesh đầu vào:**

```
P time_limit 200
P memory_limit 768
P ncpus 1
P mpi_nbcpu 1
P mpi_nbnoeud 1
P testlist verification sequential

F comm <script>.comm D 1
F msh grout_row.msh D 19
```

Chạy: `C:\Users\bayng\AppData\Local\code_aster\v2025\17.4\bin\run_aster.bat <job>.export`

**3. Physical Group → tên chung `GM<N>`, PHẢI đổi tên thủ công:**

Code_Aster's GMSH reader **KHÔNG đọc `$PhysicalNames` string** — chỉ dùng số
hiệu physical, tạo nhóm `GM<số>`. Bảng số hiệu của `grout_row.msh` (đọc trực
tiếp từ `$PhysicalNames`):

| dim | số hiệu | tên gmsh | → GM |
|---|---|---|---|
| 2 | 5 | BASE | GM5 |
| 2 | 6 | SIDE_XMIN | GM6 |
| 2 | 7 | SIDE_XMAX | GM7 |
| 2 | 8 | SIDE_YMIN | GM8 |
| 2 | 9 | SIDE_YMAX | GM9 |
| 2 | 10 | TOP_SOIL | GM10 |
| 2 | 11 | TOP_COLUMN | GM11 |
| 3 | 1 | SOIL_dat_dap | GM1 |
| 3 | 2 | SOIL_dat_yeu | GM2 |
| 3 | 3 | SOIL_lop_cung | GM3 |
| 3 | 4 | CDM_COLUMN | GM4 |

Đổi tên qua `DEFI_GROUP(reuse=MA, MAILLAGE=MA, CREA_GROUP_MA=(_F(GROUP_MA="GM5", NOM="BASE"), ...))`
(xác nhận cú pháp qua `cont007a.comm`).

**4. Vật liệu + tải + giải — xác nhận qua `ssnv232b.comm` (test triaxial 3D thật):**

```python
SOL = DEFI_MATERIAU(ELAS=_F(E=YOUNG, NU=POISSON, ALPHA=0.0),
                     MOHR_COULOMB=_F(PHI=0.0, ANGDIL=0.0, COHESION=5000.0))
MODELE = AFFE_MODELE(MAILLAGE=MA, AFFE=_F(TOUT="OUI", PHENOMENE="MECANIQUE", MODELISATION="3D"))
CHMAT = AFFE_MATERIAU(MAILLAGE=MA, AFFE=(_F(GROUP_MA="SOIL_dat_yeu", MATER=SOL), ...))
CHAR = AFFE_CHAR_MECA(MODELE=MODELE, PRES_REP=_F(GROUP_MA="TOP_SOIL", PRES=-40.8))  # ap luc mat THAT, tot hon xap xi luc nut
DEPL = AFFE_CHAR_CINE(MODELE=MODELE, MECA_IMPO=(_F(GROUP_MA="BASE", DX=0,DY=0,DZ=0), _F(GROUP_MA="SIDE_XMIN", DX=0), ...))
RESU = STAT_NON_LINE(MODELE=MODELE, CHAM_MATER=CHMAT, EXCIT=(_F(CHARGE=CHAR), _F(CHARGE=DEPL)),
                      COMPORTEMENT=_F(RELATION="MOHR_COULOMB"),
                      NEWTON=_F(MATRICE="TANGENTE", REAC_ITER=1),
                      CONVERGENCE=_F(RESI_GLOB_RELA=1e-4, ITER_GLOB_MAXI=20),
                      INCREMENT=_F(LIST_INST=..., INST_FIN=1.0))
RESU = CALC_CHAMP(reuse=RESU, CONTRAINTE="SIGM_NOEU", RESULTAT=RESU)  # ung suat nut de trich N/M
```

**CHƯA xác minh — cần thử nghiệm thực tế trước khi tin dùng:**

- `MOHR_COULOMB` với `PHI=0.0` (tương đương Tresca) — mọi ví dụ tìm được đều
  dùng PHI>0 (vd 33°), CHƯA có ví dụ PHI=0 xác nhận không suy biến trong
  Code_Aster (khác CalculiX đã xác nhận PHI=0 chạy tốt).
- `PRES_REP` chỉ áp được cho TOÀN BỘ 1 GROUP_MA — GD5 cần tải NỬA MIỀN (+X)
  và tải hàng cọc vữa cần CHỌN NÚT theo toạ độ (x=0) — DEFI_GROUP có các OPTION
  `SPHERE`/`CYLINDRE`/`BANDE`/`ENV_SPHERE`/`PLAN` (đã tra `U4.22.01`, xem bảng
  dưới) nhưng KHÔNG option nào cho nửa-không-gian (half-space) trực tiếp.
  Hướng khả thi: tính trước (bằng Python/meshio NGOÀI Code_Aster, tái dùng
  chính logic `_read_boundary_triangles`/centroid-filter đã có trong
  `ccx_input.py`) danh sách phần tử cần tải, rồi dùng
  `CREA_GROUP_MA(NOM=..., MAILLE=("M12","M45",...))` — phần tử sau khi
  `LIRE_MAILLAGE(FORMAT="GMSH")` được đặt tên **`M<n>`** tuần tự (xác nhận qua
  nhiều test: `rccm15a.comm`, `sdld104a.comm`...) — nhưng **CHƯA xác minh chắc
  chắn `n` có khớp đúng thứ tự phần tử trong file `.msh` gốc / thứ tự đọc bằng
  meshio hay không** — đây là rủi ro lớn nhất, PHẢI kiểm chứng bằng thử nghiệm
  nhỏ (vd tạo `CREA_GROUP_MA` cho 1-2 phần tử biết trước toạ độ, in ra
  `IMPR_RESU` hoặc dùng `MA.getCoordinates()` để đối chiếu) trước khi tin dùng
  cho mô hình đầy đủ.

**Bảng OPTION của `DEFI_GROUP` (tra `U4.22.01`, dùng khi cần):**

| Lệnh | OPTION | Tham số chính | Dùng cho |
|---|---|---|---|
| CREA_GROUP_MA | `SPHERE` | POINT/GROUP_NO_CENTRE, RAYON | phần tử có nút trong 1 hình cầu |
| CREA_GROUP_MA | `CYLINDRE` | POINT, RAYON, VECT_NORMALE | phần tử có nút trong 1 hình trụ — **dùng được cho chọn 1 cọc theo trục Z** |
| CREA_GROUP_MA | `BANDE` | POINT, VECT_NORMALE, DIST | phần tử trong 1 lớp quanh mặt phẳng (2 phía, không phải nửa-không-gian) |
| CREA_GROUP_NO | `ENV_SPHERE` | POINT, RAYON, PRECISION | nút trên bề mặt 1 hình cầu |
| CREA_GROUP_NO | `PLAN` | POINT, VECT_NORMALE, PRECISION | nút nằm đúng trên 1 mặt phẳng |

**Việc CẦN LÀM tiếp (thứ tự, thay thế bước 3 cũ ở trên khi quay lại):**

1. Viết script nhỏ CHỈ để kiểm chứng thứ tự đánh số `M<n>` (đọc `MA.getCoordinates()`
   qua Python API, đối chiếu với toạ độ phần tử thứ n trong `.msh` gốc).
2. Nếu khớp: viết `CREA_GROUP_MA` bằng danh sách `MAILLE=(...)` tính sẵn bằng
   Python (tái dùng logic centroid-filter của `ccx_input.py`) cho tải GD5 nửa
   miền + hàng cọc vữa.
3. Nếu KHÔNG khớp: tìm cách khác lấy toạ độ trực tiếp từ `code_aster.Objects.Mesh`
   API (chưa nghiên cứu chi tiết) để lọc trong chính COMM script.
4. Thử PHI=0.0 trong MOHR_COULOMB trên model nhỏ (1 cọc) trước — nếu suy biến,
   dùng PHI nhỏ khác 0 (vd 0.1°) thay thế, giữ tinh thần "khong bind" như CalculiX.
5. Chỉ sau khi (1)-(4) xong mới viết script đầy đủ 9 cọc + 5 mức P + trích M/N
   (dùng lại phương pháp hồi quy `sigma_zz=a+b.x+c.y` đã kiểm chứng ở CalculiX)
   + biểu đồ so sánh với kết quả CalculiX đã có.

### Trạng thái: ĐÃ CÀI ĐẶT (2026-08-28) — CHƯA VIẾT FILE COMM

Bước 1 của checklist trên đã hoàn thành trong cùng ngày (khác thời điểm ghi ban đầu):

- **Code_Aster v2025** cài thành công qua MSI (`code-aster_v2025_std.msi`, MD5 đã
  xác minh khớp `95a2171a6eb967874f7d0c98e881c66c`) — cài tại
  `C:\Users\bayng\AppData\Local\code_aster\v2025\` (không cần quyền admin, đúng
  như dự kiến). Gồm 2 bản Code_Aster: `16.9` và `17.4`. Post-install (liên kết
  Python, dọn file tạm) đã tự chạy xong qua MSI, đã xác minh (`Python37.exe`/
  `Python311.exe` stub đã bị xoá, junction `17.4\Python311` đã tạo đúng).
- **Salome-Meca 2025** (gói 7-Zip self-extracting `SM-2025-w64-0.1.exe`, MD5 đã
  xác minh khớp `1a71719ef26d1ad593e17c37d0266ae6` sau khi tải lại lần 2 — lần
  tải đầu bị đứt kết nối TLS giữa chừng ở 82,7%, curl báo lỗi `(56) schannel:
  server closed abruptly` nhưng bị pipe `| tail` che mất exit code thật, tưởng
  nhầm là thành công — bài học: không pipe `curl` qua `tail` khi cần kiểm tra
  exit code) — giải nén SILENT (`-o"C:\SALOME-MECA-2025" -y`, không cần bấm tay)
  vào `C:\SALOME-MECA-2025\v2025\`. Có đủ module `GEOM`, `GUI`, **`ASTERSTUDY`**
  (tích hợp Code_Aster vào giao diện Salome), `HYBRIDPLUGIN`, `GMSHPLUGIN`...
  `install_bin.bat` đi kèm CHỈ dành cho "developer mode" (build SALOME từ mã
  nguồn qua git) — **KHÔNG cần chạy** để dùng bản nhị phân có sẵn.
- Thư mục rác từ lần thử WSL2 trước đó (`C:\smeca`, ~32GB: `ext4.vhdx` +
  `smeca-2024.1-wsl2-verified.tar.gz`) đã **XOÁ** theo yêu cầu người dùng
  (2026-08-28) — WSL không hề được cài trên máy, xác nhận lần thử đó đã bỏ dở.
  `C:\SALOME-9.15.0` (bản Salome cũ không kèm Code_Aster, có 1 file
  `Study4.hdf` từ 21/05/2026) — GIỮ NGUYÊN, không đụng tới, độc lập với
  `C:\SALOME-MECA-2025` mới.

**Cách khởi động:** `C:\SALOME-MECA-2025\v2025\run_salome.bat` (GUI đầy đủ, có
ASTERSTUDY) hoặc gọi trực tiếp Code_Aster qua
`C:\Users\bayng\AppData\Local\code_aster\v2025\17.4\...` (cần xác định đúng
executable/entry point khi viết script chạy batch, chưa kiểm tra ở bước này).

**Việc CÒN LẠI (bước 2-5 của checklist trên, CHƯA làm):** đọc tài liệu
`[R7.01.14]` xác nhận công thức Cc/Cs/e0/PC → λ/κ/M/e0/pc0, viết file COMM đầu
tiên cho mô hình nhỏ, kiểm chứng hội tụ, so sánh với CalculiX.
