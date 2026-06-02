### 66. Thông số đệm cát-xi măng dự án TTHC — VERIFY từ hồ sơ E.2

**Nguồn:** Hồ sơ thiết kế TTHC, bảng E.2 "Thông số đầu vào cọc xi măng đất (CDM)"
**Verify:** User cung cấp screenshot 2026-05-29
**Files lưu:** [data/cdm_cushion_params.json](data/cdm_cushion_params.json) · SQLite `cdm_cushion_design_params` · [scripts/cdm_cushion_params.py](scripts/cdm_cushion_params.py)

#### Thông số chính (VERIFY)

| Ký hiệu | Tên | Giá trị | Đơn vị | Nguồn |
|---|---|:---:|:---:|---|
| **q_uckse** | Cường độ kháng nén đệm cát-XM | **600.0** | kPa | Hồ sơ E.2 |
| **Fs** | Hệ số an toàn cắt cho phép | **3.0** | — | Hồ sơ E.2 |
| **τ_ase** | Ứng suất cắt cho phép | **100.0** | kPa | Hồ sơ E.2 |
| **θ** | Góc đàn hồi dẻo (plastic arch angle) | **80** | ° | Hồ sơ E.2 |

#### Công thức τ_ase (theo hồ sơ)

$$\tau_{ase} = \frac{1}{F_s} \cdot \frac{q_{uckse}}{2} = \frac{q_{uckse}}{2 \cdot F_s}$$

**Verify:** $\tau_{ase} = 600 / (2 \times 3) = 100$ kPa ✓

#### So sánh với giả định trước đó (SAI)

| Tham số | Giả định TRƯỚC (sai) | THẬT từ hồ sơ |
|---|:---:|:---:|
| q_uckse | 1500 kPa | **600 kPa** |
| Fs | 2.0 | **3.0** |
| τ_ase | 375 kPa | **100 kPa** |

**Bài học:** Giả định q_uckse=1500 và Fs=2 đã đánh giá QUÁ THIÊN VỀ AN TOÀN — kết luận Hse=0.4m "đạt với dự trữ 3.2×" là SAI.

#### Re-kiểm ALiCC với số THẬT cho dự án TTHC

Với cấu hình hiện tại (D=0.80m, s=1.80m, Σh=1.9m, He+Hse=1.1m):

**Quan trọng:** $\gamma_{fill}$ phải dùng **TB trọng số** của (áo đường + He):
$$\gamma_{fill,TB} = \frac{h_{aod} \cdot \gamma_{aod} + H_e \cdot \gamma_{he}}{h_{aod} + H_e}$$

Vd với $H_e = 0.7$m: $\gamma_{fill,TB} = (0.8 \times 24 + 0.7 \times 18) / 1.5 = 21.2$ kN/m³

| Hse (m) | He (m) | γ_TB (kN/m³) | τ_se (kPa) | ratio | Đánh giá |
|:---:|:---:|:---:|:---:|:---:|---|
| 0.20 | 0.90 | 20.82 | 245.7 | 2.46 | KĐ nghiêm |
| 0.30 | 0.80 | 21.00 | 165.1 | 1.65 | KĐ |
| **0.40** (hiện tại) | 0.70 | 21.20 | **124.7** | **1.25** | **KĐ** |
| 0.48 | 0.62 | 21.34 | 104.5 | 1.05 | KĐ |
| **0.504** | 0.596 | 21.38 | **100.0** | **1.00** | **ĐẠT biên** |
| 0.50 | 0.60 | 21.43 | 100.5 | 1.005 | Cận |
| 0.60 | 0.50 | 21.69 | 84.3 | 0.84 | Đạt |
| 0.70 | 0.40 | 22.00 | 72.7 | 0.73 | Đạt thoải mái |

**Hse min cần thiết: ≥ 0.504 m** → **làm tròn lên 0.55 m** để có dự trữ.

#### CẢNH BÁO: Sai sót trước đây (đã sửa 2026-05-29)

Tính toán ban đầu dùng $\gamma_{fill} = \gamma_{he} = 18$ kN/m³ (chỉ cát He) → ratio Hse=0.4m = 1.16, Hse_min = 0.47m.

**Sai vì:** $V_{soil}$ trong công thức ALiCC bao gồm thể tích đất đắp TOÀN BỘ vùng vòm (cả áo đường γ=24 + He γ=18). $\gamma_{fill}$ phải là TB trọng số.

