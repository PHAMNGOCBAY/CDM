### 64. Feedback Rules Published — Quy tắc làm việc với dự án (publish từ private memory)

**Mục đích:** Mirror 7 quy tắc memory (`C:\Users\...\.claude\projects\...\memory\`) vào project files để version control + team có thể truy cập.

**Nguyên tắc:** Khi tạo/sửa feedback memory, BẮT BUỘC cập nhật song song file này.

---

#### Rule 1 — Không dùng emoji

**Phạm vi:** Câu trả lời Claude, UI Streamlit, biểu đồ matplotlib/plotly, label/tooltip, nút, comment code.

**Why:** Báo cáo kỹ thuật chuyên ngành; emoji không phù hợp + gây rối in ấn.

**How:** Thay ✅/❌ bằng "Đạt"/"Không đạt" + màu (#2E7D32/#C62828); thay 🟢🔴🟡 bằng badge chữ; thay ⚙🏗 bằng bỏ hẳn.

Source: `memory/feedback-no-emoji.md`

---

#### Rule 2 — Luôn cập nhật `*.md` khi đổi công thức

**Phạm vi:** Sửa công thức / phương pháp / hệ số / quy trình → BẮT BUỘC cập nhật NGAY mọi file `*.md` liên quan.

**Why:** Tài liệu là nguồn tra cứu (§6b ưu tiên MD trước PDF). MD lỗi thời → tra cứu sai → tính sai.

**How:** Grep nội dung cũ trong các `*.md`, cập nhật khớp code. Nếu công thức xuất hiện ở nhiều MD → sửa TẤT CẢ, không sót.

Source: `memory/feedback-always-update-md.md`

---

#### Rule 3 — Luôn hiển thị giá trị trên biểu đồ

**Phạm vi:** Plotly, Matplotlib, PDF, Word — mọi biểu đồ.

**Why:** Báo cáo in (Ctrl+P, PDF, Word) — tooltip Plotly mất tác dụng. Phải đọc giá trị tức thời ngay trên điểm dữ liệu.

**How:**
- Plotly: `mode="lines+markers+text"` + `text=[f"{y:.1f}" for y in ys]` + `textposition="top center"`
- Matplotlib: `ax.annotate(f"{v:.1f}", xy=(x,y), xytext=(0,5), textcoords="offset points", ha="center")`
- Ngưỡng/giới hạn: kèm annotation value cụ thể.
- Font label 9-11pt, viền/padding nếu chồng đường.

Source: `memory/feedback-show-values-on-charts.md`

---

#### Rule 4 — Tiêu đề bảng in đậm

**Phạm vi:** Streamlit (`st.dataframe`/`st.table`), HTML, Word (python-docx), PDF (WeasyPrint/ReportLab).

**Why:** Phân biệt rõ header với dữ liệu — chuẩn typography báo cáo kỹ thuật.

**How:**
- Streamlit: mặc định đã bold; ép `[data-testid="stTable"] th {font-weight:700}` + nền `#e8eef5`
- HTML: `th { font-weight: bold; }`
- Word: `run.bold = True` cho header cells
- ReportLab: `TableStyle([('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')])`

**Lưới kẻ bảng đậm như Word (hiện rõ khi in):** CSS toàn cục trong `app_cdm.py` —
`[data-testid="stTable"] table {border-collapse:collapse}`, `th {border:1.2px solid #333}`,
`td {border:1px solid #444}`, kèm `@media print {border:1px solid #000; print-color-adjust:exact}`.

Source: `memory/feedback-bold-table-headers.md`

---

#### Rule 5 — Typography báo cáo (body 12pt + zebra)

**Phạm vi:** Word export, PDF, Streamlit khi Ctrl+P.

**Why:** Chuẩn TCVN/quốc tế cho báo cáo kỹ thuật Việt Nam.

**How:**
- Body 12pt, line-height 1.45
- Heading H1=18pt, H2=15pt, H3=13pt, caption 10pt
- Bảng zebra `#f3f4f6` dòng chẵn khi ≥ 5 hàng
- Word: `doc.styles["Normal"].font.size = Pt(12)` + `_shade_cell()` zebra

Source: `memory/feedback-report-typography.md`

---

#### Rule 6 — Bảng UI ↔ Word docx parity (single source)

**Phạm vi:** Bất kỳ bảng nào trong UI Streamlit hiển thị + xuất Word.

**Why:** Tránh "UI thấy đẹp, Word khác hẳn". Người đọc Word nghi ngờ độ chính xác.

**How:**
- Constants chung: `scripts/core/report_style.py` (HEADER_BG, ROW_EVEN_BG, BODY_FONT_PT=12, etc.)
- Helper UI: `html_css_block()` + `df_to_report_html()`
- Helper Word: `style_tbl_for_docx(tbl, preserve_existing=True)`
- Sửa style 1 chỗ → cả UI và Word tự đổi

Source: `memory/feedback-table-style-ui-docx-parity.md`

---

#### Rule 7 — S₂ phân nhánh sét/cát (BẮT BUỘC mô tả đầy đủ)

**Phạm vi:** Mọi tài liệu/code/biểu đồ về công thức S₂.

**Why:** Engine `calc_s2_below_cdm` phân biệt sét vs cát theo `SAND_SYMBOLS_S2`. Mô tả chỉ-Terzaghi gây hiểu nhầm.

**How:**

| Loại lớp | Công thức |
|---|---|
| Sét (NOT IN SAND_SYMBOLS_S2) | $S_i = \dfrac{h_i C_c}{1+e_0} \log_{10}\dfrac{\sigma'_{vf}}{\sigma'_{v0}}$ — OC/NC/cross-PC<br>Fallback: $E_{oed} = \dfrac{1+e_0}{a_{1-2}} \times 98{,}0665$ |
| Cát (IN SAND_SYMBOLS_S2) | $S_i = \dfrac{\Delta\sigma \cdot h_i}{E_s}$ với $E_s = \alpha_{sand} \cdot N_{SPT}$, $\alpha = 2000$ kPa |

`SAND_SYMBOLS_S2 = {F, 2a, 2b, 2c, 3a, 3b, 3c, 4, 5, 5a, 5b, 6, 7, 8}`

Tiêu chí dừng: $\Delta\sigma / \sigma'_{v0} < 10\%$ (bước 2m phân tố).

Source: `memory/feedback-s2-branches-clay-sand.md`

---

#### Rule 8 — LUÔN lưu kết quả tính toán vào SQLite

**Phạm vi:** Mọi engine compute kỹ thuật (Lc tối ưu, smoothness, S(p) curves, grid Lc, lún cố kết, sức chịu tải, ổn định...).

**Why:** Compute tốn thời gian (~30s cho grid 162 điểm). Mỗi reload UI / truy vấn team khác cần dữ liệu nhanh → query SQL <1s tốt hơn re-compute. Persist results = audit trail qua `updated_at` + team query không cần chạy Python.

**How:**

1. **Mỗi engine** `scripts/compute_xxx.py` phải có `scripts/save_xxx_results.py` tương ứng
2. **`create_table()` idempotent** — `CREATE TABLE IF NOT EXISTS` với PRIMARY KEY logic
3. **`INSERT OR REPLACE`** — re-run không tạo duplicate
4. **Tên bảng**: tiền tố module + đủ context (vd `cdm_zone_design_results`, `ke_sw_winkler_results`)
5. **PRIMARY KEY**: đủ chi tiết để identify unique row (vd `(zone_code, bh_name, delta_S_cm)`)
6. **Cột bắt buộc**: `updated_at TEXT DEFAULT CURRENT_TIMESTAMP` + `ok INTEGER (0/1)` nếu có pass/fail
7. **Lưu CẢ LOCAL + PROJECT DB**: `C:\Users\bayng\TTHC_local\TTHC.sqlite` (dev) + `data/TTHC.sqlite` (project/git)

**Khi nào KHÔNG cần save:**
- Compute siêu nhẹ <1s phụ thuộc input dynamic user (vd zoom Plotly)
- Bảng tham chiếu tra cứu chuẩn đã có (vd Bảng E.1 đã có trong SQLite)

**Checklist:**
- [ ] Hàm `compute_xxx()` engine
- [ ] File `scripts/save_xxx_results.py`
- [ ] `create_table()` idempotent
- [ ] PRIMARY KEY + `INSERT OR REPLACE`
- [ ] Cột `updated_at`
- [ ] Run thành công + verify rows trong DB
- [ ] Lưu CẢ LOCAL + PROJECT DB
- [ ] Document schema trong MD §N + JSON config

**Bảng đã có (2108 rows):**

| Bảng | Rows | Module |
|---|:---:|---|
| `cdm_zone_design_results` | 128 | qtt_cdm_analysis |
| `cdm_zone_smoothness_results` | 257 | qtt_cdm_analysis |
| `cdm_zone_s_lc_curves` | 1075 | qtt_cdm_analysis |
| `cdm_qtt_grid_lc` | 648 | qtt_cdm_analysis |
| `ke_sw_winkler_results` | (theo HK) | wall_internal_force |
| `ke_sw_stability` | (theo HK) | sw_global_stability |
| `ke_sw_nt_detail` | (theo HK) | ke_sw_nt_calc |
| `cdm_design` | 3 | cdm_column_calc |
| `tvtk_bh_cdm` | 60 | tvtk_cdm_s1_calc |

Source: `memory/feedback-persist-results-sqlite.md`

---

#### Rule 9 — KHÔNG bịa, KHÔNG suy diễn

**Phạm vi:** Mọi câu trả lời có trích dẫn tiêu chuẩn (TCVN, TCCS, ISO, BS, EN, JGS, PWRI...), tham số kỹ thuật (Fs, q_u, ngưỡng...), quy định bắt buộc.

**Why:** Dự án kỹ thuật yêu cầu chính xác cao. Bịa "TCVN X yêu cầu ≥ Y" mà không thực sự có trong tiêu chuẩn → thiết kế sai → mất an toàn / phải làm lại. User đã chỉ ra lỗi cụ thể (2026-05-29): "TCVN 9403 yêu cầu Hse ≥ 30 cm" — KHÔNG có trong tiêu chuẩn này.

**How:**

1. **CHỈ trích tiêu chuẩn** khi đã đọc file gốc PDF hoặc file tóm tắt dự án `docs/claude/NN-*.md`
2. **Verify trước khi trả lời** — grep dự án, đọc file nếu cần
3. **Ghi rõ "không chắc / cần verify"** khi không tìm thấy nguồn
4. **Tham số phải có nguồn** (thí nghiệm / tiêu chuẩn / mục cụ thể) — nếu không → ghi "giả định"
5. **Khi user hỏi "có chắc không?"** → kiểm tra lại NGAY, thừa nhận sai nếu sai

**CẤM:**

- "TCVN/TCCS yêu cầu ..." mà không trích mục
- "Thường thấy / Phổ biến" như thể là quy định
- "Mặc định = X" mà không có cơ sở

**Mẫu câu chuẩn khi không chắc:**

- "Mình nhớ là X nhưng không chắc — để verify trong file dự án"
- "Đây là kinh nghiệm thông thường, KHÔNG phải bắt buộc theo tiêu chuẩn cụ thể"
- "Cần đối chiếu PDF gốc — dự án không có file này"

Source: `memory/feedback-no-fabrication.md`

---

#### Rule 10 — Luôn lưu CẢ skill (docs) lẫn memory

**Phạm vi:** Mỗi khi user thiết lập quy tắc / convention / feedback mới — dù ngắn hạn hay dài hạn.

**Why:** Lưu một nơi → mất kết nối:
- Chỉ memory → team không thấy, không version control, mất khi đổi máy
- Chỉ docs → phiên Claude mới không tự nhớ, quên áp dụng cho đến khi grep
- Cả hai → vừa được áp dụng tự động (memory) vừa version-controlled + sharable (docs)

**How:**

1. Tạo `memory/feedback-<slug>.md` với frontmatter (`name`, `description`, `metadata.type: feedback`) + body có **Why:** + **How to apply:**
2. Thêm 1 dòng vào `memory/MEMORY.md` index
3. Cập nhật `docs/claude/NN-*.md` (chọn file phù hợp module / quy trình) hoặc CLAUDE.md hoặc `NN-*.md` ở root
4. Nếu tạo file MD mới trong `docs/claude/` → thêm `@docs/claude/NN-*.md` vào CLAUDE.md để Claude tự load mỗi phiên
5. Mirror vào §64 này nếu là rule chung toàn dự án

**Khi nào áp:** user nói "thêm quy tắc X", "luôn làm Y", "cấm Z", "feedback: …", "ghi nhớ rằng …" → tạo CẢ HAI ngay trong cùng turn, KHÔNG đợi user yêu cầu lần nữa.

**Checklist:**

- [ ] `memory/feedback-*.md` đã tạo
- [ ] `MEMORY.md` có entry mới
- [ ] Docs file (`docs/claude/*.md` / CLAUDE.md / root MD) đã cập nhật
- [ ] File MD mới → đã `@import` vào CLAUDE.md
- [ ] §64 mirror nếu rule chung

Source: `memory/feedback-always-save-skill-memory.md`

---

#### Rule 11 — Persist todos vào trí nhớ dài hạn

**Phạm vi:** Mỗi lần gọi `TodoWrite` để tạo/cập nhật danh sách task.

**Why:** `TodoWrite` chỉ giữ todo in-memory trong session conversation hiện tại. Đóng phiên → mất hết. User muốn tracking lâu dài (vài ngày sau quay lại vẫn thấy + tick tiếp).

**How:**

1. Mỗi lần `TodoWrite` → ngay sau đó tạo/cập nhật `docs/claude/NN-<module>-roadmap.md`
2. File CHƯA TỒN TẠI → tạo mới với header + section "Lịch sử cập nhật"
3. File ĐÃ TỒN TẠI → append task mới vào cuối + entry trong bảng lịch sử
4. Mark task `completed` → tick `[x]` + commit hash + ngày
5. Lần đầu tạo file roadmap → thêm `@docs/claude/NN-*.md` vào CLAUDE.md để Claude phiên sau auto-load
6. **Roadmap KHÔNG được xóa** — chỉ append (strikethrough nếu bỏ task)

**Format task chuẩn:**

```markdown
#### Task N — <tiêu đề ngắn>

- [ ] **Status:** pending | in_progress | completed
- **Mục tiêu:** ...
- **Files đụng:** [path](path)
- **DB tác động:** bảng SQLite nào
- **Verify:** cách kiểm tra hoàn thành
```

**Khi nào áp:** user nói "lưu todo", "ghi nhớ task này lâu dài", "persistent", "đừng để mất task" → tạo CẢ TodoWrite (session) lẫn MD roadmap (long-term) trong cùng turn, KHÔNG đợi user nhắc lại.

**Checklist:**

- [ ] TodoWrite đã tạo với danh sách task
- [ ] File `docs/claude/NN-*-roadmap.md` đã tạo/append
- [ ] CLAUDE.md đã có `@import` cho file roadmap (nếu mới)
- [ ] Bảng "Lịch sử cập nhật" có entry mới

Source: `memory/feedback-persist-todos-longterm.md`

---

#### Rule 12 — Self-audit sau mỗi task hoàn thành

**Phạm vi:** Mọi multi-task session (TodoWrite có ≥ 2 task).

**Why:** Khi user nói "Bắt đầu task 1 → 8", kỳ vọng Claude làm hết. Dừng giữa chừng = phải lặp lại "tiếp tục" nhiều lần → trải nghiệm gãy.

**How:**

1. Mark task X `completed` → ngay sau đó:
2. Đọc lại file audit MD phiên (vd `docs/session-audit-YYYY-MM-DD.md`)
3. Đối chiếu với TodoWrite + roadmap §72
4. Identify task pending kế tiếp (Wave 1 → 2 → 3)
5. Mark task đó `in_progress` + **bắt đầu làm NGAY**, KHÔNG hỏi user "tiếp không"
6. Cập nhật audit MD: tick task vừa xong + log task kế đang start

**Quy tắc dừng (chỉ 3 trường hợp):**

- Lỗi không tự fix được sau 2 lần thử
- Cần quyết định kiến trúc lớn từ user
- User explicitly nói "dừng" / "stop" / "xong"

Source: `memory/feedback-self-audit-after-task.md`

---

#### Rule 13 — Lún phân nhánh theo loại đất + hệ số rỗng e₀

**Phạm vi:** mọi engine/tài liệu tính lún (nền chưa xử lý, S2 dưới mũi, LK2...).

**Why:** lớp đất chặt (e₀<1) gần đàn hồi — dùng e-logp (Cc) sẽ sai; chỉ sét yếu mới cố kết chậm.

**How:**

| Loại lớp | Điều kiện | Công thức |
|---|---|---|
| Cát (hạt rời) | không e₀/Cc | đàn hồi Si=Δσ·h/Es (Es=α·N, α=2000) |
| Sét yếu | e₀ ≥ 1, có Cc | Terzaghi 1D e-logp (OC/NC/cross-PC) |
| Sét chặt | e₀ < 1 | Eoed: Si=Δσ·h/Eoed, Eoed=(1+e₀)/a₁₋₂×98,0665 |

**Lún cố kết theo thời gian CHỈ ở lớp sét e₀>1**; cát + sét chặt lún tức thời → S(t)=S_tức thời+U(t)·S_cố kết < S∞. Tiêu chí phân loại là e₀ (không chỉ ký hiệu SAND). Source: `memory/feedback-settlement-eo-branches.md`; doc §74 + 75-*.md.

---

#### Rule 14 — Biểu đồ: nhãn giá trị + cỡ chữ 12pt (cả legend)

**Phạm vi:** mọi biểu đồ Plotly/Matplotlib trên UI + báo cáo.

**Why:** báo cáo in mất hover; legend nhỏ hơn gây mất cân đối.

**How:** `font=dict(size=16)` + `legend=dict(font=dict(size=16))` + `textfont=dict(size=16)`; nhãn giá trị trực tiếp trên điểm/cột (hiện thưa nếu chồng). Bảng dài → `st.table` (hiện hết, không cuộn), CSS font 12pt. Source: `memory/feedback-chart-12pt-labels.md` (mở rộng Rule 3 + Rule 5).

---

#### Rule 15 — Font body UI = Calibri

**Phạm vi:** toàn UI Streamlit (`app_cdm.py`).

**Why:** thống nhất với báo cáo Word/Office.

**How:** chèn CSS toàn cục sau `st.set_page_config`: `font-family: Calibri, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important` cho vùng chính/sidebar/markdown/h1–h6/label/bảng/metric/nút/input; **giữ nguyên** (`revert`) `.katex` + icon Material. Cloud/Linux tự fallback. Plotly cần `font=dict(family="Calibri")` riêng nếu muốn đồng bộ. Source: `memory/feedback-ui-font-calibri.md`.

---

### Checklist tổng hợp khi viết tài liệu/code mới

- [ ] Không có emoji
- [ ] `*.md` liên quan đã được cập nhật
- [ ] Biểu đồ có label giá trị số trực tiếp
- [ ] Bảng có header bold
- [ ] Body 12pt + bảng zebra ≥ 5 hàng
- [ ] Bảng UI = Word (qua `report_style.py`)
- [ ] Công thức S₂ mô tả ĐẦY ĐỦ 2 nhánh sét/cát
- [ ] Kết quả compute lưu vào SQLite (LOCAL + PROJECT) qua hàm `save_*_results.py`
- [ ] Trích tiêu chuẩn có nguồn rõ ràng (mục cụ thể, đã đọc file dự án); ghi "giả định" / "cần verify" khi không chắc
- [ ] **Quy tắc mới đã lưu CẢ memory lẫn docs/claude** (rule 10)
- [ ] **Todos đã persist vào docs/claude/NN-*-roadmap.md** (rule 11)
- [ ] **Sau mỗi task xong: self-audit + tự bắt đầu task pending kế tiếp** (rule 12)

### Tham chiếu

Memory files private (per user):
`C:\Users\<USER>\.claude\projects\g--My-Drive-AI-SUC-TAI-COC-THEO-DAT-NEN\memory\`

12 file feedback + MEMORY.md index. Mọi sửa đổi memory → cập nhật file §64 này.
