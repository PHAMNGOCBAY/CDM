"""
scripts/pages/lk2_page.py — Trang "Móng trụ CDM (LK2)".

Tái lập 100% bảng tính Excel 'TINH MONG TRU CDM - LK2.xlsx' dưới dạng engine sống:
đổi thông số -> tính lại tức thời (auto-compute, không nút Build/Solve — §9b).

4 nhóm (trải phẳng, in PDF được — §17):
  A. Lún khối móng CDM (Sblock + Sc cố kết)
  B. Sức chịu tải cọc CDM
  C. Lún cố kết theo thời gian
  D. Kiểm toán lớp bê tông + Giới hạn lún cho phép

Engine: scripts/cdm_lk2_calc.py — đã validate khớp Excel sai số 0.00.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_ROOT = _HERE.parent
_JSON = _ROOT / "data" / "lk2_cdm_settlement.json"


def render() -> None:
    import streamlit as st

    import json as _json
    import sqlite3 as _sql
    from cdm_lk2_calc import (
        SETTLEMENT_LIMITS, build_geology_from_bh, compute_concrete_check, compute_lk2,
        compute_sct, compute_time_history, load_lk2_dataset,
    )

    st.title("Móng trụ CDM — Hố khoan LK2")
    st.caption(
        "Bản tính lún khối móng, sức chịu tải và kiểm toán cọc xi măng đất theo "
        "TCVN 9403:2012 (Phụ lục C) và 22TCN 262-2000. Mọi thông số đổi tức thời "
        "sẽ tính lại ngay. Bộ thông số mặc định theo thiết kế hiện hành."
    )

    inp, geo = load_lk2_dataset()
    full = json.loads(_JSON.read_text(encoding="utf-8"))

    # Bộ mặc định UI thiết kế hiện hành (ui_defaults trong JSON) — ghi đè scalars golden
    _ud = full.get("ui_defaults", {})
    if _ud:
        for _k in ("D_m", "S_m", "pattern", "quck", "CD1_top_pile", "CD2_bot_pile",
                   "P_fill", "q_total", "W_group", "theta_deg", "water_elev"):
            if _k in _ud:
                setattr(inp, _k, _ud[_k])
    _dv_default = float(_ud.get("dv_concrete_m", full["scalars"].get("dv_concrete_m", 0.0)))

    # ─── Nguồn địa tầng: LK2 gốc hoặc hố khoan từ 6 vùng CDM ───────────────
    _db = str(_ROOT / "data" / "TTHC.sqlite")
    _zone_bhs = []
    try:
        _con = _sql.connect(_db)
        for (_bl,) in _con.execute("SELECT bh_list FROM ke_cdm_zones").fetchall():
            _zone_bhs += _json.loads(_bl)
        _con.close()
        _zone_bhs = sorted(set(_zone_bhs), key=lambda x: int("".join(c for c in x if c.isdigit()) or 0))
    except Exception:
        _zone_bhs = []
    _opts = ["LK2 (hồ sơ gốc)"] + [f"Hố khoan {b}" for b in _zone_bhs]
    _def_idx = _opts.index("Hố khoan KE-HK2") if "Hố khoan KE-HK2" in _opts else 0
    _src = st.selectbox("Nguồn địa tầng dùng tính toán", _opts, index=_def_idx, key="lk2_geo_src")
    if _src.startswith("Hố khoan"):
        _bh = _src.replace("Hố khoan ", "")
        try:
            geo, _bh_elev = build_geology_from_bh(_bh, sublayer_m=2.0)
            st.caption(f"Đang dùng địa tầng **{_bh}** (cao độ tự nhiên {_bh_elev:.2f} m, "
                       f"{len(geo)} phân tố 2 m). Chỉ tiêu lấy từ mẫu lab gần nhất của hố; "
                       f"thiếu → mượn trung bình lớp theo vùng.")
        except Exception as e:  # noqa: BLE001
            st.error(f"Không dựng được địa tầng {_bh}: {e}")

    # ─── Thông số đầu vào (live) ──────────────────────────────────────────
    st.markdown("### Thông số thiết kế (đổi để tính lại tức thời)")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        inp.D_m = st.number_input("Đường kính trụ D (m)", 0.4, 2.0, float(inp.D_m), 0.1, key="lk2_D")
        inp.S_m = st.number_input("Khoảng cách trụ S (m)", 0.8, 4.0, float(inp.S_m), 0.1, key="lk2_S")
    with c2:
        inp.pattern = 1 if st.selectbox("Bố trí lưới", ["Vuông", "Tam giác"],
                                        index=0 if inp.pattern == 1 else 1, key="lk2_pat") == "Vuông" else 2
        inp.quck = st.number_input("Cường độ trụ q_uck (kN/m²)", 200.0, 5000.0, float(inp.quck), 50.0, key="lk2_quck")
    with c3:
        inp.CD1_top_pile = st.number_input("Cao độ đỉnh trụ (m)", -50.0, 50.0, float(inp.CD1_top_pile), 0.1, key="lk2_cd1")
        inp.CD2_bot_pile = st.number_input("Cao độ đáy trụ (m)", -80.0, 50.0, float(inp.CD2_bot_pile), 0.1, key="lk2_cd2")
    with c4:
        inp.P_fill = st.number_input("Tải đắp tĩnh P (kN/m²)", 0.0, 500.0, float(inp.P_fill), 0.5, key="lk2_P",
                                     help="Tải tính LÚN — không xét hoạt tải")
        inp.q_total = st.number_input("Tải tổng q (kN/m²)", 0.0, 500.0, float(inp.q_total), 0.5, key="lk2_q",
                                      help="Tải tính SỨC CHỊU TẢI — gồm hoạt tải")

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        inp.W_group = st.number_input("Bề rộng nhóm trụ W (m)", 1.0, 100.0, float(inp.W_group), 1.0, key="lk2_W")
    with c6:
        inp.theta_deg = st.number_input("Góc phân tán θ (độ)", 0.0, 60.0, float(inp.theta_deg), 1.0, key="lk2_theta")
    with c7:
        inp.water_elev = st.number_input("Cao độ MNN (m)", -50.0, 50.0, float(inp.water_elev), 0.1, key="lk2_wl")
    with c8:
        _dv = st.number_input("Lớp bê tông C10 dày (m)", 0.0, 1.0,
                              _dv_default, 0.05, key="lk2_dv")

    # ─── Auto-compute ─────────────────────────────────────────────────────
    # Dùng địa tầng hố khoan → bật đầy đủ §71 (mở rộng dưới HK + nhánh cát/sét chặt);
    # LK2 hồ sơ gốc → giữ Excel-faithful để khớp 100%.
    _full71 = _src.startswith("Hố khoan")
    res = compute_lk2(inp, geo, sand_elastic=_full71, extend_below_bh=_full71)
    sct = compute_sct(inp, geo, res.Ecol, res.a_ratio)
    cvt, tvu, gt = full["cv_table"], full["tvu_table"], full["golden_time"]
    th = compute_time_history(res, cvt["pressure_kPa"], cvt["Cv"], tvu["Tv"], tvu["U_pct"],
                              gt["years"], allowable_cm=gt["allowable_cm"], design_time_idx=1)
    cc = compute_concrete_check(inp.D_m, inp.S_m, inp.q_total, _dv)

    # Đáy vùng ảnh hưởng lún = cao độ phân tố sâu nhất còn có Δσ ≥ 10%·σ'v0
    _infl_elev = None
    for s in res.sublayers:
        if s.dsigma > 0 and s.sigma_vz > 0 and s.dsigma >= 0.1 * s.sigma_vz:
            _infl_elev = s.z_bot_elev

    st.divider()

    # ─── A. Lún khối móng ─────────────────────────────────────────────────
    st.markdown("### A. Độ lún khối móng CDM")
    st.caption(f"Tải tính lún (khối gia cố S₁ + cố kết S_c) = **tải đắp TĨNH P = {inp.P_fill:.1f} kN/m²** "
               "(KHÔNG xét hoạt tải — hoạt tải tần suất ngắn không gây cố kết).")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Lún khối S_block", f"{res.Sblock_m*100:.2f} cm")
    a2.metric("Lún cố kết S_c", f"{res.Sc_m*100:.2f} cm")
    a3.metric("Tổng lún S", f"{res.S_total_m*100:.2f} cm")
    a4.metric("Hệ số cải tạo a", f"{res.a_ratio*100:.2f} %")
    st.caption(
        f"E_col = {res.Ecol:,.0f} kN/m² · E_eq (khối gia cố) = {res.Eeq:,.0f} kN/m² · "
        f"Chiều dài trụ L = {res.L_pile:.2f} m · "
        f"S_block = P·L/E_eq = {inp.P_fill:.1f}·{res.L_pile:.2f}/{res.Eeq:,.0f}."
    )
    st.latex(r"S = S_{block} + S_c = \frac{P \cdot L}{E_{eq}} + \sum_i \frac{h_i}{1+e_{0i}}"
             r"\cdot C \cdot \log_{10}\frac{\sigma'_{vf}}{\sigma'_{v0}}")

    import pandas as pd
    # Chỉ thể hiện đến đáy vùng ảnh hưởng (Δσ=10%·σ'v0), không cần hết chiều sâu
    _tbl_subs = [s for s in res.sublayers
                 if _infl_elev is None or s.z_bot_elev >= _infl_elev - 0.01]
    rows = [{
        "Phân tố": s.idx, "Lớp": s.symbol, "Bề dày (m)": round(s.h, 2),
        "Cao độ đáy (m)": round(s.z_bot_elev, 2),
        "Cu (kPa)": round(s.Cu, 1), "Es=250·Cu (kPa)": round(s.Esoil, 0),
        "Trong khối (m)": round(s.in_block_thickness, 2), "σ'vz (kPa)": round(s.sigma_vz, 2),
        "Δσ (kPa)": round(s.dsigma, 2), "σ'pz (kPa)": round(s.sigma_pz, 2),
        "Trạng thái": {"NC": "Cố kết thường", "OC": "Quá cố kết", "cross": "Vượt P_c",
                       "block": "Trong khối gia cố", "-": "—",
                       "đàn hồi (cát/sét chặt)": "Đàn hồi (cát/sét chặt)",
                       "cát (bỏ qua)": "Cát (bỏ qua)",
                       "ngoài vùng ảnh hưởng": "Ngoài vùng ảnh hưởng"}.get(s.branch, s.branch),
        "Lún Sc (cm)": round(s.Sc_m * 100, 3),
    } for s in _tbl_subs]
    st.table(pd.DataFrame(rows))
    if _infl_elev is not None:
        st.caption(f"Bảng chỉ thể hiện đến đáy vùng ảnh hưởng lún (Δσ = 10%·σ'v0) ở cao độ "
                   f"{_infl_elev:.1f} m; phân tố sâu hơn (Δσ < 10%·σ'v0) đã lược bỏ.")

    # biểu đồ lún cố kết theo phân tố (giá trị hiển thị trực tiếp — rule 3)
    _consol = [s for s in res.sublayers if s.Sc_m > 0]
    if _consol:
        try:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_bar(
                x=[f"PT{s.idx}\n({s.z_bot_elev:.1f}m)" for s in _consol],
                y=[s.Sc_m * 100 for s in _consol],
                text=[f"{s.Sc_m*100:.2f}" for s in _consol], textposition="outside",
                marker_color="#1565C0", name="Lún cố kết",
            )
            fig.update_layout(title="Lún cố kết từng phân tố dưới mũi cọc (cm)",
                              yaxis_title="Sc (cm)", height=340,
                              font=dict(size=16), legend=dict(font=dict(size=16)), margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass

    # ─── Biểu đồ minh họa S1, S2 qua các lớp đất ──────────────────────────
    subs = res.sublayers
    if subs:
        try:
            import plotly.graph_objects as go
            CD1, CD2 = inp.CD1_top_pile, inp.CD2_bot_pile
            top_elev = subs[0].z_bot_elev + subs[0].h
            bot_elev = subs[-1].z_bot_elev
            # các đoạn lớp đất theo ký hiệu
            _pal = ["#FFE0B2", "#C8E6C9", "#BBDEFB", "#F8BBD0", "#D1C4E9", "#FFF9C4",
                    "#B2DFDB", "#FFCCBC", "#CFD8DC", "#DCEDC8"]
            segs, prev, t = [], None, top_elev
            for s in subs:
                if prev is not None and s.symbol != prev:
                    segs.append((prev, t, s.z_bot_elev + s.h)); t = s.z_bot_elev + s.h
                prev = s.symbol
            segs.append((prev, t, bot_elev))
            symu = []
            for sym, _, _ in segs:
                if sym not in symu:
                    symu.append(sym)
            sch = go.Figure()
            for sym, zt, zb in segs:
                sch.add_hrect(y0=zb, y1=zt, fillcolor=_pal[symu.index(sym) % len(_pal)],
                              opacity=0.45, line_width=0)
                sch.add_annotation(x=0.97, y=(zt + zb) / 2.0, text=f"Lớp {sym}", showarrow=False,
                                   xanchor="right", font=dict(size=14, color="#444"))
            # cọc CDM (khối gia cố)
            sch.add_shape(type="rect", x0=0.40, x1=0.60, y0=CD2, y1=CD1,
                          fillcolor="#90A4AE", opacity=0.85, line=dict(color="#37474F", width=1))
            sch.add_hline(y=CD1, line=dict(color="#2E7D32", dash="dash"),
                          annotation_text=f"Đỉnh trụ {CD1:.1f} m", annotation_font=dict(size=14))
            sch.add_hline(y=CD2, line=dict(color="#C62828", dash="dash"),
                          annotation_text=f"Mũi cọc {CD2:.1f} m", annotation_font=dict(size=14))
            if _infl_elev is not None:
                sch.add_hline(y=_infl_elev, line=dict(color="#6A1B9A", dash="dot"),
                              annotation_text=f"Đáy vùng ảnh hưởng {_infl_elev:.1f} m",
                              annotation_font=dict(size=14), annotation_position="bottom left")
            # vùng S1 (khối gia cố) + S2 (cố kết dưới mũi)
            sch.add_annotation(x=0.12, y=(CD1 + CD2) / 2.0,
                               text=f"S₁ (khối gia cố)<br>= {res.Sblock_m*100:.1f} cm",
                               showarrow=False, font=dict(size=15, color="#1565C0"),
                               bgcolor="rgba(255,255,255,0.7)")
            if res.Sc_m > 0 and bot_elev < CD2:
                sch.add_annotation(x=0.12, y=(CD2 + bot_elev) / 2.0,
                                   text=f"S₂ (cố kết dưới mũi)<br>= {res.Sc_m*100:.1f} cm",
                                   showarrow=False, font=dict(size=15, color="#E65100"),
                                   bgcolor="rgba(255,255,255,0.7)")
            # Trục Y bao hết: đỉnh trụ → đáy sâu nhất cần xem (mũi cọc hoặc đáy vùng ảnh hưởng)
            _deep = _infl_elev if _infl_elev is not None else bot_elev
            _y_top = max(top_elev, CD1) + 0.5
            _y_bot = min(CD2, _deep) - 2.0
            sch.update_layout(title="Minh họa S₁ (khối gia cố) và S₂ (cố kết dưới mũi) qua các lớp đất",
                              xaxis=dict(range=[0, 1], showticklabels=False, showgrid=False),
                              yaxis=dict(title="Cao độ (m)", range=[_y_bot, _y_top]),
                              height=640, font=dict(size=16), margin=dict(t=44, b=10))
            st.plotly_chart(sch, use_container_width=True)
        except Exception:
            pass

    # ─── Biểu đồ ứng suất hữu hiệu + ứng suất gây lún + đường giới hạn 10% ─
    if subs:
        try:
            import plotly.graph_objects as go
            elv = [s.z_bot_elev + s.h / 2.0 for s in subs]
            svz = [s.sigma_vz for s in subs]
            dsg = [s.dsigma for s in subs]
            svz10 = [0.1 * v for v in svz]
            def _lbl(vals): return [f"{v:.0f}" if (i % 2 == 0) else "" for i, v in enumerate(vals)]
            fst = go.Figure()
            fst.add_trace(go.Scatter(x=svz, y=elv, mode="lines+markers+text", name="σ'v0 (hữu hiệu)",
                          text=_lbl(svz), textposition="middle right", textfont=dict(size=15),
                          line=dict(color="#1565C0", width=2.5)))
            fst.add_trace(go.Scatter(x=dsg, y=elv, mode="lines+markers+text", name="Δσ (gây lún)",
                          text=_lbl(dsg), textposition="middle left", textfont=dict(size=15),
                          line=dict(color="#C62828", width=2.5)))
            fst.add_trace(go.Scatter(x=svz10, y=elv, mode="lines", name="10%·σ'v0 (giới hạn)",
                          line=dict(color="#2E7D32", width=1.6, dash="dash")))
            # ranh giới lớp
            prev, t = None, subs[0].z_bot_elev + subs[0].h
            for s in subs:
                if prev is not None and s.symbol != prev:
                    zb = s.z_bot_elev + s.h
                    fst.add_hline(y=zb, line=dict(color="#bbb", width=1, dash="dot"))
                prev = s.symbol
            fst.add_hline(y=inp.CD2_bot_pile, line=dict(color="#F57F17", dash="dot"),
                          annotation_text=f"Mũi cọc {inp.CD2_bot_pile:.1f} m", annotation_font=dict(size=14))
            if _infl_elev is not None:
                fst.add_hline(y=_infl_elev, line=dict(color="#6A1B9A", dash="dot"),
                              annotation_text=f"Đáy vùng ảnh hưởng (Δσ=10%σ'v0) {_infl_elev:.1f} m",
                              annotation_font=dict(size=14), annotation_position="bottom left")
            _deep2 = _infl_elev if _infl_elev is not None else subs[-1].z_bot_elev
            fst.update_layout(title="Ứng suất hữu hiệu σ'v0, ứng suất gây lún Δσ và giới hạn 10%",
                              xaxis_title="Ứng suất (kPa)", yaxis_title="Cao độ (m)",
                              yaxis=dict(range=[min(inp.CD2_bot_pile, _deep2) - 3,
                                                (subs[0].z_bot_elev + subs[0].h) + 0.5]),
                              height=520, font=dict(size=16), legend=dict(font=dict(size=16)),
                              margin=dict(t=44, b=10))
            st.plotly_chart(fst, use_container_width=True)
        except Exception:
            pass

    st.divider()

    # ─── B. Sức chịu tải ──────────────────────────────────────────────────
    st.markdown("### B. Sức chịu tải cọc CDM")
    st.caption(f"Tải tính sức chịu tải / tải lên đầu cọc = **tải TỔNG q = {inp.q_total:.1f} kN/m²** "
               "(gồm hoạt tải — cọc chịu trực tiếp hoạt tải xe).")
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Tải lên 1 cọc N", f"{sct.N_load:.1f} kN")
    b2.metric("SCT vật liệu N_vl", f"{sct.Nvl:.1f} kN")
    b3.metric("SCT đất nền N_đn", f"{sct.Ndn:.1f} kN")
    b4.metric("N_c = min", f"{sct.Nc:.1f} kN",
              delta=f"hệ số {sct.ratio_Nc_N:.2f}", delta_color="normal")
    _ok1 = "Đạt" if sct.ok_capacity else "Không đạt"
    _qa_mat = inp.quck / inp.Fs
    st.markdown("**Công thức chi tiết (TCVN 11823-10 / Phụ lục D):**")
    st.latex(rf"N = q \cdot s^2 = {inp.q_total:.1f}\cdot {inp.S_m:.1f}^2 = {sct.N_load:.1f}\ \text{{kN}}")
    st.latex(rf"N_{{vl}} = [q_a]\cdot A_p = \dfrac{{q_{{uck}}}}{{F_s}}\cdot A_p "
             rf"= \dfrac{{{inp.quck:.0f}}}{{{inp.Fs:.0f}}}\cdot {sct.Ap:.4f} = {sct.Nvl:.1f}\ \text{{kN}}")
    st.latex(rf"q_p = 6\,C_u = 6\cdot {sct.Cu_soil:.1f} = {sct.qp:.1f}\ \text{{kN/m}}^2")
    st.latex(rf"N_{{đn}} = \alpha\,A_p\,q_p + \pi D\,q_{{si}}\,L "
             rf"= {inp.a_pier}\cdot{sct.Ap:.4f}\cdot{sct.qp:.1f} + \pi\cdot{inp.D_m}\cdot{inp.qsi}\cdot{res.L_pile:.1f} "
             rf"= {sct.Ndn:.1f}\ \text{{kN}}")
    st.latex(rf"N_c = \min(N_{{vl}},\,N_{{đn}}) = {sct.Nc:.1f}\ \text{{kN}};\quad "
             rf"\text{{hệ số}} = N_c/N = {sct.ratio_Nc_N:.2f}")
    st.markdown(f"**Kiểm tra (N ≤ N_c):** N = {sct.N_load:.1f} kN ≤ N_c = {sct.Nc:.1f} kN → **{_ok1}**")
    st.caption("Trong đó: q = tải tổng · s = khoảng cách trụ · A_p = π D²/4 = "
               f"{sct.Ap:.4f} m² · [q_a] = q_uck/F_s = {_qa_mat:.0f} kN/m² · α (triết giảm mũi) = "
               f"{inp.a_pier} · q_si (ma sát thành) = {inp.qsi} kN/m² · L = {res.L_pile:.1f} m.")

    st.markdown("**Theo tập trung ứng suất + sức chịu tải AIT:**")
    bb1, bb2, bb3, bb4 = st.columns(4)
    bb1.metric("Ứng suất lên cọc σ_col", f"{sct.sigma_col:.1f} kN/m²")
    bb2.metric("Tải tập trung P_col", f"{sct.Pcol:.1f} kN")
    bb3.metric("Q_ult vật liệu (AIT)", f"{sct.Qult_col_AIT:.1f} kN")
    bb4.metric("Q_a đất nền (AIT)", f"{sct.Qa_soil:.1f} kN")
    _ok2 = "Đạt" if sct.ok_AIT else "Không đạt"
    st.markdown("**Công thức chi tiết (tập trung ứng suất + AIT — Viện Kỹ thuật Á Châu):**")
    st.latex(rf"\sigma_{{col}} = \dfrac{{E_{{col}}}}{{E_{{tđ}}}}\cdot q "
             rf"= \dfrac{{{res.Ecol:.0f}}}{{{sct.Etd:.0f}}}\cdot {inp.q_total:.1f} = {sct.sigma_col:.1f}\ \text{{kN/m}}^2")
    st.latex(rf"P_{{col}} = \sigma_{{col}}\cdot A_p = {sct.sigma_col:.1f}\cdot {sct.Ap:.4f} = {sct.Pcol:.1f}\ \text{{kN}}")
    st.latex(rf"Q_{{ult.vl}} = A_p\,(3{{,}}5\,q_{{uck}} + 3(q + 5\,C_u)) "
             rf"= {sct.Ap:.4f}\,(3{{,}}5\cdot{inp.quck:.0f} + 3({inp.q_total:.1f}+5\cdot{sct.Cu_soil:.1f})) "
             rf"= {sct.Qult_col_AIT:.1f}\ \text{{kN}}")
    st.latex(rf"Q_{{ult.đn}} = (\pi D L + 2{{,}}25\,\pi D^2)\,C_u "
             rf"= (\pi\cdot{inp.D_m}\cdot{res.L_pile:.1f} + 2{{,}}25\pi\cdot{inp.D_m}^2)\cdot{sct.Cu_soil:.1f} "
             rf"= {sct.Qult_soil_AIT:.1f}\ \text{{kN}}")
    st.latex(rf"Q_a = Q_{{ult.đn}}/F_s = {sct.Qult_soil_AIT:.1f}/{inp.Fs:.0f} = {sct.Qa_soil:.1f}\ \text{{kN}}")
    st.markdown(f"**Kiểm tra (P_col ≤ Q_a):** P_col = {sct.Pcol:.1f} kN ≤ Q_a = {sct.Qa_soil:.1f} kN → **{_ok2}**")
    st.caption(f"E_tđ = {sct.Etd:,.0f} kN/m² (mô đun tương đương khối) · "
               f"C_u TB khối = {sct.Cu_soil:.2f} kN/m² · 2,25πD² = 9·A_p (sức kháng mũi N_c=9).")

    st.divider()

    # ─── C. Lún theo thời gian ────────────────────────────────────────────
    st.markdown("### C. Độ lún cố kết theo thời gian")
    st.caption(f"Chiều sâu thoát nước H = {th.H_drain_m:.2f} m · "
               f"Hệ số cố kết TB C_v = {th.Ctbv_cm2s:.2e} cm²/s · "
               f"Tổng lún cố kết S_c = {th.Sc_cm:.2f} cm (cố kết 1 mặt).")
    tdf = pd.DataFrame({
        "Thời gian (năm)": th.years,
        "Nhân tố T_v": [round(x, 4) for x in th.Tv],
        "Độ cố kết U_v (%)": [round(x * 100, 1) for x in th.Uv],
        "Lún đạt St (cm)": [round(x, 2) for x in th.St_cm],
        "Lún còn lại (cm)": [round(x, 2) for x in th.residual_cm],
    })
    st.table(tdf)
    try:
        import plotly.graph_objects as go
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=th.years, y=[round(x, 2) for x in th.St_cm], mode="lines+markers+text",
            text=[f"{x:.1f}" for x in th.St_cm], textposition="top center",
            name="Lún đạt St", line=dict(color="#1565C0", width=2)))
        fig2.add_trace(go.Scatter(
            x=th.years, y=[round(x, 2) for x in th.residual_cm], mode="lines+markers",
            name="Lún còn lại", line=dict(color="#C62828", width=2, dash="dot")))
        fig2.add_hline(y=th.allowable_cm, line=dict(color="#2E7D32", dash="dash"),
                       annotation_text=f"Giới hạn cho phép {th.allowable_cm:.0f} cm")
        fig2.update_layout(title="Đường cong lún cố kết theo thời gian",
                           xaxis_title="Thời gian (năm)", yaxis_title="Độ lún (cm)",
                           height=380, margin=dict(t=40, b=10))
        st.plotly_chart(fig2, use_container_width=True)
    except Exception:
        pass
    _okt = "Đạt" if th.ok else "Không đạt"
    st.markdown(f"**Lún cố kết còn lại sau {th.years[th.design_time_idx]:.0f} năm = "
                f"{th.residual_check_cm:.2f} cm ≤ giới hạn {th.allowable_cm:.0f} cm → {_okt}**")

    st.divider()

    # ─── D. Kiểm toán bê tông + Giới hạn lún ──────────────────────────────
    st.markdown("### D. Kiểm toán lớp bê tông + Giới hạn lún cho phép")
    st.caption(f"Tải kiểm toán lớp bê tông = **tải TỔNG q = {inp.q_total:.1f} kN/m²** "
               "(M_tt = q(S−d)²/8 ; V_tt = q(S−d)/2).")
    _fc, _bv = 8.0, 1000.0   # f'c (MPa) lớp C10, bề rộng tính toán bv (mm) — mặc định engine
    _Smd = inp.S_m - inp.D_m
    # Nội lực yêu cầu (luôn hiển thị)
    st.markdown("**Nội lực yêu cầu (dầm nhịp thông thuỷ giữa 2 trụ):**")
    st.latex(rf"M_{{tt}} = \dfrac{{q\,(S-d)^2}}{{8}} = \dfrac{{{inp.q_total:.1f}\,({inp.S_m:.1f}-{inp.D_m:.1f})^2}}{{8}} "
             rf"= {cc.Mtt:.2f}\ \text{{kNm}}")
    st.latex(rf"V_{{tt}} = \dfrac{{q\,(S-d)}}{{2}} = \dfrac{{{inp.q_total:.1f}\,({_Smd:.1f})}}{{2}} = {cc.Vtt:.2f}\ \text{{kN}}")
    st.latex(rf"[\sigma] = 0{{,}}63\sqrt{{f'_c}} = 0{{,}}63\sqrt{{{_fc:.0f}}} = {cc.sigma_flex_MPa:.3f}\ \text{{MPa}}"
             r"\quad(\text{TCVN 11823-5, Điều 4.2.6})")
    if cc.dv_m > 0:
        _zse = (_bv / 1e3) * (cc.dv_m) ** 2 / 6.0   # Zse = b·h²/6 (m³), b=bv/1000 m
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Mô men yêu cầu M_tt", f"{cc.Mtt:.2f} kNm")
        d2.metric("Sức kháng uốn M_r", f"{cc.Mr:.2f} kNm")
        d3.metric("Lực cắt yêu cầu V_tt", f"{cc.Vtt:.2f} kN")
        d4.metric("Sức kháng cắt V_r", f"{cc.Vr:.2f} kN")
        st.markdown("**Sức kháng (lớp bê tông dày d_v = %.2f m, f'c = %.0f MPa, b = 1,0 m):**" % (cc.dv_m, _fc))
        st.latex(rf"Z_{{se}} = \dfrac{{b\,d_v^2}}{{6}} = \dfrac{{1{{,}}0\cdot{cc.dv_m:.2f}^2}}{{6}} = {_zse:.4f}\ \text{{m}}^3")
        st.latex(rf"M_r = \min(\alpha R_{{bt}} W_{{pl}};\ [\sigma]\,Z_{{se}}) "
                 rf"= {cc.Mr:.2f}\ \text{{kNm}}\quad(\text{{TCVN 5574 / 11823-5}})")
        st.latex(rf"V_r = \varphi\cdot\min(V_{{n1..4}}) "
                 rf"= 0{{,}}9\cdot\min(0{{,}}25 f'_c b_v d_v;\ 0{{,}}083\beta\sqrt{{f'_c}}\,b_v d_v;\ \ldots) "
                 rf"= {cc.Vr:.1f}\ \text{{kN}}")
        st.markdown(
            f"**Kiểm toán uốn:** M_tt = {cc.Mtt:.2f} ≤ M_r = {cc.Mr:.2f} kNm → "
            f"**{'Đạt' if cc.ok_moment else 'Không đạt'}** · "
            f"**Kiểm toán cắt:** V_tt = {cc.Vtt:.2f} ≤ V_r = {cc.Vr:.2f} kN → "
            f"**{'Đạt' if cc.ok_shear else 'Không đạt'}**")
    else:
        d1, d2, d3 = st.columns(3)
        d1.metric("Mô men yêu cầu M_tt", f"{cc.Mtt:.2f} kNm")
        d2.metric("Lực cắt yêu cầu V_tt", f"{cc.Vtt:.2f} kN")
        d3.metric("Cường độ kéo uốn [σ]", f"{cc.sigma_flex_MPa:.3f} MPa")
        st.info("Không bố trí lớp bê tông (d_v = 0 m) — chỉ tính nội lực yêu cầu. "
                "Nhập chiều dày lớp bê tông > 0 để kiểm toán khả năng chịu uốn/cắt (M_r, V_r).")

    st.markdown("**Giới hạn độ lún cố kết còn lại cho phép (cm) — TCCS 41:2022:**")
    lim_rows = []
    for road, vals in SETTLEMENT_LIMITS.items():
        if road == "header":
            continue
        lim_rows.append({"Loại cấp đường": road, **dict(zip(SETTLEMENT_LIMITS["header"], vals))})
    st.table(pd.DataFrame(lim_rows))

    st.divider()
    st.caption("Nguồn dữ liệu địa tầng và bộ thông số: hồ sơ tính móng trụ CDM LK2. "
               "Engine đã được đối chiếu khớp 100% với bản tính gốc.")