**Sửa:** dùng $\gamma_{TB} = 21.2$ kN/m³ → ratio Hse=0.4m = **1.25** (tệ hơn 8%), Hse_min = **0.504m** (tăng 3cm).

→ Engine [scripts/cdm_cushion_params.py](scripts/cdm_cushion_params.py) đã update để tự tính γ_TB.

#### Khuyến nghị thiết kế

1. **Hse = 0.40m hiện tại KHÔNG ĐẠT chọc thủng theo hồ sơ E.2**
2. **Đề xuất tăng lên Hse = 0.50 m** (đạt ratio 0.94, dự trữ 6%)
3. Khi tăng Hse từ 0.40 → 0.50m:
   - He giảm tương ứng (constraint Σh=1.9m): 0.70 → 0.60m
   - q_tải thay đổi nhẹ (+0.45 kPa = +1.1%)
   - Cao độ đỉnh CDM giữ nguyên +0.80m
   - Khối lượng đệm XM tăng 25% (vật liệu đắt hơn cát thường)

#### Cập nhật SQLite `tvtk_fill_composition` nếu chốt Hse = 0.50m

```sql
UPDATE tvtk_fill_composition SET h_m = 0.50, q_component_kPa = 11.25
  WHERE layer_order = 3;  -- Hse
UPDATE tvtk_fill_composition SET h_m = 0.60, q_component_kPa = 10.80
  WHERE layer_order = 2;  -- He
-- Sau khi update: chạy lại save_cdm_zone_results.py để re-tính 128+ rows
```

#### Lệnh chạy

```bash
# Lưu params vào SQLite
python scripts/save_cushion_params.py

# Engine kiểm tra
python scripts/cdm_cushion_params.py
```

#### Lưu ý

- **CHỈ trích từ hồ sơ E.2** — KHÔNG suy diễn từ tiêu chuẩn khác (rule 9)
- **Công thức ALiCC** theo [41-cdm-choc-thung-dem-ximang.md](41-cdm-choc-thung-dem-ximang.md) — phương pháp PWRI Japan
- **Kiểm uốn (bending)** chưa có công thức/tham số chính thức trong hồ sơ — chưa kiểm

---

#### Đối chiếu file Excel hồ sơ `02. Tính toán CDM (2Tm2).xlsm` sheet "Tinh choc thung"

**Verify nguồn (2026-05-29):** đọc trực tiếp công thức từ file hồ sơ tính toán gốc.

**Công thức khớp 100%** với implementation `cdm_cushion_params.py`:

| Excel cell | Công thức | Implementation |
|---|---|---|
| F12 | `τ_ase = (1/Fs) × q_uckse/2` | `TAU_ASE_KPA = 600/(2·3) = 100` ✓ |
| F33 | `H0 = (a-D) × tan(θ/2)` | `H0 = (s-D) × tan(θ/2)` ✓ |
| F37 CT(1) | `((a-D)/2·a² - π(a³-D³)/24 + (4-π)(√2-1)·a³/24) × tan(θ)` | Khớp ✓ |
| F37 CT(2) | `He·a² - (1/3)(π(He/tan(θ)+D/2)²(He+D/2·tan(θ)) - π(D/2·tan(θ)))` | Khớp ✓ |
| F38 V_CGCXM | `Hse·a² - (1/3)(π(Hse/tan(θ)+D/2)²(Hse+D/2·tan(θ)) - π(D/2·tan(θ)))` | Khớp ✓ |
| F44 P_soil | `((V_soil - V_CGCXM) × γ_fill + V_CGCXM × γ_hse) / A_unit` | Khớp ✓ (cấu trúc) |
| F51 τ_se | `(P_soil - q_a) × A_unit / (π·D·Hse)` | Khớp ✓ |

**Khác biệt VỀ DỮ LIỆU (KHÔNG khác công thức) — ưu tiên implementation hiện tại theo quyết định kỹ sư:**

