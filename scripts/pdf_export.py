"""
pdf_export.py — Tạo PDF từ snapshot tab/app Streamlit.

Dùng reportlab Platypus + matplotlib snapshot. Hỗ trợ:
- Heading, paragraph, caption
- Bảng pandas DataFrame
- Hình matplotlib (auto resize fit page width)
- Hình plotly (nếu có kaleido)
- Trang A4 portrait, font Vietnamese Unicode (Helvetica fallback)

Public API:
- PdfBuilder().h1/h2/h3/p/table/fig/image/spacer/page_break/build()
- build_tab_pdf(title, sections: list[dict]) → bytes
"""
from __future__ import annotations
import io
from datetime import datetime
from typing import Any
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Đăng ký font Vietnamese từ matplotlib bundled fonts
_FONT_REGISTERED = False
def _register_vn_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    try:
        # Windows: Arial / Tahoma có sẵn hỗ trợ tiếng Việt
        import os
        candidates = [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\tahoma.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux (Cloud)
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        for font_path in candidates:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont("VNFont", font_path))
                _FONT_REGISTERED = True
                return
    except Exception:
        pass

_register_vn_font()
_FONT = "VNFont" if _FONT_REGISTERED else "Helvetica"


def _styles():
    base = getSampleStyleSheet()
    return {
        "title":   ParagraphStyle("title",   parent=base["Title"],
                                  fontName=_FONT, fontSize=16, spaceAfter=8, alignment=1),
        "h1":      ParagraphStyle("h1",      parent=base["Heading1"],
                                  fontName=_FONT, fontSize=13, textColor=colors.HexColor("#1F4E79"),
                                  spaceBefore=12, spaceAfter=6),
        "h2":      ParagraphStyle("h2",      parent=base["Heading2"],
                                  fontName=_FONT, fontSize=11, textColor=colors.HexColor("#1F4E79"),
                                  spaceBefore=8, spaceAfter=4),
        "h3":      ParagraphStyle("h3",      parent=base["Heading3"],
                                  fontName=_FONT, fontSize=10, textColor=colors.HexColor("#444"),
                                  spaceBefore=6, spaceAfter=3),
        "p":       ParagraphStyle("p",       parent=base["BodyText"],
                                  fontName=_FONT, fontSize=9.5, leading=12, spaceAfter=4),
        "caption": ParagraphStyle("caption", parent=base["BodyText"],
                                  fontName=_FONT, fontSize=8, leading=10, textColor=colors.grey,
                                  spaceAfter=4, alignment=1),
        "footer":  ParagraphStyle("footer",  parent=base["BodyText"],
                                  fontName=_FONT, fontSize=7, textColor=colors.grey),
    }


