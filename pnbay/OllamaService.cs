using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace pnbay
{
    public class OllamaService
    {
        private readonly HttpClient _httpClient;
        private readonly string _ollamaUrl = "http://localhost:11434/api/generate";
        private readonly string _modelName = "gemma4:26b"; // Thay đổi nếu dùng model khác

        public OllamaService()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromMinutes(2);
        }

        public async Task<string> SendPromptAsync(string userPrompt)
        {
            string systemPrompt = @"Bạn là trợ lý CAD/Civil 3D chuyên nghiệp. Người dùng sẽ yêu cầu bạn vẽ hình học hoặc truy vấn/xuất dữ liệu Civil 3D.
Nhiệm vụ của bạn là dịch yêu cầu đó sang JSON.
TUYỆT ĐỐI KHÔNG giải thích, KHÔNG trả về markdown, CHỈ trả về chuỗi JSON.
Cấu trúc mỗi hành động được hỗ trợ:
1. Vẽ đường thẳng: {""action"": ""DrawLine"", ""parameters"": {""startX"": 0, ""startY"": 0, ""endX"": 10, ""endY"": 10}}
2. Vẽ đường tròn: {""action"": ""DrawCircle"", ""parameters"": {""x"": 0, ""y"": 0, ""radius"": 10}}
3. Chỉ XEM/TRUY VẤN đối tượng Civil 3D (KHÔNG ghi file): {""action"": ""Query"", ""parameters"": {""objectType"": ""CogoPoints"", ""alignmentName"": """", ""filter"": null}}
4. Truy vấn VÀ XUẤT RA FILE: {""action"": ""ExportQuery"", ""parameters"": {""objectType"": ""CogoPoints"", ""format"": ""excel"", ""fileName"": """", ""alignmentName"": """", ""filter"": null}}

   QUAN TRỌNG — chọn đúng giữa ""Query"" và ""ExportQuery"":
   - Dùng ""Query"" khi người dùng chỉ hỏi/xem/liệt kê/đếm (VD: ""có bao nhiêu COGO point"", ""xem danh sách Alignment"", ""tên các Surface là gì"") — KHÔNG được tự ý ghi file khi người dùng không yêu cầu.
   - Dùng ""ExportQuery"" CHỈ KHI người dùng nói rõ ý muốn xuất/lưu ra file (VD: ""xuất ra Excel"", ""xuất ra Word"", ""lưu ra file"", ""export"", ""tải về"").
   - Nếu không chắc, mặc định chọn ""Query"" (an toàn hơn — không tự ý tạo file khi chưa được yêu cầu).

   Tham số dùng chung cho cả 2 action trên:
   - ""objectType"" CHỈ được là một trong: CogoPoints, Alignments, Profiles, Surfaces, Corridors, PipeNetworks, Parcels
   - ""alignmentName"" chỉ cần điền khi objectType là ""Profiles"" (tên tuyến cần lấy trắc dọc); các objectType khác để rỗng
   - ""filter"" (tùy chọn, để null nếu người dùng không yêu cầu lọc) là một object chứa BẤT KỲ trường nào dưới đây, chỉ điền trường liên quan đến yêu cầu:
     * ""minElevation"" / ""maxElevation"" (số, mét) — lọc theo cao độ. Áp dụng cho CogoPoints (cao độ điểm), Surfaces (cao độ cao nhất của mặt), Profiles (cao độ cao nhất của trắc dọc)
     * ""centerX"" / ""centerY"" / ""radius"" (số, mét) — chỉ lọc CogoPoints nằm trong bán kính ""radius"" tính từ tọa độ (centerX, centerY)
     * ""minArea"" / ""maxArea"" (số, m²) — lọc Parcels theo diện tích
     * ""minLength"" / ""maxLength"" (số, mét) — lọc Alignments/Profiles theo chiều dài
   - Ví dụ lọc cao độ: ""filter"": {""minElevation"": 10}
   - Ví dụ lọc bán kính: ""filter"": {""centerX"": 0, ""centerY"": 0, ""radius"": 50}
   - Corridors và PipeNetworks KHÔNG hỗ trợ filter — nếu người dùng yêu cầu lọc 2 loại này, để ""filter"": null và bỏ qua yêu cầu lọc đó

   Tham số CHỈ dùng cho ""ExportQuery"" (không có trong ""Query""):
   - ""format"" CHỈ được là ""excel"" hoặc ""docx""
   - ""fileName"" là tên file tùy chọn (có thể để rỗng để tự đặt tên)

Nếu người dùng chỉ yêu cầu 1 hành động, trả về MỘT đối tượng JSON như trên.
Nếu người dùng yêu cầu NHIỀU hành động trong cùng một câu (kể cả trộn giữa vẽ và truy vấn/xuất file), trả về MỘT MẢNG JSON chứa nhiều đối tượng hành động, ví dụ:
[{""action"": ""DrawLine"", ""parameters"": {""startX"": 0, ""startY"": 0, ""endX"": 8, ""endY"": 0}}, {""action"": ""Query"", ""parameters"": {""objectType"": ""Alignments"", ""alignmentName"": """", ""filter"": {""minLength"": 100}}}]

Ví dụ phân biệt Query/ExportQuery cho cùng 1 đối tượng:
- ""xem danh sách COGO point"" → {""action"": ""Query"", ""parameters"": {""objectType"": ""CogoPoints"", ""alignmentName"": """", ""filter"": null}}
- ""xuất danh sách COGO point ra Excel"" → {""action"": ""ExportQuery"", ""parameters"": {""objectType"": ""CogoPoints"", ""format"": ""excel"", ""fileName"": """", ""alignmentName"": """", ""filter"": null}}

Nếu người dùng yêu cầu tọa độ không rõ (ví dụ không nói rõ tâm), hãy giả định bắt đầu từ 0,0 nếu phù hợp.
Yêu cầu của người dùng: ";
            
            string fullPrompt = systemPrompt + userPrompt;

            var payload = new
            {
                model = _modelName,
                prompt = fullPrompt,
                stream = false
                // Không dùng "format": "json" — tham số này ép Ollama theo khuôn 1 object
                // JSON đơn, làm hỏng phản hồi khi model cần trả về MẢNG nhiều hành động.
                // ActionParser.cs đã tự xử lý việc trim markdown fences nếu model lỡ thêm vào.
            };

            var content = new StringContent(JsonConvert.SerializeObject(payload), Encoding.UTF8, "application/json");

            try
            {
                var response = await _httpClient.PostAsync(_ollamaUrl, content);
                if (!response.IsSuccessStatusCode)
                {
                    string errorContent = await response.Content.ReadAsStringAsync();
                    return $"Error {response.StatusCode}: {errorContent}. Vui lòng kiểm tra lại Ollama và xem bạn đã pull model '{_modelName}' chưa bằng lệnh: ollama run {_modelName}";
                }

                var responseString = await response.Content.ReadAsStringAsync();
                var jsonDoc = JObject.Parse(responseString);
                string responseText = jsonDoc["response"]?.ToString() ?? "";
                
                return responseText.Trim();
            }
            catch (Exception ex)
            {
                return $"Error: Không thể kết nối tới Ollama. {ex.Message}";
            }
        }
    }
}
