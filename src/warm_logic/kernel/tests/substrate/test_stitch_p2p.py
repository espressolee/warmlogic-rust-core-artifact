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
import http.client
import json
import time
import unittest

from warm_logic.kernel.substrate.stitch_server import StitchServer


class TestStitchP2P(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Force Singleton Reset from previous tests
        from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey

        ChaosMonkey.reset()
        StitchServer.reset()

        # Start a local StitchServer on a different port for testing
        cls.server = StitchServer(host="127.0.0.1", port=8044)
        cls.server.start()
        time.sleep(1)  # Wait for boot
        if cls.server._httpd is None:
            raise unittest.SkipTest("Stitch server bind is unavailable in this environment")

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        StitchServer._instance = None

    def test_post_block_handler(self):
        """Verify that registering a handler and POSTing to it works with W-ID headers."""
        received_data = []

        def mock_handler(payload):
            received_data.append(payload)

        self.server.register_handler("/block", mock_handler)

        # Simulate a signed POST from a Peer
        from unittest.mock import MagicMock, patch

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.rust_loader.load_rust_core") as mock_loader:
                mock_rs = MagicMock()
                # Setup mock return values for keygen, sign, verify
                mock_rs.generate_keypair.return_value = ("pk", "sk")
                mock_rs.sign.return_value = "sig"
                mock_rs.verify.return_value = True

                mock_loader.return_value = mock_rs

                from warm_logic.kernel.identity.kinetic_id import KineticIdentity

                pk, sk = KineticIdentity.generate_keypair()

                conn = http.client.HTTPConnection("127.0.0.1", 8044, timeout=5)
                payload = {
                    "block": {"hash": "abc"},
                    "balances": {},
                    "zk_proof": "proof",
                }
                body = json.dumps(payload)
                sig = KineticIdentity.sign_intent_static(sk, body)

                headers = {
                    "Content-type": "application/json",
                    "X-Warm-ID": pk,
                    "X-Warm-Sig": sig,
                }
                try:
                    conn.request("POST", "/block", body, headers)
                except (PermissionError, OSError) as exc:
                    raise unittest.SkipTest(
                        f"Loopback HTTP is unavailable in this environment: {exc}"
                    )

                response = conn.getresponse()
                self.assertEqual(response.status, 202)

        data = json.loads(response.read().decode())
        self.assertEqual(data["status"], "accepted")
        self.assertEqual(len(received_data), 1)
        self.assertEqual(received_data[0]["block"]["hash"], "abc")


if __name__ == "__main__":
    unittest.main()
