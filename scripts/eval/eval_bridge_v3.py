import argparse
import ctypes
import gc
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

# Import strategy:
# - Default: load the repo-local extension from warm_logic_rs/python_packages_v2
# - Docker / alternate envs: set WARM_LOGIC_RS_USE_INSTALLED=1 to import the installed wheel
# - Or set WARM_LOGIC_RS_PYTHON_PATH=/path/to/python_packages_dir to override explicitly
use_installed = os.environ.get("WARM_LOGIC_RS_USE_INSTALLED") == "1"
ext_path = os.environ.get("WARM_LOGIC_RS_PYTHON_PATH")
repo_root = os.getcwd()
if not use_installed:
    ext_path = ext_path or os.path.join(
        repo_root, "warm_logic_rs", "python_packages_v2"
    )
    sys.path.insert(0, ext_path)
    sys.path.insert(1, repo_root)
else:
    # Avoid shadowing the installed wheel with a host-built `warm_logic_rs.so`.
    sys.path.append(repo_root)

try:
    import warm_logic_rs

    print(f"Loaded warm_logic_rs from: {warm_logic_rs.__file__}")
except ImportError as e:
    print(f"Failed to load warm_logic_rs: {e}")
    sys.exit(1)


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

    p50 = _quantile(corrected, 0.50)
    p95 = _quantile(corrected, 0.95)
    p99 = _quantile(corrected, 0.99)
    min_val = corrected[0]
    max_val = corrected[-1]
    avg = statistics.mean(corrected)
    std = statistics.pstdev(corrected)

    return {
        "iterations": iterations,
        "batch": batch,
        "min": min_val,
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "max": max_val,
        "avg": avg,
        "std": std,
        "negatives_clamped": negative,
    }


def params_for(path: str, size: int) -> SampleParams:
    o1_paths = {
        "Python noop",
        "C noop",
        "C noop (PyBytes arg)",
        "C noop (PyAny arg)",
        "Null (PyBytes)",
        "Acquire buffer (len_bytes)",
        "Null (PyBuffer)",
    }

    if path in o1_paths:
        return SampleParams(iterations=5000, batch=100)

    # O(N) paths:
    # Keep iteration counts small for very large, very slow cases.
    if size <= 1_000:
        return SampleParams(iterations=5000, batch=100)
    if size <= 100_000:
        return SampleParams(iterations=2000, batch=10)
    if size <= 1_000_000:
        return SampleParams(iterations=500, batch=1)

    # >= 10MB
    if path in {"Copy (Vec<u8> arg)", "Copy (Sequence to Vec<u8>)"}:
        return SampleParams(iterations=30, batch=1)
    return SampleParams(iterations=200, batch=1)


def pointer_checks(size: int) -> dict[str, Any]:
    b = b"\x00" * size
    mv = memoryview(b)

    # Rust pointers
    pybytes_ptr_rust = warm_logic_rs.get_pybytes_buf_ptr(b)
    buffer_ptr_rust = warm_logic_rs.get_buffer_buf_ptr(mv)

    # CPython pointer via C-API
    pyapi = ctypes.pythonapi
    pyapi.PyBytes_AsString.restype = ctypes.c_void_p
    pyapi.PyBytes_AsString.argtypes = [ctypes.py_object]
    pybytes_ptr_ctypes = int(pyapi.PyBytes_AsString(b))

    return {
        "size_bytes": size,
        "pybytes_ptr_rust": int(pybytes_ptr_rust),
        "pybytes_ptr_ctypes": int(pybytes_ptr_ctypes),
        "buffer_ptr_rust": int(buffer_ptr_rust),
        "pybytes_ptr_match": int(pybytes_ptr_rust) == int(pybytes_ptr_ctypes),
        "buffer_ptr_matches_pybytes": int(buffer_ptr_rust) == int(pybytes_ptr_ctypes),
    }


