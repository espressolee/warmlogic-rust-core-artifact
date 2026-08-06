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
Reality Engine - Unified Physics Simulation.

Integrates all paper-based physics models into a single simulation engine.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np

from .aerodynamics import BladeElementMomentumTheory, GroundEffect, VortexRingState
from .atmosphere import DrydenTurbulence, USStandardAtmosphere1976
from .computing import FloatingPointPrecision, TimerOverflow
from .environment import PlanetaryPhysics
from .faults import MechanicalFatigue, SingleEventUpset
from .mavlink_bridge import MAVLinkBridge
from .propulsion import BLDCMotor, ESCModel, TheveninBattery
from .sensors import AllanVarianceIMU, GPSErrorModel, MagnetometerModel, VisionSimulator


@dataclass
class SimulationState:
    """Complete simulation state."""

    # Position (geodetic)
    latitude_deg: float = 0.0
    longitude_deg: float = 0.078
    altitude_m: float = 100.0

    # Velocity (NED frame)
    velocity_n_m_s: float = 0.0
    velocity_e_m_s: float = 0.0
    velocity_d_m_s: float = 0.0

    # Attitude (Euler angles)
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0

    # Angular Velocity (Body frame, rad/s)
    p_rad_s: float = 0.0
    q_rad_s: float = 0.0
    r_rad_s: float = 0.0

    # Motor state (4 motors)
    motor_rpms: Tuple[float, float, float, float] = (10000, 10000, 10000, 10000)
    throttle: Tuple[float, float, float, float] = (0.5, 0.5, 0.5, 0.5)

    # Time
    time_s: float = 0.0

    # Metrics
    jerk_m_s3: float = 0.0

    # [Phase 140] Perception
    pos_n_m: float = 0.0
    pos_e_m: float = 0.0
    pos_d_m: float = 0.0
    visual_frame: Optional[np.ndarray] = None


