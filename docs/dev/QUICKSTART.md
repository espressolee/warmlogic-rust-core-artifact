# 🚀 WarmLogic Quickstart

> **Goal**: Get WarmLogic running in under 5 minutes.
>
> ⚠️ **research prototype Warning**: This is pre-release software. API may change without notice. Not for production use.

---

## Option 1: Docker (Enterprise Ready)

```bash
# Clone and start
git clone https://github.com/espressolee/WarmLogic
cd warmlogic
docker compose up -d

# Open the dashboard
open http://localhost:8033
```

**Done!** You now have a running WarmLogic node with:
- Sovereign Cockpit Dashboard at `http://localhost:8033`
- REST API at `http://localhost:8033/api/v1`
- Persistence: All decision data is stored in `Resonance/Citadel/out`

---

## Option 2: Local Install (2 minutes)
> **Prerequisite**: Python 3.10+ (recommend `pyenv` or `conda`)

```bash
# Clone
git clone https://github.com/espressolee/WarmLogic
cd warmlogic

# Create Virtual Environment
python3 -m venv .venv
source .venv/bin/activate

# Install Core
pip install -e .

# Start the Cockpit
wlctl cockpit start
```

---

## Your First AI Decision

Once the server is running, make your first cryptographically-signed AI decision:

```bash
curl -X POST http://localhost:8033/api/v1/decision \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-api-key>" \
  -d '{"mode": "analyze", "prompt": "Hello, Sovereign World!"}'
```

**Response:**
```json
{
  "decision_id": "dec_abc123",
  "signature": "ML-DSA-65 signature here...",
  "ledger_block": 1,
  "timestamp": "2026-02-05T17:00:00Z"
}
```

---

## Next Steps

| Action       | Command                                     |
| :----------- | :------------------------------------------ |
| Run tests    | `pytest tests/`                             |
| CLI help     | `python -m warm_logic.app.cli.wlctl --help` |
| Full docs    | docs/INDEX.md                   |
| Architecture | docs/ARCHITECTURE.md     |

---

## Troubleshooting

### `maturin: command not found`
```bash
pip install maturin
```

### `ImportError: warm_logic_rs`
```bash
cd rust_core && maturin develop --release && cd ..
```

### Port 8033 in use
```bash
COCKPIT_HTTP_PORT=8034 wlctl cockpit start
```

---

**Need more help?** See TROUBLESHOOTING.md or INSTALLATION.md.
