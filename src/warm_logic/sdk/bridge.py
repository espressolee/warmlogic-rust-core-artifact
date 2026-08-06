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
Sovereign ABI Bridge
Provides hardened serialization and communication between Python and Rust.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from warm_logic.kernel import rust_loader


class SovereignBridge:
    """
    Implements the Inter-Service Bus (ISB) for the Sovereign ABI.
    Enforces a strict serialization boundary for memory isolation.
    """

    @staticmethod
    def serialize_intent(
        agent_id: str,
        action_type: str,
        payload: Any,
        signature: str | None = None,
        metadata: bytes | None = None,
    ) -> bytes:
        """Serialize intent into a bytes payload for the Rust bridge."""
        intent_dict = {
            "agent_id": agent_id,
            "action_type": action_type,
            "payload": json.dumps(payload, sort_keys=True),
            "signature": signature,
            "metadata": list(metadata) if metadata else [],
        }
        return json.dumps(intent_dict).encode("utf-8")

    @staticmethod
    def deserialize_verdict(verdict_bytes: bytes) -> Dict[str, Any]:
        """Deserialize bytes from Rust into a verdict dictionary."""
        result = json.loads(verdict_bytes.decode("utf-8"))
        return dict(result) if isinstance(result, dict) else {"data": result}

    @classmethod
    def evaluate_hardened(
        cls, agent_id: str, action_type: str, payload: Any, signature: str | None = None
    ) -> Dict[str, Any]:
        """
        Executes a hardened evaluation via the Rust MoralGateway.
        Uses explicit serialization to ensure memory isolation.
        """
        if not rust_loader.HAS_RUST_CORE:
            raise RuntimeError("Rust Core required for hardened ABI")

        rs = rust_loader.load_rust_core()
        gateway = rs.MoralGateway()

        # 1. Serialize (O(N) copy)
        serialized_intent = cls.serialize_intent(
            agent_id, action_type, payload, signature
        )

        # 2. Call Rust Hardened FFI (O(N) copy into Rust memory)
        verdict_bytes = gateway.evaluate_intent_hardened(serialized_intent)

        # 3. Deserialize (O(N) copy into Python memory)
        return cls.deserialize_verdict(verdict_bytes)
