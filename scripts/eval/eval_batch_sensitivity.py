import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

# Import strategy matches eval_bridge_v3.py:
# - Default: load the repo-local extension from warm_logic_rs/python_packages_v2
# - Docker / alternate envs: set WARM_LOGIC_RS_USE_INSTALLED=1 to import the installed wheel
# - Or set WARM_LOGIC_RS_PYTHON_PATH=/path/to/python_packages_dir to override explicitly
use_installed = os.environ.get("WARM_LOGIC_RS_USE_INSTALLED") == "1"
ext_path = os.environ.get("WARM_LOGIC_RS_PYTHON_PATH")
repo_root = os.getcwd()
if not use_installed:
    ext_path = ext_path or os.path.join(repo_root, "warm_logic_rs", "python_packages_v2")
    sys.path.insert(0, ext_path)
    sys.path.insert(1, repo_root)
else:
    sys.path.append(repo_root)

try:
    import warm_logic_rs

    print(f"Loaded warm_logic_rs from: {warm_logic_rs.__file__}")
except ImportError as e:
    print(f"Failed to load warm_logic_rs: {e}")
    sys.exit(1)


def _quantile(samples_sorted: list[float], q: float) -> float:
    if not samples_sorted:
        return float("nan")
    idx = int(len(samples_sorted) * q)
    idx = max(0, min(idx, len(samples_sorted) - 1))
    return samples_sorted[idx]


def _measure_empty_loop(batch: int) -> int:
    start = time.perf_counter_ns()
    for _ in range(batch):
        pass
    end = time.perf_counter_ns()
    return end - start


def measure(
    func: Callable[[Any], Any],
    arg: Any,
    *,
    iterations: int,
    batch: int,
    corrected: bool,
) -> dict[str, float | int]:
    # Warmup
    for _ in range(500):
        func(arg)

    samples: list[float] = []
    negatives = 0
    for _ in range(iterations):
        empty = _measure_empty_loop(batch) if corrected else 0

        start = time.perf_counter_ns()
        for _ in range(batch):
            func(arg)
        end = time.perf_counter_ns()

        v = (end - start - empty) / batch
        if corrected and v < 0:
            negatives += 1
            v = 0.0
        samples.append(v)

    samples.sort()
    return {
        "iterations": iterations,
        "batch": batch,
        "p50": _quantile(samples, 0.50),
        "p99": _quantile(samples, 0.99),
        "avg": statistics.mean(samples),
        "std": statistics.pstdev(samples),
        "negatives_clamped": negatives,
        "corrected": corrected,
    }


def main() -> None:
    size = 1000
    data = b"\x00" * size
    mv = memoryview(data)

    def py_noop(_: Any) -> int:
        return 0

    paths: list[tuple[str, Callable[[Any], Any], Any]] = [
        ("Python noop", py_noop, data),
        ("C noop", lambda _x: warm_logic_rs.benchmark_c_noop(), None),
        ("Null (PyBytes)", warm_logic_rs.benchmark_zero_copy, data),
        ("Null (PyBuffer)", warm_logic_rs.benchmark_zero_copy_buffer, mv),
    ]

    batches = [1, 10, 100, 1000]
    iterations = 5000

    out: dict[str, Any] = {
        "metadata": {"size_bytes": size, "iterations": iterations, "batches": batches},
        "results": [],
    }

    for corrected in [False, True]:
        print(f"\n=== {'Corrected' if corrected else 'Uncorrected'} ===")
        print(f"{'Path':<18} {'batch':>6} {'p50(ns)':>10} {'p99(ns)':>10} {'neg':>6}")
        for path, func, arg in paths:
            for batch in batches:
                stats = measure(func, arg, iterations=iterations, batch=batch, corrected=corrected)
                out["results"].append({"path": path, **stats})
                print(
                    f"{path:<18} {batch:>6} {stats['p50']:>10.2f} {stats['p99']:>10.2f} {stats['negatives_clamped']:>6}"
                )

    out_dir = Path("out/bridge_eval/batch_sensitivity")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "batch_sensitivity.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()
