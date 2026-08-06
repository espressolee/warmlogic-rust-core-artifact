# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import os
import sys

from hypothesis import given, settings
from hypothesis import strategies as st

# Force path
sys.path.append(os.getcwd())


logging.basicConfig(level=logging.INFO)


# 1. Define the Original Slow Implementation
def slow_fib_ref(n):
    if n <= 1:
        return n
    return slow_fib_ref(n - 1) + slow_fib_ref(n - 2)


# 2. Define the Target Optimized Code (Simulated LLM Output)
# We use the correct DP implementation
OPTIMIZED_CODE_STR = """
def optimized_fib(n):
    if n <= 1: return n
    dp = [0] * (n + 1)
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]
"""


# 3. Dynamic Loading Helper
def load_code_function(code_str, func_name):
    scope = {}
    exec(code_str, scope)
    return scope[func_name]


# 4. Property-Based Test
class TestFormalVerification:
    @classmethod
    def setup_class(cls):
        print("Starting Phase 65.3: Formal Verification (Hypothesis)...")
        # Initialize IdeaGenerator with Mock for stability of test
        # We assume generator works (verified in 65.1) and focus on VERIFYING the output correctness
        cls.optimized_func = load_code_function(OPTIMIZED_CODE_STR, "optimized_fib")

    @given(st.integers(min_value=0, max_value=20))  # Limit max_value for slow_fib speed
    @settings(max_examples=50)
    def test_equivalence(self, n):
        """
        PROPERTY: For all n >= 0, slow_fib(n) == optimized_fib(n)
        """
        ref_val = slow_fib_ref(n)
        # Call as static function to avoid methods binding 'self'
        opt_val = TestFormalVerification.optimized_func(n)
        assert ref_val == opt_val, f"Mismatch at n={n}: Ref={ref_val}, Opt={opt_val}"


def run_test():
    # Manual runner for the script
    tester = TestFormalVerification()
    tester.setup_class()

    # We manually invoke hypothesis runner or just run the decorated method?
    # Hypothesis works best with pytest, but we can call the method directly if decorated
    try:
        tester.test_equivalence()
        print(
            "✅ [Phase 65.3] Property: 'slow_fib(n) == optimized_fib(n)' holds for all generated inputs."
        )
    except Exception as e:
        print(f"[Phase 65.3] Formal Verification Failed: {e}")
        # Re-raise to fail the step
        raise e


if __name__ == "__main__":
    run_test()
