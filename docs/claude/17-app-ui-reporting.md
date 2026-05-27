### 17. Sidebar Navigation — Button-based Grouped Menu (cập nhật 2026-05-19)

Thay `st.sidebar.radio()` bằng `st.sidebar.button()` để hỗ trợ nhóm menu có header.

#### Cấu trúc menu

```
[Địa chất]            → "geology"
[Kiểm tra mẫu TN]    → "sample_check"
**TKCS CDM**
  [Thông số]          → "params"
  [So sánh PA]        → "compare"
  [Kết quả CDM]       → "compare"
  [Dự báo độ lún]     → "settlement"
  [Xuất kết quả]      → "export"
[TKBVT CDM]           → "cdm_bvt"   (placeholder)
**TKCS Cọc ván**
  [Cọc ván SW (Kè)]  → "ke_sw"
[TKBVT Cọc ván]       → "sw_bvt"    (placeholder)
```

#### Pattern code

```python
if "_page" not in st.session_state:
    st.session_state["_page"] = "geology"

def _nav(label: str, pid: str, indent: bool = False) -> None:
    if st.sidebar.button(
        ("    " if indent else "") + label,
        key=f"_nav_{pid}",
        use_container_width=True,
        type="primary" if st.session_state.get("_page") == pid else "secondary",
    ):
        st.session_state["_page"] = pid
        st.rerun()

_page = st.session_state.get("_page", "geology")
```

**Quy tắc:** Nút active = `type="primary"` (xanh), còn lại = `"secondary"`. Header nhóm dùng `st.sidebar.markdown("**TKCS CDM**")`. KHÔNG dùng `st.sidebar.radio()` — không hỗ trợ header giữa các item.

---

### 18. Tab "Xuất kết quả" — Word Export Header/Footer (cập nhật 2026-05-19)

**Vị trí:** `app_cdm.py`, `elif _page == "export":`, cột `c_word`

#### Input fields (session state)

| Key | Widget | Mô tả |
|-----|--------|-------|
| `export_co_name` | `st.text_input` | Tên công ty → header phải |
| `export_co_staff` | `st.text_input` | Nhân sự thực hiện → footer trái |
| `export_logo_bytes` | `st.session_state` (bytes) | Logo PNG/JPG → header trái (cao 1,2 cm) |

Logo được lưu vào `session_state["export_logo_bytes"]` khi `file_uploader` trả về file — giữ nguyên khi người dùng chuyển tab rồi quay lại.

#### Hàm `_export_word_bytes` — signature

```python
def _export_word_bytes(
    scenarios, params, rec_idx,
    co_name="", co_staff="", logo_bytes=None
) -> bytes:
```

#### Header/Footer pattern (python-docx)

```python
# Chèn PAGE / NUMPAGES field
def _field_run(para, field: str) -> None:
    run = para.add_run()
    fc_b = OxmlElement("w:fldChar"); fc_b.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.text = field
    instr.set(qn("xml:space"), "preserve")
    fc_e = OxmlElement("w:fldChar"); fc_e.set(qn("w:fldCharType"), "end")
    run._r.append(fc_b); run._r.append(instr); run._r.append(fc_e)

sec = doc.sections[0]
_pw = sec.page_width - sec.left_margin - sec.right_margin  # EMU

# Header 2 cột: logo trái | tên công ty phải
ht = sec.header.add_table(1, 2, width=_pw)
ht.cell(0, 0).width = Cm(3)
ht.cell(0, 1).width = _pw - Cm(3)
# logo: ht.cell(0,0).paragraphs[0].add_run().add_picture(io.BytesIO(logo_bytes), height=Cm(1.2))
ht.cell(0,1).paragraphs[0].alignment = RIGHT
H._fmt(ht.cell(0,1).paragraphs[0].add_run(co_name), size=9, bold=True)

# Footer 2 cột: nhân sự trái | Trang X/Y phải
ft = sec.footer.add_table(1, 2, width=_pw)
ft.cell(0, 0).width = _pw - Cm(3)
ft.cell(0, 1).width = Cm(3)
H._fmt(ft.cell(0,0).paragraphs[0].add_run(co_staff), size=9)
pg = ft.cell(0,1).paragraphs[0]; pg.alignment = RIGHT
H._fmt(pg.add_run("Trang "), size=9)
_field_run(pg, "PAGE")
H._fmt(pg.add_run(" / "), size=9)
_field_run(pg, "NUMPAGES")
```

