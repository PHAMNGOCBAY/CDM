using System;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using Autodesk.Revit.UI;

namespace RevitGeotechPlugin
{
    public class App : IExternalApplication
    {
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetDllDirectory(string lpPathName);

        public Result OnStartup(UIControlledApplication application)
        {
            try
            {
                // Fix cho SQLite.Interop.dll trong Revit
                string assemblyFolder = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
                SetDllDirectory(Path.Combine(assemblyFolder, "x64"));
                // Create a custom ribbon tab
                string tabName = "Geotech BIM";
                application.CreateRibbonTab(tabName);

                // Add a new ribbon panel
                RibbonPanel ribbonPanel = application.CreateRibbonPanel(tabName, "Geotech Tools");

                // Create a push button to trigger the command
                string thisAssemblyPath = Assembly.GetExecutingAssembly().Location;
                PushButtonData buttonData = new PushButtonData("cmdBIMdiachat", 
                    "Tạo Mô hình\nĐịa chất", thisAssemblyPath, "RevitGeotechPlugin.MainCommand");

                PushButton pushButton = ribbonPanel.AddItem(buttonData) as PushButton;
                pushButton.ToolTip = "Đọc file SQLite và tạo mô hình 3D địa chất với đầy đủ dữ liệu BIM.";

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                Autodesk.Revit.UI.TaskDialog.Show("Lỗi Khởi động Plugin", ex.Message);
                return Result.Failed;
            }
        }

        public Result OnShutdown(UIControlledApplication application)
        {
            return Result.Succeeded;
        }
    }
}
