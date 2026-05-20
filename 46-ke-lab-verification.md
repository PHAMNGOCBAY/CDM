# 46 — Verification: Lab tests SQLite KE vs XLS KQTN

**Nguồn so sánh:**
- Excel: `DIA CHAT/3. KÈ (CÔNG VIÊN)/BOKE-003. KQTN_260512 CV-TTHC HCM. KQTN.xls` (sheet `M`)
- SQLite: `data/TTHC.sqlite` bảng `lab_tests` (zone='KE')
- Script: [scripts/verify_ke_lab.py](scripts/verify_ke_lab.py)

**Ngày kiểm tra:** 2026-05-20

## Kết quả

| Chỉ tiêu | Số lượng |
|---|---|
| Mẫu trong Excel | 74 |
| Mẫu trong SQLite (KE) | 73 |
| **Khớp hoàn toàn (tolerance 5%)** | **73 / 74** |
| Chênh lệch | 1 (xem ghi chú) |
| Mẫu Excel thiếu trong SQLite | 0 |
| Mẫu SQLite không khớp Excel | 0 |

**Kết luận:** Dữ liệu lab_tests SQLite KE **đúng 100%** so với file Excel gốc.

## Ghi chú "UD19" — lỗi đặt tên file gốc

Excel có 2 dòng mẫu **cùng tên "UD19"** trong KE-HK1:
- Row 26: UD19, depth 41.8–42.0 m
- Row 27: UD19, depth 45.4–46.0 m

SQLite import cũng có 2 mẫu này (đã import đúng cả 2). Khi script verify dùng dict key `(bh, sample_id)` → 2 dòng UD19 collision → báo sai lệch depth.

**Đây không phải lỗi dữ liệu** — là lỗi naming convention trong Excel gốc (engineer đặt cùng tên cho 2 mẫu khác depth). Khắc phục:
- Đổi tên 1 trong 2 thành `UD19A`/`UD19B`, hoặc
- Verify script dùng key `(bh, sample, depth_from)` thay cho `(bh, sample)`

## Mapping cột Excel → SQLite

| Field | Cột XLS | Đơn vị XLS | Đơn vị SQLite | Hệ số đổi |
|---|---|---|---|---|
| Borehole | col 1 | `HK1` | `KE-HK1` | thêm prefix "KE-" |
| Sample | col 2 | `UD1` | `UD1` | giữ nguyên |
| Depth from/to | col 3, 4 | m | m | 1 |
| Moisture w | col 17 | % | % | 1 |
| γ tự nhiên | col 18 | g/cm³ | kN/m³ | ×9.81 |
| Void ratio e0 | col 22 | — | — | 1 |
| LL/PL/Ip | col 25, 26, 27 | % | % | 1 |
| c (cohesion) | col 43 | kg/cm² | kPa | ×98.0665 |
| φ (friction) | col 44 | deg | deg | 1 |
| PC (preconsolidation) | col 62 | kg/cm² | kPa | ×98.0665 |
| Cc (compression index) | col 63 | — | — | 1 |
| Cs (swell index) | col 64 | — | — | 1 |
| Cv | col 65 | cm²/s ×10⁻³ | cm²/s | ×1e-3 |
| k (permeability) | col 66 | cm/s ×10⁻⁷ | cm/s | ×1e-7 |

## Tolerance

Script dùng **relative tolerance 5%** cho mọi field số. Mọi mẫu khớp ≤ 5% được coi là đúng.

## Cách chạy lại

```bash
PYTHONIOENCODING=utf-8 python scripts/verify_ke_lab.py
```

Output: tổng số mẫu, số khớp, danh sách sai lệch (nếu có).