**Xóa border bảng:** tạo hàm `_no_tbl_border(tbl)` dùng `OxmlElement("w:tblBorders")` với `w:val="none"` cho 6 cạnh.

**Chiều rộng usable width:** `sec.page_width - sec.left_margin - sec.right_margin` (EMU int) — dùng cho `width=` của cả 2 bảng header và footer.

---

### 18b. Quy tắc Báo cáo Word — Luôn Cập nhật, Đầy đủ, Tiếng Việt (cập nhật 2026-05-22)

**Nguyên tắc bắt buộc cho mọi báo cáo Word xuất từ app:**

#### Nội dung phải luôn mirror app

| Mục trong app | Phải có trong Word | Nguồn dữ liệu |
|---|---|---|
| Bảng thông số thiết kế per HK | Section 1 — bảng tổng hợp | SQLite `ke_sw_nt_detail` (KHÔNG từ JSON) |
| Cơ sở lý thuyết + công thức | Section 2 — formula images (matplotlib mathtext) | Hard-coded từ tiêu chuẩn |
| Tổng hợp NT1/NT2/Nội lực | Section 3 — bảng tổng hợp đầy đủ | SQLite `ke_sw_nt_detail` + kết quả Winkler |
| Biểu đồ nội lực per HK | Section 4 — 5 panel mỗi HK | Runtime compute |
| Ổn định tổng thể | Section 5 — bảng Fs + biểu đồ bar 3 phương pháp | SQLite ổn định |
| Kết luận & Kiến nghị | Section 6 | Auto-generate từ kết quả |

**Thiếu bất kỳ mục nào = lỗi cần sửa ngay.**

#### Header / Footer bắt buộc

- Header trái: logo công ty (`session_state["export_logo_bytes"]`) | Header phải: tên công ty
- Footer trái: nhân sự thực hiện | Footer phải: "Trang X / Y" (PAGE/NUMPAGES field)
- Hàm `_field_run7(para, "PAGE")` / `_field_run7(para, "NUMPAGES")` dùng OxmlElement

#### Tiếng Việt có dấu — BẮT BUỘC

- **MỌI** chuỗi hiển thị trong Word phải dùng tiếng Việt có dấu đầy đủ
- **CẤMS:** "Dat"/"Khong dat" → phải là "Đạt"/"Không đạt"
- **CẤMS:** "Ket qua:", "Ket luan", "Kien nghi", "On dinh" → phải có dấu
- **CẤMS:** `st.spinner(...)`, `st.success(...)`, `st.error(...)`, `st.download_button(...)` cũng phải tiếng Việt có dấu
- Tên cột bảng, nhãn trục biểu đồ (ylabel, title) — tất cả phải tiếng Việt có dấu
- `matplotlib` với font mặc định render OK tiếng Việt khi dùng Unicode literal; không cần thay đổi font

#### Checklist trước khi báo cáo Word "xong"

- [ ] Tất cả heading tiếng Việt có dấu
- [ ] Tất cả cell bảng: "Đạt"/"Không đạt" (không phải "Dat"/"Khong dat")
- [ ] Tất cả paragraph body text tiếng Việt
- [ ] Nhãn trục biểu đồ tiếng Việt
- [ ] Spinner/success/error/download button text tiếng Việt
- [ ] Header + footer đã setup (logo | company | page numbering)
- [ ] Section 1 đọc từ SQLite `ke_sw_nt_detail` (không từ JSON)

---

### 19. Quy tắc Định dạng Công thức trong File *.md

**File tham chiếu chuẩn:** [`41-cdm-choc-thung-dem-ximang.md`](41-cdm-choc-thung-dem-ximang.md)

#### Quy tắc bắt buộc

| Tình huống | Dùng | KHÔNG dùng |
|---|---|---|
| Công thức hiển thị (block) | `$$...$$` trên dòng riêng | Code block `` ``` `` hay inline `` ` `` |
| Ký hiệu / biến trong văn bản | `$...$` | Backtick `` `sigma_v0` `` hay ASCII |
| Mỗi phương trình | Một block `$$...$$` riêng | Gộp nhiều phương trình trong 1 block |
| Điều kiện trường hợp | Text label trước + `$$...$$` | Chú thích trong dòng code |

#### Cú pháp LaTeX chuẩn của dự án

