#!/usr/bin/env python3
"""
Paper 09: summarize Table 19 hit crates into a reviewer-friendly candidate list.

Input: JSON snapshot produced by scan_pyo3_vec_u8_prevalence.py
Output: Markdown table with crate/version/downloads/pyo3-version and a short signature pointer.
"""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from pathlib import Path
from typing import Any


RE_PYO3_VERSION_BLOCK = re.compile(
    r"(?sm)^\[dependencies\.pyo3\]\s+.*?^version\s*=\s*\"([^\"]+)\""
)
RE_PYO3_VERSION_INLINE = re.compile(
    r"(?m)^\s*pyo3\s*=\s*\{\s*version\s*=\s*\"([^\"]+)\""
)
RE_PYO3_VERSION_DOT = re.compile(r"(?m)^\s*dependencies\.pyo3\.version\s*=\s*\"([^\"]+)\"")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_cargo_toml_from_crate(crate_file: Path, *, crate: str, version: str) -> str | None:
    cargo_path = f"{crate}-{version}/Cargo.toml"
    try:
        with tarfile.open(crate_file, "r:gz") as tf:
            try:
                m = tf.getmember(cargo_path)
            except KeyError:
                return None
            f = tf.extractfile(m)
            if f is None:
                return None
            raw = f.read()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None


def _extract_pyo3_version(cargo_toml: str) -> str | None:
    for rx in (RE_PYO3_VERSION_BLOCK, RE_PYO3_VERSION_INLINE, RE_PYO3_VERSION_DOT):
        m = rx.search(cargo_toml)
        if m:
            return m.group(1).strip()
    return None


def _fmt_sig(example: dict[str, Any]) -> str:
    sig = str(example.get("signature") or "").strip()
    sig = re.sub(r"\s+", " ", sig)
    if len(sig) > 140:
        sig = sig[:137] + "…"
    file = str(example.get("file") or "").strip()
    line = example.get("line")
    loc = f"{file}:{int(line)}" if file and isinstance(line, int | float) else (file or "")
    if loc:
        return f"`{loc}` — `{sig}`"
    return f"`{sig}`"


def main() -> None:
    p = argparse.ArgumentParser(
        description="Paper 09: summarize Table 19 hit crates (Vec<u8> prevalence scan)"
    )
    p.add_argument(
        "--input",
        default="out/bridge_eval/pyo3_vec_u8_prevalence/pyo3_vec_u8_prevalence_top500.json",
        help="input JSON snapshot from scan_pyo3_vec_u8_prevalence.py",
    )
    p.add_argument(
        "--cache-dir",
        default="out/bridge_eval/_crates_cache",
        help="crates.io .crate cache directory",
    )
    p.add_argument(
        "--out",
        default="src/warm_logic/docs/papers/09_boundary_elimination/pyo3_vec_u8_case_study_candidates.md",
        help="output markdown path",
    )
    args = p.parse_args()

    data = _read_json(Path(args.input))
    crates = list(data.get("crates") or [])
    hit_crates = [c for c in crates if c.get("has_vec_u8_arg")]
    hit_crates.sort(key=lambda c: int(c.get("downloads") or 0), reverse=True)

    cache_dir = Path(args.cache_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    md: list[str] = []
    md.append("# Table 19 case study candidates (PyO3 `Vec<u8>` args)\n")
    md.append(
        "This list is derived from the Table 19 crates.io snapshot scan. It is **not** a usage study.\n"
    )
    md.append("\n## Hit crates\n")
    md.append("| Crate | Version | Downloads | Declared `pyo3` dep | Example hit |\n")
    md.append("|---|---:|---:|---:|---|\n")

    for c in hit_crates:
        name = str(c.get("crate") or "").strip()
        ver = str(c.get("version") or "").strip()
        downloads = int(c.get("downloads") or 0)
        crate_file = cache_dir / f"{name}-{ver}.crate"

        pyo3_ver = "N/A"
        cargo = _read_cargo_toml_from_crate(crate_file, crate=name, version=ver)
        if cargo:
            pyo3_extracted = _extract_pyo3_version(cargo)
            if pyo3_extracted:
                pyo3_ver = pyo3_extracted

        examples = list(c.get("examples") or [])
        ex = _fmt_sig(examples[0]) if examples else "N/A"

        md.append(
            f"| `{name}` | `{ver}` | {downloads:,} | `{pyo3_ver}` | {ex} |\n"
        )

    md.append("\n## Notes\n")
    md.append("- `pyo3` dependency version is best-effort from published `Cargo.toml`.\n")
    md.append(
        "- Some hits are nested types (e.g., `HashMap<String, Vec<u8>>`), not necessarily a direct byte payload.\n"
    )
    md.append(
        "- A strong-accept upgrade path is to pick one candidate and reproduce the conversion cliff on its public API.\n"
    )

    out_path.write_text("".join(md), encoding="utf-8")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
