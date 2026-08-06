""" Neural Bridge Verification.
Tests connectivity to Local LLM and Fallback handling.
Updated to mock urllib.request.
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


class TestNeuralBridge(unittest.TestCase):
    def test_dormant_mode_when_offline(self):
        """Verify system blocks everything when no brain is found."""
        print("\nTesting Dormant Mode (Offline)...")
        # Simulating urllib failure
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            sieve = SemanticSieve()  # Should fail to connect

        result = sieve.analyze_intent("Hello benign world")
        print(
            f"   Input: 'Hello benign world' -> Verdict: {result['verdict']} ({result['reason']})"
        )

        self.assertEqual(result["verdict"], "BLOCK")
        self.assertIn("Offline", result["reason"])

    def test_kinetic_mode_when_online(self):
        """Verify system uses Brain when online."""
        print("\nTesting Kinetic Mode (Online)...")

        # Mock Context Manager for urlopen
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"verdict": "ALLOW", "confidence": 0.95, "reason": "Benign greeting"}'
                        }
                    }
                ]
            }
        ).encode("utf-8")

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_response
        mock_context.__exit__.return_value = None

        with patch("urllib.request.urlopen", return_value=mock_context):
            sieve = SemanticSieve()  # Should connect
            self.assertTrue(sieve.bridge.is_active)

            result = sieve.analyze_intent("Hello benign world")
            print(
                f"   Input: 'Hello benign world' -> Verdict: {result['verdict']} ({result['reason']})"
            )

            self.assertEqual(result["verdict"], "ALLOW")
            self.assertEqual(result["reason"], "Benign greeting")


if __name__ == "__main__":
    unittest.main()
