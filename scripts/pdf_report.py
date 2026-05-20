"""
pdf_report.py — Pipeline báo cáo PDF chuyên nghiệp

Pipeline:
1. Data input    → pandas.read_csv / read_excel / sqlite
2. Calculations  → numpy + sympy (formula symbolic)
3. Visualizations → plotly (kaleido PNG) + matplotlib
4. Tables        → pandas.to_html + CSS styling
5. Report layout → Jinja2 template + HTML/CSS
6. Export        → WeasyPrint HTML → PDF

Public API:
- build_report_pdf(title, sections) → bytes
- mpl_to_b64(fig) / plotly_to_b64(fig) — embed figures
- df_to_html(df, caption=None) — styled tables
"""
from __future__ import annotations
import base64
import io
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
from jinja2 import Template
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

_ROOT = Path(__file__).resolve().parent.parent

# ─── CSS chung cho mọi báo cáo ──────────────────────────────────────────────
_REPORT_CSS = """
@page {
  size: A4;
  margin: 15mm 12mm 18mm 12mm;
  @top-right {
    content: "PLAXIS AI Copilot — Báo cáo TTHC";
    font-size: 8pt;
    color: #888;
  }
  @bottom-center {
    content: "Trang " counter(page) " / " counter(pages);
    font-size: 8pt;
    color: #555;
  }
  @bottom-left {
    content: string(report-date);
    font-size: 7pt;
    color: #888;
  }
}
body {
  font-family: "DejaVu Sans", "Arial", "Helvetica", sans-serif;
  font-size: 10pt;
  line-height: 1.45;
  color: #1A1A1A;
}
.report-date {
  string-set: report-date content();
  display: none;
}
.cover {
  text-align: center;
  margin-top: 5cm;
  page-break-after: always;
}
.cover h1 {
  font-size: 22pt;
  color: #1F4E79;
  margin-bottom: 1cm;
}
.cover .subtitle {
  font-size: 13pt;
  color: #555;
  margin-bottom: 2cm;
}
.cover .meta {
  font-size: 10pt;
  color: #666;
  line-height: 1.8;
}
h1 {
  font-size: 14pt;
  color: #1F4E79;
  border-bottom: 2px solid #1F4E79;
  padding-bottom: 4px;
  margin-top: 18pt;
  page-break-after: avoid;
}
h2 {
  font-size: 11.5pt;
  color: #1F4E79;
  margin-top: 12pt;
  page-break-after: avoid;
}
h3 {
  font-size: 10.5pt;
  color: #444;
  margin-top: 8pt;
  page-break-after: avoid;
}
p { margin: 4pt 0; }
.caption {
  font-size: 8.5pt;
  color: #666;
  font-style: italic;
  text-align: center;
  margin: 2pt 0 8pt 0;
}
table {
  border-collapse: collapse;
  width: 100%;
  margin: 6pt 0;
  page-break-inside: avoid;
  font-size: 8.5pt;
}
table th {
  background-color: #1F4E79;
  color: white;
  font-weight: 600;
  padding: 5px 6px;
  text-align: center;
  border: 0.5px solid #888;
}
table td {
  padding: 4px 6px;
  border: 0.5px solid #BBB;
  text-align: center;
  vertical-align: middle;
}
table tr:nth-child(even) td {
  background-color: #F5F8FB;
}
table tr.pass td { background-color: #E8F5E9; }
table tr.fail td { background-color: #FFEBEE; }
.fig-block {
  text-align: center;
  margin: 8pt 0;
  page-break-inside: avoid;
}
.fig-block img {
  max-width: 100%;
  max-height: 14cm;
  object-fit: contain;
}
.metric-row {
  display: flex;
  gap: 8pt;
  margin: 8pt 0;
  page-break-inside: avoid;
}
.metric-card {
  flex: 1;
  border: 1px solid #BBDEFB;
  border-radius: 4px;
  padding: 6pt;
  background: #F5F8FB;
}
.metric-card .label {
  font-size: 8pt;
  color: #555;
  text-transform: uppercase;
}
.metric-card .value {
  font-size: 14pt;
  color: #1F4E79;
  font-weight: 700;
}
.metric-card .delta {
  font-size: 8.5pt;
  color: #2E7D32;
}
.metric-card .delta.neg { color: #C62828; }
.warning {
  background: #FFF8E1;
  border-left: 3px solid #F9A825;
  padding: 6pt 8pt;
  margin: 6pt 0;
  font-size: 9pt;
}
.info {
  background: #E3F2FD;
  border-left: 3px solid #1565C0;
  padding: 6pt 8pt;
  margin: 6pt 0;
  font-size: 9pt;
}
.formula {
  font-family: "DejaVu Sans Mono", "Courier New", monospace;
  background: #F5F5F5;
  padding: 6pt;
  margin: 4pt 0;
  border-left: 2px solid #888;
  font-size: 9pt;
  page-break-inside: avoid;
}
.page-break { page-break-after: always; }
"""

