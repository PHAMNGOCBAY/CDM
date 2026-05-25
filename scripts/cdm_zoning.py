"""
cdm_zoning.py — Phân vùng gia cố CDM theo 7 nguyên tắc P1-P7.

Tài liệu: 55-cdm-zoning-principles.md

Quy trình:
  1. Build feature vector 6D per HK: [H_soft, Cu, N_SPT, e0, Cc, S1]
  2. Standardize (z-score) → Ward hierarchical clustering → K clusters
  3. Delaunay triangulation 2D → edges cross-boundary
  4. Check P5 QC: ≥2 HK + ≥6 qu samples per cluster
  5. Check P7 gradient: |ΔS1/L| ≤ i_cp (0.5% KE/BXN, 0.2% NHC)
  6. Save to SQLite + return result dict

Public API:
  - build_features_for_zone(zone_code, db_path) → list[dict]
  - run_clustering(features, K, method='ward') → list[int] (cluster_id 1..K)
  - delaunay_edges(coords) → list[(i, j, distance_m)]
  - check_P5_qc(clusters_data) → list[dict]
  - check_P7_gradient(features, clusters, edges, icp_pct) → list[dict]
  - create_zoning_table(db_path)
  - save_clusters_to_db(zone_code, features, clusters, K, run_id, db_path)
"""
from __future__ import annotations

import math
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
_DB   = _ROOT / "data" / "TTHC.sqlite"

# Ngưỡng i_cp (% per m) theo zone
I_CP_BY_ZONE = {
    "KE":  0.5,
    "BXN": 0.5,
    "NHC": 0.2,
}

# K mặc định per zone (số cluster ban đầu)
K_DEFAULT_BY_ZONE = {
    "KE":  3,
    "BXN": 3,
    "NHC": 4,
}

# Symbols lớp yếu cho H_soft
SOFT_SYMBOLS_FOR_HSOFT = ("1", "1b", "2", "XMD")

# Symbols cho Ip (Bjerrum)
SOFT_SYMBOLS_FOR_IP = ("1", "1b", "CH", "MH", "CH-OH", "MH-OH")


