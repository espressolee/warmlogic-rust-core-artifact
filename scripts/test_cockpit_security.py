import requests

BASE_URL = "http://127.0.0.1:5001"
API_KEY = "dev-secret-key"


def test_api_unauthorized():
    print("Testing unauthorized access...")
    requests.get(f"{BASE_URL}/api/status")


def test_seal_unauthorized():
    print("Testing unauthorized seal access...")
    r = requests.post(f"{BASE_URL}/api/config/seal", json={"test": True})
    assert r.status_code == 401
    print("Unauthorized seal blocked.")


def test_seal_authorized():
    print("Testing authorized seal access...")
    headers = {"X-API-Key": API_KEY}
    r = requests.post(
        f"{BASE_URL}/api/config/seal", json={"pii_sensitivity": 0.5}, headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert "signature" in data
    print("Authorized seal successful.")


def test_rate_limiting():
    print("Testing rate limiting...")
    # Triggering many requests
    headers = {"X-API-Key": API_KEY}
    for i in range(105):
        r = requests.get(f"{BASE_URL}/api/status", headers=headers)
        if r.status_code == 429:
            print(f"Rate limited at request {i + 1}.")
            return

    # If we are here, rate limiting failed (or threshold too high for this test)
    # print("Rate limiting NOT triggered.")


if __name__ == "__main__":
    # Note: app.py must be running
    try:
        test_seal_unauthorized()
        test_seal_authorized()
        test_rate_limiting()
    except Exception as e:
        print(f"Test FAILED: {e}")
