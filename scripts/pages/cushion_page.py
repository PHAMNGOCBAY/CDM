"""
scripts/pages/cushion_page.py — Trang "Kiểm chọc thủng đệm cát-XM" (ALiCC PWRI).

Tách từ app_cdm.py để giảm kích thước file chính.
Gọi từ app_cdm.py:
    from pages.cushion_page import render
    if _page == "cushion":
        render()
"""
from __future__ import annotations
from pathlib import Path
import sys

_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def render() -> None:
    """Render trang cushion. Gọi từ app_cdm.py khi page = 'cushion'."""
    import streamlit as st
    import datetime as _dt
    import traceback as _tb

    from cdm_cushion_params import check_alicc
    from cushion_design_charts import (
        chart_heatmap_ratio,
        chart_ratio_vs_quckse_fixed_Hse,
        chart_ratio_vs_Hse_fixed_quckse,
        chart_compare_options,
        chart_alicc_schematic,
        chart_pareto_cost_ratio,
    )
    from cushion_design_report import build_cushion_report
    from core.cost import cushion_cost_delta_pct

    st.title("Kiểm chọc thủng lớp đệm cát - xi măng (ALiCC PWRI)")
    st.caption(
        "Kiểm tra khả năng truyền tải qua đệm cát-XM theo phương pháp ALiCC "
        "(PWRI Japan). Thông số cố định từ hồ sơ thiết kế E.2: q_uckse=600 kPa, F_s=3, "
        "θ=80°. Mọi tính toán đều dùng dung trọng đắp γ_fill = TB trọng số (áo đường + He)."
    )

    try:
        # ─── A. Thông số đầu vào ──────────────────────────────────────────
        st.markdown("### A. Thông số đầu vào")
        _c1, _c2, _c3 = st.columns(3)
        with _c1:
            _Hse_cur = st.number_input(
                "Bề dày đệm H_se hiện tại (m)",
                min_value=0.10, max_value=2.00, value=0.40, step=0.05,
                key="_cush_Hse",
            )
        with _c2:
            _qu_cur = st.number_input(
                "Cường độ q_uckse hiện tại (kPa)",
                min_value=200, max_value=10000, value=600, step=50,
                key="_cush_qu",
            )
        with _c3:
            _D_cur = st.number_input(
                "Đường kính trụ D (m)",
                min_value=0.4, max_value=2.0, value=0.80, step=0.05,
                key="_cush_D",
            )
        _c4, _c5, _c6 = st.columns(3)
        with _c4:
            _s_cur = st.number_input(
                "Khoảng cách trụ s (m)",
                min_value=0.8, max_value=4.0, value=1.80, step=0.05,
                key="_cush_s",
            )
        with _c5:
            _He_cur = max(0.0, 1.10 - _Hse_cur)
            st.metric("He (m) = 1.10 - H_se", f"{_He_cur:.2f}")
        with _c6:
            _r0 = check_alicc(_Hse_cur, q_uckse=float(_qu_cur),
                              D=_D_cur, s=_s_cur)
            st.metric("γ_fill TB (kN/m³)", f"{_r0['gamma_fill_TB']:.2f}")

        st.divider()

        # ─── B. Kết quả hiện trạng ────────────────────────────────────────
        st.markdown("### B. Kết quả tính toán hiện trạng")
        _bcols = st.columns(4)
        _bcols[0].metric("τ_se (kPa)", f"{_r0['tau_se_kPa']:.1f}")
        _bcols[1].metric("τ_ase (kPa)", f"{_r0['tau_ase_kPa']:.1f}")
        _bcols[2].metric("Ratio = τ_se/τ_ase", f"{_r0['ratio']:.3f}")
        with _bcols[3]:
            if _r0["ok"]:
                st.success("ĐẠT (ratio ≤ 1)")
            else:
                st.error(f"KHÔNG ĐẠT (vượt {(_r0['ratio']-1)*100:.1f}%)")

        with st.expander("Chi tiết trung gian"):
            _rows_det = [
                ("Trường hợp công thức (CT1 hay CT2)", _r0["case"]),
                ("Chiều cao vòm H_0 (m)", f"{_r0['H0_m']:.3f}"),
                ("Thể tích V_soil (m³)", f"{_r0['V_soil_m3']:.4f}"),
                ("Thể tích V_CGCXM (m³)", f"{_r0['V_CGCXM_m3']:.4f}"),
                ("Diện tích A_unit (m²)", f"{_r0['A_unit_m2']:.4f}"),
                ("Áp lực P_soil (kPa)", f"{_r0['P_soil_kPa']:.2f}"),
            ]
            import pandas as _pd
            _df_det = _pd.DataFrame(_rows_det, columns=["Đại lượng", "Giá trị"])
            st.dataframe(_df_det, hide_index=True, use_container_width=True)

        with st.expander("Sơ đồ cơ chế truyền tải (vòm đất + chọc thủng)"):
            _fig_sch = chart_alicc_schematic(
                D=_D_cur, s=_s_cur, Hse=_Hse_cur, He=_He_cur)
            st.pyplot(_fig_sch, use_container_width=True)

        st.divider()

        # ─── C. Ma trận heatmap ───────────────────────────────────────────
        st.markdown("### C. Ma trận tối ưu hoá Hse × q_uckse")
        st.caption(
            "Heatmap thể hiện ratio = τ_se/τ_ase. Vòng tròn xanh đánh dấu cấu hình hiện tại."
        )
        _fig_hm = chart_heatmap_ratio(
            Hse_current=_Hse_cur, qu_current=int(_qu_cur))
        st.pyplot(_fig_hm, use_container_width=True)

        _csens = st.columns(2)
        with _csens[0]:
            st.markdown("**Đường ratio vs q_uckse (Hse cố định)**")
            _fig_q = chart_ratio_vs_quckse_fixed_Hse(Hse_fixed=_Hse_cur)
            st.pyplot(_fig_q, use_container_width=True)
        with _csens[1]:
            st.markdown("**Đường ratio vs Hse (q_uckse cố định)**")
            _fig_h = chart_ratio_vs_Hse_fixed_quckse(qu_fixed=int(_qu_cur))
            st.pyplot(_fig_h, use_container_width=True)

        st.divider()

        # ─── D. Pareto ────────────────────────────────────────────────────
        st.markdown("### D. Phân tích Pareto — Chi phí vs Hệ số an toàn")
        st.caption("Đường Pareto = biên không-bị-thống-trị (Pareto front). "
                    "Điểm xanh = đạt, đỏ = không đạt.")
        _fig_p = chart_pareto_cost_ratio()
        st.pyplot(_fig_p, use_container_width=True)

        st.divider()

        # ─── E. So sánh 3 phương án ───────────────────────────────────────
        st.markdown("### E. So sánh 3 phương án đề xuất")
        _opt_defaults = [
            {"label": "A — Tăng cường độ", "Hse": 0.40, "q_uckse": 800,
             "note": "Giữ Hse=0.40m, tăng q_uckse 600→800 kPa"},
            {"label": "B — Tăng chiều dày", "Hse": 0.55, "q_uckse": 600,
             "note": "Giữ q_uckse=600 kPa, tăng Hse 0.40→0.55m"},
            {"label": "C — Đệm mỏng cường độ cao", "Hse": 0.30, "q_uckse": 1000,
             "note": "Hse=0.30m, q_uckse=1000 kPa"},
        ]
        _opts_st = []
        _cE = st.columns(3)
        for _i, _o in enumerate(_opt_defaults):
            with _cE[_i]:
                st.markdown(f"**{_o['label']}**")
                _h = st.number_input(
                    "Hse (m)", value=float(_o["Hse"]), min_value=0.10,
                    max_value=2.0, step=0.05, key=f"_opt_h_{_i}")
                _q = st.number_input(
                    "q_uckse (kPa)", value=int(_o["q_uckse"]), min_value=200,
                    max_value=10000, step=50, key=f"_opt_q_{_i}")
                _r = check_alicc(_h, q_uckse=float(_q), D=_D_cur, s=_s_cur)
                _opts_st.append({
                    "label": _o["label"], "note": _o["note"],
                    "Hse": _h, "q_uckse": _q,
                    "ratio": _r["ratio"], "ok": _r["ok"],
                })
                st.metric("Ratio", f"{_r['ratio']:.3f}")
                if _r["ok"]:
                    st.success("Đạt")
                else:
                    st.error("Không đạt")

        # Cost from JSON
        for _o in _opts_st:
            _o["cost_delta_pct"] = cushion_cost_delta_pct(
                _o["Hse"], float(_o["q_uckse"]),
                Hse_base=_Hse_cur, q_uckse_base=float(_qu_cur),
            )

        _chart_opts = [{"label": _o["label"].split("—")[1].strip()
                        if "—" in _o["label"] else _o["label"],
                        "Hse": _o["Hse"], "q_uckse": _o["q_uckse"],
                        "ratio": _o["ratio"],
                        "cost_delta_pct": _o["cost_delta_pct"]}
                       for _o in _opts_st]
        _fig_cmp = chart_compare_options(_chart_opts)
        st.pyplot(_fig_cmp, use_container_width=True)

        st.divider()

        # ─── F. Xuất Word ─────────────────────────────────────────────────
        st.markdown("### F. Xuất báo cáo Word")
        st.caption(
            "Báo cáo đầy đủ: cơ sở lý thuyết, sơ đồ cơ chế, công thức kiểm toán, "
            "tính toán hiện trạng, ma trận heatmap, sensitivity, Pareto, "
            "so sánh phương án và kết luận."
        )
        _wcols = st.columns([2, 1, 1])
        with _wcols[0]:
            _co_name = st.text_input(
                "Tên công ty (header)",
                value=st.session_state.get("export_co_name", ""),
                key="_cush_co",
            )
            _co_staff = st.text_input(
                "Người thực hiện (footer)",
                value=st.session_state.get("export_co_staff", ""),
                key="_cush_staff",
            )
        with _wcols[1]:
            st.markdown(" ")
            if st.button("Tạo báo cáo Word", type="primary",
                         use_container_width=True, key="_cush_gen"):
                with st.spinner("Đang dựng báo cáo..."):
                    _logo = st.session_state.get("export_logo_bytes")
                    _opts_for_word = [
                        {"label": _o["label"], "Hse": _o["Hse"],
                         "q_uckse": _o["q_uckse"], "note": _o["note"]}
                        for _o in _opts_st
                    ]
                    _docx_bytes = build_cushion_report(
                        co_name=_co_name, co_staff=_co_staff,
                        logo_bytes=_logo,
                        Hse_current=_Hse_cur, qu_current=float(_qu_cur),
                        D=_D_cur, s=_s_cur,
                        options=_opts_for_word,
                    )
                    st.session_state["_cush_docx"] = _docx_bytes
                    st.success(f"Đã tạo báo cáo ({len(_docx_bytes)/1024:.0f} KB)")
        with _wcols[2]:
            st.markdown(" ")
            _d = st.session_state.get("_cush_docx")
            if _d:
                _fn = f"BaoCao_DemXM_ALiCC_{_dt.date.today().strftime('%Y%m%d')}.docx"
                st.download_button(
                    "Tải file .docx", data=_d, file_name=_fn,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True, key="_cush_dl",
                )

    except Exception as _exc:
        st.error(f"Lỗi module kiểm đệm: {_exc}")
        st.code(_tb.format_exc())