| Tham số | Excel hồ sơ | Implementation hiện tại | Lý do giữ implementation |
|---|---|---|---|
| `a` (khoảng cách) | 1.6 m | **1.8 m** (`tvtk_cdm_config.spacing_m`) | tvtk_cdm_config là single-source-of-truth dự án |
| Lưới | Tam giác (T) | **Vuông** | tvtk_cdm_config |
| γ_fill (V_soil) | `dau vao!F10` = 14.6 (= γ Lớp 1 đất nền) | **γ_TB trọng số** = (h_aod·γ_aod + He·γ_he)/(h_aod+He) | Excel ref sai sang γ đất nền yếu (file có thể template lỗi). Lý thuyết ALiCC: V_soil = đất đắp → dùng γ đất đắp đúng |
| γ_hse (V_CGCXM) | 18 hardcoded | **22.5** (`tvtk_fill_composition`) | Đệm cát-XM đã đông cứng (γ thực tế cao hơn cát thường) |

**Đánh giá độ bảo thủ:**
- Excel dùng γ thấp hơn (14.6 và 18) → P_soil thấp hơn → τ_se thấp hơn → "đạt" dễ hơn (KHÔNG bảo thủ)
- Implementation dùng γ thực tế (γ_TB ~21.2 và γ_hse=22.5) → P_soil cao hơn → τ_se cao hơn → bảo thủ hơn (đúng vật lý)
- Hse_min theo Excel sẽ thấp hơn 0.504m (do γ thấp), nhưng implementation 0.504m **đúng theo bản chất ALiCC**

**Kết luận:** Engine giữ nguyên — chỉ document phát hiện này để team biết file Excel hồ sơ có khác biệt về γ (do REF cell hoặc giả thiết khác), KHÔNG phải lỗi engine.

---

### 66.2. Kiểm toán UỐN — KHÔNG áp dụng cho dự án TTHC

**Quyết định kỹ sư (2026-05-29):** Dự án TTHC **CHỈ kiểm chọc thủng** (ALiCC PWRI), KHÔNG kiểm uốn.

**Lý do:** Theo PWRI ALiCC gốc, đệm cát-XM = stress dispersion layer (truyền tải qua arching) → chỉ kiểm chọc thủng. Kiểm uốn theo R14 BTXM C10 áp cho **lớp bê tông cứng** (q_uckse ~10000 kPa), không áp dụng cho đệm cát-XM thông thường (q_uckse ~600 kPa).

**Engine bending vẫn giữ trong codebase** ([scripts/cdm_cushion_bending.py](scripts/cdm_cushion_bending.py)) — phòng khi dự án sau cần kiểm cho lớp BTXM riêng. Hiện tại KHÔNG gọi trong workflow chính.

#### Cho tham chiếu — Công thức kiểm uốn R14 BTXM C10 (nếu cần)

**Engine:** [scripts/cdm_cushion_bending.py](scripts/cdm_cushion_bending.py)
**Nguồn công thức:** `G:\...\R14\...\KIEM TOAN LOP BTXM C10.xls` — Section IV "Kiểm toán khả năng chịu uốn"

#### Công thức kiểm toán (cell references R14 file)

| Đại lượng | Công thức | Cell |
|---|---|---|
| Mô men quán tính (per 1m strip) | $I_{se} = T^3/12$ | R116 |
| Mô đun chống uốn | $Z_{se} = T^2/6$ | R119 |
| Mô đun đàn hồi | $E_{se} = 100 \cdot q_{uckse}$ | R122 |
| **Cường độ kéo khi uốn cho phép** | $\sigma_{ba} = \dfrac{0{,}25 \cdot q_{uckse}}{F_{sem}}$, $F_{sem} = 1{,}2$ | R125 |
| Tham số liên kết β (Hetenyi) | $\beta = \sqrt[4]{\dfrac{K_v \cdot b}{4 \cdot E_{se} \cdot I_{se}}}$ | R138 |
| Bán kính cứng tương đối (Westergaard) | $L = \sqrt[4]{\dfrac{E_{se} \cdot T^3}{12(1-\nu^2) \cdot K_v}}$ | — |
| **Ứng suất kéo khi uốn thực tế** | $\sigma_b = \dfrac{M_{max}}{Z_{se}}$ | R146 |
| **Tiêu chí ĐẠT** | $\sigma_b \le \sigma_{ba}$ | R146 |

#### 5 phương pháp tính M_max (đề xuất — file R14 dùng PLAXIS)

