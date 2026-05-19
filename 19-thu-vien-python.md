# 19. Thư Viện Python — Phân Tích Cọc Tải Ngang, Hệ Số Nền, Dầm Đàn Hồi

Nguồn: `THU VIEN PYTHON.docx` (Drive ID: `1KqaNuU9zd4HBA5TLDXUiTEOi21JXf6wa`)  
Cập nhật: 2026-05-14 | Python: 3.12.10

---

## 19.1. Cài Đặt

```bash
python -m pip install openseespy openpile anastruct geolysis geofound \
       bedrock-ge pandera geopandas shapely numpy scipy matplotlib pandas
```

`ebbef2p-python`: không có trên PyPI — cài từ GitHub source.

---

## 19.2. Tra Cứu Nhanh

| Bài toán | Thư viện | Ghi chú |
|----------|----------|---------|
| Cọc tải ngang — tĩnh, đa lớp | **openpile** 1.0.2 | OOP, Euler-Bernoulli + Timoshenko |
| Cọc tải ngang — động, hóa lỏng | **openseespy** | FEM 3D, PySimple1/TzSimple1/QzSimple1 |
| Hệ số nền Ks — Bowles | **geolysis** 0.24.1 | `create_abc_*` → `Ks = 40·SF·qa` |
| Hệ số nền Ks — Schmertmann | **geofound** | `settlement_schmertmann` → `Ks = Δq/Δs` |
| Dầm Winkler — nhanh | **anastruct** | `add_support_spring(node, Ks)` |
| Dầm nền hai thông số | **ebbef2p-python** | Galerkin, Ks biến thiên dọc trục |
| Dữ liệu lỗ khoan AGS/GEF/CPT | **bedrock-ge** 0.3.3 | → GeoPandas pipeline |

---

## 19.3. Cọc Chịu Tải Ngang — Lý Thuyết p-y

### Cơ sở phương pháp

Phương trình vi phân cọc:

```
EI · d⁴y/dz⁴ + p(y,z) = q(z)
```

- `y` : độ võng tại chiều sâu z (m)
- `p(y,z)` : sức kháng đất phi tuyến (kN/m) — đường cong p-y
- `EI` : độ cứng uốn cọc (kN·m²)

### Đường cong p-y tiêu chuẩn API (1987) — đất rời

```
p = A·pu · tanh(k·z·y / (A·pu))
```

`pu` : sức kháng ngang cực hạn; `k` : hệ số độ cứng ban đầu (kN/m³)

| Góc ma sát φ (°) | k trên MNN (kN/m³) | k dưới MNN (kN/m³) |
|-----------------|--------------------|--------------------|
| 28.8            | 5 400              | 2 700              |
| 33.5            | 20 300             | 10 800             |
| 38.5            | 61 000             | 40 700             |
| 40.0            | 81 600             | 54 900             |

### So sánh thư viện

| | OpenSeesPy | openpile | PyPile | PY_Analysis |
|---|---|---|---|---|
| Phương pháp | FEM 3D | FEM 1D | FEM 1D | FDM + FEM |
| Đường cong p-y | PySimple1 (API) | nhiều loại | nhiều + tùy biến JS | nghiên cứu mới |
| Tải động | Có | Không | Không | Eigenvalue |
| Dễ dùng | Trung bình | Cao | Cao | Thấp |
| Nhóm cọc | Beam-solid 3D | Không | P-multiplier | Không |

---

## 19.4. Hệ Số Phản Lực Nền Ks

### Định nghĩa và đơn vị

```
Ks = q / s    [kN/m³]
```

`q` : áp lực tiếp xúc (kN/m²); `s` : độ lún (m)

**Lưu ý:** Ks KHÔNG phải thuộc tính thuần của đất — phụ thuộc vào kích thước móng, độ cứng kết cấu, chiều sâu.

### Công thức

**Bowles (1996) — thực nghiệm, dùng phổ biến:**
```
Ks = 40 · SF · qa    [kN/m³]    (hệ SI)
```
Giả định độ lún cho phép = 25 mm. SF thường = 3.

**Vesic (1961) — tích hợp độ cứng uốn EI:**
```
Ks = (0.65·Es / (1−ν²)) · (Es·B⁴ / EI)^(1/12)
```

**Biot (1937):**
```
Ks = (0.95·Es / (B·(1−ν²))) · (Es·B⁴ / EI)^0.108
```

**Schmertmann — phân bố theo độ sâu:**
```
Ks = Δq / Δs_Schmertmann
```

### Sử dụng geolysis

```python
from geolysis.bearing_capacity import create_abc_4_cohesionless_soils

abc = create_abc_4_cohesionless_soils(
    corrected_spt_n_value=15,
    terzaghi_peck_bowles_method=True,
    foundation_width=1.5,   # m
    foundation_depth=1.5,   # m
    unit_weight=18.0,        # kN/m³
)
qa  = abc.allowable_bearing_capacity()   # kN/m²
Ks  = 40 * 3 * qa                        # kN/m³  (SF=3, Bowles)
```

---

## 19.5. Dầm Trên Nền Đàn Hồi

### Mô hình Winkler

