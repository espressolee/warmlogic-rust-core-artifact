# WarmLogic SDK

The official Python SDK for interacting with the WarmLogic Sovereign AI Kernel.

## Installation

```bash
pip install warm_logic_sdk
```

## Usage

```python
from warm_logic_sdk import SovereignClient

client = SovereignClient(rpc_url="http://localhost:8000")

# check balance
print(client.get_balance())
```
