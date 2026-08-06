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
"""
Comprehensive tests for autonomy/debate.py - LLM-Powered Multi-Agent Debate Council
Target: 80%+ coverage
"""

import unittest
from unittest.mock import MagicMock

from warm_logic.kernel.autonomy.debate import (
    AgentPersona,
    DebateResult,
    DebateRound,
    LLMDebateCouncil,
    DEFAULT_PERSONAS,
    CouncilOfThreeLLM,
)


class TestAgentPersona(unittest.TestCase):
    """Test AgentPersona dataclass."""

    def test_persona_creation(self):
        """Test basic persona creation."""
        persona = AgentPersona(
            name="TestAgent",
            role="Tester",
            system_prompt="You are a test agent.",
            focus_areas=["testing", "quality"],
        )
        self.assertEqual(persona.name, "TestAgent")
        self.assertEqual(persona.role, "Tester")
        self.assertEqual(persona.system_prompt, "You are a test agent.")
        self.assertEqual(persona.focus_areas, ["testing", "quality"])

    def test_persona_default_focus_areas(self):
        """Test persona with default empty focus_areas."""
        persona = AgentPersona(
            name="Simple",
            role="Worker",
            system_prompt="Work.",
        )
        self.assertEqual(persona.focus_areas, [])


class TestDebateRound(unittest.TestCase):
    """Test DebateRound dataclass."""

    def test_round_creation(self):
        """Test basic round creation."""
        round_obj = DebateRound(
            persona="TestAgent",
            stance="APPROVE",
            reasoning="Looks good.",
            confidence=0.85,
        )
        self.assertEqual(round_obj.persona, "TestAgent")
        self.assertEqual(round_obj.stance, "APPROVE")
        self.assertEqual(round_obj.reasoning, "Looks good.")
        self.assertEqual(round_obj.confidence, 0.85)


class TestDebateResult(unittest.TestCase):
    """Test DebateResult dataclass."""

    def test_result_creation(self):
        """Test basic result creation."""
        rounds = [
            DebateRound("Agent1", "APPROVE", "Good", 0.9),
            DebateRound("Agent2", "REJECT", "Bad", 0.8),
        ]
        result = DebateResult(
            approved=True,
            rounds=rounds,
            consensus_score=0.5,
            summary="Approved by majority.",
        )
        self.assertTrue(result.approved)
        self.assertEqual(len(result.rounds), 2)
        self.assertEqual(result.consensus_score, 0.5)
        self.assertEqual(result.summary, "Approved by majority.")


class TestDefaultPersonas(unittest.TestCase):
    """Test DEFAULT_PERSONAS configuration."""

    def test_default_personas_count(self):
        """Test that there are 3 default personas."""
        self.assertEqual(len(DEFAULT_PERSONAS), 3)

    def test_default_personas_names(self):
        """Test default persona names."""
        names = [p.name for p in DEFAULT_PERSONAS]
        self.assertIn("Architect", names)
        self.assertIn("Skeptic", names)
        self.assertIn("Auditor", names)

    def test_default_personas_have_focus_areas(self):
        """Test that each default persona has focus areas."""
        for persona in DEFAULT_PERSONAS:
            self.assertGreater(len(persona.focus_areas), 0)


class TestLLMDebateCouncil(unittest.TestCase):
    """Test LLMDebateCouncil class."""

    def test_council_init_defaults(self):
        """Test council initialization with defaults."""
        council = LLMDebateCouncil()
        self.assertEqual(council.personas, DEFAULT_PERSONAS)
        self.assertIsNone(council.llm_client)
        self.assertFalse(council.require_unanimous)
        self.assertEqual(len(council._debate_history), 0)

    def test_council_init_custom_personas(self):
        """Test council with custom personas."""
        custom_personas = [
            AgentPersona("Custom1", "Role1", "Prompt1"),
            AgentPersona("Custom2", "Role2", "Prompt2"),
        ]
        council = LLMDebateCouncil(personas=custom_personas)
        self.assertEqual(council.personas, custom_personas)

    def test_council_init_with_llm_client(self):
        """Test council with provided LLM client."""
        mock_client = MagicMock()
        council = LLMDebateCouncil(llm_client=mock_client)
        self.assertIs(council.llm_client, mock_client)

    def test_council_init_require_unanimous(self):
        """Test council with unanimous requirement."""
        council = LLMDebateCouncil(require_unanimous=True)
        self.assertTrue(council.require_unanimous)


