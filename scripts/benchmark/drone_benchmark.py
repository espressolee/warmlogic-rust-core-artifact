#!/usr/bin/env python3
"""
[Phase 117.1] WarmLogic Performance Benchmark Suite.
Measures drone AI module performance.
"""

import json
import os
import statistics
import sys
import time
from datetime import datetime
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.getcwd(), "src"))


class BenchmarkResult:
    def __init__(self, name: str):
        self.name = name
        self.times: List[float] = []
        self.memory: List[int] = []

    def add(self, time_ms: float, memory_bytes: int = 0):
        self.times.append(time_ms)
        self.memory.append(memory_bytes)

    def stats(self) -> Dict:
        if not self.times:
            return {}
        return {
            "name": self.name,
            "count": len(self.times),
            "min_ms": min(self.times),
            "max_ms": max(self.times),
            "avg_ms": statistics.mean(self.times),
            "p50_ms": statistics.median(self.times),
            "p95_ms": sorted(self.times)[int(len(self.times) * 0.95)]
            if len(self.times) >= 20
            else max(self.times),
            "p99_ms": sorted(self.times)[int(len(self.times) * 0.99)]
            if len(self.times) >= 100
            else max(self.times),
            "std_ms": statistics.stdev(self.times) if len(self.times) > 1 else 0,
        }


