import asyncio
import logging
import os
import sys
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, os.path.abspath("src"))

from warm_logic.kernel.intelligence.proof_engine import ProofEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ProofTest")


async def test_recursive_verification():
    logger.info("Starting Recursive Formal Verification (Phase 79) Test...")

    # 1. Mock Kernel
    kernel_api = MagicMock()
    pe = ProofEngine(kernel_api)

    # 2. Generate Proof for a self-modification
    task_id = "EVO-80001"
    diff = "--- a/kernel.py\n+++ b/kernel.py\n@@ -1,1 +1,1 @@\n-old()\n+optimized_pqc_path()"

    proof = await pe.generate_proof_for_optimization(task_id, diff)

    # 3. Verify Proof (Simulating Mesh Consensus check)
    is_valid = await pe.verify_proof(proof)

    if is_valid:
        logger.info(
            f"🏆 SUCCESS: Proof {proof.proof_id} verified. Safe-to-Optimize confirmed."
        )
        print("\nFinal Verdict: FORMAL VERIFICATION ENFORCED")
    else:
        logger.error("FAILURE: Proof verification failed.")


if __name__ == "__main__":
    asyncio.run(test_recursive_verification())
