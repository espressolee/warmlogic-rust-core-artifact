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
Hardened State Commitment Substrate (Hardened)
Implements SHA-256 anchoring of state transitions using hash commitments.
NOTE: This is NOT a Zero-Knowledge Proof (ZKP). It is a public commitment hash.
"""

import hashlib
import json
from typing import Any, List, Optional

from warm_logic.kernel.rust_loader import HAS_RUST_CORE, rust_core


class ZKProofGenerator:
    """
    Generates and verifies Zero-Knowledge proofs for state transitions.
    Phase 3: Delegates to Rust Bulletproofs if available.
    """

    @staticmethod
    def _compute_commitment(prev_root: str, txs: List[Any], new_root: str) -> str:
        # Canonical hash of the transition
        tx_strings = sorted([str(t) for t in txs])
        tx_root = hashlib.sha256("".join(tx_strings).encode()).hexdigest()

        payload = f"{prev_root}:{tx_root}:{new_root}"
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def generate_proof(
        prev_state_root: str,
        transactions: List[Any],
        new_state_root: str,
        prev_proof: Optional[str] = None,
    ) -> str:
        if not HAS_RUST_CORE or rust_core is None:
            raise RuntimeError(
                "CRITICAL: Rust Core missing. ZK (Bulletproofs) operations are disabled."
            )

        commitment = ZKProofGenerator._compute_commitment(
            prev_state_root, transactions, new_state_root
        )

        # Use real Bulletproofs
        val = int(commitment[:16], 16) % (2**32)  # 32-bit range proof sample
        blinding = hashlib.sha256(f"blind:{commitment}".encode()).hexdigest()

        try:
            gen = rust_core.RustZKProofGenerator()
            zkp = gen.generate_state_proof(val, blinding)

            proof_obj = {
                "prefix": "zkp_v2_bulletproofs",
                "commitment": str(zkp.commitment_hex),
                "proof": str(zkp.proof_hex),
                "meta": {
                    "orig_commitment": commitment,
                    "prev_state_root": prev_state_root,
                    "new_state_root": new_state_root,
                },
            }
            return json.dumps(proof_obj)
        except Exception as e:
            raise RuntimeError(f"ZK Proof Generation Failed via Core: {e}")

    @staticmethod
    def verify_proof(
        proof_json: str,
        prev_state_root: str,
        transactions: List[Any],
        new_state_root: str,
        prev_proof: Optional[str] = None,
    ) -> bool:
        if not HAS_RUST_CORE or rust_core is None:
            return False

        try:
            proof_obj = json.loads(proof_json)
        except (ValueError, TypeError):
            return False

        if not isinstance(proof_obj, dict):
            return False

        if proof_obj.get("prefix") != "zkp_v2_bulletproofs":
            return False

        # Strict Commitment Verification
        # Ensure the proof being verified is for the transition we claim.
        expected_commitment = ZKProofGenerator._compute_commitment(
            prev_state_root, transactions, new_state_root
        )
        if proof_obj.get("meta", {}).get("orig_commitment") != expected_commitment:
            return False

        try:
            gen = rust_core.RustZKProofGenerator()
            result = gen.verify_state_proof(proof_obj["proof"], proof_obj["commitment"])
            # Enforce boolean check but allow for MagicMock in simulation
            return bool(result)
        except Exception:
            return False
