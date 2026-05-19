"""
Giao diện tính toán cọc chịu tải trọng ngang
Chạy:  streamlit run scripts/app_coc_tai_ngang.py
"""
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import streamlit as st

sys.stdout.reconfigure(encoding="utf-8")

# ── Cấu hình trang ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cọc Tải Ngang",
    page_icon="🏗️",
    layout="wide",
)

st.title("Phân Tích Cọc Chịu Tải Trọng Ngang")
st.caption("Phương pháp: FEM 1D — Đường cong p-y API (1987) | openpile 1.0.2")

# ── SIDEBAR: Nhập số liệu ─────────────────────────────────────────────────────
with st.sidebar:
    st.header("Thông Số Cọc")

    pile_type = st.selectbox("Kiểu cọc", ["Thép ống tròn (Tubular)", "BTCT tròn (Concrete)"])
    mat = "Steel" if "Thép" in pile_type else "Concrete"

    col1, col2 = st.columns(2)
    with col1:
        D_mm = st.number_input("Đường kính D (mm)", min_value=200, max_value=2000,
                               value=840, step=10)
    with col2:
        t_mm = st.number_input("Chiều dày t (mm)", min_value=5, max_value=100,
                               value=16, step=1)

    L_m = st.slider("Chiều dài cọc L (m)", min_value=5.0, max_value=60.0,
                    value=20.0, step=0.5)

    MNN_m = st.number_input("Mực nước ngầm (m, âm = dưới mặt đất)",
                             min_value=-30.0, max_value=0.0, value=-1.0, step=0.5)

    st.divider()
    st.header("Tải Trọng Đầu Cọc")

    col3, col4 = st.columns(2)
    with col3:
        H_kN = st.number_input("Lực ngang H (kN)", min_value=0.0, max_value=5000.0,
                                value=100.0, step=10.0)
    with col4:
        M_kNm = st.number_input("Mô men M (kN·m)", min_value=-5000.0, max_value=5000.0,
                                 value=0.0, step=10.0)

    st.divider()
    st.header("Địa Tầng")
    st.caption("Nhập các lớp đất từ trên xuống (API sand — đất rời hoặc tương đương)")

    n_layers = st.number_input("Số lớp đất", min_value=1, max_value=6,
                               value=3, step=1)

    layers_input = []
    LAYER_COLORS = ["#fff3cd", "#d1e7dd", "#cfe2ff", "#f8d7da", "#e2d9f3", "#fde2e4"]

    for i in range(int(n_layers)):
        st.markdown(f"**Lớp {i+1}**")
        c1, c2 = st.columns(2)
        with c1:
            z_top = st.number_input(f"z đỉnh lớp {i+1} (m)", value=float(-i*5),
                                    key=f"ztop_{i}", step=0.5)
            gamma = st.number_input(f"γ (kN/m³)", min_value=10.0, max_value=25.0,
                                    value=18.0, key=f"gamma_{i}", step=0.5)
        with c2:
            z_bot = st.number_input(f"z đáy lớp {i+1} (m)", value=float(-(i+1)*5),
                                    key=f"zbot_{i}", step=0.5)
            phi   = st.number_input(f"φ (°)", min_value=15.0, max_value=45.0,
                                    value=28.0 + i * 3, key=f"phi_{i}", step=1.0)
        name = st.text_input(f"Tên lớp {i+1}", value=f"Lớp {i+1}",
                             key=f"name_{i}")
        layers_input.append((name, z_top, z_bot, gamma, phi))

    run = st.button("Tính toán", type="primary", use_container_width=True)

# ── NỘI DUNG CHÍNH ────────────────────────────────────────────────────────────
if not run:
    st.info("Nhập số liệu bên trái rồi nhấn **Tính toán**.")
    st.stop()

# Validate đầu vào
errors = []
if t_mm * 2 >= D_mm:
    errors.append("Chiều dày t phải nhỏ hơn D/2.")
for i, (name, z_top, z_bot, gamma, phi) in enumerate(layers_input):
    if z_bot >= z_top:
        errors.append(f"Lớp {i+1}: z đáy phải nhỏ hơn z đỉnh (âm hơn).")

