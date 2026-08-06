import logging
import os
import sys

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.economy.ledger_token import RefusalToken
from warm_logic.economy.treasury_enclave import treasury

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RefusalTokenTest")


def test_mint_and_verify_token():
    logger.info("Starting Refusal Token Minting Verification")

    # 1. Simulate a Refusal Event Hash
    event_hash = "0xREFUSAL_EVENT_2026_01_27_BEEF"
    gas_cost = 1500  # Economic value burned

    logger.info(f"Minting token for event: {event_hash} (Gas: {gas_cost})")

    # 2. Mint Token
    token = treasury.mint_refusal_token(event_hash, gas_cost)

    logger.info(f"Token Minted: {token.token_id}")
    logger.info(f"   Minter: {token.minter}")
    logger.info(f"   Signature: {token.signature}")

    # 3. Basic Field Verification
    assert token.event_ref == event_hash, "Event reference mismatch"
    assert token.gas_paid == gas_cost, "Gas cost mismatch"
    assert token.signature.startswith("sig_sov_"), "Invalid signature format"

    # 4. ID Consistency Check
    expected_id = RefusalToken.calculate_id(event_hash, token.minter, token.timestamp)
    assert token.token_id == expected_id, "Token ID calculation mismatch"

    # 5. Serialization Check
    json_data = token.to_json()
    logger.info(f"Serialized Token: {json_data}")
    assert '"token_id":' in json_data
    assert event_hash in json_data

    logger.info("\nREFUSAL TOKEN VERIFIED: Economic proof generated and signed.")


if __name__ == "__main__":
    try:
        test_mint_and_verify_token()
    except Exception as e:
        logger.error(f"Verification FAILED: {e}")
        sys.exit(1)
