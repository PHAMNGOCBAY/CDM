# Công Nghệ Mã Nguồn Mở Cho Mô Phỏng Đường Sắt Tốc Độ Cao (HSR)

Tài liệu này tổng hợp các công cụ mã nguồn mở hàng đầu thế giới được sử dụng trong nghiên cứu và thiết kế hệ thống Đường sắt tốc độ cao (HSR), nhằm thay thế các giải pháp thương mại đắt đỏ.

---

## 1. Phân khúc Động lực học Đa vật thể (MBD - Tương tác Bánh / Ray)
*Mục đích: Mô phỏng sự nảy, lắc, trật bánh của đoàn tàu; sự mài mòn của bánh sắt và đường ray.*

| Hạng | Tên phần mềm | Đơn vị phát triển | Đặc điểm nổi bật |
| :--- | :--- | :--- | :--- |
| 🥇 **#1** | **Project Chrono** | ĐH Wisconsin-Madison | Nền tảng MBD (C++) mạnh nhất hiện nay. Hỗ trợ động lực học phương tiện với thư viện tiếp xúc phi tuyến cực tốt. |
| 🥈 **#2** | **FreeDyn** | ĐH Kỹ thuật Graz | Thiết kế thuần túy cho bài toán động lực học đa vật thể, giải quyết tốt hệ thống treo (suspension) của Bogie. |
| 🥉 **#3** | **MBDyn** | ĐH Bách khoa Milan | Chuyên về bài toán động lực học phi tuyến và tương tác Khí động học - Đa vật thể (Aeroelasticity). |

---

## 2. Phân khúc Kết cấu & Hạ tầng (FEA - Cầu, hầm, tà vẹt)
*Mục đích: Tính toán độ võng của cầu cạn, nứt mỏi mặt đường bê tông, độ lún nền đường (VBI / SSI).*

| Hạng | Tên phần mềm | Đơn vị phát triển | Đặc điểm nổi bật |
| :--- | :--- | :--- | :--- |
| 🥇 **#1** | **Code_Aster** <br>*(Salome-Meca)* | EDF / SNCF | **Vị Vua của nguồn mở.** Nhờ sự đóng góp trực tiếp từ SNCF, nó có sẵn các thuật toán chuẩn để tính toán tương tác động lực học Xe - Cầu (VBI) và phân tích nứt gãy (XFEM). |
| 🥈 **#2** | **CalculiX** | Đội ngũ độc lập | "Abaqus phiên bản miễn phí". Chạy cực nhanh và tính toán phi tuyến hình học tốt cho kết cấu nhà ga, hầm chui. |
| 🥉 **#3** | **Elmer FEM** | CSC (Phần Lan) | Nổi bật với khả năng giải bài toán Đa vật lý (Ví dụ: sự co giãn của ray dài vô hàn dưới tác động nhiệt). |

---

## 3. Phân khúc Khí động học & Thủy lực (CFD - Gió, ồn, sóng áp suất)
*Mục đích: Tính sức cản gió, tiếng ồn khí động học, sóng áp suất (Piston effect) khi tàu đâm vào hầm chui.*

| Hạng | Tên phần mềm | Đơn vị phát triển | Đặc điểm nổi bật |
| :--- | :--- | :--- | :--- |
| 🥇 **#1** | **OpenFOAM** | OpenCFD | Tiêu chuẩn công nghiệp thế giới. Lựa chọn số 1 để tối ưu hóa hình dáng mũi tàu. Khả năng chạy MPI siêu máy tính vô địch. |
| 🥈 **#2** | **SU2** | ĐH Stanford | Mã nguồn mở C++ sinh ra dành riêng cho mô phỏng Khí động học tốc độ cao (Compressible flow). |
| 🥉 **#3** | **Palabos** | ĐH Geneva | Sử dụng thuật toán Lattice Boltzmann (LBM). Cực kỳ mạnh trong việc mô phỏng Khí âm học (Tiếng ồn rít của Pantograph). |

---

## 4. Tương thích với Hệ điều hành Windows
Mặc dù là mã nguồn mở (thường ưu tiên Linux), các phần mềm này vẫn có thể chạy trên Windows:
*   **Chạy trực tiếp (.exe):** CalculiX, Elmer FEM, SU2, Project Chrono.
*   **Khuyến nghị chuẩn công nghiệp (Dùng WSL):** Đối với các phần mềm hạng nặng như **OpenFOAM, Code_Aster, và preCICE**, các kỹ sư bắt buộc nên sử dụng **WSL (Windows Subsystem for Linux)**. Bằng cách cài đặt Ubuntu ngầm bên trong Windows, hệ thống sẽ tận dụng được 100% sức mạnh đa luồng của CPU và tránh được các lỗi tương thích.

