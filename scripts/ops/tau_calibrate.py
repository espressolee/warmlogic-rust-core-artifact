#!/usr/bin/env python3
"""CLI to preview τ constraint impact before applying a bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:  # pragma: no cover - exercised via CLI
    sys.path.insert(0, str(REPO_ROOT))

from warm_logic.core.governance.policy_loader import (
    extract_tau_constraints,
    load_tau_policy_bundle,
)


def _build_result(
    *,
    bundle: Dict[str, Any],
    constraints: Dict[str, Any],
    current_epsilon: float,
    current_drift: float,
) -> Dict[str, Any]:
    epsilon_limit = constraints.get("epsilon_c_max")
    drift_limit = constraints.get("drift_psi_max")
    result = {
        "bundle_id": bundle.get("bundle_id"),
        "mode": constraints.get("mode"),
        "epsilon": {
            "current": current_epsilon,
            "limit": epsilon_limit,
            "margin": (
                None if epsilon_limit is None else epsilon_limit - current_epsilon
            ),
            "violation": bool(
                epsilon_limit is not None and current_epsilon > float(epsilon_limit)
            ),
        },
        "drift": {
            "current": current_drift,
            "limit": drift_limit,
            "margin": None if drift_limit is None else drift_limit - current_drift,
            "violation": bool(
                drift_limit is not None and current_drift > float(drift_limit)
            ),
        },
        "notes": constraints.get("notes"),
    }
    return result


def run(args: argparse.Namespace) -> Dict[str, Any]:
    bundle_path = Path(args.bundle)
    bundle = load_tau_policy_bundle(bundle_path)
    constraints = extract_tau_constraints(bundle)
    if not constraints:
        raise ValueError("bundle missing constraints block")
    return _build_result(
        bundle=bundle.raw,
        constraints=constraints,
        current_epsilon=args.current_epsilon,
        current_drift=args.current_drift,
    )


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--bundle",
        required=True,
        help="Path to τ policy bundle JSON",
    )
    parser.add_argument(
        "--current-epsilon",
        type=float,
        default=0.15,
        help="Current epsilon_c value for comparison",
    )
    parser.add_argument(
        "--current-drift",
        type=float,
        default=0.04,
        help="Current drift ψ value for comparison",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output instead of formatted text",
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _add_arguments(parser)
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except ValueError as exc:
        parser.exit(status=1, message=f"[tau-calibrate] {exc}\n")
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    epsilon = result["epsilon"]
    drift = result["drift"]
    print(f"[tau-calibrate] bundle={result['bundle_id']} mode={result['mode']}")
    print(
        "  epsilon current={current:.4f} limit={limit} margin={margin:.4f} violation={violation}".format(
            current=epsilon["current"],
            limit=epsilon["limit"],
            margin=epsilon["margin"] if epsilon["margin"] is not None else float("nan"),
            violation=str(epsilon["violation"]).lower(),
        )
    )
    print(
        "  drift   current={current:.4f} limit={limit} margin={margin:.4f} violation={violation}".format(
            current=drift["current"],
            limit=drift["limit"],
            margin=drift["margin"] if drift["margin"] is not None else float("nan"),
            violation=str(drift["violation"]).lower(),
        )
    )
    if result.get("notes"):
        print(f"  notes: {result['notes']}")


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
