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
import re
import sqlite3
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
from jinja2 import Template

# ─── PDF engine auto-detect (tier-1 → tier-2 → tier-3) ──────────────────────
# tier-1: weasyprint  — best HTML/CSS, cần GTK3 (Windows) hoặc apt libs (Cloud)
# tier-2: xhtml2pdf   — pure Python, CSS cơ bản, chạy được Cloud Python 3.14
# tier-3: reportlab   — programmatic PDF, fallback cuối nếu HTML→PDF fail
_HAS_WEASYPRINT = False
_HAS_XHTML2PDF = False
_HAS_REPORTLAB = False
try:
    from weasyprint import HTML as _WP_HTML  # noqa: F401
    from weasyprint.text.fonts import FontConfiguration as _WP_FontConfig  # noqa: F401
    _HAS_WEASYPRINT = True
except Exception:
    pass
try:
    from xhtml2pdf import pisa as _pisa  # noqa: F401
    _HAS_XHTML2PDF = True
except Exception:
    pass
try:
    from reportlab.lib.pagesizes import A4 as _RL_A4  # noqa: F401
    from reportlab.lib.styles import getSampleStyleSheet as _rl_styles  # noqa: F401
    from reportlab.platypus import (  # noqa: F401
        SimpleDocTemplate as _RL_Doc,
        Paragraph as _RL_Para,
        Spacer as _RL_Spacer,
        PageBreak as _RL_PageBreak,
    )
    _HAS_REPORTLAB = True
except Exception:
    pass

_ROOT = Path(__file__).resolve().parent.parent

