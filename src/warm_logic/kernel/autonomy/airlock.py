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
Airlock: The Runtime Sandbox for Sovereign Evolution.
Ensures that synthesized patches does not corrupt the kernel.
"""

import logging
import os
import subprocess
import sys
import tempfile
import time
from typing import Optional

logger = logging.getLogger("Airlock")


class AirlockValidator:
    """
    Executes code in a subprocess sandbox to verify safety.
    Prevents infinite loops, segfaults, and immediate crashes from infecting the host.
    """

    @staticmethod
    def validate(
        code_body: str,
        test_logic: str,
        timeout_sec: float = 0.5,
        func_name: Optional[str] = None,
    ) -> bool:
        """
        Runs the code_body + test_logic in a separate process.
        Returns True if the process exits with 0.
        """
        logger.info(
            f"🛡️ [Airlock] Initiating sandboxed verification for {func_name or 'fragment'} (timeout={timeout_sec}s)..."
        )

        # 1. Construct the verification harness
        if func_name:
            import textwrap

            indented_body = textwrap.indent(code_body, "    ")
            # Broadened signature to handle common synthesized variable names
            code_block = (
                f"def {func_name}(n=None, a=None, b=None, *args, **kwargs):\n"
                f"{indented_body}"
            )
        else:
            code_block = code_body

        harness = f"""
import sys
import os

# --- SYNTHESIZED PATCH ---
{code_block}
# -------------------------

# --- VERIFICATION TEST ---
try:
    import textwrap
    exec(textwrap.dedent('''{test_logic}'''))
    print("TEST_PASSED")
except Exception as e:
    print(f"TEST_FAILED: {{e}}")
    sys.exit(1)
# -------------------------
"""

        # 2. Write to strict temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
            tf.write(harness)
            tf_path = tf.name

        try:
            # 3. Execute in subprocess (The Airlock)
            # -S: Don't imply 'import site' on initialization
            start_time = time.time()
            result = subprocess.run(
                [sys.executable, "-S", tf_path],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            duration = time.time() - start_time

            if result.returncode == 0:
                logger.info(f"[Airlock] Verification PASSED in {duration:.3f}s")
                return True
            else:
                logger.warning(
                    f"⛔ [Airlock] Verification FAILED (Exit {result.returncode})"
                )
                logger.debug(f"Airlock Stderr: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"⏳ [Airlock] Verification TIMED OUT (> {timeout_sec}s)")
            return False

        except Exception as e:
            logger.error(f"[Airlock] System Error: {e}")
            return False

        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)
