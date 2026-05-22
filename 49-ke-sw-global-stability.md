# 49 — Ổn định Tổng thể Tường Cừ SW + CDM

**Mục đích:** Tài liệu chuẩn bị cho **3 kiểm tra ổn định tổng thể** của hệ kè cọc ván SW + nền CDM gia cố. Áp dụng cho dự án 202605‑TTHC (Kè Công Viên Trung Tâm).

**3 kiểm tra trong scope (chốt 2026‑05‑20):**
1. **Trượt cung tròn tổng thể qua dưới chân cừ** (Bishop / Spencer LE)
2. **Lật quanh chân cừ** (ΣM)
3. **Xoay nhổ chân cừ — toe kick‑out** (Free Earth Support, Mp ≥ Ma)

**Không trong scope (có thể bổ sung sau):**
- Trượt phẳng đáy hố đào (sliding)
- Đẩy trồi đáy đào (basal heave)

**Phạm vi:**
- Tường cọc ván SW DUL (BETON 6 catalog)
- Nền sét chảy gia cố CDM (xi măng đất)
- Quy ước Front/Back theo CLAUDE.md §20

**File liên quan (sẽ tạo):**
- Engine: `scripts/sw_global_stability.py`
- Tham số: `data/sw_global_stability.json`
- UI: Tab "E. Ổn định tổng thể" trong `scripts/app_cdm.py`

**Tiêu chuẩn áp dụng:**
- TCVN 4253:2012 — Móng cọc + tường chắn — Tiêu chuẩn thiết kế
- TCVN 9362:2012 — Nền các công trình xây dựng — Tiêu chuẩn thiết kế
- TCVN 10304:2014 — Móng cọc — Tiêu chuẩn thiết kế
- TCVN 9403:2012 — Gia cố nền đất yếu — Phương pháp trụ đất xi măng
- FHWA‑NHI‑10‑034 (GEC‑13) — Drilled Shafts / Soldier Pile Walls
- USACE EM 1110‑2‑2504 — Design of Sheet Pile Walls
- Eurocode 7 (EN 1997‑1) — Geotechnical design

---

## 1. Tổng quan 3 kiểm tra trong scope

| # | Tên | Cơ chế phá hoại | $F_s$ min | Phương pháp | Module |
|---|---|---|:---:|---|:---:|
| 1 | **Trượt cung tròn tổng thể** | Cung qua dưới chân cừ, kéo cả khối đất + tường | 1,30 | Bishop / Spencer LE | ✓ slope_stability_tab.py (mở rộng) |
| 3 | **Lật quanh chân cừ** | Tường lật quanh điểm xoay tại chân | 2,00 | $\Sigma M$ | ✗ sw_global_stability.py (mới) |
| 5 | **Xoay nhổ chân cừ** | Cọc không đủ neo, mũi nhổ ra | 1,50 | Free Earth Support $M_p \geq M_a$ | ✗ sw_global_stability.py (mới) |

**Ngoài scope (tham khảo, có thể bổ sung sau):**
- #2 Trượt phẳng đáy hố đào ($F_s \geq 1{,}50$ — TCVN 9362)
- #4 Đẩy trồi đáy đào basal heave ($F_s \geq 1{,}50$ — Terzaghi/Bjerrum)

---

## 2. CDM Block — Thông số tổng hợp (composite)

Khi CDM gia cố nền phía Front, tính các thông số tổng hợp theo **TCVN 9403:2012 Phụ lục C** với hệ số diện tích thay thế $a = A_c / A_{\text{đơn vị}}$:

$$c_{\text{comp}} = (1 - a) \cdot c_{\text{soil}} + a \cdot c_{\text{col}}$$

$$\tan\varphi_{\text{comp}} = (1 - a) \cdot \tan\varphi_{\text{soil}} + a \cdot \tan\varphi_{\text{col}}$$

$$\gamma_{\text{comp}} = (1 - a) \cdot \gamma_{\text{soil}} + a \cdot \gamma_{\text{col}}$$

