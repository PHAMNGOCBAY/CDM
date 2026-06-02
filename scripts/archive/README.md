# scripts/archive/ — Mã tham chiếu, không production

Các module trong thư mục này được giữ lại làm tham chiếu kỹ thuật.
KHÔNG import từ code production. KHÔNG được sửa nếu không có lý do rõ ràng.

## Danh sách

### `cdm_cushion_bending.py`

**Trạng thái:** archive từ 2026-05-29.
**Lý do archive:** Theo PWRI ALiCC gốc, lớp đệm cát-XM được kiểm bằng chọc thủng,
KHÔNG kiểm uốn. File R14 `KIEM TOAN LOP BTXM C10.xls` áp công thức uốn cho **lớp
bê tông xi măng cứng** (q_uckse = 10000 kPa), không phải đệm cát-XM thông thường
(q_uckse = 600 kPa). Áp công thức uốn vào đệm cát-XM cho ratio 5-10 → không khả thi.

**Giá trị tham chiếu:** file chứa 5 phương pháp tính M_max (Hetenyi, Westergaard,
plate Timoshenko, simple beam clear/full span) có thể dùng cho dự án sau nếu cấu
tạo có lớp BTXM riêng giữa đệm và cọc CDM.

**Xem thêm:** `docs/claude/66-cushion-params-tthc.md` §66.2.

Nếu cần áp dụng lại — copy ra `scripts/`, import từ `scripts.archive.cdm_cushion_bending`
hoặc adapt cho cấu hình mới (cần hiệu chỉnh γ_fill, kiểm tra ngưỡng σ_ba).
