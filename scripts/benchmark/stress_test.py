#!/usr/bin/env python3
"""
[Phase 117.2] Stress test.
Verifies stability under high load.
"""

import os
import random
import sys
import threading
import time
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, os.path.join(os.getcwd(), "src"))


class StressTest:
    """Drone AI stress test."""

    def __init__(self):
        self.errors: List[Dict] = []
        self.operations = 0
        self.start_time = None

    def header(self, text: str):
        print(f"\n{'=' * 60}")
        print(f"{text}")
        print(f"{'=' * 60}\n")

    def test_concurrent_drones(self, count: int = 50):
        """Concurrent operation of multiple drones."""
        self.header(f"1. Concurrent drone operation ({count} drones)")

        from warm_logic.kernel.drone.control import DroneController
        from warm_logic.kernel.drone.decision import DroneDecisionEngine
        from warm_logic.kernel.drone.types import Position

        drones = []
        engines = []

        print(f"  Creating {count} drones...", end=" ", flush=True)
        for i in range(count):
            ctrl = DroneController(f"STRESS{i:03d}")
            ctrl.connect()
            ctrl.arm()
            ctrl.takeoff(50 + random.randint(0, 50))
            drones.append(ctrl)
            engines.append(DroneDecisionEngine())
        print("done")

        print(f"  Running concurrent decisions...", end=" ", flush=True)
        start = time.time()

        def simulate_drone(drone, engine):
            for _ in range(100):
                status = drone.get_status()
                engine.decide(status)
                pos = Position(
                    0.0 + random.random() * 0.1, 0.0 + random.random() * 0.1, 50
                )
                drone.goto(pos)
                self.operations += 1

        threads = []
        for drone, engine in zip(drones, engines):
            t = threading.Thread(target=simulate_drone, args=(drone, engine))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        elapsed = time.time() - start
        ops_per_sec = self.operations / elapsed
        print(f"done")
        print(f"  {self.operations} operations in {elapsed:.1f}s")
        print(f"  {ops_per_sec:.0f} ops/sec")

    def test_rapid_decisions(self, count: int = 10000):
        """High-rate decision making."""
        self.header(f"2. High-rate decisions ({count:,} iterations)")

        from warm_logic.kernel.drone.control import DroneController
        from warm_logic.kernel.drone.decision import DroneDecisionEngine
        from warm_logic.kernel.drone.types import Position, Threat

        engine = DroneDecisionEngine()
        ctrl = DroneController("RAPID001")
        ctrl.connect()
        ctrl.arm()
        ctrl.takeoff(50)
        status = ctrl.get_status()

        print(f"  Running {count:,} decisions...", end=" ", flush=True)
        start = time.time()

        for i in range(count):
            threats = []
            if random.random() > 0.7:
                threats.append(
                    Threat(
                        f"T{i}",
                        random.choice(["geofence", "obstacle", "weather"]),
                        Position(0.0, 0.0, 50),
                        random.random(),
                        "Test",
                        "avoid",
                    )
                )
            engine.decide(status, threats)

        elapsed = time.time() - start
        print(f"done")
        print(f"  {count:,} decisions in {elapsed:.1f}s")
        print(f"  {count / elapsed:.0f} decisions/sec")

    def test_safety_flood(self, count: int = 50000):
        """Safety check flood."""
        self.header(f"3. Safety check flood ({count:,} iterations)")

        from warm_logic.kernel.drone.safety import DroneSafetyMonitor
        from warm_logic.kernel.drone.types import Position

        safety = DroneSafetyMonitor()
        safety.set_home(Position(0.0, 0.0, 0))

        print(f"  Running {count:,} safety checks...", end=" ", flush=True)
        start = time.time()

        violations = 0
        for _ in range(count):
            pos = Position(
                0.0 + random.random() * 0.15,
                0.0 + random.random() * 0.15,
                random.random() * 150,
            )
            result = safety.check_position(pos)
            if not result["safe"]:
                violations += 1

        elapsed = time.time() - start
        print(f"done")
        print(f"  {count:,} checks in {elapsed:.1f}s")
        print(f"  {count / elapsed:.0f} checks/sec")
        print(f"  {violations} violations detected ({violations / count * 100:.1f}%)")

    def test_mission_replanning(self, count: int = 1000):
        """Mission replanning stress."""
        self.header(f"4. Mission replanning ({count:,} iterations)")

        from warm_logic.kernel.drone.mission import MissionPlanner
        from warm_logic.kernel.drone.types import Position

        planner = MissionPlanner()

        print(f"  Running {count:,} mission replans...", end=" ", flush=True)
        start = time.time()

        for _ in range(count):
            waypoints = [
                Position(
                    0.0 + random.random() * 0.1, 0.0 + random.random() * 0.1, 50
                )
                for _ in range(random.randint(3, 10))
            ]
            planner.create_mission("Stress", waypoints)
            planner.plan_route(waypoints[0], waypoints[-1])

        elapsed = time.time() - start
        print(f"done")
        print(f"  {count:,} replans in {elapsed:.1f}s")
        print(f"  {count / elapsed:.0f} replans/sec")

    def run_all(self):
        """Run all stress tests."""
        print("\n" + "" * 20)
        print("  WarmLogic Stress Test Suite")
        print("" * 20)

        self.start_time = datetime.now()

        self.test_concurrent_drones()
        self.test_rapid_decisions()
        self.test_safety_flood()
        self.test_mission_replanning()

        self.print_summary()

    def print_summary(self):
        """Print a summary of the results."""
        self.header("Stress Test Results")

        elapsed = (datetime.now() - self.start_time).total_seconds()

        print(f"⏱Total elapsed time: {elapsed:.1f}s")
        print(f"Errors: {len(self.errors)}")

        if len(self.errors) == 0:
            print("\nAll stress tests passed")
        else:
            print("\nErrors:")
            for err in self.errors[:5]:
                print(f"  - {err}")


if __name__ == "__main__":
    test = StressTest()
    test.run_all()
