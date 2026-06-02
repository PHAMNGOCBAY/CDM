"""
scripts/pages/soil_stats_page.py — Trang "Thống kê chỉ tiêu cơ lý đất".

Bảng thống kê chỉ tiêu cơ lý các lớp đất (gồm nén cố kết, dung trọng, lực dính...)
cho TẤT CẢ hố khoan, TẤT CẢ lớp đất — gom theo vùng + ký hiệu lớp địa tầng.
Auto-compute (§17 trải phẳng).
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def render() -> None:
    import pandas as pd
    import streamlit as st

    from cdm_no_treat_settlement import LEVEE_KEY, levee_boreholes
    from soil_param_stats import FIELDS, ZONES, save_stats, stats_by_layer

    st.title("Thống kê chỉ tiêu cơ lý các lớp đất")
    st.caption(
        "Giá trị trung bình các chỉ tiêu cơ lý theo từng lớp đất (gồm nén cố kết: e₀, Cc, "
        "Cs, P_c, Cv, a₁₋₂; dung trọng γ; lực dính c; góc ma sát φ; giới hạn Atterberg...) "
        "tổng hợp từ thí nghiệm phòng. Mẫu ánh xạ vào lớp theo độ sâu; lớp xi măng đất (KE-HK8) "
        "tính như lớp bùn 1."
    )

    c1, c2 = st.columns([1, 3])
    with c1:
        zopts = {LEVEE_KEY: "_LEVEE_", "Tất cả vùng": None}
        zopts.update({z: pfx for z, pfx in ZONES})
        zsel = st.selectbox("Vùng", list(zopts.keys()), index=0, key="ss_zone")
    if zopts[zsel] == "_LEVEE_":
        bhs = levee_boreholes()
        rows = stats_by_layer(bh_names=bhs)
        st.caption("Chỉ các hố khoan trên tuyến cừ bờ kè (on_sw_alignment=1), "
                   "KHÔNG đưa KE-HK8 vào tính toán: " + ", ".join(bhs))
    else:
        rows = stats_by_layer(zone_prefix=zopts[zsel])
    if not rows:
        st.warning("Không có dữ liệu.")
        return

    # ── Bảng nén cố kết (trọng tâm) ──────────────────────────────────────
    st.markdown("### Chỉ tiêu nén cố kết theo lớp")
    consol = ["e0", "Cc", "Cs", "PC_kPa", "Cv_cm2s", "a12_cm2kgf", "qu_kPa"]
    label = {f: lb for f, lb, _ in FIELDS}
    dfc = pd.DataFrame([{
        "Vùng": r["zone"], "Lớp": r["symbol"], "n HK": r["n_bh"], "n mẫu": r["n_samples"],
        **{label[f]: (r[f] if r[f] is not None else "—") for f in consol},
    } for r in rows])
    st.table(dfc)

    # ── Bảng vật lý + sức kháng cắt ──────────────────────────────────────
    st.markdown("### Chỉ tiêu vật lý và sức kháng cắt theo lớp")
    phys = ["w_pct", "gamma_kNm3", "gamma_dry_kNm3", "Sr_pct", "wL_pct", "wP_pct", "Ip",
            "c_kPa", "phi_deg", "Cu_UU_kPa"]
    dfp = pd.DataFrame([{
        "Vùng": r["zone"], "Lớp": r["symbol"], "n mẫu": r["n_samples"],
        **{label[f]: (r[f] if r[f] is not None else "—") for f in phys},
    } for r in rows])
    st.table(dfp)

    # ── Biểu đồ so sánh e0 / Cc theo lớp ─────────────────────────────────
    try:
        import plotly.graph_objects as go
        labels = [f"{r['zone']}-{r['symbol']}" for r in rows]
        cc = [r["Cc"] for r in rows]
        if any(v is not None for v in cc):
            fig = go.Figure()
            fig.add_bar(x=labels, y=[v or 0 for v in cc],
                        text=[f"{v:.2f}" if v else "" for v in cc], textposition="outside",
                        marker_color="#1565C0", name="Cc")
            fig.update_layout(title="Chỉ số nén Cc theo lớp (vùng-lớp)",
                              yaxis_title="Cc", height=360, margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass

    st.caption("Ghi chú: ô '—' nghĩa là lớp không có mẫu thí nghiệm cho chỉ tiêu đó "
               "(thường gặp ở lớp cát: không thí nghiệm nén cố kết / Atterberg).")

    if st.button("Lưu bảng thống kê", key="ss_save", type="primary"):
        try:
            save_stats(stats_by_layer())  # luôn lưu đủ tất cả vùng
            st.success("Đã lưu bảng thống kê chỉ tiêu cơ lý theo lớp.")
        except Exception as e:  # noqa: BLE001
            st.error(f"Lỗi lưu: {e}")
