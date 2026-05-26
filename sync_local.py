#!/usr/bin/env python3
"""
sync_local.py — Auto-sync worktree đang active → main local (cho Streamlit 8503).

Usage:
    python sync_local.py                # one-shot
    python sync_local.py --watch        # watch mode (mỗi 2s)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
WT_DIR = ROOT / ".claude" / "worktrees"


def find_active_worktree() -> Path | None:
    if not WT_DIR.exists():
        return None
    worktrees = [d for d in WT_DIR.iterdir() if d.is_dir() and (d / ".git").exists()]
    if not worktrees:
        return None
    worktrees.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return worktrees[0]


def get_changed_files(wt: Path) -> list[str]:
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "origin/main..HEAD"],
            cwd=wt, capture_output=True, text=True, encoding="utf-8",
        )
        if r.returncode != 0:
            return []
        return [f.strip() for f in r.stdout.splitlines() if f.strip()]
    except Exception as e:
        print(f"[ERROR] git diff: {e}")
        return []


def sync_files(wt: Path, files: list[str], verbose: bool = True) -> tuple[int, int]:
    n_ok = n_fail = 0
    for f in files:
        src = wt / f
        dst = ROOT / f
        if not src.exists():
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                if (src.stat().st_size == dst.stat().st_size and
                    abs(src.stat().st_mtime - dst.stat().st_mtime) < 1):
                    continue
            shutil.copy2(str(src), str(dst))
            if verbose:
                print(f"  OK    {f}")
            n_ok += 1
        except Exception as e:
            if verbose:
                print(f"  FAIL  {f}: {e}")
            n_fail += 1
    return n_ok, n_fail


def watch_loop(wt: Path, interval: float = 2.0) -> None:
    print(f"[WATCH] Worktree: {wt}")
    print(f"[WATCH] Interval: {interval}s — Ctrl+C để dừng\n")
    last_files: dict[str, float] = {}
    while True:
        try:
            files = get_changed_files(wt)
            changed = []
            for f in files:
                src = wt / f
                if not src.exists():
                    continue
                mt = src.stat().st_mtime
                if last_files.get(f) != mt:
                    last_files[f] = mt
                    changed.append(f)
            if changed:
                ts = time.strftime("%H:%M:%S")
                print(f"[{ts}] {len(changed)} file thay đổi:")
                n_ok, n_fail = sync_files(wt, changed, verbose=True)
                print(f"   → Synced {n_ok} OK, {n_fail} fail\n")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[WATCH] Dừng.")
            break


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--worktree", type=str, default=None)
    args = ap.parse_args()

    wt = Path(args.worktree).resolve() if args.worktree else find_active_worktree()
    if wt is None or not wt.exists():
        print("[ERROR] Không tìm thấy worktree.")
        return 1
    print(f"=== Worktree: {wt} ===\n")

    files = get_changed_files(wt)
    if not files:
        print("[INFO] Không có file branch nào đã sửa.")
        if args.watch:
            watch_loop(wt, args.interval)
        return 0

    print(f"=== {len(files)} file branch đã sửa ===")
    n_ok, n_fail = sync_files(wt, files)
    print(f"\n=== Synced: {n_ok} OK, {n_fail} fail ===")
    if n_ok > 0:
        print("Streamlit http://localhost:8503 sẽ tự reload trong 1-2 giây.")
    if args.watch:
        print()
        watch_loop(wt, args.interval)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
