import os

# Set required env var before importing server (which checks at import time)
os.environ.setdefault("SOVEREIGN_COCKPIT_KEY", "test_key_for_ci")

from fastapi.testclient import TestClient

from warm_logic.app.cockpit.server import API_KEY, app

# Set raise_server_exceptions=False to allow checking the 500 response body
# instead of having the TestClient re-raise the exception.
client = TestClient(app, raise_server_exceptions=False)


def test_ui_security_global_handler():
    """
    Phase 53.3: Verify Global Exception Handler catches 500s and masks stack trace.
    SIM-037: UI Security Guard.
    """

    # 1. Define a route that crashes
    @app.get("/api/test/crash")
    def crash_route():
        raise ValueError("Simulated Core Meltdown")

    # 2. Call it
    response = client.get("/api/test/crash", headers={"X-API-Key": API_KEY})

    # 3. Verify Response
    assert (
        response.status_code == 500
    ), f"Expected 500, got {response.status_code}: {response.text}"
    data = response.json()

    # 4. Assert Security Properties
    assert "error_code" in data
    assert data["error_code"] == "WL-E500"
    assert "correlation_id" in data
    assert data["message"] == "Internal Sovereign Error"

    # 5. Assert NO leak
    assert "Simulated Core Meltdown" not in data.values()
    assert "traceback" not in str(data)

    print(f"✅ UI Security Handler Verified: {data}")


if __name__ == "__main__":
    test_ui_security_global_handler()
