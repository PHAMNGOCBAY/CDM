# -*- coding: utf-8 -*-
"""
app_cdm.py  –  Ứng dụng thiết kế cọc đất xi măng (CDM)
Streamlit, cấu trúc tương tự app_coc_tai_ngang.py

Chạy:  streamlit run app_cdm.py --server.port 8503
"""
import io
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    _HAS_PLOTLY = True
except ImportError:
    _HAS_PLOTLY = False

try:
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except ImportError:
    _HAS_MPL = False

try:
    import pydeck as pdk
    _HAS_PYDECK = True
except ImportError:
    _HAS_PYDECK = False

import sqlite3

# ── Đường dẫn ────────────────────────────────────────────────────────────────
_ROOT    = Path(__file__).parent.parent
_DB      = _ROOT / "data" / "TTHC.sqlite"
_CDM_SC  = _ROOT / "CDM" / "scripts"
_THEORY  = _ROOT / "35-ly-thuyet-cdm.md"


# ── Pile schematic (GEO5 style) — dùng cho tab Cọc ván SW mục C ──────────────
def draw_pile_schematic(
    L_m, water_lvl, top_elev, H_kN, M_kNm, layers, bc_type,
    pile_H_mm=840,
    soil_lvl_front=None,
    soil_lvl_back=None,
    back_layers=None,
    gamma_fill=18.0,
    phi_fill=25.0,
    c_fill=5.0,
    water_lvl_back=None,
):
    if not _HAS_MPL:
        return None
    bot  = top_elev - L_m
    ypad = max(L_m * 0.06, 0.8)
    y_top = top_elev + ypad * 2.2
    y_bot = bot - ypad * 1.2

    fig, ax = plt.subplots(figsize=(4.5, 5.5), dpi=90)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    ax.set_xlim(-5, 5)
    ax.set_ylim(y_bot, y_top)
    ax.set_ylabel("Elevation [m]", fontsize=9)
    ax.set_xticks([])
    ax.tick_params(axis="y", labelsize=8)
    for sp in ["top", "right", "bottom"]:
        ax.spines[sp].set_visible(False)

    _fill_label = f"Fill\nγ={gamma_fill:.0f} kN/m³\nφ={phi_fill:.0f}°  c={c_fill:.0f} kPa"
    if soil_lvl_front is not None and top_elev > soil_lvl_front:
        ax.fill_between(
            [-4.8, 0], [soil_lvl_front, soil_lvl_front], [top_elev, top_elev],
            color="#c8a96e", alpha=0.35, hatch="\\\\", zorder=2,
            linewidth=0.5, edgecolor="#a07040",
        )
        ax.text(-2.4, (soil_lvl_front + top_elev) / 2, _fill_label,
                fontsize=7, color="#7a5020", ha="center", va="center",
                style="italic", linespacing=1.4)

    if soil_lvl_front is not None:
        ax.plot([-4.8, 0], [soil_lvl_front, soil_lvl_front],
                color="saddlebrown", lw=1.8, solid_capstyle="round", zorder=6)
        ax.text(-4.8, soil_lvl_front + ypad * 0.15, "Ground F",
                fontsize=8, color="saddlebrown", va="bottom", fontweight="bold")
    if soil_lvl_back is not None:
        ax.plot([0, 4.8], [soil_lvl_back, soil_lvl_back],
                color="saddlebrown", lw=1.8, solid_capstyle="round", zorder=6)
        ax.text(0.2, soil_lvl_back + ypad * 0.15, "Ground B",
                fontsize=8, color="saddlebrown", va="bottom", fontweight="bold")

    ax.plot([0, 0], [bot, top_elev], color="red", lw=3.5, solid_capstyle="butt", zorder=10)
    ax.plot([-4.8, 5], [top_elev, top_elev], color="#888", lw=1.0, ls="--", zorder=5)
    ax.plot([-0.25], [top_elev], "v", color="#444", ms=7, zorder=11,
            markerfacecolor="none", markeredgewidth=1.5)
    ax.text(-4.8, top_elev + ypad * 0.22, "SP Top", fontsize=9, color="#333", va="bottom")
    ax.text(0.25, top_elev + ypad * 0.05, f"{top_elev:.2f} m", fontsize=7.5, color="#555", va="bottom")

    for i, (nm, zt, zb, gm, ph, *_) in enumerate(layers):
        if i > 0:
            ax.plot([-4.8, 0], [zt, zt], color="goldenrod", lw=1.0, ls="--", zorder=5)
            ax.plot([-0.25], [zt], "v", color="goldenrod", ms=7, zorder=11,
                    markerfacecolor="none", markeredgewidth=1.5)
            ax.text(-4.8, zt + ypad * 0.12, f"Soil {i}", fontsize=9, color="goldenrod", va="bottom")

    if back_layers:
        for i, (nm, zt, zb, gm, ph, *_) in enumerate(back_layers):
            if i > 0:
                ax.plot([0, 4.8], [zt, zt], color="goldenrod", lw=0.9, ls=":", zorder=4, alpha=0.8)
                ax.text(0.3, zt + ypad * 0.12, f"Back {i}", fontsize=8, color="goldenrod", va="bottom", alpha=0.85)

    ax.text(0.25, bot - ypad * 0.05, f"{bot:.2f} m", fontsize=7.5, color="#555", va="top")

    w_gap = ypad * 0.18
    ax.plot([-4.2, -0.8], [water_lvl, water_lvl], color="steelblue", lw=2.0, zorder=7)
    ax.plot([-3.8, -1.1], [water_lvl - w_gap, water_lvl - w_gap], color="steelblue", lw=1.5, zorder=7)
    ax.text(-4.8, water_lvl + ypad * 0.15, f"Water F  {water_lvl:.2f} m", fontsize=8, color="steelblue")
    _wlb = water_lvl_back if water_lvl_back is not None else water_lvl
    ax.plot([0.8, 4.2], [_wlb, _wlb], color="steelblue", lw=2.0, zorder=7, ls="--")
    ax.plot([1.1, 3.8], [_wlb - w_gap, _wlb - w_gap], color="steelblue", lw=1.5, zorder=7, ls="--")
    ax.text(0.3, _wlb + ypad * 0.15, f"Water B  {_wlb:.2f} m", fontsize=8, color="steelblue")

    if bc_type == "Fixed":
        ax.plot([-0.6, 0.6], [bot, bot], color="#333", lw=1.8, zorder=8)
        for k in range(6):
            x0 = -0.40 + k * 0.16
            ax.plot([x0, x0 - 0.12], [bot, bot - ypad * 0.25], color="#333", lw=0.8, zorder=7)
    elif bc_type == "Cantilever":
        ax.plot([0], [bot], "^", ms=12, color="#333", zorder=8,
                markerfacecolor="none", markeredgewidth=2.0)
        ax.plot([-0.5, 0.5], [bot - ypad * 0.12, bot - ypad * 0.12], "#333", lw=1.0, zorder=7)
    elif bc_type == "Free":
        ax.plot([-0.2, 0.2], [bot, bot], "#333", lw=1.5, ls=":", zorder=7)

    if abs(H_kN) > 1e-3:
        sign = 1 if H_kN > 0 else -1
        ax.annotate("", xy=(0, top_elev), xytext=(-sign * 2.8, top_elev),
                    arrowprops=dict(arrowstyle="->, head_width=0.35, head_length=0.20",
                                   color="red", lw=2.2), zorder=12)
        ax.text(-sign * 1.4, top_elev + ypad * 0.50, f"H = {H_kN:.0f} kN",
                fontsize=9, color="red", ha="center", fontweight="bold")
    if abs(M_kNm) > 1e-3:
        ax.text(0.4, top_elev + ypad * 1.2, f"M = {M_kNm:.0f} kN.m",
                fontsize=8.5, color="darkorange", ha="left", fontweight="bold")

    ax.text(-4.0, y_bot + ypad * 0.4, "Front", fontsize=10, color="#666", style="italic")
    ax.text(1.5,  y_bot + ypad * 0.4, "Back",  fontsize=10, color="#666", style="italic")
    plt.tight_layout()
    return fig


@st.cache_data(show_spinner=False)
def _load_theory() -> str:
    try:
        return _THEORY.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""

_PUNCH_THEORY = _ROOT / "41-cdm-choc-thung-dem-ximang.md"

@st.cache_data(show_spinner=False)
def _load_punch_theory() -> str:
    try:
        return _PUNCH_THEORY.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""

st.set_page_config(
    page_title="CDM Design Tool",
    page_icon="🏗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS app + print PDF ───────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { min-width: 220px; max-width: 280px; }
div[data-testid="stMetricValue"] { font-size: 1.1rem; }
#MainMenu { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
[data-testid="stDecoration"] { display: none; }
footer { visibility: hidden; }

/* ── Nội dung lý thuyết trong expander: font rõ hơn trên màn hình ── */
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p,
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] li,
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] td,
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] th {
    font-size: 15px;
    line-height: 1.75;
}
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] h2 { font-size: 18px; margin-top: 1.2em; }
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] h3 { font-size: 16px; margin-top: 1em; }
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] h4 { font-size: 15px; }

/* ── Print / PDF ── */
@media print {
    /* Ẩn sidebar và toolbar khi in */
    [data-testid="stSidebar"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    footer { display: none !important; }

    /* Mở rộng vùng nội dung ra full trang */
    [data-testid="stAppViewContainer"] > section { padding: 0 !important; }
    .block-container { max-width: 100% !important; padding: 0 1cm !important; }

    /* Font báo cáo kỹ thuật */
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] td,
    [data-testid="stMarkdownContainer"] th {
        font-family: "Times New Roman", Times, serif !important;
        font-size: 12pt !important;
        line-height: 1.6 !important;
        color: #000 !important;
    }
    [data-testid="stMarkdownContainer"] h1 { font-size: 16pt !important; font-weight: bold !important; page-break-after: avoid; }
    [data-testid="stMarkdownContainer"] h2 { font-size: 14pt !important; font-weight: bold !important; page-break-after: avoid; }
    [data-testid="stMarkdownContainer"] h3 { font-size: 13pt !important; font-weight: bold !important; page-break-after: avoid; }
    [data-testid="stMarkdownContainer"] h4 { font-size: 12pt !important; font-weight: bold !important; page-break-after: avoid; }

    /* Không ngắt trang giữa bảng */
    [data-testid="stMarkdownContainer"] table { page-break-inside: avoid; }

    /* Mở expander khi in */
    details { display: block !important; }
    summary { display: none !important; }
}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
_CLAY_SYMBOLS = {        # symbol lớp bùn sét yếu theo zone
    "KE":  ["1", "1b"],
    "BXN": ["2"],
    "NHC": ["2", "1"],   # NHC chưa có layers – fallback
}
_ZONE_NAMES = {"KE": "Kè Công Viên (KE)", "BXN": "Bãi Đỗ Xe Ngầm (BXN)", "NHC": "Nhà Hành Chính (NHC)"}

_LAYER_COLORS: dict[str, str] = {
    # Ký hiệu địa tầng Việt Nam (TCVN)
    "F":    "#9E9E9E",
    "1":    "#81D4FA",
    "1b":   "#4FC3F7",
    "2":    "#1565C0",
    "2a":   "#66BB6A",
    "2b":   "#FDD835",
    "2c":   "#C5E1A5",
    "3":    "#8D6E63",
    "3a":   "#A5D6A7",
    "3b":   "#69B578",
    "3c":   "#43A047",
    "4":    "#5C85D6",
    "5":    "#FFA726",
    "5a":   "#FB8C00",
    "5b":   "#E65100",
    "6":    "#6D4C41",
    "7":    "#795548",
    "8":    "#BCAAA4",
    "TK6a": "#FFD54F",
    "TK6b": "#FFB300",
    "XMD":  "#E91E63",
    # USCS symbols (NHC lab_tests.symbol_tcvn)
    "CH":   "#1A237E",   # High-plasticity clay – xanh đậm
    "CL":   "#1565C0",   # Low-plasticity clay
    "MH":   "#29B6F6",   # High-plasticity silt – xanh nhạt
    "ML":   "#81D4FA",   # Low-plasticity silt
    "OH":   "#4527A0",   # Organic high-plasticity
    "OL":   "#7E57C2",   # Organic low-plasticity
    "SM":   "#8D6E63",   # Silty sand – nâu
    "SC":   "#A1887F",   # Clayey sand
    "SW":   "#D4AC0D",   # Well-graded sand – vàng
    "SP":   "#F9E79F",   # Poorly-graded sand
    "GW":   "#5C85D6",   # Well-graded gravel
    "GP":   "#AED6F1",   # Poorly-graded gravel
    "GM":   "#7FB3D3",   # Silty gravel
    "GC":   "#5DADE2",   # Clayey gravel
    "PT":   "#2E7D32",   # Peat – xanh lá
}
_LAYER_DEFAULT_COLOR = "#EEEEEE"
_ZONE_MARKER: dict[str, str] = {"KE": "circle", "BXN": "square", "NHC": "diamond"}

# ─── Bảng dịch VN / EN ────────────────────────────────────────────────────────
_L: dict[str, tuple[str, str]] = {
    # Sidebar
    "app_sub":      ("Thiết kế cọc đất xi măng",    "Cement Deep Mixing Design"),
    "save_load":    ("Lưu / Mở dự án",              "Save / Load Project"),
    "download":     ("Tải xuống (.cdm)",             "Download (.cdm)"),
    "upload":       ("Mở file dự án (.cdm)",         "Open project file (.cdm)"),
    "load_ok":      ("Đã tải dự án.",               "Project loaded."),
    "lang_lbl":     ("Ngôn ngữ / Language",          "Language / Ngôn ngữ"),
    # Pages
    "p_geology":    ("Địa chất",                    "Geology"),
    "p_sample_check":("Kiểm tra mẫu TN",            "Sample Check"),
    "p_tkcs_cdm":   ("TKCS CDM",                    "CDM Prelim Design"),
    "p_params":     ("Thông số",                    "Parameters"),
    "p_compare":    ("Kết quả CDM",                 "CDM Results"),
    "p_settlement": ("Dự báo độ lún",               "Settlement Prediction"),
    "p_export":     ("Xuất kết quả",                "Export Results"),
    "p_cdm_bvt":    ("TKBVTC CDM",                  "CDM Detail Design"),
    "p_tkcs_sw":    ("TKCS Cọc ván",                "Sheet Pile Prelim Design"),
    "p_ke_sw":      ("Cọc ván SW (Kè)",             "Sheet Pile SW (Ke)"),
    "p_sw_bvt":     ("TKBVTC Cọc SW",              "Sheet Pile Detail Design"),
    # Page 1 – Geology
    "p1_sub":       ("Địa chất – Chọn hố khoan",    "Geology – Borehole Selection"),
    "zone_lbl":     ("Zone",                        "Zone"),
    "bh_lbl":       ("Hố khoan",                   "Borehole"),
    "apply_bh":     ("Áp dụng hố khoan",            "Apply Borehole"),
    "apply_bh_ok":  ("Đã áp dụng {bh}.",            "Applied {bh}."),
    "no_bh_warn":   ("Zone này chưa có dữ liệu hố khoan.", "No borehole data for this zone."),
    "clay_thick":   ("Bề dày lớp bùn sét",          "Soft clay thickness"),
    "clay_elev":    ("Cao độ đáy lớp bùn",          "Clay base elevation"),
    "su_avg":       ("Su trung bình (VST)",          "Average Su (VST)"),
    "strat_title":  ("Địa tầng hố khoan",           "Borehole Stratigraphy"),
    "no_strat":     ("Hố khoan này chưa có dữ liệu địa tầng trong CSDL.",
                     "No stratigraphy data in database."),
    "vst_sel":      ("Chọn hố khoan VST (để trống = toàn bộ)",
                     "Select VST locations (blank = all)"),
    "no_bh_col":    ("Chọn hố khoan để xem cột địa chất.", "Select borehole to view soil column."),
    "cdm_test_exp": ("Kết quả thí nghiệm CDM (R7)", "CDM Test Results (R7)"),
    "cdm_test_note":("Lưu ý: Kết quả R7 (7 ngày). Cần qu_R90 để tính Ec chính xác.",
                     "Note: R7 results (7-day). qu_R90 needed for accurate Ec."),
    "view_mode":    ("Chế độ xem",                  "View Mode"),
    "view_3d":      ("3D địa chất",                 "3D Geology"),
    "view_map":     ("Bản đồ vị trí",               "Location Map"),
    "clay_surf":    ("Mặt đáy lớp bùn",             "Clay Base Surface"),
    "cdm_top_show": ("Đỉnh trụ CDM",                "CDM Pile Top"),
    "elev_lbl":     ("Cao độ (m)",                  "Elevation (m)"),
    "no_zone":      ("Chọn ít nhất một zone.",      "Select at least one zone."),
    "map_style":    ("Nền bản đồ",                  "Map Style"),
    "gps_done":     ("Hiệu chỉnh GPS — đã áp dụng", "GPS Calibration — applied"),
    "gps_needed":   ("Hiệu chỉnh GPS — cần thiết lập lần đầu",
                     "GPS Calibration — setup required"),
    "ref_bh":       ("Hố khoan tham chiếu",         "Reference Borehole"),
    "apply_calib":  ("Áp dụng hiệu chỉnh",          "Apply Calibration"),
    "no_coords":    ("Không có hố khoan nào có tọa độ.", "No boreholes with coordinates."),
    "no_plotly":    ("Cài `plotly` để xem bản đồ địa chất.", "Install `plotly` to view geology map."),
    "no_coords_db": ("Chưa có tọa độ hố khoan trong CSDL (x_coord_m / y_coord_m = NULL).",
                     "No borehole coordinates in database (x_coord_m / y_coord_m = NULL)."),
    # Page 2 – Parameters
    "p2_sub":       ("Thông số CDM",                "CDM Parameters"),
    "cdm_geom":     ("Hình học trụ CDM",            "CDM Pile Geometry"),
    "D_lbl":        ("Đường kính D (m)",             "Diameter D (m)"),
    "Lc_lbl":       ("Chiều dài Lc (m)",             "Length Lc (m)"),
    "CDTK_lbl":     ("Cao độ đỉnh cọc CDM (m)",     "CDM Top Elevation (m)"),
    "cdtk_info":    ("CDTK = đỉnh + đệm + đắp = **{v:+.2f} m**",
                     "CDTK = top + mat + fill = **{v:+.2f} m**"),
    "arr_lbl":      ("Bố trí lưới",                 "Grid Pattern"),
    "arr_tri":      ("Tam giác",                    "Triangular"),
    "arr_sq":       ("Hình vuông",                  "Square"),
    "material":     ("Vật liệu xi măng đất",        "Cement-Soil Material"),
    "cement_lbl":   ("Loại xi măng",                "Cement Type"),
    "dosage_lbl":   ("Hàm lượng XM (kg/m³)",       "Cement Dosage (kg/m³)"),
    "wc_lbl":       ("Tỷ lệ N/XM",                 "Water/Cement Ratio"),
    "qu_lbl":       ("qu thiết kế HT (kPa)",        "qu Design Field (kPa)"),
    "fs_lab":       ("FS quy đổi TN→HT",            "FS Lab→Field Conversion"),
    "geo_params":   ("Thông số địa kỹ thuật",       "Geotechnical Parameters"),
    "top_clay_lbl": ("Cao độ đỉnh lớp bùn (m)",    "Top of Soft Clay Elev. (m)"),
    "h_clay_lbl":   ("Bề dày lớp bùn h₁ (m)",      "Soft Clay Thickness h₁ (m)"),
    "bot_clay_info":("Đáy lớp bùn = {v:+.2f} m",   "Bottom of Soft Clay = {v:+.2f} m"),
    "su_lbl":       ("Su trung bình (kPa)",         "Average Su (kPa)"),
    "gamma_lbl":    ("γ tự nhiên (kN/m³)",          "Unit Weight γ (kN/m³)"),
    "loads_title":  ("Tải trọng gây lún",           "Settlement Loads"),
    "q_traf":       ("Hoạt tải (kN/m²)",            "Traffic Load (kN/m²)"),
    "pavement":     ("*Áo đường:*",                 "*Pavement:*"),
    "fill":         ("*Cát đắp:*",                  "*Fill:*"),
    "mat":          ("*Đệm cát:*",                  "*Sand Mat:*"),
    "h_lbl":        ("h (m)",                       "h (m)"),
    "punch_exp":    ("Kiểm tra chọc thủng lớp đệm xi măng", "Punching Check – Cement Mat"),
    "qu_mat_lbl":   ("qu đệm xi măng (kPa)",        "Cement mat qu (kPa)"),
    "fs_mat_lbl":   ("Hệ số an toàn Fs",            "Safety Factor Fs"),
    "theta_lbl":    ("Góc đàn hồi dẻo θ (°)",       "Plastic Arch Angle θ (°)"),
    "qa_lbl":       ("qa vùng không GC (kPa)",      "qa Unimproved Zone (kPa)"),
    "theory_exp":   ("Lý thuyết tính toán – TCVN 9403:2012",
                     "Design Theory – TCVN 9403:2012"),
    # Page 3 – Comparison
    "p3_sub":       ("So sánh các phương án khoảng cách trụ", "Pile Spacing Alternatives"),
    "setup_exp":    ("Thiết lập phương án",          "Setup Alternatives"),
    "sp_title":     ("Khoảng cách trụ",              "Pile Spacing"),
    "auto_lbl":     ("Tự động",                     "Auto"),
    "manual_lbl":   ("Nhập tay",                    "Manual"),
    "e_min":        ("e min (m)",                   "e min (m)"),
    "e_max":        ("e max (m)",                   "e max (m)"),
    "step_lbl":     ("Bước (m)",                    "Step (m)"),
    "sp_list":      ("Danh sách e (m), cách nhau bởi dấu phẩy",
                     "List of e (m), comma-separated"),
    "mat_punch":    ("Lớp đệm xi măng – kiểm tra chọc thủng",
                     "Cement Mat – Punching Check"),
    "qu_mat_sp":    ("qu đệm (kPa)",                "mat qu (kPa)"),
    "rec_sel":      ("Chọn phương án thiết kế",     "Select Design Alternative"),
    "pa_table":     ("Bảng so sánh phương án",      "Alternatives Comparison Table"),
    "param_sens":   ("Phân tích tham số (giữ nguyên e = PA kiến nghị)",
                     "Parametric Analysis (fixed e = recommended alt.)"),
    "qu_comp":      ("So sánh qu thiết kế",         "qu Design Comparison"),
    "D_comp":       ("So sánh đường kính D",        "Diameter D Comparison"),
    "hmat_comp":    ("So sánh chiều dày đệm cát",   "Sand Mat Thickness Comparison"),
    "qu_inp":       ("Các giá trị qu (kPa)",        "qu values (kPa)"),
    "D_inp":        ("Các giá trị D (m)",           "D values (m)"),
    "hmat_inp":     ("Các giá trị h_mat (m)",       "h_mat values (m)"),
    "punch_chart":  ("Kiểm tra chọc thủng đệm xi măng", "Cement Mat Punching Check"),
    "shear_ax":     ("Ứng suất cắt (kPa)",          "Shear Stress (kPa)"),
    # Page 4 – Results
    "p4_sub":       ("Kết quả chi tiết – Phương án kiến nghị",
                     "Detailed Results – Recommended Alternative"),
    "no_scenarios": ("Chưa có phương án. Vào tab So sánh PA để tính.",
                     "No alternatives defined. Go to Comparison tab."),
    "rec_pa":       ("Phương án kiến nghị: **PA{n} — e = {e} m**",
                     "Recommended: **Alt.{n} — e = {e} m**"),
    "settle_calc":  ("Tính toán độ lún",            "Settlement Calculation"),
    "bearing_calc": ("Kiểm tra sức chịu tải (AIT – TCVN 9403:2012 Phụ lục B)",
                     "Bearing Capacity Check (AIT – TCVN 9403:2012 Appendix B)"),
    "punch_res":    ("Kiểm tra chọc thủng lớp đệm xi măng (ALiCC)",
                     "Cement Mat Punching Check (ALiCC)"),
    "col_param":    ("Thông số",                    "Parameter"),
    "col_formula":  ("Công thức",                   "Formula"),
    "col_value":    ("Giá trị",                     "Value"),
    "bear_lbl":     ("Sức chịu tải",               "Bearing Capacity"),
    # Page 5 – Export
    "p5_sub":       ("Xuất báo cáo",               "Export Report"),
    "export_sum":   ("Tóm tắt trước khi xuất",     "Summary before export"),
    "rec_alt":      ("Phương án kiến nghị",         "Recommended Alt."),
    "settle_metric":("Độ lún S₁",                  "Settlement S₁"),
    "word_title":   ("Thuyết minh tính toán (Word)", "Calculation Report (Word)"),
    "word_cap":     ("Tài liệu gồm 6 mục: Cơ sở pháp lý · Địa chất · Thông số · "
                     "Phương pháp · So sánh PA · Kết quả PA kiến nghị.",
                     "Document: Legal basis · Geology · Parameters · "
                     "Method · Comparison · Recommended results."),
    "create_word":  ("Tạo file Word",              "Generate Word File"),
    "creating":     ("Đang tạo tài liệu...",        "Generating document..."),
    "dl_docx":      ("Tải xuống (.docx)",           "Download (.docx)"),
    # Sidebar summary
    "si_bh":        ("**HK:**",                    "**BH:**"),
}


def _t(key: str, **kw) -> str:
    """Trả về chuỗi theo ngôn ngữ hiện tại."""
    lang = st.session_state.get("lang", "VN")
    pair = _L.get(key, (key, key))
    s = pair[0 if lang == "VN" else 1]
    return s.format(**kw) if kw else s


# ═══════════════════════════════════════════════════════════════════════════════
# DB HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _db() -> sqlite3.Connection:
    con = sqlite3.connect(_DB)
    con.row_factory = sqlite3.Row
    return con


@st.cache_data(ttl=300)
def _load_boreholes_by_zone(zone_code: str) -> list[dict]:
    with _db() as con:
        rows = con.execute("""
            SELECT b.name, b.elevation_m, b.depth_m
            FROM boreholes b JOIN zones z ON b.zone_id=z.id
            WHERE z.code=? ORDER BY b.name
        """, (zone_code,)).fetchall()
    return [dict(r) for r in rows]


@st.cache_data(ttl=300)
def _load_layers(bh_name: str) -> list[dict]:
    with _db() as con:
        # Thử bảng layers cũ (KE / BXN)
        rows = con.execute("""
            SELECT l.symbol, l.description, l.depth_top_m, l.depth_bot_m, l.thickness_m,
                   ROUND(AVG(lt.gamma_kNm3), 2) AS gamma_kNm3,
                   ROUND(AVG(lt.c_kPa),      1) AS c_kPa,
                   ROUND(AVG(lt.phi_deg),     1) AS phi_deg,
                   ROUND(AVG(lt.e0),          3) AS e0,
                   ROUND(AVG(lt.Cc),          4) AS Cc,
                   ROUND(AVG(lt.Cs),          4) AS Cs,
                   ROUND(AVG(lt.PC_kPa),      1) AS PC_kPa,
                   AVG(lt.Cv_cm2s)               AS Cv_cm2s
            FROM layers l
            JOIN boreholes b ON l.borehole_id = b.id
            LEFT JOIN lab_tests lt
                   ON lt.borehole_id = b.id
                  AND lt.depth_from_m < l.depth_bot_m
                  AND lt.depth_to_m   > l.depth_top_m
            WHERE b.name = ?
            GROUP BY l.id
            ORDER BY l.depth_top_m
        """, (bh_name,)).fetchall()
        if rows:
            return [dict(r) for r in rows]

        # Fallback: strat_layers (NHC – import từ DXF)
        rows = con.execute("""
            SELECT
                COALESCE(
                    (SELECT lt2.symbol_tcvn FROM lab_tests lt2
                     WHERE lt2.borehole_id = b.id
                       AND lt2.depth_from_m < sl.depth_bot_m
                       AND lt2.depth_to_m   > sl.depth_top_m
                     ORDER BY lt2.depth_from_m LIMIT 1),
                    'L' || sl.layer_no
                ) AS symbol,
                sl.description,
                sl.depth_top_m,
                sl.depth_bot_m,
                ROUND(sl.depth_bot_m - sl.depth_top_m, 2) AS thickness_m,
                ROUND(AVG(lt.gamma_kNm3), 2) AS gamma_kNm3,
                ROUND(AVG(lt.c_kPa),      1) AS c_kPa,
                ROUND(AVG(lt.phi_deg),     1) AS phi_deg,
                ROUND(AVG(lt.e0),          3) AS e0,
                ROUND(AVG(lt.Cc),          4) AS Cc,
                ROUND(AVG(lt.Cs),          4) AS Cs,
                ROUND(AVG(lt.PC_kPa),      1) AS PC_kPa,
                AVG(lt.Cv_cm2s)               AS Cv_cm2s
            FROM strat_layers sl
            JOIN boreholes b ON sl.borehole_id = b.id
            LEFT JOIN lab_tests lt
                   ON lt.borehole_id = b.id
                  AND lt.depth_from_m < sl.depth_bot_m
                  AND lt.depth_to_m   > sl.depth_top_m
            WHERE b.name = ?
            GROUP BY sl.id
            ORDER BY sl.depth_top_m
        """, (bh_name,)).fetchall()
        if rows:
            return [dict(r) for r in rows]

        # Fallback cuối: build từ lab_tests (gom run liên tiếp cùng symbol)
        rows = con.execute("""
            SELECT
                symbol_tcvn AS symbol,
                COALESCE(description_vi, symbol_tcvn) AS description,
                MIN(depth_from_m) AS depth_top_m,
                MAX(depth_to_m)   AS depth_bot_m,
                ROUND(AVG(gamma_kNm3), 2) AS gamma_kNm3,
                ROUND(AVG(c_kPa),      1) AS c_kPa,
                ROUND(AVG(phi_deg),    1) AS phi_deg,
                ROUND(AVG(e0),         3) AS e0,
                ROUND(AVG(Cc),         4) AS Cc,
                ROUND(AVG(Cs),         4) AS Cs,
                ROUND(AVG(PC_kPa),     1) AS PC_kPa,
                AVG(Cv_cm2s)             AS Cv_cm2s
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (ORDER BY depth_from_m) -
                    ROW_NUMBER() OVER (PARTITION BY symbol_tcvn ORDER BY depth_from_m) AS grp
                FROM lab_tests
                WHERE borehole_id = (SELECT id FROM boreholes WHERE name = ?)
                  AND symbol_tcvn IS NOT NULL
                  AND depth_from_m IS NOT NULL
            )
            GROUP BY symbol_tcvn, grp
            ORDER BY depth_top_m
        """, (bh_name,)).fetchall()

    if not rows:
        return []
    result = [dict(r) for r in rows]
    # Lấp khoảng trống giữa các run: kéo đáy lớp trước = đỉnh lớp sau
    for i in range(len(result) - 1):
        result[i]["depth_bot_m"] = result[i + 1]["depth_top_m"]
    for r in result:
        r["thickness_m"] = round(r["depth_bot_m"] - r["depth_top_m"], 2)
    return result


@st.cache_data(ttl=300)
def _load_zone_params_by_symbol(zone_code: str, symbol: str) -> dict:
    """Trả về {Cc, Cs, e0, PC_kPa, Cv_cm2s, gamma_kNm3, source_bh} trung bình
    từ mọi hố khoan trong zone có symbol khớp (dùng khi hố khoan hiện tại thiếu)."""
    with _db() as con:
        row = con.execute("""
            SELECT
                ROUND(AVG(lt.Cc),        4) AS Cc,
                ROUND(AVG(lt.Cs),        4) AS Cs,
                ROUND(AVG(lt.e0),        3) AS e0,
                ROUND(AVG(lt.PC_kPa),    1) AS PC_kPa,
                AVG(lt.Cv_cm2s)             AS Cv_cm2s,
                ROUND(AVG(lt.gamma_kNm3),2) AS gamma_kNm3,
                GROUP_CONCAT(DISTINCT b.name) AS source_bh
            FROM lab_tests lt
            JOIN boreholes b ON lt.borehole_id = b.id
            JOIN zones z ON b.zone_id = z.id
            WHERE z.code = ?
              AND lt.symbol_tcvn = ?
              AND lt.Cc IS NOT NULL
        """, (zone_code, symbol)).fetchone()
    return dict(row) if row and row["Cc"] is not None else {}


@st.cache_data(ttl=300)
def _load_spt(bh_name: str) -> list[dict]:
    with _db() as con:
        # Thử spt_values cũ (KE / BXN)
        rows = con.execute("""
            SELECT sv.depth_m, sv.N1, sv.N2, sv.N3, sv.N
            FROM spt_values sv
            JOIN boreholes b ON sv.borehole_id = b.id
            WHERE b.name = ?
            ORDER BY sv.depth_m
        """, (bh_name,)).fetchall()
        if rows:
            return [dict(r) for r in rows]

        # Fallback: spt_tests (NHC – import từ DXF)
        rows = con.execute("""
            SELECT st.depth_from_m AS depth_m,
                   st.N1, st.N2, st.N3,
                   st.N_value AS N
            FROM spt_tests st
            JOIN boreholes b ON st.borehole_id = b.id
            WHERE b.name = ?
            ORDER BY st.depth_from_m
        """, (bh_name,)).fetchall()
    return [dict(r) for r in rows]


@st.cache_data(ttl=300)
def _load_vst_su(zone_code: str) -> pd.DataFrame:
    """VST Su toàn zone, dùng để vẽ profile và tính trung bình."""
    with _db() as con:
        rows = con.execute("""
            SELECT vt.depth_m, vt.Su_kPa, vl.name loc_name
            FROM vane_shear_tests vt
            JOIN vst_locations vl ON vt.vst_loc_id=vl.id
            JOIN zones z ON vl.zone_id=z.id
            WHERE z.code=? AND vt.Su_kPa IS NOT NULL
            ORDER BY vt.depth_m
        """, (zone_code,)).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


@st.cache_data(ttl=300)
def _load_lab(bh_name: str) -> pd.DataFrame:
    with _db() as con:
        rows = con.execute("""
            SELECT depth_from_m, depth_to_m, gamma_kNm3, e0,
                   Cu_UU_kPa, c_kPa, phi_deg, Cc, Cs, E_kPa
            FROM lab_tests WHERE borehole_id=(
                SELECT id FROM boreholes WHERE name=?
            ) ORDER BY depth_from_m
        """, (bh_name,)).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


@st.cache_data(ttl=300)
def _load_consol_summary(zone_code: str) -> pd.DataFrame:
    """Per-borehole summary: số mẫu và trung bình các chỉ tiêu nén cố kết."""
    with _db() as con:
        rows = con.execute("""
            SELECT
                b.name AS borehole,
                COUNT(lt.id) AS n_mau,
                SUM(CASE WHEN lt.Cc IS NOT NULL THEN 1 ELSE 0 END) AS n_Cc,
                ROUND(AVG(CASE WHEN lt.Cc  IS NOT NULL THEN lt.Cc  END), 4) AS Cc_tb,
                ROUND(AVG(CASE WHEN lt.Cs  IS NOT NULL THEN lt.Cs  END), 4) AS Cs_tb,
                ROUND(AVG(CASE WHEN lt.Cv_cm2s IS NOT NULL THEN lt.Cv_cm2s END), 12) AS Cv_tb,
                ROUND(AVG(CASE WHEN lt.k_cm_s  IS NOT NULL THEN lt.k_cm_s  END), 12) AS k_tb,
                ROUND(MIN(CASE WHEN lt.PC_kPa  IS NOT NULL THEN lt.PC_kPa  END), 1) AS PC_min,
                ROUND(MAX(CASE WHEN lt.PC_kPa  IS NOT NULL THEN lt.PC_kPa  END), 1) AS PC_max,
                ROUND(AVG(CASE WHEN lt.e0      IS NOT NULL THEN lt.e0      END), 3) AS e0_tb
            FROM boreholes b
            JOIN zones z ON b.zone_id = z.id
            LEFT JOIN lab_tests lt ON lt.borehole_id = b.id
            WHERE z.code = ?
            GROUP BY b.name
            HAVING n_Cc > 0
            ORDER BY b.name
        """, (zone_code,)).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


@st.cache_data(ttl=300)
def _load_cdm_tests() -> pd.DataFrame:
    with _db() as con:
        rows = con.execute("""
            SELECT ct.*, b.name bh_name
            FROM cdm_tests ct JOIN boreholes b ON ct.borehole_id=b.id
            ORDER BY ct.cement_type, ct.WC_ratio, ct.dosage_kgm3
        """).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def _clay_params(bh_name: str, zone_code: str) -> dict:
    """Trả về h_clay, elevation, depth_clay_bot từ layers."""
    layers = _load_layers(bh_name)
    syms = _CLAY_SYMBOLS.get(zone_code, ["1", "2"])
    clay = [l for l in layers if l["symbol"] in syms]
    if not clay:
        return {}
    h_clay = sum(l["thickness_m"] or 0 for l in clay)
    depth_bot = max(l["depth_bot_m"] for l in clay)
    with _db() as con:
        row = con.execute("SELECT elevation_m FROM boreholes WHERE name=?", (bh_name,)).fetchone()
    elev = row["elevation_m"] if row and row["elevation_m"] else 0.0
    return {"h_clay": round(h_clay, 2), "depth_clay_bot": round(depth_bot, 2),
            "elev_clay_bot": round(elev - depth_bot, 2), "elevation_m": elev}


def _su_avg_in_range(zone_code: str, depth_top: float, depth_bot: float) -> float | None:
    df = _load_vst_su(zone_code)
    if df.empty:
        return None
    sub = df[(df.depth_m >= depth_top) & (df.depth_m <= depth_bot)]
    return round(float(sub.Su_kPa.mean()), 2) if not sub.empty else None


def _gamma_avg(bh_name: str) -> float:
    df = _load_lab(bh_name)
    if df.empty or df.gamma_kNm3.dropna().empty:
        return 15.0
    return round(float(df.gamma_kNm3.dropna().mean()), 3)


# ═══════════════════════════════════════════════════════════════════════════════
# 3D BOREHOLE MAP
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def _load_borehole_3d_data() -> tuple[list[dict], list[dict]]:
    if not _DB.exists():
        return [], []
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    bhs = [dict(r) for r in conn.execute(
        "SELECT b.id, b.name, z.code zone, b.elevation_m, b.depth_m, "
        "b.x_coord_m, b.y_coord_m "
        "FROM boreholes b JOIN zones z ON z.id=b.zone_id "
        "WHERE b.x_coord_m IS NOT NULL "
        "  AND b.elevation_m IS NOT NULL AND b.depth_m IS NOT NULL "
        "ORDER BY z.id, b.name"
    ).fetchall()]
    ids = [b["id"] for b in bhs]
    if not ids:
        conn.close()
        return [], []
    ph = ",".join("?" * len(ids))
    lays = [dict(r) for r in conn.execute(
        f"SELECT borehole_id, symbol, description, depth_top_m, depth_bot_m "
        f"FROM layers WHERE borehole_id IN ({ph}) ORDER BY borehole_id, depth_top_m",
        ids,
    ).fetchall()]
    conn.close()
    return bhs, lays


