#!/usr/bin/env python3
# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Unified benchmark runner for WarmLogic.

Usage:
    python scripts/benchmark_runner.py --all
    python scripts/benchmark_runner.py --suite crypto
    python scripts/benchmark_runner.py --suite consensus --iterations 1000
    python scripts/benchmark_runner.py --memory
    python scripts/benchmark_runner.py --hotspot
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_crypto_benchmarks(iterations: int = 1000):
    """Run cryptographic benchmarks."""
    print("\nRunning Crypto Benchmarks...\n")

    try:
        from benchmarks.crypto.bench_zk_prove import bench_zk

        bench_zk(iterations)
    except ImportError as e:
        print(f"    Skipping ZK benchmarks: {e}")
    except Exception as e:
        print(f"   ZK benchmark failed: {e}")


def run_consensus_benchmarks(iterations: int = 200):
    """Run consensus benchmarks."""
    print("\nRunning Consensus Benchmarks...\n")

    try:
        from benchmarks.consensus.bench_5node_bft import bench_bft

        bench_bft(iterations)
    except ImportError as e:
        print(f"    Skipping BFT benchmarks: {e}")
    except Exception as e:
        print(f"   BFT benchmark failed: {e}")


def run_storage_benchmarks(iterations: int = 10000):
    """Run storage benchmarks."""
    print("\nRunning Storage Benchmarks...\n")

    try:
        from benchmarks.storage.bench_sled_throughput import bench_sled

        bench_sled(iterations)
    except ImportError as e:
        print(f"    Skipping Sled benchmarks: {e}")
    except Exception as e:
        print(f"   Storage benchmark failed: {e}")


def run_integration_benchmarks():
    """Run integration benchmarks."""
    print("\nRunning Integration Benchmarks...\n")

    try:
        from benchmarks.integration.bench_kernel_pipeline import run_benchmark_suite

        results = run_benchmark_suite()
        return results
    except ImportError as e:
        print(f"    Skipping integration benchmarks: {e}")
    except Exception as e:
        print(f"   Integration benchmark failed: {e}")

    return []


def run_memory_profiling():
    """Run memory profiling benchmarks."""
    print("\nRunning Memory Profiling...\n")

    try:
        from benchmarks.profiling.bench_memory import run_memory_benchmarks

        reports = run_memory_benchmarks()
        return reports
    except ImportError as e:
        print(f"    Skipping memory benchmarks: {e}")
    except Exception as e:
        print(f"   Memory benchmark failed: {e}")

    return []


def run_hotspot_analysis():
    """Run hotspot analysis using cProfile."""
    print("\nRunning Hotspot Analysis...\n")

    try:
        from benchmarks.profiling import run_with_profiler

        # Profile the integration benchmark
        with run_with_profiler(output_lines=20) as prof:
            from benchmarks.integration.bench_kernel_pipeline import (
                bench_governance_snapshot,
            )

            for _ in range(100):
                bench_governance_snapshot()

    except ImportError as e:
        print(f"    Skipping hotspot analysis: {e}")
    except Exception as e:
        print(f"   Hotspot analysis failed: {e}")


def save_results(results: dict, output_dir: Path):
    """Save benchmark results to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"benchmark_results_{timestamp}.json"

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="WarmLogic Benchmark Runner")
    parser.add_argument("--all", action="store_true", help="Run all benchmarks")
    parser.add_argument(
        "--suite",
        choices=["crypto", "consensus", "storage", "integration"],
        help="Run specific benchmark suite",
    )
    parser.add_argument("--memory", action="store_true", help="Run memory profiling")
    parser.add_argument("--hotspot", action="store_true", help="Run hotspot analysis")
    parser.add_argument(
        "--iterations", type=int, default=100, help="Number of iterations"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "benchmarks" / "results",
        help="Output directory for results",
    )
    parser.add_argument("--save", action="store_true", help="Save results to JSON")

    args = parser.parse_args()

    print("=" * 60)
    print("WarmLogic Benchmark Runner")
    print("=" * 60)

    results = {"timestamp": datetime.now().isoformat(), "benchmarks": {}}

    if args.all:
        run_crypto_benchmarks(args.iterations * 10)
        run_consensus_benchmarks(args.iterations * 2)
        run_storage_benchmarks(args.iterations * 100)
        integration_results = run_integration_benchmarks()
        if integration_results:
            results["benchmarks"]["integration"] = [
                r.to_dict() for r in integration_results
            ]
        run_memory_profiling()
        run_hotspot_analysis()

    elif args.suite:
        if args.suite == "crypto":
            run_crypto_benchmarks(args.iterations)
        elif args.suite == "consensus":
            run_consensus_benchmarks(args.iterations)
        elif args.suite == "storage":
            run_storage_benchmarks(args.iterations)
        elif args.suite == "integration":
            integration_results = run_integration_benchmarks()
            if integration_results:
                results["benchmarks"]["integration"] = [
                    r.to_dict() for r in integration_results
                ]

    elif args.memory:
        memory_results = run_memory_profiling()
        if memory_results:
            results["benchmarks"]["memory"] = [
                {"name": r.name, "peak_mb": r.peak_mb, "current_mb": r.current_mb}
                for r in memory_results
            ]

    elif args.hotspot:
        run_hotspot_analysis()

    else:
        # Default: run integration benchmarks
        integration_results = run_integration_benchmarks()
        if integration_results:
            results["benchmarks"]["integration"] = [
                r.to_dict() for r in integration_results
            ]

    if args.save and results["benchmarks"]:
        save_results(results, args.output_dir)

    print("\n" + "=" * 60)
    print("Benchmark run complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
