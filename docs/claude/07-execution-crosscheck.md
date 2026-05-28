## Quy tắc Thực thi & Kiểm tra Chéo (BẮT BUỘC)

### 7. Bash Command — Luôn Chọn "Yes to All"

Khi xuất hiện hộp thoại xác nhận quyền chạy lệnh bash (permission prompt):

```
"Allow this bash command?" / "Allow all bash commands for this session?"
```

**→ BẮT BUỘC chọn "Yes" / "Yes to all" — KHÔNG chờ, KHÔNG hỏi lại user.**

Lý do: Mọi lệnh bash trong dự án này đều là thao tác nội bộ an toàn (đọc/ghi file, chạy Python script, query SQLite). Việc dừng lại xin phép từng lệnh làm gián đoạn luồng làm việc.

| Loại lệnh | Phải xin phép? |
| --- | :---: |
| `python script.py` | Không |
| `sqlite3 ...` / Python query DB | Không |
| `cp`, `rm` file trong project | Không |
| `streamlit run ...` | Không |
| `git push --force`, xóa dữ liệu ngoài project | **Có** |

### 8. Kiểm tra Chéo Bằng Subagent (Agent Cross-Check)

Với mọi thay đổi code ảnh hưởng đến logic tính toán hoặc DB:

1. **Agent chính** viết và chạy code
2. **Subagent `Explore`** đọc lại file đã sửa, xác nhận:
   - SQL query trả về đúng dữ liệu
   - Không có regression ở các borehole khác
   - Fallback logic theo đúng thứ tự ưu tiên
3. Chỉ báo cáo "hoàn thành" khi subagent không tìm thấy lỗi

**Khi nào bắt buộc dùng Agent cross-check:**

- Sửa hàm `_load_layers`, `_load_spt`, hoặc bất kỳ hàm DB nào
- Thêm bảng mới hoặc thay đổi schema SQLite
- Sửa công thức tính toán địa kỹ thuật
- Thêm/xóa fallback logic

**Mẫu gọi:**

```python
Agent(subagent_type="Explore",
      prompt="Đọc scripts/app_cdm.py hàm _load_layers (dòng ~287). "
             "Xác nhận: (1) 3 fallback đúng thứ tự layers→strat_layers→lab_tests, "
             "(2) SQL window function GROUP BY symbol_tcvn,grp đúng cú pháp SQLite 3.25+, "
             "(3) gap-filling loop không lỗi index. Báo cáo ngắn gọn.")
```

### 9. Luôn Publish vào CLAUDE.md

**Sau mỗi thay đổi kỹ thuật quan trọng, BẮT BUỘC cập nhật CLAUDE.md ngay trong cùng session.**

Áp dụng khi:

- Phát hiện pattern mới (fallback logic, SQL technique, color mapping...)
- Thêm bảng/cột mới vào SQLite schema
- Thêm tính năng mới vào app (tab, chart, metric...)
- Đặt ra quy tắc mới về workflow hoặc kiểm tra

Cách thực hiện:

1. Viết/sửa code → test OK → Explore agent cross-check OK
2. **Cập nhật CLAUDE.md** với pattern/quy tắc mới (không cần ghi chi tiết code, chỉ ghi nguyên tắc)
3. **Lưu memory** nếu là feedback hoặc quyết định kiến trúc quan trọng

### 9c. Luôn Đồng Bộ File Tài Liệu *.md (BẮT BUỘC)

**Sau MỖI thay đổi công thức / phương pháp / thông số / quy trình, BẮT BUỘC cập nhật NGAY tất cả file `NN-*.md` (root) liên quan để phản ánh nội dung mới nhất — KHÔNG để tài liệu lỗi thời.**

Quy tắc:

- Đổi/sửa **công thức** → cập nhật mọi file MD có công thức đó (vd sửa sức chịu tải mũi → `35-ly-thuyet-cdm.md`, `60-cdm-suc-chiu-tai-coc.md`).
- Đổi **phương pháp tính** (engine) → làm mới file MD mô tả phương pháp (vd S2 đa lớp → `59-cdm-s2-partial.md`).
- Thêm **mục/biểu đồ/thông số** vào UI → bổ sung file MD mô tả tab (vd `54-tvtk-cdm-prep.md`).
- Đổi **hệ số / mặc định** (FS, k, q...) → sửa con số trong MD cho khớp.

**Checklist trước khi báo "xong":** đã grep nội dung cũ trong các `*.md` liên quan và cập nhật chưa? Công thức/con số trong MD có khớp code không? Nếu một công thức xuất hiện ở nhiều MD → sửa TẤT CẢ, không sót.

**Lý do:** tài liệu là nguồn tra cứu (§6b ưu tiên đọc MD trước PDF). MD lỗi thời → tra cứu sai → tính sai.

### 9b. Auto-Compute — KHÔNG có nút "Build / Solve / Run" trong app

**Mọi tính toán BẮT BUỘC chạy tự động khi input thay đổi.** KHÔNG dùng nút như "Build", "Solve", "Run verification" — Streamlit rerun toàn bộ script trên mỗi input change, vậy chỉ cần đặt logic compute ở script-level.

**Why:** Tránh quy trình "nhập → bấm → chờ → bấm tiếp" rườm rà. Người dùng nhìn kết quả live → trải nghiệm liền mạch + phù hợp luồng báo cáo Ctrl+P.

**How to apply:**

1. Bọc compute trong hàm helper, gọi ở script-level:
   ```python
   try:
       model = _build_model_auto(...)
       st.session_state["model"] = model
   except Exception as e:
       st.error(f"Lỗi build: {e}")
   ```
2. Dùng `@st.cache_data(show_spinner=False)` cho compute nặng (solver, FEM) — key bằng hash của input để skip re-compute khi không đổi.
3. **Giữ nút CHỈ khi:** thao tác mutate DB (Save model), xóa dữ liệu, hoặc external side-effect (xuất file, gọi API). KHÔNG đặt nút cho compute đơn thuần.
4. Validation lỗi → `st.warning()` / `st.error()` + `session_state["X"] = None` để mục sau biết model invalid.

File tham chiếu: `scripts/app_fem2d.py` (auto-build + cached solve + cached verify), `scripts/app_cdm.py` mục B Kè SW (cọc tối ưu auto-fill).

