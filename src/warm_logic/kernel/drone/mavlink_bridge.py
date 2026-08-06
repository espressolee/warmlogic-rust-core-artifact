# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
[Phase 150] MAVLink Hardware Bridge.
Connects DroneController to MAVLink-enabled hardware (Pixhawk, Cube, SITL).
"""

import logging
import time
from datetime import datetime
from threading import Event, Thread
from typing import Any, Dict, Optional, Tuple

try:
    from pymavlink import mavutil
except ImportError:
    mavutil = None

# Correct import path assuming this file is in warm_logic.kernel.drone
from warm_logic.kernel.drone.hardware import (
    DroneHardwareInterface,
    DroneStatus,
    HardwareConfig,
)
from warm_logic.kernel.drone.types import (
    Attitude,
    DroneState,
    FlightMode,
    Position,
    Velocity,
)

logger = logging.getLogger("MavlinkBridge")


class MavlinkBridge(DroneHardwareInterface):
    """
    Real MAVLink Interface using pymavlink.
    Supports: HEARTBEAT, GLOBAL_POSITION_INT, ATTITUDE, SYS_STATUS.
    """

    def __init__(self, config: HardwareConfig) -> None:
        self.config = config
        self._master: Optional[Any] = None
        self._connected = False
        self._armed = False
        self._mode = FlightMode.STABILIZE

        # Telemetry State
        self._position = Position(0, 0, 0)
        self._velocity = Velocity(0, 0, 0)
        self._attitude = Attitude(0, 0, 0)
        self._battery_voltage = 0.0
        self._battery_current = 0.0
        self._battery_remaining = 0
        self._satellites_visible = 0

        # Threading
        self._stop_event = Event()
        self._thread: Optional[Thread] = None

        if mavutil is None:
            logger.warning("pymavlink not installed. MAVLink bridge will not function.")

    def connect(self) -> bool:
        if mavutil is None:
            return False

        try:
            logger.info(
                f"Connecting to MAVLink: {self.config.connection} (Baud: {self.config.baud_rate})"
            )
            # Create the connection
            self._master = mavutil.mavlink_connection(
                self.config.connection, baud=self.config.baud_rate
            )

            # Wait for the first heartbeat
            self._master.wait_heartbeat(timeout=5)
            logger.info(
                "Heartbeat received from system (system %u component %u)"
                % (self._master.target_system, self._master.target_component)
            )

            self._connected = True

            # Start listener thread
            self._stop_event.clear()
            self._thread = Thread(target=self._listener_loop, daemon=True)
            self._thread.start()

            # Request data stream
            self._request_data_stream()

            return True
        except Exception as e:
            logger.error(f"Failed to connect to MAVLink: {e}")
            return False

    def _request_data_stream(self) -> None:
        """Request all data streams."""
        if self._master is None:
            return

        # MAV_DATA_STREAM_ALL = 0
        self._master.mav.request_data_stream_send(
            self._master.target_system,
            self._master.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            4,  # Rate (Hz)
            1,  # Start
        )

    def _listener_loop(self) -> None:
        """Background thread to read MAVLink messages."""
        while not self._stop_event.is_set():
            if self._master is None:
                break
            try:
                msg = self._master.recv_match(blocking=True, timeout=1.0)
                if not msg:
                    continue

                self._handle_message(msg)

            except Exception as e:
                logger.debug(f"MAVLink verify error: {e}")
                time.sleep(0.1)

    def _handle_message(self, msg: Any) -> None:
        """Parse incoming MAVLink messages."""
        msg_type = msg.get_type()

        if msg_type == "HEARTBEAT":
            self._handle_heartbeat(msg)
        elif msg_type == "GLOBAL_POSITION_INT":
            self._handle_global_position(msg)
        elif msg_type == "ATTITUDE":
            self._handle_attitude(msg)
        elif msg_type == "SYS_STATUS":
            self._handle_sys_status(msg)
        elif msg_type == "GPS_RAW_INT":
            self._satellites_visible = msg.satellites_visible

    def _handle_heartbeat(self, msg: Any) -> None:
        self._armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
        # Map custom mode to FlightMode if needed (complex mapping usually)

    def _handle_global_position(self, msg: Any) -> None:
        # Lat/Lon are deg * 1e7
        # Alt is mm
        # Vx, Vy, Vz are cm/s
        self._position = Position(
            latitude=msg.lat / 1e7,
            longitude=msg.lon / 1e7,
            altitude=msg.relative_alt / 1000.0,
        )
        self._velocity = Velocity(
            north=msg.vx / 100.0, east=msg.vy / 100.0, down=msg.vz / 100.0
        )

    def _handle_attitude(self, msg: Any) -> None:
        # Roll, Pitch, Yaw in radians
        self._attitude = Attitude(roll=msg.roll, pitch=msg.pitch, yaw=msg.yaw)

    def _handle_sys_status(self, msg: Any) -> None:
        self._battery_voltage = msg.voltage_battery / 1000.0  # mV -> V
        self._battery_current = msg.current_battery / 100.0  # cA -> A
        self._battery_remaining = msg.battery_remaining  # %

    def arm(self) -> Dict[str, Any]:
        if not self._connected or self._master is None:
            return {"success": False, "error": "not_connected"}

        try:
            self._master.arducopter_arm()
            self._master.motors_armed_wait()
            return {"success": True}
        except Exception as e:
            logger.error(f"Arming failed: {e}")
            return {"success": False, "error": str(e)}

    def takeoff(self, alt: float) -> Dict[str, Any]:
        if not self._connected or self._master is None:
            return {"success": False, "error": "not_connected"}

        try:
            # Switch to GUIDED mode first
            if not self.set_mode("GUIDED"):
                return {"success": False, "error": "failed_to_enter_guided_mode"}

            # Send Takeoff command
            self._master.mav.command_long_send(
                self._master.target_system,
                self._master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,  # Confirmation
                0,
                0,
                0,
                0,
                0,
                0,  # Params 1-6 (Empty)
                alt,  # Param 7: Altitude
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def land(self) -> Dict[str, Any]:
        if not self._connected:
            return {"success": False, "error": "not_connected"}

        try:
            if not self.set_mode("LAND"):
                return {"success": False, "error": "failed_to_enter_land_mode"}
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_mode(self, mode: str) -> bool:
        """Set flight mode (e.g. GUIDED, STABILIZE)."""
        if self._master is None:
            return False

        # Check mapping
        mode_id = self._master.mode_mapping().get(mode)
        if mode_id is None:
            logger.error(f"Unknown mode: {mode}")
            return False

        try:
            self._master.set_mode(mode_id)
            return True
        except Exception as e:
            logger.error(f"Failed to set mode {mode}: {e}")
            return False

    def get_status(self) -> DroneStatus:
        if not self._connected:
            # Return dummy if not connected
            return DroneStatus(
                timestamp=datetime.now(),
                state=DroneState.IDLE,
                mode=FlightMode.STABILIZE,
                position=self._position,
                velocity=self._velocity,
                attitude=self._attitude,
                battery_percent=0.0,
                gps_satellites=0,
                is_armed=False,
                is_connected=False,
            )

        return DroneStatus(
            timestamp=datetime.now(),
            state=DroneState.FLYING if self._armed else DroneState.IDLE,
            mode=FlightMode.GUIDED,  # Simplified
            position=self._position,
            velocity=self._velocity,
            attitude=self._attitude,
            battery_percent=float(self._battery_remaining),
            gps_satellites=self._satellites_visible,
            is_armed=self._armed,
            is_connected=self._connected,
        )

    # --- HITL (Hardware-In-The-Loop) Support ---

    def send_hil_sensor(
        self,
        time_usec: int,
        accel: Tuple[float, float, float],
        gyro: Tuple[float, float, float],
        mag: Tuple[float, float, float],
        abs_pressure: float,
        diff_pressure: float,
        pressure_alt: float,
        temperature: float,
    ) -> None:
        """Send HIL_SENSOR message to the FC."""
        if self._master is None:
            return

        self._master.mav.hil_sensor_send(
            time_usec,
            accel[0],
            accel[1],
            accel[2],
            gyro[0],
            gyro[1],
            gyro[2],
            mag[0],
            mag[1],
            mag[2],
            abs_pressure,
            diff_pressure,
            pressure_alt,
            temperature,
            fields_updated=0xFFFFFFFF,  # Mark all fields as updated
        )

    def send_hil_gps(
        self,
        time_usec: int,
        fix_type: int,
        lat: int,
        lon: int,
        alt: int,
        eph: int,
        epv: int,
        vel: int,
        vn: int,
        ve: int,
        vd: int,
        cog: int,
        satellites_visible: int,
    ) -> None:
        """Send HIL_GPS message to the FC."""
        if self._master is None:
            return

        self._master.mav.hil_gps_send(
            time_usec,
            fix_type,
            lat,
            lon,
            alt,
            eph,
            epv,
            vel,
            vn,
            ve,
            vd,
            cog,
            satellites_visible,
        )

    def send_hil_state_quaternion(
        self,
        time_usec: int,
        q: Tuple[float, float, float, float],
        rollspeed: float,
        pitchspeed: float,
        yawspeed: float,
        lat: int,
        lon: int,
        alt: int,
        vx: int,
        vy: int,
        vz: int,
        ind_airspeed: int,
        true_airspeed: int,
        xacc: int,
        yacc: int,
        zacc: int,
    ) -> None:
        """Send HIL_STATE_QUATERNION message (Ground Truth)."""
        if self._master is None:
            return

        self._master.mav.hil_state_quaternion_send(
            time_usec,
            list(q),
            rollspeed,
            pitchspeed,
            yawspeed,
            lat,
            lon,
            alt,
            vx,
            vy,
            vz,
            ind_airspeed,
            true_airspeed,
            xacc,
            yacc,
            zacc,
        )
