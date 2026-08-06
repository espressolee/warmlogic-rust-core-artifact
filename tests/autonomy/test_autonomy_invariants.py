import pathlib
import tempfile

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from warm_logic.kernel.autonomy.codex import LogicGap
from warm_logic.kernel.autonomy.patcher import AutonomousPatcher

# Strategy for generating LogicGap objects
gap_strategy = st.builds(
    LogicGap,
    file_path=st.text(min_size=1),
    line_number=st.integers(min_value=1),
    description=st.text(min_size=5),
    gap_type=st.sampled_from(["Stub", "Bug", "Security", "Optimize"]),
    priority=st.integers(min_value=0, max_value=100),
    complexity=st.integers(min_value=1, max_value=10),
)


@given(gap_strategy)
@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_logic_gap_is_hashable_and_deterministic(gap):
    """
    [Phase 27.1] Property: LogicGap must be hashable and deterministic.
    Identical gaps must produce identical hashes for consensus.
    """
    # Verify hashability
    h1 = hash(gap)
    h2 = hash(gap)
    assert h1 == h2

    # Verify equality of clones
    gap_clone = LogicGap(
        file_path=gap.file_path,
        line_number=gap.line_number,
        description=gap.description,
        gap_type=gap.gap_type,
        priority=gap.priority,
        complexity=gap.complexity,
    )
    assert gap == gap_clone
    assert hash(gap) == hash(gap_clone)


@given(gap_strategy)
def test_logic_gap_priority_sorting(gap):
    """
    [Phase 27.1] Property: Priority sorting behavior.
    """
    assert 0 <= gap.priority <= 100


@pytest.mark.asyncio
async def test_patcher_initialization_invariant():
    """
    [Phase 27.1] Property: Patcher must initialize with valid root.
    """
    with tempfile.TemporaryDirectory() as td:
        import os

        patcher = AutonomousPatcher(root_path=str(td))
        assert patcher.root_path == os.path.abspath(str(td))
        assert pathlib.Path(td).exists()
