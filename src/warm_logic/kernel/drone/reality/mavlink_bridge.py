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
MAVLink HITL Bridge.

Bridges RealityEngine sensor data to MAVLink HIL messages.
"""

from typing import Tuple

try:
    from pymavlink import mavutil
except ImportError:
    mavutil = None


class MAVLinkBridge:
    """Handles MAVLink communication for HITL simulation."""

    def __init__(self, connection_string: str = "udpout:127.0.0.1:14550"):
        if mavutil is None:
            raise RuntimeError(
                "pymavlink is required for MAVLinkBridge; install pymavlink to use HITL."
            )
        self.master = mavutil.mavlink_connection(connection_string)
        self.source_system = 1
        self.source_component = 1
        print(f"[MAVLinkBridge] Connected to {connection_string}")

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
        fields_updated: int = 0xFFFFFFFF,
    ) -> None:
        """Send HIL_SENSOR message."""
        self.master.mav.hil_sensor_send(
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
            fields_updated,
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
        """Send HIL_GPS message."""
        self.master.mav.hil_gps_send(
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

    def heartbeat(self) -> None:
        """Send MAVLink heartbeat."""
        self.master.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0,
            0,
            0,
        )