- **Phân số:** `\frac{tử}{mẫu}` (inline: `\dfrac`)
- **Ký hiệu Hy Lạp:** `\alpha \beta \gamma \delta \sigma \tau \varphi \pi`
- **Nhân:** `\times` (giữa hai đại lượng) hoặc `\cdot` (tích vô hướng)
- **Hàm mũ:** `\exp\!\left(...\right)`
- **Log:** `\log_{10}`, `\ln`
- **Căn:** `\sqrt{}`
- **Chỉ số dưới/trên:** `_{...}` / `^{...}` — dùng `{}` khi hơn 1 ký tự
- **Tham chiếu tiêu chuẩn:** `\qquad \text{(C.1)}` hoặc `\qquad \text{(công thức 38)}`
- **Dấu phẩy thập phân trong LaTeX:** `1{,}5` (không dùng `1.5` cho số Việt)

#### Cấu trúc mỗi khối công thức

```markdown
**Tên trường hợp / điều kiện (nếu có):**

$$\text{công thức LaTeX}$$

Trong đó:
- $ký_hiệu$ — mô tả ngắn (đơn vị)
- ...
```

#### Bảng ký hiệu cuối section

Dùng bảng Markdown 3 cột: `$Ký hiệu$` | `Đơn vị` | `Mô tả`. Đặt sau nhóm công thức liên quan.

---

### 20. Quy ước Front / Back — Tường Cừ SW (BẮT BUỘC toàn dự án)

Áp dụng cho mọi script, JSON, biểu đồ, app liên quan đến tường cừ SW / sheet pile / tường chắn.

**Cừ SW là tâm sơ đồ.** Mặt đất + lớp đất hai bên thường khác nhau (Front có fill cao hơn, Back đào xuống thấp).

| Phía | Vị trí trên sơ đồ | Bản chất vật lý | Áp lực chính | Có fill ? | Màu chuẩn |
|---|---|---|---|---|---|
| **Front** | **TRÁI** | Đất đắp / mặt đường / xe chạy / người đi / tải trọng công trình | **Active (Ka)** — đẩy cừ về phía Back | **Có** (fill cao hơn cừ) | Tomato / `#1a8cff` |
| **Back** | **PHẢI** | Đào / sông / mặt nước hở | **Passive (Kp)** — chỉ phát triển dưới đáy đào, kháng lại chuyển vị cừ | Không | Green / `steelblue` |

**Quy tắc đặt tên biến trong code:**

| Biến / dataclass field | Ý nghĩa |
| --- | --- |
| `soil_level_front` | Cao độ mặt đất phía Front = cao độ chân đất đắp (THƯỜNG LÀ MẶT ĐẤT TỰ NHIÊN, cao) |
| `soil_level_back` | Cao độ mặt đất phía Back = cao độ đáy đào (THẤP HƠN front) |
| `water_elev_front` / `water_elev_back` | Mực nước 2 phía (có thể khác) |
| `front_layers` | Danh sách lớp đất tự nhiên phía Front (dưới `soil_level_front`) |
| `back_layers` | Danh sách lớp đất tự nhiên phía Back (dưới `soil_level_back`) |
| `fill` | Lớp đất đắp phía Front, nằm từ `soil_level_front` lên đến `top_elev` |
| `surcharge_front` | Tải mặt phân bố phía Front (kPa) — tải hoạt, xe, người |
| `sv_front`, `sigma_h_active` | Ứng suất đứng + áp lực ngang Active phía Front |
| `sv_back`, `sigma_h_passive` | Ứng suất đứng + áp lực ngang Passive phía Back |

**Áp lực NET tổng hợp (kN/m²) — chọn theo mô hình:**

| Mô hình | Công thức p_net | Ghi chú |
| --- | --- | --- |
| `mode='winkler'` (có lò xo nền) | `p_net = sigma_h_active + p_w_front − p_w_back` | Lò xo Winkler tự đảm nhiệm phản kháng bị động. KHÔNG được trừ `sigma_h_passive` ở đây — sẽ DOUBLE-COUNT. |
| `mode='free_earth'` (không lò xo, tính D ngàm) | `p_net = (sigma_h_active + p_w_front) − (sigma_h_passive + p_w_back)` | Cổ điển, cân bằng tĩnh ΣM=0 quanh điểm xoay. |

**Quy ước dấu:** Net dương → đẩy cừ từ Front sang Back (theo chiều tải trọng đất đắp + xe). Nội lực M dương khi sợi căng phía Front.

