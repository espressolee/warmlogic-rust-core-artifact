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
from __future__ import annotations

import json
import logging
import struct

logger = logging.getLogger("Protocol")
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

# Consolidated Base Protocol & Schemas
# -----------------------------------------------------------------------------

# --- PACKET FRAMING (HGP) ---

MSG_HEARTBEAT = 0x01
MSG_COMMAND = 0x02


@dataclass
class HeartbeatPayload:
    state_hash: str
    ethical_status: bool

    def to_bytes(self) -> bytes:
        return f"{self.state_hash}:{int(self.ethical_status)}".encode()


@dataclass
class HGPFrame:
    msg_type: int
    payload: bytes
    timestamp: float

    def pack(self) -> bytes:
        payload_len = len(self.payload)
        header = struct.pack("IdI", self.msg_type, self.timestamp, payload_len)
        return header + self.payload

    @classmethod
    def unpack(cls, data: bytes) -> "HGPFrame":
        header_len = struct.calcsize("IdI")
        msg_type, timestamp, payload_len = struct.unpack("IdI", data[:header_len])
        payload = data[header_len : header_len + payload_len]
        return cls(msg_type, payload, timestamp)


# --- RESULT TYPES ---


@dataclass
class OperationStatus:
    status: str = "ok"
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "meta": self.meta}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OperationStatus":
        return cls(status=data.get("status", "ok"), meta=data.get("meta", {}))


# --- SPEC & SCHEMA LOADERS ---


def load_ct_spec(path: Path | None = None) -> Dict[str, Any]:
    """Loads a CT specification from a JSON file."""
    if path is None:
        path = Path("config/ct_spec.json")

    if not path.exists():
        logger.warning(
            f"CT Spec file missing at {path}. Returning baseline safety spec."
        )
        # Minimal baseline for safety
        return {"version": "0.1", "allow_anonymous": False, "max_value": 0}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Verify it's a dict
        if not isinstance(data, dict):
            return {}
        return data
    except Exception as e:
        logger.error(f"Failed to parse CT Spec at {path}: {e}")
        raise RuntimeError(f"CRITICAL: Integrity breach in CT Specification: {e}")


def load_json_schema(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


def load_yaml_schema(path: Path) -> Dict[str, Any]:
    import yaml

    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


# --- Legacy Symbol Stubs DELETED ---