@st.cache_data(ttl=300, show_spinner=False)
def _load_clay_bottom_3d() -> list[dict]:
    """Đáy lớp bùn sét yếu cho mỗi hố khoan có tọa độ."""
    if not _DB.exists():
        return []
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("""
        SELECT b.name, z.code zone, b.elevation_m, b.x_coord_m, b.y_coord_m,
               ROUND(MAX(l.depth_bot_m), 3) clay_bot_depth,
               ROUND(b.elevation_m - MAX(l.depth_bot_m), 3) clay_bot_elev
        FROM boreholes b
        JOIN zones z ON z.id=b.zone_id
        JOIN layers l ON l.borehole_id=b.id
        WHERE b.x_coord_m IS NOT NULL
          AND ((z.code='KE'  AND l.symbol IN ('1','1b'))
            OR (z.code IN ('BXN','NHC') AND l.symbol='2'))
        GROUP BY b.id
        ORDER BY z.id, b.name
    """).fetchall()]
    conn.close()
    return rows


def _draw_boreholes_3d(
    selected_zones: list[str],
    show_clay_bottom: bool = False,
    show_cdm_top: bool = False,
    cdm_top_z: float = 2.7,
    focus_bh: str | None = None,
    pair_highlight: tuple | None = None,
) -> "go.Figure":
    """pair_highlight = (bh1_name, bh2_name, dist_m) — vẽ đường kích thước giữa 2 HK."""
    from collections import defaultdict

    bhs, lays = _load_borehole_3d_data()
    bhs  = [b for b in bhs if b["zone"] in selected_zones]
    if focus_bh:
        bhs_focus = [b for b in bhs if b["name"] == focus_bh]
        if bhs_focus:
            bhs = bhs_focus
    bh_ids = {b["id"] for b in bhs}
    lays = [l for l in lays if l["borehole_id"] in bh_ids]

    fig = go.Figure()
    if not bhs:
        fig.update_layout(title="Không có dữ liệu tọa độ hố khoan")
        return fig

    lay_by_bh: dict[int, list[dict]] = defaultdict(list)
    for l in lays:
        lay_by_bh[l["borehole_id"]].append(l)

    # Một trace / symbol → gộp legend
    all_syms: list[str] = []
    for l in lays:
        if l["symbol"] not in all_syms:
            all_syms.append(l["symbol"])

    added_legends: set[str] = set()
    for sym in all_syms:
        color = _LAYER_COLORS.get(sym, _LAYER_DEFAULT_COLOR)
        xs, ys, zs, texts = [], [], [], []
        for bh in bhs:
            for l in lay_by_bh[bh["id"]]:
                if l["symbol"] != sym:
                    continue
                z0 = bh["elevation_m"] - l["depth_top_m"]
                z1 = bh["elevation_m"] - l["depth_bot_m"]
                desc = l.get("description") or sym
                hover = (
                    f"<b>{bh['name']}</b><br>"
                    f"Lớp {sym}: {desc}<br>"
                    f"Sâu {l['depth_top_m']:.1f}–{l['depth_bot_m']:.1f} m<br>"
                    f"Cao độ {z0:.2f} → {z1:.2f} m"
                )
                xs += [bh["x_coord_m"], bh["x_coord_m"], None]
                ys += [bh["y_coord_m"], bh["y_coord_m"], None]
                zs += [z0, z1, None]
                texts += [hover, hover, None]

        show_leg = sym not in added_legends
        added_legends.add(sym)
        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs, mode="lines",
            line=dict(color=color, width=10),
            name=f"Lớp {sym}", legendgroup=sym, showlegend=show_leg,
            hovertemplate="%{text}<extra></extra>", text=texts,
        ))

    # Labels tên hố khoan
    _zone_colors = {"KE": "#E53935", "BXN": "#1565C0", "NHC": "#2E7D32"}
    fig.add_trace(go.Scatter3d(
        x=[b["x_coord_m"] for b in bhs],
        y=[b["y_coord_m"] for b in bhs],
        z=[b["elevation_m"] + 3 for b in bhs],
        mode="text+markers",
        text=[b["name"].replace("BXN-CV-", "").replace("KE-", "") for b in bhs],
        textposition="top center",
        textfont=dict(size=9, color="#212121"),
        marker=dict(
            size=5,
            color=[_zone_colors.get(b["zone"], "#333") for b in bhs],
            symbol=[_ZONE_MARKER.get(b["zone"], "circle") for b in bhs],
        ),
        name="Vị trí HK", showlegend=True,
        hovertemplate="<b>%{text}</b><extra></extra>",
    ))

    # Đáy lớp bùn
    if show_clay_bottom:
        _clay = [c for c in _load_clay_bottom_3d() if c["zone"] in selected_zones]
        if len(_clay) >= 3:
            cx = [c["x_coord_m"] for c in _clay]
            cy = [c["y_coord_m"] for c in _clay]
            cz = [c["clay_bot_elev"] for c in _clay]
            ct = [
                f"<b>{c['name']}</b><br>"
                f"Đáy bùn sâu: {c['clay_bot_depth']:.1f} m<br>"
                f"Cao độ đáy: {c['clay_bot_elev']:.2f} m"
                for c in _clay
            ]
            fig.add_trace(go.Mesh3d(
                x=cx, y=cy, z=cz, delaunayaxis="z",
                intensity=cz,
                colorscale=[[0, "#0D47A1"], [0.5, "#42A5F5"], [1, "#BBDEFB"]],
                showscale=False, opacity=0.55,
                name="Đáy lớp bùn", legendgroup="clay_bot", showlegend=True,
                hovertemplate="%{text}<extra></extra>", text=ct,
            ))
            fig.add_trace(go.Scatter3d(
                x=cx, y=cy, z=cz, mode="markers",
                marker=dict(size=6, color="#0D47A1", symbol="diamond"),
                name="Điểm đáy bùn", legendgroup="clay_bot", showlegend=False,
                hovertemplate="%{text}<extra></extra>", text=ct,
            ))
            vx, vy, vz, vt = [], [], [], []
            for c in _clay:
                vx += [c["x_coord_m"], c["x_coord_m"], None]
                vy += [c["y_coord_m"], c["y_coord_m"], None]
                vz += [c["elevation_m"], c["clay_bot_elev"], None]
                lbl = f"<b>{c['name']}</b><br>Bùn dày {c['clay_bot_depth']:.1f} m"
                vt += [lbl, lbl, None]
            fig.add_trace(go.Scatter3d(
                x=vx, y=vy, z=vz, mode="lines",
                line=dict(color="#1565C0", width=3, dash="dot"),
                name="Chiều dày bùn", legendgroup="clay_bot", showlegend=False,
                hovertemplate="%{text}<extra></extra>", text=vt,
            ))

    # Mặt phẳng đỉnh trụ CDM
    if show_cdm_top:
        all_x = [b["x_coord_m"] for b in bhs]
        all_y = [b["y_coord_m"] for b in bhs]
        pad = 20.0
        mx, Mx = min(all_x) - pad, max(all_x) + pad
        my, My = min(all_y) - pad, max(all_y) + pad
        fig.add_trace(go.Mesh3d(
            x=[mx, Mx, Mx, mx], y=[my, my, My, My],
            z=[cdm_top_z]*4, i=[0, 0], j=[1, 2], k=[2, 3],
            color="#E91E63", opacity=0.25,
            name=f"Đỉnh trụ CDM +{cdm_top_z:.2f} m",
            showlegend=True, flatshading=True,
            hovertemplate=f"Đỉnh trụ CDM: <b>{cdm_top_z:.2f} m</b><extra></extra>",
        ))
        fig.add_trace(go.Scatter3d(
            x=[mx, Mx, Mx, mx, mx], y=[my, my, My, My, my],
            z=[cdm_top_z]*5, mode="lines",
            line=dict(color="#C2185B", width=3),
            name="Viền đỉnh CDM", showlegend=False,
        ))

    # Đường kích thước giữa 2 hố khoan (khi user chọn cặp)
    if pair_highlight:
        _ph_b1, _ph_b2, _ph_dist = pair_highlight
        _ph_bh1 = next((b for b in bhs if b["name"] == _ph_b1), None)
        _ph_bh2 = next((b for b in bhs if b["name"] == _ph_b2), None)
        if _ph_bh1 and _ph_bh2:
            _ph_z = max(_ph_bh1["elevation_m"], _ph_bh2["elevation_m"]) + 4
            _ph_mx = (_ph_bh1["x_coord_m"] + _ph_bh2["x_coord_m"]) / 2
            _ph_my = (_ph_bh1["y_coord_m"] + _ph_bh2["y_coord_m"]) / 2
            fig.add_trace(go.Scatter3d(
                x=[_ph_bh1["x_coord_m"], _ph_bh2["x_coord_m"]],
                y=[_ph_bh1["y_coord_m"], _ph_bh2["y_coord_m"]],
                z=[_ph_z, _ph_z],
                mode="lines",
                line=dict(color="#FF6F00", width=6),
                name=f"Khoảng cách {_ph_b1}↔{_ph_b2}",
                showlegend=True,
                hovertemplate=f"<b>{_ph_b1} ↔ {_ph_b2}</b><br>Khoảng cách: {_ph_dist:.1f} m<extra></extra>",
            ))
            # Nhãn khoảng cách tại trung điểm
            fig.add_trace(go.Scatter3d(
                x=[_ph_mx], y=[_ph_my], z=[_ph_z + 1.5],
                mode="text",
                text=[f"  {_ph_dist:.1f} m"],
                textfont=dict(size=14, color="#E65100"),
                showlegend=False,
                hovertemplate=f"{_ph_dist:.1f} m<extra></extra>",
            ))
            # Đường dọc từ mặt đất xuống đến đường kích thước (2 đầu)
            for _ph_bh in (_ph_bh1, _ph_bh2):
                fig.add_trace(go.Scatter3d(
                    x=[_ph_bh["x_coord_m"], _ph_bh["x_coord_m"]],
                    y=[_ph_bh["y_coord_m"], _ph_bh["y_coord_m"]],
                    z=[_ph_bh["elevation_m"] + 1, _ph_z],
                    mode="lines",
                    line=dict(color="#FF6F00", width=2, dash="dot"),
                    showlegend=False,
                    hoverinfo="skip",
                ))

    # Layout
    all_x = [b["x_coord_m"] for b in bhs]
    all_y = [b["y_coord_m"] for b in bhs]
    span_x = max(all_x) - min(all_x) or 1
    span_y = max(all_y) - min(all_y) or 1
    max_z = max(b["elevation_m"] for b in bhs) + 5
    min_z = min(b["elevation_m"] - b["depth_m"] for b in bhs) - 2

    fig.update_layout(
        height=420,
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(
            x=1.01, y=0.95,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#ccc", borderwidth=1,
            font=dict(size=11),
        ),
        scene=dict(
            xaxis=dict(title="X — Easting (m)", tickformat=".0f"),
            yaxis=dict(title="Y — Northing (m)", tickformat=".0f"),
            zaxis=dict(title="Cao độ (m)", range=[min_z, max_z + 5]),
            aspectmode="manual",
            aspectratio=dict(
                x=span_x / max(span_x, span_y),
                y=span_y / max(span_x, span_y),
                z=0.35,
            ),
            camera=dict(eye=dict(x=1.4, y=-1.4, z=0.8)),
        ),
        paper_bgcolor="#FAFAFA",
    )
    return fig


def _draw_boreholes_3d_mpl(
    selected_zones: list[str],
    show_clay_bottom: bool = False,
    show_cdm_top: bool = False,
    cdm_top_z: float = 2.7,
    focus_bh: str | None = None,
    pair_highlight: tuple | None = None,
    elev: float = 20.0,
    azim: float = -60.0,
    zoom: float = 1.0,
):
    """Matplotlib fallback cho bản đồ 3D địa chất (khi không có plotly)."""
    import matplotlib.pyplot as plt
    from collections import defaultdict
    try:
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    except ImportError:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, "Không có mpl_toolkits.mplot3d", ha="center", va="center",
                transform=ax.transAxes)
        ax.axis("off")
        return fig

    bhs, lays = _load_borehole_3d_data()
    bhs = [b for b in bhs if b["zone"] in selected_zones]
    if focus_bh:
        bhs_focus = [b for b in bhs if b["name"] == focus_bh]
        if bhs_focus:
            bhs = bhs_focus
    if not bhs:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, "Không có dữ liệu tọa độ hố khoan", ha="center", va="center",
                transform=ax.transAxes)
        ax.axis("off")
        return fig

    bh_ids = {b["id"] for b in bhs}
    lays = [l for l in lays if l["borehole_id"] in bh_ids]
    lay_by_bh: dict[int, list[dict]] = defaultdict(list)
    for l in lays:
        lay_by_bh[l["borehole_id"]].append(l)

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")

    # Vẽ từng đoạn lớp đất bằng đường thẳng đứng có màu
    legend_seen: set[str] = set()
    for bh in bhs:
        for l in lay_by_bh[bh["id"]]:
            sym   = l["symbol"]
            color = _LAYER_COLORS.get(sym, _LAYER_DEFAULT_COLOR)
            z0    = bh["elevation_m"] - l["depth_top_m"]
            z1    = bh["elevation_m"] - l["depth_bot_m"]
            label = f"Lớp {sym}" if sym not in legend_seen else None
            legend_seen.add(sym)
            ax.plot(
                [bh["x_coord_m"], bh["x_coord_m"]],
                [bh["y_coord_m"], bh["y_coord_m"]],
                [z0, z1],
                color=color, lw=5, label=label, solid_capstyle="butt",
            )

    # Markers + nhãn tên HK
    _zone_colors = {"KE": "#E53935", "BXN": "#1565C0", "NHC": "#2E7D32"}
    _zone_markers = {"KE": "o", "BXN": "s", "NHC": "D"}
    for bh in bhs:
        z_top = bh["elevation_m"] + 3
        ax.scatter(bh["x_coord_m"], bh["y_coord_m"], z_top,
                   c=_zone_colors.get(bh["zone"], "#333"),
                   marker=_zone_markers.get(bh["zone"], "o"),
                   s=40, edgecolor="#000", lw=0.5)
        _nm = bh["name"].replace("BXN-CV-", "").replace("KE-", "")
        ax.text(bh["x_coord_m"], bh["y_coord_m"], z_top + 0.5, _nm,
                fontsize=8, ha="center", color="#212121")

    # Mặt đáy lớp bùn (vẽ scatter, không vẽ mesh)
    if show_clay_bottom:
        _clay = [c for c in _load_clay_bottom_3d() if c["zone"] in selected_zones]
        if _clay:
            ax.scatter(
                [c["x_coord_m"] for c in _clay],
                [c["y_coord_m"] for c in _clay],
                [c["clay_bot_elev"] for c in _clay],
                c="#0D47A1", marker="D", s=50, label="Đáy bùn",
            )

    # Mặt phẳng đỉnh trụ CDM
    if show_cdm_top:
        import numpy as _np
        all_x_ = [b["x_coord_m"] for b in bhs]
        all_y_ = [b["y_coord_m"] for b in bhs]
        pad = 20.0
        mx, Mx = min(all_x_) - pad, max(all_x_) + pad
        my, My = min(all_y_) - pad, max(all_y_) + pad
        ax.plot_surface(
            _np.array([[mx, Mx], [mx, Mx]]),
            _np.array([[my, my], [My, My]]),
            _np.array([[cdm_top_z]*2, [cdm_top_z]*2]),
            color="#E91E63", alpha=0.25, edgecolor="#C2185B",
        )

    # Đường kích thước giữa 2 HK
    if pair_highlight:
        _b1, _b2, _dist = pair_highlight
        _bh1 = next((b for b in bhs if b["name"] == _b1), None)
        _bh2 = next((b for b in bhs if b["name"] == _b2), None)
        if _bh1 and _bh2:
            _z = max(_bh1["elevation_m"], _bh2["elevation_m"]) + 4
            ax.plot(
                [_bh1["x_coord_m"], _bh2["x_coord_m"]],
                [_bh1["y_coord_m"], _bh2["y_coord_m"]],
                [_z, _z],
                color="#FF6F00", lw=2.5,
            )
            _mx = (_bh1["x_coord_m"] + _bh2["x_coord_m"]) / 2
            _my = (_bh1["y_coord_m"] + _bh2["y_coord_m"]) / 2
            ax.text(_mx, _my, _z + 1.5, f"{_dist:.1f} m",
                    fontsize=11, color="#E65100", ha="center", fontweight="bold")

    ax.set_xlabel("X — Easting (m)", fontsize=9)
    ax.set_ylabel("Y — Northing (m)", fontsize=9)
    ax.set_zlabel("Cao độ (m)", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.legend(loc="upper left", fontsize=7, framealpha=0.85, ncol=2)
    ax.view_init(elev=float(elev), azim=float(azim))

    # Zoom: thu/giãn quanh tâm trục
    if abs(zoom - 1.0) > 1e-3:
        for lim_get, lim_set in (
            (ax.get_xlim, ax.set_xlim),
            (ax.get_ylim, ax.set_ylim),
            (ax.get_zlim, ax.set_zlim),
        ):
            _lo, _hi = lim_get()
            _ctr  = 0.5 * (_lo + _hi)
            _half = 0.5 * (_hi - _lo) / float(zoom)
            lim_set(_ctr - _half, _ctr + _half)

    fig.tight_layout()
    return fig


def _build_borehole_3d_deck(
    selected_zones: list[str],
    show_clay_bottom: bool = False,
    show_cdm_top: bool = False,
    cdm_top_z: float = 2.7,
    pair_highlight: tuple | None = None,
    z_scale: float = 5.0,
    col_radius: float = 2.5,
    pair_lines: list[dict] | None = None,
    show_pair_labels: bool = True,
    show_bh_names: bool = True,
):
    """Pydeck 3D map cho hố khoan — native drag/zoom/rotate qua deck.gl.
    z_scale: phóng đại trục Z (vì khoảng cách HK ~100m, độ sâu chỉ ~30m,
             nếu không scale sẽ thấy như mặt phẳng)."""
    bhs, lays = _load_borehole_3d_data()
    bhs = [b for b in bhs if b["zone"] in selected_zones]
    if not bhs:
        return None
    bh_ids = {b["id"] for b in bhs}
    lays = [l for l in lays if l["borehole_id"] in bh_ids]

    # VN2000 → WGS84
    for b in bhs:
        _lat, _lon = _vn2000_to_latlon(b["y_coord_m"], b["x_coord_m"])
        b["lat"], b["lon"] = _lat, _lon
    bh_by_id = {b["id"]: b for b in bhs}

    def _hex_rgb(h: str) -> list[int]:
        h = h.lstrip("#")
        if len(h) < 6:
            return [200, 200, 200]
        return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)]

    # ColumnLayer: mỗi lớp = trụ extrude từ z_bot lên z_top → thấy rõ bề dày
    columns = []
    for l in lays:
        b = bh_by_id.get(l["borehole_id"])
        if b is None:
            continue
        sym  = l["symbol"]
        col  = _LAYER_COLORS.get(sym, _LAYER_DEFAULT_COLOR)
        rgb  = _hex_rgb(col)
        z_top = (b["elevation_m"] - l["depth_top_m"]) * z_scale
        z_bot = (b["elevation_m"] - l["depth_bot_m"]) * z_scale
        thick = max(z_top - z_bot, 0.01)
        columns.append({
            # base position bao gồm altitude → ColumnLayer extrude lên từ z này
            "position":  [b["lon"], b["lat"], z_bot],
            "elevation": thick,
            "color":     rgb + [220],
            "bh":        b["name"],
            "sym":       sym,
            "desc":      (l.get("description") or sym)[:40],
            "rng":       f"{l['depth_top_m']:.1f}–{l['depth_bot_m']:.1f} m",
            "thk":       f"{l['depth_bot_m'] - l['depth_top_m']:.2f} m",
        })

    layers_deck = [
        pdk.Layer(
            "ColumnLayer",
            columns,
            pickable=True,
            extruded=True,
            radius=float(col_radius),    # bán kính trụ — đơn vị mét
            disk_resolution=24,          # 24 cạnh → trông tròn
            elevation_scale=1.0,         # đã scale trong z_scale
            get_position="position",
            get_elevation="elevation",
            get_fill_color="color",
            line_width_min_pixels=0,
            material={"ambient": 0.6, "diffuse": 0.6, "shininess": 30},
            auto_highlight=True,
        ),
    ]

    # Nhãn tên HK (toggle được)
    _zone_rgb = {"KE": [229, 57, 53], "BXN": [21, 101, 192], "NHC": [46, 125, 50]}
    if show_bh_names:
        label_data = [
            {
                "position": [b["lon"], b["lat"], (b["elevation_m"] + 3) * z_scale],
                "text":     b["name"].replace("BXN-CV-", "").replace("KE-", ""),
                "color":    _zone_rgb.get(b["zone"], [50, 50, 50]),
            }
            for b in bhs
        ]
        layers_deck.append(pdk.Layer(
            "TextLayer",
            label_data,
            get_position="position",
            get_text="text",
            get_color="color",
            get_size=14,
            size_units="pixels",
            get_alignment_baseline="'bottom'",
            pickable=False,
        ))

    # Markers HK (ScatterplotLayer)
    marker_data = [
        {
            "position": [b["lon"], b["lat"], b["elevation_m"] * z_scale],
            "color":    _zone_rgb.get(b["zone"], [50, 50, 50]),
            "bh":       b["name"],
            "zone":     b["zone"],
        }
        for b in bhs
    ]
    layers_deck.append(pdk.Layer(
        "ScatterplotLayer",
        marker_data,
        get_position="position",
        get_fill_color="color",
        get_radius=6,
        radius_units="pixels",
        pickable=True,
    ))

    # Đáy lớp bùn
    if show_clay_bottom:
        _clay = [c for c in _load_clay_bottom_3d() if c["zone"] in selected_zones]
        if _clay:
            clay_data = []
            for c in _clay:
                _lat, _lon = _vn2000_to_latlon(c["y_coord_m"], c["x_coord_m"])
                clay_data.append({
                    "position": [_lon, _lat, c["clay_bot_elev"] * z_scale],
                    "bh":       c["name"],
                    "elev":     c["clay_bot_elev"],
                    "depth":    c["clay_bot_depth"],
                })
            layers_deck.append(pdk.Layer(
                "ScatterplotLayer",
                clay_data,
                get_position="position",
                get_fill_color=[13, 71, 161, 200],
                get_radius=8,
                radius_units="pixels",
                pickable=True,
            ))

    # Mặt phẳng đỉnh trụ CDM (PolygonLayer)
    if show_cdm_top:
        all_lons = [b["lon"] for b in bhs]
        all_lats = [b["lat"] for b in bhs]
        pad = 0.0005
        mn_lon, mx_lon = min(all_lons) - pad, max(all_lons) + pad
        mn_lat, mx_lat = min(all_lats) - pad, max(all_lats) + pad
        cdm_data = [{
            "polygon": [
                [mn_lon, mn_lat], [mx_lon, mn_lat],
                [mx_lon, mx_lat], [mn_lon, mx_lat],
            ],
            "z": cdm_top_z * z_scale,
        }]
        layers_deck.append(pdk.Layer(
            "PolygonLayer",
            cdm_data,
            get_polygon="polygon",
            get_elevation="z",
            extruded=False,
            get_fill_color=[233, 30, 99, 70],
            get_line_color=[194, 24, 91],
            line_width_min_pixels=1,
        ))

    # Vẽ tất cả cặp khoảng cách HK (color-coded theo status TCCS41)
    _bh_lookup = {b["name"]: b for b in bhs}
    _status_color = {
        "Đạt":      [46, 125, 50, 220],     # xanh
        "Gần quá":  [229, 57, 53, 220],     # đỏ
        "Xa quá":   [255, 152, 0, 220],     # cam
    }
    if pair_lines:
        _line_data = []
        _label_data = []
        # Cao độ đường kích thước: max elev của tất cả HK + offset
        _z_lines = (max(b["elevation_m"] for b in bhs) + 4) * z_scale
        for p in pair_lines:
            _b1 = _bh_lookup.get(p["bh1"])
            _b2 = _bh_lookup.get(p["bh2"])
            if not (_b1 and _b2):
                continue
            _col = _status_color.get(p.get("status", ""), [120, 120, 120, 200])
            _dist = p.get("distance_m", 0.0)
            _line_data.append({
                "path": [[_b1["lon"], _b1["lat"], _z_lines],
                         [_b2["lon"], _b2["lat"], _z_lines]],
                "color":    _col,
                "bh1":      p["bh1"],
                "bh2":      p["bh2"],
                "distance": f"{_dist:.1f} m",
                "status":   p.get("status", ""),
            })
            if show_pair_labels:
                _label_data.append({
                    "position": [(_b1["lon"] + _b2["lon"]) / 2,
                                 (_b1["lat"] + _b2["lat"]) / 2,
                                 _z_lines + 1],
                    "text":     f"{_dist:.0f}m",
                    "color":    _col[:3],
                })
        if _line_data:
            layers_deck.append(pdk.Layer(
                "PathLayer",
                _line_data,
                get_path="path",
                get_color="color",
                get_width=2,
                width_units="pixels",
                pickable=True,
            ))
        if _label_data:
            layers_deck.append(pdk.Layer(
                "TextLayer",
                _label_data,
                get_position="position",
                get_text="text",
                get_color="color",
                get_size=12,
                size_units="pixels",
                get_alignment_baseline="'bottom'",
            ))

    # Đường kích thước được highlight (cặp user chọn cụ thể)
    if pair_highlight:
        _b1n, _b2n, _dist = pair_highlight
        _b1 = next((b for b in bhs if b["name"] == _b1n), None)
        _b2 = next((b for b in bhs if b["name"] == _b2n), None)
        if _b1 and _b2:
            _zline = (max(_b1["elevation_m"], _b2["elevation_m"]) + 6) * z_scale
            layers_deck.append(pdk.Layer(
                "PathLayer",
                [{
                    "path": [[_b1["lon"], _b1["lat"], _zline],
                             [_b2["lon"], _b2["lat"], _zline]],
                    "color": [255, 111, 0, 255],
                }],
                get_path="path",
                get_color="color",
                get_width=5,
                width_units="pixels",
                pickable=False,
            ))
            _mid_lon = (_b1["lon"] + _b2["lon"]) / 2
            _mid_lat = (_b1["lat"] + _b2["lat"]) / 2
            layers_deck.append(pdk.Layer(
                "TextLayer",
                [{
                    "position": [_mid_lon, _mid_lat, _zline + 1],
                    "text":     f"{_dist:.1f} m",
                    "color":    [230, 81, 0],
                }],
                get_position="position",
                get_text="text",
                get_color="color",
                get_size=18,
                size_units="pixels",
            ))

    mid_lat = sum(b["lat"] for b in bhs) / len(bhs)
    mid_lon = sum(b["lon"] for b in bhs) / len(bhs)
    view = pdk.ViewState(
        latitude=mid_lat, longitude=mid_lon,
        zoom=16, pitch=55, bearing=-20,
    )
    return pdk.Deck(
        layers=layers_deck,
        initial_view_state=view,
        tooltip={"html": "<b>{bh}{bh1}</b>{bh2}<br>"
                          "<span>Lớp <b>{sym}</b>: {desc}</span>"
                          "<span>Độ sâu: {rng} | Dày: <b>{thk}</b></span>"
                          "<span>Khoảng cách: <b>{distance}</b> — {status}</span>",
                 "style": {"color": "white",
                           "backgroundColor": "rgba(33,33,33,0.92)",
                           "fontSize": "12px"}},
        map_style=None,
    )


_VN2000_CM  = 105.75          # kinh tuyến trục TP.HCM: 105°45'E
_VN2000_FE  = 500_000.0       # False Easting
_M_PER_DEG  = 110_574.0       # m/độ vĩ tuyến (xích đạo ≈ 110,574 m)


def _vn2000_to_latlon(northing: float, easting: float) -> tuple[float, float]:
    """VN-2000 TP.HCM (CM=105°45', FE=500000) → WGS84 (lat, lon).
    Sai số <1 m trong phạm vi TP.HCM; đủ dùng cho overlay bản đồ.
    """
    lat = northing / _M_PER_DEG
    lon = _VN2000_CM + (easting - _VN2000_FE) / (_M_PER_DEG * math.cos(math.radians(lat)))
    return lat, lon


def _project_to_latlon(
    bhs: list[dict],
    ref_bh_name: str = "",
    ref_lat: float = 0.0,
    ref_lon: float = 0.0,
    use_gps_ref: bool = False,
) -> list[dict] | None:
    """Chuyển tọa độ VN-2000 → lat/lon.

    Mặc định dùng công thức trực tiếp CM=105°45'.
    Nếu use_gps_ref=True và có điểm tham chiếu GPS → hiệu chỉnh thêm offset.
    """
    result = []
    for b in bhs:
        if b.get("x_coord_m") is None:
            continue
        lat, lon = _vn2000_to_latlon(b["x_coord_m"], b["y_coord_m"])
        result.append({**b, "lat": lat, "lon": lon})

    if use_gps_ref and ref_bh_name and result:
        ref_calc = next((b for b in result if b["name"] == ref_bh_name), None)
        if ref_calc:
            dlat = ref_lat - ref_calc["lat"]
            dlon = ref_lon - ref_calc["lon"]
            result = [{**b, "lat": b["lat"] + dlat, "lon": b["lon"] + dlon}
                      for b in result]
    return result or None


_MAP_STYLES = {
    "Đường phố (OSM)": "open-street-map",
    "Bản đồ sáng": "carto-positron",
    "Vệ tinh (Esri)": "__esri__",
}


