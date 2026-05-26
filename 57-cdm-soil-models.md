# 57 — Mô hình constitutive cho đất gia cố xi măng (CDM/XMD)

**Phiên bản:** 2026-05-25 · Áp dụng cho PLAXIS 2D 2024.2 + UDSM
**Phạm vi:** Trụ đất xi măng (Cement Deep Mixing — CDM) trong dự án TTHC
**Tài liệu liên kết:**
- [39-tcvn9403-tru-dat-xi-mang.md](39-tcvn9403-tru-dat-xi-mang.md) — TCVN 9403:2012 chi tiết
- [41-cdm-choc-thung-dem-ximang.md](41-cdm-choc-thung-dem-ximang.md) — kiểm tra chọc thủng
- [56-plaxis-soil-models-application.md](56-plaxis-soil-models-application.md) — bảng mô hình Plaxis tổng quát
- [scripts/cdm_column_calc.py](scripts/cdm_column_calc.py) — engine analytical TCVN 9403
- [data/tcvn9403_params.json](data/tcvn9403_params.json) — tham số mặc định

---

## 1. Bản chất vật liệu CDM và lý do KHÔNG dùng mô hình đất thông thường

Đất gia cố xi măng (Cement-Treated Soil — CTS) là **vật liệu composite** tạo từ phản ứng hydrate giữa xi măng Portland và đất sét/cát tự nhiên. Sau 28 ngày dưỡng hộ, hành vi cơ học khác biệt hoàn toàn với đất nguyên trạng:

| Đặc tính | Đất sét nguyên trạng | Đất gia cố xi măng (qu = 0,8–2 MPa) |
|---|---|---|
| Cường độ nén nở hông $q_u$ | 30–120 kPa | **800–2 000 kPa** (× 10–60 lần) |
| Mô-đun biến dạng $E$ | 3–15 MPa | **40–200 MPa** (× 10) |
| Lực dính $c$ | 5–30 kPa | **400–1 000 kPa** |
| Hành vi sau peak | Dẻo (ductile) | **Giòn (brittle) — strain softening** |
| Tỉ số $E/q_u$ | ~50–200 | **50–200** (vẫn vậy) |
| Tỉ số $q_t/q_u$ (tension/compression) | ~0,1 | **0,10–0,15** — quan trọng |
| OCR | 1–3 | Không áp dụng — có **bonding** thay vì stress history |

**Hệ quả khi mô hình hóa:**

1. **Mô hình MC thuần** áp dụng cho CDM thì $\varphi = 0$ → mất khả năng kháng cắt theo $\sigma_n$ tăng → kết quả ổn định mái dốc / chọc thủng sai.
2. **Cần tension cut-off** — đất gia cố xi măng có cường độ kéo $q_t \approx 0{,}1 q_u$, nhưng MC mặc định cho tension vô hạn → khi tải gần biên cọc, ứng suất kéo phi lý xuất hiện → tường vây / cừ bị "kéo lên" sai.
3. **Hành vi giòn (brittle)** không tự nhiên trong MC/HS — sau peak cường độ tụt nhanh, cần **strain softening** hoặc **damage model**.
4. **Bonding** (liên kết xi măng) làm yield surface lớn hơn đất gốc → mô hình Cam-Clay thông thường không reproduce được, cần **Structured Cam-Clay** hoặc **Bonded Soft Soil**.

---

## 2. Hai hướng tiếp cận tổng quát

### 2.1 Composite Homogenization — vùng CDM = vật liệu composite tương đương

Quy đổi cả vùng CDM (cọc + đất xen kẽ) thành **một material đồng nhất** với thông số trung bình theo tỉ lệ diện tích thay thế $a = A_{col} / A_{unit}$.

**Mô-đun composite (TCVN 9403 Phụ lục C):**

$$E_{\text{comp}} = a \cdot E_c + (1 - a) \cdot E_s$$

**Cường độ cắt composite (TCVN 9403 Phụ lục B):**

$$c_{uu,\text{comp}} = a \cdot c_{col} + (1 - a) \cdot c_{u,\text{soft}}$$

**Áp dụng:**
- **TKCS** — tính lún sơ bộ, không cần biết chi tiết phân bố ứng suất trong từng cọc.
- **Phân tích 2D đường dài** (kè KE) — khi không thể vẽ từng cọc 800mm trong mô hình rộng 50m.
- **Ổn định tổng thể** (Bishop / Janbu / Spencer).
- **Bài toán quy mô lớn** — móng nhà cao tầng NHC với 200+ cọc.

**Hạn chế:**
- Không thấy được **phá hoại cục bộ** trong một cọc (chọc thủng, kéo, uốn).
- Không cho phép **kiểm tra nội lực** từng cọc.

