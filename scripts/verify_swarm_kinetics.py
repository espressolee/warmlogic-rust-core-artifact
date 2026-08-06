import os
import sys
import time

import numpy as np

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from warm_logic.kernel.drone.control.controller import DroneController
from warm_logic.kernel.swarm.kinetic import KineticSwarmEngine


def test_swarm_boids():
    print("[Swarm] Starting Boids Behavioral Verification...")

    # 1. Setup Engine & Peers
    engine = KineticSwarmEngine("drone-alpha")

    # Mock Peers (Pos [N,E,D], Vel [VN, VE, VD])
    # Peer 1: 3 meters North (triggers Separation)
    engine.update_peer("peer-1", (3.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    # Peer 2: 20 meters East, moving South at 5m/s (triggers Cohesion & Alignment)
    engine.update_peer("peer-2", (0.0, 20.0, 0.0), (-5.0, 0.0, 0.0))

    # My State: Origin, Stationary
    my_pos = np.array([0.0, 0.0, 0.0])
    my_vel = np.array([0.0, 0.0, 0.0])

    # 2. Calculate Forces
    force = engine.calculate_swarm_force(my_pos, my_vel)
    print(f"  > Calculated Swarm Force: {force}")

    # EXPECTATIONS:
    # - Separation from Peer 1 (at +3m N) should push us South (-N)
    # - Cohesion towards Peers (+N, +E avg) should pull us North/East
    # - Alignment with Peer 2 (-5m/s N) should push us South (-N)

    assert force[0] < 0, (
        f"Expected Southward force due to separation/alignment, got {force[0]}"
    )
    assert force[1] > 0, f"Expected Eastward force due to cohesion, got {force[1]}"
    print("[Boids] Behavioral Logic Verified.")


def test_controller_injection():
    print("[Swarm] Verifying Controller Force Injection...")

    # Setup Controller
    controller = DroneController(drone_id="drone-beta")
    controller._armed = True

    # Mock sensors to be level and at origin
    from warm_logic.kernel.drone.control.controller import Attitude, Position, Velocity

    controller._position = Position(latitude=0, longitude=0, altitude=10.0)
    controller._velocity = Velocity(north=0, east=0, down=0)
    controller._attitude = Attitude(roll=0, pitch=0, yaw=0)

    # Set Target: Hover at same spot
    controller._target_position = Position(latitude=0, longitude=0, altitude=10.0)

    # 1. Baseline (No Peers)
    m1, m2, m3, m4 = controller.get_control_output()
    # Assume symmetric output for hover
    print(f"  > Baseline Output: {(m1, m2, m3, m4)}")

    # 2. Inject Swarm Peer to the East (should cause Roll Right to compensate? No, Boids: Separation pulls West)
    # Wait, if peer is East, Separation pushes West. Cohesion pulls East.
    # Let's put peer very close East (3m) to trigger Separation dominance.
    controller._swarm_engine.update_peer("peer-east", (0.0, 3.0, 0.0), (0.0, 0.0, 0.0))

    # Expected Force: West (-E).
    # To move West, drone needs to Roll Left (-Roll).
    # In controller: target_roll_deg += swarm_f_body[1]
    # swarm_f_body[1] is for East. If force is West, swarm_f_body[1] is negative.
    # so target_roll becomes negative.

    # We can't easily see internal target_roll_deg without print or mocking,
    # but we can see motor output change.
    m1_new, m2_new, m3_new, m4_new = controller.get_control_output()
    print(f"  > Swarm Active Output: {(m1_new, m2_new, m3_new, m4_new)}")

    # Roll Left (towards -E) usually means increasing right motors or decreasing left.
    # Drone Mixer:
    # m1 (FrontRight), m2 (RearLeft), m3 (FrontLeft), m4 (RearRight)
    # Roll Left: Increase Right (m1, m4), Decrease Left (m2, m3) ? Depends on mixer.

    # Just verify output is different
    assert (m1_new, m2_new, m3_new, m4_new) != (m1, m2, m3, m4), (
        "Control output did not react to swarm force!"
    )
    print("[Controller] Swarm Force Injection Verified.")


if __name__ == "__main__":
    try:
        test_swarm_boids()
        test_controller_injection()
        print("\nALL SWARM VERIFICATIONS PASSED.")
    except Exception as e:
        print(f"\nVERIFICATION FAILED: {e}")
        sys.exit(1)
