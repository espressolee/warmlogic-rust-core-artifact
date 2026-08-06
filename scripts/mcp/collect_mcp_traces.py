#!/usr/bin/env python3
"""
MCP Trace Collector v1

Collects MCP events and writes them to the Audit Spine introspection/ slot.

Usage:
    python scripts/mcp/collect_mcp_traces.py \
        --session-log logs/mcp/session_001.jsonl \
        --out-dir out/audit_spine_v1/RUN_001/runs/RUN_001/introspection

    python scripts/mcp/collect_mcp_traces.py \
        --session-log logs/mcp/session_001.jsonl \
        --out-dir out/introspection \
        --emit-plan-traces

SSOT: docs/runtime/Audit_Spine_v1_Spec.md
Schema: spec/schema/mcp/mcp_event_v1.schema.json, mcp_call_v1.schema.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class MCPCall:
    """Parsed MCP call from session log."""

    call_id: str
    session_id: str
    call_seq: int
    tool_name: str
    params_hash: str
    result_hash: Optional[str] = None
    status: str = "ok"
    latency_ms: Optional[int] = None
    decision_id: Optional[str] = None
    guard: Optional[dict] = None
    emitted_at: Optional[str] = None
    raw: dict = field(default_factory=dict)


@dataclass
class PlanStep:
    """Step within a plan trace."""

    step_seq: int
    intent: str
    call_ids: list[str]
    decision_id: Optional[str]
    tool_selection: Optional[dict]
    outcome: str
    duration_ms: Optional[int] = None


@dataclass
class PlanTrace:
    """Agent plan trace grouping multiple MCP calls."""

    plan_id: str
    session_id: str
    goal: str
    steps: list[PlanStep]
    final_outcome: str
    metrics: dict


def compute_sha256(data: bytes) -> str:
    """Compute SHA256 hash."""
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def parse_session_log(log_path: Path) -> list[MCPCall]:
    """
    Parse session log and extract MCP calls.

    Supports multiple log formats:
    - JSONL with mcp_call_v1 schema
    - JSONL with raw tool invocations
    """
    calls = []

    if not log_path.exists():
        print(f"Warning: Log file not found: {log_path}", file=sys.stderr)
        return calls

    with open(log_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                print(f"Warning: Invalid JSON at line {line_num}", file=sys.stderr)
                continue

            if not _is_mcp_call(entry):
                continue

            call = _parse_mcp_call(entry, line_num)
            if call:
                calls.append(call)

    return calls


def _is_mcp_call(entry: dict) -> bool:
    """Check if log entry represents an MCP call."""
    if entry.get("schema_version") == "mcp_call_v1":
        return True

    if "tool_name" in entry or "tool" in entry:
        return True

    if entry.get("event_type") in ("tool_call", "mcp_call", "tool_invocation"):
        return True

    return False


def _parse_mcp_call(entry: dict, line_num: int) -> Optional[MCPCall]:
    """Parse a log entry into MCPCall."""
    try:
        if entry.get("schema_version") == "mcp_call_v1":
            return MCPCall(
                call_id=entry["call_id"],
                session_id=entry["session_id"],
                call_seq=entry["call_seq"],
                tool_name=entry["tool_name"],
                params_hash=entry["params_hash"],
                result_hash=entry.get("result_hash"),
                status=entry.get("status", "ok"),
                latency_ms=entry.get("latency_ms"),
                decision_id=entry.get("decision_id"),
                guard=entry.get("guard"),
                emitted_at=entry.get("emitted_at"),
                raw=entry,
            )

        tool_name = entry.get("tool_name") or entry.get("tool", "Unknown")
        call_id = entry.get("call_id") or f"call_{line_num}_{uuid.uuid4().hex[:8]}"
        session_id = entry.get("session_id", "unknown")

        params = entry.get("params") or entry.get("arguments", {})
        params_json = json.dumps(params, sort_keys=True, separators=(",", ":"))
        params_hash = compute_sha256(params_json.encode())

        return MCPCall(
            call_id=call_id,
            session_id=session_id,
            call_seq=entry.get("call_seq", line_num),
            tool_name=tool_name,
            params_hash=params_hash,
            result_hash=entry.get("result_hash"),
            status=entry.get("status", "ok"),
            latency_ms=entry.get("latency_ms") or entry.get("duration_ms"),
            decision_id=entry.get("decision_id"),
            guard=entry.get("guard"),
            emitted_at=entry.get("timestamp") or entry.get("emitted_at"),
            raw=entry,
        )

    except (KeyError, TypeError) as e:
        print(
            f"Warning: Failed to parse entry at line {line_num}: {e}", file=sys.stderr
        )
        return None


def validate_mcp_call(call: MCPCall) -> tuple[bool, list[str]]:
    """
    Validate MCPCall against mcp_call_v1 schema requirements.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if not call.call_id:
        errors.append("Missing required field: call_id")
    if not call.session_id:
        errors.append("Missing required field: session_id")
    if not call.tool_name:
        errors.append("Missing required field: tool_name")
    if not call.params_hash:
        errors.append("Missing required field: params_hash")

    if call.params_hash and call.params_hash != "unhashable":
        if len(call.params_hash) != 64:
            errors.append(f"Invalid params_hash length: {len(call.params_hash)}")

    valid_statuses = {"ok", "error", "rejected"}
    if call.status not in valid_statuses:
        errors.append(f"Invalid status: {call.status}")

    return len(errors) == 0, errors


