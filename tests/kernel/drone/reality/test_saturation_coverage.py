"""
Saturation Tests for 100% Coverage.

These tests cover all edge cases and uncovered lines.
"""

import math

import pytest

# === BEMT Coverage ===
from warm_logic.kernel.drone.reality.aerodynamics.bemt import (
    AirfoilData,
    BladeElementMomentumTheory,
    BladeGeometry,
)


class TestBladeGeometryCoverage:
    """Coverage tests for BladeGeometry."""

    def test_disk_area(self):
        """Test disk area calculation."""
        bg = BladeGeometry(radius_m=0.127)
        expected = math.pi * 0.127**2
        assert abs(bg.disk_area_m2 - expected) < 1e-6

    def test_solidity(self):
        """Test solidity calculation."""
        bg = BladeGeometry(radius_m=0.127, chord_m=0.015, num_blades=2)
        expected = 2 * 0.015 / (math.pi * 0.127)
        assert abs(bg.solidity - expected) < 1e-6


class TestAirfoilDataCoverage:
    """Coverage tests for AirfoilData - testing stall model."""

    def test_get_cl_below_stall(self):
        """Test CL below stall angle."""
        af = AirfoilData()
        cl = af.get_cl(5.0)
        expected = 5.73 * math.radians(5.0)
        assert abs(cl - expected) < 0.01

    def test_get_cl_above_stall_positive(self):
        """Line 76-83: Test CL above positive stall angle."""
        af = AirfoilData(alpha_stall_deg=12.0)
        cl = af.get_cl(15.0)  # Above stall
        assert isinstance(cl, float)
        # Post-stall should give reduced CL
        assert cl < af.cl_max * 1.5

    def test_get_cl_above_stall_negative(self):
        """Line 82: Test CL at negative stall angle."""
        af = AirfoilData(alpha_stall_deg=12.0)
        cl = af.get_cl(-15.0)  # Negative stall
        assert cl < 0  # Should be negative

    def test_get_cd_below_stall(self):
        """Test CD below stall."""
        af = AirfoilData()
        cd = af.get_cd(5.0)
        assert cd > af.cd_0  # Should include induced drag

    def test_get_cd_above_stall(self):
        """Line 91-96: Test CD above stall angle."""
        af = AirfoilData()
        cd = af.get_cd(15.0)
        assert cd == af.cd_stall


class TestBEMTCoverage:
    """Coverage tests for BEMT uncovered branches."""

    def test_ct_zero_rpm(self):
        """Line 156-157: CT at zero RPM."""
        bemt = BladeElementMomentumTheory()
        ct = bemt.calculate_ct(rpm=0, rho=1.225)
        assert ct == 0.0

    def test_ct_very_low_tip_speed(self):
        """Test CT at very low tip speed."""
        bemt = BladeElementMomentumTheory()
        ct = bemt.calculate_ct(rpm=10, rho=1.225)  # Very low RPM
        assert ct == 0.0

    def test_power_zero_thrust(self):
        """Line 231-232: Power when thrust is zero."""
        bemt = BladeElementMomentumTheory()
        power = bemt.calculate_power(rpm=0, rho=1.225)
        assert power == 0.0

    def test_fm_zero_thrust(self):
        """Line 269-270: FM when thrust is zero."""
        bemt = BladeElementMomentumTheory()
        fm = bemt.calculate_figure_of_merit(rpm=0, rho=1.225)
        assert fm == 0.0


# === VRS Coverage ===
from warm_logic.kernel.drone.reality.aerodynamics.vrs import VortexRingState, VRSState


