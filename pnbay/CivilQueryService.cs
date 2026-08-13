using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.Civil.ApplicationServices;
using Autodesk.Civil.DatabaseServices;
using CivilSurface = Autodesk.Civil.DatabaseServices.Surface;

namespace pnbay
{
    /// <summary>Bộ lọc tùy chọn theo giá trị số / vùng hình học cho các hàm QueryXxx.
    /// Mọi trường đều nullable — không set thì không lọc theo tiêu chí đó.</summary>
    public class QueryFilter
    {
        public double? MinElevation;
        public double? MaxElevation;
        public double? CenterX;
        public double? CenterY;
        public double? Radius;
        public double? MinArea;
        public double? MaxArea;
        public double? MinLength;
        public double? MaxLength;

        public bool PassElevation(double elev) =>
            (!MinElevation.HasValue || elev >= MinElevation.Value) &&
            (!MaxElevation.HasValue || elev <= MaxElevation.Value);

        public bool PassRadius(double x, double y) =>
            !(CenterX.HasValue && CenterY.HasValue && Radius.HasValue) ||
            Math.Sqrt(Math.Pow(x - CenterX.Value, 2) + Math.Pow(y - CenterY.Value, 2)) <= Radius.Value;

        public bool PassArea(double area) =>
            (!MinArea.HasValue || area >= MinArea.Value) &&
            (!MaxArea.HasValue || area <= MaxArea.Value);

        public bool PassLength(double length) =>
            (!MinLength.HasValue || length >= MinLength.Value) &&
            (!MaxLength.HasValue || length <= MaxLength.Value);
    }

    public static class CivilQueryService
    {
        public static CivilDocument GetCivilDocument(Document doc)
        {
            return CivilDocument.GetCivilDocument(doc.Database);
        }

        public static List<Dictionary<string, object>> QueryCogoPoints(Document doc, QueryFilter filter)
        {
            var rows = new List<Dictionary<string, object>>();
            var civilDoc = GetCivilDocument(doc);
            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
            {
                foreach (ObjectId id in civilDoc.CogoPoints)
                {
                    CogoPoint pt = tr.GetObject(id, OpenMode.ForRead) as CogoPoint;
                    if (pt == null) continue;
                    if (!filter.PassElevation(pt.Elevation)) continue;
                    if (!filter.PassRadius(pt.Easting, pt.Northing)) continue;

                    rows.Add(new Dictionary<string, object>
                    {
                        ["PointNumber"] = pt.PointNumber,
                        ["Easting"] = pt.Easting,
                        ["Northing"] = pt.Northing,
                        ["Elevation"] = pt.Elevation,
                        ["Description"] = pt.RawDescription ?? ""
                    });
                }
                tr.Commit();
            }
            return rows;
        }

        public static List<Dictionary<string, object>> QueryAlignments(Document doc, QueryFilter filter)
        {
            var rows = new List<Dictionary<string, object>>();
            var civilDoc = GetCivilDocument(doc);
            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
            {
                foreach (ObjectId id in civilDoc.GetAlignmentIds())
                {
                    Alignment al = tr.GetObject(id, OpenMode.ForRead) as Alignment;
                    if (al == null) continue;
                    if (!filter.PassLength(al.Length)) continue;

                    rows.Add(new Dictionary<string, object>
                    {
                        ["Name"] = al.Name,
                        ["Length"] = al.Length,
                        ["StartStation"] = al.StartingStation,
                        ["EndStation"] = al.EndingStation
                    });
                }
                tr.Commit();
            }
            return rows;
        }

        public static List<Dictionary<string, object>> QueryProfiles(Document doc, string alignmentName, QueryFilter filter)
        {
            var rows = new List<Dictionary<string, object>>();
            var civilDoc = GetCivilDocument(doc);
            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
            {
                foreach (ObjectId alId in civilDoc.GetAlignmentIds())
                {
                    Alignment al = tr.GetObject(alId, OpenMode.ForRead) as Alignment;
                    if (al == null) continue;
                    if (!string.IsNullOrEmpty(alignmentName) &&
                        !string.Equals(al.Name, alignmentName, StringComparison.OrdinalIgnoreCase))
                        continue;

                    foreach (ObjectId profId in al.GetProfileIds())
                    {
                        Profile prof = tr.GetObject(profId, OpenMode.ForRead) as Profile;
                        if (prof == null) continue;
                        if (!filter.PassElevation(prof.ElevationMax)) continue;
                        if (!filter.PassLength(prof.Length)) continue;

                        rows.Add(new Dictionary<string, object>
                        {
                            ["AlignmentName"] = al.Name,
                            ["ProfileName"] = prof.Name,
                            ["Length"] = prof.Length,
                            ["StartStation"] = prof.StartingStation,
                            ["EndStation"] = prof.EndingStation,
                            ["MinElevation"] = prof.ElevationMin,
                            ["MaxElevation"] = prof.ElevationMax
                        });
                    }
                }
                tr.Commit();
            }
            return rows;
        }

