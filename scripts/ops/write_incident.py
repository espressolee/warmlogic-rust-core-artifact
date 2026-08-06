# ==========================================================
# Module: write_incident.py
# Project: Warm Logic — Model Layer
# Description: Auto-inserted header (add description).
# Author: espressolee
# ==========================================================

#!/usr/bin/env python3
"""Write a governance/CT incident record using the v1 schema."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:  # pragma: no cover
    sys.path.insert(0, str(REPO_ROOT))

INCIDENT_SCHEMA_PATH = REPO_ROOT / "spec" / "schema" / "ops" / "incident_v1.schema.json"


def _load_schema() -> Dict[str, Any]:
    return json.loads(INCIDENT_SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_details(args: argparse.Namespace) -> Dict[str, Any] | None:
    if args.details_file:
        return json.loads(Path(args.details_file).read_text(encoding="utf-8"))
    if args.details:
        return json.loads(args.details)
    return None


def _build_record(args: argparse.Namespace) -> Dict[str, Any]:
    details = _load_details(args)
    record: Dict[str, Any] = {
        "incident_id": args.incident_id or f"inc_{uuid.uuid4().hex[:10]}",
        "ts": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "category": args.category,
        "severity": args.severity,
        "summary": args.summary,
        "sensitivity": {
            "privacy": args.sensitivity_privacy,
            "ip": args.sensitivity_ip,
        },
    }
    if details:
        record["details"] = details
    if args.tau_bundle_id:
        record["tau_bundle_id"] = args.tau_bundle_id
    if args.audit_event_id:
        record["audit_event_id"] = args.audit_event_id
    if args.risk_score is not None:
        record["risk_score"] = args.risk_score
    if args.source:
        record["source"] = args.source
    if args.related_patch:
        record["related_patch"] = args.related_patch
    return record


def _write_record(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def run(args: argparse.Namespace) -> Dict[str, Any]:
    record = _build_record(args)
    schema = _load_schema()
    jsonschema.validate(record, schema)
    _write_record(Path(args.out), record)
    return record


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=str, default="model/data/governance_incidents.jsonl"
    )
    parser.add_argument(
        "--category",
        choices=["tau_policy", "governance", "ct", "security", "drift", "other"],
        required=True,
    )
    parser.add_argument(
        "--severity",
        choices=["info", "warn", "high", "critical"],
        required=True,
    )
    parser.add_argument("--summary", required=True)
    parser.add_argument("--tau-bundle-id")
    parser.add_argument("--audit-event-id")
    parser.add_argument("--risk-score", type=float)
    parser.add_argument("--source")
    parser.add_argument("--related-patch")
    parser.add_argument("--incident-id")
    parser.add_argument("--details")
    parser.add_argument("--details-file")
    parser.add_argument(
        "--sensitivity-privacy",
        default="internal",
        choices=["public", "internal", "confidential", "secret"],
    )
    parser.add_argument(
        "--sensitivity-ip",
        default="differentiating",
        choices=["trivial", "standard", "differentiating", "core_strategic"],
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        record = run(args)
    except (
        json.JSONDecodeError,
        jsonschema.ValidationError,
    ) as exc:  # pragma: no cover
        parser.exit(status=1, message=f"[incident] {exc}\n")
    print(json.dumps({"written": args.out, "incident_id": record["incident_id"]}))


if __name__ == "__main__":  # pragma: no cover
    main()