# ─── CSS A4 cao cấp — typography + palette + paged-media ────────────────────
# Thiết kế (2026-05-22): bookish + technical document
#   - Palette: navy #1F4E79 + gold accent #B7892C + neutrals (cream/cream-dark)
#   - Typography: DejaVu Serif (heading) + DejaVu Sans (body), Unicode full
#   - Paged media: 3 page kinds — @page :cover / @page toc / @page (content)
#       cover: không header/footer
#       toc:   header tối giản
#       content: header section-title (right) + page x/total (bottom)
#   - Auto-numbering: figure / table qua CSS counter
#   - Status pills: .badge.pass / .badge.fail / .badge.warn
#   - Print-safe: page-break-inside: avoid cho table / .fig-block / .card
_REPORT_CSS = """
/* ── PALETTE ── */
:root {
  --navy: #1F4E79;
  --navy-dark: #163A5A;
  --navy-light: #2E6BA5;
  --gold: #B7892C;
  --gold-light: #E5C870;
  --ink: #1A1A1A;
  --ink-soft: #4A4A4A;
  --rule: #C9D4E0;
  --rule-soft: #E6ECF2;
  --bg-tint: #F5F8FB;
  --bg-cream: #FAF7EE;
  --pass-bg: #E6F4EA;
  --pass-fg: #1E6F3D;
  --fail-bg: #FCE8E8;
  --fail-fg: #B71C1C;
  --warn-bg: #FFF6D6;
  --warn-fg: #8B6914;
  --info-bg: #E7F0FA;
  --info-fg: #1F4E79;
}

/* ── PAGE GEOMETRY ── */
@page {
  size: A4;
  margin: 22mm 18mm 22mm 22mm;  /* top right bottom left (left wider for binding) */

  @top-left {
    content: string(doc-title);
    font-family: "DejaVu Serif", "Times New Roman", serif;
    font-size: 8.5pt;
    color: #777;
    border-bottom: 0.3pt solid var(--rule);
    padding-bottom: 2mm;
    vertical-align: bottom;
  }
  @top-right {
    content: string(section-title);
    font-family: "DejaVu Sans", "Arial", sans-serif;
    font-size: 8.5pt;
    color: var(--navy);
    font-weight: 600;
    border-bottom: 0.3pt solid var(--rule);
    padding-bottom: 2mm;
    vertical-align: bottom;
    text-align: right;
  }
  @bottom-left {
    content: string(doc-meta);
    font-family: "DejaVu Sans", sans-serif;
    font-size: 8pt;
    color: #888;
    padding-top: 2mm;
    border-top: 0.3pt solid var(--rule);
  }
  @bottom-right {
    content: "Trang " counter(page) " / " counter(pages);
    font-family: "DejaVu Sans", sans-serif;
    font-size: 8pt;
    color: var(--navy);
    font-weight: 600;
    padding-top: 2mm;
    border-top: 0.3pt solid var(--rule);
    text-align: right;
  }
}

/* Cover page: KHÔNG header/footer */
@page :first {
  margin: 0;
  @top-left { content: none; }
  @top-right { content: none; }
  @bottom-left { content: none; }
  @bottom-right { content: none; }
}

@page toc {
  @top-right { content: "Mục lục"; }
}

/* ── BASE TYPOGRAPHY ── */
body {
  font-family: "DejaVu Sans", "Arial", "Helvetica", sans-serif;
  font-size: 10.5pt;
  line-height: 1.55;
  color: var(--ink);
  text-rendering: geometricPrecision;
  -webkit-font-smoothing: antialiased;
}

.doc-title {
  string-set: doc-title content();
  display: none;
}
.doc-meta {
  string-set: doc-meta content();
  display: none;
}
.section-marker {
  string-set: section-title content();
  display: none;
}

/* ── COVER PAGE ── */
.cover {
  page: first;
  page-break-after: always;
  width: 210mm;
  height: 297mm;
  margin: 0;
  padding: 28mm 22mm;
  box-sizing: border-box;
  background: linear-gradient(180deg, #FFFFFF 0%, #FFFFFF 55%, #F5F8FB 100%);
  color: var(--ink);
  position: relative;
}
.cover .brand-bar {
  width: 60mm;
  height: 6mm;
  background: var(--navy);
  margin-bottom: 14mm;
  position: relative;
}
.cover .brand-bar::after {
  content: "";
  position: absolute;
  left: 60mm;
  top: 0;
  width: 18mm;
  height: 6mm;
  background: var(--gold);
}
.cover .eyebrow {
  font-family: "DejaVu Sans", sans-serif;
  font-size: 9.5pt;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--gold);
  font-weight: 700;
  margin-bottom: 6mm;
}
.cover h1.cover-title {
  font-family: "DejaVu Serif", "Times New Roman", serif;
  font-size: 28pt;
  line-height: 1.15;
  color: var(--navy-dark);
  font-weight: 700;
  margin: 0 0 6mm 0;
  border: 0;
  padding: 0;
}
.cover .cover-subtitle {
  font-size: 13pt;
  line-height: 1.4;
  color: var(--ink-soft);
  margin-bottom: 28mm;
  max-width: 150mm;
}
.cover .cover-meta {
  border-top: 0.5pt solid var(--rule);
  padding-top: 6mm;
  font-size: 10.5pt;
  line-height: 1.85;
  color: var(--ink-soft);
}
.cover .cover-meta .row {
  display: flex;
  border-bottom: 0.3pt solid var(--rule-soft);
  padding: 2mm 0;
}
.cover .cover-meta .row .k {
  width: 55mm;
  font-weight: 600;
  color: var(--navy);
  letter-spacing: 0.02em;
}
.cover .cover-meta .row .v { flex: 1; }
.cover .footer-strip {
  position: absolute;
  left: 22mm; right: 22mm; bottom: 18mm;
  border-top: 0.5pt solid var(--rule);
  padding-top: 4mm;
  font-size: 9pt;
  color: #888;
  display: flex;
  justify-content: space-between;
}
.cover .footer-strip .accent { color: var(--gold); font-weight: 700; }

/* ── TABLE OF CONTENTS ── */
.toc {
  page: toc;
  page-break-after: always;
}
.toc h1 {
  border: 0;
  margin-bottom: 8mm;
}
.toc ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.toc li {
  display: flex;
  align-items: baseline;
  font-size: 10.5pt;
  padding: 1.6mm 0;
  border-bottom: 0.2pt dotted var(--rule);
}
.toc li.lv1 {
  font-weight: 700;
  color: var(--navy);
  font-size: 11pt;
  padding-top: 3mm;
  border-bottom: 0.3pt solid var(--navy);
}
.toc li.lv2 { padding-left: 6mm; }
.toc li.lv3 { padding-left: 12mm; color: var(--ink-soft); font-size: 9.5pt; }
.toc li .ttl { flex: 1; }
.toc li .dots {
  flex: 0 0 auto;
  border-bottom: 0.5pt dotted #999;
  margin: 0 4mm;
  height: 0.5em;
  min-width: 10mm;
  flex-grow: 1;
}
.toc li .pg { flex: 0 0 auto; color: var(--ink-soft); font-variant-numeric: tabular-nums; }

/* ── CHAPTER DIVIDER PAGE ── */
.chapter-divider {
  page-break-before: always;
  page-break-after: always;
  text-align: left;
  padding-top: 70mm;
}
.chapter-divider .chap-num {
  font-family: "DejaVu Serif", serif;
  font-size: 72pt;
  font-weight: 700;
  color: var(--gold-light);
  line-height: 1;
  margin: 0;
}
.chapter-divider .chap-title {
  font-family: "DejaVu Serif", serif;
  font-size: 26pt;
  font-weight: 700;
  color: var(--navy-dark);
  margin-top: 4mm;
  border-bottom: 1.5pt solid var(--navy);
  padding-bottom: 4mm;
  display: inline-block;
}
.chapter-divider .chap-lead {
  font-size: 11pt;
  color: var(--ink-soft);
  margin-top: 6mm;
  max-width: 140mm;
  line-height: 1.55;
}

/* ── HEADINGS (content) ── */
h1 {
  font-family: "DejaVu Serif", "Times New Roman", serif;
  font-size: 16pt;
  color: var(--navy-dark);
  border-bottom: 1.5pt solid var(--navy);
  padding-bottom: 3pt;
  margin: 18pt 0 8pt 0;
  page-break-after: avoid;
  letter-spacing: -0.005em;
}
h1.chapter { page-break-before: always; margin-top: 0; }
h1.no-break { page-break-before: avoid; }
h1 .h-num {
  color: var(--gold);
  margin-right: 6pt;
  font-family: "DejaVu Serif", serif;
}

h2 {
  font-family: "DejaVu Sans", sans-serif;
  font-size: 12pt;
  color: var(--navy);
  margin-top: 14pt;
  margin-bottom: 4pt;
  padding-left: 6pt;
  border-left: 2pt solid var(--gold);
  page-break-after: avoid;
}

h3 {
  font-family: "DejaVu Sans", sans-serif;
  font-size: 10.5pt;
  color: var(--navy-dark);
  font-weight: 700;
  margin: 10pt 0 3pt 0;
  text-transform: none;
  letter-spacing: 0.01em;
  page-break-after: avoid;
}
h3::before { content: "▸ "; color: var(--gold); }

p {
  margin: 4pt 0;
  text-align: justify;
  hyphens: auto;
  orphans: 3;
  widows: 3;
}
p.lead {
  font-size: 11pt;
  color: var(--ink-soft);
  margin: 6pt 0 10pt 0;
  border-left: 3pt solid var(--gold);
  padding-left: 10pt;
}
ul, ol { margin: 4pt 0 4pt 6mm; padding: 0; }
li { margin: 2pt 0; }
strong { color: var(--navy-dark); }
em { color: var(--ink-soft); }

/* ── CAPTIONS — auto numbering ── */
body { counter-reset: fig tbl section; }
h1 { counter-reset: subsection; counter-increment: section; }
h2 { counter-increment: subsection; }

.caption {
  font-size: 9pt;
  color: var(--ink-soft);
  font-style: italic;
  text-align: center;
  margin: 2pt 0 8pt 0;
  line-height: 1.35;
}
figure {
  margin: 8pt 0;
  page-break-inside: avoid;
  text-align: center;
}
figure img {
  max-width: 100%;
  max-height: 14cm;
  object-fit: contain;
}
figure figcaption {
  font-size: 9pt;
  color: var(--ink-soft);
  font-style: italic;
  margin-top: 3pt;
  text-align: center;
  counter-increment: fig;
}
figure figcaption::before {
  content: "Hình " counter(section) "." counter(fig) ". ";
  font-style: normal;
  font-weight: 700;
  color: var(--navy);
}

table {
  border-collapse: collapse;
  width: 100%;
  margin: 6pt 0;
  page-break-inside: auto;
  font-size: 9pt;
  font-variant-numeric: tabular-nums;
}
table.no-break { page-break-inside: avoid; }
table thead { display: table-header-group; }     /* lặp header khi tách trang */
table tfoot { display: table-footer-group; }
table tr { page-break-inside: avoid; }           /* không tách giữa 1 hàng */
table caption {
  caption-side: top;
  text-align: left;
  font-size: 9pt;
  color: var(--navy);
  font-weight: 700;
  padding: 2pt 0;
  counter-increment: tbl;
}
table caption::before {
  content: "Bảng " counter(section) "." counter(tbl) ". ";
  color: var(--gold);
}
table th {
  background-color: var(--navy);
  color: white;
  font-weight: 600;
  padding: 5pt 6pt;
  text-align: center;
  border: 0.4pt solid var(--navy-dark);
  letter-spacing: 0.01em;
  font-size: 9pt;
}
table th.subhead {
  background-color: var(--navy-light);
  font-weight: 500;
  font-size: 8.5pt;
}
table td {
  padding: 3.5pt 6pt;
  border: 0.3pt solid var(--rule);
  vertical-align: middle;
  text-align: center;
}
table td.left { text-align: left; }
table td.right { text-align: right; }
table tr:nth-child(even) td { background-color: var(--bg-tint); }
table tr.pass td {
  background-color: var(--pass-bg);
  color: var(--pass-fg);
}
table tr.fail td {
  background-color: var(--fail-bg);
  color: var(--fail-fg);
  font-weight: 600;
}
table tr.total td {
  background-color: var(--navy);
  color: white;
  font-weight: 700;
  border-top: 1pt solid var(--navy-dark);
}

/* ── STATUS BADGES ── */
.badge {
  display: inline-block;
  padding: 1.5pt 6pt;
  border-radius: 8pt;
  font-size: 8.5pt;
  font-weight: 700;
  letter-spacing: 0.02em;
  line-height: 1;
  vertical-align: middle;
}
.badge.pass { background: var(--pass-bg); color: var(--pass-fg); }
.badge.fail { background: var(--fail-bg); color: var(--fail-fg); }
.badge.warn { background: var(--warn-bg); color: var(--warn-fg); }
.badge.info { background: var(--info-bg); color: var(--info-fg); }
.badge.neutral { background: #ECEFF1; color: #455A64; }

/* ── METRIC CARDS ── */
.metric-row {
  display: flex;
  gap: 6pt;
  margin: 8pt 0 10pt 0;
  page-break-inside: avoid;
}
.metric-card {
  flex: 1;
  border-left: 3pt solid var(--navy);
  background: var(--bg-tint);
  padding: 6pt 8pt 7pt 9pt;
  border-radius: 0 2pt 2pt 0;
}
.metric-card.accent { border-left-color: var(--gold); }
.metric-card.pass { border-left-color: var(--pass-fg); background: var(--pass-bg); }
.metric-card.fail { border-left-color: var(--fail-fg); background: var(--fail-bg); }
.metric-card .label {
  font-size: 7.5pt;
  color: var(--ink-soft);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}
.metric-card .value {
  font-family: "DejaVu Serif", serif;
  font-size: 16pt;
  color: var(--navy-dark);
  font-weight: 700;
  line-height: 1.15;
  margin-top: 1pt;
}
.metric-card .unit {
  font-size: 8.5pt;
  color: var(--ink-soft);
  font-weight: 400;
  margin-left: 2pt;
}
.metric-card .delta {
  font-size: 8.5pt;
  color: var(--pass-fg);
  margin-top: 1pt;
}
.metric-card .delta.neg { color: var(--fail-fg); }

/* ── CALLOUT BLOCKS ── */
.callout {
  margin: 8pt 0;
  padding: 6pt 10pt 6pt 12pt;
  border-radius: 3pt;
  font-size: 9.5pt;
  page-break-inside: avoid;
}
.callout .ttl {
  font-weight: 700;
  display: block;
  margin-bottom: 2pt;
  font-size: 9.5pt;
}
.callout.info {
  background: var(--info-bg);
  border-left: 3pt solid var(--info-fg);
  color: var(--info-fg);
}
.callout.warning {
  background: var(--warn-bg);
  border-left: 3pt solid var(--warn-fg);
  color: var(--warn-fg);
}
.callout.success {
  background: var(--pass-bg);
  border-left: 3pt solid var(--pass-fg);
  color: var(--pass-fg);
}
.callout.danger {
  background: var(--fail-bg);
  border-left: 3pt solid var(--fail-fg);
  color: var(--fail-fg);
}

/* Backwards compat */
.info { background: var(--info-bg); border-left: 3pt solid var(--info-fg); padding: 6pt 8pt; margin: 6pt 0; font-size: 9.5pt; color: var(--info-fg); }
.warning { background: var(--warn-bg); border-left: 3pt solid var(--warn-fg); padding: 6pt 8pt; margin: 6pt 0; font-size: 9.5pt; color: var(--warn-fg); }

/* ── PULL QUOTE / KEY-POINT ── */
.pull-quote {
  margin: 10pt 4mm;
  padding: 6pt 10pt;
  border-left: 4pt solid var(--gold);
  font-family: "DejaVu Serif", serif;
  font-size: 12pt;
  font-style: italic;
  color: var(--navy);
  background: var(--bg-cream);
}

/* ── FIG-BLOCK (legacy alias) ── */
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
.fig-block .caption {
  margin-top: 3pt;
}

/* ── FORMULA / CODE ── */
.formula {
  font-family: "DejaVu Sans Mono", "Courier New", monospace;
  background: var(--bg-cream);
  padding: 8pt 10pt;
  margin: 6pt 0;
  border-left: 2pt solid var(--gold);
  font-size: 9.5pt;
  line-height: 1.65;
  page-break-inside: avoid;
}

/* ── SIGNATURE BLOCK ── */
.signature-block {
  page-break-inside: avoid;
  margin-top: 18mm;
  display: table;
  width: 100%;
}
.signature-block .sig {
  display: table-cell;
  width: 33%;
  text-align: center;
  padding: 0 6mm;
  vertical-align: top;
}
.signature-block .sig .role {
  font-size: 9pt;
  color: var(--ink-soft);
  margin-bottom: 24mm;
}
.signature-block .sig .line {
  border-top: 0.6pt solid var(--ink);
  padding-top: 1.5mm;
  font-weight: 700;
  font-size: 10pt;
  color: var(--navy-dark);
}
.signature-block .sig .name-hint {
  font-size: 8.5pt;
  color: var(--ink-soft);
  font-style: italic;
}

/* ── UTILITY ── */
.page-break { page-break-after: always; }
/* Tránh blank page khi page-break đứng ngay sau cover/toc đã break sẵn */
.cover + .page-break,
.toc + .page-break,
section + .page-break,
.page-break + .page-break,
.page-break:first-child { display: none; }
.no-break { page-break-inside: avoid; }
.text-right { text-align: right; }
.text-center { text-align: center; }
.small { font-size: 9pt; color: var(--ink-soft); }
.muted { color: var(--ink-soft); }
.rule {
  border: 0;
  border-top: 0.5pt solid var(--rule);
  margin: 8pt 0;
}
"""

