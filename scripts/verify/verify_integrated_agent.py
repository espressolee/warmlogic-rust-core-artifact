import logging
import os
import sys
from unittest.mock import MagicMock

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from warm_logic.kernel.intelligence.llm_bridge import LocalInferenceClient
from warm_logic.kernel.intelligence.reasoning import ReasoningEngine
from warm_logic.kernel.intelligence.tools import ToolRegistry
from warm_logic.kernel.memory.engine import MemoryEngine

# Setup logging
logging.basicConfig(level=logging.INFO)


def test_integrated_agent():
    print("Initializing Integrated Agent (Brain + Hands)...")

    # 1. Real ToolRegistry
    registry = ToolRegistry()

    # 2. Mock Memory
    memory = MagicMock(spec=MemoryEngine)
    memory.retrieve_context.return_value = "Context: Need to find WarmLogic news."

    # 3. Mock LLM to force a tool call
    llm = MagicMock(spec=LocalInferenceClient)
    # LLM returns a thought that includes a JSON action to search web
    llm.generate_thought.side_effect = [
        # 1. Initial Thought + Tool Call
        """THOUGHT: I need to search for 'WarmLogic'.
PLAN: Use search_web tool.
JSON: {"action": "search_web", "query": "WarmLogic latest news"}""",
        # 2. Critique
        "CRITIQUE: Plan is valid.",
    ]

    # 4. Initialize ReasoningEngine with Tools
    agent = ReasoningEngine(memory=memory, llm=llm, tool_registry=registry)

    # 5. Run Cycle
    print("Action: Find WarmLogic News")
    trace = agent.think("Find WarmLogic News")

    print("\n--- Agent Trace ---")
    print(trace)
    print("-------------------\n")

    # 6. Verify Tool Execution
    assert trace["action"] == "search_web"
    assert "Simulated Search Results" in trace["result"]
    assert "WarmLogic latest news" in trace["result"]

    print("Integrated Agent Verified (Goal -> Think -> Tool -> Result)!")


if __name__ == "__main__":
    test_integrated_agent()
