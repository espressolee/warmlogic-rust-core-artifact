#!/usr/bin/env python3
"""
[Phase 99.1] Verify Expanded Tool Suite.
Tests Browser Automation and Code Execution tools.
"""

import logging
import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from warm_logic.kernel.intelligence.tools import ToolRegistry

# Setup logging
logging.basicConfig(level=logging.INFO)


def test_expanded_tools():
    print("Testing Expanded Tool Suite...")
    print("=" * 60)

    registry = ToolRegistry()

    # Check tool count
    print(f"\nAvailable Tools ({len(registry.tools)}):")
    print(registry.get_tool_list())

    # Test 1: Browser Navigation
    print("\n--- Test 1: Browser Navigation ---")
    result = registry.execute("browser", action="navigate", target="http://example.com")
    print(result[:200] + "...")
    assert "Example Domain" in result or "Page content" in result

    # Test 2: Code Execution (Python)
    print("\n--- Test 2: Python Execution ---")
    code = "print('Hello from WarmLogic!')\nprint(2 + 2)"
    result = registry.execute("execute_code", language="python", code=code)
    print(result)
    assert "Hello from WarmLogic" in result
    assert "4" in result

    # Test 3: Code Execution (Shell)
    print("\n--- Test 3: Shell Execution ---")
    result = registry.execute(
        "execute_code", language="shell", code="echo 'System: '$(uname -s)"
    )
    print(result)
    assert "Darwin" in result or "Linux" in result

    # Test 4: Safety Block
    print("\n--- Test 4: Dangerous Code Block ---")
    result = registry.execute("execute_code", language="shell", code="rm -rf /")
    print(result)
    assert "BLOCKED" in result

    # Test 5: Web Search (still works)
    print("\n--- Test 5: Web Search (existing) ---")
    result = registry.execute("search_web", query="WarmLogic")
    print(result[:150] + "...")

    print("\n" + "=" * 60)
    print(f"Expanded Tool Suite Verified! ({len(registry.tools)} tools)")


if __name__ == "__main__":
    test_expanded_tools()
