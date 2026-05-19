# 32 — Địa chất Bãi Đỗ Xe Ngầm (BXN) — Dự án TTHC 2026-05

**Khu vực:** BXN — Bãi Đỗ Xe Ngầm, đường Võ Văn Kiệt, An Khánh, Thủ Đức  
**Nguồn dữ liệu:**
| File | Nội dung |
|------|---------|
| `BXN-3. KQTN ĐẤT_15.05.2026 BXN-TTHC. KQTN.xls` | 291 mẫu đất (14 HK) — sheet: tong hop (3) |
| `BXN-5. CẮT CÁNH_7.5.26-BXN. TTHCHCM. KQCC.pdf` | Cắt cánh — 5 vị trí VST |
| `BXN-2. TRỤ_BXN-TTHC. Tru DC.pdf` | Trụ địa chất (cần đọc thêm để có cao độ/tọa độ) |

**JSON (tra cứu trực tiếp):**
- `data/bxn_lab_tests_202605_TTHC.json` — 291 mẫu
- `data/bxn_vane_shear_202605_TTHC.json` — 5 VST × 10 điểm

**SQLite:** `data/TTHC.sqlite` → `zone_id = 2`

---

## Danh sách Hố khoan

| Tên DB | Tên gốc | Z (m) | Sâu (m) | X (VN2000) | Y (VN2000) | Mẫu |
|--------|---------|-------|---------|-----------|-----------|-----|
| BXN-CV-HK1  | CV-HK1  | +2.899 | 70 | 1191602.053 | 606114.279 | 14 |
| BXN-CV-HK2  | CV-HK2  | +2.551 | 70 | 1191585.870 | 606077.724 | 21 |
| BXN-CV-HK3  | CV-HK3  | +2.398 | 70 | 1191569.698 | 606041.174 | 23 |
| BXN-CV-HK4  | CV-HK4  | +2.282 | 70 | 1191553.467 | 606004.580 | 22 |
| BXN-CV-HK5  | CV-HK5  | +2.193 | 70 | 1191537.283 | 605968.022 | 21 |
| BXN-CV-HK6  | CV-HK6  | +2.183 | 70 | 1191573.853 | 605951.807 | 18 |
| BXN-CV-HK7  | CV-HK7  | +2.243 | 70 | 1191590.044 | 605988.342 | 21 |
| BXN-CV-HK8  | CV-HK8  | +2.258 | 70 | 1191606.260 | 606024.982 | 21 |
| BXN-CV-HK9  | CV-HK9  | +3.058 | 70 | 1191622.441 | 606061.542 | — |
| BXN-CV-HK10 | CV-HK10 | +3.070 | 70 | 1191638.680 | 606098.186 | — |
| BXN-CV-HK11 | CV-HK11 | +2.983 | 70 | 1191678.381 | 606089.422 | 22 |
| BXN-CV-HK12 | CV-HK12 | +2.708 | 70 | 1191662.015 | 606052.169 | — |
| BXN-CV-HK13 | CV-HK13 | +2.268 | 70 | 1191645.843 | 606015.603 | 21 |
| BXN-CV-HK14 | CV-HK14 | +2.185 | 70 | 1191629.624 | 605979.066 | 19 |
| BXN-CV-HK15 | CV-HK15 | +2.311 | 70 | 1191683.770 | 606002.554 | 23 |
| BXN-CV-HK16 | CV-HK16 | +2.642 | 70 | 1191770.009 | 606039.124 | 23 |
| BXN-CV-HK17 | CV-HK17 | +2.112 | 70 | 1191633.615 | 605966.866 | 22 |

> HK9, HK10, HK12 chỉ có trụ ĐC + SPT, không có KQTN mẫu đất.  
> Tọa độ VN2000, nguồn: BXN-2. TRỤ_BXN-TTHC. Tru DC.pdf (2026-05-18).  
> HK10: tọa độ X điều chỉnh từ OCR artifact 119163.868 → 1191638.680.

---

## Thí nghiệm Cắt cánh (VST) — 22 TCN 355-06, thiết bị Tonichi

