# Phân vùng gia cố CDM — 7 nguyên tắc thiết kế

Tài liệu phương pháp luận **chia hố khoan thành các vùng đồng nhất** để tối ưu thông số trụ CDM, đảm bảo chuyển tiếp êm thuận, giảm số phương án thi công, và thỏa mãn yêu cầu QC mẫu thí nghiệm.

---

## Cơ sở khoa học

Mục tiêu phân vùng CDM:

- **Giảm số phương án** thi công (mỗi vùng = 1 thiết kế trụ chuẩn)
- **Tránh "bước nhảy"** chiều dài cọc / mật độ cọc giữa các đoạn liền kề
- **Đảm bảo QC**: mỗi vùng có đủ mẫu thí nghiệm cường độ ($q_u$) đại diện theo TCVN 9403 Bảng B.1
- **Kiểm soát lún cố kết còn lại** $\Delta S$ trong giới hạn TCCS 41 Bảng 1 (Điều 6.2.3)

---

## 7 Nguyên tắc P1 ↔ P7

### P1 — Địa chất đồng nhất (Ward clustering trên feature vector 6D)

Mỗi hố khoan biểu diễn bằng vector đặc trưng:

$$\mathbf{x}_i = [\,H_{soft,i},\ C_{u,i},\ N_{SPT,i},\ e_{0,i},\ C_{c,i},\ S_{1,i}\,]$$

| Thành phần | Ý nghĩa | Nguồn |
|---|---|---|
| $H_{soft}$ | Chiều dày tổng lớp đất yếu (m) | `SUM(layers WHERE symbol IN ('1','1b','2','XMD'))` |
| $C_u$ | Cường độ kháng cắt tính toán $\mu \cdot S_u$ (kPa) | VST + hiệu chỉnh Bjerrum |
| $N_{SPT}$ | SPT trung bình lớp yếu | `spt_values` |
| $e_0$ | Hệ số rỗng ban đầu | `lab_tests` |
| $C_c$ | Chỉ số nén | `lab_tests` |
| $S_1$ | Lún đàn hồi khối gia cố CDM (cm) | TCVN 9403 Phụ lục C |

**Phương pháp:** Ward hierarchical clustering trên vector đã chuẩn hóa (`StandardScaler` → z-score), cắt cây ở K cụm.

**K mặc định:** KE=3 · BXN=3 · NHC=4 (kích cỡ zone phù hợp số HK).

---

### P2 — Liên thông không gian (Delaunay edges)

Sau khi gán cluster theo P1, kiểm tra **tính liền kề trong không gian** bằng Delaunay triangulation trên (x, y) HK:

- **Edge same-zone** (hai HK kết nối thuộc cùng cluster): vẽ **màu xám liền mảnh** — OK
- **Edge cross-zone** (hai HK kết nối khác cluster): vẽ **màu đỏ đứt** — cần xem xét

**Nguyên tắc:** zone phải **liên thông** trong không gian, KHÔNG có HK "lạc loài" giữa zone khác.

---

### P3 — Tải / lún đồng nhất

$S_1$ (lún khối gia cố CDM) trong feature vector đảm bảo HK trong cùng vùng có **mức lún tương đương**.

Cross-check sau khi clustering: $\sigma(S_1)$ trong mỗi cluster < 30% TB cluster.

---

### P4 — Thi công được (Constructability)

| Tham số | Ngưỡng |
|---|---|
| Số cluster K | 3 ≤ K ≤ 8 |
| Diện tích zone tối thiểu | 100 m² |
| Shape ratio (chu vi² / diện tích) | ≥ 0,3 (zone không quá thon) |

K quá nhỏ → mỗi zone quá rộng, không tận dụng được khác biệt địa chất. K quá lớn → zone vụn vặt, khó thi công.

---

### P5 — Mẫu QC tối thiểu (TCVN 9403 Bảng B.1)

| Loại mẫu | Yêu cầu tối thiểu per zone |
|---|:---:|
| Số HK đại diện | **≥ 2** |
| Số mẫu $q_u$ (cường độ trụ CDM) | **≥ 6** |

