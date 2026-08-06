
---

After the ADP integration section:

ADP Patch Proposal schema is defined in model/OS_Phase_1_to_19_FULL_SPEC.md, Phase 18.
Warm Logic OS — Developer Environment Specification v1.3
(DevEnv v4.2 → v5.0 → v1.3 Unified)

Status: Stable — OS/ADP v8, Phase 24–30 unified schema

---

1. Purpose
----------

As the Layer-6 Developer Operating Layer, Warm Logic DevEnv provides:

1. Unified observability (Observability Layer)
   - EventBus v30E (WS/SSE)
   - Reflective Agent Stream
   - Unified OS / Scheduler / Governance / ADP patch_history signals

2. Automated development loop (Automation Layer)
   - Runs AutoDev, Scheduler, and Dashboard in a single layer
   - Unified execution via tmux, VSCode, and CLI

3. Consistency and reproducibility (Reproducibility Layer)
   - canonical EventBus schema
   - Relative-path import normalization
   - ZIP packaging + layout check

4. UI/UX Layer
   - WebHUD (Event Stream, Inspector, KPI, Federation view)

5. Federation (v5.0–v1.3)
   - F0: single-node event relay
   - F1: multi-agent routing (by agent_id)
   - F2: multi-node DevEnv cluster (heartbeat, metadata)

---

2. Architectural Alignment (Layers 0–6)
---------------------------------------

Layer | Component        | DevEnv role
----- | ---------------- | ------------------------------------------
0     | Data / Archive   | EventBus I/O (watches JSON/JSONL artifacts)
1     | OS / Memory      | Canonicalizes Phase 24-30 signals
2     | Scheduler / Meta | Integrates switching, drift, entropy forecast
3     | ADP              | patch_history broadcast
4     | Reflective Agent | Real-time RII / τ_ethics stream
5     | Dashboard        | Emits Phase 29-30 metrics
6     | DevEnv           | EventBus + Federation + Automation

---

3. EventBus v30E
----------------

Transport: WebSocket + SSE

### 3.1 /emit Request

```json
{
  "channel": "<agent|os_state|scheduler|governance|patch_history|federation>",
  "payload": { },
  "origin": "local|remote",
  "agent_id": "agent-a"
}

3.2 Canonical Routed Event

router.py:

{
  "type": "<canonical-type>",
  "timestamp": 173123.123,
  "origin": "local",
  "agent_id": "agent-a",
  "metrics": { },
  "raw": { ... }
}

Canonical Types (v1.3):

Type	From	Notes
agent_reflection	Reflective Agent	answer, RII, τ_ethics, retrieval
os_update	OS Phase 24–28	metrics, meta_kernel
scheduler_status	Scheduler Phase29	risk_score, drift, entropy
governance_status	Phase 30A–30C	status, policy signals
patch_history	ADP	patch_count, last_patch
federation_event	F0–F2	remote multiplex routing
unknown	other	fallback (never fails)


⸻

	4.	DevOps / Automation

⸻

	•	install/install.sh
	•	Python venv, CLI symlink, base tool installation
	•	tmux/tmux_restore.sh, tmux/.tmux.conf
	•	4-window DevOS (dev / tests / agent / eventbus)
	•	vscode/keybindings.json, vscode/tasks.json
	•	Shortcuts to run AutoDev / Scheduler / Dashboard
	•	build/build_zip.py
	•	VERSION-based DevEnv ZIP packaging
	•	build/check_dev_env_layout.py
	•	v1.3 layout validation

⸻

	5.	Federation v1.3 (F0–F2)

⸻

Directory: dev_env/federation/

Component	Role
federation_router.py	route_federated_event → federation_event
cluster_manager.py	Node registry, heartbeat table
agent_proxy.py	HTTP proxy to a remote EventBus /emit
tests/test_federation*	F0-F2 scaffold tests

F0 — Single-node passthrough
F1 — agent-aware routing (by agent_id)
F2 — multi-node cluster (register_node, heartbeat, snapshot)

⸻

	6.	Directory Layout (v1.3)

⸻


dev_env/
    VERSION
    __init__.py

    agent/
        stream.py

    build/
        build_zip.py
        check_dev_env_layout.py
        templates/README_DEV_ENV.md.j2

    cli/
        wl_agent_stream
        wl_eventbus
        wl_patch_watch

    eventbus/
        router.py
        server.py
        sse.py
        ws.py
        ui/index.html
        channels/

    federation/
        routers/federation_router.py
        cluster/cluster_manager.py
        agents/agent_proxy.py
        tests/test_federation_bootstrap.py

    monitor/
        watcher.py

    install/
        install.sh

    specs/
        DEV_ENV_SPEC.md

    tmux/
        .tmux.conf
        tmux_restore.sh
        sessions/

    vscode/
        keybindings.json
        tasks.json

    tests/
        test_eventbus_router.py
        test_paths.py
        test_eventbus_ws.py  (manual smoke)


⸻

Enterprise Notice
-----------------

DevEnv Enterprise v1.3 introduces additional routing, layout, and schema
rules defined in `docs/DEV_ENV_ENTERPRISE_V1.3.md`. The layout validator
and schema validator must consult that document when running in
enterprise mode.
