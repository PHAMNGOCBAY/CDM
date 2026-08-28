import unicodedata
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# Font mac dinh (DejaVu/monospace) render sai mot so to hop dau tieng Viet.
# Dung Segoe UI (chuan cua du an, xem chroma_ex2_rag.py) cho van ban thuong,
# Consolas cho doan code de vua doc dau vua giu can le.
plt.rcParams["font.family"] = "Segoe UI"
_mono = "Consolas" if any("Consolas" in f.name for f in fm.fontManager.ttflist) else "monospace"

fig, ax = plt.subplots(figsize=(8, 6))
ax.axis("off")
ax.set_title(unicodedata.normalize("NFC", "Gemma4:26b — THẤT BẠI khi tự chạy code (lần đầu, không sửa tay)"),
              fontsize=12, fontweight="bold", color="#B71C1C")

prose = unicodedata.normalize("NFC",
    "Nghiệm đưa ra trong phần văn bản: x = 1, 2, 3  (ĐÚNG)\n\n"
    "Nhưng code Python model tự sinh ra có lỗi cú pháp (SyntaxError)\n"
    "ngay tại dòng định nghĩa hàm số — model để lộ một dòng \"nháp\"\n"
    "chưa hoàn chỉnh rồi viết đè bằng dòng đúng ngay bên dưới,\n"
    "nhưng KHÔNG xoá dòng nháp bị lỗi:"
)
code_block = (
    "    def f(x):\n"
    "        return x**3 - 6*x** import x**2 + 11*x - 6\n"
    "        # Note: Fixed typo in thought, writing actual code below\n\n"
    "    f = lambda x: x**3 - 6*x**2 + 11*x - 6"
)
tail = unicodedata.normalize("NFC",
    "  <- dòng đúng, nhưng quá muộn\n\n"
    "Kết quả: chương trình dừng ngay ở bước biên dịch (compile),\n"
    "KHÔNG có bất kỳ biểu đồ nào được tạo ra — 0 ảnh output."
)

ax.text(0.02, 0.85, prose, fontsize=10.5, family="Segoe UI", va="top",
        transform=ax.transAxes, color="#333333")
ax.text(0.02, 0.60, code_block, fontsize=10, family=_mono, va="top",
        transform=ax.transAxes, color="#8A1F1F")
ax.text(0.02, 0.30, tail, fontsize=10.5, family="Segoe UI", va="top",
        transform=ax.transAxes, color="#333333")

fig.tight_layout()
fig.savefig("gemma_output.png", dpi=150)
print("Da luu the loi: gemma_output.png")
