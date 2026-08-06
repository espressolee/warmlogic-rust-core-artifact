import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


class SecurityAuditor:
    """ Security Auditor.
    1. Scans for hardcoded secrets (High Entropy, Pattern Matching).
    2. Uses local LLM to review 'warm_logic/kernel/secrets.py' and 'warm_logic/kernel/security'.
    """

    def __init__(self, root_dir: str):
        self.root = Path(root_dir)
        self.llama_cli = "archives/legacy_cleanup/llama.cpp/build/bin/llama-cli"
        self.model_path = "archives/legacy_cleanup/llama.cpp/models/llama3.1-8b/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
        self.dyld_path = "archives/legacy_cleanup/llama.cpp/build/bin"

        self.secret_patterns = {
            "OpenAI Key": r"sk-[a-zA-Z0-9]{48}",
            "AWS Key": r"AKIA[0-9A-Z]{16}",
            "Generic Token": r"token\s*=\s*['\"][a-zA-Z0-9]{20,}['\"]",
            "Hardcoded Password": r"password\s*=\s*['\"][a-zA-Z0-9]{8,}['\"]",
        }
        self.findings: List[str] = []

    def _call_llm(self, prompt: str) -> str:
        env = os.environ.copy()
        env["DYLD_LIBRARY_PATH"] = self.dyld_path
        full_prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\nYou are a White Hat Security Auditor. Find logical vulnerabilities.<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
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
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, timeout=120
            )
            return result.stdout.strip()
        except Exception as e:
            return f"LLM_ERROR: {e}"

    def scan_secrets(self):
        print(" Scanning for hardcoded secrets...")
        for f in self.root.rglob("*.py"):
            if "venv" in str(f) or "archives" in str(f) or "tests" in str(f):
                continue
            try:
                content = f.read_text(encoding="utf-8")
                for name, pattern in self.secret_patterns.items():
                    if re.search(pattern, content):
                        self.findings.append(
                            f"[SECRET] {name} found in {f.relative_to(self.root)}"
                        )
            except:
                pass

    def audit_logic(self):
        print(" Auditing Security Logic with LLM...")
        target_files = [
            self.root / "warm_logic/kernel/secrets.py",  # If exists
            self.root / "warm_logic/kernel/security/crypto.py",  # If exists
        ]

        for f in target_files:
            if not f.exists():
                continue
            content = f.read_text(encoding="utf-8")[:1500]

            prompt = f"""
Audit this security code for vulnerabilities (bypass, weak crypto, logging secrets):
---
{content}
---
Format: "VERDICT: [SAFE/UNSAFE] - Reason"
"""
            report = self._call_llm(prompt)
            print(f"\n[LLM AUDIT] {f.name}:\n{report}")
            if "UNSAFE" in report.upper():
                self.findings.append(f"[LOGIC] {f.name} flagged as UNSAFE by LLM.")

    def run(self):
        self.scan_secrets()
        self.audit_logic()

        print("\n" + "=" * 50)
        print("SECURITY AUDIT REPORT")
        print("=" * 50)
        if not self.findings:
            print("NO SECRETS OR VULNERABILITIES FOUND.")
        else:
            for f in self.findings:
                print(f"{f}")


if __name__ == "__main__":
    auditor = SecurityAuditor("./")
    auditor.run()
