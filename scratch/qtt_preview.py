"""
qtt_preview.py — Preview 3 biểu đồ QTT trong VSCode Interactive Window.

Cách dùng:
1. Cài extension Jupyter (Microsoft) + Python — VSCode/Antigravity hầu hết có sẵn.
2. Mở file này, đặt con trỏ trong cell (#%%) → Shift+Enter để chạy.
3. Plotly fig sẽ render inline trong Interactive Window pane.
4. Sửa code, chạy lại cell → render mới ngay, không cần Streamlit reload.

Cell 0 chạy trước để load data dùng chung. 3 cell sau độc lập.
"""

# %% Cell 0 — Setup + load data dùng chung -------------------------------
import sys
import sqlite3
import math
from pathlib import Path

import plotly.graph_objects as go

_ROOT = Path(__file__).resolve().parent.parent
_DB = _ROOT / "data" / "TTHC.sqlite"
sys.path.insert(0, str(_ROOT / "scripts"))

from settlement_calc import compare_methods, calc_settlement_iterative_9_2_3  # noqa: E402


def _q(sql: str, *args) -> list[dict]:
    with sqlite3.connect(_DB) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute(sql, args).fetchall()]


# Hố khoan QTT (ND-*)
nd_hks = _q("""
    SELECT name, elevation_m, x_coord_m, y_coord_m
    FROM boreholes WHERE name LIKE 'ND-%' ORDER BY name
""")
# Grid cao độ thiết kế / tự nhiên (162 điểm)
grid = _q("SELECT easting_m, northing_m, elev_nat_m, elev_des_m FROM qtt_elevation_points")
# HK ND có Cc (cho mượn data)
cc_rows = _q("""
    SELECT b.name, b.x_coord_m, b.y_coord_m
    FROM boreholes b JOIN lab_tests lt ON lt.borehole_id = b.id
    WHERE lt.Cc > 0 AND b.name LIKE 'ND-%' GROUP BY b.id
""")
cc_names = {r["name"] for r in cc_rows}
cc_coords = {r["name"]: (r["y_coord_m"], r["x_coord_m"]) for r in cc_rows}  # (E, N)

print(f"ND HKs: {[h['name'] for h in nd_hks]}")
print(f"Grid points: {len(grid)}")
print(f"HK có Cc: {sorted(cc_names)}")


# %% Cell 1 — 3D bề mặt: thiết kế / tự nhiên / sau lún -------------------
S_GT_INIT_PCT = 7.5
TOLERANCE_CM = 1.0


def _hfill_at(bh):
    """H_fill = elev_des(nearest grid) − elev_nat(HK)."""
    E, N, nat = bh["y_coord_m"], bh["x_coord_m"], bh["elevation_m"]
    nearest = min(grid, key=lambda g: (g["easting_m"] - E) ** 2 + (g["northing_m"] - N) ** 2)
    return max(0.0, float(nearest["elev_des_m"]) - float(nat)), float(nearest["elev_des_m"])


# Tính S_per_m_fill cho từng HK ND có H_fill > 0
s_per_m = {}
for hk in nd_hks:
    h_fill, des = _hfill_at(hk)
    if h_fill <= 0.05:
        continue
    try:
        r = calc_settlement_iterative_9_2_3(
            hk["name"], "QTT",
            H_fill_m=h_fill, S_gt_init_pct=S_GT_INIT_PCT, tolerance_cm=TOLERANCE_CM,
        )
        s_per_m[hk["name"]] = (hk["y_coord_m"], hk["x_coord_m"],
                                float(r["S_final_cm"]) / h_fill,
                                float(r["S_final_cm"]), h_fill)
        print(f"  {hk['name']}: H_fill={h_fill:.2f}m  S={r['S_final_cm']:.1f}cm")
    except Exception as e:
        print(f"  {hk['name']}: ERR {e}")

# Build matrices
es = sorted({float(g["easting_m"]) for g in grid})
ns = sorted({float(g["northing_m"]) for g in grid})
e2i = {e: i for i, e in enumerate(es)}
n2i = {n: i for i, n in enumerate(ns)}
NaN = float("nan")
Zdes = [[NaN] * len(es) for _ in ns]
Znat = [[NaN] * len(es) for _ in ns]
Zset = [[NaN] * len(es) for _ in ns]
Spred = [[NaN] * len(es) for _ in ns]
spm_list = [(E, N, sp) for (E, N, sp, _, _) in s_per_m.values()]

