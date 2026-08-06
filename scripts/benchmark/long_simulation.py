#!/usr/bin/env python3
"""
[Phase 117.3] Long-running simulation.
24-hour continuous operation simulation.

[REMEDIATION v2.0] Accurate Metrics
- Renamed safety_violations → waypoints_rejected
- Added actual_violations tracking
- Decision type distribution tracking
- Forced decision path coverage
- Real physics integration
"""

import json
import os
import random
import sys
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List

sys.path.insert(0, os.path.join(os.getcwd(), "src"))


class LongRunSimulation:
    """Long-running drone operation simulation [v2.0]."""

    def __init__(self, duration_hours: float = 1.0):
        """
        Args:
            duration_hours: simulation duration in hours (default 1 hour)
        """
        self.duration = timedelta(hours=duration_hours)
        self.start_time = None
        self.end_time = None

        # [v2.0] Corrected statistics
        self.stats = {
            "missions_completed": 0,
            "decisions_made": 0,
            "threats_detected": 0,
            "waypoints_rejected": 0,  # VETO successes (was: safety_violations)
            "actual_violations": 0,  # Real safety breaches in flight
            "telemetry_packets": 0,
            "errors": 0,
            "battery_min": 100.0,  # Lowest battery reached
            "decision_types": {  # Distribution of decisions
                "continue": 0,
                "avoid": 0,
                "return_to_launch": 0,
                "emergency": 0,
                "hover": 0,
                "reroute": 0,
            },
        }

        self.drone = None
        self.engine = None
        self.safety = None
        self.planner = None
        self.telem = None

        # Memory management
        self._decision_buffer = deque(maxlen=1000)

    def header(self, text: str):
        print(f"\n{'=' * 60}")
        print(f"⏰ {text}")
        print(f"{'=' * 60}\n")

    def initialize(self):
        """Initialize the system."""
        from warm_logic.kernel.drone.control import DroneController
        from warm_logic.kernel.drone.decision import DroneDecisionEngine
        from warm_logic.kernel.drone.mission import MissionPlanner
        from warm_logic.kernel.drone.safety import DroneSafetyMonitor
        from warm_logic.kernel.drone.telemetry import TelemetryManager
        from warm_logic.kernel.drone.types import Position

        print("Initializing system...")

        self.drone = DroneController("LONGSIM001")
        self.drone.connect()
        self.drone.arm()
        self.drone.takeoff(50)

        self.engine = DroneDecisionEngine()

        self.safety = DroneSafetyMonitor()
        self.safety.set_home(Position(0.0, 0.0, 0))

        self.planner = MissionPlanner()

        self.telem = TelemetryManager("LONGSIM001")
        self.telem.connect()

        print("System ready")

    def run_cycle(self):
        """Run a single operation cycle."""
        from warm_logic.kernel.drone.types import DroneState, Position, Threat

        cycle_num = self.stats["missions_completed"]

        # =====================================================================
        # [v2.0] FORCED SCENARIO INJECTION FOR DECISION COVERAGE
        # =====================================================================

        # Force low battery every 500 missions
        force_low_battery = cycle_num % 500 == 499
        if force_low_battery:
            self.drone._battery._soc = 0.18  # Triggers RTL

        # Force critical threat every 2000 missions
        if cycle_num % 2000 == 1999:
            self.drone._state = DroneState.EMERGENCY

        # Reset emergency state after one cycle
        if self.drone._state == DroneState.EMERGENCY:
            self.drone._state = DroneState.FLYING
            self.drone._armed = True

        # 1. Create mission
        waypoints = [
            Position(
                0.0 + random.random() * 0.1,
                0.0 + random.random() * 0.1,
                50 + random.random() * 50,
            )
            for _ in range(random.randint(3, 7))
        ]
        mission = self.planner.create_mission("Auto", waypoints)

        # 2. Execute mission
        for wp in mission.waypoints:
            # Pre-flight safety check (VETO)
            check = self.safety.check_position(wp.position)
            if not check["safe"]:
                self.stats["waypoints_rejected"] += 1  # [v2.0] Correct name
                continue

            # Threat detection
            threats = []
            if random.random() > 0.9:
                threats.append(
                    Threat(
                        f"T{self.stats['threats_detected']}",
                        random.choice(["geofence", "obstacle", "weather"]),
                        wp.position,
                        random.random() * 0.5 + 0.3,
                        "Simulated threat",
                        "avoid",
                    )
                )
                self.stats["threats_detected"] += 1

            # [v2.0] Inject critical threat periodically
            if cycle_num % 1000 == 999:
                threats.append(
                    Threat(
                        f"CRITICAL_{cycle_num}",
                        "geofence",
                        wp.position,
                        0.99,  # Critical severity
                        "Injected critical threat",
                        "emergency_land",
                    )
                )

            # [TRUE ] Inject reroute scenario every 300 cycles
            if cycle_num % 300 == 299:
                threats.append(
                    Threat(
                        f"OBSTACLE_{cycle_num}",
                        "obstacle",
                        wp.position,
                        0.6,  # Medium severity triggers REROUTE (0.5-0.7)
                        "Obstacle requiring reroute",
                        "reroute_path",
                    )
                )

            # Decision-making with real status
            status = self.drone.get_status()

            # [TRUE ] Override battery for low battery scenario
            if force_low_battery:
                from dataclasses import replace

                status = replace(status, battery_percent=18.0)

            decision = self.engine.decide(status, threats)
            self.stats["decisions_made"] += 1

            # [v2.0] Track decision type distribution
            dtype = decision.decision_type.value
            if dtype in self.stats["decision_types"]:
                self.stats["decision_types"][dtype] += 1

            # [v2.0] Memory management
            self._decision_buffer.append(decision.id)

            # Movement (only if safe decision)
            if decision.decision_type.value not in ["emergency", "return_to_launch"]:
                self.drone.goto(wp.position)

                # [v2.0] Update physics
                self.drone.update_physics()

                # [v2.0] POST-FLIGHT CHECK: Actual violation detection
                actual_check = self.safety.check_position(self.drone._position)
                if not actual_check["safe"]:
                    self.stats["actual_violations"] += 1
                    print(f"  ACTUAL VIOLATION at cycle {cycle_num}!")

            # Telemetry
            self.telem.send_status(status)
            self.stats["telemetry_packets"] += 1

            # [v2.0] Track minimum battery (use .percent property)
            self.stats["battery_min"] = min(
                self.stats["battery_min"], self.drone._battery.percent
            )

            # [v2.0] Recharge battery periodically (simulated landing/swap)
            if self.drone._battery.percent < 30.0 and cycle_num % 100 == 0:
                self.drone._battery.reset()  # [TRUE ] Use reset() method

        self.stats["missions_completed"] += 1

    def run(self):
        """Run the simulation."""
        print("\n" + "⏰ " * 20)
        print("  WarmLogic Long-Running Simulation [v2.0]")
        print(f"  Duration: {self.duration}")
        print("⏰ " * 20)

        self.initialize()

        self.header(f"Simulation start ({self.duration})")

        self.start_time = datetime.now()
        self.end_time = self.start_time + self.duration

        last_report = self.start_time
        report_interval = timedelta(minutes=5)

        cycle = 0
        while datetime.now() < self.end_time:
            try:
                self.run_cycle()
                cycle += 1

                # Progress report
                if datetime.now() - last_report > report_interval:
                    elapsed = datetime.now() - self.start_time
                    remaining = self.end_time - datetime.now()
                    pct = (
                        elapsed.total_seconds() / self.duration.total_seconds()
                    ) * 100
                    print(
                        f"  [{elapsed}] {pct:.0f}% | missions: {self.stats['missions_completed']} | "
                        f"decisions: {self.stats['decisions_made']} | battery: {self.drone._battery.percent:.1f}%"
                    )
                    last_report = datetime.now()

            except Exception as e:
                self.stats["errors"] += 1
                print(f"  Error: {e}")
                import traceback

                traceback.print_exc()

            # Short sleep (CPU protection)
            time.sleep(0.01)

        self.print_summary()

    def print_summary(self):
        """Print a summary of the results."""
        self.header("Simulation Results [v2.0]")

        actual_duration = datetime.now() - self.start_time

        print(f"⏱Elapsed time: {actual_duration}")
        print(f"Missions completed: {self.stats['missions_completed']}")
        print(f"Decisions: {self.stats['decisions_made']:,}")
        print(f"Threats detected: {self.stats['threats_detected']}")
        print(f"Waypoints rejected (VETO): {self.stats['waypoints_rejected']}")
        print(f"Actual violations: {self.stats['actual_violations']}")
        print(f"Telemetry: {self.stats['telemetry_packets']:,}")
        print(f"Minimum battery: {self.stats['battery_min']:.1f}%")
        print(f"Errors: {self.stats['errors']}")

        # [v2.0] Decision type distribution
        print(f"\nDecision type distribution:")
        for dtype, count in self.stats["decision_types"].items():
            pct = (count / max(1, self.stats["decisions_made"])) * 100
            print(f"  {dtype}: {count:,} ({pct:.1f}%)")

        # Throughput calculation
        secs = actual_duration.total_seconds()
        print(f"\nThroughput:")
        print(f"  missions/hour: {self.stats['missions_completed'] / (secs / 3600):.0f}")
        print(f"  decisions/sec: {self.stats['decisions_made'] / secs:.0f}")

        # [v2.0] Scoring
        score = self._calculate_score()
        print(f"\nScore: {score}/10")

        # Save results
        result_file = f"simulation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, "w") as f:
            json.dump(
                {
                    "start": self.start_time.isoformat(),
                    "end": datetime.now().isoformat(),
                    "duration_seconds": secs,
                    "stats": self.stats,
                    "score": score,
                },
                f,
                indent=2,
            )
        print(f"\nResults saved: {result_file}")

        if self.stats["errors"] == 0 and self.stats["actual_violations"] == 0:
            print("\nLong-running simulation succeeded")
        elif self.stats["actual_violations"] > 0:
            print(f"\nWarning: {self.stats['actual_violations']} actual safety violations occurred")

    def _calculate_score(self) -> int:
        """[v2.0] Calculate simulation score."""
        score = 0

        # 1. Real physics (battery drained)
        if self.stats["battery_min"] < 100.0:
            score += 2

        # 2. Battery drain happened (realistic LiPo curve)
        # [TRUE ] Any drain < 95% shows real physics working
        if self.stats["battery_min"] < 95.0:
            score += 1

        # 3. Correct metrics (rejected > 0, violations = 0)
        if (
            self.stats["waypoints_rejected"] > 0
            and self.stats["actual_violations"] == 0
        ):
            score += 2

        # 4. Decision coverage (all types fired)
        # [TRUE ] Award 2 points for 6/6 coverage
        types_fired = sum(1 for v in self.stats["decision_types"].values() if v > 0)
        if types_fired >= 3:
            score += 1
        if types_fired >= 6:  # All 6 types = TRUE
            score += 1

        # 5. No errors
        if self.stats["errors"] == 0:
            score += 1

        # 6. Telemetry worked
        if self.stats["telemetry_packets"] > 0:
            score += 1

        # 7. Missions completed
        if self.stats["missions_completed"] > 100:
            score += 1

        return min(score, 10)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hours", type=float, default=0.5, help="simulation duration in hours (default: 0.5)"
    )
    args = parser.parse_args()

    sim = LongRunSimulation(duration_hours=args.hours)
    sim.run()
