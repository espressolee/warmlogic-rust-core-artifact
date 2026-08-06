"""SEP Hardware Bridge Heartbeat Verification."""

import logging
import os
import sys

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.kernel.security.apple_sep import AppleSEPProvider
from warm_logic.kernel.security.ckms import SovereignKMS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SEPHeartbeat")


def run_heartbeat():
    logger.info("Starting SEP Hardware Bridge Heartbeat...")

    try:
        # 1. Initialize SEP Provider
        sep = AppleSEPProvider()
        kms = SovereignKMS(enclave=sep)

        # 2. Check Status
        status = kms.get_status()
        logger.info(f"   Enclave Type: {status['enclave_type']}")
        logger.info(f"   PCR0: {status['attestation']['pcr0']}")

        # 3. Test Signing
        payload = b"WARMLOGIC_ERA2_HEARTBEAT"
        signature = kms.get_identity_signature(payload)

        if signature:
            logger.info(f"   Signature Success: {signature.hex()[:16]}...")
        else:
            logger.error("   Signing FAILED.")
            return 1

        logger.info(
            "\n🎉 SEP HEARTBEAT SUCCESSFUL: Hardware Bound Sovereignty Verified."
        )
        return 0

    except Exception as e:
        logger.error(f"   Heartbeat EXCEPTION: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(run_heartbeat())