class BenchmarkSuite:
    """WarmLogic drone AI benchmark suite."""

    def __init__(self):
        self.results: Dict[str, BenchmarkResult] = {}
        self.start_time = datetime.now()

    def header(self, text: str):
        print(f"\n{'=' * 60}")
        print(f"{text}")
        print(f"{'=' * 60}\n")

    def run_benchmark(self, name: str, fn, iterations: int = 1000) -> BenchmarkResult:
        """Run benchmark with specified iterations."""
        result = BenchmarkResult(name)
        print(f"  Running {name}... ", end="", flush=True)

        # Warmup
        for _ in range(min(10, iterations // 10)):
            fn()

        # Actual benchmark
        for _ in range(iterations):
            start = time.perf_counter()
            fn()
            elapsed = (time.perf_counter() - start) * 1000
            result.add(elapsed)

        self.results[name] = result
        stats = result.stats()
        print(f"avg={stats['avg_ms']:.3f}ms, p95={stats['p95_ms']:.3f}ms")
        return result

    def bench_control(self):
        """Drone control benchmark."""
        self.header("1. Drone Control")

        from warm_logic.kernel.drone.control import DroneController
        from warm_logic.kernel.drone.types import Position

        ctrl = DroneController("BENCH001")
        ctrl.connect()
        ctrl.arm()
        ctrl.takeoff(50)

        self.run_benchmark("control.arm", lambda: ctrl.arm())
        self.run_benchmark(
            "control.goto", lambda: ctrl.goto(Position(0.07, 0.08, 50))
        )
        self.run_benchmark("control.get_status", lambda: ctrl.get_status())

    def bench_decision(self):
        """Decision engine benchmark."""
        self.header("2. Decision Engine")

        from warm_logic.kernel.drone.control import DroneController
        from warm_logic.kernel.drone.decision import DroneDecisionEngine
        from warm_logic.kernel.drone.types import Position, Threat

        engine = DroneDecisionEngine()
        ctrl = DroneController("BENCH002")
        ctrl.connect()
        ctrl.arm()
        ctrl.takeoff(30)
        status = ctrl.get_status()

        # No threat
        self.run_benchmark("decision.no_threat", lambda: engine.decide(status))

        # With threats
        threats = [
            Threat("T1", "geofence", Position(0.08, 0.07, 50), 0.8, "Test", "avoid")
        ]
        self.run_benchmark(
            "decision.with_threat", lambda: engine.decide(status, threats)
        )

    def bench_safety(self):
        """Safety system benchmark."""
        self.header("3. Safety System")

        from warm_logic.kernel.drone.safety import DroneSafetyMonitor
        from warm_logic.kernel.drone.types import Position

        safety = DroneSafetyMonitor()
        safety.set_home(Position(0.0, 0.0, 0))

        safe_pos = Position(0.0, 0.0, 50)
        danger_pos = Position(0.0886, 0.0773, 50)  # Blue House

        self.run_benchmark("safety.check_safe", lambda: safety.check_position(safe_pos))
        self.run_benchmark(
            "safety.check_danger", lambda: safety.check_position(danger_pos)
        )
        self.run_benchmark("safety.get_threats", lambda: safety.get_threats(safe_pos))

    def bench_mission(self):
        """Mission planning benchmark."""
        self.header("4. Mission Planning")

        from warm_logic.kernel.drone.mission import MissionPlanner
        from warm_logic.kernel.drone.types import Position

        planner = MissionPlanner()
        waypoints = [
            Position(0.0, 0.0, 50),
            Position(0.0700, 0.0800, 50),
            Position(0.0750, 0.0850, 50),
        ]

        self.run_benchmark(
            "mission.create", lambda: planner.create_mission("Test", waypoints), 500
        )
        self.run_benchmark(
            "mission.plan_route",
            lambda: planner.plan_route(waypoints[0], waypoints[-1]),
            500,
        )

    def bench_telemetry(self):
        """Telemetry benchmark."""
        self.header("5. Telemetry")

        from warm_logic.kernel.drone.control import DroneController
        from warm_logic.kernel.drone.telemetry import TelemetryManager

        telem = TelemetryManager("BENCH003")
        telem.connect()
        ctrl = DroneController("BENCH003")
        ctrl.connect()
        status = ctrl.get_status()

        self.run_benchmark("telemetry.send_status", lambda: telem.send_status(status))
        self.run_benchmark(
            "telemetry.check_connection", lambda: telem.check_connection()
        )

    def bench_sitl(self):
        """SITL simulator benchmark."""
        self.header("6. SITL Simulator")

        from warm_logic.kernel.drone.simulator import ArduPilotSITL

        sitl = ArduPilotSITL()
        sitl.connect()
        sitl.arm()

        self.run_benchmark("sitl.arm", lambda: sitl.arm())
        self.run_benchmark("sitl.goto", lambda: sitl.goto(0.07, 0.08, 50))
        self.run_benchmark("sitl.get_telemetry", lambda: sitl.get_telemetry())

    def run_all(self):
        """Run all benchmarks."""
        print("\n" + "" * 20)
        print("  WarmLogic Drone AI Performance Benchmark Suite")
        print("" * 20)

        self.bench_control()
        self.bench_decision()
        self.bench_safety()
        self.bench_mission()
        self.bench_telemetry()
        self.bench_sitl()

        self.print_summary()

    def print_summary(self):
        """Print a summary of the results."""
        self.header("Benchmark Result Summary")

        elapsed = (datetime.now() - self.start_time).total_seconds()

        print(f"{'Benchmark':<30} {'Avg(ms)':<12} {'P95(ms)':<12} {'P99(ms)':<12}")
        print("-" * 66)

        for name, result in self.results.items():
            stats = result.stats()
            print(
                f"{name:<30} {stats['avg_ms']:<12.3f} {stats['p95_ms']:<12.3f} {stats['p99_ms']:<12.3f}"
            )

        print(f"\n⏱Total elapsed time: {elapsed:.1f}s")

        # Check targets
        print("\nPerformance target check:")
        targets = {
            "control": 5.0,
            "decision": 10.0,
            "safety": 1.0,
            "mission": 100.0,
            "telemetry": 1.0,
            "sitl": 5.0,
        }

        all_passed = True
        for category, target in targets.items():
            cat_results = [r for n, r in self.results.items() if n.startswith(category)]
            if cat_results:
                max_p95 = max(r.stats()["p95_ms"] for r in cat_results)
                passed = max_p95 < target
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"  {category}: P95 {max_p95:.3f}ms < {target}ms {status}")
                if not passed:
                    all_passed = False

        # Save results
        result_file = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "elapsed_seconds": elapsed,
                    "results": {n: r.stats() for n, r in self.results.items()},
                    "all_passed": all_passed,
                },
                f,
                indent=2,
            )
        print(f"\nResults saved: {result_file}")

        if all_passed:
            print("\nAll performance targets met")
        else:
            print("\nSome performance targets not met")


if __name__ == "__main__":
    suite = BenchmarkSuite()
    suite.run_all()