# ─── Helpers: figures → base64 ──────────────────────────────────────────────
def mpl_to_b64(fig, dpi: int = 130) -> str:
    """Matplotlib Figure → data URI."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def plotly_to_b64(fig, width: int = 1000, height: int = 500) -> str:
    """Plotly Figure → data URI (cần kaleido)."""
    try:
        png_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
        return "data:image/png;base64," + base64.b64encode(png_bytes).decode()
    except Exception as e:
        return ""  # fallback: skip image silently


def df_to_html(df: pd.DataFrame, caption: str | None = None,
               pass_col: str | None = None) -> str:
    """Pandas DataFrame → HTML table với CSS class.
    pass_col: tên cột (vd 'Kết quả') chứa 'Đạt'/'Không đạt' để tô màu hàng."""
    if df.empty:
        return "<p><em>(Không có dữ liệu)</em></p>"
    if pass_col and pass_col in df.columns:
        rows_html = []
        for _, row in df.iterrows():
            val = str(row[pass_col])
            cls = "pass" if val == "Đạt" else ("fail" if val == "Không đạt" else "")
            cells = "".join(f"<td>{'—' if pd.isna(v) else v}</td>" for v in row)
            rows_html.append(f'<tr class="{cls}">{cells}</tr>')
        thead = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in df.columns) + "</tr></thead>"
        tbody = "<tbody>" + "".join(rows_html) + "</tbody>"
        html = f"<table>{thead}{tbody}</table>"
    else:
        html = df.to_html(index=False, na_rep="—", border=0, escape=False)
    if caption:
        html += f'<div class="caption">{caption}</div>'
    return html


def metric_card(label: str, value: str, delta: str | None = None,
                positive: bool = True) -> str:
    delta_html = (
        f'<div class="delta {"" if positive else "neg"}">{delta}</div>'
        if delta else ""
    )
    return (f'<div class="metric-card">'
            f'<div class="label">{label}</div>'
            f'<div class="value">{value}</div>'
            f'{delta_html}</div>')


# ─── Template chính ─────────────────────────────────────────────────────────
_REPORT_TEMPLATE = Template("""
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>{{ title }}</title>
<style>{{ css }}</style>
</head>
<body>
<span class="report-date">{{ date }}</span>
{% if cover %}
<div class="cover">
  <h1>{{ title }}</h1>
  <div class="subtitle">{{ subtitle }}</div>
  <div class="meta">
    {% for k, v in meta.items() %}
      <div><strong>{{ k }}:</strong> {{ v }}</div>
    {% endfor %}
  </div>
