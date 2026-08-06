import os

import pytest
from fastapi.testclient import TestClient

# Mock Environment BEFORE Import
os.environ["SOVEREIGN_COCKPIT_KEY"] = "test_key"
os.environ["SOVEREIGN_COMMERCIAL_MODE"] = "1"

from warm_logic.app.cockpit.server import app, token_ledger

client = TestClient(app)


def test_free_endpoints():
    # Health checks should be free
    response = client.get("/health/live")
    assert response.status_code == 200

    # Static files (mocked check)
    # response = client.get("/static/style.css")
    # assert response.status_code != 402


def test_paid_endpoint_no_payment():
    # Force Commercial Mode logic in Middleware
    from warm_logic.app.cockpit import server

    server.COMMERCIAL_MODE = True

    # Try accessing mesh status without X-Sovereign-Node-ID
    response = client.get("/api/mesh")
    # Should get 402 Payment Required
    assert response.status_code == 402
    assert response.json()["error"] == "Payment Required"


def test_paid_endpoint_insufficient_funds():
    from warm_logic.app.cockpit import server

    server.COMMERCIAL_MODE = True

    # User B has 0 balance
    headers = {"X-Sovereign-Node-ID": "NODE_POOR"}
    response = client.get("/api/mesh", headers=headers)
    assert response.status_code == 402
    assert response.json()["error"] == "Insufficient Funds"


def test_paid_endpoint_success():
    from warm_logic.app.cockpit import server

    server.COMMERCIAL_MODE = True

    # Mint coins for RICH user
    token_ledger.mint("NODE_RICH", 10.0)

    headers = {"X-Sovereign-Node-ID": "NODE_RICH"}
    # Add API Key to bypass 401
    headers["X-API-Key"] = "test_key"

    response = client.get("/api/mesh", headers=headers)

    # Mock adapter might fail, so we accept 200 or 500/404/503
    # BUT we specifically want to assert NOT 402
    assert response.status_code != 402

    # Expect balance deduction
    # 0.1 per call
    assert token_ledger.get_balance("NODE_RICH") == 9.9
