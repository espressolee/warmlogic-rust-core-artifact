import importlib
import os
import sys

import pytest

from warm_logic.kernel.autonomy.codex import LogicGap
from warm_logic.kernel.autonomy.patcher import AutonomousPatcher


@pytest.fixture
def generative_workspace(tmp_path):
    # Ensure root is in sys.path
    if str(tmp_path) not in sys.path:
        sys.path.insert(0, str(tmp_path))

    # Create a module with a stub
    stub_file = tmp_path / "math_logic.py"
    stub_content = """
import logging
logger = logging.getLogger("MathLogic")

def add_numbers(a, b):
    \"\"\"Adds two numbers.\"\"\"
    raise NotImplementedError("Fix me")
"""
    stub_file.write_text(stub_content)
    return tmp_path


@pytest.mark.asyncio
async def test_generative_patching_replaces_stub(generative_workspace):
    patcher = AutonomousPatcher(root_path=str(generative_workspace))

    gap = LogicGap(
        file_path=str(generative_workspace / "math_logic.py"),
        line_number=7,
        description="add_numbers stub",
        gap_type="Stub",
    )

    # Apply patch with 'generative' strategy
    success = await patcher.apply_patch(gap, strategy="generative")
    assert success is True

    # Reload and verify
    sys.path.insert(0, str(generative_workspace))
    if "math_logic" in sys.modules:
        del sys.modules["math_logic"]

    import math_logic

    # The heuristic synthesizer for "add" should have generated "return a + b"
    result = math_logic.add_numbers(10, 20)
    assert result == 30

    print(
        "\n✅ [Test] Generative Synthesis successfully replaced stub with functional logic."
    )


if __name__ == "__main__":
    # Manual run support
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        from pathlib import Path

        test_generative_patching_replaces_stub(Path(td))
