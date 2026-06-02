"""
qtt_dxf_import.py — Import HK QTT (ND-XX) từ DXF gốc, cập nhật JSON + SQLite.

Hỗ trợ:
  - 1 file đơn:   python qtt_dxf_import.py "G:\\...\\QTT-HO KHOAN ND02.dxf"
  - Batch dir:    python qtt_dxf_import.py "G:\\...\\7. QUANG TRUONG TRUNG TAM"
  - Mặc định:     scan thư mục QTT cho mọi QTT-HO KHOAN ND*.dxf

Lưu vào:
  - data/qtt_ndXX_borehole.json (snapshot per HK)
  - SQLite tables: boreholes, layers, spt_values, tvtk_bh_cdm
  - 2 DB: LOCAL + PROJECT

Convention SPT QTT: N = N2 + N3 (ASTM standard, 4 cột x=154/159/164/169)
"""
from __future__ import annotations
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import ezdxf

_ROOT = Path(__file__).resolve().parent.parent
DXF_ROOT = Path(r"G:\My Drive\202605-TRUNG TAM HCM\DIA CHAT"
                 r"\7. QUANG TRUONG TRUNG TAM")
DB_LOCAL = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
DB_PROJ = _ROOT / "data" / "TTHC.sqlite"

SOFT_SYMBOLS = {"1", "1b", "2", "XMD"}


