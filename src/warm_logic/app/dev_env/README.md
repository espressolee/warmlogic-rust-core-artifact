# Warm Logic DevEnv v1.0
_Reflective OS Development Environment (2025-11)_

This document describes the **DevEnv v1.0** architecture that integrates the full Warm Logic stack:

- OS Phase 20–30C
- Scheduler & Meta-Kernel
- ADP v9.x (Auto-Development Protocol)
- Patch Engine v5.0
- Reflective Agent v1
- Dashboard v30E
- EventBus v30E

DevEnv is the **Layer 6 “development operating system”** that lets a researcher treat Warm Logic as a single controllable OS instance: observable, patchable, and self-evaluating.

---

## 0. Purpose

DevEnv provides a reproducible environment where the full Warm Logic stack can be:

- Executed end-to-end in a single workspace
- Observed in real time (agent, OS, scheduler, governance, ADP)
- Patched and auto-evaluated via ADP
- Governed via stability envelopes and meta-kernel signals

### Quick start (automation)
- `wlctl devenv boot` — run the install script (`dev_env/install/install.sh`) to prepare the virtualenv and CLI shims.
- `wlctl devenv smoke` — execute the smoke bundle (`dev_env/tests/smoke.py`) which in turn runs critical tests like `test_eventbus_load.py` and `test_agent_proxy.py`.

The design goal: **“one command to boot the reflective OS + DevEnv loop, and one command to validate it.”**

### Configuration

- Canonical settings live in `dev_env/config/devenv.yaml` (schema: `spec/schema/dev_env/devenv_config.schema.json`).
- `dev_env.common.config.load_devenv_config()` is the single loader used by DevEnv tools and `wlctl devenv …` commands.
- `wlctl` validates the YAML against the schema before running DevEnv automation, so update the config via the schema keys (`eventbus`, `paths`, `tests`) to avoid CI failures.
- The EventBus exports per-channel metrics via `/health` plus an optional Prometheus endpoint (`WARMLOGIC_EVENTBUS_PROM_PORT`), and `dev_env/gui/hud.py` will display a live EventBus card when the config points to the health URL.
- ADP telemetry uses the contract in `spec/schema/dev_env/adp_contract.schema.json`. `dev_env/agent/stream.py` emits canonical `adp_hook` payloads (also written to `model/data/adp_hook.json`), and `dev_env/dev_env/adp/service.py` exposes a contract-driven helper for closed-loop tests.

### ADP Closed Loop

- `dev_env/dev_env/adp/contract.py` defines dataclasses (`ADPTelemetry`, `PatchSubmission`, `PatchEvaluationResult`) plus JSON Schema validation.
- `dev_env/dev_env/adp/service.DevEnvADPService` wraps the v9 protocol so tests can submit patches, receive evaluations, and inspect lineage depth.
- `dev_env/tests/test_adp_service.py` provides the reference regression for “submit → evaluate → lineage update,” and the HUD renders the latest `adp_hook` snapshot via the same schema.

### Packaging & Release Automation

- Docker image: `docker/dev_env/Dockerfile` builds the EventBus/HUD container (entrypoint `docker/dev_env/entrypoint.sh`) with Prometheus metrics enabled by default.
- Kubernetes manifest: `k8s/dev_env/deployment.yaml` includes a reference Deployment/Service that exposes port `8765` (EventBus) and `9751` (metrics). Replace the `image:` value with your GHCR registry before applying.
- Release workflow: `.github/workflows/dev-env-release.yml` runs on `devenv-v*` tags (or via `workflow_dispatch`). It renders release notes (`dev_env/build/generate_release_notes.py` + `dev_env/release_notes.template.md`), builds the ZIP (`dev_env/build/build_zip.py` now writes a `.sha256` **and `sbom_spdx.json`**), publishes the Docker image to GHCR, and attaches the artifacts to a GitHub Release. An optional S3 upload step runs if AWS credentials are provided.
- Compliance artifacts: the same workflow now stages a runtime profile, runs `wlctl compliance-bundle` for every preset (`hipaa`, `pci`, `gdpr`, `sox`), captures attestations/submission manifests, and calls `scripts/report_compliance.py --dry-run` so releases include machine-readable reports for downstream ticketing systems.
- Manual invocation: `gh workflow run "DevEnv Release" --ref main -f version=v1.3.1`
- SBOM: `scripts/generate_sbom.py --lock requirements.lock --output out/sbom_spdx.json --package warm-logic-devenv --version <tag>` (automatically included in DevEnv ZIPs). The release workflow also runs `wlctl sbom verify` and ships `out/sbom_status_<tag>.json` so Prometheus metrics can point at the exact published digest.
- Air-gapped bundle: CI now runs the bundler as part of `DevEnv Release` (see the workflow for inputs/outputs). The generated artifact `out/wl_airgap_<tag>.tar.gz` contains the ZIP, checksum, SBOM, optional Docker tarball, and `airgap_manifest.json`. You can still run `python scripts/build_airgap_bundle.py --zip dev_env/WarmLogic_DevEnv_<tag>.zip --checksum dev_env/WarmLogic_DevEnv_<tag>.zip.sha256 --sbom out/sbom_spdx.json [--docker-tar warm-logic-devenv_<tag>.tar] --output out/wl_airgap_<tag>.tar.gz` locally for ad-hoc builds.
- Workflow validation: CI runs `python scripts/validate_workflows.py` to ensure key steps (release/managed smoke) remain in the Github Actions definitions.
- HUD telemetry cards: `dev_env/gui/hud.py` renders EventBus + ADP summaries alongside the latest SBOM status (`sbom_status.json`) and the most recent air-gap manifest (parsed from `out/wl_airgap_*.tar.gz`). Keep `out/sbom_status_<tag>.json` and a recent `wl_airgap_*.tar.gz` checked in/on the release to make the HUD cards useful for operators.