class PdfBuilder:
    """Build PDF từ các block: heading, paragraph, table, fig."""
    def __init__(self, page_size=A4):
        self.story: list = []
        self.page_size = page_size
        self.styles = _styles()
        # Page width usable
        self._w = page_size[0] - 24 * mm  # 12mm margin mỗi bên

    def title(self, text: str):
        self.story.append(Paragraph(text, self.styles["title"]))
        self.story.append(Spacer(1, 6))

    def h1(self, text: str):
        self.story.append(Paragraph(text, self.styles["h1"]))

    def h2(self, text: str):
        self.story.append(Paragraph(text, self.styles["h2"]))

    def h3(self, text: str):
        self.story.append(Paragraph(text, self.styles["h3"]))

    def p(self, text: str):
        # Escape XML đặc biệt
        text = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        text = text.replace("\n", "<br/>")
        self.story.append(Paragraph(text, self.styles["p"]))

    def caption(self, text: str):
        text = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        self.story.append(Paragraph(text, self.styles["caption"]))

    def spacer(self, h: float = 6):
        self.story.append(Spacer(1, h))

    def page_break(self):
        self.story.append(PageBreak())

    def table(self, data, header=True, col_widths=None, caption: str | None = None):
        """data: list[list] | pandas.DataFrame."""
        try:
            import pandas as pd
            if isinstance(data, pd.DataFrame):
                hdr = [str(c) for c in data.columns]
                rows = [[str(v) if v is not None else "—" for v in r] for r in data.values.tolist()]
                data = [hdr] + rows if header else rows
        except Exception:
            pass
        if not data:
            return
        n_cols = len(data[0])
        if col_widths is None:
            col_widths = [self._w / n_cols] * n_cols
        tbl = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
        ts = [
            ("FONTNAME", (0, 0), (-1, -1), _FONT),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEADING",  (0, 0), (-1, -1), 10),
            ("GRID",     (0, 0), (-1, -1), 0.4, colors.HexColor("#888")),
            ("VALIGN",   (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",    (0, 0), (-1, -1), "CENTER"),
        ]
        if header:
            ts += [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
                ("FONTSIZE",   (0, 0), (-1, 0), 8.5),
            ]
        tbl.setStyle(TableStyle(ts))
        self.story.append(KeepTogether([tbl, Spacer(1, 4)]))
        if caption:
            self.caption(caption)

    def fig(self, mpl_fig, caption: str | None = None, max_width: float | None = None):
        """Matplotlib Figure → embed as PNG."""
        buf = io.BytesIO()
        mpl_fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
        buf.seek(0)
        self.image(buf, caption=caption, max_width=max_width)

    def image(self, buf_or_path, caption: str | None = None, max_width: float | None = None):
        try:
            mw = max_width if max_width else self._w
            img = Image(buf_or_path, width=mw, kind="proportional")
            # Giới hạn chiều cao 16cm để không vượt 1 trang
            if img.imageHeight * (mw / img.imageWidth) > 16 * cm:
                ratio = 16 * cm / (img.imageHeight * (mw / img.imageWidth))
                img._width  = mw * ratio
                img._height = 16 * cm
            self.story.append(KeepTogether([img, Spacer(1, 3)]))
            if caption:
                self.caption(caption)
        except Exception as e:
            self.p(f"[Lỗi nhúng ảnh: {e}]")

    def build(self, title: str = "Báo cáo", author: str = "PLAXIS AI Copilot") -> bytes:
        out = io.BytesIO()
        doc = SimpleDocTemplate(
            out, pagesize=self.page_size,
            leftMargin=12 * mm, rightMargin=12 * mm,
            topMargin=14 * mm, bottomMargin=14 * mm,
            title=title, author=author,
        )

        def _on_page(canvas, doc_):
            canvas.saveState()
            canvas.setFont(_FONT, 7)
            canvas.setFillColor(colors.grey)
            canvas.drawString(12 * mm, 8 * mm,
                              f"{title} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            canvas.drawRightString(
                self.page_size[0] - 12 * mm, 8 * mm,
                f"Trang {doc_.page}",
            )
            canvas.restoreState()

        doc.build(self.story, onFirstPage=_on_page, onLaterPages=_on_page)
        return out.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# Tab snapshot builders
# ──────────────────────────────────────────────────────────────────────────────

def build_params_pdf(state: dict) -> bytes:
    """Snapshot tab Thông số CDM từ session_state."""
    b = PdfBuilder()
    b.title("Báo cáo Thông số CDM")
    b.p(f"Khu vực: {state.get('cdm_zone','—')} | Hố khoan: {state.get('cdm_bh','—')}")
    b.h1("1. Hình học cọc")
    rows = [
        ["Tham số", "Giá trị", "Đơn vị"],
        ["Đường kính D", f"{state.get('cdm_D',0.8):.2f}", "m"],
        ["Khoảng cách e", f"{state.get('cdm_e',1.6):.2f}", "m"],
        ["Cao độ đỉnh cọc CDTK", f"{state.get('cdm_CDTK',2.7):+.2f}", "m"],
        ["Chiều dài cọc Lc", f"{state.get('cdm_Lc',23):.1f}", "m"],
        ["Bố trí", state.get('cdm_arrangement','triangle'), "—"],
    ]
    b.table(rows)
    b.h1("2. Vật liệu")
    rows = [
        ["Tham số", "Giá trị", "Đơn vị"],
        ["Loại xi măng", state.get("cdm_cement_type", "PCB40"), "—"],
        ["Hàm lượng xi măng", f"{state.get('cdm_dosage',250)}", "kg/m³"],
        ["Tỷ lệ N/XM", f"{state.get('cdm_WC',0.8):.2f}", "—"],
        ["qu thiết kế", f"{state.get('cdm_qu',1000):.0f}", "kPa"],
        ["FS_lab", f"{state.get('cdm_FS_lab',1.5):.1f}", "—"],
    ]
    b.table(rows)
    b.h1("3. Thông số địa chất")
    rows = [
        ["Tham số", "Giá trị", "Đơn vị"],
        ["Đỉnh lớp bùn", f"{state.get('cdm_top_clay',-1):+.2f}", "m"],
        ["Chiều dày h_clay", f"{state.get('cdm_h_clay',22):.1f}", "m"],
        ["Su trung bình", f"{state.get('cdm_Su',10):.1f}", "kPa"],
        ["γ đất", f"{state.get('cdm_gamma',16):.1f}", "kN/m³"],
    ]
    b.table(rows)
    b.h1("4. Tải trọng")
    ld = state.get("cdm_loads", {})
    rows = [
        ["Tham số", "Giá trị", "Đơn vị"],
        ["Tải trọng xe q_traffic", f"{ld.get('q_traffic',20):.1f}", "kN/m²"],
        ["Chiều cao mặt đường h_road", f"{ld.get('h_road',0.8):.2f}", "m"],
        ["He — cát đắp", f"{ld.get('h_fill',1.5):.2f}", "m"],
        ["Hse — đệm cát", f"{ld.get('h_mat',0.4):.2f}", "m"],
        ["Cao độ thiết kế z_tk", f"{ld.get('z_tk',3.5):+.2f}", "m"],
    ]
    b.table(rows)
    return b.build("Báo cáo Thông số CDM")


def build_settlement_pdf(state: dict, result: dict | None = None) -> bytes:
    b = PdfBuilder()
    b.title("Báo cáo Dự báo lún (TCCS 41:2022)")
    b.p(f"Khu vực: {state.get('sl_zone','—')} | Hố khoan: {state.get('sl_bh','—')}")
    if result:
        cdm_sc = next((s for s in result["scenarios"] if s["method"] == "cdm"), None)
        b.h1("Tóm tắt kết quả")
        rows = [["Phương án", "Lún tổng (cm)", "Lún tại TC (cm)", "U TC (%)",
                 "Lún còn lại (cm)", "Đánh giá"]]
        for sc in result["scenarios"]:
            rows.append([
                sc["label"], f"{sc['S_total_cm']:.1f}", f"{sc['S_at_constr_cm']:.1f}",
                f"{sc['U_at_constr_pct']:.0f}", f"{sc['residual_cm']:.1f}",
                "Đạt" if sc["feasible"] else "Không đạt",
            ])
        b.table(rows)
        b.spacer(8)
        b.h2("Thông số CDM")
        b.p(f"a = {result.get('cdm_area_ratio',0.25):.2f} | "
            f"beta = {result.get('cdm_beta',1):.3f} | "
            f"Ec = {result.get('cdm_Ec_kPa',0):.0f} kPa | "
            f"Es = {result.get('cdm_Es_kPa',0):.0f} kPa")
    else:
        b.p("(Chưa có kết quả tính. Nhấn 'Tính toán lún' trên app trước.)")
    return b.build("Báo cáo Dự báo lún")


def build_ke_sw_pdf(db_path: Path) -> bytes:
    import sqlite3
    b = PdfBuilder()
    b.title("Báo cáo Cọc ván SW kè TTHC — NT1 / NT2 (TCVN 11823-10:2017)")
    con = sqlite3.connect(str(db_path))
    rows = con.execute("""
        SELECT bh_name, pile_type, L_design_m, L_req_nt1_m, margin_nt1_m, nt1_result,
               Rs_kN, Rp_kN, RR_kN, W_kN, ratio_nt2, nt2_result, tip_symbol, tip_method
        FROM ke_sw_nt_detail ORDER BY bh_name
    """).fetchall()
    con.close()
    if not rows:
        b.p("Chưa có dữ liệu NT trong SQLite.")
    else:
        b.h1("Bảng tổng hợp NT1 / NT2 — 7 HK trên tuyến kè")
        tbl_rows = [["HK", "Cọc", "L tk", "L req", "Δ NT1", "NT1",
                     "Rs", "Rp", "RR", "W", "RR/W", "NT2", "Tip", "Method"]]
        for r in rows:
            tbl_rows.append([
                r[0].replace("KE-", ""), r[1], f"{r[2]:.0f}", f"{r[3]:.1f}",
                f"{r[4]:+.2f}", r[5][:5],
                f"{r[6]:.0f}", f"{r[7]:.0f}", f"{r[8]:.0f}", f"{r[9]:.0f}",
                f"{r[10]:.2f}", r[11][:5], r[12] or "—", r[13] or "α",
            ])
        b.table(tbl_rows)
        b.spacer(8)
        b.h2("Ghi chú phương pháp")
        b.p("Method: α = Tomlinson 1980 (sét, Điều 7.3.8.6.2, φ=0.35);  "
            "SPT = Meyerhof (cát, Điều 7.3.8.6.7, φ=0.30).  "
            "Auto: α cho sét + SPT cho cát, φ dynamic.")
    return b.build("Báo cáo Cọc ván SW kè TTHC")


def build_all_pdf(state: dict, db_path: Path,
                  settlement_result: dict | None = None) -> bytes:
    """PDF tổng hợp gồm tất cả tab."""
    b = PdfBuilder()
    b.title("BÁO CÁO TỔNG HỢP — Dự án 202605 TTHC")
    b.p(f"Khu vực: {state.get('cdm_zone','—')} | "
        f"Hố khoan ưu tiên: {state.get('cdm_bh','—')}  \n"
        f"Ngày in: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    b.page_break()

    b.h1("PHẦN 1 — THÔNG SỐ CDM")
    sub = build_params_pdf(state)  # tạo 1 PDF rồi parse story là phức tạp; gọi inline:
    # Tận dụng helpers trực tiếp
    b.h2("Hình học cọc")
    b.table([
        ["Tham số", "Giá trị", "Đơn vị"],
        ["D",  f"{state.get('cdm_D',0.8):.2f}",  "m"],
        ["e",  f"{state.get('cdm_e',1.6):.2f}",  "m"],
        ["CDTK",  f"{state.get('cdm_CDTK',2.7):+.2f}", "m"],
        ["Lc", f"{state.get('cdm_Lc',23):.1f}", "m"],
    ])
    b.h2("Vật liệu + Tải trọng")
    ld = state.get("cdm_loads", {})
    b.table([
        ["Tham số", "Giá trị"],
        ["qu thiết kế", f"{state.get('cdm_qu',1000):.0f} kPa"],
        ["q_traffic",  f"{ld.get('q_traffic',20):.1f} kN/m²"],
        ["z_tk",  f"{ld.get('z_tk',3.5):+.2f} m"],
    ])

    b.page_break()
    b.h1("PHẦN 2 — DỰ BÁO LÚN")
    if settlement_result:
        rows = [["Phương án", "Lún tổng (cm)", "Lún còn lại (cm)", "Đánh giá"]]
        for sc in settlement_result["scenarios"]:
            rows.append([
                sc["label"], f"{sc['S_total_cm']:.1f}",
                f"{sc['residual_cm']:.1f}",
                "Đạt" if sc["feasible"] else "Không đạt",
            ])
        b.table(rows)
    else:
        b.p("(Chạy 'Tính toán lún' để có dữ liệu phần này.)")

    b.page_break()
    b.h1("PHẦN 3 — CỌC VÁN SW (NT1 / NT2)")
    import sqlite3
    try:
        con = sqlite3.connect(str(db_path))
        rows = con.execute("""
            SELECT bh_name, L_design_m, L_req_nt1_m, margin_nt1_m, nt1_result,
                   Rs_kN, Rp_kN, RR_kN, W_kN, ratio_nt2, nt2_result, tip_method
            FROM ke_sw_nt_detail ORDER BY bh_name
        """).fetchall()
        con.close()
        if rows:
            tbl = [["HK", "L tk", "L req", "Δ NT1", "NT1",
                    "Rs", "Rp", "RR", "W", "RR/W", "NT2", "Method"]]
            for r in rows:
                tbl.append([
                    r[0].replace("KE-", ""), f"{r[1]:.0f}", f"{r[2]:.1f}",
                    f"{r[3]:+.2f}", r[4][:5],
                    f"{r[5]:.0f}", f"{r[6]:.0f}", f"{r[7]:.0f}", f"{r[8]:.0f}",
                    f"{r[9]:.2f}", r[10][:5], r[11] or "α",
                ])
            b.table(tbl)
        else:
            b.p("Chưa có dữ liệu NT.")
    except Exception as e:
        b.p(f"Lỗi đọc DB: {e}")

    return b.build("Báo cáo Tổng hợp Dự án TTHC")
