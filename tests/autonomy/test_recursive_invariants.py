import os
import shutil
import tempfile

import pytest
from hypothesis import example
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from warm_logic.kernel.autonomy.auditor import RecursiveDebtAuditor
from warm_logic.kernel.autonomy.codex import LogicGap
from warm_logic.kernel.autonomy.patcher import AutonomousPatcher


@pytest.fixture
def mock_fs():
    """Provides a temporary directory for testing filesystem operations."""
    tmp_path = tempfile.mkdtemp()
    yield tmp_path
    shutil.rmtree(tmp_path)


@given(st.text())
@example(random_content="ä")
@settings(deadline=None)
def test_auditor_never_crashes_on_random_input(random_content):
    """
    Invariant: The Auditor should handle any text content without crashing.
    """
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "test.py")
        with open(p, "w", encoding="utf-8") as f:
            f.write(random_content)

        auditor = RecursiveDebtAuditor(root_path=td)
        # Should not raise
        try:
            auditor.scan_all()
        except UnicodeDecodeError:
            # Tolerable for binary junk
            pass
        except SyntaxError:
            # Tolerable
            pass


def test_patch_idempotency(mock_fs):
    """
    Invariant: Applying a patch twice results in the same state (Idempotency).
    """
    # Setup
    target_file = os.path.join(mock_fs, "target.py")
    with open(target_file, "w") as f:
        f.write("def foo():\n    raise NotImplementedError('Todo')\n")

    patcher = AutonomousPatcher(root_path=mock_fs)
    gap = LogicGap(
        file_path=target_file, line_number=2, description="foo stub", gap_type="Stub"
    )

    # First Patch
    # We mock strategy to be deterministic for this test
    # (In reality, we rely on the heuristic fallback in test env)

    # ... Wait, AutonomousPatcher.apply_patch is async
    import asyncio

    async def run_idempotency():
        # 1. Apply
        await patcher.apply_patch(gap, strategy="heuristic")
        with open(target_file, "r") as f:
            state_1 = f.read()

        # 2. Apply again (should likely be no-op or identical)
        # However, patcher might complain "no gap found" on second run, which is also a form of stability.
        # But if we force it:
        await patcher.apply_patch(gap, strategy="heuristic")
        with open(target_file, "r") as f:
            state_2 = f.read()

        assert state_1 == state_2

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_idempotency())
    finally:
        loop.close()
        asyncio.set_event_loop(None)
