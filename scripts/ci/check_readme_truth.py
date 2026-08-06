#!/usr/bin/env python3
"""Fail CI when README claims drift from source-of-truth metadata."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"
CARGO = ROOT / "rust_core" / "Cargo.toml"


def fail(msg: str) -> None:
    print(f"[README-TRUTH] ERROR: {msg}")
    sys.exit(1)


def read_text(path: Path) -> str:
    if not path.exists():
        fail(f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def parse_pyproject_version() -> str:
    content = read_text(PYPROJECT)
    m = re.search(
        r"^\[project\][\s\S]*?^\s*version\s*=\s*\"([^\"]+)\"",
        content,
        re.MULTILINE,
    )
    if not m:
        fail("failed to parse pyproject.toml project.version")
    return m.group(1)


def parse_cargo_version() -> str:
    content = read_text(CARGO)
    m = re.search(r'^\s*version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not m:
        fail("failed to parse rust_core/Cargo.toml package.version")
    return m.group(1)


def parse_readme_badge_version(content: str) -> str:
    m = re.search(r"version-([0-9]+\.[0-9]+\.[0-9]+)-blue", content)
    if not m:
        fail("failed to parse README version badge")
    return m.group(1)


def main() -> None:
    readme = read_text(README)
    py_ver = parse_pyproject_version()
    cargo_ver = parse_cargo_version()
    readme_ver = parse_readme_badge_version(readme)

    if len({py_ver, cargo_ver, readme_ver}) != 1:
        fail(
            "version mismatch: "
            f"pyproject={py_ver}, cargo={cargo_ver}, readme_badge={readme_ver}"
        )

    if "Validation Snapshot (Measured)" not in readme:
        fail("README must include 'Validation Snapshot (Measured)' section")

    if "Measured locally on" not in readme:
        fail("README must label metrics as measured with explicit date context")

    if "100% line coverage" in readme:
        fail("README contains overclaim: '100% line coverage'")

    print(
        "[README-TRUTH] OK: version sync and measured-claims guard passed "
        f"(version={py_ver})"
    )


if __name__ == "__main__":
    main()
