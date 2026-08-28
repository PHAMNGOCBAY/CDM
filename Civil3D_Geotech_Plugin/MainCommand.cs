using System;
using System.IO;
using System.Windows.Forms;
using System.Data.SQLite;
using System.Collections.Generic;
using Newtonsoft.Json;
using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.EditorInput;
using System.Linq;

[assembly: CommandClass(typeof(Civil3DGeotechPlugin.MainCommand))]

namespace Civil3DGeotechPlugin
{
    // Cấu trúc dữ liệu chuẩn BIM
    public class GeotechData
    {
        public string LayerSymbol { get; set; }
        public string Description { get; set; }
        public double TopDepth { get; set; }
        public double BottomDepth { get; set; }
        public double Thickness { get; set; }
        // Các chỉ tiêu cơ lý (có thể trích từ bảng lab_tests)
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

    public class BIMElementModel
    {
        public string BoreholeName { get; set; }
        public GeotechData Geology { get; set; }
        public AIMAsset AIM { get; set; }
        public COBieData COBie { get; set; }
    }

    public class LayerData
    {
        public string BhName { get; set; }
        public double X { get; set; }
        public double Y { get; set; }
        public double Elev { get; set; }
        public string Symbol { get; set; }
        public double Top { get; set; }
        public double Bot { get; set; }
        public double Thickness { get; set; }
    }

    public class MainCommand
    {
        private double GetSafeDouble(SQLiteDataReader reader, string colName)
        {
            object val = reader[colName];
            if (val == DBNull.Value || val == null) return 0.0;
            try { return Convert.ToDouble(val); } catch { return 0.0; }
        }

        private string GetSafeString(SQLiteDataReader reader, string colName)
        {
            object val = reader[colName];
            if (val == DBNull.Value || val == null) return "";
            return val.ToString();
        }

