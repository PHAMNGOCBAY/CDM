# 43 — Khoảng Cách Hố Khoan Kè KE → Tim Cọc CDM Gần Nhất

**Mục đích:** Kiểm tra độ đại diện của mỗi hố khoan đối với vùng CDM — hố khoan càng xa CDM theo phương vuông góc (d⊥) thì số liệu càng ít trực tiếp đặc trưng cho khu vực gia cố.

**File engine:** [scripts/ke_cdm_dist.py](scripts/ke_cdm_dist.py)  
**Dữ liệu đầu ra:** [data/ke_cdm_distances_202605_TTHC.json](data/ke_cdm_distances_202605_TTHC.json)  
**SQLite:** bảng `ke_cdm_distances` (21 cột)  
**Nguồn CDM:** SQLite `cdm_toado` WHERE zone='KE' — 8 201 tim cọc CDM  
**Nguồn BH:** SQLite `boreholes` WHERE name LIKE 'KE-%' — 12 hố khoan  

---

## 1. Phương pháp xác định khoảng cách

### 1.1 Trục tuyến kè (PCA)

Sử dụng phân tích thành phần chính (PCA) trên 8 hố khoan trên tuyến kè SW để xác định trục tuyến:

$$\mathbf{u} = \text{eigenvector thứ nhất của }\text{SVD}\!\left(\mathbf{X} - \bar{\mathbf{X}}\right)$$

Kết quả: $\mathbf{u} = (0{,}9934;\; 0{,}1151)$ theo hệ [Northing, Easting]  
Điểm gốc: $N = 1\,191\,794{,}1\text{ m}$; $E = 605\,861{,}6\text{ m}$

Pháp tuyến vuông góc: $\mathbf{n} = (-u_E;\; u_N)$ (xoay 90° CCW)

### 1.2 Phân tích khoảng cách

Cho hố khoan $P$ và cọc CDM $C$, vectơ $\mathbf{v} = C - P$:

$$d_\parallel = \mathbf{v} \cdot \mathbf{u} \qquad \text{(thành phần dọc trục tuyến kè)}$$

$$d_\perp = \mathbf{v} \cdot \mathbf{n} \qquad \text{(thành phần vuông góc trục tuyến kè)}$$

$$d_\text{Euclid} = \|\mathbf{v}\| = \sqrt{d_\parallel^2 + d_\perp^2}$$

**Cọc CDM gần nhất theo phương vuông góc** = cọc có $|d_\perp|$ nhỏ nhất (không phụ thuộc vị trí dọc tuyến).  
**Cọc CDM gần nhất theo Euclid** = cọc có $d_\text{Euclid}$ nhỏ nhất — dùng làm số liệu chính trong bảng thống kê.

**Lưu ý:** $d_\perp$ ở đây là thành phần vuông góc của vectơ $P \rightarrow C_\text{Euclid,gần nhất}$, không phải khoảng cách đến đường thẳng.

---

## 2. Bảng thống kê — Khoảng cách hố khoan → CDM gần nhất

| Hố khoan | Trên tuyến kè | Chainage (m) | Offset (m) | d Euclid (m) | **d⊥ (m)** | d∥ (m) | CDM gần nhất |
| -------- | :---: | ---: | ---: | ---: | ---: | ---: | --- |
| KE-HK4 | Không | +97,4 | +247,5 | 141,2 | **126,3** | −63,1 | KE-865 |
| KE-HK5 | Không | +225,0 | +225,8 | 136,7 | **112,6** | −77,5 | KE-4 |
| **KE-HK11** | **Có** | **−224,8** | **−85,1** | **75,5** | **75,3** | −3,8 | **KE-4520** |
| KE-HK12 | Không | +314,1 | +178,7 | 179,1 | **65,5** | −166,7 | KE-4 |
| **KE-HK10** | **Có** | **−79,2** | **−110,9** | **35,1** | **34,1** | −7,9 | **KE-5014** |
| **KE-HK3** | **Có** | **−38,9** | **+171,7** | **29,4** | **28,6** | −6,8 | **KE-6513** |
| KE-HK6 | Có | +192,3 | +121,6 | 45,3 | 11,8 | −43,7 | KE-7 |
| KE-HK8 | Có | +171,5 | −130,8 | 14,3 | 11,1 | −9,0 | KE-8199 |
| KE-HK9 | Có | +63,0 | −63,7 | 12,6 | 12,4 | +2,2 | KE-267 |
| KE-HK2 | Có | −176,8 | +100,9 | 10,1 | 9,2 | −4,2 | KE-7085 |
| KE-HK1 | Không | −295,3 | +50,0 | 20,1 | 0,7 | +20,1 | KE-8198 |
| KE-HK7 | Có | +93,0 | −3,8 | 7,0 | **1,9** | +6,7 | KE-2243 |

