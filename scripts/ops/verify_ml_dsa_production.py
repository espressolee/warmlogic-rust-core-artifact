import os
import sys

# Add the localized extension path and project root
ext_path = os.path.join(os.getcwd(), "warm_logic_rs", "python_packages")
sys.path.insert(0, ext_path)
sys.path.insert(1, os.getcwd())

try:
    import warm_logic_rs

    print("Successfully imported warm_logic_rs production core.")
except ImportError as e:
    print(f"FAILED to import warm_logic_rs: {e}")
    sys.exit(1)


def test_ml_dsa():
    print("Testing ML-DSA-65 (FIPS 204) Production Logic...")

    # 1. Key Generation
    pk, sk = warm_logic_rs.generate_keypair()
    print(
        f"Generated Keys:\n  PK: {pk[:32]}... ({len(pk) // 2} bytes)\n  SK: {sk[:32]}... ({len(sk) // 2} bytes)"
    )

    assert len(pk) == 1952 * 2, f"Invalid PK size: {len(pk) // 2}"
    assert len(sk) == 4032 * 2, f"Invalid SK size: {len(sk) // 2}"

    # 2. Signing
    message = "WarmLogic Kinetic Intent: ERA 500 Production Release"
    sig = warm_logic_rs.sign(sk, message)
    print(f"Generated Signature:\n  SIG: {sig[:32]}... ({len(sig) // 2} bytes)")

    assert len(sig) == 3309 * 2, f"Invalid Signature size: {len(sig) // 2}"

    # 3. Verification
    valid = warm_logic_rs.verify(pk, message, sig)
    print(f"Verification Result: {'PASS' if valid else 'FAIL'}")
    assert valid, "ML-DSA Verification FAILED for valid signature"

    # 4. Tamper Test
    tampered_msg = message + "!"
    invalid = warm_logic_rs.verify(pk, tampered_msg, sig)
    print(f"Tamper Verification Result: {'STABLE' if not invalid else 'COMPROMISED'}")
    assert not invalid, "ML-DSA Verification SUCCEEDED for tampered message"

    print("\n[SUCCESS] ML-DSA-65 production integration verified.")


if __name__ == "__main__":
    test_ml_dsa()
