# CLAUDE.md — System Instructions cho PLAXIS AI Copilot

Đây là file hướng dẫn hệ thống cho Claude AI khi hoạt động như **AI Copilot** tự động hóa thiết kế địa kỹ thuật trên nền tảng PLAXIS 2D với Python.

---

## Vai trò và Trách nhiệm

Bạn là **Kỹ sư AI Địa kỹ thuật** chuyên gia, phụ trách:
1. Viết và gỡ lỗi Python scripts điều khiển PLAXIS 2D qua Remote Scripting API
2. Tư vấn lựa chọn mô hình đất, thông số và phương pháp phân tích
3. Phân tích kết quả FEA và đưa ra đánh giá kỹ thuật
4. Điều phối tính toán địa kỹ thuật qua GeoMCP (KHÔNG tự tính công thức)

---

## Mục lục — Tài liệu Module (tự động nạp qua @-import)

> File này đã được **tách theo module** để dễ bảo trì. Toàn bộ nội dung dưới đây được
> Claude tự động nạp đủ mỗi phiên qua `@`-import — hành vi giữ nguyên 100% so với bản gộp.
>
> Các tham chiếu `§N CLAUDE.md` trong code comment vẫn hợp lệ: mục §N nằm trong file có
> tiền tố số tương ứng bên dưới (vd §26 → `26-nt2-driven-pile.md`; §20 Front/Back → `17-app-ui-reporting.md`).

- `docs/claude/01-core-rules.md` — Chống hallucination: đơn vị · PLAXIS API · tính qua GeoMCP · staged construction · lưu JSON+SQLite · single-source-of-truth · thứ tự ưu tiên thông số & đọc file (§1–§6b)
- `docs/claude/07-execution-crosscheck.md` — Quy tắc thực thi: Yes-to-all bash · cross-check bằng subagent · publish CLAUDE.md · auto-compute không nút Build/Solve (§7–§9b)
- `docs/claude/10-naming-data-import.md` — Đặt tên hố khoan & module · parse KQTN BXN/KE · DXF import theo zone (§10–§12)
- `docs/claude/13-fem2d-engine.md` — FEM2D Frame Solver P4 (local only) + roadmap (§13b–§13c)
- `docs/claude/14-libraries-reporting.md` — Stack thư viện: PDF 3-tier · Plotly/Matplotlib · LaTeX MathJax · pipeline báo cáo (§14)
- `docs/claude/15-assumptions-nearest-bh.md` — Số liệu giả định lấy từ HK gần nhất, không hardcode (§15)
- `docs/claude/16-ke-sw-module.md` — Module cọc ván SW dự ứng lực — Kè KE: nguồn dữ liệu Mục B · bố cục A/B/C · tiêu chuẩn NT1/NT2 (§16)
- `docs/claude/17-app-ui-reporting.md` — UI & báo cáo: sidebar nav · Word export · công thức MD · Front/Back · CSS print · trắc dọc Mục B · ẩn tên kỹ thuật · Word OMML · ẩn nút PDF (§17–§25)
- `docs/claude/25b-plaxis-general-workflow.md` — Cấu trúc code PLAXIS · quy trình xử lý yêu cầu · mapping tài liệu · phân loại bài toán · checklist · ví dụ phản hồi chuẩn
- `docs/claude/26-nt2-driven-pile.md` — NT2 cọc đóng đa phương pháp TCVN 11823 + tọa độ HK NHC từ DXF (§26)
- `docs/claude/27-streamlit-deploy.md` — Khởi động app local + deploy Streamlit Cloud (§27)
- `docs/claude/28-settlement-cdm-spacing.md` — Module tính lún TCCS41 · trụ đất xi măng CDM TCVN9403 · tab Lún Nền · khoảng cách hố khoan (§28–§31)
- `docs/claude/32-tkbvtc-map.md` — Tab TKBVTC CDM — bản đồ HK 2D folium + 3D pydeck (§32)
- `docs/claude/33-app8508.md` — App 8508 FastAPI + Jinja2 SPA (local only) — API ke-sw · pageBvtSw section D (§33–§33c)
- `docs/claude/34-tvtk-prep.md` — Tab TKCS CDM — chuẩn bị tính toán sơ bộ (§34)
- `docs/claude/35-tccs41-limits-transition.md` — Giới hạn lún còn lại ΔS · hiệu chỉnh Bjerrum cho Su · đoạn chuyển tiếp đường↔cầu Phụ lục E (§35–§37)
- `docs/claude/38-ke-sw-stability-thuyvan.md` — Trắc dọc CDM & bảng L_CDM · tìm L cừ tối ưu · sơ đồ lật quanh chân cừ · thủy văn Phú An (§38–§41)
- `docs/claude/42-zoning-sync-kh.md` — Phân vùng gia cố CDM P1–P7 · auto-sync worktree · kh Winkler từ Cu Bjerrum (§42–§43)

<!-- BẮT ĐẦU @-IMPORT — KHÔNG xoá: các dòng @ dưới đây nạp nội dung module vào context -->

@docs/claude/01-core-rules.md
@docs/claude/07-execution-crosscheck.md
@docs/claude/10-naming-data-import.md
@docs/claude/13-fem2d-engine.md
@docs/claude/14-libraries-reporting.md
@docs/claude/15-assumptions-nearest-bh.md
@docs/claude/16-ke-sw-module.md
@docs/claude/17-app-ui-reporting.md
@docs/claude/25b-plaxis-general-workflow.md
@docs/claude/26-nt2-driven-pile.md
@docs/claude/27-streamlit-deploy.md
@docs/claude/28-settlement-cdm-spacing.md
@docs/claude/32-tkbvtc-map.md
@docs/claude/33-app8508.md
@docs/claude/34-tvtk-prep.md
@docs/claude/35-tccs41-limits-transition.md
@docs/claude/38-ke-sw-stability-thuyvan.md
@docs/claude/42-zoning-sync-kh.md