**File tham chiếu:**
- `scripts/wall_internal_force.py` — solver Winkler PyNiteFEA + tải phân bố
- `scripts/earth_pressure.py` — engine áp lực đất Active/Passive
- `scripts/water_pressure.py` — áp lực nước Hydrostatic/Seepage 2 phía
- Memory: `memory/feedback_front_back_convention.md`

---

### 21. CSS `@media print` cho Ctrl+P trình duyệt (BẮT BUỘC)

Khi user in PDF qua Ctrl+P trên 8503, các vấn đề thường gặp + cách fix.

| Vấn đề | Nguyên nhân | Fix CSS |
|---|---|---|
| Plotly chart trống ở giữa | Wildcard `* { position: static !important }` đè lên `position: absolute` của Plotly internals | **KHÔNG** override position toàn cục. Chỉ override cho `[data-testid="stSidebar/stHeader/stToolbar/stMainBlockContainer/stAppViewBlockContainer"]`, `.main`, `.block-container` |
| Plotly chart hiện 2-3 lần | Streamlit để `display:none` cho DOM stale; CSS ép `display:block` hiện tất cả | Bỏ ép display:block cho `.js-plotly-plot` / `.main-svg`. Rule ẩn duplicate: `.stPlotlyChart .js-plotly-plot ~ .js-plotly-plot { display: none }` |
| Công thức KaTeX lặp 2 lần (HTML + MathML) | `.katex-mathml` (screen reader) hiện ra khi `position: revert` | Ép ẩn cứng: `.katex-mathml { display:none; visibility:hidden; clip:rect(0,0,0,0); position:absolute }` |
| Dấu Việt + subscript trôi loạn | Wildcard `* { height: auto }` đè lên glyph stack KaTeX | Restore với `.katex *, .katex-html *, span.katex * { height: revert; position: revert; vertical-align: revert; line-height: revert }` |
| Bảng `st.dataframe` đè công thức `st.latex` phía dưới | Glide Data Grid canvas height cố định ~280px | Chuyển sang `st.table` cho bảng nhỏ; CSS fallback: `[data-testid="stDataFrame"] { min-height: fit-content; height: auto }` |
| Chart matplotlib pyplot tràn trang A4 | Không giới hạn chiều cao | `.stPyplot img, [data-testid="stPyplot"] img { max-height: 22cm; object-fit: contain }` |
| Hàng 2 cột (label+chart, label+chart) tách trang | label + pyplot là 2 element riêng | `[data-testid="stHorizontalBlock"] { break-inside: avoid }` (KHÔNG áp dụng cho `stColumn` / `stVerticalBlock` — quá rộng, gây gap lớn) |
| Heading + content kế tiếp tách trang | — | `[data-testid="stMarkdownContainer"] h1-h6, strong { break-after: avoid }` |

**JS handler `beforeprint`:** mở tất cả `<details>` + gọi `Plotly.Plots.resize()` cho mọi `.js-plotly-plot` → force redraw trước khi Chrome capture print preview + `scrollTo(0,0)`.

**File tham chiếu:** `scripts/app_cdm.py` block CSS `@media print` (line ~3335) + JS `beforeprint` (line ~3436). Memory: `feedback_browser_print_css.md`.

**Quy tắc khi áp dụng:**

1. **Bảng nhỏ ≤20 dòng, là reference/lookup** → dùng `st.table(df)` thay `st.dataframe`. Đặc biệt khi sau bảng có `st.latex` hoặc nội dung khác.
2. **Bảng có `column_config` (format số), `style.map` (color highlight), cần scroll** → giữ `st.dataframe`, dựa vào CSS fallback.
3. **Công thức tổng quát (chung mọi HK)** → KHÔNG đặt trong vòng lặp HK; tách ra **1 expander chung** trước vòng lặp, đặt suffix `"(chung cho mọi HK)"`. Mỗi HK chỉ render kết quả riêng.
4. **PDF qua nút app** → user yêu cầu ẩn (Streamlit canvas + Plotly iframe không reliable cho server-side render). Gate bằng `_HAS_PDF = False`. User dùng Ctrl+P browser + Word export.

---

### 22. Trắc dọc địa chất + Bình đồ HK ở Mục B (Cọc ván SW)

Hai khung view nhúng ngay sau bảng `data_editor` của Mục B, trước biểu đồ NT2 ratio.