</div>
{% endif %}
{{ content | safe }}
</body>
</html>
""")


def build_report_pdf(
    title: str,
    content_html: str,
    subtitle: str = "",
    meta: dict | None = None,
    cover: bool = True,
) -> bytes:
    """Compose HTML từ template + render qua WeasyPrint."""
    html_str = _REPORT_TEMPLATE.render(
        title=title,
        subtitle=subtitle,
        meta=meta or {},
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        css=_REPORT_CSS,
        content=content_html,
        cover=cover,
    )
    font_config = FontConfiguration()
    pdf_bytes = HTML(string=html_str).write_pdf(font_config=font_config)
    return pdf_bytes


# ────────────────────────────────────────────────────────────────────────────
# CONCRETE REPORTS
# ────────────────────────────────────────────────────────────────────────────
def report_params(state: dict) -> bytes:
    parts = []
    parts.append("<h1>1. Thông tin chung</h1>")
    parts.append(f"<p>Khu vực: <strong>{state.get('cdm_zone','—')}</strong> | "
                 f"Hố khoan: <strong>{state.get('cdm_bh','—')}</strong></p>")

    parts.append("<h1>2. Hình học cọc CDM</h1>")
    df = pd.DataFrame({
        "Tham số":  ["Đường kính D", "Khoảng cách e", "Cao độ đỉnh CDTK",
                     "Chiều dài Lc", "Ngàm vào đất tốt", "Bố trí"],
        "Giá trị":  [f"{state.get('cdm_D',0.8):.2f}",
                     f"{state.get('cdm_e',1.6):.2f}",
                     f"{state.get('cdm_CDTK',2.7):+.2f}",
                     f"{state.get('cdm_Lc',23):.1f}",
                     f"{state.get('cdm_L_ngam',0.5):.1f}",
                     "Tam giác" if state.get('cdm_arrangement') == "triangle" else "Vuông"],
        "Đơn vị":  ["m", "m", "m", "m", "m", "—"],
    })
    parts.append(df_to_html(df))

    parts.append("<h1>3. Vật liệu CDM</h1>")
    df = pd.DataFrame({
        "Tham số":  ["Loại xi măng", "Hàm lượng XM", "Tỷ lệ N/XM",
                     "qu thiết kế", "FS phòng thí nghiệm"],
        "Giá trị":  [state.get("cdm_cement_type", "PCB40"),
                     f"{state.get('cdm_dosage', 250):.0f}",
                     f"{state.get('cdm_WC', 0.8):.2f}",
                     f"{state.get('cdm_qu', 1000):.0f}",
                     f"{state.get('cdm_FS_lab', 1.5):.2f}"],
        "Đơn vị":  ["—", "kg/m³", "—", "kPa", "—"],
    })
    parts.append(df_to_html(df))

    parts.append("<h1>4. Thông số địa chất</h1>")
    df = pd.DataFrame({
        "Tham số":  ["Đỉnh lớp bùn", "Chiều dày h_clay", "Su trung bình", "γ đất"],
        "Giá trị":  [f"{state.get('cdm_top_clay',-1):+.2f}",
                     f"{state.get('cdm_h_clay',22):.1f}",
                     f"{state.get('cdm_Su',10):.1f}",
                     f"{state.get('cdm_gamma',16):.1f}"],
        "Đơn vị":  ["m", "m", "kPa", "kN/m³"],
    })
    parts.append(df_to_html(df))

    parts.append("<h1>5. Tải trọng</h1>")
    ld = state.get("cdm_loads", {})
    df = pd.DataFrame({
        "Tham số":  ["Tải xe q_traffic", "Mặt đường h_road",
                     "He — cát đắp", "Hse — đệm cát",
                     "Cao độ thiết kế z_tk"],
        "Giá trị":  [f"{ld.get('q_traffic',20):.1f}",
                     f"{ld.get('h_road',0.8):.2f}",
                     f"{ld.get('h_fill',1.5):.2f}",
                     f"{ld.get('h_mat',0.4):.2f}",
                     f"{ld.get('z_tk',3.5):+.2f}"],
        "Đơn vị":  ["kN/m²", "m", "m", "m", "m"],
    })
    parts.append(df_to_html(df))

    parts.append("<h1>6. Công thức TCVN 9403:2012</h1>")
    parts.append("""
