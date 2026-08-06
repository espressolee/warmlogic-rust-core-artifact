# Copyright 2026 espressolee
import socket
import time
from unittest.mock import MagicMock

import pytest

from warm_logic.kernel.drone.reality.engine import RealityEngine, SimulationState
from warm_logic.kernel.drone.reality.mavlink_bridge import MAVLinkBridge


def test_mavlink_bridge_streaming():
    """Verify that RealityEngine calls bridge methods during simulation."""
    # Setup mock bridge
    mock_bridge = MagicMock(spec=MAVLinkBridge)

    engine = RealityEngine(mavlink_bridge=mock_bridge)
    state = SimulationState()

    # Run one step
    engine.simulate_step(state, dt=0.01)

    # Verify bridge calls
    assert mock_bridge.send_hil_sensor.called
    assert mock_bridge.send_hil_gps.called

    # Check arguments
    args, kwargs = mock_bridge.send_hil_sensor.call_args
    assert "time_usec" in kwargs or args[0] == 0
    assert len(args) >= 3 or "accel" in kwargs


def test_mavlink_bridge_real_udp_init():
    """Verify that MAVLinkBridge can initialize a UDP socket."""
    try:
        bridge = MAVLinkBridge(connection_string="udpin:127.0.0.1:14551")
        assert bridge.master is not None
        bridge.master.close()
    except Exception as e:
        pytest.fail(f"MAVLinkBridge initialization failed: {e}")
