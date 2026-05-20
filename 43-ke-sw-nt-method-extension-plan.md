# 43 — Kế hoạch Mở rộng NT1/NT2 — Bổ sung Cát + Đa phương pháp

**Trạng thái:** ĐÃ TRIỂN KHAI Phương án A (2026-05-20) — bước 1-10 hoàn tất
**Ngày tạo:** 2026-05-20
**Tiêu chuẩn:** TCVN 11823-10:2017 Điều 7.3.8.6 — sức chịu tải cọc đóng theo đất nền
**Liên quan:**
- Doc lý thuyết: [18-driven-pile-TCVN11823.md](18-driven-pile-TCVN11823.md)
- Doc α-method hiện tại: [42-ke-sw-nt1-nt2-chi-tiet.md](42-ke-sw-nt1-nt2-chi-tiet.md)
- Engine: [scripts/ke_sw_nt_calc.py](scripts/ke_sw_nt_calc.py)
- UI: [scripts/app_cdm.py](scripts/app_cdm.py) — tab `ke_sw` (Section B + C)

---

## 1. Hiện trạng (đã có)

| Thành phần | Trạng thái |
|---|---|
| **NT1** = `L_req = fill + D_bottom_soft + min_pen` | Đầy đủ, Z + đáy lớp '1'/'XMD' đọc từ SQLite |
| **NT2 α-method (sét)** `Rs = α·Su·P·L`, `Rp = 9·Su·Ap`, `RR = 0.35(Rs+Rp)` | Đầy đủ |
| Su priority **VST → lab (Cu_UU/c_kPa) → SU_BY_SYMBOL** + warnings | Đủ |
| SQLite `ke_sw_nt_detail` (24 cột) + `ke_sw_nt2_layers` (su/source/α/Rs từng lớp) | Đủ |
| Tab Section B (bảng tổng hợp 7 HK) + expander chi tiết | Đủ |
| Tab Section C (kiểm tra thủ công α-method) | Đủ |

---

## 2. Khoảng trống (so với doc 18)

| Mục doc 18 | Thiếu trong app |
|---|---|
| **18.5 SPT-Meyerhof — qs cát:** `qs = 0.0019·N₁₆₀` (chiếm chỗ) hoặc `0.00096·N₁₆₀` (chữ H/ống hở) | `SAND_SYMBOLS` đang để Rs = 0 → bỏ ma sát lớp 2a/2b/2c/4/5a/6/7 |
| **18.5 qp cát:** `qp = 0.038·N₁₆₀·(Db/D) ≤ λq` với `λq = 3.2·N₁₆₀` MPa (cát) | Khi mũi cọc trong lớp cát → Rp = 0 |
| **18.3 β-method** (sét, OCR): `qs = β·σ'v` | Chưa có |
| **18.4 λ-method** (cọc ống): `qs = λ·(σ'v + 2Su)` | Chưa có |
| **φ_stat theo phương pháp:** α=0.35 / β=0.25 / λ=0.40 / SPT=0.30 (Bảng 9) | Hard-code 0.35 |
| **N₁₆₀ hiệu chỉnh áp lực phủ:** `CN = √(100/σ'v)` (Điều 4.6.2.4) | Đang đọc N thô từ `spt_values` |

---

## 3. Phương án Triển khai

### Phương án A (tối thiểu — KHUYẾN NGHỊ cho dự án KE TTHC)

Mở rộng α-method hiện có để xử lý cả lớp cát bằng SPT-Meyerhof.

**Thay đổi engine `ke_sw_nt_calc.py`:**
1. Thêm hàm `_get_N160_for_layer(bh_name, depth_top, depth_bot)` đọc `spt_values`, hiệu chỉnh `CN = √(100/σ'v_kPa)` rồi clamp `CN ∈ [0.5, 2.0]`.
2. Thêm hàm helper `_sigma_v_eff(layers, depth_mid, water_lvl)` tính `σ'v` tại độ sâu giữa lớp (cần dung trọng γ mỗi lớp — đọc từ `lab_tests` AVG).
3. Trong `calc_nt2_layers`: khi `symbol ∈ SAND_SYMBOLS` → tính `Rs_lyr = 0.0019·N₁₆₀·P·L` (SW = cọc chiếm chỗ; đơn vị MPa·mm² → N, đổi sang kN).
4. Khi mũi cọc trong lớp cát → `Rp = 0.038·N₁₆₀·(Db/D)·Ap` (MPa·mm²/mm·mm² → N), với `Db` = chiều sâu mũi trong tầng cát chịu lực.
5. Tách `φ_stat`: nếu mọi lớp ma sát là sét → 0.35; có lớp cát đóng góp Rs > 10% → 0.30 (Bảng 9 — chọn phương pháp chủ đạo).