def extract_qtt_from_dxf(dxf_path: Path, bh_name: str | None = None) -> dict:
    """Trích thông tin 1 HK QTT từ DXF. bh_name auto-detect từ filename."""
    if bh_name is None:
        m = re.search(r"ND(\d+)", dxf_path.name, re.IGNORECASE)
        if m:
            bh_name = f"ND-{m.group(1)}"
        else:
            raise ValueError(f"Không suy được tên HK từ filename: {dxf_path.name}")

    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    texts = [(e.dxf.text, e.dxf.insert.x, e.dxf.insert.y)
              for e in msp.query("TEXT")]
    mtexts = [(e.text, e.dxf.insert.x, e.dxf.insert.y)
               for e in msp.query("MTEXT")]

    # ─── HEADER — pattern-based detection (template QTT có 2 biến thể) ───
    # Pattern phổ biến: 1 số 7 chữ số ~119xxxx (Northing), 1 số 6 chữ số ~605xxx (Easting),
    # 1 số ngắn ~1-5 m (elevation), 1 số ~20-40 m (total depth)
    def parse_num(s: str) -> float | None:
        s = s.strip().replace(",", ".").replace(" m", "")
        try:
            return float(s)
        except ValueError:
            return None

    # Quét toàn bộ TEXT có giá trị số ở vùng header (y > -55)
    header_texts = [(t, x, y, parse_num(t))
                     for t, x, y in texts if -60 <= y <= 10 and t.strip()]
    header_texts = [(t, x, y, v) for t, x, y, v in header_texts if v is not None]

    N = E = elev = total_depth = 0.0
    for t, x, y, v in header_texts:
        # Northing: 7-digit ~ 1.19e6
        if 1_190_000 < v < 1_200_000 and N == 0:
            N = v
        # Easting: 6-digit ~ 605xxx
        elif 600_000 < v < 610_000 and E == 0:
            E = v
        # Total depth: 20-60 m
        elif 15 < v < 80 and total_depth == 0:
            total_depth = v
        # Elevation: -5 to +10 m
        elif -5 < v < 10 and elev == 0:
            elev = v

    if N == 0 or E == 0:
        raise ValueError(f"Không trích được toạ độ HK từ {dxf_path.name}")

    # ─── LAYER BOUNDARIES — auto-detect cột cao độ đáy lớp ───
    # Template 1: x≈37-39 (ND-02..03, ND-05..07)
    # Template 2: x≈42 (ND-04)
    # Tìm cột x∈[35,45] có ≥2 giá trị cao độ rời nhau và monotonic giảm
    from collections import Counter
    col_candidates = Counter()
    for t, x, y in texts:
        v_str = t.strip().replace("−", "-").replace(",", ".").replace(" m", "")
        try:
            v = float(v_str)
            if -40 < v < elev + 0.5 and y < -60:
                col_candidates[round(x, 0)] += 1
        except ValueError:
            continue
    best_x = None; best_n = 0
    for x_col, n in col_candidates.items():
        if 35 <= x_col <= 45 and n >= 2 and n > best_n:
            best_x = x_col; best_n = n
    if best_x is None:
        best_x = 37

    bottoms = []
    seen_y = set()
    for t, x, y in texts:
        if abs(x - best_x) <= 2:
            v_str = t.strip().replace("−", "-").replace(",", ".").replace(" m", "")
            try:
                v = float(v_str)
                if v < -40 or v > elev + 0.5:
                    continue
                ry = round(y, 1)
                if ry not in seen_y:
                    bottoms.append((v, y))
                    seen_y.add(ry)
            except ValueError:
                continue
    bottoms.sort(key=lambda r: -r[1])
    layer_bounds = [(round(elev - v, 2), v, y) for v, y in bottoms]

    # ─── FALLBACK 1: Nếu cột "cao độ đáy" tìm được < 2 entries, thử dùng cột
    # "độ sâu cộng dồn" tại x≈31 (ND-04 template) ───
    if len(layer_bounds) < 2:
        cum_depths = []
        seen_y2 = set()
        # x≈31 là cột cumulative depth (depth_bot từ mặt đất)
        for t, x, y in texts:
            if 30 <= x <= 33 and y < -60:
                v_str = t.strip().replace(",", ".").replace(" m", "")
                try:
                    v = float(v_str)
                    if 0.1 < v < 80:  # depth từ 0.1 đến 80m
                        ry = round(y, 1)
                        if ry not in seen_y2:
                            cum_depths.append((v, y))
                            seen_y2.add(ry)
                except ValueError:
                    continue
        # Loại dedup giá trị (cùng cum_depth viết 2 lần do page break)
        seen_v = set()
        cum_unique = []
        for v, y in sorted(cum_depths, key=lambda r: r[0]):
            rv = round(v, 1)
            if rv not in seen_v:
                cum_unique.append((v, y))
                seen_v.add(rv)
        if len(cum_unique) >= 2:
            # depth_bot → elev_bot
            layer_bounds = [(v, round(elev - v, 2), y)
                            for v, y in cum_unique]

    # ─── MTEXT descriptions ───
    descs = []
    for t, x, y in mtexts:
        s = re.sub(r"\\[A-Za-z][^;]*;", "", t)
        s = s.replace("{", "").replace("}", "").replace("\\P", " ").strip()
        # Loại bỏ header lặp lại "Quảng trường" / "Hạ tầng" / "Phường"
        if any(skip in s for skip in ("Quảng trường", "Hạ tầng", "Phường")):
            continue
        if any(kw in s for kw in ("Đá san", "Bùn", "Sét", "Cát",
                                    "Cuội", "Sỏi", "Bê tông")):
            descs.append((s, y))
    descs.sort(key=lambda r: -r[1])

    def classify_symbol(desc: str) -> str:
        d = desc.lower()
        # Prefix "(CH)" / "(SM)" / "(CL)" — USCS classification (ND-04 template)
        m = re.match(r"\s*\(([A-Z]{1,3})\)", desc)
        uscs = m.group(1) if m else ""
        if "đá san lấp" in d or "đá đổ" in d or "bê tông" in d:
            return "F"
        if "bùn sét" in d and "chảy" in d:
            return "1"
        if "bùn" in d:
            return "1"
        if "sét pha" in d and "dẻo mềm" in d:
            return "1b"
        if "sét pha" in d and "dẻo cứng" in d:
            return "3"
        if "sét pha" in d and ("nửa cứng" in d or "cứng" in d):
            return "3"
        if "sét pha" in d:
            return "1b"
        # CH (Sét rất dẻo) trạng thái chảy/dẻo chảy → lớp yếu "1"
        if uscs == "CH" and ("chảy" in d or "dẻo chảy" in d):
            return "1"
        if uscs == "CH":
            return "1b"
        # SM (Cát lẫn bụi)
        if uscs == "SM":
            return "2a"
        # CL (Sét dẻo thấp)
        if uscs == "CL":
            return "1b"
        if "sét" in d and ("chảy" in d or "dẻo chảy" in d):
            return "1"
        if "sét" in d and "dẻo mềm" in d:
            return "1b"
        if "cát pha" in d or "cát mịn" in d or "cát bột" in d:
            return "2a"
        if "cát" in d:
            return "5"
        if "cuội sỏi" in d or "sỏi" in d:
            return "6"
        return "?"

    # ─── Build layers — match by Y (descs Y nằm giữa layer Y range) ───
    # Mỗi cao độ đáy có 1 layer. Mô tả lấy bằng cách tìm desc có Y nằm trong vùng lớp.
    # Đơn giản hóa: assign theo thứ tự sort Y descending
    layers = []
    prev_bot = 0.0
    # Tách descs unique (loại bỏ duplicate do tách page)
    unique_descs = []
    seen_desc = set()
    for d, y in descs:
        if d not in seen_desc:
            unique_descs.append((d, y))
            seen_desc.add(d)

    for i, (depth_bot, elev_bot, y_bot) in enumerate(layer_bounds):
        desc = ""
        if i < len(unique_descs):
            desc = unique_descs[i][0]
        symbol = classify_symbol(desc)
        layers.append({
            "order": i + 1,
            "depth_top_m": prev_bot,
            "depth_bot_m": depth_bot,
            "thickness_m": round(depth_bot - prev_bot, 2),
            "elev_bot_m": elev_bot,
            "symbol": symbol,
            "description": desc,
        })
        prev_bot = depth_bot

    # ─── SPT — auto-detect 4 cột (xcol spaced ~5 DXF) ───
    # Template 1: x=154,159,164,169 (ND-02..03, ND-05..07)
    # Template 2: x=139,144,149,154 (ND-04)
    int_texts = [(int(t.strip()), x, y) for t, x, y in texts
                  if re.match(r'^\d+$', t.strip())
                  and 0 <= int(t.strip()) <= 99 and y < -65]
    x_counts = Counter(round(x, 0) for v, x, y in int_texts)
    # Tìm 4 cột liền kề (spacing ~5)
    common_xs = sorted(x for x, n in x_counts.items() if n >= 5)
    spt_x_start = None
    for xc in common_xs:
        if all(round(xc + k * 5) in x_counts for k in range(4)):
            spt_x_start = xc; break
    if spt_x_start is None:
        spt_x_start = 154  # fallback

    spt_raw = defaultdict(dict)
    for t, x, y in texts:
        if re.match(r'^\d+$', t.strip()) and y < -65:
            for col in range(4):
                if abs(x - (spt_x_start + col * 5)) < 1.5:
                    ry = round(y, 0)
                    spt_raw[ry][col] = int(t)
                    break

    def y_to_depth(y):
        if y > -360:
            return (-y - 92.11) / 10 + 2.0
        return (-y - 419.11) / 10 + 22.0

    spt_samples = []
    for ry, cols in sorted(spt_raw.items(), reverse=True):
        if 0 not in cols:
            continue
        depth = y_to_depth(ry)
        if depth <= 0 or depth > 50:
            continue
        N1, N2, N3 = cols.get(0, 0), cols.get(1, 0), cols.get(2, 0)
        N_total_dxf = cols.get(3)
        spt_samples.append({
            "depth_m": round(depth, 2),
            "depth_from_m": round(depth - 0.6, 2),
            "depth_to_m": round(depth, 2),
            "N1": N1, "N2": N2, "N3": N3,
            "N_astm": N2 + N3,
            "N_total_dxf": N_total_dxf,
        })
    spt_samples.sort(key=lambda r: r["depth_m"])

    H_soft = round(sum(L["thickness_m"] for L in layers
                        if L["symbol"] in SOFT_SYMBOLS), 2)

    return {
        "_meta": {
            "source_dxf": str(dxf_path),
            "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tool": "ezdxf 1.4.4",
        },
        "borehole": {
            "name": bh_name,
            "northing_m": N,
            "easting_m": E,
            "elevation_m": elev,
            "total_depth_m": total_depth,
            "H_soft_m": H_soft,
            "n_layers": len(layers),
            "n_spt_samples": len(spt_samples),
        },
        "layers": layers,
        "spt_samples": spt_samples,
    }


