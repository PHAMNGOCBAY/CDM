# 60 — Bề mặt cao độ tự nhiên & thiết kế — Quảng Trường Trung Tâm (QTT)

## Nguồn dữ liệu

| File DXF | Nội dung | Layer | Thực thể |
|---|---|---|---|
| `QTT-MTEXT CAO DO TU NHIEN-RANH XULYNEN CDM.dxf` | Cao độ tự nhiên | `C-TOPO-TEXT` | 162 MTEXT |
| `QTT-MTEXT CAO DO THIET KE-RANH XULYNEN CDM.dxf` | Cao độ thiết kế | `C-TOPO-TEXT` | 162 MTEXT |
| (như trên) | Ranh giới vùng xử lý nền CDM | `C-PROP-BNDY` | 1 LWPOLYLINE (15 đỉnh) |

**Hệ tọa độ:** VN-2000 / TM-3 106°E (EPSG:9210)  
**Script import:** `scripts/qtt_elevation_import.py`  
**JSON:** `data/qtt_elevation_202605_TTHC.json`  
**SQLite:** `qtt_elevation_points` + `qtt_cdm_boundary` trong `TTHC.sqlite`

---

## Thống kê lưới điểm

| Tham số | Giá trị |
|---|---|
| Số điểm | 162 |
| Bước lưới | 20 × 20 m |
| Phạm vi Easting | 605 188,93 – 605 488,93 m (rộng 300 m) |
| Phạm vi Northing | 1 191 613,04 – 1 191 853,04 m (rộng 240 m) |
| Diện tích bao | ~72 000 m² (~7,2 ha) |

---

## Thống kê cao độ

### Cao độ tự nhiên (m, Hệ Quốc gia)

| Tham số | Giá trị |
|---|:---:|
| Min | **0,79** |
| Max | **5,15** |
| Trung bình | **2,60** |

### Cao độ thiết kế (m, Hệ Quốc gia)

| Tham số | Giá trị |
|---|:---:|
| Min | **2,70** |
| Max | **4,02** |
| Trung bình | **2,97** |

### Chênh cao (fill = thiết kế − tự nhiên)

| Tham số | Giá trị |
|---|:---:|
| Min (cần đào) | **−1,91 m** |
| Max (cần đắp) | **+2,11 m** |
| Trung bình | **+0,37 m** (đắp nhẹ) |

> Giá trị âm = khu vực cần đào hạ cao độ xuống  
> Giá trị dương = khu vực cần đắp nâng cao độ lên

---

## Schema SQLite

### Bảng `qtt_elevation_points`

| Cột | Kiểu | Mô tả |
|---|---|---|
| `easting_m` | REAL PK | Tọa độ Easting VN-2000 |
| `northing_m` | REAL PK | Tọa độ Northing VN-2000 |
| `elev_nat_m` | REAL | Cao độ tự nhiên (m) |
| `elev_des_m` | REAL | Cao độ thiết kế (m) |
| `fill_m` | REAL | Chiều dày đắp/đào (thiết kế − tự nhiên, m) |

### Bảng `qtt_cdm_boundary`

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | INTEGER PK | |
| `easting_m` | REAL | |
| `northing_m` | REAL | |
| `vertex_order` | INTEGER | Thứ tự đỉnh polyline |

---

## Ứng dụng trong thiết kế CDM

Chiều dày đắp tại mỗi điểm lưới $H_{fill}$ được dùng làm tải ngoài $q$ khi tính lún:

$$q = \gamma_{fill} \times H_{fill} \quad [\text{kN/m}^2]$$

với $\gamma_{fill} = 18{,}0 \text{ kN/m}^3$ (đất đắp điển hình, tra bảng soil_presets).

Chiều dài cọc CDM tại HK bất kỳ:

$$L_{CDM} = (z_{top} - z_{TN}) + H_{soft} + h_{ngàm}$$

Khi $z_{top} = z_{thiết kế} < z_{TN}$: phần $(z_{top} - z_{TN}) < 0$ → cần đào trước khi thi công cọc.

---

## Vị trí code hiển thị 3D

Tab **TKCS CDM** (`tvtk_prep`), Section 2: "Bề mặt cao độ" — Plotly 3D surface (`go.Surface`) với 2 lớp:
- Xanh lam: cao độ tự nhiên
- Cam: cao độ thiết kế
- Colormap fill: RdBu (đỏ = đào, xanh = đắp)