**Trục X chainage qua PCA SVD:** chiếu `(x_coord_m, y_coord_m)` HK lên trục chính của tập điểm → tuyến đi qua tất cả HK theo đúng thứ tự dọc.

**Inputs (3 cột):** Cao độ đỉnh kè TK · Cao độ mặt nước · Lớp dưới muốn vẽ (selectbox từ symbol ≠ '1').

**Đường vẽ Plotly (chính):**
- Mặt đất tự nhiên (nâu, marker tròn)
- Lớp 1 bùn — fill `_LAYER_COLORS['1']` + line đáy
- Lớp dưới user chọn — fill + line đỉnh/đáy (▲▼)
- Đáy lớp đất yếu — đường hồng đứt + ◆ — từ `ke_sw_nt_detail.D_bottom_soft_m`
- **Mũi cọc TK** — cam, ▼, có **đường nối liền** giữa các điểm
- Đỉnh kè TK + mặt nước (hlines)

**Hover (per layer per HK):** symbol, độ sâu, cao độ, su VST/Lab, N̄-SPT — query 1 lần từ SQLite `vane_shear_tests` + `lab_tests` + `spt_values`.

**Matplotlib double-render:** lưu vào `st.session_state["_ke_b_profile_mpl_fig"]` + expander thu gọn "Bản Matplotlib (dùng cho PDF)". Tương tự cho bình đồ.

**Bình đồ vị trí:** Plotly scatter X=Northing, Y=Easting, **tỷ lệ trục 1:1** (`scaleratio=1`); annotation khoảng cách Euclidean giữa các cặp HK liên tiếp; bảng `st.table` khoảng cách + tổng chiều dài.

**Live link:** đổi multiselect HK / cọc / L thiết kế trong bảng data_editor → trắc dọc + bình đồ tự cập nhật.

**Helper bắt buộc:**
```python
def _hex_to_rgba(hex_str: str, alpha: float) -> str:
    # Plotly 6.x KHÔNG chấp nhận hex 8 ký tự #RRGGBBAA
    # → phải convert sang rgba(R,G,B,alpha)
```

**File tham chiếu:** `scripts/app_cdm.py` ~line 8160-8800. Memory: `project_tracdoc_binhdo_mucB.md`.

---

### 23. Ẩn tên kỹ thuật trên UI (BẮT BUỘC)

Mọi text hiển thị trên 8503 (`st.markdown`, `st.caption`, `st.info`, `st.warning`, `st.error`, `help=`, expander label) KHÔNG được chứa:

- Tên thư viện: `SQLite`, `matplotlib`, `plotly`, `numpy`, `pandas`, `reportlab`, `weasyprint`, `streamlit`...
- Đuôi file: `.py`, `.md`, `.json`, `.sqlite`, `.xlsx`, `.xls`, `.csv`, `.dxf`, `.dwg`
- Tên bảng SQL: `lab_tests`, `vane_shear_tests`, `ke_sw_nt_detail`, `boreholes`, `layers`, `spt_values`, `ke_sw_winkler_results`, `ke_sw_stability`...
- Tên hàm/biến code: `_db()`, `_load_layers()`, `_HAS_PDF`...
- Tiếng Anh thuần không cần thiết: `Auto` → `Tự chọn`, `tip method` → `Phương pháp mũi`

**Thay thế chuẩn (đã đúc kết 2026-05-22):**

| Trước | Sau |
|---|---|
| "Kết quả lưu SQLite" | "Kết quả được lưu" |
| "lưu vào bảng scenario SQLite riêng" | "lưu vào kịch bản riêng" |
| "thí nghiệm UU trong SQLite" | "thí nghiệm cắt cánh hiện trường (VST) hoặc UU phòng" |
| "nguồn: SQLite" | "nguồn: thí nghiệm" |
| "Đáy bùn (NT detail)" | "Đáy lớp đất yếu (tính NT1)" |
| `Auto` (phương pháp NT2) | "Tự chọn" |
| `tip method` (cột bảng) | "Phương pháp mũi" |
| "Không đọc được `ke_sw_winkler_results`" | "Không đọc được kết quả Winkler đã lưu" |
| "Lỗi đọc `ke_sw_stability`" | "Lỗi đọc kết quả ổn định tổng thể" |
| "Kiểm tra `scripts/winkler_np.py`" | "Liên hệ kỹ sư phát triển để kiểm tra môi trường" |

**Vẫn được phép:**

