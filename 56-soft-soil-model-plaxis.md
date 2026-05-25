# 56 — Mô hình Soft Soil PLAXIS cho Dự án TTHC

**Nguồn:** PLAXIS Material Models Manual, Chapter 10 – Soft Soil Model  
**File PDF gốc:** `G:/My Drive/202605-TRUNG TAM HCM/IPNUT-SOFT SOIL MODEL.pdf`  
**Dữ liệu đầu vào:** `data/TTHC.sqlite` — bảng `lab_tests`, `layers`, `boreholes`  
**Kết quả tính toán:** `data/TTHC.sqlite` — bảng `soft_soil_params`  
**Engine tính toán:** `scripts/soft_soil_calc.py`

---

## 1. Điều kiện Áp dụng

Mô hình Soft Soil phù hợp cho:
- Đất sét mềm **gần NC** (normally consolidated hoặc lightly OC, OCR ≤ 2–3)
- Bùn, than bùn, đất hữu cơ
- **Không áp dụng** cho cát, sỏi, đất cứng OC

Dự án TTHC áp dụng cho các lớp: **1, 1b, XMD** (sét bùn, bùn) và lớp **2** tại NHC (sét dẻo mềm, $e_0 > 1$).

---

## 2. Thông số Mô hình và Công thức Chuyển đổi

### 2.1 Modified Compression Index $\lambda^*$

Chuyển đổi từ hệ số nén $C_c$ đo trong thí nghiệm nén cố kết:

$$\lambda^* = \frac{C_c}{2{,}303 \times (1 + e_0)}$$

### 2.2 Modified Swelling Index $\kappa^*$

Chuyển đổi từ hệ số nở $C_s$:

$$\kappa^* = \frac{2 \cdot C_s}{2{,}303 \times (1 + e_0)}$$

Hệ số 2 là quy ước PLAXIS: giả thiết dỡ tải đẳng hướng ($K_0 = 1$) làm tăng gấp đôi chỉ số nở so với công thức Cam-Clay gốc (Bảng 3, PLAXIS Manual).

**Fallback khi không có $C_s$:**

$$C_s = 0{,}15 \times C_c$$

Tỷ lệ $C_s/C_c \approx 0{,}10$–$0{,}25$ cho sét mềm. Giá trị $0{,}15$ bảo thủ ở mức trung bình.

**Kiểm tra tỷ lệ điển hình:**

$$\frac{\lambda^*}{\kappa^*} \approx \frac{C_c}{2 \cdot C_s} \approx 2{,}5\text{–}7{,}0$$

### 2.3 Hệ số Poisson dỡ tải $\nu_{ur}$

$$\nu_{ur} = 0{,}15 \quad \text{(mặc định)}$$

Phạm vi thực tế: $0{,}10$–$0{,}20$.

### 2.4 Góc ma sát $\varphi'$ và Lực dính $c'$

Lấy từ thí nghiệm CU (unconsolidated undrained) hoặc cắt phẳng (direct shear):

| Nguồn ưu tiên | Bảng SQLite | Cột |
|---|---|---|
| 1. CU triaxial (φ hiệu quả) | `lab_tests` | `phi_deg`, `c_kPa` |
| 2. Trực tiếp (φ cắt phẳng) | `lab_tests` | `phi_direct_deg`, `c_direct_kPa` |
| 3. HK gần nhất cùng zone + cùng symbol | `lab_tests` nearest-BH | — |

### 2.5 Hệ số áp lực ngang NC $K_0^{NC}$

Công thức Jaky (1944):

$$K_0^{NC} = 1 - \sin\varphi'$$

PLAXIS tự tính từ $\varphi'$ nếu không nhập tay.

### 2.6 Hệ số M — đường trạng thái tới hạn

**Công thức gần đúng (Eq. 235 — đủ dùng cho thực tế):**

$$M \approx 3{,}0 - 2{,}8 \times K_0^{NC}$$

**Công thức chính xác (Eq. 234 — Brinkgreve, 1994):**

$$M^2 = \frac{3(3 - K_0^{NC})^2 \cdot (1 - 2\nu_{ur}) \cdot (\lambda^*/\kappa^* - 1)}{(1 + 2K_0^{NC})^2 \cdot (1 - 2\nu_{ur}) \cdot \lambda^*/\kappa^* - (3 - K_0^{NC}) \cdot (1 + \nu_{ur})}$$

### 2.7 Điều kiện Ứng suất Ban đầu — OCR và POP

**Over-Consolidation Ratio (OCR):**

