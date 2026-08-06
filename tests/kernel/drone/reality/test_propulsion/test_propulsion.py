"""
Tests for Propulsion Models.

Validates Thevenin Battery and BLDC Motor models.
"""

import math

import pytest


class TestTheveninBattery:
    """Test suite for Thevenin Battery Model."""

    def test_initial_soc(self, battery):
        """Test initial SOC is 100%."""
        assert battery.soc == 1.0

    def test_ocv_at_full_charge(self, battery):
        """Test OCV at full charge (4.2V per cell)."""
        ocv = battery.get_ocv(soc=1.0)
        assert abs(ocv - 4.2) < 0.1

    def test_ocv_at_empty(self, battery):
        """Test OCV at empty (3.0V per cell)."""
        ocv = battery.get_ocv(soc=0.0)
        assert abs(ocv - 3.0) < 0.1

    def test_terminal_voltage_under_load(self, battery):
        """Test terminal voltage drops under load."""
        v_no_load = battery.get_terminal_voltage(current_a=0.0)
        v_20a = battery.get_terminal_voltage(current_a=20.0)

        # Voltage should drop under load
        assert v_20a < v_no_load

        # Drop should be reasonable (not more than 2V for 4S)
        assert v_no_load - v_20a < 2.0

    def test_soc_decreases_with_discharge(self, battery):
        """Test SOC decreases during discharge."""
        initial_soc = battery.soc

        # Discharge for 1 second at 5A
        battery.update_soc(current_a=5.0, dt=1.0)

        assert battery.soc < initial_soc

    def test_soc_clamped(self, battery):
        """Test SOC is clamped to [0, 1]."""
        battery.soc = 0.01
        battery.update_soc(current_a=1000.0, dt=10.0)  # Massive discharge

        assert battery.soc == 0.0


class TestBLDCMotor:
    """Test suite for BLDC Motor Model."""

    def test_kt_calculation(self, motor):
        """Test torque constant calculation."""
        kt = motor.kt
        kv = motor.kv

        # Kt = 9.55 / Kv
        expected = 9.55 / kv
        assert abs(kt - expected) < 0.001

    def test_back_emf(self, motor):
        """Test back-EMF calculation."""
        rpm = 10000
        bemf = motor.get_back_emf(rpm)

        # E = V / Kv at no load
        expected = rpm / motor.kv
        assert abs(bemf - expected) < 0.5

    def test_max_rpm(self, motor):
        """Test maximum RPM at given voltage."""
        voltage = 16.0
        max_rpm = motor.get_max_rpm(voltage)

        # Should be close to Kv × V
        expected = motor.kv * voltage
        # Account for no-load current drop
        assert max_rpm < expected
        assert max_rpm > expected * 0.9

    def test_operating_point(self, motor):
        """Test steady-state operating point calculation."""
        rpm, current, efficiency = motor.calculate_operating_point(
            voltage=14.8, load_torque=0.05
        )

        assert rpm > 0
        assert current > 0
        assert 0 < efficiency < 1
