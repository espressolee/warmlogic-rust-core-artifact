import hashlib
import os
from pathlib import Path

from warm_logic.core.security.enclave import NitroProvider, calculate_kernel_hash


def test_enclave_reality():
    print("Starting Enclave Reality Verification")

    # 1. Verify Dynamic PCR10
    print("Checking dynamic PCR10 calculation...")
    os.environ["WARMLOGIC_HW_ROOT_SECRET"] = "TEST_SECRET_KEY_123"

    provider = NitroProvider()
    expected_hash = calculate_kernel_hash()

    print(f"   PCR10 (Kernel Hash): {provider.pcr_10[:16]}...")
    if provider.pcr_10 == expected_hash:
        print("   PCR10 matches kernel directory hash.")
    else:
        print("   PCR10 mismatch!")
        return 1

    # 2. Verify Attestation Report
    print("Verifying Attestation Report...")
    report = provider.get_attestation()
    if report.verify():
        print("   Attestation Report signature is valid.")
    else:
        print("   Attestation Report signature failed verification!")
        return 1

    # 3. Verify PCR-Locked Sealing
    print("Testing PCR-Locked Sealing...")
    secret_data = b"TOP_SECRET_RESONANCE_DATA"
    sealed = provider.seal(secret_data)
    unsealed = provider.unseal(sealed)

    if unsealed == secret_data:
        print("   Seal/Unseal successful with matching PCRs.")
    else:
        print("   Seal/Unseal failed!")
        return 1

    # 4. Verify Integrity Breach (Simulated)
    print("Testing Integrity Breach (Simulating PCR10 change)...")
    # Manually override PCR10 to simulate a different kernel version
    original_pcr10 = provider.pcr_10
    provider.pcr_10 = "CORRUPTED_KERNEL_HASH_000"

    try:
        broken_unseal = provider.unseal(sealed)
        if broken_unseal != secret_data:
            print(
                "   ✅ SUCCESS: Data could not be unsealed correctly after PCR change."
            )
        else:
            print("   FAILURE: Data was unsealed despite PCR change!")
            return 1
    except Exception as e:
        print(f"   SUCCESS: System blocked unsealing due to error: {e}")

    print(
        "\n🎉 ENCLAVE REALITY SCENARIO OK (not verification): High-Fidelity Attestation and Sealing Active."
    )
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(test_enclave_reality())