def update_sqlite(data: dict, db_path: Path) -> dict:
    """Cập nhật SQLite với dữ liệu HK (idempotent)."""
    bh = data["borehole"]
    layers = data["layers"]
    spt = data["spt_samples"]
    bh_name = bh["name"]
    counters = {"borehole": 0, "layers": 0, "spt": 0, "tvtk_bh_cdm": 0}

    with sqlite3.connect(db_path) as con:
        bh_row = con.execute(
            "SELECT id FROM boreholes WHERE name = ?", (bh_name,)
        ).fetchone()
        if not bh_row:
            # Insert HK mới
            zone_row = con.execute(
                "SELECT id FROM zones WHERE code = 'QTT' OR name LIKE '%QTT%'"
            ).fetchone()
            zone_id = zone_row[0] if zone_row else None
            con.execute("""
                INSERT INTO boreholes (zone_id, name, elevation_m,
                                        x_coord_m, y_coord_m, depth_m)
                VALUES (?,?,?,?,?,?)
            """, (zone_id, bh_name, bh["elevation_m"],
                  bh["northing_m"], bh["easting_m"], bh["total_depth_m"]))
            counters["borehole"] = 1
        else:
            cur = con.execute("""
                UPDATE boreholes
                   SET elevation_m = ?, x_coord_m = ?, y_coord_m = ?, depth_m = ?
                 WHERE name = ?
            """, (bh["elevation_m"], bh["northing_m"],
                  bh["easting_m"], bh["total_depth_m"], bh_name))
            counters["borehole"] = cur.rowcount

        bh_id = con.execute(
            "SELECT id FROM boreholes WHERE name = ?", (bh_name,)
        ).fetchone()[0]

        # 2. layers — replace
        con.execute("DELETE FROM layers WHERE borehole_id = ?", (bh_id,))
        for L in layers:
            con.execute("""
                INSERT INTO layers (borehole_id, symbol, description,
                                     depth_top_m, depth_bot_m, thickness_m)
                VALUES (?,?,?,?,?,?)
            """, (bh_id, L["symbol"], L["description"],
                  L["depth_top_m"], L["depth_bot_m"], L["thickness_m"]))
            counters["layers"] += 1

        # 3. spt_values — replace (only if file has SPT)
        if spt:
            cols = [r[1] for r in con.execute(
                "PRAGMA table_info(spt_values)").fetchall()]
            con.execute("DELETE FROM spt_values WHERE borehole_id = ?", (bh_id,))
            for s in spt:
                row = {
                    "borehole_id": bh_id,
                    "depth_m": s["depth_m"],
                    "depth_from_m": s["depth_from_m"],
                    "depth_to_m": s["depth_to_m"],
                    "N": s["N_astm"],
                    "N1": s["N1"], "N2": s["N2"], "N3": s["N3"],
                    "N_astm": s["N_astm"],
                }
                insert_cols = [c for c in row if c in cols]
                placeholders = ",".join("?" for _ in insert_cols)
                con.execute(
                    f"INSERT INTO spt_values ({','.join(insert_cols)}) "
                    f"VALUES ({placeholders})",
                    tuple(row[c] for c in insert_cols),
                )
                counters["spt"] += 1

        # 4. tvtk_bh_cdm — UPDATE H_soft_m if row exists
        cur = con.execute("""
            UPDATE tvtk_bh_cdm SET H_soft_m = ?, updated_at = CURRENT_TIMESTAMP
             WHERE bh_name = ?
        """, (bh["H_soft_m"], bh_name))
        counters["tvtk_bh_cdm"] = cur.rowcount

        con.commit()
    return counters