for g in grid:
    des, nat = g["elev_des_m"], g["elev_nat_m"]
    if des is None or nat is None:
        continue
    i, j = n2i[float(g["northing_m"])], e2i[float(g["easting_m"])]
    Zdes[i][j], Znat[i][j] = float(des), float(nat)
    fill = max(0.0, float(des) - float(nat))
    if fill < 0.05 or not spm_list:
        Zset[i][j] = float(des)
        Spred[i][j] = 0.0
        continue
    w_sum = s_w = 0.0
    for (E, N, sp) in spm_list:
        d2 = (float(g["easting_m"]) - E) ** 2 + (float(g["northing_m"]) - N) ** 2
        w = 1e9 if d2 < 0.01 else 1.0 / d2
        w_sum += w
        s_w += w * sp
    S_cm = (s_w / w_sum) * fill if w_sum > 0 else 0.0
    Spred[i][j] = S_cm
    Zset[i][j] = float(des) - S_cm / 100.0

s_max = max((max(r) for r in Spred if any(v == v for v in r)), default=1.0)

fig = go.Figure()
fig.add_trace(go.Surface(x=es, y=ns, z=Zdes, name="Thiết kế",
                          colorscale=[[0, "#93c5fd"], [1, "#1d4ed8"]],
                          opacity=0.85, showscale=False))
fig.add_trace(go.Surface(x=es, y=ns, z=Znat, name="Tự nhiên",
                          colorscale=[[0, "#fde68a"], [1, "#92400e"]],
                          opacity=0.85, showscale=False))
fig.add_trace(go.Surface(x=es, y=ns, z=Zset, name="Sau lún",
                          colorscale=[[0, "#fca5a5"], [1, "#991b1b"]],
                          opacity=0.55, surfacecolor=Spred,
                          cmin=0, cmax=max(1.0, s_max), showscale=True,
                          colorbar=dict(title="S (cm)", x=1.02, len=0.6)))
_hk_lbl = []
for h in nd_hks:
    name = h["name"]
    nat = float(h["elevation_m"])
    s_at = s_per_m.get(name)
    if s_at:
        _hk_lbl.append(f"{name}<br>z={nat:.2f}<br>S={s_at[3]:.0f}cm")
    else:
        _hk_lbl.append(f"{name}<br>z={nat:.2f}")
fig.add_trace(go.Scatter3d(
    x=[h["y_coord_m"] for h in nd_hks],
    y=[h["x_coord_m"] for h in nd_hks],
    z=[h["elevation_m"] for h in nd_hks],
    mode="markers+text",
    marker=dict(size=6, color="#dc2626", symbol="diamond"),
    text=_hk_lbl, textposition="top center",
    textfont=dict(size=10, color="#7f1d1d"),
    name="Hố khoan",
))
fig.update_layout(
    title="QTT — Bề mặt 3D: Thiết kế / Tự nhiên / Sau lún",
    scene=dict(
        xaxis_title="Easting (m)", yaxis_title="Northing (m)",
        zaxis_title="Cao độ (m)",
        aspectmode="manual", aspectratio=dict(x=2.2, y=2.2, z=0.5),
    ),
    height=700, margin=dict(l=0, r=0, t=40, b=0),
    legend=dict(orientation="h", y=-0.05),
)
fig.show()


# %% Cell 2 — Đường cong lún cố kết 15 năm -------------------------------
curves = []
for hk in nd_hks:
    name = hk["name"]
    nat = hk["elevation_m"]
    E, N = hk["y_coord_m"], hk["x_coord_m"]
    h_fill, _ = _hfill_at(hk)
    if h_fill <= 0.05:
        continue
    # Nguồn Cc
    if name in cc_names:
        src, src_d = name, 0.0
    elif cc_names:
        src = min(cc_names, key=lambda n: (cc_coords[n][0] - E) ** 2 + (cc_coords[n][1] - N) ** 2)
        src_d = math.hypot(cc_coords[src][0] - E, cc_coords[src][1] - N)
    else:
        continue
    try:
        res = compare_methods(src, zone_code="NHC", H_fill_m=h_fill, t_construction_months=6.0)
        ts = [pt for pt in res["time_series"]["no_treat"] if pt["t_years"] <= 15.0]
        if ts and ts[0]["t_months"] > 0.5:
            ts.insert(0, {"t_months": 0, "t_years": 0.0, "U_pct": 0.0, "S_cm": 0.0})
        S15 = max(pt["S_cm"] for pt in ts) if ts else 0.0
        curves.append((name, src, src_d, h_fill, ts, S15))
        print(f"  {name}: src={src} d={src_d:.0f}m  H_fill={h_fill:.2f}m  S_15y={S15:.1f}cm")
    except Exception as e:
        print(f"  {name}: ERR {e}")