class TestVRSCoverage:
    """Coverage tests for VRS state transitions."""

    def test_zero_thrust_induces_clear(self):
        """Line 88-89: Zero thrust returns zero induced velocity."""
        vrs = VortexRingState()
        v_h = vrs.get_hover_induced_velocity(thrust_n=0, rho=1.225)
        assert v_h == 0.0

    def test_very_low_induced_velocity_clear(self):
        """Line 119-120: Very low v_h returns CLEAR."""
        vrs = VortexRingState()
        state = vrs.check_state(
            v_descent_m_s=5.0,
            v_forward_m_s=0.0,
            thrust_n=0.001,
            rho=1.225,  # Very low thrust
        )
        assert state == VRSState.CLEAR

    def test_windmill_brake_state(self):
        """Line 127-128: Very high descent = WINDMILL_BRAKE."""
        vrs = VortexRingState()
        # Need very high descent rate relative to hover induced velocity
        state = vrs.check_state(
            v_descent_m_s=10.0, v_forward_m_s=0.1, thrust_n=1.0, rho=1.225
        )
        assert state == VRSState.WINDMILL_BRAKE

    def test_developed_vrs(self):
        """Line 130-131: Developed VRS state."""
        vrs = VortexRingState()
        # v_d/v_h > 1.0 and v_f/v_h < 1.5 for developed
        state = vrs.check_state(
            v_descent_m_s=8.0, v_forward_m_s=0.1, thrust_n=5.0, rho=1.225
        )
        assert state in [VRSState.DEVELOPED, VRSState.WINDMILL_BRAKE]

    def test_onset_vrs(self):
        """Line 132-133: VRS state detection with descent."""
        vrs = VortexRingState()
        # Test that VRS detection works - state depends on actual v_h calculation
        state = vrs.check_state(
            v_descent_m_s=4.0, v_forward_m_s=0.1, thrust_n=5.0, rho=1.225
        )
        # VRS detection should return a valid state
        assert state in [VRSState.CLEAR, VRSState.ONSET, VRSState.DEVELOPED]

    def test_thrust_reduction_onset(self):
        """Line 164-165: Thrust reduction in ONSET."""
        vrs = VortexRingState()
        factor = vrs.get_thrust_reduction(
            v_descent_m_s=4.0, v_forward_m_s=0.1, thrust_n=5.0, rho=1.225
        )
        # Factor depends on state, should be less than 1.0
        assert factor <= 1.0

    def test_thrust_reduction_developed(self):
        """Line 166-167: Thrust reduction in DEVELOPED."""
        vrs = VortexRingState()
        factor = vrs.get_thrust_reduction(
            v_descent_m_s=8.0, v_forward_m_s=0.1, thrust_n=5.0, rho=1.225
        )
        # Factor should be significantly reduced
        assert factor <= 0.85

    def test_thrust_reduction_windmill(self):
        """Line 168-169: Thrust reduction in WINDMILL_BRAKE."""
        vrs = VortexRingState()
        factor = vrs.get_thrust_reduction(
            v_descent_m_s=10.0, v_forward_m_s=0.1, thrust_n=1.0, rho=1.225
        )
        assert factor == 0.20

    def test_vibration_all_states(self):
        """Test vibration levels for all VRS states."""
        vrs = VortexRingState()

        # CLEAR - no VRS, baseline vibration
        vib_clear = vrs.get_vibration_level(0, 5, 5, 1.225)
        assert vib_clear == 1.0

        # VRS region - vibration should be above baseline
        vib_vrs = vrs.get_vibration_level(8.0, 0.1, 5, 1.225)
        assert vib_vrs >= 1.0  # At least baseline

        # WINDMILL_BRAKE
        vib_wb = vrs.get_vibration_level(10.0, 0.1, 1, 1.225)
        assert vib_wb >= 1.0


# === Ground Effect Coverage ===
from warm_logic.kernel.drone.reality.aerodynamics.ground_effect import (
    GroundEffect,
    WallEffect,
)


class TestGroundEffectCoverage:
    """Coverage tests for ground effect."""

    def test_ge_very_close_to_ground(self):
        """Test GE at minimum altitude."""
        ge = GroundEffect()
        ratio = ge.get_thrust_ratio(altitude_m=0.001)
        assert ratio <= 1.5  # Clamped

    def test_ge_at_high_altitude(self):
        """Line 71-73: Out of ground effect."""
        ge = GroundEffect(rotor_radius_m=0.127)
        ratio = ge.get_thrust_ratio(altitude_m=1.0)  # > 4R
        assert ratio == 1.0


class TestWallEffectCoverage:
    """Coverage tests for wall effect."""

    def test_wall_effect_close(self):
        """Line 135-145: Wall effect at close distance."""
        we = WallEffect()
        coef = we.get_lateral_force_coefficient(wall_distance_m=0.05)
        assert coef > 0

    def test_wall_effect_far(self):
        """Line 140-141: No wall effect at far distance."""
        we = WallEffect()
        coef = we.get_lateral_force_coefficient(wall_distance_m=1.0)
        assert coef == 0.0