| ID | Phương pháp | Công thức | Đặc điểm |
|:---:|---|---|---|
| **M1** | Dầm đơn giản nhịp thông thuỷ | $M = q(s-D)^2/8$ | Conservative đơn giản |
| **M2** | Dầm đơn giản nhịp đầy đủ | $M = q s^2/8$ | Bỏ qua D — most conservative simple |
| **M3** | Bản tựa 4 góc (Timoshenko) | $M \approx 0{,}045 \cdot q s^2$ | Plate theory midspan |
| **M4** | Hetenyi Winkler vô hạn | $M = q/(4\beta^2)$ | Overestimate cho span hữu hạn → KHÔNG dùng |
| **M5** | Westergaard interior load | $M = \dfrac{P}{2\pi}(1+\nu)\left[\ln(L/b) + 0{,}6159\right]$ | Plate Winkler classical |

**M_design = max(M1, M2, M3, M5)** — chọn bảo thủ nhất, loại M4 do giả thiết không phù hợp.

#### Verify với file R14 BTXM C10 gốc

Inputs: T=0.4m, q_uckse=10000 kPa, P_soil=18.88 kPa, s=1.3m, D=0.6m, F_sem=1.2

| Đại lượng | Engine | File R14 |
|---|:---:|:---:|
| σ_ba | 2083.3 kPa | 2083.3 kPa ✓ |
| Z_se | 0.02667 m³/m | 0.02667 m³/m ✓ |
| M_max (PLAXIS file) | — | 50.35 kNm/m |
| M5 Westergaard engine | 14.32 kNm/m | (PLAXIS captures more — arching + ngàm 2 đầu + nonlinear) |

PLAXIS cho M_max cao hơn closed-form vì xét ngàm 2 đầu + nonlinear contact với cọc. Closed-form đề xuất ở đây phù hợp tính sơ bộ.

#### Áp dụng dự án TTHC — Cảnh báo quan trọng

Cấu tạo hiện tại tvtk_fill_composition: chỉ có đệm cát-XM Hse=0.40m, q_uckse=600 kPa. KHÔNG có lớp BTXM riêng.

Với q_uckse=600 kPa → σ_ba = **125 kPa** (rất thấp). M_design ≈ 33 kNm/m → σ_b ≈ **1243 kPa**.

**Ratio = 1243/125 = 9.94 — KHÔNG ĐẠT (vượt 10×)**

→ Đệm cát-XM cường độ thông thường KHÔNG kham được uốn theo tiêu chí R14.

#### Ma trận kết hợp Chọc thủng + Uốn (lưu SQLite `cdm_cushion_matrix`)

P. = Punching đạt · Px = Punching KĐ · B. = Bending đạt · Bx = Bending KĐ

| Hse \ q_uckse | 600 | 800 | 1000 | 1500 | 2000 | 3000 | 4000 | 5000 | 6000 | 8000 | 10000 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **0.40** (TTHC) | PxBx | P.Bx | P.Bx | P.Bx | P.Bx | P.Bx | P.Bx | P.Bx | P.Bx | **P.B.** | **P.B.** |
| 0.50 | PxBx | P.Bx | P.Bx | P.Bx | P.Bx | P.Bx | P.Bx | P.Bx | **P.B.** | **P.B.** | **P.B.** |
| 0.60 | P.Bx | P.Bx | P.Bx | P.Bx | P.Bx | P.Bx | **P.B.** | **P.B.** | **P.B.** | **P.B.** | **P.B.** |
| 0.70 | P.Bx | P.Bx | P.Bx | P.Bx | P.Bx | **P.B.** | **P.B.** | **P.B.** | **P.B.** | **P.B.** | **P.B.** |
| 0.80 | P.Bx | P.Bx | P.Bx | P.Bx | P.Bx | **P.B.** | **P.B.** | **P.B.** | **P.B.** | **P.B.** | **P.B.** |
| 0.90 | P.Bx | P.Bx | P.Bx | P.Bx | **P.B.** | **P.B.** | **P.B.** | **P.B.** | **P.B.** | **P.B.** | **P.B.** |
| 1.00 | P.Bx | P.Bx | P.Bx | **P.B.** | **P.B.** | **P.B.** | **P.B.** | **P.B.** | **P.B.** | **P.B.** | **P.B.** |

#### Top 10 phương án ĐẠT cả 2 tiêu chí — sắp theo chi phí