def save_json(data: dict, out_root: Path | None = None) -> Path:
    out_root = out_root if out_root is not None else (_ROOT / "data")
    bh_name = data["borehole"]["name"]
    fn = f"qtt_{bh_name.lower().replace('-', '')}_borehole.json"
    out = out_root / fn
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return out


def import_one(dxf_path: Path, verbose: bool = True,
                 min_layers: int = 2) -> dict:
    """Import 1 HK — return data + counters.

    Nếu parse được < min_layers thì SKIP update SQLite (giữ data cũ),
    chỉ lưu JSON snapshot — tránh phá data đã có từ source khác.
    """
    data = extract_qtt_from_dxf(dxf_path)
    bh = data["borehole"]
    out_json = save_json(data)
    counters = {}
    if bh["n_layers"] < min_layers:
        skipped = "SKIPPED (layers <2 — template không khớp, giữ data cũ trong SQLite)"
        if verbose:
            print(f"  {bh['name']:>7s}  N={bh['northing_m']:>12.2f}  "
                  f"E={bh['easting_m']:>11.2f}  elev={bh['elevation_m']:>5.2f}  "
                  f"H_soft={bh['H_soft_m']:>5.2f}  "
                  f"layers={bh['n_layers']}  spt={bh['n_spt_samples']}  "
                  f"→ JSON only, {skipped}")
        return {"data": data, "json": str(out_json), "counters": counters,
                "skipped": True}
    for label, db in (("LOCAL", DB_LOCAL), ("PROJECT", DB_PROJ)):
        if not db.exists() and db == DB_LOCAL:
            continue
        counters[label] = update_sqlite(data, db)
    if verbose:
        print(f"  {bh['name']:>7s}  N={bh['northing_m']:>12.2f}  "
              f"E={bh['easting_m']:>11.2f}  elev={bh['elevation_m']:>5.2f}  "
              f"H_soft={bh['H_soft_m']:>5.2f}  "
              f"layers={bh['n_layers']}  spt={bh['n_spt_samples']}  "
              f"→ {out_json.name}")
    return {"data": data, "json": str(out_json), "counters": counters}


def import_directory(dir_path: Path) -> list[dict]:
    """Scan thư mục cho mọi QTT-HO KHOAN ND*.dxf và import."""
    files = sorted(dir_path.glob("QTT-HO KHOAN ND*.dxf"))
    print(f"Tìm thấy {len(files)} file DXF trong {dir_path.name}")
    print(f"{'HK':>10s}  {'Northing':>12s}  {'Easting':>11s}  "
          f"{'elev':>5s}  {'H_soft':>7s}  {'layers':>7s}  {'spt':>5s}")
    print("-" * 95)
    results = []
    for f in files:
        try:
            results.append(import_one(f))
        except Exception as e:
            print(f"  FAIL {f.name}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    return results


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if not args:
        # Default: scan QTT dir
        target = DXF_ROOT
    else:
        target = Path(args[0])

    if target.is_dir():
        import_directory(target)
    elif target.is_file():
        import_one(target)
    else:
        print(f"Không tìm thấy: {target}")
        return 1
    print("\nXong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
