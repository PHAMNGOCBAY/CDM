### 32. Tab TKBVTC CDM — Bản đồ HK 2D folium + 3D pydeck (cập nhật 2026-05-23)

**Vị trí:** `app_cdm.py`, `if _page == "cdm_bvt":` (~line 13700)
**Thư viện:** `folium`, `streamlit-folium`, `pydeck`, `pyproj` (đã thêm vào requirements.txt)

#### Quy ước tọa độ VN-2000 → WGS-84

| Nguồn | Convention | Truyền vào `Transformer.transform(always_xy=True)` |
|---|---|---|
| `boreholes` table | `x_coord_m = Northing`, `y_coord_m = Easting` | `(y_coord_m, x_coord_m)` |
| `ke_binhdo_*.json` polyline | `x_m = Easting`, `y_m = Northing` | `(x_m, y_m)` |

**3 hệ EPSG dùng được cho HCM** (selectable trong UI, mặc định EPSG:9210 vì Q1/Thủ Thiêm):

| EPSG | Tên | Central meridian | Khi dùng |
|---|---|---|---|
| **9210** | VN-2000 / TM-3 106°00' | 106°E | TTHC Quận 1, Thủ Thiêm (mặc định) |
| 9209 | VN-2000 / TM-3 105°45' | 105.75°E | HCM tổng quát các quận khác |
| 3405 | VN-2000 / UTM 48N | 105°E | Khi dữ liệu gốc dùng UTM 6-degree |

#### UI structure

- 3 cột điều khiển: zone (KE/BXN/NHC/Tất cả) · CRS · view mode (2D / 3D)
- **2D folium**: 4 nền togglable (OSM / Vệ tinh Esri / OpenTopoMap / CartoDB) + FeatureGroup HK (CircleMarker + DivIcon label) + FeatureGroup polyline kè đen + plugins (Fullscreen / MeasureControl / MiniMap) + LayerControl không collapsed
- **3D pydeck**: ColumnLayer (HK depth × 10x cho dễ nhìn) + ScatterplotLayer (đỉnh column) + PathLayer (polyline kè) + 4 map_style (light/dark/road/satellite) + tooltip HTML hover

#### Pitfalls đã giải quyết

1. **`x_coord_m` vs `x_m`** — KHÔNG nhất quán giữa `boreholes` (x=N, y=E) và `ke_binhdo` (x=E, y=N). Phải nhớ swap đúng khi gọi `transformer.transform()`.
2. **CRS sai → HK lệch 25-50km** trên bản đồ. Mặc định EPSG:9210 cho TTHC, có dropdown selector phòng dự án khác.
3. **`pyproj` axis_swap** — luôn dùng `always_xy=True` → input/output dạng (x=Easting/lon, y=Northing/lat). Dễ nhớ.
4. **`contextily` / `rasterio`** — kéo GDAL ~40MB, KHÔNG đưa lên Cloud (đã ghi rõ trong requirements.txt).

---

