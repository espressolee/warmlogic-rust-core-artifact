import os
import sys
import time

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

try:
    from warm_logic_rs import RustZKProofGenerator
except ImportError as e:
    print(f"CRITICAL: warm_logic_rs not available: {e}")
    sys.exit(1)


def bench_zk(iterations: int = 1000):
    print(f"🚀 Benchmarking Rust ZK Proofs ({iterations} iterations)...")

    generator = RustZKProofGenerator()

    # Data preparation
    blinding = os.urandom(32).hex()
    value = 1000

    # 1. Generation
    start_gen = time.time()
    proofs = []
    for _ in range(iterations):
        p = generator.generate_state_proof(value, blinding)
        proofs.append(p)
    end_gen = time.time()

    gen_time = end_gen - start_gen
    gen_rate = iterations / gen_time

    print(
        f"   [Prove]  Total: {gen_time:.4f}s | Rate: {gen_rate:.2f} proofs/s | Latency: {1000 / gen_rate:.2f}ms"
    )

    # 2. Verification
    start_ver = time.time()
    for p in proofs:
        # p is ZKProof object
        # We need proof string format "challenge:z1:z2" and commitment hex
        proof_str = p.proof_hex
        comm_hex = p.commitment_hex

        valid = generator.verify_state_proof(proof_str, comm_hex)
        if not valid:
            raise RuntimeError("Proof validation failed!")
    end_ver = time.time()

    ver_time = end_ver - start_ver
    ver_rate = iterations / ver_time

    print(
        f"   [Verify] Total: {ver_time:.4f}s | Rate: {ver_rate:.2f} verifs/s | Latency: {1000 / ver_rate:.2f}ms"
    )


if __name__ == "__main__":
    bench_zk(5000)
