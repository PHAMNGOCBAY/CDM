# 59 — Kết Quả Thí Nghiệm Quảng Trường Trung Tâm TTHC (QTTTTP)

**Nguồn:** `260524 QTTT TP. KQTN.xls` (sheet M)  
**Script import:** [scripts/qtt_lab_import.py](scripts/qtt_lab_import.py)  
**JSON output:** [data/qtt_lab_tests_202605_TTHC.json](data/qtt_lab_tests_202605_TTHC.json)  
**SQLite:** bảng `lab_tests` — `borehole_id` của QTTTTP-ND-02, ND-06, ND-07  
**Ngày lấy mẫu:** 08–21/05/2026 (ND-02: 11–12/05, ND-06: 11–12/05, ND-07: 08–10/05)

---

## 1. Tổng quan mẫu thí nghiệm

| Hố khoan | Mẫu nguyên dạng (U) | Mẫu phá huỷ (D) | Tổng |
|---|:---:|:---:|:---:|
| QTTTTP-ND-02 | 10 | 1 | 11 |
| QTTTTP-ND-06 | 12 | 0 | 12 |
| QTTTTP-ND-07 | 13 | 0 | 13 |
| **Tổng** | **35** | **1** | **36** |

**Lưu ý:** ND-03, ND-04, ND-05 không có trong file KQTN này.

---

## 2. Loại thí nghiệm thực hiện

| Mã `type_code` | Ý nghĩa | Số mẫu |
|---|---|:---:|
| `uu` | Thí nghiệm nén ba trục UU (không cố kết — không thoát nước) | 3 |
| `cu` | Thí nghiệm nén ba trục CU (cố kết — không thoát nước) | 3 |
| `uu-cu` | Cả UU và CU trên cùng mẫu | 3 |
| ` ` | Chỉ thí nghiệm cơ lý thông thường (không triaxial) | 27 |

---

## 3. Kết quả thí nghiệm tổng hợp

### 3.1 Thông số vật lý (lớp bùn sét CH)

| Hố khoan | γ (kN/m³) | γ_dry (kN/m³) | e₀ | Ip (%) | w (%) |
|---|:---:|:---:|:---:|:---:|:---:|
| ND-02 (TB) | 14,6–17,0 | — | 1,31–2,45 | 37–42 | — |
| ND-06 (TB) | 14,2–19,7 | — | 0,66–2,57 | — | — |
| ND-07 (TB) | 14,0–19,7 | — | 0,65–2,62 | — | — |

**Nhận xét:** e₀ = 1,3–2,6 đặc trưng cho bùn sét rất yếu đến yếu tại TTHC HCM; giảm dần theo chiều sâu.

### 3.2 Thí nghiệm UU (cắt không thoát nước)

| Mẫu | HK | Độ sâu (m) | Cu = c_UU (kPa) | φ_UU (°) |
|---|---|:---:|:---:|:---:|
| U1 | ND-02 | 3,4–4,0 | **12,6** | 4,15 |
| U7 | ND-02 | 15,4–16,0 | **12,2** | 3,98 |
| U12 | ND-02 | 25,4–26,0 | **31,7** | 9,63 |
| U4 | ND-06 | 9,4–10,0 | **12,5** | 4,42 |
| U10 | ND-06 | 21,4–22,0 | **32,1** | 9,08 |
| U12 | ND-06 | 25,4–26,0 | **17,6** | 6,10 |

**Cu trung bình lớp 1 CH (3–24 m):** ≈ **12,4 kPa** (ND-02 U1, U7; ND-06 U4)  
**Cu tăng theo chiều sâu:** 12–13 kPa (nông) → 17–32 kPa (>24 m, lớp cứng hơn)

### 3.3 Thí nghiệm CU (cố kết không thoát nước)