if errors:
    for e in errors:
        st.error(e)
    st.stop()

# Clip các lớp không vượt đáy cọc, bỏ lớp nằm hoàn toàn dưới đáy cọc
layers_clipped = []
for name, z_top, z_bot, gamma, phi in layers_input:
    if z_top <= -L_m:
        break                           # lớp này nằm hoàn toàn dưới đáy cọc
    z_bot_clip = max(z_bot, -L_m)      # cắt đáy lớp tại đáy cọc
    layers_clipped.append((name, z_top, z_bot_clip, gamma, phi))

# Đảm bảo lớp cuối luôn chạm đáy cọc — kéo dài nếu còn thiếu
if layers_clipped:
    last = layers_clipped[-1]
    if last[2] > -L_m:                 # đáy lớp cuối chưa tới đáy cọc
        layers_clipped[-1] = (last[0], last[1], -L_m, last[3], last[4])
else:
    st.error("Không có lớp đất nào phủ phần cọc trong đất. Kiểm tra lại z đỉnh/đáy các lớp.")
    st.stop()

# ── Chạy openpile ─────────────────────────────────────────────────────────────
with st.spinner("Đang tính toán..."):
    try:
        from openpile.construct import (
            Pile, SoilProfile, Layer, Model, BoundaryFixation,
        )
        from openpile.soilmodels import API_sand
        from openpile.winkler import winkler

        pile = Pile.create_tubular(
            name=f"D{D_mm}",
            top_elevation=0.0,
            bottom_elevation=-L_m,
            diameter=D_mm / 1000,
            wt=t_mm / 1000,
            material=mat,
        )

        sp = SoilProfile(
            name="Dia tang",
            top_elevation=0.0,
            water_line=MNN_m,
            layers=[
                Layer(
                    name=name,
                    top=z_top, bottom=z_bot,
                    weight=gamma,
                    lateral_model=API_sand(phi=phi, kind="static"),
                )
                for name, z_top, z_bot, gamma, phi in layers_clipped
            ],
        )

        bc     = [BoundaryFixation(elevation=-L_m, x=True, y=True, z=True)]
        model  = Model(name="calc", pile=pile, soil=sp, boundary_conditions=bc)
        if H_kN != 0:
            model.set_pointload(elevation=0.0, Py=H_kN)
        if M_kNm != 0:
            model.set_pointload(elevation=0.0, Mx=M_kNm)

        result = winkler(model)
        converged = True

    except Exception as exc:
        st.error(f"Lỗi tính toán: {exc}")
        st.stop()

# ── Xử lý kết quả ─────────────────────────────────────────────────────────────
elev   = result.deflection["Elevation [m]"].values
y_mm   = result.deflection["Deflection [m]"].values * 1000

fdf    = result.forces.drop_duplicates(subset="Elevation [m]", keep="first")
elev_f = fdf["Elevation [m]"].values
V_kN_arr = fdf["V [kN]"].values
M_arr    = fdf["M [kNm]"].values

y_head   = y_mm[0]
y_max    = np.nanmax(np.abs(y_mm))
V_max    = np.nanmax(np.abs(V_kN_arr))
M_max    = np.nanmax(np.abs(M_arr))
z_Vmax   = elev_f[np.nanargmax(np.abs(V_kN_arr))]
z_Mmax   = elev_f[np.nanargmax(np.abs(M_arr))]

# ── KPI cards ─────────────────────────────────────────────────────────────────
st.success("Tính toán hội tụ.")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Chuyển vị đỉnh cọc", f"{y_head:.3f} mm")
k2.metric("Chuyển vị lớn nhất", f"{y_max:.3f} mm")
k3.metric(f"M_max  (z = {z_Mmax:.1f} m)", f"{M_max:.1f} kN·m")
k4.metric(f"V_max  (z = {z_Vmax:.1f} m)", f"{V_max:.1f} kN")

st.divider()

# ── Biểu đồ nội lực ───────────────────────────────────────────────────────────
col_left, col_right = st.columns([3, 1])

