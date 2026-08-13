using System;
using System.Collections.Generic;
using System.Text;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.EditorInput;
using Newtonsoft.Json.Linq;

namespace pnbay
{
    public class ActionParser
    {
        /// <summary>Thực thi 1 hoặc nhiều hành động từ JSON của LLM.
        /// Trả về chuỗi tóm tắt kết quả (để hiển thị trên chat panel), đồng thời vẫn ghi ra dòng lệnh AutoCAD.</summary>
        public static string ExecuteAction(Document doc, string jsonResponse)
        {
            Editor ed = doc.Editor;
            var resultText = new StringBuilder();
            try
            {
                // Tiền xử lý để đảm bảo LLM không nhét markdown code blocks vào JSON
                if (jsonResponse.StartsWith("```json")) jsonResponse = jsonResponse.Substring(7);
                if (jsonResponse.StartsWith("```")) jsonResponse = jsonResponse.Substring(3);
                if (jsonResponse.EndsWith("```")) jsonResponse = jsonResponse.Substring(0, jsonResponse.Length - 3);
                jsonResponse = jsonResponse.Trim();

                JToken root = JToken.Parse(jsonResponse);

                // Chấp nhận cả 1 object hành động đơn lẻ lẫn 1 mảng nhiều hành động.
                JArray actions;
                if (root is JArray arr)
                {
                    actions = arr;
                }
                else
                {
                    actions = new JArray(root);
                }

                using (DocumentLock docLock = doc.LockDocument())
                {
                    using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
                    {
                        BlockTable bt = (BlockTable)tr.GetObject(doc.Database.BlockTableId, OpenMode.ForRead);
                        BlockTableRecord btr = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

                        int successCount = 0;
                        foreach (JToken item in actions)
                        {
                            JObject json = item as JObject;
                            string action = json?["action"]?.ToString();
                            JToken parameters = json?["parameters"];

                            if (json == null || string.IsNullOrEmpty(action) || parameters == null)
                            {
                                ed.WriteMessage("\n[Lỗi] Một phần tử JSON không hợp lệ hoặc thiếu 'action', bỏ qua.\n");
                                continue;
                            }

                            if (action == "DrawLine")
                            {
                                double startX = parameters["startX"]?.Value<double>() ?? 0;
                                double startY = parameters["startY"]?.Value<double>() ?? 0;
                                double endX = parameters["endX"]?.Value<double>() ?? 0;
                                double endY = parameters["endY"]?.Value<double>() ?? 0;

                                using (Line line = new Line(new Point3d(startX, startY, 0), new Point3d(endX, endY, 0)))
                                {
                                    btr.AppendEntity(line);
                                    tr.AddNewlyCreatedDBObject(line, true);
                                }
                                string msg = $"Đã vẽ đường thẳng từ ({startX},{startY}) đến ({endX},{endY}).";
                                ed.WriteMessage($"\n[LLM] {msg}\n");
                                resultText.AppendLine(msg);
                                successCount++;
                            }
                            else if (action == "DrawCircle")
                            {
                                double x = parameters["x"]?.Value<double>() ?? 0;
                                double y = parameters["y"]?.Value<double>() ?? 0;
                                double radius = parameters["radius"]?.Value<double>() ?? 10;

                                using (Circle circle = new Circle())
                                {
                                    circle.Center = new Point3d(x, y, 0);
                                    circle.Radius = radius;
                                    circle.Normal = Vector3d.ZAxis;
                                    btr.AppendEntity(circle);
                                    tr.AddNewlyCreatedDBObject(circle, true);
                                }
                                string msg = $"Đã vẽ đường tròn tại ({x},{y}) bán kính {radius}.";
                                ed.WriteMessage($"\n[LLM] {msg}\n");
                                resultText.AppendLine(msg);
                                successCount++;
                            }
                            else if (action == "Query" || action == "ExportQuery")
                            {
                                string objectType = parameters["objectType"]?.ToString() ?? "";
                                string alignmentName = parameters["alignmentName"]?.ToString() ?? "";
                                var filter = ParseFilter(parameters["filter"]);

                                List<Dictionary<string, object>> rows = RunQuery(doc, objectType, alignmentName, filter);
                                if (rows == null)
                                {
                                    string err = $"objectType '{objectType}' không hợp lệ.";
                                    ed.WriteMessage($"\n[Lỗi] {err}\n");
                                    resultText.AppendLine(err);
                                    continue;
                                }

                                if (action == "Query")
                                {
                                    // Chỉ xem/hỏi — không ghi file, chỉ hiển thị tóm tắt kết quả.
                                    string summary = FormatRowsSummary(objectType, rows);
                                    ed.WriteMessage($"\n[LLM] {summary}\n");
                                    resultText.AppendLine(summary);
                                    successCount++;
                                }
                                else // ExportQuery — người dùng yêu cầu rõ ràng xuất ra file
                                {
                                    string format = parameters["format"]?.ToString() ?? "excel";
                                    string fileName = parameters["fileName"]?.ToString() ?? "";

                                    string outPath = ExportService.ResolveOutputPath(objectType, format, fileName);
                                    if (string.Equals(format, "docx", StringComparison.OrdinalIgnoreCase))
                                        ExportService.ExportToDocx(objectType, rows, outPath);
                                    else
                                        ExportService.ExportToExcel(objectType, rows, outPath);

                                    string msg = $"Đã xuất {rows.Count} dòng '{objectType}' ra: {outPath}";
                                    ed.WriteMessage($"\n[LLM] {msg}\n");
                                    resultText.AppendLine(msg);
                                    successCount++;
                                }
                            }
                            else
                            {
                                string msg = $"Hành động '{action}' chưa được hỗ trợ trong code hiện tại.";
                                ed.WriteMessage($"\n[Lỗi] {msg}\n");
                                resultText.AppendLine(msg);
                            }
                        }

                        tr.Commit();
                        ed.WriteMessage($"\n[LLM] Hoàn tất: {successCount}/{actions.Count} hành động đã thực hiện.\n");
                    }
                }
            }
            catch (Exception ex)
            {
                ed.WriteMessage($"\n[Exception] Lỗi khi xử lý phản hồi LLM: {ex.Message}\nChuỗi nhận được: {jsonResponse}\n");
                resultText.AppendLine($"Lỗi: {ex.Message}");
            }

            return resultText.ToString().TrimEnd();
        }

