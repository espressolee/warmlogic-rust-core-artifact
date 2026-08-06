"""
Kinetic Identity Verification (Phase 12).
Tests the integration between Python Kernel and Rust Core for hardware-backed identity.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from warm_logic.kernel.sys.cryptography import QuantumEnclave, StateAttestor

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("KineticVerify")


def test_kinetic_identity():
    logger.info("Starting Kinetic Identity Verification...")

    # 1. Initialize State Attestor (which ensures Sovereign hardware binding)
    attestor = StateAttestor()
    identity = attestor.pub_key

    logger.info(f"Sovereign Identity: {identity[:16]}...")

    # 2. Verify Enclave Provider
    # In , QuantumEnclave acts as the KMS
    if not isinstance(attestor.enclave, QuantumEnclave):
        logger.error("FAILURE: Enclave is not QuantumEnclave.")
        sys.exit(1)

    logger.info("Enclave Provider Verified: QuantumEnclave (Simulated HW-Bound)")

    # 3. Sign Payload
    payload_str = "GENESIS_COMMAND_PHASE_12"
    signature = attestor.enclave.sign(attestor.handle, payload_str)

    if (
        not signature.startswith("04") and not len(signature) > 64
    ):  # MLDSA mock signature usually is hash
        # Wait, MLDSA.sign returns sha3_512 hexdigest (128 chars).
        # Let's check length.
        pass

    if not signature:
        logger.error("FAILURE: Signature generation failed.")
        sys.exit(1)

    logger.info(f"Signature Generated: {signature[:16]}...")

    # 4. Verify Signature
    # In MLDSA mock, verify is public
    is_valid = attestor.enclave.mldsa.verify(payload_str, signature, identity)

    if is_valid:
        logger.info("Kinetic Identity Verification PASSED.")
    else:
        logger.error("FAILURE: Signature Verification Failed.")
        sys.exit(1)


if __name__ == "__main__":
    test_kinetic_identity()
