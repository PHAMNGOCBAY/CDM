### 74. Engine móng trụ CDM LK2 — tái lập 100% file Excel "TINH MONG TRU CDM - LK2.xlsx"

**Bối cảnh:** Hồ sơ gốc là bảng tính Excel 7 sheet, ~2.640 công thức, có liên kết ngoài ổ E:.
Yêu cầu: trình bày lên UI **sống** (đổi input → tính lại) mà **khớp 100%** số của Excel.

**Quyết định kỹ thuật (verify 2026):** KHÔNG chạy thẳng công thức Excel qua thư viện —
- `pycel` đọc tĩnh khớp 100% nhưng **không lan truyền** thay đổi qua dải `SUM` (Ecol đổi nhưng Eeq giữ nguyên);
- `formulas` lỗi vì file liên kết ngoài ổ E:;
- openpyxl ghi đè input → xoá cache → pycel ra DIV/0.

→ Chọn **port từng cột công thức sang Python** (engine sống), đối chiếu với giá trị "vàng" (cache Excel) — sai số **0.00**.

#### Files

| File | Vai trò |
|---|---|
| [scripts/cdm_lk2_calc.py](../../scripts/cdm_lk2_calc.py) | Engine — 4 nhóm tính, dataclass + compute_* |
| [scripts/save_lk2_results.py](../../scripts/save_lk2_results.py) | Lưu SQLite (LOCAL+PROJECT) + JSON snapshot |
| [scripts/pages/lk2_page.py](../../scripts/pages/lk2_page.py) | UI trang "Móng trụ CDM (LK2)" — auto-compute, trải phẳng |
| [data/lk2_cdm_settlement.json](../../data/lk2_cdm_settlement.json) | Dataset LK2 (địa tầng + thông số) + **golden values** + 2 bảng tra (Cv–áp lực, Tv–U%) |
| [data/lk2_results_snapshot.json](../../data/lk2_results_snapshot.json) | Snapshot kết quả |
| [tests/test_lk2_cdm.py](../../tests/test_lk2_cdm.py) | 23 golden tests (sai số <1e-6 lún/SCT, <1e-3 lún-thời gian) |

**Nav:** sidebar "Móng trụ CDM (LK2)" (page id `"lk2"`) trong [app_cdm.py](../../scripts/app_cdm.py).

#### 4 nhóm tính (port từ 4 nhóm sheet) — đều khớp Excel sai số 0.00

**A. Lún khối móng (sheet `(1)`)** — `compute_lk2()`
- a = Ac/A_unit ; Ac = π(D/2)² ; A_unit = S² (vuông) | S²·√3/2 (tam giác)
- Ecol = factor·quck/2 ; Esoil_i = E_i (bảng, E=200·Cu) ; M_i = Ecol·a + Esoil_i·(1−a)
- Eeq = Σ(M_i·g_i)/Σ g_i (g_i = bề dày trong khối [CD2..CD1])
- **S_block = P·L/Eeq** (P = tải đắp TĨNH, L = CD1−CD2)
- **Sc** = Σ phân tố **dưới mũi** (z_bot < CD2), nhánh OC/NC/cross-PC (Terzaghi 1D), với
  Δσ phân tán **W/(2·z'·tanθ + W)** (z' = bề dày tích luỹ dưới mũi tới đáy phân tố),
  σ'vz = Σγ·h tới giữa phân tố (γ=γdn dưới MNN).
- **S = S_block + Sc**. (LK2: 0.0299 + 0.428 = **0.4579 m**)

**B. Sức chịu tải (sheet `SCT`)** — `compute_sct()` — dùng q CÓ hoạt tải
- N = q·s² ; Nvl = (quck/Fs)·Ap ; Nđn = a_pier·Ap·qp + π·D·qsi·L ; qp = 6·Cu ; Nc = min(Nvl,Nđn)
- Tập trung ứng suất: σ_col = Ecol/Etd·q ; Pcol = σ_col·Ap (Etd = ΣM·g/max_depth)
- AIT: Qult.col = Ap·(3.5·quck + 3(q + 5·Cu)) ; Qult.soil = (πD·L + 2.25πD²)·Cu ; Qa = Qult.soil/Fs

