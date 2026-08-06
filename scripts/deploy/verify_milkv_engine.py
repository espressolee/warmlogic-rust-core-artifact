import math

import warm_logic_rs


def test_rust_engine():
    print("--- WarmLogic RISC-V Engine Verification ---")

    # 1. Initialize Controller
    try:
        controller = warm_logic_rs.PyDroneController()
        print("PyDroneController Initialized")
    except Exception as e:
        print(f"Initialization Failed: {e}")
        return

    # 2. Test EKF / Attitude
    # Simulate a 10-degree roll
    # accel: [0, sin(10), -cos(10)] * 9.81
    roll_rad = math.radians(10)
    ay = math.sin(roll_rad) * 9.81
    az = -math.cos(roll_rad) * 9.81

    print(f"Simulating 10-degree roll (ay={ay:.2f}, az={az:.2f})...")

    # Run a few updates to let EKF settle
    for _ in range(50):
        controller.update_imu(0.0, 0.0, 0.0, 0.0, ay, az)

    r, p, y = controller.get_attitude()
    print(f"Detected Attitude: Roll={r:.2f}°, Pitch={p:.2f}°, Yaw={y:.2f}°")

    if abs(r - 10.0) < 1.0:
        print("EKF Math Logic Verified (Roll matches gravity vector)")
    else:
        print("EKF Convergence issues or coordinate mismatch")

    # 3. Test Control Loop
    controller.set_target(
        0.0, 0.0, -10.0, 0.0
    )  # Target 10m altitude (Down is negative? No, Z is Down in NED)
    # Wait, check controller.rs for Z convention.
    # Usually NED means Z-Down. So target_pos.z = -10.0 means 10m Up.

    controller.set_armed(True)
    out = controller.get_control_output(0.0)  # Current alt 0
    print(f"Control Output (at 0m, target 10m): {out}")

    if any(m > 0 for m in out):
        print("Control Loop Producing Thrust")
    else:
        print("Control Loop Idle (Check arming/target)")

    print("--- Verification Complete ---")


if __name__ == "__main__":
    test_rust_engine()
