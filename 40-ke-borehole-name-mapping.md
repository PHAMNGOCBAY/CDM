# 40 — Mapping Tên Hố Khoan Kè Công Viên (KE) — 202605-TTHC

## Quy tắc bắt buộc

| Ngữ cảnh | Tên dùng | Ví dụ |
|----------|---------|-------|
| Query SQLite / code Python / file JSON / báo cáo / bảng biểu | **`db_name`** | `KE-HK1` |
| Tra cứu báo cáo địa chất PDF gốc | `pdf_name` | `3BOKECONGVIEN-HK1` |

> **KHÔNG dùng `short_name` (HK1) ở bất kỳ đâu** — dự án có nhiều khu vực (KE, BXN, NHC),  
> `HK1` không phân biệt được khu vực. Luôn dùng `KE-HK1`.  
> Lỗi điển hình: JSON `ke_sw` cũ dùng `HK8` với `Z_m=-1.300` (nhầm dữ liệu HK4 vào HK8).

---

## Bảng Mapping Đầy đủ

| db_name (SQLite) | short_name | pdf_name | Z mặt đất (m) | Northing (m) | Easting (m) | Tọa độ | Tuyến kè SW |
|-----------------|-----------|---------|:---:|:---:|:---:|:---:|:---:|
| `KE-HK1`  | HK1  | 3BOKECONGVIEN-HK1  | −0.800 | — | — | Thiếu | Ngoài tuyến |
| `KE-HK2`  | HK2  | 3BOKECONGVIEN-HK2  | +2.030 | 1 191 606.808 | 605 941.494 | Có | **Trên tuyến** |
| `KE-HK3`  | HK3  | 3BOKECONGVIEN-HK3  | +1.256 | 1 191 735.670 | 606 027.680 | Có | **Trên tuyến** |
| `KE-HK4`  | HK4  | 3BOKECONGVIEN-HK4  | −1.400 | — | — | Thiếu | Ngoài tuyến |
| `KE-HK5`  | HK5  | 3BOKECONGVIEN-HK5  | −0.680 | — | — | Thiếu | Ngoài tuyến |
| `KE-HK6`  | HK6  | 3BOKECONGVIEN-HK6  | −1.150 | — | — | Thiếu | Ngoài tuyến |
| `KE-HK7`  | HK7  | 3BOKECONGVIEN-HK7  | −0.561 | 1 191 886.862 | 605 868.540 | Có | **Trên tuyến** |
| `KE-HK8`  | HK8  | 3BOKECONGVIEN-HK8  | +2.579 | 1 191 979.459 | 605 751.412 | Có | **Trên tuyến** |
| `KE-HK9`  | HK9  | 3BOKECONGVIEN-HK9  | −2.250 | 1 191 863.956 | 605 805.575 | Có | **Trên tuyến** |
| `KE-HK10` | HK10 | 3BOKECONGVIEN-HK10 | −0.381 | 1 191 728.126 | 605 742.279 | Có | **Trên tuyến** |
| `KE-HK11` | HK11 | 3BOKECONGVIEN-HK11 | −0.220 | 1 191 580.576 | 605 751.153 | Có | **Trên tuyến** |
| `KE-HK12` | HK12 | 3BOKECONGVIEN-HK12 | −1.058 | — | — | Thiếu | Ngoài tuyến |

**Trên tuyến kè SW (7 HK):** KE-HK2, KE-HK3, KE-HK7, KE-HK8, KE-HK9, KE-HK10, KE-HK11 — theo bình đồ khảo sát.

**Ngoài tuyến (5 HK):** KE-HK1, KE-HK4, KE-HK5, KE-HK6, KE-HK12.

**Hố khoan thiếu tọa độ:** HK1, HK4, HK5, HK6, HK12 — cần trích xuất từ DXF địa hình.

---

## Ghi chú Đặc biệt theo Hố khoan

| db_name | Ghi chú |
|---------|---------|
| `KE-HK8` | Có lớp **XMD** (CDM gia cố Lớp 1, dày 15.7m). Khi tính NT2: `su_XMD = 10 kN/m²` (su gốc Lớp 1). KHÔNG đặt `qs_XMD = 0`. |
| `KE-HK10` | Hố kiểm soát NT1 — biên chỉ 0.3m với SW-840 → chọn **SW-940**. |
| `KE-HK12` | Lớp XMD từ độ sâu 11m. Cọc ván **SPECIAL** — thiết kế riêng, không đóng thông thường. |

---

## Lịch sử Lỗi Đã Sửa (2026-05-19)

| HK | Lỗi cũ trong ke_sw_202605_TTHC.json | Giá trị đúng từ SQLite |
|----|-------------------------------------|----------------------|
| HK2 | Z_m = −1.220 (sai) | Z_m = **+2.030** |
| HK3 | Z_m = −0.550 (sai) | Z_m = **+1.256** |
| HK7 | Z_m = −0.920 (sai) | Z_m = **−0.561** |
| HK8 | Z_m = **−1.300** (nhầm sang HK4!) | Z_m = **+2.579** |
| HK2 | H_layer1_m = 24.0m (sai) | H_layer1_m = **20.0m** |
| HK3 | H_layer1_m = 23.5m (sai) | H_layer1_m = **19.2m** |
| HK7 | H_layer1_m = 23.0m (sai) | H_layer1_m = **21.0m** |
| HK8 | H_layer1_m = 19.5m (sai) | H_layer1_m = **24.1m** (eff. bao gồm XMD) |
| HK8 | qs_XMD = 0 (sai — tính NT2 thấp giả tạo) | su_XMD = **10 kN/m²** (Lớp 1 gốc được gia cố) |

---

## Nguồn dữ liệu tham chiếu

| Nguồn | File | Dùng cho |
|-------|------|---------|
| SQLite `boreholes` | `data/TTHC.sqlite` | Z_m, tọa độ, id — **nguồn chuẩn** |
| SQLite `layers` | `data/TTHC.sqlite` | Chiều dày từng lớp — **nguồn chuẩn** |
| SQLite `sw_design` | `data/TTHC.sqlite` | NT1/NT2, cọc kiến nghị |
| SQLite `borehole_name_mapping` | `data/TTHC.sqlite` | Mapping 3 tên |
| JSON mapping | `data/ke_borehole_mapping.json` | Tra cứu nhanh không cần SQLite |
| JSON thiết kế | `data/ke_sw_202605_TTHC.json` | Tính toán chi tiết NT1/NT2 |
| Python lookup | `scripts/ke_borehole_mapping.py` | `db_name('HK1')` → `'KE-HK1'` |
| Địa tầng chi tiết | `15-soil-profile-202605-TTHC.md` (mục 15.3) | Mô tả lớp đất — tin cậy hơn mục 15.2 |
| Thiết kế cọc SW | `16-ke-sw-202605-TTHC.md` | Công thức, bảng cọc (kiểm tra lại H_lớp1 vs SQLite) |
