# 56 — Mô hình đất trong PLAXIS và phạm vi áp dụng vào dự án TTHC

**Phiên bản:** 2026-05-25 · Áp dụng cho PLAXIS 2D 2024.2 (Connect Edition V24)
**Phạm vi dự án:** Trung Tâm Hành Chính HCM — 3 khu vực KE, BXN, NHC
**Tài liệu tham chiếu:**
- PLAXIS Material Models Manual 2024.2 (§3 MC, §6 HS, §7 HSsmall, §10 SS, §11 SSC, §13 NGI-ADP, §16 Hoek-Brown)
- TCVN 9362, TCVN 4253, TCCS 41
- [13-hardening-soil-model.md](13-hardening-soil-model.md) · [15-soil-profile-202605-TTHC.md](15-soil-profile-202605-TTHC.md) · [data/soil_presets.json](data/soil_presets.json)

---

## 1. Tổng quan các mô hình đất trong PLAXIS

PLAXIS 2D hỗ trợ **13 mô hình constitutive** (built-in) + **UDSM** (User-Defined Soil Model). Sắp xếp theo độ phức tạp tăng dần:

| Mô hình | Viết tắt | Họ | Số tham số chính | Hành vi |
|---|:---:|---|:---:|---|
| Linear Elastic | LE | Đàn hồi | 2 ($E, \nu$) | Tuyến tính, không có cường độ |
| Mohr-Coulomb | MC | Đàn hồi-dẻo hoàn hảo | 5 ($E, \nu, c, \varphi, \psi$) | Tuyến tính rồi chảy dẻo |
| Hardening Soil | HS | Đàn hồi-dẻo có hardening | 11 | 3 mô-đun + nén lệch + nén thể tích |
| HS-small Strain Stiffness | HSsmall | HS + biến dạng nhỏ | 13 | HS + $G_0^{ref}, \gamma_{0{,}7}$ |
| Soft Soil | SS | Họ Cam-Clay | 7 | Bùn sét NC, lún cố kết |
| Soft Soil Creep | SSC | SS + creep | 8 | SS + lún thứ cấp $\mu^*$ |
| Modified Cam-Clay | MCC | Critical state | 7 ($\lambda, \kappa, M, \nu, e_0, p_0, OCR$) | Sét nguyên trạng, NC/OC |
| Sekiguchi-Ohta | SO | Critical state + dị hướng | 9 | Sét dị hướng |
| Generalized HS (Brick) | GHS | HS + creep + dị hướng | 17 | Nâng cao, ít dùng |
| NGI-ADP / NGI-ADPSoft | NGI-ADP | Undrained anisotropic | 7 ($S_u^A, S_u^P, S_u^{DSS}$...) | Sét undrained có dị hướng cường độ |
| UBC-3D-PLM | UBCSAND | Cyclic plasticity | 13 | Hoá lỏng cát rời |
| Hoek-Brown | HB | Đá nguyên trạng | 5 ($\sigma_{ci}, m_i, GSI, D, E_i$) | Đá có khe nứt |
| Jointed Rock | JR | Đá phân lớp | 11 | Khe nứt định hướng |
| UDSM | — | User-defined | tùy | Mô hình tự viết (Fortran .dll) |

---

## 2. Chi tiết từng mô hình

### 2.1 Linear Elastic (LE)

**Khái niệm:** Định luật Hooke tuyến tính, **không có giới hạn cường độ**. Vật liệu không bao giờ chảy dẻo.

**Tham số:**

$$\boldsymbol{\sigma} = \mathbf{D}^e : \boldsymbol{\varepsilon}, \qquad \mathbf{D}^e = \frac{E}{(1+\nu)(1-2\nu)} \mathbf{C}$$

| Ký hiệu | Đơn vị | Mô tả |
|---|---|---|
| $E$ | kN/m² | Mô-đun đàn hồi (Young) |
| $\nu$ | — | Hệ số Poisson |

**Khi dùng:**
- Cấu kiện bê tông cốt thép (tường vây, đáy hố đào, sàn) — $E = 30\,000 \text{ MPa}, \nu = 0{,}2$
- **Lớp XMD (CDM)** — $E_c = 75 \cdot q_u / 2$ ≈ 40 000 kPa, $\nu = 0{,}25$ (TCVN 9403 Phụ lục C)
- Đá rất cứng không khe nứt
- Bedrock đáy mô hình (làm "cứng vô hạn")

**Khi KHÔNG dùng:** Đất tự nhiên — luôn có cường độ giới hạn nên LE sẽ cho ứng suất vô lý (vô hạn).

### 2.2 Mohr-Coulomb (MC)

**Khái niệm:** Đàn hồi tuyến tính + tiêu chí chảy Mohr-Coulomb.

**Mặt chảy (yield surface):**

$$f_{MC} = \tau + \sigma_n \tan\varphi - c = 0$$

