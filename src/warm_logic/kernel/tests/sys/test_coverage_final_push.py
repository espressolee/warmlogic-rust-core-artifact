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
import time
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

from warm_logic.kernel.ops.audit_agent import AuditAgent, IntegrityReport
from warm_logic.kernel.substrate.stitch_server import StitchRequestHandler, StitchServer


class TestAuditAgentSurgical(unittest.TestCase):
    @patch("warm_logic.sdk.identity.SovereignIdentity")
    def test_lifecycle(self, MockIdentity):
        # Mock Identity instance to avoid hardware check
        MockIdentity.return_value = MagicMock()

        mock_audit = MagicMock()
        mock_fleet = MagicMock()
        # Mock Fleet nodes
        node = MagicMock()
        node.hardware_id = "HW123"
        node.region = "US-EAST"
        mock_fleet.nodes = {"N1": node}

        agent = AuditAgent(mock_audit, mock_fleet, interval=0.1)

        # Test autonomous audit logic
        mock_audit.detect_drift.return_value = "Drift"
        mock_audit.run_full_audit.return_value = IntegrityReport(score=9.0)
        mock_audit.detect_misconduct.return_value = [{"node_id": "N1", "reason": "Bad"}]

        agent.perform_autonomous_audit()

        mock_audit.reconcile_state.assert_called()
        self.assertEqual(agent.last_report.score, 9.0)

        # Test Threading
        agent.start()
        time.sleep(0.2)
        agent.stop()
        self.assertFalse(agent._thread)


class TestStitchServerSurgical(unittest.TestCase):
    def setUp(self):
        pass

    @patch("warm_logic.kernel.substrate.stitch_server.HTTPServer")
    def test_server_lifecycle(self, MockServer):
        server = StitchServer("localhost", 0)
        server.start()
        self.assertTrue(server.running)

        server.broadcast("TEST", {"a": 1})

        server.register_handler("/test", lambda x: None)

        server.stop()
        self.assertFalse(server.running)

    @patch("warm_logic.kernel.identity.kinetic_id.KineticIdentity")
    def test_request_handler_post(self, MockIdentity):
        # Mock socket
        mock_req = MagicMock()
        # Provide rfile/wfile via makefile
        rfile = BytesIO(b'{"key": "val"}')
        wfile = BytesIO()
        mock_req.makefile.side_effect = lambda mode, *args: (
            rfile if "r" in mode else wfile
        )

        # Instantiating handler calls setup() which calls makefile
        # We patch BaseHTTPRequestHandler init to skip standard setup
        with patch("http.server.BaseHTTPRequestHandler.__init__", return_value=None):
            handler = StitchRequestHandler(mock_req, ("127.0.0.1", 80), MagicMock())
            handler.headers = {
                "Content-Length": "14",  # len of JSON string
                "X-Warm-ID": "PUBKEY",
                "X-Warm-Sig": "SIG",
            }
            handler.rfile = rfile
            handler.wfile = wfile
            handler.client_address = ("127.0.0.1", 1234)
            handler.path = "/test"
            handler.requestline = "POST /test HTTP/1.1"  # Required for log_request
            handler.request_version = "HTTP/1.1"  # Required for log_request
            handler.command = "POST"

            # 1. Success
            MockIdentity.verify_intent.return_value = True
            StitchServer.register_handler("/test", lambda x: None)

            handler.do_POST()

            resp = wfile.getvalue()
            self.assertIn(b"accepted", resp)

            # 2. Invalid Sig
            MockIdentity.verify_intent.return_value = False
            # Reset buffers
            rfile.seek(0)
            wfile = BytesIO()
            handler.wfile = wfile

            handler.do_POST()
            self.assertIn(b"Invalid Kinetic Proof", wfile.getvalue())
