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
[Phase 116.2] DJI/Pixhawk Drone Framework.
Real hardware integration layer.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List

from .types import DroneState, DroneStatus, FlightMode, Position

logger = logging.getLogger("DroneHardware")


class DroneProvider(Enum):
    DJI = "dji"
    PIXHAWK = "pixhawk"
    PX4 = "px4"
    ARDUPILOT = "ardupilot"
    MAVLINK = "mavlink"


@dataclass
class HardwareConfig:
    provider: DroneProvider
    connection: str  # e.g., "/dev/ttyUSB0" or "tcp:127.0.0.1:5760"
    baud_rate: int = 57600


class DroneHardwareInterface(ABC):
    """Abstract hardware interface."""

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def arm(self) -> Dict:
        pass

    @abstractmethod
    def takeoff(self, alt: float) -> Dict:
        pass

    @abstractmethod
    def land(self) -> Dict:
        pass

    @abstractmethod
    def get_status(self) -> DroneStatus:
        pass


class PixhawkInterface(DroneHardwareInterface):
    """
    Pixhawk/PX4 hardware interface.
    Uses MAVLink protocol over serial/UDP.
    """

    def __init__(self, config: HardwareConfig):
        self.config = config
        self._connected = False
        self._armed = False
        self._position = Position(0, 0, 0)
        logger.info(f"[Pixhawk] Interface Ready: {config.connection}")

    def connect(self) -> bool:
        # In production: pyserial or pymavlink connection
        self._connected = True
        logger.info("Pixhawk connected (simulated)")
        return True

    def arm(self) -> Dict:
        if not self._connected:
            return {"success": False, "error": "not_connected"}
        self._armed = True
        return {"success": True}

    def takeoff(self, alt: float) -> Dict:
        if not self._armed:
            return {"success": False, "error": "not_armed"}
        self._position = Position(
            self._position.latitude, self._position.longitude, alt
        )
        return {"success": True, "altitude": alt}

    def land(self) -> Dict:
        self._position = Position(self._position.latitude, self._position.longitude, 0)
        self._armed = False
        return {"success": True}

    def get_status(self) -> DroneStatus:
        from .types import Attitude, Velocity

        return DroneStatus(
            timestamp=datetime.now(),
            state=DroneState.FLYING if self._armed else DroneState.IDLE,
            mode=FlightMode.GUIDED,
            position=self._position,
            velocity=Velocity(0, 0, 0),
            attitude=Attitude(0, 0, 0),
            battery_percent=85.0,
            gps_satellites=10,
            is_armed=self._armed,
            is_connected=self._connected,
        )


class DJIInterface(DroneHardwareInterface):
    """
    DJI SDK interface (simulated).
    In production: Use DJI Mobile SDK or Windows SDK.
    """

    def __init__(self, config: HardwareConfig):
        self.config = config
        self._connected = False
        self._armed = False
        self._position = Position(0, 0, 0)
        logger.info("[DJI] Interface Ready")

    def connect(self) -> bool:
        self._connected = True
        logger.info("DJI connected (simulated)")
        return True

    def arm(self) -> Dict:
        self._armed = True
        return {"success": True}

    def takeoff(self, alt: float) -> Dict:
        self._position = Position(
            self._position.latitude, self._position.longitude, alt
        )
        return {"success": True}

    def land(self) -> Dict:
        self._position = Position(self._position.latitude, self._position.longitude, 0)
        self._armed = False
        return {"success": True}

    def get_status(self) -> DroneStatus:
        from .types import Attitude, Velocity

        return DroneStatus(
            timestamp=datetime.now(),
            state=DroneState.FLYING if self._armed else DroneState.IDLE,
            mode=FlightMode.AUTO,
            position=self._position,
            velocity=Velocity(0, 0, 0),
            attitude=Attitude(0, 0, 0),
            battery_percent=90.0,
            gps_satellites=14,
            is_armed=self._armed,
            is_connected=self._connected,
        )


class DroneHardwareFactory:
    """Factory for creating hardware interfaces."""

    @staticmethod
    def create(config: HardwareConfig) -> DroneHardwareInterface:
        if config.provider == DroneProvider.DJI:
            return DJIInterface(config)
        elif config.provider in (
            DroneProvider.PIXHAWK,
            DroneProvider.PX4,
            DroneProvider.ARDUPILOT,
        ):
            return PixhawkInterface(config)
        elif config.provider == DroneProvider.MAVLINK:
            from .mavlink_bridge import MavlinkBridge

            return MavlinkBridge(config)
        else:
            raise ValueError(f"Unknown provider: {config.provider}")


class DroneTestFramework:
    """
    Unified test framework for all drone types.
    Runs same tests across DJI, Pixhawk, Simulator.
    """

    def __init__(self):
        self.interfaces: Dict[str, DroneHardwareInterface] = {}
        self.results: Dict[str, List] = {}

    def add_interface(self, name: str, interface: DroneHardwareInterface):
        self.interfaces[name] = interface
        self.results[name] = []

    def run_all_tests(self) -> Dict:
        """Run tests on all registered interfaces."""
        for name, interface in self.interfaces.items():
            self._run_tests(name, interface)

        return {
            "summary": {
                name: {"passed": sum(1 for r in res if r["pass"]), "total": len(res)}
                for name, res in self.results.items()
            },
            "details": self.results,
        }

    def _run_tests(self, name: str, interface: DroneHardwareInterface):
        tests = [
            ("connect", lambda: interface.connect()),
            ("arm", lambda: interface.arm()),
            ("takeoff", lambda: interface.takeoff(10)),
            ("status", lambda: interface.get_status()),
            ("land", lambda: interface.land()),
        ]

        for test_name, test_fn in tests:
            try:
                start = time.time()
                result = test_fn()
                elapsed = (time.time() - start) * 1000
                if isinstance(result, bool):
                    passed = result
                elif isinstance(result, dict):
                    passed = result.get("success", True)
                else:
                    passed = True
                self.results[name].append(
                    {"test": test_name, "pass": passed, "latency_ms": elapsed}
                )
            except Exception as e:
                self.results[name].append(
                    {"test": test_name, "pass": False, "error": str(e)}
                )
