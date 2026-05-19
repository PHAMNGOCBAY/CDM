# 26 — API Clay (Matlock 1970) p-y Model — Lateral Pile Analysis

## Mục đích

Tích hợp mô hình đất sét **Matlock (1970) / API (1974)** vào Streamlit app `app_coc_tai_ngang.py`
song song với mô hình cát API (1987) đã có sẵn. Cho phép phân tích cọc SW trong địa tầng hỗn hợp
(cát + sét) theo đường cong p-y chuẩn API.

> **AI workflow:** Đọc file này trước → `data/api_clay_matlock.json` → `scripts/api_clay_matlock.py`

---

## 1. Lý thuyết — Matlock (1970) / API RP 2GEO (1974)

### 1.1 Đường cong p-y cho đất sét mềm–cứng

$$p = 0.5 \cdot p_u \cdot \left(\frac{y}{y_{50}}\right)^{1/3}$$

- **p** — phản lực đất tại độ dịch chuyển y [kN/m]
- **p_u** — sức kháng đất cực hạn [kN/m]
- **y₅₀ = 2.5 · ε₅₀ · D** — độ dịch chuyển tại 50% p_u [m]
- **ε₅₀** — biến dạng tại 50% tải phá hoại trong thí nghiệm UU (không thoát nước)
- **D** — đường kính (hoặc bề rộng tương đương) cọc [m]

### 1.2 Sức kháng đất cực hạn p_u

