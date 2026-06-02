### 71. Quy tắc tính S2 đầy đủ — Mở rộng đến đáy vùng ảnh hưởng + Tức thời

**Áp dụng:** TẤT CẢ zones (QTT, BXN, NHC, KE_park, KE_levee) và mọi tính lún CDM.
**Tài liệu kỹ thuật:** TCCS 41:2022 §6.2.3 + Phụ lục C, Terzaghi (1925)
**File engine:** [scripts/settlement_calc.py](scripts/settlement_calc.py) — `calc_s2_below_cdm()`

---

#### 1. Định nghĩa S2 đầy đủ (BẮT BUỘC)

$$S_2 = \underbrace{\sum_{i \in \text{sét}} S_{i,clay}}_{\text{cố kết Terzaghi}} + \underbrace{\sum_{j \in \text{cát/sét cứng}} S_{j,instant}}_{\text{lún tức thời}}$$

**Phạm vi tích phân:** từ **mũi cọc CDM** đến **đáy vùng ảnh hưởng** (depth tại đó $\Delta\sigma / \sigma'_{v0} < 10\%$ — TCCS 41 §6.2.3).

**KHÔNG dừng ở đáy hố khoan** — nếu HK chưa tới đáy vùng ảnh hưởng, **ngoại suy** bằng γ, Cc, e₀ của **lớp cuối HK** cho đến khi đạt ngưỡng 10%.

---

#### 2. Hai thành phần S2

| Thành phần | Lớp đất | Cơ chế | Thời gian | Công thức |
|---|---|---|---|---|
| **S2_clay** | sét bùn (symbol ∉ SAND_SYMBOLS_S2) | Cố kết Terzaghi 1D | Theo U(t) | $S_i = \dfrac{h_i C_c}{1+e_0} \log_{10}\dfrac{\sigma'_{vf}}{\sigma'_{v0}}$ (NC) hoặc OC/cross-PC |
| **S2_sand** | cát, sỏi (symbol ∈ SAND_SYMBOLS_S2) | Đàn hồi tức thời | t = 0 | $S_i = \dfrac{\Delta\sigma \cdot h_i}{E_s}$ với $E_s = \alpha_{sand} \cdot N_{SPT}$ |
| **S2_stiff_clay** | sét cứng (e₀ < 1) | Cố kết nhanh ≈ tức thời | t ≈ 0 | $S_i$ Terzaghi nhưng U(t) ≈ 100% sau ~1 năm |

**SAND_SYMBOLS_S2 = {F, 2a, 2b, 2c, 3a, 3b, 3c, 4, 5, 5a, 5b, 6, 7, 8}**

**Engine output mỗi phân tố:**
```json
{
  "depth_mid_m": 24.0, "H_i_m": 2.0,
  "symbol": "1b", "is_sand": false,
  "is_extrapolated": false,
  "sigma_v0_kPa": 145.6, "dsigma_kPa": 40.8,
  "Si_cm": 4.2, "method": "Cc"
}
```

---

#### 3. Logic mở rộng vượt HK (mới — §71)

Engine `calc_s2_below_cdm` (line ~804) cũ chỉ tích phân đến `max_depth_m = MAX(layers.depth_bot_m)`. Vấn đề: HK 30-36m không đủ tới đáy vùng ảnh hưởng (thường 50-60m).

**Sửa đổi:**

```python
EXTEND_MAX_M = 200.0
extended_max = max_depth_m + EXTEND_MAX_M

while z <= extended_max:
    p = _interp_params(z)         # khi z > max_depth: dùng layer cuối HK
    sigma_v0 = calc_sigma_v0(z, p["gamma"], gwt_depth_m)
    dsig     = _dsigma_at(z)

    if sigma_v0 > 0 and (dsig / sigma_v0) < stop_ratio:
        stop_reason = f"delta_sigma/sigma_v0 < 10% tai z={z:.1f}m"
        break

    is_extrapolated = z > max_depth_m
    # ... compute Si ...
    layers_out.append({..., "is_extrapolated": is_extrapolated})
    z += sublayer_m
```

**Safety cap:** 200m từ mũi cọc — tránh runaway nếu σ'v0 không đủ tăng.

**Cờ `is_extrapolated`** cho mỗi phân tố — UI/Word report có thể đánh dấu phân tố ngoại suy.

---

#### 4. Verify trên 6 HK QTT (ΔS=30, q=40.8 kPa)

Engine cũ (dừng tại HK_max):

| HK | HK_max (m) | S2 cũ (cm) | Stop |
|:---:|:---:|:---:|:---:|
| ND-02 | 31 | 24.6 | max_depth (đã dừng tại HK) |
| ND-04 | 33 | 9.6 | max_depth |

Engine mới (extend đến đáy ảnh hưởng):

| HK | tip (m) | HK_max (m) | **S2 mới (cm)** | n_ngoại suy | S2_ngoại suy | stop_depth |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| ND-02 | 15.8 | 31 | **37.7** | 12 | **12.0** | 56.8m |
| ND-03 | 18.0 | 36 | 30.8 | 9 | 9.8 | 55.0m |
| ND-04 | 19.5 | 33 | **22.1** | 11 | **12.5** | 56.5m |
| ND-05 | 17.9 | 36 | 28.2 | 8 | 8.6 | 52.9m |
| ND-06 | 17.1 | 36 | 32.3 | 1 | 1.2 | 38.1m |
| ND-07 | 15.0 | 36 | 35.6 | 0 | 0 | 38.0m (vừa đủ trong HK) |

ND-02 và ND-04 nhận thêm **~12 cm lún** từ phân tố ngoại suy — đáng kể.

---

#### 5. Pipeline áp dụng — TẤT CẢ ZONES

Sau khi sửa engine, cần **re-compute toàn bộ** `cdm_zone_design_results` cho mọi zone:

```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from save_cdm_zone_results import save_zone
from pathlib import Path

DBs = [
    Path(r'C:\Users\bayng\TTHC_local\TTHC.sqlite'),
    Path('data/TTHC.sqlite'),
]
ZONES = ['QTT', 'BXN', 'NHC', 'KE_park', 'KE_levee']
for db in DBs:
    if not db.exists(): continue
    for z in ZONES:
        n = save_zone(z, db_path=db)
        print(f'{db.parent.name} / {z}: {n} rows')
"
```

→ Re-tính S1, S2 (với extension), S_total, Lc tối ưu cho mọi (HK, ΔS).

---

#### 6. Quy tắc bắt buộc khi gọi `calc_s2_below_cdm`

| Tham số | Quy tắc | Tham chiếu |
|---|---|---|
| `gwt_depth_m` | BẮT BUỘC truyền theo cao độ MNN zone | §69 |
| `q_kPa` | Tải đắp/CDM (tải gây lún ngoài S1) | Per zone |
| `stop_ratio` | 0.10 (mặc định) — chuẩn TCCS 41 | §71 (này) |
| `sublayer_m` | 2.0 (mặc định) — chia nhỏ phân tố | §71 |
| `t_years_residual` | 15.0 (mặc định) — tuổi đường | TCCS 41 §6.2.3 |
| `double_drainage` | False mặc định (cố kết 1 mặt — đáy không thấm) | §71 |

**KHÔNG được override `stop_ratio` > 0.10** — đó là chuẩn TCCS 41 cho đáy vùng ảnh hưởng.

---

#### 7. Output JSON snapshot (per zone)

Sau re-compute, lưu snapshot JSON `data/sN_extension_<zone>.json` để audit:

```json
{
  "_meta": {
    "rule": "§71 — S2 extension to influence depth",
    "stop_ratio": 0.10,
    "extended_max_m": 200.0,
    "updated": "2026-06-02 HH:MM:SS"
  },
  "zone_code": "QTT",
  "boreholes": [
    {
      "bh_name": "ND-07",
      "tip_depth_m": 15.0,
      "hk_max_m": 36.0,
      "stop_depth_m": 38.0,
      "S2_total_cm": 35.6,
      "S2_clay_cm": 35.6,
      "S2_sand_cm": 0.0,
      "n_layers_in_hk": 11,
      "n_layers_extrapolated": 0,
      "S2_extrapolated_cm": 0.0
    }
  ]
}
```

---

#### 8. Tác động lên Lc tối ưu

| Zone | HK có Lc thay đổi lớn nhất | Lc cũ → Lc mới (ΔS=30) |
|---|---|---|
| QTT | ND-02 | 14.9 → **16.9 m** (+2m) |
| QTT | ND-04 | 19.2 → **20.2 m** (+1m) |
| Khác | (chạy lại sẽ thấy) | (verify sau re-compute) |

→ Cọc phải dài hơn vì S2 lớn hơn (cộng phần ngoại suy + tức thời lớp cát/cứng dưới mũi).

---

#### 9. Checklist khi commit thay đổi

- [ ] Verify `calc_s2_below_cdm` có vòng `while z <= max_depth_m + EXTEND_MAX_M`
- [ ] Mỗi phân tố output có field `is_extrapolated`
- [ ] Đã chạy `save_zone` cho **5 zones** (QTT/BXN/NHC/KE_park/KE_levee)
- [ ] Đã ghi cả LOCAL + PROJECT SQLite
- [ ] Cập nhật `qtt_zone_meta.json` + tương đương cho zones khác
- [ ] Lưu JSON snapshot `data/s2_extension_<zone>.json` per zone
- [ ] Verify Lc thay đổi (so với version cũ) trong commit message
