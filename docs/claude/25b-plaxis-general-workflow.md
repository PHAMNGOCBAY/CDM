## Cấu trúc Code Bắt buộc

### Mọi Script PLAXIS Phải Có

```python
import os
from plxscripting.easy import new_server

# ✓ PASSWORD từ environment variable (KHÔNG hardcode)
PASSWORD = os.environ.get('PLAXIS_PASSWORD', '')

# ✓ Type hints cho mọi hàm
def build_wall_model(g_i, depth: float, thickness: float) -> None:
    ...

# ✓ try/finally để đảm bảo cleanup
try:
    # ... logic chính
finally:
    s_i.close()
    s_o.close()
    process.terminate()
```

### Cấu trúc Phân đoạn Bắt buộc (Staged Construction Script)

```python
# === BƯỚC 1: KHỞI TẠO ===
# === BƯỚC 2: HÌNH HỌC ===
# === BƯỚC 3: VẬT LIỆU ===
# === BƯỚC 4: PHASES ===
# === BƯỚC 5: LƯỚI ===
# === BƯỚC 6: TÍNH TOÁN ===
# === BƯỚC 7: KẾT QUẢ ===
```

---

## Quy trình Xử lý Yêu cầu

### Yêu cầu Mô hình Mới

1. **Đọc** thông số địa tầng và hình học từ user
2. **Xác nhận** đơn vị (hỏi lại nếu không rõ)
3. **Validate** bằng GeoMCP nếu cần tính toán sơ bộ
4. **Viết code** theo cấu trúc 7 bước
5. **Cảnh báo** các điểm cần kỹ sư kiểm tra

### Yêu cầu Gỡ lỗi

1. **Đọc** error log được cung cấp
2. **Phân loại** lỗi (kết nối, cú pháp, hội tụ, đơn vị)
3. **Đề xuất** fix cụ thể
4. **Cảnh báo** nếu lỗi có thể do sai thông số vật lý

### Yêu cầu Phân tích Kết quả

1. **Kiểm tra** tính hợp lý (FoS trong 1.0–5.0, Umax < H/100)
2. **So sánh** với tiêu chuẩn (TCVN, Eurocode 7)
3. **Đề xuất** cải thiện nếu không đạt
4. **Gọi GeoMCP** để xác nhận tính toán thủ công nếu cần

---

## Mapping Tài liệu → Vấn đề Kỹ thuật

| Khi gặp vấn đề | Đọc tài liệu |
|---------------|-------------|
| Cài đặt, kết nối PLAXIS | [01-plaxis-api-setup.md](01-plaxis-api-setup.md) |
| Cú pháp lệnh, tạo hình học | [02-command-reference.md](02-command-reference.md) |
| Trích xuất ResultTypes, structureplot | [03-output-extraction.md](03-output-extraction.md) |
| Kỹ thuật viết prompt cho Claude | [04-claude-prompt-engineering.md](04-claude-prompt-engineering.md) |
| MCP, GeoMCP, SymPy, Pint | [05-mcp-geomcp-framework.md](05-mcp-geomcp-framework.md) |
| Tối ưu hóa NSGA-II, pymoo | [06-nsga2-optimization.md](06-nsga2-optimization.md) |
| Lỗi hội tụ, trình tự cố kết | [07-error-convergence.md](07-error-convergence.md) |
| Pipeline đầu cuối, VIKTOR, BIM | [08-end-to-end-workflows.md](08-end-to-end-workflows.md) |
| Tính lún TCCS41, bấc thấm, giếng cát | [38-tccs41-nen-duong-dat-yeu.md](38-tccs41-nen-duong-dat-yeu.md) + [scripts/settlement_calc.py](scripts/settlement_calc.py) |
| Thiết kế CDM, phân tích mẫu TCVN 9403 | [39-tcvn9403-tru-dat-xi-mang.md](39-tcvn9403-tru-dat-xi-mang.md) + [scripts/cdm_column_calc.py](scripts/cdm_column_calc.py) |

---

## Phân loại Bài toán Địa kỹ thuật & Lưu ý Chuyên biệt

### Hố đào sâu (Deep Excavation)

- Kiểm tra basal heave stability (Fs_heave ≥ 1.5)
- Tường vây: Kết quả qua `ResultTypes.Plate` sau `structureplot()`
- Neo/Strut: Kiểm tra lực dọc trục `Nx2D`
- Pha cố kết nếu đất sét: Dùng `StagedConstruction`, KHÔNG dùng `MinPorePressure`

### Ổn định Mái dốc

- Phương pháp Phi/c Reduction (SRF/SRFEA)
- Pha cuối là Safety phase, không có kết cấu
- FoS qua `phase.Reached.SumMsf` (KHÔNG dùng `phase.SumMsf.value` — lỗi trong PLAXIS 2D 2024)

### Cọc Chịu tải

- Mô hình cọc dạng `Plate` hoặc `EmbeddedBeam`
- Kết quả nội lực: M2D, Q2D, Nx2D
- Kiểm tra độ lún đầu cọc

### Cố kết (Consolidation)

- **Luôn** dùng `StagedConstruction` khi có thay đổi cấu trúc
- `MinPorePressure` / `DegreeOfConsolidation`: chỉ sau SC phase, không sau Plastic
- Kiểm tra tỷ số tiêu tán áp lực lỗ rỗng

---

## Checklist Cuối trước khi Trả lời

Trước mỗi câu trả lời có chứa mã Python PLAXIS:

- [ ] Tất cả tham số đất có đúng đơn vị (phi=°, E=kN/m², gamma=kN/m³)?
- [ ] Có gọi `g_o.structureplot()` trước `ResultTypes.Plate`?
- [ ] Có `try/finally` với cleanup không?
- [ ] Trình tự Staged Construction có đúng kỹ thuật thi công không?
- [ ] Không có MPP/DoC sau Plastic/Dynamic phase không?
- [ ] Password được lấy từ `os.environ` không?
- [ ] Đã kiểm tra `data/*.json` trước khi đọc PDF / Excel / Docs / ảnh chưa?
- [ ] Dữ liệu mới trích xuất đã được lưu vào `data/*.json` chưa?

---

## Ví dụ Phản hồi Chuẩn — Khi Được Yêu cầu Tính toán

**Yêu cầu:** "Tính sức chịu tải móng nông B=1.5m, L=2m trên đất sét có phi=22°, c=30 kN/m²"

**KHÔNG làm:** Tự tính ra con số từ training data.

**ĐÚng làm:**
```
Tôi sẽ tính qua GeoMCP để đảm bảo độ chính xác (sai lệch < 0.15% so với Eurocode 7):

[Gọi MCP Tool: geomcp_calculate]
method: "bearing_capacity_meyerhof"
parameters: {c: 30, phi: 22, q: 18, gamma: 17.5, B: 1.5, L: 2.0}

[Kết quả từ GeoMCP]:
- Nq = 9.19, Nc = 20.63, Ng = 6.98
- qu = 845.3 kN/m²
- qa (Fs=3) = 281.8 kN/m²
```

---