$$OCR_i = \frac{P_c}{\sigma'_{v0,i}}$$

Trong đó $\sigma'_{v0,i}$ là ứng suất hữu hiệu thẳng đứng tại **giữa lớp thứ $i$**:

$$\sigma'_{v0,i} = \sum_{j=0}^{i-1} \gamma'_j H_j + \gamma'_i \cdot \frac{H_i}{2}$$

$\gamma' = \gamma_{sat} - \gamma_w$ cho đất dưới mực nước ngầm ($\gamma_w = 10$ kN/m³).

**Pre-Overburden Pressure (POP)** — thay thế cho OCR trong PLAXIS:

$$POP = P_c - \sigma'_{v0}$$

Nếu $POP = 0$: đất NC. Nếu $POP > 0$: đất OC.

---

## 3. Bảng SQLite `soft_soil_params`

Schema đầy đủ:

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | INTEGER PK | Auto |
| `bh_name` | TEXT | Tên HK (vd `KE-HK3`) hoặc zone PA2 (`KE_PA2`) |
| `pa` | TEXT | `'BH'` (per HK) hoặc `'PA2'` (đại diện zone) |
| `symbol` | TEXT | Ký hiệu lớp đất (1, 1b, 2, XMD...) |
| `depth_top_m` | REAL | Độ sâu đỉnh lớp (m) |
| `depth_bot_m` | REAL | Độ sâu đáy lớp (m) |
| `H_i_m` | REAL | Chiều dày lớp (m) |
| `e0` | REAL | Hệ số rỗng trung bình |
| `Cc` | REAL | Hệ số nén $C_c$ |
| `Cs` | REAL | Hệ số nở $C_s$ |
| `phi_deg` | REAL | Góc ma sát hiệu quả (°) |
| `c_kPa` | REAL | Lực dính hiệu quả (kPa) |
| `sigma_v0_kPa` | REAL | Ứng suất hữu hiệu tại giữa lớp (kPa) |
| `PC_kPa` | REAL | Áp lực tiền cố kết $P_c$ (kPa) |
| `OCR` | REAL | Tỷ số quá cố kết |
| `POP_kPa` | REAL | Pre-Overburden Pressure (kPa) |
| `lambda_star` | REAL | $\lambda^*$ |
| `kappa_star` | REAL | $\kappa^*$ |
| `nu_ur` | REAL | $\nu_{ur}$ (mặc định 0.15) |
| `K0_nc` | REAL | $K_0^{NC}$ |
| `M` | REAL | $M$ (gần đúng Eq. 235) |
| `M_exact` | REAL | $M$ (chính xác Eq. 234) |
| `cc_source` | TEXT | Nguồn Cc/Cs: `'lab'` / `'fallback:<BH>(d=Xm)'` |
| `phi_source` | TEXT | Nguồn φ: `'lab'` / `'fallback:<BH>(d=Xm)'` |
| `Cs_inferred` | INTEGER | 1 nếu Cs tính từ 0.15×Cc (không đo) |
| `updated_at` | TEXT | Thời điểm cập nhật |
| `notes` | TEXT | Cảnh báo hoặc ghi chú |

**UNIQUE:** `(bh_name, pa, symbol)` — một HK, một PA, một ký hiệu lớp.

---

## 4. Thứ tự Ưu tiên Lấy Dữ liệu Cc/Cs

```
1. lab_tests HK hiện tại — trung bình tất cả mẫu trong lớp (cùng symbol_tcvn)
2. lab_tests HK gần nhất cùng zone có data cho symbol tương ứng (nearest-BH)
3. Cs = 0.15 × Cc nếu không có Cs (Cs_inferred = 1)
4. Cc = None → không tính → ghi WARNING
```

---

## 5. PA2 — Thông số Đại diện theo Zone

**PA2** = trung bình theo trọng số chiều dày từ tất cả HK được chọn (selected=1) trong zone:

$$\lambda^*_{zone} = \frac{\sum_i H_i \cdot \lambda^*_i}{\sum_i H_i}$$

Tương tự cho $\kappa^*$, $\varphi'$, $c'$, $e_0$. Riêng $OCR$ lấy trung bình số học (không theo chiều dày vì OCR thay đổi theo độ sâu).

**Lưu vào SQLite:** `bh_name = 'KE_PA2'` / `'BXN_PA2'` / `'NHC_PA2'`, `pa = 'PA2'`.

---

## 6. Kết quả Dự kiến TTHC (sơ bộ)

### 6.1 KE — Lớp 1 (sét bùn, $e_0 \approx 1{,}3$–$2{,}1$)

| Thông số | Giá trị điển hình |
|---|---|
| $C_c$ | 0.6–1.2 |
| $C_s$ | 0.08–0.15 |
| $e_0$ | 1.3–2.1 |
| $\lambda^*$ | 0.10–0.22 |
| $\kappa^*$ | 0.010–0.025 |
| $\varphi'$ | 10–20° |
| $K_0^{NC}$ | 0.66–0.83 |
| $M$ | 1.15–1.15 (approx) |

### 6.2 BXN — Lớp 1 (bùn sét, $e_0 \approx 1{,}5$–$2{,}5$)

Tương tự KE nhưng $e_0$ cao hơn → $\lambda^*$ nhỏ hơn một chút.

### 6.3 NHC — Lớp 1 + Lớp 2 (sét dẻo mềm, $e_0 > 1{,}0$)

Lớp 2 NHC có $e_0 > 1{,}0$ từ lab → đưa vào mô hình Soft Soil với $OCR > 1$ thường.

---

## 7. Nhập vào PLAXIS 2D

**Quy trình:**

1. Tạo material set: model = **Soft Soil**, drainage = **Undrained (B)** hoặc **Drained** tuỳ pha
2. Nhập: $\lambda^*$, $\kappa^*$, $\nu_{ur}$, $c'$, $\varphi'$, $\psi = 0$
3. $K_0^{NC}$ và $M$ — để PLAXIS tự tính từ $\varphi'$
4. Trong Initial Conditions: nhập $OCR$ hoặc $POP$ per stress point (hoặc dùng $K_0$-procedure)

**Lưu ý:** Với $\psi = 0$ (dilatancy = 0) và Undrained (B), PLAXIS tính $c_u$ internally từ λ*/κ* — không cần nhập $c_u$ ngoài.

---

## 8. Tham chiếu

- PLAXIS Material Models Manual, Chapter 10: Soft Soil Model
- Brinkgreve, R.B.J. (1994). *Geomaterial Models and Numerical Analysis of Softening.* TU Delft.
- Jaky, J. (1944). The coefficient of earth pressure at rest. *J. Soc. Hung. Eng. Arch.*, 355–358.
- Mesri, G. & Olson, R.E. (1971). Mechanisms controlling the permeability of clays. *Clays and Clay Minerals*, 19, 151–158.
