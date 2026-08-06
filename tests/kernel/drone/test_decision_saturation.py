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


class TestDecisionSaturation(unittest.TestCase):
    def setUp(self):
        self.engine = DroneDecisionEngine()
        self.status = DroneStatus(
            timestamp=datetime.now(),
            state=DroneState.FLYING,
            mode=FlightMode.GUIDED,
            position=Position(37.0, 127.0, 10.0),
            velocity=Velocity(0, 0, 0),
            attitude=Attitude(0, 0, 0),
            battery_percent=80.0,
            gps_satellites=12,
            is_armed=True,
            is_connected=True,
            errors=[],
        )

    def test_geofence_rule(self):
        """L188: Verify geofence violation rule trigger."""
        # Severity must be < 0.95 to avoid EMERGENCY rule (P100)
        threat = Threat(
            "T1", "geofence", Position(0, 0, 0), 0.8, "Outside", "return_to_boundary"
        )
        decision = self.engine.decide(self.status, [threat])

        # Geofence violation -> AVOID (L76 in decision.py)
        self.assertEqual(decision.decision_type, DecisionType.AVOID)
        self.assertTrue(any("Geofence" in r for r in decision.reasoning))

    def test_weather_rule(self):
        """L216-217: Verify weather rule trigger."""
        threat = Threat(
            "T2", "weather", Position(0, 0, 0), 0.65, "Windy", "hover_and_wait"
        )
        decision = self.engine.decide(self.status, [threat])

        # Weather logic -> HOVER (L79 in decision.py)
        self.assertEqual(decision.decision_type, DecisionType.HOVER)
        self.assertTrue(any("Weather" in r for r in decision.reasoning))

    def test_reroute_trigger(self):
        """L231: Verify reroute for medium severity obstacle."""
        threat = Threat(
            "T3", "obstacle", Position(37.001, 127.001, 10), 0.6, "Tree", "reroute"
        )
        decision = self.engine.decide(self.status, [threat])

        # Reroute logic -> REROUTE (L77 in decision.py)
        self.assertEqual(decision.decision_type, DecisionType.REROUTE)
        self.assertTrue(any("Obstacle" in r for r in decision.reasoning))

    def test_assess_threat_priority(self):
        """L260-281: Verify assess_threat priority classification."""
        # Critical
        t1 = Threat("1", "x", None, 0.95, "desc", "act")
        a1 = self.engine.assess_threat(t1)
        self.assertEqual(a1["priority"], "CRITICAL")
        self.assertEqual(a1["urgency"], "immediate")

        # High
        t2 = Threat("2", "x", None, 0.75, "desc", "act")
        a2 = self.engine.assess_threat(t2)
        self.assertEqual(a2["priority"], "HIGH")

        # Medium
        t3 = Threat("3", "x", None, 0.55, "desc", "act")
        a3 = self.engine.assess_threat(t3)
        self.assertEqual(a3["priority"], "MEDIUM")

        # Low
        t4 = Threat("4", "x", None, 0.4, "desc", "act")
        a4 = self.engine.assess_threat(t4)
        self.assertEqual(a4["priority"], "LOW")