| Mẫu | HK | Độ sâu (m) | c_CU (kPa) | φ_CU (°) | c'_CU (kPa) | φ'_CU (°) |
|---|---|:---:|:---:|:---:|:---:|:---:|
| U3 | ND-02 | 7,4–8,0 | 13,2 | 7,68 | 9,1 | 15,28 |
| U9 | ND-02 | 19,4–20,0 | 12,4 | 7,45 | 8,6 | 15,43 |
| U12 | ND-02 | 25,4–26,0 | 25,0 | 15,52 | 18,2 | 21,67 |
| U2 | ND-06 | 5,4–6,0 | 11,7 | 7,27 | 8,3 | 15,43 |
| U9 | ND-06 | 19,4–20,0 | 24,3 | 15,38 | 17,2 | 22,58 |
| U12 | ND-06 | 25,4–26,0 | 18,2 | 9,25 | 12,2 | 18,12 |

**TB lớp 1 CH:** c_CU ≈ **12–13 kPa**, φ_CU ≈ **7,5°** · c'_CU ≈ **8–9 kPa**, φ'_CU ≈ **15°**

### 3.4 Thí nghiệm nén cố kết (Oedometer)

| Mẫu | HK | Độ sâu (m) | Cc | Cs | PC (kPa) | Cv (×10⁻³ cm²/s) |
|---|---|:---:|:---:|:---:|:---:|:---:|
| U1 | ND-02 | 3,4–4,0 | 0,889 | — | 55,0 | — |
| U7 | ND-02 | 15,4–16,0 | 0,938 | — | 50,9 | — |
| U12 | ND-02 | 25,4–26,0 | 0,223 | — | 97,8 | — |
| U2 | ND-06 | 5,4–6,0 | 0,979 | — | 52,8 | — |
| U8 | ND-06 | 17,4–18,0 | 0,996 | — | 50,6 | — |
| U10 | ND-06 | 21,4–22,0 | 0,245 | — | 95,1 | — |
| U12 | ND-06 | 25,4–26,0 | 0,735 | — | 62,9 | — |
| U3 | ND-07 | 7,4–8,0 | 0,816 | — | 58,2 | — |
| U8 | ND-07 | 17,4–18,0 | 0,828 | — | 55,4 | — |
| U14 | ND-07 | 29,4–30,0 | 0,253 | — | 98,5 | — |

**Cc trung bình lớp 1 CH (độ sâu 3–25 m):** ≈ **0,88** (rất cao — bùn rất dẻo)  
**PC trung bình lớp 1:** ≈ **52–58 kPa** (hơi cố kết thường, tỷ số OC ≈ 1,0–1,2)  
**Cc lớp 2 / CL-CH (>24 m):** ≈ **0,22–0,25** (thấp hơn nhiều — đất cứng hơn)

---

## 4. So sánh với KE và BXN

| Thông số | QTT (ND-02/06/07) | KE (HK1–12) | BXN (CV-HK1–17) |
|---|:---:|:---:|:---:|
| Cu (lớp 1, nông) | ≈ 12 kPa | ≈ 8–12 kPa | ≈ 8–10 kPa |
| Cc (lớp 1) | **0,82–0,99** | 0,75–1,1 | 0,7–1,0 |
| e₀ trung bình | **2,0–2,4** | 1,8–2,2 | 2,0–2,5 |
| PC (kPa) | 51–59 | 40–65 | 45–60 |
| φ'_CU (lớp 1) | **15,3°** | 14–16° | 13–15° |

**Nhận xét:** QTT có tính chất địa kỹ thuật tương đồng với KE và BXN — đều là bùn sét CH rất yếu, Cc cao, e₀ lớn.

---

## 5. SQLite Schema

### Tra cứu tất cả KQTN QTT

```sql
SELECT b.name, lt.sample_id, lt.depth_from_m, lt.depth_to_m,
       lt.gamma_kNm3, lt.e0, lt.Ip, lt.Cu_UU_kPa, lt.c_CU_kPa, lt.phi_CU_deg,
       lt.c_CU_eff_kPa, lt.phi_CU_eff_deg, lt.Cc, lt.PC_kPa, lt.symbol_tcvn
FROM lab_tests lt
JOIN boreholes b ON lt.borehole_id = b.id
WHERE b.name LIKE 'QTTTTP-%'
ORDER BY b.name, lt.depth_from_m
```

### Tra cứu Cu UU (Su cho thiết kế CDM)

