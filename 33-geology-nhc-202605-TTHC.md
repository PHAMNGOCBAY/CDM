# 33 — Địa chất Nhà Hành Chính (NHC) — Dự án TTHC 2026-05

**Khu vực:** NHC — Nhà Hành Chính, đường Võ Văn Kiệt, An Khánh, Thủ Đức  
**Nguồn dữ liệu:**
| File | Nội dung |
|------|---------|
| `NHC-2. KQTN_14.5.26. NHC. TONG KQTN.xlsx` | 277 mẫu đất (10 HK) — sheet: BTH |
| `NHC-3. CẮT CÁNH_7.5.26-NHC. TTHCHCM. KQCC.pdf` | Cắt cánh — 4 vị trí VST |
| `1. TRỤ_TTHC_Tru hien truong.dwg` | Bản vẽ trụ ĐC (AutoCAD, chưa có PDF) |

**JSON (tra cứu trực tiếp):**
- `data/nhc_lab_tests_202605_TTHC.json` — 277 mẫu
- `data/nhc_vane_shear_202605_TTHC.json` — 4 VST × 12 điểm

**SQLite:** `data/TTHC.sqlite` → `zone_id = 3`

---

## Danh sách Hố khoan

| Tên DB | Tên gốc | Mẫu (UD+D) | Chiều sâu (m) |
|--------|---------|-----------|--------------|
| NHC-BH-01 | BH-01 | 27 | 1.8 – 88 |
| NHC-BH-02 | BH-02 | 28 | 3.4 – 90 |
| NHC-BH-03 | BH-03 | 30 | 1.4 – 100 |
| NHC-BH-05 | BH-05 | 27 | 1.3 – 90 |
| NHC-BH-09 | BH-09 | 29 | 1.4 – 88 |
| NHC-BH-30 | BH-30 | 26 | 1.7 – 88 |
| NHC-BH-31 | BH-31 | 28 | 1.4 – 88 |
| NHC-BH-33 | BH-33 | 27 | 3.4 – 90 |
| NHC-BH-42 | BH-42 | 27 | 1.4 – 90 |
| NHC-BH-44 | BH-44 | 28 | 1.8 – 100 |

> Cao độ và tọa độ chưa có (file trụ ĐC là DWG — cần xuất PDF hoặc đọc trực tiếp).  
> Bộ hố khoan có thể nhiều hơn (BH-01 đến BH-44) nhưng chỉ 10 HK có KQTN.

---

## Thí nghiệm Cắt cánh (VST) — 22 TCN 355-06, thiết bị Geonor

| Vị trí    | Z_ground (m) | n | Chiều sâu (m) | Su (kPa) |
|-----------|-------------|---|--------------|----------|
| NHC-VST1  | 0.875 | 12 | 2.5 – 24.5 | 4.7 – 20.2 (tb 14.5) |
| NHC-VST5  | 2.036 | 12 | 4.0 – 26.0 | 11.9 – 30.8 (tb 19.9) |
| NHC-VST6  | 1.973 | 12 | 4.0 – 26.0 | 11.9 – 50.7 (tb 23.4) |
| NHC-VST7  | 2.340 | 12 | 4.0 – 26.0 | 9.9 – 31.8 (tb 21.4) |

- VST1 dùng cánh nhỏ D=H=7.58 cm, K=1.685×10⁻³ m³ (thiết bị Geonor)
- VST5/6/7 dùng cánh tiêu chuẩn D=6.5/H=13 cm, K=1.006×10⁻³ m³
- Ranh L2/L3 xuất hiện tại điểm sâu nhất VST6 (26m, Su=50.7 kPa, ghi chú trong PDF)

---

## Chỉ tiêu Cơ lý Trung bình theo Ký hiệu TCVN

| Symbol | n | w (%) | e₀ | wL (%) | Ip | φ (°) | c (kPa) |
|--------|---|------|----|-------|----|-------|---------|
| MH-OH  | 22 | 78.3 | 2.152 | 72.9 | 32.0 | 4.39 | 6.4 |
| MH     | 53 | 72.7 | 1.988 | 61.0 | 22.2 | 5.67 | 7.9 |
| ML-OL  |  1 | 78.8 | 2.128 | 44.0 | 13.9 | 4.40 | 6.2 |
| ML     |  3 | 66.6 | 1.859 | 46.0 | 15.6 | 6.00 | 6.4 |
| CH     |  3 | 61.6 | 1.737 | 51.4 | 22.9 | 4.32 | 5.5 |
| CL     | 50 | 22.6 | 0.661 | 38.9 | 17.1 | 17.15 | 29.1 |
| CL-ML  |  5 | 15.0 | 0.532 | 19.9 |  6.5 | 15.79 | 13.7 |
| ML-CL  |  4 | 21.2 | 0.657 | 23.8 |  6.1 | 17.88 | 16.0 |
| SC     |  2 | 17.4 | 0.512 | 23.5 |  9.4 | 15.45 | 16.2 |
| SM     |  1 | 24.5 | 0.732 | 29.3 |  4.9 | 19.55 | 28.2 |

> c từ thí nghiệm cắt phẳng (kPa); φ từ DDMM → DD + MM/60 độ.

---

## Ghi chú Kỹ thuật

- Lớp đất yếu (MH/MH-OH): Su ≈ 5–20 kPa, φ ≈ 4–6°, c ≈ 6–8 kPa — chiều sâu điển hình 0–26m
- NHC có tầng sâu hơn BXN và KE (đến 100m); lớp cứng (CL/SC) bắt đầu từ ~40m
- VST6 ghi nhận Su=50.7 kPa tại 26m (ranh L2/L3) — cao hơn VST1 và VST5/7
- Hố khoan BH-03 và BH-44 sâu nhất (100m) — cung cấp thông tin địa tầng sâu

---

## Query mẫu — TTHC.sqlite

```sql
-- Su profile toàn bộ VST NHC
SELECT vl.name, vs.depth_m, vs.elev_m, vs.Su_kPa, vs.Sp_kPa, vs.St
FROM vane_shear_tests vs
JOIN vst_locations vl ON vl.id = vs.vst_loc_id
WHERE vl.zone_id = 3
ORDER BY vl.name, vs.depth_m;

-- Trung bình MH/MH-OH theo từng BH
SELECT b.name, COUNT(*) n, ROUND(AVG(l.w_pct),1) w, ROUND(AVG(l.e0),3) e0,
       ROUND(AVG(l.phi_deg),2) phi, ROUND(AVG(l.c_kPa),2) c
FROM lab_tests l JOIN boreholes b ON b.id = l.borehole_id
WHERE b.zone_id = 3
  AND l.symbol_tcvn IN ('MH','MH-OH')
GROUP BY b.name ORDER BY b.name;
```