        [CommandMethod("BIMdiachat")]
        public void BIMdiachat()
        {
            Document doc = Autodesk.AutoCAD.ApplicationServices.Application.DocumentManager.MdiActiveDocument;
            Database db = doc.Database;
            Editor ed = doc.Editor;

            // 1. Hiển thị hộp thoại chọn file SQLite
            string dbPath = "";
            using (OpenFileDialog openFileDialog = new OpenFileDialog())
            {
                openFileDialog.Filter = "SQLite Database (*.sqlite;*.db)|*.sqlite;*.db|All files (*.*)|*.*";
                openFileDialog.Title = "Chọn file dữ liệu địa chất SQLite";
                openFileDialog.InitialDirectory = @"G:\My Drive\AI-SUC TAI COC THEO DAT NEN\data";

                if (openFileDialog.ShowDialog() == DialogResult.OK)
                {
                    dbPath = openFileDialog.FileName;
                }
                else
                {
                    ed.WriteMessage("\nĐã hủy chọn file.");
                    return;
                }
            }

            ed.WriteMessage($"\nĐang đọc dữ liệu từ: {dbPath}");

            string connectionString = $"Data Source={dbPath};Version=3;";
            
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                try
                {
                    BlockTable bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                    BlockTableRecord btr = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

                    int layerCount = 0;
                    string lastBorehole = "";
                    
                    List<LayerData> allLayers = new List<LayerData>();

                    using (SQLiteConnection conn = new SQLiteConnection(connectionString))
                    {
                        conn.Open();
                        
                        // Lấy dữ liệu cơ lý mẫu (Trong thực tế bạn có thể JOIN với bảng lab_tests)
                        // Do cấu trúc phức tạp, ta sẽ truy vấn các lớp đất trước
                        string sql = @"
                            SELECT b.id as bh_id, b.name as bh_name, b.x_coord_m, b.y_coord_m, b.elevation_m, 
                                   l.id as layer_id, l.symbol, l.description, l.depth_top_m, l.depth_bot_m, l.thickness_m 
                            FROM layers l
                            JOIN boreholes b ON l.borehole_id = b.id
                            WHERE b.x_coord_m IS NOT NULL
                            ORDER BY b.name, l.depth_top_m";

                        using (SQLiteCommand cmd = new SQLiteCommand(sql, conn))
                        {
                            using (SQLiteDataReader reader = cmd.ExecuteReader())
                            {
                                while (reader.Read())
                                {
                                    string bhName = GetSafeString(reader, "bh_name");
                                    string bhId = GetSafeString(reader, "bh_id");
                                    string layerId = GetSafeString(reader, "layer_id");
                                    double x = GetSafeDouble(reader, "x_coord_m");
                                    double y = GetSafeDouble(reader, "y_coord_m");
                                    double elev = GetSafeDouble(reader, "elevation_m");
                                    
                                    string symbol = GetSafeString(reader, "symbol");
                                    string desc = GetSafeString(reader, "description");
                                    double top = GetSafeDouble(reader, "depth_top_m");
                                    double bot = GetSafeDouble(reader, "depth_bot_m");
                                    double thickness = GetSafeDouble(reader, "thickness_m");

                                    if (thickness <= 0) continue;
                                    
                                    allLayers.Add(new LayerData {
                                        BhName = bhName, X = x, Y = y, Elev = elev,
                                        Symbol = symbol, Top = top, Bot = bot, Thickness = thickness
                                    });

                                    if (bhName != lastBorehole)
                                    {
                                        Point3d textPt = new Point3d(x, y, elev + 1.0);
                                        DBText text = new DBText();
                                        text.Position = textPt;
                                        text.TextString = bhName;
                                        text.Height = 2.0;
                                        btr.AppendEntity(text);
                                        tr.AddNewlyCreatedDBObject(text, true);
                                        lastBorehole = bhName;
                                    }

                                    // Vẽ khối Cylinder
                                    Solid3d cylinder = new Solid3d();
                                    double radius = 1.0; 
                                    cylinder.CreateFrustum(thickness, radius, radius, radius);

                                    // Tạo Block vô danh (*U) cho từng khối trụ để gắn Attributes
                                    BlockTableRecord btrAnon = new BlockTableRecord();
                                    btrAnon.Name = "*U";
                                    ObjectId btrAnonId = bt.Add(btrAnon);
                                    tr.AddNewlyCreatedDBObject(btrAnon, true);

                                    short colorIndex = (short)((Math.Abs(symbol.GetHashCode()) % 254) + 1);
                                    cylinder.ColorIndex = colorIndex;

                                    btrAnon.AppendEntity(cylinder);
                                    tr.AddNewlyCreatedDBObject(cylinder, true);

                                    // Tạo Attribute Definitions (ẩn)
                                    string[] tags = { "BOREHOLE", "LAYER", "TOP_DEPTH", "BOTTOM_DEPTH", "BIM_JSON" };
                                    List<ObjectId> attDefIds = new List<ObjectId>();
                                    foreach (string tag in tags)
                                    {
                                        AttributeDefinition ad = new AttributeDefinition();
                                        ad.Position = Point3d.Origin;
                                        ad.Tag = tag;
                                        ad.Invisible = true; // Ẩn khỏi bản vẽ 3D
                                        btrAnon.AppendEntity(ad);
                                        tr.AddNewlyCreatedDBObject(ad, true);
                                        attDefIds.Add(ad.ObjectId);
                                    }

                                    // Tạo Block Reference
                                    double zCenter = elev - top - (thickness / 2.0);
                                    Vector3d translation = new Vector3d(x, y, zCenter);
                                    BlockReference br = new BlockReference(new Point3d(x, y, zCenter), btrAnonId);
                                    btr.AppendEntity(br);
                                    tr.AddNewlyCreatedDBObject(br, true);

                                    // 1. Tạo cấu trúc dữ liệu BIM
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
                                    string jsonString = JsonConvert.SerializeObject(bimData, Formatting.None); // Dùng None để thu gọn một dòng

                                    string[] values = { bhName, symbol, top.ToString("F2"), bot.ToString("F2"), jsonString };
                                    
                                    // Gắn giá trị AttributeReference vào BlockReference
                                    for (int i = 0; i < tags.Length; i++)
                                    {
                                        AttributeDefinition ad = (AttributeDefinition)tr.GetObject(attDefIds[i], OpenMode.ForRead);
                                        AttributeReference ar = new AttributeReference();
                                        ar.SetAttributeFromBlock(ad, br.BlockTransform);
                                        ar.TextString = values[i];
                                        br.AttributeCollection.AppendAttribute(ar);
                                        tr.AddNewlyCreatedDBObject(ar, true);
                                    }

                                    layerCount++;
                                }
                            }
                        }
                    }
                    
                    // --- VẼ TRẮC DỌC ĐỊA CHẤT 2D (2D PROFILE) ---
                    Draw2DProfile(btr, tr, allLayers, ed);

                    tr.Commit();
                    
                    // Zoom Extents
                    try
                    {
                        dynamic acadApp = Autodesk.AutoCAD.ApplicationServices.Application.AcadApplication;
                        acadApp.ZoomExtents();
                    }
                    catch { }

                    ed.WriteMessage($"\nThành công! Đã chạy lệnh BIMdiachat: vẽ {layerCount} lớp địa tầng chuẩn BIM và tạo Trắc dọc 2D.");
                }
                catch (System.Exception ex)
                {
                    ed.WriteMessage("\nLỗi tạo mô hình 3D chi tiết: " + ex.ToString());
                    tr.Abort();
                }
            }
        }
        
