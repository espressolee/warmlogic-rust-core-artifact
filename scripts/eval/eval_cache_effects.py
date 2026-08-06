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
        "p50": _quantile(corrected, 0.50),
        "p99": _quantile(corrected, 0.99),
        "avg": statistics.mean(corrected),
        "std": statistics.pstdev(corrected),
        "negatives_clamped": negative,
    }


def _paths_hot(b: bytes, mv: memoryview) -> list[tuple[str, Callable[[Any], Any], Any]]:
    return [
        ("Copy (PyBytes to_vec)", warm_logic_rs.benchmark_copy_bridge, b),
        ("Copy (Buffer to_vec)", warm_logic_rs.benchmark_copy_buffer_to_vec, mv),
        ("Copy (BytesVec arg)", warm_logic_rs.benchmark_copy_bytesvec_arg, b),
        ("Copy (Vec<u8> arg)", warm_logic_rs.benchmark_copy_vec_arg, b),
        ("Consume (PyBytes)", warm_logic_rs.benchmark_consume_bridge, b),
    ]


def _paths_streaming(
    bytes_pool: list[bytes],
    mv_pool: list[memoryview],
) -> list[tuple[str, Callable[[Any], Any], Any]]:
    idx_b = 0
    idx_mv = 0

    def next_b() -> bytes:
        nonlocal idx_b
        b = bytes_pool[idx_b]
        idx_b = (idx_b + 1) % len(bytes_pool)
        return b

    def next_mv() -> memoryview:
        nonlocal idx_mv
        mv = mv_pool[idx_mv]
        idx_mv = (idx_mv + 1) % len(mv_pool)
        return mv

    def copy_pybytes(_: Any) -> Any:
        return warm_logic_rs.benchmark_copy_bridge(next_b())

    def copy_buffer(_: Any) -> Any:
        return warm_logic_rs.benchmark_copy_buffer_to_vec(next_mv())

    def copy_bytesvec(_: Any) -> Any:
        return warm_logic_rs.benchmark_copy_bytesvec_arg(next_b())

    def copy_vec_arg(_: Any) -> Any:
        return warm_logic_rs.benchmark_copy_vec_arg(next_b())

    def consume(_: Any) -> Any:
        return warm_logic_rs.benchmark_consume_bridge(next_b())

    return [
        ("Copy (PyBytes to_vec)", copy_pybytes, None),
        ("Copy (Buffer to_vec)", copy_buffer, None),
        ("Copy (BytesVec arg)", copy_bytesvec, None),
        ("Copy (Vec<u8> arg)", copy_vec_arg, None),
        ("Consume (PyBytes)", consume, None),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="cache_effects")
    parser.add_argument("--size", type=int, default=10_000_000)
    parser.add_argument("--pool-count", type=int, default=16)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=20)
    args = parser.parse_args()

    if args.pool_count < 2:
        raise SystemExit("--pool-count must be >= 2")

    gc.disable()

    size = args.size
    pool_count = args.pool_count

    hot_b = b"\x00" * size
    hot_mv = memoryview(hot_b)

    # Use distinct allocations to exceed caches (when possible) while keeping per-call overhead low.
    bytes_pool = [b"\x00" * size for _ in range(pool_count)]
    mv_pool = [memoryview(b) for b in bytes_pool]

    meta = {
        "run_id": args.run_id,
        "timestamp": time.time(),
        "cpu": os.uname().machine,
        "platform": platform.platform(),
        "python": sys.version,
        "gc_disabled": True,
        "import": {
            "use_installed": use_installed,
            "python_path": ext_path,
            "module_file": getattr(warm_logic_rs, "__file__", None),
        },
        "params": {
            "size_bytes": size,
            "pool_count": pool_count,
            "iterations": args.iterations,
            "batch": args.batch,
            "warmup": args.warmup,
        },
    }

    results: dict[str, Any] = {"metadata": meta, "hot": {}, "streaming": {}, "ratios": {}}

    print(f"\nHot vs streaming cache-sensitivity at size={size}B pool={pool_count}")

    for name, func, arg in _paths_hot(hot_b, hot_mv):
        stats = measure_corrected_ns_per_call(
            func, arg, iterations=args.iterations, batch=args.batch, warmup=args.warmup
        )
        results["hot"][name] = stats

    for name, func, arg in _paths_streaming(bytes_pool, mv_pool):
        stats = measure_corrected_ns_per_call(
            func, arg, iterations=args.iterations, batch=args.batch, warmup=args.warmup
        )
        results["streaming"][name] = stats

    for name in results["hot"].keys():
        hot_p50 = float(results["hot"][name]["p50"])
        streaming_p50 = float(results["streaming"][name]["p50"])
        ratio = (streaming_p50 / hot_p50) if hot_p50 > 0 else float("inf")
        results["ratios"][name] = {"p50_ratio_streaming_over_hot": ratio}

    # Print compact summary
    print("\nSummary (corrected p50, ns/call):")
    for name in results["hot"].keys():
        hot_p50 = float(results["hot"][name]["p50"])
        streaming_p50 = float(results["streaming"][name]["p50"])
        ratio = float(results["ratios"][name]["p50_ratio_streaming_over_hot"])
        print(f"- {name:<20} hot={hot_p50:>10.1f}  streaming={streaming_p50:>10.1f}  ratio={ratio:>5.2f}x")

    out_dir = Path("out/bridge_eval/cache_effects")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.run_id}.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()

