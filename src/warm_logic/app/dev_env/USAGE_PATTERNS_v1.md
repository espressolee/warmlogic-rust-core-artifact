# Codex Usage Patterns (v1)

- Modes: cli / vscode / cursor (record which was used per task in `logs/CODEX_TASK_LOG.jsonl`).
- Prompts:
  - structure-first: describe pattern/targets/restrictions explicitly.
  - include repo hash when available.
- Live vs dry-run:
  - default dry-run; live requires gate + whitelist (`DEVLOOP_CODEX_MODE=live`, `DEVLOOP_CODEX_PATTERNS`).
- Good practices:
  - batch per pattern; avoid free-form repo search.
  - prefer deterministic auto-apply for Class A.
  - note network/proxy used (see `docs/llm/NETWORK_PROFILE_FOR_LLM.md`).
