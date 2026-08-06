import sys
import os
import logging

# Add project root to path
sys.path.append(os.getcwd())

from warm_logic.core.security.passkey import PasskeyProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PasskeyCheck")


def test_passkey_registration():
    logger.info("Starting WarmLogic Passkey Registration...")
    logger.info(
        "⚠️  Note: This will trigger a macOS system prompt. Please use TouchID or your Passcode."
    )

    provider = PasskeyProvider()

    # Using a test handle and name
    user_handle = "user-1234-resonance"
    user_name = "Resonance-Dev-User"

    credential = provider.register(user_handle, user_name)

    if credential:
        print("\n" + "=" * 50)
        print("PASSKEY REGISTERED SUCCESSFULLY")
        print(f"ID: {credential.get('credentialID')[:20]}...")
        print("=" * 50 + "\n")
        logger.info("Now this credential can be synced via iCloud Keychain.")
    else:
        logger.error("Registration failed or was cancelled.")


if __name__ == "__main__":
    test_passkey_registration()