def group_into_plan_traces(
    calls: list[MCPCall],
    session_id: str,
) -> list[PlanTrace]:
    """
    Group MCP calls into plan traces based on decision_id.

    Calls with the same decision_id are assumed to be part of the same plan.
    Calls without decision_id are grouped into a "misc" plan.
    """
    groups: dict[str, list[MCPCall]] = defaultdict(list)

    for call in calls:
        key = call.decision_id or "misc"
        groups[key].append(call)

    plan_traces = []

    for decision_id, group_calls in groups.items():
        group_calls.sort(key=lambda c: c.call_seq)

        steps = []
        total_duration = 0

        for i, call in enumerate(group_calls):
            step = PlanStep(
                step_seq=i,
                intent=f"Execute {call.tool_name}",
                call_ids=[call.call_id],
                decision_id=call.decision_id,
                tool_selection={"selected_tool": call.tool_name},
                outcome="success" if call.status == "ok" else "failed",
                duration_ms=call.latency_ms,
            )
            steps.append(step)

            if call.latency_ms:
                total_duration += call.latency_ms

        failed_steps = [s for s in steps if s.outcome == "failed"]
        if not failed_steps:
            final_outcome = "achieved"
        elif len(failed_steps) < len(steps):
            final_outcome = "partial"
        else:
            final_outcome = "failed"

        plan_trace = PlanTrace(
            plan_id=f"PLAN_{decision_id}_{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            goal=(
                f"Decision: {decision_id}"
                if decision_id != "misc"
                else "Miscellaneous calls"
            ),
            steps=steps,
            final_outcome=final_outcome,
            metrics={
                "total_steps": len(steps),
                "successful_steps": len(steps) - len(failed_steps),
                "total_calls": len(group_calls),
                "total_duration_ms": total_duration,
            },
        )
        plan_traces.append(plan_trace)

    return plan_traces


def convert_call_to_event(call: MCPCall) -> dict:
    """Convert MCPCall to mcp_event_v1 format."""
    return {
        "schema_version": "mcp_event_v1",
        "event_id": f"EVT_{call.call_id}",
        "event_type": "tool_call",
        "session_id": call.session_id,
        "call_id": call.call_id,
        "call_seq": call.call_seq,
        "tool_name": call.tool_name,
        "params_hash": call.params_hash,
        "result_hash": call.result_hash,
        "status": call.status,
        "latency_ms": call.latency_ms,
        "decision_id": call.decision_id,
        "guard": call.guard,
        "emitted_at": call.emitted_at or datetime.now(timezone.utc).isoformat(),
    }


