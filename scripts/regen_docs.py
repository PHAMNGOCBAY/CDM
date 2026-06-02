"""
regen_docs.py — Tự render LaTeX công thức vào MD từ core.formulas registry.

Cách dùng trong file MD:

    <!-- AUTO-FORMULA: cdm-s1 -->
    $$S_1 = \\dfrac{q \\cdot H}{a \\cdot E_c + (1-a) \\cdot E_s}$$
    <!-- /AUTO-FORMULA -->

Chạy: `python scripts/regen_docs.py`
→ Quét tất cả `*.md` trong project root + docs/ + docs/claude/
→ Replace nội dung giữa marker bằng LaTeX render từ Formula.latex_display.

Idempotent — chạy lại không đổi gì khi MD đã khớp registry.
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

from core.formulas.registry import _load_all_modules, get  # noqa: E402


MARKER = re.compile(
    r"<!--\s*AUTO-FORMULA:\s*([a-z0-9\-]+)\s*-->"
    r"(.*?)"
    r"<!--\s*/AUTO-FORMULA\s*-->",
    re.DOTALL,
)


def regen_text(text: str) -> tuple[str, int, list[str]]:
    """Trả về (new_text, n_blocks, missing_ids)."""
    missing: list[str] = []
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        fid = m.group(1).strip()
        try:
            f = get(fid)
        except KeyError:
            missing.append(fid)
            return m.group(0)
        count += 1
        rendered = f.latex_display
        return (
            f"<!-- AUTO-FORMULA: {fid} -->\n"
            f"{rendered}\n"
            f"<!-- /AUTO-FORMULA -->"
        )

    new_text = MARKER.sub(repl, text)
    return new_text, count, missing


def regen_file(path: Path, check_only: bool = False) -> tuple[int, int, list[str]]:
    """Trả về (n_blocks, n_changed_files, missing_ids)."""
    text = path.read_text(encoding="utf-8")
    new_text, n_blocks, missing = regen_text(text)
    changed = 0
    if new_text != text:
        changed = 1
        if not check_only:
            path.write_text(new_text, encoding="utf-8")
    return n_blocks, changed, missing


def scan_dirs() -> list[Path]:
    """Quét MD trong root + docs/claude/ + docs/."""
    dirs = [_ROOT, _ROOT / "docs", _ROOT / "docs" / "claude"]
    out: list[Path] = []
    for d in dirs:
        if d.exists():
            out.extend(d.glob("*.md"))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate AUTO-FORMULA blocks in MD files.")
    parser.add_argument(
        "--check", action="store_true",
        help="Không ghi file, exit 1 nếu cần regen (dùng cho pre-commit).",
    )
    args = parser.parse_args()

    _load_all_modules()

    total_blocks = 0
    total_changed = 0
    all_missing: dict[Path, list[str]] = {}

    for md in scan_dirs():
        n_blocks, changed, missing = regen_file(md, check_only=args.check)
        if n_blocks:
            rel = md.relative_to(_ROOT)
            mark = "↻" if changed else "·"
            print(f"  {mark} {rel} — {n_blocks} block(s)")
        total_blocks += n_blocks
        total_changed += changed
        if missing:
            all_missing[md] = missing

    print()
    print(f"Tổng cộng: {total_blocks} block, {total_changed} file đã đổi")

    if all_missing:
        print("\nFORMULA-ID thiếu trong registry:")
        for path, mids in all_missing.items():
            for mid in mids:
                print(f"  ! {path.relative_to(_ROOT)} → {mid!r}")
        return 2

    if args.check and total_changed > 0:
        print("\nMD chưa đồng bộ — chạy `python scripts/regen_docs.py` để cập nhật.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