# ─── Helpers: figures → base64 ──────────────────────────────────────────────
def mpl_to_b64(fig, dpi: int = 130) -> str:
    """Matplotlib Figure → data URI."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def plotly_to_b64(fig, width: int = 1000, height: int = 500) -> str:
    """Plotly Figure → data URI (cần kaleido).

    LƯU Ý: kaleido KHÔNG có wheel cp314 → không chạy được trên Streamlit Cloud.
    Quy tắc dự án (CLAUDE.md): mọi chart embed PDF phải vẽ lại bằng Matplotlib
    qua `mpl_to_b64()`. Hàm này chỉ dùng cho local Windows có kaleido cài sẵn.
    """
    try:
        png_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
        return "data:image/png;base64," + base64.b64encode(png_bytes).decode()
    except Exception as e:
        warnings.warn(
            f"plotly_to_b64 fail ({type(e).__name__}: {e}). "
            "Trên Cloud Python 3.14 không có kaleido → vẽ lại bằng Matplotlib "
            "qua mpl_to_b64(). Chart sẽ bị BỎ QUA trong PDF.",
            RuntimeWarning, stacklevel=2,
        )
        return ""


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


def metric_card(label: str, value: str, *,
                unit: str = "", delta: str | None = None,
                positive: bool = True, variant: str = "") -> str:
    """Metric card khối thông số nổi bật.

    variant ∈ "" / "accent" / "pass" / "fail" — đổi màu border + background.
    unit  — hậu tố nhỏ sau value (ví dụ "kPa", "cm").
    """
    delta_html = (
        f'<div class="delta {"" if positive else "neg"}">{delta}</div>'
        if delta else ""
    )
    unit_html = f'<span class="unit">{unit}</span>' if unit else ""
    cls = f"metric-card {variant}".strip()
    return (f'<div class="{cls}">'
            f'<div class="label">{label}</div>'
            f'<div class="value">{value}{unit_html}</div>'
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
<span class="doc-title">{{ doc_title_running }}</span>
<span class="doc-meta">{{ doc_meta_running }}</span>

{% if cover %}
<div class="cover">
  <div class="brand-bar"></div>
  <div class="eyebrow">{{ eyebrow or "Báo cáo kỹ thuật" }}</div>
  <h1 class="cover-title">{{ title }}</h1>
  {% if subtitle %}<div class="cover-subtitle">{{ subtitle }}</div>{% endif %}

  <div class="cover-meta">
    {% for k, v in meta.items() %}
      <div class="row"><div class="k">{{ k }}</div><div class="v">{{ v }}</div></div>
    {% endfor %}
  </div>

  <div class="footer-strip">
    <div>Sinh tự động ngày <span class="accent">{{ date }}</span></div>
    <div>{{ doc_meta_running }}</div>
  </div>
</div>
{% endif %}

{% if toc and toc_items %}
<section class="toc">
  <h1 class="no-break">Mục lục</h1>
  <ul>
    {% for item in toc_items %}
      <li class="lv{{ item.level }}">
        <span class="ttl">{{ item.title }}</span>
        <span class="dots"></span>
        <span class="pg">{{ item.page or '' }}</span>
      </li>
    {% endfor %}
  </ul>
</section>
{% endif %}

{{ content | safe }}

{% if signatures %}
<div class="signature-block">
  {% for s in signatures %}
    <div class="sig">
      <div class="role">{{ s.role }}</div>
      <div class="line">{{ s.name or "(ký, họ tên)" }}</div>
      {% if s.title %}<div class="name-hint">{{ s.title }}</div>{% endif %}
    </div>
  {% endfor %}
</div>
{% endif %}
</body>
</html>
""")


