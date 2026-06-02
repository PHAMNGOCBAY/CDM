"""Verify 1 file Excel HK qua engine 'formulas' — in các ô kết quả + quét lỗi."""
import sys
import warnings
warnings.filterwarnings("ignore")
import formulas

path = sys.argv[1]
xl = formulas.ExcelModel().loads(path).finish()
sol = xl.calculate()


def get(sheet, cell):
    suf1 = f"'{sheet}'!{cell}"
    suf2 = f"{sheet}!{cell}"
    for k, v in sol.items():
        if k.endswith(suf1) or k.endswith(suf2):
            try:
                val = v.value
                try:
                    return val[0, 0]
                except Exception:
                    return val
            except Exception:
                return "?"
    return "NA"


cells = {
    "K14 q(kPa)": ("(1)", "K14"),
    "I89 P(S1)": ("(1)", "I89"),
    "I92 Eeq": ("(1)", "I92"),
    "F129 Sblock(m)": ("(1)", "F129"),
    "P180 S2(m)": ("(1)", "P180"),
    "Q180": ("(1)", "Q180"),
    "I187 Total(m)": ("(1)", "I187"),
    "O26 CDTN": ("(1)", "O26"),
    "I26 CD2": ("(1)", "I26"),
    "I25 CD1": ("(1)", "I25"),
    "J74 tip": ("(1)", "J74"),
}
for label, (sh, c) in cells.items():
    print(f"{label:20s} = {get(sh, c)}")

# Quét lỗi toàn bộ
errs = {}
for k, v in sol.items():
    try:
        val = v.value
        try:
            val = val[0, 0]
        except Exception:
            pass
        s = str(val)
        if any(e in s for e in ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A")):
            errs.setdefault(s, []).append(k.split("]")[-1])
    except Exception:
        pass
print("\n--- LỖI CÔNG THỨC ---")
if not errs:
    print("Không có lỗi (#REF/#DIV/0/#VALUE/#NAME/#N/A)")
else:
    for e, locs in errs.items():
        print(f"{e}: {len(locs)} ô — {locs[:8]}")