def build_paths(
    bytes_data: bytes, buffer_view: memoryview
) -> list[tuple[str, Callable[[Any], Any], Any]]:
    def py_noop(_: Any) -> int:
        return 0

    return [
        ("Python noop", py_noop, bytes_data),
        ("C noop", lambda _x: warm_logic_rs.benchmark_c_noop(), None),
        ("C noop (PyBytes arg)", warm_logic_rs.benchmark_c_noop_pybytes, bytes_data),
        ("C noop (PyAny arg)", warm_logic_rs.benchmark_c_noop_any, buffer_view),
        ("Null (PyBytes)", warm_logic_rs.benchmark_zero_copy, bytes_data),
        (
            "Acquire buffer (len_bytes)",
            warm_logic_rs.benchmark_acquire_buffer_len,
            buffer_view,
        ),
        ("Null (PyBuffer)", warm_logic_rs.benchmark_zero_copy_buffer, buffer_view),
        ("Copy (PyBytes to_vec)", warm_logic_rs.benchmark_copy_bridge, bytes_data),
        (
            "Copy (Buffer to_vec)",
            warm_logic_rs.benchmark_copy_buffer_to_vec,
            buffer_view,
        ),
        ("Copy (Vec<u8> arg)", warm_logic_rs.benchmark_copy_vec_arg, bytes_data),
        (
            "Copy (Sequence to Vec<u8>)",
            warm_logic_rs.benchmark_copy_sequence_to_vec_u8,
            bytes_data,
        ),
        ("Copy (BytesVec arg)", warm_logic_rs.benchmark_copy_bytesvec_arg, bytes_data),
        ("Consume (PyBytes)", warm_logic_rs.benchmark_consume_bridge, bytes_data),
        ("Consume (PyBuffer)", warm_logic_rs.benchmark_consume_buffer, buffer_view),
        # --- Granular Consume Steps (Scientific Sealing) ---
        ("Consume Step 1: Len", warm_logic_rs.benchmark_consume_step_1_len, bytes_data),
        (
            "Consume Step 2: Head",
            warm_logic_rs.benchmark_consume_step_2_touch_head,
            bytes_data,
        ),
        (
            "Consume Step 3: Tail",
            warm_logic_rs.benchmark_consume_step_3_touch_tail,
            bytes_data,
        ),
        (
            "Consume Step 4: Iter Only",
            warm_logic_rs.benchmark_consume_step_4_full_iter,
            bytes_data,
        ),
        ("Consume Step 5: Sum", warm_logic_rs.benchmark_consume_step_5_sum, bytes_data),
        (
            "Consume Step 6: Hash (Heavy)",
            warm_logic_rs.benchmark_consume_step_6_hash,
            bytes_data,
        ),
    ]


def _try_cmd(cmd: list[str]) -> str | None:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
    except Exception:
        return None