def convert_plan_to_trace(plan: PlanTrace) -> dict:
    """Convert PlanTrace to mcp_plan_trace_v1 format."""
    return {
        "schema_version": "mcp_plan_trace_v1",
        "plan_id": plan.plan_id,
        "session_id": plan.session_id,
        "goal": plan.goal,
        "steps": [
            {
                "step_seq": step.step_seq,
                "intent": step.intent,
                "call_ids": step.call_ids,
                "decision_id": step.decision_id,
                "tool_selection": step.tool_selection,
                "outcome": step.outcome,
                "duration_ms": step.duration_ms,
            }
            for step in plan.steps
        ],
        "final_outcome": plan.final_outcome,
        "metrics": plan.metrics,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
    }


def write_jsonl(path: Path, items: list[dict]) -> str:
    """Write items to JSONL file and return SHA256."""
    path.parent.mkdir(parents=True, exist_ok=True)

    content_bytes = b""
    with open(path, "w") as f:
        for item in items:
            line = json.dumps(item, separators=(",", ":")) + "\n"
            f.write(line)
            content_bytes += line.encode()

    return compute_sha256(content_bytes)


def collect_and_emit(
    session_log_path: Path,
    out_dir: Path,
    emit_plan_traces: bool = False,
    validate: bool = True,
) -> dict[str, Any]:
    """
    Collect MCP traces from session log and emit to Audit Spine introspection slot.

    Args:
        session_log_path: Path to session log (JSONL)
        out_dir: Output directory (introspection/)
        emit_plan_traces: Whether to group calls into plan traces
        validate: Whether to validate calls against schema

    Returns:
        Collection result with statistics and hashes
    """
    calls = parse_session_log(session_log_path)

    if not calls:
        return {
            "status": "empty",
            "message": "No MCP calls found in session log",
            "calls_found": 0,
        }

    validation_errors = []
    valid_calls = []

    for call in calls:
        if validate:
            is_valid, errors = validate_mcp_call(call)
            if is_valid:
                valid_calls.append(call)
            else:
                validation_errors.append({"call_id": call.call_id, "errors": errors})
        else:
            valid_calls.append(call)

    events = [convert_call_to_event(call) for call in valid_calls]

    events_path = out_dir / "mcp_events.jsonl"
    events_hash = write_jsonl(events_path, events)

    result = {
        "status": "success",
        "calls_found": len(calls),
        "calls_valid": len(valid_calls),
        "validation_errors": len(validation_errors),
        "artifacts": [
            {
                "kind": "mcp_events",
                "path": str(events_path),
                "sha256": events_hash,
                "count": len(events),
            }
        ],
    }

    if emit_plan_traces and valid_calls:
        session_id = valid_calls[0].session_id
        plan_traces = group_into_plan_traces(valid_calls, session_id)
        trace_dicts = [convert_plan_to_trace(p) for p in plan_traces]

        traces_path = out_dir / "mcp_plan_traces.jsonl"
        traces_hash = write_jsonl(traces_path, trace_dicts)

        result["artifacts"].append(
            {
                "kind": "mcp_plan_traces",
                "path": str(traces_path),
                "sha256": traces_hash,
                "count": len(trace_dicts),
            }
        )

    if validation_errors:
        result["validation_errors_detail"] = validation_errors[:10]

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect MCP traces for Audit Spine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--session-log",
        type=Path,
        required=True,
        help="Path to session log (JSONL)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for introspection artifacts",
    )
    parser.add_argument(
        "--emit-plan-traces",
        action="store_true",
        help="Group calls into plan traces",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation against schema",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Output result as JSON",
    )

    args = parser.parse_args()

    if not args.session_log.exists():
        print(f"Error: Session log not found: {args.session_log}", file=sys.stderr)
        return 1

    result = collect_and_emit(
        session_log_path=args.session_log,
        out_dir=args.out_dir,
        emit_plan_traces=args.emit_plan_traces,
        validate=not args.no_validate,
    )

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print("MCP Trace Collection Complete")
        print(f"  Status: {result['status']}")
        print(f"  Calls found: {result.get('calls_found', 0)}")
        print(f"  Calls valid: {result.get('calls_valid', 0)}")
        print(f"  Validation errors: {result.get('validation_errors', 0)}")
        print("\nArtifacts:")
        for artifact in result.get("artifacts", []):
            print(
                f"  - {artifact['kind']}: {artifact['path']} ({artifact['count']} entries)"
            )

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
