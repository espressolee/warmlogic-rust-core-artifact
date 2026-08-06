#!/usr/bin/env python3
"""Generate a minimal WLPv4 governance decision artifact for CI."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True)
    parser.add_argument("--env-scope", required=True)
    parser.add_argument("--autonomy-cap", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--comment", default="")
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "warmlogic.govdec.wlpv4.v1",
        "decision_id": f"GOVDEC-WLPv4-{args.env_scope.upper()}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "env_scope": args.env_scope,
        "autonomy_cap": args.autonomy_cap,
        "evidence": args.evidence,
        "comment": args.comment,
        "verdict": "allow",
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[GOVDEC] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
