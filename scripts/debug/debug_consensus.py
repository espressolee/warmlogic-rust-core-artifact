import hashlib

from warm_logic.kernel.sys.consensus import BFTEngine, Vote
from warm_logic.kernel.sys.cryptography import MLDSA, PQCKeypair


def debug_consensus():
    # Use real SHA256 hash
    block_hash = hashlib.sha256(b"block1").hexdigest()
    print(f"Testing with Hash: {block_hash}")

    signer = MLDSA()
    kp1 = signer.generate_keypair()
    kp2 = signer.generate_keypair()
    kp3 = signer.generate_keypair()
    kp4 = signer.generate_keypair()

    # Hypothesis: Maybe Rust needs simple format like block_hash byte string?
    # But Vote takes string.

    # Try start_round(0)
    print("\n=== TEST 5: Round 0 + SHA256 Hash + Format loop ===")

    formats = [
        block_hash,
        f"VOTE:{block_hash}",
    ]

    for fmt in formats:
        print(f"Format: {fmt}")
        e = BFTEngine(4)
        e.start_round(0)  # Round 0
        e.propose(block_hash)

        # Vote 1
        s1 = signer.sign(fmt, kp1.private_key)
        v1 = Vote(block_hash, kp1.public_key, s1)
        print(f"  V1: {e.cast_vote(v1)}")

        # Vote 2
        s2 = signer.sign(fmt, kp2.private_key)
        v2 = Vote(block_hash, kp2.public_key, s2)
        print(f"  V2: {e.cast_vote(v2)}")

        # Vote 3
        s3 = signer.sign(fmt, kp3.private_key)
        v3 = Vote(block_hash, kp3.public_key, s3)
        print(f"  V3: {e.cast_vote(v3)}")

        # Vote 4
        s4 = signer.sign(fmt, kp4.private_key)
        v4 = Vote(block_hash, kp4.public_key, s4)
        print(f"  V4: {e.cast_vote(v4)}")


if __name__ == "__main__":
    debug_consensus()
