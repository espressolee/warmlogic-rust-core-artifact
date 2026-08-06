import gc
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path

# Ensure import path
ext_path = os.path.join(os.getcwd(), "warm_logic_rs", "python_packages_v2")
sys.path.insert(0, ext_path)
sys.path.insert(1, os.getcwd())

try:
    import warm_logic_rs

    print(f"Loaded warm_logic_rs v2 from: {warm_logic_rs.__file__}")
    print(f"Module attributes: {dir(warm_logic_rs)}")
except ImportError as e:
    print(f"Failed to load warm_logic_rs: {e}")
    sys.exit(1)


def run_experiment_v2(run_id="bridge_eval_v2"):
    gc.disable()
    sizes = [1, 10, 100, 1000, 10000, 100000, 1000000, 10000000]  # 1B -> 10MB
    base_iterations = 5000  # reduced iterations for deep statistical analysis per size

    print(f"\nRUN_ID: {run_id} | Bridge Evaluation v2 (Deep Forensic)")
    print(f"{'Path':<22} | {'Size':<10} | {'iters':<5} | {'batch':<5} | {'p50 (ns)':<10} | {'p99 (ns)':<10} | {'p99.9 (ns)':<12}")
    print("-" * 92)

    all_results = {
        "metadata": {
            "run_id": run_id,
            "timestamp": time.time(),
            "cpu": os.uname().machine,
            "platform": platform.platform(),
            "python": sys.version,
            "base_iterations": base_iterations,
            "gc_disabled": True,
        },
        "experiments": [],
    }

    for size in sizes:
        bytes_data = b"\x00" * size
        buffer_view = memoryview(bytes_data)

        # Paths to evaluate
        paths = [
            ("Null (PyBytes)", warm_logic_rs.benchmark_zero_copy, bytes_data),
            ("Consume (PyBytes)", warm_logic_rs.benchmark_consume_bridge, bytes_data),
            ("Copy (PyBytes)", warm_logic_rs.benchmark_copy_bridge, bytes_data),
            ("Copy (Vec<u8> arg)", warm_logic_rs.benchmark_copy_vec_arg, bytes_data),
            ("Null (PyBuffer)", warm_logic_rs.benchmark_zero_copy_buffer, buffer_view),
            ("Consume (PyBuffer)", warm_logic_rs.benchmark_consume_buffer, buffer_view),
        ]

        size_str = (
            f"{size}B"
            if size < 1024
            else f"{size // 1024}KB"
            if size < 1024 * 1024
            else f"{size // (1024 * 1024)}MB"
        )

        for name, func, arg in paths:
            latencies = []

            # Warmup
            for _ in range(100):
                func(arg)

            # Batch and iteration selection:
            # - O(1) paths stay batched even at large sizes to reduce timer quantization.
            # - O(N) paths scale down iterations/batching as size grows.
            if name.startswith("Null"):
                iterations = base_iterations
                batch = 100
            elif size <= 10000:
                iterations = base_iterations
                batch = 100 if size <= 1000 else 10
            elif size <= 1000000:
                iterations = 1000
                batch = 10 if size <= 100000 else 1
            else:
                iterations = 200
                batch = 1

            for _ in range(iterations):
                start = time.perf_counter_ns()
                for _ in range(batch):
                    func(arg)
                end = time.perf_counter_ns()
                latencies.append((end - start) / batch)

            latencies.sort()
            p50 = latencies[int(iterations * 0.50)]
            p99 = latencies[int(iterations * 0.99)]
            p999 = latencies[int(iterations * 0.999)]
            avg = statistics.mean(latencies)
            std = statistics.stdev(latencies)

            print(
                f"{name:<22} | {size_str:<10} | {iterations:<5} | {batch:<5} | {p50:<10.1f} | {p99:<10.1f} | {p999:<12.1f}"
            )

            all_results["experiments"].append(
                {
                    "path": name,
                    "size_bytes": size,
                    "iterations": iterations,
                    "batch": batch,
                    "p50": p50,
                    "p99": p99,
                    "p999": p999,
                    "avg": avg,
                    "std": std,
                }
            )

    # Record Internal Timing Calibration
    print("\nCalibrating Internal Boundary Overhead...")
    internal_latencies = []
    big_data = b"\x00" * (10 * 1024 * 1024)  # 10MB
    calibration_iterations = 200
    for _ in range(calibration_iterations):
        _, rust_nanos = warm_logic_rs.benchmark_internal_timer(big_data)
        internal_latencies.append(rust_nanos)

    internal_latencies.sort()
    int_p50 = internal_latencies[int(calibration_iterations * 0.50)]
    print(f"Internal Rust Logic (10MB): p50={int_p50}ns")
    all_results["calibration"] = {"internal_p50": int_p50, "iterations": calibration_iterations}

    # Save Results
    out_dir = Path(f"out/bridge_eval/{run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "full_telemetry.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nForensic Bundle SEALED at {out_dir}/full_telemetry.json")


if __name__ == "__main__":
    run_experiment_v2()
