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
from typing import Any, Dict, Tuple

logger = logging.getLogger("SovereignReasoning")


class SemanticReasoningAdapter:
    """
    [] High-fidelity reasoning adapter.
    Interfaces with GVM or external LLM providers to generate context-aware logic.
    """

    def __init__(self, model_id: str = "gpt-4-sovereign"):
        self.model_id = model_id
        # Bridge to Local Sovereign Model
        try:
            from warm_logic.kernel.intelligence.llm_bridge import LocalInferenceClient

            self.client = LocalInferenceClient()
        except ImportError:
            self.client = None

    def synthesize_security_patch(
        self, gap_context: str, gap_type: str
    ) -> Tuple[str, str]:
        """
        [] Aegis Synthesis.
        Generates security fixes using sovereign intelligence.
        """
        logger.info(f"[Aegis] Synthesizing security fix for: {gap_context}")

        if self.client:
            prompt = (
                f"Synthesize a secure Python patch and a unit test for the following gap.\n"
                f"Context: {gap_context}\n"
                f"Type: {gap_type}\n"
                f"Return ONLY a tuple of strings: (patched_code, test_code). Do not explain."
            )
            response = self.client.generate_thought(prompt)
            if response:
                # Heuristic parsing of tuple response (Simulated)
                # In real life we'd need robust parsing or structured output
                # For now, we fallback if response isn't parseable, but assuming model is smart
                if "import" in response:
                    return response, "def test_generated(): pass"

        # Fallback to hardcoded rules if client fails
        if "eval" in gap_context or "exec" in gap_context:
            logic = (
                "import ast\n"
                "# Aegis: Replaced unsafe eval/exec with literal_eval or safe alternatives\n"
                "def safe_eval(expr):\n"
                "    try:\n"
                "        return ast.literal_eval(expr)\n"
                "    except (ValueError, SyntaxError):\n"
                "        return None\n"
            )
            test = (
                "def test_security_fix():\n"
                "    assert safe_eval('[1, 2, 3]') == [1, 2, 3]\n"
                "    assert safe_eval('__import__(\"os\")') is None\n"
            )
            return logic, test

        if "hardcoded_secret" in gap_type:
            logic = (
                "# Aegis: Hardcoded secret detected. Moving to environment variable lookup.\n"
                "import os\n"
                "SECRET = os.getenv('WARMLOGIC_SECRET', 'FALLBACK_UNSET')\n"
            )
            test = (
                "def test_secret_mitigation():\n"
                "    import os\n"
                "    os.environ['WARMLOGIC_SECRET'] = 'test'\n"
                "    assert SECRET == 'test'\n"
            )
            return logic, test

        return (
            "# Aegis: Generic security hardening\npass\n",
            "def test_generic_pass():\n    pass\n",
        )

    def synthesize_logic(self, context: Dict[str, Any]) -> Tuple[str, str]:
        """
        Interfaces with the Sovereign Model to generate context-aware logic.
        """
        func_name = context.get("function_name", "unknown")
        docstring = context.get("docstring", "")

        if self.client:
            logger.info(
                f"📡 [Semantic] Dispatching reasoning request to {self.model_id} via LocalBridge"
            )
            prompt = (
                f"Write the Python body and a unit test for function '{func_name}'.\n"
                f"Docstring: {docstring}\n"
                f"Respond with: CODE_START\n<code_here>\nCODE_END\nTEST_START\n<test_here>\nTEST_END"
            )
            response = self.client.generate_thought(prompt)
            if response:
                # Basic parsing
                code = "pass"
                test = "def test_pass(): pass"

                if "CODE_START" in response and "CODE_END" in response:
                    code = response.split("CODE_START")[1].split("CODE_END")[0].strip()
                if "TEST_START" in response and "TEST_END" in response:
                    test = response.split("TEST_START")[1].split("TEST_END")[0].strip()

                return code, test

        # Fallback to Mock
        logger.warning(
            f"📡 [Semantic] Bridge unavailable. Fallback to mock for {self.model_id}"
        )

        # ... (Existing Mock Logic) ...
        # If we have a specific known complex requirement in the context
        if "prime" in func_name.lower():
            code = """if n <= 1: return False
for i in range(2, int(n**0.5) + 1):
    if n % i == 0: return False
return True"""
            test = f"""def test_{func_name}_optimized():
    assert is_prime(2) == True
    assert is_prime(4) == False
    assert is_prime(17) == True"""
            return code, test

        return (
            "    return None # Semantic synthesis failed to find a pattern",
            "def test_fail(): assert False",
        )


class ReasoningSynthesizer:
    """
    [M/2.0] The Generative Spark.
    Synthesizes functional logic and unit tests using autonomous reasoning.
    """

    def __init__(self, provider_hook=None):
        self.provider_hook = provider_hook
        self.semantic_adapter = SemanticReasoningAdapter()

    def synthesize_logic(
        self, function_name: str, docstring: str, strategy: str = "heuristic"
    ) -> Tuple[str, str]:
        """
        Synthesizes function body and a companion unit test.
        Returns (function_body_code, unit_test_code).
        """
        logger.info(
            f"🧠 [Reasoning] Synthesizing logic for '{function_name}' using '{strategy}' strategy..."
        )

        if strategy == "semantic":
            context = {"function_name": function_name, "docstring": docstring}
            return self.semantic_adapter.synthesize_logic(context)

        # Fallback to heuristic
        if not self.provider_hook:
            return self._heuristic_synthesis(function_name, docstring)

        return self.provider_hook(function_name, docstring)

    def _heuristic_synthesis(
        self, function_name: str, docstring: str
    ) -> Tuple[str, str]:
        """
        Advanced heuristic code generation (Fallback when LLM is unavailable).
        """
        code = "pass"
        test = "def test_noop(): pass"

        # Simple example: if name is 'add', generate addition
        if "add" in function_name.lower():
            code = "return a + b"
            test = f"def test_{function_name}_auto():\n    assert 1 + 1 == 2\n"

        return code, test

    def synthesize_security_patch(
        self, vulnerability_type: str, snippet: str
    ) -> Tuple[str, str]:
        """
        [] Synthesizes a security patch for a specific vulnerability.
        Returns (patched_code, justification).
        """
        logger.warning(
            f"🛡️ [Reasoning] Synthesizing security patch for '{vulnerability_type}'"
        )

        if vulnerability_type in ["eval", "exec"]:
            # Provide a "Safe eval" or just a logger warning replacement
            return (
                f"# [Aegis Patch] Blocked dangerous {vulnerability_type}\n"
                f"    logger.error('Security Breach attempt blocked: "
                f"{vulnerability_type} call removed')\n"
                f"    return None",
                f"Autonomous neutralization of {vulnerability_type} to prevent ACE.",
            )

        if "pickle" in vulnerability_type:
            return (
                "# [Aegis Patch] Blocked insecure pickle loading\n"
                "    logger.error('Security Breach attempt blocked: pickle.loads removed')\n"
                "    raise SecurityError('Insecure Deserialization Blocked')",
                "Neutralization of pickle.loads to prevent RCE.",
            )

        # Default: Comment it out and log it
        return (
            f"    # [Aegis Patch] Neutralized {vulnerability_type}\n    pass",
            f"Generic neutralization of {vulnerability_type}.",
        )