Trong đó:
- $a$ = tỷ lệ diện tích thay thế (thông thường 0,15–0,30 cho CDM dày)
- $c_{\text{col}} = q_u^{\text{field}} / 2$ ≈ 50–100 kPa (CDM xi măng điển hình)
- $\varphi_{\text{col}}$ ≈ 25–35° (cát hạt mịn của trụ CDM cứng hóa)
- $\gamma_{\text{col}}$ ≈ 18–20 kN/m³

**Vùng CDM block trong sơ đồ:**
- $z_{\text{cdm,top}}$ = mặt đất Front (sau khi đào fill)
- $z_{\text{cdm,bot}}$ = $z_{\text{cdm,top}} - (L_c - L_{\text{ngàm}})$

---

## 3. Kiểm tra #1 — Trượt cung tròn tổng thể (Bishop / Spencer)

### 3.1 Lý thuyết

Mặt trượt giả định dạng cung tròn tâm $(x_c, y_c)$, bán kính $R$, **đi qua chân cừ** (`pile_tip`).

**Bishop Simplified** (1955):

$$F_s = \frac{\sum \left[ (c_i' \, b_i + (W_i - u_i b_i) \tan\varphi_i') / m_{\alpha,i} \right]}{\sum W_i \sin\alpha_i}$$