### 2.2 Discrete Column Modeling — từng cọc là cluster riêng

Mỗi cọc CDM được vẽ riêng trong Plaxis 2D dưới dạng cluster vật liệu cứng. Đất xung quanh giữ nguyên model HS/SS/MC.

**Áp dụng:**
- **TKBVT** chi tiết — cần kiểm tra nội lực mỗi cọc.
- **Hố đào sâu BXN** — cọc chống đỡ tường vây hoặc làm vành xi măng quanh hố.
- **Kiểm tra chọc thủng** dưới móng nông.
- **Phân tích chuyển vị cọc dưới tải ngang** (cọc CDM kết hợp với cừ SW kè KE).

**Hạn chế 2D plane strain:**
- Trong 2D, mỗi cọc trở thành **"tường liên tục"** không phải cọc tròn → phải hiệu chỉnh chiều dày tường để giữ đúng độ cứng dọc trục.

**Quy đổi 2D tương đương** (Bergado 1996):

$$t_{\text{2D}} = \frac{\pi D^2 / 4}{s_y}, \qquad E_{\text{2D}} = E_c$$

trong đó $s_y$ là khoảng cách cọc theo phương vuông góc mặt cắt, $t_{\text{2D}}$ là chiều dày tường tương đương để bảo toàn $E \cdot A$ trên 1 m chiều dài tuyến mặt cắt.

---

## 3. Các mô hình constitutive khả thi cho CDM

Sắp xếp theo độ phức tạp và mục đích sử dụng:

| # | Mô hình | Số tham số | Bài toán phù hợp | Ưu / Nhược |
|:-:|---|:-:|---|---|
| 1 | Linear Elastic (LE) | 2 | Lún composite, sơ bộ | ✅ Đơn giản · ❌ Không có cường độ |
| 2 | **MC + tension cut-off** | 5+1 | **Chuẩn ngành** — ổn định + chuyển vị | ✅ Đủ dùng · ⚠ Không brittle |
| 3 | Modified Hoek-Brown | 5 | qu cao (>2 MPa, gần như đá yếu) | ✅ Phi tuyến tự nhiên · ⚠ Ít dùng cho CDM |
| 4 | Hardening Soil (HS) | 11 | Hố đào + dỡ tải + chu trình tải | ✅ Phân biệt nén/cắt · ⚠ Không có bonding |
| 5 | Structured Cam-Clay (SCC) | 9 | Nghiên cứu hành vi nguyên gốc | ✅ Bonding + degradation · ❌ Chỉ UDSM, hiếm |
| 6 | Bonded Soft Soil (BSS) | 10 | Cám sét gia cố xi măng | ✅ Mô tả phá vỡ bonding · ❌ Chỉ UDSM Vatsala |
| 7 | Concrete-like (CDP) | 8+ | qu > 3 MPa (giống bê tông) | ✅ Strain softening · ❌ Cần Abaqus, không phải Plaxis |

### 3.1 Linear Elastic (LE) — đơn giản nhất

**Khi dùng:**
- Cluster CDM trong bài toán **lún** sơ cấp (TKCS).
- Khi $q_u > 1$ MPa và tải nhỏ → vùng đất xung quanh chảy dẻo trước, CDM vẫn đàn hồi.

**Tham số:**

| Ký hiệu | Công thức | Giá trị TTHC ($q_{u,\text{lab}} = 1\,000$ kPa, $r = 0{,}33$) |
|---|---|---|
| $q_{u,\text{field}}$ | $r \cdot q_{u,\text{lab}}$ | $0{,}33 \times 1\,000 = 330$ kPa |
| $C_{c,\text{col}}$ | $q_{u,\text{field}} / 2$ | $165$ kPa |
| $E_c$ | $(50\text{–}100) \times C_{c,\text{col}}$, default $75$ | $12\,375$ kPa (preset TTHC) |
| $\nu_c$ | 0,20–0,25 | 0,25 |
| $\gamma_c$ | Theo TCVN 9403 | 16,5 kN/m³ (≈ đất gốc + xi măng ít) |

> **Lưu ý:** TCVN 9403 Phụ lục C cho phép dùng **mô-đun thiết kế** dựa trên $q_{u,\text{design}}$ — đây là cường độ **mục tiêu** sau 28 ngày dưỡng hộ ngoài hiện trường, KHÔNG phải $q_u$ lab. Hệ số $r = q_{u,\text{field}}/q_{u,\text{lab}} = 0{,}20\text{–}0{,}50$ tuỳ chất lượng thi công; TTHC dùng $r = 0{,}33$ (default).

**Hạn chế:** Không có giới hạn cường độ → khi tải ngoài lớn, ứng suất trong cluster CDM lên vô hạn → không reproduce được chọc thủng hoặc cắt qua cọc.

