# 58 — Hố Khoan Quảng Trường Trung Tâm TTHC (QTTTTP)

**Nguồn:** `QTTTTP HCM.Tru- INPUT SQLITE-20260526.dxf`  
**Script import:** [scripts/qtt_borehole_import.py](scripts/qtt_borehole_import.py)  
**JSON output:** [data/qtt_boreholes_202605_TTHC.json](data/qtt_boreholes_202605_TTHC.json)  
**SQLite:** bảng `boreholes` / `layers` / `spt_values` / `qtt_samples` — zone `QTT` (id=4)  
**Ngày khảo sát:** 08–21/05/2026

---

## 1. Vị trí hố khoan (VN-2000, Zone QTT)

| Hố khoan | DB name | Northing (m) | Easting (m) | Cao độ (m) | Tổng sâu (m) | Ngày |
|---|---|---:|---:|:---:|:---:|---|
| ND-02 | QTTTTP-ND-02 | 1 191 680,407 | 605 239,025 | +1,700 | 31,00 | 11–12/05 |
| ND-03 | QTTTTP-ND-03 | 1 191 670,883 | 605 340,450 | +1,891 | 36,00 | 13–14/05 |
| ND-04 | QTTTTP-ND-04 | 1 191 661,331 | 605 441,004 | +1,095 | 33,00 | 20–21/05 |
| ND-05 | QTTTTP-ND-05 | 1 191 736,974 | 605 446,000 | +3,197 | 36,00 | 13–14/05 |
| ND-06 | QTTTTP-ND-06 | 1 191 761,037 | 605 349,440 | +4,237 | 36,00 | 11–12/05 |
| ND-07 | QTTTTP-ND-07 | 1 191 785,152 | 605 252,890 | +3,467 | 36,00 | 08–10/05 |

**Quy ước SQLite:** `x_coord_m = Northing`, `y_coord_m = Easting` (nhất quán với KE/BXN/NHC).

---

## 2. Địa tầng tổng hợp

### 2.1 ND-02 (cao độ +1,700 m, sâu 31,00 m)

| Lớp | USCS | Mô tả | Độ sâu (m) | Chiều dày (m) | Cao độ đáy (m) |
|---|---|---|---|:---:|:---:|
| F | F | San lấp, đất đắp | 0,00 – 2,80 | 2,80 | −1,10 |
| 1 | CH | Bùn sét, rất dẻo, trạng thái chảy đến dẻo mềm, màu xám xanh | 2,80 – 25,00 | 22,20 | −23,30 |
| 2 | CL-CH | Sét ít dẻo đến rất dẻo, dẻo cứng đến nửa cứng | 25,00 – 27,20 | 2,20 | −25,50 |
| 3 | ML | Cát bụi, kết cấu chặt vừa | 27,20 – 31,00 | 3,80 | −29,30 |

### 2.2 ND-03 (cao độ +1,891 m, sâu 36,00 m)

| Lớp | USCS | Độ sâu (m) | Chiều dày (m) | Cao độ đáy (m) |
|---|---|---|:---:|:---:|
| F | F | 0,00 – 3,00 | 3,00 | −1,11 |
| 1 | CH | 3,00 – 22,80 | 19,80 | −20,91 |
| 2 | CL-CH | 22,80 – 31,00 | 8,20 | −29,11 |
| 4 | SM | 31,00 – 36,00 | 5,00 | −34,11 |

### 2.3 ND-04 (cao độ +1,095 m, sâu 33,00 m) — không có lớp san lấp riêng

| Lớp | USCS | Độ sâu (m) | Chiều dày (m) | Cao độ đáy (m) |
|---|---|---|:---:|:---:|
| 1 | CH | 0,00 – 29,50 | 29,50 | −28,41 |
| 3 | ML | 29,50 – 32,60 | 3,10 | −31,50 |
| 4 | SM | 32,60 – 33,00 | 0,40 | −31,91 |

### 2.4 ND-05 (cao độ +3,197 m, sâu 36,00 m)

| Lớp | USCS | Độ sâu (m) | Chiều dày (m) | Cao độ đáy (m) |
|---|---|---|:---:|:---:|
| F | F | 0,00 – 2,90 | 2,90 | +0,30 |
| 1 | CH | 2,90 – 31,00 | 28,10 | −27,80 |
| 2 | CL-CH | 31,00 – 33,00 | 2,00 | −29,80 |
| 4 | SM | 33,00 – 34,80 | 1,80 | −31,60 |
| 4 | SM | 34,80 – 36,00 | 1,20 | −32,80 |

### 2.5 ND-06 (cao độ +4,237 m, sâu 36,00 m)

| Lớp | USCS | Độ sâu (m) | Chiều dày (m) | Cao độ đáy (m) |
|---|---|---|:---:|:---:|
| F | F | 0,00 – 2,60 | 2,60 | +1,64 |
| 1 | CH | 2,60 – 31,50 | 28,90 | −27,26 |
| 4 | SM | 31,50 – 36,00 | 4,50 | −31,76 |

### 2.6 ND-07 (cao độ +3,467 m, sâu 36,00 m)

| Lớp | USCS | Độ sâu (m) | Chiều dày (m) | Cao độ đáy (m) |
|---|---|---|:---:|:---:|
| F | F | 0,00 – 3,00 | 3,00 | +0,47 |
| 1a | CH | 3,00 – 18,80 | 15,80 | −15,33 |
| 1b | CH | 18,80 – 23,00 | 4,20 | −19,53 |
| 2 | CL-CH | 23,00 – 33,20 | 10,20 | −29,73 |
| 4 | SM | 33,20 – 36,00 | 2,80 | −32,53 |

