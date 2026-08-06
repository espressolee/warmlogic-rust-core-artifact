import math
import statistics

from warm_logic.kernel.drone.reality.atmosphere.dryden import DrydenGustModel


def test_dryden_statistics():
    """Verify Dryden model produces expected variance."""
    dt = 0.01
    model = DrydenGustModel(dt=dt)

    # Test Condition: Low Altitude, Moderate Speed
    alt = 50.0  # m
    speed = 10.0  # m/s (approx 20 knots)

    duration = 60.0  # seconds
    steps = int(duration / dt)

    u_hist = []
    v_hist = []
    w_hist = []

    for _ in range(steps):
        u, v, w = model.get_turbulence(alt, speed)
        u_hist.append(u)
        v_hist.append(v)
        w_hist.append(w)

    u_std = statistics.stdev(u_hist)
    v_std = statistics.stdev(v_hist)
    w_std = statistics.stdev(w_hist)

    print(f"Dryden Statistics (Alt={alt}m, Speed={speed}m/s):")
    print(f"  u_gust std: {u_std:.3f} m/s")
    print(f"  v_gust std: {v_std:.3f} m/s")
    print(f"  w_gust std: {w_std:.3f} m/s")

    # Basic check: Standard deviation should be non-zero and reasonable
    assert u_std > 0.1, "u_gust standard deviation too low"
    assert v_std > 0.1, "v_gust standard deviation too low"
    assert w_std > 0.1, "w_gust standard deviation too low"
    assert u_std < 5.0, "u_gust standard deviation too high"

    print("✅ Dryden Statistics Test Passed")


if __name__ == "__main__":
    test_dryden_statistics()