palette = ["#1d4ed8", "#dc2626", "#ea580c", "#16a34a", "#7c3aed", "#0891b2"]
fig = go.Figure()
for i, (name, src, src_d, h_fill, ts, S15) in enumerate(curves):
    if not ts:
        continue
    label = name
    if src != name:
        label += f" (Cc mượn từ {src}, d={src_d:.0f}m)"
    label += f" · H_fill={h_fill:.2f}m"
    xs = [pt["t_years"] for pt in ts]
    ys = [pt["S_cm"] for pt in ts]
    mark_years = {1, 2, 5, 10, 15}
    last_idx = len(xs) - 1
    txt = []
    for ix, (tx, ty) in enumerate(zip(xs, ys)):
        if ix == last_idx or (round(tx) in mark_years and abs(tx - round(tx)) < 0.6):
            txt.append(f"{ty:.0f}")
        else:
            txt.append("")
    fig.add_trace(go.Scatter(
        x=xs, y=ys,
        mode="lines+markers+text", name=label,
        text=txt, textposition="top center",
        textfont=dict(size=10, color=palette[i % len(palette)]),
        line=dict(color=palette[i % len(palette)], width=2.2),
        marker=dict(size=6),
    ))
# 4 ngưỡng ΔS TCCS 41 Bảng 1 (Điều 6.2.3) — gộp theo giá trị unique
_lim_rows = _q("""
    SELECT delta_S_cm_max, road_class_code, position_desc
    FROM tccs41_settlement_limits ORDER BY delta_S_cm_max
""")
_lim_groups = {}
for r in _lim_rows:
    v = float(r["delta_S_cm_max"])
    cap = "cấp 1" if r["road_class_code"] == "cat1" else "cấp 2"
    _lim_groups.setdefault(v, []).append(f"{cap} · {r['position_desc']}")
_lim_colors = {10.0: "#991b1b", 20.0: "#dc2626", 30.0: "#ea580c", 40.0: "#f59e0b"}
for v in sorted(_lim_groups):
    cases = " / ".join(_lim_groups[v])
    fig.add_hline(
        y=v, line_dash="dash",
        line_color=_lim_colors.get(v, "#9ca3af"), line_width=1.5,
        annotation_text=f"ΔS ≤ {v:.0f} cm — {cases}",
        annotation_position="top left",
        annotation_font=dict(size=10, color=_lim_colors.get(v, "#9ca3af")),
    )
fig.update_layout(
    title="QTT — Đường cong lún cố kết 15 năm (no_treat)",
    xaxis_title="Thời gian (năm)", yaxis_title="Lún cố kết S (cm)",
    height=520, hovermode="x unified",
    legend=dict(orientation="h", y=-0.18),
    margin=dict(l=50, r=20, t=50, b=110),
)
fig.update_xaxes(range=[0, 15], dtick=1.0)
fig.update_yaxes(rangemode="tozero")
fig.show()


# %% Cell 3 — Sensitivity S vs H_fill / S vs H_soft ----------------------
sens = _q("""
    SELECT b.name,
           AVG(lt.Cc) AS Cc, AVG(lt.Cs) AS Cs, AVG(lt.e0) AS e0,
           AVG(lt.PC_kPa) AS PC, AVG(lt.gamma_kNm3) AS gamma,
           MIN(lt.depth_from_m) AS d_top, MAX(lt.depth_to_m) AS d_bot,
           COUNT(lt.id) AS n
    FROM boreholes b JOIN lab_tests lt ON lt.borehole_id = b.id
    WHERE b.name LIKE 'ND-%' AND lt.Cc > 0
    GROUP BY b.id ORDER BY b.name
""")


