# WarmLogic Python SDK

> **"Governance as Code" for your AI Agents.**

Add verifiable safety to your LangChain, AutoGen, or custom AI agents with one line of code.

## Installation

```bash
pip install warmlogic
```

## Quick Start

```python
import warmlogic

# 1. Connect to local daemon sidecar
warmlogic.init(ipc_port=9000)

# 2. Check Governance Status
print(warmlogic.check())

# 3. Enforce Policy (Blocking)
if warmlogic.govern(subject="Agent", action="EXECUTE_CODE", target="KERNEL"):
    print("✅ Action Allowed by Swarm Policy")
    exec(code)
else:
    print("❌ Action BLOCKED by WarmLogic")
```