def build_features_for_zone(
    zone_code: str,
    db_path: Optional[Path] = None,
    cdm_q_kPa: float = 40.8,
    cdm_a: float = 0.155,    # tỷ lệ thay thế mặc định
    cdm_Ec_kPa: float = 40000,
    pen_m: float = 1.0,
) -> list[dict]:
    """Tính feature vector 6D cho mọi HK của zone.

    Returns: [{bh_name, x, y, H_soft, Cu, N_spt, e0, Cc, S1, n_qu_samples}, ...]
    """
    _p = db_path or _DB
    try:
        from scripts.settlement_calc import bjerrum_mu
    except ImportError:
        bjerrum_mu = lambda ip: 1.0

    out = []
    with sqlite3.connect(_p) as con:
        con.row_factory = sqlite3.Row
        # Filter zone qua tên HK
        if zone_code == "KE":
            like = "KE-%"
        elif zone_code == "BXN":
            like = "BXN-%"
        elif zone_code == "NHC":
            like = "NHC-%"
        else:
            return []

        bhs = con.execute(f"""
            SELECT id, name, x_coord_m, y_coord_m, elevation_m
            FROM boreholes
            WHERE name LIKE ? AND x_coord_m IS NOT NULL AND y_coord_m IS NOT NULL
            ORDER BY name
        """, (like,)).fetchall()

        ph_h = ",".join("?" * len(SOFT_SYMBOLS_FOR_HSOFT))
        ph_ip = ",".join("?" * len(SOFT_SYMBOLS_FOR_IP))

        for b in bhs:
            # H_soft từ layers
            r = con.execute(f"""
                SELECT COALESCE(SUM(depth_bot_m - depth_top_m), 0.0)
                FROM layers WHERE borehole_id = ?
                  AND symbol IN ({ph_h})
            """, (b["id"], *SOFT_SYMBOLS_FOR_HSOFT)).fetchone()
            H_soft = float(r[0]) if r and r[0] else 0.0

            # Su từ VST trong phạm vi lớp yếu
            r2 = con.execute("""
                SELECT AVG(v.Su_kPa)
                FROM vane_shear_tests v
                JOIN vst_locations vl ON v.vst_loc_id = vl.id
                WHERE vl.name = ? AND v.Su_kPa > 0 AND v.depth_m <= ?
            """, (b["name"], max(H_soft, 1))).fetchone()
            Su = float(r2[0]) if r2 and r2[0] else None

            # Ip TB cho Bjerrum
            r3 = con.execute(f"""
                SELECT AVG(Ip)
                FROM lab_tests
                WHERE borehole_id = ? AND Ip IS NOT NULL AND Ip > 0
                  AND symbol_tcvn IN ({ph_ip})
            """, (b["id"], *SOFT_SYMBOLS_FOR_IP)).fetchone()
            Ip = float(r3[0]) if r3 and r3[0] else None
            mu = bjerrum_mu(Ip) if Ip else 1.0
            Cu = (Su * mu) if Su else None

            # N SPT trung bình trong phạm vi lớp yếu
            r4 = con.execute("""
                SELECT AVG(N) FROM spt_values
                WHERE borehole_id = ? AND depth_m <= ? AND N IS NOT NULL AND N > 0
            """, (b["id"], max(H_soft, 1))).fetchone()
            N_spt = float(r4[0]) if r4 and r4[0] else None

            # e0 + Cc TB từ lab_tests
            r5 = con.execute(f"""
                SELECT AVG(e0), AVG(Cc)
                FROM lab_tests
                WHERE borehole_id = ?
                  AND symbol_tcvn IN ({ph_ip})
                  AND e0 > 0
            """, (b["id"], *SOFT_SYMBOLS_FOR_IP)).fetchone()
            e0 = float(r5[0]) if r5 and r5[0] else None
            Cc = float(r5[1]) if r5 and r5[1] else None

            # S1 = q*H/(a*Ec + (1-a)*Es), Es = 250*Cu
            if Cu and H_soft > 0:
                Es = 250.0 * Cu
                Ecomp = cdm_a * cdm_Ec_kPa + (1.0 - cdm_a) * Es
                S1 = cdm_q_kPa * H_soft / Ecomp * 100  # cm
            else:
                S1 = None

            # cdm_lab_results chỉ có zone_code (không per HK) — đếm zone-level ở P5
            n_qu = 0

            out.append({
                "bh_name":  b["name"],
                "x":        float(b["x_coord_m"]),
                "y":        float(b["y_coord_m"]),
                "elev":     float(b["elevation_m"] or 0),
                "H_soft":   round(H_soft, 2),
                "Cu":       round(Cu, 2) if Cu is not None else None,
                "N_spt":    round(N_spt, 1) if N_spt is not None else None,
                "e0":       round(e0, 3) if e0 is not None else None,
                "Cc":       round(Cc, 3) if Cc is not None else None,
                "S1":       round(S1, 1) if S1 is not None else None,
                "n_qu":     int(n_qu),
            })

    return out


def _table_exists(con, name: str) -> bool:
    r = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,)
    ).fetchone()
    return r is not None


def run_clustering(features: list[dict], K: int) -> list[int]:
    """Ward hierarchical clustering trên feature vector 6D đã chuẩn hóa.

    Returns: list[int] cluster_id 1..K (cùng thứ tự với features).
    HK thiếu feature → fill mean trước khi cluster.
    """
    if not features or K < 2:
        return [1] * len(features)
    try:
        import numpy as np
        from scipy.cluster.hierarchy import linkage, fcluster
        from sklearn.preprocessing import StandardScaler
    except ImportError as e:
        raise ImportError(f"Cần scipy + scikit-learn: {e}")

    keys = ["H_soft", "Cu", "N_spt", "e0", "Cc", "S1"]
    X = np.array([
        [f.get(k) if f.get(k) is not None else np.nan for k in keys]
        for f in features
    ], dtype=float)

    # Fill NaN với column mean
    col_mean = np.nanmean(X, axis=0)
    for j in range(X.shape[1]):
        if np.isnan(col_mean[j]):
            col_mean[j] = 0.0
        nan_mask = np.isnan(X[:, j])
        X[nan_mask, j] = col_mean[j]

    # Standardize
    Xs = StandardScaler().fit_transform(X)

    # Ward linkage
    Z = linkage(Xs, method="ward")
    K = min(K, len(features))
    if K < 2:
        return [1] * len(features)
    labels = fcluster(Z, t=K, criterion="maxclust")
    return [int(l) for l in labels]


