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
from typing import Any, Dict, Optional

logger = logging.getLogger("StochasticGateway")


class StochasticGateway:
    """
    Stochastic Gateway.
    Bridges the gap between deterministic GVM and stochastic LLM reasoning.
    """

    def __init__(self, provider_url: str = "http://localhost:11434/api/generate"):
        self.provider_url = provider_url
        self.model = "llama3"

    async def check_ollama_health(self) -> bool:
        """Verifies if Ollama is accessible."""
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                # Ollama's base URL usually returns a simple 200/404 if running
                # but /api/tags is a better check
                health_url = self.provider_url.replace("/api/generate", "/api/tags")
                response = await client.get(health_url, timeout=5.0)
                return response.status_code == 200
        except Exception:
            return False

    async def get_mutation_strategy(
        self, context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Requests an evolution strategy from the stochastic inference engine (Ollama).
        """
        import httpx

        logger.info("[convergence] Requesting stochastic strategy from Ollama...")

        source_code = context.get("source_code", "")
        prompt = (
            "You are the WarmLogic convergence Engine. "
            "Suggest a minor Python code optimization or improvement for the following code. "
            'Return JSON only: {"proposed_change": "...", "new_code": "...", "confidence": 0.95, "reasoning": "..."}\n\n'
            f"Code:\n{source_code}"
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.provider_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    # Ollama returns { "response": "..." } where response is the JSON string
                    content = data.get("response", "{}")
                    strategy = json.loads(content)

                    logger.info(
                        f"✨ [convergence] Ollama proposed strategy with {strategy.get('confidence', 0) * 100}% confidence."
                    )

                    # Ethical Quorum.
                    # Do not return raw code; return a 'Governance Proposal' packet.
                    return {
                        "type": "AI_MUTATION_PROPOSAL",
                        "proposer": "SINGULARITY_LLM",
                        "strategy": strategy,
                        "requires_quorum": True,
                    }
                else:
                    logger.warning(
                        f"🌪️ [convergence] Ollama API error: {response.status_code}"
                    )
        except Exception as e:
            logger.error(f"[convergence] Failed to reach Ollama: {e}")

        # hardware attestation enforcement: Stubs are deprecated.
        # Fallback to a hard error or re-try instead of silent simulation
        # unless explicitly in 'demo' mode.
        logger.error(
            "🌪️ [convergence] Stochastic inference UNAVAILABLE. Reality level compromised."
        )
        return None


class ConfidenceGate:
    """
    Confidence Gate.
    Filters out unstable stochastic proposals.
    """

    MIN_STOCHASTIC_CONFIDENCE = 0.9

    @staticmethod
    def validate_proposal(proposal: Dict[str, Any]) -> bool:
        conf = proposal.get("confidence", 0.0)
        if conf >= ConfidenceGate.MIN_STOCHASTIC_CONFIDENCE:
            logger.info(
                f"✅ [Gate] Stochastic proposal PASSED ConfidenceGate ({conf})."
            )
            return True
        logger.warning(f"[Gate] Stochastic proposal FAILED ConfidenceGate ({conf}).")
        return False
