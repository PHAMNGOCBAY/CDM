"""
check_formula_sync.py — Validator cho hệ thống FORMULA-ID.

Kiểm tra:
1. Mọi FORMULA-ID trong AUTO-FORMULA marker phải tồn tại trong registry
2. MD đã render khớp registry (gọi regen_docs --check)
3. Mọi tag `# FORMULA-ID: <id>` trong code Python phải tồn tại trong registry
4. Mọi formula numeric callable hoạt động (smoke-test gọi với dummy args)

Exit 0 nếu OK, exit 1 nếu drift, exit 2 nếu FORMULA-ID không tồn tại.

Dùng cho pre-commit hook hoặc CI:
    python scripts/check_formula_sync.py
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

from core.formulas.registry import _load_all_modules, ids, get  # noqa: E402


CODE_TAG = re.compile(r"#\s*FORMULA-ID:\s*([a-z0-9\-]+)")
MD_MARKER = re.compile(r"<!--\s*AUTO-FORMULA:\s*([a-z0-9\-]+)\s*-->")


def find_code_tags() -> dict[str, list[Path]]:
    """{formula_id: [paths uses it]}"""
    out: dict[str, list[Path]] = {}
    for py in (_ROOT / "scripts").rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for fid in CODE_TAG.findall(text):
            out.setdefault(fid, []).append(py)
    return out


def find_md_tags() -> dict[str, list[Path]]:
    out: dict[str, list[Path]] = {}
    dirs = [_ROOT, _ROOT / "docs", _ROOT / "docs" / "claude"]
    for d in dirs:
        if not d.exists():
            continue
        for md in d.glob("*.md"):
            text = md.read_text(encoding="utf-8")
            for fid in MD_MARKER.findall(text):
                out.setdefault(fid, []).append(md)
    return out


def main() -> int:
    _load_all_modules()
    registry_ids = set(ids())
    code_tags = find_code_tags()
    md_tags = find_md_tags()

    print(f"Registry: {len(registry_ids)} formulas")
    print(f"  Code tags: {sum(len(v) for v in code_tags.values())} usage trong {len(code_tags)} ID")
    print(f"  MD tags:   {sum(len(v) for v in md_tags.values())} usage trong {len(md_tags)} ID")
    print()

    failed = False

    # 1. Tag không có trong registry
    unknown_code = set(code_tags) - registry_ids
    unknown_md = set(md_tags) - registry_ids
    if unknown_code:
        print("FORMULA-ID trong code nhưng KHÔNG có trong registry:")
        for fid in sorted(unknown_code):
            for p in code_tags[fid]:
                print(f"  ! {fid} → {p.relative_to(_ROOT)}")
        failed = True
    if unknown_md:
        print("FORMULA-ID trong MD nhưng KHÔNG có trong registry:")
        for fid in sorted(unknown_md):
            for p in md_tags[fid]:
                print(f"  ! {fid} → {p.relative_to(_ROOT)}")
        failed = True

    # 2. MD đồng bộ
    print("Kiểm tra MD đã render khớp registry...")
    rc = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "regen_docs.py"), "--check"],
        cwd=str(_ROOT),
    ).returncode
    if rc != 0:
        print("  MD bị drift — chạy `python scripts/regen_docs.py` để cập nhật.")
        failed = True
    else:
        print("  MD đồng bộ.")
    print()

    # 3. Numeric callable hoạt động
    print("Smoke-test numeric callable...")
    broken: list[str] = []
    for fid in sorted(registry_ids):
        f = get(fid)
        if f.numeric is None:
            continue
        try:
            # Cho mọi arg = 1.0
            sig = f.numeric.__code__.co_varnames[: f.numeric.__code__.co_argcount]
            kwargs = {name: 1.0 for name in sig}
            f.numeric(**kwargs)
        except TypeError:
            try:
                f.numeric(1.0)
            except Exception as e:
                broken.append(f"{fid}: {e}")
        except Exception as e:
            broken.append(f"{fid}: {e}")
    if broken:
        print("  Numeric callable lỗi:")
        for b in broken:
            print(f"  ! {b}")
        failed = True
    else:
        print(f"  {sum(1 for fid in registry_ids if get(fid).numeric)} numeric OK.")

    print()
    if failed:
        print("FAIL — sửa lỗi trên rồi chạy lại.")
        return 1
    print("PASS — tất cả formula đồng bộ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
