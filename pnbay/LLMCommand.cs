using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.ApplicationServices;

[assembly: CommandClass(typeof(pnbay.LLMCommand))]

namespace pnbay
{
    public class LLMCommand
    {
        [CommandMethod("PNBAY")]
        public void LlmDrawCommand()
        {
            Document doc = Application.DocumentManager.MdiActiveDocument;
            if (doc == null) return;

            // Mở (hoặc đưa lên trước) panel chat dock — panel giữ nguyên qua nhiều lần gọi lệnh.
            ChatPanel.ShowPanel(doc);
        }
    }
}
