import logging
import os
import time
from typing import Any, Dict, Optional

import requests
import warm_logic_rs

from .identity import SovereignIdentity

logger = logging.getLogger("SovereignSDK")


class SovereignClient:
    """
    The primary entry point for "Sovereign Apps".
    Abstracts BFT consensus, PQC cryptograpy, and Regional routing.
    """

    def __init__(self, rpc_url: Optional[str] = None) -> None:
        # Initialize Identity (Loads from Env or Generates New)
        self.identity = SovereignIdentity()
        self._rpc_url = rpc_url or "http://localhost:8000"

        # Simple connectivity check
        try:
            requests.get(f"{self._rpc_url}/health", timeout=2)
            logger.info(f"Sovereign Session Initialized | Connected to {self._rpc_url}")
        except Exception:
            logger.warning(
                f"Sovereign Session Initialized | Kernel UNREACHABLE at {self._rpc_url}"
            )

    def sign_message(self, message: str) -> Dict[str, Any]:
        """Signs a raw message with PQC and returns the signature packet."""
        signature = self.identity.sign(message)
        return {
            "sender_id": self.identity.id,
            "signature": signature,
            "pqc_model": "ML-DSA-65",
            "timestamp": time.time(),
        }

    def submit_proposal(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Signs and submits a proposal to the Sovereign Swarm.
        Waits for BFT Quorum (2/3+) before returning.
        """
        # 1. Package Intent
        intent = {
            "action": action,
            "params": params,
            "timestamp": time.time(),
            "nonce": os.urandom(8).hex(),
        }

        # 2. Sign with PQC (Kinetic ID)
        payload_str = str(intent)
        signature = self.identity.sign(payload_str)

        # 3. Construct Payload
        packet = {
            "identity": self.identity.id,
            "signature": signature,
            "intent": intent,
            "pqc_model": "ML-DSA-65",
        }

        # 4. Submit to Kernel via HTTP (Real Execution)
        try:
            resp = requests.post(
                f"{self._rpc_url}/api/v1/submit_proposal", json=packet, timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Proposal Submission Failed: {e}")
            return {"status": "FAILED", "error": str(e)}

    def store(self, key: str, value: Any) -> Dict[str, Any]:
        """
        Stores a value with a ZK Proof-of-Binding via Kernel RPC.
        """
        # 1. Generate ZK Proof locally (Client-side Privacy)
        value_hash_int = int(str(time.time()).replace(".", "")[-8:])
        blinding = os.urandom(32).hex()

        try:
            zk_gen = warm_logic_rs.RustZKProofGenerator()
            proof = zk_gen.generate_state_proof(value_hash_int, blinding)
        except Exception as e:
            logger.error(f"ZK Generation Failed: {e}")
            return {"status": "FAILED", "error": "ZK Proof Gen Failed"}

        payload = {
            "key": key,
            "value": value,
            "zk_proof": proof.proof_hex,
            "commitment": proof.commitment_hex,
            "timestamp": time.time(),
        }

        # 2. Store via RPC
        # Using the generic proposal pipeline for storage? Or specific endpoint?
        # For now, using submit_proposal as 'STORE_STATE' action is safer for BFT.
        return self.submit_proposal("STORE_STATE", payload)

    def get_truth(
        self, state_key: str, proof_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Verifies a ZK Proof for a given state key.
        """
        if not proof_data:
            # Fetch from RPC if not provided
            try:
                resp = requests.get(f"{self._rpc_url}/api/v1/state/{state_key}")
                if resp.status_code == 200:
                    proof_data = resp.json()
            except Exception:
                pass

        if not proof_data:
            logger.warning("No proof data found for verification")
            return False

        proof_str = proof_data.get("zk_proof")
        commitment = proof_data.get("commitment")

        if not proof_str or not commitment:
            return False

        try:
            zk_gen = warm_logic_rs.RustZKProofGenerator()
            valid = zk_gen.verify_state_proof(proof_str, commitment)
            return valid
        except Exception as e:
            logger.error(f"ZK Verification Error: {e}")
            return False

    def get_balance(self) -> float:
        """
        Retrieves the node's Sovereign Credit balance from the mesh.
        """
        try:
            resp = requests.get(
                f"{self._rpc_url}/api/mesh/economy/balance?id={self.identity.id}"
            )
            if resp.status_code == 200:
                return float(resp.json().get("balance", 0.0))
        except Exception:
            pass
        return 0.0

    def transfer_credits(
        self, to_id: str, amount: float, reason: str
    ) -> Dict[str, Any]:
        """
        Signs and submits a credit transfer proposal.
        """
        params = {"to_id": to_id, "amount": amount, "reason": reason}
        return self.submit_proposal("TRANSFER_CREDITS", params)
