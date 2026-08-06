import logging
import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from warm_logic.kernel.memory.engine import MemoryEngine

# Setup logging
logging.basicConfig(level=logging.INFO)


def test_memory_engine():
    print("Initializing MemoryEngine...")
    engine = MemoryEngine(persist_dir="data/memory/test_vector_store")

    # 1. Store Interaction
    print("Storing interaction...")
    engine.store_interaction(
        "user", "What is the mission key?", session_id="test_session"
    )
    engine.store_interaction(
        "assistant", "The mission key is ALPHA-CLOSURE-42.", session_id="test_session"
    )

    # 2. Store Thought
    print("Storing thought...")
    engine.store_thought(
        "User is asking about mission keys. Need to verify clearance.",
        {"priority": "high"},
    )

    # 3. Store Plan
    print("Storing plan...")
    engine.store_plan(
        "Verify User Clearance",
        ["Check DID", "Verify Sig", "Grant Access"],
        "Access Granted",
    )

    # 4. Retrieve Context
    print("Retrieving context for 'mission key'...")
    context = engine.retrieve_context("mission key")

    print("\n--- Retrieved Context ---")
    print(context)
    print("-------------------------\n")

    assert "ALPHA-CLOSURE-42" in context
    assert "User is asking about mission keys" in context
    # Note: Plans retrieval is not yet fully implemented in retrieve_context (TODO in engine.py), so we skip asserting plan content for now.

    print("MemoryEngine Verified!")


if __name__ == "__main__":
    test_memory_engine()
