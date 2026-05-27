### 14. Stack Thư viện — Quy tắc Áp dụng cho Mỗi Loại Việc

| Thư viện | Phiên bản | Dùng cho | Đánh giá | Phạm vi áp dụng |
|---|---|---|---|---|
| **WeasyPrint** | ≥ 68.0 | **PDF từ HTML/CSS** (tier-1) | ★★★ PDF quality | `scripts/pdf_report.py` — primary engine, HTML/CSS/Jinja2 pipeline. KHÔNG có trên Cloud Python 3.14 (brotli/zopfli wheel) |
| **xhtml2pdf** | ≥ 0.2.16 | **PDF từ HTML/CSS** (tier-2) | ★★ pure Python, CSS cơ bản | Fallback tier-2 — chạy được trên Cloud. Hỗ trợ table/color/font/page-break, KHÔNG hỗ trợ flexbox/grid/`@top-right` (đã strip auto trong `_strip_unsupported_css`) |
| **Plotly** | ≥ 6.0 | **Biểu đồ tương tác** | ★★★ professional charts | Biểu đồ trên web (drag/zoom/hover). Static PNG → embed PDF qua `kaleido` (chỉ local) |
| **Matplotlib** | ≥ 3.8 | **Biểu đồ cho PDF + fallback** | ★★ simple & fast | Sơ đồ CDM, soil column, mặt cắt. **BẮT BUỘC dùng MPL cho mọi chart embed PDF trên Cloud** (kaleido không khả dụng) |
| **Pandas** | ≥ 2.0 | **Xử lý dữ liệu + Bảng** | ★★★ easy data | `read_csv/read_excel`, `DataFrame.to_html()` cho table render |
| **SymPy** | ≥ 1.14 | **Công thức symbolic** | ★★★ math symbolic | Derive công thức parametric ($\sigma = f(\epsilon)$), latex output |
| **LaTeX (MathJax/KaTeX)** | — (built-in) | **Render công thức** | ★★★ standard | `$$...$$` trong `st.markdown` (web) + WeasyPrint MathML (PDF); chuẩn hoá tất cả công thức |
| **ReportLab** | ≥ 4.0 | **PDF programmatic** (tier-3) | ★★★ full control | `scripts/pdf_export.py` + tier-3 fallback trong `pdf_report.py` — text-only khi cả weasyprint+xhtml2pdf đều fail |
| **Kaleido** | ≥ 1.0 | Plotly fig → PNG | — | CHỈ LOCAL — không có wheel cp314. Trên Cloud: vẽ lại bằng Matplotlib |
| **Jinja2** | ≥ 3.1 | HTML template | — | `_REPORT_TEMPLATE` trong `pdf_report.py` |
| **NumPy** | ≥ 1.26 | Tính toán array | — | Mọi tính toán số |
| **openpyxl + xlrd** | — | Đọc Excel | — | `.xlsx` (openpyxl), `.xls` cũ (xlrd) |

**Quy tắc bắt buộc**:

1. **PDF báo cáo** — pipeline 3-tier auto-fallback trong `scripts/pdf_report.py::build_report_pdf(engine="auto")`:
   - **Tier-1 WeasyPrint** (local Windows có GTK3) — HTML/CSS chất lượng cao nhất
   - **Tier-2 xhtml2pdf** (Cloud Python 3.14) — pure Python, CSS cơ bản, tự strip `@top-right`/`string-set` không hỗ trợ
   - **Tier-3 ReportLab** — programmatic, text-only fallback nếu cả 2 tier trên fail
   - Gọi `build_report_pdf(...)` không cần truyền `engine` — auto chọn tier khả dụng đầu tiên
   - **Layout cao cấp A4 (cập nhật 2026-05-22)**: cover page (eyebrow + brand-bar navy+gold + serif title + meta key-value + footer strip) · TOC tự sinh (dot-leaders) · running header bottom-bordered (doc title trái / section title phải) · running footer (meta trái / "Trang X / Y" phải) · h1 chapter (page-break-before: always) · h2 với gold left-border · h3 với `▸` accent · tables zebra + `thead` lặp khi tách trang + tabular numerals · status pills `.badge.{pass,fail,warn,info}` · metric cards `metric_row(metric_card(...))` · callouts `.callout.{info,warning,success,danger}` · pull quote · signature block 3 cột (người lập / kiểm tra / phê duyệt) · auto-numbered figure/table caption qua CSS counter (Hình `<section>.<n>`, Bảng `<section>.<n>`)
   - Helpers mới: `figure(b64, caption)`, `badge(text, kind)`, `callout(body, kind, title)`, `pull_quote(text)`, `metric_row(*cards)`, `section_marker(title)`
   - `build_report_pdf()` thêm args: `eyebrow`, `toc`, `toc_items`, `signatures`, `doc_title_running`, `doc_meta_running`