### 3.2 Mohr-Coulomb với tension cut-off — **chuẩn ngành**

**Đây là mô hình được khuyến nghị phổ biến nhất** cho CDM trong Plaxis 2D theo PLAXIS Material Models Manual §3.6 và Bergado et al. (1996), Lorenzo & Bergado (2003).

**Lý do:**
1. MC thuần đã đủ mô tả cường độ giới hạn của CDM trong điều kiện tĩnh.
2. Tension cut-off **bắt buộc** vì CDM có cường độ kéo nhỏ ($\approx 0{,}1 q_u$) — bỏ qua thì ứng suất kéo phi lý trong cluster gần biên gây sai số.
3. Tham số dễ xác định từ thí nghiệm nở hông không hạn chế ($q_u$).

**Tham số đầu vào:**

| Ký hiệu | Công thức / Giá trị | Ghi chú |
|---|---|---|
| $E$ | $(50\text{–}100) \times C_{c,\text{col}}$ kPa | Mặc định $75 \times C_{c,\text{col}}$ |
| $\nu$ | 0,20–0,25 | TCVN 9403 dùng 0,25 |
| $c$ | $q_{u,\text{field}} / 2$ | TCVN 9403 Phụ lục B |
| $\varphi$ | 25°–35° | Tăng nhẹ so với đất gốc do bonding (Lorenzo-Bergado: $\varphi_c \approx \varphi_{\text{soil}} + 5°$). Đặt thận trọng $30°$ |
| $\psi$ | 0° | KHÔNG dùng $\psi > 0$ cho CDM — sai vật lý |
| **$\sigma_t$ (tension cut-off)** | **$0{,}10 \times q_{u,\text{field}}$** | Plaxis: **Tension cut-off** trong Material panel; phải bật |
| $\gamma$ | 16,0–17,0 kN/m³ | TTHC default 16,5 |
| Drainage | **Drained** | Sau 28 ngày, CDM cứng — coi như drained dù sét gốc undrained |

**Yield surface mở rộng:**

$$f_{MC} = \tau - \sigma_n \tan\varphi - c \le 0, \qquad \sigma_3' \ge -\sigma_t$$

Plaxis tự cắt yield surface tại $\sigma_3' = -\sigma_t$ → mặt phẳng $\sigma_3 \cdot \mathbf{n} - \sigma_t = 0$.

**Ví dụ TTHC ($q_{u,\text{design}} = 800$ kPa, $r = 0{,}33$):**

- $q_{u,\text{field}} = 0{,}33 \times 800 = 264$ kPa (nếu $q_u$ thiết kế = 800 kPa lab)
- Hoặc nếu $q_{u,\text{design}}$ là field: $q_{u,\text{field}} = 800$ kPa
- $C_{c,\text{col}} = 400$ kPa → $c = 400$ kPa
- $E_c = 75 \times 400 = 30\,000$ kPa
- $\sigma_t = 0{,}1 \times 800 = 80$ kPa

**Sai lầm phổ biến:** Đặt $\varphi = 0$ + $c = q_u/2$ → khi $\sigma_3' = 0$ thì cường độ chỉ = $q_u/2$. Nhưng nếu giữ $\sigma_3'$ thực = 50 kPa, cường độ thực = $q_u/2 + 50 \tan 30° \approx q_u/2 + 29$ kPa — bỏ qua đáng kể. **Khuyến nghị**: $\varphi = 25°\text{–}30°$ cho CDM nén tốt, $\varphi = 0$ chỉ dùng phân tích nhanh.

### 3.3 Mohr-Coulomb với strain softening — **CDM giòn (brittle)**

Khi CDM chất lượng cao ($q_u > 1{,}5$ MPa), hành vi sau peak là **giòn**: cường độ tụt 30–50% trong khoảng biến dạng cắt 1–3%.

PLAXIS không có **MC softening built-in** — phải dùng:
- **Cohesion / friction angle giảm theo plastic strain** (Plaxis UDSM "MC-Strain-Soft" tải từ Plaxis Knowledge Base).
- Hoặc lập trình UDSM Fortran riêng theo Vermeer & de Borst (1984).

Công thức softening đơn giản:

$$c(\bar{\varepsilon}^p) = c_{\text{peak}} - (c_{\text{peak}} - c_{\text{res}}) \cdot \min(\bar{\varepsilon}^p / \bar{\varepsilon}_f, 1)$$

với $c_{\text{res}} \approx 0{,}5 c_{\text{peak}}$, $\bar{\varepsilon}_f \approx 0{,}05$ (5%).

