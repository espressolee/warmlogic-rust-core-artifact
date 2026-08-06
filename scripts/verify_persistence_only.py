import time

import requests

BASE_URL = "http://localhost:8000"
TARGET_CONTENT = "Persistence API Test"


def check_feed():
    print(f"Checking feed at {BASE_URL}...")
    try:
        time.sleep(2)
        r = requests.get(f"{BASE_URL}/api/social/feed")
        if r.status_code != 200:
            print(f"Server error: {r.status_code}")
            return False

        feed = r.json()
        found = any(m["content"] == TARGET_CONTENT for m in feed)
        if found:
            print(f"SUCCESS: '{TARGET_CONTENT}' found in feed.")
            return True
        else:
            print(f"FAILED: '{TARGET_CONTENT}' NOT found in feed.")
            print(f"Feed items: {len(feed)}")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    check_feed()
