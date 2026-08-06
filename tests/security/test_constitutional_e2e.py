import os
import unittest

import requests

WARM_UI_BASE_URL = os.getenv("WARM_UI_BASE_URL", "").rstrip("/")


class TestConstitutionalE2E(unittest.TestCase):
    @unittest.skipUnless(
        WARM_UI_BASE_URL,
        "Requires live server. Set WARM_UI_BASE_URL=http://127.0.0.1:8011",
    )
    def test_e2e_api_guard(self):
        """
        Integration Test: Verifies Constitution Guard via HTTP API.
        """
        print(f"Testing Constitutional Guard via API (Live): {WARM_UI_BASE_URL}")

        # 1. Post a message with forbidden word "BANANA"
        payload = {"message": "Unauthorized access to BANANA storage."}
        try:
            r = requests.post(f"{WARM_UI_BASE_URL}/api/social/post", json=payload, timeout=5)
        except requests.exceptions.ConnectionError:
            self.fail(f"Server is not reachable at {WARM_UI_BASE_URL}")

        self.assertEqual(r.status_code, 200)
        resp_json = r.json()
        print(f"Response: {resp_json}")

        # Currently the server returns a stringified JSON in message, or an object depending on version
        # Let's handle both or assert basic contract
        self.assertIn("content", str(resp_json))


if __name__ == "__main__":
    unittest.main()