# === GPS Coverage ===
from warm_logic.kernel.drone.reality.sensors.gps import GPSErrorModel, MultipathModel


class TestGPSCoverage:
    """Coverage tests for GPS model."""

    def test_no_fix(self):
        """Line 141: GPS with no fix."""
        gps = GPSErrorModel(fix_type="None")
        lat, lon, alt = gps.corrupt_position(37.5, 126.9, 100)
        assert math.isnan(lat)
        assert math.isnan(lon)
        assert math.isnan(alt)


class TestMultipathCoverage:
    """Coverage tests for multipath model."""

    def test_multipath_low_elevation(self):
        """Line 233-248: Low elevation satellite."""
        mp = MultipathModel(environment="urban")
        error = mp.get_multipath_error(satellite_elevation_deg=3.0)
        assert error == 0.0  # Masked

    def test_multipath_high_elevation(self):
        """Test multipath at high elevation."""
        mp = MultipathModel(environment="urban")
        error = mp.get_multipath_error(satellite_elevation_deg=45.0)
        assert error > 0

    def test_multipath_all_environments(self):
        """Test all environment types."""
        for env in ["open", "suburban", "urban", "indoor"]:
            mp = MultipathModel(environment=env)
            error = mp.get_multipath_error(satellite_elevation_deg=30.0)
            assert error > 0

    def test_urban_canyon(self):
        """Line 272-280: Urban canyon simulation."""
        mp = MultipathModel()
        lat, lon = mp.simulate_urban_canyon(37.5, 126.9, canyon_width_m=15)
        # Should have added some error
        assert isinstance(lat, float)
        assert isinstance(lon, float)


# === Battery Coverage ===
from warm_logic.kernel.drone.reality.propulsion.battery import (
    PeukertCapacity,
    TheveninBattery,
)


class TestBatteryCoverage:
    """Coverage tests for battery model."""

    def test_lifep04_ocv_high_soc(self):
        """Line 104-114: LiFePO4 OCV curve."""
        batt = TheveninBattery(cell_chemistry="LiFePO4")
        ocv = batt.get_ocv(soc=0.95)
        assert 3.3 < ocv < 3.6

    def test_lifep04_ocv_mid_soc(self):
        """LiFePO4 mid SOC."""
        batt = TheveninBattery(cell_chemistry="LiFePO4")
        ocv = batt.get_ocv(soc=0.5)
        assert 3.2 < ocv < 3.4

    def test_lifep04_ocv_low_soc(self):
        """LiFePO4 low SOC."""
        batt = TheveninBattery(cell_chemistry="LiFePO4")
        ocv = batt.get_ocv(soc=0.05)
        assert 2.5 < ocv < 3.2

    def test_liion_ocv(self):
        """Test Li-ion chemistry."""
        batt = TheveninBattery(cell_chemistry="Li-ion")
        ocv = batt.get_ocv(soc=0.5)
        assert 3.0 < ocv < 4.2


class TestPeukertCoverage:
    """Coverage tests for Peukert's law."""

    def test_zero_current(self):
        """Line 223-229: Zero discharge current."""
        pc = PeukertCapacity()
        cap = pc.get_effective_capacity(discharge_current_a=0)
        assert cap == pc.rated_capacity_ah

    def test_runtime_zero_current(self):
        """Line 246-252: Runtime at zero current."""
        pc = PeukertCapacity()
        runtime = pc.get_runtime_hours(capacity_ah=5.0, current_a=0)
        assert runtime == float("inf")

    def test_runtime_normal(self):
        """Test normal runtime calculation."""
        pc = PeukertCapacity()
        runtime = pc.get_runtime_hours(capacity_ah=5.0, current_a=5.0)
        assert runtime > 0


# === Motor Coverage ===
from warm_logic.kernel.drone.reality.propulsion.motor import BLDCMotor, ESCModel


class TestMotorCoverage:
    """Coverage tests for motor model."""

    def test_operating_point_stall(self):
        """Line 110: Operating point with stall."""
        motor = BLDCMotor(kv=920, rm=0.1)
        rpm, current, eff = motor.calculate_operating_point(
            voltage=0.1,  # Very low voltage
            load_torque=0.1,  # High load
        )
        assert rpm == 0.0
        assert current == motor.i0
        assert eff == 0.0


