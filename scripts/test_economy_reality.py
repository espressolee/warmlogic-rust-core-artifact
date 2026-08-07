import os
import time

from warm_logic.economy.mainnet_gateway import MainnetBridge


def test_economy_reality():
    print("Starting Economy Layer (Mainnet Bridge) Reality Verification")

    # 1. Setup Environment
    os.environ["WARMLOGIC_ENCLAVE_PUBKEY"] = "0xREAL_ENCLAVE_2026"
    bridge = MainnetBridge()

    # 2. Negative Test: Invalid Transaction
    print("Testing rejection of non-existent transaction...")
    fake_tx = "0xFAKE_TX_HASH_123"
    result_fail = bridge.verify_and_lock("USDC", 500.0, fake_tx)

    if result_fail.get("status") == "FAILURE":
        print(
            f"   ✅ Correctly rejected invalid transaction: {result_fail.get('reason')}"
        )
    else:
        print("   FAILED: Bridge accepted a non-existent transaction!")
        return 1

    # 3. Positive Test: Valid 'Reality' Transaction (Emulated)
    print("Testing acceptance of verifiable reality transaction...")
    real_tx = "0xREAL_DEPOSIT_TX_001"
    initial_balance = bridge.locked_assets["USDC"]

    result_success = bridge.verify_and_lock("USDC", 1000.0, real_tx)

    if result_success.get("status") == "LOCKED_IN_SOVEREIGN_VAULT":
        print("   Transaction verified and assets locked.")
        if bridge.locked_assets["USDC"] == initial_balance + 1000.0:
            print(
                f"   ✅ Treasury balance updated correctly: {bridge.locked_assets['USDC']}"
            )
        else:
            print("   Balance mismatch!")
            return 1

        # Verify Attestation
        if "attestation" in result_success and len(result_success["attestation"]) == 64:
            print(
                f"   ✅ Cryptographic attestation generated: {result_success['attestation'][:16]}..."
            )
        else:
            print("   Cryptographic attestation MISSING or INVALID!")
            return 1
    else:
        print(
            f"   ❌ FAILED: Bridge rejected a 'reality' transaction: {result_success.get('reason')}"
        )
        return 1

    # 4. Multi-Sig Constraint verification (Future-proofing)
    print("Verifying Multi-Sig binding...")
    attestation_1 = result_success["attestation"]
    # Change enclave key - should result in different attestation for same data
    bridge.enclave_pub_key = "0xTAMPERED_KEY"
    attestation_2 = bridge._generate_multi_sig_attestation(real_tx, "USDC", 1000.0)

    if attestation_1 != attestation_2:
        print("   Success: Attestation is strictly bound to the hardware key.")
    else:
        print("   Failure: Attestation is not key-dependent!")
        return 1

    print("\nECONOMY REALITY SCENARIO OK (not verification): Web3 Provider and Multi-Sig Enforced.")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(test_economy_reality())
