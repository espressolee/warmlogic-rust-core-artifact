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

logger = logging.getLogger("KAIEngine")


class KAIEngine:
    """
    Kinetic Autonomy Index Engine.
    Calculates the system's autonomy score based on four pillars.
    """

    WEIGHTS = {
        "autonomy": 0.3,
        "replication": 0.2,
        "proof": 0.25,
        "sustainability": 0.25,
    }

    def __init__(self):
        # Baseline scores as of
        self.scores = {
            "autonomy": 9.2,
            "replication": 9.5,
            "proof": 8.0,
            "sustainability": 8.8,
        }
        self.entropy_gaps = 0.013  # 1 - 0.987

    def calculate_kai(self, stochastic_creativity: float = 0.0) -> float:
        """
        Calculates the weighted average KAI score.
        [convergence] Stochastic creativity can boost the Sustainability and Autonomy scores.
        """
        # Apply stochastic boost
        current_sustainability = min(
            10.0, self.scores["sustainability"] + (stochastic_creativity * 1.5)
        )
        current_autonomy = min(
            10.0, self.scores["autonomy"] + (stochastic_creativity * 1.0)
        )

        weighted_sum = (
            (current_autonomy * self.WEIGHTS["autonomy"])
            + (self.scores["replication"] * self.WEIGHTS["replication"])
            + (self.scores["proof"] * self.WEIGHTS["proof"])
            + (current_sustainability * self.WEIGHTS["sustainability"])
        )

        # KAI = (Weighted Sum / 10) * (1 - Entropy Gaps) * 100
        kai = (weighted_sum / 1.0) * (1 - self.entropy_gaps) * 10
        return round(kai, 1)

    def get_status_report(self, stochastic_creativity: float = 0.0) -> Dict[str, Any]:
        kai = self.calculate_kai(stochastic_creativity)
        return {
            "kai_score": f"{kai}%",
            "pillars": {
                "Autonomy": f"{self.scores['autonomy']}/10",
                "Replication": f"{self.scores['replication']}/10",
                "Proof": f"{self.scores['proof']}/10",
                "Sustainability": f"{self.scores['sustainability']}/10",
            },
            "status": "SINGULARITY" if kai >= 90.0 else "DETERMINISTIC_LIMIT",
        }