**Khi dùng (TTHC):** Kiểm tra chọc thủng cọc CDM dưới móng nông (NHC) — sau peak, đáy chọc thủng phát triển nhanh, cần softening để dự đoán phá hoại tiến triển.

**Khi KHÔNG dùng:** TKCS thông thường, lún cố kết — softening không quan trọng.

### 3.4 Hardening Soil (HS) cho CDM

Khi cần mô tả **chu trình tải / dỡ tải** (hố đào BXN, cọc cừ + CDM xen kẽ), HS có lợi thế vì có $E_{ur}$ riêng.

**Tham số HS cho CDM:**

| Ký hiệu | Giá trị | Ghi chú |
|---|---|---|
| $E_{50}^{ref}$ | $1{,}25 \times E_{oed}^{ref}$ ≈ $E_c$ | Khoảng $30\,000$–$60\,000$ kPa |
| $E_{oed}^{ref}$ | $E_c / 1{,}25$ ≈ $24\,000$–$48\,000$ kPa | |
| $E_{ur}^{ref}$ | $3 \times E_{50}^{ref}$ | CDM dỡ tải gần đàn hồi |
| $m$ | $0{,}5$–$0{,}8$ | Thấp hơn đất tự nhiên do bonding; thường 0,5 |
| $c, \varphi, \psi$ | Giống MC + tension | $\varphi = 25\text{–}30°$, $\psi = 0$ |
| $\sigma_t$ | $0{,}1 q_u$ | Tension cut-off bắt buộc |
| Drainage | Drained | |

**Khi dùng:**
- Hố đào BXN có CDM gia cố quanh tường → HS xử lý đúng phần dỡ tải đáy + nén lệch sườn.
- Cọc CDM kết hợp cừ SW (KE) — HS cho ứng xử tốt khi nội lực thay đổi qua các phase.

**Khi KHÔNG dùng:** Tính lún quasi-static đơn giản — LE hoặc MC đủ; HS làm phức tạp thêm 11 tham số.

### 3.5 Structured Cam-Clay (SCC) — Liu & Carter (2002)

Mô hình cao cấp cho CTS, **không có sẵn trong Plaxis** — phải dùng UDSM.

**Khái niệm:** Mở rộng MCC với bonding $b$ — bonding làm yield surface lớn hơn (kích thước $p_y^* + p_b$), và **giảm dần** theo plastic strain (damage).

$$p_y = p_y^* (1 + b), \qquad \dot{b} = -\omega \cdot b \cdot |\dot{\varepsilon}^p_v|$$

**Tham số (9):** Cam-Clay cơ bản ($\lambda, \kappa, M, \nu, e_0$) + bonding $b_0, \omega$ + cường độ ngưỡng phá vỡ bonding $p_b$ + intrinsic compression line.

**Khi dùng:**
- Nghiên cứu, bài báo khoa học.
- Khi cần mô tả chính xác **degradation** của CDM theo tải tích lũy / cyclic.

**Khi KHÔNG dùng (TTHC):** Quá phức tạp cho thực hành. Tham số cần thí nghiệm CIU triaxial + nén đẳng hướng chuyên sâu — chi phí cao, không tương xứng giá trị thông tin với dự án TKCS/TKBVT.

### 3.6 Bonded Soft Soil (BSS) — Vatsala et al. (2001)

Tương tự SCC nhưng dựa trên Soft Soil thay vì MCC. Cũng phải dùng UDSM.

Không khuyến nghị cho TTHC vì lý do tương tự SCC.

### 3.7 Concrete-Like (CDP — Concrete Damaged Plasticity)

**Khi CDM có $q_u > 3$ MPa** → vật liệu hành xử gần như bê tông yếu / vữa xi măng.

CDP có trong Abaqus, **không có sẵn Plaxis**. Tham số: nén, kéo + 2 evolution function damage.

**Khi áp dụng:** Cọc CDM siêu bền (JET grouting cường độ cao). TTHC dùng CDM thông thường ($q_u$ design 800–1 200 kPa) → không cần CDP.

---

## 4. Bảng đề xuất chọn mô hình theo bài toán

