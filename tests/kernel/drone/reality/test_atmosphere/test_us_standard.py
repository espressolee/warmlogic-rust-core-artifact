"""
Tests for US Standard Atmosphere 1976.

Validates against NOAA-S/T 76-1562 Table 1 reference data.
"""

import math

import pytest

from warm_logic.kernel.drone.reality.atmosphere import DrydenTurbulence


class TestUSStandardAtmosphere:
    """Test suite for US Standard Atmosphere 1976."""

    # Reference data from NOAA-S/T 76-1562 Table 1
    REFERENCE_DATA = [
        # (altitude_m, temp_k, pressure_pa, density_kg_m3)
        (0, 288.15, 101325.0, 1.2250),
        (1000, 281.65, 89874.6, 1.1117),
        (5000, 255.65, 54019.9, 0.7361),
        (10000, 223.15, 26436.3, 0.4127),
        (11000, 216.65, 22632.1, 0.3639),
        (15000, 216.65, 12044.6, 0.1937),
        (20000, 216.65, 5474.89, 0.0880),
    ]

    def test_sea_level_temperature(self, atmosphere):
        """Test sea level temperature (288.15 K = 15°C)."""
        T = atmosphere.get_temperature(0)
        assert abs(T - 288.15) < 0.01

    def test_sea_level_pressure(self, atmosphere):
        """Test sea level pressure (101325 Pa)."""
        P = atmosphere.get_pressure(0)
        assert abs(P - 101325.0) < 1.0

    def test_sea_level_density(self, atmosphere):
        """Test sea level density (1.225 kg/m³)."""
        rho = atmosphere.get_density(0)
        assert abs(rho - 1.225) < 0.001

    @pytest.mark.parametrize("alt,expected_T,expected_P,expected_rho", REFERENCE_DATA)
    def test_reference_data(
        self, atmosphere, alt, expected_T, expected_P, expected_rho
    ):
        """Test against NOAA reference data (Table 1)."""
        T = atmosphere.get_temperature(alt)
        P = atmosphere.get_pressure(alt)
        rho = atmosphere.get_density(alt)

        # Temperature tolerance: 0.5 K
        assert abs(T - expected_T) < 0.5, f"Temp at {alt}m: {T} vs {expected_T}"

        # Pressure tolerance: 1%
        assert abs(P - expected_P) / expected_P < 0.01, (
            f"Press at {alt}m: {P} vs {expected_P}"
        )

        # Density tolerance: 1%
        assert abs(rho - expected_rho) / expected_rho < 0.01, (
            f"Density at {alt}m: {rho} vs {expected_rho}"
        )

    def test_tropopause_isothermal(self, atmosphere):
        """Test isothermal layer at tropopause (11-20 km)."""
        T_11km = atmosphere.get_temperature(11000)
        T_15km = atmosphere.get_temperature(15000)
        T_20km = atmosphere.get_temperature(20000)

        # All should be 216.65 K in isothermal layer
        assert abs(T_11km - 216.65) < 0.1
        assert abs(T_15km - 216.65) < 0.1
        assert abs(T_20km - 216.65) < 0.1

    def test_speed_of_sound(self, atmosphere):
        """Test speed of sound at sea level (340.3 m/s)."""
        a = atmosphere.get_speed_of_sound(0)
        assert abs(a - 340.3) < 1.0

    def test_viscosity_sutherland(self, atmosphere):
        """Test Sutherland's law for viscosity."""
        mu_0 = atmosphere.get_dynamic_viscosity(0)
        mu_10k = atmosphere.get_dynamic_viscosity(10000)

        # Sea level: ~1.789×10⁻⁵ Pa·s
        assert abs(mu_0 - 1.789e-5) < 0.1e-5

        # Lower at altitude due to lower temperature
        assert mu_10k < mu_0

    def test_negative_altitude_clamped(self, atmosphere):
        """Test that negative altitudes are clamped to 0."""
        T_neg = atmosphere.get_temperature(-100)
        T_zero = atmosphere.get_temperature(0)
        assert T_neg == T_zero

    def test_high_altitude_clamped(self, atmosphere):
        """Test that altitudes above 86km are clamped."""
        T_86k = atmosphere.get_temperature(86000)
        T_100k = atmosphere.get_temperature(100000)
        assert T_86k == T_100k

    def test_complete_state(self, atmosphere):
        """Test get_state returns complete atmospheric state."""
        state = atmosphere.get_state(5000)

        assert hasattr(state, "temperature_k")
        assert hasattr(state, "pressure_pa")
        assert hasattr(state, "density_kg_m3")
        assert hasattr(state, "speed_of_sound_m_s")
        assert hasattr(state, "dynamic_viscosity_pa_s")
        assert hasattr(state, "kinematic_viscosity_m2_s")

        assert state.altitude_m == 5000


class TestDrydenTurbulence:
    """Test suite for Dryden Wind Turbulence Model."""

    def test_sample_returns_tuple(self, wind):
        """Test that sample returns 3-element tuple."""
        u, v, w = wind.sample(0.01)
        assert isinstance(u, float)
        assert isinstance(v, float)
        assert isinstance(w, float)

    def test_turbulence_statistics(self, wind):
        """Test that turbulence has correct statistical properties."""
        samples = [wind.sample(0.01) for _ in range(10000)]
        u_samples = [s[0] for s in samples]

        mean_u = sum(u_samples) / len(u_samples)
        var_u = sum((x - mean_u) ** 2 for x in u_samples) / len(u_samples)

        # Mean should be near zero
        assert abs(mean_u) < 0.5

        # Variance should be positive and reasonable
        assert var_u > 0

    def test_reset_clears_state(self, wind):
        """Test that reset clears filter states."""
        _ = wind.sample(0.01)
        wind.reset()

        assert wind._u_state == 0.0
        assert wind._v_state == 0.0
        assert wind._w_state == 0.0

    def test_altitude_affects_scale_length(self):
        """Test that altitude affects turbulence scale length."""
        wind_low = DrydenTurbulence(altitude_m=50)
        wind_high = DrydenTurbulence(altitude_m=1000)

        # Low altitude has shorter scale length
        assert wind_low.L_w < wind_high.L_w

    def test_intensity_levels(self):
        """Test different turbulence intensity levels."""
        from warm_logic.kernel.drone.reality.atmosphere import DrydenTurbulence

        light = DrydenTurbulence(turbulence_intensity="light")
        severe = DrydenTurbulence(turbulence_intensity="severe")

        # Severe has higher intensity
        assert severe.sigma_u > light.sigma_u
