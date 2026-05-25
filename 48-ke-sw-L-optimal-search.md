# Tìm chiều dài cừ SW tối ưu cho ổn định tổng thể — Thuật toán lặp +1 m

Mô-đun phụ trợ cho Mục E (Ổn định tổng thể — 3 phương pháp + Fs lật) trong tab **Cọc ván SW Kè** (`ke_sw`) của app_cdm.

---

## 1. Nguyên tắc

Khi một hố khoan có $L_{thiết\_kế}$ hiện tại **không đạt** một trong 4 tiêu chí ổn định, hệ thống tự động:

1. Bắt đầu từ $L_0$ = L_thiết_kế hiện tại
2. Lặp tăng dần $L = L_0, L_0 + 1, L_0 + 2, \ldots$ (bước $\Delta L = 1{,}0$ m)
3. Tại mỗi $L$, **chạy đầy đủ 4 kiểm tra:** Bishop · Spencer · Morgenstern–Price · Lật
4. **Lưu kết quả** mỗi bước vào SQLite (kể cả bước không đạt) — phục vụ tra cứu, kiểm chứng
5. Dừng tại $L$ đầu tiên thỏa mãn **TẤT CẢ** 4 điều kiện
6. Giới hạn trên: $L_{\max}$ = L_max của cọc trong catalog (`sw_pile_catalog.json`)

## 2. Ngưỡng Fs cho phép (BẮT BUỘC)

| Phương pháp | Ký hiệu | Fs tối thiểu | Ghi chú |
|---|:---:|:---:|---|
| Bishop Simplified | $F_{s,Bishop}$ | **≥ 1,40** | TCVN 4253 cho công trình tạm |
| Spencer | $F_{s,Spencer}$ | **≥ 1,40** | Phân mảnh tổng quát |
| Morgenstern–Price | $F_{s,MP}$ | **≥ 1,40** | Phân mảnh thỏa mãn cân bằng lực + mô men |
| Lật quanh chân cừ | $F_{s,lật}$ | **≥ 1,20** | Bao gồm cả mô men giữ + lật |

**Pass = `min(Fs_Bishop, Fs_Spencer, Fs_MP) ≥ 1,40` VÀ `Fs_lật ≥ 1,20`.**

## 3. Pseudocode

```text
INPUT:  bh_name, pile_type, geom_template, soil_layers,
        L_start (m), L_max (m), Fs_targets
OUTPUT: L_optimal (m), iteration_history[]

L      ← L_start
history ← []
WHILE L ≤ L_max:
    geom ← update_geom(geom_template, L)
    res  ← check_all(geom, layers, fill, cdm, pile)
            for method ∈ {Bishop, Spencer, MP}
    pass_slip   ← min(res.Fs_slip[Bishop,Spencer,MP]) ≥ 1,40
    pass_overt  ← res.Fs_overturning ≥ 1,20
    all_pass    ← pass_slip AND pass_overt
    history.append({L, Fs_bishop, Fs_spencer, Fs_mp, Fs_lật, all_pass})
    save_to_sqlite(history[-1])
    IF all_pass:
        RETURN L_optimal = L, history
    L ← L + 1,0
RETURN L_optimal = None (không tìm thấy trong [L_start, L_max])
```

## 4. Cấu trúc bảng SQLite — `ke_sw_L_iteration`

| Cột | Type | Mô tả |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `bh_name` | TEXT | `KE-HK1`, `KE-HK10`... |
| `pile_type` | TEXT | `SW-740`, `SW-840`... |
| `L_m` | REAL | Chiều dài cừ (m) |
| `Fs_bishop` | REAL | Fs Bishop |
| `Fs_spencer` | REAL | Fs Spencer |
| `Fs_mp` | REAL | Fs Morgenstern-Price |
| `Fs_overturning` | REAL | Fs lật |
| `pass_slip` | INTEGER | 1 nếu min(3 PP) ≥ 1,40 |
| `pass_overt` | INTEGER | 1 nếu Fs_lật ≥ 1,20 |
| `all_pass` | INTEGER | 1 nếu pass cả 2 |
| `is_final` | INTEGER | 1 nếu là L_optimal cuối (=L đầu tiên all_pass) |
| `run_id` | TEXT | UUID phiên tìm kiếm |
| `ts` | TEXT | datetime('now','localtime') |
| **UNIQUE** | | `(bh_name, pile_type, L_m, run_id)` |

## 5. Hàm Python public

**File:** [scripts/sw_global_stability.py](scripts/sw_global_stability.py)

```python
def find_optimal_L_iterative(
    bh_name: str,
    pile_type: str,
    geom_template: WallGeometry,
    front_layers: list[EarthLayer],
    back_layers: list[EarthLayer],
    fill: EarthLayer | None,
    cdm: CDMBlock | None,
    pile: PileProps,
    L_start: float,
    L_max: float = 50.0,
    L_step: float = 1.0,
    Fs_min_slip: float = 1.40,
    Fs_min_overt: float = 1.20,
    save_to_db: bool = True,
    db_path: Path | None = None,
    run_id: str | None = None,
) -> dict:
    """Tìm L tối ưu lặp +1m. Trả về:
       {'L_optimal_m': float | None,
        'history': [{L_m, Fs_bishop, Fs_spencer, Fs_mp, Fs_lat, all_pass}, ...],
        'n_iterations': int, 'run_id': str}
    """
```

## 6. Ví dụ — KE-HK1 / SW-740

| Bước | L (m) | Bishop | Spencer | M-P | Fs lật | Đạt? |
|---|---|---|---|---|---|---|
| 0 | 28.0 | 3.837 | 3.837 | 3.837 | **1.173** | Không |
| 1 | 29.0 | 4.123 | 4.118 | 4.131 | 1.245 | Đạt |

→ $L_{tối\_ưu} = 29.0$ m (lưu `is_final=1`).

## 7. Tích hợp app (BẮT BUỘC)

**Vị trí:** Mục E sau bảng so sánh 4 PP, hiện nút **"Tìm L tối ưu cho HK chưa đạt"** khi có ≥ 1 HK không đạt:

1. Lọc HK có cột "Kết quả = Không đạt"
2. Với mỗi HK chưa đạt → gọi `find_optimal_L_iterative()` 
3. Hiển thị bảng iteration_history dưới dạng expander/data_editor
4. Cập nhật cột "L thiết kế" về `L_optimal` (lưu vào `ke_sw_design`)

## 8. Liên kết

- `scripts/sw_global_stability.py` — engine 4 kiểm tra
- `scripts/app_cdm.py` ~line 10200–10600 — Mục E tab `ke_sw`
- `data/tccs41_params.json` → `sw_stability_search` — config ngưỡng + bước
- [42-ke-sw-nt1-nt2-chi-tiet.md](42-ke-sw-nt1-nt2-chi-tiet.md), [48-ke-sw-L-optimal-search.md](48-ke-sw-L-optimal-search.md) (file này)
