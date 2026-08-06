import json
import os
import socket
import subprocess
import time
from pathlib import Path


def run_test():
    print("[TEST] Phase 19: ZK-Evolution (Mathematical Invariants)")

    # 1. Start a Sovereign Node
    # Use a dummy port for testing
    PORT = 5005
    node_process = subprocess.Popen(
        [".venv/bin/python3", "warm_logic/main.py"],
        env={
            **os.environ,
            "WARMLOGIC_NODE_PORT": str(PORT),
            "SOVEREIGN_MESH_ENABLED": "1",
        },
    )
    time.sleep(3)  # Wait for startup

    try:
        # 2. Case 1: Valid Evolution with Mathematical Proof
        print("\n--- CASE 1: Valid ZK-Evolution ---")
        subprocess.run(
            [
                ".venv/bin/python3",
                "scripts/omega_patch.py",
                f"localhost:{PORT}",
                "2.0.0",
            ],
            check=True,
        )
        time.sleep(2)  # Give time to process

        # 3. Case 2: Tampered Invariant Proof (Invalid JSON)
        print("\n--- CASE 2: Invalid Proof Format ---")
        # Manually craft a bad packet
        bad_bundle = {
            "version": "2.1.0",
            "binary_hash": "abc123789",
            "invariant_proof": "NOT_JSON_OR_TAMPERED",
            "signature": "deadbeef",
        }
        send_packet(PORT, "UPGRADE_PROPOSAL", bad_bundle)
        time.sleep(2)

        # 4. Case 3: Invariant Violation (Bad Latch Logic Hash)
        print("\n--- CASE 3: Invariant Violation (Tampered Latch logic) ---")
        bad_proof = {
            "latch_integrity": "BAD_HASH_ATTEMPTING_TO_BYPASS_SECURITY",
            "owner_consistency": "7987979",  # dummy
        }
        bad_bundle_2 = {
            "version": "2.2.0",
            "binary_hash": "abc123123",
            "invariant_proof": json.dumps(bad_proof),
            "signature": "cafebabe",  # signature verification comes AFTER proof in gate.rs or will fail too
        }
        send_packet(PORT, "UPGRADE_PROPOSAL", bad_bundle_2)
        time.sleep(2)

    finally:
        node_process.terminate()
        print("\n[TEST] ZK-Evolution Integration Test Completed.")


def send_packet(port, payload_type, bundle):
    packet = {
        "sender": "TEST_HACKER",
        "term": 999,
        "payload": payload_type,
        "signature": json.dumps(bundle),
    }
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("localhost", port))
        s.sendall(json.dumps(packet).encode())


if __name__ == "__main__":
    run_test()
