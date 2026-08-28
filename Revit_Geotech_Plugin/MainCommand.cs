using System;
using System.Collections.Generic;
using System.Data.SQLite;
using System.IO;
using System.Windows.Forms;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using Newtonsoft.Json;

namespace RevitGeotechPlugin
{
    // Cấu trúc dữ liệu BIM (giống bên Civil 3D)
    public class BIMElementModel
    {
        public string BoreholeName { get; set; }
        public GeotechData Geology { get; set; }
        public AIMAsset AIM { get; set; }
        public COBieData COBie { get; set; }
    }

    public class GeotechData
    {
        public string LayerSymbol { get; set; }
        public string Description { get; set; }
        public double TopDepth { get; set; }
        public double BottomDepth { get; set; }
        public double Thickness { get; set; }
        public Dictionary<string, string> SoilProperties { get; set; }
    }

    public class AIMAsset
    {
        public string AssetID { get; set; }
        public string Status { get; set; }
        public string InstalledDate { get; set; }
        public string LifecycleStage { get; set; }
    }

    public class COBieData
    {
        public string TypeName { get; set; }
        public string ComponentName { get; set; }
        public string Space { get; set; }
        public string Category { get; set; }
    }

    [Transaction(TransactionMode.Manual)]
    public class MainCommand : IExternalCommand
    {
        private static double MtoFt(double meters)
        {
            return meters * 3.28083989501312;
        }

        private string GetSafeString(SQLiteDataReader reader, string colName)
        {
            int ordinal = reader.GetOrdinal(colName);
            return reader.IsDBNull(ordinal) ? "" : reader.GetString(ordinal);
        }

        private double GetSafeDouble(SQLiteDataReader reader, string colName)
        {
            int ordinal = reader.GetOrdinal(colName);
            return reader.IsDBNull(ordinal) ? 0.0 : reader.GetDouble(ordinal);
        }

        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            UIApplication uiapp = commandData.Application;
            Document doc = uiapp.ActiveUIDocument.Document;

