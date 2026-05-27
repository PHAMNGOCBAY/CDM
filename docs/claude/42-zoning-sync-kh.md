### 42. Phân vùng gia cố CDM — 7 nguyên tắc P1–P7

**File tài liệu:** [55-cdm-zoning-principles.md](55-cdm-zoning-principles.md)
**Module Python:** `scripts/cdm_zoning.py` (Ward clustering + Delaunay + P5/P7 check)
**SQLite:** `cdm_zoning_clusters` (UNIQUE `(bh_name, run_id)`)
**UI:** `scripts/app_cdm.py` tab `tvtk_prep` Section 8 — sau Section 6 (Mực nước ngầm)

#### 7 nguyên tắc

| Nguyên tắc | Nội dung |
|---|---|
| **P1 Địa chất đồng nhất** | Feature vector 6D `[H_soft, Cu, N_SPT, e0, Cc, S1]` → StandardScaler → Ward clustering (scipy.cluster.hierarchy) |
| **P2 Liên thông không gian** | Delaunay triangulation (scipy.spatial) — edges xám same-cluster, đỏ đứt cross-boundary |
| **P3 Tải/lún đồng nhất** | S₁ trong feature vector |
| **P4 Thi công được** | 3 ≤ K ≤ 8, area ≥ 100 m², shape ratio ≥ 0,3 |
| **P5 Mẫu QC** | ≥ 2 HK + ≥ 6 mẫu qu/cụm (TCVN 9403 Bảng B.1); qu samples chia pro-rata theo HK trong cụm |
| **P6 Polygon DXF** | (tương lai) |
| **P7 Gradient** | `|ΔS₁/L| ≤ i_cp` cho mọi cặp Delaunay cross-boundary; i_cp = 0,5% (KE/BXN) hoặc 0,2% (NHC — gần nhà cao tầng) |

#### Symbols filter

- **Lớp yếu cho H_soft:** `('1','1b','2','XMD')` (`layers.symbol`)
- **Lớp yếu cho Ip:** `('1','1b','CH','MH','CH-OH','MH-OH')` (`lab_tests.symbol_tcvn`)

#### Bố cục Section 8

| Mục | Nội dung |
|---|---|
| **8.0** | **Lý thuyết** — expander render trực tiếp từ MD file 55-cdm-zoning-principles.md |
| **8.1** | Radio chọn zone + slider K (2–6) + input i_cp (%) |
| **8a** | Bảng feature vector 6D per HK + cột Cụm |
| **8b** | **Bình đồ phân vùng — màu theo cụm** (Plotly scatter + Delaunay edges) |
| **8c** | Đặc trưng cụm + P5 check (đạt/không đạt mỗi cụm + ngưỡng) |
| **8d** | P7 gradient — bảng cross-boundary edges với pass/fail |
| **8e** | Nút lưu kết quả vào `cdm_zoning_clusters` với run_id mới |

#### API

```python
from scripts.cdm_zoning import (
    build_features_for_zone, run_clustering, delaunay_edges,
    check_P5_qc, check_P7_gradient, save_clusters_to_db,
    I_CP_BY_ZONE, K_DEFAULT_BY_ZONE,
)
feats = build_features_for_zone('KE')         # list[dict] 6D
clusters = run_clustering(feats, K=3)          # [1,2,3,...] Ward
edges = delaunay_edges([(f['x'],f['y']) for f in feats])
p5 = check_P5_qc(feats, clusters, zone_code='KE')
p7 = check_P7_gradient(feats, clusters, edges, icp_pct=0.5)
run_id = save_clusters_to_db('KE', feats, clusters, K=3)
```

#### Constants

```python
I_CP_BY_ZONE      = {"KE": 0.5, "BXN": 0.5, "NHC": 0.2}   # % per m
K_DEFAULT_BY_ZONE = {"KE": 3,   "BXN": 3,   "NHC": 4}
```

#### Style hiển thị bình đồ

- **Cụm 1–8:** màu `#1565C0 #D32F2F #2E7D32 #F57F17 #6A1B9A #00838F #AD1457 #558B2F`
- **Marker HK:** circle size 16, viền trắng width 2
- **Delaunay same-cluster:** line xám `#BBBBBB` width 1.2 liền
- **Delaunay cross-boundary:** line đỏ `#D32F2F` width 2.0 đứt (dot)
- **Aspect ratio:** `scaleanchor='x', scaleratio=1` (tỷ lệ thật)

---

### 42b. Auto-sync worktree → main local (BẮT BUỘC sau mỗi commit)

**File:** `sync_local.py` + `sync_local.bat` + `watch_local.bat` (project root)

#### Vấn đề