- Tên file user **download** (vd `BaoCao_CDM_HK2_20260522.xlsx`) — đó là tên thật của file output
- Comments trong code (`# ...`) — không hiển thị UI
- Tên hố khoan có prefix zone (`KE-HK6`, `BXN-HK1`, `NHC-BH-03`) — quy ước dự án
- Tên cọc theo catalog (`SW-840`, `SW-940`) — danh pháp kỹ thuật
- Ký hiệu tiêu chuẩn (`TCVN 4253`, `USACE EM 1110-2-2504`, `FHWA GEC-13`)

**Memory tham chiếu:** `memory/feedback_no_tech_names_in_ui.md`.

---

### 24. Thư viện mới cho Word OMML + Typography (cập nhật 2026-05-22)

Cài đặt qua `pip install`:

| Lib | Phiên bản min | Vai trò |
|---|---|---|
| `latex2mathml` | ≥ 3.81 | LaTeX → MathML XML (W3C, bảo toàn dấu Việt) |
| `math2docx` | ≥ 3.1 | LaTeX → MathML → OMML embed vào `python-docx` paragraph |
| `docxtpl` | ≥ 0.20 | Word template Jinja2 — tách logic Python ↔ thiết kế Word (header/footer/watermark phức tạp) |
| `pylatex` | ≥ 1.4 | Mô phỏng object TeX trong Python — dành cho PDF academic chuẩn LaTeX |
| `typst` | ≥ 0.14 | Python binding cho Typst (Rust compiler) — typography next-gen, response <100ms |

**Đã thêm vào** `requirements.txt` + `cdm-deploy/requirements.txt`.

**Cách dùng `math2docx` cho công thức editable trong Word:**

```python
from docx import Document
from math2docx import add_math

doc = Document()
p = doc.add_paragraph("Công thức kiểm tra NT1: ")
add_math(p, r"L_{\text{thiết kế}} \geq L_{\text{yêu cầu}} = (Z_{\text{đỉnh kè}} - Z) + H_{\text{lớp yếu}} + h_{\text{ngàm}}")
doc.save("baocao.docx")
```

Lợi ích so với mathtext PNG cũ:
- Công thức **editable** trong Word (chỉnh được)
- Render đẹp ở mọi zoom (vector OMML, không vỡ)
- File Word nhẹ hơn (không cần PNG mỗi công thức)

**Lưu ý cài Quarto:** `pip install quarto-cli` thất bại trên Windows do MAX_PATH limit (260 ký tự). Phải dùng `winget install Posit.Quarto` hoặc installer từ https://quarto.org. Chưa cần Quarto trong production hiện tại.

---

### 25. Ẩn nút Xuất PDF qua app — user dùng Ctrl+P + Word

User yêu cầu (2026-05-22): bỏ TẤT CẢ nút "Xuất PDF" qua engine server-side. Chỉ giữ:
- Các nút **Xuất Word** (Word export pipeline vẫn dùng)
- **Ctrl+P** trình duyệt → in PDF qua print preview (CSS @media print đã optimize — xem mục 21)

**Cách ẩn:**

```python
# Ép disable PDF engine — gate tất cả nút `if _HAS_PDF:`
_HAS_PDF = False
_PDF_ENGINE = "—"
```

Sau dòng này, các nút sau KHÔNG render (tự động):
- "Xuất PDF Tổng hợp (tất cả tab)" — sidebar
- "Xuất PDF tab Thông số CDM"
- "Xuất PDF tab Dự báo lún"
- "Xuất PDF tab Cọc ván SW"
- "Tải PDF bảng so sánh + biểu đồ"

**Section "Báo cáo PDF tuỳ chỉnh"** trong tab Thông số CDM (checkboxes + 2 nút) **KHÔNG gated** → đã xoá hẳn block ~80 dòng (vì có nội dung `_custom_report_pdf` không phụ thuộc `_HAS_PDF`).

**Sidebar PDF section** (`st.sidebar.markdown("### Xuất PDF")` + caption) **KHÔNG gated** → đã xoá toàn bộ block.

**Khôi phục:** chỉ cần đổi `_HAS_PDF = True`. Các nút trong `if _HAS_PDF:` sẽ tự render lại. Block "Báo cáo PDF tuỳ chỉnh" + sidebar PDF phải khôi phục từ git history.

**Memory:** `feedback_hide_pdf_buttons.md`.

---

