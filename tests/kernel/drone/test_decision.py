"""
Tests for Drone Decision Engine (Rules, Memory, Reroute).
"""

import unittest
from datetime import datetime

from warm_logic.kernel.drone.decision import DecisionType, DroneDecisionEngine
from warm_logic.kernel.drone.types import (
    Attitude,
    DroneState,
    DroneStatus,
    FlightMode,
    Position,
    Threat,
    Velocity,
)


class TestDecisionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = DroneDecisionEngine()
        self.status = DroneStatus(
            timestamp=datetime.now(),
            state=DroneState.FLYING,
            mode=FlightMode.GUIDED,
            position=Position(37.5, 127.0, 50.0),
            velocity=Velocity(0, 0, 0),
            attitude=Attitude(0, 0, 0),
            battery_percent=80.0,
            gps_satellites=12,
            is_armed=True,
            is_connected=True,
            errors=[],
        )

    def test_normal_flight(self):
        """Verify normal flight continues."""
        decision = self.engine.decide(self.status, [])
        self.assertEqual(decision.decision_type, DecisionType.CONTINUE)
        self.assertEqual(len(self.engine._decision_history), 1)

    def test_emergency_trigger(self):
        """Verify emergency override."""
        self.status.state = DroneState.EMERGENCY
        decision = self.engine.decide(self.status, [])
        self.assertEqual(decision.decision_type, DecisionType.EMERGENCY)
        self.assertEqual(decision.confidence, 1.0)

    def test_low_battery_rtl(self):
        """Verify low battery triggers RTL."""
        self.status.battery_percent = 15.0  # < 20%
        decision = self.engine.decide(self.status, [])
        self.assertEqual(decision.decision_type, DecisionType.RTL)
        # Check all reasoning lines
        found = any("Low battery" in line for line in decision.reasoning)
        self.assertTrue(found, f"Reasoning: {decision.reasoning}")

    def test_reroute_trigger(self):
        """Verify obstacle detected triggers REROUTE."""
        threat = Threat(
            id="OBS_01",
            threat_type="obstacle",
            position=Position(37.5001, 127.0001, 50.0),
            severity=0.6,  # 0.5 <= s < 0.7 triggers REROUTE
            description="Building",
            recommended_action="reroute_path",
        )
        decision = self.engine.decide(self.status, [threat])
        self.assertEqual(decision.decision_type, DecisionType.REROUTE)
        self.assertTrue(decision.action["reroute"])

    def test_avoid_trigger(self):
        """Verify high severity threat triggers AVOID."""
        threat = Threat(
            id="COLLISION_01",
            threat_type="aircraft",  # Matches _check_collision_risk filter
            position=Position(37.5, 127.0, 50.0),
            severity=0.8,  # >= 0.7 triggers AVOID
            description="Other Drone",
            recommended_action="climb",
        )
        # Ensure priority: Collision (70) > Mission (50)
        decision = self.engine.decide(self.status, [threat])
        self.assertEqual(decision.decision_type, DecisionType.AVOID)

    def test_memory_bounds(self):
        """Verify decision history is bounded."""
        # Fill history > MAX_HISTORY_SIZE (10000)
        # To test quickly, we can manually check deque maxlen
        self.assertEqual(self.engine._decision_history.maxlen, 10000)

        # Add 5 dummy decisions
        for _ in range(5):
            self.engine.decide(self.status, [])

        self.assertEqual(len(self.engine._decision_history), 5)
        # Confirm it's a deque
        from collections import deque

        self.assertIsInstance(self.engine._decision_history, deque)
