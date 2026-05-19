# Borehole Stratigraphy Import — NHC Zone

## Nguồn dữ liệu

| Trường | Giá trị |
|--------|---------|
| File DXF | `G:\My Drive\202605-TRUNG TAM HCM\DIA CHAT\2. NHÀ HÀNH CHÍNH\NHC-1. TRỤ_TTHC_Tru hien truong.dxf` |
| Script import | `scripts/import_dxf_boreholes.py` |
| SQLite target | `data/TTHC.sqlite` |
| Ngày import | 2026-05-19 |

---

## Cấu trúc bảng SQLite

### `strat_layers`

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| id | INTEGER PK | |
| borehole_id | INTEGER FK | → boreholes.id |
| layer_no | INTEGER | Thứ tự lớp (1, 2, 3…) |
| depth_top_m | REAL | Cao độ đỉnh lớp (m, từ mặt đất) |
| depth_bot_m | REAL | Cao độ đáy lớp (m) |
| description | TEXT | Mô tả địa chất (tiếng Việt, từ DXF MTEXT) |

Ràng buộc: `UNIQUE(borehole_id, depth_top_m)`

### `spt_tests`

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| id | INTEGER PK | |
| borehole_id | INTEGER FK | → boreholes.id |
| depth_from_m | REAL | Chiều sâu đỉnh đoạn thử (m) |
| depth_to_m | REAL | Chiều sâu đáy đoạn thử (m, = depth_from + 0.45) |
| N1 | INTEGER | Nhát búa 0–15 cm (định hướng) |
| N2 | INTEGER | Nhát búa 15–30 cm |
| N3 | INTEGER | Nhát búa 30–45 cm (NULL nếu kết thúc sớm) |
| N_value | INTEGER | N = N2 + N3 (khi đủ 3 đoạn); N = N2 (khi N3=NULL) |

Ràng buộc: `UNIQUE(borehole_id, depth_from_m)`

---

## Kết quả import

| Số liệu | Giá trị |
|---------|---------|
| Số hố khoan NHC có dữ liệu | 16 |
| Tổng lớp địa chất (`strat_layers`) | 144 |
| Tổng thí nghiệm SPT (`spt_tests`) | 722 |
| SPT thiếu N3 (N_value = N2) | 122 |

### Danh sách hố khoan

| Hố khoan | Số lớp | Số SPT |
|----------|:------:|:------:|
| NHC-BH-03 | 8 | 40 |
| NHC-BH-05 | 8 | 44 |
| NHC-BH-20 | 6 | 44 |
| NHC-BH-25 | 8 | 44 |
| NHC-BH-26 | 12 | 48 |
| NHC-BH-27 | 13 | 48 |
| NHC-BH-28 | 13 | 48 |
| NHC-BH-29 | 9 | 48 |
| NHC-BH-30 | 5 | 48 |
| NHC-BH-32 | 11 | 42 |
| NHC-BH-33 | 10 | 42 |
| NHC-BH-34 | 6 | 44 |
| NHC-BH-35 | 9 | 44 |
| NHC-BH-36 | 7 | 47 |
| NHC-BH-37 | 12 | 44 |
| NHC-BH-38 | 7 | 47 |

Hố khoan chưa có dữ liệu (không có trong DXF này): BH-01, BH-02, BH-09, BH-31, BH-39, BH-42, BH-44.

---

## Ví dụ: NHC-BH-03

```
L1:  0.00 – 25.10 m  Sét lẫn hữu cơ màu xám đen, trạng thái dẻo chảy
L2: 25.10 – 33.00 m  Sét kẹp cát xám xanh, trạng thái dẻo
L3: 33.00 – 38.80 m  Cát hạt vừa màu xám ghi, kết cấu xốp – chặt vừa
L4: 38.80 – 52.80 m  Sét màu nâu đỏ, nâu vàng, trạng thái cứng
L5: 52.80 – 68.50 m  Cát hạt mịn màu nâu đỏ xám xanh, kết cấu chặt
L6: 68.50 – 71.20 m  Sét pha màu nâu vàng, xám xanh, trạng thái cứng
L7: 71.20 – 98.50 m  Cát mịn – trung màu xám xanh, kết cấu chặt
L8: 98.50 – 100.00 m (đáy hố)
```

