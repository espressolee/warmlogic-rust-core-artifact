"""
[Phase 150] Mock SITL for MAVLink Bridge Verification.
Simulates an ArduCopter firmware behavior:
1. Listens on UDP 14550 (Standard SITL port).
2. Sends HEARTBEAT (1Hz).
3. Sends GLOBAL_POSITION_INT (4Hz).
4. Responds to COMMAND_LONG (Arm/Takeoff).
5. Accepts SET_POSITION_TARGET_LOCAL_NED.
"""

import math
import socket
import struct
import sys
import time
from threading import Thread

# Try to import pymavlink, else fail gracefully
try:
    from pymavlink import mavutil
except ImportError as e:
    print(f"Error: pymavlink not installed. Cannot run Mock SITL. {e}")
    # DEBUG INFO
    print(f"sys.executable: {sys.executable}")
    print(f"sys.path: {sys.path}")
    sys.exit(1)


class MockSITL:
    def __init__(self, port=14550):
        self.port = port
        self.master = mavutil.mavlink_connection(f"udpin:0.0.0.0:{port}")
        print(f"Mock SITL Listening on 0.0.0.0:{port}")

        # State
        self.armed = False
        self.mode = "STABILIZE"
        self.lat = 0.0 * 1e7
        self.lon = 0.0 * 1e7
        self.alt = 0.0  # mm
        self.vx = 0
        self.vy = 0
        self.vz = 0
        self.boot_time = time.time()

    def run(self):
        # Start Heartbeat Thread
        t_hb = Thread(target=self._heartbeat_loop, daemon=True)
        t_hb.start()

        # Start Position Loop
        t_pos = Thread(target=self._position_loop, daemon=True)
        t_pos.start()

        # Main Command Listener
        self._command_loop()

    def _heartbeat_loop(self):
        while True:
            base_mode = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
            if self.armed:
                base_mode |= mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED

            self.master.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_QUADROTOR,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                base_mode,
                0,  # Custom mode
                mavutil.mavlink.MAV_STATE_ACTIVE,
            )
            time.sleep(1.0)

    def _position_loop(self):
        while True:
            # Simple simulation: Constant velocity motion
            dt = 0.25  # 4Hz

            # Update Position
            self.lat += int(self.vx * dt * 100)  # Simple approx
            self.lon += int(self.vy * dt * 100)
            self.alt += int(-self.vz * dt * 1000)

            # Send TELEMETRY
            self.master.mav.global_position_int_send(
                int((time.time() - self.boot_time) * 1000),
                int(self.lat),
                int(self.lon),
                int(self.alt),
                int(self.alt),  # Relative alt
                int(self.vx * 100),
                int(self.vy * 100),
                int(self.vz * 100),
                int(4500),  # Heading
            )

            # Send ATTITUDE (Dummy)
            self.master.mav.attitude_send(
                int((time.time() - self.boot_time) * 1000), 0, 0, 0, 0, 0, 0
            )

            # Send SYS_STATUS (Battery)
            self.master.mav.sys_status_send(
                0,
                0,
                0,
                500,
                12500,  # 12.5V
                1000,  # 10A
                95,  # 95%
                0,
                0,
                0,
                0,
                0,
                0,
            )

            time.sleep(dt)

    def _command_loop(self):
        while True:
            msg = self.master.recv_match(blocking=True)
            if not msg:
                continue

            msg_type = msg.get_type()

            if msg_type == "COMMAND_LONG":
                self._handle_command(msg)
            elif msg_type == "SET_MODE":
                self._handle_mode(msg)
            elif msg_type == "SET_POSITION_TARGET_LOCAL_NED":
                self._handle_set_target(msg)
            elif msg_type == "REQUEST_DATA_STREAM":
                # Ack
                pass

    def _handle_command(self, msg):
        command = msg.command
        print(f"Received COMMAND_LONG: {command}")

        result = mavutil.mavlink.MAV_RESULT_ACCEPTED

        if command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
            arm_cmd = int(msg.param1)
            if arm_cmd == 1:
                print(" ARMING MOTORS")
                self.armed = True
            else:
                print("DISARMING MOTORS")
                self.armed = False

        elif command == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF:
            alt = msg.param7
            print(f"TAKEOFF to {alt}m")
            self.armed = True
            self.vz = -1.0  # 1m/s climb

        # Send ACK
        self.master.mav.command_ack_send(command, result)

    def _handle_mode(self, msg):
        print(f"Setting Mode: {msg.custom_mode}")
        # Need mapping logic, skipping for now

    def _handle_set_target(self, msg):
        # We received a velocity/position setpoint
        # Let's just print it for verification
        print(
            f"🎯 Target: x={msg.x:.1f}, y={msg.y:.1f}, z={msg.z:.1f} (Type: {msg.type_mask})"
        )


if __name__ == "__main__":
    sitl = MockSITL()
    sitl.run()