**C. Lún theo thời gian (sheet `(2)`)** — `compute_time_history()`
- Cvi = nội suy(bảng Cv–áp lực, σ'vf)·**1e-3** cm²/s ; σ'vf = σ'vz + Δσ
- Ctbv = (H·100)²/(Σ h·100/√Cvi)² ; H = Σ z'(thoát nước 1 mặt)
- Tv = Ctbv/(H·100)²·t·**31.104.000** (năm = 360 ngày) ; Uv = TLOOKUP bảng Tv–U% (sheet `about`)
- St = Uv·Sc ; lún còn lại = Sc − St ; so với giới hạn (mặc định 40 cm).

**D. Kiểm toán + giới hạn lún (sheet `KIEM TOAN`, `Gioihan lun`)** — `compute_concrete_check()` + `SETTLEMENT_LIMITS`
- Mtt = q(S−d)²/8 ; Vtt = q(S−d)/2 ; [σ] = 0.63·√f'c
- dv>0: Vr = φ·min(4 công thức 11823-5) ; Mr = min(TCVN5574, 11823-5). LK2 dv=0 → chỉ tính nội lực yêu cầu.
- Bảng giới hạn lún TCCS 41: cao tốc/cấp I–IV [10/20/30], cấp 60 trở xuống [20/30/40].

#### Bảng SQLite (tiền tố `lk2_`)

| Bảng | Nội dung |
|---|---|
| `lk2_settlement_summary` | Sblock/Sc/S_total + Eeq/a/L |
| `lk2_settlement_sublayers` | chi tiết từng phân tố (σvz, Δσ, nhánh, Sc) |
| `lk2_time_history` | Tv/Uv/St/residual theo năm |
| `lk2_bearing` | N/Nvl/Nđn/Nc/Pcol/AIT |
| `lk2_concrete_check` | Mtt/Vtt/Vr/Mr |

#### Lưu ý
- Đổi tham số trên UI → engine tính lại tức thời (auto-compute §9b, không nút Build/Solve).
- Bộ thông số mặc định = đúng hồ sơ LK2 → metric hiển thị trùng Excel.
- Tải LÚN = P tĩnh (không hoạt tải) ; tải SỨC CHỊU TẢI = q tổng (có hoạt tải) — đồng bộ §28.

#### Phương án lún nền CHƯA xử lý (trang "Lún nền chưa xử lý", page id `no_treat`)

- **Engine:** [scripts/cdm_no_treat_settlement.py](../../scripts/cdm_no_treat_settlement.py) — `compute_no_treat()`, `list_zone_boreholes()`, `save_results()`.
- **UI:** [scripts/pages/no_treat_page.py](../../scripts/pages/no_treat_page.py) — 2 chế độ (radio): "Theo hố khoan (chọn vùng KE/BXN/NHC/QTT)" và **"Theo 6 vùng CDM (Bờ kè)"** (gom theo `ke_cdm_zones`, lún đại diện vùng = max nhóm HK). Chọn CĐTK + γ + MNN + Δσ (1D/Boussinesq), auto-compute. Engine: `compute_no_treat_6zones()`.
- **Tải gây lún:** q = γ_đắp · (CĐTK − CĐTN của hố khoan) ; H_đắp = max(0, CĐTK − CĐTN).
- **Tính trong VÙNG ẢNH HƯỞNG (§71):** dùng `settlement_calc.calc_s2_below_cdm(cdm_tip_depth_m=0)` —
  chia phân tố 2 m, tích phân tới đáy vùng ảnh hưởng (Δσ/σ'v0 < 10%), **mở rộng dưới đáy hố khoan**
  nếu cần, phân nhánh sét (Terzaghi OC/NC/cross) + cát (Es từ SPT). Δσ: 1D không đổi (mặc định) hoặc
  Boussinesq dải (B_load_m). MNN: gwt_depth = max(0, CĐTN − cao_độ_MNN).
  (KHÔNG dùng `calc_settlement_from_db` vì hàm này chỉ cộng theo mẫu nén lab, không cắt vùng ảnh hưởng.)
- **SQLite:** `cdm_no_treat_design_settlement` (PK zone+bh_name; cột H_fill_m, q_kPa, S_total_cm=S∞,
  S_15yr_cm, **d_influence_m** (đáy vùng ảnh hưởng), n_sublayers…), lưu LOCAL + PROJECT.
- Mục đích: cơ sở so sánh với phương án xử lý CDM (S₁+S₂). KE bờ kè: S∞ ~0,1–230 cm; đáy vùng ảnh hưởng tới ~90 m (HK9).

#### Bảng thống kê chỉ tiêu cơ lý (trang "Thống kê cơ lý đất", page id `soil_stats`)

- **Engine:** [scripts/soil_param_stats.py](../../scripts/soil_param_stats.py) — `stats_by_layer(zone_prefix | bh_names)` gom theo (vùng, ký hiệu lớp), trung bình 17 chỉ tiêu (γ, c, φ, e₀, Atterberg + **nén cố kết** Cc/Cs/PC/Cv/a₁₋₂/qu). Mẫu ánh xạ vào lớp theo độ sâu trung điểm.
- **UI:** [scripts/pages/soil_stats_page.py](../../scripts/pages/soil_stats_page.py) — chọn vùng (gồm "KE — Bờ kè (tuyến cừ)"); 2 bảng (nén cố kết + vật lý/cắt) + biểu đồ Cc.
- **SQLite:** `soil_param_layer_stats` (PK zone+symbol; 39 dòng vùng×lớp).

#### Quy tắc Bờ kè (tuyến cừ) — áp cho cả lún chưa xử lý & thống kê cơ lý

- **Phạm vi:** chỉ hố khoan trên tuyến cừ — `ke_sw_design.on_sw_alignment=1`, **trừ `LEVEE_EXCLUDE={"KE-HK8"}`** → {KE-HK2,3,7,9,10,11} (6 HK). Helper `levee_boreholes()` / `resolve_boreholes(LEVEE_KEY)`. (HK1,4,5,6,12 ngoài tuyến cừ; HK8 loại vì là vị trí cọc thử CDM.)
- **KE-HK8 KHÔNG đưa vào tính toán bờ kè** (lớp xi măng đất 6,7–22,4m — vị trí cọc thử CDM). `SYMBOL_OVERRIDE={("KE-HK8","XMD"):"1"}` vẫn giữ để khi xem "Tất cả vùng" thì XMD tính như bùn 1; KE-HK12 không có lớp XMD.

#### Bảng 6 vùng đại diện (BCL) + Chỉ tiêu cơ lý TRUNG BÌNH theo lớp (thống nhất)

- **Cấu hình 6 vùng (nguồn BCL — Ban chiến lược):** `ZONE_FILL_CONFIG` trong [cdm_no_treat_settlement.py](../../scripts/cdm_no_treat_settlement.py) — HK đại diện + cao độ tự nhiên + chiều dày đắp (PA1 xe chạy / PA2 vỉa hè): ZONE1 HK11, ZONE2-3 HK9, ZONE3 HK10, ZONE4 HK7, ZONE5 HK5, ZONE6 HK2. Tải q = γ·H_đắp. UI: chế độ "Theo bảng 6 vùng (HK đại diện)".
- **Thống nhất dùng chỉ tiêu TRUNG BÌNH theo lớp:** mọi tính toán gán cho mỗi lớp của hố khoan bộ chỉ tiêu cơ lý trung bình (vùng × ký hiệu) thay vì lab rời rạc → nhất quán, tái lập.
  - **4 file:** SQLite `soil_param_layer_stats` (39 dòng) · JSON [data/soil_param_layer_stats.json](../../data/soil_param_layer_stats.json) · MD [75-chi-tieu-co-ly-trung-binh-lop-dat.md](../../75-chi-tieu-co-ly-trung-binh-lop-dat.md) · PY [scripts/soil_param_stats.py](../../scripts/soil_param_stats.py) + [scripts/cdm_layer_avg_settlement.py](../../scripts/cdm_layer_avg_settlement.py).
  - **Engine:** `cdm_layer_avg_settlement.settle_avg()` — σ'v0 theo γ_tb (γ' dưới MNN), Δσ 1D/Boussinesq, vùng ảnh hưởng §71. **Phân nhánh công thức theo loại đất + e₀:** cát → đàn hồi Es ; **sét e₀≥1 → nén cố kết Terzaghi** (Cc/Cs/e0/PC, OC/NC/cross) ; **sét e₀<1 → mô đun biến dạng Eoed=(1+e0)/a12×98,0665**. Lưu SQLite `cdm_avg_layer_settlement`.
  - UI chế độ "Theo bảng 6 vùng" có radio chọn nguồn chỉ tiêu: **"Chỉ tiêu BCL (Ban chiến lược)"** (mặc định) / "Trung bình theo lớp (lab)" / "Số liệu từng hố khoan".
  - **Lún theo thời gian (cố kết Terzaghi):** chỉ lớp **sét e₀>1** cố kết theo U(t); lớp cát + sét chặt e₀<1 lún tức thời. S(15 năm) = S_tức thời + U(15năm)·S_cố kết (< S∞). Cv lấy từ BCL; checkbox thoát nước 1/2 mặt. Biểu đồ: S(t) 15 năm + ứng suất σ'v0/Δσ/vùng ảnh hưởng theo độ sâu.
  - **Phương án "mới san lấp":** checkbox giả định CĐTN = 0,0 cho hố có CĐTN > 0 (HK11/HK5/HK2) → phần san lấp (CĐTN cũ) thành tải đắp bổ sung (H_đắp += CĐTN), tải gây lún + độ lún tăng.

#### Bộ chỉ tiêu BCL (Ban chiến lược) — single source bờ kè

- **Nguồn:** bảng "TTHC tpHCM — Thu Thiem" của BCL (10 lớp F/1/1b/2a/2b/2c/3/4/5/6/7). Lưu: SQLite `bcl_soil_params` · JSON [data/bcl_soil_params.json](../../data/bcl_soil_params.json) · PY [scripts/bcl_soil_params.py](../../scripts/bcl_soil_params.py) · MD [75-chi-tieu-co-ly-trung-binh-lop-dat.md](../../75-chi-tieu-co-ly-trung-binh-lop-dat.md) mục A.
- **Tham số chính:** γ, e₀, Cc, Cs, Cv (×10⁻⁴ cm²/s), N_spt; E=α·N (α=2000) cho cát/lớp chặt; Su(VST)=5+0,7·Z cho sét; **P_c không cho → sét NC**.
- **Áp dụng:** `settle_avg(..., bcl_params=get_bcl_params())` ưu tiên BCL thay cho trung bình lab. Lún 6 vùng (BCL, PA1): HK11=80,7 · HK9=342,5 · HK10=278,4 · HK7=261,1 · HK5=119,9 · HK2=84,4 cm.

#### Cập nhật trang LK2 — chọn địa tầng hố khoan + §71 đầy đủ + công thức chi tiết

- **Chọn nguồn địa tầng:** selectbox "Nguồn địa tầng" = "LK2 (hồ sơ gốc)" hoặc hố khoan 6 vùng KE (mặc định **KE-HK2** thay LK2 gốc). `build_geology_from_bh(bh, sublayer_m=2.0)` dựng SubLayer từ DB (mẫu lab gần nhất; thiếu → mượn TB lớp theo vùng §15). **Es = 250·Cu** (Mesri & Olson).
- **S2 đầy đủ §71 khi dùng địa tầng hố khoan:** `compute_lk2(inp, geo, sand_elastic=True, extend_below_bh=True)` —
  (1) cắt vùng ảnh hưởng Δσ ≥ 10%·σ'v0 (`INFLUENCE_STOP_RATIO=0.10`, áp cả mode Excel);
  (2) lớp cát + sét chặt (Cc=0) → lún đàn hồi Si=Δσ·h/E;
  (3) mở rộng dưới đáy hố khoan (thông số lớp cuối, tối đa 80m) tới đáy vùng ảnh hưởng.
  **Mặc định cờ TẮT (Excel-faithful) → 23 golden test pass.** Trang bật cờ khi chọn hố khoan.
- **ui_defaults** trong JSON: D=0,8 · S=1,8 · CD1=0,8 · CD2=−25,2 · P=40,8 · q=55,8 · W=100 · θ=60 · MNN=0 · dv=0,4. Page đọc làm mặc định (không đụng scalars golden).
- **Công thức chi tiết hiển thị (LaTeX, thay số):** mục A (S=Sblock+Sc, σ'v0 xét MNN, nhánh OC/NC/cross + đàn hồi), mục B (N=q·s², N_vl=qa·Ap, N_đn=α·Ap·qp+πD·qsi·L, σ_col, P_col, Q_ult.vl/đn AIT, Q_a), mục D (M_tt=q(S−d)²/8, V_tt, [σ]=0,63√f'c, Z_se, M_r, V_r).
- **Biểu đồ mục A:** (1) minh họa S₁/S₂ qua các lớp đất (dải màu lớp + cọc + vùng S₁/S₂ + đường mũi cọc + **đáy vùng ảnh hưởng**); (2) ứng suất σ'v0/Δσ/10%·σ'v0 + ranh giới lớp + tải đắp + đáy vùng ảnh hưởng. **Bảng + biểu đồ giới hạn đến đáy vùng ảnh hưởng 10%.**
- **Tải:** lún (Sblock+Sc) dùng P tĩnh; SCT + kiểm toán BT dùng q tổng (caption ghi rõ từng mục).

#### Trang "Lún nền chưa xử lý" — chọn hố QTT trong bảng chi tiết

Mục "Bảng chi tiết từng phân tố" (chế độ Theo bảng 6 vùng) cho chọn cả hố **QTT (ND-*)**: tính on-demand `settle_avg` (H_đắp=CĐTK 2,70 − CĐTN), dùng chung định dạng bảng + biểu đồ + công thức.

#### UI toàn cục (app_cdm.py)

- **Font body = Calibri** (fallback Segoe UI/Arial); giữ KaTeX + icon. Rule 15 §64.
- **Bảng st.table:** tiêu đề in đậm + lưới kẻ đậm (viền 1px #333/#444) + `@media print` viền đen — in ra rõ như Word. Rule 4 §64.
- **Biểu đồ:** nhãn giá trị + cỡ chữ 12pt cho cả legend. Rule 14 §64.