2. **Biểu đồ tương tác trên web** → **Plotly** (drag/zoom/rotate/hover). KHÔNG dùng Matplotlib cho web charts trừ fallback.

3. **Biểu đồ kỹ thuật cố định** (sơ đồ CDM, mặt cắt, soil column) → **Matplotlib** (đơn giản, kiểm soát chính xác layout).

4. **Bảng** → **Pandas DataFrame** → render qua `st.dataframe()` trên web, `df.to_html()` trong PDF. KHÔNG xây bảng thủ công bằng list-of-lists.

5. **Công thức — BẮT BUỘC dùng LaTeX MathJax** (chuẩn render thống nhất toàn dự án):

   | Tình huống | Cú pháp | Ví dụ |
   |---|---|---|
   | Inline trong câu văn | `$...$` | `Hệ số $C_c = 0.45$` |
   | Display block (1 dòng) | `$$...$$` | `$$E_c = 75 \cdot C_c$$` |
   | Display block (Streamlit) | `st.latex(r"...")` | `st.latex(r"S = \frac{q H}{E}")` |
   | Có giá trị động | f-string + `st.latex(rf"...")` | `st.latex(rf"q = {q:.1f} \text{{ kPa}}")` |
   | Symbolic derivation | `sympy.latex(expr)` → embed `$$...$$` | `f"$${sp.latex(expr)}$$"` |
   | Trong WeasyPrint PDF | LaTeX → MathML qua `latex2mathml` | (tự động trong `pdf_report.py`) |

   **Quy ước ký hiệu**:
   - Subscript: `\sigma'_{vf}`, `H_{\text{soft}}`, `E_{\text{composite}}` (text mode khi nhiều chữ)
   - Phân số: `\frac{tử}{mẫu}` hoặc `\dfrac{}{}`(display lớn)
   - Tích phân/Σ: `\sum_{i=1}^{n}`, `\int_{0}^{H}`
   - Phẩy (effective stress): `\sigma'_v` (apostrophe sau ký tự)
   - Đơn vị: `\text{kPa}` (text mode trong math) — KHÔNG ghi đơn vị thô `kPa`
   - Tham chiếu: `\cdot` (nhân), `\leq`/`\geq` (≤/≥), `\Delta` (Δ)

   **Pitfalls cần tránh**:
   - **F-string + LaTeX brace conflict**: `\dfrac{X}{Y}` xung đột với f-string interpolation. Fix: tách `st.markdown(r"""...""")` cho LaTeX tĩnh + `st.markdown(f"...")` cho số.
   - KHÔNG dùng ASCII math (`Si = Hi × Cc/(1+e0) × log(σvf/σv0)`) — chỉ LaTeX.
   - KHÔNG render công thức bằng Matplotlib `usetex` (chậm + cần TeX runtime). Để LaTeX cho Streamlit/WeasyPrint xử lý.

6. **Pipeline báo cáo PDF chuẩn**: `pandas` (input) → `numpy + sympy` (calc) → `plotly + matplotlib` (figs, → PNG qua kaleido) → `pandas.to_html + CSS` (tables) → `Jinja2` template → `WeasyPrint` HTML→PDF.

**Yêu cầu Cloud**: `packages.txt` cài 7 apt libs cho WeasyPrint (libpango, libcairo, libharfbuzz, libgdk-pixbuf, libffi-dev, shared-mime-info).

**Yêu cầu local Windows**: WeasyPrint cần GTK3 runtime (https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer). Nếu thiếu → tự fallback `pdf_export.py` (reportlab).

