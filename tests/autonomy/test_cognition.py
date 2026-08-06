import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

from warm_logic.kernel.intelligence.llm_bridge import LocalInferenceClient


class TestCognition(unittest.TestCase):
    @patch("subprocess.run")
    def test_bridge_connection_success(self, mock_run):
        """Verify the bridge parses a successful API response."""
        # Mock subprocess.run result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            '{"choices": [{"message": {"content": "I am Sovereign."}}]}'
        )
        mock_run.return_value = mock_result

        client = LocalInferenceClient()
        response = client.generate_thought("Who are you?")

        self.assertEqual(response, "I am Sovereign.")

    @patch("subprocess.run")
    def test_bridge_fallback(self, mock_run):
        """Verify the bridge accepts failure gracefully (returns None)."""
        # Mock subprocess failure
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        client = LocalInferenceClient()
        response = client.generate_thought("Who are you?")

        self.assertIsNone(response)


if __name__ == "__main__":
    unittest.main()