| Bài toán | Bước thiết kế | Approach | Mô hình CDM | Mô hình đất xung quanh |
|---|:---:|---|---|---|
| **Lún tổng hợp** (TKCS) | TKCS | Composite | **LE composite** (TCVN 9403 Phụ lục C) | — (vùng CDM đã composite) |
| **Lún tổng hợp** (TKBVT) | TKBVT | Discrete | **LE** ($E_c$) | **HS** hoặc **SS** |
| **Ổn định mái dốc** (slip qua vùng CDM) | TKCS/TKBVT | Composite | **MC + tension** với $c, \varphi$ composite | MC ($S_u$) |
| **Hố đào BXN** với vành CDM | TKBVT | Discrete | **MC + tension** hoặc **HS + tension** | **HSsmall** |
| **Kè KE** — CDM + cừ SW | TKBVT | Discrete | **MC + tension** | HS |
| **Chọc thủng nóc cọc CDM** | TKBVT | Discrete | **MC + tension + softening** (UDSM) | HS Undrained A |
| **Cọc CDM chịu tải ngang** | TKBVT | Discrete + plate | **MC + tension** | NGI-ADP hoặc HSsmall |
| **Cycle tải dài hạn** (giao thông KE) | TKBVT nâng cao | Discrete | **HS + tension** | HSsmall |
| **Phân tích phá hoại tiến triển** | Nghiên cứu | Discrete | **SCC / BSS** (UDSM) | HS / SS |

> **Quy tắc 1:** TKCS chấp nhận LE composite. TKBVT bắt buộc tối thiểu MC + tension cut-off.
>
> **Quy tắc 2:** Bài toán dỡ tải (hố đào, chu trình) cần HS chứ không phải MC, vì MC không phân biệt $E$ nén với $E$ dỡ tải.

---

## 5. Thiết lập cluster CDM trong PLAXIS 2D

### 5.1 Cấu trúc cluster

```python
# scripts/plaxis_cdm_material.py — auto-create material CDM
from plxscripting.easy import new_server
import json, os

g_i, _ = new_server('localhost', 10000, password=os.environ['PLAXIS_PASSWORD'])

def create_cdm_material(qu_design_kPa: float,
                        r_field_lab: float = 0.33,
                        Ec_factor: float = 75.0,
                        phi_deg: float = 30.0,
                        nu: float = 0.25,
                        gamma_kNm3: float = 16.5,
                        soil_model: str = 'MC',  # 'LE', 'MC', 'HS'
                        identification: str = 'CDM_XMD'):
    """
    Tạo material CDM trong Plaxis theo TCVN 9403.
    qu_design_kPa: cường độ thiết kế trường (sau khi đã nhân r_field_lab nếu cần)
    """
    qu_field = qu_design_kPa            # giả sử đã là field; nếu là lab thì × r
    Cc_col   = qu_field / 2.0
    E_c      = Ec_factor * Cc_col       # kPa
    c_kPa    = Cc_col                   # = qu_field/2
    sigma_t  = 0.10 * qu_field          # tension cut-off
    
    mat = g_i.soilmat()
    mat.Identification = identification
    mat.gammaUnsat = gamma_kNm3
    mat.gammaSat   = gamma_kNm3
    mat.DrainageType = 'Drained'
    mat.eInit = 0.50
    
    if soil_model == 'LE':
        mat.SoilModel = 1
        mat.EYoungRef = E_c
        mat.nu        = nu
    elif soil_model == 'MC':
        mat.SoilModel = 2
        mat.EYoungRef = E_c
        mat.nu        = nu
        mat.cRef      = c_kPa
        mat.phi       = phi_deg
        mat.psi       = 0.0
        # Bật tension cut-off
        mat.TensionCutOff = True
        mat.TensileStrength = sigma_t
    elif soil_model == 'HS':
        mat.SoilModel = 3
        mat.E50ref    = E_c
        mat.Eoedref   = E_c / 1.25
        mat.Eurref    = 3.0 * E_c
        mat.power     = 0.5
        mat.cRef      = c_kPa
        mat.phi       = phi_deg
        mat.psi       = 0.0
        mat.nuur      = 0.20
        mat.pref      = 100
        mat.Rf        = 0.90
        mat.TensionCutOff = True
        mat.TensileStrength = sigma_t
    
    return mat

# Sử dụng cho TTHC
cdm_mat = create_cdm_material(qu_design_kPa=800, soil_model='MC',
                              identification='CDM_TTHC_800kPa')
```

### 5.2 Quy đổi 2D plane strain — chiều dày tường tương đương

Khi mỗi cọc CDM được vẽ riêng trong 2D, cọc tròn $D=800$ mm với khoảng cách $s = 1{,}8$ m trở thành **tường liên tục dày $t_{2D}$** — phải hiệu chỉnh để giữ đúng diện tích thay thế:

$$t_{2D} = \frac{\pi D^2 / 4}{s_y}$$

**Ví dụ TTHC** ($D = 0{,}8$ m, $s_y = 1{,}8$ m bố trí vuông): $t_{2D} = \pi \times 0{,}64 / 4 / 1{,}8 = 0{,}279$ m.

Tức là vẽ 1 cọc CDM trong 2D = vẽ "tường" rộng 0,279 m, dài bằng chiều dài cọc. Vùng giữa các "tường" để đất tự nhiên.

**Bố trí tam giác:** $s_y = s \cdot \sqrt{3}/2$.

