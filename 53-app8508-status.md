# 53. App 8508 (FastAPI) — Trạng thái & Roadmap

**Cập nhật:** 2026-05-24
**Mục đích:** App 8508 là phiên bản UI custom HTML/JS thay cho Streamlit 8503,
chạy độc lập trên port 8508 qua FastAPI + Uvicorn.

## 1. Kiến trúc

| Layer | Stack | File |
|---|---|---|
| Backend API | FastAPI + Uvicorn | `web/app8508.py` (~550 dòng) |
| Frontend | HTML5 + ES2020 JS + Plotly + Leaflet + Chart.js | `web/templates/app.html` (~6,500 dòng) |
| Styling | Custom CSS dark theme | `web/static/style.css` |
| Data | Chung SQLite `data/TTHC.sqlite` với 8503 | (read-only) |

**Khởi động** (detached, không phụ thuộc Claude session):

```powershell
Start-Process -FilePath python.exe `
  -ArgumentList '-X','utf8','-m','uvicorn','web.app8508:app','--port','8508' `
  -WorkingDirectory 'G:\My Drive\AI-SUC TAI COC THEO DAT NEN' `
  -WindowStyle Hidden
```

URL: `http://localhost:8508`

## 2. API endpoints (16 endpoints active)

### Địa chất
- `GET /api/boreholes?zone={KE|BXN|NHC|QTT|all}` — danh sách HK + zone
- `GET /api/borehole/{name}/layers` — địa tầng + SPT + VST cho 1 HK

### CDM
- `GET /api/cdm/toado?zone=` — tọa độ cọc CDM
- `GET /api/cdm/stats` — thống kê cọc CDM theo zone/HK
- `GET /api/cdm/tien-do` — tiến độ thi công daily + tổ đội
- `GET /api/cdm/kiem-tra` — kết quả qu kiểm tra

### Cọc ván SW
- `GET /api/ke-sw/catalog` — 22 loại SW (Atd, Itd, Mcr, L_max...)
- `GET /api/ke-sw/design` — kết quả NT detail + JSON config 8 HK alignment
- `GET /api/ke-sw/winkler` — kết quả nội lực Winkler
- `GET /api/ke-sw/stability` — Fellenius ổn định tổng thể
- `GET /api/ke-sw/nt-layers` — chi tiết lớp đất NT2 per HK
- `GET /api/ke-sw/nt2-compare` — so sánh 5 PP (auto/α/β/λ/SPT)
- `GET /api/ke-sw/profile-chainage` — trắc dọc PCA SVD + bình đồ + khoảng cách

### Khác
- `GET /api/ke-binhdo` — polylines tuyến kè
- `GET /api/geo/locations?epsg={9209|9210|3405}` — VN-2000 → WGS-84
- `GET /api/settlement/{compare,analyze}` — wrap settlement_calc.py
- `POST /api/pdf/weasyprint` — HTML → PDF bytes

## 3. Trạng thái 19 trang trong sidebar

### Nghiệp vụ (8 trang)

| Page | Coverage vs 8503 | Phase |
|---|---:|---|
| ke_sw — Cọc ván SW (Kè) | **~50%** | Phase 1+2 xong (A/B/B.2/B.3/B.4/C). Còn D+E |
| bvt_sw — TKBVTC Cọc SW | ~50% | Đã có A Winkler + B Stability + C Conditions |
| sample_check — Kiểm tra mẫu TN | ~70% | Cơ bản đủ, thiếu heatmap + box plot + scatter qu-E50 |
| cdm_tien_do — Tiến độ CDM | ~50% | Daily + tổ đội cơ bản, thiếu Gantt timeline |
| geology — Địa chất | ~50% | Leaflet + bh log Plotly. Thiếu 3D pydeck + nén cố kết |
| cdm_bvt — TKBVTC CDM | ~30% | Bản đồ folium/pydeck OK. Thiếu Plotly mặt bằng + KL CDM |
| params — Thiết kế CDM | ~20% | Bảng tham số. Thiếu compare PA + S(t) |
| settlement — Dự báo lún | ~25% | Single curve. Thiếu compare 5 PA + bảng layer |

### Lab/Dev (11 trang — đặc trưng 8508)

`fem_libs`, `fem_wasm`, `webgl_viz`, `wasm_offline`, `wasm_native`, `viz_heavy`, `api_ui`, `draw_2d`, `cad_param`, `pdf_tools`, `ban_do_vi_tri`

Không có ở 8503 — không cần match.

## 4. Lịch sử đã làm

| Session | Việc |
|---|---|
| Initial | FastAPI skeleton + Jinja2 templates + 13 endpoints + 19 page handlers |
| Sửa lỗi tab Địa chất | Fix `/api/borehole/{name}/layers`: layer_no→id, VST link qua vst_locations.name, Su_kPa chữ S hoa |
| Sửa in PDF | beforeprint Plotly relayout sang light theme + CSS @media print ép `rect.bg` trắng, height max 12cm, 2-col→1-col |
| Sidebar | Thiết kế nút đóng/mở to 44×44px + hover navy + transition |
| Phase 1 ke_sw | API `/api/ke-sw/profile-chainage` (PCA SVD chainage 8 HK alignment). Section A+B (editable cọc kiến nghị + L thiết kế + nút "Dùng cọc tối ưu") + B.2 trắc dọc + B.3 bình đồ |
| Phase 2 ke_sw | API `/api/ke-sw/nt-layers` + `/api/ke-sw/nt2-compare`. Section B.4 chi tiết NT từng HK (7 expander) + Section C so sánh 5 PP NT2 (bảng 15 cột + bar chart + expander detail) |

