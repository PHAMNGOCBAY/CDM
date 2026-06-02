"""
scripts/pages/qtt_page.py — UI tab Zone QTT (Quảng Trường Trung Tâm).

Page id: "qtt"
Nav label: "Zone QTT"

Cấu trúc 10 section:
  A. Tổng quan zone
  B. 6 hố khoan ND
  C. Bản đồ ranh giới + 162 điểm grid
  D. Stratigraphy viewer (chọn HK → 4-5 lớp + SPT)
  E. Trạng thái import DXF
  F. Tiêu chí thiết kế ΔS — TCCS 41
  G. Lc tối ưu per HK × ΔS
  H. Heatmap Lc grid 162 điểm
  I. Smoothness pair-wise check
  J. Phân vùng thiết kế (P1-P4)
  K. Xuất báo cáo Word + DXF zoning
"""
from __future__ import annotations
from pathlib import Path
import sys

_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def render() -> None:
    """Render trang QTT — đầy đủ tính toán + map + Word/DXF export."""
    import streamlit as st
    import pandas as pd
    import numpy as np
    import sqlite3
    import plotly.graph_objects as go
    import plotly.express as px
    import traceback
    from datetime import date

    from qtt_zone_data import (
        load_zone_meta, load_borehole_full, load_boundary,
        build_qtt_zone_meta_json, _db,
    )

    # ─── CSS toàn trang: text body 12pt, header in đậm, bảng zebra ───
    st.markdown("""
    <style>
    /* Body text + paragraph */
    div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stMarkdownContainer"] li,
    div[data-testid="stCaptionContainer"],
    div[data-testid="stText"] {
        font-size: 12pt !important;
        line-height: 1.45;
    }
    /* Headers — chỉ kích cỡ, đã sẵn bold */
    div[data-testid="stMarkdownContainer"] h1 { font-size: 18pt !important; font-weight: bold; }
    div[data-testid="stMarkdownContainer"] h2 { font-size: 15pt !important; font-weight: bold; }
    div[data-testid="stMarkdownContainer"] h3 { font-size: 13pt !important; font-weight: bold; }
    div[data-testid="stMarkdownContainer"] h4 { font-size: 12pt !important; font-weight: bold; }
    /* Metric */
    div[data-testid="stMetricValue"] { font-size: 18pt !important; font-weight: bold; }
    div[data-testid="stMetricLabel"] { font-size: 11pt !important; }
    div[data-testid="stMetricDelta"] { font-size: 10pt !important; }
    /* Table + DataFrame — TIÊU ĐỀ IN ĐẬM TRIỆT ĐỂ */
    div[data-testid="stTable"] table th,
    div[data-testid="stDataFrame"] thead th,
    div[data-testid="stDataFrame"] thead tr th,
    div[data-testid="stTable"] thead tr th,
    div[data-testid="stDataFrame"] th[role="columnheader"],
    div[data-testid="stTable"] th[role="columnheader"],
    .stDataFrame thead th,
    .stDataFrame [role="columnheader"],
    [data-testid="stDataFrameResizable"] thead th,
    [data-testid="stDataFrameResizable"] th {
        font-size: 12pt !important;
        font-weight: 700 !important;
        color: #111827 !important;
        background-color: #F3F4F6 !important;
    }
    /* Glide Data Grid headers (Streamlit ≥1.30) */
    .gdg-header,
    .gdg-cell.gdg-header,
    [class*="gdg-h"] {
        font-weight: 700 !important;
        font-size: 12pt !important;
    }
    div[data-testid="stTable"] table td,
    div[data-testid="stDataFrame"] tbody td {
        font-size: 12pt !important;
    }
    /* DataFrame Glide grid cell text */
    .gdg-cell-vertical-text-mode { font-size: 12pt !important; }
    /* Button, selectbox label, number_input label */
    label[data-testid="stWidgetLabel"] p,
    div[data-testid="stWidgetLabel"] p {
        font-size: 12pt !important;
        font-weight: 600;
    }
    /* Selectbox + number_input value */
    div[data-baseweb="select"] div,
    input[type="number"], input[type="text"] {
        font-size: 12pt !important;
    }
    /* Info / Success / Warning / Error box */
    div[data-testid="stAlert"] div,
    div[data-testid="stAlert"] p {
        font-size: 12pt !important;
    }
    /* Caption */
    div[data-testid="stCaptionContainer"] p {
        font-size: 11pt !important;
        font-style: italic;
    }
    /* Expander */
    summary p, details summary {
        font-size: 12pt !important;
        font-weight: 600;
    }
    /* Code blocks */
    code, pre {
        font-size: 11pt !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ════════ TỰ ĐỘNG REFRESH ════════
    try:
        from streamlit_autorefresh import st_autorefresh
        _HAS_AUTOREFRESH = True
    except ImportError:
        _HAS_AUTOREFRESH = False

    with st.sidebar:
        st.markdown("**Tự động refresh (Zone QTT)**")
        _ar_enable = st.checkbox(
            "Bật auto-refresh", value=False, key="_qtt_ar_enable",
            help="Tự động rerun trang theo chu kỳ — hữu ích khi data SQLite "
                 "đang được cập nhật ở tiến trình khác, hoặc khi đang sửa "
                 "code mà Google Drive sync trễ.",
        )
        _ar_interval = st.select_slider(
            "Chu kỳ (giây)",
            options=[5, 10, 15, 30, 60, 120, 300], value=30,
            key="_qtt_ar_interval",
            disabled=not _ar_enable,
        )
        if st.button("Refresh ngay", key="_qtt_ar_now",
                     use_container_width=True):
            st.rerun()

    if _ar_enable and _HAS_AUTOREFRESH:
        _ar_count = st_autorefresh(
            interval=_ar_interval * 1000,
            key="_qtt_autorefresh_counter",
        )
        st.sidebar.caption(
            f"Đang auto-refresh — chu kỳ {_ar_interval}s · "
            f"số lần đã rerun: {_ar_count}"
        )
    elif _ar_enable and not _HAS_AUTOREFRESH:
        st.sidebar.warning(
            "Chưa cài `streamlit-autorefresh`. "
            "Chạy: `pip install streamlit-autorefresh`"
        )

    # Helper: render bảng có HEADER IN ĐẬM (HTML thuần, không qua Glide).
    # st.dataframe dùng Glide Data Grid canvas — CSS không apply được.
    # → Phải render qua st.markdown với HTML to_html() của Styler.
    def _render_bold_table(df_in, **fmt_kwargs):
        try:
            s = df_in.style.set_table_styles([
                {"selector": "table",
                 "props": [("border-collapse", "collapse"),
                           ("width", "100%"),
                           ("margin", "0.5em 0 1em 0"),
                           ("font-family", "inherit"),
                           ("font-size", "12pt")]},
                {"selector": "thead th",
                 "props": [("font-weight", "700"),
                           ("font-size", "12pt"),
                           ("background-color", "#F3F4F6"),
                           ("color", "#111827"),
                           ("padding", "8px 10px"),
                           ("border", "1px solid #D1D5DB"),
                           ("text-align", "left")]},
                {"selector": "tbody td",
                 "props": [("padding", "6px 10px"),
                           ("border", "1px solid #D1D5DB"),
                           ("font-size", "12pt"),
                           ("color", "#111827")]},
                {"selector": "tbody tr:nth-child(even) td",
                 "props": [("background-color", "#F9FAFB")]},
                {"selector": "tbody tr:nth-child(odd) td",
                 "props": [("background-color", "#FFFFFF")]},
            ]).hide(axis="index")
            if fmt_kwargs:
                s = s.format(na_rep="—", **fmt_kwargs)
            html = s.to_html(escape=False)
            st.markdown(html, unsafe_allow_html=True)
        except Exception as _err:
            st.dataframe(df_in, hide_index=True, use_container_width=True)
            st.caption(f"(Fallback dùng st.dataframe vì lỗi Styler: {_err})")

    # Alias cũ để backward-compat — chuyển hướng tới render_bold_table
    def _bold_styler(df_in, **fmt_kwargs):
        _render_bold_table(df_in, **fmt_kwargs)
        return None  # caller không nên dùng giá trị trả về

    st.title("Zone QTT — Quảng Trường Trung Tâm")
    st.caption(
        "Phường An Khánh, Thành phố Thủ Đức, TP. Hồ Chí Minh · "
        "Hệ toạ độ VN-2000 / TM-3 106° (EPSG:9210)"
    )

    try:
        meta = load_zone_meta()

        # ═══════════════════════════════════════════════════════════════
        # CẤU TRÚC BÁO CÁO XỬ LÝ NỀN ĐẤT YẾU — TCCS 41:2022
        #   I. Tổng quan          (A)
        #   II. Số liệu khảo sát  (B, C, D, E, F, G)
        #   III. Tham số thiết kế (H)
        #   IV. Phân tích ứng suất(I)
        #   V. Tính lún + tối ưu Lc (J, K, L)
        #   VI. Phân vùng + kiểm tra (M, N, O)
        #   VII. Hiển thị 3D         (P)
        #   VIII. Xuất báo cáo        (Q)
        # ═══════════════════════════════════════════════════════════════

        # ════════ A. Tổng quan dự án ════════
        st.markdown("### A. Tổng quan zone")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Số hố khoan", meta["n_boreholes"])
        col2.metric("Đỉnh polygon ranh giới", meta["boundary_n_vertices"])
        col3.metric("Điểm grid tính toán", meta["grid"]["n"])
        col4.metric("H_soft TB (m)",
                    f"{meta['H_soft_stats']['avg']:.1f}",
                    f"min {meta['H_soft_stats']['min']:.1f} - "
                    f"max {meta['H_soft_stats']['max']:.1f}")

        if st.button("Cập nhật lại meta zone (rebuild JSON + SQLite)",
                     key="_qtt_refresh", type="secondary"):
            with st.spinner("Đang cập nhật..."):
                out = build_qtt_zone_meta_json()
                st.success(f"Đã cập nhật: {out}")

        st.divider()

        # ════════ B. Danh sách 6 hố khoan + DXF status ════════
        st.markdown("### B. Danh sách 6 hố khoan ND")
        df_bh = pd.DataFrame([
            {
                "HK": b["name"],
                "Northing (m)": b["N"],
                "Easting (m)": b["E"],
                "Cao độ TN (m)": b["elevation_m"],
                "Tổng độ sâu (m)": b.get("depth_m"),
                "H_soft (m)": b.get("H_soft_m"),
                "Selected": "Có" if b.get("selected") else "Không",
            }
            for b in meta["boreholes_summary"]
        ])
        _render_bold_table(df_bh)

        max_bh = max(meta["boreholes_summary"],
                      key=lambda b: b.get("H_soft_m") or 0)
        min_bh = min(meta["boreholes_summary"],
                      key=lambda b: b.get("H_soft_m") or float("inf"))
        c1, c2 = st.columns(2)
        c1.info(f"HK H_soft lớn nhất: **{max_bh['name']}** "
                f"({max_bh.get('H_soft_m', 0):.1f} m) — tới hạn thiết kế")
        c2.info(f"HK H_soft nhỏ nhất: **{min_bh['name']}** "
                f"({min_bh.get('H_soft_m', 0):.1f} m)")

        st.divider()

        # ════════ B2. Dự báo lún KHÔNG xử lý — TCCS 41 (§72 Task 8 + U + W) ════════
        st.markdown("### B2. Dự báo lún KHÔNG xử lý nền — S∞ + S(15 năm)")
        st.caption(
            "**Bốn phương án tải đắp cho nền chưa xử lý — so sánh kịch bản:**  \n"
            "- **PA1:** đắp từ TN lên TK của HK → $q_1 = \\gamma·(TK - TN)$  \n"
            "- **PA2 (§72 Task U):** đắp lan từ cao độ 0.0 → TK; tải = "
            "$\\gamma_{TB}·TN$ với $\\gamma_{TB} = 21.47$ kN/m³ "
            "(TB trọng số từ Áo đường + He + Hse, §72 V #1 fix)  \n"
            "- **PA3a (§72 Task W):** dùng **TK_max QTT** (cao nhất vùng) → "
            "$q_{3a} = \\gamma_{TB}·(TK_{max} - TN)$ — bao gồm **S1** (lún tức thì "
            "cát/đắp = $q·H_{cát}/E_{cát}$, $E_{cát}=20$ MPa) + **S2** (cố kết "
            "Terzaghi lớp bùn)  \n"
            "- **PA3b:** dùng TK_avg QTT; **PA3c:** dùng TN_max QTT (upper bound)  \n"
            "$S(15y)$ = $S_1$ + $S_2·U(T_{15y})$ với $C_v$ lab + "
            "**thoát nước 1 mặt** ($H_{drain} = H_{soft}$, đáy bùn kín — "
            "§72 Task X, đồng bộ §28). Nguồn: `cdm_zone_no_treat_predict`."
        )
        try:
            with sqlite3.connect(_db()) as con:
                con.row_factory = sqlite3.Row
                nt_rows = con.execute(
                    "SELECT n.bh_name, n.H_soft_m, "
                    "       n.S_inf_cm, n.S_15y_cm, n.U_15y, "
                    "       n.Cv_avg_m2_year, n.method, "
                    "       n.H_fill_pa2_m, n.q_pa2_kPa, "
                    "       n.S_inf_pa2_cm, n.S_15y_pa2_cm, n.U_15y_pa2, "
                    "       n.q_pa3a_kPa, n.S_total_pa3a_cm, n.S_15y_pa3a_cm, "
                    "       n.q_pa3b_kPa, n.S_total_pa3b_cm, n.S_15y_pa3b_cm, "
                    "       n.q_pa3c_kPa, n.S_total_pa3c_cm, n.S_15y_pa3c_cm, "
                    "       n.cc_source, n.cc_borrowed, n.cc_dist_m, "
                    "       b.elevation_m AS tn "
                    "FROM cdm_zone_no_treat_predict n "
                    "JOIN boreholes b ON b.name = n.bh_name "
                    "WHERE n.zone_code='QTT' ORDER BY n.bh_name"
                ).fetchall()
            df_nt = pd.DataFrame([
                {
                    "HK": r["bh_name"],
                    "TN (m)": r["tn"],
                    "H_soft (m)": r["H_soft_m"],
                    "Cc nguồn": (f"{r['cc_source']} (mượn d={r['cc_dist_m']:.0f}m)"
                                  if r["cc_borrowed"]
                                  else r["cc_source"] or r["bh_name"]),
                    "q PA1": 40.8,
                    "q PA2": r["q_pa2_kPa"],
                    "q PA3a": r["q_pa3a_kPa"],
                    "q PA3b": r["q_pa3b_kPa"],
                    "q PA3c": r["q_pa3c_kPa"],
                    "S∞ PA1": r["S_inf_cm"],
                    "S∞ PA2": r["S_inf_pa2_cm"],
                    "S∞ PA3a": r["S_total_pa3a_cm"],
                    "S∞ PA3b": r["S_total_pa3b_cm"],
                    "S∞ PA3c": r["S_total_pa3c_cm"],
                    "S(15y) PA1": r["S_15y_cm"],
                    "S(15y) PA2": r["S_15y_pa2_cm"],
                    "S(15y) PA3a": r["S_15y_pa3a_cm"],
                    "S(15y) PA3b": r["S_15y_pa3b_cm"],
                    "S(15y) PA3c": r["S_15y_pa3c_cm"],
                }
                for r in nt_rows
            ])
            if not df_nt.empty:
                _render_bold_table(df_nt)
                # Biểu đồ song song PA1 + PA2 + PA3a/b/c (§72 Task 7 + U + W)
                fig_nt = go.Figure()
                fig_nt.add_trace(go.Bar(
                    x=df_nt["HK"], y=df_nt["S∞ PA1"],
                    name="S∞ PA1 (TN→TK)", marker_color="#D32F2F",
                    text=[f"{v:.0f}" if v else "" for v in df_nt["S∞ PA1"]],
                    textposition="outside",
                ))
                fig_nt.add_trace(go.Bar(
                    x=df_nt["HK"], y=df_nt["S∞ PA2"],
                    name="S∞ PA2 (0.0→TN)", marker_color="#AD1457",
                    text=[f"{v:.0f}" if v else "" for v in df_nt["S∞ PA2"]],
                    textposition="outside",
                ))
                fig_nt.add_trace(go.Bar(
                    x=df_nt["HK"], y=df_nt["S∞ PA3a"],
                    name="S∞ PA3a (TK_max QTT)", marker_color="#6A1B9A",
                    text=[f"{v:.0f}" if v else "" for v in df_nt["S∞ PA3a"]],
                    textposition="outside",
                ))
                fig_nt.add_trace(go.Bar(
                    x=df_nt["HK"], y=df_nt["S∞ PA3c"],
                    name="S∞ PA3c (TN_max QTT)", marker_color="#00838F",
                    text=[f"{v:.0f}" if v else "" for v in df_nt["S∞ PA3c"]],
                    textposition="outside",
                ))
                fig_nt.add_trace(go.Bar(
                    x=df_nt["HK"], y=df_nt["S(15y) PA1"],
                    name="S(15y) PA1", marker_color="#F57F17",
                    text=[f"{v:.0f}" if v else "" for v in df_nt["S(15y) PA1"]],
                    textposition="outside",
                ))
                fig_nt.add_trace(go.Bar(
                    x=df_nt["HK"], y=df_nt["S(15y) PA3a"],
                    name="S(15y) PA3a", marker_color="#9C27B0",
                    text=[f"{v:.0f}" if v else "" for v in df_nt["S(15y) PA3a"]],
                    textposition="outside",
                ))
                # Đường tham chiếu TCCS 41 limits
                for lim, col in [(10, "#2E7D32"), (20, "#1565C0"),
                                  (30, "#5D4037"), (40, "#6A1B9A")]:
                    fig_nt.add_hline(y=lim, line=dict(color=col, dash="dash",
                                                      width=1),
                                      annotation_text=f"ΔS={lim}",
                                      annotation_position="right",
                                      annotation_font=dict(size=10, color=col))
                fig_nt.update_layout(
                    title=dict(text="<b>Lún KHÔNG xử lý 4 phương án — so với giới hạn TCCS 41</b>",
                                font=dict(size=13)),
                    barmode="group", height=520, plot_bgcolor="white",
                    xaxis_title="Hố khoan", yaxis_title="Lún (cm)",
                    legend=dict(orientation="h", y=-0.22),
                )
                st.plotly_chart(fig_nt, use_container_width=True)
                # Cảnh báo HK có S∞ PA bất kỳ vượt 100cm
                df_max = df_nt[["HK", "S∞ PA1", "S∞ PA2",
                                  "S∞ PA3a", "S∞ PA3c"]].copy()
                df_max["S∞ max"] = df_max[["S∞ PA1", "S∞ PA2",
                                              "S∞ PA3a", "S∞ PA3c"]
                                            ].fillna(0).max(axis=1)
                over = df_max[df_max["S∞ max"] > 100]
                if not over.empty:
                    st.error(
                        f"**{len(over)} HK có lún (worst phương án) vượt 100 cm:** "
                        + ", ".join(f"{r['HK']} ({r['S∞ max']:.0f} cm)"
                                     for _, r in over.iterrows()) + ". "
                        "→ BẮT BUỘC xử lý CDM xuyên hết bùn."
                    )
            else:
                st.info("Chưa có dữ liệu S_no_treatment. Chạy: "
                         "`python scripts/save_no_treat_predict.py`")
        except Exception as _exc:
            st.warning(f"Không tải được B2: {_exc}")

        st.divider()

        # ════════ B3. Lún nền ĐÃ xử lý CDM — S1 + S2 × tất cả ΔS (§72 Task AA) ════════
        st.markdown("### B3. Lún nền ĐÃ xử lý CDM — S1 + S2 × tất cả ΔS")
        st.caption(
            "Thống kê **S1** (lún đàn hồi khối gia cố CDM, TCVN 9403 Phụ lục C) "
            "+ **S2** (lún cố kết Terzaghi lớp bùn dưới mũi cọc, §71) + "
            "**Lc tối ưu** cho 6 HK × 6 ΔS cho phép (10/15/20/25/30/40 cm). "
            "So sánh trực tiếp với B2 (chưa xử lý) để thấy hiệu quả CDM. "
            "Nguồn: `cdm_zone_design_results`."
        )
        try:
            with sqlite3.connect(_db()) as con:
                con.row_factory = sqlite3.Row
                cdm_rows = con.execute(
                    "SELECT bh_name, delta_S_cm, Lc_m, S1_cm, S2_cm, "
                    "       S_total_cm, ok, penetrates_full "
                    "FROM cdm_zone_design_results "
                    "WHERE zone_code='QTT' ORDER BY bh_name, delta_S_cm"
                ).fetchall()
            df_cdm = pd.DataFrame([dict(r) for r in cdm_rows])
            if not df_cdm.empty:
                # 4 ma trận: S1, S2, S_total, Lc
                for metric, label, color_scale in [
                    ("S1_cm", "S1 — lún khối gia cố CDM (cm)", "Blues"),
                    ("S2_cm", "S2 — lún cố kết dưới mũi (cm)", "Oranges"),
                    ("S_total_cm", "S_total = S1 + S2 (cm)", "RdYlGn_r"),
                    ("Lc_m", "Lc tối ưu (m)", "Viridis"),
                ]:
                    st.markdown(f"**Ma trận {label}:**")
                    pivot = df_cdm.pivot(index="bh_name", columns="delta_S_cm",
                                          values=metric)
                    pivot.columns = [f"ΔS={int(c)}cm" for c in pivot.columns]
                    pivot.index.name = "Hố khoan"
                    _render_bold_table(pivot.reset_index())
                    # Heatmap
                    fig_hm = go.Figure(data=go.Heatmap(
                        z=pivot.values,
                        x=pivot.columns.tolist(),
                        y=pivot.index.tolist(),
                        colorscale=color_scale,
                        text=[[f"{v:.1f}" if pd.notna(v) else "—" for v in row]
                              for row in pivot.values],
                        texttemplate="%{text}",
                        textfont=dict(size=11),
                        colorbar=dict(title=metric),
                    ))
                    fig_hm.update_layout(
                        title=dict(text=f"<b>{label}</b>", font=dict(size=13)),
                        height=320, font=dict(size=11),
                        margin=dict(l=80, r=30, t=60, b=40),
                    )
                    st.plotly_chart(fig_hm, use_container_width=True)

                # Bar chart so sánh S1 vs S2 tại ΔS=30 cm (TCCS 41 cao tốc thường)
                st.markdown("**So sánh S1 vs S2 tại ΔS = 30 cm (cao tốc thường):**")
                df_30 = df_cdm[df_cdm["delta_S_cm"] == 30.0].copy()
                if not df_30.empty:
                    fig_bar = go.Figure()
                    fig_bar.add_trace(go.Bar(
                        x=df_30["bh_name"], y=df_30["S1_cm"],
                        name="S1 (khối gia cố)", marker_color="#1565C0",
                        text=[f"{v:.1f}" for v in df_30["S1_cm"]],
                        textposition="outside",
                    ))
                    fig_bar.add_trace(go.Bar(
                        x=df_30["bh_name"], y=df_30["S2_cm"],
                        name="S2 (cố kết dưới mũi)", marker_color="#F57F17",
                        text=[f"{v:.1f}" for v in df_30["S2_cm"]],
                        textposition="outside",
                    ))
                    fig_bar.add_hline(y=30, line=dict(color="#2E7D32",
                                                       dash="dash", width=1.5),
                                       annotation_text="ΔS=30 cm (giới hạn)",
                                       annotation_position="right")
                    fig_bar.update_layout(
                        title=dict(text="<b>S1 + S2 per HK tại ΔS=30 cm</b>",
                                    font=dict(size=13)),
                        barmode="stack", height=420, plot_bgcolor="white",
                        xaxis_title="Hố khoan",
                        yaxis_title="Lún (cm)",
                        legend=dict(orientation="h", y=-0.18),
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Chưa có dữ liệu cdm_zone_design_results cho QTT.")
        except Exception as _exc:
            st.warning(f"Không tải được B3: {_exc}")

        st.divider()

        # ════════ C. Bản đồ zone — polygon + 162 điểm grid ════════
        st.markdown("### C. Bản đồ zone — Polygon + 162 điểm grid")
        fig_map = go.Figure()
        bd = load_boundary()
        bd_x = [v["easting_m"] for v in bd] + [bd[0]["easting_m"]]
        bd_y = [v["northing_m"] for v in bd] + [bd[0]["northing_m"]]
        fig_map.add_trace(go.Scatter(
            x=bd_x, y=bd_y, mode="lines+markers",
            line=dict(color="#1565C0", width=3),
            marker=dict(size=8, color="#1565C0"),
            name="Ranh giới QTT",
            fill="toself", fillcolor="rgba(21,101,192,0.08)",
        ))
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            grid_rows = con.execute("""
                SELECT easting_m AS E, northing_m AS N, elev_des_m, elev_nat_m
                FROM qtt_elevation_points ORDER BY northing_m, easting_m
            """).fetchall()
        gx = [r["E"] for r in grid_rows]
        gy = [r["N"] for r in grid_rows]
        gz = [r["elev_des_m"] for r in grid_rows]
        fig_map.add_trace(go.Scatter(
            x=gx, y=gy, mode="markers",
            marker=dict(size=5, color=gz, colorscale="Viridis",
                        showscale=True, colorbar=dict(title="Cao độ TK (m)")),
            name="Grid 162 điểm",
            text=[f"E={x:.1f}<br>N={y:.1f}<br>TK={z:.2f}m"
                  for x, y, z in zip(gx, gy, gz)],
            hoverinfo="text",
        ))
        bhs = meta["boreholes_summary"]
        fig_map.add_trace(go.Scatter(
            x=[b["E"] for b in bhs], y=[b["N"] for b in bhs],
            mode="markers+text",
            marker=dict(size=18, color="white", symbol="diamond",
                        line=dict(color="black", width=2)),
            text=[b["name"] for b in bhs], textposition="top center",
            textfont=dict(size=11, color="black"),
            name="Hố khoan ND",
        ))
        fig_map.update_layout(
            xaxis=dict(title="Easting (m)", scaleanchor="y", scaleratio=1),
            yaxis=dict(title="Northing (m)"),
            height=600, showlegend=True,
            title="Bản đồ Zone QTT",
        )
        st.plotly_chart(fig_map, use_container_width=True)

        st.divider()

        # ════════ D. Trắc dọc địa chất qua 6 HK (PCA-SVD) ════════
        # Đặt ngay sau A để có overview địa chất toàn zone trước khi đi vào chi tiết
        st.markdown("### D. Trắc dọc địa chất qua 6 hố khoan (PCA-SVD chainage)")
        st.caption(
            "Cột địa tầng tô màu theo ký hiệu lớp. Nhãn bên phải mỗi đáy lớp là "
            "**cao độ** (m) để khớp với trục Y; số trong ngoặc là độ sâu từ mặt đất. "
            "Đường nâu = mặt đất tự nhiên; đường đen chấm = đáy hố khoan; "
            "đường đỏ = đáy lớp yếu."
        )
        from qtt_charts import (
            cross_section_geo, cdm_tip_profile, stress_chart_with_10pct,
            layer_params_chart, floating_pile_warning_table,
        )
        # Load layers per HK — dùng chung cho A2, N, O, P sau này
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            layers_by_bh = {}
            for b in meta["boreholes_summary"]:
                ls = con.execute("""
                    SELECT symbol, depth_top_m, depth_bot_m, thickness_m, description
                    FROM layers
                    WHERE borehole_id = (SELECT id FROM boreholes WHERE name=?)
                    ORDER BY depth_top_m
                """, (b["name"],)).fetchall()
                layers_by_bh[b["name"]] = [dict(r) for r in ls]
            # Cao độ thiết kế tại nearest grid point cho mỗi HK
            grid_for_des = con.execute("""
                SELECT easting_m AS E, northing_m AS N, elev_des_m
                FROM qtt_elevation_points WHERE elev_des_m IS NOT NULL
            """).fetchall()
        design_elev_by_bh = {}
        for b in meta["boreholes_summary"]:
            best_d = float("inf"); best_z = None
            for r in grid_for_des:
                dx = b["E"] - r["E"]; dy = b["N"] - r["N"]
                d = (dx * dx + dy * dy) ** 0.5
                if d < best_d:
                    best_d = d; best_z = r["elev_des_m"]
            if best_z is not None:
                design_elev_by_bh[b["name"]] = best_z
        fig_cs = cross_section_geo(
            meta["boreholes_summary"], layers_by_bh,
            design_elev_by_bh=design_elev_by_bh,
        )
        st.plotly_chart(fig_cs, use_container_width=True)

        st.divider()

        # ════════ E. Địa tầng + SPT + e₀ + MNN — 6 HK ════════
        st.markdown("### E. Địa tầng + SPT + e₀ + MNN — Tất cả 6 hố khoan")
        st.caption(
            "Mỗi panel: cột địa tầng (tô màu theo ký hiệu) + cao độ đỉnh/đáy lớp "
            "+ chỉ số SPT N + hệ số rỗng e₀ (đỏ nếu >1) + mực nước ngầm (MNN). "
            "Bố cục 3 HK / hàng."
        )

        # Import chart helper
        from qtt_charts import bh_full_panel

        # Load layers + SPT + lab cho 6 HK
        bh_list = sorted(meta["boreholes_summary"], key=lambda b: b["name"])
        full_data = {}
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            for b in bh_list:
                ls = con.execute("""
                    SELECT symbol, depth_top_m, depth_bot_m, thickness_m, description
                    FROM layers
                    WHERE borehole_id = (SELECT id FROM boreholes WHERE name=?)
                    ORDER BY depth_top_m
                """, (b["name"],)).fetchall()
                sp = con.execute("""
                    SELECT depth_m, N, N1, N2, N3 FROM spt_values
                    WHERE borehole_id = (SELECT id FROM boreholes WHERE name=?)
                    ORDER BY depth_m
                """, (b["name"],)).fetchall()
                lab = con.execute("""
                    SELECT depth_from_m, depth_to_m, symbol_tcvn, e0
                    FROM lab_tests
                    WHERE borehole_id = (SELECT id FROM boreholes WHERE name=?)
                """, (b["name"],)).fetchall()
                full_data[b["name"]] = {
                    "bh": b,
                    "layers": [dict(r) for r in ls],
                    "spt": [dict(r) for r in sp],
                    "lab": [dict(r) for r in lab],
                }

        # Mực nước ngầm — input theo CAO ĐỘ tuyệt đối
        gwl_col1, gwl_col2 = st.columns([1, 3])
        with gwl_col1:
            gwl_elev = st.number_input(
                "MNN — Cao độ (m)", min_value=-10.0, max_value=10.0,
                value=0.0, step=0.5, key="_qtt_gwl",
                help="Cao độ mực nước ngầm tuyệt đối (so với mốc Quốc gia). "
                     "Áp chung cho tất cả 6 HK QTT. Độ sâu MNN từ mặt đất "
                     "tự tính riêng cho mỗi HK = elev_TN - gwl_elev.",
            )
        with gwl_col2:
            st.metric("Tổng HK", f"{len(bh_list)}",
                      f"{sum(1 for b in bh_list if (b.get('H_soft_m') or 0)>10)} có H_soft >10m")

        # 6 HK chia 3 cột × 2 hàng
        for row_start in range(0, len(bh_list), 3):
            row_bhs = bh_list[row_start:row_start + 3]
            cols = st.columns(len(row_bhs))
            for col, b in zip(cols, row_bhs):
                with col:
                    data = full_data[b["name"]]
                    if not data["layers"]:
                        st.warning(f"HK {b['name']}: chưa có địa tầng "
                                   f"(template DXF khác — cần parse manual)")
                        continue
                    fig_panel = bh_full_panel(
                        bh=data["bh"],
                        layers=data["layers"],
                        spt=data["spt"],
                        lab_rows=data["lab"],
                        gwl_elev_m=gwl_elev,
                    )
                    st.plotly_chart(fig_panel, use_container_width=True,
                                     key=f"_qtt_panel_{b['name']}")

        # §72 Task 3 — Trải phẳng: thay expander bằng markdown subhead
        st.markdown("**Bảng địa tầng tổng hợp 6 HK:**")
        if True:
            rows_all = []
            for b in bh_list:
                for L in full_data[b["name"]]["layers"]:
                    rows_all.append({
                        "HK": b["name"],
                        "Lớp": L["symbol"],
                        "Top (m)": L["depth_top_m"],
                        "Bot (m)": L["depth_bot_m"],
                        "Dày (m)": L["thickness_m"],
                        "Cao độ đáy (m)": round(
                            b["elevation_m"] - L["depth_bot_m"], 2),
                        "Mô tả": L.get("description", ""),
                    })
            if rows_all:
                st.dataframe(pd.DataFrame(rows_all), hide_index=True,
                              use_container_width=True)

        st.divider()

        # ════════ F. Thống kê thí nghiệm nén cố kết ════════
        st.markdown("### F. Thống kê thí nghiệm nén cố kết — QTT")
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            # Per HK
            con_rows = con.execute("""
                SELECT b.name AS bh,
                       COUNT(*) AS n_total,
                       SUM(CASE WHEN lt.Cc IS NOT NULL THEN 1 ELSE 0 END) AS n_cc,
                       SUM(CASE WHEN lt.Cs IS NOT NULL THEN 1 ELSE 0 END) AS n_cs,
                       SUM(CASE WHEN lt.PC_kPa IS NOT NULL THEN 1 ELSE 0 END) AS n_pc,
                       SUM(CASE WHEN lt.Cv_cm2s IS NOT NULL THEN 1 ELSE 0 END) AS n_cv,
                       SUM(CASE WHEN lt.k_cm_s IS NOT NULL THEN 1 ELSE 0 END) AS n_k,
                       SUM(CASE WHEN lt.a12_cm2kgf IS NOT NULL THEN 1 ELSE 0 END) AS n_a12,
                       SUM(CASE WHEN lt.e0 > 1 THEN 1 ELSE 0 END) AS n_e_gt1
                FROM lab_tests lt JOIN boreholes b ON b.id = lt.borehole_id
                WHERE b.name LIKE 'ND-%'
                GROUP BY b.name ORDER BY b.name
            """).fetchall()
        df_con = pd.DataFrame([dict(r) for r in con_rows])

        if not df_con.empty:
            df_con_display = df_con.rename(columns={
                "bh": "HK", "n_total": "Tổng mẫu",
                "n_cc": "Có Cc", "n_cs": "Có Cs", "n_pc": "Có PC",
                "n_cv": "Có Cv", "n_k": "Có k", "n_a12": "Có a₁₂",
                "n_e_gt1": "Mẫu e₀ > 1",
            })
            st.markdown("**Số mẫu có thí nghiệm cố kết theo HK:**")
            _render_bold_table(df_con_display)

            # Cảnh báo HK thiếu
            missing = df_con[df_con["n_cc"] == 0]
            if not missing.empty:
                st.warning(
                    f"**{len(missing)} HK CHƯA có thí nghiệm nén cố kết:** "
                    f"{', '.join(missing['bh'].tolist())} — cần bổ sung "
                    f"hoặc mượn từ HK gần nhất (xem §15 fallback rule)."
                )

            # Phổ giá trị Cc/PC/Cv (per HK có data)
            with sqlite3.connect(_db()) as con:
                con.row_factory = sqlite3.Row
                stats_rows = con.execute("""
                    SELECT b.name AS bh,
                           AVG(lt.Cc) AS Cc_avg, MIN(lt.Cc) AS Cc_min, MAX(lt.Cc) AS Cc_max,
                           AVG(lt.PC_kPa) AS PC_avg, MIN(lt.PC_kPa) AS PC_min, MAX(lt.PC_kPa) AS PC_max,
                           AVG(lt.Cv_cm2s) AS Cv_avg, MIN(lt.Cv_cm2s) AS Cv_min, MAX(lt.Cv_cm2s) AS Cv_max,
                           AVG(lt.Cs) AS Cs_avg
                    FROM lab_tests lt JOIN boreholes b ON b.id = lt.borehole_id
                    WHERE b.name LIKE 'ND-%' AND lt.Cc IS NOT NULL
                    GROUP BY b.name ORDER BY b.name
                """).fetchall()
            df_stat = pd.DataFrame([dict(r) for r in stats_rows])
            if not df_stat.empty:
                st.markdown("**Phổ giá trị Cc / PC / Cv / Cs (HK có data):**")
                fmts = {
                    "Cc_avg": "{:.3f}", "Cc_min": "{:.3f}", "Cc_max": "{:.3f}",
                    "PC_avg": "{:.0f}", "PC_min": "{:.0f}", "PC_max": "{:.0f}",
                    "Cv_avg": "{:.5f}", "Cv_min": "{:.5f}", "Cv_max": "{:.5f}",
                    "Cs_avg": "{:.3f}",
                }
                st.dataframe(
                    df_stat.style.format(fmts, na_rep="—"),
                    hide_index=True, use_container_width=True,
                )

        st.divider()

        # ════════ G. Chỉ tiêu cơ lý các lớp đất ════════
        st.markdown("### G. Chỉ tiêu cơ lý các lớp đất — QTT")
        st.caption("Lớp đất có **hệ số rỗng e₀ > 1** được tô đậm (đặc trưng đất yếu).")
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            soil_stats = con.execute("""
                SELECT lt.symbol_tcvn AS symbol,
                       COUNT(*) AS n,
                       AVG(lt.w_pct) AS w,
                       AVG(lt.gamma_kNm3) AS gamma,
                       AVG(lt.gamma_dry_kNm3) AS gamma_dry,
                       AVG(lt.gamma_sub_kNm3) AS gamma_sub,
                       AVG(lt.Gs) AS Gs,
                       AVG(lt.Sr_pct) AS Sr,
                       AVG(lt.e0) AS e0,
                       AVG(lt.wL_pct) AS wL,
                       AVG(lt.wP_pct) AS wP,
                       AVG(lt.Ip) AS Ip,
                       AVG(lt.phi_deg) AS phi,
                       AVG(lt.c_kPa) AS c,
                       AVG(lt.Cu_UU_kPa) AS Cu_UU,
                       AVG(lt.phi_UU_deg) AS phi_UU,
                       AVG(lt.Cc) AS Cc, AVG(lt.Cs) AS Cs,
                       AVG(lt.PC_kPa) AS PC,
                       AVG(lt.Cv_cm2s) AS Cv,
                       AVG(lt.a12_cm2kgf) AS a12,
                       AVG(lt.k_cm_s) AS k
                FROM lab_tests lt JOIN boreholes b ON b.id = lt.borehole_id
                WHERE b.name LIKE 'ND-%' AND lt.symbol_tcvn IS NOT NULL
                  AND lt.symbol_tcvn != ''
                GROUP BY lt.symbol_tcvn
                ORDER BY AVG(lt.depth_from_m)
            """).fetchall()
        df_soil = pd.DataFrame([dict(r) for r in soil_stats])

        if not df_soil.empty:
            df_disp = df_soil.rename(columns={
                "symbol": "Lớp",
                "w": "w (%)", "gamma": "γ", "gamma_dry": "γ_dry",
                "gamma_sub": "γ_sub", "Gs": "Gs", "Sr": "Sr (%)",
                "e0": "e₀", "wL": "wL (%)", "wP": "wP (%)", "Ip": "Ip",
                "phi": "φ (°)", "c": "c (kPa)",
                "Cu_UU": "Cu_UU (kPa)", "phi_UU": "φ_UU (°)",
                "Cc": "Cc", "Cs": "Cs", "PC": "PC (kPa)",
                "Cv": "Cv (cm²/s)", "a12": "a₁₋₂", "k": "k (cm/s)",
            })

            # Style: bold rows where e₀ > 1
            def highlight_soft(row):
                e0_val = row["e₀"]
                if e0_val is not None and e0_val > 1.0:
                    return ["font-weight: bold; background-color: #FFE0B2"] * len(row)
                return [""] * len(row)

            fmts = {
                "w (%)": "{:.1f}", "γ": "{:.1f}", "γ_dry": "{:.1f}",
                "γ_sub": "{:.1f}", "Gs": "{:.2f}", "Sr (%)": "{:.1f}",
                "e₀": "{:.3f}", "wL (%)": "{:.1f}", "wP (%)": "{:.1f}",
                "Ip": "{:.1f}", "φ (°)": "{:.2f}", "c (kPa)": "{:.1f}",
                "Cu_UU (kPa)": "{:.1f}", "φ_UU (°)": "{:.2f}",
                "Cc": "{:.3f}", "Cs": "{:.3f}", "PC (kPa)": "{:.0f}",
                "Cv (cm²/s)": "{:.5f}", "a₁₋₂": "{:.3f}",
                "k (cm/s)": "{:.2e}",
            }

            styled = (df_disp.style
                      .format(fmts, na_rep="—")
                      .apply(highlight_soft, axis=1))
            st.dataframe(styled, hide_index=True, use_container_width=True)

            # Diễn giải
            n_soft = (df_soil["e0"] > 1.0).sum()
            soft_syms = df_soil[df_soil["e0"] > 1.0]["symbol"].tolist()
            st.info(
                f"**Lớp đất yếu (e₀ > 1):** {n_soft} lớp — "
                f"{', '.join(soft_syms) if soft_syms else '(không có)'}. "
                f"Đây là vùng cần xử lý CDM trọng tâm."
            )

            # Biểu đồ so sánh e₀ + Cu
            c1, c2 = st.columns(2)
            with c1:
                fig_e = go.Figure()
                colors_e = ["#C62828" if (v is not None and v > 1) else "#2E7D32"
                             for v in df_soil["e0"]]
                fig_e.add_trace(go.Bar(
                    x=df_soil["symbol"],
                    y=df_soil["e0"].fillna(0),
                    marker=dict(color=colors_e),
                    text=[f"{v:.2f}" if v else "—" for v in df_soil["e0"]],
                    textposition="outside",
                ))
                fig_e.add_hline(y=1.0, line_dash="dash", line_color="#F57C00",
                                 annotation_text="e₀ = 1 (ranh giới sét yếu)")
                fig_e.update_layout(
                    title="Hệ số rỗng e₀ trung bình theo lớp đất",
                    xaxis_title="Ký hiệu lớp", yaxis_title="e₀",
                    height=380,
                )
                st.plotly_chart(fig_e, use_container_width=True)
            with c2:
                fig_cu = go.Figure()
                fig_cu.add_trace(go.Bar(
                    x=df_soil["symbol"],
                    y=df_soil["Cu_UU"].fillna(0),
                    marker_color="#1565C0",
                    text=[f"{v:.1f}" if v else "—" for v in df_soil["Cu_UU"]],
                    textposition="outside",
                ))
                fig_cu.update_layout(
                    title="Cường độ kháng cắt không thoát nước Cu_UU",
                    xaxis_title="Ký hiệu lớp", yaxis_title="Cu (kPa)",
                    height=380,
                )
                st.plotly_chart(fig_cu, use_container_width=True)

        st.divider()

        # (Section "Trắc dọc địa chất" đã được di chuyển lên đầu, ngay sau A)
        # ════════ H. Tiêu chí thiết kế — TCCS 41 Bảng 1 + Bảng E.1 ════════
        st.markdown("### H. Tiêu chí thiết kế — TCCS 41 Bảng 1 + Bảng E.1")
        st.caption(
            "Bảng tổng hợp **đầy đủ tiêu chí** TCCS 41:2022 — KHÔNG đề xuất "
            "mức nào, để kỹ sư tự đánh giá theo điều kiện thực tế dự án. "
            "Các mục J-O sẽ tính cho **MỌI ΔS** và **MỌI ngưỡng độ bằng phẳng**."
        )

        # H.1 — Bảng 1: Giới hạn độ lún cố kết còn lại ΔS (cm)
        st.markdown("**H.1. TCCS 41 Bảng 1 — Giới hạn độ lún cố kết còn lại ΔS (cm):**")
        ds_table = [
            {"Cấp đường": "Cao tốc / ≥80 km/h / A1",
             "Gần mố cầu (cm)": 10, "Hai bên cống (cm)": 20,
             "Đoạn thông thường (cm)": 30},
            {"Cấp đường": "≤60 km/h / A1",
             "Gần mố cầu (cm)": 20, "Hai bên cống (cm)": 30,
             "Đoạn thông thường (cm)": 40},
        ]
        df_ds = pd.DataFrame(ds_table)
        _render_bold_table(df_ds)
        st.caption(
            "Áp dụng cho tuổi thọ t = 15 năm (mặt đường mềm) hoặc 30 năm "
            "(mặt đường cứng). Công thức (36) TCCS 41: ΔS = S_c · (1 − U_t)."
        )

        # H.2 — Bảng E.1: Giới hạn độ bằng phẳng i = 1/N
        st.markdown("**H.2. TCCS 41 Bảng E.1 — Độ bằng phẳng i dọc tim đường:**")
        try:
            with sqlite3.connect(_db()) as con:
                con.row_factory = sqlite3.Row
                sm_rows = con.execute("""
                    SELECT road_class_code, structure, speed_kmh, i_denominator
                    FROM tccs41_smoothness_limits
                    ORDER BY road_class_code, structure, speed_kmh
                """).fetchall()
            sm_rows = [dict(r) for r in sm_rows]
        except sqlite3.OperationalError:
            sm_rows = []

        if sm_rows:
            # Pivot: row = (road_class, structure), col = speed
            speeds = sorted({r["speed_kmh"] for r in sm_rows})
            pivot_rows = []
            seen = set()
            for r in sm_rows:
                key = (r["road_class_code"], r["structure"])
                if key in seen:
                    continue
                seen.add(key)
                pivot = {
                    "Cấp đường": ("Cao tốc" if r["road_class_code"] == "cao_toc"
                                    else "Cấp I-IV"),
                    "Công trình": "Cầu" if r["structure"] == "cau" else "Cống",
                }
                for v in speeds:
                    val = next((x["i_denominator"] for x in sm_rows
                                 if x["road_class_code"] == r["road_class_code"]
                                 and x["structure"] == r["structure"]
                                 and x["speed_kmh"] == v), None)
                    pivot[f"v={v} km/h"] = f"1/{int(val)}" if val else "—"
                pivot_rows.append(pivot)
            df_sm = pd.DataFrame(pivot_rows)
            _render_bold_table(df_sm)
        else:
            # Fallback bảng TCCS 41 E.1 cứng nếu DB chưa có
            df_sm = pd.DataFrame([
                {"Cấp đường": "Cao tốc", "Công trình": "Cầu",
                 "v=60": "1/175", "v=80": "1/200",
                 "v=100": "1/250", "v=120": "1/250"},
                {"Cấp đường": "Cao tốc", "Công trình": "Cống",
                 "v=60": "1/150", "v=80": "1/150",
                 "v=100": "1/150", "v=120": "1/150"},
                {"Cấp đường": "Cấp I-IV", "Công trình": "Cầu",
                 "v=60": "1/150", "v=80": "1/175",
                 "v=100": "1/200", "v=120": "1/200"},
                {"Cấp đường": "Cấp I-IV", "Công trình": "Cống",
                 "v=60": "1/125", "v=80": "1/150",
                 "v=100": "1/150", "v=120": "1/150"},
            ])
            _render_bold_table(df_sm)
        st.caption(
            "Cho phép tạo vồng trước với độ dốc tối đa **1/125**. "
            "Mục N (kiểm tra bằng phẳng) sẽ áp tất cả các ngưỡng "
            "i = 1/100, 1/125, 1/150, 1/175, 1/200, 1/250."
        )

        # Đặt biến chung — KHÔNG yêu cầu user chọn
        # Mặc định cho việc hiển thị bản đồ 1 ΔS = 30 cm (đoạn thường cao tốc)
        # Các mục J-O đều tính cho TẤT CẢ 4 ΔS
        dS_pick = 30  # default cho heatmap M, smoothness N, zoning O
        # criteria placeholder cho Word export
        road_class = ("cat1", "Cao tốc / ≥80 km/h / A1")
        position = ("general", "Đoạn thông thường")
        dS_limit = 30.0

        st.divider()

        # ════════ I. Biểu đồ ứng suất + vùng ảnh hưởng lún 10% ════════
        st.markdown("### I. Biểu đồ ứng suất σ'v0 + Δσ_CDM + ngưỡng 10% — 6 hố khoan")
        st.caption(
            "**Tải trọng CDM q = 40.8 kPa**. Mỗi biểu đồ so sánh 2 phương án "
            "tính Δσ dưới mũi cọc CDM:  \n"
            "- **Phương án 1D (đỏ đứt)** — Δσ = q không đổi theo độ sâu "
            "(thiên về an toàn, được dùng để xác định d_stop chuẩn TCCS 41)  \n"
            "- **Phương án Boussinesq (xanh ngọc chấm) — §72 Task S** — "
            "Δσ giảm dần theo độ sâu z dưới mũi theo công thức "
            "Δσ(z) = q · B² / (B+z)² (2:1 method, B = spacing 1.8m)  \n"
            "Đường ngang dashdot xanh đen = vị trí mũi CDM (đọc từ "
            "`cdm_zone_design_results` tại ΔS=30 cm). "
            "Hộp xanh ngọc góc dưới trái = so sánh d_stop hai phương án."
        )
        Q_CDM_KPA = 40.8  # tải phương án CDM, cố định
        # Sắp xếp HK ND-02 → ND-07 — bố cục 2 biểu đồ/hàng (3 hàng × 2 cột)
        bh_sorted = sorted(meta["boreholes_summary"], key=lambda b: b["name"])
        for row_start in range(0, len(bh_sorted), 2):
            row_bhs = bh_sorted[row_start:row_start + 2]
            cols_stress = st.columns(len(row_bhs))
            for col, b in zip(cols_stress, row_bhs):
                with col:
                    if not layers_by_bh.get(b["name"]):
                        st.warning(f"HK {b['name']}: chưa có địa tầng")
                        continue
                    bh_data_s = {
                        "elevation_m": b["elevation_m"],
                        "layers": layers_by_bh[b["name"]],
                        "H_soft_m": b.get("H_soft_m"),
                    }
                    # §72 Task S — truyền tip CDM thực tế từ cdm_zone_design_results
                    # để Boussinesq decay tính từ đúng vị trí mũi.
                    _tip = None
                    try:
                        with sqlite3.connect(_db()) as _con_t:
                            r_tip = _con_t.execute(
                                "SELECT tip_depth_m FROM cdm_zone_design_results "
                                "WHERE zone_code='QTT' AND bh_name=? AND delta_S_cm=30.0",
                                (b["name"],),
                            ).fetchone()
                        if r_tip and r_tip[0]:
                            _tip = float(r_tip[0])
                    except Exception:
                        pass
                    # B_eq = spacing cọc (đại diện ô đơn vị)
                    fig_s = stress_chart_with_10pct(
                        b["name"], bh_data_s,
                        q_cdm_kPa=Q_CDM_KPA, compact=True,
                        show_boussinesq=True,
                        cdm_tip_depth_m=_tip,
                        B_eq_m=1.8,
                    )
                    st.plotly_chart(fig_s, use_container_width=True,
                                     key=f"_qtt_stress_{b['name']}")

        # ─── Bảng thống kê cao độ + đáy vùng ảnh hưởng ───
        st.markdown("#### Bảng thống kê — cao độ thiết kế / tự nhiên / đáy vùng ảnh hưởng lún")
        from qtt_charts import compute_d_stop
        table_rows = []
        # §72 Task S — tính thêm d_stop Boussinesq
        from qtt_charts import compute_dsigma_boussinesq
        import numpy as np
        for b in bh_sorted:
            if not layers_by_bh.get(b["name"]):
                continue
            bh_d = {
                "elevation_m": b["elevation_m"],
                "layers": layers_by_bh[b["name"]],
            }
            # §72 Issue V #3 — MNN từ tvtk_cdm_config (không hardcode)
            from qtt_cdm_analysis import get_gwl_elev_m
            stop = compute_d_stop(bh_d, q_cdm_kPa=Q_CDM_KPA,
                                    gwl_elev_m=get_gwl_elev_m(_db()))
            # Lấy tip từ DB
            _tip_b = None
            try:
                with sqlite3.connect(_db()) as _con_t:
                    _r = _con_t.execute(
                        "SELECT tip_depth_m FROM cdm_zone_design_results "
                        "WHERE zone_code='QTT' AND bh_name=? AND delta_S_cm=30.0",
                        (b["name"],),
                    ).fetchone()
                if _r and _r[0]:
                    _tip_b = float(_r[0])
            except Exception:
                pass
            # d_stop_Boussinesq — quét bước 0.5m từ tip xuống
            d_stop_b = None
            if _tip_b is not None:
                layers_b = layers_by_bh[b["name"]]
                GAMMA = {"F": 18.0, "1": 14.6, "1b": 17.5, "2": 18.0,
                          "2a": 18.5, "3": 19.0, "5": 19.5, "6": 20.0}
                max_d_b = layers_b[-1]["depth_bot_m"]
                last_g = GAMMA.get(layers_b[-1]["symbol"], 17.5)
                for d_test in np.arange(_tip_b + 0.5, _tip_b + 100, 0.5):
                    # σ'v0(d_test)
                    cs = 0.0; last = 0.0
                    for L in layers_b:
                        g = GAMMA.get(L["symbol"], 17.5)
                        top, bot = L["depth_top_m"], L["depth_bot_m"]
                        if d_test <= top: break
                        if d_test >= bot:
                            cs += g * (bot - top); last = bot
                        else:
                            cs += g * (d_test - max(top, last)); last = d_test; break
                    if d_test > max_d_b:
                        cs += last_g * (d_test - max(last, max_d_b))
                    u = 9.81 * max(0.0, d_test - max(0.0, b["elevation_m"] - 0.0))
                    sig_eff = cs - u
                    dsig_b = compute_dsigma_boussinesq(
                        d_test - _tip_b, Q_CDM_KPA, 1.8, method="2:1")
                    if sig_eff > 0 and (dsig_b / sig_eff) < 0.10:
                        d_stop_b = float(d_test)
                        break
            tk = design_elev_by_bh.get(b["name"])
            tn = b["elevation_m"]
            dap = (tk - tn) if tk is not None else None
            table_rows.append({
                "Hố khoan": b["name"],
                "Cao độ TN (m)": round(tn, 2),
                "Cao độ TK (m)": round(tk, 2) if tk is not None else None,
                "Δ đắp/đào (m)": round(dap, 2) if dap is not None else None,
                "Tổng độ sâu HK (m)": b.get("depth_m") or layers_by_bh[b["name"]][-1]["depth_bot_m"],
                "H_soft (m)": b.get("H_soft_m"),
                "Mũi CDM (m)": round(_tip_b, 1) if _tip_b else None,
                "d_stop 1D (m)": stop["d_stop_m"],
                "d_stop Boussinesq (m)": round(d_stop_b, 1) if d_stop_b else None,
                "Δd_stop (m)": (round(stop["d_stop_m"] - d_stop_b, 1)
                                 if stop["d_stop_m"] and d_stop_b else None),
                "Cao độ đáy AH 1D (m)": stop["elev_stop_m"],
            })
        if table_rows:
            df_summary = pd.DataFrame(table_rows)
            _render_bold_table(df_summary)
            # Ghi chú diễn giải — §72 Task Z: dùng cột 'd_stop 1D (m)' sau khi
            # đổi schema bảng cho Task S (Boussinesq)
            n_inside_hk = sum(1 for r in table_rows
                              if r.get("d_stop 1D (m)") is not None
                              and r["d_stop 1D (m)"] <= r["Tổng độ sâu HK (m)"])
            n_bouss_inside = sum(1 for r in table_rows
                                   if r.get("d_stop Boussinesq (m)") is not None
                                   and r["d_stop Boussinesq (m)"] <= r["Tổng độ sâu HK (m)"])
            st.caption(
                f"**Δ đắp/đào** > 0 = phải đắp, < 0 = phải đào. "
                f"**d_stop 1D** = độ sâu tại đó σ'v0 ≥ 10 × q_CDM "
                f"= {10 * Q_CDM_KPA:.0f} kPa (phương án Δσ không đổi). "
                f"**d_stop Boussinesq** = phương án §72 Task S "
                f"(Δσ giảm theo z dưới mũi). "
                f"**1D: {n_inside_hk}/{len(table_rows)}** HK có đáy vùng ảnh hưởng "
                f"trong phạm vi khoan; **Boussinesq: {n_bouss_inside}/{len(table_rows)}** "
                f"HK trong phạm vi. Phần ngoài đã extrapolate theo γ lớp cuối (vô tận)."
            )

        st.divider()

        # ════════ J. Phân tích chi tiết S1, S2, Lc — 6 HK × 4 ΔS ════════
        st.markdown("### J. Phân tích chi tiết S1, S2, Lc — 6 HK × 4 ΔS")
        st.caption(
            "Bảng + biểu đồ tổng hợp lún đàn hồi S1 (khối CDM) + lún cố kết S2 "
            "(phần dưới mũi cọc) + tổng S = S1+S2 + Lc tối ưu cho mỗi tổ hợp HK × ΔS. "
            "Sử dụng để chọn ΔS phù hợp + Lc thiết kế."
        )

        # Load Lc data cho tất cả ΔS — dùng chung cho J, J2b, M, N, O
        bh_colors = {"ND-02": "#1565C0", "ND-03": "#D32F2F",
                      "ND-04": "#2E7D32", "ND-05": "#F57F17",
                      "ND-06": "#6A1B9A", "ND-07": "#00838F"}
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            grp_rows = con.execute("""
                SELECT bh_name, delta_S_cm, Lc_m, ok
                FROM cdm_zone_design_results WHERE zone_code='QTT'
                ORDER BY delta_S_cm, bh_name
            """).fetchall()
        df_grp = pd.DataFrame([dict(r) for r in grp_rows])

        # Bảng pivot — 6 HK × 4 ΔS
        if not df_grp.empty:
            with sqlite3.connect(_db()) as con:
                con.row_factory = sqlite3.Row
                det_rows = con.execute("""
                    SELECT bh_name, delta_S_cm, Lc_m, tip_depth_m,
                           S1_cm, S2_cm, S_total_cm, ok, H_soft_m,
                           penetrates_full
                    FROM cdm_zone_design_results
                    WHERE zone_code='QTT'
                    ORDER BY bh_name, delta_S_cm
                """).fetchall()
            df_det = pd.DataFrame([dict(r) for r in det_rows])

            # Pivot table với MultiIndex columns
            def _fmt(v, d=2):
                return f"{v:.{d}f}" if v is not None and not pd.isna(v) else "—"
            table_pivot = []
            for bh in sorted(df_det["bh_name"].unique()):
                sub = df_det[df_det["bh_name"] == bh]
                row = {"HK": bh, "H_soft (m)": sub.iloc[0]["H_soft_m"]}
                for ds in [10, 20, 30, 40]:
                    sds = sub[sub["delta_S_cm"] == ds]
                    if len(sds) == 0:
                        continue
                    r0 = sds.iloc[0]
                    row[f"ΔS={ds} | Lc"] = _fmt(r0["Lc_m"], 2)
                    row[f"ΔS={ds} | S1"] = _fmt(r0["S1_cm"], 2)
                    row[f"ΔS={ds} | S2"] = _fmt(r0["S2_cm"], 2)
                    row[f"ΔS={ds} | S"] = _fmt(r0["S_total_cm"], 2)
                    row[f"ΔS={ds} | OK"] = "Đạt" if r0["ok"] else "KĐ"
                table_pivot.append(row)
            df_tp = pd.DataFrame(table_pivot)
            st.markdown("**Bảng chi tiết — đầy đủ các tổ hợp:**")
            _render_bold_table(df_tp)

            # ─── Biểu đồ stacked bar S1+S2 per HK × ΔS ───
            st.markdown("**Stacked bar — Thành phần lún S1 + S2 cho mỗi tổ hợp:**")
            fig_stk = go.Figure()
            categories = []
            for bh in sorted(df_det["bh_name"].unique()):
                for ds in [10, 20, 30, 40]:
                    categories.append(f"{bh}<br>ΔS={ds}")
            s1_vals = []; s2_vals = []; ok_status = []
            for bh in sorted(df_det["bh_name"].unique()):
                for ds in [10, 20, 30, 40]:
                    sds = df_det[(df_det["bh_name"] == bh) & (df_det["delta_S_cm"] == ds)]
                    if len(sds):
                        r0 = sds.iloc[0]
                        s1_vals.append(r0["S1_cm"] or 0)
                        s2_vals.append(r0["S2_cm"] or 0)
                        ok_status.append(bool(r0["ok"]))
                    else:
                        s1_vals.append(0); s2_vals.append(0); ok_status.append(False)
            fig_stk.add_trace(go.Bar(
                name="S1 (đàn hồi khối CDM)",
                x=categories, y=s1_vals,
                marker_color="#1976D2",
                text=[f"{v:.1f}" for v in s1_vals],
                textposition="inside", textfont=dict(size=9, color="white"),
            ))
            fig_stk.add_trace(go.Bar(
                name="S2 (cố kết dưới mũi)",
                x=categories, y=s2_vals,
                marker_color="#F57C00",
                text=[f"{v:.1f}" for v in s2_vals],
                textposition="inside", textfont=dict(size=9, color="white"),
            ))
            # Đường ngang giới hạn ΔS — sử dụng max bằng phẳng
            for ds_v, color in zip([10, 20, 30, 40],
                                     ["#D32F2F", "#F57C00", "#2E7D32", "#5D4037"]):
                fig_stk.add_hline(
                    y=ds_v, line=dict(color=color, dash="dash", width=1),
                    annotation_text=f"ΔS={ds_v}",
                    annotation_position="right",
                    annotation_font=dict(size=9, color=color),
                )
            fig_stk.update_layout(
                title=dict(text="<b>S1 + S2 stacked theo mỗi phương án</b>",
                            font=dict(size=13)),
                xaxis_title="HK × ΔS",
                yaxis_title="Lún S (cm)",
                barmode="stack", height=550, plot_bgcolor="white",
                xaxis=dict(tickangle=-30, tickfont=dict(size=10)),
            )
            st.plotly_chart(fig_stk, use_container_width=True)

            # ─── Line chart Lc vs ΔS per HK ───
            st.markdown("**Quan hệ Lc — ΔS — 6 hố khoan:**")
            fig_lcds = go.Figure()
            for bh in sorted(df_det["bh_name"].unique()):
                sub = df_det[df_det["bh_name"] == bh].sort_values("delta_S_cm")
                fig_lcds.add_trace(go.Scatter(
                    x=sub["delta_S_cm"],
                    y=[v if v is not None and not pd.isna(v) else None
                       for v in sub["Lc_m"]],
                    mode="lines+markers+text",
                    line=dict(color=bh_colors.get(bh, "#666"), width=2),
                    marker=dict(size=10),
                    text=[f"{v:.1f}m" if v is not None and not pd.isna(v) else "KĐ"
                          for v in sub["Lc_m"]],
                    textposition="top center",
                    textfont=dict(size=10, color=bh_colors.get(bh, "#666")),
                    name=bh,
                ))
            fig_lcds.update_layout(
                title=dict(text="<b>Lc tối ưu theo ΔS — nhạy cảm</b>",
                            font=dict(size=13)),
                xaxis_title="ΔS cho phép (cm)",
                yaxis_title="Lc tối ưu (m)",
                height=500, plot_bgcolor="white",
                xaxis=dict(tickvals=[10, 20, 30, 40]),
            )
            st.plotly_chart(fig_lcds, use_container_width=True)

            # ─── Tỷ trọng S2/S_total ───
            st.markdown("**Tỷ trọng S2 / S_total (lún cố kết chiếm bao nhiêu %):**")
            ratios = []
            for bh in sorted(df_det["bh_name"].unique()):
                row = {"HK": bh}
                for ds in [10, 20, 30, 40]:
                    sds = df_det[(df_det["bh_name"] == bh) & (df_det["delta_S_cm"] == ds)]
                    if len(sds):
                        r0 = sds.iloc[0]
                        s2 = r0["S2_cm"] or 0
                        st_total = r0["S_total_cm"] or 0
                        ratio = (s2 / st_total * 100) if st_total > 0 else 0
                        row[f"ΔS={ds}cm"] = round(ratio, 1)
                    else:
                        row[f"ΔS={ds}cm"] = None
                ratios.append(row)
            df_ratios = pd.DataFrame(ratios)
            _render_bold_table(df_ratios)
            st.caption(
                "Tỷ trọng S2/S_total cao (>70%) → cọc trong lớp bùn nghiêm trọng — "
                "phần lớn lún do cố kết phần dưới mũi cọc (không xử lý). "
                "Tỷ trọng thấp (<50%) → cọc đã xử lý phần lớn lún (đáng kể tốt)."
            )

        st.divider()

        # ════════ K. Đường cong S_total vs Lc (sweep p) ════════
        st.markdown("### K. Đường cong S_total vs Lc — sweep độ xuyên cọc")
        st.caption(
            "Mỗi đường = 1 HK. Trục X = chiều dài cọc Lc (m), trục Y = tổng "
            "lún S_total (cm). Quét từng độ xuyên p (0.5-35m bước 1m). "
            "Đường ngang đứt đỏ/cam/xanh/nâu = mức ΔS giới hạn TCCS 41 (10/20/30/40 cm); "
            "đường chấm xám = các mức tham chiếu S_total (15/25/35 cm)."
        )
        bh_colors = {"ND-02": "#1565C0", "ND-03": "#D32F2F",
                      "ND-04": "#2E7D32", "ND-05": "#F57F17",
                      "ND-06": "#6A1B9A", "ND-07": "#00838F"}
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            curves_rows = con.execute("""
                SELECT bh_name, Lc_m, p_m, S_total_cm, S1_cm, S2_cm
                FROM cdm_zone_s_lc_curves WHERE zone_code='QTT'
                ORDER BY bh_name, p_m
            """).fetchall()
        df_curves = pd.DataFrame([dict(r) for r in curves_rows])
        if not df_curves.empty:
            fig_curves = go.Figure()
            for bh_name in sorted(df_curves["bh_name"].unique()):
                sub = df_curves[df_curves["bh_name"] == bh_name]
                fig_curves.add_trace(go.Scatter(
                    x=sub["Lc_m"], y=sub["S_total_cm"],
                    mode="lines+markers",
                    line=dict(color=bh_colors.get(bh_name, "#666"), width=2),
                    marker=dict(size=6),
                    name=bh_name,
                ))
            for dS_v, color in zip([10, 20, 30, 40],
                                     ["#D32F2F", "#F57F17", "#2E7D32", "#5D4037"]):
                fig_curves.add_hline(
                    y=dS_v, line=dict(color=color, dash="dash", width=1),
                    annotation_text=f"ΔS = {dS_v} cm",
                    annotation_position="right",
                    annotation_font=dict(size=10, color=color),
                )
            for S_ref in [15, 25, 35]:
                fig_curves.add_hline(
                    y=S_ref, line=dict(color="#888888", dash="dot", width=1),
                    annotation_text=f"S = {S_ref} cm",
                    annotation_position="left",
                    annotation_font=dict(size=10, color="#555555"),
                )
            fig_curves.update_layout(
                title=dict(text="<b>S_total vs Lc — 6 HK QTT</b>",
                            font=dict(size=13)),
                xaxis_title="Chiều dài cọc Lc (m)",
                yaxis_title="Tổng lún S_total (cm)",
                height=500, plot_bgcolor="white",
                legend=dict(orientation="h", y=-0.15),
            )
            st.plotly_chart(fig_curves, use_container_width=True)

        st.divider()

        # ════════ L. Đường cong lún S(t) 15 năm — Terzaghi ════════
        st.markdown("### L. Đường cong lún cố kết S(t) 15 năm — TCCS 41")
        st.caption(
            "**Phân tách lún theo cơ chế (rule §64 #7 + §69):**  \n"
            "- **S1** (đàn hồi khối CDM) — **tức thời** tại t=0  \n"
            "- **S2_instant** = Σ Si các lớp **cát** dưới mũi (granular, "
            "thoát nước nhanh) — **tức thời** tại t=0  \n"
            "- **S2_consol** = Σ Si các lớp **sét** dưới mũi — **cố kết Terzaghi** "
            "với Cv lab, H_d = chiều dày bùn dưới mũi (1 mặt thoát)  \n"
            "→ **S_total(t) = S1 + S2_instant + S2_consol × U(t)**"
        )
        import math

        # 1) Lấy Cv per HK từ lab — fallback HK gần nhất
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            cv_lab = {r["bh"]: r["Cv_avg"] for r in con.execute("""
                SELECT b.name AS bh, AVG(lt.Cv_cm2s) AS Cv_avg,
                       COUNT(lt.Cv_cm2s) AS n
                FROM lab_tests lt
                JOIN boreholes b ON b.id = lt.borehole_id
                WHERE b.name LIKE 'ND-%' AND lt.Cv_cm2s IS NOT NULL
                GROUP BY b.name
                HAVING n > 0
            """).fetchall()}
            bh_coords = {r["name"]: (r["x_coord_m"], r["y_coord_m"])
                         for r in con.execute(
                "SELECT name, x_coord_m, y_coord_m FROM boreholes "
                "WHERE name LIKE 'ND-%'"
            ).fetchall()}

        # Cv fallback: nearest HK với Cv lab
        cv_default = sum(cv_lab.values()) / len(cv_lab) if cv_lab else 5e-4

        def get_cv(bh_name):
            if bh_name in cv_lab:
                return cv_lab[bh_name], "lab", 0.0
            # Nearest HK với Cv
            if bh_name not in bh_coords:
                return cv_default, "default (TB zone)", -1
            N0, E0 = bh_coords[bh_name]
            best_d = float("inf"); best_bh = None
            for nb, cv in cv_lab.items():
                N1, E1 = bh_coords.get(nb, (None, None))
                if N1 is None:
                    continue
                d = ((N0 - N1) ** 2 + (E0 - E1) ** 2) ** 0.5
                if d < best_d:
                    best_d = d; best_bh = nb
            if best_bh:
                return cv_lab[best_bh], f"borrowed from {best_bh}", best_d
            return cv_default, "default (TB zone)", -1

        # 2) Lấy S1, S2 riêng (KHÔNG dùng S_total) — S2 mới là phần cố kết
        # tip_depth_m là cần thiết để tính H_S2 = chiều dày bùn dưới mũi cọc
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            st_rows = con.execute("""
                SELECT bh_name, S1_cm, S2_cm, S_total_cm, H_soft_m,
                       tip_depth_m, Lc_m
                FROM cdm_zone_design_results
                WHERE zone_code='QTT' AND delta_S_cm = ? AND S_total_cm IS NOT NULL
                ORDER BY bh_name
            """, (dS_pick,)).fetchall()
            # Đỉnh lớp bùn (clay_top) per HK từ layers
            clay_tops = {}
            for r in st_rows:
                _row = con.execute("""
                    SELECT MIN(depth_top_m) FROM layers
                    WHERE borehole_id = (SELECT id FROM boreholes WHERE name=?)
                      AND symbol IN ('1', '1b', '2', 'XMD')
                """, (r["bh_name"],)).fetchone()
                clay_tops[r["bh_name"]] = _row[0] if _row and _row[0] else 0.0

        def get_H_S2(r):
            """H_S2 = chiều dày bùn DƯỚI mũi cọc (m)."""
            tip = r["tip_depth_m"]
            clay_top = clay_tops.get(r["bh_name"], 0.0)
            H_soft = r["H_soft_m"] or 0
            clay_bot = clay_top + H_soft
            if tip is None or tip >= clay_bot:
                return 0.0  # cọc xuyên hết bùn → không có S2
            return round(clay_bot - tip, 2)

        # Gọi calc_s2_below_cdm để tách S2 theo lớp sand vs clay
        from settlement_calc import calc_s2_below_cdm

        s2_breakdown = {}
        for r in st_rows:
            bh = r["bh_name"]
            tip = r["tip_depth_m"]
            if tip is None:
                s2_breakdown[bh] = {"clay_cm": 0, "sand_cm": 0,
                                      "n_clay": 0, "n_sand": 0}
                continue
            # gwt_depth theo §69
            with sqlite3.connect(_db()) as con2:
                _row = con2.execute(
                    "SELECT elevation_m FROM boreholes WHERE name = ?",
                    (bh,)).fetchone()
            gwt = max(0.0, (_row[0] if _row and _row[0] else 0.0))
            try:
                detail = calc_s2_below_cdm(bh, cdm_tip_depth_m=tip,
                                             q_kPa=40.8, gwt_depth_m=gwt,
                                             db_path=_db())
                clay_cm = sum(L["Si_cm"] for L in detail["layers"]
                                if not L["is_sand"])
                sand_cm = sum(L["Si_cm"] for L in detail["layers"]
                                if L["is_sand"])
                n_clay = sum(1 for L in detail["layers"]
                              if not L["is_sand"])
                n_sand = sum(1 for L in detail["layers"]
                              if L["is_sand"])
                s2_breakdown[bh] = {
                    "clay_cm": round(clay_cm, 2),
                    "sand_cm": round(sand_cm, 2),
                    "n_clay": n_clay, "n_sand": n_sand,
                }
            except Exception:
                s2_breakdown[bh] = {"clay_cm": r["S2_cm"] or 0, "sand_cm": 0,
                                      "n_clay": 0, "n_sand": 0}

        cv_table_rows = []
        for r in st_rows:
            cv, source, dist = get_cv(r["bh_name"])
            H_S2 = get_H_S2(r)
            br = s2_breakdown[r["bh_name"]]
            cv_table_rows.append({
                "HK": r["bh_name"],
                "Cv (×10⁻⁴ cm²/s)": round(cv * 1e4, 3),
                "Nguồn Cv": source,
                "Mũi cọc (m)": r["tip_depth_m"],
                "H_soft (m)": r["H_soft_m"],
                "H_S2 bùn dưới mũi (m)": H_S2,
                "S1 (cm) tức thời": r["S1_cm"],
                "S2_sand (cm) tức thời": br["sand_cm"],
                "S2_clay_∞ (cm) cố kết": br["clay_cm"],
                "S_total_∞ (cm)": round(
                    (r["S1_cm"] or 0) + br["sand_cm"] + br["clay_cm"], 2),
            })
        st.markdown(
            "**Bảng phân tách lún theo cơ chế — tức thời (S1 + S2_sand) "
            "+ cố kết Terzaghi (S2_clay):**"
        )
        df_cv = pd.DataFrame(cv_table_rows)
        _render_bold_table(df_cv)

        # 3) Vẽ S_total(t) = S1 + S2_sand + S2_clay × U(t)
        years = np.linspace(0.01, 15, 80)
        fig_st = go.Figure()
        for r in st_rows:
            bh = r["bh_name"]
            S1 = r["S1_cm"] or 0
            br = s2_breakdown[bh]
            S2_clay = br["clay_cm"]
            S2_sand = br["sand_cm"]
            S_instant = S1 + S2_sand  # tức thời tại t=0
            H_d = get_H_S2(r)
            color = bh_colors.get(bh, "#666")

            if H_d <= 0 or S2_clay < 0.01:
                # Không còn clay dưới mũi → lún hoàn toàn tức thời
                S_t = [S_instant] * len(years)
                fig_st.add_trace(go.Scatter(
                    x=years, y=S_t, mode="lines",
                    line=dict(color=color, width=2.5),
                    name=(f"{bh} · Tức thời ({S_instant:.1f}cm: "
                          f"S1={S1:.1f}+sand={S2_sand:.1f})"),
                    hovertemplate=(f"{bh} (xuyên hết bùn)<br>"
                                   f"S1={S1:.1f}+S2_sand={S2_sand:.1f}"
                                   "<br>S=%{y:.1f}cm<extra></extra>"),
                ))
                continue

            Cv_cm2s, source, _ = get_cv(bh)
            Cv_m2yr = Cv_cm2s * 1e-4 * 365 * 86400  # cm²/s → m²/year
            T_v = [Cv_m2yr * t / (H_d ** 2) for t in years]
            U_t = [min(1.0, 2.0 * math.sqrt(tv / math.pi) if tv < 0.197 else
                        1 - 0.81 * math.exp(-9.87 * tv / 4)) for tv in T_v]
            # S2_consol(t) = U(t) × S2_clay ; tức thời = S1 + S2_sand
            S2_consol_t = [u * S2_clay for u in U_t]
            S_total_t = [S_instant + sc for sc in S2_consol_t]
            src_tag = ("lab" if source == "lab"
                       else "↩" if source.startswith("borrowed")
                       else "*")
            # Đường S_total(t) — chính (liền, đậm)
            fig_st.add_trace(go.Scatter(
                x=years, y=S_total_t, mode="lines",
                line=dict(color=color, width=2.8),
                name=(f"{bh} · S_total(t) ({src_tag}, "
                      f"Cv={Cv_cm2s*1e4:.2f}e-4, S∞={S_instant+S2_clay:.1f}cm)"),
                hovertemplate=(f"{bh}<br>Cv={Cv_cm2s:.6f} cm²/s ({source})<br>"
                               f"H_d=H_S2={H_d:.1f}m (1-mặt, đáy không thấm)<br>"
                               f"S_instant={S_instant:.1f}cm "
                               f"(S1={S1:.1f}+sand={S2_sand:.1f})<br>"
                               f"S2_clay_∞={S2_clay:.1f}cm<br>"
                               "t=%{x:.1f}năm<br>"
                               "S_total=%{y:.1f}cm<extra></extra>"),
            ))
            # Đường S_instant nằm ngang — tham chiếu (đứt mỏng)
            fig_st.add_trace(go.Scatter(
                x=years, y=[S_instant] * len(years), mode="lines",
                line=dict(color=color, width=1, dash="dot"),
                name=f"{bh} · S_instant",
                showlegend=False,
                hovertemplate=(f"{bh}<br>S_instant={S_instant:.1f}cm "
                               "(S1+S2_sand, tại t=0+)<extra></extra>"),
            ))
        fig_st.add_vline(x=15, line=dict(color="black", dash="dash", width=1),
                          annotation_text="15 năm")
        fig_st.update_layout(
            title=dict(
                text=("<b>S_total(t) = S_instant + S2_clay × U(t) — "
                       "Terzaghi 1-mặt</b>"),
                font=dict(size=13),
            ),
            xaxis_title="Thời gian t (năm)",
            yaxis_title="Lún tổng S_total(t) (cm)",
            height=500, plot_bgcolor="white",
            legend=dict(orientation="v", y=0.5, x=1.02, font=dict(size=10)),
        )
        st.plotly_chart(fig_st, use_container_width=True)
        st.caption(
            "**Đường liền** = S2(t) lún cố kết theo thời gian. "
            "**Đường đứt cùng màu** = S_total(t) = S1 (tức thì) + S2(t). "
            "**Chú thích nguồn Cv:** `lab` = từ HK đó (tooltip chi tiết); "
            "`↩` = mượn từ HK gần nhất; `*` = TB toàn zone. "
            "H_d = H_soft (cố kết **1 mặt** — giả thiết đáy lớp yếu là không thấm)."
        )

        st.divider()

        # ════════ M. Heatmap Lc 162 điểm grid × TẤT CẢ ΔS (§72 Task BB) ════════
        st.markdown("### M. Heatmap Lc 162 điểm grid — TẤT CẢ ΔS cho phép")
        st.caption(
            "Mỗi biểu đồ = 1 mức ΔS cho phép TCCS 41 Bảng 1. Polygon đen = "
            "ranh giới QTT; 162 điểm vuông = grid 20×20m; 6 HK ND-02..ND-07 "
            "kim cương trắng. Colorscale Turbo (xanh = Lc nhỏ, đỏ = Lc lớn). "
            "Nguồn: `cdm_qtt_grid_lc`. **Note:** ΔS=15, 25 chỉ hiển thị nếu Task T "
            "(grid 6 ΔS) đã chạy."
        )
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            grid_all_rows = con.execute("""
                SELECT delta_S_cm, easting_m AS E, northing_m AS N,
                       Lc_m, S_total_cm, ok, ref_hk
                FROM cdm_qtt_grid_lc
                ORDER BY delta_S_cm, northing_m, easting_m
            """).fetchall()
        df_grid_all_M = pd.DataFrame([dict(r) for r in grid_all_rows])

        if not df_grid_all_M.empty:
            ds_available_M = sorted(df_grid_all_M["delta_S_cm"].unique().tolist())
            # Render 2 heatmap mỗi hàng (3 hàng nếu 6 ΔS, 2 hàng nếu 4 ΔS)
            for row_start in range(0, len(ds_available_M), 2):
                row_ds = ds_available_M[row_start:row_start + 2]
                cols_M = st.columns(len(row_ds))
                for col_M, dS_v in zip(cols_M, row_ds):
                    with col_M:
                        sub_grid = df_grid_all_M[
                            df_grid_all_M["delta_S_cm"] == dS_v
                        ].copy()
                        sub_grid["Lc_m"] = sub_grid["Lc_m"].fillna(0)
                        n_ok = int(sub_grid["ok"].sum())
                        fig_m = px.scatter(
                            sub_grid, x="E", y="N", color="Lc_m",
                            color_continuous_scale="Turbo",
                            hover_data=["Lc_m", "S_total_cm", "ref_hk", "ok"],
                            labels={"Lc_m": "Lc (m)",
                                     "E": "Easting (m)",
                                     "N": "Northing (m)"},
                            title=f"<b>Lc tối ưu 162 điểm grid — ΔS={int(dS_v)}cm</b>",
                        )
                        fig_m.update_traces(marker=dict(size=11, symbol="square"))
                        fig_m.update_yaxes(scaleanchor="x", scaleratio=1)
                        fig_m.update_layout(
                            height=450,
                            margin=dict(l=50, r=30, t=50, b=40),
                            title_font=dict(size=12),
                        )
                        fig_m.add_trace(go.Scatter(
                            x=bd_x, y=bd_y, mode="lines",
                            line=dict(color="black", width=2),
                            showlegend=False, hoverinfo="skip",
                        ))
                        fig_m.add_trace(go.Scatter(
                            x=[b["E"] for b in bhs], y=[b["N"] for b in bhs],
                            mode="markers+text",
                            marker=dict(size=13, color="white",
                                        symbol="diamond",
                                        line=dict(color="black", width=1.8)),
                            text=[b["name"] for b in bhs],
                            textposition="top center",
                            textfont=dict(size=9),
                            showlegend=False, hoverinfo="skip",
                        ))
                        st.plotly_chart(fig_m, use_container_width=True,
                                         key=f"_qtt_heatmap_M_{int(dS_v)}")
                        st.caption(
                            f"ΔS={int(dS_v)}cm — Điểm đạt: "
                            f"{n_ok}/{len(sub_grid)} "
                            f"({n_ok / len(sub_grid) * 100:.0f}%) · "
                            f"Lc max: {sub_grid['Lc_m'].max():.1f}m · "
                            f"Lc TB: {sub_grid['Lc_m'].mean():.1f}m"
                        )
            # Cảnh báo nếu chưa có 6 ΔS
            if len(ds_available_M) < 6:
                missing = sorted(set([10.0, 15.0, 20.0, 25.0, 30.0, 40.0])
                                  - set(ds_available_M))
                st.warning(
                    f"DB hiện chỉ có {len(ds_available_M)} ΔS — thiếu: "
                    f"{[int(d) for d in missing]} cm. Chạy Task T "
                    f"(`save_qtt_grid_lc()`) để bổ sung."
                )
        else:
            st.info("Chưa có dữ liệu `cdm_qtt_grid_lc`. Chạy Task T.")

        st.divider()

        # ════════ N. Kiểm tra độ bằng phẳng — TẤT CẢ ΔS × ngưỡng i ════════
        st.markdown("### N. Kiểm tra độ bằng phẳng — tất cả ΔS × ngưỡng i")
        st.caption(
            "Bảng tổng hợp tỉ lệ cặp HK đạt độ bằng phẳng theo MỌI tổ hợp "
            "(4 ΔS × 6 ngưỡng i). Không đề xuất ngưỡng cụ thể — kỹ sư tự "
            "đánh giá theo tiêu chí dự án."
        )
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            sm_all_rows = con.execute("""
                SELECT delta_S_cm, hk_i, hk_j, d_m, dS_pair_m, i_inv_actual,
                       S_i_cm, S_j_cm
                FROM cdm_zone_smoothness_results
                WHERE zone_code = 'QTT'
                ORDER BY delta_S_cm, i_inv_actual ASC
            """).fetchall()
        df_sm_all = pd.DataFrame([dict(r) for r in sm_all_rows])

        if not df_sm_all.empty:
            # Ma trận pass-rate: rows = ΔS, cols = i_inv ngưỡng
            i_inv_thresholds = [100, 125, 150, 175, 200, 250]
            matrix_rows = []
            for dS_v in [10, 20, 30, 40]:
                sub = df_sm_all[df_sm_all["delta_S_cm"] == dS_v]
                if sub.empty:
                    continue
                row = {"ΔS (cm)": dS_v, "Tổng cặp": len(sub)}
                for thr in i_inv_thresholds:
                    n_pass = int((sub["i_inv_actual"] >= thr).sum())
                    pct = round(n_pass / len(sub) * 100, 1)
                    row[f"i≥1/{thr} (%)"] = pct
                matrix_rows.append(row)
            df_sm_matrix = pd.DataFrame(matrix_rows)
            st.markdown(
                "**Bảng tỉ lệ cặp HK đạt độ bằng phẳng (%) — "
                "rows: ΔS × cols: ngưỡng i:**"
            )
            _render_bold_table(df_sm_matrix)

            # Biểu đồ quan hệ ΔS × i_inv_threshold
            fig_sm_grid = go.Figure()
            for thr in i_inv_thresholds:
                pcts = []
                for dS_v in [10, 20, 30, 40]:
                    sub = df_sm_all[df_sm_all["delta_S_cm"] == dS_v]
                    n_pass = int((sub["i_inv_actual"] >= thr).sum())
                    pct = (n_pass / len(sub) * 100) if len(sub) else 0
                    pcts.append(pct)
                fig_sm_grid.add_trace(go.Scatter(
                    x=[10, 20, 30, 40], y=pcts,
                    mode="lines+markers+text",
                    text=[f"{v:.0f}%" for v in pcts],
                    textposition="top center",
                    name=f"i ≥ 1/{thr}",
                    line=dict(width=2),
                    marker=dict(size=10),
                ))
            fig_sm_grid.update_layout(
                title=dict(
                    text="<b>Quan hệ tỉ lệ đạt bằng phẳng (%) theo ΔS</b>",
                    font=dict(size=13),
                ),
                xaxis_title="ΔS cho phép (cm)",
                yaxis_title="Tỉ lệ cặp HK đạt (%)",
                height=480, plot_bgcolor="white",
                xaxis=dict(tickvals=[10, 20, 30, 40]),
                yaxis=dict(range=[-5, 105]),
            )
            st.plotly_chart(fig_sm_grid, use_container_width=True)

        st.divider()

        # ════════ O. Phân vùng thiết kế — TẤT CẢ ΔS ════════
        st.markdown("### O. Phân vùng thiết kế quantile — tất cả ΔS")
        st.caption(
            "Mỗi ΔS có 1 bảng phân vùng riêng. Hiển thị Lc_design (max) per "
            "vùng + % diện tích. Không đề xuất ΔS — kỹ sư tự đánh giá."
        )
        # Sub-zoning tables for each ΔS
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            all_grid = con.execute("""
                SELECT delta_S_cm, easting_m AS E, northing_m AS N,
                       Lc_m, ok
                FROM cdm_qtt_grid_lc ORDER BY delta_S_cm, easting_m
            """).fetchall()
        df_grid_all = pd.DataFrame([dict(r) for r in all_grid])
        if not df_grid_all.empty:
            # §72 Task 3: Trải phẳng — KHÔNG dùng st.tabs. Render tuần tự 6 ΔS.
            available_dS = sorted(df_grid_all["delta_S_cm"].unique().tolist())
            for dS_v in available_dS:
                st.markdown(f"#### Phân vùng tại ΔS = {dS_v:.0f} cm")
                sub_grid = df_grid_all[df_grid_all["delta_S_cm"] == dS_v].copy()
                if sub_grid.empty:
                    st.warning(f"Không có data grid cho ΔS = {dS_v}")
                    continue
                sub_grid["Lc_m"] = sub_grid["Lc_m"].fillna(0)
                lcs = sub_grid["Lc_m"].values
                n_zones_local = 4
                q = [np.quantile(lcs, k / n_zones_local)
                     for k in range(1, n_zones_local)]
                zones = np.digitize(lcs, q) + 1
                sub_grid["zone"] = zones
                zone_stats = sub_grid.groupby("zone").agg(
                    Lc_max=("Lc_m", "max"),
                    Lc_min=("Lc_m", "min"),
                    Lc_mean=("Lc_m", "mean"),
                    n_cells=("Lc_m", "count"),
                ).reset_index()
                zone_stats["Vùng"] = "P" + zone_stats["zone"].astype(str)
                zone_stats["Lc thiết kế (m)"] = zone_stats["Lc_max"].round(1)
                zone_stats["% diện tích"] = (
                    zone_stats["n_cells"] / len(sub_grid) * 100
                ).round(1)
                _render_bold_table(
                    zone_stats[["Vùng", "Lc thiết kế (m)", "n_cells",
                                 "% diện tích", "Lc_min", "Lc_max"]]
                )

            # Biểu đồ quan hệ Lc_design × ΔS per vùng
            st.markdown("**Quan hệ Lc thiết kế (max mỗi vùng) theo ΔS:**")
            fig_zone_ds = go.Figure()
            for dS_v in available_dS:
                sub_grid = df_grid_all[df_grid_all["delta_S_cm"] == dS_v].copy()
                sub_grid["Lc_m"] = sub_grid["Lc_m"].fillna(0)
                lcs = sub_grid["Lc_m"].values
                if len(lcs) == 0: continue
                n_zones_local = 4
                q = [np.quantile(lcs, k / n_zones_local)
                     for k in range(1, n_zones_local)]
                zones = np.digitize(lcs, q) + 1
                tmp = pd.DataFrame({"Lc_m": lcs, "zone": zones})
                lc_max_per_zone = tmp.groupby("zone")["Lc_m"].max().tolist()
                fig_zone_ds.add_trace(go.Bar(
                    name=f"ΔS={dS_v}",
                    x=[f"P{z}" for z in range(1, len(lc_max_per_zone) + 1)],
                    y=lc_max_per_zone,
                    text=[f"{v:.1f}m" for v in lc_max_per_zone],
                    textposition="outside",
                ))
            fig_zone_ds.update_layout(
                title=dict(text=f"<b>Lc thiết kế per vùng × {len(available_dS)} ΔS</b>",
                            font=dict(size=13)),
                xaxis_title="Vùng (quantile)",
                yaxis_title="Lc tối đa trong vùng (m)",
                barmode="group", height=480, plot_bgcolor="white",
            )
            st.plotly_chart(fig_zone_ds, use_container_width=True)

        st.divider()

        # ════════ O2. (cũ O) Phân vùng quantile + Pareto cho ΔS chọn ════════
        st.markdown(f"### O2. Phân vùng chi tiết (ΔS = {dS_pick} cm) + Pareto")
        # §72 Task BB — df_grid filter từ df_grid_all_M (đã load đầy đủ ở section M)
        df_grid = (df_grid_all_M[df_grid_all_M["delta_S_cm"] == dS_pick].copy()
                    if not df_grid_all_M.empty else pd.DataFrame())
        if not df_grid.empty:
            df_grid["Lc_m"] = df_grid["Lc_m"].fillna(0)
            n_zones = st.slider("Số vùng phân (quantile)",
                                  2, 6, value=4, key="_qtt_nz")
            lcs = df_grid["Lc_m"].values
            q = [np.quantile(lcs, k / n_zones) for k in range(1, n_zones)]
            zones = np.digitize(lcs, q) + 1  # 1..n_zones
            df_grid["zone"] = zones

            # Bar chart per zone
            zone_stats = df_grid.groupby("zone").agg(
                Lc_max=("Lc_m", "max"),
                Lc_min=("Lc_m", "min"),
                Lc_mean=("Lc_m", "mean"),
                n_cells=("Lc_m", "count"),
            ).reset_index()
            zone_stats["Vùng"] = "P" + zone_stats["zone"].astype(str)
            zone_stats["Lc thiết kế (m)"] = zone_stats["Lc_max"].round(1)
            zone_stats["% diện tích"] = (
                zone_stats["n_cells"] / len(df_grid) * 100
            ).round(1)
            st.markdown("**Bảng phân vùng:**")
            st.dataframe(
                zone_stats[["Vùng", "Lc thiết kế (m)", "n_cells",
                             "% diện tích", "Lc_min", "Lc_max"]],
                hide_index=True, use_container_width=True,
            )

            # Map theo zone
            colors_zone = ["#1565C0", "#D32F2F", "#2E7D32", "#F57F17",
                            "#6A1B9A", "#00838F"]
            fig_zone = go.Figure()
            for i in range(1, n_zones + 1):
                sub = df_grid[df_grid["zone"] == i]
                fig_zone.add_trace(go.Scatter(
                    x=sub["E"], y=sub["N"], mode="markers",
                    marker=dict(size=12, color=colors_zone[i - 1],
                                symbol="square"),
                    name=f"P{i}: Lc={zone_stats.loc[zone_stats['zone']==i,'Lc thiết kế (m)'].values[0]:.1f}m",
                ))
            fig_zone.add_trace(go.Scatter(
                x=bd_x, y=bd_y, mode="lines",
                line=dict(color="black", width=2),
                name="Ranh giới", showlegend=True,
            ))
            fig_zone.add_trace(go.Scatter(
                x=[b["E"] for b in bhs], y=[b["N"] for b in bhs],
                mode="markers+text",
                marker=dict(size=16, color="white", symbol="diamond",
                            line=dict(color="black", width=2)),
                text=[b["name"] for b in bhs], textposition="top center",
                name="HK ND",
            ))
            fig_zone.update_yaxes(scaleanchor="x", scaleratio=1)
            fig_zone.update_layout(
                height=600,
                title=f"Phân vùng thiết kế CDM — {n_zones} vùng theo Lc",
            )
            st.plotly_chart(fig_zone, use_container_width=True)

        st.divider()

        # ════════ O2. PA-A: Tăng q_u + giảm spacing — đạt ΔS=10cm (§72 Task 4) ════════
        st.markdown("### O2. Phương án thay thế A — Tăng q_u + giảm spacing")
        st.caption(
            "Sweep $(q_u, s)$ tìm cấu hình đạt $\\Delta S = 10$ cm "
            "(cấp cao tốc gần mố cầu — TCCS 41 Bảng 1). Chi phí tương đối "
            "= $(q_u/800) \\times (1.8/s)^2 \\times (L_c/20)$. "
            "Nguồn: `qtt_cdm_alternative_strength`."
        )
        try:
            with sqlite3.connect(_db()) as con:
                pa_a_rows = con.execute("""
                    SELECT bh_name, q_u_kPa, spacing_m, Lc_m, S_total_cm,
                           ok, cost_rel
                    FROM qtt_cdm_alternative_strength
                    WHERE zone_code='QTT' AND delta_S_cm=10.0
                    ORDER BY bh_name, q_u_kPa, spacing_m
                """).fetchall()
            if pa_a_rows:
                df_pa = pd.DataFrame(pa_a_rows, columns=[
                    "HK", "q_u (kPa)", "s (m)", "Lc (m)",
                    "S_total (cm)", "ok", "Chi phí",
                ])
                df_pa["Đạt"] = df_pa["ok"].map({1: "Đạt", 0: "Không đạt"})
                df_pa = df_pa.drop(columns=["ok"])
                # Bảng tóm tắt: best cost per HK
                df_best = (df_pa[df_pa["Đạt"] == "Đạt"]
                              .sort_values("Chi phí")
                              .drop_duplicates("HK", keep="first"))
                if not df_best.empty:
                    st.markdown("**Cấu hình tối ưu chi phí per HK:**")
                    _render_bold_table(df_best)
                    # Bar chart Chi phí + Lc
                    fig_pa = go.Figure()
                    fig_pa.add_trace(go.Bar(
                        x=df_best["HK"], y=df_best["Chi phí"],
                        name="Chi phí (tương đối)", marker_color="#1565C0",
                        text=[f"{v:.2f}" for v in df_best["Chi phí"]],
                        textposition="outside",
                    ))
                    fig_pa.update_layout(
                        title=dict(text="<b>PA-A: Chi phí cấu hình tối ưu per HK</b>",
                                     font=dict(size=13)),
                        height=380, plot_bgcolor="white",
                        xaxis_title="Hố khoan",
                        yaxis_title="Chi phí (tương đối baseline)",
                    )
                    st.plotly_chart(fig_pa, use_container_width=True)
                else:
                    st.warning("Không HK nào đạt được ΔS=10cm trong sweep grid hiện tại. "
                                "Thử tăng q_u_max hoặc giảm spacing_min.")
            else:
                st.info("Chưa có dữ liệu PA-A QTT. Chạy: "
                         "`python scripts/cdm_alternative_design.py`")
        except Exception as _exc:
            st.warning(f"Không tải được O2: {_exc}")

        st.divider()

        # ════════ O3. PA-B: Lc ≤ 30m tìm (q_u, s) tối ưu (§72 Task 5) ════════
        st.markdown("### O3. Phương án thay thế B — Lc ≤ 30m")
        st.caption(
            "Hạn chế chiều dài cọc CDM $L_{coc} \\le 30$ m (giới hạn thiết bị "
            "thi công). Tìm $(q_u, s)$ tối ưu chi phí đạt $\\Delta S = 30$ cm "
            "(cao tốc thông thường). Nguồn: `qtt_cdm_alternative_Lmax`."
        )
        try:
            with sqlite3.connect(_db()) as con:
                pa_b_rows = con.execute("""
                    SELECT bh_name, L_max_m, q_u_opt_kPa, spacing_opt_m,
                           Lc_m, S_total_cm, ok, cost_rel, note
                    FROM qtt_cdm_alternative_Lmax
                    WHERE zone_code='QTT' AND L_max_m=30.0 AND delta_S_cm=30.0
                    ORDER BY bh_name
                """).fetchall()
            if pa_b_rows:
                df_pb = pd.DataFrame(pa_b_rows, columns=[
                    "HK", "L_max (m)", "q_u tối ưu (kPa)", "s tối ưu (m)",
                    "Lc (m)", "S_total (cm)", "ok", "Chi phí", "Ghi chú",
                ])
                df_pb["Đạt"] = df_pb["ok"].map({1: "Đạt", 0: "Không đạt"})
                df_pb = df_pb.drop(columns=["ok"])
                _render_bold_table(df_pb)
            else:
                st.info("Chưa có dữ liệu PA-B QTT. Chạy: "
                         "`python scripts/cdm_alternative_design.py`")
        except Exception as _exc:
            st.warning(f"Không tải được O3: {_exc}")

        st.divider()

        # ════════ O4. PA2 phân vùng theo tuyến/cặp HK (§72 Task CC) ════════
        st.markdown("### O4. Phân vùng QTT theo cấu trúc tuyến/cặp HK")
        st.caption(
            "**Phương án 2 — phân vùng dễ thi công** (so với phân vùng "
            "quantile bất quy tắc của Section O):  \n"
            "- **PA2a:** 2 tuyến song song theo Northing: "
            "**Tuyến Nam** (ND-02 + ND-03 + ND-04, N≈1191670) và "
            "**Tuyến Bắc** (ND-05 + ND-06 + ND-07, N≈1191761)  \n"
            "- **PA2b:** 3 cặp HK cross-tuyến theo Easting: "
            "**Cặp Tây** (ND-02 ↔ ND-07), "
            "**Cặp Giữa** (ND-03 ↔ ND-06), "
            "**Cặp Đông** (ND-04 ↔ ND-05)  \n"
            "Lc thiết kế per nhóm = max(Lc của các HK trong nhóm) ở mỗi ΔS — "
            "an toàn cho mọi HK trong nhóm. Nguồn: `cdm_zone_design_results`."
        )
        try:
            with sqlite3.connect(_db()) as con:
                con.row_factory = sqlite3.Row
                lc_alignment_rows = con.execute(
                    "SELECT bh_name, delta_S_cm, Lc_m FROM cdm_zone_design_results "
                    "WHERE zone_code='QTT' ORDER BY bh_name, delta_S_cm"
                ).fetchall()
            df_lcA = pd.DataFrame([dict(r) for r in lc_alignment_rows])
            if not df_lcA.empty:
                # Định nghĩa nhóm
                pa2a_groups = {
                    "Tuyến Nam (02-03-04)": ["ND-02", "ND-03", "ND-04"],
                    "Tuyến Bắc (05-06-07)": ["ND-05", "ND-06", "ND-07"],
                }
                pa2b_groups = {
                    "Cặp Tây (02-07)":   ["ND-02", "ND-07"],
                    "Cặp Giữa (03-06)":  ["ND-03", "ND-06"],
                    "Cặp Đông (04-05)":  ["ND-04", "ND-05"],
                }

                def lc_matrix_from_groups(groups: dict) -> pd.DataFrame:
                    rows = []
                    for grp_name, hks_in_grp in groups.items():
                        sub = df_lcA[df_lcA["bh_name"].isin(hks_in_grp)].copy()
                        row = {"Nhóm": grp_name,
                                "HK trong nhóm": " + ".join(hks_in_grp)}
                        for dS in [10, 15, 20, 25, 30, 40]:
                            vals = sub[sub["delta_S_cm"] == dS]["Lc_m"].dropna()
                            row[f"ΔS={dS}"] = (round(float(vals.max()), 1)
                                                if len(vals) > 0 else None)
                        rows.append(row)
                    return pd.DataFrame(rows)

                # PA2a — tuyến
                st.markdown("**PA2a — 2 tuyến song song theo Northing:**")
                df_pa2a = lc_matrix_from_groups(pa2a_groups)
                _render_bold_table(df_pa2a)
                # Bar chart so sánh 2 tuyến qua mọi ΔS
                fig_pa2a = go.Figure()
                colors_2a = ["#1565C0", "#D32F2F"]
                for idx, (grp_name, _) in enumerate(pa2a_groups.items()):
                    row = df_pa2a[df_pa2a["Nhóm"] == grp_name].iloc[0]
                    ys = [row[f"ΔS={d}"] for d in [10, 15, 20, 25, 30, 40]]
                    fig_pa2a.add_trace(go.Bar(
                        x=[f"ΔS={d}" for d in [10, 15, 20, 25, 30, 40]],
                        y=ys, name=grp_name,
                        marker_color=colors_2a[idx],
                        text=[f"{v:.1f}m" if v else "—" for v in ys],
                        textposition="outside",
                    ))
                fig_pa2a.update_layout(
                    title=dict(text="<b>PA2a: Lc thiết kế per tuyến × 6 ΔS</b>",
                                font=dict(size=13)),
                    barmode="group", height=400, plot_bgcolor="white",
                    xaxis_title="ΔS cho phép", yaxis_title="Lc thiết kế (m)",
                    legend=dict(orientation="h", y=-0.18),
                )
                st.plotly_chart(fig_pa2a, use_container_width=True)

                # PA2b — cặp
                st.markdown("**PA2b — 3 cặp HK cross-tuyến theo Easting:**")
                df_pa2b = lc_matrix_from_groups(pa2b_groups)
                _render_bold_table(df_pa2b)
                fig_pa2b = go.Figure()
                colors_2b = ["#1565C0", "#2E7D32", "#F57F17"]
                for idx, (grp_name, _) in enumerate(pa2b_groups.items()):
                    row = df_pa2b[df_pa2b["Nhóm"] == grp_name].iloc[0]
                    ys = [row[f"ΔS={d}"] for d in [10, 15, 20, 25, 30, 40]]
                    fig_pa2b.add_trace(go.Bar(
                        x=[f"ΔS={d}" for d in [10, 15, 20, 25, 30, 40]],
                        y=ys, name=grp_name,
                        marker_color=colors_2b[idx],
                        text=[f"{v:.1f}m" if v else "—" for v in ys],
                        textposition="outside",
                    ))
                fig_pa2b.update_layout(
                    title=dict(text="<b>PA2b: Lc thiết kế per cặp × 6 ΔS</b>",
                                font=dict(size=13)),
                    barmode="group", height=400, plot_bgcolor="white",
                    xaxis_title="ΔS cho phép", yaxis_title="Lc thiết kế (m)",
                    legend=dict(orientation="h", y=-0.18),
                )
                st.plotly_chart(fig_pa2b, use_container_width=True)

                # Bản đồ vị trí HK + tô màu nhóm (2 hàng × 2 cột: 2a trái, 2b phải)
                st.markdown("**Bản đồ phân vùng — vị trí HK + nhóm:**")
                meta_b = meta["boreholes_summary"]
                map_cols = st.columns(2)
                # 2a map
                with map_cols[0]:
                    fig_map_2a = go.Figure()
                    fig_map_2a.add_trace(go.Scatter(
                        x=bd_x, y=bd_y, mode="lines",
                        line=dict(color="black", width=2),
                        name="Ranh giới QTT", showlegend=False,
                    ))
                    for idx, (grp_name, hks_in_grp) in enumerate(pa2a_groups.items()):
                        xs = [b["E"] for b in meta_b if b["name"] in hks_in_grp]
                        ys = [b["N"] for b in meta_b if b["name"] in hks_in_grp]
                        nms = [b["name"] for b in meta_b if b["name"] in hks_in_grp]
                        fig_map_2a.add_trace(go.Scatter(
                            x=xs, y=ys, mode="markers+text",
                            marker=dict(size=18, color=colors_2a[idx],
                                        symbol="diamond",
                                        line=dict(color="black", width=2)),
                            text=nms, textposition="top center",
                            textfont=dict(size=11),
                            name=grp_name,
                        ))
                    fig_map_2a.update_yaxes(scaleanchor="x", scaleratio=1)
                    fig_map_2a.update_layout(
                        title=dict(text="<b>PA2a — 2 tuyến song song</b>",
                                    font=dict(size=12)),
                        height=420, plot_bgcolor="white",
                        xaxis_title="Easting (m)", yaxis_title="Northing (m)",
                        legend=dict(orientation="h", y=-0.18),
                    )
                    st.plotly_chart(fig_map_2a, use_container_width=True)

                # 2b map — 3 cặp với đường nối
                with map_cols[1]:
                    fig_map_2b = go.Figure()
                    fig_map_2b.add_trace(go.Scatter(
                        x=bd_x, y=bd_y, mode="lines",
                        line=dict(color="black", width=2),
                        name="Ranh giới QTT", showlegend=False,
                    ))
                    bh_by_name = {b["name"]: b for b in meta_b}
                    for idx, (grp_name, hks_in_grp) in enumerate(pa2b_groups.items()):
                        xs = [bh_by_name[h]["E"] for h in hks_in_grp]
                        ys = [bh_by_name[h]["N"] for h in hks_in_grp]
                        # Đường nối cặp
                        fig_map_2b.add_trace(go.Scatter(
                            x=xs, y=ys, mode="lines+markers+text",
                            line=dict(color=colors_2b[idx], width=2.5,
                                       dash="dash"),
                            marker=dict(size=18, color=colors_2b[idx],
                                        symbol="diamond",
                                        line=dict(color="black", width=2)),
                            text=hks_in_grp, textposition="top center",
                            textfont=dict(size=11),
                            name=grp_name,
                        ))
                    fig_map_2b.update_yaxes(scaleanchor="x", scaleratio=1)
                    fig_map_2b.update_layout(
                        title=dict(text="<b>PA2b — 3 cặp cross-tuyến</b>",
                                    font=dict(size=12)),
                        height=420, plot_bgcolor="white",
                        xaxis_title="Easting (m)", yaxis_title="Northing (m)",
                        legend=dict(orientation="h", y=-0.18),
                    )
                    st.plotly_chart(fig_map_2b, use_container_width=True)

                # Caption tổng kết
                st.caption(
                    "Lc thiết kế per nhóm dùng **max** để bao trùm mọi HK trong "
                    "nhóm (an toàn). Khi thi công, mỗi nhóm thiết kế 1 loại cọc "
                    "đồng nhất → đơn giản hóa biện pháp thi công so với phân vùng "
                    "quantile bất quy tắc."
                )
            else:
                st.info("Chưa có dữ liệu `cdm_zone_design_results` cho QTT.")
        except Exception as _exc:
            st.warning(f"Không tải được O4: {_exc}")

        st.divider()

        # ════════ P. Bề mặt 3D — Thiết kế/TN/Sau lún + Trắc dọc đáy CDM ════════
        st.markdown("### P. Bề mặt 3D — Thiết kế / Tự nhiên / Sau lún")
        st.caption(
            "3 bề mặt 3D dựng từ 162 điểm grid: mặt thiết kế (đỏ nhạt), "
            "mặt tự nhiên (nâu), mặt sau lún (xanh). Lún tại mỗi grid point "
            "= IDW từ 6 HK với S_total tại ΔS hiện tại."
        )
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            grid3d = con.execute("""
                SELECT easting_m AS E, northing_m AS N,
                       elev_des_m, elev_nat_m
                FROM qtt_elevation_points ORDER BY northing_m, easting_m
            """).fetchall()
            hks_s = con.execute("""
                SELECT b.name, b.x_coord_m AS N, b.y_coord_m AS E,
                       d.S_total_cm
                FROM boreholes b
                JOIN cdm_zone_design_results d ON d.bh_name = b.name
                WHERE d.zone_code='QTT' AND d.delta_S_cm = ?
                  AND d.S_total_cm IS NOT NULL
            """, (dS_pick,)).fetchall()
        if grid3d and hks_s:
            Es3 = np.array([r["E"] for r in grid3d])
            Ns3 = np.array([r["N"] for r in grid3d])
            z_des = np.array([r["elev_des_m"] for r in grid3d])
            z_nat = np.array([r["elev_nat_m"] for r in grid3d])
            bh_E = np.array([r["E"] for r in hks_s])
            bh_N = np.array([r["N"] for r in hks_s])
            bh_S = np.array([r["S_total_cm"] for r in hks_s])
            S_at_grid = np.zeros(len(grid3d))
            for i in range(len(grid3d)):
                d = np.sqrt((Es3[i] - bh_E)**2 + (Ns3[i] - bh_N)**2)
                d = np.maximum(d, 0.5)
                w = 1.0 / d**2
                S_at_grid[i] = np.sum(w * bh_S) / np.sum(w)
            z_settled = z_des - S_at_grid / 100.0
            es_u = sorted(set(Es3.tolist()))
            ns_u = sorted(set(Ns3.tolist()))
            nE, nN = len(es_u), len(ns_u)
            if nE * nN == len(Es3):
                e_idx = {v: i for i, v in enumerate(es_u)}
                n_idx = {v: i for i, v in enumerate(ns_u)}
                Z_des = np.full((nN, nE), np.nan)
                Z_nat = np.full((nN, nE), np.nan)
                Z_set = np.full((nN, nE), np.nan)
                for i in range(len(Es3)):
                    ii = n_idx[Ns3[i]]; jj = e_idx[Es3[i]]
                    Z_des[ii, jj] = z_des[i]
                    Z_nat[ii, jj] = z_nat[i]
                    Z_set[ii, jj] = z_settled[i]
                fig_3d = go.Figure()
                fig_3d.add_trace(go.Surface(
                    z=Z_des, x=es_u, y=ns_u, name="Thiết kế",
                    colorscale=[[0, "#FFCDD2"], [1, "#FFCDD2"]],
                    showscale=False, opacity=0.65,
                ))
                fig_3d.add_trace(go.Surface(
                    z=Z_nat, x=es_u, y=ns_u, name="Tự nhiên",
                    colorscale=[[0, "#A1887F"], [1, "#A1887F"]],
                    showscale=False, opacity=0.65,
                ))
                fig_3d.add_trace(go.Surface(
                    z=Z_set, x=es_u, y=ns_u,
                    name=f"Sau lún (ΔS={dS_pick}cm)",
                    colorscale=[[0, "#1976D2"], [1, "#1976D2"]],
                    showscale=False, opacity=0.85,
                ))
                fig_3d.update_layout(
                    title=dict(text=f"<b>Bề mặt 3D — ΔS = {dS_pick} cm</b>",
                                font=dict(size=13)),
                    height=600,
                    scene=dict(
                        xaxis_title="Easting (m)",
                        yaxis_title="Northing (m)",
                        zaxis_title="Cao độ (m)",
                        aspectmode="manual",
                        aspectratio=dict(x=2, y=2, z=0.4),
                    ),
                )
                st.plotly_chart(fig_3d, use_container_width=True)

        st.divider()

        # ════════ P2. Trắc dọc đáy cọc CDM ════════
        st.markdown(f"### P2. Trắc dọc đáy cọc CDM (ΔS = {dS_pick} cm)")
        with sqlite3.connect(_db()) as con:
            con.row_factory = sqlite3.Row
            lc_rows_for_chart = con.execute("""
                SELECT bh_name, delta_S_cm, Lc_m, tip_depth_m, p_optimal_m,
                       S1_cm, S2_cm, S_total_cm, ok, penetrates_full,
                       H_soft_m, cdm_top_elev_m
                FROM cdm_zone_design_results
                WHERE zone_code = 'QTT'
            """).fetchall()
        lc_list = [dict(r) for r in lc_rows_for_chart]
        fig_tip = cdm_tip_profile(meta["boreholes_summary"], lc_list,
                                    dS_cm=float(dS_pick),
                                    layers_by_bh=layers_by_bh)
        st.plotly_chart(fig_tip, use_container_width=True)

        # Cảnh báo cọc trong lớp bùn
        warns = floating_pile_warning_table(
            meta["boreholes_summary"], lc_list, layers_by_bh,
            dS_cm=float(dS_pick), threshold=0.8,
        )
        if warns:
            st.error(
                f"**Cảnh báo {len(warns)} HK có cọc trong lớp bùn nghiêm trọng "
                f"(p/H_soft < 0.8):**"
            )
            st.dataframe(pd.DataFrame(warns), hide_index=True,
                          use_container_width=True)
            st.caption(
                "Cọc trong lớp bùn trong bùn → tiềm ẩn rủi ro lún dài hạn S2 lớn, "
                "ổn định nhóm cọc yếu. Khuyến nghị xem xét tăng Lc xuyên xuống "
                "lớp cứng (lớp 3 hoặc sâu hơn) hoặc giảm khoảng cách s."
            )
        else:
            st.success("Không có HK nào cọc trong lớp bùn nghiêm trọng (p/H_soft ≥ 0.8)")

        st.divider()

        # (Section "Biểu đồ ứng suất" đã được di chuyển lên sau A2)
        # ════════ Q. Xuất báo cáo Word + DXF ════════
        st.markdown("### Q. Xuất báo cáo Word — Quyết định thiết kế CDM QTT")
        st.caption(
            "Báo cáo `build_qtt_decision_docx` đầy đủ: bảng Lc per HK × ΔS, "
            "tiêu chí thiết kế, kiểm tra độ bằng phẳng, phân vùng, biểu đồ, "
            "kết luận."
        )
        word_cols = st.columns([2, 1, 1])
        with word_cols[0]:
            wco_name = st.text_input(
                "Tên công ty (header)",
                value=st.session_state.get("export_co_name", ""),
                key="_qtt_word_co",
            )
            wco_staff = st.text_input(
                "Người thực hiện (footer)",
                value=st.session_state.get("export_co_staff", ""),
                key="_qtt_word_staff",
            )
            # §72 Task Q — chọn ΔS để xuất chi tiết
            dS_export = st.multiselect(
                "Các mức ΔS xuất chi tiết trong báo cáo",
                options=[10.0, 15.0, 20.0, 25.0, 30.0, 40.0],
                default=[10.0, 15.0, 20.0, 25.0],
                key="_qtt_word_ds",
                help="Mỗi ΔS sinh 1 chương riêng trong báo cáo Word "
                     "(bảng Lc per HK + heatmap + phân vùng + smoothness).",
            )
        with word_cols[1]:
            st.markdown(" ")
            if st.button("Tạo báo cáo Word QTT", type="primary",
                         use_container_width=True, key="_qtt_word_gen"):
                with st.spinner("Đang dựng báo cáo..."):
                    try:
                        from qtt_cdm_report import build_qtt_decision_docx
                        # Prepare data
                        meta_word = {
                            "zone": "QTT",
                            "project": "Quảng Trường Trung Tâm TP.HCM",
                            "location": "Phường An Khánh, Thành phố Thủ Đức",
                            "co_name": wco_name, "co_staff": wco_staff,
                            "delta_S_values_cm": dS_export or [10.0, 15.0, 20.0, 25.0],
                        }
                        with sqlite3.connect(_db()) as con:
                            con.row_factory = sqlite3.Row
                            lc_matrix = [dict(r) for r in con.execute(
                                "SELECT * FROM cdm_zone_design_results "
                                "WHERE zone_code='QTT' ORDER BY bh_name, delta_S_cm"
                            ).fetchall()]
                            smooth_pairs = [dict(r) for r in con.execute(
                                "SELECT * FROM cdm_zone_smoothness_results "
                                "WHERE zone_code='QTT' ORDER BY delta_S_cm, hk_i, hk_j"
                            ).fetchall()]
                            grid_points = [dict(r) for r in con.execute(
                                "SELECT easting_m AS E, northing_m AS N, "
                                "elev_des_m, elev_nat_m FROM qtt_elevation_points"
                            ).fetchall()]
                        criteria = {
                            "road_class": road_class[0],
                            "position": position[0],
                            "dS_limit_cm": dS_limit,
                            "i_inv_threshold": 125,
                        }
                        zoning = {"n_zones": 4,
                                   "stats": [{"zone_id": z - 1,
                                                "Lc_design": 0}
                                              for z in range(1, 5)]}
                        grid_meta = {"n_points": len(grid_points)}
                        hks_with_S = [{"name": r["bh_name"],
                                        "E": next((b["E"] for b in meta["boreholes_summary"]
                                                   if b["name"] == r["bh_name"]), 0),
                                        "N": next((b["N"] for b in meta["boreholes_summary"]
                                                   if b["name"] == r["bh_name"]), 0)}
                                       for r in lc_matrix
                                       if r["delta_S_cm"] == dS_pick]
                        data = build_qtt_decision_docx(
                            meta=meta_word, lc_matrix=lc_matrix,
                            criteria=criteria, smoothness_pairs=smooth_pairs,
                            zoning=zoning, grid_meta=grid_meta,
                            grid_points=grid_points, hks_with_S=hks_with_S,
                        )
                        st.session_state["_qtt_word_bytes"] = data
                        st.success(f"Đã tạo báo cáo ({len(data)/1024:.0f} KB)")
                    except Exception as e:
                        st.error(f"Lỗi xuất Word: {e}")
                        import traceback
                        st.code(traceback.format_exc())
        with word_cols[2]:
            st.markdown(" ")
            wd = st.session_state.get("_qtt_word_bytes")
            if wd:
                import datetime as _dt2
                fn = f"BaoCao_QTT_CDM_{_dt2.date.today().strftime('%Y%m%d')}.docx"
                st.download_button(
                    "Tải file .docx", data=wd, file_name=fn,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True, key="_qtt_word_dl",
                )

        st.divider()


        # ═══════════════════════════════════════════════════════════════
        # SECTIONS REMOVED (consolidated to avoid duplicate):
        #   G (Lc per HK × ΔS pivot)        → merged into J (J2b chi tiết)
        #   J2 (bar group 4 ΔS)             → merged into J (J2b stacked)
        #   E (DXF status)                  → merged into B
        #   P (Verify chỉ tiêu cơ lý SQLite) → merged into G (Chỉ tiêu cơ lý)
        # ═══════════════════════════════════════════════════════════════

    except Exception as _exc:
        st.error(f"Lỗi page Zone QTT: {_exc}")
        st.code(traceback.format_exc())