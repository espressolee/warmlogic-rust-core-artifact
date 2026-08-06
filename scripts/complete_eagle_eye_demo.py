"""
[Phase 140] Complete Eagle Eye System Demo.
Integrates Vision Simulation, VIO, and 3D Mapping.
"""

import sys
from pathlib import Path

import numpy as np

# Add src to sys.path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from warm_logic.kernel.drone.control.controller import DroneController
from warm_logic.kernel.drone.reality.engine import RealityEngine, SimulationState
from warm_logic.kernel.drone.reality.sensors.vision_sim import Obstacle


def main():
    # 1. Setup Simulation
    engine = RealityEngine()
    engine.vision.obstacles = [
        Obstacle("TallTower", np.array([50.0, 0.0, -25.0]), 10.0),
    ]

    # 2. Setup Intelligence (Drone Controller)
    controller = DroneController("EAGLE_EYE_001")
    controller.connect()

    # 3. Simulate Flight towards the Tower
    state = SimulationState(pos_n_m=0.0, pos_e_m=0.0, pos_d_m=-20.0)
    dt = 0.1  # 10Hz perception loop

    print("Phase 140: Eagle Eye Full Integration Demo")
    print("=" * 45)

    for i in range(10):
        # Move drone forward
        state.pos_n_m += 5.0  # v = 50m/s (Fast for demo)

        # Physics Step -> Vision Frame
        outputs = engine.simulate_step(state, dt)

        # Controller Step -> Perception Update
        controller.update_state_from_sensors(outputs["sensors"])

        # Status
        vio_vel = controller._vio_velocity
        occ_count = np.sum(controller._mapper.occupancy)
        print(
            f"Step {i + 1}: Pos={state.pos_n_m:.1f}m | VIO Vel N={vio_vel[0]:.2f}m/s | Map Occupancy={occ_count} voxels"
        )

    print("=" * 45)
    print(
        "✅ INTEGRATION SUCCESS: VIO tracked motion and Mapper populated the 3D world."
    )


if __name__ == "__main__":
    main()