            // Chọn file SQLite
            using (OpenFileDialog ofd = new OpenFileDialog())
            {
                ofd.Title = "Chọn cơ sở dữ liệu TTHC.sqlite";
                ofd.Filter = "SQLite Database (*.sqlite;*.db)|*.sqlite;*.db|All Files (*.*)|*.*";
                
                if (ofd.ShowDialog() != DialogResult.OK)
                {
                    return Result.Cancelled;
                }

                string dbPath = ofd.FileName;
                string connString = $"Data Source={dbPath};Version=3;";

                try
                {
                    using (SQLiteConnection conn = new SQLiteConnection(connString))
                    {
                        conn.Open();

                        // Lấy danh sách hố khoan và thông tin cơ bản
                        Dictionary<long, (string Name, double X, double Y, double Z)> bhDict = new Dictionary<long, (string, double, double, double)>();
                        string sqlBh = "SELECT id, name, coord_x, coord_y, elevation FROM Boreholes";
                        using (SQLiteCommand cmdBh = new SQLiteCommand(sqlBh, conn))
                        {
                            using (SQLiteDataReader reader = cmdBh.ExecuteReader())
                            {
                                while (reader.Read())
                                {
                                    long id = reader.GetInt64(reader.GetOrdinal("id"));
                                    string name = GetSafeString(reader, "name");
                                    double x = GetSafeDouble(reader, "coord_x");
                                    double y = GetSafeDouble(reader, "coord_y");
                                    double z = GetSafeDouble(reader, "elevation");
                                    bhDict[id] = (name, x, y, z);
                                }
                            }
                        }

                        // Bắt đầu Transaction trong Revit
                        using (Transaction trans = new Transaction(doc, "Tạo Mô hình Địa chất 3D"))
                        {
                            trans.Start();

                            string sqlLayers = "SELECT id, borehole_id, symbol, description, depth_top_m, depth_bot_m, thickness_m FROM GeotechLayers ORDER BY borehole_id, depth_top_m";
                            using (SQLiteCommand cmd = new SQLiteCommand(sqlLayers, conn))
                            {
                                using (SQLiteDataReader reader = cmd.ExecuteReader())
                                {
                                    int count = 0;
                                    while (reader.Read())
                                    {
                                        long layerId = reader.GetInt64(reader.GetOrdinal("id"));
                                        long bhId = reader.GetInt64(reader.GetOrdinal("borehole_id"));
                                        
                                        if (!bhDict.ContainsKey(bhId)) continue;
                                        
                                        var bhInfo = bhDict[bhId];
                                        string bhName = bhInfo.Name;
                                        double elev = bhInfo.Z;
                                        double x = bhInfo.X;
                                        double y = bhInfo.Y;

                                        string symbol = GetSafeString(reader, "symbol");
                                        string desc = GetSafeString(reader, "description");
                                        double top = GetSafeDouble(reader, "depth_top_m");
                                        double bot = GetSafeDouble(reader, "depth_bot_m");
                                        double thickness = GetSafeDouble(reader, "thickness_m");

                                        if (thickness <= 0) continue;

                                        // Chuyển đổi toạ độ sang hệ đơn vị Feet của Revit
                                        double topElevFt = MtoFt(elev - top);
                                        double thicknessFt = MtoFt(thickness);
                                        double radiusFt = MtoFt(1.0); // Bán kính khối trụ 1 mét
                                        double xFt = MtoFt(x);
                                        double yFt = MtoFt(y);

                                        // Tạo CurveLoop hình tròn
                                        XYZ center = new XYZ(xFt, yFt, topElevFt);
                                        Plane plane = Plane.CreateByNormalAndOrigin(XYZ.BasisZ, center);
                                        Arc arc = Arc.Create(plane, radiusFt, 0, 2 * Math.PI);
                                        CurveLoop curveLoop = CurveLoop.Create(new List<Curve> { arc });

                                        // Tạo khối Cylinder bằng Extrusion
                                        // Đẩy xuống dưới (chiều âm Z)
                                        Solid cylinder = GeometryCreationUtilities.CreateExtrusionGeometry(
                                            new List<CurveLoop> { curveLoop }, 
                                            XYZ.BasisZ.Negate(), 
                                            thicknessFt);

                                        // Tạo DirectShape
                                        DirectShape ds = DirectShape.CreateElement(doc, new ElementId(BuiltInCategory.OST_GenericModel));
                                        ds.ApplicationId = "AI_TAI_COC";
                                        ds.ApplicationDataId = $"BH_{bhId}_L_{layerId}";
                                        ds.SetShape(new List<GeometryObject> { cylinder });

                                        // --- TÍCH HỢP BIM DATA ---
                                        BIMElementModel bimData = new BIMElementModel
                                        {
                                            BoreholeName = bhName,
                                            Geology = new GeotechData
                                            {
                                                LayerSymbol = symbol,
                                                Description = desc,
                                                TopDepth = top,
                                                BottomDepth = bot,
                                                Thickness = thickness,
                                                SoilProperties = new Dictionary<string, string>
                                                {
                                                    { "N_value_avg", "15" }, 
                                                    { "Gamma_kNm3", "18.5" } 
                                                }
                                            },
                                            AIM = new AIMAsset
                                            {
                                                AssetID = $"BH-{bhId}-L{layerId}",
                                                Status = "Existing",
                                                InstalledDate = DateTime.Now.ToString("yyyy-MM-dd"),
                                                LifecycleStage = "Investigation"
                                            },
                                            COBie = new COBieData
                                            {
                                                TypeName = "GeotechLayer",
                                                ComponentName = symbol,
                                                Space = "Underground",
                                                Category = "Soil"
                                            }
                                        };

                                        string jsonString = JsonConvert.SerializeObject(bimData, Formatting.None);
                                        
                                        // Gán dữ liệu vào các Parameter mặc định của Revit để người dùng nhìn thấy
                                        Parameter commentsParam = ds.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS);
                                        if (commentsParam != null && !commentsParam.IsReadOnly)
                                        {
                                            commentsParam.Set($"JSON Data: {jsonString}");
                                        }

                                        Parameter markParam = ds.get_Parameter(BuiltInParameter.ALL_MODEL_MARK);
                                        if (markParam != null && !markParam.IsReadOnly)
                                        {
                                            markParam.Set($"{bhName} - {symbol}");
                                        }

                                        count++;
                                    }
                                    
                                    trans.Commit();
                                    Autodesk.Revit.UI.TaskDialog.Show("Thành công", $"Đã tạo thành công {count} lớp địa chất 3D vào dự án Revit!");
                                }
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    Autodesk.Revit.UI.TaskDialog.Show("Lỗi", "Quá trình sinh mô hình gặp lỗi: " + ex.Message + "\n\n" + ex.StackTrace);
                    return Result.Failed;
                }
            }
            return Result.Succeeded;
        }
    }
}
