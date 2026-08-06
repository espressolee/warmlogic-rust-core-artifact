import argparse
import gc
import json
import os
import platform
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


def measure_corrected_ns_per_call(
    func: Callable[[Any], Any],
    arg: Any,
    *,
    iterations: int,
    batch: int,
    warmup: int,
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
        "warmup": warmup,
        "p50": _quantile(corrected, 0.50),
        "p99": _quantile(corrected, 0.99),
        "avg": statistics.mean(corrected),
        "std": statistics.pstdev(corrected),
        "negatives_clamped": negative,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="warmup_sensitivity")
    parser.add_argument("--size-o1", type=int, default=1_000)
    parser.add_argument("--size-on", type=int, default=10_000_000)
    parser.add_argument("--iterations-o1", type=int, default=2000)
    parser.add_argument("--batch-o1", type=int, default=100)
    parser.add_argument("--iterations-on", type=int, default=80)
    parser.add_argument("--batch-on", type=int, default=1)
    parser.add_argument(
        "--warmups",
        default="0,10,200",
        help="comma-separated warmup values (calls) to test",
    )
    args = parser.parse_args()

    warmups = [int(x.strip()) for x in args.warmups.split(",") if x.strip()]
    if not warmups:
        raise SystemExit("--warmups must contain at least one value")

    gc.disable()

    b_o1 = b"\x00" * args.size_o1
    mv_o1 = memoryview(b_o1)

    b_on = b"\x00" * args.size_on
    mv_on = memoryview(b_on)

    # Paths chosen to cover boundary-only and payload-scaling behavior.
    paths = [
        ("Null (PyBytes)", warm_logic_rs.benchmark_zero_copy, b_o1, args.iterations_o1, args.batch_o1),
        ("Null (PyBuffer)", warm_logic_rs.benchmark_zero_copy_buffer, mv_o1, args.iterations_o1, args.batch_o1),
        ("Copy (PyBytes to_vec)", warm_logic_rs.benchmark_copy_bridge, b_on, args.iterations_on, args.batch_on),
        ("Copy (Vec<u8> arg)", warm_logic_rs.benchmark_copy_vec_arg, b_on, args.iterations_on, args.batch_on),
        ("Consume (PyBytes)", warm_logic_rs.benchmark_consume_bridge, b_on, args.iterations_on, args.batch_on),
    ]

    meta = {
        "run_id": args.run_id,
        "timestamp": time.time(),
        "cpu": os.uname().machine,
        "platform": platform.platform(),
        "python": sys.version,
        "gc_disabled": True,
        "sizes": {"o1": args.size_o1, "on": args.size_on},
        "warmups": warmups,
        "import": {
            "use_installed": use_installed,
            "python_path": ext_path,
            "module_file": getattr(warm_logic_rs, "__file__", None),
        },
    }

    out: dict[str, Any] = {"metadata": meta, "results": {}}

    print("\nWarmup sensitivity (corrected p50 ns/call):")
    for name, func, arg, iterations, batch in paths:
        out["results"][name] = []
        for w in warmups:
            stats = measure_corrected_ns_per_call(func, arg, iterations=iterations, batch=batch, warmup=w)
            out["results"][name].append(stats)
            print(f"- {name:<20} warmup={w:<4}  p50={stats['p50']:.1f}  p99={stats['p99']:.1f}  neg={stats['negatives_clamped']}")

    out_dir = Path("out/bridge_eval/warmup_sensitivity")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.run_id}.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()

