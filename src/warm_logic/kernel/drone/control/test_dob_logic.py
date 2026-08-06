# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.



def test_dob():
    # 1. Setup constants
    m = 2.5
    max_thrust = 80.0
    g = 9.81

    # 2. Simulate Hover (No wind, No drag)
    # Controller side
    thrust_total = (m * g) / max_thrust  # 0.3065
    cmd_accel = (0, 0, -thrust_total * max_thrust / m)  # (0, 0, -9.81)

    # Physics side
    # a = T/m + g = [0, 0, -9.81] + [0, 0, 9.81] = 0
    # imu = a - g = [0, 0, -9.81]
    imu_accel = (0, 0, -9.81)

    dist_raw = (
        imu_accel[0] - cmd_accel[0],
        imu_accel[1] - cmd_accel[1],
        imu_accel[2] - cmd_accel[2],
    )
    print(f"Hover Test: Dist={dist_raw} (Expect 0)")

    # 3. Simulate Forward Flight with Drag
    # v_fwd = 10 m/s
    # Physics side
    # a_thrust = -9.81 (hovering while moving)
    # a_drag = -0.1 * 10 = -1.0
    # a_drone = a_thrust + g + a_drag = -9.81 + 9.81 - 1.0 = -1.0
    # imu = a_drone - g = -1.0 - 9.81 = -10.81? No, world frame vs body frame.
    # Level flight: imu_x = a_drone_x = -1.0. imu_z = a_drone_z - g_z = -9.81.
    imu_accel = (-1.0, 0.0, -9.81)

    # Controller side (doesn't know about drag in raw DOB)
    dist_raw = (imu_accel[0] - 0, imu_accel[1] - 0, imu_accel[2] - (-9.81))
    print(f"Drag Test Raw: Dist={dist_raw} (Expect -1.0 in X)")

    # Drag compensation
    drag_coeff = 0.1
    # expected_drag = -drag_coeff * v_fwd = -1.0
    expected_drag_x = -0.1 * 10
    dist_corr_x = dist_raw[0] - expected_drag_x
    print(f"Drag Test Corr: DistX={dist_corr_x} (Expect 0)")


if __name__ == "__main__":
    test_dob()
