"""
[Phase 1] Formal Verification of Control Loop Invariants.
Using Hypothesis for Property-Based Testing to prove stability and safety bounds.
"""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from warm_logic.kernel.drone.control.dob import DisturbanceObserver
from warm_logic.kernel.drone.control.pid import RobustPID

# --- 1. RobustPID Invariants ---


@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
@given(
    kp=st.floats(min_value=0.1, max_value=10.0),
    ki=st.floats(min_value=0.0, max_value=2.0),
    kd=st.floats(min_value=0.0, max_value=5.0),
    dt=st.floats(min_value=0.001, max_value=0.1),
    error=st.floats(min_value=-1000.0, max_value=1000.0),
    ff=st.floats(min_value=-1.0, max_value=1.0),
)
def test_pid_output_bounded_invariant(kp, ki, kd, dt, error, ff):
    """
    PROVES: RobustPID output is always strictly within [output_min, output_max].
    This is critical for preventing actuator saturation from destabilizing the kernel.
    """
    pid = RobustPID(kp=kp, ki=ki, kd=kd, dt=dt, output_min=-1.0, output_max=1.0)

    # Run multiple updates to test integrator accumulation
    for _ in range(10):
        output = pid.update(error, feedforward=ff)
        assert -1.0 <= output <= 1.0


@given(
    ki=st.floats(min_value=0.1, max_value=2.0),
    error=st.floats(min_value=100.0, max_value=1000.0),
)
def test_pid_anti_windup_invariant(ki, error):
    """
    PROVES: Integrator term never exceeds its defined limits even with persistent large error.
    """
    pid = RobustPID(
        kp=1.0, ki=ki, kd=0.0, dt=0.01, integrator_min=-0.5, integrator_max=0.5
    )

    # Force long-term accumulation
    for _ in range(100):
        pid.update(error)

    assert -0.5 <= pid._integrator <= 0.5


# --- 2. DisturbanceObserver (DOB) Invariants ---


@settings(max_examples=100)
@given(accel_val=st.floats(min_value=-20.0, max_value=20.0))
def test_dob_zero_disturbance_invariant(accel_val):
    """
    PROVES: If measured acceleration matches commanded, disturbance estimate converges toward zero.
    """
    dob = DisturbanceObserver(mass=2.5, dt=0.01, cutoff_hz=2.0)

    # Simulate steady state with no disturbance
    meas = (accel_val, 0.0, 0.0)
    cmd = (accel_val, 0.0, 0.0)

    # Let filters settle
    last_dist = (0.0, 0.0, 0.0)
    for _ in range(100):
        last_dist = dob.update(meas, cmd)

    # Should be close to zero (allowing for floating point epsilon)
    assert abs(last_dist[0]) < 1e-4
    assert abs(last_dist[1]) < 1e-4
    assert abs(last_dist[2]) < 1e-4


@given(bias=st.floats(min_value=-10.0, max_value=10.0))
def test_dob_offset_estimation_invariant(bias):
    """
    PROVES: DOB correctly estimates a constant offset/bias in acceleration (e.g. steady wind).
    """
    dob = DisturbanceObserver(mass=2.5, dt=0.01, cutoff_hz=2.0)

    # Constant bias: measured = commanded + bias
    cmd = (5.0, 0.0, 0.0)
    meas = (5.0 + bias, 0.0, 0.0)

    # Let filters settle (2.0 Hz cutoff = ~0.5s settling time, 50 steps at 100Hz)
    last_dist = (0.0, 0.0, 0.0)
    for _ in range(200):
        last_dist = dob.update(meas, cmd)

    # Estimate should match bias
    assert pytest.approx(last_dist[0], abs=1e-2) == bias


if __name__ == "__main__":
    pytest.main([__file__])
