### 76. Roadmap — LK2 / Lún nền chưa xử lý / BCL (phiên 2026)

Tracker tổng hợp các task đã làm trong chuỗi phiên về móng trụ CDM LK2, lún nền chưa xử lý
và bộ chỉ tiêu BCL. Quy tắc: hoàn thành → tick `[x]`; chỉ append, không xóa.

#### Đã hoàn thành

- [x] **LK2 Excel port** — tái lập 100% `TINH MONG TRU CDM - LK2.xlsx` (4 nhóm: lún khối, SCT, lún-thời gian, kiểm toán BT), 23 golden test sai số 0.00. (§74)
- [x] **Lún nền chưa xử lý** — engine `cdm_no_treat_settlement` + trang UI (theo hố khoan / 6 vùng CDM / bảng 6 vùng HK đại diện / hố khoan QTT mượn gần nhất). Vùng ảnh hưởng §71 (Δσ/σ'v0<10%, mở rộng dưới HK).
- [x] **Bộ chỉ tiêu BCL** (Ban chiến lược) — `bcl_soil_params` (SQLite+JSON+PY), P_c lấy từ lab khi BCL thiếu; single source bờ kè.
- [x] **Chỉ tiêu cơ lý trung bình theo lớp** — `soil_param_stats` (39 dòng) + trang "Thống kê cơ lý đất".
- [x] **Phân nhánh lún theo e₀** — cát Es / sét e₀≥1 cố kết Terzaghi / sét e₀<1 Eoed; lún thời gian chỉ ở sét e₀>1.
- [x] **Phạm vi bờ kè tuyến cừ** (on_sw_alignment=1, loại KE-HK8) + override XMD→bùn 1 + phương án "mới san lấp".
- [x] **Lún theo thời gian** (Cv từ BCL) + biểu đồ 15 năm + biểu đồ ứng suất σ'v0/Δσ/10% + đáy vùng ảnh hưởng.
- [x] **LK2 chọn địa tầng hố khoan** 6 vùng KE (mặc định KE-HK2) qua `build_geology_from_bh` (phân tố 2m); **Es=250·Cu**.
- [x] **S2 LK2 đầy đủ §71** qua cờ `sand_elastic` + `extend_below_bh` + cắt 10% (`INFLUENCE_STOP_RATIO`); golden vẫn pass.
- [x] **Công thức chi tiết LaTeX** mục A/B/C/D trang LK2; bảng + biểu đồ giới hạn đến vùng ảnh hưởng 10%.
- [x] **ui_defaults** (D0,8/S1,8/CD2 −25,2/P40,8/q55,8/W100/θ60/dv0,4) làm mặc định, giữ golden riêng.
- [x] **Chọn hố QTT** trong "Bảng chi tiết từng phân tố" (tính on-demand, dùng chung định dạng).
- [x] **Mode "Hố khoan QTT" trình bày 100% giống "Theo bảng 6 vùng"** — tách helper chung `_render_settlement_results(st, rows, full_results, …)` (bảng tổng hợp + bar S∞/15năm + công thức + chi tiết phân tố sửa CĐTK/CĐTN + lún-thời gian + đường cong 15 năm + biểu đồ ứng suất/vùng ảnh hưởng); `_render_zone_fill` và `_render_qtt` cùng gọi. CĐTK QTT lấy từ lưới `qtt_elevation_points` (điểm gần nhất); CĐTN từ `boreholes.elevation_m`; hố H=0 (CĐTN≥CĐTK) → sửa cao độ trong chi tiết.
- [x] **UI toàn cục:** font Calibri; bảng lưới đậm + tiêu đề đậm + print CSS; biểu đồ 12pt + legend (Rule 4/14/15 §64).
- [x] **Cập nhật khu QTT (2026-06):** 6 hố ND-02..07 ký hiệu lớp theo DXF gốc (tuần tự 1,2,3…); ND-03/04/05 mượn lab hố gần nhất ND-06; lab ND-02/06/07 verify khớp `260524 QTTT TP. KQTN.xls`; `qtt_elevation_points` (162 điểm); bảng định dạng `report_style`; CĐTN/CĐTK sửa được (data_editor) → bảng tự tính lại.
- [x] **Thống kê cơ lý gom theo LOẠI ĐẤT** cho QTT (`soil_param_stats.soil_type_of` + `group_mode="soil"`) — ký hiệu lớp tuần tự không đồng nhất; nhãn lớp đắp = "Đá san lấp".
- [x] **NC bùn chảy** (`nc_soft_clay`, mặc định) + **lựa chọn NC↔quá cố kết** (UI, không bỏ phương án); công thức TCCS 41 Điều 9.1 (CT 25–28) ghi trên app + doc 38.
- [x] **Lún tức thời** TCCS 41 Điều 9.2.1 SĐ1: `m_coef` (ô nhập 1,1–1,4), Si=(m−1)Sc cho bùn + Si đất không cố kết; bảng tách 3 thành phần Si; biểu đồ tránh số âm (tính trực tiếp).
- [x] **Dự báo đến 100 năm** + mốc 15/30/50 năm (bảng + biểu đồ); nhãn biểu đồ 2 chữ số thập phân; bỏ giới hạn ô bề rộng B.
- [x] **Htn theo CỤM sét** + tự nhận diện 1/2 mặt (`drainage="auto"/"double"/"single"`); cụm bị cắt ở đáy vùng ảnh hưởng → 1 mặt; bảng chi tiết từng cụm.
- [x] **Engine đọc DB cục bộ** (`_primary_db`) — tránh kết quả nhảy do Drive sync; phục hồi DB hỏng (§ memory corruption).

#### Pending / mở rộng tương lai

- [ ] Cho chọn hố BXN/NHC/QTT trong selectbox "Nguồn địa tầng" trang LK2 (hiện chỉ 6 vùng KE).
- [ ] Xuất Word báo cáo trang LK2 (mẫu 4 mục A/B/C/D + biểu đồ).
- [x] Cao độ thiết kế QTT theo từng điểm lưới thực (`qtt_elevation_points`, điểm gần nhất) thay vì 2,70 m chung.

#### Lịch sử

| Ngày | Hành động |
|---|---|
| 2026 | Khởi tạo + hoàn thành chuỗi task LK2/no-treat/BCL; lưu §74, §75, §76 + memory + SQLite/JSON |
