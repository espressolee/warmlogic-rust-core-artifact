# Quickstart Guide (0-5 Minutes)

> **Status**: research prototype (Research Prototype)
> **Warning**: This SDK is experimental. Do not use in production.

WarmLogic provides the infrastructure to make AI agentic decisions verifiable. This guide will help you boot your first Sovereign Kernel.

## 1. ⚡ One-Line Start (Docker)

The easiest way to explore WarmLogic is via Docker.

```bash
docker-compose up -d
```

- **Dashboard**: [http://localhost:8000](http://localhost:8000)
- **Logs**: `docker-compose logs -f warmlogic`

---

## 2. 🛠️ Native Installation (Local Dev)

If you want to modify policies or integrate with your Python code.

### Prerequisites
- Python 3.12+
- Rust 1.75+

### Steps
```bash
# 1. Install and compile Rust core
make install-dev

# 2. Start the UI server
python -m warm_logic.ui.server
```

---

## 3. 🧪 Your First Sovereign Decision

Open a Jupyter notebook or a Python script and run the following:

```python
from warm_logic.sdk import SovereignClient

# Connect to the local kernel
client = SovereignClient()

# Propose an intent
decision = client.propose_action(
    intent="send_email",
    context={"to": "user@example.com", "subject": "Hello"}
)

print(f"Decision: {decision.verdict}")
print(f"Audit Hash: {decision.proof_hash}")
```

---

## 🔍 What's Next?

1.  **Modify Policies**: Edit `config/constitution.yaml` to change what your agent is allowed to do.
2.  **Explore the Mesh**: Add a second node using `docker-compose -f docker-compose.test.yml up`.
3.  **Check the Glossary**: Stumbled on a term? See [GLOSSARY.md](../GLOSSARY.md).
4.  **Troubleshooting**: See [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) if you hit any snags.