# ─── Helpers v2: figure / table / badge / callout / quote ──────────────────────
def section_marker(title: str) -> str:
    """Đặt section title cho running header (CSS string-set).

    Chèn ngay sau mở h1 để CSS @page :top-right tự lấy.
    """
    return f'<span class="section-marker">{title}</span>'


def figure(img_b64: str, caption: str = "") -> str:
    """<figure> với auto-numbered caption (Hình X.Y)."""
    cap_html = f"<figcaption>{caption}</figcaption>" if caption else ""
    return f'<figure><img src="{img_b64}" />{cap_html}</figure>'


def badge(text: str, kind: str = "neutral") -> str:
    """Pill badge — kind ∈ pass/fail/warn/info/neutral."""
    return f'<span class="badge {kind}">{text}</span>'


def callout(body: str, kind: str = "info", title: str = "") -> str:
    """Box thông báo. kind ∈ info/warning/success/danger."""
    ttl = f'<span class="ttl">{title}</span>' if title else ""
    return f'<div class="callout {kind}">{ttl}{body}</div>'


def pull_quote(text: str) -> str:
    """Khối trích dẫn nổi bật (italic + gold accent)."""
    return f'<div class="pull-quote">{text}</div>'


def metric_row(*cards: str) -> str:
    """Hàng 2-4 metric cards. Gọi: metric_row(metric_card(...), metric_card(...))"""
    return '<div class="metric-row">' + "".join(cards) + "</div>"


def _render_pdf_weasyprint(html_str: str) -> bytes:
    """Tier-1: WeasyPrint — chất lượng HTML/CSS cao nhất."""
    font_config = _WP_FontConfig()
    return _WP_HTML(string=html_str).write_pdf(font_config=font_config)


def _render_pdf_xhtml2pdf(html_str: str) -> bytes:
    """Tier-2: xhtml2pdf (pisa) — pure Python, hỗ trợ CSS cơ bản.

    Lưu ý so với weasyprint:
    - Không hỗ trợ CSS Paged Media @page với @top-right/@bottom-center →
      đã được _strip_unsupported_css() loại bỏ trước khi render.
    - Hỗ trợ font Unicode qua @font-face nếu file TTF tồn tại.
    """
    buf = io.BytesIO()
    html_clean = _strip_unsupported_css(html_str)
    result = _pisa.CreatePDF(src=html_clean, dest=buf, encoding="utf-8")
    if result.err:
        raise RuntimeError(f"xhtml2pdf render failed ({result.err} errors)")
    return buf.getvalue()


def _render_pdf_reportlab(title: str, content_html: str,
                          subtitle: str, meta: dict, cover: bool) -> bytes:
    """Tier-3: ReportLab — fallback cuối, dựng PDF từ HTML thô.

    Strip tag HTML, giữ text + heading + bảng tối giản. Không render được
    figure base64 (ảnh) và CSS — chỉ đảm bảo nội dung text không mất.
    """
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     PageBreak)
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.2*cm, rightMargin=1.2*cm,
                            topMargin=1.5*cm, bottomMargin=1.8*cm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=14,
                        textColor="#1F4E79", spaceAfter=8)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12,
                        textColor="#2E5C8A", spaceAfter=6)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10,
                          leading=14)

    flow = []
    if cover:
        flow.append(Paragraph(title, ParagraphStyle(
            "Cover", parent=styles["Title"], fontSize=22,
            textColor="#1F4E79", alignment=1)))
        if subtitle:
            flow.append(Spacer(1, 0.5*cm))
            flow.append(Paragraph(subtitle, ParagraphStyle(
                "Sub", parent=styles["BodyText"], fontSize=12,
                textColor="#555", alignment=1)))
        flow.append(Spacer(1, 1*cm))
        for k, v in (meta or {}).items():
            flow.append(Paragraph(f"<b>{k}:</b> {v}", body))
        flow.append(PageBreak())

    # Strip HTML thô: thay <h1>/<h2>/<p>/<table> bằng paragraph riêng
    blocks = re.split(r"(<h[12][^>]*>.*?</h[12]>|<table.*?</table>|<p>.*?</p>)",
                      content_html, flags=re.DOTALL | re.IGNORECASE)
    for blk in blocks:
        if not blk or not blk.strip():
            continue
        if re.match(r"<h1", blk, re.I):
            txt = re.sub(r"<[^>]+>", "", blk).strip()
            flow.append(Paragraph(txt, h1))
        elif re.match(r"<h2", blk, re.I):
            txt = re.sub(r"<[^>]+>", "", blk).strip()
            flow.append(Paragraph(txt, h2))
        elif re.match(r"<table", blk, re.I):
            # Render bảng đơn giản từ thẻ <tr>/<td>
            rows = re.findall(r"<tr.*?>(.*?)</tr>", blk, re.DOTALL | re.I)
            for r in rows:
                cells = re.findall(r"<t[hd].*?>(.*?)</t[hd]>", r, re.DOTALL | re.I)
                line = " | ".join(re.sub(r"<[^>]+>", "", c).strip() for c in cells)
                if line:
                    flow.append(Paragraph(line, body))
            flow.append(Spacer(1, 0.3*cm))
        else:
            txt = re.sub(r"<[^>]+>", "", blk).strip()
            if txt:
                flow.append(Paragraph(txt, body))
                flow.append(Spacer(1, 0.2*cm))

    doc.build(flow)
    return buf.getvalue()


def _strip_unsupported_css(html_str: str) -> str:
    """Loại bỏ CSS Paged Media advanced không được xhtml2pdf hỗ trợ.

    - @top-right / @bottom-center / @bottom-left blocks (CSS3 paged media)
    - string-set declarations
    Giữ lại @page { size + margin } cơ bản — xhtml2pdf hiểu được.
    """
    # Bỏ các block @top-*/@bottom-* lồng trong @page
    out = re.sub(r"@(top|bottom|left|right)-[a-z]+\s*\{[^}]*\}", "",
                 html_str, flags=re.IGNORECASE)
    # Bỏ string-set
    out = re.sub(r"string-set\s*:[^;]+;", "", out, flags=re.IGNORECASE)
    # Bỏ content: counter()/string() (xhtml2pdf không hỗ trợ counter advanced)
    out = re.sub(r"content\s*:\s*[^;}]*counter\([^)]*\)[^;}]*;", "", out,
                 flags=re.IGNORECASE)
    out = re.sub(r"content\s*:\s*string\([^)]*\)\s*;", "", out,
                 flags=re.IGNORECASE)
    return out


