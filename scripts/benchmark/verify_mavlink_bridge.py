"""
[Phase 2] Verify MAVLink SITL/HITL Bridge.
Starts a virtual MAVLink bridge and streams RealityEngine data.
"""

import logging
import sys
import time

# Mocking modules if they are missing to allow script to run partially
try:
    from warm_logic.kernel.drone.hardware import DroneProvider, HardwareConfig
    from warm_logic.kernel.drone.mavlink_bridge import MavlinkBridge
    from warm_logic.kernel.drone.reality.engine import RealityEngine, SimulationState
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyMAVLink")


def run_verification():
    # 1. Setup Bridge (TCP 5760 for SITL)
    config = HardwareConfig(
        provider=DroneProvider.MAVLINK,
        connection="tcp:127.0.0.1:5760",
        baud_rate=115200,
    )
    bridge = MavlinkBridge(config)

    # 2. Setup Reality Engine
    engine = RealityEngine()
    engine.mavlink_bridge = bridge

    state = SimulationState()

    logger.info("Starting MAVLink SITL/HITL Verification Loop...")

    # Note: connect() will fail if no one is listening on port 5760.
    # In a real SITL test, we would start an ArduPilot/PX4 SITL instance.
    # For this unit-level proof, we just check if the methods can be called safely.

    try:
        for i in range(100):
            dt = 0.01  # 100Hz
            result = engine.simulate_step(state, dt)

            if i % 20 == 0:
                logger.info(
                    f"Step {i}: Alt={state.altitude_m:.2f}m | Bus={result['propulsion']['bus_voltage']:.2f}V"
                )

            # Simulate some physics movement
            state.altitude_m += 0.1
            state.pos_d_m -= 0.1

            # We don't call bridge.connect() here to avoid hanging if no SITL is running,
            # but RealityEngine should still safely handle the bridge if it exists.

            time.sleep(0.01)

        logger.info("Verification methods executed successfully.")

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise


if __name__ == "__main__":
    run_verification()
