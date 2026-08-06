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
[Phase 113] Real-time API and Edge Deployment.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List

logger = logging.getLogger("RealTimeAPI")


class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    STREAM = "stream"
    ERROR = "error"


@dataclass
class RealtimeMessage:
    id: str
    type: MessageType
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class RealtimeAPIServer:
    """[Phase 113.3] Real-time API with WebSocket."""

    def __init__(self, max_conn: int = 1000, rate_limit: int = 100) -> None:
        self.max_conn = max_conn
        self.rate_limit = rate_limit
        self.connections: Dict[str, Dict] = {}
        self.handlers: Dict[str, Callable] = {}
        self._counter = 0
        self._rates: Dict[str, List[float]] = {}
        logger.info(f"[RealTimeAPI] Active. Max: {max_conn}")

    def connect(self, client_id: str) -> bool:
        if len(self.connections) >= self.max_conn:
            return False
        self.connections[client_id] = {"time": time.time()}
        return True

    def disconnect(self, client_id: str) -> None:
        self.connections.pop(client_id, None)

    def process(self, client_id: str, msg: RealtimeMessage) -> RealtimeMessage:
        self._counter += 1
        action = msg.payload.get("action")

        if action in self.handlers:
            result = self.handlers[action](msg.payload)
            return RealtimeMessage(
                f"M{self._counter}", MessageType.RESPONSE, {"result": result}
            )
        return RealtimeMessage(
            f"M{self._counter}", MessageType.ERROR, {"error": "unknown"}
        )

    def get_stats(self) -> Dict:
        return {"connections": len(self.connections), "max": self.max_conn}


class EdgeRuntime:
    """[Phase 113.2] Edge Runtime."""

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}
        self.initialized = True
        logger.info("[EdgeRuntime] Active.")

    def infer(self, data: Dict) -> Dict:
        start = time.time()
        key = str(sorted(data.items()))
        if key in self._cache:
            return {
                "result": self._cache[key],
                "cached": True,
                "ms": (time.time() - start) * 1000,
            }

        result = {"processed": True}
        self._cache[key] = result
        return {"result": result, "cached": False, "ms": (time.time() - start) * 1000}


class PerformanceOptimizer:
    """[Phase 113.1] Performance utilities."""

    def __init__(self) -> None:
        self.timings: Dict[str, List[float]] = {}
        logger.info("[PerfOptimizer] Active.")

    def record(self, name: str, elapsed: float) -> None:
        if name not in self.timings:
            self.timings[name] = []
        self.timings[name].append(elapsed)

    def get_stats(self, name: str) -> Dict:
        if name not in self.timings:
            return {}
        t = self.timings[name]
        return {
            "count": len(t),
            "avg_ms": sum(t) / len(t) * 1000,
            "max_ms": max(t) * 1000,
        }


def get_realtime_server() -> RealtimeAPIServer:
    return RealtimeAPIServer()


def get_edge_runtime() -> EdgeRuntime:
    return EdgeRuntime()


def get_optimizer() -> PerformanceOptimizer:
    return PerformanceOptimizer()
