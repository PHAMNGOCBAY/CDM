# 47 — Địa chất khu Quảng Trường Trung Tâm (QTT)

**Dự án:** 202605-TTHC — Trung tâm Hành chính TP. HCM
**Khu vực:** Quảng Trường Trung Tâm thành phố (An Khánh, Thành phố Thủ Đức)
**Nguồn DXF:** `G:/My Drive/202605-TRUNG TAM HCM/DIA CHAT/7. QUANG TRUONG TRUNG TAM/QTTT-7HK_TruHienTruong.dxf`
**Script import:** [scripts/import_qtt_zone.py](scripts/import_qtt_zone.py)
**Data JSON:** [data/zone_qtt_overview.json](data/zone_qtt_overview.json)
**SQLite zone:** `zones.code = 'QTT'` (id=4)

## 1. Tổng quan 5 hố khoan

DXF chứa 5 HK (tên file là "7HK" nhưng thực tế 5):

| Hố khoan | Cao độ mặt đất (m) | Tổng độ sâu (m) | Northing VN-2000 | Easting VN-2000 |
|---|---|---|---|---|
| ND-02 | +1.70 | 31.0 | 1,191,680.407 | 605,239.025 |
| ND-03 | +1.89 | 36.0 | 1,191,670.883 | 605,340.447 |
| ND-05 | +3.20 | 36.0 | 1,191,736.974 | 605,445.999 |
| ND-06 | +4.24 | 36.0 | 1,191,761.037 | 605,349.439 |
| ND-07 | +3.47 | 36.0 | 1,191,785.152 | 605,252.887 |

ND-01 và ND-04 không có trong file DXF này (có thể ở file khác).

## 2. Đặc điểm địa tầng (sơ bộ từ MTEXT)

Mô tả lớp đất xuất hiện trong DXF:
- **Lớp F** — Đá san lấp, đá đổ lẫn sét (đất đắp mặt)
- **Lớp 1** — Bùn sét màu xám xanh, trạng thái chảy (lớp yếu chính)
- **Lớp 3** — Sét pha màu xám xanh, trạng thái dẻo mềm
- **Lớp 4/5** — Cát màu xám trắng kết cấu chặt vừa (lớp chịu lực)

**Chú thích**: Layers cụ thể với depth_top/depth_bot cho mỗi HK chưa được import (script chỉ trích metadata header). Khi cần đầy đủ, mở rộng `import_qtt_zone.py` để parse layer descriptions từ MTEXT theo y position.

## 3. Cập nhật trong app

**`scripts/app_cdm.py`** đã bổ sung QTT vào:
- `_ZONE_NAMES["QTT"] = "Quảng Trường Trung Tâm (QTT)"`
- `_CLAY_SYMBOLS["QTT"] = ["1", "2"]` (lớp bùn sét yếu)
- `_ZONE_MARKER["QTT"] = "cross"` (Plotly 3D map)
- `_zone_colors["QTT"] = "#F9A825"` (cam vàng — phân biệt với 3 zone cũ)
- `_zone_rgb["QTT"] = [249, 168, 37]` (Pydeck 3D)

## 4. Workflow user trên app

1. Tab **Địa chất** → Radio "Khu vực" → chọn **QTT**
2. Selectbox hố khoan: ND-02 / ND-03 / ND-05 / ND-06 / ND-07
3. Nhấn "Áp dụng" → set `cdm_zone = 'QTT'`, `cdm_bh = 'ND-XX'`
4. Sang tab **Thông số** → block "Áp địa chất" tự lấy data từ SQLite (cao độ + depth từ boreholes; γ/Su nearest fallback nếu chưa có lab)
5. Bản đồ 3D zone QTT hiển thị với marker `cross` màu cam

## 5. Bước tiếp theo (khi có yêu cầu)

- [ ] Parse layers chi tiết từ DXF (depth_top/bot/symbol/description)
- [ ] Import lab_tests từ file Excel KQTN của QTT
- [ ] Import SPT data từ trang riêng trong DXF
- [ ] Tạo file Excel CDM riêng cho zone QTT
- [ ] Cập nhật script `borehole_spacing` để check khoảng cách HK QTT
