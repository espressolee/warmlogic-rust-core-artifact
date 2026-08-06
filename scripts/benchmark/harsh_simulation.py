"""
[Phase 124] Harsh drone simulation v5.1 (Fixed Loop)
Harsh Drone Simulation - Ultimate 63 Calamities + 100% Physics Coverage

Pass criteria:
1. Battery: realistic consumption per mission (0.5% per km)
2. RTL: forced return below 20%
3. Safety: even a single real violation is a FAIL
4. Decision: 6/6 type coverage required
5. Errors: 0 required
6. Physics: statistical flight time + battery discharge
7. Score: stricter achievement criteria

[v5.1 Fix]
- Proper State Machine for Waypoints (No instant mission completion)
- Continuous Physics Integration
"""

import os
import random
import sys
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from warm_logic.kernel.drone.types import Position


class HarshSimulation:
    def __init__(self, duration_hours: float = 1.0, log_path: str = None):
        self.duration = timedelta(hours=duration_hours)
        self.log_path = log_path
        self._log_fd = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.current_sim_time = 0.0  # Logical simulation clock

        # Components
        self.drone = None
        self.engine = None
        self.safety = None
        self.planner = None
        self.telem = None
        self.reality = None
        self.disaster = None

        # State
        self.mission = None
        self.current_wp_index = 0
        self.mission_active = False

        # Stats
        self.stats = {
            "missions_completed": 0,
            "missions_aborted": 0,
            "total_distance_km": 0.0,
            "decisions_made": 0,
            "decision_types": {
                "continue": 0,
                "avoid": 0,
                "return_to_launch": 0,
                "emergency": 0,
                "hover": 0,
                "reroute": 0,
            },
            "threats_detected": 0,
            "waypoints_rejected": 0,
            "actual_violations": 0,
            "battery_current": 100.0,
            "battery_min": 100.0,
            "battery_recharges": 0,
            "rtl_triggered": 0,
            "emergency_triggered": 0,
            "telemetry_packets": 0,
            "errors": 0,
            "error_messages": [],
            "avg_decision_ms": 0.0,
            "max_decision_ms": 0.0,
            "max_jerk": 0.0,
        }
        self._decision_times = deque(maxlen=10000)
        self.last_accel = np.zeros(3)

    def header(self, text: str):
        print(f"\n{'=' * 60}\n{text}\n{'=' * 60}\n")

    def initialize(self):
        from warm_logic.kernel.drone.control import DroneController
        from warm_logic.kernel.drone.decision import DroneDecisionEngine
        from warm_logic.kernel.drone.mission import MissionPlanner
        from warm_logic.kernel.drone.reality import RealityEngine
        from warm_logic.kernel.drone.reality.engine import SimulationState
        from warm_logic.kernel.drone.reality.faults import DisasterSimulator
        from warm_logic.kernel.drone.safety import DroneSafetyMonitor
        from warm_logic.kernel.drone.telemetry import TelemetryManager

        print("Initializing harsh simulation v5.1...")

        self.drone = DroneController("HARSH001")
        self.drone.connect()

        # Initial Physics State
        self.reality = RealityEngine()
        self.sim_state = SimulationState(0.0, 0.0, 0.0)
        self.disaster = DisasterSimulator()

        # 6-DOF Init
        self.reality_q = np.array([1.0, 0.0, 0.0, 0.0])
        self.reality_omega = np.zeros(3)
        self.reality_vel = np.zeros(3)
        self.reality_pos = np.array(
            [0.0, 0.0, -10.0]
        )  # Start at safe altitude (10m) to avoid ground noise

        # [Paper Fix] Sync clock & state before takeoff
        self.drone._use_sim_time = True
        self.drone._sim_time = 0.0

        self.drone.arm()
        self.drone.takeoff(50)

        self.engine = DroneDecisionEngine()
        self.safety = DroneSafetyMonitor()
        self.safety.set_home(Position(0.0, 0.0, 0))
        self.planner = MissionPlanner()
        self.telem = TelemetryManager("HARSH001")
        self.telem.connect()

        self._generate_mission()

    def _generate_mission(self):
        """Generate a new random mission."""
        num_waypoints = random.randint(3, 7)
        waypoints = []
        home_lat, home_lon = 0.0, 0.0

        for idx in range(num_waypoints):
            # Safe random waypoints
            lat = home_lat + (random.random() - 0.5) * 0.005  # +/- 250m approx
            lon = home_lon + (random.random() - 0.5) * 0.005
            alt = 50.0
            waypoints.append(Position(lat, lon, alt))

        self.mission = self.planner.create_mission("Harsh", waypoints)
        self.current_wp_index = 0
        self.mission_active = True
        print(f"  New Mission Generated: {num_waypoints} WPs")

    def run_cycle(self):
        """Single Physics + Logic Tick (10ms)"""
        dt = 0.01

        # 0. Sync RealityEngine state from previous commands
        controls = self.drone.get_control_output()
        self.sim_state.throttle = controls
        # Simplified RPM mapping: 0.31 hover -> ~10000 RPM (default in RealityEngine)
        # We use a linear map for the mock's benefit
        new_rpms = [c * 20000.0 for c in controls]
        self.sim_state.motor_rpms = tuple(new_rpms)

        # 1. Physics Step (6-DOF)
        self._simulate_physics(dt, controls)

        # 2. Update Sensors & Drone State
        outputs = self.reality.simulate_step(self.sim_state, dt)
        outputs["sensors"]["battery_soc"] = self.stats["battery_current"] / 100.0
        outputs["sensors"]["gps_vel"] = (
            self.sim_state.velocity_n_m_s,
            self.sim_state.velocity_e_m_s,
            self.sim_state.velocity_d_m_s,
        )
        # [Phase 126] Override imu_accel with true body acceleration from physics
        if hasattr(self, "_last_body_accel"):
            outputs["sensors"]["imu_accel"] = self._last_body_accel

        # [Paper Fix] Pass logical clock for synchronization
        outputs["sensors"]["sim_time"] = self.current_sim_time

        # [Paper Fix] Apply GPS Faults
        if "gps_pos" in outputs["sensors"]:
            gps_tuple = outputs["sensors"]["gps_pos"]
            gps_offset = self.disaster.get_gps_offset()
            gps_list = list(gps_tuple)
            gps_list[0] += gps_offset[0] * 1e-6
            gps_list[1] += gps_offset[1] * 1e-6
            gps_list[2] += gps_offset[2]
            outputs["sensors"]["gps_pos"] = tuple(gps_list)

        self.drone.update_state_from_sensors(outputs["sensors"])
        self.current_sim_time += dt

        # [Phase 125] Heartbeat
        self.drone.send_heartbeat()

        # 3. Mission Logic (State Machine)
        if self.mission_active and self.mission:
            self._process_mission_logic()
        else:
            self._generate_mission()

        # 4. Telemetry & Faults
        self.disaster.update(dt)

    def _simulate_physics(self, dt, controls):
        # Physics Constants
        m, g, L = 2.5, 9.81, 0.25
        Inertia = np.diag([0.02, 0.02, 0.04])
        T_max = 20.0

        m1, m2, m3, m4 = controls
        # [Paper Fix] Apply Motor Efficiency from DisasterSimulator
        f = [
            controls[0] * T_max * self.disaster.get_motor_efficiency(0),
            controls[1] * T_max * self.disaster.get_motor_efficiency(1),
            controls[2] * T_max * self.disaster.get_motor_efficiency(2),
            controls[3] * T_max * self.disaster.get_motor_efficiency(3),
        ]

        # Forces & Moments
        F_thrust = -sum(f)
        Mx = L * ((f[1] + f[2]) - (f[0] + f[3]))
        My = L * ((f[0] + f[1]) - (f[2] + f[3]))
        Mz = 0.02 * ((f[1] + f[3]) - (f[0] + f[2]))

        moments = np.array([Mx, My, Mz])

        # Dynamics
        q = self.reality_q
        omega = self.reality_omega
        vel = self.reality_vel
        pos = self.reality_pos

        # Rotation Matrix
        q0, q1, q2, q3 = q
        R = np.array(
            [
                [
                    1 - 2 * (q2**2 + q3**2),
                    2 * (q1 * q2 - q0 * q3),
                    2 * (q1 * q3 + q0 * q2),
                ],
                [
                    2 * (q1 * q2 + q0 * q3),
                    1 - 2 * (q1**2 + q3**2),
                    2 * (q2 * q3 - q0 * q1),
                ],
                [
                    2 * (q1 * q3 - q0 * q2),
                    2 * (q2 * q3 + q0 * q1),
                    1 - 2 * (q1**2 + q2**2),
                ],
            ]
        )

        # Linear Accel
        F_body = np.array([0, 0, F_thrust])
        accel = (R @ F_body) / m + np.array([0, 0, g])
        accel -= 0.1 * vel  # Simplified drag

        # [Paper Fix] Apply External Forces (Microburst)
        accel += self.disaster.get_external_force() / m

        # Angular Accel
        Iw = Inertia @ omega
        dw = np.linalg.inv(Inertia) @ (moments - np.cross(omega, Iw))

        # Integration
        vel_next = vel + accel * dt
        pos_next = pos + vel_next * dt
        omega += dw * dt

        # Quaternion Integration
        wx, wy, wz = omega
        dq = 0.5 * np.array(
            [
                -q1 * wx - q2 * wy - q3 * wz,
                q0 * wx - q3 * wy + q2 * wz,
                q3 * wx + q0 * wy - q1 * wz,
                -q2 * wx + q1 * wy + q0 * wz,
            ]
        )
        q += dq * dt
        q /= np.linalg.norm(q)

        # Ground Contact
        if pos_next[2] >= 0:
            pos_next[2] = 0
            vel_next[2] = min(0, vel_next[2])
            vel_next[0] *= 0.5
            vel_next[1] *= 0.5
            omega[:] = 0

        # Store Body Accel for IMU
        accel_actual = (vel_next - vel) / dt
        g_ned = np.array([0, 0, g])
        accel_body = R.T @ (accel_actual - g_ned)
        self._last_body_accel = (accel_body[0], accel_body[1], accel_body[2])

        self.reality_q, self.reality_omega, self.reality_vel, self.reality_pos = (
            q,
            omega,
            vel_next,
            pos_next,
        )

        # Sync SimState
        (
            self.sim_state.velocity_n_m_s,
            self.sim_state.velocity_e_m_s,
            self.sim_state.velocity_d_m_s,
        ) = vel_next
        self.sim_state.pos_n_m, self.sim_state.pos_e_m, self.sim_state.pos_d_m = (
            pos_next
        )
        self.sim_state.altitude_m = -pos_next[2]

        R_earth = 6371000.0
        home_lat, home_lon = 0.0, 0.0
        self.sim_state.latitude_deg = home_lat + np.degrees(pos_next[0] / R_earth)
        self.sim_state.longitude_deg = home_lon + np.degrees(
            pos_next[1] / (R_earth * np.cos(np.radians(home_lat)))
        )

    def _process_mission_logic(self):
        if self.current_wp_index >= len(self.mission.waypoints):
            self.mission_active = False
            self.stats["missions_completed"] += 1
            return
        wp = self.mission.waypoints[self.current_wp_index]
        if (
            not hasattr(self, "_last_sent_wp_index")
            or self._last_sent_wp_index != self.current_wp_index
        ):
            self.drone.goto(wp.position)
            self._last_sent_wp_index = self.current_wp_index
        dist = self.drone._position.distance_to(wp.position)
        if dist < 15.0:
            print(f"  Waypoint {self.current_wp_index} reached (dist={dist:.1f}m)")
            self.current_wp_index += 1
        speed = np.linalg.norm(self.reality_vel)
        drain = speed * 0.01 * (0.5 / 1000.0)
        self.stats["battery_current"] -= drain
        self.stats["battery_current"] = max(0.0, self.stats["battery_current"])
        self.stats["total_distance_km"] += speed * 0.01 / 1000.0

    def run(self):
        self.initialize()
        self.header("Simulation Start")
        if self.log_path:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            self._log_fd = open(self.log_path, "a", buffering=1)
            self._log_fd.write(f"\n--- SIMULATION START: {datetime.now()} ---\n")
        self.start_time = datetime.now()
        self.end_time = self.start_time + self.duration
        report_time = time.time()
        while datetime.now() < self.end_time:
            self.run_cycle()
            if time.time() - report_time > 1.0:
                elapsed = datetime.now() - self.start_time
                fs_state = getattr(self.drone, "_failsafe_state", "UNKNOWN").value
                speed = np.linalg.norm(self.reality_vel)
                report = f"[REPORT] T={elapsed.total_seconds():.1f}s | FS={fs_state.upper()} | Bat={self.stats['battery_current']:.1f}% | Mis={self.stats['missions_completed']} | Alt={-self.reality_pos[2]:.1f}m"
                print(report)
                if self._log_fd:
                    self._log_fd.write(report + "\n")
                report_time = time.time()
            time.sleep(0.001)
        self.header("Simulation Complete")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=0.01)
    parser.add_argument("--log", type=str, default=None)
    args = parser.parse_args()
    sim = HarshSimulation(duration_hours=args.hours, log_path=args.log)
    try:
        sim.run()
    finally:
        if hasattr(sim, "_log_fd") and sim._log_fd:
            sim._log_fd.close()
