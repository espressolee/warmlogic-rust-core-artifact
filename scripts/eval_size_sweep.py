import json
import os
import statistics
import sys
import time
from pathlib import Path

# Ensure import path
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import warm_logic_rs
except ImportError:
    print("Error: warm_logic_rs module not found.")
    sys.exit(1)


def run_sweep(run_id="bridge_eval_v1"):
    # sweep: 1B -> 10MB
    sizes = [1, 10, 100, 1000, 10000, 100000, 1000000, 10000000]
    iterations = 10000

    results = []

    print(f"RUN_ID: {run_id} | Experiment: A1 (Size Sweep)")
    print(f"{'Size (B)':<12} | {'p50 (ns)':<12} | {'p99 (ns)':<12} | {'p999 (ns)':<12}")
    print("-" * 60)

    for size in sizes:
        data = b"x" * size
        latencies = []

        # Warmup
        for _ in range(100):
            warm_logic_rs.benchmark_zero_copy(data)

        for _ in range(iterations):
            start = time.perf_counter_ns()
            warm_logic_rs.benchmark_zero_copy(data)
            end = time.perf_counter_ns()
            latencies.append(end - start)

        latencies.sort()
        p50 = latencies[int(iterations * 0.50)]
        p99 = latencies[int(iterations * 0.99)]
        p999 = latencies[int(iterations * 0.999)]

        print(f"{size:<12} | {p50:<12.2f} | {p99:<12.2f} | {p999:<12.2f}")
        results.append(
            {
                "size_bytes": size,
                "p50_ns": p50,
                "p99_ns": p99,
                "p999_ns": p999,
                "raw": latencies[:100],  # store some raw for forensic
            }
        )

    # Save results
    out_dir = Path(f"out/bridge_eval/{run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "results_a1.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {out_dir}/results_a1.json")


if __name__ == "__main__":
    run_sweep()