## 5. Roadmap (priority đánh dấu)

### ★★★ Trang ke_sw — Phase 3+4

**Phase 3** (Section D — Winkler + lý thuyết + áp lực + nội lực):
- Section D.1 Tổng quan: bảng + chart u_max/M_max/Mcr ratio cho 8 HK
- Section D.1 Chi tiết per HK với lý thuyết:
  - Matlock 1970 (sét) + API GoM (cát) + CDM hiệu chỉnh
  - Biểu đồ p-y curve mẫu per vật liệu
- Áp lực nước (hydrostatic + seepage 2 phía) + tải Boussinesq
- Biểu đồ áp lực đất ngang Active/Net/Passive (TCVN 11823-3 §10.5)
- 5 panel nội lực/HK: u(z), p(z), Q(z), M(z), M/Mcr
- API mới: `/api/ke-sw/winkler-detail/{bh_name}` returning profile z-arrays

**Phase 4** (Section E — Ổn định 3 PP + Word):
- Bảng Fs 3 phương pháp (Fellenius / Bishop / Janbu) per HK
- Biểu đồ bar so sánh Fs theo PP
- Chi tiết mặt trượt nguy hiểm — vẽ cung tròn trên cross-section
- API mới: `/api/ke-sw/stability-detail/{bh_name}` returning slip surface
- Nút "Xuất Word" giống 8503 (7 chương, python-docx + math2docx, header/footer)

### ★★ Các trang khác

| Trang | Còn cần |
|---|---|
| params (Thiết kế CDM) | Compare phương án a-spacing, S(t) chart, ứng suất theo z, cross-check qu lab vs design |
| settlement (Dự báo lún) | Biểu đồ lún 5 PA cùng đồ thị, bảng layer (σ'v0, σ'vf, PC, OC/cross_PC/NC), expander lý thuyết |
| cdm_bvt (TKBVTC CDM) | Plotly mặt bằng raw VN-2000, Matplotlib backup PDF, thống kê khối lượng KL, bảng L theo HK |
| geology | 3D pydeck ColumnLayer 4 zone, trắc dọc multi-HK, expander nén cố kết, bảng khoảng cách TCCS 41 |
| cdm_tien_do | Gantt timeline thi công, heatmap qu × cement_dosage |
| sample_check | Heatmap qu × dosage × W/C × cement, box plot qu theo cement, scatter qu↔E50 |

### ★ Hạ tầng chung

- PDF export per-tab: hook `/api/pdf/weasyprint` cho từng trang (currently endpoint sẵn nhưng chưa wire)
- Word export đầy đủ qua endpoint mới `/api/word/{section}/{bh_name}`
- Theme switcher light/dark (8503 light, 8508 dark — match optional)
- Auto-refresh khi SQLite đổi (mtime check + SSE hoặc polling 5s)
- Deploy 8508 lên Cloud? — chưa có (current `/deploy-cloud` chỉ deploy 8503)

## 6. Pitfalls đã đúc kết

1. **Restart uvicorn**: dùng `Start-Process -WindowStyle Hidden`. Background Bash bị kill khi Claude session đóng.
2. **Endpoint mới chưa active**: phải kill process trên port 8508 trước khi restart.
3. **SQLite schema mismatch** với code Streamlit:
   - `layers` KHÔNG có `layer_no` — dùng `id`
   - `vane_shear_tests` link qua `vst_locations.name`, KHÔNG có FK borehole_id
   - Cột là `Su_kPa` (S hoa), không phải `su_kPa`
4. **Plotly print PDF**: nền tối render inline SVG → CSS không override. Phải JS `Plotly.relayout()` trong `beforeprint` ép sang light theme.
5. **CRS boreholes**: x_coord_m=Northing, y_coord_m=Easting. QTT từng bị ngược.
6. **SQLite lock**: nếu 8503 đang chạy → 8508 update có thể fail. Kill python trước.

## 7. Workflow chuẩn cho phase tiếp theo

1. Đọc 8503 source page tương ứng (`scripts/app_cdm.py`) → hiểu logic
2. Check SQLite schema đủ data chưa (PRAGMA table_info)
3. Tạo API endpoint mới ở `web/app8508.py` (sau endpoint cùng group)
4. Restart uvicorn + verify curl + Python parse
5. Thêm HTML section + JS handler vào `pageXxx` trong `app.html`
6. Bind buttons, localStorage nếu cần
7. Test browser hard refresh
8. Commit (chưa deploy — 8508 chỉ chạy local hiện tại)

## 8. Liên kết

- Memory: [`project_8508_status.md`](memory/project_8508_status.md) (auto-load mỗi session)
- Skill deploy 8503: [`.claude/commands/deploy-cloud.md`](.claude/commands/deploy-cloud.md)
- CLAUDE.md §32: convention CRS VN-2000 → WGS-84 (áp dụng cả 8508)