def build_report_pdf(
    title: str,
    content_html: str,
    subtitle: str = "",
    meta: dict | None = None,
    cover: bool = True,
    engine: str = "auto",
    *,
    eyebrow: str = "",
    toc: bool = False,
    toc_items: list[dict] | None = None,
    signatures: list[dict] | None = None,
    doc_title_running: str = "",
    doc_meta_running: str = "",
) -> bytes:
    """Compose HTML từ template + render PDF với 3-tier fallback.

    Args mới (đẹp hơn):
      eyebrow            — nhãn nhỏ phía trên title trên cover (vd "Báo cáo tổng hợp")
      toc                — True để chèn mục lục (cần toc_items)
      toc_items          — [{level: 1|2|3, title: str, page: str?}]
      signatures         — [{role: "Người lập", name: ".......", title: "KS"}]
      doc_title_running  — chuỗi hiển thị ở @top-left mọi trang (mặc định = title)
      doc_meta_running   — chuỗi hiển thị ở @bottom-left (vd "Dự án 202605 TTHC")

    engine:
      - "auto"        — thử weasyprint → xhtml2pdf → reportlab
      - "weasyprint"  — bắt buộc tier-1 (raise nếu không có)
      - "xhtml2pdf"   — bắt buộc tier-2
      - "reportlab"   — bắt buộc tier-3 (text-only)
    """
    html_str = _REPORT_TEMPLATE.render(
        title=title,
        subtitle=subtitle,
        meta=meta or {},
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        css=_REPORT_CSS,
        content=content_html,
        cover=cover,
        eyebrow=eyebrow,
        toc=toc,
        toc_items=toc_items or [],
        signatures=signatures or [],
        doc_title_running=doc_title_running or title,
        doc_meta_running=doc_meta_running or (meta.get("Dự án", "") if meta else ""),
    )

    chain: list[str]
    if engine == "auto":
        chain = ["weasyprint", "xhtml2pdf", "reportlab"]
    else:
        chain = [engine]

    errors: list[str] = []
    for eng in chain:
        try:
            if eng == "weasyprint":
                if not _HAS_WEASYPRINT:
                    raise ImportError("weasyprint không khả dụng")
                return _render_pdf_weasyprint(html_str)
            if eng == "xhtml2pdf":
                if not _HAS_XHTML2PDF:
                    raise ImportError("xhtml2pdf không khả dụng")
                return _render_pdf_xhtml2pdf(html_str)
            if eng == "reportlab":
                if not _HAS_REPORTLAB:
                    raise ImportError("reportlab không khả dụng")
                return _render_pdf_reportlab(title, content_html,
                                             subtitle, meta or {}, cover)
            raise ValueError(f"Engine không hỗ trợ: {eng}")
        except Exception as e:
            errors.append(f"{eng}: {e}")
            warnings.warn(f"PDF engine '{eng}' fail → fallback. ({e})",
                          RuntimeWarning, stacklevel=2)
            continue

    raise RuntimeError(
        "Không engine PDF nào khả dụng. Lỗi:\n  - "
        + "\n  - ".join(errors)
        + "\nCài 1 trong: weasyprint / xhtml2pdf / reportlab."
    )


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
        eyebrow="Báo cáo thiết kế",
        subtitle="Cọc đất xi măng (Cement Deep Mixing) — Dự án 202605 TTHC",
        content_html="\n".join(parts),
        meta={
            "Dự án":        "202605 — Trung tâm Hành chính TP.HCM",
            "Khu vực":      state.get("cdm_zone", "—"),
            "Hố khoan":     state.get("cdm_bh", "—"),
            "Tiêu chuẩn":   "TCVN 9403:2012 · TCCS 41:2022",
            "Ngày xuất":    datetime.now().strftime("%d/%m/%Y %H:%M"),
        },
        doc_meta_running="202605 TTHC · " + state.get("cdm_zone", ""),
        signatures=[
            {"role": "Người lập",   "name": state.get("export_co_staff", ""), "title": "Kỹ sư địa kỹ thuật"},
            {"role": "Kiểm tra",    "name": "",                                "title": "Chủ nhiệm thiết kế"},
            {"role": "Phê duyệt",   "name": "",                                "title": "Lãnh đạo đơn vị"},
        ],
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
        title="BÁO CÁO DỰ BÁO LÚN NỀN",
        eyebrow="Báo cáo phân tích",
        subtitle="TCCS 41:2022 — So sánh phương án xử lý đất yếu",
        content_html="\n".join(parts),
        meta={
            "Dự án":      "202605 — Trung tâm Hành chính TP.HCM",
            "Khu vực":    state.get("sl_zone", "—"),
            "Hố khoan":   state.get("sl_bh", "—"),
            "Tiêu chuẩn": "TCCS 41:2022 · TCVN 9403:2012",
            "Ngày xuất":  datetime.now().strftime("%d/%m/%Y %H:%M"),
        },
        doc_meta_running="202605 TTHC · " + state.get("sl_zone", ""),
        signatures=[
            {"role": "Người lập",  "name": state.get("export_co_staff", ""), "title": "Kỹ sư địa kỹ thuật"},
            {"role": "Kiểm tra",   "name": "",                                "title": "Chủ nhiệm thiết kế"},
            {"role": "Phê duyệt",  "name": "",                                "title": "Lãnh đạo đơn vị"},
        ],
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
        title="BÁO CÁO CỌC VÁN SW — KÈ TTHC",
        eyebrow="Báo cáo thiết kế",
        subtitle="Kiểm tra NT1 / NT2 — TCVN 11823-10:2017 (đa phương pháp)",
        content_html="\n".join(parts),
        meta={
            "Dự án":      "202605 — Trung tâm Hành chính TP.HCM",
            "Khu vực":    "KE — Kè Công viên",
            "Loại cọc":   "SW (BTCT DUL chữ U lõi đặc)",
            "Tiêu chuẩn": "TCVN 11823-10:2017 · α-Tomlinson · SPT-Meyerhof",
            "Ngày xuất":  datetime.now().strftime("%d/%m/%Y %H:%M"),
        },
        doc_meta_running="202605 TTHC · Kè KE",
        signatures=[
            {"role": "Người lập",  "name": "", "title": "Kỹ sư địa kỹ thuật"},
            {"role": "Kiểm tra",   "name": "", "title": "Chủ nhiệm thiết kế"},
            {"role": "Phê duyệt",  "name": "", "title": "Lãnh đạo đơn vị"},
        ],
    )


# ────────────────────────────────────────────────────────────────────────────
# SQLite query helpers (sử dụng trong report_all mở rộng)
# ────────────────────────────────────────────────────────────────────────────
def _safe_query(db_path: Path, sql: str) -> pd.DataFrame:
    """Thực thi SQL an toàn — trả DataFrame rỗng nếu lỗi/bảng không tồn tại."""
    try:
        con = sqlite3.connect(str(db_path))
        df = pd.read_sql_query(sql, con)
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


