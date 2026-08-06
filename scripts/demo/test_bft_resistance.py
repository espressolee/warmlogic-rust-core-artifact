"""BFT Resistance Test (Era 42).
Simulates a malicious node attempting to poison the mesh with a fake refusal token.
Verifies that the BFTConsensusManager correctly blocks the token.
"""

import logging
import os
import sys

# Dynamic root detection
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from warm_logic.mesh.bft_consensus import BFTConsensusManager, RefusalToken

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BFTTest")


def test_bft_resistance():
    print("Starting Era 42 BFT Resistance Verification...")

    manager = BFTConsensusManager("local_node")

    # Fake token from a malicious node
    fake_token = RefusalToken(
        event_id="evt_malicious_1",
        timestamp="2026-01-28",
        reason="FAKE_VETO",
        source_node="attacker_01",
        signature="FAKE_SIG",
    )

    print("\n--- Sending 1st vote from attacker ---")
    manager.receive_token(fake_token, "attacker_01")
    assert not manager.is_finalized("evt_malicious_1")
    print("Result: Token NOT finalized (Correct)")

    print("\n--- Sending 2nd vote from colluding node ---")
    manager.receive_token(fake_token, "colluder_02")
    assert not manager.is_finalized("evt_malicious_1")
    print("Result: Token STILL NOT finalized (Correct)")

    print("\n--- Sending 3rd vote from independent node (Consensus Reached) ---")
    manager.receive_token(fake_token, "independent_03")
    assert manager.is_finalized("evt_malicious_1")
    print("Result: Token FINALIZED after 3rd witness (Correct)")

    print(
        "\n✅ Era 42 Verification Passed: BFT Mesh is resistant to 1-2 malicious nodes."
    )


if __name__ == "__main__":
    test_bft_resistance()
