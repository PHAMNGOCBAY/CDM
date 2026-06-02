### 65. PLAXIS 2D Remote Scripting — API skills + Push từ SQLite

**Files engine:**
- [scripts/plaxis_connect.py](scripts/plaxis_connect.py) — connect API (port 10000 Input / 10001 Output)
- [scripts/plaxis_push_borehole.py](scripts/plaxis_push_borehole.py) — push 1 HK đơn + log
- [scripts/plaxis_push_zone_v2.py](scripts/plaxis_push_zone_v2.py) — **CHÍNH** push cả zone với GLOBAL layers (đúng API)

**SQLite:**
- `cdm_plaxis_push_log` — log mọi lần push (zone, BH, x, layers, status, file)
- `plaxis_api_reference` — bảng tra cứu tên attribute + writable + notes

**JSON config:** [data/plaxis_api_reference.json](data/plaxis_api_reference.json)

**MCP:** dùng `sqlite-tthc` và `sqlite-tthc-drive` server (xem `.mcp.json`) — không có MCP riêng cho PLAXIS.

#### Setup kết nối

1. PLAXIS 2D GUI → **Expert → Configure remote scripting server**
2. Set password (vd `+g=GW5R>A9WY?He7`) + Port 10000 → **Start server**
3. Trong shell:
   ```powershell
   $env:PLAXIS_PASSWORD = '<password>'
   ```
4. Chạy script connect — code dùng `plxscripting.easy.new_server(host, port, password=...)`.

Port 10001 (Output Viewer) chỉ chạy sau khi Calculate hoặc khi Output Viewer được mở thủ công.

#### API skills (đã verify thực tế qua probe)

##### Tên attribute (CHÍNH XÁC — PascalCase / mixedCase, KHÔNG phải snake_case)

| Saỉ | Đúng | Model | Ghi chú |
|---|---|---|---|
| `Eref` | **`ERef`** | Mohr-Coulomb | mô đun đàn hồi (kN/m²) |
| `cref` | **`cRef`** | MC + SS | lực dính (kN/m²) |
| `Eoed` | **`EOed`** | MC | oedometer modulus |
| `lambda_star` | **`lambdaModified`** | Soft Soil | λ* = Cc / [2.303(1+e₀)] |
| `kappa_star` | **`kappaModified`** | Soft Soil | κ* = Cs / [2.303(1+e₀)] |
| `nuur` | **`nuUR`** | Soft Soil | Poisson unloading-reloading |
| `nu` | `nu` | MC | OK |
| `phi`, `psi` | `phi`, `psi` | MC, SS | OK |
| `gammaUnsat`, `gammaSat` | OK | tất cả | OK |
| `DrainageType` | OK | tất cả | string (xem dưới) |
| `Identification` | OK | tất cả | tên material |
| `SoilModel` | OK | tất cả | xem dưới |

##### Attribute READ-ONLY (KHÔNG được set)

| Attribute | Khi nào | Lý do |
|---|---|---|
| `M` | Soft Soil | Auto computed = 6 sinφ / (3 − sinφ) |
| `EOed` | Soft Soil | Auto từ λ* và σ' |
| `psi` | MC khi DrainageType ≠ "drained" | Undrained mặc định ψ=0 |
| `Top` | mọi SoilLayer.Zones[bh] | Auto derived từ Bottom layer trên + Head |

##### Giá trị hợp lệ — `SoilModel`

`"Mohr-Coulomb"`, `"Soft Soil"`, `"Hardening Soil"`, `"HS small"`, `"Soft Soil Creep"`, `"Mohr-Coulomb (advanced)"`, `"Linear Elastic"`, `"User-defined"`...

##### Giá trị hợp lệ — `DrainageType`

- **Mohr-Coulomb:** `"drained"`, `"undraineda"`, `"undrainedb"`, `"undrainedc"`, `"nonporous"`
- **Soft Soil:** CHỈ `"drained"`, `"undraineda"` (KHÔNG có undrainedb)

##### Borehole + SoilLayer geometry (PLAXIS 2D)