        private static QueryFilter ParseFilter(JToken filterToken)
        {
            var filter = new QueryFilter();
            if (filterToken != null && filterToken.Type == JTokenType.Object)
            {
                filter.MinElevation = filterToken["minElevation"]?.Value<double?>();
                filter.MaxElevation = filterToken["maxElevation"]?.Value<double?>();
                filter.CenterX = filterToken["centerX"]?.Value<double?>();
                filter.CenterY = filterToken["centerY"]?.Value<double?>();
                filter.Radius = filterToken["radius"]?.Value<double?>();
                filter.MinArea = filterToken["minArea"]?.Value<double?>();
                filter.MaxArea = filterToken["maxArea"]?.Value<double?>();
                filter.MinLength = filterToken["minLength"]?.Value<double?>();
                filter.MaxLength = filterToken["maxLength"]?.Value<double?>();
            }
            return filter;
        }

        private static List<Dictionary<string, object>> RunQuery(Document doc, string objectType, string alignmentName, QueryFilter filter)
        {
            switch (objectType)
            {
                case "CogoPoints":
                    return CivilQueryService.QueryCogoPoints(doc, filter);
                case "Alignments":
                    return CivilQueryService.QueryAlignments(doc, filter);
                case "Profiles":
                    return CivilQueryService.QueryProfiles(doc, alignmentName, filter);
                case "Surfaces":
                    return CivilQueryService.QuerySurfaces(doc, filter);
                case "Corridors":
                    return CivilQueryService.QueryCorridors(doc, filter);
                case "PipeNetworks":
                    return CivilQueryService.QueryPipeNetworks(doc, filter);
                case "Parcels":
                    return CivilQueryService.QueryParcels(doc, filter);
                default:
                    return null;
            }
        }

        private static string FormatRowsSummary(string objectType, List<Dictionary<string, object>> rows, int maxRows = 15)
        {
            if (rows.Count == 0)
                return $"Không tìm thấy '{objectType}' nào phù hợp.";

            var sb = new StringBuilder();
            sb.AppendLine($"Tìm thấy {rows.Count} '{objectType}':");
            int shown = Math.Min(rows.Count, maxRows);
            for (int i = 0; i < shown; i++)
            {
                var parts = new List<string>();
                foreach (var kv in rows[i])
                    parts.Add($"{kv.Key}={kv.Value}");
                sb.AppendLine($"  {i + 1}. {string.Join(", ", parts)}");
            }
            if (rows.Count > maxRows)
                sb.AppendLine($"  ... và {rows.Count - maxRows} dòng khác.");

            return sb.ToString().TrimEnd();
        }
    }
}