def run_once(sizes: list[int], *, warmup: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for size in sizes:
        bytes_data = b"\x00" * size
        buffer_view = memoryview(bytes_data)

        for path, func, arg in build_paths(bytes_data, buffer_view):
            params = params_for(path, size)

            # Special case: C-noop takes no arg; we pass None through a lambda.
            actual_arg = arg
            if path == "C noop":
                actual_arg = None

            stats = measure_corrected_ns_per_call(
                func,
                actual_arg,
                iterations=params.iterations,
                batch=params.batch,
                warmup=warmup,
            )
            results.append(
                {
                    "path": path,
                    "size_bytes": size,
                    **stats,
                }
            )

    return results


def aggregate_across_runs(all_runs: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, int], dict[str, list[float]]] = {}

    for run in all_runs:
        for row in run:
            key = (row["path"], int(row["size_bytes"]))
            slot = by_key.setdefault(
                key,
                {
                    "min": [],
                    "p50": [],
                    "p95": [],
                    "p99": [],
                    "max": [],
                    "avg": [],
                    "std": [],
                    "neg": [],
                },
            )
            slot["min"].append(float(row["min"]))
            slot["p50"].append(float(row["p50"]))
            slot["p95"].append(float(row["p95"]))
            slot["p99"].append(float(row["p99"]))
            slot["max"].append(float(row["max"]))
            slot["avg"].append(float(row["avg"]))
            slot["std"].append(float(row["std"]))
            slot["neg"].append(float(row["negatives_clamped"]))

    out: list[dict[str, Any]] = []
    for (path, size), series in sorted(
        by_key.items(), key=lambda x: (x[0][0], x[0][1])
    ):
        p50s = sorted(series["p50"])
        p95s = sorted(series["p95"])
        p99s = sorted(series["p99"])
        mins = sorted(series["min"])
        maxs = sorted(series["max"])

        out.append(
            {
                "path": path,
                "size_bytes": size,
                "repeats": len(p50s),
                "p50_median": statistics.median(p50s),
                "p50_iqr": _quantile(p50s, 0.75) - _quantile(p50s, 0.25),
                "p95_median": statistics.median(p95s),
                "p99_median": statistics.median(p99s),
                "min_median": statistics.median(mins),
                "max_median": statistics.median(maxs),
                "negatives_clamped_avg": statistics.mean(series["neg"]),
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="bridge_eval_v3")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument(
        "--sizes",
        default=None,
        help="Comma-separated list of payload sizes in bytes (overrides default sweep).",
    )
    args = parser.parse_args()

    gc.disable()

    # Default: full sweep (0B to 10MB) to show O(1) boundary behavior and O(N) payload scaling.
    if args.sizes:
        sizes = [int(s.strip()) for s in args.sizes.split(",") if s.strip()]
    else:
        sizes = [0, 64, 512, 1024, 4096, 16384, 65536, 262144, 1048576, 4194304, 10000000]

    meta = {
        "run_id": args.run_id,
        "timestamp": time.time(),
        "cpu": os.uname().machine,
        "cpu_count": os.cpu_count(),
        "processor": platform.processor(),
        "platform": platform.platform(),
        "python": sys.version,
        "gc_disabled": True,
        "repeats": args.repeats,
        "warmup": args.warmup,
        "sizes": sizes,
        "import": {
            "use_installed": use_installed,
            "python_path": ext_path,
            "module_file": getattr(warm_logic_rs, "__file__", None),
        },
        "tool_versions": {
            "rustc": _try_cmd(["rustc", "--version"]),
            "cargo": _try_cmd(["cargo", "--version"]),
            "maturin": _try_cmd([sys.executable, "-m", "maturin", "--version"]),
            "pip": _try_cmd([sys.executable, "-m", "pip", "--version"]),
        },
    }

    ptr = pointer_checks(10_000_000)

    runs: list[list[dict[str, Any]]] = []
    for r in range(args.repeats):
        print(f"\n=== Repeat {r + 1}/{args.repeats} ===")
        runs.append(run_once(sizes, warmup=args.warmup))

    agg = aggregate_across_runs(runs)

    out_dir = Path(f"out/bridge_eval/{args.run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "full_telemetry.json"
    out_path.write_text(
        json.dumps(
            {"metadata": meta, "pointer_checks": ptr, "runs": runs, "aggregate": agg},
            indent=2,
        )
    )

    # Print a compact summary for key points
    print("\nSummary (aggregate p50 median, ns/call, corrected):")
    keys = [
        ("C noop", 1_000),
        ("Null (PyBytes)", 1_000),
        ("Null (PyBuffer)", 1_000),
        ("Copy (PyBytes to_vec)", 10_000_000),
        ("Copy (Buffer to_vec)", 10_000_000),
        ("Copy (Vec<u8> arg)", 10_000_000),
        ("Consume (PyBytes)", 10_000_000),
    ]
    index = {(row["path"], row["size_bytes"]): row for row in agg}
    for k in keys:
        row = index.get(k)
        if not row:
            continue
        print(
            f"- {k[0]:<22} size={k[1]:>9}B  p50={row['p50_median']:.1f} ns  (IQR {row['p50_iqr']:.1f})"
        )

    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()
