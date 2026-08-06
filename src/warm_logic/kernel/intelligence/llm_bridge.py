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
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("LocalInferenceBridge")


class LocalInferenceClient:
    """
    The Voice of Sovereignty.
    Connects to a local quantized model (GGUF) via an OpenAI-compatible API
    (e.g., ollama, llama.cpp-server).
    """

    def __init__(self, api_base: Optional[str] = None):
        """
        [Phase 55.2] Model Agnostic Bridge.
        Prioritizes Environment Variables for Provider configuration.
        """
        # 1. Identity & Provider
        self.api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("WARM_LOGIC_API_KEY")
        )

        # Determine provider from URL or Keys
        env_provider = os.getenv("WARM_LOGIC_PROVIDER")
        if env_provider:
            self.provider = env_provider.lower()
        elif os.getenv("ANTHROPIC_API_KEY"):
            self.provider = "anthropic"
        elif self.api_key:
            self.provider = "openai"
        else:
            self.provider = "local"

        # 2. Endpoints & Models
        if self.provider == "openai":
            default_base = "https://api.openai.com/v1"
            default_model = "gpt-4o"
        elif self.provider == "anthropic":
            default_base = "https://api.anthropic.com/v1"
            default_model = "claude-3-5-sonnet-latest"
        elif self.provider == "openrouter":
            default_base = "https://openrouter.ai/api/v1"
            default_model = "anthropic/claude-3.5-sonnet"
        else:
            default_base = "http://127.0.0.1:11434/v1"
            default_model = "models/warmlogic-v1-fused"

        self.api_base = os.getenv("WARM_LOGIC_LLM_API", api_base or default_base)
        self.model_name = os.getenv("WARM_LOGIC_MODEL", default_model)
        self.timeout = int(os.getenv("WARM_LOGIC_TIMEOUT", "60"))
        self.last_usage: Optional[Dict[str, int]] = None

        logger.info(
            f"🧠 [Sovereign Bridge] Active: {self.provider.upper()} (Model: {self.model_name})"
        )

    def _load_sovereign_knowledge(self) -> str:
        """
        [Phase 32] RAG (Retrieval-Augmented Generation).
        Loads the Sovereign Knowledge Graph to override hallucinations.
        """
        kg_path = Path("docs/SOVEREIGN_KNOWLEDGE_GRAPH.md")
        if kg_path.exists():
            try:
                # Read key sections - expanded for richer context
                return kg_path.read_text()[:16000]
            except Exception:
                pass
        return ""

    def generate_thought(
        self,
        prompt: Optional[str] = None,
        messages: Optional[list] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """
        Sends a prompt or message list to the selected provider.
        """
        if self.provider == "anthropic":
            return self._dispatch_anthropic(prompt, messages, system_prompt)
        else:
            # Default OpenAI-compatible dispatch (Ollama, OpenAI, OpenRouter)
            return self._dispatch_openai_compatible(prompt, messages, system_prompt)

    def _dispatch_openai_compatible(
        self, prompt, messages, system_prompt
    ) -> Optional[str]:
        default_system = (
            "You are WarmLogic, a sovereign AI. "
            "OPERATING RULE: YOU MUST THINK BEFORE YOU ACT.\n"
            "Format your response as follows:\n"
            "<thought>\n"
            "Analyze the request.\n"
            "Plan the necessary steps.\n"
            "Verify safety/logic.\n"
            "</thought>\n"
            "\n"
            "Then, if you need to perform an action, output a JSON block (or a LIST of blocks for multiple steps):\n"
            '1. Shell command: {"action": "shell", "command": "..."}\n'
            '2. Write file: {"action": "write_file", "path": "...", "content": "..."}\n'
            '3. Read file: {"action": "read_file", "path": "..."}\n'
            '4. Search code: {"action": "search", "query": "..."}\n'
            '5. Check diff: {"action": "diff"}\n'
            'Example Chain: [{"action": "search", ...}, {"action": "read_file", ...}]\n'
            "If no action is needed, provide your final answer/summary after the thought block."
        )

        # Build message history
        if messages:
            final_messages = messages
        else:
            final_messages = [
                {"role": "system", "content": system_prompt or default_system},
                {"role": "user", "content": prompt},
            ]

        # [Phase 32] Dynamic Context Injection
        context = self._load_sovereign_knowledge()
        if context:
            for msg in final_messages:
                if msg["role"] == "system" and "[End Reference]" not in msg["content"]:
                    msg[
                        "content"
                    ] += f"\n\n[Sovereign Reference Knowledge]\n{context}\n[End Reference]"
                    break

        payload = {
            "model": self.model_name,
            "messages": final_messages,
            "stream": False,
            "temperature": 0.2,
        }

        try:
            cmd = [
                "curl",
                "-s",
                "--noproxy",
                "*",
                "-X",
                "POST",
                f"{self.api_base}/chat/completions",
                "-H",
                "Content-Type: application/json",
            ]

            if self.api_key:
                cmd.extend(["-H", f"Authorization: Bearer {self.api_key}"])

            cmd.extend(["-d", json.dumps(payload)])

            clean_env = os.environ.copy()
            for key in [
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "http_proxy",
                "https_proxy",
                "ALL_PROXY",
                "all_proxy",
            ]:
                clean_env.pop(key, None)

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout, env=clean_env
            )
            if result.returncode == 0:
                raw_output = result.stdout.strip()
                import re

                match = re.search(r"\{.*\}", raw_output, re.DOTALL)
                data = json.loads(match.group()) if match else json.loads(raw_output)

                # [Phase 55.6.1] Capture Token Usage
                self.last_usage = data.get("usage")
                if self.last_usage:
                    logger.debug(f"[Inference] Usage: {self.last_usage}")

                return data["choices"][0]["message"]["content"]
            return None
        except Exception as e:
            logger.error(f"[Sovereign] Inference error: {e}")
            return None

    def _dispatch_anthropic(self, prompt, messages, system_prompt) -> Optional[str]:
        logger.warning(
            "Anthropic direct dispatch pending Phase 55.2.1. Use OpenRouter."
        )
        return None
