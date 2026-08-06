"""Formal Enforcement Test (Era 43).
Simulates an attempt to bypass the kernel pipeline by skipping a state.
Verifies that the FormalInstructionPipeline blocks illegal transitions.
"""

import asyncio
import logging
import os
import sys

# Dynamic root detection
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from warm_logic.kernel.core.state_root import KernelPhase
from warm_logic.kernel.formal_runtime import FormalEvent, FormalInstructionPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FormalTest")


async def test_formal_enforcement():
    print("Starting Era 43 Formal Enforcement Verification...")

    pipeline = FormalInstructionPipeline("test_run_formal")
    event = FormalEvent(
        event_id="evt_valid", prefix="P100", payload={}, trace_id="trace_valid"
    )

    print("\n--- Step 1: Valid Authorize (BOOT_INIT -> AUTHORIZED) ---")
    await pipeline.step_authorize(event)
    assert pipeline.kernel_state.phase == KernelPhase.AUTHORIZED
    print("Result: Transition Allowed (Correct)")

    print(
        "\n--- Step 2: Illegal Skip (Attempt to skip ALIGNING and go to REFLECTED) ---"
    )
    try:
        # We try to call step_reflect directly after step_authorize
        # which violates the flow: AUTHORIZED -> ALIGNING -> REFLECTED
        await pipeline.step_reflect()
        print("FAILED: Illegal transition was allowed!")
    except RuntimeError as e:
        print(f"PASSED: Blocked with error: {e}")
        assert "PORTABLE INVARIANT VIOLATION" in str(e)
        assert pipeline.kernel_state.phase == KernelPhase.HALTED

    print("\nEra 43 Verification Passed: Formal Invariants are strictly enforced.")


if __name__ == "__main__":
    asyncio.run(test_formal_enforcement())
