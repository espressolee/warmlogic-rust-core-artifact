#!/usr/bin/env python3
"""
Paper 09: ecosystem-prevalence probe for `Vec<u8>` in PyO3-exposed APIs.

Motivation (ASPLOS reviewer-proofing):
  - The paper's main empirical result is about a *signature→conversion-policy* choice:
      bytes-like input + `Vec<u8>` argument can compile into sequence-style extraction.
  - A fair reviewer question is: "Is `Vec<u8>` a contrived API shape, or does it occur in the wild?"
  - This script runs a conservative crates.io snapshot scan to quantify how often Python-exposed APIs
    (#[pyfunction] and #[pymethods]) mention `Vec<u8>` in argument lists.

Important limitations (do not overclaim):
  - This is a regex/state-machine pass over source tarballs (no macro expansion; no Rust parsing).
  - Counts are a *lower bound* (generated code may be missed) and can also include cfg-gated code.
  - Presence of `Vec<u8>` does not prove users pass `bytes` at runtime; it only shows the API shape exists.

Output:
  - JSON snapshot (default under out/bridge_eval/pyo3_vec_u8_prevalence/)
  - Markdown summary alongside it (human-readable)
"""

from __future__ import annotations

import argparse
import json
import re
import tarfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CRATES_IO = "https://crates.io"
REVERSE_DEPS_API = f"{CRATES_IO}/api/v1/crates/pyo3/reverse_dependencies"

RE_VEC_U8 = re.compile(r"Vec\s*<\s*u8\s*>")
RE_PYFUNCTION_ATTR = re.compile(r"#\s*\[\s*(?:pyo3::)?pyfunction\b")
RE_PYMETHODS_ATTR = re.compile(r"#\s*\[\s*(?:pyo3::)?pymethods\b")


@dataclass(frozen=True)
class CrateVersion:
    crate: str
    version: str
    downloads: int
    dl_path: str
    yanked: bool


def _http_json(url: str, *, timeout_s: float) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WarmLogic/Paper09-PrevalenceScan (contact: local)",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        return json.load(r)


def _download(url: str, *, out_path: Path, timeout_s: float) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "WarmLogic/Paper09-PrevalenceScan (contact: local)"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as r, out_path.open("wb") as f:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)


