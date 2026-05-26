# Hệ số nền $k_h$ tính từ Cu tính toán (Bjerrum) — Cừ ván SW

Tài liệu cập nhật công thức $k_h$ Winkler trong tab **Cọc ván SW (Kè)** để dùng **cường độ kháng cắt tính toán** $c_u = \mu \cdot S_u$ theo TCCS 41:2022 Phụ lục C.3.2 (Công thức C.5), KHÔNG dùng $S_u$ VST nguyên hay $C_u$ UU phòng.

---

## 1. Bối cảnh

Trước đây, code Winkler trong `wall_internal_force.kh_clay_matlock()` nhận `Su_kPa` từ:
- **Lab UU test** (`lab_tests.Cu_UU_kPa`) — phổ biến nhất
- Hoặc `c_kPa` (lực dính trực tiếp đẳng cấp với Su trong sét yếu)

Trong khi đó, biểu đồ VST đã được cập nhật hiển thị **Cu tính toán** = $\mu \cdot S_u$ theo TCCS 41 C.5. Hai dòng dữ liệu này **không nhất quán**:
- Biểu đồ VST: hiển thị $C_u = \mu \cdot S_u$ ≈ 13–18 kPa (KE)
- Tính kh: dùng $S_u$ VST hoặc $C_u$ UU lab ≈ 11–22 kPa (không thống nhất)

→ Cần **thống nhất** dùng $C_u = \mu \cdot S_u$ ở mọi nơi: biểu đồ + tính kh + ổn định.

## 2. Công thức (Matlock 1970 + TCCS 41 C.5)

$$k_h = \dfrac{p_u}{y_{50}} = \dfrac{N_p \cdot c_u}{2{,}5 \cdot \varepsilon_{50}} \quad [\text{kN/m}^3]$$

trong đó:

