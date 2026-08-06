import os

import pytest

from warm_logic.kernel.autonomy.codex import SovereignCodebase


@pytest.fixture
def dummy_broken_file(tmp_path):
    d = tmp_path / "subdir"
    d.mkdir()
    p = d / "broken.py"
    p.write_text(
        """
def incomplete_function():
    print("Doing work...")
    # TODO: Finish this logic
    raise NotImplementedError("Kernel panic")
    """,
        encoding="utf-8",
    )
    return p


def test_codex_scan(dummy_broken_file):
    """
    Verify that SovereignCodebase correctly detects logic gaps.
    """
    root_dir = str(dummy_broken_file.parent)
    codex = SovereignCodebase(root_path=root_dir)

    gaps = codex.scan_codebase()

    # Expect 2 gaps: 1 TODO, 1 NotImplementedError
    assert len(gaps) == 2

    todo_gap = next(g for g in gaps if g.gap_type == "TODO")
    error_gap = next(g for g in gaps if g.gap_type == "NotImplemented")

    assert "Finish this logic" in todo_gap.description
    assert "Kernel panic" in error_gap.description
    assert todo_gap.file_path == str(dummy_broken_file)


def test_propose_backfill():
    from warm_logic.kernel.autonomy.codex import LogicGap

    codex = SovereignCodebase()
    gap = LogicGap("test.py", 10, "Missing", "TODO")
    plan = codex.propose_backfill(gap)
    assert "PLAN: Implement" in plan
