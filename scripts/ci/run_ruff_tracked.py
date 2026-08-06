#!/usr/bin/env python3
"""Run ruff only on git-tracked Python files within given scopes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    scopes = sys.argv[1:] or ["src/warm_logic"]

    git_cmd = ["git", "ls-files", "-z", "--", *scopes]
    try:
        tracked = subprocess.check_output(git_cmd)
    except subprocess.CalledProcessError as exc:
        print(f"[RUFF-TRACKED] git ls-files failed: {exc}", file=sys.stderr)
        return 2

    files = [entry.decode("utf-8") for entry in tracked.split(b"\0") if entry]
    py_files = [path for path in files if Path(path).suffix == ".py"]
    existing_py_files = [path for path in py_files if Path(path).is_file()]
    missing_py_files = [path for path in py_files if not Path(path).is_file()]

    if missing_py_files:
        sample = ", ".join(missing_py_files[:3])
        extra = "" if len(missing_py_files) <= 3 else " ..."
        print(
            f"[RUFF-TRACKED] skipped {len(missing_py_files)} missing tracked paths: {sample}{extra}",
            file=sys.stderr,
        )

    if not existing_py_files:
        print(f"[RUFF-TRACKED] no existing tracked Python files under: {', '.join(scopes)}")
        return 0

    ruff_cmd = [sys.executable, "-m", "ruff", "check", *existing_py_files]
    return subprocess.call(ruff_cmd)


if __name__ == "__main__":
    raise SystemExit(main())
