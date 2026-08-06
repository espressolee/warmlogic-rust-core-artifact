"""
Tests for Sensor Models.

Validates IMU, GPS, and Magnetometer against statistical expectations.
"""

import math

import pytest


class TestAllanVarianceIMU:
    """Test suite for Allan Variance IMU model."""

    def test_gyro_output_format(self, imu):
        """Test gyro output is 3-tuple of floats."""
        true_rate = (0.0, 0.0, 0.1)
        noisy = imu.corrupt_gyro(true_rate, dt=0.01)

        assert len(noisy) == 3
        assert all(isinstance(x, float) for x in noisy)

    def test_accel_output_format(self, imu):
        """Test accel output is 3-tuple of floats."""
        true_accel = (0.0, 0.0, -9.81)
        noisy = imu.corrupt_accel(true_accel, dt=0.01)

        assert len(noisy) == 3
        assert all(isinstance(x, float) for x in noisy)

    def test_noise_is_added(self, imu):
        """Test that noise is actually added."""
        true_rate = (0.0, 0.0, 0.0)

        samples = [imu.corrupt_gyro(true_rate, 0.01) for _ in range(100)]
        z_values = [s[2] for s in samples]

        # Not all values should be zero
        assert not all(z == 0 for z in z_values)

        # Should have some variance
        mean_z = sum(z_values) / len(z_values)
        var_z = sum((z - mean_z) ** 2 for z in z_values) / len(z_values)
        assert var_z > 0

    def test_reset_clears_bias(self, imu):
        """Test reset clears accumulated bias."""
        # Accumulate some bias
        for _ in range(1000):
            imu.corrupt_gyro((0, 0, 0), 0.01)

        imu.reset()

        assert imu._gyro_bias == (0.0, 0.0, 0.0)
        assert imu._gyro_rw == (0.0, 0.0, 0.0)


class TestGPSErrorModel:
    """Test suite for GPS Error Model."""

    def test_horizontal_accuracy(self, gps):
        """Test horizontal accuracy calculation."""
        h_acc = gps.get_horizontal_accuracy()

        # Should be positive
        assert h_acc > 0

        # Should be reasonable (1-20m for consumer GPS)
        assert 1 < h_acc < 20

    def test_vertical_accuracy_worse(self, gps):
        """Test vertical accuracy is worse than horizontal."""
        h_acc = gps.get_horizontal_accuracy()
        v_acc = gps.get_vertical_accuracy()

        # VDOP typically > HDOP
        assert v_acc > h_acc

    def test_position_corruption(self, gps):
        """Test position corruption adds error."""
        true_lat, true_lon, true_alt = 0.0, 0.078, 100.0

        # Multiple samples
        samples = [
            gps.corrupt_position(true_lat, true_lon, true_alt) for _ in range(100)
        ]

        lat_errors = [abs(s[0] - true_lat) for s in samples]
        lon_errors = [abs(s[1] - true_lon) for s in samples]

        # Should have non-zero errors
        assert max(lat_errors) > 0
        assert max(lon_errors) > 0

    def test_velocity_corruption(self, gps):
        """Test velocity corruption."""
        true_vel = (10.0, 0.0, 0.0)

        noisy = gps.corrupt_velocity(true_vel, dt=1.0)

        assert len(noisy) == 3
        assert all(isinstance(x, float) for x in noisy)


class TestMagnetometer:
    """Test suite for Magnetometer Model."""

    def test_measurement_format(self, magnetometer):
        """Test measurement output format."""
        true_field = (0.2, 0.0, 0.4)
        measured = magnetometer.corrupt_measurement(true_field)

        assert len(measured) == 3
        assert all(isinstance(x, float) for x in measured)

    def test_noise_added(self, magnetometer):
        """Test noise is added to measurements."""
        true_field = (0.2, 0.0, 0.4)

        samples = [magnetometer.corrupt_measurement(true_field) for _ in range(100)]
        x_values = [s[0] for s in samples]

        # Should have variance
        mean_x = sum(x_values) / len(x_values)
        var_x = sum((x - mean_x) ** 2 for x in x_values) / len(x_values)
        assert var_x > 0

    def test_heading_calculation(self, magnetometer):
        """Test heading calculation."""
        # Field pointing North
        heading_n = magnetometer.get_heading((1.0, 0.0, 0.0))
        assert abs(heading_n - 0) < 1 or abs(heading_n - 360) < 1

        # Field pointing East
        heading_e = magnetometer.get_heading((0.0, -1.0, 0.0))
        assert abs(heading_e - 90) < 1

    def test_declination_applied(self, magnetometer):
        """Test declination is added to heading."""
        # Field pointing North
        heading_no_dec = magnetometer.get_heading((1.0, 0.0, 0.0), declination_deg=0)
        heading_dec = magnetometer.get_heading((1.0, 0.0, 0.0), declination_deg=10)

        assert abs(heading_dec - heading_no_dec - 10) < 1