class TestLLMDebateCouncilGetLLMClient(unittest.TestCase):
    """Test _get_llm_client method."""

    def test_get_llm_client_returns_existing(self):
        """Test that existing client is returned."""
        mock_client = MagicMock()
        council = LLMDebateCouncil(llm_client=mock_client)
        result = council._get_llm_client()
        self.assertIs(result, mock_client)

    def test_get_llm_client_import_error(self):
        """Test fallback when LLM import fails by returning None."""
        council = LLMDebateCouncil()

        # Test the fallback behavior: when there's no client and import fails,
        # _get_llm_client should return None
        # We patch the internal import to raise ImportError
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "llm_bridge" in name:
                raise ImportError("No LLM available")
            return original_import(name, *args, **kwargs)

        builtins.__import__ = mock_import
        try:
            result = council._get_llm_client()
            self.assertIsNone(result)
        finally:
            builtins.__import__ = original_import


class TestLLMDebateCouncilRuleBasedVote(unittest.TestCase):
    """Test _rule_based_vote method."""

    def setUp(self):
        self.council = LLMDebateCouncil()

    def test_architect_approves_with_code(self):
        """Test Architect approves when code is present."""
        persona = AgentPersona("Architect", "Designer", "")
        context = {"patch_code": "def foo(): pass", "test_code": ""}
        result = self.council._rule_based_vote(persona, context)

        self.assertEqual(result.persona, "Architect")
        self.assertEqual(result.stance, "APPROVE")
        self.assertIn("valid", result.reasoning)

    def test_architect_rejects_empty_code(self):
        """Test Architect rejects empty code."""
        persona = AgentPersona("Architect", "Designer", "")
        context = {"patch_code": "", "test_code": ""}
        result = self.council._rule_based_vote(persona, context)

        self.assertEqual(result.stance, "REJECT")
        self.assertIn("Empty", result.reasoning)

    def test_skeptic_approves_with_tests(self):
        """Test Skeptic approves when tests are present."""
        persona = AgentPersona("Skeptic", "Critic", "")
        context = {"patch_code": "code", "test_code": "def test_foo(): pass"}
        result = self.council._rule_based_vote(persona, context)

        self.assertEqual(result.persona, "Skeptic")
        self.assertEqual(result.stance, "APPROVE")
        self.assertIn("Tests provided", result.reasoning)

    def test_skeptic_rejects_without_tests(self):
        """Test Skeptic rejects when no tests."""
        persona = AgentPersona("Skeptic", "Critic", "")
        context = {"patch_code": "code", "test_code": ""}
        result = self.council._rule_based_vote(persona, context)

        self.assertEqual(result.stance, "REJECT")
        self.assertIn("NO TESTS FOUND", result.reasoning)

    def test_auditor_approves_short_code(self):
        """Test Auditor approves code under 50 lines."""
        persona = AgentPersona("Auditor", "Compliance", "")
        context = {"patch_code": "line1\nline2\nline3", "test_code": ""}
        result = self.council._rule_based_vote(persona, context)

        self.assertEqual(result.persona, "Auditor")
        self.assertEqual(result.stance, "APPROVE")
        self.assertIn("acceptable", result.reasoning)

    def test_auditor_rejects_long_code(self):
        """Test Auditor rejects code over 50 lines."""
        persona = AgentPersona("Auditor", "Compliance", "")
        long_code = "\n".join([f"line{i}" for i in range(60)])
        context = {"patch_code": long_code, "test_code": ""}
        result = self.council._rule_based_vote(persona, context)

        self.assertEqual(result.stance, "REJECT")
        self.assertIn("too high", result.reasoning)

    def test_unknown_persona_default_approval(self):
        """Test unknown persona defaults to approval."""
        persona = AgentPersona("Unknown", "Mystery", "")
        context = {"patch_code": "code", "test_code": ""}
        result = self.council._rule_based_vote(persona, context)

        self.assertEqual(result.stance, "APPROVE")
        self.assertIn("Default approval", result.reasoning)

    def test_auditor_with_empty_code(self):
        """Test Auditor handles empty code."""
        persona = AgentPersona("Auditor", "Compliance", "")
        context = {"patch_code": "", "test_code": ""}
        result = self.council._rule_based_vote(persona, context)

        self.assertEqual(result.stance, "APPROVE")  # 0 lines <= 50