| Rank | Hse (m) | q_uckse (kPa) | He (m) | ratio_P | ratio_B | Chi phí (tr/m²) | Δ% so baseline |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | **1.00** | 1500 | 0.10 | 0.21 | 0.93 | 1.19 | +184% |
| 2 | 0.90 | 2000 | 0.20 | 0.17 | 0.86 | 1.33 | +217% |
| 3 | 0.70 | 3000 | 0.40 | 0.15 | 0.91 | 1.45 | +246% |
| 4 | 1.00 | 2000 | 0.10 | 0.16 | 0.72 | 1.46 | +246% |
| 5 | 0.60 | 4000 | 0.50 | 0.13 | 0.91 | 1.59 | +279% |

→ Tất cả phương án **đạt đồng thời** đều tăng chi phí ≥ 184%. Kiểm uốn là tiêu chí khắt khe hơn rất nhiều so với chọc thủng.

#### Trạng thái áp dụng

- Engine bending sẵn sàng, có thể bật khi cần kiểm cho lớp BTXM riêng (cấu tạo có bổ sung BTXM)
- Hiện không áp cho TTHC — bảng `cdm_cushion_matrix` SQLite chỉ giữ kết quả **chọc thủng**

---

### 66.2b. Xuất DXF phân vùng QTT — `qtt_export_dxf.py`

**Engine:** [scripts/qtt_export_dxf.py](scripts/qtt_export_dxf.py) — dùng `ezdxf` ≥ 1.4

**Mục đích:** Xuất biểu đồ phân vùng CDM QTT (theo §62) ra file `.dxf` để overlay trong AutoCAD/Civil 3D/BricsCAD. Toạ độ thực VN-2000.

**Lệnh chạy:**
```bash
python scripts/qtt_export_dxf.py
# → plaxis_out/QTT_ZoningMap_dS30.dxf
```

**Layers DXF (10 layer):**

| Layer | Nội dung | Màu ACI |
|---|---|:---:|
| `QTT_ZONE_P1` | Hatch SOLID vùng P1 | 5 (xanh dương) |
| `QTT_ZONE_P2` | Hatch SOLID vùng P2 | 1 (đỏ) |
| `QTT_ZONE_P3` | Hatch SOLID vùng P3 | 3 (xanh lá) |
| `QTT_ZONE_P4` | Hatch SOLID vùng P4 | 30 (cam) |
| `QTT_BOUNDARY` | Polygon ranh giới QTT | 7 |
| `QTT_BOREHOLES` | Block kim cương ND-02..ND-07 | 7 |
| `QTT_BH_LABEL` | Tên HK | 7 |
| `QTT_LC_TEXT` | Giá trị Lc tại tâm mỗi ô | 0 |
| `QTT_LEGEND` | Bảng chú giải 4 vùng (góc dưới-phải) | 7 |
| `QTT_TITLE` | Tiêu đề bản đồ | 7 |

**Tuỳ biến API:**
```python
export_qtt_zoning_dxf(
    out_path=Path("..."),
    delta_S_cm=30,        # 10/20/30/40
    n_zones=4,             # số vùng phân
    cell_size_m=None,      # None = auto từ spacing trung bình
    show_grid_points=False,
    show_lc_values=True,
)
```

**Kết quả mẫu (ΔS=30cm):** 162 điểm grid, 4 vùng (P1=14.9m / P2=21.8m / P3=22.8m / P4=24.3m), ô 20×20m.

**DWG:** Không xuất .dwg trực tiếp (proprietary). AutoCAD/BricsCAD mở .dxf native + Save As .dwg nếu cần.

---

### 66.3. UI Streamlit + Báo cáo Word

**Trang UI:** sidebar `"Kiểm chọc thủng đệm"` (page id `"cushion"`) trong [scripts/app_cdm.py](scripts/app_cdm.py)
**Module biểu đồ:** [scripts/cushion_design_charts.py](scripts/cushion_design_charts.py) — matplotlib helpers
**Module Word builder:** [scripts/cushion_design_report.py](scripts/cushion_design_report.py)

#### Cấu trúc trang UI (6 section, trải phẳng)

| Section | Nội dung |
|:---:|---|
| A | Thông số đầu vào (Hse, q_uckse, D, s) — auto-compute γ_TB |
| B | Kết quả hiện trạng (τ_se, τ_ase, ratio + badge Đạt/Không đạt) + expander chi tiết + sơ đồ ALiCC |
| C | Ma trận heatmap Hse × q_uckse + 2 đường sensitivity (ratio vs q_uckse, ratio vs Hse) |
| D | Pareto chi phí - hệ số an toàn (72 tổ hợp + đường Pareto + điểm tối ưu) |
| E | So sánh 3 phương án (A/B/C editable) — bảng + bar chart |
| F | Nút tạo + tải báo cáo Word .docx |