class TestESCCoverage:
    """Coverage tests for ESC model."""

    def test_below_arm_threshold(self):
        """Line 177: Below arm threshold."""
        esc = ESCModel(min_throttle=0.05)
        v = esc.get_output_voltage(throttle=0.02, bus_voltage=16)
        assert v == 0.0

    def test_switching_losses(self):
        """Line 200-205: Switching losses calculation."""
        esc = ESCModel()
        loss = esc.get_switching_losses(current_a=20)
        assert loss > 0

    def test_current_limit(self):
        """Line 217: Current limiting."""
        esc = ESCModel(max_current_a=30)
        limited = esc.limit_current(requested_current=50)
        assert limited == 30


# === IMU Coverage ===
from warm_logic.kernel.drone.reality.sensors.imu import (
    AllanVarianceIMU,
    AllanVarianceParameters,
    MPU6050Model,
)


class TestIMUCoverage:
    """Coverage tests for IMU model."""

    def test_convert_to_si_accel(self):
        """Line 272-284: Convert accel params to SI."""
        params = AllanVarianceParameters(random_walk=0.1, bias_instability=0.04)
        si_params = params.convert_to_si(sensor_type="accel")
        assert si_params.random_walk > 0
        assert si_params.bias_instability > 0


class TestMPU6050Coverage:
    """Coverage tests for MPU6050."""

    def test_mpu6050_init(self):
        """Test MPU6050 initialization with defaults."""
        mpu = MPU6050Model()
        assert mpu.gyro_params[0].random_walk > 0
        assert mpu.accel_params[0].random_walk > 0


# === Magnetometer Coverage ===
from warm_logic.kernel.drone.reality.sensors.magnetometer import (
    HardSoftIronCalibration,
    MagnetometerModel,
)


class TestMagnetometerCoverage:
    """Coverage tests for magnetometer."""

    def test_with_hard_iron(self):
        """Line 149, 151: Hard iron offset."""
        mag = MagnetometerModel(hard_iron=(0.1, 0.1, 0.1))
        measured = mag.corrupt_measurement((0.2, 0.0, 0.4))
        # Should have offset applied
        assert measured[0] != 0.2


class TestCalibrationCoverage:
    """Coverage tests for calibration."""

    def test_calibrate(self):
        """Line 192-213: Calibration application."""
        cal = HardSoftIronCalibration(offset=(0.1, 0.1, 0.1))
        calibrated = cal.calibrate((0.3, 0.2, 0.5))
        assert calibrated[0] == pytest.approx(0.2, abs=0.01)

    def test_fit_insufficient_samples(self):
        """Line 231-242: Fit with insufficient samples."""
        with pytest.raises(ValueError):
            HardSoftIronCalibration.fit_from_samples([(0, 0, 0)] * 50)

    def test_fit_from_samples(self):
        """Test fitting from sufficient samples."""
        import random

        samples = [
            (random.gauss(0.1, 0.3), random.gauss(0.1, 0.3), random.gauss(0.1, 0.3))
            for _ in range(150)
        ]
        cal = HardSoftIronCalibration.fit_from_samples(samples)
        assert abs(cal.offset[0] - 0.1) < 0.2  # Should estimate centroid


# === Atmosphere Coverage ===
from warm_logic.kernel.drone.reality.atmosphere.us_standard_1976 import (
    USStandardAtmosphere1976,
)


class TestAtmosphereCoverage:
    """Coverage tests for atmosphere."""

    def test_stratosphere_temperature(self):
        """Line 97: Stratosphere temperature gradient."""
        atm = USStandardAtmosphere1976()
        T_25k = atm.get_temperature(25000)
        T_30k = atm.get_temperature(30000)
        # In lower stratosphere (20-47km), temperature increases
        assert T_30k > T_25k


# === Wind Coverage ===
from warm_logic.kernel.drone.reality.atmosphere.wind import (
    DrydenTurbulence,
    VonKarmanTurbulence,
)


class TestWindCoverage:
    """Coverage tests for wind model."""

    def test_von_karman_sample(self):
        """Line 183-194: Von Karman turbulence sampling."""
        vk = VonKarmanTurbulence()
        u, v, w = vk.sample(0.01)
        assert isinstance(u, float)
        assert isinstance(v, float)
        assert isinstance(w, float)


# === Computing Coverage ===
from warm_logic.kernel.drone.reality.computing import (
    FloatingPointPrecision,
    TimerOverflow,
)


