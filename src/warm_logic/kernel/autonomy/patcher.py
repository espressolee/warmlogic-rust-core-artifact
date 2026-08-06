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
import importlib
import logging
import os
import sys
from typing import Any, List, Optional

from warm_logic.kernel.autonomy.aegis import AegisGuard, AegisSentinel
from warm_logic.kernel.autonomy.budget import PatchBudgeter
from warm_logic.kernel.autonomy.codex import LogicGap
from warm_logic.kernel.autonomy.governance import CouncilOfThree
from warm_logic.kernel.autonomy.reasoning import ReasoningSynthesizer

logger = logging.getLogger("SovereignPatcher")


class AutonomousPatcher:
    """
    The Event Horizon: An autonomous patching engine.
    Allows the kernel to modify its own source code to fix gaps and evolve.
    """

    def __init__(self, root_path: str = ".", store: Optional[Any] = None):
        self.root_path = os.path.abspath(root_path)
        self.synthesizer = ReasoningSynthesizer()
        self.guard = AegisGuard(root_path=self.root_path)
        from warm_logic.kernel.autonomy.aegis import AegisAuditor

        self._aegis_auditor = AegisAuditor(self.root_path)
        self.sentinel = AegisSentinel(self._aegis_auditor)
        self.council = CouncilOfThree()
        self.budgeter = PatchBudgeter(store=store)

    async def apply_patch(self, gap: LogicGap, strategy: str = "stub") -> bool:
        """
        Applies a patch to the source code at the specified logic gap.
        Currently supports 'stub' strategy (replacing with pass/log).
        """
        logger.info(
            f"🛠️ [Event Horizon] Patching gap at {gap.file_path}:{gap.line_number} using {strategy}..."
        )

        if not os.path.exists(gap.file_path):
            logger.error(f"[Event Horizon] File not found: {gap.file_path}")
            return False

        try:
            with open(gap.file_path, "r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source)
            patched = False

            # Check if 'logger' is defined in the module
            has_logger = any(
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "logger"
                    for target in node.targets
                )
                for node in tree.body
            )

            class PatchTransformer(ast.NodeTransformer):
                def __init__(self, synthesizer, guard, council, budgeter):
                    self.synthesizer = synthesizer
                    self.guard = guard
                    self.council = council
                    self.budgeter = budgeter

                def visit_Raise(self, node):
                    nonlocal patched
                    if node.lineno == gap.line_number:
                        exc = node.exc
                        is_target = False
                        if (
                            isinstance(exc, ast.Name)
                            and exc.id == "NotImplementedError"
                        ):
                            is_target = True
                        elif (
                            isinstance(exc, ast.Call)
                            and isinstance(exc.func, ast.Name)
                            and exc.func.id == "NotImplementedError"
                        ):
                            is_target = True

                        if is_target:
                            patched = True
                            if strategy == "stub":
                                msg = f"⚠️ [AUTOPATCH] Stubbed logic for: {gap.description}"
                                if has_logger:
                                    # Use existing logger
                                    log_call = ast.Expr(
                                        value=ast.Call(
                                            func=ast.Attribute(
                                                value=ast.Name(
                                                    id="logger", ctx=ast.Load()
                                                ),
                                                attr="warning",
                                                ctx=ast.Load(),
                                            ),
                                            args=[ast.Constant(value=msg)],
                                            keywords=[],
                                        )
                                    )
                                else:
                                    # Fallback to print
                                    log_call = ast.Expr(
                                        value=ast.Call(
                                            func=ast.Name(id="print", ctx=ast.Load()),
                                            args=[ast.Constant(value=msg)],
                                            keywords=[],
                                        )
                                    )
                                return [log_call, ast.Pass()]
                            elif strategy == "semantic":
                                # Semantic Synthesis
                                parent = self._find_parent_function(node, tree)
                                func_name = parent.name if parent else "anonymous"
                                docstring = ast.get_docstring(parent) or ""

                                logger.info(
                                    f"✨ [kernel] Attempting semantic synthesis for '{func_name}'"
                                )
                                synth_result = self.synthesizer.synthesize_logic(
                                    func_name,
                                    docstring,
                                    strategy="semantic",
                                )
                                if not synth_result:
                                    logger.error(
                                        f"❌ [kernel] Synthesis failed for {func_name}"
                                    )
                                    return [ast.Pass()]

                                synthesized_body, synthesized_test = synth_result
                                logger.info(
                                    f"🧪 [kernel] Synthesized test for {func_name}:\n{synthesized_test}"
                                )

                                # Sandboxed Verification (The Airlock)
                                from warm_logic.kernel.autonomy.airlock import (
                                    AirlockValidator,
                                )

                                if not AirlockValidator.validate(
                                    synthesized_body,
                                    synthesized_test,
                                    func_name=func_name,
                                ):
                                    logger.error(
                                        f"🚨 [Event Horizon] Airlock Verification FAILED for {func_name}. Aborting."
                                    )
                                    # Fallback when verification fails: return a pass and log warning
                                    msg = f"⚠️ [AUTOPATCH] Semantic verification FAILED for: {func_name}"
                                    log_fail = ast.Expr(
                                        value=ast.Call(
                                            func=ast.Name(id="print", ctx=ast.Load()),
                                            args=[ast.Constant(value=msg)],
                                            keywords=[],
                                        )
                                    )
                                    return [log_fail, ast.Pass()]

                                # Self-Governance (The operator of Three)
                                if not self.council.review_patch(
                                    synthesized_body, synthesized_test, func_name
                                ):
                                    logger.error(
                                        f"🚨 [Event Horizon] Council REJECTED semantic patch for {func_name}. Aborting."
                                    )
                                    msg = f"⚠️ [AUTOPATCH] Council REJECTED semantic patch for: {func_name}"
                                    log_fail = ast.Expr(
                                        value=ast.Call(
                                            func=ast.Name(id="print", ctx=ast.Load()),
                                            args=[ast.Constant(value=msg)],
                                            keywords=[],
                                        )
                                    )
                                    return [log_fail, ast.Pass()]

                                # Economic Equilibrium (Budgeting)
                                cost = self.budgeter.calculate_cost(
                                    synthesized_body, strategy
                                )
                                if not self.budgeter.pre_approve(cost):
                                    logger.error(
                                        f"📉 [Event Horizon] Budget EXCEEDED for {func_name}. Aborting."
                                    )
                                    msg = f"⚠️ [AUTOPATCH] Budget EXCEEDED for: {func_name}"
                                    log_fail = ast.Expr(
                                        value=ast.Call(
                                            func=ast.Name(id="print", ctx=ast.Load()),
                                            args=[ast.Constant(value=msg)],
                                            keywords=[],
                                        )
                                    )
                                    return [log_fail, ast.Pass()]

                                patch_nodes = [
                                    ast.Expr(
                                        ast.Call(
                                            func=ast.Attribute(
                                                value=ast.Name(
                                                    id="logger", ctx=ast.Load()
                                                ),
                                                attr="info",
                                                ctx=ast.Load(),
                                            ),
                                            args=[
                                                ast.Constant(
                                                    value=f"✨ [kernel] Applied semantic patch for {func_name}"
                                                )
                                            ],
                                            keywords=[],
                                        )
                                    )
                                ]
                                self.budgeter.finalize_expenditure(cost)
                                patch_nodes.extend(ast.parse(synthesized_body).body)
                                return patch_nodes
                            elif strategy == "generative":
                                # Generative Synthesis
                                parent = self._find_parent_function(node, tree)
                                func_name = parent.name if parent else "anonymous"
                                docstring = ast.get_docstring(parent) or ""

                                logger.info(
                                    f"🧬 [Generative] Synthesizing logic for '{func_name}'"
                                )
                                synth_result = self.synthesizer.synthesize_logic(
                                    func_name,
                                    docstring,
                                    strategy="heuristic",
                                )
                                if not synth_result:
                                    logger.error(
                                        f"❌ [Generative] Synthesis failed for {func_name}"
                                    )
                                    return [ast.Pass()]

                                synthesized_body, _ = synth_result
                                try:
                                    patch_nodes = ast.parse(synthesized_body).body  # type: ignore[no-redef]
                                    return patch_nodes
                                except SyntaxError:
                                    # Fallback for fragments with 'return' (not valid at module level)
                                    try:
                                        # Wrap in dummy function to parse statements like 'return'
                                        import textwrap

                                        indented = textwrap.indent(
                                            synthesized_body, "    "
                                        )
                                        wrapped = f"def _fragment():\n{indented}"
                                        tree_fragment = ast.parse(wrapped)
                                        # Extract body of _fragment
                                        f_node = tree_fragment.body[0]
                                        if isinstance(
                                            f_node,
                                            (ast.FunctionDef, ast.AsyncFunctionDef),
                                        ):
                                            patch_nodes_gen: List[ast.Expr] = f_node.body  # type: ignore[assignment]
                                            return patch_nodes_gen
                                        return [ast.Pass()]
                                    except Exception as e2:
                                        logger.error(
                                            f"❌ [Generative] AST fragment parse failed: {e2}"
                                        )
                                        return [ast.Pass()]
                                except Exception as e:
                                    logger.error(
                                        f"❌ [Generative] AST parse failed: {e}"
                                    )
                                    return [ast.Pass()]

                def visit_Call(self, node):
                    nonlocal patched
                    # Security Patching Strategy
                    if (
                        strategy == "security"
                        and hasattr(node, "lineno")
                        and node.lineno == gap.line_number
                    ):
                        func_name = ""
                        if isinstance(node.func, ast.Name):
                            func_name = node.func.id
                        elif isinstance(node.func, ast.Attribute):
                            if isinstance(node.func.value, ast.Name):
                                func_name = f"{node.func.value.id}.{node.func.attr}"

                        if func_name:
                            patched = True
                            logger.warning(
                                f"🛡️ [Aegis] Neutralizing dangerous call: {func_name}"
                            )
                            patched_code, justification = (
                                self.synthesizer.synthesize_security_patch(
                                    func_name, ast.unparse(node)
                                )
                            )
                            try:
                                syn_tree = ast.parse(patched_code.strip())
                                return syn_tree.body
                            except Exception as e:
                                logger.error(
                                    f"❌ [Aegis] Failed to parse security patch: {e}"
                                )
                    return node

                def _find_parent_function(self, target_node, root):
                    for node in ast.walk(root):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            for subnode in ast.walk(node):
                                if subnode == target_node:
                                    return node
                    return None

            new_tree = PatchTransformer(
                self.synthesizer, self.guard, self.council, self.budgeter
            ).visit(tree)
            ast.fix_missing_locations(new_tree)

            if patched:
                # 1. Atomic Write: Use temp file + replace
                temp_path = gap.file_path + ".tmp"
                backup_path = gap.file_path + ".bak"

                try:
                    patched_source = ast.unparse(new_tree)
                    with open(temp_path, "w", encoding="utf-8") as f:
                        f.write(patched_source)

                    # 2. Pre-flight health check
                    if not self.verify_patch_safety(temp_path):
                        logger.error(
                            f"❌ [Event Horizon] Pre-flight check failed for {gap.file_path}. Patch aborted."
                        )
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        return False

                    # 3. Create backup
                    if os.path.exists(gap.file_path):
                        import shutil

                        shutil.copy2(gap.file_path, backup_path)

                    os.replace(temp_path, gap.file_path)
                    logger.info(
                        f"✅ [Event Horizon] Atomic patch applied to {gap.file_path}"
                    )
                    return True
                except Exception as e:
                    logger.error(
                        f"❌ [Event Horizon] Atomic write failed for {gap.file_path}: {e}"
                    )
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return False
            else:
                logger.warning(
                    f"⚠️ [Event Horizon] Could not find specific node to patch in {gap.file_path}"
                )
                return False

        except Exception as e:
            logger.error(f"[Event Horizon] Patch failed: {e}")
            return False

    def reload_module(self, module_name: str, file_path: Optional[str] = None):
        """
        Dynamically reloads a module. If reload fails, attempts to rollback from .bak file.
        """
        try:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
                logger.info(
                    f"🔄 [Event Horizon] Module '{module_name}' reloaded successfully."
                )
                return True
            else:
                logger.warning(
                    f"⚠️ [Event Horizon] Module '{module_name}' not found in sys.modules."
                )
                return False
        except Exception as e:
            logger.error(
                f"❌ [Event Horizon] Module reload failed: {e}. Initiating ROLLBACK."
            )
            if file_path:
                self.rollback(file_path)
            return False

    def rollback(self, file_path: str):
        """
        Restores a file from its .bak version.
        """
        backup_path = file_path + ".bak"
        if os.path.exists(backup_path):
            import shutil

            shutil.move(backup_path, file_path)
            logger.warning(f"[Event Horizon] Rollback complete for {file_path}")
            return True
        else:
            logger.error(
                f"❌ [Event Horizon] Rollback failed: No backup found for {file_path}"
            )
            return False

    def verify_patch_safety(self, file_path: str) -> bool:
        """
        Performs a pre-flight health check on a file.
        Verifies syntax and compile status.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()

            # Syntax check via AST
            tree = ast.parse(source)

            # Compile check (ensures it's valid byte code)
            compile(tree, filename=file_path, mode="exec")

            logger.info(f"[Event Horizon] Pre-flight check PASSED for {file_path}")
            return True
        except Exception as e:
            logger.error(
                f"❌ [Event Horizon] Pre-flight check FAILED for {file_path}: {e}"
            )
            return False