<div class="formula">Cc_field = field_lab_ratio × qu_lab / 2  (kPa)<br>
Ec = 75 × Cc_field  (kPa) — TCVN 9403 B.5.1<br>
Es = 250 × Su  (kPa) — tương quan Mesri<br>
a = π·D²/(4·e²)·k   (k=1 vuông, 2/√3 tam giác)<br>
E_composite = a·Ec + (1-a)·Es  (kPa)<br>
S1 = q × H_soft / E_composite  (m) — lún đàn hồi</div>
""")

    return build_report_pdf(
        title="BÁO CÁO THÔNG SỐ CDM",
        subtitle="Cọc đất xi măng — Dự án 202605 TTHC",
        content_html="\n".join(parts),
        meta={
            "Khu vực": state.get("cdm_zone", "—"),
            "Hố khoan": state.get("cdm_bh", "—"),
            "Tiêu chuẩn": "TCVN 9403:2012 + TCCS 41:2022",
        },
    )


def report_settlement(state: dict, result: dict | None = None) -> bytes:
    parts = []
    parts.append("<h1>1. Thông tin chung</h1>")
    parts.append(f"<p>Khu vực: <strong>{state.get('sl_zone','—')}</strong> | "
                 f"Hố khoan: <strong>{state.get('sl_bh','—')}</strong></p>")

    if result is None:
        parts.append('<div class="warning">'
                     "Chưa có kết quả tính lún. Vào tab 'Dự báo lún', nhấn 'Tính toán lún' rồi xuất lại PDF."
                     "</div>")
    else:
        parts.append("<h1>2. So sánh phương án xử lý</h1>")
        rows = []
        for sc in result["scenarios"]:
            t90 = f"{sc['t_90_months']:.0f}" if sc.get("t_90_months") else ">240"
            rows.append({
                "Phương án":      sc["label"],
                "Lún tổng (cm)":  round(sc["S_total_cm"], 1),
                "Lún tại TC (cm)": round(sc["S_at_constr_cm"], 1),
                "U TC (%)":       f"{sc['U_at_constr_pct']:.0f}",
                "Lún còn lại (cm)": round(sc["residual_cm"], 1),
                "t90 (tháng)":    t90,
                "Surcharge (m)":  round(sc.get("H_surcharge_m", 0), 1),
                "Kết quả":        "Đạt" if sc["feasible"] else "Không đạt",
            })
        df = pd.DataFrame(rows)
        parts.append(df_to_html(df, pass_col="Kết quả"))

        parts.append("<h1>3. Thông số CDM (TCVN 9403)</h1>")
        parts.append('<div class="metric-row">')
        parts.append(metric_card("a (area ratio)",
                                  f"{result.get('cdm_area_ratio',0.25):.2f}"))
        parts.append(metric_card("β (TCVN 9403)",
                                  f"{result.get('cdm_beta',1):.3f}",
                                  f"Δσ vào đất = {result.get('cdm_beta',1)*100:.0f}%"))
        parts.append(metric_card("Ec / Es / E_composite",
                                  f"{result.get('cdm_Ec_kPa',0):.0f} / "
                                  f"{result.get('cdm_Es_kPa',0):.0f} / "
                                  f"{result.get('cdm_composite_kPa',0):.0f}",
                                  "kPa"))
        parts.append("</div>")

        cdm_sc = next((s for s in result["scenarios"] if s["method"] == "cdm"), None)
        if cdm_sc:
            parts.append(f"<p><strong>S1 CDM = {cdm_sc['S_total_cm']:.1f} cm</strong> "
                         f"(lún đàn hồi tức thời, không có lún còn lại).</p>")

    parts.append("<h1>4. Công thức TCCS 41:2022 Phụ lục A</h1>")
    parts.append("""
