# Thủy văn trạm Phú An — Sông Sài Gòn 1977–2024

Tài liệu phân tích chuỗi mực nước trung bình ngày (MNTB) trạm thủy văn **Phú An** trên **sông Sài Gòn** trong 48 năm (1977–2024), phục vụ thiết kế kè / công trình ven sông tại Trung Tâm Hành Chính TP.HCM (Quận 1, Thủ Thiêm).

---

## 1. Nguồn dữ liệu

| File gốc | Sheet | Nội dung |
|---|---|---|
| `THUYVAN-PhuAn_ H(77-24)ok.xlsx` | `Hn` | MNTB ngày × tháng × 48 năm (17,530 records) + đặc trưng năm |
| `THUYVAN-Tidal information summary_PhuAnStation.xlsx` | `Sheet1` | Đỉnh triều tối đa lịch sử 13 năm tiêu biểu (1977–2019) |

**Mốc cao độ:** Quốc gia (chuẩn Hòn Dấu / VN-2000).
**Đơn vị:** centimet (cm).
**Trạm:** Phú An — quan trắc liên tục, đại diện cho khu vực TP.HCM trên hệ sông Sài Gòn–Đồng Nai.

---

## 2. Triển khai 4 layer

| Layer | File | Nội dung |
|---|---|---|
| Tài liệu | `50-thuyvan-phuan-1977-2024.md` (file này) | Phân tích + thống kê + bảng tra cứu |
| JSON | `data/thuyvan_phuan_daily_77-24.json` | 17,530 records `(year, month, day, iso_date, h_cm)` |
| JSON | `data/thuyvan_phuan_summary.json` | 48 annual + 13 tidal peaks |
| JSON | `data/thuyvan_phuan_stats.json` | Tổng hợp thống kê (overall, trend, decade_mean) |
| Python | `scripts/thuyvan_phuan_import.py` | Parser XLSX + insert SQLite + dump JSON |
| Python | `scripts/thuyvan_phuan_plots.py` | 6 biểu đồ matplotlib + stats summary |
| SQLite | `thuyvan_daily` | 17,530 rows, UNIQUE `(year, month, day)` |
| SQLite | `thuyvan_annual_summary` | 48 rows + monthly_avg/max/min JSON arrays |
| SQLite | `thuyvan_tidal_peaks` | 13 rows |
| Hình | `data/thuyvan_phuan_analysis.png` | 5 subplot tổng hợp |
| Hình | `data/thuyvan_phuan_decades.png` | So sánh phân bố theo thập kỷ |

---

## 3. Kết quả thống kê chính

### 3.1 Tổng quan MNTB ngày (1977–2024)

| Chỉ số | Giá trị |
|---|:---:|
| Số records | **17,530** ngày |
| Số năm | **48** năm (1977–2024) |
| Min | **−55 cm** (1992-06-26) |
| Max | **+80 cm** (1978-10-17 và 1979-10-07) |
| Trung bình | **+12,11 cm** |
| Phân vị P5 / P50 / P95 / P99 | **−25 / +13 / +48 / +59 cm** |

### 3.2 Đỉnh triều tối đa lịch sử (file summary)

| Năm | Đỉnh triều (cm) | Năm | Đỉnh triều (cm) |
|:---:|:---:|:---:|:---:|
| 1977 | 137 | 2009 | 156 |
| 1978 | 137 | 2011 | 159 |
| 1999 | 144 | 2012 | 162 |
| 2002 | 146 | 2013 | 168 |
| 2006 | 147 | 2017 | 171 |
| 2007 | 149 | **2019** | **177** |
| 2008 | 155 | | |

**Đỉnh triều cao nhất ghi nhận: 177 cm (2019).**

### 3.3 Xu thế dài hạn (linear regression 48 năm)

| Đại lượng | Tốc độ tăng |
|---|:---:|
| MNTB năm | **+3,66 cm/thập kỷ** |
| Max năm | **+11,63 cm/thập kỷ** |
| Min năm | −1,74 cm/thập kỷ (giảm nhẹ) |

→ **Biên độ dao động mở rộng theo thời gian** (đỉnh cao hơn, đáy sâu hơn).

### 3.4 MNTB trung bình theo thập kỷ

| Thập kỷ | MNTB TB (cm) | So sánh 1977–1989 |
|---|:---:|:---:|
| 1977–1989 | **6,63** | 1,00× |
| 1990–1999 | 8,02 | 1,21× |
| 2000–2009 | 11,54 | 1,74× |
| 2010–2019 | 19,83 | 2,99× |
| **2020–2024** | **20,24** | **3,05×** |

