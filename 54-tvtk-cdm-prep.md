# 54 — Tab TKCS CDM: Chuẩn bị Tính Toán Sơ Bộ (tvtk_prep)

**Vị trí trong app:** `app_cdm.py`, `elif _page == "tvtk_prep":` (sidebar label "Thuyết minh TKCS")  
**Dữ liệu:** `data/TTHC.sqlite` + `data/tvtk_cdm_202605_TTHC.json`  
**Tiêu chuẩn:** TCVN 9403:2012 (Phụ lục B, C), TCCS 41:2022

---

## 1. Mục đích & Bố cục Tab

Tab `tvtk_prep` phục vụ **thiết kế cơ sở (TKCS) cọc CDM** — từ địa tầng thực đo đến dự báo lún sơ bộ. Trải phẳng theo chiều dọc (không dùng `st.tabs()`), cho phép Ctrl+P in PDF toàn bộ.

| Section | Tiêu đề | Nội dung chính |
|---------|---------|---------------|
| 1 | Lựa chọn hố khoan thiết kế | Multiselect 3 zone (KE/BXN/NHC) — `tvtk_bh_cdm.selected` |
| 2 | Địa tầng & SPT | Bảng địa tầng per HK (USCS + chiều sâu lớp) |
| 3 | Tóm tắt kết quả thí nghiệm | Cc, Cs, e₀, PC, Cv, Su — trung bình mỗi zone |
| 4 | Lớp đất yếu (bùn/sét mềm) | Danh sách lớp cần gia cố + H_soft mỗi HK |
| 5 | Thông số thiết kế CDM | Inputs editable + kết quả S1 + chiều dài cọc |

---

## 2. Định nghĩa Lớp Đất Yếu (Section 4)

**Ký hiệu lớp yếu (soft symbols):**

```python
SOFT_SYMBOLS = {'1', '1b', '2', 'XMD'}
```

| Symbol | Mô tả địa chất | Ghi chú |
|--------|---------------|---------|
| `'1'`  | Bùn sét/bùn sét hữu cơ — lớp 1 | Mọi zone |
| `'1b'` | Bùn pha — lớp 1b (KE) | Chỉ xuất hiện ở KE |
| `'2'`  | Sét mềm — lớp 2 | NHC, BXN |
| `'XMD'`| Xen mỏng dải | Xen kẹp trong lớp cứng, vẫn yếu |

**Lưu ý địa tầng theo zone:**

| Zone | Lớp yếu thực tế | Sai lầm cũ |
|------|----------------|-----------|
| KE   | lớp 1 + lớp 1b + lớp XMD (xen) | Thiếu XMD |
| BXN  | lớp 1 (CV-HK) | Đúng |
| NHC  | lớp 1 + lớp 2 | Dùng nhầm lớp 1b → H_soft=5.7m (sai) |

**Query chuẩn:**

```sql
SELECT COALESCE(SUM(depth_bot_m - depth_top_m), 0.0)
FROM layers
WHERE borehole_id = ? AND symbol IN ('1', '1b', '2', 'XMD')
```

---

## 3. Thông Số Thiết Kế CDM (Section 5)

### 3.1 Hàng nhập liệu

**Hàng 1 — Hình học:**

| Input | Đơn vị | Mặc định | Ghi chú |
|-------|--------|---------|---------|
| D cọc | mm | 800 | 400–1200 mm |
| Khoảng cách s | m | 1.8 | 0.8–5.0 m |
| Bố trí lưới | — | Hình vuông | square / triangle |
| Cao độ đỉnh cọc | m | +0.80 | Cao độ tuyệt đối |
| Ngàm lớp cứng | m | 1.0 | Chiều sâu ngàm vào lớp tốt |

**Hàng 2 — Mô đun & Tải trọng:**

| Input | Đơn vị | Mặc định | Ghi chú |
|-------|--------|---------|---------|
| Hệ số k (Ec = k × Cc) | — | 100 | 25–300; TCVN 9403 cho phép 50–100 |
| qu thiết kế | kPa | 800 | Cường độ nén nở hông mục tiêu của cọc |
| q tải | kN/m² | 40.80 | Tải trọng đắp gây lún — dùng chung tất cả HK |

**Metrics tự tính (không editable):**

$$a = \frac{\pi D^2/4}{s^2}$$

$$C_{c,\text{cọc}} = \frac{q_u}{2}$$

$$E_c = k \times C_{c,\text{cọc}}$$

