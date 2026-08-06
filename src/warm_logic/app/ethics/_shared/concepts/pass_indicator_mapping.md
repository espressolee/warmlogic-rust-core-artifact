# PASS Indicator Mapping v1 (WarmLogic SSOT)

Single source for PASS indicators and their observation surface in WarmLogic. For each indicator, record the PASS dimension, description, WarmLogic artefact/field, and how to measure (qual/quant).

| Indicator ID | PASS dimension (A/T/E/C) | Description | WarmLogic observation (artefact/field) | Measurement method |
| --- | --- | --- | --- | --- |
| AUTH_TOPOLOGY | Authority (A) | Who can approve/override; how concentrated | GOVDEC (`authority_stack`, `decision_type`), run_manifest (`governance_overrides`) | Qual: governance doc; Quant: override rate vs budget |
| TIME_APPEAL | Time (T) | Appeal/reopen latency | window_snapshot/automation_window (`hard_max_prefix`,`soft_max_prefix`), GOVDEC timestamps | p50/p95 appeal/closure latency |
| EVIDENCE_FLOW | Evidence (E) | Evidence availability/preservation | run_manifest (`evidence_refs`), incident_event (`evidence_status`), proof_manifest_refs | Count of missing/expired refs; evidence loss incidents |
| COST_REVERSAL | Cost (C) | Reversal/rollback cost | run_manifest (`rollback_cost_estimate`), GOVDEC (`binding_effect`), os_eval metrics | Median rollback cost/time; rollback success rate |
| DISAGREE_RATE | Authority/Evidence | Contestation/disagreement presence | external coder labels (P2), R_CULT probes, incident_log (`contest_event`) | κ/agree rate; count of contest events |

Notes
- Add rows as new indicators enter P2/P5/P6; keep IDs stable.
- WarmLogic fields refer to current schemas: `run_manifest_v4`, `govdec_event_v1`, `automation_window.json`, incident logs.
- Indicators tagged synthetic-only in the relevant paper must be flagged in R-EXT scope filters.
