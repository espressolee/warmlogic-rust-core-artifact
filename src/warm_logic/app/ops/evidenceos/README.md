SSOT: no
Scope: prod
Status: draft
AppliesTo: EvidenceOS ingest helpers

# EvidenceOS ingest helpers (DRIFT guard)

- `update_ledger_from_run.py`: rejects ingest when required identity fields are missing (`org_id`, `tenant_id`, `attempt`) or when a `(run_id, attempt)` collision is detected (append-only DRIFT).
- Integrate with EvidenceOS ingest pipeline to enforce Level 2 immutability before updating ledgers/indexes.