### 5.3 Phase + drainage trong Plaxis

| Phase | Tên | Hành động | Drainage CDM | Drainage đất |
|:-:|---|---|:-:|:-:|
| 0 | Initial | $K_0$ procedure | — | — |
| 1 | CDM installation | Activate cluster CDM (gamma = 0,5 × tự nhiên trong quá trình trộn) | Drained | Undrained A |
| 2 | Curing | Thay material → CDM hoàn chỉnh + tăng $\gamma$ | Drained | Drained (cố kết) |
| 3 | Fill loading | Đắp trên | Drained | Undrained A → Consolidation |
| 4 | Consolidation | Wait | Drained | Consolidation Biot |
| 5 | Service load | Áp tải khai thác | Drained | Undrained A hoặc Drained |
| 6 | Safety | $\varphi/c$ reduction toàn cục | Drained | Drained |

**Lưu ý:** Trong Plaxis, phase **Cement Mixing → Curing** thường được đơn giản thành 1 phase duy nhất "Activate CDM" với $E_c$ trực tiếp, bỏ qua giai đoạn lỏng do thời gian rất ngắn (<24h) so với cố kết.

---

## 6. Áp dụng cụ thể cho 3 zone TTHC

### 6.1 KE — Kè đường ô tô với CDM hỗn hợp cọc cừ SW

**Bố trí:** CDM nằm dưới đáy đất yếu (gia cố nền), kết hợp với cừ SW làm tường chắn. $D = 800$ mm, $s = 1{,}8$ m, $L \approx 23$ m (đến lớp 4 cát chặt).

**Mô hình khuyến nghị:**

| Phần tử | TKCS | TKBVT |
|---|---|---|
| Vùng CDM gia cố | **LE composite** ($E_c = 30\,000$ kPa, $a = 0{,}25$) | Discrete: **MC + tension** mỗi cọc; đất Lớp 1 xung quanh: **SS** |
| Lớp 1 (bùn sét) bên dưới CDM | MC | SS hoặc HS Undrained A |
| Cọc cừ SW | Plate (LE bê tông) | Plate + Connection (HingeFix tại đỉnh) |
| Lớp 4 cát chặt (chân CDM) | MC | HS, $m = 0{,}5$ |

**Phase đặc biệt:** Sau khi cừ SW + CDM đã thi công, phase tải kè đắp + giao thông. CDM giúp truyền tải xuống lớp 4, giảm lún cố kết lớp 1.

### 6.2 BXN — Bãi xe ngầm có vành CDM quanh tường vây

**Bố trí:** CDM tạo vành quanh chu vi hố đào để giảm chuyển vị tường + chống bùng đáy. $D = 800$ mm, $s = 1{,}5$ m, $L$ từ đáy hố đào xuống lớp 4.

**Mô hình khuyến nghị:**

| Phần tử | TKBVT |
|---|---|
| Vành CDM | Discrete cluster **MC + tension** ($c = 400$ kPa, $\varphi = 30°$, $\sigma_t = 80$ kPa) hoặc **HS + tension** nếu phân tích chu trình |
| Tường vây | Plate (LE) hoặc Volume bê tông |
| Lớp 1 + 2 trong/ngoài hố | **HSsmall** Undrained A |
| Anchor / strut | Node-to-Node Anchor |

**Quan trọng:** Trong phase hố đào, áp lực kéo xuất hiện ở mặt trong CDM → tension cut-off **bắt buộc** để tránh lực kéo ảo.

### 6.3 NHC — Móng nhà hành chính trên CDM nền

**Bố trí:** CDM gia cố toàn diện dưới đáy móng nhà cao tầng, $D = 800$ mm, $s = 1{,}8$ m, $L \approx 27$ m (đến hết lớp đất yếu).

**Mô hình khuyến nghị:**

| Bài toán | Approach | CDM | Đất gốc |
|---|---|---|---|
| Lún tổng + chênh lún cột-cột | Composite cho lún tổng + Discrete cho chi tiết cột | **LE composite** ($E_c = 40\,000$ kPa) + **discrete LE** cho cột chính | **HS + SS zoned** cho lớp 1/2 |
| Chọc thủng đáy móng | Discrete | **MC + tension + softening** (UDSM nếu cần) | HS Undrained A |
| Tải động (rung động máy) | Discrete | **HS + tension** | **HSsmall** |

---

## 7. Pitfalls và quy tắc kiểm tra

### 7.1 Mười lỗi phổ biến

