#!/usr/bin/env python3
"""
Paper 09: Cython case study (additional binding-layer example).

This mirrors the pybind11 probe:
  - We do NOT claim cross-framework speed comparisons.
  - We measure *within Cython* how different argument semantics move the cost model
    for bytes-like payloads (sequence-style STL vector conversion vs explicit buffer copy).

This script is self-contained:
  - Creates a venv under out/bridge_eval/cython_case/.venv (cached)
  - Installs cython + build tooling
  - Builds and installs a small extension (scripts/eval/cython_case)
  - Runs empty-loop-corrected latency measurements and writes telemetry JSON
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class SampleParams:
    iterations: int
    batch: int


def _quantile(samples_sorted: list[float], q: float) -> float:
    if not samples_sorted:
        return float("nan")
    idx = int(len(samples_sorted) * q)
    idx = max(0, min(idx, len(samples_sorted) - 1))
    return samples_sorted[idx]


def _iqr(values: list[float]) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    return _quantile(xs, 0.75) - _quantile(xs, 0.25)


def _measure_empty_loop(batch: int) -> int:
    start = time.perf_counter_ns()
    for _ in range(batch):
        pass
    end = time.perf_counter_ns()
    return end - start


def measure_corrected_ns_per_call(
    func: Callable[[Any], Any],
    arg: Any,
    *,
    iterations: int,
    batch: int,
    warmup: int = 200,
) -> dict[str, float | int]:
    for _ in range(warmup):
        func(arg)

    corrected: list[float] = []
    negative = 0
    for _ in range(iterations):
        empty = _measure_empty_loop(batch)

        start = time.perf_counter_ns()
        for _ in range(batch):
            func(arg)
        end = time.perf_counter_ns()

        per_call = (end - start - empty) / batch
        if per_call < 0:
            negative += 1
            per_call = 0.0
        corrected.append(per_call)

    corrected.sort()
    return {
        "iterations": iterations,
        "batch": batch,
        "p50": _quantile(corrected, 0.50),
        "p99": _quantile(corrected, 0.99),
        "negatives_clamped": negative,
    }


def _ensure_venv(venv_dir: Path) -> Path:
    if not venv_dir.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])

    python = venv_dir / "bin" / "python"
    subprocess.check_call([str(python), "-m", "pip", "install", "-U", "pip"])
    subprocess.check_call(
        [str(python), "-m", "pip", "install", "-U", "setuptools", "wheel"]
    )
    cython_version = os.environ.get("CYTHON_VERSION", "3.0.12")
    subprocess.check_call(
        [str(python), "-m", "pip", "install", f"cython=={cython_version}"]
    )
    return python


def _ensure_module(python: Path, *, module_dir: Path) -> None:
    # Avoid PEP517 build isolation for editable installs: setup.py imports Cython at import time.
    subprocess.check_call(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "-e",
            str(module_dir),
        ]
    )


def _reexec_in_venv(venv_python: Path) -> None:
    if os.environ.get("_PAPER09_CYTHON_IN_VENV") == "1":
        return
    env = os.environ.copy()
    env["_PAPER09_CYTHON_IN_VENV"] = "1"
    os.execve(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]], env)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size-bytes", type=int, default=10_000_000)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument(
        "--out",
        default="out/bridge_eval/cython_case/cython_case_telemetry.json",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if os.environ.get("_PAPER09_CYTHON_IN_VENV") != "1":
        venv_dir = Path("out/bridge_eval/cython_case/.venv")
        venv_python = _ensure_venv(venv_dir)
        _ensure_module(venv_python, module_dir=Path("scripts/eval/cython_case"))
        _reexec_in_venv(venv_python)
        raise RuntimeError("execve failed")

    # When running this file as a script, Python puts `scripts/eval` on sys.path[0].
    # Avoid namespace package shadows (same issue as pybind11_case).
    script_dir = str(Path(__file__).resolve().parent)
    sys.path[:] = [p for p in sys.path if os.path.abspath(p) != script_dir]

    import cython_case  # type: ignore[import-not-found]

    size = int(args.size_bytes)
    repeats = int(args.repeats)

    b = b"\x01" * size
    ba = bytearray(b)
    mv = memoryview(b)

    rejects_bytes_for_vector = False
    try:
        cython_case.vec_len(b)
    except TypeError:
        rejects_bytes_for_vector = True

    paths: list[tuple[str, str, Callable[[Any], Any], Any]] = []
    if not rejects_bytes_for_vector:
        paths.append(("bytes", "vector_arg", cython_case.vec_len, b))
    paths.extend(
        [
            ("bytearray", "vector_arg", cython_case.vec_len, ba),
            ("memoryview(bytes)", "vector_arg", cython_case.vec_len, mv),
        ]
    )
    paths.extend(
        [
            ("bytes", "buffer_copy", cython_case.buffer_copy_len, b),
            ("bytearray", "buffer_copy", cython_case.buffer_copy_len, ba),
            ("memoryview(bytes)", "buffer_copy", cython_case.buffer_copy_len, mv),
        ]
    )

    runs: list[dict[str, Any]] = []
    for rep in range(repeats):
        rep_rows: list[dict[str, Any]] = []
        for input_name, mode, fn, arg in paths:
            stats = measure_corrected_ns_per_call(
                fn,
                arg,
                iterations=int(args.iterations),
                batch=int(args.batch),
                warmup=int(args.warmup),
            )
            rep_rows.append(
                {
                    "input": input_name,
                    "mode": mode,
                    "size_bytes": size,
                    "p50": float(stats["p50"]),
                    "p99": float(stats["p99"]),
                    "iterations": int(stats["iterations"]),
                    "batch": int(stats["batch"]),
                    "negatives_clamped": int(stats["negatives_clamped"]),
                }
            )
        runs.append({"repeat": rep, "rows": rep_rows})

    agg: list[dict[str, Any]] = []
    keys = {(r["input"], r["mode"]) for run in runs for r in run["rows"]}
    for input_name, mode in sorted(keys):
        p50s = [
            r["p50"]
            for run in runs
            for r in run["rows"]
            if (r["input"], r["mode"]) == (input_name, mode)
        ]
        p99s = [
            r["p99"]
            for run in runs
            for r in run["rows"]
            if (r["input"], r["mode"]) == (input_name, mode)
        ]
        agg.append(
            {
                "input": input_name,
                "mode": mode,
                "size_bytes": size,
                "repeats": repeats,
                "p50_median": float(statistics.median(p50s)),
                "p50_iqr": float(_iqr(p50s)),
                "p99_median": float(statistics.median(p99s)),
                "p99_iqr": float(_iqr(p99s)),
            }
        )

    out = {
        "metadata": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "rejects_bytes_for_vector": rejects_bytes_for_vector,
        },
        "runs": runs,
        "aggregate": agg,
    }

    out_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
