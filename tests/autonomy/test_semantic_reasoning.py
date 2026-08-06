import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.autonomy.codex import LogicGap
from warm_logic.kernel.autonomy.patcher import AutonomousPatcher


def _fresh_store():
    """Create a fresh mock store for testing to avoid budget exhaustion."""
    store = MagicMock()
    store.get_meta = MagicMock(return_value=None)  # Simulate fresh start
    store.set_meta = MagicMock()
    return store


@pytest.fixture
def semantic_workspace(tmp_path):
    # Ensure root is in sys.path
    root = str(tmp_path)
    if root not in sys.path:
        sys.path.insert(0, root)

    # Create a mock module with a semantic stub
    module_dir = tmp_path / "semantic_app"
    module_dir.mkdir()
    (module_dir / "__init__.py").touch()

    stub_file = module_dir / "math_utils.py"
    # Note: line 7 is the raise statement
    stub_content = """import logging
logger = logging.getLogger("MathUtils")

def is_prime(n):
    \"\"\"TODO: Implement optimized primality test\"\"\"
    raise NotImplementedError("Fix me")
"""
    stub_file.write_text(stub_content)
    return tmp_path


@pytest.mark.asyncio
@patch("warm_logic.kernel.autonomy.patcher.ReasoningSynthesizer")
async def test_semantic_synthesis(mock_synth_class, semantic_workspace):
    # Mock the synthesizer to return a valid primality test
    mock_synth = mock_synth_class.return_value
    mock_synth.synthesize_logic.return_value = (
        "if n <= 1: return False\nfor i in range(2, int(n**0.5) + 1):\n    if n % i == 0: return False\nreturn True",
        "assert is_prime(7) == True\nassert is_prime(10) == False",
    )

    patcher = AutonomousPatcher(root_path=str(semantic_workspace), store=_fresh_store())

    # Define a gap targeting the semantic stub (line 6 indexed from 1 is 'raise...')
    # Actually let's count:
    # 1: import logging
    # 2: logger = ...
    # 3:
    # 4: def is_prime(n):
    # 5:     docstring
    # 6:     raise ...
    gap = LogicGap(
        file_path=str(semantic_workspace / "semantic_app" / "math_utils.py"),
        line_number=6,
        description="Fix me",
        gap_type="NotImplemented",
    )

    # Apply patch using the 'semantic' strategy
    success = await patcher.apply_patch(gap, strategy="semantic")
    assert success is True

    # Verify the code was actually modified
    patch_content = (semantic_workspace / "semantic_app" / "math_utils.py").read_text()
    assert "Applied semantic patch" in patch_content
    assert "if n <= 1:" in patch_content
    assert "return False" in patch_content

    # Hot-reload and test the synthesized function
    import semantic_app.math_utils as math_utils

    importlib.reload(math_utils)

    assert math_utils.is_prime(7) is True
    assert math_utils.is_prime(10) is False
    assert math_utils.is_prime(1) is False

    print(
        "\n✅ [Test] Semantic synthesis successfully generated and applied complex logic."
    )
