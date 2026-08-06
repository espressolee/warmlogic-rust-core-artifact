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
# HANGUL_REGEX is a Unicode range used to detect Korean-language documents, not prose.

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger("CognitiveHarvester")


@dataclass
class InstructionEntry:
    instruction: str
    input: str
    output: str
    source: str  # e.g., "chronicle", "audit", "patch"


class CognitiveHarvester:
    """
    The Memory Harvester.
    Extracts structured 'thought patterns' from the system's history
    to train the Sovereign Model.
    """

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir)
        self.dataset_path = (
            self.root_dir / "meta" / "datasets" / "warmlogic_instruct_v1.jsonl"
        )
        self.chronicle_path = self.root_dir / "meta" / "memory" / "chronicle.md"
        # Ingest external Command Center data if available
        # GOV-003: Use environment variable for path neutrality
        external_dir = os.environ.get(
            "WARMLOGIC_COMMAND_CENTER",
            str(self.root_dir / "external" / "command_center"),
        )
        self.external_data_dir = Path(external_dir) / "library" / "datasets"

    def harvest_all(self) -> List[Dict[str, str]]:
        """Runs all harvest strategies and saves the dataset."""
        entries = []

        # 1. Internal Memories
        internal_entries = self._harvest_chronicle()
        internal_entries.extend(self._harvest_patches())

        # Convert internal entries to ChatML format
        for entry in internal_entries:
            entries.append(self._format_chatml(entry))

        # 2. External Sovereign Knowledge
        if self.external_data_dir.exists():
            entries.extend(self._ingest_external_data())

        self._save_dataset(entries)
        logger.info(f"Harvest complete. Gathered {len(entries)} cognitive samples.")
        return entries

    def _format_chatml(self, entry: InstructionEntry) -> Dict[str, str]:
        """Converts InstructionEntry to ChatML with <thought> block."""
        thought = "To ensure sovereign integrity and alignment with the chronicle."
        if "decision" in entry.output.lower():
            thought = (
                "To make a decision that aligns with past precedents and future goals."
            )
        elif "patch" in entry.source.lower():
            thought = "To implement a functional and secure patch for the detected gap."

        text = (
            f"<|im_start|>user\n{entry.instruction}\nInput:\n{entry.input}<|im_end|>\n"
            f"<|im_start|>assistant\n<thought>\n{thought}\n</thought>\n{entry.output}<|im_end|>"
        )
        return {"text": text}

    def _ingest_external_data(self) -> List[Dict[str, str]]:
        """Reads raw JSONL from Command Center and normalizes to ChatML."""
        external_entries = []
        for file in self.external_data_dir.glob("*.jsonl"):
            try:
                with open(file, "r") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            raw = json.loads(line)
                            # Normalization Logic
                            if "text" in raw:
                                external_entries.append(raw)
                            elif "instruction" in raw:
                                # Retrofit old Alpaca style to ChatML
                                entry = InstructionEntry(
                                    instruction=raw.get("instruction", ""),
                                    input=raw.get("input", ""),
                                    output=raw.get("output", ""),
                                    source="external_legacy",
                                )
                                external_entries.append(self._format_chatml(entry))
                        except Exception:
                            continue
                logger.info(f"Ingested {file.name}")
            except Exception as e:
                logger.warning(f"Failed to ingest {file}: {e}")
        return external_entries

    def _harvest_textbooks(self) -> List[Dict[str, str]]:
        """
        [Phase 30] Korean Language Alignment.
        Ingests Markdown documentation as 'Textbook' knowledge.
        Focuses on files containing Korean characters.
        """
        textbook_entries = []
        docs_dir = self.root_dir / "docs"

        if not docs_dir.exists():
            return []

        import re

        HANGUL_REGEX = re.compile(r"[가-힣]")

        for file in docs_dir.rglob("*.md"):
            try:
                content = file.read_text(encoding="utf-8")
                # Check for significant Korean content (> 10 characters)
                if len(HANGUL_REGEX.findall(content)) > 10:
                    # Create a "Knowledge" entry
                    # Prompt: Explain [Filename Topic] in Korean.
                    topic = (
                        file.stem.replace("_", " ").replace("ko", "").strip().title()
                    )

                    entry = InstructionEntry(
                        instruction=f"Explain the technical details of '{topic}' in Korean based on the WarmLogic documentation.",
                        input="",
                        output=content[
                            :2500
                        ],  # Reduced to avoid OOM (approx 1000-1500 tokens)
                        source=f"textbook_{file.name}",
                    )
                    textbook_entries.append(self._format_chatml(entry))
                    logger.info(f"🇰🇷 Ingested Textbook: {file.name}")
            except Exception as e:
                logger.warning(f"Failed to read doc {file}: {e}")

        return textbook_entries

    def harvest_all(
        self, output_path: str = "meta/datasets/warmlogic_instruct_v1.jsonl"
    ):
        """Main execution entry point."""
        logger.info("Starting Cognitive Harvest...")

        dataset = []
        # 1. Internal Memories (Need formatting)
        internal_code = self._harvest_system_code()
        internal_chronicle = self._harvest_chronicle()

        for entry in internal_code + internal_chronicle:
            dataset.append(self._format_chatml(entry))

        # 2. External & Pre-formatted Data
        dataset.extend(self._ingest_external_data())
        dataset.extend(self._harvest_textbooks())  # Added in Phase 30

        # Save to JSONL
        out_file = self.root_dir / output_path
        out_file.parent.mkdir(parents=True, exist_ok=True)

        with open(out_file, "w") as f:
            for entry in dataset:
                if isinstance(entry, InstructionEntry):
                    entry = self._format_chatml(entry)
                f.write(json.dumps(entry) + "\n")

        logger.info(f"Dataset saved to {output_path}")
        logger.info(f"Harvest complete. Gathered {len(dataset)} cognitive samples.")

    def _save_dataset(self, entries: List[Dict[str, str]]):
        """Saves entries to standard JSONL."""
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.dataset_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info(f"Dataset saved to {self.dataset_path}")

    def _harvest_chronicle(self) -> List[InstructionEntry]:
        """
        Parses chronicle.md for 'Decision -> Consequence' patterns.
        Looking for:
        ## [2025-XX-XX] Event Title
        - Context: ...
        - Decision: ...
        """
        entries = []
        if not self.chronicle_path.exists():
            return entries

        content = self.chronicle_path.read_text()
        # Heuristic: Split by headers
        sections = re.split(r"^## ", content, flags=re.MULTILINE)

        for section in sections:
            if not section.strip():
                continue

            lines = section.strip().split("\n")
            title = lines[0]

            # Simple heuristic extraction
            context = ""
            decision = ""

            for line in lines:
                if line.strip().startswith("- Context:"):
                    context = line.split(":", 1)[1].strip()
                elif line.strip().startswith("- Decision:"):
                    decision = line.split(":", 1)[1].strip()

            if context and decision:
                entries.append(
                    InstructionEntry(
                        instruction="Analyze the following system context and make a sovereign decision.",
                        input=f"Context: {context}",
                        output=f"Decision: {decision}",
                        source="chronicle",
                    )
                )

        return entries

    def _harvest_patches(self) -> List[InstructionEntry]:
        """
        Harvests successful patches from the AutonomousPatcher logs (if available)
        or simulated history.
        """
        # In a real run, we'd parse .patch logs.
        # For this bootrap phase, we generate synthetic "Gold Standard" examples
        # based on our codebase conventions.
        entries = []

        # Example 1: Stub Fixing
        entries.append(
            InstructionEntry(
                instruction="Implement the following function stub to match the docstring description.",
                input='def add_numbers(a, b):\n    """Adds two numbers."""\n    raise NotImplementedError()',
                output='def add_numbers(a, b):\n    """Adds two numbers."""\n    return a + b',
                source="synthetic_gold",
            )
        )

        # Example 2: Security Hardening (Aegis)
        entries.append(
            InstructionEntry(
                instruction="Review the code for security vulnerabilities and apply a fix.",
                input="user_input = get_input()\neval(user_input)",
                output="# [Aegis Patch] Blocked dangerous eval\nimport ast\n# user_input = get_input()\n# safe_eval(user_input)",
                source="synthetic_gold",
            )
        )

    def _harvest_system_code(self) -> List[InstructionEntry]:
        """
        Scans logical kernel files for docstrings and signatures.
        Generates: "Write a function that...", "Explain class..."
        """
        entries = []
        kernel_dir = self.root_dir / "warm_logic" / "kernel"

        if not kernel_dir.exists():
            return entries

        for file in kernel_dir.rglob("*.py"):
            if "test" in file.name:
                continue

            try:
                content = file.read_text()
                # Heuristic: Extract classes and functions with docstrings
                # (Simple regex for now, AST would be better but heavier)
                funcs = re.findall(
                    r'def\s+(\w+)\(.*\):\n\s+"""(.*?)"""', content, re.DOTALL
                )

                for fname, doc in funcs:
                    doc = doc.strip().split("\n")[0]  # First line of docstring
                    entries.append(
                        InstructionEntry(
                            instruction=f"Write a Python function named '{fname}' that performs: {doc}",
                            input="",
                            output=f"Computed from context: {file.name}",  # Placeholder for actual code extraction if needed
                            source="codebase",
                        )
                    )
            except Exception:
                continue

        return entries


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    harvester = CognitiveHarvester()
    harvester.harvest_all()
