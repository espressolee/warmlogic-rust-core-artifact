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
[Phase 44] Vision Cortex.
High-level perception module that wraps the raw VisionClient.
Provides the 'Eyes' for Level 5 Autonomy.
"""

import logging
from pathlib import Path
from typing import Optional, Union

# Import low-level vision client
try:
    from warm_logic.kernel.intelligence.vision import VisionClient
except ImportError:
    VisionClient = None

logger = logging.getLogger("VisionCortex")


class VisionCortex:
    """
    [] The Visual Cortex.
    Integrates visual perception into the agent's cognitive loop.
    """

    def __init__(self):
        self.client = VisionClient() if VisionClient else None
        if not self.client:
            logger.warning("VisionClient unavailable. VisionCortex is blind.")

    def perceive(
        self, image_source: Union[str, Path], prompt: Optional[str] = None
    ) -> str:
        """
        The primary sensory method.
        'Looks' at an image and returns a comprehensive description of reality.

        Args:
            image_source: Path to image file or URL.

        Returns:
            Description string.
        """
        if not self.client:
            return "[Vision Unavailable: Cortex Blind]"

        logger.info(f"[Cortex] Perceiving visual input: {image_source}")

        # General perception prompt
        perception_prompt = (
            prompt
            or "Describe this image in detail. Focus on structure, text, and anomalies."
        )
        description = self.client.analyze_image(
            prompt=perception_prompt,
            images=image_source,
            system_prompt="You are the Visual Cortex of an AI. Encode visual reality into text.",
        )

        return description or "[Vision Failed: No Description]"

    def perceive_screen(self, image_path: Union[str, Path]) -> str:
        """Specialized perception for UI/Screens."""
        if not self.client:
            return "[Vision Unavailable]"

        return self.client.describe_screenshot(image_path) or "[Vision Failed]"
