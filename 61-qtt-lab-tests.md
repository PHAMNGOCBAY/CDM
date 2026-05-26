# 61 — Kết quả thí nghiệm địa chất — Quảng Trường Trung Tâm (QTT)

## Nguồn dữ liệu

| File | Nội dung |
|---|---|
| `QTT-260524 QTT TP. KQTN.xls` (sheet `M`) | Bảng tổng hợp chỉ tiêu cơ lý 36 mẫu, 3 hố khoan |

**Script import:** `scripts/qtt_lab_import.py`  
**JSON:** `data/qtt_lab_tests_202605_TTHC.json`  
**SQLite:** bảng `lab_tests` trong `TTHC.sqlite` (`zone_id=4`)

---

## Hố khoan và số mẫu

| Hố khoan | Số mẫu | Mẫu có Cc/PC | Mẫu có Cu UU | Mẫu có CU |
|---|:---:|:---:|:---:|:---:|
| ND-02 | 11 | 3 | 3 | 2 |
| ND-06 | 12 | 4 | 3 | 4 |
| ND-07 | 13 | 3 | 3 | 3 |
| **Tổng** | **36** | **10** | **9** | **9** |

> ND-03 và ND-05 không có trong file này — chỉ có số liệu phân loại hạt (từ tài liệu cũ).

---

## Thống kê chỉ tiêu chính

### Tính chất vật lý (32 mẫu đất dính)

| Chỉ tiêu | Min | Max | Trung bình |
|---|:---:|:---:|:---:|
| Độ ẩm W (%) | 16,5 | 98,5 | 64,0 |
| Dung trọng tự nhiên γ (kN/m³) | 13,96 | 19,67 | 15,62 |
| Hệ số rỗng e₀ | 0,65 | 2,62 | 1,86 |
| Chỉ số dẻo Ip | 21,2 | 45,1 | 36,0 |

### Nén cố kết (10 mẫu)

| Chỉ tiêu | Min | Max | Trung bình |
|---|:---:|:---:|:---:|
| Chỉ số nén Cc | 0,22 | 1,00 | 0,69 |
| Áp lực tiền cố kết PC (kPa) | 49,6 | 96,6 | 66,4 |

### Cắt không thoát nước UU (9 mẫu)

| Chỉ tiêu | Min | Max | Trung bình |
|---|:---:|:---:|:---:|
| Cu = c UU (kPa) | 12,0 | 32,2 | **19,4** |
| φ UU (°) | ~0 | ~1,5 | ~0,8 |

### Cắt cố kết không thoát nước CU (9 mẫu)

| Chỉ tiêu | Min | Max | Trung bình |
|---|:---:|:---:|:---:|
| c_CU (kPa) | 11,2 | 26,8 | — |
| φ_CU (°) | 7,3 | 15,5 | 10,4 |
| c'_CU hiệu quả (kPa) | 8,3 | 19,0 | — |
| φ'_CU hiệu quả (°) | 15,3 | 23,5 | **18,2** |

---

## Column Mapping — sheet "M" (77 cột, 0-based)

| Col | Trường | Đơn vị gốc | Chuyển đổi |
|---|---|---|---|
| 1 | Tên HK | — | ND-02, ND-06, ND-07 |
| 2 | Số hiệu mẫu | — | D1, U1, U3... |
| 3–4 | Độ sâu From–To | m | giữ nguyên |
| 17 | W% | % | giữ nguyên |
| 18 | γ tự nhiên | g/cm³ | × 9,81 → kN/m³ |
| 19 | γ khô | g/cm³ | × 9,81 |
| 20 | γ' đẩy nổi | g/cm³ | × 9,81 |
| 21 | Gs | — | giữ nguyên |
| 22 | e₀ | — | giữ nguyên |
| 25–28 | wL, wP, Ip, IS | % / — | giữ nguyên |
| 43 | c cắt thẳng | kgf/cm² | × 98,07 → kPa |
| 44 | φ cắt thẳng | độ | giữ nguyên (số) |
| 58 | a₁₋₂ | cm²/kgf | giữ nguyên (raw) |
| 61 | E₁₋₂ | kgf/cm² | × 98,07 → kPa |
| 62 | c_CU | kgf/cm² | × 98,07 |
| 63 | φ_CU | chuỗi "d°m'" | parse → độ thập phân |
| 64 | c'_CU hiệu quả | kgf/cm² | × 98,07 |
| 65 | φ'_CU hiệu quả | chuỗi "d°m'" | parse |
| 66 | c_UU | kgf/cm² | × 98,07 → Cu_UU_kPa |
| 67 | φ_UU | chuỗi "d°m'" | parse |
| 68 | PC | kgf/cm² | × 98,07 → kPa |
| 69 | Cc | — | giữ nguyên |
| 70 | Cs | — | giữ nguyên |
| 71 | cv × 10⁻³ | cm²/s | × 1e-3 |
| 72 | kv × 10⁻⁷ | cm/s | × 1e-7 |
| 75 | Ký hiệu TCVN | — | giữ nguyên |

---

## Nhận xét địa kỹ thuật

- **Lớp 1 (bùn sét CH):** e₀ = 1,86 – 2,62, Cu ≈ 12–25 kPa, Cc ≈ 0,60–1,00 — **rất yếu**, OCR nhỏ (PC ≈ 50–70 kPa).
- **Lớp chuyển tiếp (độ sâu ~25–32m):** Cc giảm xuống 0,22–0,25, PC tăng lên 96 kPa, φ'_CU ≈ 21–23° — **cứng dần**.
- **φ'_CU TB = 18,2°** phù hợp để tính ổn định mái thoát nước dài hạn.
- **Cu TB = 19,4 kPa** dùng cho tính ổn định ngắn hạn không thoát nước và hệ số nền k_h Winkler.