def _section_geology(db_path: Path) -> str:
    """PHẦN 1 — Tổng quan địa chất: HK + lab + VST."""
    out = ['<div class="page-break"></div>',
           "<h1>PHẦN 1 — TỔNG QUAN ĐỊA CHẤT</h1>"]
    # 1.1 Danh sách hố khoan
    out.append("<h2>1.1 Danh sách hố khoan TTHC</h2>")
    df_bh = _safe_query(db_path, """
        SELECT z.code as 'Khu vực', b.name as 'HK',
               b.x_coord_m as 'X', b.y_coord_m as 'Y',
               b.elevation_m as 'Cao độ (m)',
               b.depth_m as 'Chiều sâu (m)'
        FROM boreholes b LEFT JOIN zones z ON z.id = b.zone_id
        ORDER BY z.code, b.name
    """)
    if not df_bh.empty:
        for col in ["X", "Y", "Cao độ (m)", "Chiều sâu (m)"]:
            if col in df_bh.columns:
                df_bh[col] = df_bh[col].apply(
                    lambda v: f"{v:.2f}" if pd.notna(v) else "—")
        out.append(df_to_html(df_bh))
    else:
        out.append('<div class="warning">Chưa có dữ liệu HK trong bảng boreholes.</div>')

    # 1.2 Thí nghiệm nén cố kết
    out.append("<h2>1.2 Thí nghiệm nén cố kết (lab_tests)</h2>")
    df_lab = _safe_query(db_path, """
        SELECT z.code as 'Khu vực', b.name as 'HK',
               COUNT(lt.Cc) as 'n mẫu Cc',
               ROUND(AVG(lt.Cc), 3) as 'Cc TB',
               ROUND(AVG(lt.Cs), 4) as 'Cs TB',
               ROUND(AVG(lt.e0), 3) as 'e₀ TB',
               ROUND(MIN(lt.PC_kPa), 0) as 'PC min',
               ROUND(MAX(lt.PC_kPa), 0) as 'PC max'
        FROM lab_tests lt
        JOIN boreholes b ON b.id = lt.borehole_id
        LEFT JOIN zones z ON z.id = b.zone_id
        WHERE lt.Cc IS NOT NULL
        GROUP BY b.id ORDER BY z.code, b.name
    """)
    if not df_lab.empty:
        out.append(df_to_html(df_lab))
    else:
        out.append('<div class="warning">Chưa có lab_tests với cột Cc.</div>')

    # 1.3 Vane Shear
    out.append("<h2>1.3 Thí nghiệm cắt cánh hiện trường (VST)</h2>")
    df_vst = _safe_query(db_path, """
        SELECT vl.name as 'Vị trí',
               COUNT(*) as 'n test',
               ROUND(MIN(vt.depth_m), 1) as 'Z min (m)',
               ROUND(MAX(vt.depth_m), 1) as 'Z max (m)',
               ROUND(AVG(vt.Su_kPa), 1) as 'Su TB (kPa)',
               ROUND(MIN(vt.Su_kPa), 1) as 'Su min',
               ROUND(MAX(vt.Su_kPa), 1) as 'Su max'
        FROM vane_shear_tests vt
        JOIN vst_locations vl ON vl.id = vt.vst_loc_id
        GROUP BY vl.id ORDER BY vl.name
    """)
    if not df_vst.empty:
        out.append(df_to_html(df_vst))
    else:
        out.append('<div class="warning">Chưa có vane_shear_tests.</div>')

    # 1.4 Khoảng cách hố khoan (TCCS 41:2022 Điều 5.3.2)
    out.append("<h2>1.4 Khoảng cách hố khoan vs TCCS 41:2022</h2>")
    df_sp = _safe_query(db_path, """
        SELECT bh1_name as 'HK 1', bh2_name as 'HK 2',
               ROUND(distance_m, 1) as 'Khoảng cách (m)',
               status as 'Trạng thái'
        FROM borehole_distances
        WHERE status != 'Đạt' OR design_step = 'BVTK'
        ORDER BY distance_m LIMIT 30
    """)
    if not df_sp.empty:
        out.append(df_to_html(df_sp, pass_col="Trạng thái"))
    else:
        out.append('<div class="warning">Chưa có borehole_distances. '
                   'Vào tab Địa chất → tính khoảng cách HK.</div>')
    return "\n".join(out)


def _section_sample_check(db_path: Path) -> str:
    """PHẦN 2 — Kiểm tra mẫu Cc vs TCCS 41:2022."""
    out = ['<div class="page-break"></div>',
           "<h1>PHẦN 2 — KIỂM TRA MẪU TN vs TCCS 41:2022</h1>"]
    out.append('<div class="info">Tiêu chuẩn TCCS 41:2022 yêu cầu tối thiểu '
               '6 mẫu Cc/HK (BVTK) với khoảng cách độ sâu ≤ 2m. '
               'Khu vực thiếu mẫu cần khoan bổ sung trước khi tính lún.</div>')
    df = _safe_query(db_path, """
        SELECT z.code as 'Khu vực', b.name as 'HK',
               COUNT(lt.Cc) as 'n_Cc có',
               CASE WHEN COUNT(lt.Cc) >= 6 THEN 'Đạt' ELSE 'Không đạt' END as 'Kết quả'
        FROM lab_tests lt
        JOIN boreholes b ON b.id = lt.borehole_id
        LEFT JOIN zones z ON z.id = b.zone_id
        WHERE lt.Cc IS NOT NULL
        GROUP BY b.id ORDER BY z.code, b.name
    """)
    if not df.empty:
        df["n_Cc cần"] = 6
        df["Thiếu"] = (6 - df["n_Cc có"]).clip(lower=0)
        df = df[["Khu vực", "HK", "n_Cc có", "n_Cc cần", "Thiếu", "Kết quả"]]
        out.append(df_to_html(df, pass_col="Kết quả"))
        # Tổng hợp theo khu vực
        out.append("<h2>2.1 Tổng hợp theo khu vực</h2>")
        df_zone = df.groupby("Khu vực").agg(
            n_HK_tổng=("HK", "count"),
            n_HK_đạt=("Kết quả", lambda s: int((s == "Đạt").sum())),
            thiếu_tổng=("Thiếu", "sum"),
        ).reset_index()
        df_zone["Trạng thái"] = df_zone.apply(
            lambda r: "Đạt" if r["n_HK_đạt"] == r["n_HK_tổng"] else "Không đạt",
            axis=1)
        out.append(df_to_html(df_zone, pass_col="Trạng thái"))
    else:
        out.append('<div class="warning">Chưa có dữ liệu lab_tests để kiểm tra.</div>')
    return "\n".join(out)


def _section_compare_scenarios(settlement_result: dict | None) -> str:
    """PHẦN 4 — So sánh phương án xử lý nền."""
    out = ['<div class="page-break"></div>',
           "<h1>PHẦN 4 — SO SÁNH 5 PHƯƠNG ÁN XỬ LÝ NỀN</h1>"]
    if not settlement_result or not settlement_result.get("scenarios"):
        out.append('<div class="warning">'
                   "Chưa chạy so sánh phương án. Vào tab 'Dự báo lún' → 'Tính toán lún'.</div>")
        return "\n".join(out)
    rows = []
    for sc in settlement_result["scenarios"]:
        t90 = f"{sc['t_90_months']:.0f}" if sc.get("t_90_months") else ">240"
        rows.append({
            "Phương án":         sc.get("label", "—"),
            "S tổng (cm)":       round(sc["S_total_cm"], 1),
            "S tại TC (cm)":     round(sc.get("S_at_constr_cm", 0), 1),
            "U TC (%)":          f"{sc.get('U_at_constr_pct', 0):.0f}",
            "S còn lại (cm)":    round(sc["residual_cm"], 1),
            "t₉₀ (tháng)":       t90,
            "Kết quả":           "Đạt" if sc.get("feasible") else "Không đạt",
        })
    out.append(df_to_html(pd.DataFrame(rows), pass_col="Kết quả"))
    out.append('<div class="info">Tham chiếu TCVN 9403:2012 Phụ lục C + TCCS 41:2022 mục 4.4. '
               'Lún CDM tính theo công thức S₁ đàn hồi: '
               '<code>S₁ = qH/(a·Ec + (1-a)·Es)</code>.</div>')
    return "\n".join(out)