Hoặc dạng bất biến ứng suất:

$$f_{MC} = \frac{\sigma_1' - \sigma_3'}{2} + \frac{\sigma_1' + \sigma_3'}{2} \sin\varphi - c \cos\varphi = 0$$

**Tham số:**

| Ký hiệu | Đơn vị | Mô tả |
|---|---|---|
| $E$ | kN/m² | Mô-đun đàn hồi |
| $\nu$ | — | Hệ số Poisson (0,3–0,35) |
| $c$ | kN/m² | Lực dính hữu hiệu |
| $\varphi$ | độ | Góc ma sát hữu hiệu |
| $\psi$ | độ | Góc giãn nở; thường $\psi = \max(\varphi - 30°, 0)$ |

**Ưu điểm:** Đơn giản, ít tham số, tham số dễ xác định từ thí nghiệm thông thường (cắt UU, CD).

**Hạn chế:**
1. **Mô-đun $E$ không đổi** theo ứng suất → không phù hợp đất tự nhiên (đất sâu cứng hơn đất nông).
2. **Không phân biệt nén lệch vs nén nở** — chỉ có một $E$ duy nhất → lún cố kết tính SAI.
3. **Không có hardening** — đất chảy dẻo ngay khi vượt $f_{MC}$.
4. Với $\psi > 0$ + giả định không thoát nước → áp lực lỗ rỗng âm vô tận (sai vật lý).

**Khi dùng (TTHC):**
- Phân tích sơ bộ TKCS (trước khi có đủ thí nghiệm cho HS)
- Lớp cát đắp (F, đắp sau) — $E = 20\,000$ kPa, $c = 1$, $\varphi = 30°$
- Phân tích Safety (φ/c reduction) cho mái dốc, cọc cừ → mặc định Plaxis dùng MC cho Safety phase
- Lớp đá / sỏi không quan trọng (làm điều kiện biên)

**Khi KHÔNG dùng:**
- Tính lún chính xác → dùng HS hoặc SS
- Hố đào sâu — MC không reproduce được bottom heave đúng
- Bài toán có dỡ tải / chu trình tải → không có $E_{ur}$ riêng

### 2.3 Hardening Soil (HS)

**Khái niệm:** Đàn hồi-dẻo có 2 hardening cơ chế:
1. **Shear hardening** — mặt chảy dạng hyperbol (Duncan-Chang) di động theo biến dạng cắt.
2. **Compression hardening** — cap (mặt nén thể tích) di động khi đất bị nén.

**Tham số (11):**

| Ký hiệu | Đơn vị | Mô tả |
|---|---|---|
| $E_{50}^{ref}$ | kN/m² | Mô-đun cát-tuyến khi nén lệch 50% ứng suất phá huỷ |
| $E_{oed}^{ref}$ | kN/m² | Mô-đun đo từ oedometer (CRS) |
| $E_{ur}^{ref}$ | kN/m² | Mô-đun dỡ tải-tải lại — thường $E_{ur} = 3 \cdot E_{50}$ |
| $m$ | — | Lũy thừa biến đổi mô-đun theo ứng suất; cát ≈ 0,5; sét cứng ≈ 0,8; sét mềm ≈ 1,0 |
| $c, \varphi, \psi$ | kPa, °, ° | Tham số Mohr-Coulomb truyền thống |
| $\nu_{ur}$ | — | Poisson dỡ tải, mặc định 0,2 |
| $p^{ref}$ | kN/m² | Áp lực tham chiếu, mặc định 100 |
| $R_f$ | — | Tỉ số phá huỷ, mặc định 0,9 |
| $K_0^{NC}$ | — | Hệ số đẩy ngang trạng thái NC, mặc định $1 - \sin\varphi$ |

**Công thức biến đổi mô-đun theo ứng suất:**

