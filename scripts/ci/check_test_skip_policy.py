#!/usr/bin/env python3
"""Enforce strict skip/xfail policy for tests with expiring allowlist."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = ROOT / "tests"
POLICY_FILE = ROOT / "config" / "security" / "test_skip_policy.json"

@dataclass(frozen=True)
class SkipHit:
    path: str
    line: int
    kind: str

    @property
    def key(self) -> str:
        return f"{self.path}:{self.line}:{self.kind}"


def fail(msg: str) -> None:
    print(f"[TEST-SKIP-POLICY] ERROR: {msg}")
    raise SystemExit(1)


def qualname(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        base = qualname(expr.value)
        if not base:
            return None
        return f"{base}.{expr.attr}"
    return None


def decorator_kind(expr: ast.AST) -> str | None:
    target = expr.func if isinstance(expr, ast.Call) else expr
    qn = qualname(target)
    if qn == "pytest.mark.skipif":
        return "skipif"
    if qn == "pytest.mark.skip":
        return "skip"
    if qn == "pytest.mark.xfail":
        return "xfail"
    return None


def collect_hits() -> list[SkipHit]:
    hits: list[SkipHit] = []
    if not TEST_ROOT.exists():
        fail(f"missing tests directory: {TEST_ROOT}")

    for path in sorted(TEST_ROOT.rglob("test_*.py")):
        rel = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as e:
            fail(f"failed to parse {rel}: {e}")

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for dec in node.decorator_list:
                    kind = decorator_kind(dec)
                    if kind:
                        hits.append(
                            SkipHit(path=rel, line=getattr(dec, "lineno", node.lineno), kind=kind)
                        )
            if isinstance(node, ast.Call):
                if qualname(node.func) == "pytest.skip":
                    hits.append(
                        SkipHit(
                            path=rel,
                            line=getattr(node, "lineno", 1),
                            kind="pytest.skip",
                        )
                    )
    return hits


def load_allowlist() -> dict[str, dict[str, str]]:
    if not POLICY_FILE.exists():
        fail(f"missing policy file: {POLICY_FILE}")

    try:
        payload = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"{POLICY_FILE} contains invalid JSON: {e}")

    if payload.get("schema") != "warmlogic.test_skip_policy.v1":
        fail(f"{POLICY_FILE} has invalid schema: {payload.get('schema')!r}")

    allowlist = payload.get("allowlist")
    if not isinstance(allowlist, list):
        fail(f"{POLICY_FILE} allowlist must be a list")
    max_entries = payload.get("max_allowlist_entries")
    if not isinstance(max_entries, int) or max_entries < 0:
        fail(f"{POLICY_FILE} max_allowlist_entries must be >= 0 integer")
    if len(allowlist) > max_entries:
        fail(
            f"{POLICY_FILE} allowlist exceeds budget: "
            f"{len(allowlist)} > {max_entries}"
        )

    today = date.today()
    out: dict[str, dict[str, str]] = {}
    for item in allowlist:
        if not isinstance(item, dict):
            fail(f"{POLICY_FILE} allowlist entries must be objects")
        path = item.get("path")
        line = item.get("line")
        kind = item.get("kind")
        reason = item.get("reason")
        expires_on = item.get("expires_on")
        if not isinstance(path, str) or not path:
            fail(f"{POLICY_FILE} allowlist entry missing path")
        if not isinstance(line, int) or line < 1:
            fail(f"{POLICY_FILE} allowlist entry {path!r} has invalid line")
        if not isinstance(kind, str) or not kind:
            fail(f"{POLICY_FILE} allowlist entry {path!r} missing kind")
        if not isinstance(reason, str) or not reason:
            fail(f"{POLICY_FILE} allowlist entry {path!r}:{line} missing reason")
        if not isinstance(expires_on, str) or not expires_on:
            fail(
                f"{POLICY_FILE} allowlist entry {path!r}:{line} missing expires_on"
            )
        try:
            expires = date.fromisoformat(expires_on)
        except ValueError:
            fail(
                f"{POLICY_FILE} allowlist entry {path!r}:{line} has invalid "
                f"expires_on (expected YYYY-MM-DD): {expires_on!r}"
            )
        if expires < today:
            fail(
                f"{POLICY_FILE} allowlist entry {path!r}:{line} expired on "
                f"{expires_on}"
            )

        key = f"{path}:{line}:{kind}"
        out[key] = {"reason": reason, "expires_on": expires_on}
    return out


def enforce() -> None:
    hits = collect_hits()
    allowlist = load_allowlist()

    hit_keys = {h.key for h in hits}
    stale = sorted(set(allowlist) - hit_keys)
    if stale:
        fail(
            "stale allowlist entries (marker removed, delete allowlist entry): "
            + ", ".join(stale)
        )

    violations = [h.key for h in hits if h.key not in allowlist]
    if violations:
        fail(
            "unallowlisted skip/xfail markers found:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    print(
        "[TEST-SKIP-POLICY] OK: "
        f"markers={len(hits)}, allowlist={len(allowlist)}"
    )


def main() -> None:
    enforce()


if __name__ == "__main__":
    main()
