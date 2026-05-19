# 20 — UI Design Specification — Lateral Pile Analysis App

**App:** `scripts/app_coc_tai_ngang.py`  
**Reference screenshots:** `giao dien/01-05-UI-*.png` (GEO5 Headwall module)  
**Data spec:** `data/ui_design_spec.json`  
**Rule:** All UI labels in English following GEO5 naming convention.

---

## §20.1 Design Principles

| Principle | Rule |
|-----------|------|
| Language | English — all tab names, field labels, column headers, buttons |
| Layout | Top tabs + left form (40%) + right live diagram (60%) |
| Diagram | Updates on every input change — no "Refresh" needed |
| Table inputs | `st.data_editor` with `num_rows="dynamic"` — GEO5-style spreadsheet |
| Pile catalog | Scrollable read-only table + `st.selectbox` to highlight selected row |
| Buttons | "Calculate" (primary), "Export CSV", "Reset" |
| Error messages | English, shown with `st.error()` |

---

## §20.2 Tab Structure

Tab order (sidebar radio, top → bottom):

| # | Tab | Content |
| --- | --- | --- |
| 1 | **Geo Data** | Pile geometry, soil levels, water level, fill properties (density/phi/c/slope H:V), earth support, live schematic |
| 2 | **Soil Layers** | Two independent tables: "Layers in Front" + "Layers behind", soil profile diagram |
| 3 | **Concentrated Forces** | Force table (H, V, depth) + quick head-load inputs |
| 4 | **Boussinesq** | Strip surcharge table + diagram preview |
| 5 | **Sheet Pile Section** | SW catalog list, concrete grade, PLAXIS parameters, cross-section drawing |
| 6 | **Bearing Capacity** | Axial pile capacity — 4 methods (Nordlund/Tomlinson/Beta/Auto) in parallel, CVD charts, comparison bar chart |
| 7 | **Sheet Pile Design** | Cantilever/anchored sheet pile design, earth pressure diagram, lateral force calculation |
| 8 | **Slope Stability** | Limit equilibrium — 4 methods, R through pile tip constraint, grid search |
| 9 | **P-y** | Lateral pile analysis — openpile, API Sand/Clay, component analysis |

Navigation: `st.sidebar.radio("Navigation", _PAGES)` — vertical list, NOT `st.tabs()`.

---

## §20.3 Field Name Mapping

| GEO5 Label | Our Label | Key | Unit | Notes |
|------------|-----------|-----|------|-------|
| Sheet Pile Top Level | Pile Top Level | `top_elev` | m | elevation, negative = below datum |
| Soil Level in Front | Soil Level | `soil_level` | m | ground surface elevation |
| Water Level in Front | Water Level | `water_level` | m | phreatic level |
| — | Pile Length | `L_m` | m | derived: top_elev − L_m = pile tip |
| Earth Support | Earth Support | `bc_type` | — | Fixed / Free / Cantilever |
| Layer Tip [m] | Layer Tip [m] | column | m | elevation at layer bottom |
| Density Moist | Density Moist [kN/m3] | column | kN/m³ | moist unit weight |
| Density Submerged | Density Sub [kN/m3] | column | kN/m³ | auto = Moist − 10.0 |
| Phi [Deg] | Phi [Deg] | column | ° | friction angle |
| Delta [Deg] | Delta [Deg] | column | ° | interface friction (future) |
| Cohesion [kN/m2] | Cohesion [kN/m2] | column | kN/m² | undrained/drained cohesion |
| Horiz. Component | Horiz. Component [kN/m] | column | kN/m | lateral load per meter wall |
| Vert. Component | Vert. Component [kN/m] | column | kN/m | vertical load per meter wall |
| Depth Horiz. Comp. | Depth [m] | column | m | depth from pile top (positive down) |
| Distance Wall | Distance Wall [m] | column | m | Boussinesq surcharge distance |
| Width Surcharge | Width Surcharge [m] | column | m | |
| Depth Surcharge | Depth Surcharge [m] | column | m | |
| Surcharge | Surcharge [kN/m2] | column | kN/m² | |
| Sheet Pile list | SW catalog table | — | — | 19 SW pile types from BETON 6 |
| Steel Grades | Concrete Grade | `concrete_grade` | — | f'c = 30/40/60/70 MPa |
| Requested Safety | Requested Safety | `safety` | — | default 1.5 |

---

## §20.4 Soil Layers Table Design

**Layer tip approach** (matching GEO5): user inputs only the bottom elevation of each layer.  
Layer tops are derived automatically:

```
Layer 1 top = Pile Top Level  (from Geo Data)
Layer 2 top = Layer 1 Tip
Layer N top = Layer (N-1) Tip
```

This means the table has **one fewer column** than a full top+bottom table, reducing input burden.  
Internally, `_get_layers()` reconstructs `(name, z_top, z_bot, gamma, phi)` tuples for openpile.

