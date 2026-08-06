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
import time
from unittest.mock import MagicMock

# Force path
sys.path.append(os.getcwd())

from warm_logic.kernel.evolution.evaluation_loop import EvaluationLoop
from warm_logic.kernel.evolution.idea_generator import IdeaGenerator
from warm_logic.kernel.sys.hot_swapper import HotSwapManager as HotSwapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestSelfImprovement")


def test_recursive_evolution():
    print("Starting Recursive Self-Improvement Verification...")

    # 1. Setup Temporary Module with Slow Code
    # We will create 'target_func.py'
    target_code = """
import time

def slow_fib(n):
    # Inefficient recursive implementation
    if n <= 1: return n
    return slow_fib(n-1) + slow_fib(n-2)
"""
    with open("target_func.py", "w") as f:
        f.write(target_code)

    import target_func

    # 2. Baseline Measurement
    start = time.time()
    res = target_func.slow_fib(30)
    duration = time.time() - start
    print(f"Baseline (Recursive): {duration:.4f}s")

    # 3. Initialize Evolution Engines
    mock_dht = MagicMock()
    swapper = HotSwapper(dht_client=mock_dht)
    # Add reload_module method that EvaluationLoop expects
    swapper.reload_module = lambda mod_name: __import__("importlib").reload(
        sys.modules.get(mod_name)
    )
    generator = IdeaGenerator(use_mock=True)
    evaluator = EvaluationLoop(generator, swapper)

    # 4. Trigger Evolution
    print("Triggering Evaluation Loop...")
    success = evaluator.evaluate_and_evolve("target_func", "slow_fib")

    assert success, "Evolution failed unexpectedly."

    # 5. Verify Hot-Swap & Performance
    # Re-import not needed if HotSwapper did its job on sys.modules['target_func']
    # But for safety in test script top-level, we use the reference again

    start_v2 = time.time()
    res_v2 = target_func.slow_fib(30)  # Should call new version
    duration_v2 = time.time() - start_v2

    print(f"Evolved (Iterative): {duration_v2:.6f}s")

    assert res == res_v2, "Result mismatch! Logic error in evolution."
    assert duration_v2 < duration * 0.1, "Performance did not improve significantly."

    # Check source file content
    with open("target_func.py", "r") as f:
        content = f.read()
    assert "# OPTIMIZED by WarmLogic" in content

    print("Recursive Self-Improvement Cycle Verified!")

    # Cleanup
    if os.path.exists("target_func.py"):
        os.remove("target_func.py")
    if os.path.exists("target_func_candidate.py"):
        os.remove("target_func_candidate.py")
    # Clean sys.modules to avoid pollution
    if "target_func" in sys.modules:
        del sys.modules["target_func"]
    if "target_func_candidate" in sys.modules:
        del sys.modules["target_func_candidate"]


if __name__ == "__main__":
    try:
        test_recursive_evolution()
    except Exception as e:
        print(f"Verification Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
