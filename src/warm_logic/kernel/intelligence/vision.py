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
[Phase A3: Agent ] Vision Module for Multimodal Input.
Enables image analysis through local vision-capable LLMs (LLaVA, BakLLaVA).
"""

import base64
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("SovereignVision")


class VisionClient:
    """
    [] The Eyes of Sovereignty.
    Enables multimodal input (text + images) via vision-capable LLMs.

    Supports:
    - Local files (PNG, JPEG, WebP)
    - Base64 encoded images
    - URLs (passed directly to vision model)
    """

    def __init__(
        self,
        api_base: str = "http://127.0.0.1:11434/v1",
        model_name: str = "moondream",
    ):
        self.api_base = os.getenv("WARM_LOGIC_VISION_API", api_base)
        self.model_name = os.getenv("WARM_LOGIC_VISION_MODEL", model_name)
        self.timeout = (
            300  # Vision models need more time (increased for local hardware)
        )
        self.max_image_size = 4 * 1024 * 1024  # 4MB limit

    def _encode_image(self, image_path: Union[str, Path]) -> Optional[str]:
        """Encode a local image file to base64."""
        path = Path(image_path)
        if not path.exists():
            logger.error(f"Image not found: {path}")
            return None

        # Check file size
        if path.stat().st_size > self.max_image_size:
            logger.warning(f"Image too large: {path} ({path.stat().st_size} bytes)")
            return None

        # Determine MIME type
        suffix = path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        mime_type = mime_types.get(suffix, "image/png")

        try:
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            return f"data:{mime_type};base64,{encoded}"
        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            return None

    def _build_vision_message(
        self,
        text: str,
        images: List[Union[str, Path]],
    ) -> Dict[str, Any]:
        """Build a multimodal message with text and images."""
        content: List[Dict[str, Any]] = []

        # Add text content
        content.append({"type": "text", "text": text})

        # Add image content
        for image in images:
            if isinstance(image, str) and image.startswith(("http://", "https://")):
                # URL - pass directly
                content.append({"type": "image_url", "image_url": {"url": image}})
            elif isinstance(image, str) and image.startswith("data:"):
                # Already base64 encoded
                content.append({"type": "image_url", "image_url": {"url": image}})
            else:
                # Local file - encode
                encoded = self._encode_image(image)
                if encoded:
                    content.append({"type": "image_url", "image_url": {"url": encoded}})

        return {"role": "user", "content": content}

    def analyze_image(
        self,
        prompt: str,
        images: Union[str, Path, List[Union[str, Path]]],
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """
        Analyze one or more images with a text prompt.

        Args:
            prompt: The analysis question/instruction.
            images: Single image or list of images (paths or URLs).
            system_prompt: Optional system context.

        Returns:
            The model's analysis response.
        """
        # Normalize images to list
        if not isinstance(images, list):
            images = [images]

        default_system = (
            "You are WarmLogic Vision, a sovereign AI with visual perception. "
            "Analyze images carefully and provide detailed, accurate descriptions. "
            "If you see code, UI elements, or technical content, describe them precisely."
        )

        messages = [
            {"role": "system", "content": system_prompt or default_system},
            self._build_vision_message(prompt, images),
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 2048,
        }

        try:
            # Use a temporary file for the payload to avoid "Argument list too long" errors
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".json"
            ) as tf:
                json.dump(payload, tf)
                temp_payload_path = tf.name

            # Use curl for reliability (same pattern as llm_bridge)
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
                "-d",
                f"@{temp_payload_path}",
            ]

            logger.info(f"[Vision] Analyzing {len(images)} image(s)...")

            # Clean environment
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
                try:
                    import re

                    match = re.search(r"\{.*\}", raw_output, re.DOTALL)
                    if match:
                        data = json.loads(match.group())
                    else:
                        data = json.loads(raw_output)

                    if "choices" in data:
                        content = data["choices"][0]["message"]["content"]
                        logger.info(
                            f"👁️ [Vision] Analysis complete ({len(content)} chars)"
                        )
                        return content
                    else:
                        logger.error(
                            f"❌ [Vision] Invalid response: {raw_output[:200]}"
                        )
                except json.JSONDecodeError as je:
                    logger.error(f"[Vision] JSON Error: {je}")
                    return None
            else:
                return None

        except subprocess.TimeoutExpired:
            logger.error("[Vision] Timeout - image analysis took too long")
            return None
        except Exception as e:
            logger.error(f"[Vision] Error: {e}")
            return None
        finally:
            # Cleanup temporary file
            if "temp_payload_path" in locals() and os.path.exists(temp_payload_path):
                os.remove(temp_payload_path)

    def describe_screenshot(self, image_path: Union[str, Path]) -> Optional[str]:
        """Convenience method for UI/screenshot analysis."""
        return self.analyze_image(
            prompt="Describe this screenshot in detail. Identify all UI elements, text, buttons, and their layout.",
            images=image_path,
            system_prompt=(
                "You are a UI analysis expert. "
                "Describe the screenshot with focus on: "
                "1) Main UI components and layout "
                "2) All visible text and labels "
                "3) Interactive elements (buttons, inputs) "
                "4) Color scheme and visual style"
            ),
        )

    def extract_text_from_image(self, image_path: Union[str, Path]) -> Optional[str]:
        """Convenience method for OCR-like text extraction."""
        return self.analyze_image(
            prompt="Extract all visible text from this image. Format it clearly, preserving structure where possible.",
            images=image_path,
            system_prompt=(
                "You are an OCR specialist. "
                "Extract all text visible in the image. "
                "Preserve formatting like tables, lists, and headings. "
                "If text is unclear, indicate with [unclear]."
            ),
        )

    def analyze_code_screenshot(self, image_path: Union[str, Path]) -> Optional[str]:
        """Convenience method for code screenshot analysis."""
        return self.analyze_image(
            prompt="Analyze this code screenshot. Identify the language, explain what the code does, and note any potential issues.",
            images=image_path,
            system_prompt=(
                "You are a code review expert. "
                "Analyze the code in this image: "
                "1) Identify the programming language "
                "2) Explain the code's purpose "
                "3) Note any bugs, issues, or improvements "
                "4) Extract the actual code text if possible"
            ),
        )


def analyze_image(
    prompt: str,
    images: Union[str, Path, List[Union[str, Path]]],
) -> Optional[str]:
    """Convenience function for quick image analysis."""
    client = VisionClient()
    return client.analyze_image(prompt, images)