với $m_{\alpha,i} = \cos\alpha_i + \dfrac{\sin\alpha_i \tan\varphi_i'}{F_s}$ — giải lặp Picard.

**Spencer** (1967): thêm cân bằng moment giữa các slice → chính xác hơn ~5–10 % vs Bishop, đặc biệt khi đất phi tuyến.

### 3.2 Nguyên tắc dự án

- **Mọi cung trượt phải đi qua chân cừ**: $R_i = \sqrt{x_c^2 + (y_c - z_{\text{tip}})^2}$
- Grid search $(x_c, y_c)$ với:
  - $x_c \in [-1{,}5 \cdot \text{slope\_x}, \; 0{,}5 \cdot L]$
  - $y_c \in [z_{\text{top}}, \; z_{\text{top}} + L]$
  - $n_x = n_y = 8$ (mặc định) → 64 mặt trượt thử
- $n_{\text{slices}}$ = 30
- Mặt đất: nếu $h_{\text{fill}} > 0$ → ramp 1:slope_ratio (mặc định 1:2)
- Bao gồm vùng CDM (composite phi, c, gamma)

### 3.3 Tiêu chí

| Điều kiện | $F_s$ min |
|---|:---:|
| Thường xuyên (TCVN 4253) | **1,30** |
| Thi công (TCVN 4253) | 1,20 |
| Có động đất (kh ≥ 0,1) | 1,10 |

---

## 4. Kiểm tra #3 — Lật quanh chân cừ

### 4.1 Lý thuyết

Tường lật quanh điểm xoay tại chân cừ (gần `pile_tip` hoặc tại điểm áp lực thuần = 0).

$$F_s = \frac{\Sigma M_{\text{giữ}}}{\Sigma M_{\text{lật}}}$$

- **$M_{\text{lật}}$**: moment do $P_a$ (Active phía Front) + $P_{w,\text{front}}$ (nước Front) + tải mặt $q$ + Boussinesq
- **$M_{\text{giữ}}$**: moment do trọng lượng tường + đất đắp + $P_{p,\text{back}}$ (Passive phía Back) + ma sát chân cừ

Tay đòn $z_a, z_p, z_W$ đo từ tâm xoay (chân cừ).

### 4.2 Tác dụng CDM

CDM phía Front có $c_{\text{comp}}$ cao → giảm $P_a$ → giảm $M_{\text{lật}}$.
CDM phía Back (nếu có) tăng $K_p \cdot \sigma'_v$ → tăng $P_p$ → tăng $M_{\text{giữ}}$.

### 4.3 Tiêu chí

$$F_s \geq 2{,}00$$ (FHWA GEC‑13 cho cantilever; có thể giảm 1,75 nếu có anchor / headwall)

---

## 5. Kiểm tra #5 — Xoay nhổ chân cừ (Toe Kick‑Out)

### 5.1 Lý thuyết — Free Earth Support (FES) Method

Cọc cantilever đủ ngàm dưới đáy đào để moment bị động $M_p$ phía dưới cân bằng moment chủ động $M_a$ phía trên:

$$F_s = \frac{M_p}{M_a}$$

- **$M_a$**: tích phân áp lực chủ động × tay đòn từ chân cừ
- **$M_p$**: tích phân áp lực bị động × tay đòn từ chân cừ

Khi tường có headwall (pin top như mô hình Winkler) → support đỉnh giữ momen → tính theo **Fixed Earth Support**: cộng thêm phản lực headwall vào cân bằng. Anchor đỉnh giảm yêu cầu ngàm đáng kể.

### 5.2 Khác biệt với #3 Lật

| Đặc điểm | #3 Lật | #5 Toe Kick‑Out |
|---|---|---|
| Tâm xoay | Chân cừ (toe) | Chân cừ (toe) — FES |
| Tay đòn | Cả tường + đất đắp | **Chỉ phần trong đất** |
| Trọng lượng | Có (giữ) | Bỏ qua |
| Áp lực ngang | Active+Passive tổng | Active+Passive **tích phân theo chiều sâu** |
| Mục đích | Toàn khối lật ngang | Cọc bị nhổ mũi do thiếu ngàm |

#3 đánh giá ổn định tổng thể bao gồm cả trọng lượng; #5 đánh giá xem cọc có đủ chiều sâu ngàm để **không bị xoay nhổ mũi ra**.

### 5.3 Yêu cầu CDM

Vùng CDM phía Back dưới đáy đào (nếu có) tăng $K_p \cdot \sigma'_v$ → tăng $M_p$ → tăng $F_s$. Trong cấu hình kè TTHC hiện tại, CDM chủ yếu ở Front (giảm $P_a$, giảm $M_a$) → tăng $F_s$ qua đường giảm $M_a$.

### 5.4 Tiêu chí

$$F_s \geq 1{,}50$$ (USACE EM 1110‑2‑2504 cho FES; có thể nâng lên 2,0 cho Fixed Earth Support)

---

## 6. Quy trình tính toán

```text
Đầu vào (từ session_state app_cdm):
  - bh_name, Z_m, H_layer1_m, top_elev, surcharge_front
  - cdm_Lc, cdm_L_ngam, cdm_arrangement, cdm_D, cdm_qu, cdm_a (area ratio)
  - pile_name, pile_L
  - Layers Front/Back từ SQLite

Bước 1: Tính composite CDM (TCVN 9403 Phụ lục C)
  → φ_comp, c_comp, γ_comp cho khối CDM phía Front

Bước 2: Build SlopeGeometry cho slope_stability engine
  - Surface points = mặt đất Front (có ramp) + đỉnh kè + mặt đất Back
  - Soil layers = fill + CDM (composite) + lớp 1 sét + lớp 2b sand
  - GWT points = mực nước
  - Surcharge = surcharge_front

Bước 3 — KIỂM TRA #1: Trượt cung tròn (Bishop + Spencer)
  - Mọi cung qua chân cừ (pile_tip)
  - Grid search 8×8 (xc, yc)
  - Trả Fs_critical, (xc, yc, R) nguy hiểm nhất
  - Tiêu chí: Fs ≥ 1.30

Bước 4 — KIỂM TRA #3: Lật quanh chân cừ
  - Tích phân Active phía Front + nước Front + surcharge → M_lật
  - Trọng lượng tường + đất đắp + Passive phía Back → M_giữ
  - Tay đòn đo từ pile_tip
  - Tiêu chí: Fs = M_giữ / M_lật ≥ 2.00

Bước 5 — KIỂM TRA #5: Xoay nhổ chân cừ (Toe kick-out FES)
  - Tích phân áp lực (Active, Passive) theo chiều sâu quanh pile_tip
  - M_a = ∫ σ_a(z) × (z_tip − z) dz
  - M_p = ∫ σ_p(z) × (z_tip − z) dz  (chỉ vùng dưới đáy đào)
  - Tiêu chí: Fs = M_p / M_a ≥ 1.50

Bước 6: Tổng hợp
  - return SWStabilityResult(
        Fs_global_slip, Fs_overturning, Fs_toe_kickout,
        critical_xc, critical_yc, critical_R, ...)
```

---

## 7. Cấu trúc dữ liệu Python (skeleton)

```python
from dataclasses import dataclass, field
import math


@dataclass
class CDMBlock:
    """Khối CDM gia cố phía Front — composite theo TCVN 9403 Phụ lục C."""
    top_elev: float
    bot_elev: float
    area_ratio_a: float       # 0.15–0.30
    c_col_kPa: float = 75.0   # qu/2
    phi_col_deg: float = 30.0
    gamma_col_kNm3: float = 19.0

    def composite_with(self, soil_lay):
        """Trả EarthLayer composite TCVN 9403 từ soil_lay + CDM."""
        a = self.area_ratio_a
        c = (1 - a) * soil_lay.c + a * self.c_col_kPa
        tan_phi = ((1 - a) * math.tan(math.radians(soil_lay.phi))
                  + a * math.tan(math.radians(self.phi_col_deg)))
        phi = math.degrees(math.atan(tan_phi))
        gamma = (1 - a) * soil_lay.gamma + a * self.gamma_col_kNm3
        gamma_sub = gamma - 9.81
        return EarthLayer(soil_lay.tip_elev, gamma, gamma_sub, phi, c)


@dataclass
class SWStabilityResult:
    """Kết quả 3 kiểm tra ổn định tổng thể."""
    Fs_global_slip:   float       # #1 Bishop/Spencer
    Fs_overturning:   float       # #3 Lật quanh chân cừ
    Fs_toe_kickout:   float       # #5 FES toe kick-out

    # Chi tiết
    critical_xc:      float = 0.0
    critical_yc:      float = 0.0
    critical_R:       float = 0.0
    M_lat:            float = 0.0   # M_lật (Σ moment lật)
    M_giu:            float = 0.0   # M_giữ
    Ma_fes:           float = 0.0   # M_a tích phân theo z
    Mp_fes:           float = 0.0   # M_p tích phân theo z

    method:           str = "bishop"
    warnings:         list = field(default_factory=list)

    # Ngưỡng (configurable per TCVN/FHWA)
    FS_MIN_GLOBAL:    float = 1.30
    FS_MIN_OVERTURN:  float = 2.00
    FS_MIN_TOE:       float = 1.50

    @property
    def all_pass(self) -> bool:
        return (self.Fs_global_slip >= self.FS_MIN_GLOBAL and
                self.Fs_overturning >= self.FS_MIN_OVERTURN and
                self.Fs_toe_kickout >= self.FS_MIN_TOE)

    def summary_table(self) -> list[dict]:
        return [
            {"check": "#1 Trượt cung tròn", "Fs": self.Fs_global_slip,
             "Fs_min": self.FS_MIN_GLOBAL,
             "pass": self.Fs_global_slip >= self.FS_MIN_GLOBAL},
            {"check": "#3 Lật quanh chân cừ", "Fs": self.Fs_overturning,
             "Fs_min": self.FS_MIN_OVERTURN,
             "pass": self.Fs_overturning >= self.FS_MIN_OVERTURN},
            {"check": "#5 Xoay nhổ chân cừ", "Fs": self.Fs_toe_kickout,
             "Fs_min": self.FS_MIN_TOE,
             "pass": self.Fs_toe_kickout >= self.FS_MIN_TOE},
        ]


# ─── 3 hàm kiểm tra riêng biệt ─────────────────────────────────────────────

def check_global_slip(geom, front_layers, back_layers, fill, cdm,
                      pile, surcharge=0.0, method="bishop",
                      nx=8, ny=8, n_slices=30) -> tuple[float, float, float, float]:
    """#1 — Trượt cung tròn qua chân cừ.

    Returns (Fs, xc_critical, yc_critical, R_critical).
    Reuse slope_stability_tab engine + composite CDM layer.
    """
    ...


def check_overturning(geom, front_layers, back_layers, fill, cdm, pile,
                      surcharge=0.0) -> tuple[float, float, float]:
    """#3 — Lật quanh chân cừ.

    Returns (Fs, M_lật, M_giữ).
    - M_lật = ∫ σ_a × (z - z_tip) dz (Front, qua tay đòn từ chân cừ)
    - M_giữ = W_tường × x_tâm + ∫ σ_p × tay đòn dz (Back)
    """
    ...


def check_toe_kickout(geom, front_layers, back_layers, fill, cdm, pile,
                      surcharge=0.0, has_anchor=False) -> tuple[float, float, float]:
    """#5 — Toe kick-out theo Free Earth Support.

    Returns (Fs, Ma_total, Mp_total).
    - Ma = ∫ σ_a(z) × (z_tip - z) dz từ đỉnh đến chân cừ
    - Mp = ∫ σ_p(z) × (z_tip - z) dz chỉ vùng dưới đáy đào
    - has_anchor=True → Fixed Earth Support: cộng phản lực anchor
    """
    ...


def check_sw_overall_stability(
    geom, front_layers, back_layers, fill=None, cdm=None, pile=None,
    method="bishop", surcharge_front=10.0, kh_seismic=0.0,
) -> SWStabilityResult:
    """Wrapper chạy cả 3 kiểm tra → SWStabilityResult.

    Args:
        geom: WallGeometry (top_elev, soil_level_front/back, water_elev...)
        front_layers / back_layers: list[EarthLayer]
        fill: EarthLayer | None — đất đắp Front
        cdm: CDMBlock | None — khối CDM gia cố
        pile: PileProps — thông số cọc SW
        method: 'bishop' | 'spencer' cho #1
        surcharge_front: tải hoạt phía Front (kPa)
        kh_seismic: hệ số động đất ngang (mặc định 0)

    Returns:
        SWStabilityResult với 3 Fs + critical surface info
    """
    Fs1, xc, yc, R = check_global_slip(
        geom, front_layers, back_layers, fill, cdm, pile,
        surcharge=surcharge_front, method=method)
    Fs3, Ml, Mg = check_overturning(
        geom, front_layers, back_layers, fill, cdm, pile,
        surcharge=surcharge_front)
    Fs5, Ma, Mp = check_toe_kickout(
        geom, front_layers, back_layers, fill, cdm, pile,
        surcharge=surcharge_front)
    return SWStabilityResult(
        Fs_global_slip=Fs1, Fs_overturning=Fs3, Fs_toe_kickout=Fs5,
        critical_xc=xc, critical_yc=yc, critical_R=R,
        M_lat=Ml, M_giu=Mg, Ma_fes=Ma, Mp_fes=Mp,
        method=method,
    )
```

---

## 8. Tham chiếu

- TCVN 4253:2012 — Móng cọc và tường chắn
- TCVN 9362:2012 — Nền các công trình xây dựng
- TCVN 9403:2012 — Phụ lục C — Trụ đất xi măng
- FHWA‑NHI‑10‑034 — GEC‑13 — Drilled Shafts
- USACE EM 1110‑2‑2504 — Sheet Pile Walls
- Bishop (1955) — *The use of the slip circle in slope stability analysis*
- Spencer (1967) — *A method of analysis of slopes with parallel inter‑slice forces*
- Terzaghi (1943) — *Theoretical Soil Mechanics* (Chapter on Basal Heave)
- Duncan & Wright (2005) — *Soil Strength and Slope Stability*
- File hệ thống: [scripts/slope_stability_tab.py](scripts/slope_stability_tab.py) (đã có)
- File hệ thống: [data/slope_stability.json](data/slope_stability.json) (đã có)
- Module mới sẽ tạo: `scripts/sw_global_stability.py` + tab "E" trong `app_cdm.py`
