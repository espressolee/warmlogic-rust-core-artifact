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
Drone Control Package.

Provides robust control algorithms for stabilization and autonomy.
"""

from .controller import CommandType, DroneController

# Re-export types for convenience
from warm_logic.kernel.drone.types import DroneState, FlightMode

# Future imports (will be uncommented as implemented)
# from .filter import NotchFilter, LowPassFilter
# from .pid import RobustPID
# from .ekf import ExtendedKalmanFilter

__all__ = ["DroneController", "CommandType", "DroneState", "FlightMode"]
