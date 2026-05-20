"""
word_html_export.py — Tạo file Word từ HTML template (Microsoft Word Open-XML compatible)

Approach: Word có thể MỞ TRỰC TIẾP file HTML chứa Mso namespaces. Không cần
python-docx. Hoạt động trên mọi môi trường có jinja2 (built-in Streamlit).

Output: bytes của file .doc (HTML format) — user mở bằng Word, lưu lại thành .docx.

Pipeline:
1. Pandas DataFrame → HTML table
2. Jinja2 render template với data
3. Word đọc HTML qua MIME type application/msword
"""
from __future__ import annotations
import io
import math
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Template

# ── Template HTML — Word-compatible ──────────────────────────────────────────
_WORD_TEMPLATE = Template(r"""<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office"
      xmlns:w="urn:schemas-microsoft-com:office:word"
      xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta name="ProgId" content="Word.Document">
<meta name="Generator" content="Microsoft Word 15">
<meta name="Originator" content="Microsoft Word 15">
<title>{{ title }}</title>
<!--[if gte mso 9]>
<xml>
<w:WordDocument>
  <w:View>Print</w:View>
  <w:Zoom>100</w:Zoom>
  <w:DoNotOptimizeForBrowser/>
</w:WordDocument>
</xml>
<![endif]-->
<style>
@page {
  size: A4 portrait;
  margin: 2.5cm 2cm 2.5cm 2.5cm;
  mso-header-margin: 1cm;
  mso-footer-margin: 1cm;
  mso-paper-source: 0;
}
body {
  font-family: "Times New Roman", serif;
  font-size: 12pt;
  line-height: 1.4;
  color: #1A1A1A;
}
h1.cover { font-size: 18pt; text-align: center; margin: 4cm 0 0.5cm 0; }
h1.cover .sub { font-size: 14pt; font-weight: normal; display: block; margin-top: 0.3cm; }
h1 { font-size: 14pt; color: #1F4E79; margin-top: 16pt; margin-bottom: 6pt; }
h2 { font-size: 12pt; color: #1F4E79; margin-top: 12pt; margin-bottom: 4pt; }
h3 { font-size: 11.5pt; color: #444; margin-top: 8pt; margin-bottom: 3pt; }
p  { margin: 4pt 0; text-align: justify; }
ul { margin: 4pt 0; padding-left: 1cm; }
li { margin: 2pt 0; }
table {
  border-collapse: collapse;
  width: 100%;
  margin: 6pt 0;
  font-size: 10.5pt;
}
table th {
  background-color: #1F4E79;
  color: white;
  padding: 5px 8px;
  border: 1px solid #888;
  text-align: center;
  font-weight: 600;
}
table td {
  padding: 4px 8px;
  border: 1px solid #BBB;
  vertical-align: middle;
}
table tr:nth-child(even) td { background-color: #F5F8FB; }
table tr.pass td { background-color: #E8F5E9; }
table tr.fail td { background-color: #FFEBEE; }
.formula {
  font-family: "Cambria Math", "Times New Roman", serif;
  font-style: italic;
  text-align: center;
  margin: 6pt 0;
  font-size: 11pt;
}
.caption {
  font-style: italic;
  font-size: 10pt;
  text-align: center;
  color: #555;
  margin: 2pt 0 8pt 0;
}
.toc { margin: 0.5cm 0 1cm 0; }
.note { background: #FFF8E1; padding: 6pt; border-left: 3px solid #F9A825; margin: 6pt 0; }
.center { text-align: center; }
.page-break { page-break-before: always; mso-special-character: line-break; }
</style>
</head>
<body>

<!-- COVER PAGE -->
<h1 class="cover">
  THUYẾT MINH TÍNH TOÁN<br>
  GIA CỐ NỀN ĐẤT YẾU BẰNG CỌC ĐẤT XI MĂNG (CDM)
  <span class="sub">D = {{ '%.0f' | format(D*1000) }} mm  ·  Lc = {{ '%.1f' | format(Lc) }} m  ·  qu = {{ '%.0f' | format(qu) }} kPa</span>
  <span class="sub" style="font-size:11pt; margin-top:3cm;">Khu vực: {{ zone }}  ·  Hố khoan: {{ bh_name }}</span>
  <span class="sub" style="font-size:11pt; margin-top:5cm; font-style:italic;">
    TP. Hồ Chí Minh, {{ today }}
  </span>
</h1>

<div class="page-break"></div>

<!-- I. CƠ SỞ PHÁP LÝ -->
<h1>I. CƠ SỞ PHÁP LÝ VÀ TIÊU CHUẨN ÁP DỤNG</h1>
<ul>
  <li>TCVN 9403:2012 — Gia cố nền đất yếu — Phương pháp trụ đất xi măng.</li>
  <li>TCVN 4200:2012 — Đất xây dựng — Phương pháp xác định tính nén lún.</li>
  <li>TCVN 8868:2011 — Thí nghiệm xác định sức kháng cắt không cố kết, không thoát nước.</li>
  <li>TCCS 41:2022 — Nền đường đắp trên đất yếu.</li>
  <li>Kết quả khảo sát địa kỹ thuật (hố khoan {{ bh_name }}).</li>
  <li>Kết quả thí nghiệm thành phần cấp phối xi măng đất.</li>
</ul>

<!-- II. ĐỊA CHẤT -->
<h1>II. ĐẶC ĐIỂM ĐỊA CHẤT KHU VỰC</h1>
<p>Căn cứ kết quả khảo sát hố khoan <b>{{ bh_name }}</b> tại khu vực <b>{{ zone }}</b>,
các thông số địa kỹ thuật chính dùng cho thiết kế:</p>
<table>
  <thead><tr><th>Thông số</th><th>Ký hiệu</th><th>Giá trị</th></tr></thead>
  <tbody>
  <tr><td>Bề dày lớp bùn sét (lớp cần gia cố)</td><td>h₁ (m)</td><td class="center">{{ '%.2f' | format(h_clay) }}</td></tr>
  <tr><td>Sức kháng cắt không thoát nước</td><td>Su (kN/m²)</td><td class="center">{{ '%.2f' | format(Su) }}</td></tr>
  <tr><td>Dung trọng tự nhiên</td><td>γ (kN/m³)</td><td class="center">{{ '%.2f' | format(gamma) }}</td></tr>
  <tr><td>Mô đun biến dạng đất nền</td><td>Es = 250·Su (kN/m²)</td><td class="center">{{ '{:,}'.format(Es_int) }}</td></tr>
  </tbody>
</table>

<!-- III. THÔNG SỐ THIẾT KẾ -->
<h1>III. THÔNG SỐ THIẾT KẾ CỌC ĐẤT XI MĂNG</h1>
<table>
  <thead><tr><th>Thông số</th><th>Ký hiệu</th><th>Giá trị</th></tr></thead>
  <tbody>
  <tr><td>Đường kính trụ CDM</td><td>D</td><td class="center">{{ '%.0f' | format(D*1000) }} mm</td></tr>
  <tr><td>Khoảng cách tâm-tâm (lưới {{ arr_label }})</td><td>e</td><td class="center">{{ e_list }}</td></tr>
  <tr><td>Chiều dài trụ CDM</td><td>Lc</td><td class="center">{{ '%.1f' | format(Lc) }} m</td></tr>
  <tr><td>Hàm lượng xi măng</td><td>x</td><td class="center">{{ dosage }} kg/m³</td></tr>
  <tr><td>Cường độ nén TK hiện trường</td><td>q<sub>u,tk</sub></td><td class="center">{{ '%.0f' | format(qu) }} kPa</td></tr>
  <tr><td>Cường độ kháng cắt thiết kế</td><td>Cc = qu/2</td><td class="center">{{ '%.0f' | format(Cc) }} kN/m²</td></tr>
  <tr><td>Mô đun đàn hồi trụ</td><td>Ec = 100·Cc</td><td class="center">{{ '{:,}'.format(Ec_int) }} kN/m²</td></tr>
  <tr><td>Tải trọng tổng (xét hoạt tải)</td><td>q</td><td class="center">{{ '%.2f' | format(q_total) }} kN/m²</td></tr>
  <tr><td>Tải trọng tĩnh (bỏ hoạt tải, dùng cho lún)</td><td>q<sub>tĩnh</sub></td><td class="center">{{ '%.2f' | format(q_static) }} kN/m²</td></tr>
  </tbody>
</table>

<!-- IV. PHƯƠNG PHÁP -->
<h1>IV. PHƯƠNG PHÁP TÍNH TOÁN LÚN (TCVN 9403:2012 — Phụ lục C)</h1>
<p>Tỷ lệ thay thế diện tích:</p>
<p class="formula">{{ a_formula }}</p>
<p>Mô đun tương đương khối gia cố:</p>
<p class="formula">E<sub>tb</sub> = a · E<sub>c</sub> + (1 − a) · E<sub>s</sub></p>
<p>Độ lún đàn hồi tức thời (dùng tải tĩnh, bỏ hoạt tải):</p>
<p class="formula">S₁ = q<sub>tĩnh</sub> × L<sub>c</sub> / E<sub>tb</sub> × 100  (cm)</p>
<p>S₂ = 0 (trụ CDM xuyên qua toàn bộ lớp bùn sét yếu).</p>

<!-- V. SO SÁNH PHƯƠNG ÁN -->
<h1>V. SO SÁNH CÁC PHƯƠNG ÁN KHOẢNG CÁCH TRỤ</h1>
<p class="caption">Bảng V.1 — So sánh phương án (D = {{ '%.0f' | format(D*1000) }} mm, qu = {{ '%.0f' | format(qu) }} kPa, q = {{ '%.1f' | format(q_total) }} kN/m²)</p>
<table>
  <thead>
    <tr>
      <th>PA</th><th>e (m)</th><th>a (%)</th><th>Etb (kN/m²)</th>
      <th>S₁ (cm)</th><th>Pcol (kN)</th><th>Qa (kN)</th><th>Đạt SCT</th>
    </tr>
  </thead>
  <tbody>
  {% for s in scenarios %}
    <tr class="{{ 'pass' if s['Đạt SCT'] == 'Đạt' else 'fail' }}{{ ' bold' if loop.index0 == rec_idx else '' }}">
      <td class="center"><b>{{ 'PA' ~ loop.index }}{{ ' ★' if loop.index0 == rec_idx else '' }}</b></td>
      <td class="center">{{ s['e (m)'] }}</td>
      <td class="center">{{ '%.1f' | format(s['a (%)']) }}%</td>
      <td class="center">{{ '{:,}'.format(s['Etb (kN/m²)'] | int) }}</td>
      <td class="center"><b>{{ '%.2f' | format(s['S₁ (cm)']) }}</b></td>
      <td class="center">{{ '%.1f' | format(s['Pcol (kN)']) }}</td>
      <td class="center">{{ '%.1f' | format(s['Qa (kN)']) }}</td>
      <td class="center"><b>{{ s['Đạt SCT'] }}</b></td>
    </tr>
  {% endfor %}
  </tbody>
</table>
<p class="caption">★ = Phương án kiến nghị</p>

<!-- VI. KẾT QUẢ PA KIẾN NGHỊ -->
{% if rec %}
<h1>VI. KẾT QUẢ — PHƯƠNG ÁN KIẾN NGHỊ (e = {{ rec['e (m)'] }} m)</h1>
<table>
  <thead><tr><th>Đại lượng</th><th>Giá trị</th></tr></thead>
  <tbody>
  <tr><td>Tỷ lệ thay thế a</td><td class="center">{{ '%.4f' | format(rec['a']) }}  ({{ '%.1f' | format(rec['a (%)']) }}%)</td></tr>
  <tr><td>Mô đun tương đương Etb</td><td class="center">{{ '{:,}'.format(rec['Etb (kN/m²)'] | int) }} kN/m²</td></tr>
  <tr><td>Độ lún S₁ (đàn hồi tức thời)</td><td class="center"><b>{{ '%.2f' | format(rec['S₁ (cm)']) }} cm</b></td></tr>
  <tr><td>Độ lún S₂</td><td class="center">0,00 cm</td></tr>
  <tr><td>Tổng độ lún S</td><td class="center"><b>{{ '%.2f' | format(rec['S₁ (cm)']) }} cm</b></td></tr>
  <tr><td>Lực nén lên 1 trụ Pcol</td><td class="center">{{ '%.1f' | format(rec['Pcol (kN)']) }} kN</td></tr>
  <tr><td>Sức chịu tải cho phép Qa</td><td class="center">{{ '%.1f' | format(rec['Qa (kN)']) }} kN</td></tr>
  <tr class="{{ 'pass' if rec['Đạt SCT'] == 'Đạt' else 'fail' }}">
    <td><b>Kiểm tra sức chịu tải (Pcol &lt; Qa)</b></td>
    <td class="center"><b>{{ rec['Đạt SCT'] }}</b></td>
  </tr>
  </tbody>
</table>

<div class="note">
<b>Kết luận:</b> Phương án thiết kế với khoảng cách trụ e = {{ rec['e (m)'] }} m
{{ 'đạt' if rec['Đạt SCT'] == 'Đạt' else 'KHÔNG đạt' }} yêu cầu về sức chịu tải.
Độ lún dự kiến S = {{ '%.2f' | format(rec['S₁ (cm)']) }} cm.
</div>
{% endif %}

<p style="margin-top:1cm; font-style:italic; font-size:10pt; text-align:right;">
Báo cáo tự động — {{ now }}
</p>

</body>
</html>
""")


