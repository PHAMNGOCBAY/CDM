# 27 — Phân tích thành phần tải trọng ngang (Component Analysis)

Nguồn: openpile 1.0.x — API p-y (Matlock 1970, API 1987)  
File tính: `scripts/app_coc_tai_ngang.py` — section "Phan tich tung thanh phan tai trong"

---

## Mục đích

Chạy riêng từng thành phần tải trọng trên cùng mô hình đất để kiểm tra đóng góp độc lập của từng nguồn vào chuyển vị / lực cắt / moment.

---

## Các thành phần tải trọng

| Ký hiệu | Nguồn gốc | File lý thuyết |
|---------|-----------|---------------|
| **H + M** | Tải tập trung tại đỉnh cọc (kN, kN.m) | — |
| **Earth** | Áp lực đất phân bố dọc cọc (net = active − passive) | [23-earth-pressure-diagram.md](23-earth-pressure-diagram.md) |
| **Water** | Áp lực nước phân bố (p_back − p_front) | [22-water-pressure.md](22-water-pressure.md) |
| **Boussinesq** | Tải trọng mặt phân bố qua Boussinesq | [25-boussinesq-surcharge.md](25-boussinesq-surcharge.md) |
| **Total** | Tổng hợp H+M + earth + water + Boussinesq | — |

---

## Quy trình rời rạc hóa tải phân bố → lực tập trung

Mỗi biểu đồ áp lực phân bố được chia thành các lực tập trung tại midpoint mỗi đoạn 1 m:

$$F_i = \text{sign} \times \frac{p(e_{hi}) + p(e_{lo})}{2} \times \Delta z \quad [\text{kN/m}]$$

| Thành phần | sign | Lý do |
|-----------|------|-------|
| Earth net\_h = active − passive | +1 | active đẩy về phía Front → Py dương |
| Water p\_net = p\_back − p\_front | +1 | p\_back > p\_front → đẩy về phía Front |
| Boussinesq front\_p − back\_p | −1 | tải Front đẩy cọc về phía Back → Py âm |

Áp dụng vào model: `model.set_pointload(elevation=mid, Py=F_i)`

---

## Quy ước dấu Py trong openpile

| Py > 0 | Py < 0 |
|--------|--------|
| Lực hướng về phía Front (phía đào) | Lực hướng về phía Back (phía giữ đất) |
| Cùng chiều áp lực chủ động | Ngược chiều áp lực chủ động |

---

## Diễn giải biểu đồ

```
┌──────────────┬────────────────┬────────────────┐
│ Chuyển vị    │   Lực cắt V    │  Moment M      │
│ y [mm]       │   [kN]         │  [kN.m]        │
│              │                │                │
│ (+) = Front  │  đường zero =  │  --- Mcr ---   │
│ (−) = Back   │  điểm đổi dấu  │  (gạch cam)    │
└──────────────┴────────────────┴────────────────┘
```

- **Chuyển vị (+)**: cọc lệch về phía Front (hướng đào)
- **Lực cắt**: cực đại thường nằm trong vùng đất gần mặt đào
- **Moment**: cực đại ở độ sâu 1–4 m dưới mặt đào; so sánh với Mcr để kiểm tra nứt

---

## Kiểm tra kết quả

| Điều kiện | Ý nghĩa |
|-----------|---------|
| y_total ≈ Σy_i | Tuyến tính — p-y tuyến tính hoặc tải nhỏ |
| y_total < Σy_i | Bất tuyến tính — phản lực p-y giảm khi kết hợp tải |
| M_max < Mcr | Cọc chưa nứt — dùng EI nguyên |
| M_max ≥ Mcr | Cọc nứt — xem xét giảm EI hoặc cốt thép thêm |

---

## Liên kết

| File | Vai trò |
|------|---------|
| `scripts/app_coc_tai_ngang.py` | Chạy component analysis, vẽ biểu đồ |
| `22-water-pressure.md` | Công thức áp lực nước |
| `23-earth-pressure-diagram.md` | Công thức áp lực đất |
| `25-boussinesq-surcharge.md` | Công thức Boussinesq |
| `26-api-clay-matlock.md` | Mô hình p-y đất sét |
