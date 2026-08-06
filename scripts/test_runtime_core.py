import sys
import os
import json

# Ensure we can import warm_logic
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print(f"DEBUG: sys.path[0] = {sys.path[0]}")
try:
    import warm_logic

    print(f"DEBUG: warm_logic file = {warm_logic.__file__}")
    print(f"DEBUG: warm_logic path = {warm_logic.__path__}")
except ImportError as e:
    print(f"DEBUG: Could not import warm_logic: {e}")

from warm_logic.core.runtime.compiler import PassCompiler, strict_no_pii_policy


def test_p999_conformance_basic():
    print(">>> Starting P999 Basic Conformance Test...")

    compiler = PassCompiler(identity_key="TEST:UNIT_TESTER")

    # CASE 1: Valid Input (PASS)
    print("\n[Test 1] Valid Input -> PASS Packet")
    artifacts_good = ["safe_data_block_1", "config_yaml"]
    packet_good = compiler.compile_intent(
        artifacts_good, strict_no_pii_policy, "policy:no_pii_v1"
    )
    compiler.sign_packet(packet_good)

    # Audit Structure
    assert packet_good.decision.verdict == "PASS", (
        f"Expected PASS, got {packet_good.decision.verdict}"
    )
    assert packet_good.signature is not None, "Packet must be signed"
    assert packet_good.decision.ce_ref is None, "PASS packet should not have CE Ref"
    print(f"PASS verified. ID: {packet_good.packet_id}")
    print(json.dumps(packet_good.model_dump(), indent=2))

    # CASE 2: Invalid Input (FAIL + CE Ref)
    print("\n[Test 2] Invalid Input (PII) -> FAIL Packet + CE Ledger")
    artifacts_bad = ["user_db_export_PII", "config_yaml"]
    packet_bad = compiler.compile_intent(
        artifacts_bad, strict_no_pii_policy, "policy:no_pii_v1"
    )
    compiler.sign_packet(packet_bad)

    # Audit Structure
    assert packet_bad.decision.verdict == "FAIL", (
        f"Expected FAIL, got {packet_bad.decision.verdict}"
    )
    assert packet_bad.decision.ce_ref is not None, "FAIL packet MUST have CE Ref"
    assert "CE-" in packet_bad.decision.ce_ref, "CE Ref format invalid"
    print(f"FAIL verified. CE Ref: {packet_bad.decision.ce_ref}")
    print(f"Verdict: {packet_bad.decision.verdict}")

    print("\n>>> P999 Conformance Test Passed (Local Runtime).")


if __name__ == "__main__":
    test_p999_conformance_basic()