def _section_ke_sw_detail(db_path: Path) -> str:
    """PHẦN 6 — Cọc ván SW chi tiết: NT1+NT2 + 4 phương pháp + multilayer."""
    out = ['<div class="page-break"></div>',
           "<h1>PHẦN 6 — CỌC VÁN SW KÈ KE (NT1/NT2 + 4 phương pháp)</h1>"]
    # 6.1 NT1
    out.append("<h2>6.1 NT1 — Chiều dài xuyên qua lớp yếu</h2>")
    df_nt1 = _safe_query(db_path, """
        SELECT bh_name as 'HK', pile_type as 'Cọc',
               ROUND(Z_m, 2) as 'Z (m)',
               ROUND(D_bottom_soft_m, 2) as 'D_bot_soft (m)',
               ROUND(L_req_nt1_m, 2) as 'L yêu cầu (m)',
               ROUND(L_design_m, 2) as 'L thiết kế (m)',
               ROUND(margin_nt1_m, 2) as 'Biên (m)',
               nt1_result as 'Kết quả NT1'
        FROM ke_sw_nt_detail ORDER BY bh_name
    """)
    if not df_nt1.empty:
        out.append(df_to_html(df_nt1, pass_col="Kết quả NT1"))
    else:
        out.append('<div class="warning">Chưa có ke_sw_nt_detail.</div>')

    # 6.2 NT2 đầy đủ
    out.append("<h2>6.2 NT2 — Sức kháng nhổ TCVN 11823-10:2017</h2>")
    df_nt2 = _safe_query(db_path, """
        SELECT bh_name as 'HK',
               ROUND(Rs_clay_kN, 0) as 'Rs sét (kN)',
               ROUND(Rs_sand_kN, 0) as 'Rs cát (kN)',
               ROUND(Rp_kN, 0) as 'Rp (kN)',
               ROUND(RR_kN, 0) as 'RR (kN)',
               ROUND(W_kN, 0) as 'W (kN)',
               ROUND(ratio_nt2, 2) as 'RR/W',
               nt2_result as 'Kết quả NT2',
               tip_method as 'Tip method',
               ROUND(phi_stat, 2) as 'φ_stat'
        FROM ke_sw_nt_detail ORDER BY bh_name
    """)
    if not df_nt2.empty:
        out.append(df_to_html(df_nt2, pass_col="Kết quả NT2"))
        out.append('<div class="info">'
                   '<strong>φ_stat dynamic</strong>: 0,30 khi cát Rs > 10% hoặc tip cát; '
                   '0,35 nếu sét chiếm ưu thế.</div>')
    else:
        out.append('<div class="warning">Chưa có dữ liệu NT2.</div>')

    # 6.3 Multilayer Rs per layer (nếu có) — JOIN với ke_sw_nt_detail
    df_ml = _safe_query(db_path, """
        SELECT d.bh_name as 'HK',
               m.layer_order as '#',
               m.symbol as 'Lớp',
               ROUND(m.L_m, 1) as 'L (m)',
               m.method as 'Phương pháp',
               ROUND(m.su_kPa, 1) as 'Su (kPa)',
               m.su_source as 'Nguồn Su',
               ROUND(m.alpha, 2) as 'α',
               ROUND(m.N160, 0) as 'N₁₆₀',
               ROUND(m.sigma_v_eff_kPa, 0) as 'σ_v eff (kPa)',
               ROUND(m.Rs_kN, 0) as 'Rs (kN)'
        FROM ke_sw_nt2_layers m
        JOIN ke_sw_nt_detail d ON d.id = m.sw_design_id
        ORDER BY d.bh_name, m.layer_order
    """)
    if not df_ml.empty:
        out.append("<h2>6.3 Phân tích đa lớp NT2 (Rs theo từng lớp)</h2>")
        out.append(df_to_html(df_ml))
    return "\n".join(out)


def _section_winkler_forces(db_path: Path) -> str:
    """PHẦN 7 — Nội lực cừ Winkler 7 HK (M/Q/u)."""
    out = ['<div class="page-break"></div>',
           "<h1>PHẦN 7 — NỘI LỰC CỪ WINKLER (7 HK KÈ KE)</h1>"]
    df = _safe_query(db_path, """
        SELECT bh_name as 'HK', pile_type as 'Cọc',
               ROUND(L_m, 1) as 'L (m)',
               ROUND(u_max_mm, 1) as 'u max (mm)',
               ROUND(M_max_kNm, 1) as 'M max (kN·m)',
               ROUND(Mcr_kNm, 1) as 'M_cr (kN·m)',
               CASE WHEN ABS(M_max_kNm) <= ABS(Mcr_kNm) THEN 'Đạt' ELSE 'Không đạt' END as 'Kiểm tra M',
               ROUND(Q_max_kN, 1) as 'Q max (kN)'
        FROM ke_sw_winkler_results ORDER BY bh_name
    """)
    if not df.empty:
        out.append(df_to_html(df, pass_col="Kiểm tra M"))
        out.append('<div class="info">Tải đầu vào: Active earth pressure + áp lực nước Front-Back '
                   '(quy ước CLAUDE.md §20). Solver: Winkler beam Euler-Bernoulli FEM thuần NumPy '
                   '(scripts/winkler_np.py) với consistent load vector Hermite.</div>')
    else:
        out.append('<div class="warning">'
                   '<strong>Phần này yêu cầu bảng <code>ke_sw_winkler_results</code></strong> '
                   '(chưa được tạo trong schema TTHC.sqlite).<br><br>'
                   'Để kích hoạt: cần thêm hàm <code>save_winkler_results_to_db()</code> '
                   'trong <code>scripts/wall_internal_force.py</code> để lưu (bh_name, '
                   'pile_type, L_m, u_max_mm, M_max_kNm, Mcr_kNm, Q_max_kN) sau mỗi lần '
                   'solve. Hiện tại nội lực cừ chỉ tồn tại trong báo cáo Word 7 HK '
                   '(tab Cọc ván SW → mục D).'
                   '</div>')
    return "\n".join(out)


def _section_summary(state: dict, db_path: Path,
                     settlement_result: dict | None) -> str:
    """PHẦN 8 — Tổng kết và khuyến nghị."""
    out = ['<div class="page-break"></div>',
           "<h1>PHẦN 8 — TỔNG KẾT VÀ KHUYẾN NGHỊ</h1>"]
    out.append("<h2>8.1 Kết quả chính</h2>")
    rows = []
    # CDM
    rows.append({"Hạng mục": "CDM — Khu vực", "Giá trị": state.get("cdm_zone", "—")})
    rows.append({"Hạng mục": "CDM — Hố khoan", "Giá trị": state.get("cdm_bh", "—")})
    rows.append({"Hạng mục": "CDM — D × Lc",
                 "Giá trị": f"{state.get('cdm_D', 0.8):.2f} × {state.get('cdm_Lc', 23):.1f} m"})
    rows.append({"Hạng mục": "CDM — qu thiết kế",
                 "Giá trị": f"{state.get('cdm_qu', 1000):.0f} kPa"})
    # Settlement
    if settlement_result and settlement_result.get("scenarios"):
        cdm_sc = next((s for s in settlement_result["scenarios"]
                       if "cdm" in s.get("label", "").lower()), None)
        if cdm_sc:
            rows.append({"Hạng mục": "Lún CDM",
                         "Giá trị": f"{cdm_sc['S_total_cm']:.1f} cm "
                         f"(còn lại {cdm_sc['residual_cm']:.1f} cm)"})
    # SW
    df_sw = _safe_query(db_path, """
        SELECT COUNT(*) as n,
               SUM(CASE WHEN nt1_result='Đạt' THEN 1 ELSE 0 END) as nt1_ok,
               SUM(CASE WHEN nt2_result='Đạt' THEN 1 ELSE 0 END) as nt2_ok
        FROM ke_sw_nt_detail
    """)
    if not df_sw.empty and df_sw.iloc[0]["n"] > 0:
        r = df_sw.iloc[0]
        rows.append({"Hạng mục": "Cọc ván SW — NT1",
                     "Giá trị": f"{r['nt1_ok']}/{r['n']} HK đạt"})
        rows.append({"Hạng mục": "Cọc ván SW — NT2",
                     "Giá trị": f"{r['nt2_ok']}/{r['n']} HK đạt"})
    out.append(df_to_html(pd.DataFrame(rows)))

    out.append("<h2>8.2 Khuyến nghị tiêu chuẩn</h2>")
    out.append('<div class="formula">'
               'Thiết kế tuân thủ:<br>'
               '• <strong>TCVN 9403:2012</strong> — Trụ đất xi măng (CDM)<br>'
               '• <strong>TCCS 41:2022</strong> — Nền đường đất yếu (tính lún + bấc thấm + giếng cát)<br>'
               '• <strong>TCVN 11823-10:2017</strong> — Móng và nền — Cọc đóng (NT2)<br>'
               '• <strong>Eurocode 7</strong> — Đối chứng giá trị thiết kế (Fs ≥ 1,5)'
               '</div>')
    return "\n".join(out)