**Ghi chú cột:**
- **Chainage (m):** vị trí dọc trục tuyến kè (âm = phía HK2/HK11; dương = phía HK6/HK8)
- **Offset (m):** khoảng cách vuông góc từ HK đến trục kè (dương = phía landward/Front; âm = phía sông/Back)
- **d⊥ (m):** thành phần vuông góc của vectơ HK→CDM gần nhất Euclid, đo theo phương vuông góc trục tuyến kè
- **d∥ (m):** thành phần dọc trục tuyến kè

---

## 3. Nhận xét kỹ thuật

### 3.1 Hố khoan trên tuyến kè — khoảng cách d⊥

| Mức | d⊥ | Hố khoan | Đánh giá |
|---|---|---|---|
| Xa (>30m) | >30 m | **HK11 (75,3m)**, **HK10 (34,1m)**, **HK3 (28,6m)** | Số liệu không trực tiếp đặc trưng cho CDM |
| Trung bình (10–30m) | 10–30 m | HK6 (11,8m), HK8 (11,1m), HK9 (12,4m), HK2 (9,2m) | Có thể dùng với chú ý |
| Gần (<10m) | <10 m | **HK7 (1,9m)** | Đặc trưng tốt nhất cho CDM |

### 3.2 Giải thích tại sao HK11 xa CDM nhất

- **HK11** có offset = **−85,1 m** (phía sông/Back), trong khi CDM zone chủ yếu nằm về phía **+Northing** (phía Landward/Front)
- Vùng CDM KE không phủ đến phía Back của tuyến kè → HK11 nằm ngoài vùng CDM hoàn toàn
- d⊥ = 75,3m >> s_CDM = 1,8m → HK11 cách CDM zone gần 42 nhịp cọc CDM

### 3.3 HK10 cũng xa CDM (d⊥ = 34,1m)

- Offset = −110,9m (phía sông, xa hơn HK11)
- HK10 cũng là HK kiểm soát NT1 (margin −0,1m) — đây là vị trí kỹ thuật quan trọng nhất trên tuyến nhưng số liệu địa chất không đại diện tốt cho CDM zone

### 3.4 Đề xuất

- **HK7** (d⊥=1,9m) — đặc trưng tốt nhất cho CDM zone → ưu tiên dùng số liệu HK7 khi thiết kế CDM cho khu vực giữa tuyến kè
- **HK4, HK5** (ngoài tuyến, d⊥=126m, 113m) — quá xa CDM zone; số liệu chỉ dùng tham khảo vùng phía Front
- Cần xem xét bổ sung hố khoan tại khu vực gần CDM zone phía Back (HK11/HK10) nếu muốn có số liệu thiết kế CDM chính xác tại đó

---

## 4. Thông số trục PCA

| Thông số | Giá trị |
|----------|---------|
| axis_u [Northing, Easting] | (0,9934; 0,1151) |
| Góc với trục Northing | arctan(0,1151/0,9934) ≈ 6,6° |
| Điểm gốc — Northing | 1 191 794,1 m |
| Điểm gốc — Easting | 605 861,6 m |
| HK dùng tính PCA | HK2, HK3, HK6, HK7, HK8, HK9, HK10, HK11 (8 HK trên tuyến) |
| Số tim cọc CDM vùng KE | 8 201 điểm |

---

## 5. SQLite schema — bảng `ke_cdm_distances`

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `bh_name` | TEXT | Tên hố khoan (KE-HKx) |
| `on_alignment` | INTEGER | 1 = trên tuyến kè SW |
| `bh_northing_m` | REAL | Northing hố khoan (m) |
| `bh_easting_m` | REAL | Easting hố khoan (m) |
| `chainage_m` | REAL | Vị trí dọc trục tuyến kè (m) |
| `bh_offset_m` | REAL | Offset vuông góc trục tuyến kè (m, + = Front) |
| `nearest_cdm_perp_name` | TEXT | Tên CDM gần nhất theo d⊥ |
| `nearest_cdm_perp_north_m` | REAL | Northing CDM đó |
| `nearest_cdm_perp_east_m` | REAL | Easting CDM đó |
| `dist_perp_m` | REAL | d⊥ (có dấu) đến CDM gần nhất vuông góc |
| `dist_perp_abs_m` | REAL | |d⊥| đến CDM gần nhất vuông góc |
| `dist_along_at_perp_m` | REAL | d∥ tại CDM đó |
| `dist_eucl_at_perp_m` | REAL | d Euclid tại CDM đó |
| `nearest_cdm_eucl_name` | TEXT | Tên CDM gần nhất theo Euclid |
| `nearest_cdm_eucl_north_m` | REAL | Northing CDM đó |
| `nearest_cdm_eucl_east_m` | REAL | Easting CDM đó |
| `dist_eucl_m` | REAL | d Euclid đến CDM gần nhất |
| `dist_perp_at_eucl_m` | REAL | **d⊥ tại CDM Euclid gần nhất** (cột chính) |
| `dist_along_at_eucl_m` | REAL | d∥ tại CDM Euclid gần nhất |
| `updated_at` | TEXT | Thời điểm cập nhật |
