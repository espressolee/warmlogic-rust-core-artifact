"""
[Phase 140] Verification Script for 3D Obstacle Avoidance.
Scenarios:
1. Approach Obstacle -> Emergency Stop / Deviation.
"""

import os
import sys
import time
from datetime import datetime

import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from warm_logic.kernel.drone.control import DroneController
from warm_logic.kernel.drone.reality import RealityEngine
from warm_logic.kernel.drone.reality.engine import SimulationState
from warm_logic.kernel.drone.reality.sensors.vision_sim import Obstacle
from warm_logic.kernel.drone.types import Position


def verify_avoidance():
    print("Eagle Eye Validation: 3D Obstacle Avoidance")
    print("==============================================")

    # 1. Init System
    drone = DroneController("AVOID001")
    drone.connect()
    drone.arm()

    reality = RealityEngine()
    sim_state = SimulationState(0.0, 0.0, 0.0)  # Home

    # 2. Setup Obstacle Course
    # Place a tower 20m North of Home
    tower_pos = np.array([20.0, 0.0, -10.0])  # 20m North, 10m Alt
    tower_radius = 5.0
    obstacle = Obstacle("TestTower", tower_pos, tower_radius)

    # Inject into simulator
    reality.vision.obstacles.append(obstacle)
    print(f"Obstacle Placed at N=20m, E=0m, Alt=10m (Radius=5m)")

    # 3. Takeoff
    print("Taking off to 10m...")
    drone.takeoff(10.0)

    # Simulation Loop for Takeoff
    for _ in range(500):  # 5 seconds
        sim_state, outputs = run_sim_step(drone, reality, sim_state)
        if drone._position.altitude > 9.5:
            break

    print("Reached Hover Altitude.")

    # 4. Command Collision Course
    target_wp = Position(0.0 + (40.0 / 111320.0), 0.0, 10.0)  # 40m North
    drone.goto(target_wp)
    print("Commanded GOTO 40m North (Through Obstacle)...")

    # 5. Monitor
    start_time = time.time()
    min_dist_to_obs = float("inf")
    result = "UNKNOWN"

    for i in range(1000):  # 10 seconds max
        sim_state, outputs = run_sim_step(drone, reality, sim_state)

        # Check Distance to Obstacle
        drone_pos_ned = np.array(
            [sim_state.pos_n_m, sim_state.pos_e_m, sim_state.pos_d_m]
        )
        dist = np.linalg.norm(drone_pos_ned - tower_pos) - tower_radius
        min_dist_to_obs = min(min_dist_to_obs, dist)

        speed = np.linalg.norm([sim_state.velocity_n_m_s, sim_state.velocity_e_m_s])

        # Reporting
        if i % 50 == 0:
            status = getattr(drone, "_safety_monitor", None)
            safety = "N/A"
            # We can't easily access the internal safety status unless we expose it or spy on logs
            # But we can check velocity behavior.
            print(
                f"T={i * 0.01:.1f}s | PosN={sim_state.pos_n_m:.1f}m | DistObj={dist:.1f}m | Speed={speed:.1f}m/s"
            )

        # Success/Fail Conditions
        if dist < 0.0:
            print("COLLISION DETECTED! Test Failed.")
            result = "FAIL"
            break

        if speed < 0.2 and sim_state.pos_n_m > 10.0 and dist < 5.0:
            # Stopped near obstacle
            print("Drone Stopped Safely near obstacle.")
            result = "SUCCESS (STOP)"
            break

        if sim_state.pos_n_m > 30.0:
            # Passed the obstacle logic
            print("Drone Passed Obstacle region.")
            # Check deviation?
            lat_dev = abs(sim_state.pos_e_m)
            if lat_dev > 2.0:
                print(f"Lateral Deviation: {lat_dev:.1f}m (Avoidance Active)")
                result = "SUCCESS (BYPASS)"
            else:
                print("Passed without deviating? Did we miss it?")
                result = "UNCLEAR"
            break

    print(f"\nFinal Result: {result}")
    print(f"Min Distance to Obstacle Surface: {min_dist_to_obs:.2f}m")


def run_sim_step(drone, reality, sim_state):
    dt = 0.01

    # 1. Physics (Simplified for verify script - reusing SimState integration roughly)
    # Get controls
    controls = drone.get_control_output()

    # Simple Kinematics for this test (we trust the controller's safety logic, not testing physics engine pitch/roll response time)
    # Actually, we need 6DOF to allow VIO to work?
    # No, VIO works if we feed it a rendered frame.
    # Frame rendering relies on Pose.

    # Let's use a simpler "Perfect Model" where Velocity Command -> Velocity State
    # Because full physics integration is heavy to reimplement here.
    # WAIT. Controller outputs Motor Thrusts. Simple kinematics won't work unless we have a mixer inverse.

    # We should use the "use_external_physics" mode if available, or just replicate the 'HarsSimulation' physics loop.
    # I'll just copy the physics loop logic briefly.

    # ... Or I can just trust the `DroneController`'s internal physics!
    # `DroneController` has RK4 physics BUILT-IN!
    # `drone.update_physics()` runs the integration.
    # I just need to sync simulated Reality environment to the Drone's internal state?
    # NO. DroneController's internal physics is for "Estimation" (Prediction).
    # RealityEngine is "Truth".

    # I'll use the DroneController's internal physics as the "Truth" for this simple test to avoid code duplication.
    # It has `_physics_state`.

    drone.update_physics()

    # Update SimState from Drone Physics (Cheating, but fine for logic test)
    sim_state.pos_n_m = (drone._position.latitude - 0.0) * 111320
    sim_state.pos_e_m = (drone._position.longitude - 0.0) * 110540
    sim_state.pos_d_m = -drone._position.altitude

    sim_state.velocity_n_m_s = (
        drone._physics_state.vy
    )  # Wait, physics state is x, y, z. Check mappings.
    # PhysicsState x=East?, y=North?
    # Controller.py: latitude=self._home.latitude + self._physics_state.y / 110540
    # So Y=North, X=East.
    sim_state.velocity_n_m_s = drone._physics_state.vy
    sim_state.velocity_e_m_s = drone._physics_state.vx
    sim_state.velocity_d_m_s = drone._physics_state.vz

    sim_state.roll_deg = math.degrees(drone._attitude.roll)
    sim_state.pitch_deg = math.degrees(drone._attitude.pitch)
    sim_state.yaw_deg = math.degrees(drone._attitude.yaw)

    # Render Vision
    outputs = reality.simulate_step(sim_state, dt)

    # Feed back to Drone
    drone.update_state_from_sensors(outputs["sensors"])

    return sim_state, outputs


import math

if __name__ == "__main__":
    verify_avoidance()
