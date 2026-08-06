import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _parse_pairs(pairs_raw: Any) -> List[tuple]:
    """Parses raw pairs (string or list) into a list of (A, B) tuples."""
    if isinstance(pairs_raw, str):
        # Format: "A:B, C:D"
        results = []
        for segment in pairs_raw.split(","):
            if ":" in segment:
                a, b = segment.strip().split(":", 1)
                results.append((a, b))
        return results
    return pairs_raw or []


def build_payload(
    status_path: Path,
    scenarios_combined: Path,
    pairs: list,
    top_n: int,
    repo: str,
    run_url: str,
    status_text: str,
    audit_path: Path | None = None,
    audit_csv_path: Path | None = None,
    max_lines: int = 10,
    **kwargs,
) -> Dict[str, Any]:
    """Builds a Slack payload with pair deltas and Top info."""

    blocks = []
    blocks.append(
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"WarmLogic Run: {status_text}"},
        }
    )

    dash_data = {}
    if status_path and status_path.exists():
        dash_data = json.loads(status_path.read_text(encoding="utf-8"))

    # Policy/Warning Checks
    policy = dash_data.get("dashboard_policy", {})
    warn_count = int(policy.get("advisory_warn", 0)) + int(
        policy.get("ct_strict_warn", 0)
    )

    if warn_count > 0:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Warn:* Found {warn_count} advisory/strict warnings.",
                },
            }
        )

    # Load combined scenarios for global stats
    combined_data = {}
    if scenarios_combined.exists():
        combined_data = json.loads(scenarios_combined.read_text(encoding="utf-8")).get(
            "scenarios", {}
        )

    # Load dashboard for per-range stats if needed (skipped for simplicity if not used in deltas)

    # Process pairs
    parsed_pairs = pairs  # Already parsed in test or via _parse_pairs
    if not isinstance(parsed_pairs, list) or (
        parsed_pairs and not isinstance(parsed_pairs[0], tuple)
    ):
        parsed_pairs = _parse_pairs(pairs)

    lines = []
    for i, (a, b) in enumerate(parsed_pairs):
        a_stats = combined_data.get(a, {"success_rate": 0, "avg_duration": 0})
        b_stats = combined_data.get(b, {"success_rate": 0, "avg_duration": 0})

        sr_delta = a_stats.get("success_rate", 0) - b_stats.get("success_rate", 0)
        dur_delta = a_stats.get("avg_duration", 0) - b_stats.get("avg_duration", 0)

        label = "primary pair" if i == 0 else "combo"
        lines.append(
            f"*{label}:* ({a} - {b}) | SR Δ: {sr_delta:+.2f} | Dur Δ: {dur_delta:+.2f}s"
        )

        if i < top_n:
            lines.append(f"  > Top {i + 1} success: {a_stats.get('success_rate')}")
            lines.append(f"  > Top {i + 1} avg duration: {a_stats.get('avg_duration')}")

    if lines:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(lines[:max_lines])},
            }
        )
        if len(lines) > max_lines:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "(...truncated...)"},
                }
            )

    if audit_csv_path and audit_csv_path.exists():
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Audit CSV: attached* ({audit_csv_path.name})",
                },
            }
        )

    return {"blocks": blocks}