def delaunay_edges(coords: list[tuple[float, float]]) -> list[tuple[int, int, float]]:
    """Delaunay triangulation 2D → unique edges.

    Args:
        coords: [(x1,y1), (x2,y2), ...]

    Returns:
        [(i, j, L_m), ...] với i<j, L_m = Euclidean distance
    """
    if len(coords) < 3:
        return []
    try:
        import numpy as np
        from scipy.spatial import Delaunay
    except ImportError:
        return []

    pts = np.array(coords)
    try:
        tri = Delaunay(pts)
    except Exception:
        return []

    edges = set()
    for simplex in tri.simplices:
        for k in range(3):
            i, j = simplex[k], simplex[(k + 1) % 3]
            if i > j:
                i, j = j, i
            edges.add((int(i), int(j)))

    out = []
    for i, j in edges:
        dx = pts[i, 0] - pts[j, 0]
        dy = pts[i, 1] - pts[j, 1]
        L = math.hypot(dx, dy)
        out.append((i, j, round(L, 2)))
    return sorted(out)


def get_qu_samples_for_zone(zone_code: str, db_path: Optional[Path] = None) -> int:
    """Tổng số mẫu qu thí nghiệm CDM cho cả zone (cdm_lab_results)."""
    _p = db_path or _DB
    with sqlite3.connect(_p) as con:
        if not _table_exists(con, "cdm_lab_results"):
            return 0
        r = con.execute("""
            SELECT COUNT(*) FROM cdm_lab_results
            WHERE UPPER(zone_code) = UPPER(?)
        """, (zone_code,)).fetchone()
        return int(r[0]) if r else 0


def check_P5_qc(features: list[dict], clusters: list[int],
                zone_code: str = "",
                min_hk: int = 2, min_qu: int = 6,
                db_path: Optional[Path] = None) -> list[dict]:
    """P5: kiểm tra QC mỗi cluster có ≥2 HK + ≥6 mẫu qu.

    Số mẫu qu (cdm_lab_results) chỉ có ở zone-level → pro-rata theo số HK
    trong cluster vs tổng HK của zone.

    Returns: [{cluster_id, n_hk, n_qu_total, pass_hk, pass_qu, pass_all}, ...]
    """
    from collections import defaultdict
    by_cluster = defaultdict(lambda: {"n_hk": 0})
    for c in clusters:
        by_cluster[c]["n_hk"] += 1

    # Lấy tổng số qu samples cho zone
    n_qu_zone = get_qu_samples_for_zone(zone_code, db_path) if zone_code else 0
    n_hk_total = len(features) or 1

    out = []
    for cid in sorted(by_cluster.keys()):
        n_hk = by_cluster[cid]["n_hk"]
        # Pro-rata: chia số mẫu qu zone theo tỷ lệ HK trong cluster
        n_qu = int(round(n_qu_zone * n_hk / n_hk_total))
        pass_hk = n_hk >= min_hk
        pass_qu = n_qu >= min_qu
        out.append({
            "cluster_id": int(cid),
            "n_hk":       int(n_hk),
            "n_qu_total": int(n_qu),
            "pass_hk":    bool(pass_hk),
            "pass_qu":    bool(pass_qu),
            "pass_all":   bool(pass_hk and pass_qu),
            "min_hk":     int(min_hk),
            "min_qu":     int(min_qu),
        })
    return out


def check_P7_gradient(features: list[dict], clusters: list[int],
                      edges: list[tuple[int, int, float]],
                      icp_pct: float = 0.5) -> list[dict]:
    """P7: kiểm tra gradient |ΔS1|/L ≤ i_cp cho mọi cặp cross-boundary.

    Args:
        icp_pct: ngưỡng % per m (0.5 cho KE/BXN, 0.2 cho NHC)

    Returns: [{i, j, bh_i, bh_j, cluster_i, cluster_j, cross_zone,
               S1_a, S1_b, L_m, grad_pct, pass}, ...]
    """
    out = []
    for i, j, L_m in edges:
        if i >= len(features) or j >= len(features):
            continue
        cross_zone = (clusters[i] != clusters[j])
        S1_a = features[i].get("S1")
        S1_b = features[j].get("S1")
        if S1_a is None or S1_b is None or L_m <= 0:
            grad = None
            pass_grad = None
        else:
            # ΔS1 (cm) / L (m) * 100 → % per m
            grad = abs(S1_a - S1_b) / (100.0 * L_m) * 100
            pass_grad = grad <= icp_pct
        out.append({
            "i":          int(i),
            "j":          int(j),
            "bh_i":       features[i]["bh_name"],
            "bh_j":       features[j]["bh_name"],
            "cluster_i":  int(clusters[i]),
            "cluster_j":  int(clusters[j]),
            "cross_zone": bool(cross_zone),
            "S1_a_cm":    S1_a,
            "S1_b_cm":    S1_b,
            "L_m":        float(L_m),
            "grad_pct":   round(grad, 3) if grad is not None else None,
            "pass":       pass_grad,
        })
    return out