with col_left:
    fig, axes = plt.subplots(1, 3, figsize=(12, 8), sharey=True)
    fig.suptitle(
        f"D={D_mm}mm  t={t_mm}mm  L={L_m}m  |  H={H_kN} kN  M={M_kNm} kN·m",
        fontsize=11, fontweight="bold",
    )

    def _draw_layers(ax):
        # vẽ nền địa tầng theo layers_input (có thể sâu hơn cọc)
        for i, (name, z_top, z_bot, *_) in enumerate(layers_input):
            ax.axhspan(z_top, z_bot, alpha=0.15,
                       color=LAYER_COLORS[i % len(LAYER_COLORS)])
        ax.axhline(MNN_m, color="steelblue", lw=1.2, ls="--", alpha=0.7,
                   label="MNN")
        # ylim: dương lên trên, âm xuống dưới — KHÔNG invert
        ax.set_ylim(-L_m * 1.03, 0.6)
        ax.axvline(0, color="k", lw=0.7)

    # Chuyển vị
    ax = axes[0]
    _draw_layers(ax)
    ax.plot(y_mm, elev, "b-o", ms=2.5, lw=1.5)
    ax.fill_betweenx(elev, 0, y_mm, where=y_mm > 0, alpha=0.12, color="blue")
    ax.fill_betweenx(elev, 0, y_mm, where=y_mm < 0, alpha=0.12, color="red")
    ax.set_xlabel("Chuyển vị y (mm)")
    ax.set_ylabel("Cao độ (m)")
    ax.set_title("Chuyển vị ngang")
    ax.annotate(f"{y_head:.2f} mm", xy=(y_head, 0),
                xytext=(y_head * 0.35, -2.0),
                arrowprops=dict(arrowstyle="->", color="navy"),
                color="navy", fontsize=8)

    # Lực cắt
    ax = axes[1]
    _draw_layers(ax)
    ax.plot(V_kN_arr, elev_f, "g-o", ms=2.5, lw=1.5)
    ax.fill_betweenx(elev_f, 0, V_kN_arr, alpha=0.12, color="green")
    ax.set_xlabel("Lực cắt V (kN)")
    ax.set_title("Lực cắt")
    idx_v = np.nanargmax(np.abs(V_kN_arr))
    ax.annotate(f"{V_max:.1f} kN\nz={z_Vmax:.1f}m",
                xy=(V_kN_arr[idx_v], elev_f[idx_v]),
                xytext=(V_kN_arr[idx_v] * 0.3, elev_f[idx_v] + 1.5),
                arrowprops=dict(arrowstyle="->", color="darkgreen"),
                color="darkgreen", fontsize=8)

    # Mô men
    ax = axes[2]
    _draw_layers(ax)
    ax.plot(M_arr, elev_f, "r-o", ms=2.5, lw=1.5)
    ax.fill_betweenx(elev_f, 0, M_arr, alpha=0.12, color="red")
    ax.set_xlabel("Mô men M (kN·m)")
    ax.set_title("Mô men uốn")
    idx_m = np.nanargmax(np.abs(M_arr))
    ax.annotate(f"{M_max:.1f} kN·m\nz={z_Mmax:.1f}m",
                xy=(M_arr[idx_m], elev_f[idx_m]),
                xytext=(M_arr[idx_m] * 0.3, elev_f[idx_m] + 1.5),
                arrowprops=dict(arrowstyle="->", color="darkred"),
                color="darkred", fontsize=8)

    # Chú thích địa tầng
    for i, (name, z_top, z_bot, gamma, phi) in enumerate(layers_clipped):
        z_mid = (z_top + z_bot) / 2
        axes[0].text(
            min(y_mm) * 0.02 if min(y_mm) < 0 else -max(abs(y_mm)) * 0.05,
            z_mid, f"{name}\nφ={phi}°  γ={gamma}",
            fontsize=6.5, color="#555", va="center", ha="left",
        )

    # Legend MNN
    legend_patch = mpatches.Patch(color="steelblue", alpha=0.5, label="Mực nước ngầm")
    axes[2].legend(handles=[legend_patch], fontsize=8, loc="lower right")

    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

