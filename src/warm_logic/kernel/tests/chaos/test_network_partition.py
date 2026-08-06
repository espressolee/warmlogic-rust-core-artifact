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

from warm_logic.kernel.identity.kinetic_id import KineticIdentity
from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey
from warm_logic.kernel.substrate.stitch_server import StitchServer

# Use a separate port for chaos testing
TEST_PORT = 8099


class TestNetworkPartition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start server first so SkipTest cannot leak global patches.
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            cls.server = StitchServer(port=TEST_PORT)
            cls.server.start()
            # Give server time to start
            time.sleep(1)
            if cls.server._httpd is None:
                raise unittest.SkipTest("Stitch server bind is unavailable in this environment")

        # Patch KineticIdentity globally for this test class
        cls.verify_patcher = patch(
            "warm_logic.kernel.identity.kinetic_id.KineticIdentity.verify_intent",
            return_value=True,
        )
        cls.sign_patcher = patch(
            "warm_logic.kernel.identity.kinetic_id.KineticIdentity.sign_intent_static",
            return_value="mock_sig",
        )
        cls.verify_patcher.start()
        cls.sign_patcher.start()

        # Register a dummy handler
        def echo_handler(payload):
            StitchServer.broadcast("echo", payload)

        StitchServer.register_handler("/echo", echo_handler)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "server"):
            cls.server.stop()
        if hasattr(cls, "verify_patcher"):
            cls.verify_patcher.stop()
        if hasattr(cls, "sign_patcher"):
            cls.sign_patcher.stop()

    def setUp(self):
        # Reset chaos before each test
        ChaosMonkey.configure(enabled=False)

    def _post(self, path, payload):
        url = f"http://127.0.0.1:{TEST_PORT}{path}"
        body = json.dumps(payload)
        data = body.encode("utf-8")

        # We use the patched sign_intent_static
        sig = KineticIdentity.sign_intent_static("priv", body)

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-Warm-ID": "pub",
                "X-Warm-Sig": sig,
            },
        )
        try:
            with urllib.request.urlopen(req) as response:
                return response.status
        except urllib.error.HTTPError as e:
            return e.code
        except urllib.error.URLError as e:
            if isinstance(getattr(e, "reason", None), PermissionError):
                raise unittest.SkipTest(
                    f"Loopback HTTP is unavailable in this environment: {e.reason}"
                )
            raise

    def test_normal_traffic(self):
        """Verify normal traffic works."""
        status = self._post("/echo", {"msg": "hello"})
        self.assertEqual(status, 202)

    def test_packet_drop_simulation(self):
        """Verify 100% packet drop works."""
        # Use mutable list for side effect verification
        received = []

        def probe_handler(p):
            received.append(p)

        StitchServer.register_handler("/probe", probe_handler)

        # 1. Test Pass
        ChaosMonkey.configure(enabled=False)
        self._post("/probe", {"id": 1})
        time.sleep(0.1)
        self.assertEqual(len(received), 1)

        # 2. Test Drop
        ChaosMonkey.configure(enabled=True, drop_rate=1.0)
        self._post("/probe", {"id": 2})
        time.sleep(0.2)  # Longer wait for drop
        self.assertEqual(len(received), 1, "Packet should have been dropped")

    def test_latency_injection(self):
        """Verify latency works."""
        ChaosMonkey.configure(enabled=True, latency_ms=500)  # 500ms

        start = time.time()
        self._post("/echo", {"msg": "slow"})
        duration = (time.time() - start) * 1000

        self.assertGreater(
            duration, 400, f"Latency should be injected (got {duration}ms)"
        )


if __name__ == "__main__":
    unittest.main()
