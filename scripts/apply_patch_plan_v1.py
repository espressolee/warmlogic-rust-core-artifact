"""Apply Patch Plan v1 Script (Reconstructed)."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]


def apply_plan(plan_path: Path, risk_level: str = "low") -> int:
    """Apply a patch plan from a JSON file."""
    if not plan_path.exists():
        return 1

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    suggestions = plan.get("suggestions", [])

    for sug in suggestions:
        pattern = sug.get("pattern")
        targets = sug.get("targets", [])

        for t in targets:
            path = Path(t)
            if not path.is_absolute():
                path = ROOT / path

            if not path.exists():
                continue

            if pattern == "P1_HEADER_FIX":
                _fix_header(path)
            elif pattern == "P2_SCHEMA_ALIGN":
                _align_schema(path)

    return 0


def _fix_header(path: Path):
    if path.is_dir():
        for p in path.glob("**/*.py"):
            _fix_header_file(p)
    else:
        _fix_header_file(path)


def _fix_header_file(path: Path):
    if not path.name.endswith(".py"):
        return
    text = path.read_text(encoding="utf-8")
    if "Module:" in text:
        return
    header = f"# ==========================================================\n# Module: {path.name}\n# Project: Warm Logic\n# ==========================================================\n\n"
    path.write_text(header + text, encoding="utf-8")


def _align_schema(path: Path):
    if path.is_dir():
        for p in path.glob("**/*.json"):
            _align_schema_file(p)
    else:
        _align_schema_file(path)


def _align_schema_file(path: Path):
    if not path.name.endswith(".json"):
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Sort keys to align
        text = json.dumps(data, indent=2, sort_keys=True)
        path.write_text(text + "\n", encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        sys.exit(1)
    sys.exit(apply_plan(Path(sys.argv[1])))
