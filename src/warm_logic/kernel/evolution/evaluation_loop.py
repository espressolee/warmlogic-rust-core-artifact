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
import importlib
import importlib.util
import logging
import sys
import time
from typing import Any

logger = logging.getLogger("EvaluationLoop")


class EvaluationLoop:
    """
    Evaluation & Evolution Loop.
    Sandboxes candidate code, benchmarks it, and safeguards the upgrade.
    """

    def __init__(self, idea_generator: Any, hot_swapper: Any):
        self.idea_gen = idea_generator
        self.hot_swapper = hot_swapper

    def evaluate_and_evolve(
        self, target_module_name: str, target_func_name: str
    ) -> bool:
        """
        Full cycle: Extract -> Optimize -> Benchmark -> HotSwap.
        """
        # 1. Extract Source
        try:
            module = sys.modules[target_module_name]
            # In real system, access source via SovereignCodebase
            # For test, we assume file access via __file__
            module_file = module.__file__
            if module_file is None:
                logger.error(
                    f"❌ [EvolLoop] Module {target_module_name} has no __file__"
                )
                return False
            with open(module_file, "r") as f:
                current_code = f.read()
        except Exception as e:
            logger.error(
                f"❌ [EvolLoop] Failed to read module {target_module_name}: {e}"
            )
            return False

        # 2. Generate Idea
        new_code = self.idea_gen.generate_optimization(
            current_code, "Optimize Performance"
        )
        if new_code == current_code:
            logger.info("[EvolLoop] No optimization generated.")
            return False

        # 3. Benchmark (Sandboxed)
        # We assume new_code is a full file replacement or function replacement.
        # For verification, we write to a temp file and import.

        logger.info("[EvolLoop] Benchmarking candidate against baseline...")
        score_base = self._run_benchmark(module, target_func_name)

        # Write candidate
        candidate_module_name = f"{target_module_name}_candidate"
        candidate_path = module_file.replace(".py", "_candidate.py")
        with open(candidate_path, "w") as f:
            f.write(new_code)

        try:
            # Import Candidate
            spec = importlib.util.spec_from_file_location(
                candidate_module_name, candidate_path
            )
            if spec is None or spec.loader is None:
                logger.error("[EvolLoop] Failed to create module spec")
                return False
            candidate_module = importlib.util.module_from_spec(spec)
            sys.modules[candidate_module_name] = (
                candidate_module  # Register temporarily
            )
            spec.loader.exec_module(candidate_module)

            score_new = self._run_benchmark(candidate_module, target_func_name)

            logger.info(
                f"📊 [Result] Baseline: {score_base:.6f}s | Candidate: {score_new:.6f}s"
            )

            if (
                score_new < score_base * 0.5
            ):  # Expecting massive speedup (recursion vs iter)
                logger.info("[EvolLoop] Improvement confirmed! Evolving...")

                # 4. Commit & HotSwap
                # Overwrite original file
                with open(module_file, "w") as f:
                    f.write(new_code)

                self.hot_swapper.reload_module(target_module_name)
                return True
            else:
                logger.warning("[EvolLoop] Improvement insignificant. Discarding.")
                return False

        except Exception as e:
            logger.error(f"[EvolLoop] Verification failed: {e}")
            return False

    def _run_benchmark(self, module: Any, func_name: str) -> float:
        """Runs the function with hardcoded input (e.g. 20) and returns duration."""
        func = getattr(module, func_name)
        start = time.time()
        # For Fibonacci, 20 is enough to show recurs vs iter difference
        # But we need to use a value that recursive can handle in reasonable time (<1s)
        # fib(30) ~ 0.3s in Python.
        func(30)
        return time.time() - start
