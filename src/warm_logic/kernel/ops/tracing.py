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
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class TraceContext:
    trace_id: str
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_span_id: Optional[str] = None
    node_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceContext":
        return cls(**data)


class TraceLogger:
    """
    Logs events to specialized trace files for visual tracking in Cockpit.
    """

    def __init__(self, root_path: str = "."):
        self.root = Path(root_path).resolve()
        self.trace_dir = self.root / "out/sovereign/traces"
        os.makedirs(self.trace_dir, exist_ok=True)

    def log_event(self, context: TraceContext, event_type: str, data: Dict[str, Any]):
        trace_file = self.trace_dir / f"{context.trace_id}.jsonl"

        event = {
            "ts": time.time(),
            "node_id": context.node_id,
            "span_id": context.span_id,
            "parent_span_id": context.parent_span_id,
            "type": event_type,
            "data": data,
        }

        try:
            with open(trace_file, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            # Fallback to standard logging if file write fails
            import logging

            logging.getLogger("TraceLogger").warning(
                f"Failed to write trace event: {e}"
            )


# Global singleton for easy access
_global_logger = TraceLogger()


def log_trace(context: TraceContext, event_type: str, **kwargs):
    _global_logger.log_event(context, event_type, kwargs)


def new_trace(node_id: str) -> TraceContext:
    return TraceContext(trace_id=str(uuid.uuid4()), node_id=node_id)