**Schema bổ sung `ke_sw_nt2_layers`:**
```sql
ALTER TABLE ke_sw_nt2_layers ADD COLUMN N160 REAL;
ALTER TABLE ke_sw_nt2_layers ADD COLUMN method TEXT;  -- 'alpha' | 'SPT'
ALTER TABLE ke_sw_nt2_layers ADD COLUMN sigma_v_eff_kPa REAL;
```

**UI Section B (bảng chi tiết):** thêm cột "Phương pháp", "N₁₆₀" bên cạnh "α/su" hiện có.

**UI Section C (kiểm tra thủ công):** thêm tab bên cạnh α-method → SPT-Meyerhof với input `N₁₆₀`, `Db`, `D`, loại cọc (chiếm chỗ / không chiếm chỗ).

### Phương án B (đầy đủ — cho tương lai)

Bổ sung thêm β-method và λ-method:
- Section C có dropdown `Phương pháp = α / β / λ / SPT-Meyerhof` cho từng lớp sét.
- Lookup `φ_stat` tự động theo phương pháp được chọn (0.35 / 0.25 / 0.40 / 0.30).
- Cần thêm input OCR cho β-method (đọc từ `PC/σ'v` nếu có trong `lab_tests`).
- λ-method cần `σ'v` tại điểm giữa toàn bộ chiều dài cọc trong sét + Su trung bình.

---

## 4. Thứ tự công việc khi tiếp tục

1. [x] Đọc tài liệu 18, khảo sát code + SQLite — XONG
2. [x] Thêm `_get_N160_for_layer` + `_sigma_v_eff_at_depth` + `_get_gamma_for_layer` vào `ke_sw_nt_calc.py`
3. [x] Mở rộng `calc_nt2_layers` để xử lý lớp cát SPT-Meyerhof + tip Rp cát + φ_stat động
4. [x] ALTER schema: `ke_sw_nt_detail` (thêm Rs_clay/Rs_sand/tip_method/tip_N160/phi_basis); `ke_sw_nt2_layers` (thêm method/N160/sigma_v_eff_kPa/gamma_kNm3)
5. [x] Re-run `calc_all_alignment_hks()` — 7 HK cập nhật, warnings rõ ràng cho sand-no-SPT
6. [x] UI Section B: cột Phương pháp + N₁₆₀ + γ + σ'v. Section C.2 mới: form SPT-Meyerhof độc lập
7. [x] Test KE-HK2 (tip clay) + KE-HK3/7/8/9/11 (tip sand, warning Rp=0) — đúng kỳ vọng
8. [x] Explore agent cross-check — qs/qp/λq đúng, đã fix σ'v cross-MNN chia lớp đôi
9. [x] Update doc 42 với phần SPT method (Section 0)
10. [x] Deploy

**Phương án B (β/λ)** chỉ thêm khi có yêu cầu cụ thể — không cần cho dự án KE TTHC hiện tại.

---

## 5. Đơn vị (BẮT BUỘC kiểm tra)

TCVN 11823-10 dùng **MPa và mm**:
- `qs, qp`: MPa
- `Ap, As`: mm²
- `Rn, RR`: N → đổi sang kN (÷1000) trước khi so sánh `W_kN`

Engine hiện tại của α-method đang dùng **kN/m² và m** (kết quả đúng vì `α·Su[kN/m²]·P[m]·L[m]` = kN). Khi thêm SPT phải nhất quán: tốt nhất viết riêng `_qs_spt_kN_per_m(N160, P_m, displacing=True)` trả về kN/m rồi nhân `L_m`.

Công thức SPT đổi đơn vị:
```
qs_kPa = 0.0019 × N160 × 1000  (MPa → kPa)
       = 1.9 × N160  kPa
Rs_kN  = (1.9 × N160) × P_m × L_m  (kN)
```

```
qp_kPa = 0.038 × N160 × (Db_m / D_m) × 1000  (MPa → kPa)
       = 38 × N160 × Db/D  kPa  ≤  λq = 3200 × N160  kPa
Rp_kN  = qp_kPa × Ap_m2  (kN)
```
