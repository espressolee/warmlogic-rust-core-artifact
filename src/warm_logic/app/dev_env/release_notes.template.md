# Warm Logic DevEnv {{version}}
_Date: {{date}}_

## Highlights
- EventBus + HUD telemetry alignment
- Container/K8s packaging automation

## Artifacts
- Docker image: `ghcr.io/<org>/warm-logic-devenv:{{version}}`
- ZIP bundle: `WarmLogic_DevEnv_{{version}}.zip` (see `.sha256` for checksum)

## Verification Checklist
- [ ] `wlctl devenv smoke`
- [ ] `python -m pytest dev_env/tests -m "not slow"`
- [ ] EventBus `/health` returning metrics and Prometheus endpoint reachable
