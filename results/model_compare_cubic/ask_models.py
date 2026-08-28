import sys
import io
import requests
import re
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROMPT = """Giai phuong trinh bac 3: x^3 - 6x^2 + 11x - 6 = 0. Tim tat ca nghiem thuc.
Sau do viet DAY DU code Python dung matplotlib de ve do thi ham so y = x^3 - 6x^2 + 11x - 6
trong khoang x tu -1 den 5, danh dau ro cac diem nghiem tren do thi, co luoi, tieu de, chu thich truc.
Luu anh ra file 'output.png'. Code phai chay duoc ngay, khong loi.
Chi tra loi gom: (1) cac nghiem tim duoc, (2) dung 1 khoi code Python hoan chinh."""

MODELS = ["nemotron-3.5-lightning", "gemma4:26b"]

for model in MODELS:
    print(f"Đang hỏi {model}...")
    r = requests.post("http://localhost:11434/api/generate",
                       json={"model": model, "prompt": PROMPT, "stream": False},
                       timeout=600)
    d = r.json()
    text = d.get("response", "")
    fname_txt = f"raw_response_{model.replace(':', '_')}.txt"
    with open(fname_txt, "w", encoding="utf-8") as f:
        f.write(text)

    # Trích code block ```python ... ``` hoặc ``` ... ```
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    code = m.group(1).strip() if m else ""
    fname_py = f"model_code_{model.replace(':', '_')}.py"
    with open(fname_py, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  -> Đã lưu: {fname_txt} ({len(text)} ký tự), {fname_py} ({len(code)} ký tự code)")
