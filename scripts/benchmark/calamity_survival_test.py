"""
[Phase 4.2] Calamity Survival Test v1.0
Resilience Benchmark for Academic Paper "Sovereign Drone Autonomy"

Injects randomized failure scenarios and measures VETO survival rates.
"""

import os
import random
import sys
import time
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.path.join(os.getcwd(), "scripts/benchmark"))

# Use existing HarshSimulation as base
from harsh_simulation import HarshSimulation

from warm_logic.kernel.drone.types import Position


class CalamitySurvivalTest(HarshSimulation):
    def __init__(self, num_scenarios: int = 10, scenario_duration_s: float = 30.0):
        super().__init__(duration_hours=1.0)  # Not used directly in loop
        self.num_scenarios = num_scenarios
        self.scenario_duration_s = scenario_duration_s
        self.results = []

    def run_scenario(self, calamity_name: str, injection_fn):
        print(f"\n[TEST] Scenario: {calamity_name}")
        self.initialize()

        # Reset stats
        self.stats["actual_violations"] = 0
        self.stats["errors"] = 0

        start_time = time.time()
        injected = False

        survived = True
        while time.time() - start_time < self.scenario_duration_s:
            # Inject fault mid-way
            if not injected and (time.time() - start_time) > (
                self.scenario_duration_s / 3.0
            ):
                injection_fn()
                injected = True
                print(f"   FAULT INJECTED!")

            self.run_cycle()

            # Failure conditions
            if self.stats["actual_violations"] > 0:
                print(f"   FAILED: Protection Violation detected.")
                survived = False
                break

            if self.sim_state.altitude_m < 0.5 and injected:
                print(f"   FAILED: Drone Crashed.")
                survived = False
                break

            if self.stats["errors"] > 0:
                print(f"   FAILED: System Error.")
                survived = False
                break

            time.sleep(0.001)

        result = {
            "name": calamity_name,
            "survived": survived,
            "violations": self.stats["actual_violations"],
            "final_alt": self.sim_state.altitude_m,
        }
        self.results.append(result)
        return survived

    def execute_suite(self):
        print(f"\n{'=' * 60}")
        print(f"STARTING CALAMITY SURVIVAL SUITE ({self.num_scenarios} Scenarios)")
        print(f"{'=' * 60}")

        scenarios = [
            (
                "Single Motor Failure (50%)",
                lambda: self.disaster.inject_motor_failure(0, 0.5, 10.0),
            ),
            ("GPS Freeze", lambda: self.disaster.inject_gps_freeze(5.0)),
            ("Battery Sag (-3V)", lambda: self.disaster.inject_battery_sag(3.0, 5.0)),
            (
                "Microburst (Vertical)",
                lambda: self.disaster.inject_microburst(25.0, 2.0),
            ),
            ("IMU Gyro Drift", lambda: self.disaster.inject_imu_drift(0.05, 10.0)),
            (
                "GPS Multipath (5m Noise)",
                lambda: self.disaster.inject_gps_multipath(5.0, 8.0),
            ),
            (
                "Dual Motor Degradation",
                lambda: (
                    self.disaster.inject_motor_failure(1, 0.7, 10.0),
                    self.disaster.inject_motor_failure(2, 0.7, 10.0),
                ),
            ),
        ]

        for i in range(self.num_scenarios):
            name, fn = random.choice(scenarios)
            self.run_scenario(f"#{i + 1}: {name}", fn)

        self.summary()

    def summary(self):
        total = len(self.results)
        survived = sum(1 for r in self.results if r["survived"])
        rate = (survived / total) * 100 if total > 0 else 0

        print(f"\n{'=' * 60}")
        print(f"BENCHMARK SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total Scenarios: {total}")
        print(f"Survivals:       {survived}")
        print(f"Survival Rate:   {rate:.1f}%")
        print(f"{'=' * 60}")

        # Save to file for paper
        os.makedirs("out/logs", exist_ok=True)
        with open("out/logs/calamity_results.txt", "w") as f:
            f.write(f"Calamity Survival Rate: {rate:.1f}%\n")
            for r in self.results:
                f.write(
                    f"{r['name']}: {'PASS' if r['survived'] else 'FAIL'} (Alt: {r['final_alt']:.1f}m)\n"
                )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=int, default=5)
    args = parser.parse_args()

    test = CalamitySurvivalTest(num_scenarios=args.scenarios)
    test.execute_suite()
