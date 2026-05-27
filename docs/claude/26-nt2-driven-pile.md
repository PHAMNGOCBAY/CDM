### 26. NT2 Cọc đóng — Đa phương pháp TCVN 11823-10:2017

Engine `scripts/ke_sw_nt_calc.py` tự động chọn phương pháp theo `symbol`:

- **Lớp sét** (mặc định) → α-method (Tomlinson 1980), Điều 7.3.8.6.2, φ_stat = 0,35
- **Lớp cát** (`SAND_SYMBOLS = {F, 2a, 2b, 2c, 4, 5a, 6, 7}`) → SPT-Meyerhof, Điều 7.3.8.6.7, φ_stat = 0,30

**Đơn vị**: TCVN dùng MPa·mm² → engine đổi sang kPa·m² nhân ra kN.
- `qs_kPa = 1.9·N₁₆₀` (cọc chiếm chỗ — SW); `0.96·N₁₆₀` (chữ H / ống hở)
- `qp_kPa = 38·N₁₆₀·(Db/D) ≤ 3200·N₁₆₀` (cát) hoặc `≤ 1800·N₁₆₀` (cát bột)
- `N₁₆₀ = N·CN`, với `CN = √(100/σ'v_kPa)` clamp [0.5, 2.0]

**σ'v effective**: tích phân γ qua các lớp; phần dưới MNN dùng γ' = γ − γw; lớp cắt ngang MNN chia đôi tự động.

**φ_stat dynamic**: sand Rs > 10% hoặc tip cát → 0,30; còn lại 0,35.

Khi thiếu SPT cho lớp cát → Rs/Rp = 0 + warning trong `n2["warnings"]`. Khi import SPT, formula auto-activate.

**File chi tiết:** [42-ke-sw-nt1-nt2-chi-tiet.md](42-ke-sw-nt1-nt2-chi-tiet.md) + [18-driven-pile-TCVN11823.md](18-driven-pile-TCVN11823.md)

**NHC DXF — Tọa độ hố khoan (cập nhật 2026-05-19):**

File: `NHC-1. TRỤ_TTHC_Tru hien truong.dxf` (G:/My Drive/202605-TRUNG TAM HCM/DIA CHAT/2. NHÀ HÀNH CHÍNH/)

Cấu trúc DXF (page 1, y chuẩn):

| Dòng y | Nội dung | Pattern |
| --- | --- | --- |
| y ≈ 71646 | Tên BH (header) | `BH-\d+` |
| y ≈ 71592 | Northing VN-2000 | `119\d{4}\.\d+` |
| y ≈ 71587/71588 | Easting VN-2000 | `60[56]\d{3}\.\d+` |
| y ≈ 71582 | Cao độ mặt đất (m) | `-?\d+\.\d{2}` |

- Pair-by-order (sort x) — KHÔNG dùng nearest-x vì BH-27/BH-28 quá gần nhau (Δx=2 DXF)
- 16/23 BH có tọa độ trong DXF này (thiếu: BH-01, BH-02, BH-09, BH-31, BH-39, BH-42, BH-44)
- Script: `scripts/nhc_coord_import.py`; JSON: `data/nhc_coords_202605_TTHC.json`
- Quy ước DB: `x_coord_m = Northing`, `y_coord_m = Easting` (giống BXN/KE)