def report_all(state: dict, db_path: Path,
               settlement_result: dict | None = None) -> bytes:
    """PDF tổng hợp toàn bộ — 8 phần đầy đủ.

    Cấu trúc:
      1. Tổng quan địa chất (HK, lab, VST, khoảng cách)
      2. Kiểm tra mẫu TN vs TCCS 41:2022
      3. Thông số CDM
      4. So sánh 5 phương án xử lý nền
      5. Dự báo lún chi tiết (scenarios)
      6. Cọc ván SW (NT1+NT2 đa phương pháp)
      7. Nội lực cừ Winkler 7 HK
      8. Tổng kết & khuyến nghị
    """
    parts = []

    # ── Phần 1 + 2: Địa chất + Mẫu TN (mới — đọc từ SQLite) ─────────────────
    parts.append(_section_geology(db_path))
    parts.append(_section_sample_check(db_path))

    # Phần 3: Thông số CDM
    parts.append('<div class="page-break"></div>')
    parts.append("<h1>PHẦN 3 — THÔNG SỐ CDM</h1>")
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

    # ── Phần 4: So sánh phương án CDM (mới) ─────────────────────────────────
    parts.append(_section_compare_scenarios(settlement_result))

    # Phần 5: Dự báo lún chi tiết
    parts.append('<div class="page-break"></div>')
    parts.append("<h1>PHẦN 5 — DỰ BÁO LÚN CHI TIẾT (TCCS 41:2022)</h1>")
    if settlement_result:
        rows = []
        for sc in settlement_result["scenarios"]:
            t90 = f"{sc.get('t_90_months', 0):.0f}" if sc.get("t_90_months") else ">240"
            rows.append({
                "Phương án":        sc["label"],
                "Lún tổng (cm)":    round(sc["S_total_cm"], 1),
                "Lún tại TC (cm)":  round(sc.get("S_at_constr_cm", 0), 1),
                "U TC (%)":         f"{sc.get('U_at_constr_pct', 0):.0f}",
                "Lún còn lại (cm)": round(sc["residual_cm"], 1),
                "t₉₀ (tháng)":      t90,
                "Kết quả":          "Đạt" if sc["feasible"] else "Không đạt",
            })
        parts.append(df_to_html(pd.DataFrame(rows), pass_col="Kết quả"))
        # Bảng lún từng lớp (nếu có)
        layers_df = _safe_query(db_path, """
            SELECT scenario_label as 'Phương án', layer_symbol as 'Lớp',
                   ROUND(depth_top_m, 1) as 'Z top (m)',
                   ROUND(depth_bot_m, 1) as 'Z bot (m)',
                   ROUND(sigma_v0_kPa, 0) as 'σ_v0 (kPa)',
                   ROUND(sigma_vf_kPa, 0) as 'σ_vf (kPa)',
                   ROUND(PC_kPa, 0) as 'PC (kPa)',
                   ROUND(Si_cm, 1) as 'Si (cm)',
                   OC_status as 'OC/NC'
            FROM settlement_layers
            ORDER BY scenario_label, depth_top_m
        """)
        if not layers_df.empty:
            parts.append("<h2>5.1 Chi tiết lún từng lớp</h2>")
            parts.append(df_to_html(layers_df))
    else:
        parts.append('<div class="warning">Chưa chạy tính lún. Vào tab Dự báo lún → nhấn Tính toán.</div>')

    # ── Phần 6: Cọc ván SW chi tiết (mở rộng) ───────────────────────────────
    parts.append(_section_ke_sw_detail(db_path))

    # ── Phần 7: Nội lực cừ Winkler (mới) ────────────────────────────────────
    parts.append(_section_winkler_forces(db_path))

    # ── Phần 8: Tổng kết & khuyến nghị (mới) ────────────────────────────────
    parts.append(_section_summary(state, db_path, settlement_result))

    # TOC tĩnh — tên 8 phần theo cấu trúc report_all
    _toc = [
        {"level": 1, "title": "Phần 1 — Tổng quan địa chất"},
        {"level": 2, "title": "1.1 Hố khoan và lớp đất"},
        {"level": 2, "title": "1.2 Thí nghiệm phòng & VST"},
        {"level": 1, "title": "Phần 2 — Kiểm tra mẫu vs TCCS 41:2022"},
        {"level": 1, "title": "Phần 3 — Thông số CDM"},
        {"level": 1, "title": "Phần 4 — So sánh 5 phương án xử lý"},
        {"level": 1, "title": "Phần 5 — Dự báo lún chi tiết"},
        {"level": 2, "title": "5.1 Chi tiết lún từng lớp"},
        {"level": 1, "title": "Phần 6 — Cọc ván SW (NT1 + NT2)"},
        {"level": 1, "title": "Phần 7 — Nội lực cừ Winkler 7 HK"},
        {"level": 1, "title": "Phần 8 — Tổng kết & khuyến nghị"},
    ]
    return build_report_pdf(
        title="BÁO CÁO TỔNG HỢP",
        eyebrow="Báo cáo kỹ thuật tổng hợp",
        subtitle=("Địa chất · Thí nghiệm · CDM · Lún · Cọc ván SW · Nội lực cừ "
                  "— Dự án 202605 TTHC"),
        content_html="\n".join(parts),
        meta={
            "Dự án":      "202605 — Trung tâm Hành chính TP.HCM",
            "Khu vực":    state.get("cdm_zone", "—"),
            "Hố khoan":   state.get("cdm_bh", "—"),
            "Tiêu chuẩn": ("TCVN 9403:2012 · TCCS 41:2022 · "
                          "TCVN 11823-10:2017 · Eurocode 7"),
            "Phạm vi":    "8 phần · ~30–60 trang A4",
            "Ngày xuất":  datetime.now().strftime("%d/%m/%Y %H:%M"),
        },
        toc=True,
        toc_items=_toc,
        doc_meta_running="202605 TTHC · " + state.get("cdm_zone", ""),
        signatures=[
            {"role": "Người lập",  "name": state.get("export_co_staff", ""), "title": "Kỹ sư địa kỹ thuật"},
            {"role": "Kiểm tra",   "name": "",                                "title": "Chủ nhiệm thiết kế"},
            {"role": "Phê duyệt",  "name": "",                                "title": "Lãnh đạo đơn vị"},
        ],
    )
