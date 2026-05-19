# 34 — Tổng quan Địa chất 3 Khu vực — Dự án TTHC 2026-05

**Dự án:** 260512 CVTT-TTHC — Trung tâm Hành chính TP.HCM  
**Cập nhật:** 2026-05-18  
**Cơ sở dữ liệu thống nhất:** `data/TTHC.sqlite`

---

## Sơ đồ Tổng thể

```
TTHC.sqlite
├── KE  — Kè Công Viên       12 HK  12 VST   74 lab  110 VS điểm  12 CDM
├── BXN — Bãi Đỗ Xe Ngầm    14 HK   5 VST  291 lab   50 VS điểm
└── NHC — Nhà Hành Chính    10 HK   4 VST  277 lab   48 VS điểm
```

---

## File Dữ liệu theo Khu vực

| Zone | Borehole logs | Lab tests JSON | VST JSON | Ghi chú |
|------|--------------|---------------|---------|---------|
| KE   | `data/soil_profile_202605_TTHC.json` | `data/lab_tests_202605_TTHC.json` | `data/vane_shear_202605_TTHC.json` | 12 HK, cao độ + địa tầng + layers |
| BXN  | `data/bxn_boreholes_202605_TTHC.json` | `data/bxn_lab_tests_202605_TTHC.json` | `data/bxn_vane_shear_202605_TTHC.json` | 17 HK, tọa độ + cao độ + SPT + layers |
| NHC  | — (bản vẽ DWG, chưa có PDF) | `data/nhc_lab_tests_202605_TTHC.json` | `data/nhc_vane_shear_202605_TTHC.json` | 10 HK, thiếu cao độ |
| CDM  | — | `data/cdm_tests_202605_TTHC.json` | — | KE-HK12, R7 |

### Tài liệu kỹ thuật chi tiết
- [15-soil-profile-202605-TTHC.md](15-soil-profile-202605-TTHC.md) — KE địa tầng, vane shear, lab, CDM
- [32-geology-bxn-202605-TTHC.md](32-geology-bxn-202605-TTHC.md) — BXN chi tiết
- [33-geology-nhc-202605-TTHC.md](33-geology-nhc-202605-TTHC.md) — NHC chi tiết

---

## Schema TTHC.sqlite

```
zones(id, code, name_vi, notes)
boreholes(id, zone_id, name, name_raw, elevation_m, depth_m, date, x_coord_m, y_coord_m)
layers(id, borehole_id, symbol, description, depth_top_m, depth_bot_m, thickness_m)
spt_values(id, borehole_id, depth_m, elev_m, N1, N2, N3, N)
vst_locations(id, zone_id, name, date, Z_ground_m, vane_D_cm, vane_H_cm, K_m3, x_coord_m, y_coord_m)
vane_shear_tests(id, vst_loc_id, depth_m, elev_m, Su_kPa, Sp_kPa, St, note)
lab_tests(id, borehole_id, sample_id, depth_from_m, depth_to_m,
          w_pct, gamma_kNm3, gamma_dry_kNm3, Gs, Sr_pct, n_pct, e0,
          wL_pct, wP_pct, Ip, IS_liq, phi_deg, c_kPa,
          a12_cm2kgf, E_kPa, Cc, Cs, Cu_UU_kPa, phi_UU_deg,
          symbol_tcvn, description_vi)
cdm_tests(id, borehole_id, group_id, test_id, cement_type, WC_ratio, dosage_kgm3, qu_R7_kPa, E50_R7_MPa)
```

> Nạp lại DB: `python scripts/project_db.py --reset`  
> Chỉ query: `python scripts/project_db.py --query`

---

## So sánh Su — Cắt cánh (chiều sâu ≤15m)

| Zone | n điểm | Su min | Su avg | Su max | (kPa) |
|------|--------|--------|--------|--------|-------|
| KE   | 76 |  2.4 | 11.1 | 26.8 |
| BXN  | 32 |  5.9 | 15.4 | 22.9 |
| NHC  | 25 |  4.7 | 16.0 | 31.8 |

> KE có Su thấp hơn do bao gồm các điểm nông (L1a/fill) và các HK tuyến kè.

---

## So sánh Chỉ tiêu Đất mềm (CH/MH/MH-OH)

| Zone | n | w (%) | e₀ | φ (°) | c (kPa) |
|------|---|------|----|-------|---------|
| KE   | 30 | 74.0 | 1.971 | 5.17 |  9.5 |
| BXN  | 97 | 77.0 | 2.073 | 5.15 | 10.3 |
| NHC  | 78 | 73.8 | 2.025 | 5.26 |  7.4 |

> BXN gộp CH + MH-OH + CH-OH; NHC gộp MH + MH-OH + CH. Các khu vực có đặc tính đất yếu tương đương nhau.

---

## Đặt tên Hố khoan trong SQLite

| Zone | Tên DB | Ví dụ |
|------|--------|-------|
| KE  | `KE-HK{n}` | `KE-HK1`, `KE-HK12` |
| BXN | `BXN-CV-HK{n}` | `BXN-CV-HK2`, `BXN-CV-HK17` |
| NHC | `NHC-BH-{nn}` | `NHC-BH-01`, `NHC-BH-44` |
| KE VST  | `KE-HK{n}` (trùng boreholes) | `KE-HK5` |
| BXN VST | `BXN-CV-VST{n}` | `BXN-CV-VST3` |
| NHC VST | `NHC-VST{n}` | `NHC-VST6` |

---

## Đơn vị Lưu trữ trong DB

| Cột | Đơn vị | Ghi chú |
|-----|--------|---------|
| `gamma_kNm3` | kN/m³ | Đã quy đổi từ g/cm³ × 9.81 |
| `c_kPa` | kPa | Đã quy đổi từ kgf/cm² × 98.07 (NHC, BXN lab) |
| `phi_deg` | ° (độ thập phân) | Phân tích DDMM → DD + MM/60 (BXN/NHC); nguyên độ (KE) |
| `a12_cm2kgf` | cm²/kgf | Chưa quy đổi (×0.0102 = m²/kN) |
| `E_kPa` | kPa | Đã quy đổi từ kgf/cm² × 98.07 (KE); nguyên kPa (BXN) |
| `Su_kPa`, `Sp_kPa` | kPa | Cắt cánh — trực tiếp từ PDF |

---

## Query Tổng hợp

```sql
-- So sánh Su 3 khu vực, depth ≤ 20m
SELECT z.code, vs.depth_m, AVG(vs.Su_kPa) avg_Su, COUNT(*) n
FROM vane_shear_tests vs
JOIN vst_locations vl ON vl.id = vs.vst_loc_id
JOIN zones z ON z.id = vl.zone_id
WHERE vs.depth_m <= 20
GROUP BY z.code, ROUND(vs.depth_m / 2) * 2
ORDER BY z.id, vs.depth_m;

-- Toàn bộ mẫu đất yếu + phi + c — 3 khu vực
SELECT z.code, b.name borehole, l.symbol_tcvn, l.depth_from_m,
       l.w_pct, l.e0, l.phi_deg, l.c_kPa
FROM lab_tests l
JOIN boreholes b ON b.id = l.borehole_id
JOIN zones z ON z.id = b.zone_id
WHERE l.symbol_tcvn IN ('CH','MH','MH-OH','CH-OH','ML-OL')
ORDER BY z.id, b.name, l.depth_from_m;
```
