"""Vong lap tu sua loi that cho model local qua Ollama /api/chat:
gui de bai -> chay code model tra ve -> neu loi, gui NGUYEN VAN traceback that
lai cho model tu sua -> lap toi da MAX_ITERS lan hoac den khi thanh cong.
Do thoi gian tung vong + tong thoi gian + so vong can de thanh cong.
"""
import sys
import io
import os
import re
import time
import traceback
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OLLAMA_URL = "http://localhost:11434/api/chat"
MAX_ITERS = 6
TIMEOUT_S = 600

BASE_PROMPT = """Giai phuong trinh bac 7: 2x^7 - 4x^5 + 3x^4 - x^2 + 5 = 0.
Tim TAT CA nghiem THUC (bo qua nghiem phuc). Luu y day la phuong trinh bac cao,
khong co cong thuc dai so don gian - phai giai bang phuong phap so (vi du dung
numpy.roots hoac numpy.polynomial), KHONG duoc tu doan/bia nghiem dep.

Sau do viet DAY DU code Python:
1. Dung numpy de tim nghiem so hoc chinh xac cua da thuc (numpy.roots voi he so
   [2, 0, -4, 3, 0, -1, 0, 5] tuong ung 2x^7+0x^6-4x^5+3x^4+0x^3-x^2+0x+5).
2. Loc ra cac nghiem THUC (phan ao gan bang 0, dung sai 1e-6).
3. Dung matplotlib ve do thi y = 2x^7 - 4x^5 + 3x^4 - x^2 + 5 trong khoang x tu -2.2 den 2.2,
   gioi han truc y tu -30 den 30 de nhin ro vung gan 0.
4. Danh dau ro CAC NGHIEM THUC tim duoc (khong ve nghiem phuc).
5. Co luoi, tieu de, chu thich truc, chu thich so nghiem thuc/phuc tim duoc.
6. Luu anh ra file 'output.png'.

Code phai chay duoc ngay, khong loi cu phap, khong loi runtime.
Chi tra loi gom: (1) danh sach nghiem thuc tim duoc bang so, (2) dung 1 khoi code Python hoan chinh."""

FIX_PROMPT_TMPL = """Code ban vua dua ra khi chay THAT bi loi. Day la traceback that:

{error}

Hay sua lai code cho DUNG va chay duoc ngay. Chi tra ve DUY NHAT 1 khoi code Python
hoan chinh (khong giai thich dai dong, khong lap lai code cu neu no van con loi)."""


def ask_chat(model, messages):
    r = requests.post(OLLAMA_URL, json={"model": model, "messages": messages, "stream": False},
                       timeout=TIMEOUT_S)
    r.raise_for_status()
    d = r.json()
    return d["message"]["content"]


def extract_code(text):
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def run_code_isolated(code, iter_dir):
    os.makedirs(iter_dir, exist_ok=True)
    code_path = os.path.join(iter_dir, "code.py")
    with open(code_path, "w", encoding="utf-8") as f:
        f.write(code)

    try:
        compiled = compile(code, code_path, "exec")
    except SyntaxError as e:
        return False, f"SyntaxError: {e}\n{traceback.format_exc()}"

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.show = lambda *a, **k: None

    cwd0 = os.getcwd()
    os.chdir(iter_dir)
    try:
        ns = {"__name__": "__main__"}
        exec(compiled, ns)
        if os.path.exists("output.png"):
            return True, None
        else:
            return False, "Code chay xong nhung KHONG tao ra file 'output.png' nhu yeu cau."
    except Exception as e:
        return False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
    finally:
        os.chdir(cwd0)


def run_iterative(model, outdir):
    print(f"\n{'='*60}\n=== {model} — vong lap tu sua loi (toi da {MAX_ITERS} lan) ===\n{'='*60}")
    messages = [{"role": "user", "content": BASE_PROMPT}]
    log = []
    t_total_start = time.time()
    final_ok = False
    final_iter_dir = None

    for i in range(1, MAX_ITERS + 1):
        iter_dir = os.path.join(outdir, f"iter_{i}")
        t0 = time.time()
        try:
            reply = ask_chat(model, messages)
        except Exception as e:
            print(f"  [Vong {i}] LOI GOI API: {e}")
            log.append({"iter": i, "time_s": 0, "ok": False, "err": f"API error: {e}"})
            break
        dt = time.time() - t0
        messages.append({"role": "assistant", "content": reply})
        code = extract_code(reply)
        ok, err = run_code_isolated(code, iter_dir)
        print(f"  [Vong {i}] thoi gian phan hoi: {dt:.1f}s -> {'THANH CONG' if ok else 'LOI'}")
        if not ok:
            print(f"           loi: {err.splitlines()[0] if err else ''}")
        log.append({"iter": i, "time_s": round(dt, 1), "ok": ok, "err": err})
        if ok:
            final_ok = True
            final_iter_dir = iter_dir
            break
        else:
            messages.append({"role": "user", "content": FIX_PROMPT_TMPL.format(error=err)})

    total_time = time.time() - t_total_start
    print(f"  => Tong thoi gian: {total_time:.1f}s | Thanh cong: {final_ok} | So vong dung: {len(log)}")

    # luu log
    with open(os.path.join(outdir, "iteration_log.txt"), "w", encoding="utf-8") as f:
        f.write(f"model={model}\ntotal_time_s={total_time:.1f}\nsuccess={final_ok}\niterations_used={len(log)}\n\n")
        for entry in log:
            f.write(f"--- Vong {entry['iter']} ---\ntime_s={entry['time_s']}\nok={entry['ok']}\n")
            if entry["err"]:
                f.write(f"error:\n{entry['err']}\n")
            f.write("\n")

    # luu toan bo hoi thoai
    with open(os.path.join(outdir, "full_conversation.txt"), "w", encoding="utf-8") as f:
        for m in messages:
            f.write(f"\n{'='*20} {m['role'].upper()} {'='*20}\n{m['content']}\n")

    return {
        "model": model, "success": final_ok, "total_time_s": total_time,
        "iterations_used": len(log), "final_iter_dir": final_iter_dir, "log": log,
    }


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    results = {}
    for model, outdir_name in [
        ("nemotron-3.5-lightning", "nemotron_run"),
        ("gemma4:26b", "gemma_run"),
    ]:
        outdir = os.path.join(base_dir, outdir_name)
        os.makedirs(outdir, exist_ok=True)
        results[model] = run_iterative(model, outdir)

    print(f"\n{'='*60}\nTOM TAT\n{'='*60}")
    for model, r in results.items():
        print(f"{model}: thanh_cong={r['success']} | tong_thoi_gian={r['total_time_s']:.1f}s | so_vong={r['iterations_used']}")
