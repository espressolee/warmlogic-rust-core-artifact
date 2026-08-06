# Dashboard artifact contracts (dev bootstrap)

This page captures minimal fields required by the dashboard renderers and
tests. Sample payloads in `dev_env/dashboard/sample_data` satisfy these
contracts.

## Core artifacts

- **CT summary** (`out/ct/phase40_training_summary.json`)
  - Required: `ts`, `current_state`, `next_state`, `unsafe_rate`, `total_steps`, `_status.status`
  - Purpose: CT health/epsilon bound computation, operator cards.

- **Drift report** (`out/drift/consensus_drift_report.json`)
  - Required: `ts`, `drift_score`, `action`, `cause`
  - Purpose: drift overview, causal chain, operator banners.

- **Orchestrator snapshot** (`out/ct/orchestrator_snapshot.json`)
  - Required: `ts`, `ct`, `drift`, `kernel` (each with status), `_status.status`
  - Purpose: ops health pill, causal trace, CT missing flagging.

- **DevLoop report** (`out/devloop_report.json`)
  - Required: `ts`, `status`, `steps` (list)
  - Purpose: operator console status, gaps/steps rendering.

- **Patch plan** (`out/patch_plan_v1.json`)
  - Required: `ts`, `status`, `gaps` (list), `suggestions` (list)
  - Purpose: patch plan card, dependency sanity checks.

- **DevLoop gaps** (`out/devloop_gaps.json`)
  - Required: `ts`, `gaps` (list)
  - Purpose: gaps card rendering.

- **Patch history** (`out/patch_history.jsonl`)
  - Required per row: `ts`, `id`, `status`
  - Purpose: patch history card timeline.

- **Codex queue** (`out/codex/codex_queue_v1.json`)
  - Required: `jobs` (list of codex tasks)
  - Purpose: DevLoop queue filters, budget estimation.

- **LLM gate status** (`out/codex/llm_gate_status.json`)
  - Required: `max_cost` (number), optional `sat_available`, `value_cost`.
  - Purpose: budget/knapsack overlays in queue card.

- **Meta governance status** (`data/meta_governance_status.json`)
  - Required: `status`, `risk_score` (float), `_status` recommended.
  - Purpose: meta governance card, risk/stability panel, policy panels.

- **Governance history** (`data/governance_history.jsonl`)
  - Required per row: `ts`, `status`, `risk_score` optional.
  - Purpose: meta governance timeline figure.

### Governance dashboard DTOs

- **Governance status DTO** — documents the payload consumed by
  `meta_governance_status.json`.
  - Required: `status` (str), `risk_score` (float), `schema_version` (int),
    `warm_logic_version` (str).
  - Optional: `early_warning` (bool), `suggestion` (str), `flags`
    (list[str]), `_status` diagnostics.
  - Sample payload: `dev_env/dashboard/sample_data/data/meta_governance_status.json`.
- **Governance history DTO** — documents each line emitted in
  `governance_history.jsonl`.
  - Required per row: `ts` (ISO 8601 str), `status` (str).
  - Optional: `risk_score` (float), `note` (str) for operator context.
  - Sample payload: `dev_env/dashboard/sample_data/data/governance_history.jsonl`.

- **ML internal metrics** (`out/ml_internal_metrics.json`)
  - Required: at least one of `reflective_severity_v2`, `planner_alignment_v1`, `meta_policy_oscillation`, `drift_ct_correlation`.
  - Optional: `reflection_efficiency_score` (RES).
  - Purpose: ML Internal Metrics card.

- **Commons semantic summary** (`out/commons_semantic_summary.json`)
  - Optional: `summary` (str), `clusters` (list of {label, score}), `ai_explanations` (list of text/objects).
  - Purpose: Commons Semantic Summary card.

## Personal artifacts

- **Personal day plan** (`data/personal/day_plan_v2.json`)
  - Required: `schema_version`, `date`, `blocks` (list of `{id, kind, start, end}`), `sensitivity` metadata per schema.
  - Purpose: used by personal planner cards and DevLoop personal dashboard smoke. Sample payload: `dev_env/dashboard/sample_data/data/personal/day_plan_v2.json`.

- **Personal feed items** (`data/personal/feed_items_v2.json`)
  - Required per entry: `id`, `category`, `title`, `timestamp`, `sensitivity`; optional `score` informs card ranking.
  - Purpose: personal feed/dashboard layout and WL Shell personal summaries. Sample payload: `dev_env/dashboard/sample_data/data/personal/feed_items_v2.json`.

## Notes

- Schema versions: include `schema_version` and `warm_logic_version` when
  adding new fields to preserve compatibility.
- Optional artifacts (e.g., devloop queue/apply, meta governance history)
  should degrade gracefully; add contract sections here as they become
  dashboard-blocking.
- Validation helpers: `make dashboard-validate` (quick check) and
  `python -m pytest model/memory/dashboard/tests/test_dashboard_artifact_contracts.py`
  (contract tests).