def _draw_map_2d(bhs_ll: list[dict], style_key: str) -> "go.Figure":
    """Bản đồ 2D vị trí hố khoan, hỗ trợ OSM / Esri satellite."""
    _zone_colors = {"KE": "#E53935", "BXN": "#1565C0", "NHC": "#2E7D32"}
    fig = go.Figure()

    for zone, color in _zone_colors.items():
        grp = [b for b in bhs_ll if b["zone"] == zone]
        if not grp:
            continue
        fig.add_trace(go.Scattermap(
            lat=[b["lat"] for b in grp],
            lon=[b["lon"] for b in grp],
            mode="markers+text",
            text=[b["name"].replace("BXN-CV-", "").replace("KE-", "") for b in grp],
            textposition="top right",
            textfont=dict(size=10),
            marker=dict(size=13, color=color),
            name=zone,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "lat=%{lat:.6f}<br>lon=%{lon:.6f}"
                "<extra></extra>"
            ),
        ))

    c_lat = sum(b["lat"] for b in bhs_ll) / len(bhs_ll)
    c_lon = sum(b["lon"] for b in bhs_ll) / len(bhs_ll)

    if style_key == "__esri__":
        map_cfg = dict(
            style="white-bg",
            layers=[{
                "below": "traces",
                "sourcetype": "raster",
                "source": [
                    "https://server.arcgisonline.com/ArcGIS/rest/services/"
                    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
                ],
                "sourceattribution": "Esri World Imagery",
            }],
            center=dict(lat=c_lat, lon=c_lon),
            zoom=17,
        )
    else:
        map_cfg = dict(
            style=style_key,
            center=dict(lat=c_lat, lon=c_lon),
            zoom=17,
        )

    fig.update_layout(
        map=map_cfg,
        height=600,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(
            orientation="h", x=0.01, y=0.01,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#ccc", borderwidth=1,
        ),
        paper_bgcolor="#FAFAFA",
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# CDM CALCULATIONS
# ═══════════════════════════════════════════════════════════════════════════════
def calc_a(D: float, e: float, arrangement: str = "triangle") -> float:
    if arrangement == "triangle":
        return math.pi * D**2 / (2 * math.sqrt(3) * e**2)
    return math.pi * D**2 / (4 * e**2)  # square


def calc_Ec(qu_field: float) -> float:
    return 100 * (qu_field / 2)   # Ec = 100·Cc, Cc = qu/2


def calc_Es(Cu: float) -> float:
    return 250 * Cu


def calc_Etb(a: float, Ec: float, Es: float) -> float:
    return a * Ec + (1 - a) * Es


def calc_S1(q: float, Lc: float, Etb: float) -> float:
    """Độ lún S1 (cm)."""
    return q * Lc / Etb * 100


def calc_sigma_col(q: float, Ec: float, Etb: float) -> float:
    """Ứng suất tập trung lên đầu cọc (kN/m²)."""
    return (Ec / Etb) * q


def calc_Pcol(sigma_col: float, D: float) -> float:
    """Lực nén lên 1 trụ CDM (kN)."""
    return sigma_col * math.pi * D**2 / 4


def calc_bearing(D: float, Lc: float, Cc: float, Cu: float, FS: float = 2.0) -> dict:
    """Sức chịu tải trụ CDM theo phương pháp AIT (TCVN 9403:2012 Phụ lục B)."""
    Ac = math.pi * D**2 / 4
    Qult_col  = 9 * Cc * Ac                         # sức chịu ở mũi (kN)
    Qult_skin = math.pi * D * Lc * Cu               # ma sát thân (kN)
    Qult      = Qult_col + Qult_skin
    Qa        = Qult / FS
    return {"Qult": round(Qult, 1), "Qa": round(Qa, 1),
            "Qult_col": round(Qult_col, 1), "Qult_skin": round(Qult_skin, 1)}


def calc_punching_check(
    D: float, e: float, Hse: float, He: float,
    quckse: float, Fs: float, theta_deg: float,
    gamma_fill: float, gamma_mat: float, qa: float = 0.0,
) -> dict:
    """Kiểm tra chọc thủng lớp đệm xi măng – phương pháp ALiCC (PWRI Japan)."""
    tan_t2 = math.tan(math.radians(theta_deg / 2))   # tan(θ/2) cho Ho
    tan_t  = math.tan(math.radians(theta_deg))        # tan(θ) cho thể tích
    tase   = quckse / (2.0 * Fs)
    Ho     = (e - D) * tan_t2

    if Ho <= He:
        Vsoil = (((e - D) * 0.5 * e**2
                  - math.pi * (e**3 - D**3) / 24.0
                  + (4.0 - math.pi) * (math.sqrt(2) - 1.0) * e**3 / 24.0)
                 * tan_t)
    else:
        r0    = He / tan_t + D / 2.0
        Vsoil = (He * e**2
                 - (1.0/3.0) * (math.pi * r0**2 * (He + D/2.0 * tan_t)
                                - math.pi * D / 2.0 * tan_t))

    r_mat  = Hse / tan_t + D / 2.0
    VCGCXM = (Hse * e**2
              - (1.0/3.0) * (math.pi * r_mat**2 * (Hse + D/2.0 * tan_t)
                             - math.pi * D / 2.0 * tan_t))

    A_unit = e**2 - math.pi * D**2 / 4.0
    PSoil  = ((Vsoil - VCGCXM) * gamma_fill + VCGCXM * gamma_mat) / A_unit
    tse    = (PSoil - qa) * A_unit / (math.pi * D * Hse)

    return {
        "tase_kPa":  round(tase, 2),
        "Ho_m":      round(Ho, 3),
        "He_m":      round(He, 3),
        "cong_thuc": "CT(1) Ho≤He" if Ho <= He else "CT(2) Ho>He",
        "Vsoil_m3":  round(Vsoil, 4),
        "VCGCXM_m3": round(VCGCXM, 4),
        "PSoil_kPa": round(PSoil, 3),
        "tse_kPa":   round(tse, 3),
        "check_CT":  "Đạt" if tse <= tase else "Không đạt",
    }


def build_scenarios(
    D: float, Lc: float, qu_field: float, Cu: float,
    q: float, spacings: list[float], arrangement: str
) -> list[dict]:
    Ec = calc_Ec(qu_field)
    Es = calc_Es(Cu)
    Cc = qu_field / 2
    rows = []
    for e in spacings:
        a    = calc_a(D, e, arrangement)
        Etb  = calc_Etb(a, Ec, Es)
        S1   = calc_S1(q, Lc, Etb)
        sc   = calc_sigma_col(q, Ec, Etb)
        Pcol = calc_Pcol(sc, D)
        bc   = calc_bearing(D, Lc, Cc, Cu)
        rows.append({
            "e (m)": e, "a": round(a, 4), "a (%)": round(a*100, 1),
            "Ec (kN/m²)": int(Ec), "Es (kN/m²)": int(Es),
            "Etb (kN/m²)": round(Etb, 0),
            "S₁ (cm)": round(S1, 2),
            "σ_col (kN/m²)": round(sc, 1),
            "Pcol (kN)": round(Pcol, 1),
            "Qa (kN)": bc["Qa"],
            "Đạt SCT": "Đạt" if Pcol < bc["Qa"] else "Không đạt",
        })
    return rows


def q_total(loads: dict) -> float:
    return (loads.get("q_traffic", 20)
            + loads.get("h_road", 0.8) * loads.get("g_road", 24)
            + loads.get("h_fill", 1.5) * loads.get("g_fill", 18)
            + loads.get("h_mat",  0.4) * loads.get("g_mat",  22.5))


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE INIT
# ═══════════════════════════════════════════════════════════════════════════════
_DEFAULTS = {
    "cdm_zone": "KE",
    "cdm_bh": None,
    "cdm_top_clay": 0.8,
    "cdm_h_clay": 24.8,
    "cdm_Su": 11.2,
    "cdm_gamma": 15.0,
    "cdm_elevation": 0.0,
    "cdm_D": 0.8,
    "cdm_e": 1.6,
    "cdm_L_ngam": 0.5,
    "cdm_Lc": 26.2,
    "cdm_CDTK": 0.8,
    "cdm_qu": 800.0,
    "cdm_FS_lab": 2.0,
    "cdm_arrangement": "triangle",
    "cdm_cement_type": "Hoàng Thạch PCB40",
    "cdm_dosage": 240,
    "cdm_WC": 1.0,
    "cdm_spacings": [1.4, 1.6, 1.8],
    "cdm_rec_idx": 1,
    "cdm_geo_view": "3D địa chất",
    "cdm_map_ref_bh": "",
    "cdm_map_ref_lat": 10.7770,
    "cdm_map_ref_lon": 106.6800,
    "cdm_map_style": "Đường phố (OSM)",
    "cdm_vst_sel": [],
    "cdm_quckse": 600.0,
    "cdm_Fs_mat": 3.0,
    "cdm_theta":  80.0,
    "cdm_qa_mat": 0.0,
    "lang": "VN",
    "cdm_loads": {
        "q_traffic": 20.0,
        "z_tk":   3.5,
        "h_road": 0.8,   "g_road": 24.0,
        "h_fill": 1.5,   "g_fill": 18.0,
        "h_mat":  0.4,   "g_mat":  22.5,
    },
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _get(key):
    return st.session_state.get(key, _DEFAULTS.get(key))


# ═══════════════════════════════════════════════════════════════════════════════
# CHART HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _chart_scenarios(df: pd.DataFrame, rec_idx: int) -> go.Figure:
    """3 biểu đồ con: a(%), Etb, S1."""
    x = [f"e={r['e (m)']}m" for _, r in df.iterrows()]
    colors = ["#ED7D31" if i == rec_idx else "#4472C4" for i in range(len(df))]

    fig = go.Figure()
    # S1
    fig.add_trace(go.Bar(name="S₁ (cm)", x=x, y=df["S₁ (cm)"],
                         marker_color=colors, text=df["S₁ (cm)"].apply(lambda v: f"{v:.2f}"),
                         textposition="outside"))
    fig.update_layout(title="Độ lún S₁ theo khoảng cách trụ",
                      yaxis_title="S₁ (cm)", height=340,
                      legend=dict(orientation="h"), margin=dict(t=40, b=20))
    return fig


def _chart_etb(df: pd.DataFrame, rec_idx: int) -> go.Figure:
    x = [f"e={r['e (m)']}m" for _, r in df.iterrows()]
    colors = ["#ED7D31" if i == rec_idx else "#5B9BD5" for i in range(len(df))]
    fig = go.Figure(go.Bar(name="Etb", x=x, y=df["Etb (kN/m²)"],
                            marker_color=colors,
                            text=df["Etb (kN/m²)"].apply(lambda v: f"{int(v):,}"),
                            textposition="outside"))
    fig.update_layout(title="Mô đun tương đương Etb", yaxis_title="kN/m²",
                      height=300, margin=dict(t=40, b=20))
    return fig


def _linreg(xs: list, ys: list) -> tuple[float, float]:
    """Hồi quy tuyến tính đơn giản, trả về (a, b) với y = a*x + b."""
    n = len(xs)
    if n < 2:
        return 0.0, (ys[0] if ys else 0.0)
    sx  = sum(xs);  sy  = sum(ys)
    sxy = sum(xi*yi for xi, yi in zip(xs, ys))
    sxx = sum(xi**2 for xi in xs)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return 0.0, sy / n
    a = (n * sxy - sx * sy) / denom
    b = (sy - a * sx) / n
    return a, b


def _chart_su_profile_mpl(
    df_vst: pd.DataFrame,
    selected_locs: list[str] | None = None,
):
    """Matplotlib fallback cho biểu đồ Su–VST khi không có plotly."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 6))
    if df_vst.empty:
        ax.text(0.5, 0.5, "Không có dữ liệu VST", ha="center", va="center", transform=ax.transAxes)
        return fig

    all_locs  = sorted(df_vst["loc_name"].unique())
    show_locs = selected_locs if selected_locs else all_locs
    _colors = ["#E53935","#1565C0","#2E7D32","#F57F17","#6A1B9A",
               "#00838F","#AD1457","#558B2F","#4527A0","#00695C"]

    for i, loc in enumerate(all_locs):
        if loc not in show_locs:
            continue
        grp    = df_vst[df_vst["loc_name"] == loc].sort_values("depth_m")
        color  = _colors[i % len(_colors)]
        depths = grp["depth_m"].tolist()
        sus    = grp["Su_kPa"].tolist()
        y_plot = [-d for d in depths]
        ax.plot(sus, y_plot, "-o", color=color, lw=1.5, ms=5, label=loc)
        for x, y in zip(sus, y_plot):
            ax.annotate(f"{x:.1f}", (x, y), xytext=(4, 0), textcoords="offset points",
                        fontsize=7, color=color, va="center")
        if len(depths) >= 2:
            a, b = _linreg(depths, sus)
            d_ext = (max(depths) - min(depths)) * 0.1
            dd = [min(depths) - d_ext, max(depths) + d_ext]
            ax.plot([a*d + b for d in dd], [-d for d in dd],
                    "--", color=color, lw=1.0, alpha=0.7)
            sign = "+" if b >= 0 else "−"
            eq = f"Su={a:+.2f}z{sign}{abs(b):.2f}".replace("+-", "−")
            ax.text(a*dd[-1] + b, -dd[-1], eq, fontsize=7, color=color,
                    bbox=dict(facecolor="white", alpha=0.75, edgecolor=color, lw=0.5, pad=1))

    ax.set_xlabel("Su (kPa)", fontsize=9)
    ax.set_ylabel("Cao độ (m)", fontsize=9)
    title = "Biểu đồ Su – Cắt cánh (VST)"
    title += f" — {', '.join(show_locs)}" if selected_locs else " — Toàn bộ"
    ax.set_title(title, fontsize=10)
    ax.grid(True, ls=":", color="#CCC", lw=0.5)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.85)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    return fig


def _draw_soil_column_mpl(
    layers: list[dict], bh_name: str = "",
    spt: list[dict] | None = None,
):
    """Matplotlib fallback cho cột địa chất + SPT."""
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    def _tc(hex_color: str) -> str:
        h = hex_color.lstrip("#")
        if len(h) < 6:
            return "#212121"
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return "white" if (0.299*r + 0.587*g + 0.114*b) < 140 else "#212121"

    def _spt_color(n: int) -> str:
        if n <= 2:   return "#E53935"
        if n <= 5:   return "#FB8C00"
        if n <= 10:  return "#FDD835"
        if n <= 30:  return "#66BB6A"
        return "#1565C0"

    has_spt = bool(spt)
    if not layers:
        fig, ax = plt.subplots(figsize=(4, 7))
        ax.text(0.5, 0.5, f"Không có địa tầng\n{bh_name}", ha="center", va="center",
                transform=ax.transAxes, fontsize=10, color="#666")
        ax.axis("off")
        return fig

    # VST figsize=(7,6) trong cột rộng 2/3 → displayed_h ≈ 0.571·W
    # Cột địa chất ở cột hẹp 1/3 cần aspect cao hơn để bù → h/w ≈ 12/7
    y_bot = layers[-1]["depth_bot_m"]
    if has_spt:
        fig, (ax_col, ax_spt) = plt.subplots(
            1, 2, figsize=(7, 12), sharey=True,
            gridspec_kw={"width_ratios": [0.4, 0.6], "wspace": 0.05},
        )
    else:
        fig, ax_col = plt.subplots(figsize=(4, 7))
        ax_spt = None

    _fs_lbl  = 14 if has_spt else 8
    _fs_sym  = 16 if has_spt else 9
    _fs_axis = 16 if has_spt else 9
    _fs_tick = 14 if has_spt else 8
    _fs_ttl  = 18 if has_spt else 10
    for lay in layers:
        y0, y1 = lay["depth_top_m"], lay["depth_bot_m"]
        sym   = (lay.get("symbol") or "").strip()
        color = _LAYER_COLORS.get(
            sym, _LAYER_COLORS.get(sym[:2] if len(sym) > 2 else sym, _LAYER_DEFAULT_COLOR))
        ax_col.add_patch(mpatches.Rectangle(
            (0, y0), 1, y1 - y0, facecolor=color, edgecolor="#555", lw=0.6))
        ax_col.text(1.04, y0, f"{y0:.1f}", fontsize=_fs_lbl, color="#555", va="center")
        if (y1 - y0) >= 0.5:
            mid = (y0 + y1) / 2
            sym_lbl = sym if sym else f"L{layers.index(lay)+1}"
            desc = (lay.get("description") or "")[:18]
            lbl = f"{sym_lbl}\n{desc}" if (y1-y0) >= 2.5 and desc else sym_lbl
            ax_col.text(0.5, mid, lbl, fontsize=_fs_sym, color=_tc(color),
                        ha="center", va="center", fontweight="bold")
    ax_col.text(1.04, y_bot, f"{y_bot:.1f}", fontsize=_fs_lbl, color="#555", va="center")
    ax_col.set_xlim(-0.05, 1.5)
    ax_col.set_ylim(y_bot + 1, -0.5)
    ax_col.set_xticks([])
    ax_col.set_ylabel("Độ sâu (m)", fontsize=_fs_axis)
    ax_col.tick_params(labelsize=_fs_tick)
    ax_col.grid(True, axis="y", ls=":", color="#EEE", lw=0.5)
    ax_col.set_title("Địa chất" if has_spt else f"Cột ĐC: {bh_name}",
                     fontsize=_fs_ttl, color="#1F4E79")

    if has_spt and ax_spt is not None:
        _n_max = max((s["N"] or 0 for s in spt), default=10)
        _x_max = max(60, _n_max + 5)
        depths = [s["depth_m"] for s in spt]
        N_vals = [min(s["N"] or 0, 60) for s in spt]
        colors = [_spt_color(n) for n in N_vals]
        ax_spt.barh(depths, N_vals, height=0.6, color=colors, edgecolor="#444", lw=0.5)
        for d, n in zip(depths, N_vals):
            ax_spt.text(n + 1, d, str(n), fontsize=14, va="center")
        ax_spt.plot(N_vals, depths, ":", color="#333", lw=1)
        ax_spt.axvline(4, ls="--", color="#E53935", lw=1, alpha=0.6)
        ax_spt.text(4.2, -0.2, "N=4", fontsize=14, color="#E53935")
        ax_spt.set_xlim(0, _x_max)
        ax_spt.set_xlabel("N (blows/30cm)", fontsize=16)
        ax_spt.tick_params(labelsize=14)
        ax_spt.grid(True, axis="x", ls=":", color="#EEE", lw=0.5)
        ax_spt.set_title("SPT – N", fontsize=18, color="#1F4E79")
        fig.suptitle(f"Cột ĐC: {bh_name}", fontsize=18, color="#1F4E79", y=0.995)

    fig.tight_layout()
    return fig


def _chart_su_profile(
    df_vst: pd.DataFrame,
    selected_locs: list[str] | None = None,
) -> go.Figure:
    if df_vst.empty:
        return go.Figure()

    all_locs = sorted(df_vst["loc_name"].unique())
    show_locs = selected_locs if selected_locs else all_locs

    _colors = [
        "#E53935","#1565C0","#2E7D32","#F57F17","#6A1B9A",
        "#00838F","#AD1457","#558B2F","#4527A0","#00695C",
    ]

    fig = go.Figure()
    reg_lines = []   # (loc, a, b, color, y_min, y_max)

    for i, loc in enumerate(all_locs):
        if loc not in show_locs:
            continue
        grp   = df_vst[df_vst["loc_name"] == loc].sort_values("depth_m")
        color = _colors[i % len(_colors)]
        depths = grp["depth_m"].tolist()
        sus    = grp["Su_kPa"].tolist()
        y_plot = [-d for d in depths]

        # Đường + markers + nhãn giá trị
        fig.add_trace(go.Scatter(
            x=sus, y=y_plot,
            mode="lines+markers+text",
            name=loc,
            line=dict(color=color, width=1.8),
            marker=dict(size=7, color=color),
            text=[f"{v:.1f}" for v in sus],
            textposition="middle right",
            textfont=dict(size=9, color=color),
            hovertemplate=(
                f"<b>{loc}</b><br>"
                "Sâu: %{customdata:.1f} m<br>"
                "Su: %{x:.1f} kPa<extra></extra>"
            ),
            customdata=depths,
        ))

        # Hồi quy tuyến tính: Su = a*depth + b
        if len(depths) >= 2:
            a, b = _linreg(depths, sus)
            reg_lines.append((loc, a, b, color, min(depths), max(depths)))

    # Vẽ đường hồi quy + annotation phương trình
    for loc, a, b, color, d_min, d_max in reg_lines:
        d_ext = (d_max - d_min) * 0.1
        dd = [d_min - d_ext, d_max + d_ext]
        su_reg = [a * d + b for d in dd]
        sign  = "+" if b >= 0 else "−"
        eq    = f"Su={a:+.2f}z{sign}{abs(b):.2f}".replace("+-", "−")
        fig.add_trace(go.Scatter(
            x=su_reg, y=[-d for d in dd],
            mode="lines",
            name=f"Hồi quy {loc}",
            line=dict(color=color, width=1.2, dash="dash"),
            hovertemplate=f"<b>Hồi quy {loc}</b><br>{eq}<extra></extra>",
            showlegend=False,
        ))
        # Nhãn phương trình ở cuối đường
        fig.add_annotation(
            x=su_reg[-1], y=-dd[-1],
            text=eq,
            showarrow=False,
            font=dict(size=9, color=color),
            xanchor="left",
            bgcolor="rgba(255,255,255,0.75)",
            bordercolor=color,
            borderwidth=1,
        )

    fig.update_layout(
        title="Biểu đồ Su – Cắt cánh (VST)" + (
            f" — {', '.join(show_locs)}" if selected_locs else " — Toàn bộ"
        ),
        xaxis_title="Su (kPa)",
        yaxis_title="Cao độ (m)",
        height=500,
        legend=dict(font_size=10, orientation="v", x=1.01, y=1),
        margin=dict(t=50, b=20, r=160),
    )
    return fig


def _chart_combined(df: pd.DataFrame, rec_idx: int) -> go.Figure:
    x = [f"e={r['e (m)']}m" for _, r in df.iterrows()]
    colors = ["#ED7D31" if i == rec_idx else "#4472C4" for i in range(len(df))]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="a (%)", x=x, y=df["a (%)"],
                         marker_color=colors, yaxis="y1",
                         offsetgroup=0,
                         text=df["a (%)"].apply(lambda v: f"{v:.1f}%"),
                         textposition="outside"))
    fig.add_trace(go.Scatter(name="S₁ (cm)", x=x, y=df["S₁ (cm)"],
                              mode="lines+markers+text",
                              text=df["S₁ (cm)"].apply(lambda v: f"{v:.2f}"),
                              textposition="top center",
                              yaxis="y2", line=dict(color="#FF0000", width=2),
                              marker=dict(size=8, color="#FF0000")))
    fig.update_layout(
        title="Tổng hợp: tỷ lệ thay thế a(%) và độ lún S₁(cm)",
        yaxis=dict(title="a (%)", side="left"),
        yaxis2=dict(title="S₁ (cm)", side="right", overlaying="y"),
        barmode="group", height=340,
        legend=dict(orientation="h"), margin=dict(t=40, b=20),
    )
    return fig


def _draw_cdm_section(
    D: float, Lc: float, CDTK: float,
    h_clay: float, h_road: float, h_fill: float, h_mat: float,
    q_traffic: float,
    top_clay: float | None = None,
):
    """Mặt cắt ngang CDM: các lớp đất, trụ CDM, mũi tên tải, kích thước D/Lc."""
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    z_mat         = CDTK + h_mat
    z_fill        = z_mat + h_fill
    z_road        = z_fill + h_road
    _clay_top_eff = top_clay if top_clay is not None else CDTK
    z_clay_bot    = _clay_top_eff - h_clay
    z_pile_bot    = CDTK - Lc
    z_base        = min(z_clay_bot, z_pile_bot) - 1.5

    W  = max(4.0 * D, 2.5)
    cx = W / 2
    r  = D / 2

    fig, ax = plt.subplots(figsize=(5, 8))
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("white")
    ax.set_xlim(-W * 0.35, W * 1.2)
    ax.set_ylim(z_base, z_road + 2.5)
    ax.set_ylabel("Cao độ (m)", fontsize=9)
    ax.set_xticks([])
    ax.tick_params(axis="y", labelsize=8)
    ax.set_title("Mặt cắt ngang CDM", fontsize=11, fontweight="bold", pad=8)
    for s in ["top", "right", "bottom"]:
        ax.spines[s].set_visible(False)

    def hrect(y0, y1, fc, ec="#666", zo=1):
        if y1 > y0:
            ax.add_patch(mpatches.Rectangle(
                (0, y0), W, y1 - y0, fc=fc, ec=ec, lw=0.7, zorder=zo
            ))

    hrect(z_base,        z_clay_bot,    "#BCAAA4", "#795548")
    hrect(z_clay_bot,    _clay_top_eff, "#BBDEFB", "#1565C0")
    if top_clay is not None and top_clay < CDTK - 0.05:
        hrect(_clay_top_eff, CDTK,     "#FFD54F", "#E6BE00")
    if h_mat > 0:
        hrect(CDTK,      z_mat,        "#FFA726", "#E65100")
    hrect(z_mat,         z_fill,       "#FFD54F", "#E6BE00")
    hrect(z_fill,        z_road,       "#90A4AE", "#546E7A")

    p_bot = max(z_pile_bot, z_base + 0.1)
    ax.add_patch(mpatches.Rectangle(
        (cx - r, p_bot), D, CDTK - p_bot, fc="#66BB6A", ec="#2E7D32", lw=1.2, zorder=3
    ))
    p_mid = (CDTK + p_bot) / 2
    ax.text(cx, p_mid, f"CDM\nD={D:.2f}m\nLc={Lc:.1f}m",
            ha="center", va="center", fontsize=8.5,
            color="white", fontweight="bold", zorder=4)

    # Cao độ thiết kế = đỉnh lớp kết cấu áo đường (z_road)
    ax.axhline(z_road, color="#E53935", lw=1.5, ls="--", zorder=5)
    ax.text(W * 0.98, z_road + 0.08, f"Cao độ TK = {z_road:+.2f} m",
            ha="right", va="bottom", fontsize=8.5, color="#E53935",
            fontweight="bold", zorder=7,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#E53935",
                      alpha=0.9, lw=0.8))
    # Đỉnh cọc CDM (nét chấm xanh lá)
    ax.axhline(CDTK, color="#2E7D32", lw=0.9, ls=":", zorder=4, alpha=0.8)
    ax.text(W * 0.98, CDTK - 0.1, f"Đỉnh cọc = {CDTK:+.2f} m",
            ha="right", va="top", fontsize=7.5, color="#2E7D32", zorder=5,
            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))

    # Đỉnh lớp bùn (nét gạch nâu) — chỉ vẽ khi khác CDTK > 0.05 m
    if top_clay is not None and abs(top_clay - CDTK) > 0.05:
        ax.axhline(top_clay, color="#6D4C41", lw=1.2, ls="-.", zorder=4, alpha=0.85)
        _va = "bottom" if top_clay > CDTK else "top"
        _dy = 0.08 if top_clay > CDTK else -0.08
        ax.text(W * 0.02, top_clay + _dy,
                f"Đỉnh lớp bùn = {top_clay:+.2f} m",
                ha="left", va=_va, fontsize=7.5, color="#6D4C41", zorder=5,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#6D4C41",
                          alpha=0.9, lw=0.6))

    # Đáy lớp bùn (nét gạch nâu nhạt)
    ax.axhline(z_clay_bot, color="#6D4C41", lw=1.0, ls="-.", zorder=4, alpha=0.7)
    ax.text(W * 0.02, z_clay_bot - 0.08,
            f"Đáy lớp bùn = {z_clay_bot:+.2f} m",
            ha="left", va="top", fontsize=7.5, color="#6D4C41", zorder=5,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#6D4C41",
                      alpha=0.9, lw=0.6))

    # Đáy cọc CDM (nét chấm xanh lá)
    ax.axhline(z_pile_bot, color="#2E7D32", lw=0.9, ls=":", zorder=4, alpha=0.8)
    ax.text(W * 0.98, z_pile_bot - 0.08,
            f"Đáy cọc = {z_pile_bot:+.2f} m",
            ha="right", va="top", fontsize=7.5, color="#2E7D32", zorder=5,
            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))

    # Kích thước phần cọc ngàm vào đất tốt (bên trái cọc)
    _emb = z_clay_bot - z_pile_bot
    if _emb > 0.05:
        dim_x_l = cx - r - W * 0.07
        ax.annotate("", xy=(dim_x_l, z_pile_bot), xytext=(dim_x_l, z_clay_bot),
                    arrowprops=dict(arrowstyle="<->", color="#D84315", lw=1.4),
                    zorder=5)
        ax.text(dim_x_l - W * 0.015, (z_pile_bot + z_clay_bot) / 2,
                f"Ngàm\n={_emb:.2f}m",
                ha="right", va="center", fontsize=7.5, color="#D84315",
                fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#D84315",
                          alpha=0.9, lw=0.6))

    def layer_text(y0, y1, txt, color):
        if (y1 - y0) > 0.4:
            ax.text(W * 0.03, (y0 + y1) / 2, txt,
                    ha="left", va="center", fontsize=8, color=color, zorder=6)

    layer_text(z_base,        z_clay_bot,    "Đất tốt",                       "#5D4037")
    layer_text(z_clay_bot,    _clay_top_eff, f"Bùn sét  h={h_clay:.1f}m",     "#0D47A1")
    if top_clay is not None and top_clay < CDTK - 0.05:
        _h_fill_below = CDTK - top_clay
        layer_text(_clay_top_eff, CDTK,     f"Cát đắp  h={_h_fill_below:.1f}m", "#827717")
    if h_mat > 0:
        layer_text(CDTK,      z_mat,        f"Đệm cát  h={h_mat:.1f}m",       "#E65100")
    layer_text(z_mat,         z_fill,       f"Cát đắp  h={h_fill:.1f}m",       "#827717")
    layer_text(z_fill,        z_road,       f"Mặt đường h={h_road:.1f}m",      "#37474F")

    dim_yD = (CDTK + z_mat) / 2 if h_mat > 0.2 else CDTK + 0.25
    ax.annotate("", xy=(cx + r, dim_yD), xytext=(cx - r, dim_yD),
                arrowprops=dict(arrowstyle="<->", color="#2E7D32", lw=1.5), zorder=5)
    ax.text(cx, dim_yD + 0.12, f"D={D:.2f}m",
            ha="center", va="bottom", fontsize=8, color="#2E7D32", zorder=5,
            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))

    dim_x = cx + r + W * 0.07
    ax.annotate("", xy=(dim_x, p_bot), xytext=(dim_x, CDTK),
                arrowprops=dict(arrowstyle="<->", color="#1A237E", lw=1.5), zorder=5)
    ax.text(dim_x + W * 0.02, p_mid, f"Lc={Lc:.1f}m",
            ha="left", va="center", fontsize=8, color="#1A237E", zorder=5)

    q_top = z_road + 1.0
    for xi in [W * 0.25, W * 0.5, W * 0.75]:
        ax.annotate("", xy=(xi, z_road), xytext=(xi, q_top),
                    arrowprops=dict(arrowstyle="-|>", color="#B71C1C", lw=1.8), zorder=6)
    ax.text(cx, q_top + 0.2, f"q = {q_traffic:.0f} kN/m²",
            ha="center", va="bottom", fontsize=10,
            color="#B71C1C", fontweight="bold", zorder=6)

    # He = h_fill (cát đắp, từ đỉnh đệm z_mat đến đỉnh lớp cát z_fill)
    _He = z_fill - z_mat
    if _He > 0.05:
        _dim_xH = -W * 0.18
        ax.annotate("", xy=(_dim_xH, z_mat), xytext=(_dim_xH, z_fill),
                    arrowprops=dict(arrowstyle="<->", color="#1565C0", lw=1.5), zorder=5)
        ax.text(_dim_xH - W * 0.03, (z_mat + z_fill) / 2,
                f"He\n={_He:.1f}m",
                ha="right", va="center", fontsize=8.5, color="#1565C0",
                fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#1565C0",
                          alpha=0.9, lw=0.8))
    # Hse = h_mat (đệm xi măng, từ CDTK đến z_mat)
    _Hse = z_mat - CDTK
    if _Hse > 0.05:
        _dim_xH2 = -W * 0.18
        ax.annotate("", xy=(_dim_xH2, CDTK), xytext=(_dim_xH2, z_mat),
                    arrowprops=dict(arrowstyle="<->", color="#E65100", lw=1.2), zorder=5)
        ax.text(_dim_xH2 - W * 0.03, (CDTK + z_mat) / 2,
                f"Hse\n={_Hse:.1f}m",
                ha="right", va="center", fontsize=7.5, color="#E65100",
                fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#E65100",
                          alpha=0.9, lw=0.7))

    plt.tight_layout(pad=0.5)
    return fig


def _draw_cdm_grid(D: float, arr: str, e_ref: float):
    """Sơ đồ bố trí lưới cọc CDM (plan view)."""
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    r = D / 2
    centers = []
    for ri in range(4):
        for ci in range(4):
            if arr == "triangle":
                px = ci * e_ref + (e_ref / 2 if ri % 2 else 0)
                py = ri * (e_ref * (3 ** 0.5) / 2)
            else:
                px = ci * e_ref
                py = ri * e_ref
            centers.append((px, py))

    all_px = [p[0] for p in centers]
    all_py = [p[1] for p in centers]
    pad = e_ref * 0.75

    fig, ax = plt.subplots(figsize=(5, 4.5))
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("#F0F4F8")
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    arr_lbl = "Tam giác" if arr == "triangle" else "Hình vuông"
    ax.set_title(f"Sơ đồ lưới {arr_lbl}  (e = {e_ref:.2f} m)",
                 fontsize=11, fontweight="bold", pad=8)
    for s in ax.spines.values():
        s.set_visible(False)

    if arr == "square":
        ax.add_patch(mpatches.Rectangle(
            (-e_ref / 2, -e_ref / 2), e_ref, e_ref,
            fc="#BBDEFB", ec="#1565C0", lw=1.5, ls="--", alpha=0.4, zorder=1
        ))
    else:
        e_h = e_ref * (3 ** 0.5) / 2
        ax.add_patch(mpatches.Polygon(
            [(0, 0), (e_ref, 0), (e_ref / 2, e_h)],
            closed=True, fc="#BBDEFB", ec="#1565C0", lw=1.5, ls="--", alpha=0.35, zorder=1
        ))

    for px, py in centers:
        ax.add_patch(mpatches.Circle(
            (px, py), r, fc="#A5D6A7", ec="#2E7D32", lw=1.2, zorder=3
        ))

    p0x, p0y = centers[0]
    p1x, _   = centers[1]
    d_y = p0y - r - 0.2
    ax.annotate("", xy=(p1x, d_y), xytext=(p0x, d_y),
                arrowprops=dict(arrowstyle="<->", color="#E53935", lw=1.5))
    ax.text((p0x + p1x) / 2, d_y - 0.12, f"e = {e_ref:.2f} m",
            ha="center", va="top", fontsize=8.5, color="#E53935")

    a_val = calc_a(D, e_ref, arr)
    ax.text((min(all_px) + max(all_px)) / 2, max(all_py) + r + 0.3,
            f"a = {a_val * 100:.1f}%",
            ha="center", va="bottom", fontsize=11, color="#1A237E", fontweight="bold")

    ax.set_xlim(min(all_px) - pad, max(all_px) + pad)
    ax.set_ylim(min(all_py) - pad * 1.8, max(all_py) + pad * 0.8)
    plt.tight_layout(pad=0.5)
    return fig


def _draw_soil_column(
    layers: list[dict], bh_name: str = "",
    spt: list[dict] | None = None,
) -> go.Figure:
    """Cột địa chất + biểu đồ SPT (subplot 2 cột, trục Y dùng chung)."""
    try:
        from plotly.subplots import make_subplots
    except ImportError:
        make_subplots = None

    has_spt = bool(spt) and make_subplots is not None

    if not layers:
        fig = go.Figure()
        fig.update_layout(height=500,
                          title=dict(text=f"Cột ĐC: {bh_name}", font=dict(size=10), x=0.5))
        return fig

    def _tc(hex_color: str) -> str:
        h = hex_color.lstrip("#")
        if len(h) < 6:
            return "#212121"
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return "white" if (0.299 * r + 0.587 * g + 0.114 * b) < 140 else "#212121"

    def _spt_color(n: int) -> str:
        if n <= 2:   return "#E53935"   # đất rất yếu
        if n <= 5:   return "#FB8C00"   # yếu
        if n <= 10:  return "#FDD835"   # trung bình yếu
        if n <= 30:  return "#66BB6A"   # trung bình
        return "#1565C0"                 # chặt / cứng

    y_bot = layers[-1]["depth_bot_m"]

    if has_spt:
        fig = make_subplots(
            rows=1, cols=2,
            shared_yaxes=True,
            column_widths=[0.35, 0.65],
            horizontal_spacing=0.04,
            subplot_titles=["Địa chất", "SPT – N"],
        )
    else:
        fig = go.Figure()

    # ── Soil column (col 1) ──────────────────────────────────────────────────
    shapes: list[dict] = []
    annotations: list[dict] = []
    seen: set[float] = set()

    xref_col = "x" if has_spt else "x"
    yref_col = "y"

    for lay in layers:
        y0    = lay["depth_top_m"]
        y1    = lay["depth_bot_m"]
        sym   = (lay.get("symbol") or "").strip()
        color = _LAYER_COLORS.get(sym,
                _LAYER_COLORS.get(sym[:2] if len(sym) > 2 else sym,
                _LAYER_DEFAULT_COLOR))
        thick = y1 - y0

        shapes.append(dict(
            type="rect", x0=0, y0=y0, x1=1, y1=y1,
            xref=xref_col, yref=yref_col,
            fillcolor=color, line=dict(color="#555", width=0.6),
        ))

        if y0 not in seen:
            annotations.append(dict(
                x=1.08 if not has_spt else 1.12, y=y0,
                xref=xref_col, yref=yref_col,
                text=f"{y0:.1f}",
                showarrow=False, font=dict(size=8, color="#555"),
                xanchor="left", yanchor="middle",
            ))
            seen.add(y0)

        if thick >= 0.5:
            mid = (y0 + y1) / 2
            tc  = _tc(color)
            desc = (lay.get("description") or "")
            sym_lbl = sym if sym else f"L{layers.index(lay)+1}"
            lbl  = (f"<b>{sym_lbl}</b><br>{desc[:18]}"
                    if thick >= 2.5 and desc else f"<b>{sym_lbl}</b>")
            annotations.append(dict(
                x=0.5, y=mid,
                xref=xref_col, yref=yref_col,
                text=lbl,
                showarrow=False, font=dict(size=9, color=tc),
                xanchor="center", yanchor="middle",
            ))

    if y_bot not in seen:
        annotations.append(dict(
            x=1.08 if not has_spt else 1.12, y=y_bot,
            xref=xref_col, yref=yref_col,
            text=f"{y_bot:.1f}",
            showarrow=False, font=dict(size=8, color="#555"),
            xanchor="left", yanchor="middle",
        ))

    # Dummy trace để giữ trục y
    if has_spt:
        fig.add_trace(go.Scatter(
            x=[0.5], y=[y_bot / 2],
            mode="markers", marker=dict(opacity=0, size=1),
            showlegend=False,
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=[0.5], y=[y_bot / 2],
            mode="markers", marker=dict(opacity=0, size=1),
            showlegend=False,
        ))

    # ── SPT chart (col 2) ────────────────────────────────────────────────────
    if has_spt:
        _n_max = max((s["N"] or 0 for s in spt), default=10)
        _x_max = max(60, _n_max + 5)

        _depths = [s["depth_m"] for s in spt]
        _N_vals = [min(s["N"] or 0, 60) for s in spt]
        _colors = [_spt_color(n) for n in _N_vals]
        _labels = [
            f"N={s['N']}  ({s['N1']}/{s['N2']}/{'–' if s['N3'] is None else s['N3']})"
            for s in spt
        ]

        # Thanh ngang N
        fig.add_trace(go.Bar(
            x=_N_vals, y=_depths,
            orientation="h",
            marker_color=_colors,
            marker_line=dict(color="#444", width=0.5),
            text=[str(n) for n in _N_vals],
            textposition="outside",
            textfont=dict(size=13),
            customdata=_labels,
            hovertemplate="%{customdata}<extra></extra>",
            showlegend=False,
            width=1.2,
        ), row=1, col=2)

        # Đường nối N theo chiều sâu
        fig.add_trace(go.Scatter(
            x=_N_vals, y=_depths,
            mode="lines",
            line=dict(color="#333", width=1, dash="dot"),
            showlegend=False,
            hoverinfo="skip",
        ), row=1, col=2)

        # Đường giới hạn N=4 (đất rất yếu)
        fig.add_vline(x=4, line_dash="dash", line_color="#E53935",
                      line_width=1, opacity=0.6,
                      annotation_text="N=4", annotation_font_size=8,
                      annotation_position="top right", row=1, col=2)

        fig.update_xaxes(
            title_text="N (blows/30cm)", title_font=dict(size=14),
            range=[0, _x_max], tickfont=dict(size=12),
            showgrid=True, gridcolor="#EEE",
            row=1, col=2,
        )

    # ── Layout ───────────────────────────────────────────────────────────────
    y_range  = [y_bot + 1, -0.5]
    _yfs_t = 14 if has_spt else 9
    _yfs_k = 12 if has_spt else 8
    y_axis   = dict(
        range=y_range,
        title="Độ sâu (m)", title_font=dict(size=_yfs_t),
        tickfont=dict(size=_yfs_k),
        showgrid=True, gridcolor="#EEE", gridwidth=0.5,
        dtick=5,
    )

    if has_spt:
        fig.update_yaxes(y_axis, row=1, col=1)
        fig.update_xaxes(
            showticklabels=False, showgrid=False, zeroline=False,
            range=[-0.05, 1.6], row=1, col=1,
        )
        fig.update_layout(
            shapes=shapes,
            annotations=annotations,
            title=dict(text=f"Cột ĐC: {bh_name}", font=dict(size=10, color="#1F4E79"), x=0.5),
            height=500,
            margin=dict(l=10, r=20, t=55, b=20),
            plot_bgcolor="white",
            paper_bgcolor="#FAFAFA",
            showlegend=False,
            bargap=0,
        )
    else:
        fig.update_layout(
            shapes=shapes,
            annotations=annotations,
            title=dict(text=f"Cột ĐC: {bh_name}", font=dict(size=10, color="#1F4E79"), x=0.5),
            height=500,
            margin=dict(l=10, r=55, t=35, b=20),
            xaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[-0.05, 1.7]),
            yaxis=y_axis,
            plot_bgcolor="white",
            paper_bgcolor="#FAFAFA",
            showlegend=False,
        )

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _export_excel(scenarios: list[dict], params: dict) -> bytes:
    """Xuất Excel 3 sheet: Đầu vào | So sánh PA | Kết quả."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.chart import BarChart, Reference
    except ImportError:
        return b""

    wb = openpyxl.Workbook()

    # --- Helpers style ---
    HDR_FILL = PatternFill("solid", fgColor="1F4E79")
    REC_FILL = PatternFill("solid", fgColor="E2EFDA")
    HDR_FONT = Font(bold=True, color="FFFFFF", size=10)
    BD = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    def _hdr(ws, row, col, val, fill=HDR_FILL, font=HDR_FONT):
        c = ws.cell(row=row, column=col, value=val)
        c.fill = fill; c.font = font; c.border = BD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        return c

    def _val(ws, row, col, val, rec=False, fmt=None):
        c = ws.cell(row=row, column=col, value=val)
        if rec: c.fill = REC_FILL
        c.border = BD
        c.alignment = Alignment(horizontal="center", vertical="center")
        if fmt: c.number_format = fmt
        return c

    # ── Sheet 1: Đầu vào ──────────────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Đầu vào"
    ws1.column_dimensions["A"].width = 36
    ws1.column_dimensions["B"].width = 20
    ws1.column_dimensions["C"].width = 16

    title_rows = [
        ("THÔNG SỐ ĐỊA KỸ THUẬT VÀ THIẾT KẾ CDM",),
        (f"Hố khoan: {params.get('bh_name','–')}   |   Zone: {params.get('zone','–')}",),
    ]
    for i, (txt,) in enumerate(title_rows, 1):
        c = ws1.cell(row=i, column=1, value=txt)
        c.font = Font(bold=True, size=11)
        ws1.merge_cells(start_row=i, start_column=1, end_row=i, end_column=3)

    _hdr(ws1, 4, 1, "Thông số"); _hdr(ws1, 4, 2, "Ký hiệu"); _hdr(ws1, 4, 3, "Giá trị")
    geo_rows = [
        ("Hố khoan tham chiếu", "HK", params.get("bh_name","–")),
        ("Bề dày lớp bùn sét", "h₁ (m)", params.get("h_clay", 0)),
        ("Sức kháng cắt VST trung bình", "Su (kN/m²)", params.get("Su", 0)),
        ("Dung trọng tự nhiên TB", "γ (kN/m³)", params.get("gamma", 0)),
        ("Đường kính trụ CDM", "D (mm)", int(params.get("D", 0.8)*1000)),
        ("Chiều dài trụ CDM", "Lc (m)", params.get("Lc", 0)),
        ("Cao độ đỉnh cọc CDM", "Đỉnh cọc (m)", params.get("CDTK", 2.7)),
        ("Bố trí", "–", "Tam giác" if params.get("arrangement","triangle")=="triangle" else "Vuông"),
        ("Cường độ TK hiện trường", "qu,tk (kPa)", params.get("qu", 800)),
        ("Hệ số quy đổi TN→HT", "FS", params.get("FS_lab", 2.0)),
        ("Cc = qu,tk/2", "Cc (kN/m²)", params.get("qu", 800)/2),
        ("Ec = 100·Cc", "Ec (kN/m²)", int(100*params.get("qu",800)/2)),
        ("Es = 250·Su", "Es (kN/m²)", int(250*params.get("Su",11.2))),
        ("Tổng tải trọng gây lún", "q (kN/m²)", params.get("q_total", 75.2)),
    ]
    for r, (n, k, v) in enumerate(geo_rows, 5):
        ws1.cell(row=r, column=1, value=n).border = BD
        ws1.cell(row=r, column=2, value=k).border = BD
        c = ws1.cell(row=r, column=3, value=v); c.border = BD
        c.alignment = Alignment(horizontal="center")

    # ── Sheet 2: So sánh PA ───────────────────────────────────────────────────
    ws2 = wb.create_sheet("So sánh PA")
    hdrs = ["PA", "e (m)", "a", "a (%)", "Ec (kN/m²)", "Es (kN/m²)",
            "Etb (kN/m²)", "S₁ (cm)", "Pcol (kN)", "Qa (kN)", "Đạt SCT"]
    for j, h in enumerate(hdrs, 1):
        _hdr(ws2, 2, j, h)
        ws2.column_dimensions[chr(64+j)].width = 13
    rec_idx = params.get("rec_idx", 0)
    for i, s in enumerate(scenarios):
        is_rec = (i == rec_idx)
        _val(ws2, i+3, 1, f"PA{i+1}", is_rec)
        _val(ws2, i+3, 2, s["e (m)"], is_rec)
        _val(ws2, i+3, 3, s["a"], is_rec, "0.0000")
        _val(ws2, i+3, 4, s["a (%)"], is_rec)
        _val(ws2, i+3, 5, s["Ec (kN/m²)"], is_rec, "#,##0")
        _val(ws2, i+3, 6, s["Es (kN/m²)"], is_rec, "#,##0")
        _val(ws2, i+3, 7, s["Etb (kN/m²)"], is_rec, "#,##0")
        _val(ws2, i+3, 8, s["S₁ (cm)"], is_rec, "0.00")
        _val(ws2, i+3, 9, s["Pcol (kN)"], is_rec, "0.0")
        _val(ws2, i+3, 10, s["Qa (kN)"], is_rec, "0.0")
        _val(ws2, i+3, 11, s["Đạt SCT"], is_rec)

    # Biểu đồ S1
    chart = BarChart()
    chart.title = "Độ lún S₁ theo khoảng cách trụ"
    chart.y_axis.title = "S₁ (cm)"
    chart.x_axis.title = "Khoảng cách e (m)"
    data_ref  = Reference(ws2, min_col=8, min_row=2, max_row=2+len(scenarios))
    cats_ref  = Reference(ws2, min_col=2, min_row=3, max_row=2+len(scenarios))
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    chart.shape = 4; chart.width = 14; chart.height = 10
    ws2.add_chart(chart, f"M2")

    # ── Sheet 3: Kết quả chi tiết PA kiến nghị ────────────────────────────────
    ws3 = wb.create_sheet("Kết quả PA KN")
    if scenarios and 0 <= rec_idx < len(scenarios):
        s = scenarios[rec_idx]
        ws3.column_dimensions["A"].width = 36
        ws3.column_dimensions["B"].width = 22
        ws3.column_dimensions["C"].width = 18
        c = ws3.cell(row=1, column=1,
                     value=f"TÍNH TOÁN CHI TIẾT – PA{rec_idx+1}: e = {s['e (m)']} m")
        c.font = Font(bold=True, size=12)
        ws3.merge_cells("A1:C1")

        _hdr(ws3, 2, 1, "Thông số"); _hdr(ws3, 2, 2, "Công thức"); _hdr(ws3, 2, 3, "Giá trị")
        detail_rows = [
            ("Khoảng cách bố trí", "e", f"{s['e (m)']} m"),
            ("Tỷ lệ thay thế", "a = π·D²/(2√3·e²)" if params.get("arrangement","triangle")=="triangle"
             else "a = π·D²/(4·e²)", f"{s['a']:.4f}  ({s['a (%)']:.1f}%)"),
            ("Mô đun trụ CDM", "Ec = 100·Cc", f"{s['Ec (kN/m²)']:,} kN/m²"),
            ("Mô đun đất nền", "Es = 250·Su", f"{s['Es (kN/m²)']:,} kN/m²"),
            ("Mô đun tương đương", "Etb = a·Ec+(1-a)·Es", f"{int(s['Etb (kN/m²)']):,} kN/m²"),
            ("Tải trọng thiết kế", "q", f"{params.get('q_total',0):.1f} kN/m²"),
            ("Chiều dài trụ", "Lc", f"{params.get('Lc',0):.1f} m"),
            ("Độ lún S₁", "q·Lc/Etb×100", f"{s['S₁ (cm)']:.2f} cm"),
            ("Ứng suất đầu cọc", "σ_col = Ec/Etb·q", f"{s['σ_col (kN/m²)']:.1f} kN/m²"),
            ("Lực nén lên trụ", "Pcol = σ_col·Ac", f"{s['Pcol (kN)']:.1f} kN"),
            ("Sức chịu tải cho phép", "Qa (AIT, FS=2)", f"{s['Qa (kN)']:.1f} kN"),
            ("Kết luận SCT", "Pcol < Qa ?", s["Đạt SCT"]),
        ]
        for r, (n, f, v) in enumerate(detail_rows, 3):
            ws3.cell(row=r, column=1, value=n).border = BD
            ws3.cell(row=r, column=2, value=f).border = BD
            c = ws3.cell(row=r, column=3, value=v); c.border = BD
            c.alignment = Alignment(horizontal="center")
            if v in ("Đạt", "Không đạt"):
                c.font = Font(color="375623" if v == "Đạt" else "C00000", bold=True)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _export_word_bytes(
    scenarios: list[dict],
    params: dict,
    rec_idx: int,
    co_name: str = "",
    co_staff: str = "",
    logo_bytes: bytes | None = None,
) -> bytes:
    """Tạo Word thuyết minh CDM và trả về bytes."""
    sys.path.insert(0, str(_CDM_SC))
    try:
        import docx_helpers as H
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn as _qn
        from docx.oxml import OxmlElement as _Oxm
        from docx.shared import Cm as _Cm
        import math as _m
    except ImportError as e:
        return b""

    H.reset_counters()
    doc = Document()
    H.setup_page(doc)

    # ── Header / Footer ───────────────────────────────────────────────────────
    def _field_run(para, field: str) -> None:
        """Chèn Word field (PAGE / NUMPAGES) vào paragraph."""
        run = para.add_run()
        fc_b = _Oxm("w:fldChar"); fc_b.set(_qn("w:fldCharType"), "begin")
        instr = _Oxm("w:instrText"); instr.text = field
        instr.set(_qn("xml:space"), "preserve")
        fc_e = _Oxm("w:fldChar"); fc_e.set(_qn("w:fldCharType"), "end")
        run._r.append(fc_b); run._r.append(instr); run._r.append(fc_e)

    def _no_tbl_border(tbl) -> None:
        tblPr = tbl._tbl.tblPr
        borders = _Oxm("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            b = _Oxm(f"w:{edge}"); b.set(_qn("w:val"), "none"); borders.append(b)
        tblPr.append(borders)

    sec = doc.sections[0]
    _pw = sec.page_width - sec.left_margin - sec.right_margin  # usable width (EMU)

    # Header: logo (trái) | tên công ty (phải)
    sec.header.is_linked_to_previous = False
    _ht = sec.header.add_table(1, 2, width=_pw)
    _no_tbl_border(_ht)
    _ht.cell(0, 0).width = _Cm(3)
    _ht.cell(0, 1).width = _pw - _Cm(3)
    _logo_p = _ht.cell(0, 0).paragraphs[0]
    if logo_bytes:
        try:
            _logo_p.add_run().add_picture(io.BytesIO(logo_bytes), height=_Cm(1.2))
        except Exception:
            pass
    _name_p = _ht.cell(0, 1).paragraphs[0]
    _name_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    H._fmt(_name_p.add_run(co_name), size=9, bold=True)

    # Footer: nhân sự (trái) | Trang X/Y (phải)
    sec.footer.is_linked_to_previous = False
    _ft = sec.footer.add_table(1, 2, width=_pw)
    _no_tbl_border(_ft)
    _ft.cell(0, 0).width = _pw - _Cm(3)
    _ft.cell(0, 1).width = _Cm(3)
    H._fmt(_ft.cell(0, 0).paragraphs[0].add_run(co_staff), size=9)
    _pg_p = _ft.cell(0, 1).paragraphs[0]
    _pg_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    H._fmt(_pg_p.add_run("Trang "), size=9)
    _field_run(_pg_p, "PAGE")
    H._fmt(_pg_p.add_run(" / "), size=9)
    _field_run(_pg_p, "NUMPAGES")

    D    = params["D"]
    Lc   = params["Lc"]
    qu   = params["qu"]
    Cu   = params["Su"]
    q    = params["q_total"]
    Cc   = qu / 2
    Ec   = 100 * Cc
    Es   = 250 * Cu
    arr  = "tam giác" if params.get("arrangement", "triangle") == "triangle" else "hình vuông"
    rec  = scenarios[rec_idx] if scenarios else {}

    # Trang bìa
    for _ in range(4): doc.add_paragraph()
    H.heading(doc, "THUYẾT MINH TÍNH TOÁN",
              size=16, bold=True, center=True, space_before=0)
    H.heading(doc, "GIA CỐ NỀN ĐẤT YẾU BẰNG CỌC ĐẤT XI MĂNG (CDM)",
              size=15, bold=True, center=True, space_before=4)
    for _ in range(2): doc.add_paragraph()
    H.heading(doc,
              f"D = {int(D*1000)} mm – e = {' / '.join(str(s['e (m)']) for s in scenarios)} m"
              f" – Lc = {Lc:.1f} m – qu = {int(qu)} kPa",
              size=13, bold=False, center=True, space_before=0)
    for _ in range(5): doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    H._fmt(p.add_run("TP. Hồ Chí Minh, tháng 5 năm 2026"), size=12)
    doc.add_page_break()

    H.add_toc(doc)

    # I. Cơ sở pháp lý
    H.heading(doc, "I. CƠ SỞ PHÁP LÝ VÀ TIÊU CHUẨN ÁP DỤNG", size=13)
    for item in [
        "– TCVN 9403:2012 – Gia cố nền đất yếu – Phương pháp trụ đất xi măng;",
        "– TCVN 4200:2012 – Đất xây dựng – Phương pháp xác định tính nén lún;",
        "– TCVN 8868:2011 – Thí nghiệm xác định sức kháng cắt không cố kết – không thoát nước;",
        f"– Kết quả khảo sát địa kỹ thuật (hố khoan {params.get('bh_name','HK1')});",
        "– Kết quả thí nghiệm thành phần cấp phối xi măng đất.",
    ]:
        H.body(doc, item, indent=0.5)

    # II. Địa chất
    H.heading(doc, "II. ĐẶC ĐIỂM ĐỊA CHẤT KHU VỰC", size=13)
    H.body(doc, f"Căn cứ kết quả khảo sát hố khoan {params.get('bh_name','–')}, "
           f"zone {params.get('zone','–')}:")
    H.tbl_caption(doc, f"Thông số địa kỹ thuật – {params.get('bh_name','–')}")
    H.make_table(doc,
        headers=["Thông số", "Ký hiệu", "Giá trị"],
        rows=[
            ("Bề dày lớp bùn sét (lớp cần gia cố)", "h₁ (m)", f"{params.get('h_clay',0):.2f}"),
            ("Sức kháng cắt không thoát nước (VST)", "Su (kN/m²)", f"{Cu:.2f}"),
            ("Dung trọng tự nhiên trung bình", "γ (kN/m³)", f"{params.get('gamma',15):.2f}"),
            ("Mô đun biến dạng đất nền", "Es = 250·Su (kN/m²)", f"{int(Es):,}"),
        ])

    # III. Thông số thiết kế
    H.heading(doc, "III. THÔNG SỐ THIẾT KẾ CỌC ĐẤT XI MĂNG", size=13)
    H.tbl_caption(doc, "Thông số hình học và vật liệu trụ CDM")
    H.make_table(doc,
        headers=["Thông số", "Ký hiệu", "Giá trị"],
        rows=[
            ("Đường kính trụ CDM",              "D",          f"{int(D*1000)} mm"),
            (f"Khoảng cách tâm-tâm (lưới {arr})", "e",        " / ".join(f"{s['e (m)']}m" for s in scenarios)),
            ("Chiều dài trụ CDM",               "Lc",         f"{Lc:.1f} m"),
            ("Hàm lượng xi măng",               "x",          f"{params.get('dosage',240)} kg/m³"),
            ("Cường độ nén TK hiện trường",      "qu,tk",      f"{int(qu)} kPa"),
            ("Cường độ kháng cắt thiết kế",      "Cc = qu/2",  f"{int(Cc)} kN/m²"),
            ("Mô đun đàn hồi trụ",              "Ec = 100·Cc", f"{int(Ec):,} kN/m²"),
            ("Tổng tải trọng gây lún",           "q",          f"{q:.1f} kN/m²"),
        ])

    # IV. Phương pháp tính
    H.heading(doc, "IV. PHƯƠNG PHÁP TÍNH TOÁN LÚN (TCVN 9403:2012 – Phụ lục C)", size=13)
    H.body(doc, "Độ lún bản thân khối CDM:")
    H.formula(doc, "S₁ = q × H / Etb    (C.2)")
    H.formula(doc, "Etb = a × Ec + (1 − a) × Es")
    form = ("a = π × D² / (2√3 × e²)  [lưới tam giác]"
            if params.get("arrangement","triangle")=="triangle"
            else "a = π × D² / (4 × e²)  [lưới vuông]")
    H.formula(doc, form)
    H.body(doc, "S₂ = 0 (trụ CDM xuyên qua toàn bộ lớp bùn sét yếu).")

    # V. So sánh phương án
    H.heading(doc, "V. SO SÁNH CÁC PHƯƠNG ÁN KHOẢNG CÁCH TRỤ", size=13)
    H.tbl_caption(doc, f"So sánh S₁ theo khoảng cách trụ (D={int(D*1000)}mm, qu={int(qu)}kPa, q={q:.1f}kN/m²)")
    H.make_table(doc,
        headers=["PA", "e (m)", "a", "Etb (kN/m²)", "S₁ (cm)", "Đạt SCT"],
        rows=[(f"PA{i+1}", str(s["e (m)"]), f"{s['a']:.4f}",
               f"{int(s['Etb (kN/m²)']):,}", f"{s['S₁ (cm)']:.2f}", s["Đạt SCT"])
              for i, s in enumerate(scenarios)],
        highlight_rows={rec_idx})

    # VI. Kết quả PA kiến nghị
    if rec:
        H.heading(doc,
                  f"VI. KẾT QUẢ – PHƯƠNG ÁN KIẾN NGHỊ (e = {rec['e (m)']} m)", size=13)
        for line in [
            f"Tỷ lệ thay thế: a = {rec['a']:.4f}  ({rec['a (%)']:.1f}%)",
            f"Mô đun tương đương: Etb = {int(rec['Etb (kN/m²)']):,} kN/m²",
            f"Độ lún: S₁ = {rec['S₁ (cm)']:.2f} cm  ;  S₂ = 0  →  S = {rec['S₁ (cm)']:.2f} cm",
            f"Sức chịu tải: Pcol = {rec['Pcol (kN)']:.1f} kN  <  Qa = {rec['Qa (kN)']:.1f} kN  →  {rec['Đạt SCT']}",
        ]:
            H.body(doc, line, indent=0.3)

    # VII. Kiểm tra chọc thủng lớp đệm xi măng
    _ld_w   = params.get("loads", {})
    _pr_w   = calc_punching_check(
        D=D, e=rec.get("e (m)", 1.8) if rec else 1.8,
        Hse=_ld_w.get("h_mat", 0.4),
        He=_ld_w.get("h_fill", 1.5),
        quckse=params.get("quckse", 600.0),
        Fs=params.get("Fs_mat", 3.0),
        theta_deg=params.get("theta", 80.0),
        gamma_fill=_ld_w.get("g_fill", 18.0),
        gamma_mat=_ld_w.get("g_mat", 22.5),
        qa=params.get("qa_mat", 0.0),
    )
    H.heading(doc, "VII. KIỂM TRA CHỌC THỦNG LỚP ĐỆM XI MĂNG", size=13)
    H.body(doc, "Phương pháp: ALiCC (PWRI Japan). Điều kiện: τse ≤ τase.")
    H.tbl_caption(doc, "Kết quả kiểm tra chọc thủng lớp đệm xi măng")
    H.make_table(doc,
        headers=["Thông số", "Công thức", "Giá trị"],
        rows=[
            ("Bề dày đệm xi măng Hse",     "—",                              f"{_ld_w.get('h_mat',0.4):.2f} m"),
            ("Ứng suất cắt cho phép",       "τase = quckse/(2·Fs)",           f"{_pr_w['tase_kPa']:.2f} kPa"),
            ("Chiều cao vùng vòm Ho",       "Ho = (e−D)·tan(θ/2)",            f"{_pr_w['Ho_m']:.3f} m"),
            ("Công thức áp dụng",           "So sánh Ho và He",               _pr_w["cong_thuc"]),
            ("Áp lực vùng không gia cố",    "PSoil",                          f"{_pr_w['PSoil_kPa']:.3f} kPa"),
            ("Ứng suất cắt thực tế τse",    "τse = PSoil·A/(π·D·Hse)",        f"{_pr_w['tse_kPa']:.3f} kPa"),
            ("Kết quả kiểm tra",            "τse ≤ τase ?",                   _pr_w["check_CT"]),
        ])

    # VIII. Biểu đồ so sánh phương án
    import matplotlib.pyplot as _plt
    from docx.shared import Inches as _In

    def _bar_to_buf(x_lbls, y_vals, title, y_lbl, hi_idx, ref_line=None):
        _fig, _ax = _plt.subplots(figsize=(8, 3))
        _cols = ["#ED7D31" if i == hi_idx else "#4472C4" for i in range(len(y_vals))]
        _bars = _ax.bar(x_lbls, y_vals, color=_cols)
        _ax.bar_label(_bars, fmt="%.2f", padding=3, fontsize=9)
        if ref_line is not None:
            _ax.axhline(ref_line, color="#E53935", ls="--", lw=1.2,
                        label=f"Giới hạn = {ref_line:.1f}")
            _ax.legend(fontsize=9)
        _ax.set_title(title, fontsize=11)
        _ax.set_ylabel(y_lbl, fontsize=9)
        _ax.tick_params(labelsize=9)
        for _sp in ["top", "right"]:
            _ax.spines[_sp].set_visible(False)
        _buf = io.BytesIO()
        _fig.tight_layout()
        _fig.savefig(_buf, format="png", dpi=150, bbox_inches="tight")
        _plt.close(_fig)
        _buf.seek(0)
        return _buf

    if scenarios:
        H.heading(doc, "VIII. BIỂU ĐỒ SO SÁNH PHƯƠNG ÁN", size=13)
        _xl = [f"e={s['e (m)']}m" for s in scenarios]

        doc.add_picture(
            _bar_to_buf(_xl, [s["S₁ (cm)"] for s in scenarios],
                        f"Độ lún S₁ (cm) – D={int(D*1000)}mm, qu={int(qu)}kPa",
                        "S₁ (cm)", rec_idx),
            width=_In(5.5))
        doc.add_paragraph()
        doc.add_picture(
            _bar_to_buf(_xl, [s["a (%)"] for s in scenarios],
                        "Tỷ lệ thay thế a (%)",
                        "a (%)", rec_idx),
            width=_In(5.5))
        doc.add_paragraph()

        _tse_list = []
        for _s in scenarios:
            _pr_s = calc_punching_check(
                D=D, e=_s["e (m)"],
                Hse=_ld_w.get("h_mat", 0.4),
                He=_ld_w.get("h_fill", 1.5),
                quckse=params.get("quckse", 600.0),
                Fs=params.get("Fs_mat", 3.0),
                theta_deg=params.get("theta", 80.0),
                gamma_fill=_ld_w.get("g_fill", 18.0),
                gamma_mat=_ld_w.get("g_mat", 22.5),
                qa=params.get("qa_mat", 0.0),
            )
            _tse_list.append(_pr_s["tse_kPa"])
        doc.add_picture(
            _bar_to_buf(_xl, _tse_list,
                        "Ứng suất cắt τse – kiểm tra chọc thủng",
                        "τse (kPa)", rec_idx,
                        ref_line=_pr_w["tase_kPa"]),
            width=_In(5.5))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT SAVE / LOAD
# ═══════════════════════════════════════════════════════════════════════════════
_SAVE_KEYS = ["cdm_zone","cdm_bh","cdm_top_clay","cdm_h_clay","cdm_Su","cdm_gamma","cdm_elevation",
              "cdm_D","cdm_e","cdm_L_ngam","cdm_Lc","cdm_CDTK","cdm_qu","cdm_FS_lab","cdm_arrangement",
              "cdm_cement_type","cdm_dosage","cdm_WC","cdm_spacings","cdm_rec_idx","cdm_loads",
              "cdm_quckse","cdm_Fs_mat","cdm_theta","cdm_qa_mat"]

def _project_to_json() -> bytes:
    return json.dumps({k: st.session_state.get(k) for k in _SAVE_KEYS},
                      ensure_ascii=False, indent=2).encode("utf-8")

def _project_from_dict(data: dict):
    for k, v in data.items():
        if k in _SAVE_KEYS:
            st.session_state[k] = v


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
st.sidebar.markdown("### CDM Design Tool")
st.sidebar.markdown(f"**{_t('app_sub')}**")
st.sidebar.divider()

# Language toggle
_lang_sel = st.sidebar.radio(
    _t("lang_lbl"), ["VN", "EN"],
    index=["VN", "EN"].index(_get("lang")),
    horizontal=True, key="_lang_radio",
)
if _lang_sel != _get("lang"):
    st.session_state["lang"] = _lang_sel
    st.rerun()

st.sidebar.divider()

# Save / Load
with st.sidebar.expander(_t("save_load"), expanded=False):
    st.download_button(_t("download"), _project_to_json(),
                       file_name="cdm_project.cdm", mime="application/json")
    _up = st.file_uploader(_t("upload"), type=["cdm"], key="cdm_upload")
    if _up:
        try:
            _project_from_dict(json.load(_up))
            st.success(_t("load_ok"))
            st.rerun()
        except Exception as e:
            st.error(f"{'Lỗi' if _get('lang')=='VN' else 'Error'}: {e}")

st.sidebar.divider()

if "_page" not in st.session_state:
    st.session_state["_page"] = "geology"

def _nav(label: str, pid: str, indent: bool = False) -> None:
    pfx = "    " if indent else ""
    if st.sidebar.button(pfx + label, key=f"_nav_{pid}",
                         use_container_width=True,
                         type="primary" if st.session_state.get("_page") == pid else "secondary"):
        st.session_state["_page"] = pid
        st.rerun()

_nav(_t("p_geology"),      "geology")
_nav(_t("p_sample_check"), "sample_check")
st.sidebar.markdown(f"**{_t('p_tkcs_cdm')}**")
_nav(_t("p_params"),    "params",     indent=True)
_nav(_t("p_compare"),   "compare",    indent=True)
_nav(_t("p_settlement"),"settlement", indent=True)
_nav(_t("p_export"),    "export",     indent=True)
_nav(_t("p_cdm_bvt"),   "cdm_bvt")
st.sidebar.markdown(f"**{_t('p_tkcs_sw')}**")
_nav(_t("p_ke_sw"),  "ke_sw",  indent=True)
_nav(_t("p_sw_bvt"), "sw_bvt")

_page = st.session_state.get("_page", "geology")

# Info sidebar dưới cùng
st.sidebar.divider()
_q_now = q_total(_get("cdm_loads"))
_Su    = _get("cdm_Su")
_Lc    = _get("cdm_Lc")
_qu    = _get("cdm_qu")
_rec   = _get("cdm_rec_idx")
_sps   = _get("cdm_spacings")
st.sidebar.caption(
    f"**Zone:** {_get('cdm_zone')}  \n"
    f"{_t('si_bh')} {_get('cdm_bh') or '–'}  \n"
    f"**q =** {_q_now:.1f} kN/m²  \n"
    f"**Su =** {_Su:.1f} kPa  \n"
    f"**Lc =** {_Lc:.1f} m  \n"
    f"**qu,tk =** {_qu:.0f} kPa"
)

# ── Print-friendly CSS (Ctrl+P → Save as PDF) ───────────────────────────────
# Streamlit dùng nhiều layer container có overflow/height ràng buộc → in 1 trang.
# Brute force: wildcard * override mọi container khi @media print.
st.markdown("""
<style>
@media print {
  /* Override TOÀN BỘ container — bắt buộc để content chảy nhiều trang */
  * {
    overflow: visible !important;
    overflow-x: visible !important;
    overflow-y: visible !important;
    max-height: none !important;
    height: auto !important;
    position: static !important;
    transform: none !important;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }
  html, body {
    width: 100% !important;
    min-height: 0 !important;
  }
  /* Ẩn UI chrome (sau wildcard để không bị override) */
  [data-testid="stSidebar"],
  [data-testid="stHeader"], header,
  [data-testid="stToolbar"], [data-testid="stDecoration"],
  [data-testid="stStatusWidget"], .stDeployButton,
  [data-testid="collapsedControl"], footer {
    display: none !important;
  }
  /* Container chính: full width, không padding thừa */
  .main .block-container,
  [data-testid="stMainBlockContainer"],
  [data-testid="stAppViewBlockContainer"] {
    max-width: 100% !important;
    width: 100% !important;
    padding: 0.4rem !important;
    margin: 0 !important;
  }
  /* Auto-mở expander khi in (hide summary, hiện content) */
  details[data-testid="stExpander"] > summary { display: none !important; }
  details[data-testid="stExpander"] > div,
  details[data-testid="stExpander"] {
    display: block !important;
    open: true !important;
  }
  details { display: block !important; }
  details > summary { display: none !important; }
  details > * { display: block !important; }
  /* Tránh ngắt giữa figure/table/expander */
  div[data-testid="stExpander"],
  .stPlotlyChart, .stImage, .stPyplot, .stDataFrame,
  table, figure {
    break-inside: avoid;
    page-break-inside: avoid;
  }
  /* iframe (Plotly): chỉ hiển thị tối đa 1 trang, không co dãn */
  iframe {
    max-width: 100% !important;
    width: 100% !important;
    page-break-inside: avoid;
  }
  body { font-size: 10pt; line-height: 1.3; color: #000 !important; }
  a { text-decoration: none !important; color: inherit !important; }
}
@page { size: A4; margin: 12mm 10mm; }
</style>
""", unsafe_allow_html=True)

# JS auto-mở expander trước khi in — qua components.v1.html (iframe same-origin)
# vì st.markdown bị sanitize <script>.
import streamlit.components.v1 as _components_pdf
_components_pdf.html("""
<script>
(function() {
  try {
    const top = window.parent;
    if (!top || top._printHandlerAttached) return;
    top._printHandlerAttached = true;
    const openAllDetails = () => {
      top.document.querySelectorAll('details').forEach(d => {
        d.setAttribute('data-was-open', d.open ? '1' : '0');
        d.open = true;
      });
      // Cuộn về đầu trang để Chrome reflow toàn bộ content
      top.scrollTo(0, 0);
    };
    const restoreDetails = () => {
      top.document.querySelectorAll('details').forEach(d => {
        if (d.getAttribute('data-was-open') === '0') d.open = false;
        d.removeAttribute('data-was-open');
      });
    };
    top.addEventListener('beforeprint', openAllDetails);
    top.addEventListener('afterprint', restoreDetails);
    if (top.matchMedia) {
      const mql = top.matchMedia('print');
      const handler = e => { if (e.matches) openAllDetails(); else restoreDetails(); };
      if (mql.addEventListener) mql.addEventListener('change', handler);
    }
    console.log('[Print] beforeprint handler attached to parent window');
  } catch(e) { console.error('[Print] Failed to attach handler:', e); }
})();
</script>
""", height=0)

st.sidebar.divider()
st.sidebar.markdown("### Xuất PDF")

# Import PDF module — ưu tiên weasyprint (HTML/CSS/Jinja2), fallback reportlab
_HAS_PDF = False
_PDF_ENGINE = "—"
import sys as _sys_pdf
_sys_pdf.path.insert(0, str(_ROOT / "scripts"))
try:
    from pdf_report import (
        report_all       as _pdf_all,
        report_params    as _pdf_params,
        report_settlement as _pdf_settle,
        report_ke_sw     as _pdf_kesw,
    )
    _HAS_PDF = True
    _PDF_ENGINE = "weasyprint (HTML/CSS)"
except Exception:
    try:
        from pdf_export import (
            build_all_pdf      as _pdf_all,
            build_params_pdf   as _pdf_params,
            build_settlement_pdf as _pdf_settle,
            build_ke_sw_pdf    as _pdf_kesw,
        )
        _HAS_PDF = True
        _PDF_ENGINE = "reportlab (fallback)"
    except Exception as _e_pdf:
        st.sidebar.caption(f"_(PDF engine chưa cài: {_e_pdf})_")

if _HAS_PDF:
    # Nút xuất PDF tổng hợp
    try:
        _pdf_all_bytes = _pdf_all(
            dict(st.session_state),
            _DB,
            st.session_state.get("sl_result"),
        )
        st.sidebar.download_button(
            "Xuất PDF Tổng hợp (tất cả tab)",
            data=_pdf_all_bytes,
            file_name=f"BaoCao_TongHop_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )
    except Exception as _e_all:
        st.sidebar.warning(f"Không tạo PDF tổng hợp: {_e_all}")
st.sidebar.caption(
    f"_Engine: {_PDF_ENGINE}_  \n"
    "_Hoặc nhấn `Ctrl+P` → Save as PDF (in nguyên trang web)._"
)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1 – ĐỊA CHẤT
# ═══════════════════════════════════════════════════════════════════════════════
if _page == "geology":
    st.subheader(_t("p1_sub"))

    col_sel, col_prof = st.columns([1, 4])

    with col_sel:
        zone = st.radio(_t("zone_lbl"), list(_ZONE_NAMES.keys()),
                        format_func=lambda z: _ZONE_NAMES[z],
                        index=list(_ZONE_NAMES.keys()).index(_get("cdm_zone")),
                        horizontal=False)
        st.session_state["cdm_zone"] = zone

        bhs = _load_boreholes_by_zone(zone)
        bh_names = [b["name"] for b in bhs]
        if not bh_names:
            st.warning(_t("no_bh_warn"))
            bh_names = ["(trống)"]

        cur_bh = _get("cdm_bh")
        sel_idx = bh_names.index(cur_bh) if cur_bh in bh_names else 0
        bh_name = st.selectbox(_t("bh_lbl"), bh_names, index=sel_idx)

        if st.button(_t("apply_bh"), type="primary"):
            st.session_state["cdm_bh"]  = bh_name
            st.session_state["sl_zone"] = zone
            st.session_state["sl_bh"]   = bh_name
            # Auto-fill soil params
            cp = _clay_params(bh_name, zone)
            if cp:
                st.session_state["cdm_h_clay"]   = cp["h_clay"]
                st.session_state["cdm_elevation"] = cp.get("elevation_m", 0.0)
                st.session_state["cdm_Lc"]        = round(cp["h_clay"] + 1.5, 1)
            su = _su_avg_in_range(zone, 0, cp.get("depth_clay_bot", 30) if cp else 30)
            if su:
                st.session_state["cdm_Su"] = su
            g = _gamma_avg(bh_name)
            if g:
                st.session_state["cdm_gamma"] = g
            # Liên kết VST: tự động chọn VST location khớp với hố khoan
            _df_vst_link = _load_vst_su(zone)
            if not _df_vst_link.empty:
                _vst_locs = sorted(_df_vst_link["loc_name"].unique().tolist())
                _matched = [l for l in _vst_locs if l == bh_name]
                if not _matched:
                    _bh_low = bh_name.lower()
                    _matched = [l for l in _vst_locs
                                if _bh_low in l.lower() or l.lower() in _bh_low]
                if _matched:
                    st.session_state["cdm_vst_sel"]  = _matched
                    st.session_state["_vst_loc_sel"] = _matched
            st.success(_t("apply_bh_ok", bh=bh_name))
            st.rerun()

        # Thông tin nhanh
        if _get("cdm_bh"):
            cp = _clay_params(_get("cdm_bh"), zone)
            if cp:
                st.metric(_t("clay_thick"), f"{cp['h_clay']:.1f} m")
                st.metric(_t("clay_elev"),  f"{cp['elev_clay_bot']:.2f} m")
            su = _su_avg_in_range(zone, 0, cp.get("depth_clay_bot",30) if cp else 30)
            if su:
                st.metric(_t("su_avg"), f"{su:.1f} kPa")

        # Bảng thống kê nén cố kết
        st.markdown("---")
        st.markdown("**Thí nghiệm nén cố kết**")
        df_cc = _load_consol_summary(zone)
        if df_cc.empty:
            st.caption("Chưa có dữ liệu nén cố kết cho khu vực này.")
        else:
            df_cc_disp = df_cc.rename(columns={
                "borehole": "Hố khoan",
                "n_Cc":     "n",
                "Cc_tb":    "Cc tb",
                "Cs_tb":    "Cs tb",
                "e0_tb":    "e₀ tb",
                "PC_min":   "PC min\n(kPa)",
                "PC_max":   "PC max\n(kPa)",
            })[["Hố khoan", "n", "Cc tb", "Cs tb", "e₀ tb", "PC min\n(kPa)", "PC max\n(kPa)"]]
            st.dataframe(df_cc_disp, use_container_width=True, hide_index=True)

    with col_prof:
        layers = _load_layers(bh_name)
        if layers:
            st.markdown(f"**{_t('strat_title')}**")
            df_lay = pd.DataFrame(layers)
            _is_vn = _get("lang") == "VN"
            if _is_vn:
                df_lay.columns = ["Ký hiệu", "Mô tả", "Đỉnh (m)", "Đáy (m)", "Dày (m)",
                                  "γ (kN/m³)", "c (kPa)", "φ (°)",
                                  "e₀", "Cc", "Cs", "PC (kPa)", "Cv (cm²/s)"]
                _desc_col = "Mô tả"
            else:
                df_lay.columns = ["Symbol", "Description", "Top (m)", "Bot (m)", "Thick (m)",
                                  "γ (kN/m³)", "c (kPa)", "φ (°)",
                                  "e₀", "Cc", "Cs", "PC (kPa)", "Cv (cm²/s)"]
                _desc_col = "Description"

            # Format Cv scientific notation
            _cv_col = "Cv (cm²/s)"
            df_lay[_cv_col] = df_lay[_cv_col].apply(
                lambda x: f"{x:.2e}" if pd.notna(x) and x is not None else "–"
            )

            st.dataframe(
                df_lay,
                use_container_width=True,
                height=310,
                column_config={
                    _desc_col:    st.column_config.TextColumn(width="medium"),
                    "γ (kN/m³)":  st.column_config.NumberColumn(format="%.2f"),
                    "c (kPa)":    st.column_config.NumberColumn(format="%.1f"),
                    "φ (°)":      st.column_config.NumberColumn(format="%.1f"),
                    "e₀":         st.column_config.NumberColumn(format="%.3f"),
                    "Cc":         st.column_config.NumberColumn(format="%.4f"),
                    "Cs":         st.column_config.NumberColumn(format="%.4f"),
                    "PC (kPa)":   st.column_config.NumberColumn(format="%.1f"),
                    _cv_col:      st.column_config.TextColumn(width="small"),
                },
            )
        else:
            st.info(_t("no_strat"))

    st.divider()
    # VST profile + soil column
    _su_col, _sc_col = st.columns([2, 1])
    with _su_col:
        df_vst = _load_vst_su(zone)
        if not df_vst.empty:
            _vst_all_locs = sorted(df_vst["loc_name"].unique().tolist())
            _vst_sel_prev = [l for l in _get("cdm_vst_sel") if l in _vst_all_locs]
            _vst_sel = st.multiselect(
                _t("vst_sel"),
                options=_vst_all_locs,
                default=_vst_sel_prev,
                key="_vst_loc_sel",
            )
            st.session_state["cdm_vst_sel"] = _vst_sel
            _vst_pass = _vst_sel if _vst_sel else None
            if _HAS_PLOTLY:
                st.plotly_chart(
                    _chart_su_profile(df_vst, _vst_pass),
                    use_container_width=True,
                )
            elif _HAS_MPL:
                _fig_vst_mpl = _chart_su_profile_mpl(df_vst, _vst_pass)
                st.pyplot(_fig_vst_mpl, use_container_width=True)
                plt.close(_fig_vst_mpl)
            else:
                st.dataframe(df_vst)
    with _sc_col:
        _bh_sc = bh_name if bh_name != "(trống)" else None
        if _bh_sc and (_HAS_PLOTLY or _HAS_MPL):
            try:
                _sc_layers = _load_layers(_bh_sc)
                _sc_spt    = _load_spt(_bh_sc)
                if _HAS_PLOTLY:
                    st.plotly_chart(
                        _draw_soil_column(_sc_layers, _bh_sc, spt=_sc_spt or None),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                else:
                    _fig_col_mpl = _draw_soil_column_mpl(_sc_layers, _bh_sc, spt=_sc_spt or None)
                    st.pyplot(_fig_col_mpl, use_container_width=True)
                    plt.close(_fig_col_mpl)
            except Exception as _e:
                st.warning(f"Không vẽ được cột địa chất: {_e}")
        else:
            st.caption(_t("no_bh_col"))

    # CDM test results
    df_cdm = _load_cdm_tests()
    if not df_cdm.empty:
        with st.expander(_t("cdm_test_exp"), expanded=False):
            _cdm_cols = (
                {"bh_name": "HK", "cement_type": "Xi măng", "WC_ratio": "N/XM",
                 "dosage_kgm3": "Hàm lượng (kg/m³)", "qu_R7_kPa": "qu R7 (kPa)",
                 "E50_R7_MPa": "E50 R7 (MPa)"}
                if _get("lang") == "VN" else
                {"bh_name": "BH", "cement_type": "Cement", "WC_ratio": "W/C",
                 "dosage_kgm3": "Dosage (kg/m³)", "qu_R7_kPa": "qu R7 (kPa)",
                 "E50_R7_MPa": "E50 R7 (MPa)"}
            )
            st.dataframe(df_cdm[list(_cdm_cols)].rename(columns=_cdm_cols),
                         use_container_width=True)
            st.caption(_t("cdm_test_note"))

    # ── Nén cố kết – thống kê hố khoan có dữ liệu ─────────────────────────────
    _df_consol = _load_consol_summary(zone)
    if not _df_consol.empty:
        _is_vn = _get("lang") == "VN"
        _consol_title = (
            "Nén cố kết – Hố khoan có dữ liệu tính lún theo thời gian"
            if _is_vn else
            "Consolidation – Boreholes with time-settlement data"
        )
        with st.expander(_consol_title, expanded=True):
            # Format Cv and k in scientific notation for readability
            _df_disp = _df_consol.copy()
            _df_disp["Cv_tb"] = _df_disp["Cv_tb"].apply(
                lambda x: f"{x:.2e}" if pd.notna(x) else "–"
            )
            _df_disp["k_tb"] = _df_disp["k_tb"].apply(
                lambda x: f"{x:.2e}" if pd.notna(x) else "–"
            )
            _df_disp["PC_kPa"] = _df_disp.apply(
                lambda r: f"{r['PC_min']:.0f}–{r['PC_max']:.0f}"
                if pd.notna(r["PC_min"]) else "–", axis=1
            )

            if _is_vn:
                _df_disp = _df_disp.rename(columns={
                    "borehole": "Hố khoan",
                    "n_mau":   "Tổng mẫu",
                    "n_Cc":    "Mẫu NCK",
                    "Cc_tb":   "Cc TB",
                    "Cs_tb":   "Cs TB",
                    "Cv_tb":   "Cv TB (cm²/s)",
                    "k_tb":    "k TB (cm/s)",
                    "PC_kPa":  "PC (kPa)",
                    "e0_tb":   "e₀ TB",
                })
                _note = (
                    "NCK = Nén cố kết. Cc: chỉ số nén. Cs: chỉ số nở lại. "
                    "Cv: hệ số cố kết. k: hệ số thấm. PC: áp lực tiền cố kết. "
                    "Các giá trị là trung bình số học của các mẫu trong hố khoan."
                )
            else:
                _df_disp = _df_disp.rename(columns={
                    "borehole": "Borehole",
                    "n_mau":   "Total",
                    "n_Cc":    "Consol.",
                    "Cc_tb":   "Cc avg",
                    "Cs_tb":   "Cs avg",
                    "Cv_tb":   "Cv avg (cm²/s)",
                    "k_tb":    "k avg (cm/s)",
                    "PC_kPa":  "PC (kPa)",
                    "e0_tb":   "e₀ avg",
                })
                _note = (
                    "Consol. = samples with consolidation data. Cv: coefficient of consolidation. "
                    "k: permeability. PC: preconsolidation pressure. Values are arithmetic means per borehole."
                )

            _drop_cols = ["PC_min", "PC_max"]
            _df_disp = _df_disp.drop(columns=[c for c in _drop_cols if c in _df_disp.columns])

            st.dataframe(
                _df_disp,
                use_container_width=True,
                hide_index=True,
                column_config={
                    _df_disp.columns[2]: st.column_config.NumberColumn(format="%d"),
                    "Cc TB" if _is_vn else "Cc avg": st.column_config.NumberColumn(format="%.4f"),
                    "Cs TB" if _is_vn else "Cs avg": st.column_config.NumberColumn(format="%.4f"),
                    "e₀ TB" if _is_vn else "e₀ avg": st.column_config.NumberColumn(format="%.3f"),
                },
            )
            st.caption(_note)

            # Tóm tắt số hố có dữ liệu
            _n_bh_ok  = len(_df_consol)
            _n_bh_all = len(_load_boreholes_by_zone(zone))
            st.info(
                f"{'Zone' if not _is_vn else 'Zone'} **{_ZONE_NAMES[zone]}**: "
                f"{_n_bh_ok}/{_n_bh_all} "
                f"{'hố khoan có thí nghiệm nén cố kết (Cc/Cs/Cv/k/PC).' if _is_vn else 'boreholes have consolidation test data (Cc/Cs/Cv/k/PC).'}"
            )

    # ── 3D / Map toggle ───────────────────────────────────────────────────────
    st.divider()
    if not _HAS_PLOTLY and _HAS_PYDECK:
        # Pydeck 3D — native drag/zoom/rotate qua deck.gl
        _bhs_all_pd, _ = _load_borehole_3d_data()
        _zones_with_coords_pd = sorted({b["zone"] for b in _bhs_all_pd})
        if not _zones_with_coords_pd:
            st.info(_t("no_coords_db"))
        else:
            st.markdown("#### Bản đồ 3D địa chất (pydeck — kéo-xoay-zoom)")
            _pc1, _pc2 = st.columns([3, 2])
            with _pc1:
                _sel_zones_pd = st.multiselect(
                    _t("zone_lbl"), _zones_with_coords_pd,
                    default=_zones_with_coords_pd, key="_3d_pd_zones",
                )
            with _pc2:
                _show_clay_pd = st.checkbox(_t("clay_surf"), value=True, key="_3d_pd_clay")
                _show_cdm_pd  = st.checkbox(_t("cdm_top_show"), value=False, key="_3d_pd_top")
            _cdm_z_pd = float(_get("cdm_CDTK"))
            _zscale_col, _radius_col, _cdmz_col = st.columns(3)
            if _show_cdm_pd:
                _cdm_z_pd = _cdmz_col.number_input(
                    _t("elev_lbl"), value=_cdm_z_pd, step=0.1, key="_3d_pd_top_z")
            _z_scale_pd = _zscale_col.slider(
                "Phóng đại trục Z", 1.0, 20.0, 5.0, 0.5, key="_3d_pd_zscale",
                help="Z (cao độ) thường rất nhỏ so với khoảng cách XY → phóng đại để dễ nhìn",
            )
            _col_radius_pd = _radius_col.slider(
                "Bán kính trụ (m)", 0.5, 10.0, 2.5, 0.5, key="_3d_pd_radius",
                help="Bán kính trụ địa chất — to để thấy rõ bề dày, nhỏ để không che HK kế bên",
            )

            # ── Toggle overlay & spacing check ──────────────────────────────
            _tc0, _tc1, _tc2, _tc3 = st.columns([1, 1.2, 1, 1.5])
            _show_bh_names_pd = _tc0.checkbox(
                "Hiện tên hố khoan",
                value=True, key="_3d_pd_bhnames",
            )
            _show_pairs_pd  = _tc1.checkbox(
                "Hiện tất cả khoảng cách HK trên 3D",
                value=True, key="_3d_pd_pairs",
                help="Vẽ đường nối + nhãn cho mọi cặp HK cùng khu vực, màu theo TCCS41",
            )
            _show_labels_pd = _tc2.checkbox(
                "Hiện nhãn khoảng cách",
                value=True, key="_3d_pd_labels",
            )
            _step_opts_pd = {
                "BVTK (100–150 m)": "BVTK",
                "LAPDA (250–500 m)": "LAPDA",
                "BVTK mặt cắt (150–300 m)": "BVTK_matcat",
            }
            _step_lbl_pd = _tc3.selectbox(
                "Bước thiết kế (TCCS41 5.3.2)",
                list(_step_opts_pd.keys()),
                key="_3d_pd_step",
            )
            _step_code_pd = _step_opts_pd[_step_lbl_pd]

            # ── Tính spacing check ──────────────────────────────────────────
            _pair_lines_pd: list[dict] = []
            _sp_res_pd: dict = {}
            _bhs_in_zone_pd = [b for b in _bhs_all_pd if b["zone"] in (_sel_zones_pd or [])]
            try:
                import sys as _sys2
                _sys2.path.insert(0, str(_ROOT / "scripts"))
                from borehole_spacing import check_spacing_532 as _chk_sp_pd
                _sp_res_pd = _chk_sp_pd(_bhs_in_zone_pd, _step_code_pd, same_zone_only=True)
                _pair_lines_pd = _sp_res_pd.get("pairs", [])

                _sp_sum = _sp_res_pd["summary"]
                _mc1, _mc2, _mc3 = st.columns(3)
                _mc1.metric(
                    "Cặp đạt yêu cầu",
                    f"{_sp_sum['n_ok']}/{_sp_sum['n_pairs']}",
                    delta=f"Gần: {_sp_sum['n_too_close']} | Xa: {_sp_sum['n_too_far']}",
                    delta_color="normal" if _sp_sum["n_ok"] == _sp_sum["n_pairs"] else "inverse",
                )
                if _sp_sum["min_dist_m"] is not None:
                    _mc2.metric(
                        "Khoảng cách (min–max)",
                        f"{_sp_sum['min_dist_m']:.0f} – {_sp_sum['max_dist_m']:.0f} m",
                        delta=f"Yêu cầu: {_sp_res_pd['limit_min_m']:.0f}–{_sp_res_pd['limit_max_m']:.0f} m",
                        delta_color="off",
                    )
                _mc3.caption(f"Tiêu chuẩn: {_sp_res_pd['limit_label']}")
            except Exception as _sp_e:
                st.warning(f"Không tải được borehole_spacing: {_sp_e}")

            # ── Đo khoảng cách 1 cặp HK riêng (highlight cam to) ────────────
            _pair_sel_pd = None
            _bh_names_pd = sorted({b["name"] for b in _bhs_in_zone_pd})
            if len(_bh_names_pd) >= 2:
                _pp1, _pp2 = st.columns(2)
                _b1p = _pp1.selectbox("Highlight cặp HK: HK 1",
                                      ["(không chọn)"] + _bh_names_pd, key="_3d_pd_pair1")
                _b2p = _pp2.selectbox("HK 2",
                                      ["(không chọn)"] + _bh_names_pd, key="_3d_pd_pair2")
                if (_b1p != "(không chọn)" and _b2p != "(không chọn)" and _b1p != _b2p):
                    _b1 = next((b for b in _bhs_in_zone_pd if b["name"] == _b1p), None)
                    _b2 = next((b for b in _bhs_in_zone_pd if b["name"] == _b2p), None)
                    if _b1 and _b2:
                        _dx = _b1["x_coord_m"] - _b2["x_coord_m"]
                        _dy = _b1["y_coord_m"] - _b2["y_coord_m"]
                        _dist_pd = (_dx*_dx + _dy*_dy) ** 0.5
                        _pair_sel_pd = (_b1p, _b2p, _dist_pd)

            if _sel_zones_pd:
                try:
                    _deck = _build_borehole_3d_deck(
                        _sel_zones_pd,
                        show_clay_bottom=_show_clay_pd,
                        show_cdm_top=_show_cdm_pd,
                        cdm_top_z=_cdm_z_pd,
                        pair_highlight=_pair_sel_pd,
                        z_scale=_z_scale_pd,
                        col_radius=_col_radius_pd,
                        pair_lines=(_pair_lines_pd if _show_pairs_pd else None),
                        show_pair_labels=_show_labels_pd,
                        show_bh_names=_show_bh_names_pd,
                    )
                    if _deck is not None:
                        st.pydeck_chart(_deck, use_container_width=True, height=560)
                        st.caption(
                            "Kéo chuột = xoay  •  Shift+kéo = pan  •  Lăn chuột = zoom  •  "
                            "Hover trên cọc/đường để xem chi tiết.  "
                            f"Trục Z phóng đại ×{_z_scale_pd:.1f}.  "
                            "Màu đường: xanh=Đạt, đỏ=Gần quá, cam=Xa quá."
                        )
                    else:
                        st.info("Không có dữ liệu cho khu vực đã chọn.")
                except Exception as _e:
                    st.warning(f"Không vẽ được bản đồ pydeck: {_e}")

                # ── Bảng chi tiết khoảng cách ───────────────────────────────
                if _pair_lines_pd:
                    with st.expander(
                        f"Bảng khoảng cách hố khoan ({len(_pair_lines_pd)} cặp)",
                        expanded=False,
                    ):
                        _sp_rows_pd = [{
                            "Hố khoan 1":      p["bh1"],
                            "Hố khoan 2":      p["bh2"],
                            "Khu vực":         p["zone1"],
                            "Khoảng cách (m)": p["distance_m"],
                            "Yêu cầu (m)":     f"{p['limit_min_m']:.0f}–{p['limit_max_m']:.0f}",
                            "Kết quả":         p["status"],
                        } for p in _pair_lines_pd]
                        _sp_df_pd = pd.DataFrame(_sp_rows_pd)

                        def _sp_color_pd(val):
                            if val == "Đạt":
                                return "background-color:#d4edda; color:#155724"
                            if val in ("Gần quá", "Xa quá"):
                                return "background-color:#f8d7da; color:#721c24"
                            return ""

                        st.dataframe(
                            _sp_df_pd.style.map(_sp_color_pd, subset=["Kết quả"]),
                            use_container_width=True, hide_index=True,
                        )
    elif not _HAS_PLOTLY and _HAS_MPL:
        # Matplotlib 3D fallback (khi không có cả plotly và pydeck)
        _bhs_all_mpl, _ = _load_borehole_3d_data()
        _zones_with_coords_mpl = sorted({b["zone"] for b in _bhs_all_mpl})
        if not _zones_with_coords_mpl:
            st.info(_t("no_coords_db"))
        else:
            st.markdown("#### Bản đồ 3D địa chất (matplotlib)")
            _mc1, _mc2 = st.columns([3, 2])
            with _mc1:
                _sel_zones_mpl = st.multiselect(
                    _t("zone_lbl"), _zones_with_coords_mpl,
                    default=_zones_with_coords_mpl, key="_3d_mpl_zones",
                )
            with _mc2:
                _show_clay_mpl = st.checkbox(_t("clay_surf"), value=True, key="_3d_mpl_clay")
                _show_cdm_mpl  = st.checkbox(_t("cdm_top_show"), value=False, key="_3d_mpl_top")
            _cdm_z_mpl = float(_get("cdm_CDTK"))
            if _show_cdm_mpl:
                _cdm_z_mpl = st.number_input(
                    _t("elev_lbl"), value=_cdm_z_mpl, step=0.1, key="_3d_mpl_top_z")
            _vc1, _vc2, _vc3 = st.columns(3)
            _elev_mpl = _vc1.slider("Góc nhìn dọc (elev°)", -90, 90, 20, 5, key="_3d_mpl_elev")
            _azim_mpl = _vc2.slider("Góc xoay ngang (azim°)", -180, 180, -60, 10, key="_3d_mpl_azim")
            _zoom_mpl = _vc3.slider("Zoom", 0.3, 3.0, 1.0, 0.1, key="_3d_mpl_zoom")
            if _sel_zones_mpl:
                try:
                    _fig_3d_mpl = _draw_boreholes_3d_mpl(
                        _sel_zones_mpl, show_clay_bottom=_show_clay_mpl,
                        show_cdm_top=_show_cdm_mpl, cdm_top_z=_cdm_z_mpl,
                        elev=_elev_mpl, azim=_azim_mpl, zoom=_zoom_mpl,
                    )
                    st.pyplot(_fig_3d_mpl, use_container_width=True)
                    plt.close(_fig_3d_mpl)
                except Exception as _e:
                    st.warning(f"Không vẽ được bản đồ 3D: {_e}")
    elif not _HAS_PLOTLY:
        st.caption("Cài `plotly` (hoặc matplotlib) để xem bản đồ địa chất.")
    else:
        _bhs_all, _ = _load_borehole_3d_data()
        _zones_with_coords = sorted({b["zone"] for b in _bhs_all})
        if not _zones_with_coords:
            st.info(_t("no_coords_db"))
        else:
            # ── Thanh điều khiển ──────────────────────────────────────────────
            _ctrl_a, _ctrl_b = st.columns([3, 2])
            _view_opts = [_t("view_3d"), _t("view_map")]
            with _ctrl_a:
                _geo_view = st.radio(
                    _t("view_mode"),
                    _view_opts,
                    index=0,
                    horizontal=True,
                    key="_geo_view_radio",
                )
                st.session_state["cdm_geo_view"] = _geo_view

            # ── 3D VIEW ───────────────────────────────────────────────────────
            if _geo_view == _t("view_3d"):
                with _ctrl_b:
                    _sel_zones = st.multiselect(
                        _t("zone_lbl"), _zones_with_coords,
                        default=_zones_with_coords, key="_3d_cdm_zones",
                    )
                _cb1, _cb2, _cb3 = st.columns(3)
                _show_clay = _cb1.checkbox(_t("clay_surf"), value=True, key="_3d_cdm_clay")
                _show_cdm  = _cb2.checkbox(_t("cdm_top_show"), value=False, key="_3d_cdm_top")
                _cdm_top_z = float(_get("cdm_CDTK"))
                if _show_cdm:
                    _cdm_top_z = _cb3.number_input(
                        _t("elev_lbl"), value=_cdm_top_z, step=0.1, key="_3d_cdm_top_z")
                _vst_focus = _get("cdm_vst_sel")
                _focus_bh = _vst_focus[0] if len(_vst_focus) == 1 else None

                # ── Layout 2 cột: 3D (trái) | Bảng khoảng cách (phải) ──────
                _col3d, _col_sp = st.columns([3, 2], gap="medium")

                # ── Bảng khoảng cách (phải) — đọc trước để lấy pair_sel ────
                _pair_sel = None
                with _col_sp:
                    st.markdown("#### Khoảng cách hố khoan — Điều 5.3.2")
                    try:
                        import sys as _sys2
                        _sys2.path.insert(0, str(_ROOT / "scripts"))
                        from borehole_spacing import check_spacing_532 as _chk_sp
                        _bhs_sp = [b for b in _bhs_all if b.get("zone") in (_sel_zones or [])]
                        _step_opts = {
                            "BVTK (100–150 m)": "BVTK",
                            "LAPDA (250–500 m)": "LAPDA",
                        }
                        _step_lbl = st.selectbox(
                            "Bước thiết kế",
                            list(_step_opts.keys()),
                            key="_sp_step_sel",
                        )
                        _step_code = _step_opts[_step_lbl]
                        _sp_res = _chk_sp(_bhs_sp, _step_code, same_zone_only=True)
                        _sp_s   = _sp_res["summary"]

                        # Metric tóm tắt
                        _mc1, _mc2 = st.columns(2)
                        _mc1.metric(
                            "Cặp đạt yêu cầu",
                            f"{_sp_s['n_ok']}/{_sp_s['n_pairs']}",
                            delta=f"Gần: {_sp_s['n_too_close']} | Xa: {_sp_s['n_too_far']}",
                            delta_color="normal" if _sp_s["n_ok"] == _sp_s["n_pairs"] else "inverse",
                        )
                        if _sp_s["min_dist_m"] is not None:
                            _mc2.metric(
                                "Khoảng cách (min–max)",
                                f"{_sp_s['min_dist_m']:.0f} – {_sp_s['max_dist_m']:.0f} m",
                                delta=f"Yêu cầu: {_sp_res['limit_min_m']:.0f}–{_sp_res['limit_max_m']:.0f} m",
                                delta_color="off",
                            )

                        # Chọn cặp HK để hiển thị kích thước trên 3D
                        _sp_pairs = _sp_res["pairs"]
                        _pair_labels = [
                            f"{p['bh1']} ↔ {p['bh2']}  ({p['distance_m']:.0f} m — {p['status']})"
                            for p in _sp_pairs
                        ]
                        _pair_choice = st.selectbox(
                            "Chọn cặp HK để đo kích thước trên 3D",
                            ["(không chọn)"] + _pair_labels,
                            key="_sp_pair_sel",
                        )
                        if _pair_choice != "(không chọn)":
                            _pidx = _pair_labels.index(_pair_choice)
                            _pp   = _sp_pairs[_pidx]
                            _pair_sel = (_pp["bh1"], _pp["bh2"], _pp["distance_m"])

                        # Bảng chi tiết
                        if _sp_pairs:
                            _sp_rows = [
                                {
                                    "Hố khoan 1":    p["bh1"],
                                    "Hố khoan 2":    p["bh2"],
                                    "Khu vực":       p["zone1"],
                                    "Khoảng cách (m)": p["distance_m"],
                                    "Kết quả":       p["status"],
                                }
                                for p in _sp_pairs
                            ]
                            _sp_df = pd.DataFrame(_sp_rows)

                            def _sp_color(val):
                                if val == "Đạt":
                                    return "background-color:#d4edda; color:#155724"
                                if val in ("Gần quá", "Xa quá"):
                                    return "background-color:#f8d7da; color:#721c24"
                                return ""

                            st.dataframe(
                                _sp_df.style.map(_sp_color, subset=["Kết quả"]),
                                use_container_width=True,
                                hide_index=True,
                                height=260,
                            )
                        else:
                            st.info("Chưa có tọa độ hố khoan để tính khoảng cách.")
                        st.caption(
                            f"Tiêu chuẩn: TCCS 41:2022 Điều 5.3.2 — {_sp_res['limit_label']}"
                        )
                    except Exception as _sp_exc:
                        st.warning(f"Không tải được borehole_spacing: {_sp_exc}")

                # ── 3D chart (trái) ─────────────────────────────────────────
                with _col3d:
                    if _sel_zones:
                        st.plotly_chart(
                            _draw_boreholes_3d(
                                _sel_zones, _show_clay, _show_cdm, _cdm_top_z,
                                focus_bh=_focus_bh,
                                pair_highlight=_pair_sel,
                            ),
                            use_container_width=True, config={"displayModeBar": True},
                        )
                    else:
                        st.info(_t("no_zone"))

            # ── MAP VIEW ──────────────────────────────────────────────────────
            else:
                with _ctrl_b:
                    _map_style_label = st.selectbox(
                        _t("map_style"),
                        list(_MAP_STYLES.keys()),
                        index=list(_MAP_STYLES.keys()).index(
                            _get("cdm_map_style")
                            if _get("cdm_map_style") in _MAP_STYLES else "Đường phố (OSM)"
                        ),
                        key="_map_style_sel",
                    )
                    st.session_state["cdm_map_style"] = _map_style_label

                # Hiệu chỉnh GPS
                _ref_default = _get("cdm_map_ref_bh") or ""
                _calibrated  = bool(_ref_default)
                with st.expander(
                    _t("gps_done") if _calibrated else _t("gps_needed"),
                    expanded=not _calibrated,
                ):
                    st.markdown(
                        "**Cách lấy toạ độ GPS:**  \n"
                        "1. Mở [Google Maps](https://maps.google.com) → tìm vị trí hố khoan trên thực địa  \n"
                        "2. **Chuột phải** vào điểm đó → copy dòng số đầu tiên (ví dụ: `10.782341, 106.718560`)  \n"
                        "3. Chọn hố khoan tương ứng bên dưới → nhập lat/lon → **Áp dụng**"
                    )
                    _bh_names_all = [b["name"] for b in _bhs_all]
                    _ref_idx = _bh_names_all.index(_ref_default) if _ref_default in _bh_names_all else 0
                    _c1, _c2, _c3 = st.columns([2, 1, 1])
                    _ref_bh  = _c1.selectbox(_t("ref_bh"), _bh_names_all,
                                             index=_ref_idx, key="_map_ref_bh_sel")
                    _ref_lat = _c2.number_input("Latitude", value=float(_get("cdm_map_ref_lat")),
                                                format="%.6f", step=0.000100, key="_map_ref_lat")
                    _ref_lon = _c3.number_input("Longitude", value=float(_get("cdm_map_ref_lon")),
                                                format="%.6f", step=0.000100, key="_map_ref_lon")
                    if st.button(_t("apply_calib"), type="primary", key="_map_calib_btn"):
                        st.session_state.update({
                            "cdm_map_ref_bh":  _ref_bh,
                            "cdm_map_ref_lat": _ref_lat,
                            "cdm_map_ref_lon": _ref_lon,
                        })
                        st.rerun()
                    if _calibrated:
                        st.success(
                            f"Đang dùng: {_get('cdm_map_ref_bh')} → "
                            f"lat={_get('cdm_map_ref_lat'):.6f}, "
                            f"lon={_get('cdm_map_ref_lon'):.6f}"
                        )
                _use_gps = True
                _ref_bh  = _get("cdm_map_ref_bh") or (_bh_names_all[0] if _bh_names_all else "")
                _ref_lat = float(_get("cdm_map_ref_lat"))
                _ref_lon = float(_get("cdm_map_ref_lon"))

                _bhs_ll = _project_to_latlon(
                    _bhs_all, _ref_bh, _ref_lat, _ref_lon, use_gps_ref=_use_gps
                )
                if _bhs_ll:
                    st.plotly_chart(
                        _draw_map_2d(_bhs_ll, _MAP_STYLES[_map_style_label]),
                        use_container_width=True,
                        config={"displayModeBar": True, "scrollZoom": True},
                    )
                else:
                    st.warning(_t("no_coords"))


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE – KIỂM TRA MẪU THÍ NGHIỆM
# ═══════════════════════════════════════════════════════════════════════════════
elif _page == "sample_check":
    import sys as _sys2
    _sys2.path.insert(0, str(_ROOT / "scripts"))

    # Import độc lập — section A không phụ thuộc section B
    try:
        from settlement_calc import check_samples_vs_tccs41 as _chk537
        _HAS_537 = True
    except Exception as _exc537:
        _HAS_537 = False
        st.error(f"Không tải được settlement_calc: {_exc537}")

    try:
        from cdm_column_calc import check_qc_adequacy as _chk9403
        _HAS_9403 = True
    except Exception:
        _HAS_9403 = False  # module chưa tồn tại — ẩn section B

    st.subheader("Kiểm tra mẫu thí nghiệm — TCCS 41:2022 & TCVN 9403:2012")

    # ── A. TCCS 41:2022 Điều 5.3.7 ──────────────────────────────────────────
    st.markdown("## A. Mẫu nén cố kết — TCCS 41:2022 Điều 5.3.7")
    st.caption(
        "Điều 5.3.7: Mỗi lớp đất yếu, mỗi chỉ tiêu đưa vào tính toán cần có **≥ 6 số liệu thí nghiệm**. "
        "Trị số tính toán: Δt = Δtb ± δ  (δ = độ lệch chuẩn mẫu). "
        "Áp dụng cho Cc, Cs, Cv, PC của các lớp đất yếu (CH/CL/MH/ML và biến thể)."
    )

    if _HAS_537:
        # Tải dữ liệu 3 khu vực
        _chk_all = {}
        for _zc in ["NHC", "BXN", "KE"]:
            try:
                _chk_all[_zc] = _chk537(_zc)
            except Exception as _ex:
                st.error(f"Khu vực {_zc}: {_ex}")

        # Metric cards tóm tắt
        _lun_params = ["Cc", "Cs", "Cv", "PC"]
        _met_cols = st.columns(3)
        for _ci, _zc in enumerate(["NHC", "BXN", "KE"]):
            if _zc not in _chk_all:
                continue
            _s       = _chk_all[_zc]["zone_summary"]
            _n_soft  = _s["n_layers_soft"]
            _ok_cc   = _s["params_ok"].get("Cc", 0)
            _fail_cc = _s["params_fail"].get("Cc", 0)
            with _met_cols[_ci]:
                st.metric(
                    f"Khu vực {_zc}",
                    f"{_ok_cc}/{_n_soft} lớp đủ Cc",
                    f"{_fail_cc} lớp thiếu mẫu (n<6)",
                    delta_color="normal" if _fail_cc == 0 else "inverse",
                )
                st.caption(
                    f"Tổng lớp: {_s['n_layers_total']} | Lớp yếu: {_n_soft}  \n"
                    + "  ".join(
                        f"{p}: {_s['params_ok'].get(p,0)}Đ/{_s['params_fail'].get(p,0)}T"
                        for p in _lun_params
                    )
                )

        def _fmt_p(info):
            if not info or info.get("n", 0) == 0:
                return "-"
            n  = info["n"]
            ok = info.get("ok")
            if ok is True:  return f"{n} (Đạt)"
            if ok is False: return f"{n} (Thiếu)"
            return str(n)

        def _cell_color(val):
            if "(Đạt)"   in str(val): return "background-color:#d4edda; color:#155724"
            if "(Thiếu)" in str(val): return "background-color:#f8d7da; color:#721c24"
            return ""

        # Bảng chi tiết per khu vực
        for _zc in ["NHC", "BXN", "KE"]:
            if _zc not in _chk_all:
                continue
            st.markdown(f"**Khu vực {_zc} — Chi tiết theo lớp đất**")
            _rows_ly = []
            for _ly in _chk_all[_zc]["layers"]:
                _p = _ly["params"]
                _rows_ly.append({
                    "Lớp (USCS)": _ly["symbol"],
                    "Đất yếu":    "Có" if _ly["is_soft"] else "-",
                    "n mẫu":      _ly["n_total"],
                    "Cc (n)":     _fmt_p(_p.get("Cc")),
                    "Cc trung bình": round(_p["Cc"]["mean"], 3) if _p.get("Cc", {}).get("n", 0) > 0 else "-",
                    "Cc độ lệch":    round(_p["Cc"]["std"], 3)  if _p.get("Cc", {}).get("n", 0) > 1 else "-",
                    "Cs (n)":     _fmt_p(_p.get("Cs")),
                    "Cv (n)":     _fmt_p(_p.get("Cv")),
                    "PC (n)":     _fmt_p(_p.get("PC")),
                    "phi (n)":    _fmt_p(_p.get("phi")),
                    "c (n)":      _fmt_p(_p.get("c")),
                })
            _df_ly = pd.DataFrame(_rows_ly)
            st.dataframe(
                _df_ly.style.map(_cell_color,
                    subset=["Cc (n)", "Cs (n)", "Cv (n)", "PC (n)"]),
                use_container_width=True, hide_index=True,
            )

        # Tóm tắt 3 khu vực
        st.divider()
        st.markdown("**Tóm tắt 3 khu vực — Thông số lún chính (Cc/Cs/Cv/PC)**")
        _sum_rows = []
        for _zc in ["NHC", "BXN", "KE"]:
            if _zc not in _chk_all:
                continue
            _s = _chk_all[_zc]["zone_summary"]
            _sum_rows.append({
                "Khu vực":      _zc,
                "Lớp yếu":      _s["n_layers_soft"],
                "Cc Đạt/Thiếu": f"{_s['params_ok'].get('Cc',0)}/{_s['params_fail'].get('Cc',0)}",
                "Cs Đạt/Thiếu": f"{_s['params_ok'].get('Cs',0)}/{_s['params_fail'].get('Cs',0)}",
                "Cv Đạt/Thiếu": f"{_s['params_ok'].get('Cv',0)}/{_s['params_fail'].get('Cv',0)}",
                "PC Đạt/Thiếu": f"{_s['params_ok'].get('PC',0)}/{_s['params_fail'].get('PC',0)}",
                "VST":           _chk_all[_zc]["n_vst_zone"],
            })
        if _sum_rows:
            st.dataframe(pd.DataFrame(_sum_rows), use_container_width=True, hide_index=True)
        st.info(
            "Xanh = đủ n≥6 | Đỏ = thiếu mẫu (<6) | '-' = không có mẫu hoặc không áp dụng. "
            "Khu vực KE chưa có mẫu Cc — ưu tiên bổ sung."
        )

    # ── B. TCVN 9403:2012 Bảng B.1 — QC mẫu CDM ────────────────────────────
    st.divider()
    st.markdown("## B. Mẫu kiểm tra chất lượng CDM — TCVN 9403:2012 Bảng B.1")
    st.caption(
        "Bảng B.1: Số mẫu thí nghiệm nén mẫu (phòng) và số mẫu kiểm tra hiện trường "
        "tối thiểu theo số lượng cột CDM thi công. Nhập số liệu để kiểm tra."
    )

    # Bảng yêu cầu Bảng B.1
    _b1_rows = [
        {"Số cột CDM": "≤ 100",      "Mẫu phòng (min/lớp)": 2,  "Kiểm tra hiện trường (min)": 5},
        {"Số cột CDM": "101 – 500",   "Mẫu phòng (min/lớp)": 5,  "Kiểm tra hiện trường (min)": 10},
        {"Số cột CDM": "501 – 1 000", "Mẫu phòng (min/lớp)": 10, "Kiểm tra hiện trường (min)": 30},
        {"Số cột CDM": "1 001 – 2 000","Mẫu phòng (min/lớp)": 15, "Kiểm tra hiện trường (min)": 50},
        {"Số cột CDM": "> 2 000",     "Mẫu phòng (min/lớp)": 20, "Kiểm tra hiện trường (min)": 100},
    ]
    st.dataframe(pd.DataFrame(_b1_rows), use_container_width=True, hide_index=True)

    if not _HAS_9403:
        st.info(
            "Module cdm_column_calc chưa được triển khai. "
            "Phần kiểm tra tự động sẽ khả dụng sau khi thêm file scripts/cdm_column_calc.py."
        )
    else:
        st.markdown("**Nhập số liệu kiểm tra thực tế:**")
        _qc_cols = st.columns(3)
        _qc_zone_inputs = {}
        for _ci, _zc in enumerate(["NHC", "BXN", "KE"]):
            with _qc_cols[_ci]:
                st.markdown(f"**Khu vực {_zc}**")
                _n_col = st.number_input(f"Số cột CDM ({_zc})", 0, 10000, 0, 50,
                                         key=f"qc_ncol_{_zc}")
                _n_lab = st.number_input(f"Mẫu phòng hiện có ({_zc})", 0, 500, 0, 1,
                                         key=f"qc_nlab_{_zc}")
                _n_fld = st.number_input(f"Kiểm tra hiện trường hiện có ({_zc})", 0, 500, 0, 1,
                                         key=f"qc_nfld_{_zc}")
                _qc_zone_inputs[_zc] = (_n_col, _n_lab, _n_fld)

        _qc_result_rows = []
        for _zc, (_nc, _nl, _nf) in _qc_zone_inputs.items():
            if _nc == 0:
                continue
            _res9403 = _chk9403(_nc, _nl, _nf)
            _qc_result_rows.append({
                "Khu vực":           _zc,
                "Số cột":            _nc,
                "Mẫu phòng cần":     _res9403["required_lab"],
                "Mẫu phòng có":      _nl,
                "MP thiếu":          _res9403["lab_gap"],
                "MP kết quả":        "Đạt" if _res9403["lab_ok"] else "Không đạt",
                "KT h.trường cần":   _res9403["required_field"],
                "KT h.trường có":    _nf,
                "KT thiếu":          _res9403["field_gap"],
                "KT kết quả":        "Đạt" if _res9403["field_ok"] else "Không đạt",
            })
        if _qc_result_rows:
            _df_qc = pd.DataFrame(_qc_result_rows)
            st.dataframe(
                _df_qc.style.apply(
                    lambda col: [
                        "background-color:#d4edda" if v == "Đạt"
                        else "background-color:#f8d7da" if v == "Không đạt"
                        else "" for v in col
                    ],
                    subset=["MP kết quả", "KT kết quả"],
                ),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("Nhập số cột CDM > 0 để kiểm tra yêu cầu mẫu theo Bảng B.1.")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2 – THÔNG SỐ
# ═══════════════════════════════════════════════════════════════════════════════
elif _page == "params":
    st.subheader(_t("p2_sub"))

    # ── Lý thuyết tính toán (đặt trên cùng để xem trước khi nhập thông số) ───
    _theory_text = _load_theory()
    if _theory_text:
        with st.expander(_t("theory_exp"), expanded=False):
            st.markdown(_theory_text)

    # Layout: thông số nhập full-width, hình minh họa bên dưới
    _col_inp = st.container()

    with _col_inp:
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.markdown(f"**{_t('cdm_geom')}**")
            D      = st.number_input(_t("D_lbl"), 0.5, 1.2, _get("cdm_D"), 0.05)
            e      = st.number_input("Khoảng cách e (m)", 0.8, 4.0, _get("cdm_e"), 0.1)
            CDTK   = st.number_input(_t("CDTK_lbl"), -5.0, 10.0, _get("cdm_CDTK"), 0.1)
            L_ngam = st.number_input("Ngàm vào đất tốt (m)", 0.0, 5.0, _get("cdm_L_ngam"), 0.1,
                                     help="Chiều dài cọc CDM ngàm vào lớp đất tốt bên dưới lớp bùn")
            _top_clay_c1 = _get("cdm_top_clay")
            _h_clay_c1   = _get("cdm_h_clay")
            _gap_c1      = CDTK - _top_clay_c1          # khoảng từ đỉnh bùn lên đỉnh cọc
            Lc           = round(_gap_c1 + _h_clay_c1 + L_ngam, 1)
            st.info(
                f"Lc = {_gap_c1:.1f} + {_h_clay_c1:.1f} + {L_ngam:.1f} = **{Lc:.1f} m**\n\n"
                f"*(đỉnh bùn→cọc) + h_bùn + ngàm*"
            )
            _ld0 = _get("cdm_loads")
            _He_v  = _ld0.get("h_fill", 1.5)
            _Hse_v = _ld0.get("h_mat",  0.4)
            st.info(f"He = **{_He_v:.2f} m**   |   Hse = **{_Hse_v:.2f} m**")
            arr  = st.radio(_t("arr_lbl"), ["triangle", "square"],
                            format_func=lambda x: _t("arr_tri") if x == "triangle" else _t("arr_sq"),
                            index=["triangle", "square"].index(_get("cdm_arrangement")))
            st.session_state.update({"cdm_D": D, "cdm_e": e, "cdm_L_ngam": L_ngam,
                                      "cdm_Lc": Lc, "cdm_CDTK": CDTK, "cdm_arrangement": arr})

        with c2:
            st.markdown(f"**{_t('material')}**")
            cement = st.text_input(_t("cement_lbl"), _get("cdm_cement_type"))
            dosage = st.number_input(_t("dosage_lbl"), 100, 400, _get("cdm_dosage"), 10)
            WC     = st.number_input(_t("wc_lbl"), 0.5, 2.0, _get("cdm_WC"), 0.1)
            qu     = st.number_input(_t("qu_lbl"), 100.0, 5000.0, _get("cdm_qu"), 50.0)
            FS_lab = st.number_input(_t("fs_lab"), 1.0, 5.0, _get("cdm_FS_lab"), 0.1)
            Cc = qu / 2
            Ec = 100 * Cc
            st.info(f"Cc = {Cc:.0f} kN/m²  |  Ec = {int(Ec):,} kN/m²")
            st.session_state.update({"cdm_cement_type": cement, "cdm_dosage": dosage,
                                      "cdm_WC": WC, "cdm_qu": qu, "cdm_FS_lab": FS_lab})

        with c3:
            st.markdown(f"**{_t('geo_params')}**")
            top_clay = st.number_input(_t("top_clay_lbl"), -20.0, 20.0,
                                       _get("cdm_top_clay"), 0.1)
            h_clay  = st.number_input(_t("h_clay_lbl"), 1.0, 60.0, _get("cdm_h_clay"), 0.5)
            Su      = st.number_input(_t("su_lbl"), 1.0, 100.0, _get("cdm_Su"), 0.5)
            gamma   = st.number_input(_t("gamma_lbl"), 10.0, 22.0, _get("cdm_gamma"), 0.1)
            st.info(_t("bot_clay_info", v=top_clay - h_clay))
            Es_show = 250 * Su
            st.info(f"Es = 250×Su = {int(Es_show):,} kN/m²")
            st.session_state.update({"cdm_top_clay": top_clay, "cdm_h_clay": h_clay,
                                     "cdm_Su": Su, "cdm_gamma": gamma})

        with c4:
            st.markdown(f"**{_t('loads_title')}**")
            ld = _get("cdm_loads").copy()
            ld["q_traffic"] = st.number_input(_t("q_traf"), 0.0, 200.0,
                                              ld.get("q_traffic", 20.0), 5.0)
            ld["z_tk"] = st.number_input(
                "Cao độ thiết kế (m)",
                -5.0, 20.0, ld.get("z_tk", 3.5), 0.1,
                help="Cao độ đỉnh mặt đường thiết kế",
            )
            _top_clay_now = _get("cdm_top_clay")
            _cdtk_now     = _get("cdm_CDTK")
            _H = ld["z_tk"] - _top_clay_now
            if _H < 0:
                st.error("Cao độ TK thấp hơn đỉnh bùn → H < 0")
            _hdr_style = "font-size:12px; font-weight:600; color:#444; margin-bottom:2px"
            _cl, _ch, _cg = st.columns([1.5, 1, 1])
            _ch.markdown(f"<div style='{_hdr_style}'>h (m)</div>", unsafe_allow_html=True)
            _cg.markdown(f"<div style='{_hdr_style}'>γ (kN/m³)</div>", unsafe_allow_html=True)

            _cl, _ch, _cg = st.columns([1.5, 1, 1])
            _cl.markdown(_t("pavement"))
            ld["h_road"] = _ch.number_input("h_road", 0.0, 2.0, ld.get("h_road", 0.8), 0.1, key="h_road", label_visibility="collapsed")
            ld["g_road"] = _cg.number_input("g_road", 10.0, 30.0, ld.get("g_road", 24.0), 0.5, key="g_road", label_visibility="collapsed")

            _cl, _ch, _cg = st.columns([1.5, 1, 1])
            _cl.markdown("*He — cát đắp:*")
            ld["h_fill"] = _ch.number_input("h_fill", 0.0, 5.0, ld.get("h_fill", 1.5), 0.1, key="h_fill", label_visibility="collapsed")
            ld["g_fill"] = _cg.number_input("g_fill", 10.0, 24.0, ld.get("g_fill", 18.0), 0.5, key="g_fill", label_visibility="collapsed")

            _cl, _ch, _cg = st.columns([1.5, 1, 1])
            _cl.markdown("*Hse — đệm cát:*")
            ld["h_mat"] = _ch.number_input("h_mat", 0.0, 2.0, ld.get("h_mat", 0.4), 0.1, key="h_mat", label_visibility="collapsed")
            ld["g_mat"] = _cg.number_input("g_mat", 10.0, 26.0, ld.get("g_mat", 22.5), 0.5, key="g_mat", label_visibility="collapsed")

            # Ràng buộc: z_tk = CDTK + Hse + He + h_đường
            _Hse       = ld["h_mat"]
            _He        = ld["h_fill"]
            _h_road    = ld["h_road"]
            _fill_gap  = _cdtk_now - _top_clay_now          # cát đắp từ đỉnh bùn lên đỉnh cọc
            _H_parts   = _fill_gap + _Hse + _He + _h_road   # H theo hình học
            _z_road_calc = _cdtk_now + _Hse + _He + _h_road
            st.info(
                f"H = (CDTK − đỉnh bùn) + Hse + He + h_đường\n\n"
                f"= {_fill_gap:.2f} + {_Hse:.2f} + {_He:.2f} + {_h_road:.2f} = **{_H_parts:.2f} m**"
            )
            _dz = ld["z_tk"] - _z_road_calc
            if abs(_dz) > 0.05:
                st.warning(
                    f"Cao độ TK nhập ({ld['z_tk']:+.2f} m) ≠ "
                    f"CDTK + Hse + He + h_đường = **{_z_road_calc:+.2f} m** (Δ = {_dz:+.2f} m)."
                )
                if st.button("Đồng bộ cao độ TK = hình học", key="sync_ztk"):
                    ld["z_tk"] = round(_z_road_calc, 2)
                    st.session_state["cdm_loads"] = ld
                    st.rerun()
            q_tot = q_total(ld)
            st.success(f"**q = {q_tot:.2f} kN/m²**")
            st.session_state["cdm_loads"] = ld

    # ── Bảng thông số địa chất (từ hố khoan đã áp dụng) ────────────────────────
    _p_bh = _get("cdm_bh")
    if _p_bh:
        _p_layers = _load_layers(_p_bh)
        if _p_layers:
            _p_zone = _get("cdm_zone")
            _p_rows = []
            _p_borrowed = False
            for _lr in _p_layers:
                _sym = _lr.get("symbol") or ""
                _Cc  = _lr.get("Cc");  _Cs = _lr.get("Cs")
                _e0  = _lr.get("e0");  _PC = _lr.get("PC_kPa")
                _Cv  = _lr.get("Cv_cm2s"); _gam = _lr.get("gamma_kNm3")
                _src = ""
                if _Cc is None or _e0 is None:
                    _fb = _load_zone_params_by_symbol(_p_zone, _sym)
                    if _fb:
                        _Cc  = _Cc  if _Cc  is not None else _fb.get("Cc")
                        _Cs  = _Cs  if _Cs  is not None else _fb.get("Cs")
                        _e0  = _e0  if _e0  is not None else _fb.get("e0")
                        _PC  = _PC  if _PC  is not None else _fb.get("PC_kPa")
                        _Cv  = _Cv  if _Cv  is not None else _fb.get("Cv_cm2s")
                        _gam = _gam if _gam is not None else _fb.get("gamma_kNm3")
                        _src = _fb.get("source_bh") or ""
                        if _src:
                            _p_borrowed = True
                _p_rows.append({
                    "Lớp":         _sym,
                    "Mô tả":       (_lr.get("description") or "")[:30],
                    "h (m)":       _lr.get("thickness_m"),
                    "γ (kN/m³)":  _gam,
                    "e0":          _e0,
                    "Cc":          _Cc,
                    "Cs":          _Cs,
                    "PC (kPa)":   _PC,
                    "Cv (cm²/s)": f"{_Cv:.2e}" if _Cv is not None else "—",
                    "_src":        _src,
                })
            _df_p = pd.DataFrame(_p_rows)
            _src_map_p = _df_p["_src"].to_dict()
            def _hl_p(row):
                return ["background-color:#FFF8DC"]*len(row) if _src_map_p.get(row.name) else [""]*len(row)
            with st.expander(f"Thông số địa chất — {_p_bh}", expanded=True):
                st.dataframe(
                    _df_p.drop(columns=["_src"]).style.apply(_hl_p, axis=1),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "h (m)":     st.column_config.NumberColumn(format="%.2f"),
                        "γ (kN/m³)":st.column_config.NumberColumn(format="%.2f"),
                        "e0":        st.column_config.NumberColumn(format="%.3f"),
                        "Cc":        st.column_config.NumberColumn(format="%.4f"),
                        "Cs":        st.column_config.NumberColumn(format="%.4f"),
                        "PC (kPa)": st.column_config.NumberColumn(format="%.1f"),
                    },
                )
                if _p_borrowed:
                    st.caption("*Ô nền vàng: tham khảo từ hố khoan khác cùng khu vực.*")

    # ── Kiểm tra ràng buộc số liệu ──────────────────────────────────────────────
    _vc_top  = _get("cdm_top_clay")
    _vc_CDTK = _get("cdm_CDTK")
    _vc_Lc   = _get("cdm_Lc")
    _vc_hc   = _get("cdm_h_clay")
    _vc_zpb  = _vc_CDTK - _vc_Lc          # đáy cọc
    _vc_zcb  = _vc_top  - _vc_hc          # đáy bùn
    _vc_emb  = _vc_zcb  - _vc_zpb         # ngàm vào đất tốt

    if _vc_top > _vc_CDTK + 0.05:
        st.error(
            f"Đỉnh lớp bùn ({_vc_top:+.2f} m) cao hơn đỉnh cọc CDM ({_vc_CDTK:+.2f} m). "
            "Hình vẽ sẽ sai — giảm 'Cao độ đỉnh lớp bùn' hoặc tăng 'Cao độ đỉnh cọc CDM'."
        )
    if _vc_emb <= 0:
        st.error(
            f"Mũi cọc ({_vc_zpb:+.2f} m) chưa qua đáy bùn ({_vc_zcb:+.2f} m). "
            f"Cần Lc > {_vc_CDTK - _vc_zcb:.1f} m để cọc ngàm vào đất tốt."
        )
    elif _vc_emb < 0.5:
        st.warning(
            f"Ngàm cọc vào đất tốt chỉ {_vc_emb:.2f} m — khuyến nghị ≥ 0.5 m "
            f"(Lc hiện = {_vc_Lc:.1f} m, cần ≥ {_vc_Lc + (0.5 - _vc_emb):.1f} m)."
        )

    # ── Hình minh họa bên dưới: mặt cắt (trái) + lưới mặt bằng (phải) ────────
    _col_sec, _col_grd = st.columns(2, gap="medium")

    with _col_sec:
        _ld_s = _get("cdm_loads")
        _fig_sec = _draw_cdm_section(
            D=_get("cdm_D"), Lc=_get("cdm_Lc"), CDTK=_get("cdm_CDTK"),
            h_clay=_get("cdm_h_clay"),
            h_road=_ld_s.get("h_road", 0.8),
            h_fill=_ld_s.get("h_fill", 1.5),
            h_mat=_ld_s.get("h_mat", 0.4),
            q_traffic=_ld_s.get("q_traffic", 20.0),
            top_clay=_get("cdm_top_clay"),
        )
        st.pyplot(_fig_sec, use_container_width=True)
        _fig_sec.clf()

    with _col_grd:
        # Hình lưới ở tab Thông số dùng e do user nhập trực tiếp (cdm_e)
        # — KHÔNG dùng cdm_spacings[rec_idx] (đó là kết quả từ tab So sánh)
        _e_ref_now = _get("cdm_e")
        _fig_grd = _draw_cdm_grid(_get("cdm_D"), _get("cdm_arrangement"), _e_ref_now)
        st.pyplot(_fig_grd, use_container_width=True)
        _fig_grd.clf()

    # ── Xuất PDF tab này ──────────────────────────────────────────────────────
    if _HAS_PDF:
        st.divider()
        try:
            _pdf_p = _pdf_params(dict(st.session_state))
            st.download_button(
                "Xuất PDF tab Thông số CDM",
                data=_pdf_p,
                file_name=f"ThongSoCDM_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as _e:
            st.warning(f"Không tạo PDF: {_e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3 – SO SÁNH PHƯƠNG ÁN
# ═══════════════════════════════════════════════════════════════════════════════
elif _page == "compare":
    st.subheader(_t("p3_sub"))

    # Input khoảng cách + thông số đệm xi măng
    with st.expander(_t("setup_exp"), expanded=True):
        _col_sp, _col_mat = st.columns([3, 2], gap="large")

        with _col_sp:
            st.markdown(f"**{_t('sp_title')}**")
            _auto_lbl, _manual_lbl = _t("auto_lbl"), _t("manual_lbl")
            mode = st.radio("", [_auto_lbl, _manual_lbl],
                            horizontal=True, label_visibility="collapsed",
                            key="_sp_mode")
            if mode == _auto_lbl:
                _sc1, _sc2, _sc3 = st.columns(3)
                e_min  = _sc1.number_input(_t("e_min"), 1.0, 3.0, 1.2, 0.1)
                e_max  = _sc2.number_input(_t("e_max"), 1.0, 4.0, 2.0, 0.1)
                e_step = _sc3.number_input(_t("step_lbl"), 0.1, 1.0, 0.2, 0.1)
                spacings = [round(e_min + i * e_step, 2)
                            for i in range(int(round((e_max - e_min) / e_step)) + 1)]
            else:
                raw = st.text_input(_t("sp_list"),
                                    ", ".join(str(s) for s in _get("cdm_spacings")),
                                    label_visibility="visible")
                try:
                    spacings = [float(x.strip()) for x in raw.split(",") if x.strip()]
                except ValueError:
                    spacings = _get("cdm_spacings")
            spacings = sorted(set(spacings))
            st.session_state["cdm_spacings"] = spacings
            _alts_label = "Các phương án" if _get("lang") == "VN" else "Alternatives"
            st.caption(f"{_alts_label}: {', '.join(f'{e}m' for e in spacings)}")

        with _col_mat:
            st.markdown(f"**{_t('mat_punch')}**")
            _mc1, _mc2 = st.columns(2)
            with _mc1:
                _quckse_sp = st.number_input(_t("qu_mat_sp"), 100.0, 3000.0,
                                             _get("cdm_quckse"), 50.0,
                                             key="_sp_quckse")
                _theta_sp  = st.number_input("θ (°)", 30.0, 89.0,
                                             _get("cdm_theta"), 5.0,
                                             key="_sp_theta")
            with _mc2:
                _Fs_sp     = st.number_input("Fs", 1.0, 5.0,
                                             _get("cdm_Fs_mat"), 0.5,
                                             key="_sp_Fs")
                _qa_sp     = st.number_input("qa (kPa)", 0.0, 200.0,
                                             _get("cdm_qa_mat"), 5.0,
                                             key="_sp_qa")
            _tase_sp = _quckse_sp / (2.0 * _Fs_sp)
            st.info(f"τase = qu/(2·Fs) = **{_tase_sp:.1f} kPa**")
            st.session_state.update({
                "cdm_quckse": _quckse_sp,
                "cdm_Fs_mat": _Fs_sp,
                "cdm_theta":  _theta_sp,
                "cdm_qa_mat": _qa_sp,
            })

    # Hình minh họa phương pháp tính (40% width mỗi cột)
    _img_load = _ROOT / "giao dien" / "PNBAY-TAI TRONG NEN DAP LEN PHAN KHÔNG GIA CO.png"
    _img_tse  = _ROOT / "giao dien" / "PNBAY-Tse.png"
    _ic1, _ic2 = st.columns(2)
    if _img_load.exists():
        with _ic1:
            _s1, _ = st.columns([2, 3])
            _s1.image(str(_img_load), use_container_width=True)
    if _img_tse.exists():
        with _ic2:
            _s2, _ = st.columns([2, 3])
            _s2.image(str(_img_tse), use_container_width=True)

    # Tính toán
    D   = _get("cdm_D")
    Lc  = _get("cdm_Lc")
    qu  = _get("cdm_qu")
    Su  = _get("cdm_Su")
    arr = _get("cdm_arrangement")
    q   = q_total(_get("cdm_loads"))

    scenarios = build_scenarios(D, Lc, qu, Su, q, spacings, arr)
    df = pd.DataFrame(scenarios)

    # Chọn PA kiến nghị
    _alt_prefix = "PA" if _get("lang") == "VN" else "Alt."
    rec_idx = st.selectbox(
        _t("rec_sel"),
        range(len(scenarios)),
        index=min(_get("cdm_rec_idx"), len(scenarios)-1),
        format_func=lambda i: f"{_alt_prefix}{i+1}: e={scenarios[i]['e (m)']}m  →  S₁={scenarios[i]['S₁ (cm)']:.2f}cm",
    )
    st.session_state["cdm_rec_idx"] = rec_idx

    # Tính kiểm tra chọc thủng cho mỗi PA
    _ld_punch = _get("cdm_loads")
    _punch = [
        calc_punching_check(
            D=D, e=s["e (m)"],
            Hse=_ld_punch.get("h_mat", 0.4),
            He=_ld_punch.get("h_fill", 1.5),
            quckse=_get("cdm_quckse"),
            Fs=_get("cdm_Fs_mat"),
            theta_deg=_get("cdm_theta"),
            gamma_fill=_ld_punch.get("g_fill", 18.0),
            gamma_mat=_ld_punch.get("g_mat", 22.5),
            qa=_get("cdm_qa_mat"),
        )
        for s in scenarios
    ]
    for i, pr in enumerate(_punch):
        df.at[i, "τse (kPa)"]  = pr["tse_kPa"]
        df.at[i, "τase (kPa)"] = pr["tase_kPa"]
        df.at[i, "Đạt CT"]     = pr["check_CT"]

    # Bảng kết quả
    st.markdown(f"**{_t('pa_table')}**")
    display_cols = ["e (m)", "a (%)", "Etb (kN/m²)", "S₁ (cm)",
                    "Pcol (kN)", "Qa (kN)", "Đạt SCT",
                    "τse (kPa)", "τase (kPa)", "Đạt CT"]

    def _row_color(row):
        idx = df.index.get_loc(row.name)
        if idx == rec_idx:
            return ["background-color: #E2EFDA"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df[display_cols].style.apply(_row_color, axis=1)
                               .format({"a (%)": "{:.1f}%",
                                        "Etb (kN/m²)": "{:,.0f}",
                                        "S₁ (cm)": "{:.2f}",
                                        "Pcol (kN)": "{:.1f}",
                                        "Qa (kN)": "{:.1f}"}),
        use_container_width=True,
    )

    if _HAS_PLOTLY:
        ca, cb, cc = st.columns(3)
        with ca:
            st.plotly_chart(_chart_scenarios(df, rec_idx), use_container_width=True)
        with cb:
            st.plotly_chart(_chart_etb(df, rec_idx), use_container_width=True)
        with cc:
            st.plotly_chart(_chart_combined(df, rec_idx), use_container_width=True)

        # Biểu đồ chọc thủng
        _x_sp = [f"e={s['e (m)']}m" for s in scenarios]
        _col_ct = ["#ED7D31" if i == rec_idx else "#4472C4" for i in range(len(scenarios))]
        _tase_v = _punch[0]["tase_kPa"] if _punch else 100.0
        _fig_ct = go.Figure()
        _fig_ct.add_trace(go.Bar(
            name="τse (kPa)", x=_x_sp,
            y=[pr["tse_kPa"] for pr in _punch],
            marker_color=_col_ct,
            text=[f"{pr['tse_kPa']:.1f}" for pr in _punch],
            textposition="outside",
        ))
        _fig_ct.add_hline(
            y=_tase_v, line_dash="dash", line_color="#E53935", line_width=1.5,
            annotation_text=f"τase = {_tase_v:.0f} kPa",
            annotation_position="top right",
        )
        _fig_ct.update_layout(
            title=_t("punch_chart"),
            yaxis_title=_t("shear_ax"),
            height=340, margin=dict(t=45, b=20),
            showlegend=False,
        )
        st.plotly_chart(_fig_ct, use_container_width=True)

    # ── Phân tích tham số ─────────────────────────────────────────────────────
    st.divider()
    st.markdown(f"### {_t('param_sens')}")

    _e_rec   = scenarios[rec_idx]["e (m)"]
    _ld_base = _get("cdm_loads").copy()
    _hmat_cur = _ld_base.get("h_mat", 0.4)

    _pa1, _pa2, _pa3 = st.columns(3)

    # ── 1. So sánh qu ─────────────────────────────────────────────────────────
    with _pa1:
        st.markdown(f"**{_t('qu_comp')}**")
        _qu_raw = st.text_input(_t("qu_inp"),
                                ", ".join(str(v) for v in [200, 300, 400, 500, 600, 700]),
                                key="_qu_list")
        try:
            _qu_list = sorted(set(float(x.strip()) for x in _qu_raw.split(",") if x.strip()))
        except ValueError:
            _qu_list = [200, 300, 400, 500]

        _qu_rows = []
        for _qv in _qu_list:
            _Ec_v  = calc_Ec(_qv)
            _Es_v  = calc_Es(Su)
            _a_v   = calc_a(D, _e_rec, arr)
            _Etb_v = calc_Etb(_a_v, _Ec_v, _Es_v)
            _S1_v  = calc_S1(q, Lc, _Etb_v)
            _sc_v  = calc_sigma_col(q, _Ec_v, _Etb_v)
            _Pcol_v = calc_Pcol(_sc_v, D)
            _bc_v  = calc_bearing(D, Lc, _qv / 2, Su)
            _qu_rows.append({
                "qu (kPa)": int(_qv),
                "Ec (kN/m²)": int(_Ec_v),
                "Etb (kN/m²)": int(_Etb_v),
                "S₁ (cm)": round(_S1_v, 2),
                "Pcol (kN)": round(_Pcol_v, 1),
                "Qa (kN)": _bc_v["Qa"],
                "Đạt SCT": "Đạt" if _Pcol_v < _bc_v["Qa"] else "Không đạt",
            })
        _df_qu = pd.DataFrame(_qu_rows)
        st.dataframe(_df_qu, use_container_width=True, hide_index=True,
                     column_config={"Etb (kN/m²)": st.column_config.NumberColumn(format="%,d"),
                                    "Ec (kN/m²)":  st.column_config.NumberColumn(format="%,d")})
        if _HAS_PLOTLY:
            _col_qu = ["#ED7D31" if r["qu (kPa)"] == int(qu) else "#4472C4"
                       for r in _qu_rows]
            _fig_qu = go.Figure(go.Bar(
                x=[f"{r['qu (kPa)']} kPa" for r in _qu_rows],
                y=_df_qu["S₁ (cm)"],
                marker_color=_col_qu,
                text=_df_qu["S₁ (cm)"].apply(lambda v: f"{v:.2f}"),
                textposition="outside",
            ))
            _fig_qu.update_layout(
                title=f"S₁ theo qu  (e={_e_rec}m, D={D}m)",
                yaxis_title="S₁ (cm)", height=300,
                margin=dict(t=45, b=20),
            )
            st.plotly_chart(_fig_qu, use_container_width=True)

    # ── 2. So sánh D ──────────────────────────────────────────────────────────
    with _pa2:
        st.markdown(f"**{_t('D_comp')}**")
        _D_raw = st.text_input(_t("D_inp"), "0.50, 0.60, 0.70, 0.80, 1.00",
                               key="_D_list")
        try:
            _D_list = sorted(set(float(x.strip()) for x in _D_raw.split(",") if x.strip()))
        except ValueError:
            _D_list = [0.5, 0.6, 0.7, 0.8]

        _D_rows = []
        for _Dv in _D_list:
            _Ec_v  = calc_Ec(qu)
            _Es_v  = calc_Es(Su)
            _a_v   = calc_a(_Dv, _e_rec, arr)
            _Etb_v = calc_Etb(_a_v, _Ec_v, _Es_v)
            _S1_v  = calc_S1(q, Lc, _Etb_v)
            _sc_v  = calc_sigma_col(q, _Ec_v, _Etb_v)
            _Pcol_v = calc_Pcol(_sc_v, _Dv)
            _bc_v  = calc_bearing(_Dv, Lc, qu / 2, Su)
            _D_rows.append({
                "D (m)": _Dv,
                "a (%)": round(_a_v * 100, 1),
                "Etb (kN/m²)": int(_Etb_v),
                "S₁ (cm)": round(_S1_v, 2),
                "Pcol (kN)": round(_Pcol_v, 1),
                "Qa (kN)": _bc_v["Qa"],
                "Đạt SCT": "Đạt" if _Pcol_v < _bc_v["Qa"] else "Không đạt",
            })
        _df_D = pd.DataFrame(_D_rows)
        st.dataframe(_df_D, use_container_width=True, hide_index=True,
                     column_config={"a (%)": st.column_config.NumberColumn(format="%.1f%%"),
                                    "Etb (kN/m²)": st.column_config.NumberColumn(format="%,d")})
        if _HAS_PLOTLY:
            _col_D = ["#ED7D31" if abs(_Dv - D) < 0.001 else "#4472C4"
                      for _Dv in _D_list]
            _fig_D = go.Figure()
            _fig_D.add_trace(go.Bar(
                name="a (%)",
                x=[f"{r['D (m)']}m" for r in _D_rows],
                y=_df_D["a (%)"],
                marker_color=_col_D,
                text=_df_D["a (%)"].apply(lambda v: f"{v:.1f}%"),
                textposition="outside",
                yaxis="y1",
            ))
            _fig_D.add_trace(go.Scatter(
                name="S₁ (cm)",
                x=[f"{r['D (m)']}m" for r in _D_rows],
                y=_df_D["S₁ (cm)"],
                mode="lines+markers+text",
                text=_df_D["S₁ (cm)"].apply(lambda v: f"{v:.2f}"),
                textposition="top center",
                yaxis="y2",
                line=dict(color="#E53935", width=2),
                marker=dict(size=8, color="#E53935"),
            ))
            _fig_D.update_layout(
                title=f"a(%) và S₁ theo D  (e={_e_rec}m, qu={int(qu)}kPa)",
                yaxis=dict(title="a (%)"),
                yaxis2=dict(title="S₁ (cm)", overlaying="y", side="right"),
                height=300, margin=dict(t=45, b=20),
                legend=dict(orientation="h"),
            )
            st.plotly_chart(_fig_D, use_container_width=True)

    # ── 3. So sánh h_mat ──────────────────────────────────────────────────────
    with _pa3:
        st.markdown(f"**{_t('hmat_comp')}**")
        _hm_raw = st.text_input(_t("hmat_inp"), "0.20, 0.30, 0.40, 0.50, 0.60, 0.80",
                                key="_hmat_list")
        try:
            _hmat_list = sorted(set(float(x.strip()) for x in _hm_raw.split(",") if x.strip()))
        except ValueError:
            _hmat_list = [0.2, 0.3, 0.4, 0.5]

        _hm_rows = []
        for _hm in _hmat_list:
            _ld_v = _ld_base.copy()
            _ld_v["h_mat"] = _hm
            _q_v   = q_total(_ld_v)
            _Ec_v  = calc_Ec(qu)
            _Es_v  = calc_Es(Su)
            _a_v   = calc_a(D, _e_rec, arr)
            _Etb_v = calc_Etb(_a_v, _Ec_v, _Es_v)
            _S1_v  = calc_S1(_q_v, Lc, _Etb_v)
            _hm_rows.append({
                "h_mat (m)": _hm,
                "q (kN/m²)": round(_q_v, 2),
                "ΔS₁ (cm)": round(_S1_v, 2),
            })
        _df_hm = pd.DataFrame(_hm_rows)
        st.dataframe(_df_hm, use_container_width=True, hide_index=True)
        if _HAS_PLOTLY:
            _col_hm = ["#ED7D31" if abs(_hm - _hmat_cur) < 0.001 else "#4472C4"
                       for _hm in _hmat_list]
            _fig_hm = go.Figure()
            _fig_hm.add_trace(go.Bar(
                name="q (kN/m²)",
                x=[f"{r['h_mat (m)']}m" for r in _hm_rows],
                y=_df_hm["q (kN/m²)"],
                marker_color=_col_hm,
                text=_df_hm["q (kN/m²)"].apply(lambda v: f"{v:.1f}"),
                textposition="outside",
                yaxis="y1",
            ))
            _fig_hm.add_trace(go.Scatter(
                name="S₁ (cm)",
                x=[f"{r['h_mat (m)']}m" for r in _hm_rows],
                y=_df_hm["ΔS₁ (cm)"],
                mode="lines+markers+text",
                text=_df_hm["ΔS₁ (cm)"].apply(lambda v: f"{v:.2f}"),
                textposition="top center",
                yaxis="y2",
                line=dict(color="#E53935", width=2),
                marker=dict(size=8, color="#E53935"),
            ))
            _fig_hm.update_layout(
                title=f"q và S₁ theo h_mat  (e={_e_rec}m, D={D}m)",
                yaxis=dict(title="q (kN/m²)"),
                yaxis2=dict(title="S₁ (cm)", overlaying="y", side="right"),
                height=300, margin=dict(t=45, b=20),
                legend=dict(orientation="h"),
            )
            st.plotly_chart(_fig_hm, use_container_width=True)

    # ── Kết quả chi tiết PA kiến nghị ─────────────────────────────────────────
    st.divider()
    st.subheader(_t("p4_sub"))

    s   = scenarios[rec_idx]
    Cc  = qu / 2
    Ec  = calc_Ec(qu)
    Es  = calc_Es(Su)
    Etb = s["Etb (kN/m²)"]

    _CP = _t("col_param"); _CF = _t("col_formula"); _CV = _t("col_value")

    def _color_sct(val):
        if val == "Đạt":       return "color: green; font-weight: bold"
        if val == "Không đạt": return "color: red; font-weight: bold"
        return ""

    st.success(_t("rec_pa", n=rec_idx+1, e=s['e (m)']))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("S₁ (cm)", f"{s['S₁ (cm)']:.2f}")
    c2.metric("Etb (kN/m²)", f"{int(Etb):,}")
    c3.metric("a (%)", f"{s['a (%)']:.1f}%")
    c4.metric("Sức chịu tải", s["Đạt SCT"])

    st.divider()
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(f"**{_t('settle_calc')}**")
        _is_tri = arr == "triangle"
        arr_label = (_t("arr_tri") + ": a = π·D²/(2√3·e²)"
                     if _is_tri else _t("arr_sq") + ": a = π·D²/(4·e²)")
        if _get("lang") == "VN":
            steps = [
                ("Khoảng cách trụ", "e", f"{s['e (m)']} m"),
                ("Tỷ lệ thay thế", arr_label, f"{s['a']:.4f}  ({s['a (%)']:.1f}%)"),
                ("Mô đun trụ CDM", "Ec = 100·Cc = 100·(qu/2)", f"{int(Ec):,} kN/m²"),
                ("Mô đun đất nền", "Es = 250·Su", f"{int(Es):,} kN/m²"),
                ("Mô đun tương đương", "Etb = a·Ec + (1−a)·Es", f"{int(Etb):,} kN/m²"),
                ("Tải trọng thiết kế", "q", f"{q:.2f} kN/m²"),
                ("Chiều dài trụ", "Lc", f"{Lc:.1f} m"),
                ("Độ lún bản thân CDM", "S₁ = q·Lc/Etb × 100", f"{s['S₁ (cm)']:.2f} cm"),
                ("Độ lún dưới mũi trụ", "S₂ = 0 (trụ xuyên qua lớp bùn)", "0,00 cm"),
                ("Tổng độ lún", "S = S₁ + S₂", f"{s['S₁ (cm)']:.2f} cm"),
            ]
        else:
            steps = [
                ("Pile spacing", "e", f"{s['e (m)']} m"),
                ("Area replacement ratio", arr_label, f"{s['a']:.4f}  ({s['a (%)']:.1f}%)"),
                ("CDM column modulus", "Ec = 100·Cc = 100·(qu/2)", f"{int(Ec):,} kN/m²"),
                ("Soil modulus", "Es = 250·Su", f"{int(Es):,} kN/m²"),
                ("Equivalent modulus", "Etb = a·Ec + (1−a)·Es", f"{int(Etb):,} kN/m²"),
                ("Design load", "q", f"{q:.2f} kN/m²"),
                ("Pile length", "Lc", f"{Lc:.1f} m"),
                ("CDM block settlement", "S₁ = q·Lc/Etb × 100", f"{s['S₁ (cm)']:.2f} cm"),
                ("Settlement below pile tip", "S₂ = 0 (pile through soft clay)", "0.00 cm"),
                ("Total settlement", "S = S₁ + S₂", f"{s['S₁ (cm)']:.2f} cm"),
            ]
        df_steps = pd.DataFrame(steps, columns=[_CP, _CF, _CV])
        st.dataframe(df_steps, use_container_width=True, hide_index=True,
                     column_config={_CF: st.column_config.TextColumn(width="medium")})

    with col_r:
        st.markdown(f"**{_t('bearing_calc')}**")
        bc = calc_bearing(D, Lc, Cc, Su)
        if _get("lang") == "VN":
            sct_steps = [
                ("Diện tích cắt ngang", "Ac = π·D²/4", f"{math.pi*D**2/4:.4f} m²"),
                ("Sức chịu tải mũi", "Qult_mũi = 9·Cc·Ac", f"{bc['Qult_col']:.1f} kN"),
                ("Sức chịu tải thân", "Qult_thân = π·D·Lc·Cu", f"{bc['Qult_skin']:.1f} kN"),
                ("Tổng sức chịu tải", "Qult = Qmũi + Qthân", f"{bc['Qult']:.1f} kN"),
                ("Sức chịu tải cho phép", "Qa = Qult / FS = Qult / 2", f"{bc['Qa']:.1f} kN"),
                ("Ứng suất đầu cọc", "σ_col = (Ec/Etb) × q", f"{s['σ_col (kN/m²)']:.1f} kN/m²"),
                ("Lực nén lên 1 trụ", "Pcol = σ_col × Ac", f"{s['Pcol (kN)']:.1f} kN"),
                ("Kiểm tra", "Pcol < Qa ?", s["Đạt SCT"]),
            ]
        else:
            sct_steps = [
                ("Cross-section area", "Ac = π·D²/4", f"{math.pi*D**2/4:.4f} m²"),
                ("Tip resistance", "Qult_tip = 9·Cc·Ac", f"{bc['Qult_col']:.1f} kN"),
                ("Skin resistance", "Qult_skin = π·D·Lc·Cu", f"{bc['Qult_skin']:.1f} kN"),
                ("Total capacity", "Qult = Qtip + Qskin", f"{bc['Qult']:.1f} kN"),
                ("Allowable capacity", "Qa = Qult / FS = Qult / 2", f"{bc['Qa']:.1f} kN"),
                ("Stress on pile head", "σ_col = (Ec/Etb) × q", f"{s['σ_col (kN/m²)']:.1f} kN/m²"),
                ("Load on single pile", "Pcol = σ_col × Ac", f"{s['Pcol (kN)']:.1f} kN"),
                ("Check", "Pcol < Qa ?", s["Đạt SCT"]),
            ]
        df_sct = pd.DataFrame(sct_steps, columns=[_CP, _CF, _CV])

        def _color_sct(val):
            if val == "Đạt":       return "color: green; font-weight: bold"
            if val == "Không đạt": return "color: red; font-weight: bold"
            return ""

        st.dataframe(df_sct.style.map(_color_sct, subset=[_CV]),
                     use_container_width=True, hide_index=True,
                     column_config={_CF: st.column_config.TextColumn(width="medium")})

    st.divider()
    st.markdown(f"**{_t('punch_res')}**")
    _ld_r   = _get("cdm_loads")
    _pr_r   = _punch[rec_idx]
    if _get("lang") == "VN":
        _punch_steps = [
            ("Bề dày đệm xi măng",        "Hse",                                f"{_ld_r.get('h_mat',0.4):.2f} m"),
            ("Chiều cao đất đắp trên đệm", "He = h_fill",                        f"{_ld_r.get('h_fill',1.5):.2f} m"),
            ("Cường độ kháng nén đệm XM",  "quckse",                             f"{_get('cdm_quckse'):.0f} kPa"),
            ("Ứng suất cắt cho phép",      "τase = quckse/(2·Fs)",               f"{_pr_r['tase_kPa']:.2f} kPa"),
            ("Chiều cao vùng vòm đất",     "Ho = (e−D)·tan(θ/2)",                f"{_pr_r['Ho_m']:.3f} m"),
            ("So sánh Ho vs He",           "Chọn công thức",                     _pr_r["cong_thuc"]),
            ("Thể tích đất tác dụng",      "Vsoil",                              f"{_pr_r['Vsoil_m3']:.4f} m³"),
            ("Thể tích đệm XM tác dụng",   "VCGCXM",                             f"{_pr_r['VCGCXM_m3']:.4f} m³"),
            ("Áp lực vùng không gia cố",   "PSoil",                              f"{_pr_r['PSoil_kPa']:.3f} kPa"),
            ("Ứng suất cắt thực tế",       "τse = PSoil·(e²−πD²/4)/(π·D·Hse)",  f"{_pr_r['tse_kPa']:.3f} kPa"),
            ("Kiểm tra",                   "τse ≤ τase ?",                       _pr_r["check_CT"]),
        ]
    else:
        _punch_steps = [
            ("Cement mat thickness",       "Hse",                                f"{_ld_r.get('h_mat',0.4):.2f} m"),
            ("Fill height above mat",      "He = h_fill",                        f"{_ld_r.get('h_fill',1.5):.2f} m"),
            ("Cement mat strength",        "quckse",                             f"{_get('cdm_quckse'):.0f} kPa"),
            ("Allowable shear stress",     "τase = quckse/(2·Fs)",               f"{_pr_r['tase_kPa']:.2f} kPa"),
            ("Arch height",               "Ho = (e−D)·tan(θ/2)",                f"{_pr_r['Ho_m']:.3f} m"),
            ("Ho vs He comparison",        "Select formula",                     _pr_r["cong_thuc"]),
            ("Soil volume acting",         "Vsoil",                              f"{_pr_r['Vsoil_m3']:.4f} m³"),
            ("Cement mat volume acting",   "VCGCXM",                             f"{_pr_r['VCGCXM_m3']:.4f} m³"),
            ("Pressure on unimproved zone","PSoil",                              f"{_pr_r['PSoil_kPa']:.3f} kPa"),
            ("Actual shear stress",        "τse = PSoil·(e²−πD²/4)/(π·D·Hse)",  f"{_pr_r['tse_kPa']:.3f} kPa"),
            ("Check",                      "τse ≤ τase ?",                       _pr_r["check_CT"]),
        ]
    _df_punch = pd.DataFrame(_punch_steps, columns=[_CP, _CF, _CV])
    st.dataframe(
        _df_punch.style.map(_color_sct, subset=[_CV]),
        use_container_width=True, hide_index=True,
        column_config={_CF: st.column_config.TextColumn(width="large")},
    )

    _punch_md = _load_punch_theory()
    if _punch_md:
        with st.expander("Diễn giải công thức kiểm tra chọc thủng lớp đệm xi măng", expanded=False):
            st.markdown(_punch_md)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 5 – XUẤT
# ═══════════════════════════════════════════════════════════════════════════════
elif _page == "export":
    st.subheader(_t("p5_sub"))

    D   = _get("cdm_D")
    Lc  = _get("cdm_Lc")
    qu  = _get("cdm_qu")
    Su  = _get("cdm_Su")
    arr = _get("cdm_arrangement")
    q   = q_total(_get("cdm_loads"))
    sps = _get("cdm_spacings")
    rec = _get("cdm_rec_idx")

    scenarios = build_scenarios(D, Lc, qu, Su, q, sps, arr)
    rec = min(rec, len(scenarios) - 1) if scenarios else 0

    params = {
        "bh_name":   _get("cdm_bh") or "–",
        "zone":      _get("cdm_zone"),
        "h_clay":    _get("cdm_h_clay"),
        "Su": Su,    "gamma": _get("cdm_gamma"),
        "D": D,      "Lc": Lc, "CDTK": _get("cdm_CDTK"),
        "qu": qu,    "FS_lab": _get("cdm_FS_lab"),
        "dosage":    _get("cdm_dosage"),
        "arrangement": arr,
        "q_total":   q,
        "rec_idx":   rec,
        "loads":     _get("cdm_loads"),
        "quckse":    _get("cdm_quckse"),
        "Fs_mat":    _get("cdm_Fs_mat"),
        "theta":     _get("cdm_theta"),
        "qa_mat":    _get("cdm_qa_mat"),
    }

    st.markdown(f"### {_t('export_sum')}")
    if scenarios:
        s = scenarios[rec]
        col1, col2, col3 = st.columns(3)
        col1.metric(_t("rec_alt"), f"e = {s['e (m)']} m")
        col2.metric(_t("settle_metric"), f"{s['S₁ (cm)']:.2f} cm")
        col3.metric(_t("bear_lbl"), s["Đạt SCT"])

    st.divider()
    c_word, c_excel = st.columns(2)

    with c_word:
        st.markdown(f"#### {_t('word_title')}")
        st.caption(_t("word_cap"))

        # ── Thông tin đơn vị (header / footer) ───────────────────────────
        st.text_input(
            "Tên công ty",
            key="export_co_name",
            placeholder="VD: CÔNG TY CỔ PHẦN TƯ VẤN XÂY DỰNG ABC",
        )
        st.text_input(
            "Nhân sự thực hiện",
            key="export_co_staff",
            placeholder="VD: KS. Nguyễn Văn A",
        )
        _logo_file = st.file_uploader(
            "Logo công ty (PNG/JPG)",
            type=["png", "jpg", "jpeg"],
            key="export_logo_uploader",
        )
        if _logo_file is not None:
            st.session_state["export_logo_bytes"] = _logo_file.read()
        if "export_logo_bytes" in st.session_state:
            st.image(st.session_state["export_logo_bytes"], width=80)

        st.divider()
        if st.button(_t("create_word"), type="primary"):
            with st.spinner(_t("creating")):
                word_bytes = _export_word_bytes(
                    scenarios, params, rec,
                    co_name=st.session_state.get("export_co_name", ""),
                    co_staff=st.session_state.get("export_co_staff", ""),
                    logo_bytes=st.session_state.get("export_logo_bytes"),
                )
            if word_bytes:
                st.download_button(
                    _t("dl_docx"),
                    word_bytes,
                    file_name=f"CDM-THUYET-MINH-{params['bh_name']}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            else:
                st.error("Lỗi tạo Word. Kiểm tra CDM/scripts/docx_helpers.py.")

    with c_excel:
        st.markdown("#### Tính toán chi tiết (Excel)")
        st.caption("3 sheet: Đầu vào · So sánh PA (bảng + biểu đồ nhúng) · Kết quả PA kiến nghị.")
        if st.button("Tạo file Excel", type="primary"):
            with st.spinner("Đang tạo Excel..."):
                xl_bytes = _export_excel(scenarios, params)
            if xl_bytes:
                st.download_button(
                    "Tải xuống (.xlsx)",
                    xl_bytes,
                    file_name=f"CDM-TINH-TOAN-{params['bh_name']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            else:
                st.error("Lỗi tạo Excel. Kiểm tra openpyxl đã cài chưa.")

    # ── Lý thuyết tính toán (in PDF) ─────────────────────────────────────────
    st.divider()
    _theory_text = _load_theory()
    if _theory_text:
        with st.expander("Lý thuyết tính toán – đính kèm khi in PDF", expanded=True):
            st.markdown(
                "<style>"
                "@media print {"
                "  details { display: block !important; }"
                "  summary { display: none; }"
                "}"
                "</style>",
                unsafe_allow_html=True,
            )
            st.markdown(_theory_text)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 6 – LÚN NỀN (TCCS 41:2022)
# ═══════════════════════════════════════════════════════════════════════════════
if _page == "settlement":
    import sys as _sys
    _sys.path.insert(0, str(_ROOT / "scripts"))
    try:
        from settlement_calc import (
            compare_methods as _sc_compare,
            calc_settlement_iterative_9_2_3 as _sc_iter923,
        )
        _HAS_SC = True
    except Exception as _exc:
        _HAS_SC = False
        st.error(f"Không tải được settlement_calc: {_exc}")

    if _HAS_SC:
        st.subheader("Dự báo độ lún – So sánh phương án xử lý (TCCS 41:2022)")

        # ── Lý thuyết tính lún (đặt trên cùng — xem trước khi chạy tính toán) ──
        with st.expander("Lý thuyết tính lún cố kết — TCCS 41:2022 + TCVN 9403:2012",
                          expanded=False):
            st.markdown(r"""
## 1. Lún cố kết sơ cấp — Phụ lục A, TCCS 41:2022

Mỗi lớp đất yếu $i$ tính theo trạng thái cố kết. Đặt $\sigma'_{v0}$ là ứng suất hữu hiệu ban đầu,
$\sigma'_{vf} = \sigma'_{v0} + \Delta\sigma$ là ứng suất sau khi đắp, $P_C$ là áp lực tiền cố kết.

### 1.1 Đất quá cố kết (OC) — $\sigma'_{vf} \leq P_C$

$$S_i = H_i \cdot \frac{C_s}{1 + e_0} \cdot \log \frac{\sigma'_{vf}}{\sigma'_{v0}}$$

### 1.2 Cắt qua $P_C$ — $\sigma'_{v0} < P_C < \sigma'_{vf}$

$$S_i = H_i \left[ \frac{C_s}{1 + e_0} \log \frac{P_C}{\sigma'_{v0}}
                  + \frac{C_c}{1 + e_0} \log \frac{\sigma'_{vf}}{P_C} \right]$$

### 1.3 Đất bình thường cố kết (NC) — $\sigma'_{v0} \geq P_C$

$$S_i = H_i \cdot \frac{C_c}{1 + e_0} \cdot \log \frac{\sigma'_{vf}}{\sigma'_{v0}}$$

### 1.4 Tổng lún

$$S_{\text{total}} = \sum_{i=1}^{n} S_i$$

Trong đó:
- $C_c$: chỉ số nén; $C_s$: chỉ số nở lại; $e_0$: hệ số rỗng tự nhiên
- $H_i$: chiều dày lớp đại diện (boundary trung điểm các mẫu)

---

## 2. Lún CDM — TCVN 9403:2012, Phụ lục C

CDM thay thế đất yếu bằng nền hỗn hợp (composite). Lún tổng:

$$S = S_1 + S_2$$

### 2.1 Lún đàn hồi tức thời trong khối gia cố

$$S_1 = \frac{q \cdot H_{\text{soft}}}{a \cdot E_c + (1 - a) \cdot E_s}$$

### 2.2 Lún cố kết bên dưới mũi cột

$$S_2 = 0 \quad (\text{nếu CDM cắm đến lớp cứng})$$

### 2.3 Mô-đun thành phần

$$E_c = 75 \cdot C_{c,\text{col}} = 75 \cdot \left( \text{ratio}_{lab \to field} \cdot \frac{q_{u,lab}}{2} \right)
\quad \text{(TCVN 9403 B.5.1)}$$

$$E_s = 250 \cdot C_u \quad \text{(tương quan Mesri)}$$

$$E_{\text{composite}} = a \cdot E_c + (1 - a) \cdot E_s$$

### 2.4 Tỷ lệ diện tích thay thế $a$

$$a_{\text{vuông}} = \frac{\pi D^2}{4 e^2} \qquad
a_{\text{tam giác}} = \frac{\pi D^2}{2\sqrt{3}\, e^2}$$

---

## 3. Độ cố kết theo thời gian — Điều 9.3–9.4 TCCS 41:2022

### 3.1 Độ cố kết và lún còn lại

$$U(t) = \frac{S(t)}{S_{\text{total}}} \qquad
\Delta S = S_{\text{total}} \cdot \bigl(1 - U(t_{tc})\bigr)$$

### 3.2 Theo phương án xử lý

| Phương án | $U(t)$ | Ghi chú |
|---|---|---|
| Không xử lý | $U_v$ (Terzaghi đứng) — phụ thuộc $C_v$, $H_{dr}$ | Chậm nhất |
| Bấc thấm | $U = 1 - (1 - U_v)(1 - U_h)$ | $U_h$ tăng theo $n = r_e/r_w$ |
| Giếng cát | Tương tự bấc thấm | Đường kính giếng lớn hơn |
| CDM | $S_1$ đàn hồi tức thời → $\Delta S \approx 0$ | Lún xảy ra ngay khi đắp |

### 3.3 Yêu cầu thiết kế

$$\Delta S \leq 30 \text{ cm} \quad \text{(TCCS 41:2022 — đường cấp I đoạn thông thường)}$$

---

## 4. Surcharge (gia tải tạm)

Tăng tải gia tải $> $ tải thiết kế trong giai đoạn cố kết → tăng tốc $U(t)$ →
sau khi dỡ surcharge, lún còn lại $\Delta S$ giảm. **Không** thay đổi $S_{\text{total}}$ dưới tải thiết kế.

---

## 5. Bảng đơn vị

| Đại lượng | Ký hiệu | Đơn vị |
|---|:---:|:---:|
| Chỉ số nén / nở lại | $C_c$, $C_s$ | — |
| Hệ số rỗng | $e_0$ | — |
| Ứng suất hữu hiệu | $\sigma'_v$, $P_C$ | kPa |
| Tải trọng | $q$ | kPa |
| Chiều dày, chiều sâu | $H_i$, $H_{\text{soft}}$ | m |
| Hệ số cố kết | $C_v$ | cm²/s |
| Lún | $S_i$, $S_{\text{total}}$, $\Delta S$ | cm |
| Mô-đun đàn hồi | $E_c$, $E_s$, $E_{\text{composite}}$ | kPa |
| Thời gian | $t$ | tháng |

**Tài liệu nguồn:** TCCS 41:2022 (Phụ lục A, Điều 9.3–9.4), TCVN 9403:2012 (Phụ lục C, Mục B.5.1).
""")

        # ── PHẦN 1: So sánh phương án ────────────────────────────────────────
        if True:
            _sc1, _sc2, _sc3 = st.columns([1, 1, 2])
            with _sc1:
                _sl_zone = st.radio("Zone", list(_ZONE_NAMES.keys()),
                                    format_func=lambda z: _ZONE_NAMES[z],
                                    key="sl_zone")
                _sl_bhs = [b["name"] for b in _load_boreholes_by_zone(_sl_zone)]
                _sl_bh  = st.selectbox("Hố khoan tính lún", _sl_bhs, key="sl_bh")
            with _sc2:
                _sl_from_cdm = st.checkbox("Lấy H từ tab Thông số CDM", key="sl_H_from_cdm")
                if _sl_from_cdm:
                    _cdm_ld  = _get("cdm_loads")
                    _cdm_top = _get("cdm_top_clay")
                    _sl_H    = round(_cdm_ld.get("z_tk", 3.5) - _cdm_top, 2)
                    st.info(f"H = z_tk − đỉnh bùn = **{_sl_H:.2f} m**")
                else:
                    _sl_H = st.number_input("Chiều cao đắp H (m)", 0.5, 15.0,
                                            st.session_state.get("sl_H_manual", 3.0), 0.5,
                                            key="sl_H_manual")
                _sl_lim = st.number_input("Giới hạn lún còn lại (cm)", 10, 50, 30, 5, key="sl_lim")
                _sl_tc  = st.number_input("Thời gian thi công (tháng)", 3, 36, 6, 1, key="sl_tc")
            with _sc3:
                st.caption("**Phương pháp tính:** TCCS 41:2022 — Phụ lục A (lún sơ cấp), Điều 9.3-9.4 (độ cố kết)")
                st.caption("**Lún còn lại ΔS** = lún tổng − lún tại thời điểm kết thúc thi công")

            # ── Bảng thông số địa chất dùng để tính lún cố kết ─────────────
            if _sl_bh:
                _geo_layers = _load_layers(_sl_bh)
                if _geo_layers:
                    _param_rows = []
                    _has_borrowed = False
                    for _lr in _geo_layers:
                        _sym = _lr.get("symbol") or ""
                        _Cc  = _lr.get("Cc")
                        _Cs  = _lr.get("Cs")
                        _e0  = _lr.get("e0")
                        _PC  = _lr.get("PC_kPa")
                        _Cv  = _lr.get("Cv_cm2s")
                        _gam = _lr.get("gamma_kNm3")
                        _src = ""
                        # Nếu thiếu thông số cố kết → tham khảo hố khoan khác trong zone
                        if _Cc is None or _e0 is None:
                            _fb = _load_zone_params_by_symbol(_sl_zone, _sym)
                            if _fb:
                                _Cc  = _Cc  if _Cc  is not None else _fb.get("Cc")
                                _Cs  = _Cs  if _Cs  is not None else _fb.get("Cs")
                                _e0  = _e0  if _e0  is not None else _fb.get("e0")
                                _PC  = _PC  if _PC  is not None else _fb.get("PC_kPa")
                                _Cv  = _Cv  if _Cv  is not None else _fb.get("Cv_cm2s")
                                _gam = _gam if _gam is not None else _fb.get("gamma_kNm3")
                                _src = _fb.get("source_bh") or ""
                                if _src:
                                    _has_borrowed = True
                        _Cv_fmt = f"{_Cv:.2e}" if _Cv is not None else "—"
                        _param_rows.append({
                            "Lớp":         _sym,
                            "Mô tả":       (_lr.get("description") or "")[:30],
                            "h (m)":       _lr.get("thickness_m"),
                            "γ (kN/m³)":  _gam,
                            "e0":          _e0,
                            "Cc":          _Cc,
                            "Cs":          _Cs,
                            "PC (kPa)":   _PC,
                            "Cv (cm²/s)": _Cv_fmt,
                            "_src":        _src,
                        })
                    _df_geo = pd.DataFrame(_param_rows)
                    _src_map_sl = _df_geo["_src"].to_dict()

                    def _highlight_borrowed(row):
                        if _src_map_sl.get(row.name):
                            return ["background-color: #FFF8DC"] * len(row)
                        return [""] * len(row)

                    st.markdown("**Thông số địa chất dùng tính lún cố kết**")
                    st.dataframe(
                        _df_geo.drop(columns=["_src"]).style.apply(_highlight_borrowed, axis=1),
                        use_container_width=True, hide_index=True,
                        column_config={
                            "h (m)":      st.column_config.NumberColumn(format="%.2f"),
                            "γ (kN/m³)": st.column_config.NumberColumn(format="%.2f"),
                            "e0":         st.column_config.NumberColumn(format="%.3f"),
                            "Cc":         st.column_config.NumberColumn(format="%.4f"),
                            "Cs":         st.column_config.NumberColumn(format="%.4f"),
                            "PC (kPa)":  st.column_config.NumberColumn(format="%.1f"),
                        },
                    )
                    if _has_borrowed:
                        st.caption("*Ô nền vàng: thông số tham khảo từ hố khoan khác cùng khu vực do hố khoan hiện tại chưa đủ dữ liệu.*")

            if st.button("Tính toán lún", type="primary", key="sl_calc"):
                with st.spinner("Đang tính..."):
                    try:
                        _cmp = _sc_compare(
                            _sl_bh, _sl_zone,
                            H_fill_m=float(_sl_H),
                            residual_limit_cm=float(_sl_lim),
                            t_construction_months=float(_sl_tc),
                        )
                        st.session_state["sl_result"] = _cmp
                    except Exception as _e:
                        st.error(f"Lỗi tính toán: {_e}")

            _cmp = st.session_state.get("sl_result")

            if _cmp:
                _cdm_beta = _cmp.get("cdm_beta", 1.0)
                _cdm_a    = _cmp.get("cdm_area_ratio", 0.25)
                _col_info1, _col_info2, _col_info3 = st.columns(3)
                with _col_info1:
                    st.metric("Lún tự nhiên (Cc)", f"{_cmp['S_total_cm']:.0f} cm",
                              help="Tổng lún cố kết sơ cấp tính từ mẫu thí nghiệm theo TCCS41 Phụ lục A")
                with _col_info2:
                    st.metric("CDM beta (TCVN 9403)", f"{_cdm_beta:.3f}",
                              f"Ứng suất vào đất = {_cdm_beta*100:.0f}% tải trọng",
                              help="beta = Es/(a*Ec+(1-a)*Es); Ec=75*Cc_col; Es=250*Cu")
                with _col_info3:
                    _cdm_sc = next((s for s in _cmp["scenarios"] if s["method"] == "cdm"), None)
                    if _cdm_sc:
                        _cdm_red = (1 - _cdm_sc["S_total_cm"] / _cmp["S_total_cm"]) * 100
                        st.metric("CDM lún đàn hồi (S1)", f"{_cdm_sc['S_total_cm']:.0f} cm",
                                  f"-{_cdm_red:.0f}% so với không xử lý | S2=0",
                                  help="S1 = q×H/(a×Ec+(1-a)×Es) — đàn hồi tức thời; S2=0 (CDM đến lớp cứng). TCVN 9403:2012 Phụ lục C")

                # Bảng so sánh phương án
                _sc_rows = []
                for _sc_item in _cmp["scenarios"]:
                    _t90_str = f"{_sc_item['t_90_months']:.0f}" if _sc_item["t_90_months"] else ">240"
                    _sc_rows.append({
                        "Phương án":        _sc_item["label"],
                        "Lún tổng (cm)":    _sc_item["S_total_cm"],
                        "Lún tại TC (cm)":  _sc_item["S_at_constr_cm"],
                        "U tại TC (%)":     _sc_item["U_at_constr_pct"],
                        "Lún còn lại (cm)": _sc_item["residual_cm"],
                        "t90% (tháng)":     _t90_str,
                        "Surcharge (m)":    _sc_item["H_surcharge_m"],
                        "Đánh giá":         "Đạt" if _sc_item["feasible"] else "Không đạt",
                    })
                _df_sc = pd.DataFrame(_sc_rows)
                st.dataframe(
                    _df_sc.style.apply(
                        lambda col: ["background-color:#d4edda" if v == "Đạt"
                                     else "background-color:#f8d7da" if v == "Không đạt"
                                     else "" for v in col],
                        subset=["Đánh giá"]
                    ),
                    use_container_width=True, hide_index=True
                )
                _cdm_S1 = _cmp.get("cdm_S1_cm", 0)
                _cdm_Ec = _cmp.get("cdm_Ec_kPa", 0)
                _cdm_Es = _cmp.get("cdm_Es_kPa", 0)
                _cdm_Etb = _cmp.get("cdm_composite_kPa", 0)
                st.caption(
                    f"CDM (TCVN 9403 Phụ lục C): S1={_cdm_S1:.0f} cm (đàn hồi), S2=0 cm. "
                    f"Ec={_cdm_Ec:.0f} kPa | Es={_cdm_Es:.0f} kPa | Etb={_cdm_Etb:.0f} kPa (a={_cdm_a:.2f}). "
                    "Không xử lý/Bấc thấm/Giếng cát: Cc cố kết (Terzaghi+Barron). "
                    "Giải thích: xem 'Lý thuyết tính lún' cuối trang."
                )

                # Biểu đồ S(t)
                if _HAS_PLOTLY:
                    _colors_sl = {
                        "no_treat":   "#636EFA",
                        "pvd_1200":   "#EF553B",
                        "pvd_1500":   "#00CC96",
                        "sand_drain": "#AB63FA",
                        "cdm":        "#FFA15A",
                    }
                    _fig_sl = go.Figure()
                    for _sc_item in _cmp["scenarios"]:
                        _mid = _sc_item["method"]
                        _ts  = _cmp["time_series"].get(_mid, [])
                        if not _ts:
                            continue
                        _fig_sl.add_trace(go.Scatter(
                            x=[p["t_months"] for p in _ts],
                            y=[p["S_cm"] for p in _ts],
                            mode="lines+markers",
                            name=_sc_item["label"],
                            line=dict(color=_colors_sl.get(_mid, "#888"), width=2),
                            marker=dict(size=4),
                        ))
                    _S_ref = _cmp["S_total_cm"] - float(_sl_lim)
                    _fig_sl.add_hline(
                        y=max(_S_ref, 0),
                        line_dash="dash", line_color="red",
                        annotation_text=f"S min để đạt ΔS≤{_sl_lim}cm",
                        annotation_position="bottom right",
                    )
                    _fig_sl.add_vline(
                        x=float(_sl_tc),
                        line_dash="dot", line_color="gray",
                        annotation_text=f"Kết thúc TC ({_sl_tc}th)",
                    )
                    _fig_sl.update_layout(
                        title="Quan hệ S-t theo phương án xử lý nền",
                        xaxis_title="Thời gian (tháng)",
                        yaxis_title="Độ lún S (cm)",
                        height=420,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                        margin=dict(t=60),
                    )
                    st.plotly_chart(_fig_sl, use_container_width=True)

                # Chi tiết lún từng lớp
                with st.expander("Chi tiết lún từng lớp"):
                    _detail = _cmp["S_detail"]
                    if _detail.get("warning"):
                        st.warning(_detail["warning"])
                    if _detail.get("layers"):
                        _df_lay = pd.DataFrame(_detail["layers"])
                        _df_lay.columns = [
                            "Độ sâu (m)", "H lớp (m)",
                            "σv0 (kPa)", "σvf (kPa)", "PC (kPa)",
                            "Cc", "Cs", "e0", "Si (cm)", "Trạng thái OC"
                        ]
                        st.dataframe(_df_lay, use_container_width=True, hide_index=True)

                # ── Biểu đồ ứng suất theo chiều sâu ──────────────────────────
                _layers = _cmp["S_detail"].get("layers", [])
                if _layers and _HAS_PLOTLY:
                    st.markdown("##### Biểu đồ ứng suất theo chiều sâu (phạm vi ảnh hưởng)")
                    _beta_plot = _cmp.get("cdm_beta", 1.0)
                    _dsig = _layers[0]["sigma_vf_kPa"] - _layers[0]["sigma_v0_kPa"]  # Delta_sigma

                    _depths  = [ly["depth_mid_m"]   for ly in _layers]
                    _sv0_arr = [ly["sigma_v0_kPa"]  for ly in _layers]
                    _svf_arr = [ly["sigma_vf_kPa"]  for ly in _layers]
                    _pc_arr  = [ly["PC_kPa"]         for ly in _layers]
                    # CDM: stress giảm theo beta
                    _svf_cdm = [ly["sigma_v0_kPa"] + _beta_plot * (ly["sigma_vf_kPa"] - ly["sigma_v0_kPa"])
                                for ly in _layers]
                    # OC status color mapping
                    _oc_colors = {
                        "OC": "#2196F3", "cross_PC": "#FF9800", "NC": "#F44336", "unknown": "#9E9E9E"
                    }
                    _oc_vals = [ly["OC_status"] for ly in _layers]

                    _fig_str = go.Figure()
                    _fig_str.add_trace(go.Scatter(
                        x=_sv0_arr, y=_depths, mode="lines+markers",
                        name="σv0 (ứng suất ban đầu)",
                        line=dict(color="#1565C0", width=2),
                        marker=dict(size=5, symbol="circle"),
                    ))
                    _fig_str.add_trace(go.Scatter(
                        x=_svf_arr, y=_depths, mode="lines+markers",
                        name="σvf (sau đắp, không xử lý)",
                        line=dict(color="#C62828", width=2, dash="dot"),
                        marker=dict(size=5, symbol="square"),
                    ))
                    _fig_str.add_trace(go.Scatter(
                        x=_svf_cdm, y=_depths, mode="lines+markers",
                        name=f"σvf CDM (beta={_beta_plot:.3f})",
                        line=dict(color="#E65100", width=2, dash="dash"),
                        marker=dict(size=5, symbol="diamond"),
                    ))
                    _fig_str.add_trace(go.Scatter(
                        x=[p for p in _pc_arr if p is not None],
                        y=[_depths[i] for i, p in enumerate(_pc_arr) if p is not None],
                        mode="lines+markers",
                        name="PC (áp lực tiền cố kết)",
                        line=dict(color="#2E7D32", width=2, dash="longdash"),
                        marker=dict(size=7, symbol="triangle-up"),
                    ))

                    # Shade OC/cross/NC zones với màu nền
                    _oc_zone_color = {"OC": "rgba(33,150,243,0.08)",
                                      "cross_PC": "rgba(255,152,0,0.12)",
                                      "NC": "rgba(244,67,54,0.10)",
                                      "unknown": "rgba(200,200,200,0.05)"}
                    for _li, _ly in enumerate(_layers):
                        _oc = _ly["OC_status"]
                        _y0 = _ly["depth_mid_m"] - _ly["H_i_m"] / 2
                        _y1 = _ly["depth_mid_m"] + _ly["H_i_m"] / 2
                        _fig_str.add_hrect(
                            y0=_y0, y1=_y1,
                            fillcolor=_oc_zone_color.get(_oc, "rgba(200,200,200,0.05)"),
                            line_width=0,
                        )

                    _fig_str.update_layout(
                        xaxis_title="Ứng suất hữu hiệu (kPa)",
                        yaxis_title="Độ sâu (m)",
                        yaxis=dict(autorange="reversed", ticksuffix=" m"),
                        height=480,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                        margin=dict(t=80, l=70),
                        annotations=[dict(
                            x=0.02, y=0.02, xref="paper", yref="paper",
                            text="<b>Màu vùng:</b> Xanh=OC | Cam=cắt qua PC | Đỏ=NC",
                            showarrow=False, font=dict(size=10),
                            bgcolor="rgba(255,255,255,0.7)", bordercolor="gray",
                        )],
                    )
                    st.plotly_chart(_fig_str, use_container_width=True)
                    st.caption(
                        f"Δσ = {_dsig:.0f} kPa (đắp H={_cmp['H_fill_m']}m, γ=20 kN/m³). "
                        f"Đường 'σvf CDM (beta={_beta_plot:.3f})' minh hoạ ứng suất vào đất giữa cột — "
                        "CDM tính lún theo S1 đàn hồi (TCVN 9403 Phụ lục C), không phải Cc cố kết. "
                        "Vùng NC/cắt qua PC là vùng có lún Cc lớn nhất nếu không xử lý."
                    )

                # ── Lý thuyết tính lún ────────────────────────────────────────
                with st.expander("Lý thuyết tính lún và giải thích kết quả CDM"):
                    _beta_txt = _cmp.get("cdm_beta", 1.0)
                    _a_txt    = _cmp.get("cdm_area_ratio", 0.25)
                    _S1_txt   = _cmp.get("cdm_S1_cm", 0)
                    _Ec_txt   = _cmp.get("cdm_Ec_kPa", 0)
                    _Es_txt   = _cmp.get("cdm_Es_kPa", 0)
                    _Etb_txt  = _cmp.get("cdm_composite_kPa", 0)
                    st.markdown(f"""
**1. Lún cố kết sơ cấp (không xử lý / bấc thấm / giếng cát) — Phụ lục A TCCS 41:2022**

Mỗi lớp i được tính theo trạng thái cố kết:

| Trạng thái | Điều kiện | Công thức |
|---|---|---|
| Quá cố kết (OC) | σvf ≤ PC | Si = Hi × Cs/(1+e0) × log(σvf/σv0) |
| Cắt qua PC | σv0 < PC < σvf | Si = Hi × [Cs/(1+e0)×log(PC/σv0) + Cc/(1+e0)×log(σvf/PC)] |
| Bình thường cố kết (NC) | σv0 ≥ PC | Si = Hi × Cc/(1+e0) × log(σvf/σv0) |

Trong đó: σv0 = ứng suất hữu hiệu ban đầu; σvf = σv0 + Δσ; PC = áp lực tiền cố kết.

Phạm vi tính: tất cả lớp đất yếu (mẫu nén cố kết có Cc). Chiều dày đại diện H_i dùng
boundary trung điểm giữa các mẫu liền kề (không phải chiều dày mẫu 0.6m).

---

**2. Lún CDM — TCVN 9403:2012 Phụ lục C (lún đàn hồi khối gia cố)**

CDM thay thế đất yếu bằng nền hỗn hợp (composite ground). Lún tính theo:

```
S = S1 + S2
S1 = q × H_soft / (a×Ec + (1-a)×Es)   [đàn hồi tức thời trong khối gia cố]
S2 = lún cố kết bên dưới cột            [= 0 nếu CDM cắm đến lớp cứng]
```

Trong đó:
```
Ec = 75 × Cc_col = 75 × (field_lab_ratio × qu_lab / 2)   [TCVN 9403 B.5.1]
Es = 250 × Cu                                              [tương quan Mesri]
```

**Kết quả cho zone này (a = {_a_txt:.2f}):**
- Ec = {_Ec_txt:.0f} kPa | Es = {_Es_txt:.0f} kPa | E_tổng hợp = {_Etb_txt:.0f} kPa
- **S1 = {_S1_txt:.1f} cm** (đàn hồi, xảy ra tức thời trong quá trình thi công)
- **S2 = 0 cm** (giả thiết CDM cắm đến lớp cứng)

*Hệ số beta = {_beta_txt:.3f}* (tỷ lệ ứng suất vào đất giữa cột — chỉ để tham khảo biên độ ứng suất).

---

**3. Tại sao lún CDM thấp hơn rất nhiều so với không xử lý?**

| Phương pháp | Cơ sở vật lý | Biên độ |
|---|---|---|
| Không xử lý | Cc cố kết (log) | {_cmp['S_total_cm']:.0f} cm (lún dài hạn) |
| CDM | S1 đàn hồi (tuyến tính) | {_S1_txt:.0f} cm (tức thời) |

Lún Cc phụ thuộc log(σvf/σv0) — tăng mạnh khi đất NC và H_soft lớn.
Lún đàn hồi CDM phụ thuộc E_tổng hợp — càng cao (cột cứng hơn, mật độ lớn hơn) thì lún càng nhỏ.

**Để giảm S1 thêm:** Tăng diện tích thay thế a (cắt chặt hơn), hoặc tăng qu_lab (> 1 MPa).

---

**4. Lún còn lại sau thi công (ΔS)**

CDM: S1 là lún đàn hồi — xảy ra NGAY trong quá trình đắp. ΔS ≈ 0 (không có lún còn lại).

Các phương án khác:
```
ΔS = S_total × (1 - U(t_tc))
```
U(t) phụ thuộc vào phương pháp xử lý:
- Không xử lý: chỉ Uv (Terzaghi, Cv, Hdr)
- Bấc thấm / Giếng cát: U = 1-(1-Uv)(1-Uh) (cố kết kết hợp)

**Surcharge**: tăng ứng suất → tăng tốc độ cố kết trong thời gian gia tải,
nhưng không thay đổi S_total dưới tải thiết kế.

TCCS 41:2022 yêu cầu ΔS ≤ {_cmp['residual_limit_cm']:.0f} cm
(đường cấp 1 đoạn thông thường) sau khi làm xong mặt đường.
""")

        # ── PHẦN 1b: Lún sơ bộ TKCS — Điều 9.2.3 TCCS 41:2022 ──────────────
        st.divider()
        st.markdown("### Tính lún sơ bộ TKCS — Điều 9.2.3 TCCS 41:2022 (vòng lặp)")
        st.caption(
            "H'_tk = H_fill + S_gt — chiều cao đắp hiệu dụng bao gồm phần đắp lún vào đất yếu. "
            "Lặp lại đến khi |S_calc - S_gt| < tolerance. "
            "Kết quả lớn hơn tính toán một lần (không lặp) do trọng lượng đắp phần lún."
        )
        _it1, _it2, _it3 = st.columns([1, 1, 2])
        with _it1:
            _it_zone = st.radio("Zone", list(_ZONE_NAMES.keys()),
                                format_func=lambda z: _ZONE_NAMES[z],
                                key="it_zone")
            _it_bhs = [b["name"] for b in _load_boreholes_by_zone(_it_zone)]
            _it_bh  = st.selectbox("Hố khoan", _it_bhs, key="it_bh")
        with _it2:
            _it_H    = st.number_input("H_fill (m)", 1.0, 10.0, 3.0, 0.5, key="it_H")
            _it_pct  = st.number_input("S_gt ban đầu (% H_soft)", 1.0, 30.0, 7.5, 0.5,
                                        key="it_pct",
                                        help="Đất thường: 5-10%; Than bùn: 20-30% (Điều 9.2.3)")
            _it_tol  = st.number_input("Tolerance (cm)", 0.1, 5.0, 1.0, 0.1, key="it_tol")
        with _it3:
            st.caption(
                "**Công thức:** H'_tk = H_fill + S_gt  →  Δσ = H'_tk × γ_fill  →  "
                "S_c = Σ công thức Cc  →  kiểm tra |S_c - S_gt| < tol"
            )
            st.caption("**Khi nào dùng:** TKCS khi chưa có mẫu Cc chi tiết — dùng thông số trung bình zone.")

        if st.button("Tính lún sơ bộ 9.2.3", type="secondary", key="it_calc"):
            with st.spinner("Đang lặp..."):
                try:
                    _iter_res = _sc_iter923(
                        _it_bh, _it_zone,
                        H_fill_m=float(_it_H),
                        S_gt_init_pct=float(_it_pct),
                        tolerance_cm=float(_it_tol),
                    )
                    st.session_state["it_result"] = _iter_res
                except Exception as _e:
                    st.error(f"Lỗi tính toán 9.2.3: {_e}")

        _iter_res = st.session_state.get("it_result")
        if _iter_res:
            _im1, _im2, _im3 = st.columns(3)
            with _im1:
                st.metric("Lún không lặp (tham chiếu)",
                          f"{_iter_res['S_ref_cm']:.0f} cm",
                          help="Δσ = H_fill × γ (không tính phần đắp lún vào)")
            with _im2:
                st.metric("Lún sơ bộ TKCS (Điều 9.2.3)",
                          f"{_iter_res['S_final_cm']:.0f} cm",
                          f"+{_iter_res['S_increase_pct']:.0f}% so với không lặp",
                          delta_color="inverse",
                          help="Δσ = H'_tk × γ; H'_tk = H_fill + S_hội tụ")
            with _im3:
                _cv_str = "Hội tụ" if _iter_res["converged"] else "Chưa hội tụ"
                st.metric(f"Vòng lặp ({_cv_str})",
                          f"{_iter_res['n_iterations']} vòng",
                          f"tol={_iter_res['tolerance_cm']} cm | S_gt_init={_iter_res['S_gt_init_cm']:.0f} cm")

            st.markdown(f"**Chi tiết vòng lặp** — Zone {_iter_res['zone_code']}, "
                        f"HK {_iter_res['bh_name']}, H_fill={_iter_res['H_fill_m']}m, "
                        f"H_soft={_iter_res['H_soft_m']}m")
            _df_iter = pd.DataFrame(_iter_res["iterations"]).rename(columns={
                "iter":       "Vòng",
                "S_gt_cm":    "S_gt (cm)",
                "H_eff_m":    "H'_tk (m)",
                "Dsigma_kPa": "Δσ (kPa)",
                "S_calc_cm":  "S_calc (cm)",
                "delta_cm":   "Delta (cm)",
                "converged":  "Hội tụ",
            })
            st.dataframe(
                _df_iter.style.apply(
                    lambda col: ["background-color:#d4edda" if v is True
                                 else "background-color:#fff3cd" if v is False
                                 else "" for v in col],
                    subset=["Hội tụ"]
                ),
                use_container_width=True, hide_index=True,
            )
            st.caption(
                f"Lún sơ bộ TKCS = {_iter_res['S_final_cm']:.0f} cm "
                f"(lớn hơn {_iter_res['S_increase_pct']:.0f}% so với tính một lần). "
                "Nguyên nhân: đất yếu bị nào xuống, cần thêm đắp bù → tăng tải trọng → tăng lún thêm."
            )

        # ── Xuất PDF tab Dự báo lún ──────────────────────────────────────────
        if _HAS_PDF:
            st.divider()
            try:
                _pdf_s = _pdf_settle(
                    dict(st.session_state),
                    st.session_state.get("sl_result"),
                )
                st.download_button(
                    "Xuất PDF tab Dự báo lún",
                    data=_pdf_s,
                    file_name=f"DuBaoLun_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as _e:
                st.warning(f"Không tạo PDF: {_e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE KE_SW – CỌC VÁN THÉP DỰ ỨNG LỰC SW (KÈ CÔNG VIÊN)
# ═══════════════════════════════════════════════════════════════════════════════
if _page == "ke_sw":
    import math as _math

    _SW_JSON  = _ROOT / "data" / "sw_pile_catalog.json"
    _KE_JSON  = _ROOT / "data" / "ke_sw_202605_TTHC.json"

    @st.cache_data(show_spinner=False)
    def _load_sw_catalog() -> list[dict]:
        try:
            raw = json.loads(_SW_JSON.read_text(encoding="utf-8"))
            return raw["piles"]
        except Exception:
            return []

    @st.cache_data(show_spinner=False)
    def _load_ke_sw(_mtime: float = 0) -> dict:
        try:
            return json.loads(_KE_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}

    _sw_piles  = _load_sw_catalog()
    try:
        _mtime = _KE_JSON.stat().st_mtime
    except OSError:
        _mtime = 0
    _ke_data   = _load_ke_sw(_mtime)
    _sw_names  = sorted({p["name"] for p in _sw_piles})
    _Ec_table  = {
        "fc30 MPa": 26_561_000,
        "fc40 MPa": 31_623_000,
        "fc60 MPa": 38_730_000,
        "fc70 MPa": 43_628_130,
    }

    def _sw_by_name(name: str) -> dict | None:
        candidates = [p for p in _sw_piles if p["name"] == name]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.get("Mcr_Tm", 0))

    st.subheader("Cọc ván thép dự ứng lực SW — Kè Công Viên (KE)")

    # ── A. Catalog tiết diện ────────────────────────────────────────────────────
    st.markdown("### A. Catalog tiết diện SW")
    if not _sw_piles:
        st.warning("Không tải được catalog. Kiểm tra `data/sw_pile_catalog.json`.")
    else:
        _fc_sel = st.selectbox("Cường độ bê tông (cho tính Ec)", list(_Ec_table.keys()),
                               index=2, key="sw_fc")
        _Ec_sel = _Ec_table[_fc_sel]

        _cat_rows = []
        for p in _sw_piles:
            _Itd  = p.get("Itd_cm4", 0) or 0
            _Atd  = p.get("Atd_cm2", 0) or 0
            _Mcr  = p.get("Mcr_Tm", 0) or 0
            _EI   = _Ec_sel * _Itd * 1e-8
            _EI_m = _EI / (p.get("width_mm", 996) / 1000)
            _cat_rows.append({
                "Loại cọc":         p["name"],
                "H (mm)":           p.get("H_mm"),
                "t (mm)":           p.get("t_mm"),
                "Cáp (sợi)":        p.get("n_strands"),
                "φ cáp (mm)":       p.get("phi_strand_mm"),
                "Atd (cm²)":        _Atd,
                "Itd (cm⁴)":        _Itd,
                "Mcr (T.m)":        _Mcr,
                "Mcr (kN.m)":       round(_Mcr * 9.81, 1),
                "EI (kN·m²/m)":     round(_EI_m, 0),
                "TL (T/cọc)":       p.get("weight_T"),
                "L tc (m)":         p.get("L_std_m"),
                "L min (m)":        p.get("L_min_m"),
                "L max (m)":        p.get("L_max_m"),
                "Spacing (mm)":     p.get("width_mm", 996),
            })

        def _hi_sw(row):
            if row["Loại cọc"] in ("SW-840", "SW-940"):
                return ["background-color:#fff3cd"] * len(row)
            return [""] * len(row)

        st.dataframe(
            pd.DataFrame(_cat_rows).style.apply(_hi_sw, axis=1),
            use_container_width=True, hide_index=True,
        )
        st.caption(
            f"Ec = {_Ec_sel/1000:.0f} MPa ({_fc_sel}). "
            "Hàng vàng = cọc đã chọn cho dự án TTHC (SW-840 / SW-940). "
            "EI tính trên 1 m dài tường (chia spacing)."
        )

        if _HAS_PLOTLY:
            _fig_cat = go.Figure()
            _xs = [p.get("H_mm") for p in _sw_piles]
            _ys = [round((p.get("Mcr_Tm") or 0) * 9.81, 1) for p in _sw_piles]
            _nm = [p["name"] for p in _sw_piles]
            _fig_cat.add_trace(go.Scatter(
                x=_xs, y=_ys, mode="markers+text", text=_nm,
                textposition="top center",
                marker=dict(size=10,
                            color=["#FF6B35" if n in ("SW-840", "SW-940") else "#4A90D9"
                                   for n in _nm]),
                name="Mcr (kN·m/cọc)",
            ))
            _fig_cat.update_layout(
                title="Mô men nứt Mcr theo chiều cao tiết diện",
                xaxis_title="Chiều cao H (mm)",
                yaxis_title="Mcr (kN·m/cọc)",
                height=320, margin=dict(t=40, b=40),
            )
            st.plotly_chart(_fig_cat, use_container_width=True)

    # ── B. Kết quả thiết kế TTHC ────────────────────────────────────────────────
    st.divider()
    st.markdown("### B. Kết quả thiết kế — Kè Công Viên TTHC")
    if not _ke_data:
        st.warning("Không tải được dữ liệu. Kiểm tra `data/ke_sw_202605_TTHC.json`.")
    else:
        _dc     = _ke_data.get("design_conditions", {})
        _bhs_ke = _ke_data.get("boreholes", [])
        _sum_ke = _ke_data.get("pile_selection_summary", {})

        _d1, _d2, _d3 = st.columns(3)
        _d1.metric("Cao độ đỉnh kè (m)", _dc.get("top_ke_elevation_m", "–"))
        _d2.metric("Lớp bùn sét yếu", _dc.get("soft_clay_layer_symbol", "–"))
        _d3.metric("Xuyên qua lớp yếu (m)", _dc.get("min_penetration_below_soft_clay_m", "–"))

        # Catalog duy nhất, sort theo H_mm tăng dần → dùng để chọn cọc tối ưu
        _seen_names: set = set()
        _catalog_sorted: list = []
        for _p in sorted(_sw_piles, key=lambda x: x.get("H_mm", 0)):
            if _p["name"] not in _seen_names:
                _seen_names.add(_p["name"])
                _catalog_sorted.append(_p)
        _pile_options = [_p["name"] for _p in _catalog_sorted]
        # Lookup: tên cọc → L_max_m
        _pile_lmax: dict[str, float] = {
            _p["name"]: _p.get("L_max_m") or 0 for _p in _catalog_sorted
        }

        def _optimal_pile(L_req: float) -> tuple[str, float]:
            """Cọc nhỏ nhất có L_max ≥ L_req. Trả (name, L_max)."""
            for _p in _catalog_sorted:
                if (_p.get("L_max_m") or 0) >= L_req:
                    return _p["name"], _p.get("L_max_m", 0)
            last = _catalog_sorted[-1] if _catalog_sorted else {}
            return "Vượt catalog", last.get("L_max_m", 0)

        # Session state: lưu "Cọc kiến nghị" và "L thiết kế" do người dùng chọn
        _rec_key = "ke_sw_rec_piles"
        _ltk_key = "ke_sw_L_thiet_ke"
        if _rec_key not in st.session_state:
            st.session_state[_rec_key] = {}
        if _ltk_key not in st.session_state:
            st.session_state[_ltk_key] = {}

        # Bảng tổng hợp — chỉ các HK trên tuyến kè SW (on_sw_alignment=True)
        _bhs_on_alignment = [b for b in _bhs_ke if b.get("on_sw_alignment")]

        # Nút tự động điền cọc tối ưu + L_max tương ứng
        _btn_opt = st.button("Dùng cọc tối ưu cho tất cả", key="btn_use_optimal")
        if _btn_opt:
            for _bh in _bhs_on_alignment:
                _on, _olmax = _optimal_pile(_bh.get("L_req_m") or 0)
                st.session_state[_rec_key][_bh["name"]] = _on
                st.session_state[_ltk_key][_bh["name"]] = _olmax
            st.rerun()

        _ke_rows = []
        for _bh in _bhs_on_alignment:
            _nt2    = _bh.get("NT2_multilayer") or {}
            _L_req  = _bh.get("L_req_m") or 0
            _opt_name, _opt_Lmax = _optimal_pile(_L_req)
            # "Cọc kiến nghị": session_state → JSON default → optimal
            _rec = st.session_state[_rec_key].get(
                _bh["name"],
                _bh.get("recommended_pile") or _opt_name,
            )
            # "L thiết kế": session_state → L_max của cọc kiến nghị → JSON default
            _ltk = st.session_state[_ltk_key].get(
                _bh["name"],
                _pile_lmax.get(_rec) or _bh.get("recommended_L_m") or _opt_Lmax,
            )
            _ke_rows.append({
                "Hố khoan":          _bh["name"],
                "Z (m)":             _bh.get("Z_m"),
                "H lớp 1 (m)":       _bh.get("H_layer1_m"),
                "L yêu cầu (m)":     _L_req,
                "Cọc tối ưu":        _opt_name,
                "L_max (m)":         _opt_Lmax,
                "Đủ chiều dài":      "Đạt" if _opt_Lmax >= _L_req else "Không đạt",
                "Cọc kiến nghị":     _rec,
                "L thiết kế (m)":    float(_ltk) if _ltk is not None else _opt_Lmax,
                "NT1":               _bh.get("NT1"),
                "NT2":               _bh.get("NT2"),
                "Rs (kN)":           _nt2.get("Rs_kN", "–"),
                "Rp (kN)":           _nt2.get("Rp_kN", "–"),
                "RR (kN)":           _nt2.get("RR_kN", "–"),
                "W (kN)":            round(_bh.get("W_pile_kN") or 0, 1),
                "RR/W":              round(_nt2.get("ratio") or 0, 2) if _nt2 else "–",
                "Ghi chú":           _bh.get("note", ""),
            })

        if not _ke_rows:
            st.warning("Không có hố khoan nào có on_sw_alignment=True trong dữ liệu.")
        else:
            _df_b = pd.DataFrame(_ke_rows)
            _editable_b = {"Cọc kiến nghị", "L thiết kế (m)"}
            _disabled_b = [c for c in _df_b.columns if c not in _editable_b]
            _edited_b = st.data_editor(
                _df_b,
                column_config={
                    "Cọc kiến nghị": st.column_config.SelectboxColumn(
                        "Cọc kiến nghị",
                        options=_pile_options,
                        required=True,
                        width="medium",
                    ),
                    "L thiết kế (m)": st.column_config.NumberColumn(
                        "L thiết kế (m)",
                        min_value=1.0,
                        max_value=40.0,
                        step=0.5,
                        format="%.1f",
                        width="small",
                    ),
                    "Đủ chiều dài": st.column_config.Column(width="small"),
                },
                disabled=_disabled_b,
                hide_index=True,
                use_container_width=True,
                key="ke_b_editor",
            )
            # Lưu chỉnh sửa vào session state — chỉ khi người dùng thay đổi
            _edit_cols = ["Cọc kiến nghị", "L thiết kế (m)"]
            if not _edited_b[_edit_cols].equals(_df_b[_edit_cols]):
                for _, _row in _edited_b.iterrows():
                    _bh_n = _row["Hố khoan"]
                    st.session_state[_rec_key][_bh_n] = _row["Cọc kiến nghị"]
                    st.session_state[_ltk_key][_bh_n] = _row["L thiết kế (m)"]

        # Kết luận phương án
        _sc1, _sc2 = st.columns(2)
        with _sc1:
            st.markdown("**Phương án A — Đồng nhất tuyến**")
            _oA = _sum_ke.get("option_A", {})
            st.info(
                f"Cọc: **{_oA.get('pile_type')}**  \n"
                f"Chiều dài: **{_oA.get('L_m')} m**  \n"
                f"Áp dụng: {', '.join(_oA.get('applies_to', []))}"
            )
        with _sc2:
            st.markdown("**Phương án B — Khu vực KE-HK10**")
            _oB = _sum_ke.get("option_B", {})
            st.warning(
                f"Cọc: **{_oB.get('pile_type')}**  \n"
                f"Chiều dài: **{_oB.get('L_m')} m**  \n"
                f"Lý do: {_oB.get('note', '')}"
            )

        if _HAS_PLOTLY and _ke_rows:
            _names_plot  = [r["Hố khoan"] for r in _ke_rows if r["RR/W"] != "–"]
            _ratios_plot = [float(r["RR/W"]) for r in _ke_rows if r["RR/W"] != "–"]
            _min_ratio   = min(_ratios_plot) if _ratios_plot else 0
            _colors_plot = [
                "#FF6B35" if v == _min_ratio else "#2E7D32"
                for v in _ratios_plot
            ]
            _fig_nt2 = go.Figure()
            _fig_nt2.add_trace(go.Bar(
                x=_names_plot, y=_ratios_plot,
                marker_color=_colors_plot,
                text=[f"{v:.2f}" for v in _ratios_plot],
                textposition="outside",
                name="RR/W",
            ))
            _fig_nt2.add_hline(y=1.0, line_dash="dash", line_color="red",
                               annotation_text="Giới hạn NT2 (RR ≥ W)")
            _fig_nt2.update_layout(
                title="Tỷ số NT2: RR/W theo hố khoan trên tuyến kè SW  (cam = HK kiểm soát)",
                yaxis_title="RR / W", xaxis_title="Hố khoan",
                height=350, margin=dict(t=50, b=40),
                yaxis=dict(range=[0, max(_ratios_plot) * 1.2 if _ratios_plot else 3]),
            )
            st.plotly_chart(_fig_nt2, use_container_width=True)
        st.caption(
            "Hiển thị 7 hố khoan trên tuyến kè SW: KE-HK2, HK3, HK7, HK8, HK9, HK10, HK11. "
            "Cam = HK kiểm soát (tỷ số RR/W nhỏ nhất). "
            "Nguồn: ke_sw_202605_TTHC.json (on_sw_alignment=True)."
        )

        # ── Chi tiết NT1/NT2 từng hố khoan (SQLite) ─────────────────────────────
        with st.expander("Chi tiết tính toán NT1/NT2 từng hố khoan"):
            _SRC_LBL = {
                "VST":     "VST",
                "lab":     "Lab",
                "default": "Giả định",
                "sand":    "Cát",
                "SPT":     "SPT",
                "missing": "Thiếu SPT",
                "unknown": "Không rõ",
            }
            try:
                _con_nt = sqlite3.connect(str(_DB))
                _cur_nt = _con_nt.cursor()
                _cur_nt.execute(
                    "SELECT bh_name, pile_type, L_design_m, Z_m, Z_source, "
                    "fill_m, L_soil_m, tip_depth_m, D_bottom_soft_m, D_source, "
                    "L_req_nt1_m, margin_nt1_m, nt1_result, "
                    "Rs_kN, Rs_clay_kN, Rs_sand_kN, "
                    "tip_symbol, tip_method, tip_su_kNm2, tip_N160, "
                    "Rp_kN, phi_stat, phi_basis, RR_kN, W_kN, "
                    "ratio_nt2, nt2_result, su_warnings "
                    "FROM ke_sw_nt_detail ORDER BY bh_name"
                )
                _nt_rows = _cur_nt.fetchall()
                _con_nt.close()
                if not _nt_rows:
                    st.info(
                        "Chưa có dữ liệu NT1/NT2 trong SQLite. "
                        "Chạy `scripts/ke_sw_nt_calc.py` để tạo dữ liệu."
                    )
                else:
                    for _nt in _nt_rows:
                        (
                            _bh_n, _pile_t, _L_d, _Z_m, _Z_src,
                            _fill_m, _L_soil, _tip_d, _D_bot, _D_src,
                            _L_req1, _marg1, _res1,
                            _Rs, _Rs_clay, _Rs_sand,
                            _tip_sym, _tip_meth, _tip_su, _tip_N160,
                            _Rp, _phi, _phi_basis, _RR, _W,
                            _rat2, _res2, _warns,
                        ) = _nt
                        st.markdown(f"#### {_bh_n}")

                        if _warns:
                            st.warning(
                                "**Cảnh báo dữ liệu:** Một số lớp thiếu thí nghiệm — "
                                "đã dùng giả định / bỏ qua ma sát.\n\n"
                                + "\n\n".join(f"- {w}" for w in _warns.split("; "))
                            )

                        _cn1, _cn2 = st.columns(2)
                        with _cn1:
                            st.markdown("**NT1 — Chiều dài xuyên qua lớp yếu**")
                            st.metric(
                                "Kết quả NT1", _res1,
                                delta=f"Biên an toàn = {_marg1:+.2f} m",
                                delta_color="normal" if _marg1 >= 0 else "inverse",
                            )
                            st.caption(
                                f"L thiết kế = **{_L_d:.1f} m** | L yêu cầu = {_L_req1:.1f} m  \n"
                                f"Đáy lớp mềm = {_D_bot:.2f} m [{_D_src}]  \n"
                                f"Z mặt đất = {_Z_m:.3f} m [{_Z_src}] | "
                                f"Đất đắp = {_fill_m:.2f} m | Trong đất = {_L_soil:.2f} m"
                            )
                        with _cn2:
                            st.markdown("**NT2 — Sức kháng nhổ (TCVN 11823-10:2017)**")
                            st.metric(
                                "Kết quả NT2", _res2,
                                delta=f"RR/W = {_rat2:.2f}",
                                delta_color="normal" if _rat2 >= 1 else "inverse",
                            )
                            _rs_parts = []
                            if _Rs_clay is not None:
                                _rs_parts.append(f"sét={_Rs_clay:.0f}")
                            if _Rs_sand is not None:
                                _rs_parts.append(f"cát={_Rs_sand:.0f}")
                            _rs_breakdown = " (" + " + ".join(_rs_parts) + ")" if _rs_parts else ""
                            _tip_info = f"**{_tip_sym}** [{_tip_meth or 'alpha'}]"
                            if _tip_meth == "SPT":
                                _tip_info += f" — N₁₆₀={_tip_N160:.0f}" if _tip_N160 else " — không SPT"
                            else:
                                _tip_info += f" — su={_tip_su:.0f} kPa"
                            st.caption(
                                f"Rs = {_Rs:.0f} kN{_rs_breakdown} | Rp = {_Rp:.0f} kN  \n"
                                f"RR = φ × (Rs + Rp) = {_RR:.0f} kN | W = {_W:.0f} kN  \n"
                                f"φ_stat = **{_phi:.2f}** ({_phi_basis or 'mặc định'})  \n"
                                f"Lớp mũi cọc: {_tip_info}"
                            )

                        _con2 = sqlite3.connect(str(_DB))
                        _cur2 = _con2.cursor()
                        _cur2.execute(
                            "SELECT l.symbol, l.L_m, l.su_kPa, l.su_source, "
                            "l.alpha, l.method, l.N160, l.sigma_v_eff_kPa, "
                            "l.gamma_kNm3, l.Rs_kN, l.note "
                            "FROM ke_sw_nt2_layers l "
                            "JOIN ke_sw_nt_detail d ON l.sw_design_id = d.id "
                            "WHERE d.bh_name=? ORDER BY l.layer_order",
                            (_bh_n,),
                        )
                        _lyrs = _cur2.fetchall()
                        _con2.close()
                        if _lyrs:
                            _ldf = []
                            for (_sym, _Llyr, _su, _su_src, _alp, _meth,
                                 _N, _sigv, _gam, _Rs_lyr, _note) in _lyrs:
                                _ldf.append({
                                    "Lớp đất":      _sym,
                                    "L (m)":        round(_Llyr, 2),
                                    "Phương pháp":  _meth or "alpha",
                                    "su (kPa)":     round(_su, 1) if _su else 0,
                                    "α":            round(_alp, 3) if _alp else 0,
                                    "N₁₆₀":        round(_N, 1) if _N is not None else "—",
                                    "γ (kN/m³)":   round(_gam, 1) if _gam else "—",
                                    "σ'v (kPa)":   round(_sigv, 0) if _sigv else "—",
                                    "Nguồn":        _SRC_LBL.get(_su_src or "", _su_src or ""),
                                    "Rs lớp (kN)":  round(_Rs_lyr, 1),
                                })
                            st.dataframe(
                                pd.DataFrame(_ldf),
                                hide_index=True,
                                use_container_width=True,
                            )
                        st.caption(
                            f"Cọc: {_pile_t} | L thiết kế = {_L_d:.1f} m | "
                            f"Chiều sâu mũi cọc = {_tip_d:.2f} m  \n"
                            "Phương pháp: **alpha** (Tomlinson, sét) · **SPT** (Meyerhof, cát) — "
                            "TCVN 11823-10:2017 Điều 7.3.8.6"
                        )
                        st.divider()
            except Exception as _exc_nt:
                st.error(f"Lỗi khi đọc dữ liệu NT: {_exc_nt}")

    # ── C. Kiểm tra NT1 / NT2 tùy chỉnh ────────────────────────────────────────
    st.divider()
    st.markdown("### C. Kiểm tra NT1 / NT2 — nhập thông số tùy chỉnh")
    st.info(
        "Tiêu chuẩn: TCVN 11823-10:2017, Điều 7.3.8.6.2 (phương pháp alpha).  \n"
        "NT1 = kiểm tra chiều dài xuyên qua lớp yếu.  \n"
        "NT2: RR = φ_stat × (Rs + Rp) ≥ W_cọc  |  φ_stat = 0,35  |  bỏ qua đất đắp khi tính Rs."
    )

    _col_form, _col_schem = st.columns([3, 2], gap="large")

    with _col_form:
        _c1, _c2, _c3 = st.columns(3)
        with _c1:
            _sw_sel   = st.selectbox("Loại cọc SW", _sw_names,
                                     index=_sw_names.index("SW-840") if "SW-840" in _sw_names else 0,
                                     key="sw_sel")
            _L_des    = st.number_input("Chiều dài thiết kế L (m)", 10.0, 35.0, 29.0, 0.5, key="sw_L")
            _top_ke   = st.number_input("Cao độ đỉnh kè (m)", 0.0, 5.0, 2.70, 0.05, key="sw_top_ke")
        with _c2:
            _Z_nat    = st.number_input("Cao độ mặt đất tự nhiên (m)", -5.0, 3.0, -0.80, 0.05, key="sw_Z")
            _H_lyr1   = st.number_input("Chiều dày lớp bùn sét H₁ (m)", 5.0, 35.0, 22.0, 0.5, key="sw_H1")
            _su_avg   = st.number_input("Su trung bình lớp bùn (kN/m²)", 5.0, 50.0, 10.0, 1.0, key="sw_su")
        with _c3:
            _alpha_sw = st.number_input("Hệ số bám α", 0.5, 1.0, 1.0, 0.05, key="sw_alpha")
            _phi_stat = st.number_input("φ_stat (TCVN 11823-10)", 0.1, 0.5, 0.35, 0.01, key="sw_phi")
            _min_pen  = st.number_input("Xuyên qua lớp cứng tối thiểu (m)", 0.5, 3.0, 1.0, 0.5, key="sw_pen")
        _wc1, _wc2 = st.columns(2)
        _water_lvl_c = _wc1.number_input("Mực nước (m)", -5.0, 3.0, -1.0, 0.5, key="sw_wlvl")
        _bc_type_c   = _wc2.selectbox("Liên kết đáy cọc", ["Fixed", "Free", "Cantilever"], key="sw_bc")

    with _col_schem:
        if _HAS_MPL:
            _lyr_mid = _Z_nat - _H_lyr1
            _pile_tip = _top_ke - _L_des
            _layers_sch = [
                ("Bùn sét", _Z_nat,    _lyr_mid,  16.0, 0.0),
                ("Lớp cứng", _lyr_mid, _pile_tip,  18.0, 20.0),
            ]
            _fig_sch = draw_pile_schematic(
                L_m=_L_des, water_lvl=_water_lvl_c, top_elev=_top_ke,
                H_kN=0, M_kNm=0, layers=_layers_sch, bc_type=_bc_type_c,
                soil_lvl_front=_Z_nat, soil_lvl_back=_Z_nat,
                water_lvl_back=_water_lvl_c,
            )
            if _fig_sch:
                st.pyplot(_fig_sch, use_container_width=True)
                plt.close(_fig_sch)

    if st.button("Kiểm tra NT1 / NT2", type="primary", key="sw_check"):
        _pile = _sw_by_name(_sw_sel)
        if _pile is None:
            st.error(f"Không tìm thấy cọc {_sw_sel} trong catalog.")
        else:
            _TL_T    = _pile.get("weight_T", 0) or 0
            _Lstd    = _pile.get("L_std_m", 1) or 1
            _spc_m   = (_pile.get("width_mm", 996)) / 1000
            _peri_m  = (_pile.get("perimeter_mm") or 0) / 1000
            _Ap_m2   = (_pile.get("Atd_cm2", 0) or 0) * 1e-4

            _w_per_pile = _TL_T * 9.81 / _Lstd
            _W_pile     = _w_per_pile * _L_des

            _L_req_nt1  = _top_ke - _Z_nat + _H_lyr1 + _min_pen
            _nt1_ok     = _L_des >= _L_req_nt1
            _nt1_margin = _L_des - _L_req_nt1

            _fill_m    = _top_ke - _Z_nat
            _L_soil_m  = max(0.0, _L_des - _fill_m)
            _Rs_kN     = _alpha_sw * _su_avg * _peri_m * _L_soil_m if _peri_m > 0 else 0
            _Rp_kN     = 9.0 * _su_avg * _Ap_m2
            _RR_kN     = _phi_stat * (_Rs_kN + _Rp_kN)
            _nt2_ok    = _RR_kN >= _W_pile
            _ratio_nt2 = _RR_kN / _W_pile if _W_pile > 0 else 0

            _r1, _r2, _r3, _r4 = st.columns(4)
            _r1.metric("NT1 — L yêu cầu (m)", f"{_L_req_nt1:.1f}",
                       f"{'Đạt' if _nt1_ok else 'Không đạt'} (biên {_nt1_margin:+.1f} m)",
                       delta_color="normal" if _nt1_ok else "inverse")
            _r2.metric("W cọc (kN)", f"{_W_pile:.1f}",
                       f"{_TL_T:.2f} T × 9.81 / {_Lstd}m × {_L_des}m")
            _r3.metric("RR = φ(Rs+Rp) (kN)", f"{_RR_kN:.1f}",
                       f"Rs={_Rs_kN:.0f}  Rp={_Rp_kN:.0f}",
                       delta_color="normal" if _nt2_ok else "inverse")
            _r4.metric("NT2 — Tỷ số RR/W", f"{_ratio_nt2:.2f}",
                       "Đạt" if _nt2_ok else "Không đạt",
                       delta_color="normal" if _nt2_ok else "inverse")

            st.dataframe(
                pd.DataFrame({
                    "Thông số": [
                        "Loại cọc", "Chiều dài L (m)", "Spacing (m)", "Chu vi P (m)",
                        "Diện tích mũi Ap (cm²)", "w (kN/m/cọc)", "W cọc (kN)",
                        "Phần đất đắp (m)", "Phần trong đất L_soil (m)",
                        "Rs (kN)", "Rp (kN)", "RR = φ×(Rs+Rp) (kN)", "Kết quả NT2",
                    ],
                    "Giá trị": [
                        _sw_sel, f"{_L_des:.1f}", f"{_spc_m:.3f}",
                        f"{_peri_m:.4f}" if _peri_m > 0 else "– (chưa có trong catalog)",
                        f"{_Ap_m2*1e4:.0f}",
                        f"{_w_per_pile:.2f}", f"{_W_pile:.1f}",
                        f"{_fill_m:.2f}", f"{_L_soil_m:.2f}",
                        f"{_Rs_kN:.1f}", f"{_Rp_kN:.1f}", f"{_RR_kN:.1f}",
                        "Đạt" if _nt2_ok else "Không đạt",
                    ],
                }).style.apply(
                    lambda col: [
                        "background-color:#d4edda" if "Đạt" in str(v) and "Không" not in str(v)
                        else "background-color:#f8d7da" if "Không đạt" in str(v)
                        else "" for v in col
                    ],
                    subset=["Giá trị"],
                ),
                use_container_width=True, hide_index=True,
            )

            if _peri_m == 0:
                st.warning(
                    f"Cọc {_sw_sel} chưa có chu vi trong catalog (perimeter_mm = null). "
                    "Rs = 0. Cần bổ sung thông số từ nhà sản xuất để tính NT2 chính xác."
                )
            st.caption(
                "Công thức: Rs = α × Su × P × L_soil  |  "
                "Rp = 9 × Su × Ap  |  RR = 0,35 × (Rs + Rp)  |  "
                "Bỏ qua đất đắp khi tính Rs (TCVN 11823-10 Điều 7.3.8.6.2)"
            )

    # ── C.2 SPT-Meyerhof cho lớp cát ────────────────────────────────────────────
    st.divider()
    st.markdown("### C.2. Kiểm tra SPT-Meyerhof — lớp cát (Điều 7.3.8.6.7)")
    st.info(
        "Áp dụng cho cọc trong cát/cát bột.  \n"
        "qs = 0,0019·N₁₆₀ (cọc chiếm chỗ — SW) hoặc 0,00096·N₁₆₀ (chữ H / ống hở), MPa  \n"
        "qp = 0,038·N₁₆₀·(Db/D) ≤ λq · MPa  |  λq cát = 3,2·N₁₆₀ MPa  |  φ_stat = 0,30"
    )

    _spt_c1, _spt_c2, _spt_c3 = st.columns(3)
    with _spt_c1:
        _spt_sw    = st.selectbox("Loại cọc SW", _sw_names,
                                  index=_sw_names.index("SW-840") if "SW-840" in _sw_names else 0,
                                  key="spt_sw_sel")
        _spt_L     = st.number_input("L cọc trong cát (m)", 1.0, 30.0, 5.0, 0.5, key="spt_L")
        _spt_disp  = st.checkbox("Cọc chiếm chỗ (SW = chiếm chỗ)",
                                 value=True, key="spt_displacing")
    with _spt_c2:
        _spt_N160  = st.number_input("N₁₆₀ trung bình lớp cát", 0.0, 100.0, 15.0, 1.0,
                                     key="spt_N160",
                                     help="N hiệu chỉnh CN = √(100/σ'v), clamp [0.5, 2.0]")
        _spt_Db    = st.number_input("Db — mũi cọc trong tầng cát (m)", 0.1, 20.0, 2.0, 0.1,
                                     key="spt_Db",
                                     help="Db = chiều sâu mũi cọc DƯỚI đỉnh tầng cát chịu lực")
        _spt_silt  = st.checkbox("Cát bột (giảm λq từ 3,2 → 1,8·N₁₆₀)",
                                 value=False, key="spt_silt")
    with _spt_c3:
        _spt_phi   = st.number_input("φ_stat SPT", 0.1, 0.5, 0.30, 0.01, key="spt_phi")
        _spt_W     = st.number_input("W cọc (kN)", 0.0, 500.0, 211.0, 1.0, key="spt_W",
                                     help="Trọng lượng cọc tự chống nhổ")

    if st.button("Kiểm tra SPT-Meyerhof", type="primary", key="spt_check"):
        _sp_pile = _sw_by_name(_spt_sw)
        if _sp_pile is None:
            st.error(f"Không tìm thấy cọc {_spt_sw}.")
        else:
            _sp_P   = (_sp_pile.get("perimeter_mm") or 0) / 1000.0
            _sp_Ap  = (_sp_pile.get("Atd_cm2", 0) or 0) * 1e-4
            _sp_D   = (_sp_pile.get("H_mm", 840) or 840) / 1000.0

            # qs (kPa) = (1.9 nếu chiếm chỗ else 0.96) × N160
            _sp_qs  = (1.9 if _spt_disp else 0.96) * _spt_N160
            _sp_Rs  = _sp_qs * _sp_P * _spt_L
            # qp (kPa) = 38 × N160 × Db/D, giới hạn λq
            _sp_qp_raw = 38.0 * _spt_N160 * (_spt_Db / _sp_D)
            _sp_lambda_q = (1800.0 if _spt_silt else 3200.0) * _spt_N160
            _sp_qp  = min(_sp_qp_raw, _sp_lambda_q)
            _sp_qp_capped = _sp_qp_raw > _sp_lambda_q
            _sp_Rp  = _sp_qp * _sp_Ap
            _sp_RR  = _spt_phi * (_sp_Rs + _sp_Rp)
            _sp_ratio = _sp_RR / _spt_W if _spt_W > 0 else 0
            _sp_ok  = _sp_RR >= _spt_W

            _sr1, _sr2, _sr3, _sr4 = st.columns(4)
            _sr1.metric("qs (kPa)", f"{_sp_qs:.1f}",
                        f"{'chiếm chỗ' if _spt_disp else 'không chiếm chỗ'}")
            _sr2.metric("qp (kPa)", f"{_sp_qp:.1f}",
                        f"{'đã cắt λq' if _sp_qp_capped else f'raw={_sp_qp_raw:.0f}'}",
                        delta_color="off")
            _sr3.metric("RR = φ(Rs+Rp) (kN)", f"{_sp_RR:.1f}",
                        f"Rs={_sp_Rs:.0f}  Rp={_sp_Rp:.0f}",
                        delta_color="normal" if _sp_ok else "inverse")
            _sr4.metric("Tỷ số RR/W", f"{_sp_ratio:.2f}",
                        "Đạt" if _sp_ok else "Không đạt",
                        delta_color="normal" if _sp_ok else "inverse")

            st.dataframe(
                pd.DataFrame({
                    "Thông số": [
                        "Cọc", "Chu vi P (m)", "Bề rộng D (m)", "Diện tích mũi Ap (cm²)",
                        "N₁₆₀", "L cát (m)", "Db (m)",
                        "qs (kPa)", "qp_raw (kPa)", "λq giới hạn (kPa)", "qp dùng (kPa)",
                        "Rs (kN)", "Rp (kN)", "RR = φ(Rs+Rp) (kN)", "W (kN)", "Kết quả",
                    ],
                    "Giá trị": [
                        _spt_sw, f"{_sp_P:.4f}", f"{_sp_D:.3f}", f"{_sp_Ap*1e4:.0f}",
                        f"{_spt_N160:.1f}", f"{_spt_L:.1f}", f"{_spt_Db:.2f}",
                        f"{_sp_qs:.2f}", f"{_sp_qp_raw:.1f}", f"{_sp_lambda_q:.0f}",
                        f"{_sp_qp:.1f}",
                        f"{_sp_Rs:.1f}", f"{_sp_Rp:.1f}", f"{_sp_RR:.1f}",
                        f"{_spt_W:.0f}", "Đạt" if _sp_ok else "Không đạt",
                    ],
                }),
                use_container_width=True, hide_index=True,
            )

    # ── C.3 So sánh 4 phương pháp NT2 ──────────────────────────────────────────
    st.divider()
    st.markdown("### C.3. So sánh 4 phương pháp NT2 cho 1 hố khoan")
    st.info(
        "So sánh Rs/Rp/RR theo 4 phương pháp TCVN 11823-10:2017 cho cùng 1 HK + 1 cọc:  \n"
        "**α** (Tomlinson 1980, sét, Điều 7.3.8.6.2, φ=0,35) · "
        "**β** (Esrig & Kirby 1979, sét, Điều 7.3.8.6.3, φ=0,25) · "
        "**λ** (Vijayvergiya & Focht 1972, cọc ống, Điều 7.3.8.6.4, φ=0,40) · "
        "**SPT-Meyerhof** (cát, Điều 7.3.8.6.7, φ=0,30)"
    )

    _cmp_c1, _cmp_c2, _cmp_c3 = st.columns(3)
    try:
        import sys as _sys_cmp
        _sys_cmp.path.insert(0, str(_ROOT / "scripts"))
        from ke_sw_nt_calc import (
            calc_nt2_all_methods as _calc_4m,
            _load_catalog as _load_cat,
            _get_bh_Z_m as _get_bh_z,
        )
        _cat_cmp = _load_cat()
        _ke_bhs  = ["KE-HK2", "KE-HK3", "KE-HK7", "KE-HK8", "KE-HK9", "KE-HK10", "KE-HK11"]
        with _cmp_c1:
            _cmp_bh = st.selectbox("Hố khoan", _ke_bhs, key="cmp_bh")
        with _cmp_c2:
            _cmp_pile_name = st.selectbox("Loại cọc",
                                          list(_cat_cmp.keys()),
                                          index=list(_cat_cmp.keys()).index("SW-840")
                                          if "SW-840" in _cat_cmp else 0,
                                          key="cmp_pile")
        with _cmp_c3:
            _cmp_L = st.number_input("L thiết kế (m)", 10.0, 35.0, 29.0, 0.5, key="cmp_L")

        if st.button("So sánh 4 phương pháp", type="primary", key="btn_cmp4"):
            _cmp_z = _get_bh_z(_cmp_bh) or 0.0
            _cmp_res = _calc_4m(_cmp_bh, _cmp_z, _cmp_pile_name,
                                _cat_cmp[_cmp_pile_name], _cmp_L)
            _common = _cmp_res["common"]

            # Hiển thị thông số chung
            _ic1, _ic2, _ic3, _ic4 = st.columns(4)
            _ic1.metric("L cọc trong sét (m)", f"{_common['L_clay_total_m']:.2f}")
            _ic2.metric("Su TB sét (kPa)", f"{_common['su_avg_clay_kPa']:.1f}")
            _ic3.metric("σ'v TB sét (kPa)", f"{_common['sigma_avg_clay_kPa']:.0f}")
            _ic4.metric("W cọc (kN)", f"{_common['W_kN']:.0f}",
                        f"D={_common['D_m']:.3f}m, P={_common['perimeter_m']:.3f}m")

            # Bảng so sánh 5 phương pháp
            _cmp_rows = []
            _method_lbl = {
                "auto":   "Auto (α+SPT)",
                "alpha":  "α-method",
                "beta":   "β-method",
                "lambda": "λ-method",
                "SPT":    "SPT (all clay)",
            }
            for m in ["auto", "alpha", "beta", "lambda", "SPT"]:
                x = _cmp_res[m]
                _cmp_rows.append({
                    "Phương pháp":  _method_lbl[m],
                    "φ_stat":       x["phi_stat"],
                    "Rs (kN)":      x["Rs_kN"],
                    "Rp (kN)":      x["Rp_kN"],
                    "RR (kN)":      x["RR_kN"],
                    "W (kN)":       _common["W_kN"],
                    "Tỷ số RR/W":   x["ratio"],
                    "Kết quả":      x["result"],
                    "tip method":   x.get("tip_method", "—"),
                })
            _cmp_df = pd.DataFrame(_cmp_rows)

            def _hl_cmp(val):
                if val == "Đạt":
                    return "background-color:#d4edda; color:#155724"
                if val == "Không đạt":
                    return "background-color:#f8d7da; color:#721c24"
                return ""

            st.dataframe(
                _cmp_df.style.map(_hl_cmp, subset=["Kết quả"]),
                use_container_width=True, hide_index=True,
                column_config={
                    "φ_stat":     st.column_config.NumberColumn(format="%.2f"),
                    "Rs (kN)":    st.column_config.NumberColumn(format="%.0f"),
                    "Rp (kN)":    st.column_config.NumberColumn(format="%.0f"),
                    "RR (kN)":    st.column_config.NumberColumn(format="%.0f"),
                    "W (kN)":     st.column_config.NumberColumn(format="%.0f"),
                    "Tỷ số RR/W": st.column_config.NumberColumn(format="%.2f"),
                },
            )
            st.caption(
                f"λ_coef = {_common['lambda_coef']:.3f} (Vijayvergiya & Focht — theo L cọc sét {_common['L_clay_total_m']:.1f}m). "
                "**Khuyến nghị TCVN**: dùng `auto` (α cho sét, SPT cho cát) — phản ánh đúng từng lớp. "
                "α/β/λ chỉ áp dụng cho lớp sét; SPT (all clay) là sai phương pháp cho minh hoạ."
            )

            if _HAS_PLOTLY:
                _fig_cmp = go.Figure()
                _fig_cmp.add_trace(go.Bar(
                    x=[r["Phương pháp"] for r in _cmp_rows],
                    y=[r["RR (kN)"] for r in _cmp_rows],
                    name="RR (kN)",
                    marker_color=["#1565C0" if r["Kết quả"] == "Đạt" else "#E53935"
                                   for r in _cmp_rows],
                    text=[f"{r['Tỷ số RR/W']:.2f}" for r in _cmp_rows],
                    textposition="outside",
                ))
                _fig_cmp.add_hline(
                    y=_common["W_kN"], line_dash="dash", line_color="#666",
                    annotation_text=f"W = {_common['W_kN']:.0f} kN",
                    annotation_position="bottom right",
                )
                _fig_cmp.update_layout(
                    title=f"So sánh RR theo 4 phương pháp — {_cmp_bh} / {_cmp_pile_name}",
                    yaxis_title="RR = φ·(Rs+Rp) (kN)",
                    height=360, margin=dict(t=45, b=40),
                )
                st.plotly_chart(_fig_cmp, use_container_width=True)
    except Exception as _e_cmp:
        st.warning(f"Không thực hiện được so sánh 4 phương pháp: {_e_cmp}")

    # ── Xuất PDF tab Cọc ván SW ──────────────────────────────────────────────
    if _HAS_PDF:
        st.divider()
        try:
            _pdf_k = _pdf_kesw(_DB)
            st.download_button(
                "Xuất PDF tab Cọc ván SW",
                data=_pdf_k,
                file_name=f"CocVanSW_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as _e:
            st.warning(f"Không tạo PDF: {_e}")

# ── Placeholder: TKBVTC CDM ──────────────────────────────────────────────────
if _page == "cdm_bvt":
    st.markdown("## TKBVTC CDM")
    st.info("Trang đang phát triển — thiết kế bản vẽ thi công CDM.")

# ── Placeholder: TKBVTC Cọc SW ───────────────────────────────────────────────
if _page == "sw_bvt":
    st.markdown("## TKBVTC Cọc SW")
    st.info("Trang đang phát triển — thiết kế bản vẽ thi công cọc ván SW.")
