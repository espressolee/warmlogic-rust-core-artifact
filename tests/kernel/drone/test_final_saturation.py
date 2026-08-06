"""
[Phase 12] Final Saturation Tests.
Targets: remaining 1.4% gaps across the entire kernel.drone package.
"""

import datetime
import json
import math
import sys
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.drone.control.controller import DroneController
from warm_logic.kernel.drone.decision import Decision, DecisionType, DroneDecisionEngine
from warm_logic.kernel.drone.physics import AStarPathfinder, LiPoBatteryModel
from warm_logic.kernel.drone.reality.constants import CONSTANTS
from warm_logic.kernel.drone.safety import DroneSafetyMonitor, ViolationType
from warm_logic.kernel.drone.telemetry import TelemetryManager, TelemetryPacket
from warm_logic.kernel.drone.types import (
    Attitude,
    DroneState,
    DroneStatus,
    FlightMode,
    GeoFence,
    Position,
    Threat,
    Velocity,
    Waypoint,
)


class TestFinalSaturation(unittest.TestCase):
    # --- Types (100%) ---
    def test_types_missing_branches(self):
        att = Attitude(0, 0, math.radians(90))
        self.assertAlmostEqual(att.heading_degrees, 90.0)

        fence = GeoFence(
            id="f1",
            name="f1",
            fence_type="include",
            vertices=[Position(0, 0, 0), Position(1, 1, 1)],
        )
        self.assertFalse(fence.contains(Position(0.5, 0.5, 10)))

    # --- Constants (100%) ---
    def test_constants_properties(self):
        self.assertGreater(CONSTANTS.earth_mu, 0)
        self.assertGreater(CONSTANTS.scale_height, 0)

    # --- Physics (100%) ---
    def test_physics_missing_branches(self):
        batt = LiPoBatteryModel()
        batt.get_state()
        batt._voltage = 0.0
        self.assertEqual(batt.estimate_current(100), 0.0)

        from warm_logic.kernel.drone.physics import SpatialIndex

        si = SpatialIndex()
        si.insert(0, 0, 10, 10, MagicMock(spec=["contains", "id", "name"]))
        si.query_with_altitude(5, 5, 100)

    # --- Safety (100%) ---
    def test_safety_missing_branches(self):
        sm = DroneSafetyMonitor()
        sm.get_stats()
        sm._veto_active = False
        sm.veto_command({}, Position(0, 0, 0))

        sm.min_battery = 10
        sm.check_battery(5)
        sm.check_battery(15)
        sm.check_battery(50)

    # --- Decision (100%) ---
    def test_decision_missing_branches(self):
        de = DroneDecisionEngine()
        status = DroneStatus(
            timestamp=datetime.datetime.now(),
            state=DroneState.IDLE,
            mode=FlightMode.GUIDED,
            position=Position(0, 0, 0),
            velocity=Velocity(0, 0, 0),
            attitude=Attitude(0, 0, 0),
            battery_percent=100,
            gps_satellites=10,
            is_armed=True,
            is_connected=True,
            errors=[],
        )

        threats = [
            Threat("t1", "aircraft", Position(0, 0, 0), 0.96, "collision", "climb")
        ]
        de.decide(status, threats)

        status.battery_percent = 25
        de.decide(status, [])

        status.state = DroneState.IDLE
        de.decide(status, [])

        de._decision_history.append(
            Decision(
                id="d1",
                decision_type=DecisionType.CONTINUE,
                confidence=1.0,
                reasoning=["test"],
                action={},
                threats_considered=[],
            )
        )
        de.get_decision_history(1)

    # --- Telemetry (100%) ---
    def test_telemetry_missing_branches(self):
        tm = TelemetryManager(drone_id="test")
        tm._sock = MagicMock()
        tm._mode = "network"
        tm._connected = True

        status = DroneStatus(
            timestamp=datetime.datetime.now(),
            state=DroneState.IDLE,
            mode=FlightMode.GUIDED,
            position=Position(0, 0, 0),
            velocity=Velocity(0, 0, 0),
            attitude=Attitude(0, 0, 0),
            battery_percent=100,
            gps_satellites=10,
            is_armed=True,
            is_connected=True,
            errors=[],
        )

        # L174-176: SUCCESSFUL send
        tm._sock.sendto.side_effect = None
        tm.send_status(status)
        self.assertGreater(tm._tx_count, 0)

        # L178: BlockingIOError
        tm._sock.sendto.side_effect = BlockingIOError()
        tm.send_status(status)

        # L180: Telemetry TX error
        tm._sock.sendto.side_effect = Exception("General Error")
        tm.send_status(status)

        # L140: PQC sign failed
        tm._pqc_enabled = True
        tm._private_key = "dummy"
        with patch("warm_logic.security.pqc.SovereignSecurity.sign") as mock_sign:
            mock_sign.side_effect = Exception("Sign fail")
            pkt = MagicMock(spec=TelemetryPacket)
            pkt.canonical_string.return_value = "test"
            tm._sign_packet(pkt)

    # --- Controller (100%) ---
    def test_controller_dob_bypass(self):
        dc = DroneController("C1")
        dc.connect()
        dc.arm()
        dc._state = DroneState.FLYING
        dc._rust_controller = None
        dc._dob = MagicMock()
        dc._dob.update.return_value = (15.0, 15.0, 15.0)

        dc.get_control_output()
        self.assertTrue(dc._dob_bypass_warned)


if __name__ == "__main__":
    unittest.main()
