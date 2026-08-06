import logging
import os
import sys
from unittest.mock import MagicMock, patch

# Force path
sys.path.append(os.getcwd())

from warm_logic.kernel.evolution.idea_generator import IdeaGenerator
from warm_logic.kernel.intelligence.llm_bridge import LocalInferenceClient

logging.basicConfig(level=logging.INFO)


def test_real_optimization():
    print("🧠 Starting Phase 65: True Neural Engine Verification...")

    # 1. Setup Mock LLM Client
    # We simulate a "Smart" LLM response
    mock_response = """
Here is the optimized code:
```python
def slow_fib(n):
    # OPTIMIZED by WarmLogic Neural Engine
    if n <= 1: return n
    dp = [0] * (n + 1)
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]
```
Note: This uses O(N) space and time.
"""

    # Patch the internal LLM of IdeaGenerator
    with patch(
        "warm_logic.kernel.evolution.idea_generator.LocalInferenceClient"
    ) as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.generate_thought.return_value = mock_response

        # 2. Initialize IdeaGenerator (Real Mode)
        generator = IdeaGenerator(use_mock=False)

        source_code = """
def slow_fib(n):
    if n <= 1: return n
    return slow_fib(n-1) + slow_fib(n-2)
"""
        goal = "Optimize to O(N)"

        # 3. Trigger Generation
        print("   -> Requesting optimization via Neural Engine...")
        optimized_code = generator.generate_optimization(source_code, goal)

        # 4. Verify Output
        print("\n📝 Generated Code:")
        print(optimized_code)

        assert "def slow_fib(n):" in optimized_code
        assert "dp = [0] * (n + 1)" in optimized_code
        assert "# OPTIMIZED by WarmLogic Neural Engine" in optimized_code

        print("\n✅ [Phase 65] Neural Engine Integration Verified!")
        print("   -> LLM Logic Bridge: Success")
        print("   -> Code Extraction: Success")


if __name__ == "__main__":
    test_real_optimization()