def create_zoning_table(db_path: Optional[Path] = None) -> None:
    """Tạo bảng cdm_zoning_clusters (idempotent)."""
    _p = db_path or _DB
    with sqlite3.connect(_p) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS cdm_zoning_clusters (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                bh_name     TEXT NOT NULL,
                zone        TEXT NOT NULL,
                cluster_id  INTEGER NOT NULL,
                K           INTEGER NOT NULL,
                H_soft_m    REAL,
                Cu_kPa      REAL,
                N_spt       REAL,
                e0          REAL,
                Cc          REAL,
                S1_cm       REAL,
                x_coord_m   REAL,
                y_coord_m   REAL,
                run_id      TEXT NOT NULL,
                ts          TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE (bh_name, run_id)
            )
        """)
        con.commit()


def save_clusters_to_db(
    zone_code: str,
    features: list[dict],
    clusters: list[int],
    K: int,
    run_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> str:
    """Lưu kết quả clustering vào SQLite. Trả về run_id."""
    _p = db_path or _DB
    create_zoning_table(_p)
    rid = run_id or uuid.uuid4().hex[:12]
    with sqlite3.connect(_p) as con:
        for f, c in zip(features, clusters):
            con.execute("""
                INSERT INTO cdm_zoning_clusters
                    (bh_name, zone, cluster_id, K, H_soft_m, Cu_kPa, N_spt,
                     e0, Cc, S1_cm, x_coord_m, y_coord_m, run_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (bh_name, run_id) DO UPDATE SET
                    cluster_id = excluded.cluster_id,
                    K = excluded.K, H_soft_m = excluded.H_soft_m,
                    Cu_kPa = excluded.Cu_kPa, N_spt = excluded.N_spt,
                    e0 = excluded.e0, Cc = excluded.Cc, S1_cm = excluded.S1_cm,
                    ts = datetime('now','localtime')
            """, (f["bh_name"], zone_code, int(c), int(K),
                  f["H_soft"], f["Cu"], f["N_spt"], f["e0"], f["Cc"], f["S1"],
                  f["x"], f["y"], rid))
        con.commit()
    return rid


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    for zone in ("KE", "BXN", "NHC"):
        print(f"\n=== Zone {zone} ===")
        feats = build_features_for_zone(zone)
        print(f"  HK: {len(feats)}")
        if not feats:
            continue
        for f in feats[:3]:
            print(f"  {f['bh_name']:14s}  H_soft={f['H_soft']:5.1f}  "
                  f"Cu={f['Cu']}  S1={f['S1']}")
        K = K_DEFAULT_BY_ZONE[zone]
        clusters = run_clustering(feats, K=K)
        print(f"  Clusters K={K}: {sorted(set(clusters))}")
        coords = [(f["x"], f["y"]) for f in feats]
        edges = delaunay_edges(coords)
        print(f"  Delaunay edges: {len(edges)}")
        p5 = check_P5_qc(feats, clusters, zone_code=zone)
        for r in p5:
            print(f"  P5 cluster {r['cluster_id']}: HK={r['n_hk']} qu={r['n_qu_total']}  pass={r['pass_all']}")
        icp = I_CP_BY_ZONE[zone]
        p7 = check_P7_gradient(feats, clusters, edges, icp_pct=icp)
        n_cross = sum(1 for r in p7 if r["cross_zone"])
        n_fail  = sum(1 for r in p7 if r["cross_zone"] and r["pass"] is False)
        print(f"  P7 i_cp={icp}%: {n_cross} cross-boundary edges, {n_fail} fail")
        rid = save_clusters_to_db(zone, feats, clusters, K)
        print(f"  Saved to SQLite run_id={rid}")
