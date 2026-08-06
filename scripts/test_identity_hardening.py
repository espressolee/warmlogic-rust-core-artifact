import os
import sys
import logging

# Ensure we can import warm_logic
sys.path.append(os.getcwd())

from warm_logic.core.security.apple_sep import ICloudStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IdentityHardeningTest")


def test_hardened_bundle():
    account = "test-account-100"
    password = "extremely-secure-password"

    storage = ICloudStorage()

    logger.info("Setting up mock identity...")
    # Directly set a seed in the fallback dir since we are in simulation
    fallback_dir = os.path.expanduser("~/.warmlogic/identity/local_sync")
    os.makedirs(fallback_dir, exist_ok=True)
    seed_path = os.path.join(fallback_dir, f"{account}.seed")

    # Create a mock sealed seed
    with open(seed_path, "wb") as f:
        # Simple simulated seal
        f.write(b"SEP_REAL_SEAL_v1:" + b"MOCK_SEED_DATA_12345678901234567890")

    logger.info("Creating hardened v2 bundle...")
    bundle = storage.create_portable_bundle(account, password)

    if not bundle:
        logger.error("Failed to create bundle")
        return

    logger.info(f"Bundle created (len={len(bundle)}). Header: {bundle[:8].decode()}")

    if not bundle.startswith(b"WLID_v2:"):
        logger.error("Bundle is not v2!")
        return

    logger.info("Restoring from hardened v2 bundle...")
    # Clear "local" seed to ensure restoration works
    os.remove(seed_path)

    success = storage.restore_from_bundle(account, bundle, password)

    if success and os.path.exists(seed_path):
        logger.info("Identity Hardening Verified: Dynamic PBE (v2) successful.")
    else:
        logger.error("Restoration failed!")


if __name__ == "__main__":
    test_hardened_bundle()