---

## Nguyên tắc Parsing DXF

### Cấu trúc file DXF (định dạng GBS)

- Mỗi hố khoan = 1 cột TEXT/MTEXT, chiều rộng ~250 DXF units
- Mỗi trang = 20 m chiều sâu = 200 DXF units (scale 10 DXF/m)
- 5 trang xếp dọc, cách nhau ~347 DXF units (page gap)
- Cột chiều sâu (depth tick): số nguyên 0–100, x ≈ x_col – 30 đến – 44 (biến đổi theo hố)

### Thuật toán xác định chiều sâu

1. **Tìm x_tick động**: Dò tìm TEXT = "0" ở y ngay dưới header (header_thresh − 120 đến header_thresh), x ∈ [x_col−70, x_col−5]
2. **Xây depth_map theo segment**: Khi Δdepth ≤ 0 (page break), tạo segment mới. Chỉ chấp nhận pair có scale = (Δy/Δdepth) ≈ 10 DXF/m (±3)
3. **Lọc bot_depth**: Float TEXT ở x ∈ [x_col−20, x_col+30]; giữ lại nếu `|val − depth_from_y(y)| < 2.0 m` — loại bỏ nhãn độ dày (thickness) vì chúng nằm giữa lớp
4. **Ghép description**: MTEXT ở x ∈ [x_col+30, x_col+250], khớp với lớp theo chiều sâu nội suy

### Lưu ý đặc biệt

- **BH-27 / BH-28**: Hai hố cách nhau 2 DXF units → cùng entity set → cùng dữ liệu địa tầng
- **Depth "20" xuất hiện 2 lần**: Cuối trang 1 (y≈71353) và đầu trang 2 (y≈71206) → segment logic xử lý tự động (Δdepth = 0 → new segment)
- **Layer# column**: Nằm ở x ≈ x_col − 16, x_tol = 8 để không lẫn với depth tick
- **Incomplete SPT**: N3 = NULL khi thử nghiệm kết thúc trước interval 3; `N_value = N2` (không phải NULL)

---

## Query mẫu

```sql
-- Địa tầng hố khoan
SELECT sl.layer_no, sl.depth_top_m, sl.depth_bot_m, sl.description
FROM strat_layers sl JOIN boreholes b ON b.id = sl.borehole_id
WHERE b.name = 'NHC-BH-03'
ORDER BY sl.depth_top_m;

-- SPT theo hố khoan
SELECT st.depth_from_m, st.N1, st.N2, st.N3, st.N_value
FROM spt_tests st JOIN boreholes b ON b.id = st.borehole_id
WHERE b.name = 'NHC-BH-03'
ORDER BY st.depth_from_m;

-- Tổng hợp theo khu vực
SELECT z.code, COUNT(DISTINCT b.id) n_bh,
       COUNT(sl.id) n_layers, COUNT(st.id) n_spt
FROM zones z
LEFT JOIN boreholes b ON b.zone_id = z.id
LEFT JOIN strat_layers sl ON sl.borehole_id = b.id
LEFT JOIN spt_tests st ON st.borehole_id = b.id
GROUP BY z.code;
```

---

## Tham chiếu

- Lý thuyết CDM (dùng Cu từ strat): [35-ly-thuyet-cdm.md](35-ly-thuyet-cdm.md)
- Dữ liệu địa chất NHC (nguồn): [data/TTHC.sqlite](data/TTHC.sqlite) — bảng `boreholes`, `layers`, `spt_tests`
- Tổng quan dự án TTHC: [34-geology-overview-202605-TTHC.md](34-geology-overview-202605-TTHC.md)
