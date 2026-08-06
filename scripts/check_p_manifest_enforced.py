# ==========================================================
# Module: check_p_manifest_enforced.py
# Project: Warm Logic — Scripts
# Description: Validate diffs against a P-series manifest.
# Author: Warm Logic Dev Team
# ==========================================================

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "spec" / "schema" / "meta" / "p_manifest_v1.schema.json"


Change = Tuple[str, str]


def _default_manifest_sensitivity() -> Dict[str, str]:
    return {
        "privacy": os.environ.get("MANIFEST_SENSITIVITY_PRIVACY", "internal"),
        "ip": os.environ.get("MANIFEST_SENSITIVITY_IP", "standard"),
    }


def _load_manifest(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"manifest missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("sensitivity", _default_manifest_sensitivity())
    return payload


def _validate_manifest(manifest: Dict[str, Any], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(manifest)


def _parse_diff_line(line: str) -> Change | None:
    parts = line.strip().split("\t")
    if not parts or len(parts) < 2:
        return None
    status = parts[0]
    path = parts[-1]
    return status, path


def _run_git_diff(git_range: str | None) -> List[Change]:
    cmd = ["git", "diff", "--name-status"]
    if git_range:
        cmd.append(git_range)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    changes = []
    for line in result.stdout.splitlines():
        parsed = _parse_diff_line(line)
        if parsed:
            changes.append(parsed)
    return changes


def _read_diff_file(path: Path) -> List[Change]:
    lines = path.read_text(encoding="utf-8").splitlines()
    changes = []
    for line in lines:
        parsed = _parse_diff_line(line)
        if parsed:
            changes.append(parsed)
    return changes


def _from_files(files: Iterable[str]) -> List[Change]:
    return [("M", f) for f in files]


def _classify_change(status: str) -> str:
    code = status[0].upper()
    if code == "A":
        return "create"
    if code == "D":
        return "delete"
    return "modify"


def _match(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        if fnmatch(normalized, pattern) or fnmatch(normalized, pattern.rstrip("/")):
            return True
    return False


def _resolve_patterns(manifest: Dict[str, Any], key: str) -> List[str]:
    allowed_key = f"allowed_{key}"
    allowed = manifest.get(allowed_key)
    if isinstance(allowed, list):
        if key in manifest:
            raise ValueError(
                f"manifest specifies both '{key}' and '{allowed_key}'; drop the legacy field"
            )
        return allowed
    if key in manifest:
        raise ValueError(
            f"manifest still uses legacy field '{key}'; regenerate with gen_p_manifest.py"
        )
    return []


def _check_changes(manifest: Dict[str, Any], changes: Iterable[Change]) -> List[str]:
    violations: List[str] = []
    create_patterns = _resolve_patterns(manifest, "create")
    modify_patterns = _resolve_patterns(manifest, "modify")
    delete_patterns = _resolve_patterns(manifest, "delete")

    for status, path in changes:
        kind = _classify_change(status)
        if kind == "create" and _match(path, create_patterns):
            continue
        if kind == "modify" and _match(path, modify_patterns):
            continue
        if kind == "delete" and _match(path, delete_patterns):
            continue
        violations.append(f"{status}\t{path}")

    return violations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check diff against a P manifest")
    parser.add_argument("--p", required=True, help="P identifier (e.g., P23)")
    parser.add_argument("--manifest", required=True, type=Path, help="Path to manifest JSON")
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH, help="Manifest schema path")
    parser.add_argument(
        "--git-range",
        help="Optional git diff range (passed to git diff --name-status)",
    )
    parser.add_argument(
        "--diff-file",
        type=Path,
        help="Optional file with name-status entries to check instead of running git diff",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        help="Explicit file paths (treated as modified) used when other inputs are omitted",
    )
    return parser


def _gather_changes(args: argparse.Namespace) -> List[Change]:
    if args.diff_file:
        return _read_diff_file(args.diff_file)
    if args.files:
        return _from_files(args.files)
    return _run_git_diff(args.git_range)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        manifest = _load_manifest(args.manifest)
        _validate_manifest(manifest, args.schema)
        if manifest.get("P") != args.p:
            print(
                f"[manifest] P mismatch: expected {args.p}, found {manifest.get('P')}",
                file=sys.stderr,
            )
            return 1
        changes = _gather_changes(args)
    except Exception as err:  # pragma: no cover - guarded failure path
        print(f"[manifest] {err}", file=sys.stderr)
        return 1

    if not changes:
        print("[manifest] no changes detected; nothing to enforce")
        return 0

    try:
        violations = _check_changes(manifest, changes)
    except ValueError as err:
        print(f"[manifest] {err}", file=sys.stderr)
        return 1
    if violations:
        print(f"[manifest] {len(violations)} files violate the manifest:", file=sys.stderr)
        for entry in violations:
            print(f"  - {entry}", file=sys.stderr)
        return 1

    print(f"[manifest] all {len(changes)} changes comply with manifest {args.p}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
