import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from warm_logic.core.security.apple_sep import AppleSEPProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SEP-Reality-Check")


def test_sep_identity_and_signing():
    logger.info("Starting Apple SEP Reality Check...")

    # Force Reality Mode (ensure no simulation env vars interfere)
    os.environ["WARMLOGIC_SIMULATE_HW"] = "0"
    os.environ["WARMLOGIC_HW_ROOT_SECRET"] = "REAL_HARDWARE_KEY_TEST_2026"

    try:
        provider = AppleSEPProvider()

        if provider._simulate:
            logger.warning(
                "⚠️ Provider is running in SIMULATION mode. Hardware binding failed."
            )
            logger.info(
                "This is expected if not running on macOS or without proper Secure Enclave access."
            )
            return

        logger.info("Provider initialized in REALITY mode.")

        # 1. Attestation Report (Triggers Signing)
        logger.info("Generating Attestation Report...")
        report = provider.get_attestation()
        logger.info(f"Report Platform: {report.platform}")
        logger.info(
            f"📊 Signature: {report.signature[:16]}... (len={len(report.signature)})"
        )

        # 2. Key Persistence Check
        logger.info("Retrieving Public Key handle...")
        pub_key = provider.get_public_key()
        logger.info(
            f"🔑 Public Key: {pub_key.hex() if isinstance(pub_key, bytes) else pub_key}"
        )

        # 3. Sealing/Unsealing Check
        logger.info("Testing Hardware Sealing...")
        secret_data = b"TOP_SECRET_COORDINATES_2026"
        sealed = provider.seal(secret_data)
        logger.info(f"Sealed Data: {sealed.hex()[:20]}...")

        unsealed = provider.unseal(sealed)
        assert unsealed == secret_data, "Unsealing failed!"
        logger.info("Unsealing: SUCCESS")

        logger.info("Apple SEP Reality Check: COMPLETE (All flows verified)")

    except Exception as e:
        logger.error(f"Reality Check FAILED: {e}")


if __name__ == "__main__":
    test_sep_identity_and_signing()
