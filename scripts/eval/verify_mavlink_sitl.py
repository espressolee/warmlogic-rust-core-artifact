"""
[Phase 150] Verify MAVLink Bridge with Mock SITL.
1. Connects to Mock SITL (UDP 14550).
2. Waits for Heartbeat.
3. Arms Drone.
4. Takes off to 10m.
5. Verifies Telemetry (Altitude > 5m).
"""

import os
import sys
import time

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from warm_logic.kernel.drone.control import DroneController
from warm_logic.kernel.drone.hardware import DroneProvider, HardwareConfig
from warm_logic.kernel.drone.types import DroneState


def verify_sitl():
    print("MAVLink Bridge Verification")
    print("============================")

    # 1. Config
    config = HardwareConfig(
        provider=DroneProvider.MAVLINK,
        connection="udp:127.0.0.1:14550",  # Standard SITL port
    )

    # 2. Initialize Controller with Hardware
    # We need to inject the hardware config into DroneController.
    # Currently DroneController defaults to internal sim.
    # We need to modify DroneController or just instantiate the hardware directly?
    # Ideally DroneController should accept a config.

    # Checking DroneController.__init__ signature...
    # It takes (drone_id: str).
    # It constructs `self.hardware` internally?
    # Let's inspect DroneController again to be sure.
    # For now, I will assume we might need to "inject" it or modify DroneController.

    # Actually, let's just use the Hardware Interface directly for this test
    # to verify the *Bridge* alone (Unit/Integration test).
    # OR, better: Update `DroneController` to accept a `hardware_config`.

    # Let's use the Factory directly first to verify connectivity.
    from warm_logic.kernel.drone.hardware import DroneHardwareFactory

    print("Connecting to SITL...")
    hw = DroneHardwareFactory.create(config)
    if not hw.connect():
        print("Failed to connect to SITL.")
        sys.exit(1)

    print("Connected. Waiting for Heartbeat/Telemetry...")
    time.sleep(2)

    status = hw.get_status()
    print(
        f"📊 Status: Armed={status.is_armed}, Mode={status.mode}, Alt={status.position.altitude:.1f}m"
    )

    if status.position.altitude != 0.0:
        # It might be non-zero if sim is running
        pass

    # 3. Arm
    print("Arming...")
    res = hw.arm()
    if not res.get("success"):
        print(f"Arm failed: {res}")
        sys.exit(1)
    time.sleep(1)

    # 4. Takeoff
    print("Takeoff to 10m...")
    res = hw.takeoff(10.0)
    if not res.get("success"):
        print(f"Takeoff failed: {res}")
        sys.exit(1)

    # 5. Monitor
    for i in range(10):
        time.sleep(1)
        status = hw.get_status()
        print(
            f"T={i}s | Armed={status.is_armed} | Alt={status.position.altitude:.1f}m | Bat={status.battery_percent:.1f}%"
        )

        if status.position.altitude > 5.0:
            print("Altitude verified (>5m).")
            print("MAVLink Bridge Verification SUCCESS!")
            return

    print("Timeout waiting for altitude.")
    sys.exit(1)


if __name__ == "__main__":
    verify_sitl()
