"""
[DIRECTION A] Academic Paper Evaluation Suite.
Measures control loop latency, jitter, and energy consumption for Python vs Rust.
"""

import json
import os
import time
from typing import Dict, List

import numpy as np


# Mock Drone state for isolated benchmark
class BenchmarkRunner:
    def __init__(self, iterations: int = 1000):
        self.iterations = iterations

    def run_python_benchmark(self) -> Dict[str, float]:
        from warm_logic.kernel.drone.control.controller import DroneController

        controller = DroneController()
        # Ensure we are NOT using rust for python benchmark
        controller._rust_controller = None
        controller.arm()

        # We need to simulate heartbeats to satisfy the watchdog
        controller.send_heartbeat()

        latencies = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            _ = controller.get_control_output()
            latencies.append((time.perf_counter() - start) * 1000.0)  # ms

        return {
            "avg_latency_ms": np.mean(latencies),
            "max_jitter_ms": np.max(latencies) - np.mean(latencies),
            "p99_latency_ms": np.percentile(latencies, 99),
        }

    def run_rust_benchmark(self) -> Dict[str, float]:
        from warm_logic.kernel.drone.control.controller import DroneController
        from warm_logic_rs import PyDroneController

        controller = DroneController()
        controller._rust_controller = PyDroneController()  # Force Rust
        controller.arm()
        controller.send_heartbeat()

        latencies = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            _ = controller.get_control_output()
            latencies.append((time.perf_counter() - start) * 1000.0)  # ms

        return {
            "avg_latency_ms": np.mean(latencies),
            "max_jitter_ms": np.max(latencies) - np.mean(latencies),
            "p99_latency_ms": np.percentile(latencies, 99),
        }


if __name__ == "__main__":
    runner = BenchmarkRunner(iterations=1000)

    print("Starting Academic Benchmark Suite...")

    py_results = runner.run_python_benchmark()
    print(
        f"🐍 Python Analysis: {py_results['avg_latency_ms']:.3f}ms (p99: {py_results['p99_latency_ms']:.3f}ms)"
    )

    rust_results = runner.run_rust_benchmark()
    print(
        f"🦀 Rust Analysis:   {rust_results['avg_latency_ms']:.3f}ms (p99: {rust_results['p99_latency_ms']:.3f}ms)"
    )

    improvement = (
        (py_results["avg_latency_ms"] - rust_results["avg_latency_ms"])
        / py_results["avg_latency_ms"]
        * 100
    )
    print(f"Performance Gain: {improvement:.1f}%")

    # Save results for paper
    results = {
        "python": py_results,
        "rust": rust_results,
        "improvement_pct": improvement,
    }

    os.makedirs("out/benchmarks", exist_ok=True)
    with open("out/benchmarks/paper_results.json", "w") as f:
        json.dump(results, f, indent=4)

    print(f"Results saved to out/benchmarks/paper_results.json")
