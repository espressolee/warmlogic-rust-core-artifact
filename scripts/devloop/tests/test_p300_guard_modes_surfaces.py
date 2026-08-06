from __future__ import annotations

from pathlib import Path
import pytest


def test_ensure_mode_allowed_ok(tmp_path, monkeypatch):
    from scripts.devloop.p300_guard import ensure_mode_allowed, load_automation_window_v3  # type: ignore

    root = Path.cwd()
    wnd = load_automation_window_v3(root)
    # If window has modes, pick the first; else this should pass without error
    modes = wnd.get("allowed_p300_modes") if isinstance(wnd, dict) else None
    mode = (modes or ["sim_only"])[0]
    ensure_mode_allowed(mode, root)


def test_validate_surfaces_blocks_forbidden():
    from scripts.devloop.p300_guard import validate_surfaces  # type: ignore

    with pytest.raises(RuntimeError):
        validate_surfaces(["spec/schema/meta/run_manifest_v3.schema.json"], ["spec/schema/**"])