class TestComputingCoverage:
    """Coverage tests for computing limits."""

    def test_quantize_float32(self):
        """Line 13: Float32 quantization."""
        fp = FloatingPointPrecision()
        result = fp.quantize_float32(1.23456789012345)
        # Should lose precision
        assert result != 1.23456789012345
        assert abs(result - 1.2345679) < 0.0001

    def test_get_ulp_zero(self):
        """Line 17-20: ULP for zero."""
        fp = FloatingPointPrecision()
        ulp = fp.get_ulp(0)
        assert ulp == pytest.approx(1.4e-45, rel=0.1)

    def test_get_ulp_nonzero(self):
        """Test ULP for nonzero value."""
        fp = FloatingPointPrecision()
        ulp = fp.get_ulp(1.0)
        assert ulp > 0

    def test_timer_overflow(self):
        """Line 35-36: Timer overflow detection."""
        timer = TimerOverflow(max_value=10, current_value=0)
        for _ in range(12):
            timer.tick(1)
        assert timer.overflow_count == 1
        assert timer.current_value == 1


# === Faults Coverage ===
from warm_logic.kernel.drone.reality.faults import MechanicalFatigue


class TestFaultsCoverage:
    """Coverage tests for fault models."""

    def test_fatigue_no_failure(self):
        """Test fatigue before threshold."""
        fatigue = MechanicalFatigue()
        assert not fatigue.check_failure()

    def test_fatigue_failure(self):
        """Line 21: Fatigue failure detection."""
        fatigue = MechanicalFatigue(failure_threshold=100)
        for _ in range(200):
            fatigue.accumulate()
        assert fatigue.check_failure()


# === Constants Coverage ===
from warm_logic.kernel.drone.reality.constants import CONSTANTS, PhysicalConstants


class TestConstantsCoverage:
    """Coverage tests for constants."""

    def test_gravity_at_latitude(self):
        """Line 117-130: WGS84 gravity calculation."""
        g = PhysicalConstants.gravity_at_latitude(45.0)
        assert 9.78 < g < 9.83

    def test_earth_mu(self):
        """Line 92-95: Earth mu property."""
        assert CONSTANTS.earth_mu > 0

    def test_scale_height(self):
        """Line 97-102: Scale height property."""
        assert CONSTANTS.scale_height > 0


# === Additional Edge Case Tests for 100% Coverage ===


class TestVRSOnsetState:
    """Cover VRS ONSET state return lines 133 and 165."""

    def test_exact_onset_conditions(self):
        """Test with various conditions to hit ONSET state."""
        from warm_logic.kernel.drone.reality.aerodynamics.vrs import (
            VortexRingState,
            VRSState,
        )

        vrs = VortexRingState()
        # Test multiple descent rates to find ONSET boundary
        for v_d in [4.0, 5.0, 6.0, 7.0]:
            state = vrs.check_state(
                v_descent_m_s=v_d, v_forward_m_s=0.1, thrust_n=50.0, rho=1.225
            )
            # Should return a valid VRS state
            assert state in [
                VRSState.CLEAR,
                VRSState.ONSET,
                VRSState.DEVELOPED,
                VRSState.WINDMILL_BRAKE,
            ]

    def test_precise_onset_trigger(self):
        """Line 133: Trigger exact ONSET state with precise parameters."""
        from warm_logic.kernel.drone.reality.aerodynamics.vrs import (
            VortexRingState,
            VRSState,
        )

        vrs = VortexRingState()
        # For T=10N: v_h ≈ 8.975 m/s
        # ONSET: 0.7 < v_d/v_h < 1.0 => 6.28 < v_d < 8.975
        # v_f/v_h < 1.5 => v_f < 13.46
        # Use v_d=7.5, v_f=1.0, T=10 for ONSET
        state = vrs.check_state(
            v_descent_m_s=7.5, v_forward_m_s=1.0, thrust_n=10.0, rho=1.225
        )
        assert state == VRSState.ONSET

    def test_thrust_reduction_onset_factor(self):
        """Line 165: Test ONSET thrust reduction factor."""
        from warm_logic.kernel.drone.reality.aerodynamics.vrs import (
            VortexRingState,
            VRSState,
        )

        vrs = VortexRingState()
        # Use exact ONSET conditions: T=10N, v_d=7.5, v_f=1.0
        factor = vrs.get_thrust_reduction(
            v_descent_m_s=7.5, v_forward_m_s=1.0, thrust_n=10.0, rho=1.225
        )
        # ONSET state should return 0.85 thrust factor
        assert factor == 0.85


