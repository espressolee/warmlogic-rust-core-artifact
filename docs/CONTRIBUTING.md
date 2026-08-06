# Contributing to Warm Logic (OSS v1)

Thank you for your interest in contributing! This project is a research‑grade, local‑first self‑improvement OS. Please read the scope and safety notes before opening issues or PRs.

## Scope and safety (read first)
- Research‑only, non‑production. Local‑first defaults (SAFE_LOCAL). External LLMs may be used for summaries/reviews; not for direct edits to Tier‑0 specs/schemas/p_status.
- Protocol/P‑Series are core contracts; changes that impact these require an RFC and evidence.
- See: `docs/oss/WarmLogic_OSS_Positioning_v1.md`, `docs/oss/WarmLogic_LLM_Policy_Overview_v1.md`, `docs/oss/Safety_Scope_Warnings_v1.md`.

## How to contribute
1) Open an issue first for significant changes (feature/bug template under `.github/ISSUE_TEMPLATE/`).
2) Create a focused PR with:
   - Tests (at least quick tests under `-m "not slow"` when applicable)
   - Lint/format applied (`flake8`, `black`)
   - Docs updated (Quickstarts/Docs Index if user‑facing)
   - Manifests/artifacts updated when behavior changes (paths listed in PR)
3) For protocol/contract changes, include a short RFC (design + backward compat) and attach evidence/artifacts.

## Coding style and tests
- Python 3.10+, 4‑space indentation, explicit imports.
- **Strict Typing**: Core modules (`warm_logic`) must pass `mypy --strict`.
- Run locally:
  - `pytest -m "not slow"`
  - `flake8`, `black`, `mypy`
- Prefer reproducible writes under `out/` and avoid network I/O in tests.

### Pre-commit hooks (recommended)
- Install once:
  - `pip install pre-commit` (or `pipx install pre-commit`)
  - `pre-commit install`
- Hooks: `black`, `flake8`, `isort` (profile=black)
- Run manually on all files: `pre-commit run -a`

## CLI and quickstarts
- Keep `scripts/cli/wl.py` minimal and user‑facing; heavy logic belongs in core modules.
- Quickstarts live under `docs/quickstart/`; keep them runnable on a clean machine.

## Governance & evidence
- When touching governance/τ/CT‑safe paths, link to the relevant Gate template and include a minimal evidence set (manifests, audit JSON).
- For P‑Series changes, propose an OSS band (e.g., P900+) if core series must remain sealed.

## CI
- PRs run CI core: lint, quick tests, personal quickstart smoke, E2 stub.
- Nightly builds dashboards/audits and may annotate proofs in advisory mode.

## Getting help
- Check the Docs Index: `docs/overview/Docs_Index_v1.md`
- Quickstarts: `docs/quickstart/Personal_OS_Quickstart_v1.md`, `docs/quickstart/Eval_E2_CT_Drift_Quickstart_v1.md`

Thanks for contributing!
## Git Commit & Branch Conventions (Warm Logic SSOT)

This repository treats Git history as part of the operations/governance/evidence chain.
The rules below are a summary of `docs/dev/WarmLogic_Git_Commit_and_Branch_Conventions_v1.md`; that document is the SSOT for the full ruleset.

### Branch

- `main`:
  - Single source of truth (SSOT). If it breaks, P-Series, Evidence, the papers, and DevLoop are all considered broken.
- P-Series:
  - A dedicated branch per P: `pXX-<short-slug>` (e.g. `p24-runtime-suite-v1`, `p230-evidenceos-v2`)
  - One branch targets exactly one P.
- Other:
  - Hotfix / experiment / docs-only: use `fix/<slug>`, `exp/<slug>`, `docs/<slug>`.

### Commit message format

The first line of a commit must follow this format:

```text
<type>(<scope>): [Pxx] summary
```

- `<type>`: feat, fix, refactor, docs, test, chore, perf, revert
- `<scope>`: subsystem or module (e.g. os, devloop, evidence, console, runtime-suite, sf, governance, schema)
- `[Pxx]`: the related P-Series ID (e.g. [P24], [P230]).
- Genuinely exceptional typo-only changes are allowed as a `docs(...)` commit that states `(non-P)`.

Examples:

```
feat(os): [P24] wire runtime suite v1 to osctl
fix(evidence): [P230] treat replay hash mismatch as ce-drift
docs(protocol): fix typo in wlpv1 scope section (non-P)
```

### Rules for Tier-0 changes

Tier-0: spec/**, docs/protocol/**, meta/**, spec/schema/**, docs/SF/WarmLogic_SF_Safety_Case_v1.md, docs/research/WarmLogic_Direction_v1.md, and similar.
- A commit that changes Tier-0 in any meaningful way must be tied to a P-Series and must include `[Pxx]` in the message.
- If the change carries no semantic content (for example, typo-only), the message must state `(non-P)`.

### gitlint script

- `scripts/gitlint_warmlogic.py` checks the commit message rules and enforces the P-ID requirement for Tier-0 changes.
- Recommended: call this script from `.git/hooks/commit-msg` so that commits are checked automatically.

```bash
#!/usr/bin/env bash
scripts/gitlint_warmlogic.py "$1"
```

Following these rules preserves traceability between the P-Series, EvidenceOS, the papers, and the governance documents, and lets the Git log be used as a reliable SSOT layer when investigating incidents, CEs, proofs, or operational issues later.
