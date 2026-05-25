# 57 — Mô hình Đất PLAXIS: MC / HS / SS / LE cho TKCS và TKBVT

**Nguồn:** PLAXIS Material Models Manual Ch. 5 (LE), Ch. 6 (MC), Ch. 7 (HS), Ch. 10 (SS);
TCVN 9403:2012 Phụ lục B (CDM — LE); Bowles (1996), Mesri & Olson (1974), Schanz et al. (1999).  
**Engine:** `scripts/mc_hs_calc.py`  
**Dữ liệu đầu vào:** `data/TTHC.sqlite` — `lab_tests`, `spt_values`, `vane_shear_tests`, `layers`  
**Kết quả:** `data/TTHC.sqlite` — bảng `plaxis_mc_hs_params`  
**Tham chiếu:** `data/plaxis_mc_hs_models.json` · [56-soft-soil-model-plaxis.md](56-soft-soil-model-plaxis.md)

---

## 1. Gán Mô hình theo Giai đoạn Thiết kế

| Lớp | Mô tả | TKCS | TKBVT | $m$ | Ghi chú |
|-----|-------|------|-------|-----|---------|
| 1 | Bùn sét mềm | **MC** | **HS + SS** (zoned) | 1,0 | SS cho lún cố kết |
| 1b | Bùn sét mềm | **MC** | **HS + SS** (zoned) | 1,0 | SS cho lún cố kết |
| 2 | Sét dẻo mềm (NHC/BXN) | **MC** | **HS** (+SS nếu OCR<2) | 0,8 | |
| 2a/2b/2c | Cát hạt mịn–vừa | **MC** | **HS** | 0,5 | SPT-based $E_{50}$ |
| 3 | Cát hạt vừa–thô | **MC** | **HS** | 0,5 | |
| 4 | Sét cứng / sét dẻo | **MC** | **HS** | 0,8 | |
| 5a/5b | Cát sỏi | **MC** | **HS** | 0,5 | |
| 6 / QTT | Tầng phủ / đất đắp | **MC** | **MC** | — | Lớp mỏng |
| XMD | CDM trụ xi măng | **LE** | **LE** | — | TCVN 9403 Phụ lục B |

**Lưu ý zoned (TKBVT):** Trong cùng một mô hình PLAXIS, lớp 1/1b được assign hai polygon:
- **Polygon "ngoài vùng CDM"** → SS (lún cố kết tự nhiên)
- **Polygon "trong vùng CDM"** → HS (composite stiffness, không cần lún cố kết riêng)

---

## 2. Mô hình Mohr-Coulomb (MC) — TKCS

### 2.1 Thông số đầu vào PLAXIS

| Ký hiệu | Tên | Đơn vị | Nguồn |
|---------|-----|---------|-------|
| $E_{ref}$ | Young's modulus | kN/m² | Oedometer hoặc tương quan |
| $\nu$ | Poisson's ratio | — | Bảng 2.3 |
| $c'$ | Lực dính hiệu quả | kN/m² | Lab CU/DS |
| $\varphi'$ | Góc ma sát hiệu quả | ° | Lab CU/DS |
| $\psi$ | Góc giãn nở | ° | 0 cho sét; $\varphi' - 30°$ cho cát chặt |
| $K_0$ | Hệ số áp lực ngang | — | Jaky: $1 - \sin\varphi'$ |

### 2.2 Công thức tính $E_{ref}$

**Ưu tiên 1 — Từ oedometer (a12, e0):**

$$E_{oed} = \frac{1 + e_0}{a_{12} \times 0{,}01} \quad \text{(kPa)}$$

$$E_{ref} \approx E_{oed} \times \frac{1 - 2\nu^2}{1 - \nu}$$

Trong đó:
- $a_{12}$ — hệ số nén từ oedometer (1–2 kgf/cm²), đơn vị cm²/kgf
- Hệ số $0{,}01$: đổi cm²/kgf → kPa⁻¹ ($1\ \text{cm}^2/\text{kgf} \approx 0{,}01\ \text{kPa}^{-1}$)
- $\nu = 0{,}35$ cho sét mềm; $0{,}30$ cho sét cứng/cát

**Ưu tiên 2 — Từ $C_u$ (sét mềm, không có a12):**

$$E_{ref} = 250 \times C_u \quad \text{(kPa)}$$

Nguồn: Mesri & Olson (1974) — $E_s \approx 250 C_u$ cho sét NC.

**Ưu tiên 3 — Từ N-SPT (cát, không có lab):**

$$E_{ref} = 300 \times N_{60} \quad \text{(kPa)}$$

Nguồn: Bowles (1996) — giá trị bảo thủ trung bình.

### 2.3 Giá trị $\nu$ theo loại đất

| Loại đất | $\nu$ (thoát nước) | Ghi chú |
|----------|-------------------|---------|
| Sét mềm / bùn (lớp 1, 1b) | 0,35 | Gần bão hoà, thoát nước chậm |
| Sét dẻo / cứng (lớp 2, 4) | 0,30 | |
| Cát (lớp 2a, 2b, 3, 5a) | 0,30 | |
| CDM / LE (XMD) | 0,25 | Đàn hồi cứng |

