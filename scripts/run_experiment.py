# ==========================================================
# Module: run_experiment.py
# Project: Warm Logic — Model Layer
# Description: Auto-inserted header (add description).
# Author: espressolee
# ==========================================================

#!/usr/bin/env python3
"""Run a Warm Logic experiment (E1/E2/E3), snapshot artifacts, and log the run."""
from __future__ import annotations

import argparse
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from scripts.devloop.p300_guard import ensure_pband_allowed_str
from scripts.experiments.collect_experiment_artifacts import collect_experiment
from scripts.patch_engine.run_log_helpers import append_run_log_with_patch_context

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_LOG_PATH = REPO_ROOT / "model" / "data" / "p_series_runs.jsonl"
DEFAULT_COMMANDS = {
    "E1": ["bash model/run_all.sh test"],
    "E2": ["bash model/run_all.sh series"],
    "E3": ["bash model/run_all.sh auto-dev"],
}


def run_command(cmd: str, dry_run: bool = False) -> None:
    if dry_run:
        print(f"[DRY-RUN] {cmd}")
        return
    subprocess.run(cmd, cwd=str(REPO_ROOT), shell=True, check=True)


def _run_log_path() -> Path:
    """Resolve the run-log path honoring WL_P_RUN_LOG_PATH at call time."""

    return Path(os.environ.get("WL_P_RUN_LOG_PATH", DEFAULT_RUN_LOG_PATH))


def append_run_log(entry: dict) -> None:
    append_run_log_with_patch_context(entry, run_log_path=_run_log_path())


def run_experiment(
    experiment: str,
    run_label: str,
    p_id: str,
    commands: Optional[List[str]] = None,
    note: Optional[str] = None,
    dry_run: bool = False,
    skip_run_log: bool = False,
) -> None:
    # Enforce WLPv3 P300-band guard (research-only) when P≥300
    scope = str(os.environ.get("WL_SESSION_SCOPE", "research_sandbox"))
    ensure_pband_allowed_str(str(p_id), scope, REPO_ROOT)
    cmds = commands or DEFAULT_COMMANDS[experiment]
    run_id = f"{experiment}-{run_label}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    started_at = datetime.now(timezone.utc)
    executed: List[str] = []
    for cmd in cmds:
        run_command(cmd, dry_run=dry_run)
        executed.append(cmd)
    finished_at = datetime.now(timezone.utc)
    collect_experiment(experiment, run_label, executed, note=note)

    if skip_run_log:
        return

    entry = {
        "P": p_id,
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "actor": os.environ.get("USER", "devloop"),
        "mode": "experiment",
        "tests": executed,
        "result": "done",
        "notes": note or "",
        "llm_backend": "none",
        "llm_mode": "SAFE_LOCAL",
        "env": {
            "experiment_id": experiment,
            "run_label": run_label,
        },
    }
    append_run_log(entry)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Warm Logic experiments")
    parser.add_argument("experiment", choices=["E1", "E2", "E3"], help="Experiment ID")
    parser.add_argument(
        "run_label", help="Label for this run (e.g., P18-run00 or perturb-0.1)"
    )
    parser.add_argument(
        "--p-id", default="P63", help="P-series entry to tag in p_run_log"
    )
    parser.add_argument(
        "--command",
        action="append",
        dest="commands",
        help="Command to execute (repeatable)",
    )
    parser.add_argument("--note", default=None, help="Optional note")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print commands without executing"
    )
    parser.add_argument(
        "--skip-run-log", action="store_true", help="Do not append to p_run_log"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_experiment(
        args.experiment,
        args.run_label,
        args.p_id,
        commands=args.commands,
        note=args.note,
        dry_run=args.dry_run,
        skip_run_log=args.skip_run_log,
    )


if __name__ == "__main__":
    main()