$$p_u = \min\left[(3 + \frac{\gamma'}{S_u} z + \frac{J}{D} z),\ 9\right] \cdot S_u \cdot D$$

| Ký hiệu | Ý nghĩa | Đơn vị |
|---------|---------|--------|
| S_u | Sức chịu cắt không thoát nước | kN/m² |
| γ' | Dung trọng đẩy nổi | kN/m³ |
| z | Chiều sâu dưới mặt đất | m |
| J | Hệ số kinh nghiệm không thứ nguyên | — |
| D | Đường kính / bề rộng cọc | m |

**Hệ số J (API 1974):**
- Đất sét mềm (soft): J = 0.50
- Đất sét cứng (stiff): J = 0.25
- Mặc định dùng: **J = 0.50**

### 1.3 Giới hạn đường cong (cap)

Khi `y → ∞`, p được giới hạn ở `p = p_u` (không tăng thêm).
Khi `y < 0`, p tính theo chiều ngược lại (đối xứng).

---

## 2. Thông số đầu vào (openpile API_clay)

```python
from openpile.soilmodels import API_clay

# Giá trị đơn (đồng nhất trong lớp)
model = API_clay(Su=10.0, eps50=0.02, kind="static", J=0.5)

# Giá trị tuyến tính (biến đổi từ đỉnh → đáy lớp)
model = API_clay(Su=[10.0, 20.0], eps50=[0.02, 0.01], kind="static", J=0.5)
```

| Tham số | Ký hiệu | Đơn vị | Giá trị điển hình |
|---------|---------|--------|------------------|
| `Su` | Sức chịu cắt không thoát nước | kN/m² | 5–200 |
| `eps50` | Biến dạng 50% phá hoại | — | Soft: 0.02 · Medium: 0.01 · Stiff: 0.005 |
| `J` | Hệ số kinh nghiệm | — | 0.25–0.50 (default: 0.50) |
| `kind` | Loại tải | — | `"static"` / `"cyclic"` |
| `G0` | Mô đun cắt nhỏ | kN/m² | Tùy chọn, None = bỏ qua |

---

## 3. Quy trình nhập liệu trong Streamlit App (v5)

### 3.1 Tab Soil Layers — 2 bảng riêng biệt

**🟡 Sand Layers** (API 1987):
- Cột cho nhập: Layer Tip, Density, **Phi [Deg]**, Delta, Cohesion
- Cột bị khóa (xám): `Su [kN/m²] ⬜`, `ε₅₀ ⬜`
- `disabled=["Su [kN/m2]", "eps50"]` trong `st.data_editor`

**🔵 Clay Layers** (Matlock 1974):
- Cột cho nhập: Layer Tip, Density, **Su [kN/m²]**, **ε₅₀**, Delta, Cohesion
- Cột bị khóa (xám): `Phi [Deg] ⬜`
- `disabled=["Phi [Deg]"]` trong `st.data_editor`

### 3.2 Merge và sắp xếp

Hai bảng được merge và sort theo `Layer Tip [m]` giảm dần (nông → sâu):

```python
merged = pd.concat([sand_df, clay_df], ignore_index=True)
merged = merged.sort_values("Layer Tip [m]", ascending=False)
```

### 3.3 Chọn model trong engine tính toán

```python
def _lateral_model(stype, ph, su_v, e50):
    if stype.strip().lower() == "clay":
        return API_clay(Su=max(su_v, 0.1), eps50=max(e50, 0.001),
                        kind="static", J=0.5)
    else:
        return API_sand(phi=max(ph, 1.0), kind="static")
```

---

## 4. Session State — Key mới (v5)

| Key | Kiểu | Nội dung |
|-----|------|---------|
| `front_sand_df` | DataFrame | Sand layers (Phi) — bảng Front Sand |
| `front_clay_df` | DataFrame | Clay layers (Su, eps50) — bảng Front Clay |
| `front_layers_df` | DataFrame | Merged view — dùng cho earth pressure, water pressure |
| `back_layers_df` | DataFrame | Combined (Sand + Clay) — Layers behind |

**Migration từ session cũ:**
```python
def _migrate_to_split(combined_df):
    """Tách combined front_layers_df → (sand_df, clay_df) theo cột Soil Type."""
    mask_sand = combined_df["Soil Type"] == "Sand"
    return combined_df[mask_sand], combined_df[~mask_sand]
```

---

## 5. Kết quả test (2026-05-16)

Profile địa tầng test: Sand (-5m) → Clay (-10m) → Sand (-20m), H = 100 kN

| KPI | Giá trị |
|-----|--------|
| Head deflection | 6.991 mm |
| Max deflection | 6.991 mm |
| M_max (z = -0.7 m) | 198.7 kN·m |
| V_max (z = 2.7 m) | 98.8 kN |
| M_max / Mcr | 0.26 ✅ OK |
| Iterations hội tụ | 4 |

---

## 6. Giá trị ε₅₀ tham khảo (Matlock 1970)

| Loại đất sét | S_u (kN/m²) | ε₅₀ |
|-------------|------------|------|
| Rất mềm (very soft) | < 12 | 0.020 |
| Mềm (soft) | 12–25 | 0.020 |
| Trung bình (medium) | 25–50 | 0.010 |
| Cứng (stiff) | 50–100 | 0.007 |
| Rất cứng (very stiff) | 100–200 | 0.005 |
| Cứng đặc (hard) | > 200 | 0.004 |

---

## 7. Ghi chú kỹ thuật

- **Cohesion** trong bảng đất → dùng cho biểu đồ áp lực đất chủ động/bị động, **KHÔNG** dùng cho p-y
- **Su trong bảng đất** → dùng cho p-y curve (API_clay), cần lấy từ UU hoặc vane shear
- **J = 0.5** mặc định (soft clay), giảm về 0.25 nếu đất sét cứng
- Cọc SW dùng `Pile.create_tubular(diameter=H/1000, wt=t/1000, material="Concrete")`

---

## 8. Yêu cầu x2mesh khi áp dụng tải phân bố

**Vấn đề:** `set_pointload` tại elevation trung gian bị bỏ qua thầm lặng nếu elevation đó không là FEM node.

openpile in cảnh báo vào stdout nhưng không raise exception:

```text
Load not applied! The chosen elevation is not meshed as a node.
Please include elevation in x2mesh variable when creating the Model.
```

**Giải pháp:** Tính midpoints của grid 1 m trước, pass vào `x2mesh` khi tạo `Model()`:

```python
n = max(2, round(abs(top_elev - bot_elev)) + 1)
pts = np.linspace(top_elev, bot_elev, n)
mids = [float((pts[k] + pts[k+1]) / 2.0) for k in range(len(pts) - 1)]

model = Model(name="run", pile=pile, soil=sp,
              boundary_conditions=bc, x2mesh=mids)   # TRƯỚC set_pointload

for mid, F in dist_loads:
    model.set_pointload(elevation=mid, Py=F)
```

**Phạm vi áp dụng:** Mọi tải phân bố rời rạc hóa — áp lực đất, áp lực nước, Boussinesq. Tải đầu cọc tại `top_elevation` luôn là node, không cần x2mesh.

**Xác nhận 2026-05-16:**

- Không có x2mesh: tải bị bỏ qua, kết quả = 0 / NaN
- Có x2mesh: tải được áp dụng, hội tụ, kết quả hợp lý

---

## Tham khảo

- Matlock, H. (1970). "Correlations for design of laterally loaded piles in soft clay." OTC-1204
- API RP 2GEO (1974, 2014). "Geotechnical and Foundation Design Considerations"
- openpile docs: `API_clay` class — `Su`, `eps50`, `J`, `kind`
