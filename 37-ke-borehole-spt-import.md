# Borehole SPT Import — KE Zone (Công viên)

## Nguồn dữ liệu

| Trường | Giá trị |
|--------|---------|
| File DXF | `DIA CHAT\3. KÈ (CÔNG VIÊN)\BOKE-1. TRỤ_260512 CVTT-TTHC. Tru DC.dxf` |
| Script import | `scripts/import_dxf_boreholes.py` |
| SQLite target | `data/TTHC.sqlite` |
| Ngày import | 2026-05-19 |

---

## Kết quả import

| Số liệu | Giá trị |
|---------|---------|
| Số hố khoan KE | 12 |
| Tổng lớp địa chất (`strat_layers`) | 151 |
| Tổng thí nghiệm SPT (`spt_tests`) | 193 |

### Danh sách hố khoan

| Hố khoan | Số lớp | Số SPT | N_min | N_max |
|----------|:------:|:------:|------:|------:|
| KE-HK1  | 7  | 22 | 2  | 83 |
| KE-HK2  | 10 | 12 | 7  | 46 |
| KE-HK3  | 12 | 20 | 2  | 49 |
| KE-HK4  | 7  | 10 | 8  | 54 |
| KE-HK5  | 24 | 38 | 2  | 71 |
| KE-HK6  | 11 | 8  | 2  | 42 |
| KE-HK7  | 9  | 16 | 1  | 65 |
| KE-HK8  | 13 | 11 | 2  | 87 |
| KE-HK9  | 24 | 25 | 2  | 93 |
| KE-HK10 | 13 | 10 | 5  | 76 |
| KE-HK11 | 11 | 11 | 6  | 92 |
| KE-HK12 | 10 | 9  | 3  | 32 |

---

## Cấu trúc DXF (định dạng GBS — khác NHC)

| Tham số | Giá trị |
|---------|---------|
| Tên hố khoan trong DXF | `HK1`..`HK12` (không có tiền tố `BH-`) |
| Tên trong DB | `KE-HK1`..`KE-HK12` |
| Scale | 10 DXF/m (y0 ≈ −5.25 per borehole) |
| Khoảng cách cột | 230 DXF units |
| Vị trí SPT interval | x_col + 117 (text "d.dd-d.dd") |
| Vị trí blow counts | x_col + 79..94 (4 cột × 5 units) |
| Vị trí layer depths | x_col − 18 (cột trái, giá trị = độ sâu thực) |
| Vị trí MTEXT mô tả | x_col + 18..68 |

### Quy tắc đọc SPT (4 blow counts)

Mỗi thí nghiệm SPT có **4 cột nhát búa** (tiêu chuẩn TCVN):

| Vị trí | Ký hiệu | Ý nghĩa |
|--------|---------|---------|
| Cột 1 (trái nhất) | N_prep | Đoạn cắm đầu (bỏ qua) |
| Cột 2 | N1 | Đoạn 15–30 cm |
| Cột 3 | N2 | Đoạn 30–45 cm |
| Cột 4 | N3 | Đoạn 45–60 cm |

**N_value = N2 + N3** (theo yêu cầu người dùng và TCVN)

### Thuật toán match mô tả địa tầng

Vì KE DXF không có cột depth tick chuẩn, script dùng SPT calibration:
1. Dùng vị trí y của SPT intervals (cùng trang) để build `depth_map_spt`
2. Chỉ chấp nhận pairs liên tiếp có scale ≈ 10 DXF/m (loại page breaks)
3. Dùng `_interp_depth` để tính depth từ y của MTEXT
4. Match vào lớp có `depth_top − 1 ≤ depth_mtext < depth_bot + 1`

---

## Quy tắc N_value

```
N_value = N2 + N3        (khi đủ 4 nhát búa)
N_value = N2             (khi N3 = NULL, thử nghiệm kết thúc sớm)
```

---

## Query mẫu

```sql
-- SPT theo hố khoan
SELECT st.depth_from_m, st.depth_to_m, st.N1, st.N2, st.N3, st.N_value
FROM spt_tests st JOIN boreholes b ON st.borehole_id=b.id
WHERE b.name = 'KE-HK1' ORDER BY st.depth_from_m;

-- Địa tầng KE với mô tả
SELECT sl.layer_no, sl.depth_top_m, sl.depth_bot_m, sl.description
FROM strat_layers sl JOIN boreholes b ON sl.borehole_id=b.id
WHERE b.name = 'KE-HK1' ORDER BY sl.depth_top_m;

-- Tổng hợp SPT toàn zone KE
SELECT b.name, COUNT(*) n_spt, MIN(st.N_value) N_min, MAX(st.N_value) N_max,
       ROUND(AVG(st.N_value),1) N_avg
FROM spt_tests st JOIN boreholes b ON st.borehole_id=b.id
JOIN zones z ON b.zone_id=z.id WHERE z.code='KE'
GROUP BY b.name ORDER BY b.name;
```

---

## Tham chiếu

- Import script: [scripts/import_dxf_boreholes.py](scripts/import_dxf_boreholes.py)
- NHC import (tương tự): [36-borehole-strat-import.md](36-borehole-strat-import.md)
- Dữ liệu địa chất KE (nguồn): [data/TTHC.sqlite](data/TTHC.sqlite) — bảng `boreholes`, `layers`, `spt_tests`