# ── Bảng mặt cắt ─────────────────────────────────────────────────────────────
with col_right:
    st.subheader("Mặt cắt địa tầng")
    fig_s, ax_s = plt.subplots(figsize=(2.5, 8))
    ax_s.set_xlim(0, 1)

    # Mở rộng ylim để hiển thị đủ cả lớp đất sâu hơn cọc
    z_min_all = min(z_bot for _, _, z_bot, _, _ in layers_input)
    y_bot = min(-L_m * 1.05, z_min_all * 1.05)
    ax_s.set_ylim(y_bot, 0.6)   # âm xuống dưới, dương lên trên — KHÔNG invert

    ax_s.set_xticks([])
    ax_s.set_ylabel("Cao độ (m)")

    # Vẽ lớp đất (full layers_input — có thể sâu hơn cọc)
    for i, (name, z_top, z_bot, gamma, phi) in enumerate(layers_input):
        ax_s.barh(
            y=(z_top + z_bot) / 2,
            width=1, height=abs(z_top - z_bot),
            color=LAYER_COLORS[i % len(LAYER_COLORS)],
            edgecolor="#888", linewidth=0.5, align="center",
        )
        ax_s.text(0.5, (z_top + z_bot) / 2,
                  f"{name}\nφ={phi}°  γ={gamma}",
                  ha="center", va="center", fontsize=6.5)

    ax_s.axhline(MNN_m, color="steelblue", lw=1.5, ls="--")
    ax_s.text(0.05, MNN_m + 0.2, f"MNN={MNN_m}m", fontsize=7, color="steelblue")

    # Cọc: từ 0 (đỉnh) xuống -L_m (mũi) — Rectangle(x_left, y_bottom, width, height)
    ax_s.add_patch(mpatches.Rectangle(
        (0.42, -L_m), 0.16, L_m,
        color="#888888", alpha=0.65, zorder=5,
    ))
    # Đánh dấu mũi cọc
    ax_s.axhline(-L_m, color="#555", lw=1, ls=":", alpha=0.8)
    ax_s.text(0.05, -L_m - abs(y_bot) * 0.03,
              f"Mũi cọc  {-L_m:.1f}m", fontsize=6.5, color="#555")

    plt.tight_layout()
    st.pyplot(fig_s)
    plt.close()

# ── Bảng số liệu chi tiết ─────────────────────────────────────────────────────
st.divider()
st.subheader("Kết Quả Chi Tiết")

tab1, tab2 = st.tabs(["Chuyển vị & Nội lực theo chiều sâu", "Thông số đầu vào"])

with tab1:
    df_out = pd.DataFrame({
        "Cao độ (m)": elev,
        "Chuyển vị y (mm)": np.round(y_mm, 4),
    })
    # merge lực cắt và mô men (có thể khác số dòng do duplicate elimination)
    df_force = pd.DataFrame({
        "Cao độ (m)": elev_f,
        "Lực cắt V (kN)": np.round(V_kN_arr, 2),
        "Mô men M (kN·m)": np.round(M_arr, 2),
    })
    df_full = pd.merge(df_out, df_force, on="Cao độ (m)", how="outer").sort_values(
        "Cao độ (m)", ascending=False
    ).reset_index(drop=True)
    st.dataframe(df_full, use_container_width=True, height=350)

    csv = df_full.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "Tải CSV",
        data=csv,
        file_name=f"ket_qua_coc_D{D_mm}L{L_m}H{H_kN}.csv",
        mime="text/csv",
    )

with tab2:
    st.markdown(f"""
| Thông số | Giá trị |
|----------|---------|
| Loại cọc | {pile_type} |
| Đường kính D | {D_mm} mm |
| Chiều dày thành t | {t_mm} mm |
| Chiều dài cọc L | {L_m} m |
| Mực nước ngầm | {MNN_m} m |
| Lực ngang H | {H_kN} kN |
| Mô men đỉnh M | {M_kNm} kN·m |
    """)
    st.markdown("**Địa tầng:**")
    df_layers = pd.DataFrame(layers_clipped,
                             columns=["Tên lớp", "z đỉnh (m)", "z đáy (m)",
                                      "γ (kN/m³)", "φ (°)"])
    st.dataframe(df_layers, use_container_width=True, hide_index=True)
