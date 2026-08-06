# ==========================================================
# Module: collect_experiment_artifacts.py
# Project: Warm Logic — Model Layer
# Description: Auto-inserted header (add description).
# Author: espressolee
# ==========================================================

#!/usr/bin/env python3
"""Utility helpers for collecting experiment artifacts into out/experiments."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(
    os.environ.get("WL_EXPERIMENTS_DATA_ROOT", REPO_ROOT / "model" / "data")
)
OUT_ROOT = Path(
    os.environ.get("WL_EXPERIMENTS_OUT_ROOT", REPO_ROOT / "out" / "experiments")
)

DEFAULT_E1_FILES = [
    DATA_ROOT / "os_state.json",
    DATA_ROOT / "os_channel_signals.json",
]
DEFAULT_E2_FILES = [
    DATA_ROOT / "ct_metrics.json",
    DATA_ROOT / "ct_history.jsonl",
]
DEFAULT_E3_FILES = [
    DATA_ROOT / "os_state.json",
    DATA_ROOT / "patch_proposal.json",
    DATA_ROOT / "patch_decision.json",
    DATA_ROOT / "governance_status.json",
]


def _copy_files(files: List[Path], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for src in files:
        if src.exists():
            target = dest / src.name
            target.write_bytes(src.read_bytes())
        else:
            print(f"[WARN] Source {src} missing; skipping")


EXPERIMENT_INVARIANTS = {
    "E1": ["I-1", "I-2", "I-3"],
    "E2": ["I-5"],
    "E3": ["I-4", "I-6"],
}


def collect_experiment(
    experiment: str,
    run_label: str,
    commands: Optional[List[str]] = None,
    extra_files: Optional[List[str]] = None,
    note: Optional[str] = None,
) -> None:
    if experiment == "E1":
        dest = OUT_ROOT / "E1_repro" / run_label
        files = DEFAULT_E1_FILES.copy()
    elif experiment == "E2":
        dest = OUT_ROOT / "E2_ct_drift" / run_label
        files = DEFAULT_E2_FILES.copy()
    else:
        dest = OUT_ROOT / "E3_self_improvement" / run_label
        files = DEFAULT_E3_FILES.copy()
    copied: List[Path] = files.copy()
    if extra_files:
        for rel_path in extra_files:
            copied.append(REPO_ROOT / rel_path)
    _copy_files(copied, dest)

    manifest = {
        "experiment_id": experiment,
        "run_label": run_label,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commands": commands or [],
        "artifacts": {
            path.name: str(dest / path.name)
            for path in copied
            if (dest / path.name).exists()
        },
        "invariants": EXPERIMENT_INVARIANTS[experiment],
        "notes": note or "",
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Collect Warm Logic experiment artifacts"
    )
    parser.add_argument("experiment", choices=["E1", "E2", "E3"], help="Experiment ID")
    parser.add_argument("run_label", help="Run label (e.g., P18/run00)")
    parser.add_argument(
        "--extra",
        nargs="*",
        default=None,
        help="Additional relative file paths to copy (optional)",
    )
    parser.add_argument(
        "--command",
        dest="commands",
        action="append",
        default=None,
        help="Command executed for this run",
    )
    parser.add_argument(
        "--note",
        dest="note",
        default=None,
        help="Optional note",
    )
    args = parser.parse_args()

    collect_experiment(
        args.experiment, args.run_label, args.commands, args.extra, args.note
    )
