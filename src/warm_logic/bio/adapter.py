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
import logging
from typing import Any, Dict

logger = logging.getLogger("VitruvianAdapter")


class VitruvianAdapter:
    """
    Maps raw biometric signals to high-level governance metrics.
    Connects to the Bio-Link Python sidecar.
    """

    def __init__(self):
        self.last_heart_rate = 70.0
        self.last_stress_idx = 0.1

    def process_pulse(self, data: Dict[str, Any]) -> Dict[str, float]:
        """
        Processes raw Pulse (Heart Rate, Variability) into a Stress Index.
        """
        hr = data.get("heart_rate", 70.0)
        hrv = data.get("hr_variability", 50.0)

        # Simple heuristic: High HR + Low HRV = High Stress
        # Normal HR: 60-100, Normal HRV: 20-100
        hr_factor = max(0, (hr - 70) / 50.0)  # 0.0 at 70bpm, 1.0 at 120bpm
        hrv_factor = max(0, (50 - hrv) / 40.0)  # 0.0 at 50ms, 1.0 at 10ms

        stress_idx = min(1.0, (hr_factor + hrv_factor) / 2.0)

        self.last_heart_rate = hr
        self.last_stress_idx = stress_idx

        return {
            "heart_rate": hr,
            "stress_index": stress_idx,
            "tau_ethics_contribution": stress_idx
        }


def get_bio_metrics(pulse_data: Dict[str, Any]) -> Dict[str, float]:
    adapter = VitruvianAdapter()
    return adapter.process_pulse(pulse_data)
