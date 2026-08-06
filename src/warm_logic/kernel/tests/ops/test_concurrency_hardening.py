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
import queue
import threading
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.substrate.stitch_server import (
    StitchRequestHandler,
    StitchServer,
    _event_buffer,
    _subscribers,
)


class TestConcurrencyHardening(unittest.TestCase):
    def setUp(self):
        # Reset globals
        StitchServer._instance = None
        global _event_buffer, _subscribers
        _event_buffer.clear()
        _subscribers.clear()

    def test_server_lifecycle_edge_cases(self):
        s = StitchServer("localhost", 0)

        class _FakeHTTPD:
            def __init__(self):
                self.server_address = ("127.0.0.1", 12345)
                self._stop = threading.Event()

            def serve_forever(self):
                self._stop.wait(timeout=2.0)

            def shutdown(self):
                self._stop.set()

            def server_close(self):
                return None

        # 1. Double Start should not spin up a second server thread while running.
        with patch(
            "warm_logic.kernel.substrate.stitch_server.HTTPServer",
            return_value=_FakeHTTPD(),
        ):
            s.start()
            first_thread = s._server_thread
            self.assertTrue(s.running)

            s.start()  # Should return early
            self.assertIs(s._server_thread, first_thread)
            s.stop()

        # 2. Start Bind Failure
        s.running = False
        s._server_thread = None

        with patch(
            "warm_logic.kernel.substrate.stitch_server.HTTPServer",
            side_effect=OSError("Bind fail"),
        ):
            s.start()
            # Start failure should leave server in a clean non-running state.
            self.assertFalse(s.running)
            self.assertIsNone(s._httpd)
            s.stop()  # Cleanup

    def test_sse_resync_and_hardening(self):
        # Populate global buffer
        _event_buffer.append((1, "TEST", {"v": 1}))
        _event_buffer.append((2, "TEST", {"v": 2}))

        h = MagicMock(spec=StitchRequestHandler)
        h.path = "/stream"
        h.headers = {"Last-Event-ID": "1"}
        h.client_address = ("1.2.3.4", 9999)

        # Mock wfile
        h.wfile = MagicMock()

        # Mock Queue behavior
        # First get returns None to break loop immediately after resync logic
        mock_q = MagicMock()
        mock_q.get.return_value = None

        with patch(
            "warm_logic.kernel.substrate.stitch_server.queue.Queue", return_value=mock_q
        ):
            StitchRequestHandler.do_GET(h)

            # Verify Re-sync write: ID 2 should be written
            # ID 1 is skipped because > 1
            h.wfile.write.assert_any_call(
                b'id: 2\ndata: {"event_id": 2, "event_type": "TEST", "data": {"v": 2}}\n\n'
            )

    def test_sse_broken_pipe(self):
        h = MagicMock(spec=StitchRequestHandler)
        h.path = "/stream"
        h.headers = {}
        h.client_address = ("1.2.3.4", 9999)
        h.wfile = MagicMock()

        # Write raises BrokenPipeError
        h.wfile.write.side_effect = BrokenPipeError("Bye")

        # Queue gives one event then None
        mock_q = MagicMock()
        mock_q.get.side_effect = [{"event_id": 3}, None]

        with patch(
            "warm_logic.kernel.substrate.stitch_server.queue.Queue", return_value=mock_q
        ):
            # This should catch exception and return cleanly
            StitchRequestHandler.do_GET(h)

            # Verify subscriber removal
            from warm_logic.kernel.substrate.stitch_server import _subscribers

            self.assertNotIn(mock_q, _subscribers)

    def test_queue_overflow(self):
        # Create a full queue
        q_full = MagicMock(spec=queue.Queue)
        q_full.put.side_effect = queue.Full("Full")

        from warm_logic.kernel.substrate.stitch_server import _subscribers

        _subscribers.append(q_full)

        # Broadcast should succeed (ignoring full queue)
        StitchServer.broadcast("EVT", {})
        q_full.put.assert_called()

    def test_cockpit_serving_error(self):
        h = MagicMock(spec=StitchRequestHandler)
        h.path = "/cockpit"

        with patch("builtins.open", side_effect=PermissionError("No Access")):
            StitchRequestHandler.do_GET(h)
            h.send_response.assert_called_with(404)

    def test_post_hardening(self):
        h = MagicMock(spec=StitchRequestHandler)
        h.path = "/api"
        h.command = "POST"
        h.headers = {"Content-Length": "2", "X-Warm-ID": "pk", "X-Warm-Sig": "sig"}
        h.client_address = ("1.2.3.4", 9999)

        # FIX: Explicitly set rfile/wfile mock
        h.rfile = MagicMock()
        h.rfile.read.return_value = b"{}"
        h.wfile = MagicMock()

        # 1. Signature Verify Fail
        with patch(
            "warm_logic.kernel.identity.kinetic_id.KineticIdentity.verify_intent",
            return_value=False,
        ):
            StitchRequestHandler.do_POST(h)
            h.send_response.assert_called_with(403)

        # 2. Missing Headers (Specifically X-Warm-ID)
        # Content-Length must exist to avoid KeyError in typical usage or should be mocked to 0
        h.headers = {"Content-Length": "0"}
        StitchRequestHandler.do_POST(h)
        h.send_response.assert_called_with(401)

        # 3. Exception in Processing
        h.headers = {"Content-Length": "2", "X-Warm-ID": "pk", "X-Warm-Sig": "sig"}
        with patch(
            "warm_logic.kernel.identity.kinetic_id.KineticIdentity.verify_intent",
            return_value=True,
        ):
            with patch("json.loads", side_effect=ValueError("Bad JSON")):
                StitchRequestHandler.do_POST(h)
                h.send_response.assert_called_with(400)