def _iter_unique_top_reverse_deps(*, limit: int, timeout_s: float) -> list[CrateVersion]:
    """
    Crates.io reverse_dependencies returns *versions* that depend on pyo3 (often optionally).
    We de-duplicate by crate name, taking the first occurrence (API appears sorted by downloads).
    """
    selected: list[CrateVersion] = []
    seen: set[str] = set()
    page = 1
    per_page = 100
    while len(selected) < limit:
        url = f"{REVERSE_DEPS_API}?page={page}&per_page={per_page}"
        data = _http_json(url, timeout_s=timeout_s)

        versions = data.get("versions") or []
        if not versions:
            break

        for v in versions:
            name = str(v.get("crate") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            selected.append(
                CrateVersion(
                    crate=name,
                    version=str(v.get("num") or ""),
                    downloads=int(v.get("downloads") or 0),
                    dl_path=str(v.get("dl_path") or ""),
                    yanked=bool(v.get("yanked") or False),
                )
            )
            if len(selected) >= limit:
                break
        page += 1
    return selected


def _extract_paren_block(signature: str) -> str | None:
    """
    Return the first (...) block in `signature`, accounting for nesting.
    This is a heuristic intended for `fn name(args...) -> ...`.
    """
    try:
        start = signature.index("(")
    except ValueError:
        return None
    depth = 0
    for i in range(start, len(signature)):
        ch = signature[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return signature[start + 1 : i]
    return None


def _scan_pyfunctions(text: str) -> tuple[int, int, list[dict[str, Any]]]:
    """
    Returns:
      (pyfunction_total, pyfunction_with_vec_u8, examples[])
    """
    lines = text.splitlines()
    total = 0
    with_vec = 0
    examples: list[dict[str, Any]] = []

    pending = False
    sig_lines: list[str] = []
    sig_start_line = 0

    for idx, line in enumerate(lines, start=1):
        if RE_PYFUNCTION_ATTR.search(line):
            pending = True
            sig_lines = []
            sig_start_line = 0
            continue

        if not pending:
            continue

        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#[") or stripped.startswith("///") or stripped.startswith("//"):
            continue

        if sig_start_line == 0:
            if "fn " not in stripped:
                continue
            sig_start_line = idx
            sig_lines.append(stripped)
        else:
            sig_lines.append(stripped)

        sig = " ".join(sig_lines)
        if "{" in sig or sig.endswith(";"):
            pending = False
            total += 1
            args = _extract_paren_block(sig) or ""
            hits = list(RE_VEC_U8.finditer(args))
            if hits:
                with_vec += 1
                examples.append(
                    {
                        "line": sig_start_line,
                        "signature": sig[:300],
                        "vec_u8_occurrences": len(hits),
                    }
                )
            sig_lines = []
            sig_start_line = 0

    return total, with_vec, examples


def _scan_pymethods(text: str) -> tuple[int, int, list[dict[str, Any]]]:
    """
    Scan `#[pymethods] impl ... { ... }` blocks and count method signatures.

    Returns:
      (pymethod_total, pymethod_with_vec_u8, examples[])
    """
    lines = text.splitlines()
    total = 0
    with_vec = 0
    examples: list[dict[str, Any]] = []

    pending_attr = False
    in_impl = False
    brace_depth = 0
    sig_lines: list[str] = []
    sig_start_line = 0

    for idx, line in enumerate(lines, start=1):
        if RE_PYMETHODS_ATTR.search(line):
            pending_attr = True
            in_impl = False
            brace_depth = 0
            sig_lines = []
            sig_start_line = 0
            continue

        if not pending_attr:
            continue

        stripped = line.strip()
        if not stripped:
            continue

        if not in_impl:
            # Skip attributes/docs between #[pymethods] and `impl ... {`
            if stripped.startswith("#[") or stripped.startswith("///") or stripped.startswith("//"):
                continue
            if "impl" not in stripped:
                continue
            in_impl = True

        # Update brace depth (heuristic; ignores strings/comments).
        brace_depth += line.count("{")
        brace_depth -= line.count("}")

        if brace_depth < 0:
            # Malformed scan state; reset.
            pending_attr = False
            in_impl = False
            brace_depth = 0
            sig_lines = []
            sig_start_line = 0
            continue

        # Only consider method signatures at the top level inside the impl block.
        if brace_depth == 1:
            if sig_start_line == 0:
                if "fn " not in stripped:
                    if brace_depth == 0:
                        pending_attr = False
                    continue
                sig_start_line = idx
                sig_lines.append(stripped)
            else:
                sig_lines.append(stripped)

            sig = " ".join(sig_lines)
            if "{" in sig or sig.endswith(";"):
                total += 1
                args = _extract_paren_block(sig) or ""
                hits = list(RE_VEC_U8.finditer(args))
                if hits:
                    with_vec += 1
                    examples.append(
                        {
                            "line": sig_start_line,
                            "signature": sig[:300],
                            "vec_u8_occurrences": len(hits),
                        }
                    )
                sig_lines = []
                sig_start_line = 0

        if in_impl and brace_depth == 0:
            pending_attr = False
            in_impl = False
            sig_lines = []
            sig_start_line = 0

    return total, with_vec, examples


def _scan_crate_tarball(crate_path: Path) -> dict[str, Any]:
    """
    Scan the .crate tarball (tar.gz) and return per-crate stats.
    """
    pyfunction_total = 0
    pyfunction_with_vec = 0
    pymethod_total = 0
    pymethod_with_vec = 0

    examples: list[dict[str, Any]] = []

    with tarfile.open(crate_path, "r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile() or not m.name.endswith(".rs"):
                continue
            f = tf.extractfile(m)
            if f is None:
                continue
            raw = f.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")

            pf_total, pf_with, pf_examples = _scan_pyfunctions(text)
            pm_total, pm_with, pm_examples = _scan_pymethods(text)

            if pf_total or pm_total:
                pyfunction_total += pf_total
                pyfunction_with_vec += pf_with
                pymethod_total += pm_total
                pymethod_with_vec += pm_with

                for e in pf_examples:
                    e2 = dict(e)
                    e2.update({"file": m.name, "kind": "pyfunction"})
                    examples.append(e2)
                for e in pm_examples:
                    e2 = dict(e)
                    e2.update({"file": m.name, "kind": "pymethod"})
                    examples.append(e2)

    has_exports = (pyfunction_total + pymethod_total) > 0
    has_vec = (pyfunction_with_vec + pymethod_with_vec) > 0
    return {
        "has_pyo3_exports": has_exports,
        "has_vec_u8_arg": has_vec,
        "pyfunction_total": pyfunction_total,
        "pyfunction_with_vec_u8": pyfunction_with_vec,
        "pymethod_total": pymethod_total,
        "pymethod_with_vec_u8": pymethod_with_vec,
        "examples": examples,
    }


def _render_markdown(summary: dict[str, Any]) -> str:
    md = []
    meta = summary["metadata"]
    agg = summary["aggregate"]
    md.append("# PyO3 `Vec<u8>` prevalence snapshot (Paper 09)\n")
    md.append(f"- Timestamp: {meta['timestamp']}\n")
    md.append(f"- Crates scanned (unique, reverse-deps of `pyo3`): {agg['crates_scanned']}\n")
    md.append(f"- Crates with any PyO3 exports: {agg['crates_with_pyo3_exports']}\n")
    md.append(f"- Crates with exported `Vec<u8>` args: {agg['crates_with_vec_u8_arg']}\n")
    md.append("\n## Aggregate counts\n")
    md.append("| Metric | Value |\n")
    md.append("|---|---:|\n")
    md.append(f"| Pyfunctions scanned | {agg['pyfunction_total']} |\n")
    md.append(f"| Pyfunctions with `Vec<u8>` arg | {agg['pyfunction_with_vec_u8']} |\n")
    md.append(f"| Pymethods scanned | {agg['pymethod_total']} |\n")
    md.append(f"| Pymethods with `Vec<u8>` arg | {agg['pymethod_with_vec_u8']} |\n")
    md.append("\n## Notes\n")
    md.append(
        "- This is a heuristic scan (no macro expansion, no Rust parsing). Treat counts as a lower bound.\n"
    )
    md.append(
        "- Presence of `Vec<u8>` in a Python-exposed signature does not prove runtime callers pass `bytes`.\n"
    )
    return "".join(md)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Paper 09: scan crates.io reverse deps for PyO3-exposed `Vec<u8>` args"
    )
    p.add_argument("--limit", type=int, default=200, help="unique crates to scan (default: 200)")
    p.add_argument(
        "--cache-dir",
        default="out/bridge_eval/_crates_cache",
        help="download cache for .crate tarballs (default: out/bridge_eval/_crates_cache)",
    )
    p.add_argument(
        "--out",
        default="out/bridge_eval/pyo3_vec_u8_prevalence/pyo3_vec_u8_prevalence.json",
        help="output JSON path",
    )
    p.add_argument(
        "--timeout-s",
        type=float,
        default=30.0,
        help="network timeout seconds (default: 30)",
    )
    p.add_argument(
        "--max-examples-per-crate",
        type=int,
        default=3,
        help="cap stored signature examples per crate (default: 3)",
    )
    args = p.parse_args()

    cache_dir = Path(args.cache_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    crates = _iter_unique_top_reverse_deps(limit=int(args.limit), timeout_s=float(args.timeout_s))
    print(f"[scan] selected {len(crates)} unique crates (reverse deps of pyo3)")

    results: list[dict[str, Any]] = []
    agg = {
        "crates_scanned": 0,
        "crates_with_pyo3_exports": 0,
        "crates_with_vec_u8_arg": 0,
        "pyfunction_total": 0,
        "pyfunction_with_vec_u8": 0,
        "pymethod_total": 0,
        "pymethod_with_vec_u8": 0,
    }

    for i, cv in enumerate(crates, start=1):
        agg["crates_scanned"] += 1
        crate_url = cv.dl_path
        if crate_url.startswith("/"):
            crate_url = CRATES_IO + crate_url
        if not crate_url:
            print(f"[scan] {i}/{len(crates)} {cv.crate} {cv.version}: missing dl_path, skipping")
            continue

        crate_file = cache_dir / f"{cv.crate}-{cv.version}.crate"
        if not crate_file.exists():
            print(f"[scan] {i}/{len(crates)} download {cv.crate} {cv.version} ({cv.downloads} dl)")
            _download(crate_url, out_path=crate_file, timeout_s=float(args.timeout_s))
        else:
            print(f"[scan] {i}/{len(crates)} cache {cv.crate} {cv.version}")

        try:
            s = _scan_crate_tarball(crate_file)
        except Exception as e:  # noqa: BLE001
            print(f"[scan] {cv.crate} {cv.version}: ERROR scanning tarball: {e}")
            continue

        if s["has_pyo3_exports"]:
            agg["crates_with_pyo3_exports"] += 1
        if s["has_vec_u8_arg"]:
            agg["crates_with_vec_u8_arg"] += 1

        agg["pyfunction_total"] += int(s["pyfunction_total"])
        agg["pyfunction_with_vec_u8"] += int(s["pyfunction_with_vec_u8"])
        agg["pymethod_total"] += int(s["pymethod_total"])
        agg["pymethod_with_vec_u8"] += int(s["pymethod_with_vec_u8"])

        examples = list(s["examples"])
        examples.sort(key=lambda x: (x.get("kind", ""), x.get("file", ""), int(x.get("line", 0))))
        examples = examples[: int(args.max_examples_per_crate)]

        results.append(
            {
                "crate": cv.crate,
                "version": cv.version,
                "downloads": cv.downloads,
                "yanked": cv.yanked,
                **{k: v for k, v in s.items() if k != "examples"},
                "examples": examples,
            }
        )

    payload = {
        "metadata": {
            "timestamp": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {
                "crates_io_reverse_deps": REVERSE_DEPS_API,
                "crate": "pyo3",
                "selection": "top-by-downloads (reverse dependencies; de-duplicated by crate name)",
            },
            "scan": {
                "limit": int(args.limit),
                "max_examples_per_crate": int(args.max_examples_per_crate),
                "match": {
                    "pyfunction_attr": RE_PYFUNCTION_ATTR.pattern,
                    "pymethods_attr": RE_PYMETHODS_ATTR.pattern,
                    "vec_u8": RE_VEC_U8.pattern,
                },
                "limitations": [
                    "heuristic scan (no macro expansion; no Rust parsing)",
                    "lower bound: generated/expanded code may be missed",
                    "cfg-gated code may be present in tarball but not compiled",
                    "API-shape prevalence != runtime usage prevalence",
                ],
            },
        },
        "aggregate": agg,
        "crates": results,
    }

    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[scan] Wrote: {out_path}")

    md_path = out_path.with_suffix(".md")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    print(f"[scan] Wrote: {md_path}")


if __name__ == "__main__":
    main()