Khi Claude làm việc trong **worktree** (`.claude/worktrees/<name>/`), code chỉ có ở worktree. Streamlit local (port 8503) đọc từ `<root>/scripts/`. **Phải copy worktree → main scripts/** để local thấy update.

#### Lệnh

```bash
# One-shot sync (sau mỗi commit worktree)
python sync_local.py

# Watch mode (chạy nền — auto sync mỗi 2s)
python sync_local.py --watch
```

Hoặc double-click `sync_local.bat` / `watch_local.bat`.

#### Logic `sync_local.py`

1. Tự tìm worktree đang active trong `.claude/worktrees/`
2. `git diff --name-only origin/main..HEAD` → lấy danh sách file branch đã sửa
3. Copy từng file `worktree/<f>` → `root/<f>` (chỉ khi khác size/mtime)
4. Streamlit `--server.runOnSave=true` tự reload

#### Quy ước workflow Claude (BẮT BUỘC)

Sau mỗi `git commit && git push` trong worktree:

```bash
python "G:/My Drive/AI-SUC TAI COC THEO DAT NEN/sync_local.py"
```

→ Đảm bảo http://localhost:8503 luôn có code mới nhất.

#### Watch mode

`watch_local.bat` chạy 1 lần đầu phiên, sau đó tự sync mọi file thay đổi trong worktree mỗi 2s — không cần chạy manual nữa.

---

### 43. Hệ số nền $k_h$ Winkler dùng Cu tính toán Bjerrum (BẮT BUỘC)

**File tài liệu:** [56-ke-sw-kh-from-cu-tinh-toan.md](56-ke-sw-kh-from-cu-tinh-toan.md)
**JSON config:** `data/tccs41_params.json` → `tccs41_limits.kh_winkler_from_cu_calc`
**Python:** `scripts/wall_internal_force.py` `kh_clay_matlock()` + 3 caller trong `app_cdm.py`

#### Quy tắc bắt buộc

`kh_clay_matlock(z, D, Su_kPa, ...)` — **tham số `Su_kPa` PHẢI là $c_u$ tính toán** = $\mu \cdot S_u$ theo TCCS 41 Phụ lục C.3.2 — Công thức C.5. **KHÔNG truyền $S_u$ VST nguyên** — kết quả $k_h$ sẽ quá lớn ~10–15%.

#### Thứ tự ưu tiên $c_u$ khi build `SoilLayer`

| Ưu tiên | Nguồn | Tag |
|:---:|---|:---:|
| 1 | **VST + Bjerrum** (Cu = μ·$\overline{S_u}_{VST}$ trong phạm vi lớp) | `'VST+mu'` |
| 2 | Lab UU (`lab_tests.Cu_UU_kPa`) | `'UU'` |
| 3 | $c$ direct shear (`lab_tests.c_kPa`) | `'shear_c'` |
| 4 | Mặc định 11,0 kPa | `'default'` |

#### Pattern khi build SoilLayer (3 nơi trong app_cdm.py)

```python
# 1. Ip TB cho HK (1 lần)
ip_avg = SELECT AVG(Ip) FROM lab_tests WHERE bh=? 
         AND symbol_tcvn IN ('1','1b','CH','MH','CH-OH','MH-OH')
mu = bjerrum_mu(ip_avg)

# 2. Per layer: Su VST trong phạm vi depth_top..depth_bot
for layer in layers:
    su_vst = SELECT AVG(v.Su_kPa) FROM vane_shear_tests v
             JOIN vst_locations vl ON v.vst_loc_id = vl.id
             WHERE vl.name = bh AND v.depth_m BETWEEN top AND bot
    cu = (su_vst * mu) if su_vst else (Cu_UU or c_kPa or 11.0)
    SoilLayer(Su_kPa=cu, ...)   # truyền Cu tính toán, không Su gốc
```

#### Vị trí code 3 caller

| Line app_cdm.py | Mục đích | Status |
|:---:|---|:---:|
| ~9930 | `_solve_pynite()` builder Winkler chính | Đã sửa |
| ~11650 | Winkler tải phân bố Boussinesq (D.1) | Đã sửa |
| ~12166 | `drained_layers` Back (lò xo phía Back) | Đã sửa |

#### Caption công thức kh UI

```latex
k_h = \dfrac{p_u}{y_{50}} = \dfrac{N_p \cdot c_u}{2{,}5 \cdot \varepsilon_{50}} \quad [\text{kN/m}^3]
```

với chú thích: "**Cu tính toán** = μ·Su_VST theo TCCS 41 Phụ lục C.3.2 (Công thức C.5). KHÔNG dùng Su VST nguyên — sẽ cho kh quá lớn ~10–15%."

#### Sample verify KE-HK2

- Ip TB lớp yếu = 35,9 → μ = 0,887
- Su VST lớp 1 = 12,9 → **Cu = 11,45 kPa**
- $N_p = 5,18$, $D = 0,84$ m, $\varepsilon_{50} = 0,02$
- **$k_h$ = 1186 kN/m³** (vs 1338 kN/m³ nếu dùng Su nguyên — **chênh +12,8%**)
