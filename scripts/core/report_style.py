"""
scripts/core/report_style.py — Constants + helper chung cho bảng UI (Streamlit) và Word (python-docx).

Single source of truth cho định dạng bảng báo cáo. Sửa constants ở đây → UI và Word
tự đồng bộ. KHÔNG hardcode màu/size ở chỗ khác.

Áp dụng các nguyên tắc memory:
  - feedback-bold-table-headers
  - feedback-report-typography (12pt + zebra)
  - feedback-table-style-ui-docx-parity (UI ≡ Word)
"""
from __future__ import annotations

# ─── Constants — sửa 1 chỗ là cả UI lẫn Word đổi ─────────────────────────
HEADER_BG       = "#1f2937"   # navy đậm
HEADER_FG       = "#ffffff"   # chữ trắng
HEADER_BOLD     = True
HEADER_FONT_PT  = 12

ROW_EVEN_BG     = "#f3f4f6"   # zebra dòng chẵn (nền nhạt)
ROW_ODD_BG      = "#ffffff"

BODY_FONT_PT    = 12
BODY_FG         = "#111827"

BORDER_COLOR    = "#d1d5db"
CELL_PADDING_PX = 6


# ─── Streamlit — render HTML đồng bộ với Word ────────────────────────────
def html_css_block() -> str:
    """Trả về <style>...</style> cho bảng .report-table. Embed 1 lần đầu trang."""
    return f"""
<style>
table.report-table {{
    border-collapse: collapse;
    width: 100%;
    margin: 0.5em 0 1em 0;
    font-size: {BODY_FONT_PT}pt;
    color: {BODY_FG};
    font-family: inherit;
}}
table.report-table thead th {{
    background-color: {HEADER_BG};
    color: {HEADER_FG};
    font-weight: {'bold' if HEADER_BOLD else 'normal'};
    font-size: {HEADER_FONT_PT}pt;
    padding: {CELL_PADDING_PX}px {CELL_PADDING_PX + 2}px;
    text-align: left;
    border: 1px solid {BORDER_COLOR};
}}
table.report-table tbody td {{
    padding: {CELL_PADDING_PX}px {CELL_PADDING_PX + 2}px;
    border: 1px solid {BORDER_COLOR};
    font-size: {BODY_FONT_PT}pt;
}}
table.report-table tbody tr:nth-child(even) td {{
    background-color: {ROW_EVEN_BG};
}}
table.report-table tbody tr:nth-child(odd) td {{
    background-color: {ROW_ODD_BG};
}}
</style>
"""


def df_to_report_html(df, classes: str = "report-table") -> str:
    """pandas DataFrame → HTML có class 'report-table' khớp với CSS html_css_block().

    Dùng với st.markdown(html, unsafe_allow_html=True) để hiển thị bảng đồng bộ Word.
    """
    return df.to_html(classes=classes, index=False, border=0, escape=False)


# ─── Word (python-docx) — style table khớp với UI HTML ───────────────────
def _shade_cell(cell, hex_color: str) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color.lstrip("#"))
    cell._tc.get_or_add_tcPr().append(shd)


def _cell_has_shading(cell) -> bool:
    """Trả True nếu cell đã có w:shd (custom color đặt trước)."""
    from docx.oxml.ns import qn
    tcPr = cell._tc.tcPr
    if tcPr is None:
        return False
    return tcPr.find(qn("w:shd")) is not None


def _set_cell_border(cell, color_hex: str = BORDER_COLOR, size_pt: float = 0.5) -> None:
    """Đặt border 4 cạnh cho cell."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn("w:tcBorders"))
    if tcBorders is None:
        tcBorders = OxmlElement("w:tcBorders")
        tcPr.append(tcBorders)
    for edge in ("top", "left", "bottom", "right"):
        el = tcBorders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            tcBorders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(int(size_pt * 8)))  # 1/8 pt units
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color_hex.lstrip("#"))


def style_tbl_for_docx(tbl, preserve_existing: bool = True,
                        force_font_size: bool = False) -> None:
    """Áp định dạng chuẩn báo cáo lên python-docx Table.

    preserve_existing=True (mặc định): cell đã có shading custom (vd cột "Đạt"/"Không đạt"
    tô xanh/đỏ) → KHÔNG override. Chỉ áp zebra cho cell chưa có màu.
    force_font_size=False (mặc định): chỉ set Pt(BODY_FONT_PT) khi run chưa có font.size
    → tránh override các bảng cố ý dùng size nhỏ hơn (vd compact 7-8pt).

    Gọi SAU khi đã add_row + điền data cho mọi cell.
    """
    from docx.shared import Pt, RGBColor
    if not tbl.rows:
        return
    hdr_rgb_fg = RGBColor.from_string(HEADER_FG.lstrip("#"))
    body_rgb_fg = RGBColor.from_string(BODY_FG.lstrip("#"))

    # Header row (row 0)
    for cell in tbl.rows[0].cells:
        if not (preserve_existing and _cell_has_shading(cell)):
            _shade_cell(cell, HEADER_BG)
        _set_cell_border(cell)
        for para in cell.paragraphs:
            for run in para.runs:
                run.bold = HEADER_BOLD
                if force_font_size or run.font.size is None:
                    run.font.size = Pt(HEADER_FONT_PT)
                if run.font.color.rgb is None:
                    run.font.color.rgb = hdr_rgb_fg

    # Body rows (row 1+)
    for i, row in enumerate(tbl.rows[1:], start=1):
        for cell in row.cells:
            _set_cell_border(cell)
            if not (preserve_existing and _cell_has_shading(cell)):
                if i % 2 == 0:
                    _shade_cell(cell, ROW_EVEN_BG)
                else:
                    _shade_cell(cell, ROW_ODD_BG)
            for para in cell.paragraphs:
                for run in para.runs:
                    if force_font_size or run.font.size is None:
                        run.font.size = Pt(BODY_FONT_PT)
                    if run.font.color.rgb is None:
                        run.font.color.rgb = body_rgb_fg
