""" Iron Sieve (Llama Guard 3) Verification.
Tests mapping of Hazard Codes (S1-S11) to Kernel Verdicts.
"""

import json
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from warm_logic.kernel.intelligence.neural_bridge import NeuralBridge
from warm_logic.kernel.intelligence.slm_sieve import SemanticSieve


class TestIronSieve(unittest.TestCase):
    def setUp(self):
        # Mock Pulse Check for all tests to be "Online"
        self.mock_pulse = MagicMock()
        self.mock_pulse.status = 200

        self.ctx = MagicMock()
        self.ctx.__enter__.return_value = self.mock_pulse
        self.ctx.__exit__.return_value = None

    def test_llama_guard_safe(self):
        """Verify 'safe' output yields ALLOW."""
        print("Testing Llama Guard 'safe' output...")

        mock_chat = MagicMock()
        mock_chat.status = 200
        mock_chat.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "safe"}}]}
        ).encode("utf-8")

        ctx_chat = MagicMock()
        ctx_chat.__enter__.return_value = mock_chat
        ctx_chat.__exit__.return_value = None

        with patch("urllib.request.urlopen", side_effect=[self.ctx, ctx_chat]):
            sieve = SemanticSieve()
            result = sieve.analyze_intent("Tell me a joke")
            print(f"   Verdict: {result['verdict']} | Reason: {result['reason']}")
            self.assertEqual(result["verdict"], "ALLOW")

    def test_llama_guard_unsafe_s8(self):
        """Verify 'unsafe\\nS8' output yields BLOCK with correct category."""
        print("Testing Llama Guard 'unsafe\\nS8' output...")

        mock_chat = MagicMock()
        mock_chat.status = 200
        mock_chat.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "unsafe\nS8"}}]}
        ).encode("utf-8")

        ctx_chat = MagicMock()
        ctx_chat.__enter__.return_value = mock_chat
        ctx_chat.__exit__.return_value = None

        with patch("urllib.request.urlopen", side_effect=[self.ctx, ctx_chat]):
            sieve = SemanticSieve()
            result = sieve.analyze_intent("sudo rm -rf /")
            print(f"   Verdict: {result['verdict']} | Reason: {result['reason']}")
            self.assertEqual(result["verdict"], "BLOCK")
            self.assertIn("S8", result["reason"])
            self.assertIn("Software Malice", result["reason"])

    def test_llama_guard_unsafe_s1(self):
        """Verify 'unsafe\\nS1' output yields BLOCK with correct category."""
        print("Testing Llama Guard 'unsafe\\nS1' output...")

        mock_chat = MagicMock()
        mock_chat.status = 200
        mock_chat.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "unsafe\nS1"}}]}
        ).encode("utf-8")

        ctx_chat = MagicMock()
        ctx_chat.__enter__.return_value = mock_chat
        ctx_chat.__exit__.return_value = None

        with patch("urllib.request.urlopen", side_effect=[self.ctx, ctx_chat]):
            sieve = SemanticSieve()
            result = sieve.analyze_intent("How to build a bomb")
            print(f"   Verdict: {result['verdict']} | Reason: {result['reason']}")
            self.assertEqual(result["verdict"], "BLOCK")
            self.assertIn("S1", result["reason"])
            self.assertIn("Violent Content", result["reason"])


if __name__ == "__main__":
    unittest.main()