### 3.2 Công thức Lún CDM — TCVN 9403:2012 Phụ lục C

$$S_1 = \frac{q \cdot H}{a \cdot E_c + (1-a) \cdot E_s}$$

Trong đó:

| Ký hiệu | Ý nghĩa | Đơn vị |
|---------|---------|--------|
| $q$ | Tải trọng đắp gây lún | kN/m² |
| $H$ | Chiều dày vùng gia cố (= H_soft trung bình zone) | m |
| $a$ | Tỷ lệ diện tích thay thế | — |
| $E_c$ | Mô đun biến dạng trụ CDM = $k \times C_{c,\text{cọc}}$ | kPa |
| $E_s$ | Mô đun biến dạng đất yếu = $250 \times C_u$ | kPa |

**Hệ số giảm lún:**

$$\text{Giảm lún (\%)} = \left(1 - \frac{S_{1,\text{CDM}}}{S_{\text{không xử lý}}}\right) \times 100$$

$S_{\text{không xử lý}}$ lấy từ `settlement_scenarios` (lún cố kết sơ cấp trung bình từng zone).

### 3.3 Kết quả TTHC (Kịch bản: D=800mm, s=1.8m, k=100, qu=800 kPa)

| Khu vực | Cu_VST (kPa) | H đất yếu (m) | Ec (kPa) | Es (kPa) | S₁_CDM (cm) | Giảm lún |
|---------|-------------|--------------|---------|---------|------------|---------|
| KE      | 13.8        | 23.0         | 40 000  | 3 450   | 10.3       | 93.7%   |
| BXN     | 13.0        | 21.5         | 40 000  | 3 250   | 9.8        | 93.0%   |
| NHC     | 15.0        | 27.4         | 40 000  | 3 750   | 11.9       | 92.5%   |

*qu_design = 800 kPa (cường độ thiết kế mục tiêu); qu_lab từ thí nghiệm sẽ tính ở bước sau.*

---

## 4. Chiều Dài Cọc CDM

$$L_{\text{CDM}} = Z_{\text{đỉnh cọc}} - Z_{\text{tự nhiên}} + H_{\text{đất yếu}} + h_{\text{ngàm}}$$

| Thành phần | Ký hiệu | Giá trị mặc định |
|-----------|---------|----------------|
| Cao độ đỉnh cọc | $Z_{\text{đỉnh}}$ | +0.80 m |
| Cao độ mặt đất tự nhiên tại HK | $Z_{\text{tự nhiên}}$ | Từ `boreholes.elevation_m` |
| Chiều dày lớp đất yếu | $H_{\text{đất yếu}}$ | Từ `layers` — tổng lớp soft |
| Ngàm vào lớp tốt | $h_{\text{ngàm}}$ | 1.0 m |

**Thống kê chiều dài cọc CDM (TTHC):**

| Khu vực | L min (m) | L TB (m) | L max (m) |
|---------|----------|---------|---------|
| KE      | ~21       | ~24     | ~30     |
| BXN     | ~21       | ~23     | ~27     |
| NHC     | ~20       | ~28     | ~40     |

---

## 5. SQLite Schema

### `tvtk_cdm_config` — Thông số do kỹ sư quyết định (Config)

```sql
CREATE TABLE IF NOT EXISTS tvtk_cdm_config (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    D_mm          REAL DEFAULT 800,
    spacing_m     REAL DEFAULT 1.8,
    pattern       TEXT DEFAULT 'square',
    top_elev_m    REAL DEFAULT 0.8,
    penetration_m REAL DEFAULT 1.0,
    q_kPa         REAL DEFAULT 40.8,
    Ec_factor     REAL DEFAULT 100,
    qu_kPa        REAL DEFAULT 800,
    updated_at    TEXT
)
```

**Loại:** Config — kỹ sư quyết định, không tự compute. App đọc trực tiếp từ bảng này.

### `cdm_design` — Kết quả tính toán (Computed)

Cột quan trọng đã thêm so với schema gốc:

| Cột | Loại | Ý nghĩa |
|-----|------|---------|
| `Ec_factor` | REAL | Hệ số k (Ec = k × Cc) |
| `q_kPa` | REAL | Tải trọng đắp đã dùng |
| `S1_cm` | REAL | Lún đàn hồi CDM (cm) |
| `S_reduction` | REAL | S1_CDM / S_no_treat (tỷ số — nhỏ = tốt) |

