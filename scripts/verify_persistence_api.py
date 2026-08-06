import json
import time

import requests

BASE_URL = "http://localhost:8000"


def test_flow():
    print(f"Checking server health at {BASE_URL}...")
    try:
        # Give it a second to be sure
        time.sleep(2)
        r = requests.get(f"{BASE_URL}/api/social/feed")
        if r.status_code != 200:
            print(f"Server not ready: {r.status_code}")
            return

        print("Server is up.")
        content = "Persistence API Test"

        print(f"Posting message: {content}")

        # POST to /api/social/post expects {"message": "..."}
        r = requests.post(f"{BASE_URL}/api/social/post", json={"message": content})
        if r.status_code == 200:
            print("Post SUCCESS")
        else:
            print(f"Post FAILED: {r.status_code} - {r.text}")
            return

        # VERIFY
        r = requests.get(f"{BASE_URL}/api/social/feed")
        feed = r.json()
        found = any(m["content"] == content for m in feed)
        if found:
            print("Verification SUCCESS: Message found in feed.")
        else:
            print("Verification FAILED: Message NOT found in feed.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_flow()
