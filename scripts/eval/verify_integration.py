import logging
import math
import os
import sys
import time

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IntegrationVerify")

try:
    from warm_logic.kernel.drone.control.controller import DroneController, DroneState
    from warm_logic.kernel.drone.types import Position

    print("Imported DroneController")
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)


def verify_integration():
    print("\nDroneController Integration Verification")
    print("===========================================")

    # 1. Initialize
    ctrl = DroneController(drone_id="TEST_DRONE")

    # Check Backend
    if hasattr(ctrl, "_rust_controller") and ctrl._rust_controller:
        print("Rust Backend Detected active in DroneController")
    else:
        print(
            "⚠️  Rust Backend NOT detected. Running in pure Python mode? (Check imports/compilation)"
        )

    # 2. Arm and Set Target
    ctrl.connect()
    ctrl.arm()
    ctrl._state = DroneState.FLYING  # Force state

    # Set Target 10m up
    target = Position(0.0, 0.0, 10.0)
    ctrl.goto(target, speed=5.0)
    print("Armed and Target Set to 10m")

    # 3. Simulation Loop
    print("\n⏱ Running Integration Loop (20 steps)...")

    # Initial state
    current_pos = Position(0.0, 0.0, 0.0)

    # Mock Sensors
    sensors = {
        "imu_accel": (0.0, 0.0, -9.8),
        "imu_gyro": (0.0, 0.0, 0.0),
        "gps_pos": (0.0, 0.0, 0.0),
        "battery_soc": 1.0,
    }

    for i in range(20):
        # Update Sensors
        ctrl.update_state_from_sensors(sensors)

        # Get Output
        outputs = ctrl.get_control_output()

        avg_thrust = sum(outputs) / 4.0

        if i % 5 == 0:
            # Check attitude sync
            att = ctrl._attitude
            print(
                f"[{i:03}] Thrust: {avg_thrust:.3f} | Roll: {math.degrees(att.roll):.1f} | Backend: {'Rust' if ctrl._rust_controller else 'Python'}"
            )

        if avg_thrust <= 0.0:
            print(" Zero thrust? Check logic.")

    print("\nIntegration Verification Complete.")


if __name__ == "__main__":
    verify_integration()
