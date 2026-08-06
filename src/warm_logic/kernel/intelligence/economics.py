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
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("SovereignEconomics")

# Global Pricing Table (Cost per 1M tokens in USD)
# [Phase 55.6.1] Standardized Prices (Feb 2026)
PRICING = {
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "claude-3-5-sonnet-latest": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "models/warmlogic-v1-fused": {"input": 0.0, "output": 0.0},  # Local is Free
    "default": {"input": 1.0, "output": 2.0},
}


class UsageRecord:
    def __init__(self, model: str, prompt_tokens: int, completion_tokens: int):
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.timestamp = time.time()

        # Calculate Cost
        rates = PRICING.get(model, PRICING["default"])
        self.cost = (prompt_tokens / 1_000_000) * rates["input"] + (
            completion_tokens / 1_000_000
        ) * rates["output"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": self.cost,
        }


class EconomicsManager:
    """
    [Phase 55.6.2] The Treasurer of Sovereignty.
    Tracks, persists, and caps LLM expenditures.
    """

    def __init__(self, log_dir: str = "out/economics"):
        self.log_path = Path(log_dir) / "usage.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self.total_cost = 0.0
        self.total_tokens = 0
        self._load_session_stats()

    def _load_session_stats(self):
        """Loads stats from the current log file to maintain session continuity."""
        if not self.log_path.exists():
            return

        try:
            with open(self.log_path, "r") as f:
                for line in f:
                    data = json.loads(line)
                    self.total_cost += data.get("cost_usd", 0.0)
                    self.total_tokens += data.get("prompt_tokens", 0) + data.get(
                        "completion_tokens", 0
                    )
        except Exception as e:
            logger.error(f"Failed to load economics logs: {e}")

    def record_usage(self, model: str, usage_data: Dict[str, int]) -> float:
        """Records usage and returns the cost of the current transaction."""
        prompt = usage_data.get("prompt_tokens", 0)
        completion = usage_data.get("completion_tokens", 0)

        record = UsageRecord(model, prompt, completion)

        # Update session totals
        self.total_cost += record.cost
        self.total_tokens += prompt + completion

        # Persist
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist usage record: {e}")

        logger.info(
            f"💰 [Economics] Usage Recorded. Cost: ${record.cost:.6f}. "
            f"Session Total: ${self.total_cost:.4f}"
        )
        return record.cost

    def is_within_budget(
        self, max_cost: float = 10.0, max_tokens: int = 1_000_000
    ) -> bool:
        """Checks if the session is still within economic safety bounds."""
        if self.total_cost > max_cost:
            logger.warning(
                f"⚠️ [Economics] COST LIMIT REACHED: ${self.total_cost:.2f} > ${max_cost:.2f}"
            )
            return False

        if self.total_tokens > max_tokens:
            logger.warning(
                f"⚠️ [Economics] TOKEN LIMIT REACHED: {self.total_tokens} > {max_tokens}"
            )
            return False

        return True