```python
# Tạo borehole
bh = g_i.borehole(x_in_plot)
bh.Head = 2.7   # cao độ Y của đỉnh BH (top of fill)

# Tạo SoilLayer là GLOBAL, KHÔNG per-BH
g_i.soillayer(thickness)   # thêm 1 layer global mới
# Layers chia sẻ giữa MỌI Borehole — mỗi BH có 1 zone trong layer

# Access per-BH zone
layer = g_i.SoilLayers[i]
zones = list(layer.Zones)  # PlxProxyIPObject, 1 zone / BH
zones[bh_idx].Bottom = y_value   # set Y của đáy layer cho BH này
# zones[bh_idx].Top = ...   # READ-ONLY, auto = Bottom layer trên (hoặc Head cho layer 0)
```

##### Lệnh mode

```python
g_i.gotosoil()          # vào chế độ Soil/Stratigraphy
g_i.gotostructures()    # mode Structures
g_i.gotomesh()          # Mesh mode
g_i.gotostages()        # Staged Construction
```

##### Project lifecycle

```python
s_i, g_i = new_server(host, port, password=pwd)
s_i.new()               # tạo project trống
s_i.open(path)          # mở file .p2dx
g_i.save(path)          # LƯU file .p2dx (KHÔNG phải s_i.save — không tồn tại)
s_i.close()             # đóng connection (project vẫn mở trong GUI)
```

##### Probe project active

```python
try:
    n = len(g_i.Boreholes)   # hoặc g_i.SoilLayers
except Exception:
    # "No active project" — cần s_i.new() hoặc s_i.open()
    s_i.new()
```

##### setmaterial — gán vật liệu cho global layer

```python
m = g_i.soilmat()
m.SoilModel = "Mohr-Coulomb"
m.Identification = "MAT_NAME"
m.gammaUnsat = 18.0
# ... set các attr khác
g_i.setmaterial(g_i.SoilLayers[i], m)   # gán cho global layer
```

#### Workflow push HK từ SQLite (đúng v2/v3)

```
1. Đọc TẤT CẢ HK selected của zone từ tvtk_bh_cdm + boreholes
2. Đọc layers + lab_tests + spt_values cho mỗi HK
3. Union symbol → list GLOBAL layers (sort theo depth_TB tăng dần)
   prepend "__FILL__" làm layer 0
4. Cho mỗi global layer: aggregate lab data từ tất cả HK có symbol đó
   → 1 material đại diện
5. Map symbol → model:
   - SOFTSOIL_SYMBOLS = {"1", "1b", "XMD"} → SoftSoil
   - SAND_SYMBOLS = {"F", "2a", "2b", "2c", "3a", "3b", "3c", "4",
                     "5", "5a", "5b", "6", "7", "8"} → MC drained
   - Còn lại → MC undraineda (sét)
6. PLAXIS:
   a. s_i.new()
   b. g_i.gotosoil()
   c. Tạo BH[0] tại x=0, Head=DESIGN_ELEV_FILL (2.7)
   d. g_i.soillayer(0) × N → tạo N global layers (0 thickness)
   e. Tạo N materials + g_i.setmaterial(layer, mat)
   f. Set Bottom cho BH[0]: list(layer.Zones)[0].Bottom = y_bot
   g. Cho mỗi BH tiếp theo: g_i.borehole(x), Head=2.7, set Bottom qua Zones
   h. g_i.save(path)
7. Log mỗi lần push vào cdm_plaxis_push_log
```

#### Quy tắc Y coordinate (cao độ tự nhiên)

- `Head = DESIGN_ELEV_FILL = 2.7` cho MỌI borehole (đỉnh đắp)
- Layer 0 (FILL): `Bottom = nat_elev` của BH → thickness = 2.7 − nat
- Layer i (i > 0, symbol thực): `Bottom = nat_elev − depth_bot_in_BH`
- Lớp KHÔNG có trong BH → `Bottom = Bottom layer trên` (zero thickness)
- Y monotonic giảm xuống dưới (Y dương lên)

#### Soft Soil parameters mapping từ lab data

