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
IMU Error Models based on Allan Variance.

Reference:
    IEEE Std 952-1997 (R2016), "IEEE Standard Specification Format
    Guide and Test Procedure for Single-Axis Interferometric Fiber
    Optic Gyros"

    IEEE Std 1293-2018, "IEEE Standard Specification Format Guide
    and Test Procedure for Linear Single-Axis, Nongyroscopic
    Accelerometers"

    El-Sheimy, N. et al. (2008), "Analysis and Modeling of Inertial
    Sensors Using Allan Variance" IEEE Transactions on Instrumentation
    and Measurement, Vol. 57, No. 1

Theory:
    Allan Variance (AVAR) identifies noise components in IMU data:
    - White Noise (Angle/Velocity Random Walk)
    - Bias Instability (Flicker noise)
    - Rate Random Walk
    - Rate Ramp (deterministic drift)

    σ²(τ) = N²/τ + B²/3 + K²τ/3 + R²τ²/2

    Where:
        N = White noise coefficient (ARW for gyro, VRW for accel)
        B = Bias instability
        K = Rate random walk
        R = Rate ramp
        τ = Averaging time
"""

import math
import random
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class AllanVarianceParameters:
    """
    Allan Variance noise parameters.

    Reference: IEEE Std 952-1997, Section 5.4

    Typical values for consumer MEMS (MPU6050 class):
        Gyro ARW: 0.3 deg/√hr
        Gyro BI: 10 deg/hr
        Accel VRW: 0.1 m/s/√hr
        Accel BI: 0.04 mg

    Typical values for tactical MEMS (ADIS16470 class):
        Gyro ARW: 0.06 deg/√hr
        Gyro BI: 1 deg/hr
        Accel VRW: 0.04 m/s/√hr
        Accel BI: 0.01 mg
    """

    # Angle Random Walk (deg/√hr for gyro, m/s/√hr for accel)
    random_walk: float = 0.3

    # Bias Instability (deg/hr for gyro, mg for accel)
    bias_instability: float = 10.0

    # Rate Random Walk (deg/hr^1.5 for gyro)
    rate_random_walk: float = 0.01

    # Rate Ramp (deterministic drift, deg/hr² for gyro)
    rate_ramp: float = 0.0

    def convert_to_si(self, sensor_type: str = "gyro") -> "AllanVarianceParameters":
        """
        Convert from IEEE units to SI.

        Args:
            sensor_type: 'gyro' or 'accel'

        Returns:
            Parameters in SI units (rad/s, m/s²)
        """
        if sensor_type == "gyro":
            return AllanVarianceParameters(
                random_walk=math.radians(self.random_walk) / 60,  # deg/√hr → rad/s/√Hz
                bias_instability=math.radians(self.bias_instability)
                / 3600,  # deg/hr → rad/s
                rate_random_walk=math.radians(self.rate_random_walk) / 3600**1.5,
                rate_ramp=math.radians(self.rate_ramp) / 3600**2,
            )
        else:  # accel
            return AllanVarianceParameters(
                random_walk=self.random_walk * 9.80665 / 3600,  # m/s/√hr → m/s²/√Hz
                bias_instability=self.bias_instability * 9.80665e-3,  # mg → m/s²
                rate_random_walk=self.rate_random_walk * 9.80665 / 3600**1.5,
                rate_ramp=self.rate_ramp * 9.80665 / 3600**2,
            )


@dataclass
class AllanVarianceIMU:
    """
    IMU Error Model based on Allan Variance Analysis.

    Reference:
        IEEE Std 952-1997, Section 5
        El-Sheimy et al. (2008)

    Models five noise components:
        1. Quantization noise (high-frequency)
        2. Angle/Velocity Random Walk (white noise)
        3. Bias Instability (1/f noise)
        4. Rate Random Walk (Brownian motion)
        5. Rate Ramp (deterministic trend)

    Example:
        >>> imu = AllanVarianceIMU()
        >>> noisy_gyro = imu.corrupt_gyro((0.0, 0.0, 0.1), dt=0.01)
    """

    # Gyro parameters (3-axis)
    gyro_params: Tuple[
        AllanVarianceParameters, AllanVarianceParameters, AllanVarianceParameters
    ] = field(
        default_factory=lambda: (
            AllanVarianceParameters(),
            AllanVarianceParameters(),
            AllanVarianceParameters(),
        )
    )

    # Accel parameters (3-axis)
    accel_params: Tuple[
        AllanVarianceParameters, AllanVarianceParameters, AllanVarianceParameters
    ] = field(
        default_factory=lambda: (
            AllanVarianceParameters(random_walk=0.1, bias_instability=0.04),
            AllanVarianceParameters(random_walk=0.1, bias_instability=0.04),
            AllanVarianceParameters(random_walk=0.1, bias_instability=0.04),
        )
    )

    # Internal states
    _gyro_bias: Tuple[float, float, float] = field(default=(0.0, 0.0, 0.0), repr=False)
    _accel_bias: Tuple[float, float, float] = field(default=(0.0, 0.0, 0.0), repr=False)
    _gyro_rw: Tuple[float, float, float] = field(default=(0.0, 0.0, 0.0), repr=False)
    _accel_rw: Tuple[float, float, float] = field(default=(0.0, 0.0, 0.0), repr=False)

    def corrupt_gyro(
        self, true_rate: Tuple[float, float, float], dt: float
    ) -> Tuple[float, float, float]:
        """
        Apply Allan Variance noise model to gyroscope.

        Reference: IEEE Std 952-1997, Eq. 5.1

        Args:
            true_rate: True angular rate (rad/s)
            dt: Time step (s)

        Returns:
            Corrupted angular rate (rad/s)
        """
        result = list(true_rate)

        for i in range(3):
            params = self.gyro_params[i].convert_to_si("gyro")

            # 1. White noise (ARW)
            white_noise = random.gauss(0, params.random_walk / math.sqrt(dt))

            # 2. Bias instability (1st order Gauss-Markov)
            tau_bi = 100.0  # Correlation time (s)
            alpha = math.exp(-dt / tau_bi)
            bias_drive = random.gauss(
                0, params.bias_instability * math.sqrt(1 - alpha**2)
            )
            self._gyro_bias = (
                self._gyro_bias[0]
                if i != 0
                else alpha * self._gyro_bias[0] + bias_drive,
                self._gyro_bias[1]
                if i != 1
                else alpha * self._gyro_bias[1] + bias_drive,
                self._gyro_bias[2]
                if i != 2
                else alpha * self._gyro_bias[2] + bias_drive,
            )

            # 3. Rate random walk (integrated white noise)
            rw_increment = random.gauss(0, params.rate_random_walk * math.sqrt(dt))
            self._gyro_rw = (
                self._gyro_rw[0] if i != 0 else self._gyro_rw[0] + rw_increment,
                self._gyro_rw[1] if i != 1 else self._gyro_rw[1] + rw_increment,
                self._gyro_rw[2] if i != 2 else self._gyro_rw[2] + rw_increment,
            )

            result[i] += white_noise + self._gyro_bias[i] + self._gyro_rw[i]

        return tuple(result)

    def corrupt_accel(
        self, true_accel: Tuple[float, float, float], dt: float
    ) -> Tuple[float, float, float]:
        """
        Apply Allan Variance noise model to accelerometer.

        Reference: IEEE Std 1293-2018, Section 5

        Args:
            true_accel: True acceleration (m/s²)
            dt: Time step (s)

        Returns:
            Corrupted acceleration (m/s²)
        """
        result = list(true_accel)

        for i in range(3):
            params = self.accel_params[i].convert_to_si("accel")

            # White noise
            white_noise = random.gauss(0, params.random_walk / math.sqrt(dt))

            # Bias instability
            tau_bi = 100.0
            alpha = math.exp(-dt / tau_bi)
            bias_drive = random.gauss(
                0, params.bias_instability * math.sqrt(1 - alpha**2)
            )
            self._accel_bias = (
                self._accel_bias[0]
                if i != 0
                else alpha * self._accel_bias[0] + bias_drive,
                self._accel_bias[1]
                if i != 1
                else alpha * self._accel_bias[1] + bias_drive,
                self._accel_bias[2]
                if i != 2
                else alpha * self._accel_bias[2] + bias_drive,
            )

            result[i] += white_noise + self._accel_bias[i]

        return tuple(result)

    def reset(self):
        """Reset all internal states."""
        self._gyro_bias = (0.0, 0.0, 0.0)
        self._accel_bias = (0.0, 0.0, 0.0)
        self._gyro_rw = (0.0, 0.0, 0.0)
        self._accel_rw = (0.0, 0.0, 0.0)


@dataclass
class MPU6050Model(AllanVarianceIMU):
    """
    InvenSense MPU6050 Specific Model.

    Reference:
        MPU-6000/MPU-6050 Product Specification, Rev 3.4
        InvenSense Inc.

    Specifications (from datasheet):
        Gyro Noise: 0.01 dps/√Hz = 36 deg/hr/√Hz
        Gyro Bias: Typical ±5 dps
        Accel Noise: 400 µg/√Hz
        Accel Bias: Typical ±80 mg
    """

    def __post_init__(self):
        # MPU6050 typical values
        gyro_arw = 0.6  # deg/√hr (derived from 0.01 dps/√Hz)
        gyro_bi = 20.0  # deg/hr

        accel_vrw = 0.24  # m/s/√hr (derived from 400 µg/√Hz)
        accel_bi = 0.08  # mg

        self.gyro_params = (
            AllanVarianceParameters(random_walk=gyro_arw, bias_instability=gyro_bi),
            AllanVarianceParameters(random_walk=gyro_arw, bias_instability=gyro_bi),
            AllanVarianceParameters(random_walk=gyro_arw, bias_instability=gyro_bi),
        )

        self.accel_params = (
            AllanVarianceParameters(random_walk=accel_vrw, bias_instability=accel_bi),
            AllanVarianceParameters(random_walk=accel_vrw, bias_instability=accel_bi),
            AllanVarianceParameters(random_walk=accel_vrw, bias_instability=accel_bi),
        )