**Automatic Density Sub checkbox:** when checked, `Density Sub [kN/m3]` column is disabled and auto-filled as `Density Moist − 10.0`. Matches GEO5 "Automatic Kph Values" concept.

---

## §20.5 Sheet Pile Section Tab

Adapted from GEO5 "Sheet Pile Section" tab (reference: `giao dien/05-UI-Sheet Pile Section.png`).

### SW Pile Catalog List

Displays all 19 BETON 6 SW pile types in a scrollable table:

| Column | Source field | Unit |
|--------|-------------|------|
| Name | `name` | — |
| H [mm] | `H_mm` | mm — pile section height |
| t [mm] | `t_mm` | mm — wall thickness |
| n strands | `n_strands` | — |
| phi [mm] | `phi_strand_mm` | mm |
| Atd [cm2] | `Atd_cm2` | cm² — transformed section area |
| Itd [cm4] | `Itd_cm4` | cm⁴ — transformed moment of inertia |
| Mcr [T.m] | `Mcr_Tm` | T.m — cracking moment |
| Weight [T] | `weight_T` | T/pile at L_std |
| L min [m] | `L_min_m` | m |
| L max [m] | `L_max_m` | m |
| Width [mm] | `width_mm` | mm — spacing when touching |

**Selection:** `st.selectbox` drives which row is highlighted (blue background).  
Pile width (996 mm or 1246 mm for SW-1100/1200) is the PLAXIS spacing.

### Concrete Grade (analogous to GEO5 "Steel Grades")

| Grade | f'c [MPa] | Ec [MPa] | Ec [kN/m²] |
|-------|-----------|---------|------------|
| f'c = 30 MPa | 30 | 26,561 | 26,561,000 |
| f'c = 40 MPa | 40 | 31,623 | 31,623,000 |
| f'c = 60 MPa | 60 | 38,730 | 38,730,000 |
| **f'c = 70 MPa** | **70** | **43,628** | **43,628,130** |

Default: f'c = 70 MPa (standard for BETON 6 SW piles).

### Auto-computed PLAXIS Parameters

```
spacing_m = width_mm / 1000
EA1   = Ec [kN/m²] × Atd [m²] / spacing_m    [kN/m]
EI    = Ec [kN/m²] × Itd [m⁴] / spacing_m    [kN.m²/m]
d_eq  = sqrt(12 × EI / EA1)                   [m]
w     = weight_T × 9.81 / L_std / spacing_m   [kN/m/m]
Mcr   = Mcr_Tm × 9.81                         [kN.m]
```

### Pile Length Constraint

Pile Length input is constrained to `[L_min, L_max]` of the selected pile.  
Changing pile type resets the length to the valid range.  
Pile Length syncs with **Geo Data → Pile Length [m]**.

---

## §20.6 Calculation Engine

| Step | Detail |
|------|--------|
| Library | openpile 1.0.2 |
| Soil model | `API_sand` — p-y curves per API (1987) |
| SW pile in openpile | Modelled as equivalent tubular: `diameter = H_mm`, `wt = t_mm` |
| Boundary | `BoundaryFixation` at pile tip (required, else "Cannot converge") |
| Load | Point load at pile head: `Py = H [kN]`, `Mx = M [kN.m]` |
| Layer clipping | Layers clipped to pile tip; last layer extended if needed |
| Results | `result.deflection`, `result.forces` → deflection, shear, moment profiles |
| Mcr check | `M_max / Mcr` shown as KPI — warns if pile is cracked |

**Note:** For exact PLAXIS plate inputs (EA1, EI), use values from **Sheet Pile Section** tab, not openpile's internal stiffness. openpile uses equivalent tubular geometry for p-y curve calculation only.

---

## §20.7 English UI Rules

| Element | Rule | Example |
|---------|------|---------|
| Tab names | Title Case | "Geo Data", "Soil Layers", "Concentrated Forces" |
| Field labels | GEO5 convention with units in brackets | "Pile Top Level [m]" |
| Column headers | GEO5 convention | "Layer Tip [m]", "Density Moist [kN/m3]" |
| Buttons | Title Case, imperative | "Calculate", "Export CSV", "Reset" |
| Diagram text | Abbreviated English | "SP Top", "Water", "Front", "Back" |
| KPI cards | English, unit in label | "Head deflection", "Max deflection" |
| Metric values | Number + unit | "12.450 mm", "234.5 kN.m" |
| Error messages | Full sentence, English | "No soil layers cover the pile embedment." |
| Captions | Sentence case | "Layer top is derived automatically from the previous layer tip." |
| Notes | Sentence case | "Boussinesq surcharge is displayed in the diagram only." |

---

## §20.9 Geo Data — Extended Fields (v4)