### 2.4 Giá trị $\psi$ (dilatancy)

$$\psi = \max(0,\ \varphi' - 30°)$$

Sét mềm và sét cứng: $\psi = 0$. Cát chặt ($\varphi' > 32°$): $\psi > 0$.

---

## 3. Mô hình Hardening Soil (HS) — TKBVT

### 3.1 Thông số bổ sung so với MC

| Ký hiệu | Tên | Đơn vị | Công thức |
|---------|-----|---------|-----------|
| $E_{50,ref}$ | Secant stiffness (q = 0,5 qf) | kN/m² | Xem §3.2 |
| $E_{oed,ref}$ | Tangent oedometer stiffness | kN/m² | $1/m_v = (1+e_0)/(a_{12} \times 0{,}01)$ |
| $E_{ur,ref}$ | Unloading-reloading stiffness | kN/m² | $3E_{50}$ (sét) · $5E_{50}$ (cát) |
| $m$ | Power law exponent | — | 1,0 · 0,8 · 0,5 |
| $p_{ref}$ | Áp suất tham chiếu | kN/m² | 100 (mặc định) |
| $R_f$ | Failure ratio | — | 0,9 (mặc định) |
| $K_0^{NC}$ | Hệ số áp lực NC | — | $1 - \sin\varphi'$ |

### 3.2 Công thức $E_{50,ref}$

**Sét mềm (lớp 1, 1b):**

$$E_{50,ref} = 500 \times C_u \quad \text{(kPa)}$$

Nguồn: Schanz et al. (1999); PLAXIS Manual Ch. 7.

**Sét dẻo / cứng (lớp 2, 4):**

$$E_{50,ref} = 600 \times C_u \quad \text{(kPa)}$$

**Cát (lớp 2a/2b/2c, 3, 5a):**

$$E_{50,ref} = 300 \times N_{60} \quad \text{(kPa)}$$

Nguồn: Bowles (1996). Phạm vi thực tế: $200$–$500 \times N_{60}$. Dùng $300$ cho TKCS bảo thủ.

### 3.3 $E_{ur,ref}$ và tỷ lệ đặc trưng

| Loại đất | $E_{ur}/E_{50}$ | $E_{oed}/E_{50}$ |
|----------|----------------|-----------------|
| Sét mềm NC | 3 | ≈ 0,8 |
| Sét cứng OC | 4 | ≈ 1,0 |
| Cát | 5 | ≈ 0,8 |

### 3.4 Power law $m$ theo loại đất

$$E_{ref}(\sigma_3) = E_{ref}^{lab} \times \left(\frac{c\cos\varphi + \sigma_3 \sin\varphi}{c\cos\varphi + p_{ref}\sin\varphi}\right)^m$$

| Loại đất | $m$ |
|----------|-----|
| Sét mềm / NC clay | 1,0 |
| Sét cứng / OC clay | 0,8 |
| Cát | 0,5 |

---

## 4. Mô hình Linear Elastic (LE) — XMD / CDM

Theo TCVN 9403:2012 Phụ lục B, trụ CDM hoạt động trong vùng đàn hồi tuyến tính dưới tải công trình thông thường:

$$E_c = k \times \frac{q_{u,design}}{2}$$

$$\nu_{LE} = 0{,}25$$

Trong đó:
- $k = 75$–$100$ (mặc định $k = 100$) — hệ số TCVN 9403 B.5.1
- $q_{u,design}$ — cường độ nén đơn trục thiết kế (kPa), đọc từ `tvtk_cdm_config`
- $q_{u,design} / 2 = C_c$ — cường độ cắt trụ CDM (undrained shear strength)

**Ví dụ TTHC** ($q_{u,design} = 800\ \text{kPa}$, $k = 100$):

$$E_c = 100 \times 400 = 40\ 000\ \text{kPa} = 40\ \text{MPa}$$

---

## 5. Mô hình Soft Soil (SS) — Lớp 1/1b TKBVT

Xem tài liệu chi tiết: [56-soft-soil-model-plaxis.md](56-soft-soil-model-plaxis.md)

Thông số cốt lõi:

$$\lambda^* = \frac{C_c}{2{,}303 (1 + e_0)}, \quad \kappa^* = \frac{2 C_s}{2{,}303 (1 + e_0)}$$

Bảng SQLite: `soft_soil_params` (PA2 zone representative).

---

## 6. Schema SQLite `plaxis_mc_hs_params`

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `bh_name` | TEXT | Tên HK (`KE-HK1`) hoặc PA2 (`KE_PA2_MC`) |
| `pa` | TEXT | `'BH'` / `'PA2'` |
| `symbol` | TEXT | Ký hiệu lớp đất |
| `depth_top_m`, `depth_bot_m` | REAL | Độ sâu lớp (m) |
| `H_i_m` | REAL | Chiều dày (m) |
| `gamma_unsat_kNm3` | REAL | Dung trọng khô (kN/m³) |
| `gamma_sat_kNm3` | REAL | Dung trọng bão hoà (kN/m³) |
| `E_ref_kPa` | REAL | Young's modulus (MC) |
| `nu_mc` | REAL | Poisson's ratio (MC) |
| `c_kPa` | REAL | Lực dính $c'$ |
| `phi_deg` | REAL | Góc ma sát $\varphi'$ |
| `psi_deg` | REAL | Góc giãn nở $\psi$ |
| `K0_mc` | REAL | $K_0 = 1-\sin\varphi'$ |
| `E50_ref_kPa` | REAL | $E_{50,ref}$ (HS) |
| `Eoed_ref_kPa` | REAL | $E_{oed,ref}$ (HS) |
| `Eur_ref_kPa` | REAL | $E_{ur,ref}$ (HS) |
| `m_hs` | REAL | Power law $m$ (HS) |
| `pref_kPa` | REAL | $p_{ref} = 100$ kPa |
| `Rf` | REAL | Failure ratio = 0,9 |
| `K0_nc_hs` | REAL | $K_0^{NC}$ (HS) |
| `E_cdm_kPa` | REAL | $E_c$ (LE / XMD) |
| `nu_le` | REAL | $\nu$ (LE) = 0,25 |
| `E_source` | TEXT | Nguồn E: `lab_a12`, `250×Cu`, `300×N_SPT`, `LE:k×qu/2` |
| `c_source`, `phi_source`, `gamma_source` | TEXT | Nguồn dữ liệu |
| `notes` | TEXT | Cảnh báo thiếu dữ liệu |
| `updated_at` | TEXT | Thời điểm cập nhật |

**UNIQUE:** `(bh_name, pa, symbol)` — idempotent UPSERT.

---

## 7. Quy trình Nhập PLAXIS 2D

### TKCS (MC — tất cả lớp):

1. Tạo material set: **Mohr-Coulomb**, drainage = **Undrained (A)** hoặc **Drained**
2. Nhập: $E_{ref}$, $\nu$, $c'$, $\varphi'$, $\psi = 0$
3. $\gamma_{unsat}$, $\gamma_{sat}$ từ cột tương ứng
4. Trong Initial conditions: K0-procedure với $K_0 = 1-\sin\varphi'$

### TKBVT (HS — lớp cát + sét cứng):

1. Tạo material set: **Hardening Soil**
2. Nhập: $E_{50,ref}$, $E_{oed,ref}$, $E_{ur,ref}$, $m$, $p_{ref} = 100$, $R_f = 0{,}9$
3. Strength: $c'$, $\varphi'$, $\psi$
4. $K_0^{NC}$ — PLAXIS tự tính từ $\varphi'$

### TKBVT (LE — XMD / CDM zones):

1. Tạo material set: **Linear Elastic**, drainage = **Non-porous**
2. Nhập: $E_c$, $\nu = 0{,}25$
3. KHÔNG nhập $c'$, $\varphi'$ (LE không có failure criterion)

---

## 8. Giá trị Điển hình TTHC

### Lớp 1 (sét bùn, KE-PA2):

| Thông số | MC (TKCS) | HS (TKBVT) |
|----------|-----------|------------|
| $E_{ref}$ / $E_{50,ref}$ | 1 500–2 500 kPa | 2 000–5 000 kPa |
| $\nu$ | 0,35 | — |
| $c'$ | 3–8 kPa | 3–8 kPa |
| $\varphi'$ | 10–16° | 10–16° |
| $m$ | — | 1,0 |

### Lớp 2a (cát hạt mịn, $N_{SPT} \approx 8$–15):

| Thông số | MC | HS |
|----------|----|----|
| $E_{ref}$ / $E_{50,ref}$ | 3 000–5 000 kPa | 4 000–6 000 kPa |
| $\varphi'$ | 28–32° | 28–32° |
| $m$ | — | 0,5 |

### XMD (CDM, $q_{u,design} = 800$ kPa):

| Thông số | LE |
|----------|----|
| $E_c$ | 40 000 kPa |
| $\nu$ | 0,25 |

---

## 9. Tham chiếu

- PLAXIS Material Models Manual — Chapters 5, 6, 7, 10
- Schanz, T., Vermeer, P.A., Bonnier, P.G. (1999). *The hardening soil model: formulation and verification.* Beyond 2000 in Computational Geotechnics.
- Mesri, G. & Olson, R.E. (1971). *Mechanisms controlling the permeability of clays.* Clays and Clay Minerals, 19, 151–158.
- Bowles, J.E. (1996). *Foundation Analysis and Design.* 5th ed. McGraw-Hill.
- TCVN 9403:2012 — Gia cố nền đất yếu bằng trụ đất xi măng. Phụ lục B — Tính toán trụ CDM.