| Ký hiệu | Ý nghĩa | Đơn vị |
|---|---|---|
| $N_p$ | $\min(3 + \gamma' z / \max(c_u, 1),\ 9)$ — hệ số khả năng chịu tải | — |
| $c_u$ | **Cường độ kháng cắt tính toán** = $\mu \cdot S_u$ (Bjerrum C.5) | kPa |
| $\mu$ | Hệ số hiệu chỉnh Bjerrum tra Bảng C.1 theo $I_p$ TB lớp yếu | — |
| $S_u$ | Cường độ kháng cắt nguyên trạng VST | kPa |
| $D$ | Bề rộng / đường kính cừ | m |
| $\varepsilon_{50}$ | Biến dạng tại 50% $q_u$, mặc định 0,02 | — |
| $z$ | Độ sâu | m |
| $\gamma'$ | Dung trọng đẩy nổi | kN/m³ |

**Ảnh hưởng:** $\mu \in [0,70;\ 1,09]$ → $k_h$ thay đổi ±10–30% so với dùng $S_u$ nguyên.

## 3. Thứ tự ưu tiên (BẮT BUỘC nhất quán toàn dự án)

Khi build `SoilLayer` cho Winkler, lấy $c_u$ theo thứ tự:

| Ưu tiên | Nguồn | Công thức | Source tag |
|---|---|---|---|
| **1** | VST + Bjerrum (TCCS 41 C.5) | $c_u = \mu \cdot \overline{S_u}_{VST}$ trong phạm vi lớp | `'VST+mu'` |
| 2 | Lab UU (`lab_tests.Cu_UU_kPa`) | $c_u = \overline{C_u}_{UU}$ | `'UU'` |
| 3 | $c$ direct shear | $c_u = c$ | `'shear_c'` |
| 4 | Mặc định | 11,0 kPa | `'default'` |

**Ip TB** tính từ `lab_tests.Ip` của lớp yếu (`symbol_tcvn IN ('1','1b','CH','MH','CH-OH','MH-OH')`) cho cả HK (1 giá trị/HK).

## 4. Triển khai trong code

### `scripts/wall_internal_force.py` — docstring rõ ràng

```python
def kh_clay_matlock(z_m, D_m, Su_kPa, gamma_kNm3, eps50=0.02):
    """QUAN TRỌNG: Su_kPa phải là Cu TÍNH TOÁN = μ × Su_VST
    theo TCCS 41 Phụ lục C.3.2 C.5. KHÔNG truyền Su VST nguyên."""
```

### `scripts/app_cdm.py` — 3 nơi build SoilLayer

| Vị trí | Mục đích | Sửa đổi |
|---|---|---|
| `~line 9930` (`_solve_pynite` builder) | Winkler chính | Query Su VST per layer + áp Bjerrum |
| `~line 11650` (`Winkler tải phân bố` D.1) | Tải phân bố Boussinesq | Query Su VST per layer + áp Bjerrum |
| `~line 12166` (`drained_layers` Back) | Lò xo Back | Query Su VST per layer + áp Bjerrum |

**Pattern chung:**
```python
# 1. Lấy Ip TB cho HK (1 lần)
ip_avg = SELECT AVG(Ip) FROM lab_tests WHERE bh=? AND symbol_tcvn IN soft
mu = bjerrum_mu(ip_avg)

# 2. Per layer: query Su VST trung bình trong phạm vi
for layer in layers:
    su_vst = SELECT AVG(Su_kPa) FROM vane_shear_tests
             WHERE vl.name=bh AND depth IN [layer.top, layer.bot]
    cu = su_vst * mu if su_vst else (Cu_UU if Cu_UU else c_kPa)
    soil_layer = SoilLayer(Su_kPa=cu, ...)
```

## 5. Caption công thức UI cập nhật

| Trước | Sau |
|---|---|
| $k_h = \dfrac{67 \cdot S_u}{d_{pile}}$ (API Clay đơn giản) | $k_h = \dfrac{N_p \cdot c_u}{2{,}5 \cdot \varepsilon_{50}}$ với $c_u = \mu \cdot S_u$ (TCCS 41 C.5) |

App thêm `st.caption` ghi rõ: "Cu tính toán = μ·Su_VST theo TCCS 41 Phụ lục C.3.2. KHÔNG dùng Su VST nguyên — sẽ cho kh quá lớn ~10–15%."

## 6. Kết quả số học — ví dụ KE-HK2

| Tham số | Giá trị |
|---|:---:|
| Ip TB lớp yếu | 35,9 |
| μ Bjerrum | 0,887 |
| Su VST TB lớp 1 | 12,9 kPa |
| **Cu = μ·Su** | **11,45 kPa** ← dùng cho kh |
| z = 5 m, D = 0,84 m, γ' = 5 kN/m³ | |
| $N_p = \min(3 + 5·5/11{,}45;\ 9) = 5{,}18$ | |
| $p_u = 5{,}18 \cdot 11{,}45 \cdot 0{,}84 = 49{,}8$ kN/m | |
| $y_{50} = 2{,}5 \cdot 0{,}02 \cdot 0{,}84 = 0{,}042$ m | |
| **$k_h = 49{,}8 / 0{,}042 = 1186$ kN/m³** | |

So với dùng Su = 12,9 (không Bjerrum): $k_h = 1338$ kN/m³ — chênh **+12,8%** so với chuẩn TCCS 41.

## 7. Liên kết

- [38-tccs41-nen-duong-dat-yeu.md](38-tccs41-nen-duong-dat-yeu.md) §3b — Công thức C.5 + Bảng C.1 Bjerrum
- [47-tvtk-cdm-trac-doc-luong-chinh.md](47-tvtk-cdm-trac-doc-luong-chinh.md) — Cu trên biểu đồ VST
- [scripts/wall_internal_force.py](scripts/wall_internal_force.py) — `kh_clay_matlock()`
- [scripts/app_cdm.py](scripts/app_cdm.py) — 3 nơi build SoilLayer
- [CLAUDE.md](CLAUDE.md) §36 (Bjerrum), §43 (mục này — kh từ Cu tính toán)
