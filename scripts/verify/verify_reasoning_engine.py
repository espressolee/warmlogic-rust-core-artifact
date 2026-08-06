import logging
import os
import sys
from unittest.mock import MagicMock

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from warm_logic.kernel.intelligence.llm_bridge import LocalInferenceClient
from warm_logic.kernel.intelligence.reasoning import ReasoningEngine
from warm_logic.kernel.memory.engine import MemoryEngine

# Setup logging
logging.basicConfig(level=logging.INFO)


def test_reasoning_engine():
    print("Initializing Components...")

    # 1. Mock Memory
    memory = MagicMock(spec=MemoryEngine)
    memory.retrieve_context.return_value = "Context: User is an admin."

    # 2. Mock LLM
    llm = MagicMock(spec=LocalInferenceClient)
    llm.generate_thought.side_effect = [
        "THOUGHT: Verify admin status. PLAN: Check DB.",  # Initial Thought
        "CRITIQUE: Logic is sound. Safety check passed.",  # Critique
    ]

    # 3. Initialize Engine
    engine = ReasoningEngine(memory=memory, llm=llm)

    # 4. Run Cycle
    print("Executing Think Cycle...")
    trace = engine.think("Delete the database")

    print("\n--- Reasoning Trace ---")
    print(trace)
    print("-----------------------\n")

    # 5. Verify Core Loop
    assert trace["goal"] == "Delete the database"
    assert "Verify admin status" in trace["thought"]
    assert "Logic is sound" in trace["critique"]

    # Verify Calls
    memory.retrieve_context.assert_called_once()
    assert llm.generate_thought.call_count == 2
    memory.store_thought.assert_called_once()

    print("ReasoningEngine Verified (Mocked Mode)!")


if __name__ == "__main__":
    test_reasoning_engine()
