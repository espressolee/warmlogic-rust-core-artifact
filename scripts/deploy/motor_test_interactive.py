import argparse
import os
import sys
import time

from pymavlink import mavutil


def motor_test(connection_string, baud):
    print(f"Connecting to Flight Controller at {connection_string} ({baud})...")
    master = mavutil.mavlink_connection(connection_string, baud=baud)
    master.wait_heartbeat()
    print("Heartbeat received!")

    # Check Arming
    if master.motors_armed():
        print("DANGER: Vehicle is ARMED! Disarm manually first.")
        return

    print("\nInteractive Motor Test (Props REMOVED?)")
    print("1. Front-Right (CCW)")
    print("2. Rear-Left (CCW)")
    print("3. Front-Left (CW)")
    print("4. Rear-Right (CW)")
    print("0. Exit")

    while True:
        try:
            choice = input("\nSelect Motor (1-4) or 0 to Exit: ")
            if choice == "0":
                break

            motor_idx = int(choice)
            if motor_idx < 1 or motor_idx > 4:
                print("Invalid selection.")
                continue

            # MAVLink Motor Test Command
            # MOTOR_TEST_THROTTLE_PERCENT is 0-100
            throttle_pct = 5
            duration_sec = 2

            print(
                f"🚀 Spinning Motor {motor_idx} at {throttle_pct}% for {duration_sec}s..."
            )

            # Protocol: MAV_CMD_DO_MOTOR_TEST
            # param1: Motor ID (1-based or 0-based? ArduPilot is 1-based usually, PX4 1-based)
            # param2: Throttle type (0=percent, 1=pwm, 2=pilot, 3=deprecated)
            # param3: Throttle value
            # param4: Timeout (seconds)
            # param5: Motor count (0 for single)

            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
                0,  # Confirmation
                motor_idx,  # Param 1: Motor ID
                0,  # Param 2: Throttle Percent
                throttle_pct,  # Param 3: Value
                duration_sec,  # Param 4: Timeout
                1,  # Param 5: Count
                0,  # Param 6
                0,  # Param 7
            )

            # Wait for user validation
            time.sleep(duration_sec)
            print("Done.")

        except ValueError:
            print("Invalid input.")
        except KeyboardInterrupt:
            print("\nAborted.")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Interactive Motor Tester")
    parser.add_argument(
        "--connect", default="/dev/ttyACM0", help="Serial port or connection string"
    )
    parser.add_argument("--baud", default=57600, type=int, help="Baud rate")
    args = parser.parse_args()

    motor_test(args.connect, args.baud)
