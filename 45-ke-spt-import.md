# 45 — Import SPT 12 Hố khoan Kè KE từ DXF

**Nguồn:** `DIA CHAT\3. KÈ (CÔNG VIÊN)\KE-1. TRỤ_260512 CVTT-TTHC. Tru DC.dxf`
**Ngày import:** 2026-05-20
**Tổng:** 12 hố khoan, 248 SPT readings

## Quy tắc N (theo user)

Mỗi SPT row có 4 cột giá trị (theo cấu trúc DXF):

| Cột DXF | Vị trí | Ý nghĩa | Sử dụng |
|---|---|---|---|
| col1 (x_base+79) | N_prep | Búa đặt (seating) | **Bỏ qua** |
| col2 (x_base+84) | N1 | 1st 15cm penetration | **Tính N** |
| col3 (x_base+89) | N2 | 2nd 15cm penetration | **Tính N** |
| col4 (x_base+94) | N3 | 3rd 15cm penetration | Lưu (N_astm) |

**Công thức N:** `N = N1 + N2 = col2 + col3` (theo user 2026-05-20)

Tham khảo: chuẩn ASTM D1586 dùng `N_astm = N2 + N3 = col3 + col4` (bỏ 1 cột seating + 1 cột đầu).
Cả 2 giá trị đều được lưu trong JSON; SQLite `spt_values.N` lưu N theo user.

## Tổng quan từng hố khoan

| Hố khoan | Số readings | Depth từ | Depth đến | N min | N max | N TB |
|---|---|---|---|---|---|---|
| KE-HK1 | 25 | 2.45 | 50.45 | 1 | 53 | 18.1 |
| KE-HK2 | 23 | 2.45 | 46.45 | 0 | 30 | 9.3 |
| KE-HK3 | 23 | 2.45 | 46.45 | 1 | 31 | 10.6 |
| KE-HK4 | 20 | 2.45 | 40.45 | 0 | 34 | 9.2 |
| KE-HK5 | 40 | 2.45 | 80.45 | 1 | 45 | 18.2 |
| KE-HK6 | 20 | 2.45 | 40.45 | 0 | 35 | 10.6 |
| KE-HK7 | 20 | 2.65 | 40.45 | 0 | 40 | 8.9 |
| KE-HK8 | 12 | 2.45 | 40.45 | 1 | 55 | 19.4 |
| KE-HK9 | 35 | 2.65 | 70.45 | 0 | 57 | 21.2 |
| KE-HK10 | 11 | 26.45 | 46.45 | 3 | 47 | 18.3 |
| KE-HK11 | 12 | 24.45 | 46.45 | 4 | 58 | 20.3 |
| KE-HK12 | 7 | 24.45 | 36.45 | 2 | 20 | 7.3 |

## Mẫu dữ liệu (KE-HK1, 5 dòng đầu)

| Depth (m) | N_prep | N1 | N2 | N3 | **N (user)** | N_astm |
|---|---|---|---|---|---|---|
| 2.45 | 0 | 0 | 1 | 1 | **1** | 2 |
| 4.45 | 0 | 0 | 1 | 1 | **1** | 2 |
| 6.45 | 0 | 0 | 1 | 1 | **1** | 2 |
| 8.45 | 0 | 0 | 1 | 1 | **1** | 2 |
| 10.45 | 0 | 0 | 1 | 1 | **1** | 2 |

## Tích hợp với engine NT2

SPT data import vào `spt_values` được hàm `_get_N160_for_layer()` trong [scripts/ke_sw_nt_calc.py](scripts/ke_sw_nt_calc.py) đọc tự động.
Sau khi import, các HK trên tuyến kè SW (HK2/3/7/8/9/10/11) sẽ có:
- `Rs` lớp cát tính theo SPT-Meyerhof (Pt.69 TCVN 11823-10)
- `Rp` khi mũi cọc trong cát tính theo Pt.68
- Warning '... không có SPT → bỏ qua ma sát' biến mất

Re-run: `python scripts/ke_sw_nt_calc.py` để cập nhật `ke_sw_nt_detail`.