| Label | Key | Default | Notes |
|-------|-----|---------|-------|
| Pile Top Level [m] | `top_elev` | 0.0 | SP Top elevation |
| Soil Level in Front [m] | `soil_level_front` | 0.0 | Natural ground Front |
| Soil Level behind [m] | `soil_level_back` | 0.0 | Natural ground Back |
| Pile Length [m] | `L_m` | 20.0 | |
| Water Level in Front [m] | `water_level` | -1.0 | |
| Earth Support | `bc_type` | Fixed | Fixed / Free / Cantilever |
| Density Fill [kN/m3] | `gamma_fill` | 18.0 | Fill unit weight |
| Phi Fill [Deg] | `phi_fill` | 25.0 | Fill friction angle |
| Cohesion Fill [kN/m2] | `c_fill` | 5.0 | Fill cohesion |
| Slope H:V (mai doc) | `fill_slope_hv` | 2.0 | H:V ratio of fill slope — used by Slope Stability tab |

### Natural Ground Line (diagram)
- Front side: horizontal golden-brown line at `soil_level_front`, labeled "Ground F"
- Back side: horizontal golden-brown line at `soil_level_back`, labeled "Ground B"
- Ground lines extend from the pile center to the diagram edge on each side

### Fill Zone (Đất đắp)
- If `soil_level_back > top_elev`: fill zone hatched from `top_elev` to `soil_level_back` on BACK side
- If `soil_level_front > top_elev`: fill zone hatched from `top_elev` to `soil_level_front` on FRONT side
- Shown as tan-colored `fill_between` with `///` hatch pattern + "Fill" label

---

## §20.10 Soil Layers — Front and Back (v4)

Two independent `st.data_editor` tables replacing the single layer table.

### Layers in Front
- Session key: `front_layers_df`
- Layer 1 top = `top_elev` (pile top level)
- Layers extend DOWNWARD from pile top
- Used as input to openpile calculation

### Layers behind
- Session key: `back_layers_df`
- Layer 1 top = `soil_level_back` (natural ground behind)
- Layers extend DOWNWARD from natural ground behind
- Displayed in diagram on BACK (right) side only — NOT used in openpile (future)

### Columns (same for both tables)
| Column | Type | Notes |
|--------|------|-------|
| Layer Tip [m] | number | Elevation at bottom of layer |
| Density Moist [kN/m3] | number | min=10, max=25 |
| Density Sub [kN/m3] | number | auto = Moist−10 when checkbox active |
| Phi [Deg] | number | min=0, max=45 |
| Delta [Deg] | number | interface friction (future) |
| Cohesion [kN/m2] | number | |

### Diagram (right panel, Soil Layers tab)
- Front (left): colored soil bands, red pile line, golden ▽ markers
- Back (right): back layer boundaries shown with dashed lines (same style)
- Natural ground lines for both sides

---

## §20.11 Project Management — Save / Open / New

Three buttons in sidebar (3 equal columns):

| Button | Action | Implementation |
| --- | --- | --- |
| **Save** | Download project as JSON | `st.download_button(data=_project_to_json(), file_name="project.json")` |
| **Open** | Upload JSON to restore | Toggle `_open_panel`; show `st.file_uploader` when active |
| **New** | Clear all data | Toggle `_confirm_new`; show Confirm/Cancel before clearing |

### Serialization keys

- `_PROJ_DF_KEYS`: DataFrames stored as `{"records": [...]}` — `front_sand_df`, `front_clay_df`, `back_layers_df`, `forces_df`, `boussinesq_df`, `bc_soil_df`
- `_PROJ_SCALAR_KEYS`: all scalar inputs including `fill_slope_hv`
- `_PROJ_RESULT_KEYS`: computed results (`bc_result`, `bc_cvd`, `result`, `layers_clipped`, etc.)

### File format

```json
{
  "_version": 2,
  "top_elev": 2.7,
  "fill_slope_hv": 2.0,
  "_df_front_sand_df": {"records": [...]},
  ...
}
```

DataFrames restored via `pd.DataFrame(data["_df_<key>"]["records"])`.

---

## §20.8 File References

| File | Role |
|------|------|
| `scripts/app_coc_tai_ngang.py` | Main Streamlit app (v3) |
| `scripts/app_coc_tai_ngang_v1.py` | Backup — original Vietnamese UI |
| `scripts/sw_pile_database.py` | SW pile catalog Python module |
| `data/ui_design_spec.json` | UI spec + SW catalog JSON (machine-readable) |
| `data/python_libs_geotechnical.json` | Library catalog |
| `giao dien/01-UI-GEODAT.png` | GEO5 Geo Data reference screenshot |
| `giao dien/02-UI-Soil Layers.png` | GEO5 Soil Layers reference |
| `giao dien/03-UI-Concentrated Forces.png` | GEO5 Forces reference |
| `giao dien/04-UI-Bossinesp.png` | GEO5 Boussinesq reference |
| `giao dien/05-UI-Sheet Pile Section.png` | GEO5 Sheet Pile Section reference |
