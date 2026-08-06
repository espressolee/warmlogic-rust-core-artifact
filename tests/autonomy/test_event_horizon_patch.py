import importlib
import os
import sys

import pytest

from warm_logic.kernel.autonomy.codex import SovereignCodebase
from warm_logic.kernel.autonomy.patcher import AutonomousPatcher


@pytest.fixture
def dummy_patch_file(tmp_path):
    # We need a file that is "importable" but in a temp location
    # So we add tmp_path to sys.path
    sys.path.append(str(tmp_path))

    p = tmp_path / "patchable_module.py"
    p.write_text(
        """
import logging
logger = logging.getLogger("test")

def feature_x():
    raise NotImplementedError("Feature X is missing")
""",
        encoding="utf-8",
    )

    yield p

    if "patchable_module" in sys.modules:
        del sys.modules["patchable_module"]
    sys.path.remove(str(tmp_path))


@pytest.mark.asyncio
async def test_autonomous_patch_cycle(dummy_patch_file):
    """
    Verify the full cycle: Detect -> Patch -> Reload -> Execute
    """
    import patchable_module

    # 1. Verify it fails initially
    with pytest.raises(NotImplementedError) as excinfo:
        patchable_module.feature_x()
    assert "Feature X is missing" in str(excinfo.value)

    # 2. Detect the gap
    root_dir = str(dummy_patch_file.parent)
    codex = SovereignCodebase(root_path=root_dir)
    gaps = codex.scan_codebase()
    assert len(gaps) == 1
    gap = gaps[0]

    # 3. Apply Patch
    patcher = AutonomousPatcher(root_path=root_dir)
    success = await patcher.apply_patch(gap)
    assert success

    # 4. Verify disk change
    patched_content = dummy_patch_file.read_text()
    assert "NotImplementedError" not in patched_content
    assert "AUTOPATCH" in patched_content

    # 5. Hot Reload and Verify Fix
    reloaded = patcher.reload_module("patchable_module")
    assert reloaded

    # Should no longer raise exception
    patchable_module.feature_x()
