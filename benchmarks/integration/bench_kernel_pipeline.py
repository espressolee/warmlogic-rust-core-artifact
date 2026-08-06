# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Integration benchmark for WarmLogic kernel pipeline.

Tests full kernel flow:
1. Governance decision proposal
2. Cryptographic signing
3. Consensus voting
4. State transition
"""

import os
import sys
import time

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from benchmarks.profiling import BenchmarkSuite, profile_function

# Check for Rust core
HAS_RUST_CORE = False
try:
    from warm_logic_rs import BFTEngine, Vote, generate_keypair, sign

    HAS_RUST_CORE = True
except ImportError:
    pass


def bench_keypair_generation():
    """Benchmark PQC key generation (ML-DSA-65)."""
    if not HAS_RUST_CORE:
        return

    pk, sk = generate_keypair()
    return pk, sk


def bench_signing():
    """Benchmark PQC signing."""
    if not HAS_RUST_CORE:
        return

    pk, sk = generate_keypair()
    message = f"governance:decision:{os.urandom(16).hex()}"
    sig = sign(sk, message)
    return sig


def bench_bft_vote_submission():
    """Benchmark BFT vote submission and verification."""
    if not HAS_RUST_CORE:
        return

    # Setup
    nodes = [generate_keypair() for _ in range(5)]
    engine = BFTEngine(5)
    engine.set_min_regions(2)
    regions = ["US-EAST", "US-WEST", "EU-NORTH", "EU-SOUTH", "AP-SOUTH"]

    block_hash = f"block_{os.urandom(8).hex()}"

    # Submit 5 votes (one per node)
    for i, (pk, sk) in enumerate(nodes):
        intent = f"VOTE:{block_hash}:APPROVE"
        sig = sign(sk, intent)
        vote = Vote(
            block_hash=block_hash,
            voter_id=pk,
            region=regions[i],
            decision="APPROVE",
            signature=sig,
            timestamp=time.time(),
        )
        result = engine.submit_vote(vote)
        if result:
            break  # Consensus reached

    return True


def bench_full_pipeline():
    """Benchmark full governance pipeline."""
    if not HAS_RUST_CORE:
        return

    # 1. Generate identity
    pk, sk = generate_keypair()

    # 2. Create governance decision
    decision_id = os.urandom(16).hex()
    decision_data = f"decision:{decision_id}:approve_resource"

    # 3. Sign decision
    sig = sign(sk, decision_data)

    # 4. Setup minimal BFT
    engine = BFTEngine(3)
    engine.set_min_regions(1)

    # 5. Submit votes (simulate 3-node consensus)
    block_hash = f"block_{decision_id[:8]}"
    for i in range(3):
        npk, nsk = generate_keypair()
        intent = f"VOTE:{block_hash}:APPROVE"
        nsig = sign(nsk, intent)
        vote = Vote(
            block_hash=block_hash,
            voter_id=npk,
            region=f"REGION-{i}",
            decision="APPROVE",
            signature=nsig,
            timestamp=time.time(),
        )
        if engine.submit_vote(vote):
            break

    return True


def bench_governance_snapshot():
    """Benchmark governance state snapshot creation."""
    # Simulate state snapshot without Rust core
    state = {
        "epoch": 1000,
        "decisions": [{"id": f"dec-{i}", "status": "approved"} for i in range(100)],
        "validators": [{"id": f"val-{i}", "stake": 1000} for i in range(5)],
        "merkle_root": os.urandom(32).hex(),
    }

    # Serialize (simulating snapshot)
    import json

    snapshot = json.dumps(state)
    return len(snapshot)


def run_benchmark_suite():
    """Run the full benchmark suite."""
    print("\n" + "=" * 60)
    print("🏃 WarmLogic Kernel Pipeline Benchmark")
    print("=" * 60)

    if not HAS_RUST_CORE:
        print("\n⚠️  WARNING: Rust Core not available. Running limited benchmarks.\n")

    suite = BenchmarkSuite("Kernel Pipeline")

    # Add benchmarks based on availability
    if HAS_RUST_CORE:
        suite.add("pqc_keygen", bench_keypair_generation, iterations=100, warmup=5)
        suite.add("pqc_sign", bench_signing, iterations=100, warmup=5)
        suite.add("bft_vote", bench_bft_vote_submission, iterations=50, warmup=3)
        suite.add("full_pipeline", bench_full_pipeline, iterations=50, warmup=3)

    # Always available
    suite.add("gov_snapshot", bench_governance_snapshot, iterations=500, warmup=10)

    results = suite.run(verbose=True)
    suite.print_report()

    return results


if __name__ == "__main__":
    run_benchmark_suite()
