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
Proof Generator
Simulates a zkVM (Succinct SP1) execution proof.
Binds context and verdict to a cryptographic commitment.
"""

import hashlib
import json
import logging
from typing import Any, Dict

logger = logging.getLogger("ProofGenerator")


class ProofGenerator:
    """
    Generates a 'Sovereign Proof' for a policy execution.
    In a real system, this would be an SP1 proof from a compiled Rust program.
    """

    @staticmethod
    def generate_proof(context: Dict[str, Any], verdict: bool) -> str:
        """
        Generates a real cryptographic Sigma proof via Rust Core.
        Binds the context hash and verdict to a Bulletproofs-lite commitment.
        """
        from warm_logic.kernel.rust_loader import HAS_RUST_CORE, rust_core

        if not HAS_RUST_CORE or rust_core is None:
            raise RuntimeError(
                "CRITICAL: Rust Core missing. Cannot generate zkVM proofs."
            )

        # 1. Canonicalize and hash the context
        ctx_json = json.dumps(context, sort_keys=True)
        ctx_hash = hashlib.sha256(ctx_json.encode()).hexdigest()

        # 2. Encode verdict into a numeric value for the Sigma proof
        # 1 for True, 0 for False (Signal only)
        val = 1 if verdict else 0
        blinding = hashlib.sha256(f"blind:{ctx_hash}".encode()).hexdigest()

        try:
            gen = rust_core.RustZKProofGenerator()
            # Generate the proof using the value and deterministic blinding
            zkp = gen.generate_state_proof(val, blinding)

            proof_obj = {
                "prefix": "zkp_v2_sigma_sp1",
                "commitment": str(zkp.commitment_hex),
                "proof": str(zkp.proof_hex),
                "meta": {
                    "ctx_hash": ctx_hash,
                    "verdict": verdict,
                },
            }
            logger.info(f"[ProofGen] Sigma Proof generated for {ctx_hash[:8]}")
            return json.dumps(proof_obj)
        except Exception as e:
            logger.error(f"[ProofGen] Sigma Generation Failed: {e}")
            raise RuntimeError(f"zkVM Proof Generation Failed: {e}")

    @staticmethod
    def verify_proof(proof_json: str, context: Dict[str, Any], verdict: bool) -> bool:
        """
        Verifies a Sigma proof via Rust Core.
        """
        from warm_logic.kernel.rust_loader import HAS_RUST_CORE, rust_core

        if not HAS_RUST_CORE or rust_core is None:
            return False

        try:
            proof_obj = json.loads(proof_json)
            if proof_obj.get("prefix") != "zkp_v2_sigma_sp1":
                return False

            # Verify context hash matches
            ctx_json = json.dumps(context, sort_keys=True)
            ctx_hash = hashlib.sha256(ctx_json.encode()).hexdigest()
            if proof_obj["meta"]["ctx_hash"] != ctx_hash:
                return False

            # Verify verdict matches
            if proof_obj["meta"]["verdict"] != verdict:
                return False

            gen = rust_core.RustZKProofGenerator()
            result = gen.verify_state_proof(proof_obj["proof"], proof_obj["commitment"])
            return bool(result)
        except Exception:
            return False
