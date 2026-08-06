"""
Tests for Reality Engine Integration.

Tests the unified physics simulation engine.
"""

import pytest


class TestRealityEngine:
    """Test suite for Reality Engine."""

    def test_engine_creation(self, engine):
        """Test engine can be created."""
        assert engine is not None
        assert engine.atmosphere is not None
        assert engine.battery is not None

    def test_simulate_step_returns_dict(self, engine, state):
        """Test simulate_step returns dictionary."""
        result = engine.simulate_step(state, dt=0.01)

        assert isinstance(result, dict)
        assert "atmosphere" in result
        assert "wind" in result
        assert "gravity" in result
        assert "propulsion" in result
        assert "sensors" in result

    def test_atmosphere_in_result(self, engine, state):
        """Test atmosphere data in result."""
        result = engine.simulate_step(state, dt=0.01)

        atm = result["atmosphere"]
        assert "temperature_k" in atm
        assert "pressure_pa" in atm
        assert "density_kg_m3" in atm

        # Reasonable values at 100m altitude
        assert 280 < atm["temperature_k"] < 300
        assert 90000 < atm["pressure_pa"] < 105000

    def test_gravity_in_result(self, engine, state):
        """Test gravity calculation in result."""
        result = engine.simulate_step(state, dt=0.01)

        g = result["gravity"]
        assert 9.7 < g < 9.9  # Reasonable gravity

    def test_sensors_corrupted(self, engine, state):
        """Test sensor outputs are corrupted."""
        result = engine.simulate_step(state, dt=0.01)

        sensors = result["sensors"]
        assert "imu_accel" in sensors
        assert "imu_gyro" in sensors
        assert "gps_pos" in sensors

    def test_time_advances(self, engine, state):
        """Test simulation time advances."""
        initial_time = state.time_s

        engine.simulate_step(state, dt=0.1)

        assert state.time_s == initial_time + 0.1

    def test_reset_clears_state(self, engine):
        """Test reset clears internal states."""
        engine.battery.soc = 0.5
        engine.fatigue.total_cycles = 10000

        engine.reset()

        assert engine.battery.soc == 1.0
        assert engine.fatigue.total_cycles == 0

    def test_multiple_steps(self, engine, state):
        """Test running multiple simulation steps."""
        for _ in range(100):
            result = engine.simulate_step(state, dt=0.01)

        assert state.time_s == pytest.approx(1.0, rel=0.01)


class TestSimulationState:
    """Test suite for SimulationState."""

    def test_default_state(self, state):
        """Test default state values."""
        assert state.latitude_deg == 0.0
        assert state.longitude_deg == 0.078
        assert state.altitude_m == 100.0
        assert state.time_s == 0.0

    def test_motor_rpms(self, state):
        """Test motor RPMs are tuple of 4."""
        assert len(state.motor_rpms) == 4
        assert all(r > 0 for r in state.motor_rpms)
