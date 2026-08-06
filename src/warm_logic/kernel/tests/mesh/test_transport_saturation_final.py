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
import os
import unittest
from unittest import mock

# We need to mock sys.modules BEFORE importing the module if we want top-level coverage?
# No, we can't easily hit 13-15 if it was already imported.
# But we can reload it.


class TestTransportSaturationFinal(unittest.IsolatedAsyncioTestCase):
    async def test_encrypted_transport_integrity_fail_surgical(self):
        # Line 255-256
        from warm_logic.kernel.mesh.transport import EncryptedTransport, UdpTransport

        mock_inner = mock.AsyncMock(spec=UdpTransport)
        enc = EncryptedTransport(mock_inner)

        handler_called = False

        def dummy_handler(d, a):
            nonlocal handler_called
            handler_called = True

        await enc.start_server("127.0.0.1", 0, dummy_handler)
        secure_handler = mock_inner.start_server.call_args[0][2]

        with mock.patch("warm_logic.kernel.mesh.transport.logger") as mock_log:
            await secure_handler(b"NOT_JSON", ("1.1.1.1", 80))
            self.assertFalse(handler_called)
            mock_log.warning.assert_called_with(
                "🛡️  Dropping unverified packet from ('1.1.1.1', 80)"
            )

    def test_chaos_middleware_no_latency_surgical(self):
        # Line 198 (the 'else' branch)
        from warm_logic.kernel.mesh.transport import ChaosMiddleware

        mock_inner = mock.MagicMock()
        with mock.patch.dict(
            os.environ,
            {"WARM_LOGIC_CHAOS_LATENCY": "0", "WARM_LOGIC_CHAOS_LOSS": "0.0"},
        ):
            chaos = ChaosMiddleware(mock_inner)
            # Force values in case of caching
            chaos.latency_ms = 0
            chaos.packet_loss = 0.0
            chaos.sendto(b"data", ("1.1.1.1", 80))
            mock_inner.sendto.assert_called_with(b"data", ("1.1.1.1", 80))

    def test_quic_surgical(self):
        # Line 142, 151, 154, 157
        from warm_logic.kernel.mesh.transport import AIOQUIC_AVAILABLE, QuicTransport

        if not AIOQUIC_AVAILABLE:
            with self.assertRaises(ImportError):
                QuicTransport()
        else:
            qt = QuicTransport()
            qt.sendto(b"", ("", 0))  # Line 151
            qt.close()  # Line 154
            self.assertEqual(qt.get_port(), 0)  # Line 157

    def test_top_level_import_fallback(self):
        """Coverage for lines 13-15 or 17-19."""
        import importlib

        # To hit 17-19: ensure aioquic is MISSING
        with mock.patch.dict(
            "sys.modules",
            {
                "aioquic": None,
                "aioquic.asyncio": None,
                "aioquic.quic.configuration": None,
            },
        ):
            # This doesn't work if already loaded, but we reload.
            import warm_logic.kernel.mesh.transport

            importlib.reload(warm_logic.kernel.mesh.transport)
            self.assertFalse(warm_logic.kernel.mesh.transport.AIOQUIC_AVAILABLE)

        # To hit 13-15: we'd need aioquic. Let's just mock it exists.
        mock_aq = mock.MagicMock()
        with mock.patch.dict(
            "sys.modules",
            {
                "aioquic": mock_aq,
                "aioquic.asyncio": mock_aq,
                "aioquic.quic.configuration": mock_aq,
            },
        ):
            importlib.reload(warm_logic.kernel.mesh.transport)
            self.assertTrue(warm_logic.kernel.mesh.transport.AIOQUIC_AVAILABLE)


if __name__ == "__main__":
    unittest.main()
