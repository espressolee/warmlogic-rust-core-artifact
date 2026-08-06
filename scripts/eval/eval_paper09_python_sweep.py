#!/usr/bin/env python3
"""
Paper 09: CPython minor-version sweep (same host).

This repo builds an abi3-py311 wheel, so the *same* wheel can be installed into multiple
CPython versions (>=3.11) on the same machine. This script runs a small sweep to show
that the key ordering (stock Vec<u8> extraction ≫ patched fast path) is not specific to
one CPython minor version.

Output:
- Telemetry: out/bridge_eval/<run-id>/full_telemetry.json (via eval_bridge_v3.py)
- Summary:   out/bridge_eval/python_sweep/paper09_python_sweep.json (Table 9 input)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = REPO_ROOT / "out" / "bridge_eval"


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print(f"+ {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None, env=env)


def _capture(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def _find_latest_wheel(dir_path: Path) -> Path:
    whls = list(dir_path.glob("*.whl"))
    if not whls:
        raise RuntimeError(f"No wheels found in: {dir_path}")
    return max(whls, key=lambda p: p.stat().st_mtime)


def _python_version(python: Path) -> str:
    return _capture([str(python), "-c", "import sys; print(sys.version.split()[0])"])


def _cp_tag(version: str) -> str:
    # "3.14.2" -> "cp3142"
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    if not m:
        raise ValueError(f"Unexpected version format: {version}")
    return f"cp{m.group(1)}{m.group(2)}{m.group(3)}"


def _ensure_venv(python: Path, venv_dir: Path) -> Path:
    venv_python = venv_dir / "bin" / "python"
    if venv_python.exists():
        return venv_python
    _run([str(python), "-m", "venv", str(venv_dir)])
    if not venv_python.exists():
        raise RuntimeError(f"venv python not found at: {venv_python}")
    return venv_python


def _extract_vec_u8_p50_iqr(telemetry_path: Path, *, size_bytes: int) -> tuple[float, float]:
    data = json.loads(telemetry_path.read_text(encoding="utf-8"))
    for row in data.get("aggregate", []):
        if (
            str(row.get("path")) == "Copy (Vec<u8> arg)"
            and int(row.get("size_bytes")) == size_bytes
        ):
            return float(row["p50_median"]), float(row.get("p50_iqr", 0.0))
    raise RuntimeError(
        f"Missing Copy (Vec<u8> arg) for size={size_bytes} in: {telemetry_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--python",
        action="append",
        default=[],
        help="CPython executable to test (repeatable). Default: python3.13 and python3.14 if found.",
    )
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--size", type=int, default=10_000_000)
    parser.add_argument(
        "--stock-wheel",
        default=None,
        help="Path to the stock wheel (.whl). Default: newest under out/bridge_eval/_stock_pyo3_wheels/",
    )
    parser.add_argument(
        "--patched-wheel",
        default=None,
        help="Path to the patched wheel (.whl). Default: newest under out/bridge_eval/_patched_pyo3_wheels/",
    )
    parser.add_argument(
        "--out",
        default=str(OUT_ROOT / "python_sweep" / "paper09_python_sweep.json"),
    )
    args = parser.parse_args()

    pythons: list[Path] = [Path(p) for p in args.python]
    if not pythons:
        for cand in ("python3.13", "python3.14"):
            p = shutil.which(cand)
            if p:
                pythons.append(Path(p))
    if not pythons:
        pythons = [Path(sys.executable)]

    stock_wheel = (
        Path(args.stock_wheel)
        if args.stock_wheel
        else _find_latest_wheel(OUT_ROOT / "_stock_pyo3_wheels")
    )
    patched_wheel = (
        Path(args.patched_wheel)
        if args.patched_wheel
        else _find_latest_wheel(OUT_ROOT / "_patched_pyo3_wheels")
    )

    sweep_root = OUT_ROOT / "_python_sweep"
    sweep_root.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for python in pythons:
        ver = _python_version(python)
        tag = _cp_tag(ver)
        print(f"\n=== CPython {ver} ({python}) ===")

        # Create isolated venvs per version + per wheel, so we never mix wheels.
        venv_stock = sweep_root / f"{tag}_stock"
        venv_patched = sweep_root / f"{tag}_patched"
        py_stock = _ensure_venv(python, venv_stock)
        py_patched = _ensure_venv(python, venv_patched)

        _run([str(py_stock), "-m", "pip", "install", "--force-reinstall", str(stock_wheel)])
        _run(
            [str(py_patched), "-m", "pip", "install", "--force-reinstall", str(patched_wheel)]
        )

        env = os.environ.copy()
        env["WARM_LOGIC_RS_USE_INSTALLED"] = "1"

        stock_run_id = f"bridge_eval_v3_stock_pyo3_{tag}"
        patched_run_id = f"bridge_eval_v3_pyo3_patch_{tag}"

        _run(
            [
                str(py_stock),
                str(REPO_ROOT / "scripts" / "eval" / "eval_bridge_v3.py"),
                "--run-id",
                stock_run_id,
                "--repeats",
                str(args.repeats),
                "--warmup",
                str(args.warmup),
                "--sizes",
                str(args.size),
            ],
            cwd=REPO_ROOT,
            env=env,
        )
        _run(
            [
                str(py_patched),
                str(REPO_ROOT / "scripts" / "eval" / "eval_bridge_v3.py"),
                "--run-id",
                patched_run_id,
                "--repeats",
                str(args.repeats),
                "--warmup",
                str(args.warmup),
                "--sizes",
                str(args.size),
            ],
            cwd=REPO_ROOT,
            env=env,
        )

        stock_telemetry = OUT_ROOT / stock_run_id / "full_telemetry.json"
        patched_telemetry = OUT_ROOT / patched_run_id / "full_telemetry.json"
        s_p50, s_iqr = _extract_vec_u8_p50_iqr(stock_telemetry, size_bytes=args.size)
        p_p50, p_iqr = _extract_vec_u8_p50_iqr(patched_telemetry, size_bytes=args.size)
        speedup = (s_p50 / p_p50) if p_p50 > 0 else float("nan")

        results.append(
            {
                "python_version": ver,
                "tag": tag,
                "size_bytes": int(args.size),
                "stock": {
                    "run_id": stock_run_id,
                    "p50_median": s_p50,
                    "p50_iqr": s_iqr,
                },
                "patched": {
                    "run_id": patched_run_id,
                    "p50_median": p_p50,
                    "p50_iqr": p_iqr,
                },
                "speedup_p50": speedup,
            }
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "timestamp": time.time(),
                    "size_bytes": int(args.size),
                    "repeats": int(args.repeats),
                    "warmup": int(args.warmup),
                    "stock_wheel": str(stock_wheel),
                    "patched_wheel": str(patched_wheel),
                },
                "results": sorted(results, key=lambda r: r["python_version"]),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()