```python
lambda_modified = Cc / (2.303 × (1 + e0))
kappa_modified  = Cs / (2.303 × (1 + e0))   # ≈ λ*/10 nếu Cs không có
M               = AUTO (PLAXIS tự tính từ φ)
OCR             = 1.0   # NC mặc định cho bùn yếu
POP             = 0.0
nuUR            = 0.15
gammaUnsat,
gammaSat        = từ lab_tests.gamma_kNm3
cRef            = max(Cu, c_lab, 1.0)   # > 0 yêu cầu của PLAXIS
phi             = lab.phi_deg hoặc 22° mặc định bùn
DrainageType    = "undraineda"   # CHỈ a, KHÔNG b cho SS
```

#### Mohr-Coulomb parameters

**Sét (clay) undrained:**
```python
DrainageType    = "undraineda"   # hoặc "undrainedb"
cRef            = Cu (kPa)
phi             = 0  (undrained)
ERef            = 250 × Cu (Mesri)
nu              = 0.35
gammaUnsat,
gammaSat        = từ lab
# psi không set (read-only khi undrained)
```

**Cát (sand) drained:**
```python
DrainageType    = "drained"
cRef            = max(c_lab, 0.1)   # PLAXIS yêu cầu > 0
phi             = 27 + 0.3 × N_SPT (clamp 28-40°)
ERef            = 2000 × N_SPT (α_sand = 2000 kPa per TCVN)
psi             = max(0, phi - 30)
nu              = 0.30
```

**Đất đắp FILL:**
```python
DrainageType    = "drained"
gammaUnsat      = 18.0
gammaSat        = 20.0
nu              = 0.30
ERef            = 25000
cRef            = 1.0
phi             = 32
psi             = 2
Identification  = "FILL_dap_2.7m"
```

#### Lệnh CLI

```bash
# Test connect (in trạng thái Input/Output server)
python scripts/plaxis_connect.py

# Push 1 HK đơn
python scripts/plaxis_push_borehole.py BXN-CV-HK1 \
    --save "plaxis_out/test.p2dx"

# Push cả zone với GLOBAL layers + FILL + SoftSoil (CHÍNH)
python scripts/plaxis_push_zone_v2.py KE_levee \
    --save "plaxis_out/KE_levee.p2dx"

# Dry-run kế hoạch
python scripts/plaxis_push_borehole.py NHC-BH-03 --dry-run
```

#### Schema bảng log

```sql
CREATE TABLE cdm_plaxis_push_log (
    bh_name TEXT, zone_code TEXT,
    push_timestamp TEXT,
    plaxis_x REAL, plaxis_head_m REAL,
    n_layers INTEGER, n_materials_ok INTEGER, n_materials_total INTEGER,
    file_path TEXT, status TEXT, note TEXT,
    PRIMARY KEY (bh_name, push_timestamp)
);

CREATE TABLE plaxis_api_reference (
    attribute_name TEXT,
    soil_model TEXT,         -- MC, SoftSoil, * (chung)
    writable INTEGER,        -- 0/1
    value_type TEXT,         -- float, string, enum
    allowed_values TEXT,     -- danh sách comma-separated nếu enum
    notes TEXT,
    PRIMARY KEY (attribute_name, soil_model)
);
```

#### Common pitfalls

1. **Snake_case attribute names** → "attribute not present" → dùng PascalCase đúng
2. **Set `Top` cho Zone** → read-only error → chỉ set `Bottom`
3. **Set `M` cho SoftSoil** → read-only → skip (PLAXIS tự tính)
4. **`psi` cho MC undrained** → read-only → if-check drainage trước khi set
5. **`undrainedb` cho SoftSoil** → invalid → dùng `undraineda`
6. **Per-BH soillayer call** → tăng global layer count → dùng Zones[bh_idx].Bottom
7. **`s_i.save()`** → method không tồn tại → dùng `g_i.save()`
8. **`gotostructures()`** trên project trống → no project → `s_i.new()` trước

#### Phase tiếp theo (chưa implement)

- `plaxis_add_phases.py` — tạo K0_init → Plastic đắp → Consolidation 15 năm
- `plaxis_compare_tccs41.py` — query u_y từ PLAXIS Output, so với S từ `cdm_zone_design_results`
- Push 4 zone còn lại (QTT/BXN/NHC/KE_park) với v2/v3 logic
