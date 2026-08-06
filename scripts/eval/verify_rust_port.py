import math
import os
import sys
import time

import numpy as np

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

try:
    from warm_logic_rs import PyDroneController

    print("Successfully imported warm_logic_rs.PyDroneController")
except ImportError as e:
    print(f"Failed to import warm_logic_rs: {e}")
    sys.exit(1)

# Mock Python implementation if imports fail/complex
# Actually, let's try to import real Python controller.
try:
    from warm_logic.kernel.drone.controller import DroneController

    from warm_logic.kernel.drone.hardware import DroneProvider, HardwareConfig

    print("Successfully imported warm_logic.kernel.drone.controller.DroneController")
except ImportError:
    print(" Could not import Python DroneController. Running Rust-only verification.")
    DroneController = None


def verify_rust_controller():
    print("\n螃蟹 Rust Drone Controller Verification")
    print("========================================")

    # 1. Initialize Rust Controller
    rust_ctrl = PyDroneController()
    print("Rust Controller Initialized")

    # 2. Configure
    # Target: 10m altitude, 0,0 pos, 0 yaw
    rust_ctrl.set_target(0.0, 0.0, -10.0, 0.0)
    rust_ctrl.set_armed(True)
    print("Configured Target: Alt=10m")

    # 3. Simulate Loop (1s)
    print("\n⏱ Running Simulation Loop (100 Hz)...")

    # Inputs: Stable hover state
    gx, gy, gz = 0.0, 0.0, 0.0
    ax, ay, az = 0.0, 0.0, -9.81  # Gravity down

    # State tracking
    alt = 0.0
    velocity_z = 0.0
    dt = 0.01

    for i in range(100):
        # Update IMU
        rust_ctrl.update_imu(gx, gy, gz, ax, ay, az)

        # Get Outputs
        # current_alt is positive up in get_control_output logic?
        # Rust impl: target_alt = -target_pos.z = 10.0. alt_error = target_alt - current_alt.
        # So current_alt should be +10.0 for target.
        # Start at 0.0
        outputs = rust_ctrl.get_control_output(alt)

        # Simple Physics (Vertical only)
        # Total Thrust normalized 0-1. Assume T_w ratio = 2.0 (hover at 0.5) or 0.31 per code?
        # Code: thrust_total = 0.31 + pid ...
        # Let's just verify outputs are valid

        fl, fr, bl, br = outputs
        avg_thrust = (fl + fr + bl + br) / 4.0

        # Verification Checks
        if i % 20 == 0:
            att = rust_ctrl.get_attitude()
            print(
                f"[{i:03}] Alt: {alt:.2f}m | Thrust: {avg_thrust:.3f} | Attitude: {att}"
            )

        if avg_thrust < 0.0 or avg_thrust > 1.0:
            print(f"Invalid Thrust Output: {avg_thrust}")
            sys.exit(1)

        # Mock physics update
        # accel_z = (thrust * T_W_ratio * g) - g
        # assume T_W = 3.0, hover at 0.33
        accel_net = (avg_thrust * 3.0 * 9.81) - 9.81
        velocity_z += accel_net * dt
        alt += velocity_z * dt

    print("\nVerification Complete.")
    print(f"Final Altitude: {alt:.2f}m (Should be climbing towards 10m)")

    if alt > 0.5:
        print("physics simulation confirms climb!")
    else:
        print(" Drone did not climb? Check tuning.")


if __name__ == "__main__":
    verify_rust_controller()
