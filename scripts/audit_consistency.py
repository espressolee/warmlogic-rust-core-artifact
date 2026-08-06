import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple


class SovereignAuditor:
    """ Sequential Documentation Auditor with LLM-Powered Semantic Analysis.
    Optimized for stability in memory-constrained local environments.
    """

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.llama_cli = "archives/legacy_cleanup/llama.cpp/build/bin/llama-cli"
        self.model_path = "archives/legacy_cleanup/llama.cpp/models/llama3.1-8b/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
        self.dyld_path = "archives/legacy_cleanup/llama.cpp/build/bin"

        # Semantic & Context Rules
        self.forbidden_terms = [
            r"\bAI God\b",
            r"\bWorld Controller\b",
            r"\bMaster of Civilization\b",
        ]
        self.results = {"errors": [], "warnings": [], "passed": [], "llm_reports": {}}

    def _call_llm(self, prompt: str) -> str:
        """Calls the local LLM sequentially."""
        env = os.environ.copy()
        env["DYLD_LIBRARY_PATH"] = self.dyld_path

        full_prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\nYou are the Sovereign Fleet Auditor. Your goal is to score documentation for ground truth, Epistemic Humility, and Technical Consistency.<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"

        cmd = [
            self.llama_cli,
            "-m",
            self.model_path,
            "-p",
            full_prompt,
            "-n",
            "256",
            "--temp",
            "0.1",
            "--no-display-prompt",
        ]

        try:
            # Reverting to 0.1 temp for deterministic scoring
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, timeout=180
            )
            if result.returncode != 0:
                return f"LLM_ERROR: {result.stderr}"
            return result.stdout.strip()
        except Exception as e:
            return f"LLM_EXCEPTION: {str(e)}"

    def semantic_audit(self, file_path: Path, content: str) -> Tuple[str, int, str]:
        rel_path = file_path.relative_to(self.root_dir)
        prompt = f"""
Audit the following document titled '{rel_path}':
---
{content[:1500]}
---

Assess based on:
1. Technical Consistency with (Chronos, Whisper, Phantom).
2. Epistemic Humility (Avoid megalomania).
3. Evidence (Are claims verifiable?).

Provide a report in this exact format:
SCORE: [0-35]
CRITIQUE: [One sentence harsh critique]
FIX: [One sentence recommendation]
"""
        response = self._call_llm(prompt)
        score_match = re.search(r"SCORE:\s*(\d+)", response)
        score = int(score_match.group(1)) if score_match else 0
        return str(rel_path), score, response

    def run(self):
        print(f"Starting SEQUENTIAL Deep Semantic Audit (Memory Safe)...")

        target_dirs = ["docs/protocol", "docs/analysis", "README.md"]
        files_to_audit = []

        for target in target_dirs:
            p = self.root_dir / target
            if p.is_file():
                files_to_audit.append(p)
            elif p.is_dir():
                files_to_audit.extend(list(p.rglob("*.md")))

        for f in files_to_audit:
            # Basic checks
            content = ""
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                content = f.read_bytes().decode("utf-8", errors="replace")

            # Metadata Check
            if not any(h in content for h in self.required_headers):
                self.results["warnings"].append(
                    f"[METADATA] Missing headers in {f.name}"
                )

            # LLM Audit
            rel_path, score, report = self.semantic_audit(f, content)
            print(f"Audit Complete: {rel_path} (Score: {score}/35)")
            self.results["llm_reports"][rel_path] = {"score": score, "report": report}
            if score < 30:
                self.results["errors"].append(f"Score {score} for {rel_path}")

        print("\n" + "=" * 50)
        print(" SOVEREIGN FINAL AUDIT REPORT")
        print("=" * 50)
        for path, data in self.results["llm_reports"].items():
            print(f"\n[{path}] Score: {data['score']}/35\nReport: {data['report']}")


if __name__ == "__main__":
    auditor = SovereignAuditor("./")
    auditor.run()
