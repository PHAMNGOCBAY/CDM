### 69. Quy tắc tính ứng suất hữu hiệu σ'v0 — BẮT BUỘC cho mọi tính lún S2

**Tài liệu kỹ thuật:** TCCS 41:2022 Phụ lục C, Terzaghi (1925)
**File engine:** [scripts/settlement_calc.py](scripts/settlement_calc.py) — `calc_sigma_v0()`
**Module dùng:** `calc_s2_below_cdm`, `compare_methods`, `find_cdm_length`

---

#### 1. Định nghĩa nguyên lý Terzaghi

Đối với đất bão hoà, ứng suất tổng $\sigma_v$ được phân chia thành **ứng suất hữu hiệu** (do hạt đất truyền) và **áp lực nước lỗ rỗng** (do nước truyền):

$$\sigma_v = \sigma'_v + u$$

→ Ứng suất hữu hiệu:

$$\sigma'_v(z) = \sigma_v(z) - u(z)$$

Trong đó:
- $\sigma_v(z) = \int_0^z \gamma_{sat}(z') \, dz'$ — tổng ứng suất do trọng lượng đất (kPa)
- $u(z) = \gamma_w \cdot \max(0,\; z - z_{gwl})$ — áp lực nước lỗ rỗng (kPa); chỉ tồn tại dưới mực nước ngầm
- $\gamma_w = 9.81$ kN/m³ — dung trọng nước
- $z_{gwl}$ — **độ sâu** mực nước ngầm tính từ mặt đất hố khoan (m)

---

#### 2. Quy đổi cao độ MNN ↔ độ sâu MNN per hố khoan

Mực nước ngầm thường được nhập theo **cao độ tuyệt đối** (mốc Quốc gia) — giống nhau cho mọi hố khoan trong cùng zone:

$$z_{gwl,BH} = \max(0,\; z_{TN,BH} - z_{gwl,elev})$$

Trong đó:
- $z_{TN,BH}$ — cao độ tự nhiên tại miệng hố khoan (m)
- $z_{gwl,elev}$ — cao độ tuyệt đối mực nước ngầm (m, mặc định **+0.0m** cho dự án QTT)

**Ví dụ QTT (z_gwl,elev = +0.00 m):**

| HK | Cao độ TN (m) | Độ sâu MNN từ mặt đất (m) |
|:---:|:---:|:---:|
| ND-02 | +1.70 | **1.70** |
| ND-03 | +1.89 | 1.89 |
| ND-04 | +1.09 | 1.09 |
| ND-05 | +3.20 | 3.20 |
| ND-06 | +4.24 | 4.24 |
| ND-07 | +3.47 | 3.47 |

---

#### 3. Hai cách tính tương đương σ'v0

**Cách 1 — Tổng trừ áp lực nước** (dùng trong [scripts/qtt_charts.py](scripts/qtt_charts.py)):

$$\sigma'_{v0}(z) = \int_0^z \gamma_{sat} \, dz - \gamma_w \cdot \max(0, z - z_{gwl})$$

**Cách 2 — Tích phân γ' dưới MNN** (dùng trong [scripts/settlement_calc.py](scripts/settlement_calc.py)):

$$\sigma'_{v0}(z) = \begin{cases}
\gamma_{sat} \cdot z & \text{nếu } z \le z_{gwl} \\
\gamma_{sat} \cdot z_{gwl} + \gamma' \cdot (z - z_{gwl}) & \text{nếu } z > z_{gwl}
\end{cases}$$

với $\gamma' = \gamma_{sat} - \gamma_w$ — dung trọng đẩy nổi.

**Verify tương đương:** với $z > z_{gwl}$:
- Cách 1: $\sigma_v - u = \gamma_{sat} \cdot z - \gamma_w (z - z_{gwl}) = \gamma_{sat} \cdot z_{gwl} + (\gamma_{sat} - \gamma_w)(z - z_{gwl}) = $ Cách 2 ✓

---

#### 4. Đáy vùng ảnh hưởng lún (TCCS 41)

Tại độ sâu $z = d_{stop}$ mà $\sigma'_{v0}(d_{stop}) = 10 \cdot \Delta\sigma$ (tải gây lún), gia tải gây lún tỉ lệ < 10% → **bỏ qua phân tố** lún bên dưới $d_{stop}$.

$$\frac{\Delta\sigma}{\sigma'_{v0}(d_{stop})} = \frac{1}{10} = 10\%$$

**Tiếp tục tích phân γ qua đáy hố khoan**: lớp đất cuối được xem **mặc định kéo dài vô tận** với $\gamma_{last}$ → cho phép tính đáy vùng ảnh hưởng vượt sâu hơn HK ban đầu.

---

#### 5. Áp dụng trong tính lún S1, S2

**S1 (lún đàn hồi khối gia cố CDM — TCVN 9403 Phụ lục C.6):**

$$S_1 = \frac{q \cdot H}{a \cdot E_c + (1-a) \cdot E_s} \times 100 \quad [\text{cm}]$$

→ **KHÔNG phụ thuộc** σ'v0, chỉ phụ thuộc tải đắp $q$, chiều dày khối gia cố $H$, mô đun composite.

**S2 (lún cố kết phần dưới mũi CDM — Terzaghi 1D):**

Phân tố từ mũi CDM xuống tới $d_{stop}$, mỗi phân tố dày $h_i = 2$ m:

| Tình trạng | Công thức |
|---|---|
| **OC** (σ'vf ≤ PC) | $S_i = \dfrac{h_i \cdot C_s}{1+e_0} \cdot \log_{10}\dfrac{\sigma'_{vf}}{\sigma'_{v0}}$ |
| **cross-PC** (σ'v0 < PC < σ'vf) | $S_i = \dfrac{h_i \cdot C_s}{1+e_0} \log_{10}\dfrac{PC}{\sigma'_{v0}} + \dfrac{h_i \cdot C_c}{1+e_0} \log_{10}\dfrac{\sigma'_{vf}}{PC}$ |
| **NC** (σ'v0 ≥ PC) | $S_i = \dfrac{h_i \cdot C_c}{1+e_0} \cdot \log_{10}\dfrac{\sigma'_{vf}}{\sigma'_{v0}}$ |

trong đó:
- $\sigma'_{v0}$ tại midspan phân tố — **TÍNH THEO QUY TẮC NÀY** (effective stress + MNN)
- $\sigma'_{vf} = \sigma'_{v0} + \Delta\sigma$ — ứng suất hữu hiệu sau gia tải (Δσ giảm theo phương Boussinesq nếu cần, hoặc 1D đơn giản = q)
- $PC$ — áp lực tiền cố kết, lab hoặc giả thiết OCR
- $C_c, C_s, e_0$ — chỉ số nén, nở, hệ số rỗng (lab)

**S2 dừng cộng dồn khi:** $\Delta\sigma_i / \sigma'_{v0,i} < 10\%$ (tiêu chí TCCS 41 Phụ lục C).

---

#### 6. Tham số `gwt_depth_m` BẮT BUỘC truyền vào engine

`calc_sigma_v0(depth_mid_m, gamma_sat, gwt_depth_m)` — KHÔNG được dùng default **0.0** khi MNN không tại mặt đất.

**Quy tắc gọi:**

```python
# Truyền đúng MNN từng HK
for bh in qtt_boreholes:
    gwt_depth = max(0.0, bh.elevation_m - GWL_ELEV_QTT)  # GWL_ELEV_QTT = 0.0 m
    res = calc_s2_below_cdm(
        bh_name=bh.name,
        cdm_tip_depth_m=tip,
        q_kPa=40.8,
        gwt_depth_m=gwt_depth,  # ← BẮT BUỘC
        ...
    )
```

**Constants dự án QTT:**

```python
GWL_ELEV_QTT = 0.0   # cao độ tuyệt đối MNN (m, mốc Quốc gia)
GAMMA_W = 9.81       # dung trọng nước (kN/m³)
Q_CDM_QTT = 40.8     # tải phương án CDM (kPa)
```

---

#### 7. Verify với ND-07 (cao độ TN +3.47 m, MNN +0.00 m)

Tại độ sâu $z = 10$ m:
- $z_{gwl,ND-07} = 3.47 - 0.00 = 3.47$ m
- $\sigma_v(10) = 3 \cdot 18 + 7 \cdot 14.6 = 54 + 102.2 = 156.2$ kPa
- $u(10) = 9.81 \cdot (10 - 3.47) = 64.06$ kPa
- **$\sigma'_{v0}(10) = 156.2 - 64.06 = 92.14$ kPa**

Chart `qtt_charts.stress_chart_with_10pct` cho **92.1 kPa** ở depth 10m → khớp ✓.

Trước khi sửa (lỗi `or` truthiness với 0.0), σ'v0 = 156.2 kPa = tổng ứng suất → SAI.

---

#### 8. Tác động lên S2 đã tính trong DB

| Trước fix | Sau fix |
|---|---|
| σ'v0 = σ_v0 total (chưa trừ u) | σ'v0 = effective (đã trừ u) |
| S2 dự kiến cao hơn (do tỉ số σvf/σv0 lớn) | S2 thấp hơn ~10-20% |
| Đáy ảnh hưởng nông hơn | Đáy ảnh hưởng sâu hơn |
| Lc tối ưu ngắn hơn | Lc tối ưu dài hơn để giữ S_total ≤ ΔS |

→ Sau khi engine S2 dùng đúng σ'v0 với gwt_depth, cần **chạy lại** `save_cdm_zone_results.py` để cập nhật bảng SQLite `cdm_zone_design_results`.

---

#### 9. Quy tắc kiểm tra trước commit

Trước khi commit thay đổi tính lún:

1. Verify `calc_sigma_v0(d=10, γ=14.6, gwt_depth=3.47)` trả về giá trị giảm so với γ × d
2. Verify đáy vùng ảnh hưởng `d_stop` sâu hơn vs trước
3. Verify Lc tối ưu dài hơn (vì S2 nhỏ hơn → cọc ngắn dễ đạt → mâu thuẫn, cần xem xét cụ thể)
4. Document mọi giá trị mới trong bảng SQLite có cột `gwt_depth_m`
