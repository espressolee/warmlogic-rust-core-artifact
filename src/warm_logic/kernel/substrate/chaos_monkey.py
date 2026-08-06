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
"""
Chaos Monkey
Injects Byzantine faults into the Stitch P2P Network.
"""

import logging
import random
from typing import Any, Callable, Optional

logger = logging.getLogger("ChaosMonkey")


class ChaosMonkey:
    _instance: Optional["ChaosMonkey"] = None
    enabled: bool = False
    drop_rate: float = 0.0
    latency_ms: int = 0
    corruption_rate: float = 0.0

    def __new__(cls) -> "ChaosMonkey":
        if cls._instance is None:
            cls._instance = super(ChaosMonkey, cls).__new__(cls)
            cls._instance.enabled = False
            cls._instance.drop_rate = 0.0
            cls._instance.latency_ms = 0
            cls._instance.corruption_rate = 0.0
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Resets the Chaos Monkey to a disabled, clean state."""
        instance = cls()
        instance.enabled = False
        instance.drop_rate = 0.0
        instance.latency_ms = 0
        instance.corruption_rate = 0.0
        logger.info("[Sovereign Reality] Chaos Monkey reset to safe state.")

    @classmethod
    def configure(
        cls,
        enabled: bool = False,
        drop_rate: float = 0.0,
        latency_ms: int = 0,
        corruption_rate: float = 0.0,
    ) -> None:
        instance = cls()
        instance.enabled = enabled
        instance.drop_rate = drop_rate
        instance.latency_ms = latency_ms
        instance.corruption_rate = corruption_rate
        if enabled:
            # Enforce deterministic chaos if enabled
            random.seed(42)
            logger.critical(
                f"🚨 [REALITY BREACH] Chaos Monkey ENABLED in Production! Drop={drop_rate}, Latency={latency_ms}ms"
            )
        else:
            logger.info(
                "🛡️ [Sovereign Reality] Chaos Monkey disabled (Production Mode)."
            )

    @classmethod
    def apply_middleware(cls, handler: Callable[[Any], None]) -> Callable[[Any], None]:
        """Wraps a handler with chaos logic."""
        instance = cls()

        def wrapper(payload: Any) -> Any:
            if not instance.enabled:
                return handler(payload)

            # 1. Packet Drop
            if random.random() < instance.drop_rate:
                logger.warning("Chaos: Packet DROPPED")
                return None  # Silent drop

            # 2. Latency Injection
            if instance.latency_ms > 0:
                import time

                time.sleep(instance.latency_ms / 1000.0)

            # 3. Payload Corruption
            if (
                instance.corruption_rate > 0
                and random.random() < instance.corruption_rate
            ):
                logger.warning("Chaos: Payload CORRUPTED")
                if isinstance(payload, dict):
                    # Tamper with sig or hash
                    if "hash" in payload:
                        payload["hash"] = "DEADBEEF" * 8
                    if "signature" in payload:
                        payload["signature"] = "INVALID"

            return handler(payload)

        return wrapper