| Vị trí       | Z_ground (m) | n | Chiều sâu (m) | Su (kPa) | St  |
|-------------|-------------|---|--------------|----------|-----|
| BXN-CV-VST1 | 2.297 | 10 | 4–22 | 7.9–48.7 (tb 20.3) | 2.0–3.0 |
| BXN-CV-VST2 | 2.112 | 10 | 4–22 | 13.9–29.8 (tb 20.2) | 1.9–5.6 |
| BXN-CV-VST3 | 2.596 | 10 | 4.5–22 | 9.9–32.8 (tb 20.9) | 1.8–5.1 |
| BXN-CV-VST4 | 3.198 | 10 | 3–21 | 5.9–22.5 (tb 16.7) | 2.9–10.7 |
| BXN-CV-VST5 | 2.139 | 10 | 2.5–20 | 6.0–28.8 (tb 14.7) | 2.0–3.0 |

- VST4 dùng cánh nhỏ D=H=7.58 cm, K=1.685×10⁻³ m³ (các VST khác: D=6.5/H=13 cm, K=1.006×10⁻³ m³)
- Ghi chú "Ranh L2/L3" xuất hiện tại điểm sâu nhất VST1 (22m, Su=48.7 kPa)

---

## Chỉ tiêu Cơ lý Trung bình theo Ký hiệu TCVN

| Symbol | n | w (%) | e₀ | wL (%) | Ip | φ (°) | c (kPa) |
|--------|---|------|----|-------|----|-------|---------|
| MH-OH  | 57 | 81.2 | 2.174 | 78.4 | 38.7 | 4.48 | 9.4 |
| CH-OH  |  8 | 84.0 | 2.232 | 77.2 | 40.7 | 3.05 | 5.1 |
| CH     | 32 | 51.2 | 1.421 | 61.3 | 32.9 | 9.91 | 25.3 |
| CL     | 20 | 25.6 | 0.748 | 44.9 | 24.1 | 14.67 | 36.7 |
| SC     | 29 | 24.7 | 0.728 | 35.8 | 14.3 | 16.46 | 26.1 |
| SM     | 16 | 28.3 | 0.824 | 35.3 |  8.3 | 21.40 | 16.9 |
| ML     |  3 | 31.6 | 0.918 | 35.8 |  9.1 | 18.69 | 13.9 |

> φ từ thí nghiệm cắt phẳng (cắt trực tiếp), c = lực dính (kPa).  
> Phi lưu theo định dạng DDMM (giá trị thô /100 ≈ centi-độ hoặc DDMM → DD°MM' = DD + MM/60 độ).

---

## Ghi chú Kỹ thuật

- Lớp đất yếu (MH-OH/CH-OH): Su ≈ 6–22 kPa, φ ≈ 3–5°, c ≈ 5–9 kPa — thuộc nhóm đất rất mềm, cần kiểm tra ổn định đáy hố đào (basal heave)
- Lớp trung gian (CH): φ ≈ 10°, c ≈ 25 kPa — nền cọc trung
- Lớp chặt (SC/SM): φ ≈ 15–21°, c ≈ 16–37 kPa — tầng đặt mũi cọc
- Ranh L2/L3 tại ~22m (cao độ –19.7m) quan sát qua VST1 (Su tăng đột biến 19.9→48.7 kPa)

---

## Query mẫu — TTHC.sqlite

```sql
-- Su theo chiều sâu tại BXN, toàn bộ VST
SELECT vl.name, vs.depth_m, vs.Su_kPa, vs.St
FROM vane_shear_tests vs
JOIN vst_locations vl ON vl.id = vs.vst_loc_id
WHERE vl.zone_id = 2
ORDER BY vl.name, vs.depth_m;

-- Chỉ tiêu đất yếu MH-OH/CH-OH tại BXN
SELECT b.name, l.sample_id, l.depth_from_m, l.w_pct, l.e0, l.phi_deg, l.c_kPa
FROM lab_tests l JOIN boreholes b ON b.id = l.borehole_id
WHERE b.zone_id = 2
  AND l.symbol_tcvn IN ('MH-OH','CH-OH')
ORDER BY b.name, l.depth_from_m;
```