```sql
SELECT b.name, lt.depth_from_m, lt.depth_to_m, lt.Cu_UU_kPa, lt.symbol_tcvn
FROM lab_tests lt
JOIN boreholes b ON lt.borehole_id = b.id
WHERE b.name LIKE 'QTTTTP-%'
  AND lt.Cu_UU_kPa IS NOT NULL
ORDER BY b.name, lt.depth_from_m
```

### Tra cứu thông số cố kết (Cc, PC)

```sql
SELECT b.name, lt.depth_from_m, lt.Cc, lt.Cs, lt.PC_kPa, lt.Cv_cm2s, lt.e0
FROM lab_tests lt
JOIN boreholes b ON lt.borehole_id = b.id
WHERE b.name LIKE 'QTTTTP-%'
  AND lt.Cc IS NOT NULL
ORDER BY b.name, lt.depth_from_m
```

### Cột mới thêm cho QTT (ALTER TABLE)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `gamma_sub_kNm3` | REAL | Dung trọng đẩy nổi (kN/m³) |
| `c_CU_kPa` | REAL | Lực dính CU (kPa) |
| `phi_CU_deg` | REAL | Góc ma sát CU (°) |
| `c_CU_eff_kPa` | REAL | Lực dính CU hữu hiệu (kPa) |
| `phi_CU_eff_deg` | REAL | Góc ma sát CU hữu hiệu (°) |
| `mv` | REAL | Hệ số nén thể tích (cm²/N) |
| `E12_kPa` | REAL | Mô đun biến dạng nén cố kết đoạn 1–2 (kPa) |
| `e_000` … `e_800` | REAL | Hệ số rỗng ở áp lực 0–8 kgf/cm² |
| `a_000_0125` … `a_400_800` | REAL | Hệ số nén từng đoạn áp lực (cm²/kgf) |

---

## 6. Đơn vị Quy đổi

| Trường XLS | Đơn vị gốc | Hệ số | Đơn vị SQLite |
|---|---|:---:|---|
| γ, γ_dry, γ_sub | g/cm³ | × 9,81 | kN/m³ |
| c (cắt phẳng, CU, UU) | kgf/cm² | × 100 | kPa |
| PC, Qu | kgf/cm² | × 100 | kPa |
| Cv | × 10⁻³ cm²/s | × 1e-3 | cm²/s |
| kv | × 10⁻⁷ cm/s | × 1e-7 | cm/s |
| φ (deg + min) | deg°min' | d + m/60 | ° |

---

## 7. Hàm load

```python
import sqlite3, json
from pathlib import Path

def load_qtt_lab_tests(db_path="data/TTHC.sqlite"):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT b.name AS bh_name, lt.*
        FROM lab_tests lt
        JOIN boreholes b ON lt.borehole_id = b.id
        WHERE b.name LIKE 'QTTTTP-%'
        ORDER BY b.name, lt.depth_from_m
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]

# Hoặc đọc JSON snapshot:
data = json.loads(open("data/qtt_lab_tests_202605_TTHC.json", encoding="utf-8").read())
# data["boreholes"] → list 3 BH, mỗi BH có "samples" list
```

---

## 8. Nhận xét kỹ thuật

1. **Cu lớp 1 CH rất thấp** (~12 kPa ở độ sâu 3–16 m) — cần gia cố CDM trước thi công.  
2. **Cc = 0,82–1,00** cho bùn sét nông — lún sơ cấp lớn (tương đương KE/BXN).  
3. **PC ≈ 52–58 kPa** — đất gần như cố kết thường (OCR ≈ 1,0–1,2), lún cố kết lớn.  
4. **Lớp 2 / CL-CH (>24 m): Cc = 0,22–0,25** — đất cứng hơn nhiều, lún nhỏ.  
5. **φ'_CU ≈ 15°** (lớp 1) — dùng cho phân tích ổn định dài hạn (thoát nước hoàn toàn).  
6. **Thiếu KQTN cho ND-03, ND-04, ND-05** — cần bổ sung từ báo cáo địa chất gốc nếu có.
