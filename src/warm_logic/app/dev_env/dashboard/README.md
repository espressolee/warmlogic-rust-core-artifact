# Dashboard local bootstrap

This folder contains quick-start assets for running the Reflective Commons
dashboard with synthetic data.

## Steps (single-node seed)

1. Copy the env template (optional overrides):
   - `cp dev_env/dashboard/.env.example dev_env/dashboard/.env`
   - Source it or export the variables you need.
2. Seed sample artifacts into `out/`:
   - `make dashboard-seed`
   - Copies `dev_env/dashboard/sample_data/**` into `out/` preserving paths.
3. Run the dashboard in light mode (skips heavier reflective loaders):
   - `make dashboard-dev`
   - Uses `WARMLOGIC_BOOTSTRAP_MODE=light` by default; adjust via env vars.

4. Validate artifacts (optional check before running):
   - `make dashboard-validate`
   - Ensures required files under `out/` have minimal schema.
   - For deeper contracts, run `python -m pytest model/memory/dashboard/tests/test_dashboard_artifact_contracts.py`.

## Band‑1 cluster workflow (P215)

Use this path when exercising the operator console cards described in `docs/observability/WarmLogic_Cluster_Observability_Map_v1.md`.

1. **Aggregate node snapshots + capture the SLO log**
   ```bash
   python scripts/ops/write_cluster_state.py --nodes-dir dev_env/dashboard/sample_data/nodes \
     --out model/data/os_cluster_state.sample.json --cluster-id demo
   python scripts/check_cluster_slo.py --cluster-state model/data/os_cluster_state.sample.json --window 24h \
     > out/cluster_slo_report.log
   ```
   - Collect worker/control JSONs under a staging directory before running the commands above.
   - Move or reference the SLO log under `docs/research/eval/logs/` and record hashes in your run log.
2. **Seed distributed artifacts**
   - Preferred: `make dashboard-seed` (copies `dev_env/dashboard/sample_data/**` into `out/`).
   - Manual refresh:
     ```bash
     cp model/data/os_cluster_state.sample.json out/os_cluster_state.json
     cp model/data/os_job_queue.sample.json out/os_job_queue.json
     ```
   - Preserve the `sensitivity` blocks (`privacy`, `ip`) in each artifact—WL_LLM_MODE guardrails depend on them.
3. **Launch dashboard with cluster context and validate artifacts**
   ```bash
   export WARMLOGIC_CLUSTER_STATE_PATH="out/os_cluster_state.json"
   export WARMLOGIC_JOB_QUEUE_PATH="out/os_job_queue.json"
   export WARMLOGIC_CLUSTER_SLO_LOG="out/cluster_slo_report.log"
   make dashboard-validate
   make dashboard-dev
   ```
   - For deeper contracts, also run `python -m pytest model/memory/dashboard/tests/test_dashboard_artifact_contracts.py`.
   - Confirm "Cluster Overview", "Job Queue", "Incident Timeline", and "Observer Health" cards render without manual JSON edits.
4. **Document acceptance + CLI hooks**
   - Capture screenshots/logs per card and note every command/env var used when filing P215.
   - Link back to the observability map reference and note whether `wlctl cluster check-slo --cluster demo` (stub) was run.

### Env overrides for distributed cards

| Variable | Purpose | Default |
|----------|---------|---------|
| `WARMLOGIC_CLUSTER_STATE_PATH` | Control-plane aggregate consumed by cluster overview + inventory cards. | `out/os_cluster_state.json` |
| `WARMLOGIC_JOB_QUEUE_PATH` | Job queue backlog JSON powering the queue card. | `out/os_job_queue.json` |
| `WARMLOGIC_CLUSTER_SLO_LOG` | Optional path to the latest `scripts/check_cluster_slo.py` output; parser feeds the SLO card. | unset |

Record overrides inside the run log (`meta/WarmLogic_P_Status_v4.json` notes or `meta/WarmLogic_P_Run_Log_*.jsonl`) so future operators can replay the flow.

> Tip: cross-check each card against the table in the observability map doc while reviewing a P215 patch; it lists the CLI commands that must succeed before screenshots/logs are accepted.

## Notes

- Sample payloads cover CT summary, drift report, orchestrator snapshot,
  DevLoop report/gaps, patch plan, patch history, Codex queue/LLM gate,
  meta-governance history/status, and optional ML/internal/commons summaries. Extend
  `dev_env/dashboard/sample_data` as new artifacts are added.
- Outputs are written under `out/` (git-ignored) and `data/` (for
  meta-governance history/status); rerun `make dashboard-seed` after edits to
  sample data.
 - ML internal metrics: add `out/ml_internal_metrics.json` if you want the
   ML Internal Metrics card populated (see contracts doc).
 - Commons semantic summary: optional `out/commons_semantic_summary.json` to
   populate the Commons Semantic Summary card.
- For full telemetry, replace the seeded files with real artifacts (including aggregated cluster state); the app
  will degrade gracefully when optional data is absent.
- Minimal field requirements are tracked in `dev_env/dashboard/ARTIFACT_CONTRACTS.md`.