class TestLLMDebateCouncilExtractJSON(unittest.TestCase):
    """Test _extract_json method."""

    def setUp(self):
        self.council = LLMDebateCouncil()

    def test_extract_valid_json(self):
        """Test extracting valid JSON."""
        text = 'Some text {"stance": "APPROVE", "reasoning": "Good"} more text'
        result = self.council._extract_json(text)

        self.assertIsNotNone(result)
        self.assertEqual(result["stance"], "APPROVE")
        self.assertEqual(result["reasoning"], "Good")

    def test_extract_json_no_match(self):
        """Test extracting from text without JSON."""
        text = "No JSON here at all"
        result = self.council._extract_json(text)
        self.assertIsNone(result)

    def test_extract_json_invalid_json(self):
        """Test extracting invalid JSON."""
        text = "Invalid {not: valid: json} here"
        result = self.council._extract_json(text)
        self.assertIsNone(result)

    def test_extract_json_multiple_objects(self):
        """Test extracting first valid JSON from multiple."""
        text = '{"first": "one"} and {"second": "two"}'
        result = self.council._extract_json(text)

        self.assertIsNotNone(result)
        self.assertEqual(result["first"], "one")


class TestLLMDebateCouncilQueryPersona(unittest.TestCase):
    """Test _query_persona method."""

    def test_query_persona_with_llm_success(self):
        """Test successful LLM query."""
        mock_client = MagicMock()
        mock_client.generate_thought.return_value = (
            '{"stance": "APPROVE", "reasoning": "LLM approved", "confidence": 0.9}'
        )

        council = LLMDebateCouncil(llm_client=mock_client)
        persona = DEFAULT_PERSONAS[0]  # Architect
        context = {"patch_code": "code", "test_code": "test", "function_name": "foo"}

        result = council._query_persona(persona, context)

        self.assertEqual(result.stance, "APPROVE")
        self.assertEqual(result.reasoning, "LLM approved")
        self.assertAlmostEqual(result.confidence, 0.9)

    def test_query_persona_llm_exception_fallback(self):
        """Test fallback when LLM raises exception."""
        mock_client = MagicMock()
        mock_client.generate_thought.side_effect = Exception("LLM error")

        council = LLMDebateCouncil(llm_client=mock_client)
        persona = DEFAULT_PERSONAS[0]  # Architect
        context = {"patch_code": "code", "test_code": "test", "function_name": "foo"}

        result = council._query_persona(persona, context)

        # Should fall back to rule-based
        self.assertIn("[Rule-based]", result.reasoning)

    def test_query_persona_no_json_fallback(self):
        """Test fallback when LLM response has no valid JSON."""
        mock_client = MagicMock()
        mock_client.generate_thought.return_value = "No JSON in response"

        council = LLMDebateCouncil(llm_client=mock_client)
        persona = DEFAULT_PERSONAS[0]
        context = {"patch_code": "code", "test_code": "test", "function_name": "foo"}

        result = council._query_persona(persona, context)

        self.assertIn("[Rule-based]", result.reasoning)

    def test_query_persona_confidence_clamping(self):
        """Test confidence is clamped to [0, 1]."""
        mock_client = MagicMock()
        mock_client.generate_thought.return_value = (
            '{"stance": "APPROVE", "reasoning": "test", "confidence": 1.5}'
        )

        council = LLMDebateCouncil(llm_client=mock_client)
        persona = DEFAULT_PERSONAS[0]
        context = {"patch_code": "code", "test_code": "test", "function_name": "foo"}

        result = council._query_persona(persona, context)

        self.assertEqual(result.confidence, 1.0)

    def test_query_persona_confidence_negative_clamping(self):
        """Test negative confidence is clamped to 0."""
        mock_client = MagicMock()
        mock_client.generate_thought.return_value = (
            '{"stance": "REJECT", "reasoning": "test", "confidence": -0.5}'
        )

        council = LLMDebateCouncil(llm_client=mock_client)
        persona = DEFAULT_PERSONAS[0]
        context = {"patch_code": "code", "test_code": "test", "function_name": "foo"}

        result = council._query_persona(persona, context)

        self.assertEqual(result.confidence, 0.0)