```
EI · d⁴y/dx⁴ = q(x) − Ks · y(x)
```

Lò xo độc lập — bỏ qua ứng suất cắt ngang giữa đất liền kề.

### Mô hình hai thông số (Pasternak)

```
EI · d⁴y/dx⁴ − Gp · d²y/dx² = q(x) − Ks · y(x)
```

`Gp` : tham số cắt của nền (kN/m) — nối các lò xo Winkler.

### Ứng dụng anaStruct (Winkler)

```python
from anastruct import SystemElements

ss = SystemElements()
for i in range(10):
    ss.add_element(location=[[i, 0], [i+1, 0]], EI=5000, EA=1e6)
    ss.add_support_spring(node_id=i+1, translation=2, k=20000)  # Ks·dx

ss.point_load(node_id=5, Fy=-100)
ss.solve()
ss.show_displacement()
```

### Sử dụng ebbef2p (hai thông số)

Cài từ GitHub. Hỗ trợ Ks và Gp biến thiên dọc theo chiều dài dầm.

---

## 19.6. Luồng Tự Động Hóa Đề Xuất

```
bedrock-ge             → parse AGS/GEF → GeoDataFrame lỗ khoan
        ↓
geolysis / geofound    → tính qa, s_schmertmann → Ks phân bố
        ↓
openpile / openseespy  → mô hình cọc p-y đa lớp → nội lực, độ võng
        ↓
anastruct / ebbef2p    → dầm đài cọc / móng băng trên Ks phân bố
        ↓
matplotlib / pandas    → xuất bảng + biểu đồ → python-docx báo cáo
```

---

## 19.7. File Liên Quan

| File | Mô tả |
|------|-------|
| [data/python_libs_geotechnical.json](data/python_libs_geotechnical.json) | Catalog thư viện — metadata, phiên bản, openpile gotchas, tools |
| [scripts/lateral_pile_demo.py](scripts/lateral_pile_demo.py) | Demo script: Ks + openpile + anastruct |
| [scripts/app_coc_tai_ngang.py](scripts/app_coc_tai_ngang.py) | Giao diện Streamlit — nhập số liệu, biểu đồ nội lực |
| [notebooks/coc_tai_ngang_openpile.ipynb](notebooks/coc_tai_ngang_openpile.ipynb) | Notebook Jupyter — biểu đồ inline trong VSCode |

---

## 19.8. openpile 1.0.x — API Đúng (Hay Nhầm)

| Điểm nhầm | Sai | Đúng |
|-----------|-----|------|
| Chiều dày thành cọc | `wall_thickness=0.016` | `wt=0.016` |
| Model đất trong Layer | `soil_model=API_sand(...)` | `lateral_model=API_sand(...)` |
| Dung trọng lớp đất | (bỏ quên) | `weight=18.0`  bắt buộc, > 10 kN/m³ |
| Lực ngang đầu cọc | `Hx=100` | `Py=100` |
| Kết quả chuyển vị | `result.global_disp` | `result.deflection["Deflection [m]"]` |
| Kết quả nội lực | `result.global_forces` | `result.forces["V [kN]"]`, `result.forces["M [kNm]"]` |

**Bắt buộc thêm `BoundaryFixation` tại mũi cọc** — không có sẽ không hội tụ:

```python
from openpile.construct import BoundaryFixation
bc = [BoundaryFixation(elevation=-L_m, x=True, y=True, z=True)]
model = Model(name="m", pile=pile, soil=sp, boundary_conditions=bc)
```

**Địa tầng phải phủ hết chiều dài cọc** — clip lớp cuối trước khi tạo `SoilProfile`:

```python
# Kéo dài lớp cuối đến đáy cọc nếu chưa đủ
last = layers[-1]
if last["z_bot"] > -L_m:
    last["z_bot"] = -L_m
```

---

## 19.9. Giao Diện Streamlit — Cách Chạy

```bash
python -m streamlit run "scripts/app_coc_tai_ngang.py"
# Mở browser: http://localhost:8501
```

**Tính năng:**
- Sidebar nhập: kiểu cọc, D, t, L, H, M, MNN, số lớp đất (φ, γ, z_top, z_bot)
- Cho phép nhập lớp đất **sâu hơn chiều dài cọc** — tự clip khi tính
- Trục Y: **âm xuống dưới, dương lên trên** (quy ước toán học chuẩn)
- 4 KPI cards: y_head, y_max, M_max (kèm chiều sâu), V_max (kèm chiều sâu)
- Biểu đồ 3 panel: chuyển vị / lực cắt / mô men — màu nền theo địa tầng
- Panel mặt cắt địa tầng + cọc (hiển thị đủ cả lớp sâu hơn mũi cọc)
- Bảng kết quả chi tiết + nút **Tải CSV**

**Jupyter Notebook (biểu đồ inline trong VSCode):**

```
notebooks/coc_tai_ngang_openpile.ipynb
Kernel: Python 3.12 (địa kỹ thuật)
```

Đăng ký kernel (nếu chưa có):
```bash
python -m ipykernel install --user --name python312 --display-name "Python 3.12 (địa kỹ thuật)"
```