Zone không đủ mẫu QC → **gộp với zone liền kề** (giảm K) hoặc **bổ sung khoan thăm dò + thí nghiệm**.

---

### P6 — Đa giác DXF (tương lai)

Vùng cuối cùng xuất sang DXF dạng polygon (CAD) — phục vụ thi công + nghiệm thu. **Hiện chưa implement**, là kế hoạch mở rộng.

---

### P7 — Gradient chuyển tiếp ΔS / L ≤ $i_{cp}$

Mọi cặp HK **cross-boundary** (Delaunay edge khác zone) phải thỏa độ dốc lún cho phép:

$$\dfrac{|S_{1,a} - S_{1,b}|}{L_{ab}} \leq i_{cp}$$

| Khu vực | $i_{cp}$ | Ghi chú |
|---|:---:|---|
| **KE** (kè ven sông) | **0,5%** | Đường công viên, tải hữu hạn |
| **BXN** (bãi đỗ xe ngầm) | **0,5%** | Tương tự |
| **NHC** (nhà hành chính) | **0,2%** | Gần móng nhà cao tầng — nghiêm ngặt hơn |

**Đơn vị:** $S_1$ (cm), $L$ (m) → gradient tính %.

```python
grad_pct = abs(S1_a - S1_b) / (100.0 * L_m) * 100   # % per m
pass     = grad_pct <= icp_pct
```

---

## Bố cục Section 8 trong app `tvtk_prep`

| Mục | Nội dung |
|---|---|
| **8.0 Lý thuyết** | Hiển thị toàn bộ MD này (markdown render) |
| **8a** | Bảng feature vector 6D per HK (HK / H_soft / Cu / N_SPT / e0 / Cc / S1) |
| **8b** | **Bình đồ phân vùng — màu theo cụm** (scatter Plotly + Delaunay edges) |
| **8c** | Bảng cluster statistics (số HK, TB H_soft, TB Cu, TB S1 mỗi cluster) + P5 QC check |
| **8d** | Bảng P7 gradient — mọi cặp Delaunay cross-boundary, đánh giá pass/fail |
| **8e** | Bảng QC tổng hợp (n_HK, n_qu_samples per zone vs ngưỡng B.1) |

---

## Thư viện sử dụng

- `scipy.cluster.hierarchy.linkage(method='ward')` + `fcluster` — cắt K cụm
- `scipy.spatial.Delaunay` — triangulation 2D
- `sklearn.preprocessing.StandardScaler` — z-score normalize

**Không cần:** `libpysal`, `spopt` — quá nặng, cài đặt khó trên Cloud.

---

## SQLite — Bảng `cdm_zoning_clusters`

| Cột | Type | Mô tả |
|---|---|---|
| `id` | INTEGER PK | Auto |
| `bh_name` | TEXT | `KE-HK1`... |
| `zone` | TEXT | `KE` / `BXN` / `NHC` |
| `cluster_id` | INTEGER | 1..K |
| `K` | INTEGER | Số cluster của zone |
| `H_soft_m` | REAL | Feature: H_soft |
| `Cu_kPa` | REAL | Feature: Cu (Bjerrum) |
| `N_spt` | REAL | Feature: N SPT |
| `e0` | REAL | Feature: e0 |
| `Cc` | REAL | Feature: Cc |
| `S1_cm` | REAL | Feature: S1 |
| `run_id` | TEXT | UUID phiên clustering |
| `ts` | TEXT | datetime |
| **UNIQUE** | `(bh_name, run_id)` | |

---

## Liên kết

- [scripts/cdm_zoning.py](scripts/cdm_zoning.py) — engine clustering
- [scripts/app_cdm.py](scripts/app_cdm.py) tab `tvtk_prep` Section 8 — UI
- [38-tccs41-nen-duong-dat-yeu.md](38-tccs41-nen-duong-dat-yeu.md) — TCCS 41 Bảng 1 (Điều 6.2.3) — ΔS limits + Bjerrum C.5
- [54-tvtk-cdm-prep.md](54-tvtk-cdm-prep.md) — tab TVTK CDM
- [CLAUDE.md](CLAUDE.md) §34 (TVTK CDM), §36 (Bjerrum), §42 (Phân vùng CDM — mục này)