def S_terzaghi(Cc, Cs, e0, PC, ge, Hs, Hf, gf=20.0):
    """S đơn lớp Terzaghi 1D [cm]. σ'v0 tại giữa lớp."""
    if not (Cc and Cc > 0 and e0 and e0 > 0) or Hs <= 0 or Hf <= 0:
        return 0.0
    Cs_v = Cs if (Cs and Cs > 0) else 0.1 * Cc
    sv0 = ge * Hs / 2
    svf = sv0 + gf * Hf
    if sv0 <= 0 or svf <= sv0:
        return 0.0
    PC_v = PC if (PC and PC > 0) else sv0
    if svf <= PC_v:
        S = Cs_v * Hs / (1 + e0) * math.log10(svf / sv0)
    elif sv0 >= PC_v:
        S = Cc * Hs / (1 + e0) * math.log10(svf / sv0)
    else:
        S = (Cs_v * math.log10(PC_v / sv0) + Cc * math.log10(svf / PC_v)) * Hs / (1 + e0)
    return S * 100


palette = {"ND-02": "#1d4ed8", "ND-06": "#dc2626", "ND-07": "#ea580c"}

# Chart A: S vs H_fill
Hf_x = [round(0.25 * i, 2) for i in range(1, 13)]
figA = go.Figure()
for p in sens:
    Hs_act = max(1.0, float(p["d_bot"] or 30) - float(p["d_top"] or 0))
    ge = max(0.1, float(p["gamma"] or 16) - 9.81)
    ys = [S_terzaghi(p["Cc"], p["Cs"], p["e0"], p["PC"], ge, Hs_act, hf) for hf in Hf_x]
    txt_hf = [f"{v:.0f}" if (xv * 2) % 1 == 0 else "" for xv, v in zip(Hf_x, ys)]
    figA.add_trace(go.Scatter(
        x=Hf_x, y=ys, mode="lines+markers+text",
        name=f"{p['name']} (H_soft={Hs_act:.0f}m, n={p['n']})",
        text=txt_hf, textposition="top center",
        textfont=dict(size=9, color=palette.get(p["name"], "#666")),
        line=dict(color=palette.get(p["name"], "#666"), width=2.2),
    ))
figA.add_hline(y=30, line_dash="dash", line_color="#dc2626", annotation_text="≤30 cm")
figA.update_layout(
    title="QTT — S 15 năm vs H_fill",
    xaxis_title="H_fill (m)", yaxis_title="S 15 năm (cm)",
    height=460, hovermode="x unified",
    legend=dict(orientation="h", y=-0.22),
)
figA.update_yaxes(rangemode="tozero")
figA.show()

# Chart B: S vs H_soft
Hs_x = list(range(5, 41, 2))
Hf_fixed = 1.0
figB = go.Figure()
for p in sens:
    ge = max(0.1, float(p["gamma"] or 16) - 9.81)
    ys = [S_terzaghi(p["Cc"], p["Cs"], p["e0"], p["PC"], ge, hs, Hf_fixed) for hs in Hs_x]
    txt_hs = [f"{v:.0f}" if xv % 5 == 0 else "" for xv, v in zip(Hs_x, ys)]
    figB.add_trace(go.Scatter(
        x=Hs_x, y=ys, mode="lines+markers+text",
        name=f"{p['name']} (n={p['n']} mẫu)",
        text=txt_hs, textposition="top center",
        textfont=dict(size=9, color=palette.get(p["name"], "#666")),
        line=dict(color=palette.get(p["name"], "#666"), width=2.2),
    ))
figB.add_hline(y=30, line_dash="dash", line_color="#dc2626", annotation_text="≤30 cm")
figB.update_layout(
    title=f"QTT — S 15 năm vs H_soft (H_fill = {Hf_fixed}m)",
    xaxis_title="H_soft (m)", yaxis_title="S 15 năm (cm)",
    height=460, hovermode="x unified",
    legend=dict(orientation="h", y=-0.22),
)
figB.update_yaxes(rangemode="tozero")
figB.show()

print("\nThông số đầu vào sensitivity:")
for p in sens:
    Hs_act = float(p["d_bot"] or 30) - float(p["d_top"] or 0)
    print(f"  {p['name']}: Cc={p['Cc']:.3f}  e0={p['e0']:.2f}  PC={p['PC'] or 0:.0f}kPa  "
          f"γ={p['gamma'] or 0:.2f}  H_soft_thực={Hs_act:.0f}m  n={p['n']}")


