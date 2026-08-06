#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


_BRACE_PATTERN = re.compile(r"\{([^{}]+)\}")


@dataclass(frozen=True)
class ExportPaths:
    paper_dir: Path
    paper_md: Path
    staging_root: Path
    staging_docs_dir: Path


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def _extract_bridge_eval_paths_from_paper(paper_md: Path) -> list[Path]:
    text = paper_md.read_text(encoding="utf-8")
    code_spans = re.findall(r"`(out/bridge_eval/[^`]+)`", text)

    expanded: list[str] = []
    for token in code_spans:
        partial = [token]
        while True:
            next_partial: list[str] = []
            changed = False
            for s in partial:
                match = _BRACE_PATTERN.search(s)
                if not match:
                    next_partial.append(s)
                    continue
                changed = True
                options = [opt.strip() for opt in match.group(1).split(",") if opt.strip()]
                for opt in options:
                    next_partial.append(s[: match.start()] + opt + s[match.end() :])
            partial = next_partial
            if not changed:
                break
        expanded.extend(partial)

    uniq: list[Path] = []
    seen: set[str] = set()
    for s in expanded:
        if s.endswith("...") or s.endswith("myhost_pack.tgz"):
            continue
        if s not in seen:
            seen.add(s)
            uniq.append(Path(s))
    return uniq


