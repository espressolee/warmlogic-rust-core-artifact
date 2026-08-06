# LLM Profiles — M4 Pro 48GB (SAFE_LOCAL)

This profile documents a practical local setup for MacBook Pro M4 Pro (48GB) with Ollama. It maps four roles to Qwen2.5 variants and shows how to route via `wl llm`.

Recommended models (Ollama tags)
- L0 (light/agent): `qwen2.5:1.5b`
- L1 (default chat/docs/spec): `qwen2.5` (7B)
- L2 (heavy reasoning/math/paper): `qwen2.5:14b` or `qwen2.5:32b`
- L3 (code): `qwen2.5-coder:7b`

Pull models
```
ollama pull qwen2.5
ollama pull qwen2.5:1.5b
ollama pull qwen2.5:14b
ollama pull qwen2.5:32b
ollama pull qwen2.5-coder:7b
```

.env presets (SAFE_LOCAL)
```
WL_LLM_MODE=SAFE_LOCAL
WL_LLM_DEFAULT_MODEL="ollama:qwen2.5"
WL_LLM_HEAVY_MODEL="ollama:qwen2.5:14b"
WL_LLM_CODE_MODEL="ollama:qwen2.5-coder:7b"
WL_LLM_LIGHT_MODEL="ollama:qwen2.5:1.5b"
```

Switch model presets on‑the‑fly
```
# default env
eval "$(wl llm policy --wl-mode safe_local --profile paper)"

# override to heavy/code/light default model
eval "$(wl llm policy --wl-mode safe_local --profile paper --use heavy)"
eval "$(wl llm policy --wl-mode safe_local --profile paper --use code)"
eval "$(wl llm policy --wl-mode safe_local --profile paper --use light)"
```

Health checks
```
wl llm health --endpoint http://127.0.0.1:11434 --mode ollama --model qwen2.5
curl -sS http://127.0.0.1:11434/api/generate -H 'Content-Type: application/json' \
  -d '{"model":"qwen2.5","prompt":"ping","stream":false}'
```

Notes
- Keep WLPv1 boundary: SAFE_LOCAL by default; avoid sending internal artifacts to remote.
- Use 32B only when required (memory/time heavier than 14B).
