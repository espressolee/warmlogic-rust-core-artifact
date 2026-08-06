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
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("SovereignIntelligenceOps")


class IntelligenceRegistry:
    """
    Sovereign Intelligence Registry.
    Manages datasets, model weights, and training configurations.
    """

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir)
        self.dataset_path = (
            self.root_dir / "meta" / "datasets" / "warmlogic_instruct_v1.jsonl"
        )

    def validate_dataset_integrity(self) -> bool:
        """
        Verifies that the generated instruction dataset is valid JSONL
        and follows the {instruction, input, output} schema.
        """
        if not self.dataset_path.exists():
            logger.error(f"Dataset not found at {self.dataset_path}")
            return False

        try:
            valid_count = 0
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f):
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        if "text" not in entry:
                            logger.error(
                                f"❌ Invalid schema at line {line_num}: Missing 'text' key."
                            )
                            return False

                        # Partial validation for ChatML format
                        if "<|im_start|>" not in entry["text"]:
                            logger.warning(
                                f"⚠️ Line {line_num} might not be ChatML formatted."
                            )

                        valid_count += 1
                    except json.JSONDecodeError:
                        logger.error(f"JSON Decode Error at line {line_num}")
                        return False

            logger.info(
                f"✅ Dataset Integrity Verified: {valid_count} valid instructions."
            )
            return True

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False

    def get_dataset_stats(self) -> Dict[str, Any]:
        """Returns statistics about the dataset."""
        if not self.dataset_path.exists():
            return {"status": "missing"}

        size_bytes = self.dataset_path.stat().st_size
        with open(self.dataset_path) as f:
            line_count = sum(1 for _ in f)
        return {
            "status": "ready",
            "path": str(self.dataset_path),
            "size_bytes": size_bytes,
            "sample_count": line_count,
        }
