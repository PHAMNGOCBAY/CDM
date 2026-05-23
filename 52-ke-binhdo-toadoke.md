# 52 — Bình đồ kè: Tọa độ đường ranh / tim kè (ke_binhdo_toadoke)

## Nguồn dữ liệu

| Mục | Giá trị |
|-----|---------|
| File DXF gốc | `pnbay-tọa dobinhdoke.dxf` |
| Thư mục | `G:\My Drive\202605-TRUNG TAM HCM\KET CAU KE\` |
| Layer DXF | `SEAPE_C-ROAD-CNTR-N` |
| Hệ tọa độ | VN-2000 (X ≈ Easting, Y ≈ Northing) |
| Script import | `scripts/ke_binhdo_import.py` |
| JSON snapshot | `data/ke_binhdo_toadoke_202605_TTHC.json` |
| Bảng SQLite | `ke_binhdo_toadoke` trong `data/TTHC.sqlite` |

## Thống kê

| Chỉ tiêu | Giá trị |
|----------|---------|
| Số polyline (LWPOLYLINE) | 184 |
| Tổng số điểm (đỉnh) | 400 |
| Kiểu polyline | Hở (closed = 0) |
| X_min (Easting) | 605 674.78 m |
| X_max (Easting) | 606 127.42 m |
| Y_min (Northing) | 1 191 461.17 m |
| Y_max (Northing) | 1 192 074.31 m |
| Phạm vi X | ~453 m |
| Phạm vi Y | ~613 m |

## Schema bảng SQLite `ke_binhdo_toadoke`

```sql
CREATE TABLE IF NOT EXISTS ke_binhdo_toadoke (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stt         INTEGER NOT NULL,       -- số thứ tự điểm toàn tập (1-based)
    polyline_id INTEGER NOT NULL,       -- id polyline trong file DXF (1-based)
    vertex_idx  INTEGER NOT NULL,       -- chỉ số đỉnh trong polyline (0-based)
    x_m         REAL    NOT NULL,       -- tọa độ X VN-2000 (m), ~Easting
    y_m         REAL    NOT NULL,       -- tọa độ Y VN-2000 (m), ~Northing
    layer       TEXT,                   -- tên layer DXF
    closed      INTEGER DEFAULT 0,      -- 1 = polyline kín, 0 = hở
    source      TEXT    DEFAULT 'DXF_pnbay'
)
```

## Truy vấn mẫu

### Lấy tất cả điểm theo thứ tự

```sql
SELECT stt, polyline_id, vertex_idx, x_m, y_m
FROM ke_binhdo_toadoke
ORDER BY polyline_id, vertex_idx;
```

### Lấy một polyline cụ thể

```sql
SELECT vertex_idx, x_m, y_m
FROM ke_binhdo_toadoke
WHERE polyline_id = 1
ORDER BY vertex_idx;
```

### Thống kê per polyline

```sql
SELECT polyline_id, layer, closed,
       COUNT(*) AS n_pts,
       MIN(x_m) AS x_min, MAX(x_m) AS x_max,
       MIN(y_m) AS y_min, MAX(y_m) AS y_max
FROM ke_binhdo_toadoke
GROUP BY polyline_id
ORDER BY polyline_id;
```

### Phạm vi toàn bộ bình đồ

```sql
SELECT layer, COUNT(DISTINCT polyline_id) AS n_poly,
       MIN(x_m) AS x_min, MAX(x_m) AS x_max,
       MIN(y_m) AS y_min, MAX(y_m) AS y_max
FROM ke_binhdo_toadoke
GROUP BY layer;
```

## Cấu trúc JSON snapshot

```json
{
  "_meta": {
    "source": "pnbay-tọa dobinhdoke.dxf",
    "updated": "YYYY-MM-DD",
    "n_points": 400,
    "n_polylines": 184
  },
  "points": [
    { "stt": 1, "polyline_id": 1, "vertex_idx": 0,
      "x_m": 605776.123456, "y_m": 1191927.654321,
      "layer": "SEAPE_C-ROAD-CNTR-N", "closed": 0 },
    ...
  ]
}
```

## Quy trình cập nhật

Khi có file DXF mới:

1. Đặt file vào `G:\My Drive\202605-TRUNG TAM HCM\KET CAU KE\`
2. Cập nhật biến `DXF` trong `scripts/ke_binhdo_import.py`
3. Chạy: `python -X utf8 scripts/ke_binhdo_import.py`
4. Kiểm tra: query `SELECT COUNT(*) FROM ke_binhdo_toadoke`

Script idempotent — `DELETE WHERE source='DXF_pnbay'` trước khi INSERT lại.

## Liên kết module

- Hố khoan tuyến kè: `boreholes` (prefix `KE-HKx`) — xem `40-ke-borehole-name-mapping.md`
- Kết quả NT1/NT2: `ke_sw_nt_detail` — xem `42-ke-sw-nt1-nt2-chi-tiet.md`
- Trắc dọc + bình đồ trong app: `scripts/app_cdm.py` trang `ke_sw` Mục B