def _minimize_copy_set(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    dirs = sorted([p for p in paths if p.is_dir()], key=lambda p: len(str(p)))
    dir_prefixes = [str(d).rstrip("/") + "/" for d in dirs]

    def is_under_dir(p: Path) -> bool:
        s = str(p)
        return any(s.startswith(prefix) for prefix in dir_prefixes)

    files = sorted([p for p in paths if p.is_file() and not is_under_dir(p)], key=str)
    return dirs, files


def _copy_tree(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)


def _sanitize_uname_string(value: str) -> str:
    parts = value.split()
    if len(parts) >= 2:
        parts[1] = "<HOST>"
    return " ".join(parts)


def _sanitize_paths_in_string(value: str) -> str:
    value = re.sub(
        r"/(Users|home)/[^/]+/(?:[^\s/]+/)*WarmLogic-OSS(?:-[^/]+)?/",
        "<WARMLOGIC_OSS_ROOT>/",
        value,
    )
    value = re.sub(
        r"/(Users|home)/[^/]+/(?:[^\s/]+/)*WarmLogic(?:-[^/]+)?/",
        "<WARMLOGIC_ROOT>/",
        value,
    )
    value = re.sub(r"file:///Users/[^/]+/", "file:///Users/<REDACTED>/", value)
    value = re.sub(r"/Users/[^/]+/", "/Users/<REDACTED>/", value)
    value = re.sub(r"/home/[^/]+/", "/home/<REDACTED>/", value)
    return value


def _sanitize_text_blob(text: str) -> str:
    text = _sanitize_paths_in_string(text)
    # Replace hostnames in `uname:` lines.
    def repl_uname(match: re.Match[str]) -> str:
        return f"{match.group(1)}{_sanitize_uname_string(match.group(2))}"

    text = re.sub(r"(^\s*uname:\s*)(.+)$", repl_uname, text, flags=re.MULTILINE)
    # Redact machine identity strings commonly captured in host_info artifacts.
    text = re.sub(
        r"(^\s*machine-id\s*\([^)]*\):\s*)(?!<)[0-9a-fA-F]{16,}\s*$",
        r"\1<MACHINE_ID>\n",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"(^\s*dmi product_uuid:\s*)(?!<)[0-9a-fA-F-]{16,}\s*$",
        r"\1<DMI_UUID>\n",
        text,
        flags=re.MULTILINE,
    )
    # Replace <hostname>.local patterns (macOS).
    text = re.sub(r"\b[A-Za-z0-9._-]+\.local\b", "<HOST>.local", text)
    # Replace obvious private IPs (keep structure, redact value).
    text = re.sub(
        r"\b(10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.(?:\d{1,3}\.)\d{1,3})\b",
        "<PRIVATE_IP>",
        text,
    )
    return text


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if k in {"machine_id_etc", "machine_id_dbus", "dmi_product_uuid"}:
                continue
            if k == "host" and isinstance(v, str) and re.fullmatch(
                r"(10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.(?:\d{1,3}\.)\d{1,3})",
                v,
            ):
                out[k] = "<PRIVATE_IP>"
                continue
            if k in {"uname", "client_uname"} and isinstance(v, str):
                out[k] = _sanitize_uname_string(_sanitize_paths_in_string(v))
                continue
            out[k] = _sanitize_json(v)
        return out
    if isinstance(value, list):
        return [_sanitize_json(v) for v in value]
    if isinstance(value, str):
        return _sanitize_paths_in_string(value)
    return value


def _sanitize_json_file(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    sanitized = _sanitize_json(data)
    path.write_text(json.dumps(sanitized, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _sanitize_text_file(path: Path) -> None:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    path.write_text(_sanitize_text_blob(raw), encoding="utf-8")


def _sanitize_tgz_file(path: Path) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tarfile.open(path, "r:gz") as src, tarfile.open(tmp_path, "w:gz") as dst:
        members = src.getmembers()
        for m in members:
            if m.isdir():
                dst.addfile(m)
                continue
            if not m.isfile():
                continue
            f = src.extractfile(m)
            if f is None:
                continue
            data = f.read()
            name = m.name
            if name.endswith(".json"):
                try:
                    obj = json.loads(data.decode("utf-8"))
                    obj = _sanitize_json(obj)
                    data = (json.dumps(obj, indent=2, sort_keys=False) + "\n").encode("utf-8")
                except Exception:
                    data = _sanitize_text_blob(data.decode("utf-8", errors="ignore")).encode("utf-8")
            elif name.endswith((".md", ".txt")):
                data = _sanitize_text_blob(data.decode("utf-8", errors="ignore")).encode("utf-8")
            info = tarfile.TarInfo(name=m.name)
            info.size = len(data)
            info.mode = m.mode
            info.mtime = m.mtime
            dst.addfile(info, io.BytesIO(data))
    tmp_path.replace(path)


def _post_scan_for_leaks(root: Path) -> list[str]:
    patterns = {
        "username_in_path": re.compile(r"/(Users|home)/[^/]+/"),
        "local_hostname": re.compile(r"\b[A-Za-z0-9._-]+\.local\b"),
        "machine_id": re.compile(r"machine_id_(etc|dbus)|dmi_product_uuid"),
        "machine_id_hostinfo": re.compile(
            r"(machine-id\s*\([^)]*\):\s*)(?!<)[0-9a-fA-F]{16,}|(dmi product_uuid:\s*)(?!<)[0-9a-fA-F-]{16,}"
        ),
        "private_ip": re.compile(
            r"\b(10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.(?:\d{1,3}\.)\d{1,3})\b"
        ),
    }
    violations: list[str] = []
    for path in _iter_files(root):
        if path.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"}:
            continue
        try:
            data = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for name, pat in patterns.items():
            if pat.search(data):
                rel = path.relative_to(root)
                violations.append(f"{name}: {rel}")
                break
    return violations


def _write_manifest(root: Path) -> None:
    lines: list[str] = []
    for path in sorted(_iter_files(root), key=lambda p: str(p.relative_to(root))):
        rel = path.relative_to(root)
        lines.append(f"{_sha256_file(path)}  {rel}")
    (root / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _copy_paper_docs(src_paper_dir: Path, dest_docs_dir: Path) -> None:
    dest_docs_dir.mkdir(parents=True, exist_ok=True)
    include_dirs = {"figures"}
    include_files = {
        "paper.md",
        "09.tex",
        "09.pdf",
        "paper_preview.pdf",
        "cloud_x86_64_vm_guide.md",
        "less_noisy_x86_64_guide.md",
        "aws_table14_guide.md",
        "azure_table14_guide.md",
        "oss_release_prep.md",
        "BRUTAL_AUDIT.md",
        "Score10_Roadmap.md",
        "upstreaming_pyo3.md",
        "pyo3_upstream_pr_template.md",
        "pyo3_vec_u8_fast_path_v0.22.6.patch",
    }
    for name in include_files:
        src = src_paper_dir / name
        if src.exists():
            shutil.copy2(src, dest_docs_dir / name)
    for name in include_dirs:
        src = src_paper_dir / name
        if src.exists() and src.is_dir():
            shutil.copytree(src, dest_docs_dir / name, dirs_exist_ok=True)


def _write_bundle_readme(paths: ExportPaths) -> None:
    source_commit = "UNKNOWN"
    if shutil.which("git") is not None:
        try:
            import subprocess

            source_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=Path(__file__).resolve().parents[2],
                text=True,
            ).strip()
        except Exception:
            source_commit = "UNKNOWN"
    (paths.staging_docs_dir / "SOURCE_COMMIT.txt").write_text(source_commit + "\n", encoding="utf-8")

    readme = f"""# Paper 09 — Boundary Elimination (Public Bundle Staging)

This directory is a **prepare-only** bundle for later copying into `WarmLogic-OSS`.

## Contents
- `paper.md` / `09.pdf` / `09.tex`: paper source and render.
- `figures/`: paper figures.
- `cloud_x86_64_vm_guide.md`: multi-VM replication guide (GCP).
- `aws_table14_guide.md`: two-host network RTT guide.
- `pyo3_vec_u8_fast_path_v0.22.6.patch`: patch referenced by the paper.

## Evidence
All evidence files referenced by the paper are copied under:
- `out/bridge_eval/`

This bundle is **sanitized** for public release:
- Hostnames in `uname` strings are replaced.
- Home-directory absolute paths are redacted.
- Machine IDs and private IPs are removed/redacted.

## Provenance
- Source commit: `{source_commit}`
- Manifest: `MANIFEST.sha256`

## Next step (manual, later)
When you actually decide to publish:
1. Copy `docs/research/papers/09_boundary_elimination/` into the `WarmLogic-OSS` repo.
2. Copy `out/bridge_eval/` sanitized subset into the `WarmLogic-OSS` repo.
3. Run a boundary scan (and visually inspect diffs) before pushing.

**Do not push until you explicitly choose to publish.**
"""
    (paths.staging_docs_dir / "README.md").write_text(readme, encoding="utf-8")


def _resolve_paths(args: argparse.Namespace) -> ExportPaths:
    paper_dir = Path(args.paper_dir)
    paper_md = paper_dir / "paper.md"
    staging_root = Path(args.out).resolve()
    staging_docs_dir = staging_root / "docs" / "research" / "papers" / "09_boundary_elimination"
    return ExportPaths(
        paper_dir=paper_dir.resolve(),
        paper_md=paper_md.resolve(),
        staging_root=staging_root,
        staging_docs_dir=staging_docs_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a public-safe staging bundle for Paper 09 (Boundary Elimination), without publishing."
    )
    parser.add_argument(
        "--paper-dir",
        default="src/warm_logic/docs/papers/09_boundary_elimination",
        help="Source paper directory (private repo).",
    )
    parser.add_argument(
        "--out",
        default="out/oss_staging/paper09_boundary_elimination_bundle",
        help="Output staging directory (safe to delete/recreate).",
    )
    args = parser.parse_args()
    paths = _resolve_paths(args)

    if not paths.paper_md.exists():
        raise SystemExit(f"paper.md not found at {paths.paper_md}")

    if paths.staging_root.exists():
        shutil.rmtree(paths.staging_root)
    paths.staging_root.mkdir(parents=True, exist_ok=True)

    _copy_paper_docs(paths.paper_dir, paths.staging_docs_dir)
    _write_bundle_readme(paths)

    evidence_paths = _extract_bridge_eval_paths_from_paper(paths.paper_md)
    existing = [p for p in evidence_paths if p.exists()]
    dirs, files = _minimize_copy_set(existing)

    for src in dirs + files:
        dst = paths.staging_root / src
        _copy_tree(src, dst)

    for path in _iter_files(paths.staging_root):
        suffix = path.suffix.lower()
        if suffix == ".json":
            _sanitize_json_file(path)
        elif suffix in {".md", ".txt", ".tex"}:
            _sanitize_text_file(path)
        elif suffix in {".tgz"}:
            _sanitize_tgz_file(path)

    _write_manifest(paths.staging_root)

    violations = _post_scan_for_leaks(paths.staging_root)
    if violations:
        print("Leak scan failed; remaining patterns detected:")
        for v in violations:
            print(f"  - {v}")
        return 2

    print(f"Staging bundle written to: {paths.staging_root}")
    print(f"Docs: {paths.staging_docs_dir}")
    print(f"Evidence copied: {len(dirs) + len(files)} items ({len(dirs)} dirs, {len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
