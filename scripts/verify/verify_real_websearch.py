import logging
import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from warm_logic.kernel.intelligence.tools import ToolRegistry

# Setup logging
logging.basicConfig(level=logging.INFO)


def test_real_websearch():
    print("Testing REAL Web Search (DuckDuckGo)...")

    registry = ToolRegistry()

    # Test 1: General knowledge query
    print("\n--- Test 1: 'Python programming language' ---")
    result1 = registry.execute("search_web", query="Python programming language")
    print(result1)
    assert len(result1) > 50, "Expected substantial results"

    # Test 2: Korean query
    print("\n--- Test 2: '양자내성암호 PQC' ---")
    result2 = registry.execute("search_web", query="양자내성암호 PQC")
    print(result2)

    # Test 3: Technical query
    print("\n--- Test 3: 'EU AI Act 2026' ---")
    result3 = registry.execute("search_web", query="EU AI Act 2026")
    print(result3)

    print("\nReal Web Search Verified!")


if __name__ == "__main__":
    test_real_websearch()