1. **Bỏ tension cut-off** → ứng suất kéo phi lý trong cluster CDM gần biên → sai cả ổn định lẫn chuyển vị.
2. **Đặt $\psi > 0$ cho CDM** → mô hình tự "nở thể tích" khi cắt → áp lực lỗ rỗng âm hoặc lún âm.
3. **Drainage = Undrained** cho CDM → CDM tự coi là không thoát nước, sai vì CDM 28 ngày đã cứng → Drained.
4. **Lấy $E_c = 75 \cdot q_{u,\text{lab}}/2$ thay vì $\cdot q_{u,\text{field}}/2$** → mô-đun cao gấp 3 → lún tính nhỏ hơn thực 3 lần.
5. **Bỏ qua $r = q_{u,\text{field}}/q_{u,\text{lab}}$** trong design tham số.
6. **Không kiểm tra $\sigma_3'$ thực trong cluster** → khi tải nhỏ, $\sigma_3'$ vẫn nhỏ → cường độ MC = $c$ (~$q_u/2$) — không bao giờ đạt $q_u$ đầy đủ.
7. **Composite cho hố đào** → quá đơn giản, bỏ qua tương tác cụ thể cọc-đất.
8. **Discrete trong 2D mà quên quy đổi $t_{2D}$** → mất diện tích thay thế → kết quả khác bài toán 3D.
9. **Đặt $\gamma_{CDM}$ quá cao** (vd 18–20 kN/m³) → CDM nhẹ hơn đáng kể đất do bọt khí trộn vào, thường 15,5–17 kN/m³.
10. **Bỏ qua cố kết trước-sau CDM** → CDM thi công làm thay đổi $\sigma'$ trong đất xung quanh, cần phase consolidation riêng.

### 7.2 Checklist trước khi chạy phase tải

- [ ] Tension cut-off đã bật trong material CDM?
- [ ] $\psi = 0$ trong material CDM?
- [ ] Drainage CDM = Drained?
- [ ] $E_c$ tính từ $q_{u,\text{field}}$, không phải $q_{u,\text{lab}}$?
- [ ] $\gamma_{CDM} = 15$–$17$ kN/m³?
- [ ] Nếu 2D discrete: $t_{2D} = \pi D^2 / (4 s_y)$?
- [ ] Phase Initial có $K_0$ đúng (CDM mới thi công, không có $K_0$ tự nhiên — Plaxis tự xử lý)?
- [ ] Nếu HS: $m = 0{,}5$ (không lấy $m = 1$ như sét mềm)?

---

## 8. Tham số thực tế dự án TTHC

Hiện tại [`data/tcvn9403_params.json`](data/tcvn9403_params.json) cho cả 3 zone:

```json
{
  "zone_soil_params": {
    "KE":  {"cdm_qu_lab_kPa": 1000, "cdm_area_ratio": 0.25,
            "cdm_Ec_factor": 75, "cdm_field_lab_ratio": 0.33},
    "BXN": {"cdm_qu_lab_kPa": 1000, "cdm_area_ratio": 0.25,
            "cdm_Ec_factor": 75, "cdm_field_lab_ratio": 0.33},
    "NHC": {"cdm_qu_lab_kPa": 1000, "cdm_area_ratio": 0.25,
            "cdm_Ec_factor": 75, "cdm_field_lab_ratio": 0.33}
  }
}
```

Quy đổi cho material Plaxis:

| Tham số | Công thức | Giá trị |
|---|---|---|
| $q_{u,\text{field}}$ | $0{,}33 \times 1\,000$ | $330$ kPa |
| $C_{c,\text{col}}$ | $q_{u,\text{field}}/2$ | $165$ kPa |
| $E_c$ | $75 \times 165$ | $12\,375$ kPa |
| $c$ (cho MC) | $C_{c,\text{col}}$ | $165$ kPa |
| $\varphi$ | Giả định bảo thủ | $25°$ |
| $\sigma_t$ | $0{,}1 \times 330$ | $33$ kPa |
| $E_{50}^{ref}$ (cho HS) | $\approx E_c$ | $12\,375$ kPa |
| $E_{ur}^{ref}$ | $3 \times E_{50}^{ref}$ | $37\,125$ kPa |

> **Lưu ý quan trọng:** Nếu thực tế đạt $q_{u,\text{design}}^{\text{TKBVT}} = 800$ kPa (giá trị mới ở §34 CLAUDE.md — TVTK CDM Section 5) thì các giá trị trên nhân $\times 0{,}8$. Cần đồng bộ giữa `cdm_qu_lab_kPa` (cũ = 1000) và `qu_design` mới của trang `"tvtk_prep"`.

---

## 9. Tham khảo

### Tiêu chuẩn

