#!/usr/bin/env python3
import logging
import os
import sys

# Ensure the project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from warm_logic.core.security.schnorr import (
    SchnorrProof,
    SchnorrProver,
    SchnorrVerifier,
)
from warm_logic.kernel.zkp import FederatedZKP, FederatedZKPProtocol, SchnorrZKP

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("ZKPVerification")


def test_pure_schnorr_math():
    logger.info("Testing Pure Schnorr Math (RFC 3526 Group 14)...")
    prover = SchnorrProver()
    pk = prover.get_public_key()
    proof = prover.prove()

    # 1. Basic acceptance
    assert SchnorrVerifier.verify(pk, proof), "Basic Schnorr verification failed!"
    logger.info("v Basic Proof Verification: SUCCESS")

    # 2. Rejection of forged proof (wrong response)
    fake_proof = SchnorrProof(commitment=proof.commitment, response=proof.response + 1)
    assert not SchnorrVerifier.verify(pk, fake_proof), (
        "Forged proof (wrong response) was accepted!"
    )
    logger.info("v Forged Response Rejection: SUCCESS")

    # 3. Rejection of forged proof (wrong commitment)
    fake_proof_2 = SchnorrProof(
        commitment=proof.commitment + 1, response=proof.response
    )
    assert not SchnorrVerifier.verify(pk, fake_proof_2), (
        "Forged proof (wrong commitment) was accepted!"
    )
    logger.info("v Forged Commitment Rejection: SUCCESS")


def test_schnorr_zkp_wrapper():
    logger.info("Testing SchnorrZKP Wrapper...")
    sk, pk = SchnorrZKP.generate_keypair()
    commitment, response = SchnorrZKP.create_proof(sk)

    assert SchnorrZKP.verify_proof(pk, commitment, response), (
        "SchnorrZKP wrapper verification failed!"
    )
    logger.info("v Wrapper Verification: SUCCESS")


def test_federated_zkp_flow():
    logger.info("Testing FederatedZKP Flow...")
    node_a = FederatedZKP("node-alpha")
    node_b = FederatedZKP("node-beta")

    # Register Node A's PK in Node B
    node_b.register_peer("node-alpha", node_a.get_public_key())

    # Node A creates a compliance proof
    state = {"uptime": 3600, "status": "HEALTHY"}
    proof = node_a.create_compliance_proof(state)

    # Node B verifies Node A's proof
    assert node_b.verify_peer_proof("node-alpha", proof), (
        "Federated peer verification failed!"
    )
    logger.info("v Federated Peer Verification: SUCCESS")

    # Verify state extraction
    extracted_state = node_b.extract_act_state(proof)
    assert extracted_state == state, "State extraction failed!"
    logger.info("v State Extraction: SUCCESS")


def test_protocol_utility():
    logger.info("Testing FederatedZKPProtocol Utility...")
    node_a = FederatedZKP("node-alpha")
    node_b = FederatedZKP("node-beta")
    node_b.register_peer("node-alpha", node_a.get_public_key())

    entry = {"id": 1, "action": "TICK", "act_state": {"tick_count": 100}}
    entry_with_proof = FederatedZKPProtocol.attach_proof_to_entry(node_a, entry)

    assert "zkp_proof" in entry_with_proof, "Proof not attached to entry!"
    assert FederatedZKPProtocol.verify_entry_proof(node_b, entry_with_proof), (
        "Protocol-level entry verification failed!"
    )
    logger.info("v Protocol-Level Verification: SUCCESS")


if __name__ == "__main__":
    logger.info("=== ZKP PERFECTION AUDIT [P999] ===")
    try:
        test_pure_schnorr_math()
        test_schnorr_zkp_wrapper()
        test_federated_zkp_flow()
        test_protocol_utility()
        logger.info("RESULT:  - MATHEMATICAL PERFECTION ACHIEVED.")
    except Exception as e:
        logger.error(f"AUDIT FAILED: {str(e)}")
        sys.exit(1)