# %% Cell 4 — Phân tích CDM QTT: Lc theo ΔS ----------------------------
from qtt_cdm_analysis import compute_cdm_lc_matrix, compute_s_vs_p_curves

mat = compute_cdm_lc_matrix()
meta = mat["meta"]
hks_m = mat["hks"]
dS_list = meta["delta_S_values_cm"]
print(f"\nMeta: q={meta['q_kPa']} kPa  D={meta['D_mm']}mm s={meta['spacing_m']}m  "
      f"a={meta['a']:.4f}  Ec={meta['Ec_kPa']:.0f}kPa  fill_h={meta['fill_thickness_m']}m")
print()
for h in hks_m:
    src = h.get("cc_source") or "—"
    note = " (mượn)" if h.get("borrowed") else ""
    print(f"  {h['name']}: nat={h['nat']} des={h.get('design')} "
          f"top_CDM={h.get('cdm_top_elev')}m exc={h.get('excavation_m')}m  Cc←{src}{note}")
    for dS in dS_list:
        r = h["by_dS"].get(dS, {})
        Lc = r.get("Lc_m"); S = r.get("S_total_cm")
        print(f"     ΔS={int(dS):2d}cm: Lc={Lc}m  S={S}cm  {'OK' if r.get('ok') else 'KĐ'}")

# Heatmap Lc 6×4
Z = []; Yl = []
for h in hks_m:
    row = []
    for dS in dS_list:
        r = h["by_dS"].get(dS, {})
        row.append(float(r["Lc_m"]) if r.get("ok") and r.get("Lc_m") else None)
    Z.append(row)
    Yl.append(h["name"] + (f" (Cc←{h['cc_source']})" if h.get("borrowed") else ""))
fig = go.Figure(go.Heatmap(
    z=Z, x=[f"ΔS ≤ {int(d)} cm" for d in dS_list], y=Yl,
    text=[[f"{v:.1f}" if v else "—" for v in r] for r in Z],
    texttemplate="%{text}", textfont=dict(size=12),
    colorscale=[[0, "#bbf7d0"], [0.4, "#fef9c3"], [0.7, "#fed7aa"], [1, "#fecaca"]],
    colorbar=dict(title="Lc (m)"),
))
fig.update_layout(title="QTT — Heatmap Lc (m) HK × ΔS",
                   yaxis=dict(autorange="reversed"),
                   xaxis=dict(side="top"), height=380)
fig.show()

# Đường cong S vs Lc
curves = compute_s_vs_p_curves(p_range_m=(0.5, 35.0), p_step_m=1.0)
palette_c = {"ND-02": "#1d4ed8", "ND-03": "#dc2626", "ND-04": "#ea580c",
             "ND-05": "#16a34a", "ND-06": "#7c3aed", "ND-07": "#0891b2"}
fig2 = go.Figure()
for hk_name, cd in curves["curves"].items():
    pts = cd.get("points") or []
    if not pts:
        continue
    xs = [pt["Lc_m"] for pt in pts]; ys = [pt["S_total_cm"] for pt in pts]
    last = len(xs) - 1
    txt = [f"{ys[i]:.0f}" if i == last or xs[i] in (10, 15, 20, 25, 30) else "" for i in range(len(xs))]
    label = hk_name + (f" (Cc←{cd['cc_source']})" if cd.get("borrowed") else "")
    fig2.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines+markers+text",
        name=label, text=txt, textposition="top center",
        textfont=dict(size=9, color=palette_c.get(hk_name, "#666")),
        line=dict(color=palette_c.get(hk_name, "#666"), width=2.2),
    ))
for dS, col in [(10, "#991b1b"), (20, "#dc2626"), (30, "#ea580c"), (40, "#f59e0b")]:
    fig2.add_hline(y=dS, line_dash="dash", line_color=col,
                   annotation_text=f"ΔS ≤ {dS} cm", annotation_position="top left",
                   annotation_font=dict(size=10, color=col))
fig2.update_layout(title="QTT — S_total vs Lc per HK",
                    xaxis_title="Lc (m)", yaxis_title="S_total (cm)",
                    height=520, hovermode="x unified")
fig2.update_yaxes(rangemode="tozero")
fig2.show()