- **TCVN 9403:2012** — Gia cố nền đất yếu bằng trụ đất xi măng. Phụ lục B (Cường độ), Phụ lục C (Lún).
- **EuroSoilStab (2002)** — Design guide for cement deep mixing, EU FP5 project.
- **JGS 0821-2009** — Practice for making and curing stabilized soil specimens (Nhật Bản).
- **FHWA-RD-99-138** (Bruce 2000) — Introduction to deep mixing methods.

### Sách & paper chính

- Bruce D.A. (2000). *An introduction to the deep mixing methods as used in geotechnical applications.* FHWA-RD-99-138.
- Kitazume M., Terashi M. (2013). **The Deep Mixing Method.** CRC Press. — Chương 6 (constitutive), Chương 7 (zoning + design).
- Lorenzo G.A., Bergado D.T. (2003). *New consolidation equation for soil-cement pile improved ground.* **Can. Geotech. J.** 40: 265–275.
- Bergado D.T., Anderson L.R., Miura N., Balasubramaniam A.S. (1996). **Soft ground improvement in lowland and other environments.** ASCE Press.
- Liu M.D., Carter J.P. (2002). *Structured Cam Clay model.* **Can. Geotech. J.** 39: 1313–1332.
- Vatsala A., Nova R., Murthy S.B.R. (2001). *Elastoplastic model for cemented soils.* **J. Geotech. Geoenviron. Eng.** ASCE 127(8): 679–687.
- Suebsuk J., Horpibulsuk S., Liu M.D. (2010). *Modified Structured Cam Clay: a generalised critical state model for destructured, naturally structured and artificially structured clays.* **Computers and Geotechnics** 37: 956–968.
- Vermeer P.A., de Borst R. (1984). *Non-associated plasticity for soils, concrete and rock.* **Heron** 29(3).
- Lade P.V. (1977). *Elasto-plastic stress-strain theory for cohesionless soil with curved yield surfaces.* **Int. J. Solids and Structures** 13: 1019–1035.

### Plaxis Manual references

- **PLAXIS 2D Material Models Manual 2024.2** §3.6 (Tension cut-off in MC), §6.7 (HS for stiff soil including stabilized), §15 (UDSM interface).
- **PLAXIS 2D Tutorial Manual** Lesson 12 — Stabilized embankment over soft soil.

### Tài liệu dự án

- [39-tcvn9403-tru-dat-xi-mang.md](39-tcvn9403-tru-dat-xi-mang.md)
- [41-cdm-choc-thung-dem-ximang.md](41-cdm-choc-thung-dem-ximang.md)
- [56-plaxis-soil-models-application.md](56-plaxis-soil-models-application.md)
- [scripts/cdm_column_calc.py](scripts/cdm_column_calc.py)
- [data/soil_presets.json](data/soil_presets.json)

---

## 10. Tóm tắt — Trả lời ngắn

**Câu hỏi:** Đất gia cố xi măng dùng mô hình gì?

**Trả lời tóm gọn:**

| Cấp thiết kế / Bài toán | Mô hình khuyến nghị |
|---|---|
| TKCS — lún sơ bộ | **LE composite** (TCVN 9403 Phụ lục C, $E_c = 75 \cdot q_u^{field}/2$) |
| TKBVT — lún chi tiết | **LE cluster** ($E_c$) trong mô hình Plaxis có HS/SS đất gốc |
| TKBVT — ổn định mái dốc | **MC + tension cut-off** ($c = q_u^{field}/2$, $\varphi = 25\text{–}30°$, $\sigma_t = 0{,}1 q_u^{field}$) |
| TKBVT — hố đào / chu trình tải | **HS + tension cut-off** |
| Chọc thủng / phá hoại cục bộ | **MC + tension + strain softening** (UDSM) |
| Nghiên cứu hành vi nguyên gốc | **Structured Cam-Clay** hoặc **Bonded Soft Soil** (UDSM) |

**Chuẩn ngành cho thực hành VN/HCM:** **Mohr-Coulomb với tension cut-off** + drainage Drained, $\psi = 0$, $E_c = 75 \times q_u^{field}/2$, $c = q_u^{field}/2$, $\varphi = 25°$–$30°$, $\sigma_t = 0{,}1 q_u^{field}$.

### Bước tiếp theo gợi ý

- [ ] Thêm preset CDM vào `data/soil_presets.json` (section mới `cement_treated`) — 3 cấp $q_u^{design}$: 600, 800, 1200 kPa.
- [ ] Tạo `scripts/plaxis_cdm_material.py` triển khai `create_cdm_material()` hoàn chỉnh.
- [ ] Thí nghiệm bổ sung trong TKBVT: 3 mẫu CDM mỗi zone với cycle loading để xác định $E_{ur}/E_{50}$ thực.
- [ ] Cập nhật CLAUDE.md mục mới quy tắc material CDM trong Plaxis: drainage, tension, $\psi$, $E$ từ field.
