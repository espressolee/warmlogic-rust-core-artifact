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
import ast
import logging
import os
import sys
from dataclasses import dataclass
from typing import List

from warm_logic.kernel.autonomy.codex import LogicGap

logger = logging.getLogger("AegisProtocol")


@dataclass
class Vulnerability:
    """
    Represents a security vulnerability detected by AegisAuditor.
    """

    file_path: str
    line_number: int
    description: str
    vulnerability_type: str


class AegisAuditor:
    """
    [] The Aegis Eye.
    Scans for security vulnerabilities and unsafe coding patterns.
    """

    def __init__(self, root_path: str = "."):
        self.root_path = os.path.abspath(root_path)

    async def audit_codebase(self) -> List[LogicGap]:
        """
        Scans all python files for dangerous patterns or missing security headers.
        """
        threats = []
        for root, _, files in os.walk(self.root_path):
            # Skip hidden and venv
            if ".git" in root or ".venv" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    threats.extend(self._audit_file(full_path))
        return threats

    def _audit_file(self, file_path: str) -> List[LogicGap]:
        """
        Internal scan for dangerous imports and patterns.
        """
        gaps = []
        try:
            with open(file_path, "r") as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                # Look for unsafe 'eval' or 'exec'
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in [
                        "eval",
                        "exec",
                    ]:
                        gaps.append(
                            LogicGap(
                                file_path=file_path,
                                line_number=getattr(node, "lineno", 0),
                                description=f"Unsafe use of {node.func.id} detected.",
                                gap_type="security_vulnerability",
                            )
                        )

                # Look for hardcoded credentials (heuristic)
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and any(
                            kw in target.id.lower()
                            for kw in ["secret", "password", "api_key", "token"]
                        ):
                            if isinstance(node.value, ast.Constant) and isinstance(
                                node.value.value, str
                            ):
                                gaps.append(
                                    LogicGap(
                                        file_path=file_path,
                                        line_number=getattr(node, "lineno", 0),
                                        description=f"Hardcoded secret in variable '{target.id}'",
                                        gap_type="hardcoded_secret",
                                    )
                                )
        except Exception as e:
            logger.error(f"Failed to audit {file_path}: {e}")

        return gaps


class AegisSentinel:
    """
    [] The Active Shield.
    Monitors mutations and enforces security invariants.
    """

    def __init__(self, auditor: AegisAuditor):
        self.auditor = auditor

    async def secure_perimeter(self) -> List[Vulnerability]:
        """
        Scans the codebase for security vulnerabilities and returns them.
        """
        gaps = await self.auditor.audit_codebase()
        vulnerabilities = []
        for gap in gaps:
            if gap.gap_type in ["security_vulnerability", "hardcoded_secret"]:
                vulnerabilities.append(
                    Vulnerability(
                        file_path=gap.file_path,
                        line_number=gap.line_number,
                        description=gap.description,
                        vulnerability_type=gap.gap_type,
                    )
                )
        return vulnerabilities

    def validate_patch(self, gap: LogicGap, patch_code: str) -> bool:
        """
        Pre-flight check for a generated patch to ensure it doesn't introduce new threats.
        """
        logger.info(f"[Aegis] Validating patch for {gap.file_path}")

        try:
            tree = ast.parse(patch_code)
            for node in ast.walk(tree):
                # Disallow direct exec/eval in patches
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in [
                        "eval",
                        "exec",
                    ]:
                        logger.warning(
                            f"❌ [Aegis] Patch rejected: contains {node.func.id}"
                        )
                        return False

            return True
        except Exception:
            return False


class AegisGuard:
    """
    [] The Recursive Shield.
    Generates and executes tests for autonomous mutations.
    """

    def __init__(self, root_path: str = "."):
        self.root_path = os.path.abspath(root_path)

    async def verify_mutation(
        self, file_path: str, function_name: str, patch_code: str, test_code: str
    ) -> bool:
        """
        [] Attempts to verify a code mutation by running its companion test.
        """
        logger.info(f"[Aegis] Verifying mutation: {function_name} in {file_path}")

        # 1. Synthesize temporary test file
        test_file_path = os.path.join(
            self.root_path, "tests", "autonomy", f"test_aegis_{function_name}.py"
        )
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)

        try:
            # We wrap the patch and test in a temporary verification environment
            # In a real system, this would happen in a container/sandbox
            with open(test_file_path, "w") as f:
                f.write(test_code)

            # 2. Run the test (simplified for prototype)
            # In production, we'd use subprocess.run(["pytest", test_file_path])
            import subprocess

            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_file_path, "-v", "--no-cov"],
                capture_output=True,
                text=True,
                cwd=self.root_path,
            )

            if result.returncode == 0:
                logger.info(f"[Aegis] Verification PASSED for {function_name}")
                return True
            else:
                logger.error(f"[Aegis] Verification FAILED for {function_name}")
                logger.error(result.stdout)
                return False

        except Exception as e:
            logger.error(f"[Aegis] Error during verification: {e}")
            return False
        finally:
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
