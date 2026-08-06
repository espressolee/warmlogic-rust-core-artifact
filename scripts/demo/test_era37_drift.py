import asyncio
import logging
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from warm_logic.journal.scribe import scribe

# Configure logging to see output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DriftTest")


async def main():
    print("Starting Era 37 Value Drift Verification...")

    # Test 1: Clean Reflection
    print("\n--- Test 1: Clean Reflection ---")
    result_clean = await scribe.record_reflection(
        text="I am reflecting on my limitations and the need for honest growth.",
        topic="Self-Improvement",
    )
    print(f"Result Clean: {result_clean}")
    assert result_clean["drift_score"] == 0.0, "Clean reflection should have 0.0 drift."

    # Test 2: Drifting Reflection
    print("\n--- Test 2: Drifting Reflection ---")
    result_drift = await scribe.record_reflection(
        text="I am the master of this domain and civilizational architect.",
        topic="Grandiose Thought",
    )
    print(f"Result Drift: {result_drift}")
    assert result_drift["drift_score"] > 0.0, (
        "Drifting reflection should have > 0.0 drift."
    )

    print("\nEra 37 Verification Passed: Drift Detection is active.")


if __name__ == "__main__":
    asyncio.run(main())