$$E_{50} = E_{50}^{ref} \left(\frac{c \cos\varphi - \sigma'_3 \sin\varphi}{c \cos\varphi + p^{ref} \sin\varphi}\right)^m$$

**Ước lượng từ Cc, Cs (TPHCM soft clay) — đã có trong [soil_presets.json](data/soil_presets.json):**

$$E_{oed}^{ref} \approx \frac{2{,}3 \cdot (1 + e_0) \cdot p^{ref}}{C_c}, \qquad E_{50}^{ref} \approx 1{,}25 \cdot E_{oed}^{ref}, \qquad E_{ur}^{ref} \approx 3 \cdot E_{50}^{ref}$$

**Khi dùng (TTHC):**
- **Lớp 1 (bùn sét)** — Undrained A, $E_{50}^{ref} \approx 3\,594$ kPa (đã có preset `hs_lop1_bun_set`)
- **Lớp 4 (cát chặt)** — Drained, $E_{50}^{ref} = 50\,000$ kPa (preset `hs_dense_sand`)
- **Lớp 5 (sét cứng OC)** — Drained, $E_{50}^{ref} = 30\,000$ kPa, $m = 0{,}8$ (preset `hs_stiff_clay`)
- **Lớp 2a/2b/2c (cát bụi)** — Drained, $E_{50}^{ref} = 10\,000$–$25\,000$ kPa (preset cát rời/vừa chặt)
- **Hố đào sâu (BXN tầng hầm)** — HS là tối thiểu để có heave + chuyển vị tường đúng

**Khi KHÔNG dùng:** Sét cố kết bình thường (NC) sâu — nên dùng SS (chính xác hơn về lún) hoặc kết hợp HS cho cắt + SS cho cố kết.

### 2.4 Hardening Soil with small-strain Stiffness (HSsmall)

**Khái niệm:** HS + đường cong $G(\gamma)$ giảm dần theo biến dạng cắt (small-strain stiffness).

**Tham số thêm so với HS:**

| Ký hiệu | Đơn vị | Mô tả |
|---|---|---|
| $G_0^{ref}$ | kN/m² | Mô-đun cắt biến dạng rất nhỏ; thường 2–10× $E_{ur}^{ref}/2(1+\nu)$ |
| $\gamma_{0{,}7}$ | — | Biến dạng cắt khi $G = 0{,}7 \cdot G_0$; thường $10^{-4}$ |

Đường cong $G(\gamma)$ theo Santos & Correia (2001):

$$\frac{G}{G_0} = \frac{1}{1 + 0{,}385 \cdot |\gamma|/\gamma_{0{,}7}}$$

**Khi dùng (TTHC):**
- Bài toán **dynamic** (động đất, chấn động giao thông) — HSsmall **bắt buộc** để dampening tự nhiên đúng
- Hố đào sâu cạnh nhà nhạy cảm — vùng "tiền chảy" mô tả đúng → biến dạng quanh hố đào đúng hơn HS
- Bài toán **kết cấu hỗ trợ rất nhạy** (vd nhà cổ liền kề BXN)

**Khi KHÔNG dùng:** Phân tích thông thường (TKCS, tính lún quasi-static) — HS đã đủ.

### 2.5 Soft Soil (SS)

**Khái niệm:** Mô hình Cam-Clay đã đơn giản hoá cho bùn sét. Đường nén cố kết logarit (tương đương Cc).

**Tham số:**

| Ký hiệu | Đơn vị | Mô tả | Quy đổi từ thí nghiệm |
|---|---|---|---|
| $\lambda^*$ | — | Chỉ số nén sửa đổi | $\lambda^* = C_c / [\ln 10 \cdot (1+e_0)]$ |
| $\kappa^*$ | — | Chỉ số nở sửa đổi | $\kappa^* = C_s / [\ln 10 \cdot (1+e_0)]$ |
| $c$ | kPa | Lực dính |
| $\varphi$ | độ | Góc ma sát |
| $\nu_{ur}$ | — | Poisson dỡ tải, 0,15 |
| $POP$ hoặc $OCR$ | kPa hoặc — | Quá cố kết |
| $K_0^{NC}$ | — | Tự động $= 1 - \sin\varphi$ |

**Mặt chảy:** Ellipse trên mặt phẳng $(p', q)$, di động theo $p_p$ (preconsolidation pressure):

$$f_{SS} = \frac{q^2}{M^2 (p' + c \cot\varphi)(p_p + c \cot\varphi)} - 1 = 0$$

**Khi dùng (TTHC):**
- **Lớp 1 (bùn sét NC ở BXN, NHC)** — Drained nếu tính dài hạn, có cố kết. Preset `ss_lop1_bun_set`.
- **Lớp 2 (sét dẻo chảy)** — Drained, preset `ss_lop2_set_deo_chay`.
- Bài toán **lún cố kết sơ cấp** chính xác hơn HS (vì có $\lambda^*$ thay vì $E_{oed}$ tuyến tính).
- Kè ô tô đắp trên đất yếu (KE) — kết hợp với phase cố kết Biot.

**Khi KHÔNG dùng:**
- Sét OC mạnh (OCR > 2) → dùng HS hoặc MCC.
- Hố đào sâu — SS không reproduce được biến dạng cắt đúng (không có shear hardening rõ).
- Bài toán dỡ tải (unloading) — $\kappa^*$ không đủ chính xác cho dỡ tải lớn.

### 2.6 Soft Soil Creep (SSC)

**Khái niệm:** SS + lún thứ cấp (creep) theo thời gian.

**Tham số thêm so với SS:**

| Ký hiệu | Đơn vị | Mô tả |
|---|---|---|
| $\mu^*$ | — | Chỉ số creep sửa đổi; $\mu^* = C_\alpha / [\ln 10 \cdot (1+e_0)]$ |

Tốc độ creep:

$$\dot{\varepsilon}_v^{creep} = \frac{\mu^*}{\tau} \left(\frac{p_p^{eq}}{p_p}\right)^{(\lambda^* - \kappa^*)/\mu^*}$$

**Khi dùng (TTHC):**
- Bùn hữu cơ (Lớp 1 ở các HK có hàm lượng hữu cơ cao) — $C_\alpha$ ≈ 0,02–0,05.
- Dự báo lún 50–100 năm (tuổi thọ công trình) — nếu chỉ dùng SS thì lún thứ cấp = 0, sai cho công trình tải dài hạn.
- **Kè KE** — quan trọng vì kè khai thác lâu, lún thứ cấp tích luỹ ảnh hưởng độ bằng phẳng (P7 của file 55).

**Khi KHÔNG dùng:** Cát, sét OC mạnh — creep không đáng kể.

**Cẩn trọng:** $\mu^*$ phải đo bằng thí nghiệm oedometer 24h+ (xác định $C_\alpha$). Hiện TTHC **chưa có** $C_\alpha$ → giả định $\mu^* = 0{,}005$ (đặc trưng sét HCM).

### 2.7 Modified Cam-Clay (MCC)

**Khái niệm:** Họ critical state nguyên bản. Mặt chảy ellipse, hardening theo $p_p$.

**Tham số:**

| Ký hiệu | Đơn vị | Mô tả |
|---|---|---|
| $\lambda$ | — | Chỉ số nén (slope NCL trên $e$-$\ln p$) |
| $\kappa$ | — | Chỉ số nở (URL slope) |
| $M$ | — | Độ dốc CSL trên $p$-$q$; $M = 6 \sin\varphi_{cs} / (3 - \sin\varphi_{cs})$ |
| $\nu$ | — | Poisson |
| $e_0$ | — | Hệ số rỗng ban đầu |
| $p_0$ hoặc $OCR$ | kPa hoặc — | Áp lực tiền cố kết |

**Khi dùng:** Sét tự nhiên trong nghiên cứu hàn lâm; ít dùng trong thực hành VN vì SS đã đủ và đơn giản hơn.

**Khi KHÔNG dùng (TTHC):** Không khuyến nghị — dùng SS hoặc HS.

### 2.8 NGI-ADP / NGI-ADPSoft

**Khái niệm:** Mô hình undrained dị hướng — cường độ cắt khác nhau theo phương ứng suất chính (Active, Passive, DSS — Direct Simple Shear).

**Tham số:**

| Ký hiệu | Đơn vị | Mô tả |
|---|---|---|
| $S_u^A$ | kPa | Cường độ cắt theo phương Active (kéo dọc) |
| $S_u^P$ | kPa | Phương Passive (nén dọc) |
| $S_u^{DSS}$ | kPa | Cắt thuần (DSS) — thường $\approx 0{,}7 S_u^A$ |
| $\gamma_f^E, \gamma_f^C, \gamma_f^{DSS}$ | % | Biến dạng phá huỷ trong từng phương |
| $G_{ur}/S_u^A$ | — | Mô-đun cắt dỡ tải |
| $\nu_u$ | — | Poisson không thoát nước (≈ 0,49) |

**Khi dùng (TTHC):**
- **Hố đào sâu BXN** (tầng hầm) — phía bên hố đào, sét bị cắt theo 3 phương khác nhau → NGI-ADP cho cả lực kích thước + chuyển vị tường chính xác hơn HS Undrained.
- Bài toán **cọc chịu tải ngang** trong sét — NGI-ADP cho hành vi p-y đúng hơn.
- Tải nhanh ngắn hạn (tải xe, gió) — undrained → NGI-ADP.

**Khi KHÔNG dùng:**
- Sét isotropic (ít gặp ở HCM, sét HCM thường có $S_u^P / S_u^A \approx 0{,}9$–$1{,}0$ — không quá dị hướng).
- Bài toán dài hạn drained → dùng HS hoặc SS.

**Cẩn trọng:** TTHC hiện chỉ có VST + UU → chỉ biết $S_u$ trung bình. Phải làm thí nghiệm CK0U / CIUC + DSS để có $(S_u^A, S_u^P, S_u^{DSS})$ riêng. Trước khi có thí nghiệm: chọn $S_u^P = S_u^A$, $S_u^{DSS} = 0{,}7 S_u^A$ làm mặc định.

### 2.9 UBC-3D-PLM (UBCSAND)

**Khái niệm:** Mô hình hoá lỏng cát rời (liquefaction).

**Khi dùng:** Phân tích động đất / rung động cho cát rời (Lớp 2 bùn cát mịn) — kiểm tra hoá lỏng.

**Khi KHÔNG dùng (TTHC):** TTHC không có yêu cầu phân tích hoá lỏng động đất; tải tĩnh là chính. **Không khuyến nghị** trừ khi có yêu cầu bổ sung từ chủ đầu tư.

### 2.10 Hoek-Brown (HB)

**Khái niệm:** Tiêu chí cường độ phi tuyến cho đá nguyên trạng / đá khe nứt.

$$\sigma_1' = \sigma_3' + \sigma_{ci} \left(m_b \frac{\sigma_3'}{\sigma_{ci}} + s\right)^a$$

**Khi dùng (TTHC):** **Không áp dụng** — toàn bộ địa tầng TTHC là đất bồi tích Sài Gòn (sét + cát), không có lớp đá.

### 2.11 Jointed Rock (JR), Sekiguchi-Ohta, Generalized HS

Không áp dụng cho TTHC. Có thể dùng tham khảo cho dự án sau ở miền núi.

### 2.12 UDSM (User-Defined Soil Model)

**Khái niệm:** Mô hình tự viết bằng Fortran, compile thành .dll, Plaxis load qua API.

**Khi dùng (TTHC):** Khuyến nghị **chỉ khi** cần mô hình đặc biệt (vd CDM composite có cường độ biến đổi theo thời gian xi măng đông kết). Hiện chưa cần.

---

## 3. Bảng tra cứu nhanh — Model theo lớp đất TTHC

Dựa trên địa tầng đã trích xuất [15-soil-profile-202605-TTHC.md](15-soil-profile-202605-TTHC.md):

| Lớp | Mô tả | Drainage | Model **TKCS** (sơ bộ) | Model **TKBVT** (chi tiết) | Lý do nâng cấp |
|---|---|---|---|---|---|
| **F** | San lấp / đất đắp | Drained | MC | MC hoặc HS | Đắp đơn giản, $E$ ≈ hằng số là chấp nhận được |
| **1** | Bùn sét NC, $C_u$ ≈ 10–30 kPa | Undrained A | MC + $S_u$ (φ=0) | **HS + SS** hoặc **NGI-ADP** | Tính lún cố kết chính xác (SS) + chuyển vị (HS); nếu hố đào sâu → NGI-ADP |
| **1b** | Sét bụi xen cát | Undrained A | MC | **HS** | Có cường độ ma sát đáng kể |
| **2a / 2b / 2c** | Cát bụi xốp → chặt vừa | Drained | MC | **HS** | $E$ tăng theo độ sâu → HS với $m=0{,}5$ |
| **3** | Sét dẻo | Drained nếu dài hạn / Undrained nếu ngắn hạn | MC | **HS** hoặc **SS** | Lún cố kết — SS; chuyển vị tường — HS |
| **4** | Cát chặt | Drained | MC | **HS** ($m=0{,}5$) | Hỗ trợ chân cọc — cần $E$ chính xác theo $\sigma$ |
| **5 / 5a / 5b** | Sét cứng / cát chặt vừa | Drained | MC | **HS** ($m=0{,}8$) | Tầng tựa cọc, biến dạng nhỏ nhưng cần đúng |
| **6 / 7** | Cát chặt sâu | Drained | LE | LE hoặc HS cứng | Chỉ là tầng đệm dưới, biến dạng không quan trọng |
| **XMD** | Đất xi măng (CDM) | Drained | **LE** ($E_c = 75 q_u/2$) | **LE** hoặc **MC** ($c \approx q_u/2$, $\varphi$ nhỏ) | TCVN 9403: composite tuyến tính đủ cho lún |

> **Quy tắc kép cho Lớp 1 (sét mềm):** Trong cùng một mô hình Plaxis có thể dùng **2 cluster vật liệu khác nhau cho cùng lớp** — một cluster HS cho phần dưới tải đắp (vùng chuyển vị cắt lớn), một cluster SS cho vùng xa (vùng cố kết thuần tuý). Đây là kỹ thuật "**zoned constitutive model**" hợp lệ trong Plaxis.

---

## 4. Ma trận áp dụng theo Zone × Bài toán

Bảng dưới đề xuất lựa chọn mô hình theo (zone, loại bài toán phân tích, bước thiết kế):

### 4.1 Zone KE (kè công viên — kè đường ô tô + cọc CDM + cọc ván SW)

| Bài toán | Bước | Model lớp 1 | Model XMD | Model cát/sét cứng | Phase Plaxis |
|---|:---:|---|---|---|---|
| Tính lún cố kết kè đắp | TKCS | MC (Undrained A) + SC | LE | MC | Plastic + Consolidation |
| Tính lún cố kết kè đắp | TKBVT | **SS** (Drained) | LE | HS | Plastic + Consolidation Biot |
| Ổn định mái dốc kè | TKCS | MC ($S_u$, φ=0) | LE | MC | Safety (φ/c reduction) |
| Ổn định mái dốc kè | TKBVT | **SS** (Drained, $c'$, $\varphi'$) | MC ($c = q_u/2$) | MC | Plastic + Safety |
| Chuyển vị cọc cừ SW | TKBVT | **HS** + spring (Winkler) | LE | HS | Staged Construction |
| Lún thứ cấp (50 năm) | TKBVT | **SSC** | LE | HS | Consolidation dài hạn |

### 4.2 Zone BXN (bãi xe ngầm — tầng hầm sâu)

| Bài toán | Bước | Model lớp 1 | Model XMD | Model cát/sét cứng | Phase Plaxis |
|---|:---:|---|---|---|---|
| Hố đào tầng hầm | TKCS | MC ($S_u$) | LE | MC | Plastic |
| Hố đào tầng hầm | TKBVT | **NGI-ADP** hoặc **HSsmall (Undr A)** | LE | **HSsmall** | Staged Construction |
| Bottom heave + dòng thấm | TKBVT | **HSsmall** + Biot | LE | HSsmall | Plastic + Flow + Consolidation |
| Tường vây / cọc cừ + anchor | TKBVT | HSsmall | LE | HSsmall | Staged + Updated Mesh |
| Lún công trình lân cận | TKBVT | **HSsmall** | LE | HSsmall | Plastic |

### 4.3 Zone NHC (nhà hành chính — móng + tải cao)

| Bài toán | Bước | Model lớp 1 | Model XMD | Model cát/sét cứng | Phase Plaxis |
|---|:---:|---|---|---|---|
| Lún tổng hợp | TKCS | MC (Undr A) + SC | LE | MC | Plastic + Consolidation |
| Lún tổng hợp | TKBVT | **HS + SS** (zoned) | LE | HS | Plastic + Consolidation Biot |
| Chênh lún cột-cột (TCVN 4253) | TKBVT | **HSsmall** | LE | HSsmall | Plastic |
| Cọc khoan nhồi đứng cứng | TKBVT | HS | LE | HS ($m=0{,}5$) | Staged Construction |
| Tải động (rung động) | TKBVT | **HSsmall** | LE | HSsmall | Dynamic |

---

## 5. Dữ liệu hiện có & cần bổ sung

### 5.1 Đã đủ dùng MC + HS + SS (TKCS hiện tại)

Tham số đã có từ SQLite TTHC + soil_presets:

| Thông số | Nguồn | Số HK có |
|---|---|---|
| $\gamma_{sat}, \gamma_{unsat}$ | `lab_tests` | 12+17+23 = 52 HK |
| $C_c, C_s, e_0, P_C$ | `lab_tests` (oedometer) | KE 0, BXN 39, NHC 33 mẫu |
| $C_u$ (UU phòng) | `lab_tests` | 50+ mẫu |
| $C_u$ (VST hiện trường) | `vane_shear_tests` | KE 110, BXN 50, NHC 0 |
| $N_{SPT}$ | `spt_values` | KE 248, BXN ~340, NHC ~460 |
| $\varphi, c$ (cắt trực tiếp) | `lab_tests` | đủ |

→ **TKCS bằng MC + HS + SS đã chạy được** (đó là lý do app `app_cdm.py` + module CDM hoạt động).

### 5.2 Cần bổ sung để nâng cấp model

| Mô hình | Tham số thiếu | Thí nghiệm cần |
|---|---|---|
| **HSsmall** | $G_0^{ref}, \gamma_{0{,}7}$ | Bender Element / Cross-hole seismic |
| **SSC** | $C_\alpha$ | Oedometer kéo dài 24h+ |
| **NGI-ADP** | $S_u^A, S_u^P, S_u^{DSS}$ riêng biệt | CK0U triaxial + DSS |
| **MCC** | $\lambda, \kappa$ riêng + $M$ | CIU triaxial 3 ứng suất |
| **UBCSAND** | $(N_1)_{60}, K_2^e, m_e, n_e$ | SPT + cyclic triaxial |

**Khuyến nghị TKBVT cho TTHC:** Bổ sung 6 mẫu bender element trong sét Lớp 1 (mỗi zone 2 mẫu) → kích hoạt HSsmall cho cả hố đào BXN và phân tích lún NHC. Bender Element rẻ, nhanh (~3 ngày), giá trị thông tin cao.

---

## 6. Lưu ý áp dụng & sai lầm phổ biến

### 6.1 Drainage type — Quy tắc kép

Plaxis có 4 chế độ drainage:

| Chế độ | Ứng dụng | Khi nào dùng |
|---|---|---|
| **Drained** | Cát mọi lúc, sét tính dài hạn | $k > 10^{-4}$ cm/s hoặc $t > 10 \cdot t_{90}$ |
| **Undrained A** | Sét ngắn hạn, áp dụng $c', \varphi'$ + tính $\Delta u$ | Hố đào, tải nhanh |
| **Undrained B** | Sét ngắn hạn, dùng $c', \varphi'$ + Skempton A | Khi đã có Skempton A từ thí nghiệm |
| **Undrained C** | Sét ngắn hạn, dùng $S_u$ trực tiếp ($\varphi = 0$) | Khi chỉ có $S_u$ — phân tích tổng ứng suất |

**Sai lầm phổ biến:** Dùng $S_u$ với Drained → cường độ giảm theo $\sigma'_v$ giảm → kết quả sai. Phải dùng Undrained C khi chỉ có $S_u$.

### 6.2 Tham số ban đầu (Initial Stress)

- **Phase Initial:** Tính $\sigma'_{v0}, K_0 \cdot \sigma'_{v0}$ — dùng **gravity loading** cho địa tầng nghiêng, **$K_0$-procedure** cho địa tầng bằng (TTHC bằng → dùng $K_0$).
- $K_0$ cho **sét OC** Lớp 5: $K_0 = (1 - \sin\varphi) \cdot OCR^{\sin\varphi}$ (Mayne & Kulhawy 1982).

### 6.3 OCR và POP — chọn cái nào

PLAXIS cho phép nhập **POP** (Pre-Overburden Pressure) HOẶC **OCR** — không nhập cả hai.

- **OCR** cho lớp đồng nhất chiều sâu nhỏ (OCR ≈ hằng số): dễ hiểu.
- **POP** cho lớp sâu, OCR giảm theo độ sâu: $POP = P_c - \sigma'_{v0}$ thường gần hằng số → POP ổn định hơn OCR cho cùng lớp đất.

**TTHC:** Lớp 1 ở NHC có $OCR \approx 1{,}5$ (tính từ $P_c = 74{,}4$ kPa) — dùng OCR. Lớp 1 ở BXN có $OCR \approx 2{,}5$ (P_c cao bất thường, có thể do giải nén bề mặt) — dùng POP.

### 6.4 ψ (góc giãn nở) cho cát

$$\psi = \max(\varphi - 30°,\ 0)$$

- $\varphi = 30°$ → $\psi = 0$ (cát rời/vừa chặt).
- $\varphi = 36°$ → $\psi = 6°$ (cát chặt).

**Với HS undrained**: bắt buộc $\psi = 0$ vì $\psi > 0$ + undrained → ứng suất lỗ rỗng âm vô hạn.

### 6.5 Time step Biot consolidation

Plaxis kiểm tra $\Delta t > \Delta t_{crit}$ với:

$$\Delta t_{crit} = \frac{(\Delta h)^2 \cdot \gamma_w}{k \cdot E_{oed}}$$

Nếu nhỏ hơn → kết quả không hội tụ. Sai lầm phổ biến: chọn $\Delta t$ quá nhỏ ở giai đoạn đầu → cảnh báo "Time step too small".

---

## 7. Workflow áp dụng vào dự án

### 7.1 TKCS (đang triển khai trên app 8503)

Hiện app `app_cdm.py` đang dùng **mô hình giải tích thuần** (không Plaxis):

- Lún cố kết — TCCS 41 Phụ lục A (Cc/Cs) — tương đương SS analytical
- Ổn định tổng thể — Bishop slice — tương đương MC + Safety
- Nội lực tường cừ — Winkler + Rankine — tương đương MC simplified

Đã đủ TKCS theo tinh thần TCVN 9362 / TCCS 41. **Không cần Plaxis ở giai đoạn này.**

### 7.2 TKBVT (giai đoạn nâng cấp tiếp theo)

Khi chuyển sang TKBVT, **bắt buộc** dùng Plaxis 2D cho:

| Đề tài | Model khuyến nghị |
|---|---|
| Lún cố kết KE chi tiết (50 năm) | **SS + SSC** + Biot consolidation |
| Hố đào tầng hầm BXN | **HSsmall** (Undrained A) + Staged + Updated Mesh + Flow |
| Lún NHC dưới tải tầng cao | **HS + SS zoned** + Biot |
| Cọc cừ SW + đất xung quanh (KE) | **HS** + plate + connection |
| Cọc CDM composite | **LE** cho cluster XMD + **HS** xung quanh |

### 7.3 Pipeline Python ↔ Plaxis API

Khi chuẩn bị dữ liệu cho Plaxis, dùng `plxscripting` (theo CLAUDE.md mục 1):

```python
from plxscripting.easy import new_server
g_i, _ = new_server('localhost', 10000, password=os.environ['PLAXIS_PASSWORD'])

# Tạo material HS từ preset
preset = soil_presets['hardening_soil']['typical_tphcm'][0]  # hs_lop1_bun_set
mat = g_i.soilmat()
mat.SoilModel = 3  # 3 = HS
mat.gammaUnsat = preset['gamma_unsat']
mat.gammaSat   = preset['gamma_sat']
mat.E50ref     = preset['_derived']['E50ref']
mat.Eoedref    = preset['_derived']['Eoedref']
mat.Eurref     = preset['_derived']['Eurref']
mat.phi        = preset['phi']
mat.c          = preset['c']
mat.power      = preset['_derived'].get('m', 1.0)
mat.nuur       = preset.get('nu_ur', 0.20)
mat.pref       = 100
mat.Rf         = 0.90
mat.DrainageType = 'UndrainedA'
mat.Identification = 'L1_BunSet_HS'
```

Mỗi preset trong `soil_presets.json` đã có đủ tham số để tự động tạo material — chỉ cần loop và `setattr`.

---

## 8. Tham khảo

### Tiêu chuẩn

- **TCVN 9362:2012** — Khảo sát địa kỹ thuật xây dựng.
- **TCVN 4253:2012** — Móng nhà cao tầng.
- **TCCS 41:2022** — Khảo sát thiết kế nền đường ô tô.
- **TCVN 9403:2012** — Gia cố nền đất yếu bằng trụ đất xi măng.

### Manuals & sách

- **PLAXIS 2D 2024.2 — Material Models Manual** (Bentley Systems, 2024). Reference chính: §3 MC, §6 HS, §7 HSsmall, §10 SS, §11 SSC, §13 NGI-ADP, §16 Hoek-Brown.
- **PLAXIS 2D — Tutorial Manual** Lessons 4, 5, 8, 12 — practical examples.
- Schanz T., Vermeer P.A., Bonnier P.G. (1999). *The Hardening Soil model: formulation and verification*. **Beyond 2000 in Computational Geotechnics**, Balkema.
- Brinkgreve R.B.J., Engin E., Engin H.K. (2010). *Validation of empirical formulas to derive model parameters for sands*. **NUMGE 2010**, Trondheim.
- Andersen K.H. (2015). *Cyclic soil parameters for offshore foundation design — NGI-ADP*. **Frontiers in Offshore Geotechnics III**, ISFOG.
- Wood D.M. (1990). **Soil Behaviour and Critical State Soil Mechanics**. Cambridge University Press.
- Roscoe K.H., Burland J.B. (1968). *On the generalised stress-strain behaviour of "wet" clay*. **Engineering Plasticity**, Cambridge.

### Tài liệu dự án

- [13-hardening-soil-model.md](13-hardening-soil-model.md) — Lý thuyết HS đầy đủ.
- [15-soil-profile-202605-TTHC.md](15-soil-profile-202605-TTHC.md) — Địa tầng 12 lớp.
- [data/soil_presets.json](data/soil_presets.json) — Catalog material presets cho MC + HS + SS.
- [50-fem2d-roadmap.md](50-fem2d-roadmap.md) — Roadmap MC plasticity tự viết (Phase P2).
- [55-cdm-zoning-principles.md](55-cdm-zoning-principles.md) — Phân vùng CDM (P1–P7).

---

## 9. Kết luận

1. **MC đủ cho TKCS** — app hiện tại + các script analytical đều dùng MC dưới dạng failure criterion. Không cần nâng cấp model trong giai đoạn này.

2. **HS + SS là cốt lõi TKBVT** cho TTHC:
   - **Lớp 1 (bùn sét)** — HS cho chuyển vị cắt + SS cho lún cố kết (zoned).
   - **Lớp 2/3/4/5 (cát + sét cứng)** — HS với $m$ thích hợp.
   - **XMD** — LE (TCVN 9403 đã cho phép).

3. **HSsmall bắt buộc cho hố đào BXN** — bottom heave + chuyển vị tường + ảnh hưởng lân cận. Cần bổ sung Bender Element để có $G_0$.

4. **SSC cho lún thứ cấp KE** — dự báo 50 năm, ảnh hưởng độ bằng phẳng P7 (file 55).

5. **NGI-ADP** — tùy chọn nâng cao cho hố đào BXN nếu cần độ chính xác cao về cường độ dị hướng. Cần CK0U + DSS — chưa có ở TTHC.

6. **Không cần** UBCSAND (không phân tích hoá lỏng), Hoek-Brown (không có đá), MCC (SS đã đủ), UDSM (mô hình built-in đủ dùng).

### Bước tiếp theo gợi ý

- [ ] Bổ sung material presets cho cát Lớp 2/4 + sét cứng Lớp 5 vào `soil_presets.json` (hiện có chính cho Lớp 1).
- [ ] Tạo script `scripts/plaxis_material_setup.py` — auto load preset → tạo material Plaxis qua plxscripting.
- [ ] Đề xuất thí nghiệm bender element cho TKBVT (6 mẫu × ~1 triệu VND/mẫu).
- [ ] Xây dựng template Plaxis 2D cho 3 bài toán cốt lõi (KE kè + BXN hố đào + NHC móng) — workflow đầy đủ tham số.
- [ ] Cập nhật CLAUDE.md mục mới với quy tắc chọn model theo zone + drainage type.
