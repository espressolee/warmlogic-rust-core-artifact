import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.intelligence.llm_bridge import LocalInferenceClient


class TestLLMBridgeSaturation:
    @pytest.fixture(autouse=True)
    def clean_env(self):
        """Ensure no real leaking of env vars during tests."""
        env_patch = patch.dict(os.environ, {}, clear=True)
        env_patch.start()
        yield
        env_patch.stop()

    def test_init_providers(self):
        """Test provider selection logic."""
        # 1. Anthropic
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant"}):
            client = LocalInferenceClient()
            assert client.provider == "anthropic"
            assert "anthropic" in client.api_base

        # 2. OpenAI
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-oa"}):
            client = LocalInferenceClient()
            assert client.provider == "openai"
            assert "openai" in client.api_base

        # 3. OpenRouter
        with patch.dict(os.environ, {"WARM_LOGIC_PROVIDER": "openrouter"}):
            client = LocalInferenceClient()
            assert client.provider == "openrouter"
            assert "openrouter" in client.api_base

        # 4. Local fallback
        client = LocalInferenceClient()
        assert client.provider == "local"
        assert "127.0.0.1" in client.api_base

    def test_load_sovereign_knowledge(self, tmp_path):
        """Test RAG knowledge loading."""
        kg_file = tmp_path / "docs" / "SOVEREIGN_KNOWLEDGE_GRAPH.md"
        kg_file.parent.mkdir(parents=True)
        kg_file.write_text("Sovereign Concept A\n" * 2000)  # Large file

        with patch(
            "warm_logic.kernel.intelligence.llm_bridge.Path", return_value=kg_file
        ):
            client = LocalInferenceClient()
            knowledge = client._load_sovereign_knowledge()
            assert len(knowledge) <= 16000
            assert "Sovereign Concept A" in knowledge

    def test_load_sovereign_knowledge_missing(self):
        """Test RAG when file is missing."""
        with patch(
            "warm_logic.kernel.intelligence.llm_bridge.Path.exists", return_value=False
        ):
            client = LocalInferenceClient()
            assert client._load_sovereign_knowledge() == ""

    def test_load_sovereign_knowledge_exception(self):
        """Test RAG when file read fails."""
        with patch(
            "warm_logic.kernel.intelligence.llm_bridge.Path.exists", return_value=True
        ):
            with patch(
                "warm_logic.kernel.intelligence.llm_bridge.Path.read_text",
                side_effect=Exception("Disk Error"),
            ):
                client = LocalInferenceClient()
                assert client._load_sovereign_knowledge() == ""

    def test_generate_thought_with_messages(self):
        """Test generate_thought when explicit messages are provided."""
        client = LocalInferenceClient()
        messages = [{"role": "user", "content": "Custom history"}]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            client.generate_thought(messages=messages)
            # Verify payload includes the custom messages
            args, _ = mock_run.call_args
            payload = json.loads(args[0][-1])
            assert payload["messages"][0]["content"] == "Custom history"

    def test_generate_thought_dispatch(self):
        """Test dispatching between providers."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant"}):
            client = LocalInferenceClient()
            assert (
                client.generate_thought("hello") is None
            )  # hits _dispatch_anthropic warning

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-oa"}):
            client = LocalInferenceClient()
            with patch.object(client, "_dispatch_openai_compatible") as mock_dispatch:
                client.generate_thought("hello")
                mock_dispatch.assert_called_once()

    def test_dispatch_openai_compatible_success(self):
        """Test successful inference call via curl."""
        client = LocalInferenceClient()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "choices": [{"message": {"content": "I think, therefore I am."}}],
                "usage": {"total_tokens": 10},
            }
        )

        with patch("subprocess.run", return_value=mock_result):
            response = client.generate_thought("Say something")
            assert response == "I think, therefore I am."
            assert client.last_usage["total_tokens"] == 10

    def test_dispatch_openai_compatible_regex_match(self):
        """Test successful inference with non-JSON stdout (regex extraction)."""
        client = LocalInferenceClient()
        mock_result = MagicMock()
        mock_result.returncode = 0
        # Extra garbage in stdout
        mock_result.stdout = (
            "DEBUG: ... "
            + json.dumps({"choices": [{"message": {"content": "Regex focus."}}]})
            + " ... END DEBUG"
        )

        with patch("subprocess.run", return_value=mock_result):
            response = client.generate_thought("Say something")
            assert response == "Regex focus."

    def test_dispatch_openai_compatible_failure(self):
        """Test inference failure (curl error)."""
        client = LocalInferenceClient()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Connection refused"

        with patch("subprocess.run", return_value=mock_result):
            assert client.generate_thought("hello") is None

    def test_dispatch_openai_compatible_exception(self):
        """Test inference exception handling."""
        client = LocalInferenceClient()
        with patch("subprocess.run", side_effect=RuntimeError("Subprocess Panic")):
            assert client.generate_thought("hello") is None

    def test_context_injection(self):
        """Test that context is injected into the system prompt."""
        client = LocalInferenceClient()
        with patch.object(
            client,
            "_load_sovereign_knowledge",
            return_value="FACT: Sovereignty is life.",
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1
                )  # Don't care about result
                client.generate_thought("hello")
                # Check payload
                args, kwargs = mock_run.call_args
                payload = json.loads(args[0][-1])
                system_msg = payload["messages"][0]["content"]
                assert "[Sovereign Reference Knowledge]" in system_msg
                assert "FACT: Sovereignty is life." in system_msg

    def test_openai_auth_header(self):
        """Test that Authorization header is added when API key is present."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            client = LocalInferenceClient()
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1)
                client.generate_thought("hello")
                cmd = mock_run.call_args[0][0]
                assert "Authorization: Bearer sk-test" in cmd
