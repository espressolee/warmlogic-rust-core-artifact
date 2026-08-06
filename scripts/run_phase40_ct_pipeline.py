# ==========================================================
# Module: run_phase40_ct_pipeline.py
# Project: Warm Logic — Model Layer
# Description: Auto-inserted header (add description).
# Author: espressolee
# ==========================================================

#!/usr/bin/env python3
# ==========================================================
# Module: run_phase40_ct_pipeline.py
# Project: Warm Logic — Scripts
# Description: Run phase40 continuous training pipeline.
# Author: espressolee
# ==========================================================

from __future__ import annotations

import argparse
import os
from pathlib import Path


def _load_ct_module():
    if os.environ.get("CT_PIPELINE_FAKE") or os.environ.get("WARMLOGIC_DISABLE_TORCH"):
        return None, None
    try:
        from model.ml.continuous_training_v2 import CtConfig, run_ct_pipeline  # type: ignore

        return CtConfig, run_ct_pipeline
    except Exception:
        return None, None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 40 Continuous Training pipeline")
    parser.add_argument("--metrics", type=Path, help="Path to metrics JSON (val_loss/collapse_prob/variance/drift_score)")
    parser.add_argument("--dataset", type=Path, help="Path to phase40_trajectories.jsonl (override default)")
    parser.add_argument("--registry", type=Path, help="Path to model registry directory (override default)")
    parser.add_argument("--history", type=Path, help="Path to rollout history JSONL")
    parser.add_argument("--stage", choices=["shadow", "canary", "full"], default="shadow", help="Rollout stage to evaluate")
    parser.add_argument("--rollout-strategy", choices=["forward", "hold", "backward"], default="forward", help="Rollout strategy gate")
    parser.add_argument("--online-drift-limit", type=float, default=0.5, help="Online drift limit for canary/full gating")
    parser.add_argument("--val-loss-limit", type=float, default=1.0, help="Validation loss limit")
    parser.add_argument("--collapse-prob-limit", type=float, default=0.2, help="Collapse probability limit")
    parser.add_argument("--adp-fail-prob-limit", type=float, default=0.4, help="ADP test failure probability limit")
    parser.add_argument("--governance-status", type=Path, help="Path to governance_status.json (risk_score/block signals)")
    parser.add_argument("--adp-bundle", type=Path, help="Path to ADP evaluator v12 bundle (JSON)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed metrics/activation info")
    return parser.parse_args()


def main() -> int:
    CtConfig, run_ct_pipeline = _load_ct_module()
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    data_root = repo_root / "model" / "data"
    metrics = args.metrics if args.metrics else data_root / "ct_metrics.json"
    registry = args.registry if args.registry else data_root / "ct_registry"
    dataset = args.dataset if args.dataset else data_root / "phase40_trajectories.jsonl"
    history = args.history if args.history else data_root / "ct_history.jsonl"

    if metrics and not metrics.exists():
        print(f"[CT v2] status=error code=CT_METRICS_MISSING metrics_path={metrics}")
        return 1

    if CtConfig is None or run_ct_pipeline is None:
        class _DummyStatus:
            status = "ok"
            error_code = None

        summary = {"current_state": "shadow", "next_state": "shadow", "reason": "stub"}
        print(
            f"[CT v2] status={_DummyStatus.status} code=stub state={summary['current_state']} -> {summary['next_state']} reason={summary['reason']}"
        )
        if args.verbose:
            print(f"[CT v2] metrics=stub activated=False registry={registry}")
        return 0

    cfg = CtConfig(
        dataset_path=dataset,
        registry_dir=registry,
        metrics_path=metrics,
        rollout_stage=args.stage,
        history_path=history,
        rollout_strategy=args.rollout_strategy,
        online_drift_limit=args.online_drift_limit,
        val_loss_limit=args.val_loss_limit,
        collapse_prob_limit=args.collapse_prob_limit,
        adp_fail_prob_limit=args.adp_fail_prob_limit,
        governance_path=args.governance_status,
        adp_bundle_path=args.adp_bundle,
    )
    status, summary = run_ct_pipeline(cfg)
    guard_info = summary.get("guard") if isinstance(summary, dict) else None
    guard_action = None
    guard_reason = None
    if guard_info is not None:
        if hasattr(guard_info, "action"):
            guard_action = getattr(guard_info, "action")
            guard_reason = getattr(guard_info, "reason", None)
        elif isinstance(guard_info, dict):
            guard_action = guard_info.get("action")
            guard_reason = guard_info.get("reason")
    print(
        f"[CT v2] status={status.status} code={status.error_code or 'none'} state={summary.get('current_state')} -> {summary.get('next_state')} reason={summary.get('reason')} guard={guard_action or 'unknown'}"
    )
    if args.verbose:
        print(
            f"[CT v2] metrics={summary.get('metrics')} activated={summary.get('activated')} registry={cfg.registry_dir} guard_reason={guard_reason or 'n/a'}"
        )
    return 0 if status.status in {"ok", "degraded"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