---

## 3. Tổng hợp chiều dày lớp đất yếu

| Hố khoan | H_fill (m) | H_soft lớp 1/CH (m) | Đáy lớp yếu (m) | Cao độ đáy (m) |
|---|:---:|:---:|:---:|:---:|
| ND-02 | 2,80 | 22,20 | 25,00 | −23,30 |
| ND-03 | 3,00 | 19,80 | 22,80 | −20,91 |
| ND-04 | — | 29,50 | 29,50 | −28,41 |
| ND-05 | 2,90 | 28,10 | 31,00 | −27,80 |
| ND-06 | 2,60 | 28,90 | 31,50 | −27,26 |
| ND-07 | 3,00 | 20,00 | 23,00 | −19,53 |

**H_soft trung bình:** ≈ 24,7 m (lớp 1 CH)  
**Cao độ đáy lớp yếu:** từ −19,53 m (ND-07) đến −28,41 m (ND-04)

---

## 4. SPT — Tóm tắt kết quả

| Hố khoan | Số readings | N > 0 | N_max | Độ sâu N_max (m) |
|---|:---:|:---:|:---:|:---:|
| ND-02 | 16 | 4 | 32 | ~28–31 m |
| ND-03 | 17 | 7 | 49 | ~34–36 m |
| ND-04 | 16 | 16 | 21 | ~4–12 m |
| ND-05 | 17 | 17 | 46 | ~34–36 m |
| ND-06 | 17 | 17 | 25 | ~32–36 m |
| ND-07 | 17 | 8 | 25 | ~28–36 m |

**Nhận xét:** ND-04 có N > 0 từ độ sâu nông (~4 m) — đất lớp 1 có thể đặc hơn các BH khác.  
ND-02/03 có N = 0 đến tận độ sâu 24–26 m (lớp bùn rất mềm).

**Quy ước lưu SPT:** N1 = seating (15 cm đầu), N2 = đoạn 2 (15 cm), N3 = đoạn 3 (15 cm),  
**N = N2 + N3** (quy ước Việt Nam, giống KE/BXN).

---

## 5. Mẫu thí nghiệm

| Loại mẫu | Ký hiệu | Số lượng / BH | Ghi chú |
|---|---|:---:|---|
| Mẫu nguyên dạng (U-tube) | U1–U12 | ~12/BH | Độ sâu 1,80–26,00 m |
| Mẫu phá huỷ (Disturbed) | D1–D4 | ~4/BH | Độ sâu 27,40–31,00 m |

---

## 6. SQLite Schema

### `boreholes` (zone_id=4, zone='QTTTTP')

```sql
SELECT name, x_coord_m AS northing, y_coord_m AS easting,
       elevation_m, total_depth_m, date_start, date_end
FROM boreholes
WHERE zone = 'QTTTTP'
ORDER BY name
```

### `layers`

```sql
SELECT b.name, l.symbol, l.uscs, l.description,
       l.depth_top_m, l.depth_bot_m, l.thickness_m,
       l.mrl_top_m, l.mrl_bot_m
FROM layers l
JOIN boreholes b ON l.borehole_id = b.id
WHERE b.zone = 'QTTTTP'
ORDER BY b.name, l.layer_order
```

### `spt_values` (N = N2+N3 quy ước Việt Nam)

```sql
SELECT b.name, s.depth_m, s.elev_m, s.N1, s.N2, s.N3, s.N
FROM spt_values s
JOIN boreholes b ON s.borehole_id = b.id
WHERE b.zone = 'QTTTTP'
ORDER BY b.name, s.depth_m
```

### `qtt_samples`

```sql
SELECT b.name, qs.sample_code, qs.sample_type,
       qs.depth_from_m, qs.depth_to_m
FROM qtt_samples qs
JOIN boreholes b ON qs.borehole_id = b.id
ORDER BY b.name, qs.depth_from_m
```

---

## 7. Nhận xét kỹ thuật

1. **Lớp san lấp (F):** dày 2,60–3,00 m ở 5/6 BH; ND-04 không có lớp F riêng (cao độ thấp +1,095 m).
2. **Lớp bùn sét CH (lớp 1):** rất dày, từ 19,80 m (ND-03) đến 29,50 m (ND-04). Đây là lớp đất yếu chính cần xử lý khi thi công.
3. **Lớp cát SM (lớp 4):** xuất hiện ở đáy hầu hết BH, N_max đến 46–49 — lớp cứng có thể làm đất tựa.
4. **ND-07 có 2 sub-lớp CH** (3–18,8 m và 18,8–23,0 m): có thể phân biệt bằng trạng thái chảy vs dẻo mềm.
5. **Thiếu BH phía tâm quảng trường** (ND-01, ND-08 trở đi chưa có trong DXF này) — cần bổ sung nếu gia cố CDM.

---

## 8. Hàm load

```python
import sqlite3
from pathlib import Path

def load_qtt_boreholes(db_path="data/TTHC.sqlite"):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT b.*, z.code AS zone_code
        FROM boreholes b
        JOIN zones z ON b.zone_id = z.id
        WHERE z.code = 'QTT'
        ORDER BY b.name
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]

# Hoặc đọc JSON snapshot:
import json
data = json.loads(open("data/qtt_boreholes_202605_TTHC.json", encoding="utf-8").read())
boreholes = data["boreholes"]  # list 6 BH, mỗi BH có layers + spt + samples
```