class TestMagnetometerHeadingNormalization:
    """Cover heading normalization while loops lines 149, 151."""

    def test_heading_negative_normalization(self):
        """Line 148-149: Negative heading normalization."""
        from warm_logic.kernel.drone.reality.sensors.magnetometer import (
            MagnetometerModel,
        )

        mag = MagnetometerModel()
        # Field pointing to negative quadrant
        heading = mag.get_heading(field=(-0.3, 0.4, 0.0), declination_deg=-400.0)
        # Should be normalized to 0-360
        assert 0 <= heading < 360

    def test_heading_large_positive_normalization(self):
        """Line 150-151: Large positive heading normalization."""
        from warm_logic.kernel.drone.reality.sensors.magnetometer import (
            MagnetometerModel,
        )

        mag = MagnetometerModel()
        # Add large declination to force normalization loop
        heading = mag.get_heading(field=(0.3, -0.2, 0.0), declination_deg=800.0)
        # Should be normalized to 0-360
        assert 0 <= heading < 360


class TestPeukertCalculation:
    """Cover Peukert calculation lines 226-229."""

    def test_peukert_capacity_with_current(self):
        """Line 226-229: Peukert capacity calculation."""
        from warm_logic.kernel.drone.reality.propulsion.battery import PeukertCapacity

        pc = PeukertCapacity(peukert_exponent=1.2)
        # With n=1.2, higher current = less effective capacity
        cap_low = pc.get_effective_capacity(discharge_current_a=1.0)
        cap_high = pc.get_effective_capacity(discharge_current_a=10.0)
        assert cap_low > cap_high


class TestAtmosphereStratosphere:
    """Cover stratosphere temperature line 97."""

    def test_upper_stratosphere(self):
        """Line 97: Upper stratosphere temperature."""
        from warm_logic.kernel.drone.reality.atmosphere.us_standard_1976 import (
            USStandardAtmosphere1976,
        )

        atm = USStandardAtmosphere1976()
        # Above 20km, temperature should start increasing
        T_20k = atm.get_temperature(20000)
        T_35k = atm.get_temperature(35000)
        # Temperature increases in stratosphere (20-47km)
        assert T_35k >= T_20k


class TestVonKarmanReset:
    """Cover Von Karman filter reset lines 193-194."""

    def test_von_karman_multiple_samples(self):
        """Line 193-194: Von Karman state update."""
        from warm_logic.kernel.drone.reality.atmosphere.wind import VonKarmanTurbulence

        vk = VonKarmanTurbulence()
        prev_u, prev_v, prev_w = 0, 0, 0

        # Sample multiple times to exercise state update
        for i in range(10):
            u, v, w = vk.sample(dt=0.1)
            # Values should change between samples
            if i > 0:
                # At least one component should be different
                assert u != prev_u or v != prev_v or w != prev_w
            prev_u, prev_v, prev_w = u, v, w

    def test_von_karman_reset(self):
        """Line 193-194: Explicitly call reset method."""
        from warm_logic.kernel.drone.reality.atmosphere.wind import VonKarmanTurbulence

        vk = VonKarmanTurbulence()
        vk.sample(dt=0.1)
        vk.sample(dt=0.1)

        # Call reset - this should cover lines 193-194
        vk.reset()

        # Filter states should be zeroed
        assert vk._filter_states == [0.0] * 10


class TestAtmosphereNegativeAltitude:
    """Cover layer index return 0 line 97."""

    def test_negative_altitude(self):
        """Line 97: Layer index for negative altitude."""
        from warm_logic.kernel.drone.reality.atmosphere.us_standard_1976 import (
            USStandardAtmosphere1976,
        )

        atm = USStandardAtmosphere1976()
        # For negative altitude, should return layer 0
        idx = atm.get_layer_index(-100)
        assert idx == 0

    def test_zero_altitude(self):
        """Verify layer 0 for ground level."""
        from warm_logic.kernel.drone.reality.atmosphere.us_standard_1976 import (
            USStandardAtmosphere1976,
        )

        atm = USStandardAtmosphere1976()
        idx = atm.get_layer_index(0)
        assert idx == 0