        public static List<Dictionary<string, object>> QuerySurfaces(Document doc, QueryFilter filter)
        {
            var rows = new List<Dictionary<string, object>>();
            var civilDoc = GetCivilDocument(doc);
            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
            {
                foreach (ObjectId id in civilDoc.GetSurfaceIds())
                {
                    CivilSurface surf = tr.GetObject(id, OpenMode.ForRead) as CivilSurface;
                    if (surf == null) continue;

                    var stats = surf.GetGeneralProperties();
                    // "Surface có cao độ > X" hiểu là điểm cao nhất của mặt đạt ngưỡng đó.
                    if (!filter.PassElevation(stats.MaximumElevation)) continue;

                    rows.Add(new Dictionary<string, object>
                    {
                        ["Name"] = surf.Name,
                        ["Description"] = surf.Description ?? "",
                        ["MinElevation"] = stats.MinimumElevation,
                        ["MaxElevation"] = stats.MaximumElevation,
                        ["MeanElevation"] = stats.MeanElevation,
                        ["NumberOfPoints"] = stats.NumberOfPoints
                    });
                }
                tr.Commit();
            }
            return rows;
        }

        public static List<Dictionary<string, object>> QueryCorridors(Document doc, QueryFilter filter)
        {
            var rows = new List<Dictionary<string, object>>();
            var civilDoc = GetCivilDocument(doc);
            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
            {
                foreach (ObjectId id in civilDoc.CorridorCollection)
                {
                    Corridor cor = tr.GetObject(id, OpenMode.ForRead) as Corridor;
                    if (cor == null) continue;
                    // Corridor không có tiêu chí số đơn giản để lọc — filter chỉ ảnh hưởng các loại khác.
                    rows.Add(new Dictionary<string, object>
                    {
                        ["Name"] = cor.Name,
                        ["Description"] = cor.Description ?? "",
                        ["BaselineCount"] = cor.Baselines.Count
                    });
                }
                tr.Commit();
            }
            return rows;
        }

        public static List<Dictionary<string, object>> QueryPipeNetworks(Document doc, QueryFilter filter)
        {
            var rows = new List<Dictionary<string, object>>();
            var civilDoc = GetCivilDocument(doc);
            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
            {
                foreach (ObjectId id in civilDoc.GetPipeNetworkIds())
                {
                    Network net = tr.GetObject(id, OpenMode.ForRead) as Network;
                    if (net == null) continue;
                    // PipeNetwork không có tiêu chí số đơn giản để lọc — filter chỉ ảnh hưởng các loại khác.
                    rows.Add(new Dictionary<string, object>
                    {
                        ["Name"] = net.Name,
                        ["Description"] = net.Description ?? "",
                        ["PipeCount"] = net.GetPipeIds().Count,
                        ["StructureCount"] = net.GetStructureIds().Count
                    });
                }
                tr.Commit();
            }
            return rows;
        }

        public static List<Dictionary<string, object>> QueryParcels(Document doc, QueryFilter filter)
        {
            var rows = new List<Dictionary<string, object>>();
            var civilDoc = GetCivilDocument(doc);
            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
            {
                foreach (ObjectId siteId in civilDoc.GetSiteIds())
                {
                    Site site = tr.GetObject(siteId, OpenMode.ForRead) as Site;
                    if (site == null) continue;
                    foreach (ObjectId parcelId in site.GetParcelIds())
                    {
                        Parcel parcel = tr.GetObject(parcelId, OpenMode.ForRead) as Parcel;
                        if (parcel == null) continue;
                        if (!filter.PassArea(parcel.Area)) continue;

                        rows.Add(new Dictionary<string, object>
                        {
                            ["SiteName"] = site.Name,
                            ["ParcelName"] = parcel.Name,
                            ["Number"] = parcel.Number,
                            ["Area"] = parcel.Area
                        });
                    }
                }
                tr.Commit();
            }
            return rows;
        }
    }
}