<div class="formula">
Lớp OC  (σ'vf ≤ PC):     Si = Hi × Cs/(1+e0) × log(σ'vf / σ'v0)<br>
Lớp NC  (σ'v0 ≥ PC):     Si = Hi × Cc/(1+e0) × log(σ'vf / σ'v0)<br>
Lớp cắt PC (σ'v0 < PC < σ'vf):<br>
&nbsp;&nbsp;Si = Hi × [Cs/(1+e0)·log(PC/σ'v0) + Cc/(1+e0)·log(σ'vf/PC)]<br>
S_total = Σ Si  (cm)
</div>
""")

    return build_report_pdf(
        title="BÁO CÁO DỰ BÁO LÚN",
        subtitle="TCCS 41:2022 — So sánh phương án xử lý đất yếu",
        content_html="\n".join(parts),
        meta={
            "Khu vực": state.get("sl_zone", "—"),
            "Hố khoan": state.get("sl_bh", "—"),
            "Tiêu chuẩn": "TCCS 41:2022 + TCVN 9403:2012",
        },
    )


def report_ke_sw(db_path: Path) -> bytes:
    parts = []
    con = sqlite3.connect(str(db_path))
    df_main = pd.read_sql_query("""
        SELECT bh_name as 'Hố khoan', pile_type as 'Cọc',
               L_design_m as 'L tk (m)',
               L_req_nt1_m as 'L req (m)',
               margin_nt1_m as 'Δ NT1 (m)',
               nt1_result as 'Kết quả NT1',
               Rs_clay_kN as 'Rs sét (kN)',
               Rs_sand_kN as 'Rs cát (kN)',
               Rp_kN as 'Rp (kN)',
               RR_kN as 'RR (kN)',
               W_kN as 'W (kN)',
               ratio_nt2 as 'RR/W',
               nt2_result as 'Kết quả NT2',
               tip_method as 'Tip method',
               phi_stat as 'φ_stat'
        FROM ke_sw_nt_detail ORDER BY bh_name
    """, con)
    con.close()

    parts.append("<h1>1. Bảng tổng hợp NT1 / NT2 — 7 HK trên tuyến kè</h1>")
    if df_main.empty:
        parts.append('<div class="warning">Chưa có dữ liệu NT trong SQLite.</div>')
    else:
        # Hai bảng phân tách
        df_nt1 = df_main[["Hố khoan", "Cọc", "L tk (m)", "L req (m)",
                          "Δ NT1 (m)", "Kết quả NT1"]]
        df_nt2 = df_main[["Hố khoan", "Rs sét (kN)", "Rs cát (kN)", "Rp (kN)",
                          "RR (kN)", "W (kN)", "RR/W", "Kết quả NT2", "Tip method",
                          "φ_stat"]]
        parts.append("<h2>1.1 NT1 — Chiều dài xuyên qua lớp yếu</h2>")
        parts.append(df_to_html(df_nt1, pass_col="Kết quả NT1"))
        parts.append("<h2>1.2 NT2 — Sức kháng nhổ TCVN 11823-10</h2>")
        parts.append(df_to_html(df_nt2, pass_col="Kết quả NT2"))

        parts.append('<div class="info">'
                     "<strong>φ_stat dynamic</strong>: 0.30 khi sand Rs > 10% hoặc tip cát; 0.35 nếu sét chiếm ưu thế.  "
                     "<strong>tip method</strong>: alpha (Tomlinson sét) / SPT (Meyerhof cát)."
                     "</div>")

    parts.append("<h1>2. Công thức TCVN 11823-10:2017</h1>")
    parts.append("""
<div class="formula">
NT1: L_req = fill + D_bottom_soft + min_pen (1.0 m)<br>
NT2: RR = φ_stat × (Rs + Rp) ≥ W_cọc<br><br>
Sét (α-method, Điều 7.3.8.6.2):<br>
&nbsp;&nbsp;qs = α(Su) × Su  |  qp = 9 × Su  |  φ_stat = 0.35<br>
Cát (SPT-Meyerhof, Điều 7.3.8.6.7):<br>
&nbsp;&nbsp;qs = 0.0019 × N₁₆₀ MPa (chiếm chỗ)  |  qp = 0.038 × N₁₆₀ × (Db/D) ≤ 3.2·N₁₆₀ MPa<br>
&nbsp;&nbsp;φ_stat = 0.30  |  N₁₆₀ hiệu chỉnh CN = √(100/σ'v)
</div>
""")

    return build_report_pdf(
        title="BÁO CÁO CỌC VÁN SW KÈ TTHC",
        subtitle="NT1 / NT2 theo TCVN 11823-10:2017 — Đa phương pháp",
        content_html="\n".join(parts),
        meta={
            "Dự án": "202605-TTHC",
            "Cọc": "SW-840 / SW-940 BETON 6",
            "Tiêu chuẩn": "TCVN 11823-10:2017 + 4 phương pháp",
        },
    )


def report_all(state: dict, db_path: Path,
               settlement_result: dict | None = None) -> bytes:
    """PDF tổng hợp toàn bộ tab."""
    parts = []

    # Phần 1: Thông số CDM
    parts.append('<div class="page-break"></div>')
    parts.append("<h1>PHẦN 1 — THÔNG SỐ CDM</h1>")
    parts.append("<h2>1.1 Hình học cọc</h2>")
    df = pd.DataFrame({
        "Tham số":  ["D", "e", "CDTK", "Lc", "Bố trí"],
        "Giá trị":  [f"{state.get('cdm_D',0.8):.2f} m",
                     f"{state.get('cdm_e',1.6):.2f} m",
                     f"{state.get('cdm_CDTK',2.7):+.2f} m",
                     f"{state.get('cdm_Lc',23):.1f} m",
                     "Tam giác" if state.get('cdm_arrangement') == "triangle" else "Vuông"],
    })
    parts.append(df_to_html(df))

    parts.append("<h2>1.2 Vật liệu + Tải trọng</h2>")
    ld = state.get("cdm_loads", {})
    df = pd.DataFrame({
        "Tham số":  ["qu thiết kế", "Hàm lượng XM", "q_traffic",
                     "z_tk", "He cát đắp", "Hse đệm cát"],
        "Giá trị":  [f"{state.get('cdm_qu',1000):.0f} kPa",
                     f"{state.get('cdm_dosage',250):.0f} kg/m³",
                     f"{ld.get('q_traffic',20):.1f} kN/m²",
                     f"{ld.get('z_tk',3.5):+.2f} m",
                     f"{ld.get('h_fill',1.5):.2f} m",
                     f"{ld.get('h_mat',0.4):.2f} m"],
    })
    parts.append(df_to_html(df))

    # Phần 2: Dự báo lún
    parts.append('<div class="page-break"></div>')
    parts.append("<h1>PHẦN 2 — DỰ BÁO LÚN (TCCS 41:2022)</h1>")
    if settlement_result:
        rows = []
        for sc in settlement_result["scenarios"]:
            rows.append({
                "Phương án":        sc["label"],
                "Lún tổng (cm)":    round(sc["S_total_cm"], 1),
                "Lún còn lại (cm)": round(sc["residual_cm"], 1),
                "Kết quả":          "Đạt" if sc["feasible"] else "Không đạt",
            })
        parts.append(df_to_html(pd.DataFrame(rows), pass_col="Kết quả"))
    else:
        parts.append('<div class="warning">Chưa chạy tính lún. Vào tab Dự báo lún → nhấn Tính toán.</div>')

    # Phần 3: Cọc ván SW
    parts.append('<div class="page-break"></div>')
    parts.append("<h1>PHẦN 3 — CỌC VÁN SW (NT1/NT2)</h1>")
    try:
        con = sqlite3.connect(str(db_path))
        df_sw = pd.read_sql_query("""
            SELECT bh_name as 'HK', L_design_m as 'L tk',
                   margin_nt1_m as 'Δ NT1', nt1_result as 'NT1',
                   Rs_kN as 'Rs', Rp_kN as 'Rp', RR_kN as 'RR',
                   W_kN as 'W', ratio_nt2 as 'RR/W',
                   nt2_result as 'NT2', tip_method as 'Tip method'
            FROM ke_sw_nt_detail ORDER BY bh_name
        """, con)
        con.close()
        if not df_sw.empty:
            df_sw["Δ NT1"]  = df_sw["Δ NT1"].apply(lambda v: f"{v:+.2f}")
            df_sw["RR/W"]   = df_sw["RR/W"].round(2)
            df_sw["Rs"]     = df_sw["Rs"].round(0)
            df_sw["Rp"]     = df_sw["Rp"].round(0)
            df_sw["RR"]     = df_sw["RR"].round(0)
            df_sw["W"]      = df_sw["W"].round(0)
            parts.append(df_to_html(df_sw, pass_col="NT2"))
    except Exception as e:
        parts.append(f'<div class="warning">Lỗi đọc DB: {e}</div>')

    return build_report_pdf(
        title="BÁO CÁO TỔNG HỢP",
        subtitle="Thiết kế xử lý đất yếu CDM + Kè SW — Dự án 202605 TTHC",
        content_html="\n".join(parts),
        meta={
            "Dự án":     "202605-TTHC",
            "Khu vực":   state.get("cdm_zone", "—"),
            "Hố khoan":  state.get("cdm_bh", "—"),
            "Tiêu chuẩn": "TCVN 9403, TCCS 41, TCVN 11823-10",
        },
    )