@dataclass
class RealityEngine:
    """
    Unified Reality Physics Engine.

    Integrates all paper-based models for comprehensive simulation.

    Reference Sources:
        - Atmosphere: NOAA-S/T 76-1562, MIL-F-8785C
        - Aerodynamics: Leishman (2006), Johnson (1980)
        - Sensors: IEEE Std 952-1997, Kaplan (2017)
        - Propulsion: Zhang et al. (2017), Krishnan (2010)
        - Environment: WGS84, IGRF-13
    """

    # Optional RNG for deterministic behavior
    rng: Optional[Any] = None

    # Physical models
    atmosphere: USStandardAtmosphere1976 = field(
        default_factory=USStandardAtmosphere1976
    )
    wind: Optional[DrydenTurbulence] = None
    bemt: BladeElementMomentumTheory = field(default_factory=BladeElementMomentumTheory)
    ground_effect: GroundEffect = field(default_factory=GroundEffect)
    vrs: VortexRingState = field(default_factory=VortexRingState)
    imu: Optional[AllanVarianceIMU] = None
    gps: GPSErrorModel = field(default_factory=GPSErrorModel)
    magnetometer: MagnetometerModel = field(default_factory=MagnetometerModel)
    battery: TheveninBattery = field(default_factory=TheveninBattery)
    motors: Tuple[BLDCMotor, ...] = field(
        default_factory=lambda: tuple(BLDCMotor() for _ in range(4))
    )
    escs: Tuple[ESCModel, ...] = field(
        default_factory=lambda: tuple(ESCModel() for _ in range(4))
    )
    planetary: PlanetaryPhysics = field(default_factory=PlanetaryPhysics)
    fatigue: MechanicalFatigue = field(default_factory=MechanicalFatigue)
    seu: SingleEventUpset = field(default_factory=SingleEventUpset)
    fp_precision: FloatingPointPrecision = field(default_factory=FloatingPointPrecision)
    timer: TimerOverflow = field(default_factory=TimerOverflow)
    vision: VisionSimulator = field(default_factory=VisionSimulator)
    mavlink_bridge: Optional[MAVLinkBridge] = None

    def __post_init__(self) -> None:
        """Initialize RNG-dependent models."""
        if self.wind is None:
            self.wind = DrydenTurbulence(rng=self.rng)
        if self.imu is None:
            self.imu = AllanVarianceIMU(rng=self.rng)

    def simulate_step(
        self, state: SimulationState, dt: float
    ) -> Dict[str, Any]:  # noqa: C901  # type: ignore[override]
        """
        Execute one simulation step with all physics.

        Args:
            state: Current simulation state
            dt: Time step (seconds)

        Returns:
            Dictionary with all computed values and corrupted sensor data
        """
        result: Dict[str, Any] = {}

        # 1. Atmospheric conditions
        atm_state = self.atmosphere.get_state(state.altitude_m)
        result["atmosphere"] = {
            "temperature_k": atm_state.temperature_k,
            "pressure_pa": atm_state.pressure_pa,
            "density_kg_m3": atm_state.density_kg_m3,
        }

        # 2. Wind turbulence
        if self.wind is not None:
            wind_uvw = self.wind.sample(dt)
        else:
            wind_uvw = (0.0, 0.0, 0.0)
        result["wind"] = wind_uvw

        # 3. Gravity and Coriolis
        g_local = self.planetary.gravity_at_location(
            state.latitude_deg, state.altitude_m
        )
        vel_ned = (state.velocity_n_m_s, state.velocity_e_m_s, state.velocity_d_m_s)
        coriolis = self.planetary.coriolis_acceleration(state.latitude_deg, vel_ned)
        result["gravity"] = g_local
        result["coriolis"] = coriolis

        # 4. Motor and propulsion
        v_bus = self.battery.get_terminal_voltage(20.0, dt)
        total_thrust = 0.0
        total_power = 0.0
        for i, (motor, esc) in enumerate(zip(self.motors, self.escs)):
            # We call get_output_voltage for ESC state simulation even if unused here
            _ = esc.get_output_voltage(state.throttle[i], v_bus)
            thrust, power, _ = self.bemt.calculate_performance(
                rpm=state.motor_rpms[i], rho=atm_state.density_kg_m3
            )
            total_thrust += thrust
            total_power += power

        result["propulsion"] = {
            "bus_voltage": v_bus,
            "total_thrust_n": total_thrust,
            "total_power_w": total_power,
        }

        # 5. Ground effect
        ge_factor = self.ground_effect.get_thrust_ratio(state.altitude_m)
        result["ground_effect"] = ge_factor

        # 6. VRS check
        vrs_state = self.vrs.check_state(
            v_descent_m_s=state.velocity_d_m_s,
            v_forward_m_s=abs(state.velocity_n_m_s),
            thrust_n=total_thrust,
            rho=atm_state.density_kg_m3,
        )
        result["vrs"] = vrs_state.value

        # 7. Vision Simulation (Eagle Eye)
        state.visual_frame = self.vision.render_depth(
            pos_ned=np.array([state.pos_n_m, state.pos_e_m, state.pos_d_m]),
            attitude_euler_deg=np.array(
                [state.roll_deg, state.pitch_deg, state.yaw_deg]
            ),
        )
        result["vision"] = {
            "frame_shape": state.visual_frame.shape,
            "min_depth": float(np.min(state.visual_frame)),
        }

        # 8. Sensor corruption
        # True accel = thrust/m + gravity_body + disturbance
        # For Phase 126, we use specific force (accel - gravity) in body frame.
        # This matches what an IMU actually measures.
        # total_thrust is in Newtons. Specific force is accel-g = Thrust / mass.
        # In body frame, thrust is in -Z direction.
        true_accel = (0.0, 0.0, -result["propulsion"]["total_thrust_n"] / 2.5)
        true_gyro = (state.p_rad_s, state.q_rad_s, state.r_rad_s)

        if self.imu is not None:
            imu_accel = self.imu.corrupt_accel(true_accel, dt)
            imu_gyro = self.imu.corrupt_gyro(true_gyro, dt)
        else:
            imu_accel = true_accel
            imu_gyro = true_gyro
        result["sensors"] = {
            "imu_accel": imu_accel,
            "imu_gyro": imu_gyro,
            "gps_pos": self.gps.corrupt_position(
                state.latitude_deg, state.longitude_deg, state.altitude_m
            ),
            "visual_frame": state.visual_frame,
        }

        # 9. Faults
        self.fatigue.accumulate()
        result["faults"] = {
            "fatigue_cycles": self.fatigue.total_cycles,
            "seu_occurred": self.seu.check_bit_flip(dt=dt),
        }

        # 10. Optional: HITL/SITL Streaming
        if getattr(self, "mavlink_bridge", None):
            self._stream_hil_telemetry(state, result)

        # 11. Update state time
        state.time_s += dt
        self.timer.tick(int(dt * 1_000_000))  # microseconds

        return result

    def _stream_hil_telemetry(
        self, state: SimulationState, result: Dict[str, Any]
    ) -> None:
        """Stream MAVLink HIL messages based on physics results."""
        bridge = self.mavlink_bridge
        if bridge is None:
            return
        time_usec = int(state.time_s * 1e6)

        # 1. HIL_SENSOR
        # Result sensors: imu_accel, imu_gyro
        # Note: pressure and mag need models in RealityEngine (placeholders for now if missing)
        bridge.send_hil_sensor(
            time_usec=time_usec,
            accel=result["sensors"]["imu_accel"],
            gyro=result["sensors"]["imu_gyro"],
            mag=(0.0, 0.0, 0.0),  # Placeholder
            abs_pressure=result["atmosphere"]["pressure_pa"],
            diff_pressure=0.0,
            pressure_alt=state.altitude_m,
            temperature=result["atmosphere"]["temperature_k"] - 273.15,  # K to C
        )

        # 2. HIL_GPS
        gps_pos = result["sensors"]["gps_pos"]
        bridge.send_hil_gps(
            time_usec=time_usec,
            fix_type=3,  # 3D Fix
            lat=int(gps_pos[0] * 1e7),
            lon=int(gps_pos[1] * 1e7),
            alt=int(gps_pos[2] * 1000),
            eph=100,
            epv=100,
            vel=0,
            vn=0,
            ve=0,
            vd=0,
            cog=0,
            satellites_visible=12,
        )

    def reset(self) -> None:
        """Reset all internal states."""
        if self.imu is not None:
            self.imu.reset()
        if self.wind is not None:
            self.wind.reset()
        self.battery.soc = 1.0
        self.fatigue.total_cycles = 0
        self.timer.current_value = 0
        self.timer.overflow_count = 0
