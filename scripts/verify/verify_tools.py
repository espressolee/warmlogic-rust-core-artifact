import logging
import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from warm_logic.kernel.intelligence.tools import ToolRegistry

# Setup logging
logging.basicConfig(level=logging.INFO)


def test_tool_registry():
    print("Initializing ToolRegistry...")
    registry = ToolRegistry()

    # 1. Test Registry Listing
    print("\nAvailable Tools:")
    print(registry.get_tool_list())

    # 2. Test Web Search (Mock)
    print("\nTesting Web Search...")
    search_result = registry.execute("search_web", query="WarmLogic AI")
    print(f"Result: {search_result[:100]}...")
    assert "Simulated Search Results" in search_result

    # 3. Test URL Reader (Real)
    print("\nTesting URL Reader (example.com)...")
    url_result = registry.execute("read_url", url="http://example.com")
    print(f"Result: {url_result[:100]}...")
    assert "Example Domain" in url_result or "html" in url_result.lower()

    print("\nToolRegistry Verified!")


if __name__ == "__main__":
    test_tool_registry()
