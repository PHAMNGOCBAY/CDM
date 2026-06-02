### 70. Quy tắc Tự động Refresh UI Streamlit

**Áp dụng:** mọi trang Streamlit có dữ liệu thay đổi theo thời gian (đang re-compute background, file Google Drive sync, hoặc dev đang sửa code).
**Thư viện:** [`streamlit-autorefresh`](https://pypi.org/project/streamlit-autorefresh/) ≥ 1.0.1
**Cài đặt:** `pip install streamlit-autorefresh` (đã có trong `requirements.txt`)

---

#### 1. Lý do cần auto-refresh

| Tình huống | Vì sao |
|---|---|
| **Re-compute background** (Lc QTT, S2 sweep…) đang chạy | UI cần update khi DB cập nhật, người dùng không phải F5 |
| **Google Drive sync trễ** | File `qtt_page.py` đã sửa nhưng Streamlit watcher chưa nhận → rerun bỏ sót |
| **DB SQLite được update bởi script khác** | Tab UI vẫn đọc cache cũ → cần rerun |
| **Demo / dashboard production** | Hiển thị data realtime mà không cần thao tác |
| **Test mode** dev sửa code liên tục | Auto rerun thay vì F5 thủ công |

---

#### 2. Pattern triển khai chuẩn (BẮT BUỘC dùng pattern này)

```python
import streamlit as st

# Try-import: nếu chưa cài, KHÔNG vỡ app
try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTOREFRESH = True
except ImportError:
    _HAS_AUTOREFRESH = False

# Sidebar controls — luôn ở sidebar để không lẫn UI chính
with st.sidebar:
    st.markdown("**Tự động refresh**")
    _ar_enable = st.checkbox(
        "Bật auto-refresh", value=False, key="_ar_enable",
        help="Tự động rerun trang theo chu kỳ.",
    )
    _ar_interval = st.select_slider(
        "Chu kỳ (giây)",
        options=[5, 10, 15, 30, 60, 120, 300], value=30,
        key="_ar_interval",
        disabled=not _ar_enable,
    )
    if st.button("Refresh ngay", key="_ar_now", use_container_width=True):
        st.rerun()

# Logic chạy
if _ar_enable and _HAS_AUTOREFRESH:
    _ar_count = st_autorefresh(
        interval=_ar_interval * 1000,  # ms
        key="_autorefresh_counter",
    )
    st.sidebar.caption(
        f"Auto-refresh ON — {_ar_interval}s · rerun: {_ar_count}"
    )
elif _ar_enable and not _HAS_AUTOREFRESH:
    st.sidebar.warning(
        "Chưa cài `streamlit-autorefresh`."
    )
```

---

#### 3. Quy tắc chọn chu kỳ refresh

| Loại tác vụ | Chu kỳ khuyến nghị | Tác động |
|---|:---:|---|
| **Sửa code dev (Google Drive sync)** | **5-10 s** | Pickup nhanh, không gây giật |
| **Re-compute Lc background** | 15-30 s | Đủ thời gian hoàn thành 1 batch |
| **DB update từ script ngoài** | 30-60 s | Tránh load DB liên tục |
| **Dashboard production realtime** | 60-300 s | Tiết kiệm tài nguyên server |
| **Báo cáo tĩnh, ít thay đổi** | **TẮT** | Không cần refresh tự động |

---

#### 4. Nguyên tắc UI/UX

- **Mặc định TẮT** (`value=False`) — chỉ bật khi user chủ động cần
- **Luôn có nút "Refresh ngay"** — fallback thủ công khi auto-refresh tắt
- **Hiển thị số lần đã rerun** — để user thấy đang hoạt động
- **Đặt trên sidebar** — không lẫn UI tính toán chính
- **`disabled` slider khi tắt** — tránh user thay đổi vô ích

---

#### 5. Caveat — KHÔNG dùng auto-refresh khi

| Tình huống | Vì sao KHÔNG |
|---|---|
| Trang có form nhập liệu phức tạp (nhiều input) | Rerun làm mất input chưa save |
| Trang đang xuất Word/PDF | Rerun gián đoạn quá trình build |
| Trang đang upload file lớn | Rerun reset upload |
| Trang Plotly có user interaction (zoom, pan) | Rerun reset state biểu đồ |
| Compute cực nặng (>30s/lần) | Rerun chồng chéo, đứng server |

→ Trong các trường hợp này, **chỉ giữ nút "Refresh ngay" thủ công**.

---

#### 6. Áp dụng cho dự án TTHC

| Trang | Auto-refresh | Lý do |
|---|:---:|---|
| **Zone QTT** | **Có (mặc định OFF)** | Có khả năng re-compute background |
| Dự báo độ lún | Có (tuỳ chọn) | Multi-zone analysis có thể compute lâu |
| Thông số CDM | Không | Form nhập liệu — rerun làm mất input |
| Cọc ván SW | Không | Compute heavy, không có data thay đổi realtime |
| Địa chất | Không | Data tĩnh từ DB |

---

#### 7. Tham chiếu code

**Mẫu tham khảo:**
- [scripts/pages/qtt_page.py](scripts/pages/qtt_page.py) — block sidebar "Tự động refresh (Zone QTT)" ngay đầu `render()`

**Lib gốc:**
- https://github.com/kmcgrady/streamlit-autorefresh
- API: `st_autorefresh(interval=ms, limit=None, key=str) -> count`