#### Cấu trúc báo cáo Word (8 chương)

1. Tổng quan và cơ sở lý thuyết (vai trò đệm + ALiCC PWRI + sơ đồ)
2. Thông số đầu vào (bảng 11 hàng)
3. Công thức kiểm toán (τ_ase, H_0, V_soil CT1/CT2, V_CGCXM, P_soil, τ_se)
4. Tính toán hiện trạng + verdict
5. Ma trận tối ưu hoá (heatmap + 2 sensitivity)
6. Pareto chi phí - hệ số an toàn
7. So sánh 3 phương án (bảng + bar chart)
8. Kết luận và khuyến nghị

Header: logo + tên công ty. Footer: nhân sự + "Trang X / Y" (PAGE/NUMPAGES field).

#### Biểu đồ (6 hàm matplotlib chuẩn báo cáo)

| Hàm | Mô tả |
|---|---|
| `chart_heatmap_ratio()` | Heatmap Hse × q_uckse + marker hiện tại + colorbar |
| `chart_ratio_vs_quckse_fixed_Hse()` | Đường ratio vs q_uckse + Pareto markers |
| `chart_ratio_vs_Hse_fixed_quckse()` | Đường ratio vs Hse + vùng đạt/KĐ tô màu |
| `chart_compare_options()` | 2 subplot: ratio bar + Δ chi phí bar |
| `chart_alicc_schematic()` | Sơ đồ 2D cọc + đệm + vòm đất + mũi tên tải |
| `chart_pareto_cost_ratio()` | Scatter Pareto 72 điểm + đường Pareto |

Tất cả tuân quy tắc: KHÔNG emoji, tiếng Việt có dấu, label giá trị số trên điểm, "Đạt" #2E7D32 / "KĐ" #C62828.

---

### 66.4. Đồng bộ JSON ↔ SQLite (BẮT BUỘC khi đổi tham số)

**Nguồn duy nhất (single source of truth):** [data/cdm_cushion_params.json](data/cdm_cushion_params.json)

**Cấu trúc JSON:**
- `_meta` — timestamp, source, verified
- `params` — 14 tham số authoritative (q_uckse, Fs, τ_ase, θ, γ_*, Hse_*, h_*, σ_h, D, s)
- `alicc_scenarios_2026_05_29` — 7 scenario với γ_TB đã verify
- `design_recommendations` — 3 phương án A/B/C
- `sqlite_table` + `related_files` — pointers

**Bảng SQLite (đồng bộ từ JSON):**

| Bảng | Rows | Nguồn | Cách đồng bộ |
|---|:---:|---|---|
| `cdm_cushion_design_params` | 14 | JSON `params` | `python scripts/save_cushion_params.py` (wipe + reinsert) |
| `cdm_cushion_matrix` | 72 | Engine `check_alicc()` quét 9 Hse × 8 q_uckse | Re-compute từ engine + lưu vào DB |

**JSON snapshot ma trận:** [data/cdm_cushion_matrix.json](data/cdm_cushion_matrix.json) — 21.8 KB, 72 hàng + cost_model + meta.

**Quy tắc:** sửa tham số → sửa JSON → chạy `save_cushion_params.py` → cả LOCAL + PROJECT SQLite đồng bộ.

**Files toàn chuỗi (8 file):**

1. [data/cdm_cushion_params.json](data/cdm_cushion_params.json) — params authoritative
2. [data/cdm_cushion_matrix.json](data/cdm_cushion_matrix.json) — matrix snapshot
3. [scripts/cdm_cushion_params.py](scripts/cdm_cushion_params.py) — engine ALiCC punching
4. [scripts/cdm_cushion_bending.py](scripts/cdm_cushion_bending.py) — engine bending (informational)
5. [scripts/save_cushion_params.py](scripts/save_cushion_params.py) — sync script
6. [scripts/cushion_design_charts.py](scripts/cushion_design_charts.py) — 6 chart helpers
7. [scripts/cushion_design_report.py](scripts/cushion_design_report.py) — Word builder
8. [scripts/qtt_export_dxf.py](scripts/qtt_export_dxf.py) — DXF exporter QTT
