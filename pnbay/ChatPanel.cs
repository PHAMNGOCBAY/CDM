using System;
using System.Drawing;
using System.Threading.Tasks;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Windows;

namespace pnbay
{
    public static class ChatPanel
    {
        private static PaletteSet _paletteSet;
        private static ChatPanelControl _control;
        private static readonly OllamaService _ollamaService = new OllamaService();

        public static void ShowPanel(Document doc)
        {
            if (_paletteSet == null)
            {
                _control = new ChatPanelControl();
                _control.SendRequested += async (text) => await HandleSend(doc, text);

                _paletteSet = new PaletteSet("Trợ lý AI - pnbay");
                _paletteSet.MinimumSize = new Size(320, 400);
                _paletteSet.Size = new Size(360, 500);
                _paletteSet.Add("Chat", _control);
            }
            _paletteSet.Visible = true;
        }

        private static async Task HandleSend(Document doc, string userPrompt)
        {
            Editor ed = doc.Editor;
            _control.SetBusy(true);
            _control.AppendMessage("Bạn", userPrompt);

            try
            {
                _control.StartThinking("Trợ lý", "Đang xử lý yêu cầu");
                string jsonResponse = await _ollamaService.SendPromptAsync(userPrompt);
                _control.StopThinking();

                if (jsonResponse.StartsWith("Error:"))
                {
                    ed.WriteMessage($"\n[Lỗi Kết Nối] {jsonResponse}\n");
                    _control.AppendMessage("Trợ lý", $"Lỗi kết nối: {jsonResponse}");
                    return;
                }

                string resultSummary = null;
                await Application.DocumentManager.ExecuteInCommandContextAsync(
                    async (obj) =>
                    {
                        resultSummary = ActionParser.ExecuteAction(doc, jsonResponse);
                        await Task.CompletedTask;
                    },
                    null
                );

                _control.AppendMessage("Trợ lý",
                    string.IsNullOrWhiteSpace(resultSummary)
                        ? "Đã thực hiện xong — xem chi tiết ở dòng lệnh AutoCAD."
                        : resultSummary);
            }
            catch (System.Exception ex)
            {
                _control.StopThinking();
                ed.WriteMessage($"\n[Lỗi Chung] {ex.Message}\n");
                _control.AppendMessage("Trợ lý", $"Lỗi: {ex.Message}");
            }
            finally
            {
                _control.SetBusy(false);
            }
        }
    }
}
