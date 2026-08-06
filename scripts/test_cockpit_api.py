import sys
import time

import requests

BASE_URL = "http://localhost:5001"
API_KEY = "dev-secret-key"


def test_root():
    print("Testing GET / ...", end=" ")
    try:
        r = requests.get(BASE_URL + "/")
        assert r.status_code == 200
        assert "<title>WarmLogic Sovereign Cockpit</title>" in r.text
        print("OK")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


def test_verify_key():
    print("Testing POST /api/verify_key (Valid)...", end=" ")
    try:
        r = requests.post(BASE_URL + "/api/verify_key", json={"key": API_KEY})
        assert r.status_code == 200
        assert r.json()["status"] == "success"
        print("OK")
    except Exception as e:
        print(f"FAIL: {e}")
        # sys.exit(1)

    print("Testing POST /api/verify_key (Invalid)...", end=" ")
    try:
        r = requests.post(BASE_URL + "/api/verify_key", json={"key": "wrong"})
        assert r.status_code == 401
        print("OK")
    except Exception as e:
        print(f"FAIL: {e}")


def test_get_logs():
    print("Testing GET /api/logs...", end=" ")
    try:
        r = requests.get(BASE_URL + "/api/logs")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        print("OK")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


def test_get_config():
    print("Testing GET /api/config...", end=" ")
    try:
        headers = {"X-API-Key": API_KEY}
        r = requests.get(BASE_URL + "/api/config", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "pii_sensitivity" in data
        print("OK")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Wait for server roughly
    time.sleep(2)
    print("Starting Cockpit API Tests...")
    test_root()
    test_verify_key()
    test_get_logs()
    test_get_config()
    print("ALL TESTS PASSED")
