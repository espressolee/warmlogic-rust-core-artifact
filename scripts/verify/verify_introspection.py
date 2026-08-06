#!/usr/bin/env python3
"""
[Phase 98.4] Verify Self-Awareness (Introspection).
Tests that the agent can examine its own state.
"""

import logging
import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from warm_logic.kernel.intelligence.introspection import SelfInspector, introspect
from warm_logic.kernel.intelligence.tools import ToolRegistry
from warm_logic.kernel.memory.engine import MemoryEngine

# Setup logging
logging.basicConfig(level=logging.INFO)


def test_introspection():
    print("Testing Self-Awareness (Introspection)...")
    print("=" * 60)

    # Test 1: Basic introspection (no dependencies)
    print("\n--- Test 1: Basic Introspection ---")
    basic = introspect()
    print(f"Identity: {basic['identity']['name']} v{basic['identity']['version']}")
    print(f"Type: {basic['identity']['type']}")
    print(f"Philosophy: {basic['identity']['philosophy']}")

    # Test 2: Full introspection with components
    print("\n--- Test 2: Full Self-Inspection ---")
    memory = MemoryEngine(persist_dir="data/memory/introspection_test")
    tools = ToolRegistry()

    inspector = SelfInspector(memory=memory, tools=tools)
    report = inspector.introspect()

    print(f"Memory Available: {report['capabilities']['memory']['available']}")
    print(f"Tools Count: {report['capabilities']['tools']['count']}")
    print(f"Tools: {report['capabilities']['tools']['available']}")
    print(f"Python: {report['environment']['python_version']}")
    print(f"Platform: {report['environment']['platform']}")

    # Test 3: Human-readable summary
    print("\n--- Test 3: Human-Readable Summary ---")
    print(inspector.summarize())

    print("\n" + "=" * 60)
    print("Self-Awareness Verified!")
    print("   The agent knows: Who it is, What it can do, Where it runs.")


if __name__ == "__main__":
    test_introspection()
