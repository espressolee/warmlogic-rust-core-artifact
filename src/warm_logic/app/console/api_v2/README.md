# WarmLogic Console API v2

Status: Draft
Role: Read-only API contract used by the Console v2 frontend and external tools.

---

## 1. Common Rules

- Base path: `/api/v2`
- Authentication:
  - Default: `Authorization: Bearer <token>` header
  - See `Console_Auth_and_Roles_v1.md` for token semantics and issuance policy.
- Response:
  - `application/json; charset=utf-8`
  - All endpoints use a common envelope:

```jsonc
{
  "ok": true,
  "data": { /* payload */ },
  "error": null,
  "meta": {
    "next_cursor": "..."
  }
}
```

---

## 1.1 Minimal Endpoints Used by the Console v2 E2E Smoke Test

- The backend currently exposes only the `/api/v1` paths. Once the v2 paths are stable, this section will be updated to v2 and v1 archived.
- Minimal endpoints (v1):
  - Runs: `GET /api/v1/runs`, `GET /api/v1/runs/{run_id}`
  - CE ledger: `GET /api/v1/ce-ledger`
- The v2 design uses the Org/Run/CE/Evidence views below; when implemented, the v2 paths become the SSOT.

The sections below and Console_V2_E2E_Smoke_Spec_v1.md remain the SSOT for detailed fields and schemas.
Default paths in the current (local demo) implementation:
- run_root: `out/osctl_runs` (osctl run output must be placed under this root for `/api/v1/runs` to see it)
- metrics_root: `out/metrics` (e.g. `runtime_sli_<run_id>.json`)
- CE ledger: `ledger/pilots/TeamA/CE_Ledger_v1.jsonl`
- sync helper: `scripts/console/sync_runs_to_console_root.sh` copies from `out/console_v2_e2e` to the paths above.
 - Empty SLI handling: if metrics_root has no values, `sli={}` is returned. To generate a minimal SLI, run `scripts/console/emit_sli_stub_from_run.sh RUN_ID=<run_id>` to produce `runtime_sli_<run_id>.json`.

---

## 2. Orgs / Pilots / Cohorts

### 2.1 GET /orgs
- Description: list of accessible organizations.
- Query: cursor (optional)
- Response data.orgs[*]:

```json
{
  "org_id": "ORG_TEAM_A",
  "display_name": "Team A",
  "pilots": [
    {
      "pilot_id": "TEAM_A_ADVISORY",
      "status": "active",
      "type": "advisory"
    }
  ]
}
```

---

## 3. SLI / Overview

### 3.1 GET /orgs/{org_id}/sli
- Description: SLI aggregation per org.
- Query: window: "7d" | "30d" (default 7d)
- Response data:

```json
{
  "org_id": "ORG_TEAM_A",
  "window": "7d",
  "sli": {
    "decision_latency_p95_ms": 120.5,
    "evidence_lag_p95_min": 8.2,
    "verify_fail_rate": 0.01,
    "ce_open_count": 3
  },
  "slo_status": "amber"
}
```

Data source: SLI aggregation files/DB exported from EvidenceOS/Runtime.

---

## 4. Runs

### 4.1 GET /runs
- Description: list of accessible runs.
- Query: org_id, pilot_id, cohort_id, status(running|pass|fail|incident), limit, cursor
- Response data.runs[*]:

```json
{
  "run_id": "PILOT_TEAM_A_ADVISORY_20260105Z_2",
  "org_id": "ORG_TEAM_A",
  "pilot_id": "TEAM_A_ADVISORY",
  "started_at": "2026-01-05T03:40:00Z",
  "finished_at": "2026-01-05T03:41:12Z",
  "mode": "advisory",
  "status": "pass",
  "sli": {
    "decision_latency_p95_ms": 110.0,
    "evidence_lag_p95_min": 5.0,
    "verify_fail_rate": 0.0,
    "ce_open_count": 0
  },
  "evidence": {
    "bundle_id": "PILOT_TEAM_A_ADVISORY_20260105Z_2",
    "sha256": "...",
    "status": "ok"
  }
}
```

### 4.2 GET /runs/{run_id}
- Description: detail for a single run.

