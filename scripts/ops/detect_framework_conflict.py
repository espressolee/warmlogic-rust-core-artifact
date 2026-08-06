#!/usr/bin/env python3
"""Minimal CE detector smoke for CI contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--spec", required=True)
    p.add_argument("--name", default="CE-detector")
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"missing file: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    manifest = load_json(args.manifest)
    spec = load_json(args.spec)

    triggers = (((spec.get("pass_compiler") or {}).get("triggers") or {}).get("map") or {})
    required = {"override_no_window", "evidence_window_missing", "cost_unknown"}
    missing = sorted(required - set(triggers))
    if missing:
        print(f"[DETECT] missing trigger(s): {', '.join(missing)}")
        return 1

    run_id = manifest.get("run_id", "unknown")
    print(f"[DETECT] name={args.name} seed={args.seed} run_id={run_id} ce=CE-0007 status=TRIGGERED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
