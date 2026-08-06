"""
Tests for Aerodynamics Models.

Validates BEMT, Ground Effect, and VRS against theoretical predictions.
"""

import math

import pytest


class TestBEMT:
    """Test suite for Blade Element Momentum Theory."""

    def test_thrust_positive_at_rpm(self, bemt):
        """Test that thrust is positive at operating RPM."""
        thrust = bemt.calculate_thrust(rpm=10000, rho=1.225)
        assert thrust > 0

    def test_thrust_zero_at_zero_rpm(self, bemt):
        """Test that thrust is zero when RPM is zero."""
        thrust = bemt.calculate_thrust(rpm=0, rho=1.225)
        assert thrust == 0

    def test_thrust_increases_with_rpm(self, bemt):
        """Test that thrust increases with RPM squared."""
        T1 = bemt.calculate_thrust(rpm=5000, rho=1.225)
        T2 = bemt.calculate_thrust(rpm=10000, rho=1.225)

        # T ∝ RPM², so T2 should be ~4× T1
        ratio = T2 / T1
        assert 3.5 < ratio < 4.5

    def test_thrust_proportional_to_density(self, bemt):
        """Test that thrust is proportional to air density."""
        T_sea = bemt.calculate_thrust(rpm=10000, rho=1.225)
        T_alt = bemt.calculate_thrust(rpm=10000, rho=0.9)

        ratio = T_alt / T_sea
        assert abs(ratio - 0.9 / 1.225) < 0.1

    def test_power_positive(self, bemt):
        """Test that power is positive at operating conditions."""
        power = bemt.calculate_power(rpm=10000, rho=1.225)
        assert power > 0

    def test_power_has_induced_and_profile(self, bemt):
        """Test that power includes both induced and profile."""
        power = bemt.calculate_power(rpm=10000, rho=1.225)
        thrust = bemt.calculate_thrust(rpm=10000, rho=1.225)

        # Minimum possible power is induced power
        A = bemt.blade.disk_area_m2
        v_i = math.sqrt(thrust / (2 * 1.225 * A))
        P_induced = thrust * v_i

        # Total power should exceed induced (profile adds to it)
        assert power > P_induced

    def test_figure_of_merit_range(self, bemt):
        """Test that Figure of Merit is in valid range."""
        fm = bemt.calculate_figure_of_merit(rpm=10000, rho=1.225)

        # FM should be between 0 and 1
        assert 0 < fm <= 1

        # Good rotor should have FM > 0.5
        assert fm > 0.5

    def test_ct_calculation(self, bemt):
        """Test thrust coefficient calculation."""
        ct = bemt.calculate_ct(rpm=10000, rho=1.225)

        # CT should be small positive number for hover
        assert 0 < ct < 0.1


class TestGroundEffect:
    """Test suite for Ground Effect model."""

    def test_ge_unity_at_high_altitude(self, ground_effect):
        """Test that GE factor is 1.0 when far from ground."""
        ratio = ground_effect.get_thrust_ratio(altitude_m=10.0)
        assert abs(ratio - 1.0) < 0.01

    def test_ge_increases_near_ground(self, ground_effect):
        """Test that GE increases thrust near ground."""
        ratio_close = ground_effect.get_thrust_ratio(altitude_m=0.1)
        ratio_far = ground_effect.get_thrust_ratio(altitude_m=1.0)

        assert ratio_close > ratio_far
        assert ratio_close > 1.0

    def test_ge_maximum_at_surface(self, ground_effect):
        """Test maximum GE at very low altitude."""
        ratio = ground_effect.get_thrust_ratio(altitude_m=0.05)

        # Should be enhanced (or at least not less than 1)
        assert ratio >= 1.0

        # Should increase as altitude decreases
        ratio_higher = ground_effect.get_thrust_ratio(altitude_m=0.5)
        assert ratio >= ratio_higher

    def test_power_ratio_inverse(self, ground_effect):
        """Test that power ratio is inverse of thrust ratio."""
        thrust_ratio = ground_effect.get_thrust_ratio(altitude_m=0.1)
        power_ratio = ground_effect.get_power_ratio(altitude_m=0.1)

        # For constant thrust, power_ratio ≈ 1/sqrt(thrust_ratio)
        expected = 1.0 / math.sqrt(thrust_ratio)
        assert abs(power_ratio - expected) < 0.01


class TestVRS:
    """Test suite for Vortex Ring State model."""

    def test_clear_in_hover(self, vrs):
        """Test no VRS in stable hover."""
        from warm_logic.kernel.drone.reality.aerodynamics import VRSState

        state = vrs.check_state(
            v_descent_m_s=0, v_forward_m_s=5.0, thrust_n=10.0, rho=1.225
        )
        assert state == VRSState.CLEAR

    def test_vrs_detection_exists(self, vrs):
        """Test VRS check_state returns valid VRSState."""
        from warm_logic.kernel.drone.reality.aerodynamics import VRSState

        state = vrs.check_state(
            v_descent_m_s=3.0, v_forward_m_s=0.5, thrust_n=10.0, rho=1.225
        )
        # Should return a valid VRSState enum
        assert isinstance(state, VRSState)

    def test_clear_with_forward_speed(self, vrs):
        """Test VRS avoidance with forward speed."""
        from warm_logic.kernel.drone.reality.aerodynamics import VRSState

        state = vrs.check_state(
            v_descent_m_s=3.0,
            v_forward_m_s=10.0,  # High forward speed
            thrust_n=10.0,
            rho=1.225,
        )
        assert state == VRSState.CLEAR

    def test_thrust_reduction_returns_value(self, vrs):
        """Test thrust reduction returns valid factor."""
        factor = vrs.get_thrust_reduction(
            v_descent_m_s=4.0, v_forward_m_s=0.1, thrust_n=10.0, rho=1.225
        )
        # Should return a valid factor between 0 and 1
        assert 0 <= factor <= 1

    def test_vibration_returns_value(self, vrs):
        """Test vibration level returns valid value."""
        vib = vrs.get_vibration_level(0, 5, 10, 1.225)
        # Should return positive value
        assert vib >= 0