---

## 1. Architecture Overview

Warm Logic is decomposed into 7 layers:

- **Layer 0 — Data & Archive**
  Corpus, archive embeddings, metrics logs, governance traces.
- **Layer 1 — OS Core & Memory**
  Kernel, attention flow, semantic memory, episodic memory, stability envelope.
- **Layer 2 — Scheduler & Meta-Governance**
  Joint scheduler, meta-governance engine, meta-kernel, stability envelopes.
- **Layer 3 — ADP (Auto-Development Protocol)**
  Patch evaluation, semantic scoring, lineage tracking, bias/decay.
- **Layer 4 — Reflective Agent**
  Reflective agent loop and semantic retrieval.
- **Layer 5 — Dashboard (Phase 24–30)**
  Unified dashboard with OS, federation, governance, and τ–ε panels.
- **Layer 6 — DevEnv (this document)**
  Developer-facing environment that glues Layers 1–5 together.

DevEnv integrates these layers via:

1. **EventBus v30E** (WebSocket/SSE hybrid)
2. **Agent Stream** (`agent_reflection_log.jsonl → EventBus`)
3. **OS Stream** (OS metric artifacts → EventBus)
4. **DevEnv CLI** (tests, diagnostics, run profiles)
5. **Patch Engine Harness** (ADP-aware patch loop)
6. **ADP Telemetry Closed Loop** (DevEnv ↔ ADP ↔ Patch Engine)
7. **DevEnv GUI/HUD** (live monitoring)
8. **Full Environment Packaging** (ZIP + config for reproducibility)

---

## 2. Core Components

### 2.1 EventBus v30E

All OS / ADP / Agent / Patch signals stream through the **DevEnv EventBus**.

Canonical channels:

- `agent` → Reflective Agent events
- `os_state` → OS metrics / τ–ε dynamics
- `scheduler` → scheduler risk / entropy / drift
- `governance` → meta-governance status / risk
- `adp_hook` → DevEnv → ADP telemetry
- `patch_history` / `patch_engine` → patch history and telemetry
- `federation` → federation events
- `dashboard` → dashboard sync (optional)

Key files:

- `dev_env/eventbus/router.py` — canonical router
- `dev_env/eventbus/server.py` — HTTP + WS + SSE server
- `dev_env/eventbus/ws.py` / `sse.py` — transports

### 2.2 Agent Stream (`dev_env/agent/stream.py`)

The Agent Stream is a tail-follower over:

- `model/data/agent_reflection_log.jsonl`

It:

1. Reads each JSON line as a raw reflection entry.
2. Canonicalizes into a v1.3 schema:

   - `answer` text
   - `metrics.rii`
   - `metrics.tau_ethics`
   - `retrieval.backend`, `retrieval.topk`
   - `meta.session_id`, `meta.agent_mode`

3. Emits the canonical payload to the EventBus channel `agent`.

ADP v9.x adds a **telemetry hook**:

- DevEnv derives:

  - `entropy_drift` (attention flow)
  - `scheduler_risk` (from scheduler metrics)
  - `governance_risk` (from meta-governance metrics)

- Emits a compact payload on `adp_hook`:

```json
{
  "entropy_drift": 0.31,
  "scheduler_risk": 0.62,
  "governance_risk": 0.71
}
