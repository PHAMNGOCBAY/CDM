"""Chay nguyen van code do model sinh ra, headless (Agg backend), KHONG sua loi logic/cu phap
cua model - chi them 2 dong scaffolding moi truong (backend + tat plt.show) de cong bang
cho ca 3 model, giong cach du an nay luon dung Agg cho chart headless."""
import sys
import io
import os
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

model_key = sys.argv[1]          # vd: nemotron-3.5-lightning
code_path = sys.argv[2]          # model_code_xxx.py
out_image = sys.argv[3]          # ten anh dich, vd: nemotron_output.png

with open(code_path, "r", encoding="utf-8") as f:
    code = f.read()

print(f"=== Chay code cua {model_key} ===")
try:
    compiled = compile(code, code_path, "exec")
except SyntaxError as e:
    print(f"[LOI CU PHAP - SyntaxError] {e}")
    with open(f"error_{model_key.replace(':','_')}.txt", "w", encoding="utf-8") as ef:
        ef.write(f"SyntaxError: {e}\n\nTraceback:\n{traceback.format_exc()}")
    sys.exit(0)

# Scaffolding moi truong trung lap cho ca 3 model: Agg backend + khong show cua so
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.show = lambda *a, **k: None

try:
    ns = {"__name__": "__main__"}
    exec(compiled, ns)
    # model luon luu ra 'output.png' theo prompt -> doi ten sang file dich rieng
    if os.path.exists("output.png"):
        if os.path.exists(out_image):
            os.remove(out_image)
        os.rename("output.png", out_image)
        print(f"THANH CONG - da luu anh: {out_image}")
    else:
        print("CANH BAO: code chay xong nhung khong tim thay 'output.png'")
except Exception as e:
    print(f"[LOI KHI CHAY - {type(e).__name__}] {e}")
    with open(f"error_{model_key.replace(':','_')}.txt", "w", encoding="utf-8") as ef:
        ef.write(f"{type(e).__name__}: {e}\n\nTraceback:\n{traceback.format_exc()}")
