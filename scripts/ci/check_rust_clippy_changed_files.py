#!/usr/bin/env python3
"""Fail CI only when clippy diagnostics touch rust_core files changed in this commit."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def fail(msg: str) -> None:
    print(f"[RUST-CLIPPY-CHANGED] ERROR: {msg}")
    sys.exit(1)


def get_changed_rust_files(base: str, head: str) -> set[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base}..{head}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        fail(f"git diff failed ({proc.returncode}): {proc.stderr.strip()}")

    changed: set[str] = set()
    for raw in proc.stdout.splitlines():
        line = raw.strip().replace("\\", "/")
        if not line.startswith("rust_core/") or not line.endswith(".rs"):
            continue
        changed.add(line[len("rust_core/") :])
    return changed


def normalize_file_path(file_name: str) -> str:
    path = file_name.strip().replace("\\", "/")
    if "/rust_core/" in path:
        path = path.split("/rust_core/", 1)[1]
    elif path.startswith("rust_core/"):
        path = path[len("rust_core/") :]
    if path.startswith("./"):
        path = path[2:]
    return path


def extract_diagnostics(jsonl_path: Path) -> tuple[list[dict], bool | None]:
    diagnostics: list[dict] = []
    build_success: bool | None = None

    with jsonl_path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            reason = payload.get("reason")
            if reason == "build-finished":
                build_success = bool(payload.get("success"))
                continue
            if reason != "compiler-message":
                continue

            msg = payload.get("message", {})
            level = msg.get("level")
            if level not in {"warning", "error"}:
                continue

            spans = msg.get("spans") or []
            span = None
            for candidate in spans:
                if candidate.get("is_primary"):
                    span = candidate
                    break
            if span is None and spans:
                span = spans[0]
            if span is None:
                continue

            file_name = span.get("file_name")
            if not file_name:
                continue

            diagnostics.append(
                {
                    "file": normalize_file_path(file_name),
                    "line": int(span.get("line_start") or 0),
                    "message": str(msg.get("message", "")).splitlines()[0],
                    "level": level,
                }
            )

    return diagnostics, build_success


def filter_changed_file_diagnostics(
    changed_files: set[str], diagnostics: list[dict]
) -> list[dict]:
    return [d for d in diagnostics if d["file"] in changed_files]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonl", required=True, type=Path, help="clippy JSONL output file")
    parser.add_argument("--base", default="HEAD~1", help="base git ref")
    parser.add_argument("--head", default="HEAD", help="head git ref")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.jsonl.exists():
        fail(f"missing clippy output file: {args.jsonl}")

    changed_files = get_changed_rust_files(args.base, args.head)
    diagnostics, build_success = extract_diagnostics(args.jsonl)
    offenders = filter_changed_file_diagnostics(changed_files, diagnostics)

    print(
        "[RUST-CLIPPY-CHANGED] observed:",
        f"changed_rust_files={len(changed_files)}",
        f"diagnostics_total={len(diagnostics)}",
        f"diagnostics_changed_files={len(offenders)}",
    )

    if offenders:
        preview = "\n".join(
            f"- {d['file']}:{d['line']}: {d['message']}" for d in offenders[:40]
        )
        fail(
            "clippy diagnostics found in changed rust files. "
            "Fix changed files before merge.\n"
            f"{preview}"
        )

    if build_success is False and diagnostics:
        print(
            "[RUST-CLIPPY-CHANGED] NOTE: clippy reported debt outside changed files;"
            " changed-file gate passed."
        )
    elif build_success is False and not diagnostics:
        fail("clippy build failed without parsable diagnostics")

    print("[RUST-CLIPPY-CHANGED] OK: no clippy diagnostics in changed rust files")


if __name__ == "__main__":
    main()
