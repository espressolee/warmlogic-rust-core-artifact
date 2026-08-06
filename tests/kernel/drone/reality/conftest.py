"""Pytest fixtures for reality simulator tests."""

import pytest

from warm_logic.kernel.drone.reality.aerodynamics import (
    BladeElementMomentumTheory,
    GroundEffect,
    VortexRingState,
)
from warm_logic.kernel.drone.reality.atmosphere import (
    DrydenTurbulence,
    USStandardAtmosphere1976,
)
from warm_logic.kernel.drone.reality.engine import RealityEngine, SimulationState
from warm_logic.kernel.drone.reality.propulsion import BLDCMotor, TheveninBattery
from warm_logic.kernel.drone.reality.sensors import (
    AllanVarianceIMU,
    GPSErrorModel,
    MagnetometerModel,
)


@pytest.fixture
def atmosphere():
    return USStandardAtmosphere1976()


@pytest.fixture
def wind():
    return DrydenTurbulence()


@pytest.fixture
def bemt():
    return BladeElementMomentumTheory()


@pytest.fixture
def ground_effect():
    return GroundEffect()


@pytest.fixture
def vrs():
    return VortexRingState()


@pytest.fixture
def imu():
    return AllanVarianceIMU()


@pytest.fixture
def gps():
    return GPSErrorModel()


@pytest.fixture
def magnetometer():
    return MagnetometerModel()


@pytest.fixture
def battery():
    return TheveninBattery()


@pytest.fixture
def motor():
    return BLDCMotor()


@pytest.fixture
def engine():
    return RealityEngine()


@pytest.fixture
def state():
    return SimulationState()