        private void Draw2DProfile(BlockTableRecord btr, Transaction tr, List<LayerData> layers, Editor ed)
        {
            if (layers.Count == 0) return;

            ed.WriteMessage("\nĐang tạo trắc dọc 2D...");
            
            // Nhóm theo tên hố khoan và sắp xếp theo tọa độ X
            var boreholes = layers.GroupBy(l => l.BhName).OrderBy(g => g.First().X).ToList();
            
            // Gốc tọa độ cho mặt cắt 2D (Offset Y = -100 để không đè lên 3D)
            double profileYOffset = -100.0;
            double verticalExaggeration = 5.0; // Phóng đại chiều cao lên 5 lần để dễ nhìn
            
            double currentX2D = 0.0;
            
            for (int i = 0; i < boreholes.Count; i++)
            {
                var bhLayers = boreholes[i].OrderBy(l => l.Top).ToList();
                var firstLayer = bhLayers.First();
                
                // Vẽ tên hố khoan trên trắc dọc
                DBText txt = new DBText();
                txt.Position = new Point3d(currentX2D, profileYOffset + (firstLayer.Elev * verticalExaggeration) + 5.0, 0);
                txt.TextString = firstLayer.BhName;
                txt.Height = 2.0;
                btr.AppendEntity(txt);
                tr.AddNewlyCreatedDBObject(txt, true);
                
                // Vẽ các lớp đất dưới dạng Polyline 2D (Rectangles)
                foreach (var layer in bhLayers)
                {
                    double yTop = profileYOffset + ((layer.Elev - layer.Top) * verticalExaggeration);
                    double yBot = profileYOffset + ((layer.Elev - layer.Bot) * verticalExaggeration);
                    double width = 5.0; // Bề rộng cột hố khoan 2D
                    
                    Polyline pl = new Polyline();
                    pl.AddVertexAt(0, new Point2d(currentX2D - width/2, yTop), 0, 0, 0);
                    pl.AddVertexAt(1, new Point2d(currentX2D + width/2, yTop), 0, 0, 0);
                    pl.AddVertexAt(2, new Point2d(currentX2D + width/2, yBot), 0, 0, 0);
                    pl.AddVertexAt(3, new Point2d(currentX2D - width/2, yBot), 0, 0, 0);
                    pl.Closed = true;
                    
                    short colorIndex = (short)((Math.Abs(layer.Symbol.GetHashCode()) % 254) + 1);
                    pl.ColorIndex = colorIndex;
                    
                    btr.AppendEntity(pl);
                    tr.AddNewlyCreatedDBObject(pl, true);
                }
                
                // Nối đường ranh giới các lớp đất giữa hố này và hố kế tiếp
                if (i < boreholes.Count - 1)
                {
                    var nextBhLayers = boreholes[i + 1].OrderBy(l => l.Top).ToList();
                    double nextX2D = currentX2D + 30.0; // Khoảng cách giả định giữa các hố khoan trên trắc dọc
                    
                    // Nối mặt đất
                    Line groundLine = new Line(
                        new Point3d(currentX2D + 2.5, profileYOffset + (firstLayer.Elev * verticalExaggeration), 0),
                        new Point3d(nextX2D - 2.5, profileYOffset + (nextBhLayers.First().Elev * verticalExaggeration), 0)
                    );
                    groundLine.ColorIndex = 3;
                    btr.AppendEntity(groundLine);
                    tr.AddNewlyCreatedDBObject(groundLine, true);
                    
                    // Thử nối các đáy lớp có cùng Symbol
                    foreach (var layer in bhLayers)
                    {
                        var matchingNextLayer = nextBhLayers.FirstOrDefault(l => l.Symbol == layer.Symbol);
                        if (matchingNextLayer != null)
                        {
                            Line boundaryLine = new Line(
                                new Point3d(currentX2D + 2.5, profileYOffset + ((layer.Elev - layer.Bot) * verticalExaggeration), 0),
                                new Point3d(nextX2D - 2.5, profileYOffset + ((matchingNextLayer.Elev - matchingNextLayer.Bot) * verticalExaggeration), 0)
                            );
                            boundaryLine.ColorIndex = 8; // Màu xám cho đường nối
                            btr.AppendEntity(boundaryLine);
                            tr.AddNewlyCreatedDBObject(boundaryLine, true);
                            
                            // Vẽ 3D Face nối bề mặt các lớp (Yêu cầu "vẽ bề mặt cắt lớp địa chất")
                            // 4 điểm: Top của layer hiện tại và layer tiếp theo
                            Face f = new Face();
                            f.SetVertexAt(0, new Point3d(layer.X, layer.Y, layer.Elev - layer.Top));
                            f.SetVertexAt(1, new Point3d(layer.X, layer.Y, layer.Elev - layer.Bot));
                            f.SetVertexAt(2, new Point3d(matchingNextLayer.X, matchingNextLayer.Y, matchingNextLayer.Elev - matchingNextLayer.Bot));
                            f.SetVertexAt(3, new Point3d(matchingNextLayer.X, matchingNextLayer.Y, matchingNextLayer.Elev - matchingNextLayer.Top));
                            
                            short colorIndex = (short)((Math.Abs(layer.Symbol.GetHashCode()) % 254) + 1);
                            f.ColorIndex = colorIndex;
                            btr.AppendEntity(f);
                            tr.AddNewlyCreatedDBObject(f, true);
                        }
                    }
                }
                
                currentX2D += 30.0; // Di chuyển sang hố kế tiếp
            }
        }
    }
}
