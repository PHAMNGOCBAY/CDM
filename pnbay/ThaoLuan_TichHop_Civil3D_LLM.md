# Nhật ký thảo luận: Tích hợp LLM (Ollama + Gemma) vào AutoCAD Civil 3D

**Thời gian:** 12 Tháng 8, 2026
**Dự án:** pnbay (C# Plugin cho Civil 3D)

## 1. Yêu cầu ban đầu
- Tích hợp mô hình ngôn ngữ lớn (LLM - Ollama + Gemma) vào AutoCAD Civil 3D để tương tác và vẽ trực tiếp trên giao diện Civil 3D.
- Khởi tạo kiến trúc kết nối thông qua C# Plugin sử dụng `.NET API` của AutoCAD.

## 2. Quá trình triển khai
- **Khởi tạo dự án:** Tạo mới dự án C# tên là `Civil3D_LLM_Plugin` (sau này đổi thành `pnbay`), bao gồm các file:
  - `pnbay.csproj`: File cấu hình dự án.
  - `OllamaService.cs`: Chịu trách nhiệm gửi HTTP POST đến Ollama API (`localhost:11434/api/generate`) để dịch ngôn ngữ tự nhiên sang JSON định dạng hình học.
  - `ActionParser.cs`: Phân tích chuỗi JSON trả về và sử dụng AutoCAD DatabaseServices để gọi lệnh vẽ (ví dụ: `DrawLine`, `DrawCircle`).
  - `LLMCommand.cs`: Đăng ký lệnh `PNBAY` cho AutoCAD để khởi động luồng giao tiếp.

## 3. Quá trình khắc phục lỗi (Troubleshooting) & Cải tiến
- **Đổi tên Plugin:** Thay đổi tên toàn bộ dự án, thư mục và namespace từ `Civil3D_LLM_Plugin` sang `pnbay` theo yêu cầu.
- **Vấn đề môi trường Build:** Máy người dùng không có sẵn SDK .NET. Hệ thống đã phải dùng script PowerShell để tải ngầm `Microsoft .NET SDK`.
- **Cập nhật Framework AutoCAD 2027:** Phát hiện AutoCAD 2027 yêu cầu tối thiểu **.NET 10** thay vì .NET 8 hay .NET Framework 4.8 cũ. Cấu hình `.csproj` được cập nhật lại thành `net10.0-windows` và đã build thành công thư viện `pnbay.dll`.
- **Nâng cấp Giao diện & Xử lý lỗi 404:**
  - Lỗi 404 Not Found từ Ollama xảy ra. Đã cập nhật code trong `OllamaService.cs` để hiển thị rõ ràng nội dung nguyên nhân báo lỗi từ máy chủ.
  - Bổ sung `PromptDialog.cs` (Sử dụng Windows Forms) để tạo giao diện hộp thoại (Dialog Box) nhập prompt thay vì bắt người dùng nhập trên giao diện dòng lệnh (Command Line) dễ lỗi font chữ.
- **Chuyển đổi Model AI:** Cập nhật model đích sử dụng trên local thành **`gemma4`** theo cấu hình mới nhất của người dùng.

## 4. Hướng dẫn sử dụng hiện tại
1. Khởi động phần mềm AutoCAD Civil 3D 2027.
2. Gõ lệnh `NETLOAD` vào dòng lệnh.
3. Trỏ tới tệp `G:\My Drive\AI-SUC TAI COC THEO DAT NEN\pnbay\bin\Release\pnbay.dll` và chọn Load.
4. Gõ lệnh `PNBAY` và nhập yêu cầu vẽ vào hộp thoại vừa xuất hiện.