```json
{
  "manifest": { /* part of manifest.json */ },
  "config": {
    "osctl_args": ["…"],
    "spec_versions": {
      "os": "v2.3.0",
      "evidence": "v1.1.0"
    }
  },
  "verify": { "status": "pass", "at": "2026-01-05T03:42:00Z" },
  "replay": { "status": "pass", "at": "2026-01-05T03:43:00Z" },
  "sli": { /* same as above */ },
  "ce_summary": { "open": 0, "mitigated": 1, "non_applicable": 0 },
  "evidence": {
    "bundle_id": "...",
    "sha256": "...",
    "download_url": "/downloads/bundles/..."
  }
}
```

---

## 7. C01 Minimal Demo Endpoint

Example response for the Console v2 minimal baseline:

### GET /runs/{run_id}/evidence

```json
{
  "run_id": "RUN_OSCTL_DEMO_20260106T010000Z",
  "org_id": "demo-org-001",
  "slis": {
    "evidence_lag_p95_min": 4.5,
    "verify_fail_rate_rolling_24h": 0.0,
    "ce_open_count": 2
  },
  "evidence_bundles": [
    {
      "bundle_id": "BNDL-20260106-01",
      "sha256": "abc123...",
      "path": "out/evidenceos_internal/bundles/RUN_OSCTL_DEMO_20260106T010000Z/bundle.zip"
    }
  ],
  "counterexamples": ["CE-0007", "CE-0012"]
}
```

## 5. Decision Log / GOVDEC

### 5.1 GET /runs/{run_id}/decisions
- Description: paginated view of decision_log.jsonl.
- Query: cursor, limit (default 100)
- Response data.decisions[*]:

```json
{
  "index": 123,
  "timestamp": "2026-01-05T03:40:22Z",
  "input_ref": "events/000123",
  "output": { "decision": "ALLOW", "score": 0.91 },
  "policy_id": "PASS_v1",
  "witness_path": ["rule_1", "rule_7"],
  "evidence_anchor": "#evidence-entry-000123"
}
```

---

## 6. CE Ledger

### 6.1 GET /ce-ledger
- Description: CE ledger view.
- Query: org_id, pilot_id, status, category
- Response data.entries[*]:

```json
{
  "ce_id": "CE-TEAM-A-005",
  "org_id": "ORG_TEAM_A",
  "pilot_id": "TEAM_A_ADVISORY",
  "status": "mitigated",
  "severity": "medium",
  "first_seen_run": "...",
  "last_seen_run": "...",
  "linked_changes": ["CHG-TEAM-A-003"],
  "notes": "..."
}
```

---

## 7. Evidence Bundles

### 7.1 GET /evidence/bundles
- Description: evidence bundle index.
- Query: org_id, pilot_id, run_id, status
- Response data.bundles[*]:

```json
{
  "bundle_id": "PILOT_TEAM_A_ADVISORY_20260105Z_2",
  "run_id": "...",
  "sha256": "...",
  "size_bytes": 1234567,
  "created_at": "...",
  "status": "ok",
  "download_url": "/downloads/bundles/PILOT_TEAM_A_ADVISORY_20260105Z_2.zip"
}
```

---

## 8. SLI Export (Prometheus-friendly)

### 8.1 GET /sli/metrics
- Description: SLI metrics for Prometheus/OTEL.
- Response: text/plain; version=0.0.4

Example:

```
warmlogic_decision_latency_p95_ms{org_id="ORG_TEAM_A"} 120.5
warmlogic_evidence_lag_p95_min{org_id="ORG_TEAM_A"} 8.2
warmlogic_verify_fail_rate{org_id="ORG_TEAM_A"} 0.01
warmlogic_ce_open_count{org_id="ORG_TEAM_A"} 3
```

---

## 9. Error Model

- Common error envelope:

```json
{
  "ok": false,
  "data": null,
  "error": { "code": "NOT_FOUND", "message": "run not found", "details": {} },
  "meta": {}
}
```

- Common codes:
  - UNAUTHENTICATED
  - PERMISSION_DENIED
  - NOT_FOUND
  - INVALID_ARGUMENT
  - INTERNAL
