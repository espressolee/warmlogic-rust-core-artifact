# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey
from warm_logic.kernel.substrate.stitch_server import StitchServer

TEST_PORT = 8099


class TestByzantineInjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = StitchServer(host="127.0.0.1", port=TEST_PORT)
        cls.server.start()
        # Give it a moment to bind
        time.sleep(0.5)
        if cls.server._httpd is None:
            raise unittest.SkipTest("Stitch server bind is unavailable in this environment")

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        StitchServer.reset()
        from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey

        ChaosMonkey.reset()

    def setUp(self):
        ChaosMonkey.configure(enabled=False)
        self.received_payload = None

        def spy_handler(p):
            self.received_payload = p

        StitchServer.register_handler("/spy", spy_handler)

    def _post(self, path, payload):
        url = f"http://127.0.0.1:{TEST_PORT}{path}"
        data_str = json.dumps(payload)
        data = data_str.encode("utf-8")

        # hardware attestation enforcement: Provide dummy but valid-format headers for test
        # In a real scenario, we'd use KineticIdentity.sign_intent_static
        headers = {
            "Content-Type": "application/json",
            "X-Warm-ID": "TEST-ID",
            "X-Warm-Sig": "TEST-SIG",
        }

        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            # Short timeout to prevent hangs
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            return 500

    def test_payload_corruption(self):
        """Verify corruption rate modifies payload."""
        # We need to mock KineticIdentity.verify_intent to accept our test headers
        from warm_logic.kernel.identity.kinetic_id import KineticIdentity

        with patch.object(KineticIdentity, "verify_intent", return_value=True):
            ChaosMonkey.configure(enabled=True, corruption_rate=1.0)  # 100% corruption

            original = {
                "hash": "12345678",
                "signature": "valid_sig",
                "data": "important",
            }
            status = self._post("/spy", original)
            self.assertEqual(status, 202)

            time.sleep(0.1)
            self.assertIsNotNone(self.received_payload)
            # Note: ChaosMonkey implementation forces hash to "DEADBEEF"*8 when corrupted
            self.assertEqual(self.received_payload["hash"], "DEADBEEF" * 8)
            self.assertEqual(self.received_payload["signature"], "INVALID")
            self.assertEqual(
                self.received_payload["data"], "important"
            )  # Untouched field


if __name__ == "__main__":
    unittest.main()