class TestLLMDebateCouncilReviewPatch(unittest.TestCase):
    """Test review_patch method."""

    def test_review_patch_majority_approve(self):
        """Test patch approval with majority vote."""
        council = LLMDebateCouncil()

        # All personas will use rule-based (no LLM client)
        # Architect: approves (code present)
        # Skeptic: approves (tests present)
        # Auditor: approves (short code)
        result = council.review_patch(
            patch_code="def foo(): pass",
            test_code="def test_foo(): pass",
            function_name="foo",
        )

        self.assertTrue(result)

    def test_review_patch_majority_reject(self):
        """Test patch rejection with majority reject."""
        council = LLMDebateCouncil()

        # Architect: approves (code present)
        # Skeptic: rejects (no tests)
        # Auditor: rejects (code too long)
        long_code = "\n".join([f"line{i}" for i in range(60)])
        result = council.review_patch(
            patch_code=long_code,
            test_code="",
            function_name="foo",
        )

        self.assertFalse(result)

    def test_review_patch_unanimous_required_all_approve(self):
        """Test unanimous approval."""
        council = LLMDebateCouncil(require_unanimous=True)

        result = council.review_patch(
            patch_code="def foo(): pass",
            test_code="def test_foo(): pass",
            function_name="foo",
        )

        self.assertTrue(result)

    def test_review_patch_unanimous_required_one_reject(self):
        """Test unanimous rejection when one rejects."""
        council = LLMDebateCouncil(require_unanimous=True)

        # Skeptic will reject (no tests)
        result = council.review_patch(
            patch_code="def foo(): pass",
            test_code="",
            function_name="foo",
        )

        self.assertFalse(result)

    def test_review_patch_updates_history(self):
        """Test that review_patch updates debate history."""
        council = LLMDebateCouncil()

        self.assertEqual(len(council._debate_history), 0)

        council.review_patch(
            patch_code="def foo(): pass",
            test_code="def test_foo(): pass",
            function_name="foo",
        )

        self.assertEqual(len(council._debate_history), 1)
        self.assertIsInstance(council._debate_history[0], DebateResult)


class TestLLMDebateCouncilGenerateSummary(unittest.TestCase):
    """Test _generate_summary method."""

    def test_generate_summary_approved(self):
        """Test summary generation for approved patch."""
        council = LLMDebateCouncil()
        rounds = [
            DebateRound("Agent1", "APPROVE", "Good code", 0.9),
            DebateRound("Agent2", "APPROVE", "Well tested", 0.85),
        ]

        summary = council._generate_summary(rounds, approved=True)

        self.assertIn("Debate Summary", summary)
        self.assertIn("Agent1", summary)
        self.assertIn("Agent2", summary)
        self.assertIn("APPROVED", summary)

    def test_generate_summary_rejected(self):
        """Test summary generation for rejected patch."""
        council = LLMDebateCouncil()
        rounds = [
            DebateRound("Agent1", "REJECT", "Bad code", 0.9),
        ]

        summary = council._generate_summary(rounds, approved=False)

        self.assertIn("REJECTED", summary)


class TestLLMDebateCouncilGetDebateHistory(unittest.TestCase):
    """Test get_debate_history method."""

    def test_get_debate_history_empty(self):
        """Test getting empty history."""
        council = LLMDebateCouncil()
        history = council.get_debate_history()

        self.assertEqual(history, [])

    def test_get_debate_history_returns_copy(self):
        """Test that get_debate_history returns a copy."""
        council = LLMDebateCouncil()
        council.review_patch("code", "test", "foo")

        history1 = council.get_debate_history()
        history2 = council.get_debate_history()

        self.assertIsNot(history1, history2)
        self.assertEqual(len(history1), len(history2))


class TestBackwardsCompatibility(unittest.TestCase):
    """Test backwards compatibility aliases."""

    def test_council_of_three_llm_alias(self):
        """Test CouncilOfThreeLLM is an alias for LLMDebateCouncil."""
        self.assertIs(CouncilOfThreeLLM, LLMDebateCouncil)


if __name__ == "__main__":
    unittest.main()
