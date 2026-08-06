# WarmLogic Console

Minimal console UI for the WarmLogic Runtime Suite.

- Run overview
- GOVDEC / decision log drill-down
- CE ledger browser
- Cohort status view (for pilots)
- SLI warning badge: the UI/API shows a warning when SLI data is missing

---

## 1. Architecture Overview

- Backend: Flask (minimal demo)
  - `/api/v1/runs`
  - `/api/v1/runs/<run_id>`
  - `/api/v1/runs/<run_id>/decisions`
  - `/api/v1/runs/<run_id>/verify`
  - `/api/v1/ce-ledger`
- Frontend: static HTML/JS (`console/static/index.html`) fetching API directly.
- Auth (v1): `X-API-Key` header (`WL_CONSOLE_API_KEY`); production-grade RBAC is out of scope.

---

## 2. Local Demo (Flask + static UI)

```bash
python console/app.py \
  --run-root out/osctl_runs \
  --ce-ledger ledger/pilots/TeamA/CE_Ledger_v1.jsonl \
  --host 127.0.0.1 --port 8765
# Browser: http://127.0.0.1:8765
```

- Flask must already be installed locally, or install it with `pip install Flask>=3,<4`.
- Data sources are the osctl run output (`out/osctl_runs/*`) and the CE ledger file.

---

## 3. API Contract (v1)
- `GET /api/v1/runs` (query: limit, status)
- `GET /api/v1/runs/<run_id>`
- `GET /api/v1/ce-ledger`
- `GET /api/v1/cohorts`
- Response examples follow the pattern in the `eval_best_choices` document and default to JSON format.

## 4. Auth / Security (v1)
- Default: the API token (e.g. `WL_CONSOLE_API_KEY`) is passed in the `X-API-Key` header.
- Production RBAC / multi-tenancy is not included; pilot and research use only.

## 5. CI / E2E Quickstart
- Workflow: `.github/workflows/console-smoke.yml`
  - Install Python 3.10 + Flask
  - Start the console backend
  - Call `/api/v1/runs`, `/api/v1/ce-ledger`, and `/` with `curl`
  - FAIL if the response is not 200 or JSON parsing fails
- Purpose: detect routing, startup, and response regressions immediately when the console changes.

- E2E smoke (backend integration): `.github/workflows/console_v2_e2e.yml`
  - API-only mode: verify that `/api/v1/runs` and `/api/v1/ce-ledger` respond correctly for an existing run_id
  - Full E2E (manual; requires an environment): osctl run -> ledger (FAIL-closed) -> run_root sync -> SLI -> console query. The script auto-discovers the run_root/metrics_root/ledger paths.
  - How to run:
    - API-only:
      ```bash
      export CONSOLE_V2_BASE="http://<host>:<port>"
      export CONSOLE_V2_RUN_ID="EXISTING_RUN_ID"
      export CONSOLE_E2E_SKIP_RUN=1
      export CONSOLE_E2E_SKIP_LEDGER=1
      bash scripts/console/console_v2_e2e_smoke.sh
      ```
    - Full E2E (recommended: start a local console pointed at E2E-only paths first):
      ```bash
      # Terminal 1: console server
      python console/app.py \
        --run-root out/osctl_runs \
        --metrics-root out/metrics \
        --ce-ledger out/console_v2_e2e/_ledgers/Counterexamples_v1.json \
        --cohorts out/console_v2_e2e/_ledgers/External_Repro_Status_v1.json \
        --host 127.0.0.1 --port 8000

      # Terminal 2: Full E2E
      export CONSOLE_V2_BASE="http://127.0.0.1:8000"
      export CONSOLE_V2_ORG_ID="demo-org"
      export CONSOLE_V2_TENANT_ID="console-e2e"
      export CONSOLE_E2E_SKIP_RUN=0
      export CONSOLE_E2E_SKIP_LEDGER=0
      bash scripts/console/console_v2_e2e_smoke.sh
      ```
    - In API-only mode SLI may be empty (`sli_warning` is set); this surfaces as a warning badge and the test still passes.
    - In Full E2E the script generates SLI, so `sli_warning == null` is expected.

## 6. Limitations (v1)
- No production-grade auth/RBAC.
- No multi-tenant / org-separated view.
- For pilot and research use; general SaaS-level UX is not a goal.

## 3. Main Screens / Feature Checklist (v1)
- Run list page
- Run detail + GOVDEC summary
- decision_log table + filters
- CE ledger list/detail
- Cohort status list
- Basic error and loading state handling

---

## 4. Limitations / TODO
- Auth/permissions: omitted in the v1 demo; a proxy/token will be added to match pilot requirements.
- UI: currently minimal HTML/JS. To be replaced by a proper console framework (React/TS or similar).
- Localization, accessibility (a11y), and theming are best-effort in v1.

---

## 5. Related Documents
- `docs/runtime/Console_Product_Spec_v1.md`
- `docs/runtime/Runtime_SLI_SLO_Spec_v1.md`
- `docs/api/Runtime_Console_API_v1.md`
