"""
scripts/pages/no_treat_page.py — Trang "Lún nền chưa xử lý".

Phương án tính lún nền tự nhiên CHƯA xử lý với tải gây lún:
    q = γ_đắp · (cao độ thiết kế − cao độ tự nhiên của hố khoan)
cho các hố khoan vùng CDM. Auto-compute (§9b), trải phẳng (§17).

Gọi từ app_cdm.py khi page = 'no_treat'.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def _nc_radio(st, key: str) -> bool:
    """Lựa chọn giả thiết cố kết lớp sét yếu (e₀≥1). Trả True nếu coi là NC (bùn chảy).
    Chỉ THÊM lựa chọn — không bỏ phương án nào (NC mặc định + xét quá cố kết)."""
    _c = st.radio(
        "Giả thiết cố kết lớp sét yếu (e₀≥1)",
        ["Cố kết thường NC — bùn chảy (Pc=σ'v0)", "Xét quá cố kết — theo Pc thí nghiệm"],
        index=0, horizontal=True, key=key,
        help="NC (TCCS 41 CT 26): bùn trạng thái chảy, dùng Cc toàn bộ → lún lớn (an toàn). "
             "Quá cố kết (CT 25/27): dùng Pc thí nghiệm, có nhánh nở Cr → lún nhỏ hơn.")
    return _c.startswith("Cố kết thường")


def _m_input(st, key: str) -> float:
    """Hệ số lún tức thời m (TCCS 41:2022 Điều 9.2.1 SĐ1, CT 30a/30b).
    S = m·Sc; lún tức thời lớp bùn Si = (m−1)·Sc. m=1,0 → bỏ qua lún tức thời bùn."""
    return st.number_input(
        "Hệ số lún tức thời m (TCCS 41 CT 30a/30b)", 1.0, 1.4, 1.1, 0.05, key=key,
        help="S = m·Sc (30a); lún tức thời lớp bùn do đẩy trồi ngang Si=(m−1)·Sc (30b). "
             "m=1,1 khi có biện pháp hạn chế đẩy trồi ngang; đắp càng cao, đất càng yếu → m "
             "càng lớn (đến 1,4). m=1,0 = không xét lún tức thời của bùn.")


def _report_table(st, df) -> None:
    """Render bảng theo chuẩn dự án (header đậm navy, thân 12pt, zebra, lưới) — đồng bộ Word.
    Nếu df có index không mặc định (đã set_index) → đưa index thành cột đầu để hiển thị."""
    import pandas as _pd
    from core.report_style import df_to_report_html
    if not isinstance(df.index, _pd.RangeIndex):
        df = df.reset_index()
    st.markdown(df_to_report_html(df), unsafe_allow_html=True)


def render() -> None:
    import pandas as pd
    import streamlit as st
    from core.report_style import html_css_block

    from cdm_no_treat_settlement import (
        LEVEE_KEY, ZONE_PREFIX, compute_no_treat, compute_no_treat_6zones,
        compute_zone_fill_settlement, resolve_boreholes, save_results,
    )

    # Nhúng CSS bảng chuẩn 1 lần cho toàn trang (mọi chế độ xem)
    st.markdown(html_css_block(), unsafe_allow_html=True)

    st.title("Lún nền chưa xử lý — vùng CDM")
    st.caption(
        "Tính tổng độ lún cố kết của nền đất tự nhiên KHI CHƯA xử lý, với tải trọng gây "
        "lún lấy bằng chiều cao đắp từ cao độ tự nhiên lên cao độ thiết kế: "
        "q = γ_đắp · (CĐTK − CĐTN). Đây là cơ sở so sánh với phương án xử lý bằng cọc CDM."
    )

    _mode = st.radio(
        "Chế độ xem",
        ["Theo hố khoan (chọn vùng)", "Theo 6 vùng CDM (Bờ kè)",
         "Theo bảng 6 vùng (HK đại diện)", "Hố khoan QTT (mượn hố gần nhất)"],
        horizontal=True, key="nt_mode",
    )
    if _mode.startswith("Theo 6"):
        _render_6zones(st, compute_no_treat_6zones)
        return
    if _mode.startswith("Theo bảng"):
        _render_zone_fill(st, compute_zone_fill_settlement)
        return
    if _mode.startswith("Hố khoan QTT"):
        _render_qtt(st)
        return

    # ─── Thông số (live) ──────────────────────────────────────────────────
    st.markdown("### Thông số đầu vào")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        zone = st.selectbox("Vùng", [LEVEE_KEY] + list(ZONE_PREFIX.keys()), index=0, key="nt_zone")
    with c2:
        design_elev = st.number_input("Cao độ thiết kế CĐTK (m)", -10.0, 20.0, 2.70, 0.05, key="nt_de")
    with c3:
        gamma_fill = st.number_input("Dung trọng đắp γ (kN/m³)", 14.0, 24.0, 18.0, 0.5, key="nt_g")
    with c4:
        gwt_elev = st.number_input("Cao độ mực nước ngầm (m)", -10.0, 10.0, 0.0, 0.1, key="nt_gw")
    with c5:
        disp = st.selectbox("Phân bố Δσ", ["1D (không đổi)", "Boussinesq dải"], index=0, key="nt_disp")
    B_load = None
    if disp.startswith("Boussinesq"):
        B_load = st.number_input("Bề rộng diện gia tải B (m)", min_value=1.0, value=20.0, step=1.0, key="nt_B")

    st.caption(
        "Lún tính theo nguyên tắc vùng ảnh hưởng (§71): chia phân tố 2 m, tích phân tới "
        "đáy vùng ảnh hưởng (Δσ/σ'v0 < 10%), mở rộng dưới đáy hố khoan nếu cần, phân nhánh "
        "sét (cố kết Terzaghi OC/NC) và cát (đàn hồi theo SPT)."
    )

    bhs = resolve_boreholes(zone)
    if not bhs:
        st.warning("Không tìm thấy hố khoan trong vùng này.")
        return
    if zone == LEVEE_KEY:
        st.caption("Chỉ tính các hố khoan trên tuyến cừ bờ kè (on_sw_alignment=1), "
                   "KHÔNG đưa KE-HK8 (vị trí cọc thử CDM) vào tính toán: " + ", ".join(bhs) + ".")

    rows = compute_no_treat(bhs, design_elev_m=design_elev, gamma_fill=gamma_fill,
                            gwt_elev_m=gwt_elev, B_load_m=B_load)

    st.divider()
    st.markdown(f"### Kết quả lún nền chưa xử lý — {zone}")
    st.latex(r"q = \gamma_{\text{đắp}} \cdot (CĐTK - CĐTN) \quad ; \quad "
             r"S = \sum_i \frac{h_i\,C_c}{1+e_{0i}}\log_{10}\frac{\sigma'_{vf}}{\sigma'_{v0}}")

    df = pd.DataFrame([{
        "Hố khoan": r.bh_name,
        "CĐTN (m)": round(r.CDTN_m, 2),
        "Chiều cao đắp (m)": round(r.H_fill_m, 2),
        "Tải q (kN/m²)": round(r.q_kPa, 1),
        "Đáy vùng ảnh hưởng (m)": round(r.d_influence_m, 1),
        "Số phân tố": r.n_sublayers,
        "Lún S∞ (cm)": round(r.S_total_cm, 1),
        "Lún 15 năm (cm)": round(r.S_15yr_cm, 1),
        "Ghi chú": (r.warning or "")[:30],
    } for r in rows])
    _report_table(st, df)

    valid = [r for r in rows if r.S_total_cm > 0]
    if valid:
        smax = max(r.S_total_cm for r in valid)
        smin = min(r.S_total_cm for r in valid)
        savg = sum(r.S_total_cm for r in valid) / len(valid)
        m1, m2, m3 = st.columns(3)
        m1.metric("Lún lớn nhất", f"{smax:.1f} cm",
                  delta=next(r.bh_name for r in valid if r.S_total_cm == smax), delta_color="off")
        m2.metric("Lún trung bình", f"{savg:.1f} cm")
        m3.metric("Lún nhỏ nhất", f"{smin:.1f} cm",
                  delta=next(r.bh_name for r in valid if r.S_total_cm == smin), delta_color="off")

        try:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_bar(
                x=[r.bh_name for r in rows], y=[r.S_total_cm for r in rows],
                text=[f"{r.S_total_cm:.2f}" for r in rows], textposition="outside",
                textfont=dict(size=16), marker_color="#C62828", name="Lún chưa xử lý",
            )
            fig.update_layout(
                title=f"Lún nền chưa xử lý theo hố khoan — {zone}",
                yaxis_title="Lún S (cm)", height=420, font=dict(size=16), legend=dict(font=dict(size=16)), margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)

            fig2 = go.Figure()
            fig2.add_bar(x=[r.bh_name for r in rows], y=[r.H_fill_m for r in rows],
                         text=[f"{r.H_fill_m:.2f}" for r in rows], textposition="outside",
                         textfont=dict(size=16), marker_color="#1565C0", name="Chiều cao đắp")
            fig2.update_layout(title="Chiều cao đắp (CĐTK − CĐTN) theo hố khoan",
                               yaxis_title="H đắp (m)", height=360, font=dict(size=16),
                               margin=dict(t=40, b=10))
            st.plotly_chart(fig2, use_container_width=True)
        except Exception:
            pass

    st.caption("Lưu ý: lún này là của nền CHƯA xử lý (tham chiếu). Khi xử lý bằng cọc CDM, "
               "tổng lún giảm còn S₁ (khối gia cố) + S₂ (cố kết dưới mũi) — xem trang thiết kế CDM.")

    if st.button("Lưu kết quả", key="nt_save", type="primary"):
        try:
            save_results(zone, rows, gamma_fill)
            st.success("Đã lưu kết quả lún nền chưa xử lý.")
        except Exception as e:  # noqa: BLE001
            st.error(f"Lỗi lưu: {e}")


def _render_qtt(st) -> None:
    """Chế độ: lún nền chưa xử lý cho hố khoan QTT (ND-*) — số liệu từng hố,
    cao độ thiết kế lấy từ lưới cao độ QTT. Trình bày GIỐNG 'Theo bảng 6 vùng'."""
    import sqlite3
    import pandas as pd
    from pathlib import Path
    from cdm_layer_avg_settlement import settle_avg, time_history

    st.markdown("### Lún nền chưa xử lý — hố khoan QTT (Quảng Trường Trung Tâm)")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        gamma_fill = st.number_input("Dung trọng đắp γ (kN/m³)", 14.0, 24.0, 18.0, 0.5, key="qtt_g")
    with c2:
        gwt_elev = st.number_input("Cao độ mực nước ngầm (m)", -10.0, 10.0, 0.0, 0.1, key="qtt_gw")
    with c3:
        disp = st.selectbox("Phân bố Δσ", ["1D (không đổi)", "Boussinesq dải"], index=0, key="qtt_disp")
    with c4:
        drain2 = st.checkbox("Cố kết thoát nước 2 mặt (H = H_sét/2)", value=True, key="qtt_drain2")
    B_load = None
    if disp.startswith("Boussinesq"):
        B_load = st.number_input("Bề rộng diện gia tải B (m)", min_value=1.0, value=20.0, step=1.0, key="qtt_B")
    _nc_qtt = _nc_radio(st, "qtt_nc")
    _m_qtt = _m_input(st, "qtt_m")

    st.caption("Mỗi hố khoan QTT dùng SỐ LIỆU RIÊNG; cao độ thiết kế mặc định lấy từ lưới cao "
               "độ QTT (điểm gần nhất) — **sửa CĐTN/CĐTK trong bảng bên dưới, kết quả tự cập "
               "nhật**. Hố thiếu thí nghiệm nén dùng số liệu lớp đại diện. Tải gây lún "
               "q = γ·H_đắp (CĐTK − CĐTN). Lún tính trong vùng ảnh hưởng (§71). "
               "**Lún cố kết theo thời gian chỉ phát triển ở lớp sét e₀ > 1; lớp cát và sét "
               "chặt e₀ < 1 lún tức thời.**")

    # CĐTK mặc định mỗi hố QTT từ lưới qtt_elevation_points (điểm gần nhất)
    # Đọc CÙNG DB cục bộ mà settle_avg dùng → CĐTK/CĐTN và tham số lún cùng 1 nguồn
    _local = Path(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
    _db = str(_local if _local.exists() else (Path(__file__).resolve().parent.parent.parent / "data" / "TTHC.sqlite"))
    _des, _elev, bhs = {}, {}, []
    try:
        con = sqlite3.connect(_db)
        bhs = [r[0] for r in con.execute(
            "SELECT name FROM boreholes WHERE name LIKE 'ND-%' ORDER BY name").fetchall()]
        _elev = dict(con.execute(
            "SELECT name, elevation_m FROM boreholes WHERE name LIKE 'ND-%'").fetchall())
        _xy = {r[0]: (r[1], r[2]) for r in con.execute(
            "SELECT name, x_coord_m, y_coord_m FROM boreholes WHERE name LIKE 'ND-%'").fetchall()}
        _grid = con.execute(
            "SELECT easting_m, northing_m, elev_des_m FROM qtt_elevation_points").fetchall()
        con.close()
        # x_coord = Northing, y_coord = Easting → điểm lưới gần nhất → elev_des_m
        for _b, (_nx, _ey) in _xy.items():
            if _nx is None or _ey is None or not _grid:
                continue
            _best, _bd = None, 1e18
            for _e, _n, _ed in _grid:
                _d = ((_e - _ey) ** 2 + (_n - _nx) ** 2) ** 0.5
                if _d < _bd:
                    _bd, _best = _d, _ed
            if _best is not None:
                _des[_b] = float(_best)
    except Exception:
        bhs = []

    if not bhs:
        st.info("Không đọc được hố khoan QTT (ND-*).")
        return

    # ── Bảng nhập cao độ từng hố — sửa CĐTN/CĐTK → kết quả tự tính lại ────
    st.markdown("**Cao độ từng hố khoan ND (sửa được — kết quả bảng tổng hợp tự cập nhật):**")
    _ed_default = pd.DataFrame([{
        "Hố khoan": b,
        "CĐTN (m)": round(float(_elev.get(b, 0.0)), 2),
        "CĐTK (m)": round(float(_des.get(b, 2.70)), 2),
    } for b in bhs])
    _edited = st.data_editor(
        _ed_default, key="qtt_elev_editor", hide_index=True, use_container_width=True,
        column_config={
            "Hố khoan": st.column_config.TextColumn("Hố khoan", disabled=True),
            "CĐTN (m)": st.column_config.NumberColumn("CĐTN (m)", format="%.2f", step=0.05,
                                                      help="Cao độ tự nhiên — sửa để tính lại tải đắp"),
            "CĐTK (m)": st.column_config.NumberColumn("CĐTK (m)", format="%.2f", step=0.05,
                                                      help="Cao độ thiết kế — mặc định lấy từ lưới cao độ QTT"),
        },
    )
    # Lưu override để mục chi tiết phân tố dùng cùng giá trị
    _over = {str(r["Hố khoan"]): (float(r["CĐTN (m)"]), float(r["CĐTK (m)"]))
             for _, r in _edited.iterrows()}
    st.session_state["qtt_elev_over"] = _over

    rows, full_results = [], {}
    for _, r in _edited.iterrows():
        b = str(r["Hố khoan"])
        cdtn = float(r["CĐTN (m)"]); cdtk = float(r["CĐTK (m)"])
        H = max(0.0, cdtk - cdtn)
        try:
            rr = settle_avg(b, H_fill_m=H, gamma_fill=gamma_fill,
                            gwt_depth_m=max(0.0, cdtn - gwt_elev), B_load_m=B_load,
                            nc_soft_clay=_nc_qtt)
        except Exception:
            continue
        th = time_history(rr, [15.0, 30.0, 50.0], double_drainage=drain2, m_coef=_m_qtt)
        full_results[b] = rr
        rows.append({
            "zone": "QTT", "bh": b, "CDTN_m": round(cdtn, 2), "H_fill_m": round(H, 2),
            "q_kPa": rr["q_kPa"], "d_influence_m": rr["stop_depth_m"],
            "S_imm_cm": th["S_immediate_cm"], "S_consol_cm": th["S_consol_cm"],
            "Si_mud_cm": th["Si_mud_cm"], "S_total_cm": th["S_inf_cm"],
            "U15_pct": th["U_pct"][0], "S_15yr_cm": th["St_cm"][0], "residual15_cm": th["residual_cm"][0],
            "U30_pct": th["U_pct"][1], "S_30yr_cm": th["St_cm"][1], "residual30_cm": th["residual_cm"][1],
            "U50_pct": th["U_pct"][2], "S_50yr_cm": th["St_cm"][2], "residual50_cm": th["residual_cm"][2],
        })

    if not rows:
        st.info("Không có tải gây lún (CĐTK ≤ CĐTN ở mọi hố). Tăng CĐTK hoặc giảm CĐTN.")
        return

    _render_settlement_results(st, rows, full_results, gamma_fill=gamma_fill,
                               gwt_elev=gwt_elev, B_load=B_load, drain2=drain2,
                               bcl=None, use_bcl=False,
                               chart_title="Lún nền chưa xử lý — hố khoan QTT",
                               assume0=False, nc_soft_clay=_nc_qtt, m_coef=_m_qtt)


def _render_settlement_results(st, rows, full_results, *, gamma_fill, gwt_elev,
                               B_load, drain2, bcl=None, use_bcl=False,
                               chart_title='Lún nền chưa xử lý', assume0=False,
                               nc_soft_clay=True, m_coef=1.0):
    """Render chung: bảng tổng hợp + biểu đồ + công thức + chi tiết phân tố + lún-thời gian.
    Dùng cho cả "Theo bảng 6 vùng" và "Hố khoan QTT"."""
    import pandas as pd
    df = pd.DataFrame([{
        "Vùng": r["zone"], "Hố khoan": r["bh"], "Cao độ TN (m)": r["CDTN_m"],
        "Chiều dày đắp (m)": r["H_fill_m"], "Tải q (kN/m²)": r["q_kPa"],
        "Đáy vùng ảnh hưởng (m)": r["d_influence_m"],
        "Lún tức thời bùn Si=(m−1)Sc (cm)": r.get("Si_mud_cm", "—"),
        "Lún tức thời (tổng, cm)": r.get("S_imm_cm", "—"),
        "Lún cố kết Sc (cm)": r.get("S_consol_cm", "—"),
        "Lún tổng S∞ (cm)": r["S_total_cm"],
        "U 15 năm (%)": r.get("U15_pct", "—"),
        "Lún 15 năm (cm)": r["S_15yr_cm"],
        "Lún còn lại 15 năm (cm)": r.get("residual15_cm", "—"),
        "U 30 năm (%)": r.get("U30_pct", "—"),
        "Lún 30 năm (cm)": r.get("S_30yr_cm", "—"),
        "Lún còn lại 30 năm (cm)": r.get("residual30_cm", "—"),
        "U 50 năm (%)": r.get("U50_pct", "—"),
        "Lún 50 năm (cm)": r.get("S_50yr_cm", "—"),
        "Lún còn lại 50 năm (cm)": r.get("residual50_cm", "—"),
    } for r in rows])
    _report_table(st, df)
    st.caption("Lún tổng S = m·Sc (TCCS 41 CT 30a); lún tức thời lớp bùn Si=(m−1)·Sc do "
               "đẩy trồi ngang (CT 30b). Lún t năm = lún tức thời + U(t)·Sc (chỉ lớp sét e₀>1). "
               "Mốc: 15 năm = mặt đường mềm, 30 năm = mặt đường cứng, 50 năm = dài hạn.")
    if assume0:
        st.caption("Đã giả định CĐTN = 0,0 m cho các hố có CĐTN > 0 (KE-HK11, HK5, HK2): "
                   "phần san lấp gần đây trở thành tải đắp bổ sung → tải gây lún và độ lún tăng.")

    try:
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_bar(x=[f"{r['zone']}\n{r['bh']}" for r in rows],
                    y=[r["S_total_cm"] for r in rows],
                    text=[f"{r['S_total_cm']:.2f}" for r in rows], textposition="outside",
                    textfont=dict(size=16), marker_color="#C62828", name="Lún S∞")
        fig.add_bar(x=[f"{r['zone']}\n{r['bh']}" for r in rows],
                    y=[r["S_15yr_cm"] for r in rows],
                    text=[f"{r['S_15yr_cm']:.2f}" for r in rows], textposition="outside",
                    textfont=dict(size=16), marker_color="#F9A825", name="Lún 15 năm")
        fig.add_bar(x=[f"{r['zone']}\n{r['bh']}" for r in rows],
                    y=[r.get("S_30yr_cm", 0) for r in rows],
                    text=[f"{r.get('S_30yr_cm', 0):.2f}" for r in rows], textposition="outside",
                    textfont=dict(size=16), marker_color="#EF6C00", name="Lún 30 năm")
        fig.add_bar(x=[f"{r['zone']}\n{r['bh']}" for r in rows],
                    y=[r.get("S_50yr_cm", 0) for r in rows],
                    text=[f"{r.get('S_50yr_cm', 0):.2f}" for r in rows], textposition="outside",
                    textfont=dict(size=16), marker_color="#8D6E63", name="Lún 50 năm")
        fig.update_layout(title=chart_title,
                          barmode="group", yaxis_title="Lún (cm)", height=420,
                          font=dict(size=16), legend=dict(font=dict(size=16)), margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass

    # ── Công thức + chi tiết từng phân tố (chỉ phương pháp trung bình theo lớp) ──
    if full_results:
        st.divider()
        st.markdown("#### Công thức tính lún cố kết — TCCS 41:2022 Điều 9.1 (phân nhánh theo loại đất + e₀)")
        _gt = ("**đang dùng: Cố kết thường NC — bùn chảy (Pc = σ'v0)**"
               if nc_soft_clay else "**đang dùng: xét quá cố kết theo Pc thí nghiệm**")
        st.caption("Giả thiết lớp sét yếu: " + _gt)
        st.markdown(r"**Lún tổng & lún tức thời lớp bùn — TCCS 41:2022 Điều 9.2.1 (Sửa đổi 1), "
                    rf"hệ số m = {m_coef:g}:**")
        st.latex(r"S = m\cdot S_c\ \ (30a); \qquad S_i = (m-1)\,S_c\ \ (30b)")
        st.caption("S = tổng lún · Sc = lún cố kết (Điều 9.1) · Si = lún tức thời lớp bùn "
                   "(đẩy trồi ngang dưới tải đắp) · m = 1,1–1,4 (hệ số kinh nghiệm).")
        st.markdown("**Lớp cát (hạt rời) → lún đàn hồi tức thời:**")
        st.latex(r"S_i = \frac{\Delta\sigma \cdot h_i}{E_s}")
        st.markdown(r"**Lớp sét yếu ($e_0 \ge 1$) → nén cố kết Terzaghi 1D (e–lg p), "
                    r"3 trường hợp theo $\sigma'_{vz}$ và $\sigma'_{pz}$:**")
        st.markdown(r"• Cố kết thường NC ($\sigma'_{vz}=\sigma'_{pz}$) — **CT (26)**:")
        st.latex(r"S_c=\sum_{i=1}^{n}\frac{H_i}{1+e_0^i}\,C_c^i\,\lg\frac{\sigma'_z+\sigma'_{vz}}{\sigma'_{vz}}"
                 r"\qquad\text{(26)}")
        st.markdown(r"• Quá cố kết, tải vượt $P_c$ ($\sigma'_z \ge \sigma'_{pz}-\sigma'_{vz}$) — **CT (25)**:")
        st.latex(r"S_c=\sum\frac{H_i}{1+e_0^i}\!\left[C_r^i\,\lg\frac{\sigma'_{pz}}{\sigma'_{vz}}"
                 r"+C_c^i\,\lg\frac{\sigma'_z+\sigma'_{vz}}{\sigma'_{pz}}\right]\qquad\text{(25)}")
        st.markdown(r"• Quá cố kết, tải chưa vượt $P_c$ ($\sigma'_z < \sigma'_{pz}-\sigma'_{vz}$) — **CT (27)**:")
        st.latex(r"S_c=\sum\frac{H_i}{1+e_0^i}\,C_r^i\,\lg\frac{\sigma'_z+\sigma'_{vz}}{\sigma'_{vz}}"
                 r"\qquad\text{(27)}")
        st.markdown(r"**Lớp sét chặt ($e_0 < 1$) → mô đun tổng biến dạng — CT (28):**")
        st.latex(r"S_c=\sum_{i=1}^{n}\frac{\sigma'_z}{E_{oed}^i}\,H_i\qquad\text{(28)};\qquad "
                 r"E_{oed} = \frac{1+e_0}{a_{1-2}}\times 98{,}0665 \ \text{kPa}")
        st.caption(r"Ký hiệu (TCCS 41): σ'vz = ứng suất bản thân (= σ'v0) · σ'z = ứng suất "
                   r"do tải đắp (= Δσ) · σ'pz = áp lực tiền cố kết (Pc) · Cc = chỉ số nén · "
                   r"Cr = chỉ số nén hồi phục (≈ Cs) · Hi ≤ 2,0 m.")
        st.latex(r"\sigma'_{vz}(z) = \sum \gamma'\,h \ \ (\gamma'=\gamma-9{,}81\ \text{dưới MNN}); \quad"
                 r"\text{vùng ảnh hưởng: dừng khi } \frac{\sigma'_z}{\sigma'_{vz}} < 10\%\ (\S 71)")

        st.markdown("#### Bảng chi tiết từng phân tố")
        # Thêm hố khoan QTT (ND-*) để xem chi tiết, dùng chung định dạng
        import sqlite3 as _sql2
        from pathlib import Path as _P2
        _local2 = _P2(r"C:\Users\bayng\TTHC_local\TTHC.sqlite")
        _db2 = str(_local2 if _local2.exists() else (_P2(__file__).resolve().parent.parent.parent / "data" / "TTHC.sqlite"))
        _qtt_des = {}     # CĐTK mặc định mỗi hố QTT (từ qtt_elevation_points điểm lưới gần nhất)
        try:
            _con2 = _sql2.connect(_db2)
            _qtt = [r[0] for r in _con2.execute(
                "SELECT name FROM boreholes WHERE name LIKE 'ND-%' ORDER BY name").fetchall()]
            _elev_map = dict(_con2.execute("SELECT name, elevation_m FROM boreholes").fetchall())
            _bh_xy = {r[0]: (r[1], r[2]) for r in _con2.execute(
                "SELECT name, x_coord_m, y_coord_m FROM boreholes WHERE name LIKE 'ND-%'").fetchall()}
            _grid = _con2.execute(
                "SELECT easting_m, northing_m, elev_des_m FROM qtt_elevation_points").fetchall()
            _con2.close()
            # x_coord = Northing, y_coord = Easting; điểm lưới gần nhất → elev_des_m
            for _b, (_nx, _ey) in _bh_xy.items():
                if _nx is None or _ey is None or not _grid:
                    continue
                _best, _bd = None, 1e18
                for _e, _n, _ed in _grid:
                    _d = ((_e - _ey) ** 2 + (_n - _nx) ** 2) ** 0.5
                    if _d < _bd:
                        _bd, _best = _d, _ed
                if _best is not None:
                    _qtt_des[_b] = float(_best)
        except Exception:
            _qtt, _elev_map = [], {}
        _opts = list(full_results.keys()) + [b for b in _qtt if b not in full_results]
        bh_sel = st.selectbox("Chọn hố khoan xem chi tiết", _opts, key="zf_detail_bh")
        if bh_sel in _qtt:
            # Hố QTT: cho NHẬP LẠI cao độ thiết kế + cao độ tự nhiên → tính lại tải gây lún
            from cdm_layer_avg_settlement import settle_avg
            _bcl_p = locals().get("bcl") if locals().get("use_bcl") else None
            # Mặc định lấy theo giá trị đã sửa ở bảng tổng hợp QTT (nếu có) → đồng nhất
            _ov = st.session_state.get("qtt_elev_over", {})
            _def_cdtn, _def_cdtk = _ov.get(
                bh_sel, (float(_elev_map.get(bh_sel, 0.0)), float(_qtt_des.get(bh_sel, 2.70))))
            qc1, qc2 = st.columns(2)
            with qc1:
                _cdtk_q = st.number_input(f"Cao độ thiết kế CĐTK — {bh_sel} (m)", -10.0, 20.0,
                                          float(_def_cdtk), 0.05,
                                          key=f"qtt_cdtk_{bh_sel}",
                                          help="Mặc định theo bảng tổng hợp (hoặc lưới cao độ QTT)")
            with qc2:
                _cdtn_q = st.number_input(f"Cao độ tự nhiên CĐTN — {bh_sel} (m)", -20.0, 20.0,
                                          float(_def_cdtn), 0.05,
                                          key=f"qtt_cdtn_{bh_sel}")
            _Hq = max(0.0, _cdtk_q - _cdtn_q)
            rr = settle_avg(bh_sel, H_fill_m=_Hq, gamma_fill=gamma_fill,
                            gwt_depth_m=max(0.0, _cdtn_q - gwt_elev), B_load_m=B_load,
                            bcl_params=_bcl_p, nc_soft_clay=nc_soft_clay)
            st.caption(f"Hố QTT {bh_sel}: CĐTK {_cdtk_q:.2f} − CĐTN {_cdtn_q:.2f} → "
                       f"H_đắp = {_Hq:.2f} m, q = γ·H = {rr['q_kPa']:.1f} kN/m².")
        else:
            rr = full_results[bh_sel]
        st.caption(f"{bh_sel}: q = {rr['q_kPa']} kN/m² · đáy vùng ảnh hưởng {rr['stop_depth_m']} m · "
                   f"{rr['n_layers']} phân tố · {rr['stop_reason']} · S∞ = {rr['S_total_cm']} cm")
        if not rr.get("layers"):
            st.info("Không có tải gây lún (CĐTK ≤ CĐTN) → không có phân tố. "
                    "Tăng cao độ thiết kế hoặc chọn hố khoan khác.")
            return
        ddf = pd.DataFrame([{
            "STT": i + 1,
            "Độ sâu giữa (m)": L["z_mid_m"], "Lớp": L["symbol"],
            "γ (kN/m³)": L["gamma"],
            "γ' (kN/m³)": L["gamma_eff"],
            "Dưới MNN": "Có" if L.get("below_gwt") else "Không",
            "e₀": L.get("e0") if L.get("e0") is not None else "—",
            "Cc": L.get("Cc") if L.get("Cc") is not None else "—",
            "Cs": L.get("Cs") if L.get("Cs") is not None else "—",
            "P_c (kPa)": L.get("PC_kPa") if L.get("PC_kPa") is not None else "—",
            "σ'v0 (kPa)": L["sigma_v0_kPa"],
            "Δσ (kPa)": L["dsigma_kPa"], "Công thức dùng": L["method"],
            "Lún Si (cm)": L["Si_cm"],
        } for i, L in enumerate(rr["layers"])]).set_index("STT")
        # cỡ chữ 12pt + hiện toàn bộ phân tố (không cuộn)
        _report_table(st, ddf)
        if rr.get("warnings"):
            st.warning(" · ".join(rr["warnings"][:5]))

        # ── Lún theo thời gian (cố kết Terzaghi, Cv từ BCL) ──────────────
        from cdm_layer_avg_settlement import time_history
        st.divider()
        st.markdown("#### Lún cố kết theo thời gian")
        YEARS = [0.5, 1, 2, 5, 10, 15, 20, 30, 40, 50, 70, 100]
        th = time_history(rr, YEARS, double_drainage=drain2, m_coef=m_coef)
        st.markdown("**Công thức (cố kết Terzaghi 1D):**")
        st.latex(r"T_v = \frac{C_v \cdot t}{H_{tn}^2}; \qquad "
                 r"U = \sqrt{\tfrac{4 T_v}{\pi}}\ (U\!<\!0{,}6),\ \ "
                 r"U = 1-\tfrac{8}{\pi^2}e^{-\pi^2 T_v/4}\ (U\!\ge\!0{,}6)")
        st.latex(r"S(t) = S_{\text{tức thời}} + U(T_v)\cdot S_{\text{cố kết}}; \qquad "
                 r"C_{v,tb} = \frac{(H\cdot100)^2}{\left(\sum h_i\cdot100/\sqrt{C_{v,i}}\right)^2}")
        st.caption(
            f"{bh_sel}: S∞ = {th['S_inf_cm']} cm (tức thời {th['S_immediate_cm']} + cố kết "
            f"{th['S_consol_cm']}) · bề dày sét cố kết {th['H_clay_m']} m · H thoát nước "
            f"{th['H_drain_m']} m · C_v,tb = {th['Ctbv_cm2s']:.2e} cm²/s (Cv từ BCL)")
        tdf = pd.DataFrame({
            "Thời gian (năm)": th["years"],
            "T_v": th["Tv"],
            "Độ cố kết U (%)": th["U_pct"],
            "Lún đạt S(t) (cm)": th["St_cm"],
            "Lún còn lại (cm)": th["residual_cm"],
        }).set_index("Thời gian (năm)")
        _report_table(st, tdf)
        try:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=th["years"], y=th["St_cm"], mode="lines+markers+text",
                          text=[f"{v:.2f}" for v in th["St_cm"]], textposition="top center",
                          textfont=dict(size=16),
                          name="Lún đạt S(t)", line=dict(color="#1565C0", width=2)))
            fig.add_trace(go.Scatter(x=th["years"], y=th["residual_cm"], mode="lines+markers+text",
                          text=[f"{v:.2f}" for v in th["residual_cm"]], textposition="bottom center",
                          textfont=dict(size=16),
                          name="Lún còn lại", line=dict(color="#C62828", width=2, dash="dot")))
            fig.add_hline(y=th["S_inf_cm"], line=dict(color="#777", dash="dash"),
                          annotation_text=f"S∞ = {th['S_inf_cm']:.0f} cm")
            fig.update_layout(title=f"Lún cố kết theo thời gian — {bh_sel}",
                              xaxis_title="Thời gian (năm)", yaxis_title="Độ lún (cm)",
                              height=420, font=dict(size=16), legend=dict(font=dict(size=16)), margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass

        # ── Biểu đồ lún cố kết đến 100 năm (mịn) ────────────────────────
        st.markdown("#### Đường cong lún cố kết đến 100 năm")
        # mịn: 0,5→15 mỗi 0,5 năm; 16→30 mỗi 1; 35→100 mỗi 5
        years100 = sorted(set([round(0.5 * k, 1) for k in range(1, 31)]
                              + list(range(16, 31)) + list(range(35, 101, 5))))
        th100 = time_history(rr, years100, double_drainage=drain2, m_coef=m_coef)
        try:
            import plotly.graph_objects as go
            f100 = go.Figure()
            # nhãn thưa: chỉ ghi tại các mốc tiêu chuẩn để không chồng chữ
            _marks = {0.5, 5, 10, 15, 20, 30, 50, 70, 100}
            _txt = [f"{v:.2f}" if th100["years"][i] in _marks else ""
                    for i, v in enumerate(th100["St_cm"])]
            f100.add_trace(go.Scatter(x=th100["years"], y=th100["St_cm"], mode="lines+markers+text",
                           text=_txt, textposition="top center", textfont=dict(size=16),
                           name="Lún đạt S(t)", line=dict(color="#1565C0", width=2.5)))
            f100.add_hline(y=th100["S_inf_cm"], line=dict(color="#777", dash="dash"),
                           annotation_text=f"S∞ = {th100['S_inf_cm']:.0f} cm")
            # mốc 15 năm (TCCS 41 mặt đường mềm) + 100 năm (dài hạn)
            for _yr, _col in [(15.0, "#C62828"), (100.0, "#2E7D32")]:
                if _yr in th100["years"]:
                    _i = th100["years"].index(_yr)
                    f100.add_trace(go.Scatter(
                        x=[_yr], y=[th100["St_cm"][_i]], mode="markers+text",
                        text=[f"{_yr:.0f} năm: {th100['St_cm'][_i]:.2f} cm "
                              f"(U={th100['U_pct'][_i]:.0f}%)"],
                        textposition="bottom right", textfont=dict(size=16),
                        marker=dict(color=_col, size=12), name=f"Mốc {_yr:.0f} năm"))
            f100.update_layout(title=f"Lún cố kết đến 100 năm — {bh_sel}",
                               xaxis_title="Thời gian (năm)", yaxis_title="Độ lún S(t) (cm)",
                               height=400, font=dict(size=16), legend=dict(font=dict(size=16)),
                               margin=dict(t=40, b=10), xaxis=dict(range=[0, 100]))
            st.plotly_chart(f100, use_container_width=True)
        except Exception:
            pass

        # ── Biểu đồ ứng suất hiệu quả + tải gây lún + vùng ảnh hưởng ─────
        st.markdown("#### Ứng suất hữu hiệu, tải gây lún và vùng ảnh hưởng lún")
        st.caption("Vùng ảnh hưởng lún kéo dài tới độ sâu mà Δσ < 10%·σ'v0 (đáy vùng ảnh hưởng).")
        try:
            import plotly.graph_objects as go
            zs = [L["z_mid_m"] for L in rr["layers"]]
            sv0 = [L["sigma_v0_kPa"] for L in rr["layers"]]
            dsig = [L["dsigma_kPa"] for L in rr["layers"]]
            sv0_10 = [0.1 * v for v in sv0]
            # nhãn giá trị thưa (mỗi ~6m) tránh chồng chữ
            def _lbl(vals):
                return [f"{v:.2f}" if (i % 3 == 0) else "" for i, v in enumerate(vals)]
            fs = go.Figure()
            fs.add_trace(go.Scatter(x=sv0, y=zs, mode="lines+markers+text", name="σ'v0 (hữu hiệu)",
                         text=_lbl(sv0), textposition="middle right", textfont=dict(size=16),
                         line=dict(color="#1565C0", width=2.5)))
            fs.add_trace(go.Scatter(x=dsig, y=zs, mode="lines+markers+text", name="Δσ (tải gây lún)",
                         text=_lbl(dsig), textposition="middle left", textfont=dict(size=16),
                         line=dict(color="#C62828", width=2.5)))
            fs.add_trace(go.Scatter(x=sv0_10, y=zs, mode="lines", name="10%·σ'v0 (ngưỡng)",
                         line=dict(color="#2E7D32", width=1.6, dash="dash")))
            # Đường phân cách các lớp đất + nhãn ký hiệu lớp
            xmax = max(max(sv0), max(dsig))
            _segs = []   # (sym, z_top, z_bot)
            _prev, _top = None, (zs[0] - 1.0 if zs else 0.0)
            for L in rr["layers"]:
                sym = L["symbol"]
                if _prev is not None and sym != _prev:
                    zb = L["z_mid_m"] - 1.0
                    fs.add_hline(y=zb, line=dict(color="#9e9e9e", width=1, dash="dot"))
                    _segs.append((_prev, _top, zb)); _top = zb
                _prev = sym
            if _prev is not None and zs:
                _segs.append((_prev, _top, zs[-1] + 1.0))
            for sym, zt, zb in _segs:
                fs.add_annotation(x=xmax, y=(zt + zb) / 2.0, text=f"Lớp {sym}",
                                  showarrow=False, xanchor="right", font=dict(size=14, color="#555"),
                                  bgcolor="rgba(255,255,255,0.6)")
            fs.add_hline(y=rr["stop_depth_m"], line=dict(color="#F57F17", dash="dot"),
                         annotation_text=f"Đáy vùng ảnh hưởng z = {rr['stop_depth_m']:.0f} m")
            # Minh họa tải trọng gây lún q (tải đắp) tác dụng lên mặt đất
            qv = rr["q_kPa"]
            fs.add_hrect(y0=-4.0, y1=0.0, fillcolor="#D2B48C", opacity=0.35, line_width=0)
            for k in range(7):
                xk = xmax * (k + 1) / 8.0
                fs.add_annotation(x=xk, y=0.0, ax=xk, ay=-3.6, xref="x", yref="y",
                                  axref="x", ayref="y", showarrow=True, arrowhead=2,
                                  arrowsize=1, arrowwidth=2, arrowcolor="#8B4513")
            fs.add_annotation(x=xmax / 2.0, y=-3.7, text=f"Tải gây lún q = {qv:.1f} kN/m²",
                              showarrow=False, font=dict(size=16, color="#5D4037"),
                              bgcolor="rgba(255,255,255,0.7)")
            fs.update_layout(title=f"Ứng suất theo chiều sâu — {bh_sel}",
                             xaxis_title="Ứng suất (kPa)", yaxis_title="Độ sâu (m)",
                             yaxis=dict(range=[rr["stop_depth_m"] + 2, -4.5]), height=560,
                             font=dict(size=16), legend=dict(font=dict(size=16)), margin=dict(t=40, b=10))
            st.plotly_chart(fs, use_container_width=True)
        except Exception:
            pass


def _render_zone_fill(st, compute_zone_fill_settlement) -> None:
    """Chế độ: lún chưa xử lý cho 6 hố khoan đại diện theo bảng cấu hình (chiều dày đắp cho sẵn)."""
    import pandas as pd

    st.markdown("### Lún nền chưa xử lý — 6 vùng (hố khoan đại diện)")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        pa = st.selectbox("Chiều dày đắp", ["PA1 (phần xe chạy)", "PA2 (phần vỉa hè)"],
                          index=0, key="zf_pa")
    with c2:
        gamma_fill = st.number_input("Dung trọng đắp γ (kN/m³)", 14.0, 24.0, 18.0, 0.5, key="zf_g")
    with c3:
        gwt_elev = st.number_input("Cao độ mực nước ngầm (m)", -10.0, 10.0, 0.0, 0.1, key="zf_gw")
    with c4:
        disp = st.selectbox("Phân bố Δσ", ["1D (không đổi)", "Boussinesq dải"], index=0, key="zf_disp")
    B_load = None
    if disp.startswith("Boussinesq"):
        B_load = st.number_input("Bề rộng diện gia tải B (m)", min_value=1.0, value=20.0, step=1.0, key="zf_B")

    which = 2 if pa.startswith("PA2") else 1
    method = st.radio(
        "Chỉ tiêu cơ lý dùng để tính",
        ["Chỉ tiêu BCL (Ban chiến lược)", "Trung bình theo lớp (lab)", "Số liệu từng hố khoan"],
        horizontal=True, key="zf_method",
    )
    drain2 = st.checkbox("Cố kết thoát nước 2 mặt (H = H_sét/2)", value=True, key="zf_drain2")
    assume0 = st.checkbox("Giả định CĐTN = 0,0 m cho hố có CĐTN > 0 (khu vực mới san lấp)",
                          value=False, key="zf_assume0")
    _nc_zf = _nc_radio(st, "zf_nc")
    _m_zf = _m_input(st, "zf_m")
    st.caption("Chiều dày đắp và cao độ tự nhiên lấy theo số liệu **BCL (Ban chiến lược)**. "
               "Tải gây lún q = γ·H_đắp. Lún tính trong vùng ảnh hưởng (§71). "
               "KE-HK8 không nằm trong nhóm này. **Lún cố kết theo thời gian chỉ phát triển ở "
               "lớp sét e₀ > 1 (cố kết Terzaghi); lớp cát và sét chặt e₀ < 1 lún tức thời.**")

    full_results = {}
    if method.startswith("Chỉ tiêu BCL") or method.startswith("Trung bình"):
        from cdm_layer_avg_settlement import settle_avg, time_history
        from cdm_no_treat_settlement import ZONE_FILL_CONFIG
        use_bcl = method.startswith("Chỉ tiêu BCL")
        bcl = None
        if use_bcl:
            from bcl_soil_params import get_bcl_params
            bcl = get_bcl_params()
        rows = []
        for c in ZONE_FILL_CONFIG:
            H = float(c["H_fill_2" if which == 2 else "H_fill_1"])
            cdtn = c["CDTN"]
            # Phương án mới san lấp: hố có CĐTN > 0 → coi CĐTN = 0; phần san lấp (CĐTN cũ)
            # trở thành tải đắp bổ sung lên đất yếu (cao độ thiết kế giữ nguyên).
            if assume0 and cdtn > 0:
                H = H + cdtn      # = cao độ thiết kế gốc − 0,0
                cdtn = 0.0
            r = settle_avg(c["bh"], H_fill_m=H, gamma_fill=gamma_fill,
                           gwt_depth_m=max(0.0, cdtn - gwt_elev), B_load_m=B_load,
                           bcl_params=bcl, nc_soft_clay=_nc_zf)
            full_results[c["bh"]] = r
            _th = time_history(r, [15.0, 30.0, 50.0], double_drainage=drain2, m_coef=_m_zf)
            rows.append({"zone": c["zone"], "bh": c["bh"], "CDTN_m": cdtn,
                         "H_fill_m": round(H, 2), "q_kPa": r["q_kPa"],
                         "d_influence_m": r["stop_depth_m"], "S_total_cm": _th["S_inf_cm"],
                         "S_consol_cm": _th["S_consol_cm"], "S_imm_cm": _th["S_immediate_cm"],
                         "Si_mud_cm": _th["Si_mud_cm"],
                         "U15_pct": _th["U_pct"][0], "S_15yr_cm": _th["St_cm"][0],
                         "residual15_cm": _th["residual_cm"][0],
                         "U30_pct": _th["U_pct"][1], "S_30yr_cm": _th["St_cm"][1],
                         "residual30_cm": _th["residual_cm"][1],
                         "U50_pct": _th["U_pct"][2], "S_50yr_cm": _th["St_cm"][2],
                         "residual50_cm": _th["residual_cm"][2]})
        if use_bcl:
            st.caption("Phương pháp: dùng bộ **chỉ tiêu cơ lý BCL (Ban chiến lược)** theo lớp "
                       "(γ, e₀, Cc, Cs, Cv, E từ N) — single source thống nhất.")
            st.markdown("##### Bảng chỉ tiêu cơ lý BCL dùng cho tính toán")
            _bdf = pd.DataFrame([{
                "Lớp": s, "Loại đất": d["soil_type"], "N (SPT)": int(d["N_spt"]),
                "γ (kN/m³)": d["gamma_kNm3"],
                "e₀": d["e0"], "Cc": d["Cc"] if d["Cc"] is not None else "—",
                "Cs": d["Cs"] if d["Cs"] is not None else "—",
                "Cv (cm²/s)": (round(d["Cv_cm2s"], 6) if d["Cv_cm2s"] is not None else "—"),
                "E (kPa)": (int(d["E_kPa"]) if d["E_kPa"] is not None else "—"),
                "P_c (kPa)": (d["PC_kPa"] if d["PC_kPa"] is not None else "—"),
                "Nguồn P_c": d.get("PC_source", "—"),
            } for s, d in (bcl or {}).items()])
            _report_table(st, _bdf.set_index("Lớp"))
            st.caption("Nguồn: BCL (Ban chiến lược) — TTHC Thủ Thiêm. Cv quy đổi từ ×10⁻⁴ cm²/s; "
                       "E = α·N (α=2000 kPa) cho cát/lớp chặt; P_c lấy từ thí nghiệm (lab) vì BCL thiếu; "
                       "Su(VST) sét = 5 + 0,7·Z.")
        else:
            st.caption("Phương pháp: chỉ tiêu cơ lý **trung bình thí nghiệm phòng** theo lớp.")
    else:
        rows = compute_zone_fill_settlement(which_fill=which, gamma_fill=gamma_fill,
                                            gwt_elev_m=gwt_elev, B_load_m=B_load)
    _render_settlement_results(st, rows, full_results, gamma_fill=gamma_fill,
                              gwt_elev=gwt_elev, B_load=B_load, drain2=drain2,
                              bcl=(bcl if 'bcl' in dir() else None),
                              use_bcl=(use_bcl if 'use_bcl' in dir() else False),
                              chart_title='Lún nền chưa xử lý 6 vùng (hố khoan đại diện)',
                              assume0=assume0, nc_soft_clay=_nc_zf, m_coef=_m_zf)

def _render_6zones(st, compute_no_treat_6zones) -> None:
    """Chế độ xem: lún nền chưa xử lý gom theo 6 vùng CDM (Bờ kè KE)."""
    import pandas as pd

    st.markdown("### Lún nền chưa xử lý theo 6 vùng CDM — Bờ kè")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        design_elev = st.number_input("Cao độ thiết kế CĐTK (m)", -10.0, 20.0, 2.70, 0.05, key="nt6_de")
    with c2:
        gamma_fill = st.number_input("Dung trọng đắp γ (kN/m³)", 14.0, 24.0, 18.0, 0.5, key="nt6_g")
    with c3:
        gwt_elev = st.number_input("Cao độ mực nước ngầm (m)", -10.0, 10.0, 0.0, 0.1, key="nt6_gw")
    with c4:
        disp = st.selectbox("Phân bố Δσ", ["1D (không đổi)", "Boussinesq dải"], index=0, key="nt6_disp")
    B_load = None
    if disp.startswith("Boussinesq"):
        B_load = st.number_input("Bề rộng diện gia tải B (m)", min_value=1.0, value=20.0, step=1.0, key="nt6_B")

    st.caption(
        "Lún tính theo vùng ảnh hưởng (§71): phân tố 2 m, tích phân tới đáy vùng ảnh hưởng "
        "(Δσ/σ'v0 < 10%), mở rộng dưới hố khoan nếu cần. Lún đại diện vùng = lớn nhất trong nhóm hố khoan."
    )

    zones = compute_no_treat_6zones(design_elev_m=design_elev, gamma_fill=gamma_fill,
                                    gwt_elev_m=gwt_elev, B_load_m=B_load)

    # Bảng tổng hợp 6 vùng
    st.markdown("#### Tổng hợp 6 vùng")
    summ = pd.DataFrame([{
        "Vùng": f"Vùng {z['zone_no']}",
        "Tổng dài (m)": z["total_length_m"],
        "Hố khoan": ", ".join(r.bh_name for r in z["boreholes"]),
        "Lún đại diện S∞ (cm)": z["S_max_cm"],
        "Lún TB (cm)": z["S_avg_cm"],
        "HK kiểm soát": z["controlling_bh"],
    } for z in zones])
    _report_table(st, summ)

    try:
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_bar(
            x=[f"Vùng {z['zone_no']}" for z in zones],
            y=[z["S_max_cm"] for z in zones],
            text=[f"{z['S_max_cm']:.2f}" for z in zones], textposition="outside",
            textfont=dict(size=16), marker_color="#C62828", name="Lún đại diện (max)")
        fig.add_bar(
            x=[f"Vùng {z['zone_no']}" for z in zones],
            y=[z["S_avg_cm"] for z in zones],
            text=[f"{z['S_avg_cm']:.2f}" for z in zones], textposition="outside",
            textfont=dict(size=16), marker_color="#F9A825", name="Lún trung bình")
        fig.update_layout(title="Lún nền chưa xử lý theo 6 vùng CDM (cm)",
                          barmode="group", yaxis_title="Lún S∞ (cm)",
                          height=420, font=dict(size=16), legend=dict(font=dict(size=16)), margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass

    # Chi tiết từng vùng
    st.markdown("#### Chi tiết từng vùng")
    for z in zones:
        st.markdown(f"**Vùng {z['zone_no']} — tổng dài {z['total_length_m']} m "
                    f"(lún đại diện {z['S_max_cm']:.2f} cm tại {z['controlling_bh']})**")
        df = pd.DataFrame([{
            "Hố khoan": r.bh_name,
            "CĐTN (m)": round(r.CDTN_m, 2),
            "Chiều cao đắp (m)": round(r.H_fill_m, 2),
            "Tải q (kN/m²)": round(r.q_kPa, 1),
            "Đáy vùng ảnh hưởng (m)": round(r.d_influence_m, 1),
            "Lún S∞ (cm)": round(r.S_total_cm, 1),
            "Lún 15 năm (cm)": round(r.S_15yr_cm, 1),
        } for r in z["boreholes"]])
        _report_table(st, df)

    st.caption("Lún này là của nền CHƯA xử lý — dùng so sánh trực tiếp với cọc CDM "
               "(xem trang thiết kế 6 vùng CDM, mục Lc/S₁/S₂ theo từng vùng).")