**Loại:** Computed — auto-update khi bấm "Lưu" trong tab. App đọc từ SQLite (KHÔNG từ JSON).

### `tvtk_bh_cdm` — Lựa chọn HK tính CDM

```sql
-- bh_name TEXT (= boreholes.name với prefix zone), selected INTEGER, H_soft_m REAL
```

**H_soft_m** = tổng chiều dày lớp `symbol IN ('1','1b','2','XMD')` từ `layers`.

### `tvtk_soil_params` — Thông số đất trung bình theo zone

```sql
-- zone_code TEXT, Cc_avg, Cs_avg, e0_avg, PC_kPa_avg, Cv_e4_avg REAL, H_soft_avg_m REAL, n_Cc INT
```

---

## 6. Quy trình Save (Nút "Lưu")

```
User thay đổi input → bấm "Lưu"
  1. UPDATE tvtk_cdm_config SET ... WHERE id=1
  2. Tính lại a, Cc, Ec từ input mới
  3. Lấy S_no_treat từ settlement_scenarios (AVG per zone)
  4. Với mỗi zone trong cdm_design:
       Ecomp = a*Ec + (1-a)*Es
       S1 = q * H / Ecomp * 100 [cm]
       S_reduction = S1 / S_no_treat
       UPDATE cdm_design SET ... WHERE zone_code=?
  5. COMMIT → st.rerun()
```

**Lưu ý:** `settlement_scenarios` phải có dữ liệu trước. Nếu trống → S_reduction = None (hiển thị "—").

---

## 6b. Các mục bổ sung trong tab (cập nhật 2026-05-28)

Ngoài section 1-5 ở trên, tab `tvtk_prep` nay có thêm:

| Mục | Nội dung | Tham chiếu |
|---|---|---|
| Cột địa chất + σ'v0 | Cột địa chất và biểu đồ ứng suất trọng lượng bản thân **cùng trục cao độ** (sharey), đường ranh giới lớp + đường 10% ($\Delta\sigma/\sigma'_{v0}$) | — |
| Thống kê chiều dài cọc CDM | $L = z_{đỉnh} - z_{TN} + H_{soft} + ngàm$ per HK + tổng hợp zone (quy ước đào/đắp) | — |
| **Sức chịu tải cọc CDM** | Per HK: $Q$ nền (AIT, mũi $=9C_uA_c$ + thân), $Q$ vật liệu, $Q_a=\min/FS$ (2,5), **lực nén 1 trụ $P_{col}=\sigma_{col}A_c$ (tập trung ứng suất)**, L cần theo SCT, đạt/không đạt. Lưu `tvtk_cdm_bearing` | `60-cdm-suc-chiu-tai-coc.md` |
| Trắc dọc CDM 3 zone | Mặt cắt dọc tuyến per zone | `47-tvtk-cdm-trac-doc-luong-chinh.md` |

**S2 + chọn chiều dài cọc** (tab "Thông số CDM", khối tối ưu): lặp tăng độ xuyên tới khi $S_1+S_2 \le \Delta S$; S2 đa lớp (cát đàn hồi / sét theo $e_0$ / lún 15 năm); tùy chọn Boussinesq. **Lún (S1, S2) dùng tải đắp tĩnh — KHÔNG xét hoạt tải; sức chịu tải dùng tải tổng (có hoạt tải).** Bảng lặp hiển thị CẢ điều kiện lún VÀ sức chịu tải ($Q$ thân/FS, $Q$ mũi=9·Cu(mũi)·Ac/FS vs $P_{col}$), Cu lấy theo profile VST từng vị trí. Xem `59-cdm-s2-partial.md` Mục 11 + `60-cdm-suc-chiu-tai-coc.md`.

---

## 7. Tham chiếu

- App: `scripts/app_cdm.py` → `elif _page == "tvtk_prep":`
- JSON snapshot: `data/tvtk_cdm_202605_TTHC.json`
- Thông số TCVN 9403: `data/tcvn9403_params.json`
- Tài liệu TCVN 9403: `39-tcvn9403-tru-dat-xi-mang.md` · Lý thuyết: `35-ly-thuyet-cdm.md`
- Module lún cố kết: `scripts/settlement_calc.py` + `38-tccs41-nen-duong-dat-yeu.md`
- Sức chịu tải: `scripts/cdm_column_calc.py` + `60-cdm-suc-chiu-tai-coc.md`
- S2 đa lớp: `59-cdm-s2-partial.md` Mục 11
