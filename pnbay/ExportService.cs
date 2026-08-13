using System;
using System.Collections.Generic;
using System.IO;
using ClosedXML.Excel;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;

namespace pnbay
{
    public static class ExportService
    {
        public static string ResolveOutputPath(string objectType, string format, string userFileName)
        {
            string dir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "pnbay_exports");
            if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);

            string ext = string.Equals(format, "docx", StringComparison.OrdinalIgnoreCase) ? ".docx" : ".xlsx";

            string fileName;
            if (!string.IsNullOrWhiteSpace(userFileName))
            {
                fileName = Path.GetFileNameWithoutExtension(userFileName) + ext;
            }
            else
            {
                fileName = $"{objectType}_{DateTime.Now:yyyyMMdd_HHmmss}{ext}";
            }

            return Path.Combine(dir, fileName);
        }

        public static string ExportToExcel(string title, List<Dictionary<string, object>> rows, string filePath)
        {
            using (var wb = new XLWorkbook())
            {
                var ws = wb.Worksheets.Add(string.IsNullOrWhiteSpace(title) ? "Data" : title);

                if (rows.Count == 0)
                {
                    ws.Cell(1, 1).Value = "Không có dữ liệu.";
                }
                else
                {
                    var headers = new List<string>(rows[0].Keys);
                    for (int c = 0; c < headers.Count; c++)
                    {
                        var cell = ws.Cell(1, c + 1);
                        cell.Value = headers[c];
                        cell.Style.Font.Bold = true;
                    }

                    for (int r = 0; r < rows.Count; r++)
                    {
                        for (int c = 0; c < headers.Count; c++)
                        {
                            object val = rows[r].ContainsKey(headers[c]) ? rows[r][headers[c]] : null;
                            ws.Cell(r + 2, c + 1).Value = val?.ToString() ?? "";
                        }
                    }

                    ws.Columns().AdjustToContents();
                }

                wb.SaveAs(filePath);
            }
            return filePath;
        }

        public static string ExportToDocx(string title, List<Dictionary<string, object>> rows, string filePath)
        {
            using (WordprocessingDocument wordDoc = WordprocessingDocument.Create(filePath, DocumentFormat.OpenXml.WordprocessingDocumentType.Document))
            {
                MainDocumentPart mainPart = wordDoc.AddMainDocumentPart();
                mainPart.Document = new Document();
                Body body = new Body();

                Paragraph titlePara = new Paragraph(
                    new Run(new RunProperties(new Bold()), new Text(title ?? "Kết quả truy vấn Civil 3D")));
                body.Append(titlePara);

                if (rows.Count == 0)
                {
                    body.Append(new Paragraph(new Run(new Text("Không có dữ liệu."))));
                }
                else
                {
                    Table table = new Table();

                    TableProperties tblProp = new TableProperties(
                        new TableBorders(
                            new TopBorder { Val = BorderValues.Single, Size = 6 },
                            new BottomBorder { Val = BorderValues.Single, Size = 6 },
                            new LeftBorder { Val = BorderValues.Single, Size = 6 },
                            new RightBorder { Val = BorderValues.Single, Size = 6 },
                            new InsideHorizontalBorder { Val = BorderValues.Single, Size = 6 },
                            new InsideVerticalBorder { Val = BorderValues.Single, Size = 6 }
                        ));
                    table.AppendChild(tblProp);

                    var headers = new List<string>(rows[0].Keys);

                    TableRow headerRow = new TableRow();
                    foreach (var h in headers)
                    {
                        headerRow.Append(new TableCell(new Paragraph(new Run(
                            new RunProperties(new Bold()), new Text(h)))));
                    }
                    table.Append(headerRow);

                    foreach (var row in rows)
                    {
                        TableRow tr = new TableRow();
                        foreach (var h in headers)
                        {
                            object val = row.ContainsKey(h) ? row[h] : null;
                            tr.Append(new TableCell(new Paragraph(new Run(new Text(val?.ToString() ?? "")))));
                        }
                        table.Append(tr);
                    }

                    body.Append(table);
                }

                mainPart.Document.Append(body);
                mainPart.Document.Save();
            }
            return filePath;
        }
    }
}