---

## 5. Quy trình Mô phỏng Toàn diện (The Dream Team)
Để mô phỏng toàn diện hệ thống HSR mà không tốn phí bản quyền, quy trình lý tưởng là sự ghép nối Đa vật lý (Multi-physics Coupling):

> **Project Chrono** (Mô phỏng bánh tàu/Dao động toa xe)  
> $\leftrightarrow$ **preCICE** (Ghép nối, ánh xạ dữ liệu)  
> $\leftrightarrow$ **Code_Aster** (Mô phỏng mặt cầu võng/Ứng suất dầm)  
> $\leftrightarrow$ **OpenFOAM** (Mô phỏng gió tạt ngang làm lật tàu)

### Câu hỏi quan trọng: "Các phần mềm này có dùng CHUNG một nguồn lưới phần tử hữu hạn không?"

**Trả lời: KHÔNG.** Chúng sử dụng các loại lưới hoàn toàn khác nhau. Và đây chính là lý do tại sao ta cần **preCICE**!

1.  **Lưới của OpenFOAM (Lưu chất):** Là lưới **Thể tích hữu hạn (Finite Volume Mesh)**. Lưới này bao trùm không khí *xung quanh* đoàn tàu và cây cầu. Nó thường rất mịn ở các lớp biên (sát vỏ tàu) và là các hình khối đa diện (Polyhedral) hoặc lục diện (Hexa).
2.  **Lưới của Code_Aster (Kết cấu):** Là lưới **Phần tử hữu hạn (Finite Element Mesh)**. Lưới này chỉ lấp đầy phần *chất rắn* (thép, bê tông của cây cầu). Lưới thường to hơn và là các hình tứ diện (Tetrahedral).
3.  **Mô hình của Project Chrono (MBD):** Thường không dùng lưới FEA truyền thống, mà dùng các khối rắn tuyệt đối (Rigid bodies) hoặc lưới cực kỳ đơn giản để tính động lực học nhanh chóng.

**Sự kỳ diệu của preCICE:**
Vì 3 lưới này hoàn toàn "vênh" nhau (không trùng khớp các điểm Node), nếu không có preCICE, lực gió từ OpenFOAM sẽ không biết phải truyền vào điểm nào trên dầm cầu của Code_Aster. 
**preCICE hoạt động như một cỗ máy nội suy toán học (Mapping Engine).** Nó tự động phân tích bề mặt tiếp xúc của 3 loại lưới này, lấy áp suất gió ở điểm A trên lưới không khí, nội suy và phân bổ chính xác thành Lực đẩy (Force) lên điểm B nằm lệch đi một chút trên lưới bê tông, đảm bảo định luật bảo toàn năng lượng. 

Do đó, kỹ sư chỉ cần vẽ lưới tối ưu nhất cho từng phần mềm độc lập, phần ghép nối đã có preCICE lo tự động hóa!

---

## 6. Ứng Dụng Đám Mây Điểm (Scan to BIM) Trong Vận Hành
Việc tích hợp dữ liệu quét 3D (Point Cloud) từ Laser Scanner hoặc Drone mang lại giá trị cốt lõi để biến hệ thống thành Bản sao kỹ thuật số (Digital Twin) thực thụ cho công trình đang vận hành. Thay vì sử dụng bản vẽ thiết kế thẳng tắp (As-designed), hệ thống sẽ mô phỏng trực tiếp trên bề mặt thực tế đã bị lún, nứt, võng (As-is).

### Các thư viện xử lý và chia lưới mã nguồn mở hàng đầu:
*   **Dành cho Kỹ sư / Xử lý thủ công:**
    *   **CloudCompare:** Tiêu chuẩn vàng để mở và xử lý các file Scan hàng trăm triệu điểm. Có thuật toán bọc lưới Poisson.
    *   **MeshLab:** Công cụ đắc lực để dọn dẹp, vá lỗ thủng bề mặt (Watertight Mesh).
*   **Dành cho Lập trình viên / Tự động hóa (Python/C++):**
    *   **Open3D / PCL:** Lọc nhiễu, trích xuất đặc trưng và tái tạo bề mặt tự động.
    *   **IfcOpenShell:** Đóng gói lưới bề mặt thành các đối tượng chuẩn BIM (IFC).
*   **Sinh lưới Thể tích (Volumetric Meshing) cho tính toán:**
    *   **Gmsh:** Đổ phần tử tứ diện (Tetrahedral) vào bên trong vỏ lưới bề mặt để Code_Aster có thể tính toán nứt gãy và biến dạng.
    *   **SnappyHexMesh (OpenFOAM):** Khoét rỗng không gian xung quanh bản scan cầu để OpenFOAM mô phỏng luồng gió thổi qua bề mặt gồ ghề.
