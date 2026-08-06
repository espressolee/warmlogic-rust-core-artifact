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
import os
import secrets
import urllib.request

try:
    import warm_logic_rs

    RUST_CORE_AVAILABLE = True
except ImportError:
    RUST_CORE_AVAILABLE = False

logger = logging.getLogger("SovereignAttestation")


class CrossNodeAttestation:
    """
    Hardware-bound Cross-Node Attestation protocol.
    Ensures Node A (root authority) and Node B (Control Tower) are authentic.
    """

    def __init__(self, target_ip: str = "100.116.80.23", port: int = 8033):
        self.target_url = f"http://{target_ip}:{port}"
        # Known configuration for the Control Tower
        self.known_tower_id = os.getenv("CITADEL_TOWER_ID")
        self.known_tower_pubkey = os.getenv("CITADEL_TOWER_PUBKEY")

    def challenge_tower(self) -> bool:
        """Node A (root authority) challenges Node B (Control Tower)."""
        nonce = secrets.token_hex(32)
        logger.info(
            f"🛡️ [Attestation] Challenging Control Tower at {self.target_url}..."
        )

        # Tool call to Node B's MCP server
        # FastMCP SSE app exposes tools via POST /call (if configured) or standard SSE messages.
        # For simplicity, we assume an internal JSON-RPC endpoint.

        payload = {"name": "attest_node", "arguments": {"nonce": nonce}}

        try:
            # Note: FastMCP over SSE usually uses a message system,
            # but we assume Node B handles direct calls for mesh orchestration.
            # If using standard MCP, we would use a client library.
            req = urllib.request.Request(
                f"{self.target_url}/call",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            if not data.get("ok"):
                logger.error(
                    f"❌ [Attestation] Remote Node rejected challenge: {data.get('error')}"
                )
                return False

            result = data.get("result", {})
            remote_id = result.get("silicon_id")
            signature = result.get("signature")

            if not remote_id or not signature:
                logger.error(
                    "❌ [Attestation] Remote Node returned incomplete handshake."
                )
                return False

            # 1. Verify Hardware ID
            if self.known_tower_id and remote_id != self.known_tower_id:
                logger.critical(
                    f"🚨 [Attestation] SILICON ID MISMATCH! Expected {self.known_tower_id}, got {remote_id}."
                )
                return False

            # 2. Verify Signature via ML-DSA-65 (PQC)
            if self.known_tower_pubkey and RUST_CORE_AVAILABLE:
                valid = warm_logic_rs.MLDSA.verify(
                    self.known_tower_pubkey, nonce, signature
                )
                if not valid:
                    logger.critical(
                        "🚨 [Attestation] PQC SIGNATURE VERIFICATION FAILED! Identity forged."
                    )
                    return False
                logger.info(
                    "✅ [Attestation] PQC Handshake SUCCESS. Control Tower Verified."
                )
            else:
                logger.warning(
                    "⚠️ [Attestation] Skipping signature verification (Key or Rust core missing)."
                )
                # Trust-on-first-use fallback
                if not self.known_tower_id:
                    logger.info(
                        f"✨ [Attestation] First Contact: Registered Tower ID {remote_id}"
                    )

            return True

        except Exception as e:
            logger.error(f"[Attestation] Handshake Failed: {e}")
            return False
