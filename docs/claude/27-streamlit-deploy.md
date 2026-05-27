### 27. Streamlit App — Khởi Động và Deploy

#### Khởi động local (bền vững)

Dùng `start_app.bat` (nằm ở project root) — double-click để mở CMD window, giữ window mở để app tiếp tục chạy.

```text
Local URL: http://localhost:8503
```

**Nguyên nhân app chết:** Khi Claude Code chạy Streamlit qua PowerShell background, process bị garbage-collect khi session kết thúc. `start_app.bat` tạo CMD window độc lập — không phụ thuộc Claude.

Nếu app không chạy được: kill Python trước (`Stop-Process -Name python -Force`), xóa `__pycache__`, chạy lại bat file.

#### Deploy lên Streamlit Cloud

**Repo đang dùng:** `https://github.com/PHAMNGOCBAY/CDM.git`
**App URL:** `https://phantichcocdm.streamlit.app`
**Thư mục deploy:** `cdm-deploy/` (embedded git repo trong project root)
**Main file path trên Cloud:** `scripts/app_cdm.py` (dùng `_ROOT = Path(__file__).parent.parent`)

**Quy trình cập nhật (dùng `update_app.bat`):**

1. Double-click `update_app.bat` ở project root
2. Script tự copy `scripts/app_cdm.py` + `data/TTHC.sqlite` vào `cdm-deploy/`
3. Commit + push vào `PHAMNGOCBAY/CDM` → Streamlit Cloud tự redeploy ~30-60 giây

**Hoặc thủ công:**

```bat
cd cdm-deploy
copy ..\scripts\app_cdm.py scripts\app_cdm.py
copy ..\data\TTHC.sqlite data\TTHC.sqlite
git add -A
git commit -m "update"
git push origin main
```

**Lưu ý quan trọng:**

- Streamlit Cloud dùng `requirements.txt` ở root của `cdm-deploy/` — phải có đủ packages
- SQLite trong repo → read-only trên Cloud (chỉ đọc) — app hiện tại OK vì chỉ đọc
- KHÔNG commit trực tiếp vào `cdm-deploy/scripts/app_cdm.py` — luôn sửa `scripts/app_cdm.py` trong project root rồi dùng `update_app.bat`

#### Quy trình deploy thủ công (PowerShell)

```powershell
$src = "G:\My Drive\AI-SUC TAI COC THEO DAT NEN"
$dst = "$src\cdm-deploy"
Copy-Item "$src\scripts\app_cdm.py"        "$dst\scripts\app_cdm.py" -Force
Copy-Item "$src\data\TTHC.sqlite"          "$dst\data\TTHC.sqlite"   -Force
Copy-Item "$src\scripts\settlement_calc.py" "$dst\scripts\settlement_calc.py" -Force
Copy-Item "$src\data\tccs41_params.json"   "$dst\data\tccs41_params.json"     -Force
cd $dst
git add -A
git commit -m "cap nhat"
git push origin main
```

---