def build_word_html(scenarios: list[dict], params: dict, rec_idx: int) -> bytes:
    """Tạo HTML format Word (Mso namespaces). Lưu .doc thì Word đọc native."""
    D    = params["D"]
    Lc   = params["Lc"]
    qu   = params["qu"]
    Cu   = params["Su"]
    Cc   = qu / 2
    Ec   = 100 * Cc
    Es   = 250 * Cu

    is_tri = params.get("arrangement", "triangle") == "triangle"
    arr_label = "tam giác" if is_tri else "hình vuông"
    a_formula = ("a = π · D² / (2 · √3 · e²)  (lưới tam giác)"
                 if is_tri else "a = π · D² / (4 · e²)  (lưới vuông)")

    e_list = " / ".join(f"{s['e (m)']}" for s in scenarios) + " m"
    rec = scenarios[rec_idx] if scenarios else {}

    html = _WORD_TEMPLATE.render(
        title=f"Thuyết minh CDM — {params.get('bh_name', '')}",
        today=datetime.now().strftime("%d/%m/%Y"),
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
        zone=params.get("zone", "—"),
        bh_name=params.get("bh_name", "—"),
        D=D, Lc=Lc, qu=qu, Cc=Cc,
        Ec_int=int(Ec), Es_int=int(Es),
        Su=Cu, gamma=params.get("gamma", 15.0),
        h_clay=params.get("h_clay", 0),
        q_total=params.get("q_total", 0),
        q_static=params.get("q_static", params.get("q_total", 0) - 20),
        arr_label=arr_label, a_formula=a_formula,
        e_list=e_list, dosage=params.get("dosage", 240),
        scenarios=scenarios, rec_idx=rec_idx, rec=rec,
    )
    return html.encode("utf-8")
