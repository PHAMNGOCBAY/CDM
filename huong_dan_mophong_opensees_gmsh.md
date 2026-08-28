# Hướng dẫn lựa chọn và Mô phỏng phi tuyến Đất - Kết cấu (SSI) 

Tài liệu này tổng hợp các đánh giá và hướng dẫn quy trình (workflow) cho bài toán phân tích dao động 3D cầu khung có xét đến tương tác phi tuyến Đất - Kết cấu (Soil-Structure Interaction - SSI), đặc biệt khi sử dụng các phần mềm mã nguồn mở.

## 1. So sánh các phần mềm mã nguồn mở

Khi đối mặt với bài toán tương tác phi tuyến đất - kết cấu dưới tải trọng động, sự lựa chọn phần mềm là yếu tố quyết định.

| Tiêu chí | OpenGeoSys (OGS) | CalculiX | OpenSees / OpenSeesPy |
| :--- | :--- | :--- | :--- |
| **Mục tiêu thiết kế** | Phân tích Đa vật lý (Nhiệt - Thủy - Cơ - Hóa) cho đất đá. | Phân tích Cơ - Nhiệt tĩnh hoặc bán tĩnh cho kết cấu kim loại/chất rắn. | **Dao động, Động đất & Tương tác Đất - Kết cấu (SSI).** |
| **Mô phỏng Đất Yếu** | Rất tốt (lún cố kết, dòng thấm đa pha). Cần dùng MFront cho vật liệu. | Yếu. Không có sẵn mô hình (phải tự viết UMAT rất phức tạp), khó hội tụ với lực dính thấp. | **Tuyệt vời.** Có sẵn các mô hình PDMY, PIMY, Manzari-Dafalias chuyên cho động lực học đất phi tuyến. |
| **Tốc độ tính toán** | Trung bình. | **Rất nhanh** (hỗ trợ đa luồng và bộ giải trực tiếp cực tốt cho bài toán tĩnh). | Tương đối chậm khi chạy trên Python (cần lặp nhiều cấp độ phần tử), nhưng bắt buộc cho tính toán động phi tuyến. |
| **Kết luận cho SSI Động lực học**| Không tối ưu. | Không phù hợp. | **Lựa chọn số 1.** Khả năng mô phỏng hóa lỏng và suy giảm độ cứng đất vô đối. |

> [!IMPORTANT]
> **Khuyến nghị:** Đối với bài toán dao động 3D cầu khung có xét phi tuyến khối đất xung quanh cọc, **OpenSeesPy** là sự lựa chọn tối ưu và chuẩn mực nhất hiện nay trong giới học thuật và nghiên cứu.

---

## 2. Quy trình (Workflow) Gmsh -> OpenSeesPy cho mô hình Khối 3D (Solid)

Nếu yêu cầu mô phỏng đòi hỏi **cả cọc và đất đều sử dụng phần tử khối liên tục 3D (Solid 3D)**, luồng công việc sẽ dựa trên Gmsh (chia lưới) và OpenSeesPy (giải hệ phương trình).

### Các bước thực hiện:
1. **Dựng hình và Chia lưới (Gmsh):** Dựng hình học 3D, phân chia các vùng không gian (Physical Groups) cho Đất, Cọc, Mặt tiếp xúc, Biên. Xuất lưới ra định dạng `.msh`.
2. **Tiền xử lý dữ liệu lưới (Python + meshio):** Sử dụng thư viện `meshio` trong Python để đọc file `.msh`, trích xuất tọa độ Nút (Nodes) và danh sách liên kết Phần tử (Elements).
3. **Đưa vào OpenSeesPy:** Viết script Python để vòng lặp qua các Nodes và Elements vừa trích xuất, phát sinh tự động các lệnh `ops.node()` và `ops.element()` trong OpenSees. 

---

## 3. Ba thách thức kỹ thuật cốt lõi và Giải pháp

Việc sử dụng 100% phần tử khối 3D cho cả cọc và đất trong OpenSeesPy đối mặt với 3 thách thức cực kỳ lớn:

### 3.1. Vấn đề loại lưới (Tứ diện vs Lục diện)
> [!WARNING]
> Gmsh rất mạnh về chia lưới Tứ diện (Tetrahedral - 4 nút), nhưng các mô hình vật liệu đất phi tuyến trong OpenSees (PDMY/PIMY) lại được tối ưu hóa cho lưới Khối hộp/Lục diện (Hexahedral/Brick - 8 nút). Dùng lưới tứ diện cho đất dẻo rất dễ gây ra hiện tượng khóa thể tích (volumetric locking) làm khối đất cứng bất thường.

*   **Giải pháp:** Bắt buộc điều khiển Gmsh chia lưới dạng **Hexahedral**. Sử dụng tính năng *Recombine*, *Transfinite mesh*, hoặc chia lưới theo dạng trụ-hộp (Box-cylinder) quanh cọc để ép Gmsh sinh ra phần tử 8 nút (phù hợp với `SSPbrick` trong OpenSees).

### 3.2. Mô phỏng Tiếp xúc / Trượt Đất-Cọc (Contact Modeling)
Khác với Abaqus hay Plaxis, OpenSees không có tính năng vẽ "Mặt tiếp xúc" (Surface-to-Surface) tự động.
*   **Cách 1 (Shared Topology - Dễ):** Yêu cầu Gmsh gộp chung Nút tại ranh giới Đất-Cọc. Cọc và đất dính chặt vào nhau, không trượt. Chấp nhận được nếu chấn động không quá lớn.
*   **Cách 2 (Zero-Length Contact - Khó):** Tách rời các nút của cọc và đất tại mặt tiếp xúc trong Gmsh. Sau đó, dùng Python rà soát các cặp nút có chung tọa độ này và gán phần tử `zeroLengthContact3D` hoặc lò xo ma sát để mô phỏng khả năng trượt/tách rời. Đòi hỏi kỹ năng lập trình xử lý mảng (numpy) rất tốt.

### 3.3. Xử lý Biên phản xạ sóng (Absorbing Boundaries)
Trong phân tích tĩnh (tính lún), chỉ cần ngàm cứng xung quanh khối đất. Nhưng trong phân tích động lực học, sóng dao động truyền tới mặt ngàm sẽ dội ngược lại mô hình.
*   **Giải pháp:** Bắt buộc phải gắn các **biên giảm chấn (Lysmer-Kuhlemeyer dashpots)**. Tại các Nút biên và đáy khối đất từ Gmsh, bạn phải dùng script Python tự động khai báo và gắn thêm hàng loạt phần tử giảm chấn (dashpot) để hấp thụ năng lượng sóng.

---
*Tài liệu được trích xuất và tổng hợp phục vụ việc ra quyết định xây dựng mô hình Đất - Kết cấu phi tuyến 3D bằng mã nguồn mở.*
