### 61. Formulas Engine — Single-Source-of-Truth cho công thức kỹ thuật

**Vị trí:** `scripts/core/formulas/` · **Generator:** `scripts/regen_docs.py` · **Validator:** `scripts/check_formula_sync.py`

Mỗi công thức kỹ thuật trong dự án được định nghĩa MỘT LẦN dưới dạng SymPy expression + numeric callable. Code Python import numeric callable (không hardcode lại biểu thức). File MD đánh marker `<!-- AUTO-FORMULA: <id> -->...<!-- /AUTO-FORMULA -->` → chạy generator để tự render LaTeX vào MD.

**Mục đích:** Sửa công thức ở MỘT chỗ (registry), MD/code khác tự đồng bộ. Loại bỏ pattern "sửa S1 ở 5 chỗ rồi sót 2 chỗ".

#### Cấu trúc

```
scripts/core/formulas/
  __init__.py       Formula dataclass + register helpers
  registry.py       _REGISTRY dict[id → Formula]
  units.py          SymPy symbols dùng chung (sigma_v0, mu, Cc...)
  cdm.py            S1, Ec, Es Bjerrum, S2 (OC/NC/cross), Eoed, μ Bjerrum
  bearing.py        NT2 Rs/Rp α-method
```

#### Pattern dùng

**1. Định nghĩa MỘT lần** (`scripts/core/formulas/cdm.py`):
```python
s1 = register(Formula(
    id="cdm-s1",
    lhs=S_1,
    rhs=q * H / (a * E_c + (1 - a) * E_s),
    description="Lún đàn hồi tức thì của khối gia cố CDM",
    standard="TCVN 9403:2012 Phụ lục C, công thức C.6",
    unit_lhs="m",
    unit_inputs={"q": "kPa", "H": "m", "a": "(0-1)", "E_c": "kPa", "E_s": "kPa"},
    numeric=lambda q_kPa, H_m, a, Ec_kPa, Es_kPa: q_kPa * H_m / (a * Ec_kPa + (1-a) * Es_kPa),
))
```

**2. Code import numeric** (`tvtk_cdm_s1_calc.py`):
```python
# FORMULA-ID: cdm-s1
from core.formulas.cdm import s1_numeric
S1_m = s1_numeric(q_kPa=40.8, H_m=23.0, a=0.155, Ec_kPa=40000, Es_kPa=2859)
```
Tag `# FORMULA-ID: <id>` phía trên import → validator track usage.

**3. MD đánh marker:**
```markdown
<!-- AUTO-FORMULA: cdm-s1 -->
$$S_{1} = \frac{H q}{E_{c} a + E_{s} \left(1 - a\right)}$$
<!-- /AUTO-FORMULA -->
```
Chạy `python scripts/regen_docs.py` → tự render LaTeX vào vùng marker từ `Formula.latex_display`.

#### Lệnh

| Lệnh | Mục đích |
| --- | --- |
| `python scripts/regen_docs.py` | Render LaTeX vào tất cả MD (root + docs/claude/) |
| `python scripts/regen_docs.py --check` | Check-only — exit 1 nếu drift (cho pre-commit) |
| `python scripts/check_formula_sync.py` | Validate: code tags, MD đồng bộ, numeric smoke-test |

#### Quy tắc bắt buộc

1. **KHÔNG hardcode công thức ở code Python** — phải import `*_numeric` từ `core.formulas.*`.
2. **Tag `# FORMULA-ID: <id>`** phía trên dòng import hoặc dòng tính, để validator track.
3. **MD công thức kỹ thuật** dùng marker `<!-- AUTO-FORMULA: <id> -->` — KHÔNG viết tay LaTeX bên trong (sẽ bị overwrite).
4. **Đơn vị trong registry** ghi rõ trong `unit_inputs` + `unit_lhs`. Khi cần convert (m → cm) làm Ở CODE GỌI, không trong registry.
5. **Sửa công thức** → sửa `rhs` SymPy + `numeric` lambda → chạy `regen_docs.py` → cả MD lẫn code tự đồng bộ.
6. **Thêm công thức mới** → thêm `register(Formula(...))` trong file phù hợp + cập nhật `_load_all_modules()` nếu thêm module mới.

#### Pre-commit hook (khuyến nghị)

`.git/hooks/pre-commit`:
```bash
#!/bin/sh
python scripts/check_formula_sync.py || exit 1
```

Hoặc dùng `pre-commit` framework với:
```yaml
- id: formula-sync
  name: Formula sync check
  entry: python scripts/check_formula_sync.py
  language: system
  pass_filenames: false
```

#### Danh sách công thức đã đăng ký (Phase 1, 11 ID)

| FORMULA-ID | Mô tả | Tiêu chuẩn |
| --- | --- | --- |
| `cdm-s1` | Lún đàn hồi khối gia cố CDM | TCVN 9403 Phụ lục C |
| `cdm-ec` | Mô đun trụ Ec = k × Cc | TCVN 9403 §B.5.1 |
| `es-bjerrum` | Mô đun đất Es = 250·μ·Su | Mesri & Olson + TCCS 41 C.5 |
| `bjerrum-mu` | μ tra Bảng C.1 theo Ip | TCCS 41 Phụ lục C.3.2 |
| `cdm-s2-oc` | Lún cố kết phân tố OC | Terzaghi 1D / TCCS 41 |
| `cdm-s2-nc` | Lún cố kết phân tố NC | Terzaghi 1D / TCCS 41 |
| `cdm-s2-cross` | Lún cố kết phân tố cross_PC | Terzaghi 1D / TCCS 41 |
| `cdm-eoed-from-a12` | Eoed từ a1-2 (cm²/kgf) | Định nghĩa Eoed |
| `cdm-s2-eoed` | Lún cố kết qua Eoed | TCCS 41 Phụ lục A |
| `nt2-rs-alpha` | Ma sát thân cọc sét (α-method) | TCVN 11823-10 §7.3.8.6.2 |
| `nt2-rp-clay` | Sức kháng mũi cọc sét (Nc=9) | TCVN 11823-10 §7.3.8.6.2 |

#### Roadmap Phase 2-3

- **Phase 2:** Mở rộng kh Winkler (`kh-clay-matlock`), Boussinesq surcharge, NT2 SPT-Meyerhof (cát), Ec_field/Ec_lab. Refactor `settlement_calc.py`, `cdm_column_calc.py`, `ke_sw_nt_calc.py` import từ registry.
- **Phase 3:** Stability (Bishop/Spencer/M-P/overturning), Rankine/Coulomb earth pressure, Phụ lục E chuyển tiếp đường-cầu. Pre-commit hook bắt buộc.
