### 15. Số liệu Giả định — Lấy từ HK Gần nhất (KHÔNG hardcode)

**Quy tắc:** Mọi giá trị giả định (su, γ, Cc, Cs, e0, PC, Cv, ...) khi hố khoan hiện tại KHÔNG có thí nghiệm cho lớp đó → **BẮT BUỘC tra cứu từ HK gần nhất** cùng khu vực có dữ liệu, từ SQLite. **KHÔNG dùng hằng số hardcode** (`SU_BY_SYMBOL`, `GAMMA_DEFAULT_BY_SYMBOL`...).

**Why:** Hằng số mặc định không phản ánh điều kiện thực địa. Số liệu HK gần nhất (cùng khu vực, cùng symbol đất) đại diện chính xác hơn — đặc biệt cho lớp '1b'/'XMD' thiếu thí nghiệm ở nhiều HK trên tuyến.

**How to apply:**

1. **Priority chain mới** cho mọi field:
   ```
   1. HK hiện tại (VST/lab có giá trị) — source = 'VST'/'lab'
   2. HK gần nhất cùng zone có data (cùng symbol) — source = 'lab_from <BH-name> (d=<dist>m)'
   3. Mặc định hardcode (CẢNH BÁO mạnh) — source = 'default (warn)'
   ```

2. **Helper bắt buộc** trong `scripts/ke_sw_nt_calc.py`:
   ```python
   def _find_nearest_bh_with_data(bh_name, symbol, field, db_path) -> tuple:
       """Return (value, source_bh_name, distance_m) — None nếu không tìm thấy.
       field: 'gamma_kNm3', 'Cu_UU_kPa', 'c_kPa', 'Cc', 'Cs', 'PC_kPa', ...
       """
   ```
   Khoảng cách = √((x1-x2)² + (y1-y2)²) từ `boreholes.x_coord_m`, `y_coord_m`.

3. **Hiển thị rõ trên UI**: warning + tooltip phải ghi:
   - Tên HK gốc lấy giá trị (vd "KE-HK1")
   - Khoảng cách (vd "d=85m")
   - Giá trị + nguồn (vd "γ=15.4 kN/m³ from KE-HK1 (d=85m, lab)")

4. **PDF báo cáo** ghi rõ cột "Nguồn dữ liệu" cho mỗi giá trị giả định.

5. **Cấm**:
   - Dùng `SU_BY_SYMBOL[symbol]` mà không tìm HK gần trước
   - Báo cáo giá trị giả định mà không ghi rõ HK gốc
   - Silent fallback (warning phải hiển thị nổi bật)

