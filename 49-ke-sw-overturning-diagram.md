# Hình minh họa tải trọng gây lật quanh chân cừ SW

Mô-đun phụ trợ hiển thị trực quan các tải trọng và mô men quanh chân cừ trong kiểm tra ổn định **lật** (Fs lật) — Mục E của tab `ke_sw`.

---

## 1. Mục đích

Khi tính $F_{s,lật} = M_{giữ} / M_{lật}$ trong Mục E, người dùng cần **hình minh họa trực quan** các lực + mô men + tay đòn để:

- Kiểm tra trực quan tính hợp lý của input (cao độ, lớp đất, mực nước, tải mặt)
- Phân biệt rõ tải trọng **gây lật** (Active đẩy) vs **giữ ổn định** (Passive kháng + trọng lượng)
- Hiểu cơ chế xoay quanh **chân cừ** (pivot point)
- Tham chiếu kết quả $F_s$ với ngưỡng cho phép 1,20

## 2. Quy ước Front / Back (BẮT BUỘC — CLAUDE.md §20)

| Phía | Vị trí trên hình | Áp lực chính | Vai trò |
|---|---|---|---|
| **Front** (TRÁI) | Đất đắp + tải mặt | Active (Ka) | **Gây lật** — đẩy cừ về Back |
| **Back** (PHẢI) | Đáy đào / sông | Passive (Kp) | **Giữ ổn định** — kháng cừ |

## 3. Thành phần đồ họa

### 3.1 Lớp đất + mặt cắt

- **Đất đắp Front** (trên `soil_level_front`): vùng tô nâu nhạt `#D2B48C`
- **Đất tự nhiên Front** (dưới `soil_level_front`): vùng tô xanh nhạt `#A4D2EB`
- **Đất tự nhiên Back** (dưới `soil_level_back`): vùng tô xanh lá nhạt `#B8D8B8`
- **Cừ SW**: dải xanh dương `#1565C0`, độ rộng 0,35 m
- **Cao độ chính**: đường ngang đứt mảnh + label phải

### 3.2 Pivot point — Chân cừ

- Vòng tròn lớn `#FF6B6B` viền `#a01010` ms 14 tại `(0, pile_tip)`
- Annotation "**Chân cừ (điểm xoay)**" với mũi tên kéo ra phải

### 3.3 Mực nước

- MNN Front: đường đứt `#1E90FF`, label trái
- MN sông Back: đường đứt `#0066CC`, label phải

### 3.4 Tải mặt phân bố $q$ (phía Front)

- 4 mũi tên đỏ chỉ xuống `#D32F2F`, lw 1.4
- Thanh ngang đỏ phía trên + label "$q = X$ kN/m²"

### 3.5 Áp lực Active phía Front (gây lật)

- Tam giác hồng `#FFCDD2` viền `#D32F2F`, vertices: `(0, top)`, `(0, tip)`, `(0 - 2, tip)`
- 7 mũi tên ngang đỏ đẩy về Back, scale tăng dần từ trên xuống (proxy $K_a \sigma_v$)
- Label "$P_a = X$ kN/m" hộp trắng viền đỏ

### 3.6 Áp lực Passive phía Back (giữ)

- Tam giác xanh lá `#C8E6C9` viền `#2E7D32`, vertices: `(0, soil_back)`, `(0, tip)`, `(0 + 2.2, tip)`
- 4 mũi tên xanh lá kháng ngược về Front, scale lớn ở chân cừ
- Label "$P_p = X$ kN/m" hộp trắng viền xanh

### 3.7 Tay đòn $z_a$, $z_p$

- $z_a$: mũi tên đôi đỏ từ chân cừ lên điểm đặt $P_a$ (Front, vị trí $x = -3.5$)
- $z_p$: mũi tên đôi xanh lá từ chân cừ lên điểm đặt $P_p$ (Back, $x = +3.5$)
- Dấu × đánh dấu điểm đặt lực trên mỗi tam giác

### 3.8 Mũi tên cong mô men

- **M_lật** (cung 130°–220° CCW): nửa vòng trái dưới `#D32F2F` — chỉ chiều xoay cừ về Back
- **M_giữ** (cung −40°→50° CW): nửa vòng phải dưới `#2E7D32` — chiều kháng
- Cả 2 vẽ với bán kính 1,4 m quanh chân cừ
- Label "**M_lật**" / "**M_giữ**" trong hộp màu tương ứng

### 3.9 Bảng kết quả $F_s$

LaTeX hộp trắng viền theo trạng thái:

$$F_s = \frac{M_{giữ}}{M_{lật}} = \frac{X}{Y} = Z$$

Ngưỡng $F_s \geq 1,20$ → **ĐẠT** (xanh) hoặc **KHÔNG ĐẠT** (đỏ).

## 4. API Python

```python
from sw_global_stability import draw_overturning_diagram

fig = draw_overturning_diagram(
    geom,             # WallGeometry
    front_layers,     # list[EarthLayer]
    back_layers,      # list[EarthLayer]
    fill=...,         # EarthLayer | None
    cdm=...,          # CDMBlock | None
    pile=...,         # PileProps | None
    M_giu_kNm=64104.1,
    M_lat_kNm=63817.1,
    Fs=1.004,
    bh_name='KE-HK1 / SW-740 / L=28m',
    figsize=(11, 8),
    Fs_min=1.20,
)
# fig: matplotlib.Figure — dùng st.pyplot() hoặc fig.savefig()
```

## 5. Tích hợp app (Mục E tab `ke_sw`)

Vị trí: ngay sau bảng tổng hợp 4 PP ổn định.

**Expander "Sơ đồ minh họa tải trọng gây lật quanh chân cừ":**

1. Selectbox chọn HK đã tính (chỉ HK có `Fs lật != None`)
2. Query `ke_sw_stability` lấy `(top_elev, Z_m, Zb_m, wlvl_front, wlvl_back, q_kPa, M_giu_kNm, M_lat_kNm, Fs_overturning)`
3. Build `WallGeometry` + EarthLayer mặc định (đất yếu chung) + Fill mặc định
4. Gọi `draw_overturning_diagram()` + `st.pyplot()` + `plt.close()`

Mặc định layer đơn giản (sét yếu chung phi=2°, c=10 kPa, gamma=14,8); fill mặc định (phi=25°, c=0, gamma=18). Hợp lý cho mục đích minh họa giáo dục.

## 6. Schema SQLite — `ke_sw_stability` (tham chiếu)

| Cột dùng cho diagram | Ý nghĩa |
|---|---|
| `top_elev` | Đỉnh cừ |
| `Z_m` | `soil_level_front` (mặt đất Front) |
| `Zb_m` | `soil_level_back` (đáy đào Back) |
| `wlvl_front` / `wlvl_back` | Mực nước 2 phía |
| `q_kPa` | Tải mặt Front |
| `M_giu_kNm` / `M_lat_kNm` | Mô men giữ / lật |
| `Fs_overturning` | Kết quả $F_s$ |

## 7. Liên kết

- [scripts/sw_global_stability.py](scripts/sw_global_stability.py) — engine `check_overturning()` + `draw_overturning_diagram()`
- [scripts/app_cdm.py](scripts/app_cdm.py) Mục E ~line 10570 — UI expander
- [48-ke-sw-L-optimal-search.md](48-ke-sw-L-optimal-search.md) — Thuật toán tìm L tối ưu (khi $F_s$ chưa đạt)
- [CLAUDE.md](CLAUDE.md) §20 (Front/Back convention), §39 (tìm L tối ưu), §40 (hình minh họa này)
