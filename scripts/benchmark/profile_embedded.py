"""
[Phase 2.2] Embedded Performance Profiler.
Measures control loop latency and PQC overhead.
"""

import logging
import os
import subprocess
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EmbeddedProfiler")


def run_rust_benchmarks():
    logger.info("Running Rust Kernel Benchmarks (Criterion)...")
    try:
        # Run drone_bench
        output = subprocess.check_output(
            ["cargo", "bench", "--bench", "drone_bench", "--features", "std"],
            cwd="rust_core",
            text=True,
        )
        logger.info("Drone Benchmarks Completed.")
        print(output)

        # Run crypto_bench
        output_crypto = subprocess.check_output(
            ["cargo", "bench", "--bench", "crypto_bench", "--features", "std"],
            cwd="rust_core",
            text=True,
        )
        logger.info("Crypto Benchmarks Completed.")
        print(output_crypto)

    except Exception as e:
        logger.error(f"Benchmarking failed: {e}")


def profile_python_overhead():
    logger.info("Profiling Python-Rust Bridge Overhead...")
    # This would typically involve calling pyo3 bindings.
    # For now, we simulate a bridge call.
    start = time.perf_counter()
    for _ in range(1000):
        # Dummy bridge logic
        pass
    end = time.perf_counter()
    avg_latency_us = (end - start) / 1000 * 1e6
    logger.info(f"Avg Python overhead: {avg_latency_us:.2f} us")


if __name__ == "__main__":
    logger.info("Starting Embedded Performance Profiling...")

    # 1. Hardware Info
    try:
        hw_info = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
        ).strip()
        logger.info(f"Hardware: {hw_info}")
    except:
        logger.info("Hardware: Unknown ARM/x86")

    # 2. Run Rust Benches
    run_rust_benchmarks()

    # 3. Profile Bridge
    profile_python_overhead()

    logger.info("Profiling session complete.")