→ **MNTB hiện tại gấp 3 lần thập kỷ 80** — phản ánh nước biển dâng + lún đất tại TP.HCM.

### 3.5 Pattern mùa (TB 48 năm)

| Tháng | MNTB TB (cm) | Đặc điểm |
|:---:|:---:|---|
| I | +27,5 | Mùa lũ kết thúc — vẫn cao |
| II | +22,0 | |
| III | +15,4 | Hạ dần |
| IV | +7,8 | |
| **V** | **−2,0** | Bắt đầu mùa khô |
| **VI** | **−13,0** | **Thấp nhất** |
| **VII** | **−11,9** | |
| VIII | −7,1 | |
| IX | +7,8 | |
| **X** | **+31,1** | Bắt đầu mùa lũ — tăng nhanh |
| **XI** | **+35,3** | **Cao nhất** |
| XII | +32,9 | |

**Biên độ mùa: ~48 cm** (Tháng XI cao nhất, Tháng VI thấp nhất).

---

## 4. Schema SQLite

### `thuyvan_daily` (17,530 rows)

| Cột | Type | Mô tả |
|---|---|---|
| id | INTEGER PK | Auto |
| station | TEXT default 'PhuAn' | |
| river | TEXT default 'SaiGon' | |
| year, month, day | INTEGER | |
| iso_date | TEXT | YYYY-MM-DD |
| h_cm | REAL | MNTB ngày (cm) |
| **UNIQUE** | `(year, month, day)` | |

### `thuyvan_annual_summary` (48 rows)

| Cột | Type | Mô tả |
|---|---|---|
| year | INTEGER UNIQUE | |
| avg_cm / max_cm / min_cm | REAL | Đặc trưng năm |
| max_day, max_month | INTEGER | Ngày/tháng xảy ra Max |
| min_day, min_month | INTEGER | Ngày/tháng xảy ra Min |
| monthly_avg_cm | TEXT (JSON array 12) | TB 12 tháng |
| monthly_max_cm | TEXT (JSON array 12) | Max 12 tháng |
| monthly_min_cm | TEXT (JSON array 12) | Min 12 tháng |

### `thuyvan_tidal_peaks` (13 rows)

| Cột | Type |
|---|---|
| year INTEGER UNIQUE | |
| peak_cm REAL | |

---

## 5. Áp dụng trong dự án TTHC

### 5.1 Mực nước thiết kế cho công trình ven sông

| Trường hợp thiết kế | MNTB phù hợp |
|---|---|
| Mực nước thấp khai thác (cừ kè khô) | **P5 = −25 cm** |
| Mực nước trung bình | **P50 = +13 cm** |
| Mực nước thiết kế cao (tải nước phía sau cừ) | **P95 = +48 cm** |
| Mực nước cực đại hiếm | **P99 = +59 cm** đến đỉnh triều **+177 cm** (kịch bản hiếm) |

### 5.2 Lưu ý cho kè SW + CDM

- Mực nước Front (sông) thiết kế: **+48 cm** (P95) hoặc **+59 cm** (P99) tùy mức độ quan trọng.
- Mực nước Back (đất sau cừ) thường thấp hơn 1–1,5 m so với Front (gradient thấm).
- Trong tính toán Winkler / áp lực đẩy nổi: dùng cao độ MNTB theo P95 cho thiết kế bền vững.
- Xu thế tăng MNTB **+11,6 cm/thập kỷ** cho đỉnh triều → cộng dự phòng cho công trình tuổi thọ 50 năm: **+58 cm** so với hiện tại.

### 5.3 Tham chiếu cho các tab app

- Tab `ke_sw`: cập nhật `wlvl_front` mặc định ≥ +0,5 m (cao độ Quốc gia) theo P95
- Tab `tvtk_prep`: cập nhật MN sông KE đã có `_wlvl_song` mặc định −1,5 m (nay nên xem lại)

---

## 6. Liên kết

- [scripts/thuyvan_phuan_import.py](scripts/thuyvan_phuan_import.py) — Parser
- [scripts/thuyvan_phuan_plots.py](scripts/thuyvan_phuan_plots.py) — Vẽ biểu đồ
- [data/thuyvan_phuan_analysis.png](data/thuyvan_phuan_analysis.png) — 5 biểu đồ tổng hợp
- [data/thuyvan_phuan_decades.png](data/thuyvan_phuan_decades.png) — So sánh thập kỷ
- [data/thuyvan_phuan_stats.json](data/thuyvan_phuan_stats.json) — Thống kê
- [CLAUDE.md](CLAUDE.md) §20 (Front/Back), §41 (thủy văn Phú An — mục này)
