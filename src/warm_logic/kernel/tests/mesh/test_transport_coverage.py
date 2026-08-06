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
import errno
import os
import sys
import unittest
from unittest import mock

from warm_logic.kernel.mesh.transport import (
    ChaosMiddleware,
    EncryptedTransport,
    QuicTransport,
    UdpTransport,
    create_transport,
)
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestTransportCoverage(WarmLogicTestCase):
    @staticmethod
    def _skip_if_socket_unavailable(exc: BaseException) -> None:
        if isinstance(exc, PermissionError):
            raise unittest.SkipTest(f"UDP sockets unavailable in this environment: {exc}")
        if isinstance(exc, OSError) and exc.errno in {errno.EPERM, errno.EACCES}:
            raise unittest.SkipTest(f"UDP sockets unavailable in this environment: {exc}")

    # --- UdpTransport ---
    async def test_udp_start_server(self):
        t = UdpTransport()
        host, port = "127.0.0.1", 0
        handler = mock.MagicMock()

        try:
            await t.start_server(host, port, handler)
        except (PermissionError, OSError) as exc:
            self._skip_if_socket_unavailable(exc)
            raise
        self.assertIsNotNone(t.transport)

        # Verify adapter behavior
        adapter_factory = t.transport.get_protocol
        adapter = adapter_factory()
        adapter.datagram_received(b"test", ("1.1.1.1", 1234))
        handler.assert_called_with(b"test", ("1.1.1.1", 1234))

        # connection_made coverage
        adapter.connection_made(mock.MagicMock())

        t.sendto(b"out", ("1.1.1.1", 1234))
        t.close()

    async def test_udp_wan_resolution_tailscale(self):
        # We manually inject psutil mock into sys.modules
        mock_psutil = mock.MagicMock()

        import socket
        from collections import namedtuple

        snic = namedtuple("snic", ["family", "address", "netmask", "broadcast", "ptp"])

        mock_psutil.net_if_addrs.return_value = {
            "tailscale0": [snic(socket.AF_INET, "100.64.1.1", None, None, None)],
            "en0": [snic(socket.AF_INET, "192.168.1.5", None, None, None)],
        }

        # Use context managers to ensure patches apply correctly especially with async tests
        with mock.patch.dict(sys.modules, {"psutil": mock_psutil}):
            with mock.patch.dict(os.environ, {"SOVEREIGN_WAN_MODE": "1"}):
                t = UdpTransport()
                with mock.patch("asyncio.get_running_loop") as mock_loop:
                    mock_loop.return_value.create_datagram_endpoint = mock.AsyncMock(
                        return_value=(mock.MagicMock(), None)
                    )

                    await t.start_server("0.0.0.0", 9000, lambda d, a: None)

                    args, kwargs = (
                        mock_loop.return_value.create_datagram_endpoint.call_args
                    )
                    local_addr = kwargs.get("local_addr")
                    self.assertEqual(local_addr[0], "100.64.1.1")

    async def test_udp_wan_resolution_fallback(self):
        # Mock psutil
        mock_psutil = mock.MagicMock()
        import socket
        from collections import namedtuple

        snic = namedtuple("snic", ["family", "address", "netmask", "broadcast", "ptp"])

        mock_psutil.net_if_addrs.return_value = {
            "lo0": [snic(socket.AF_INET, "127.0.0.1", None, None, None)],
            "eth0": [snic(socket.AF_INET, "203.0.113.5", None, None, None)],
        }
        with mock.patch.dict(sys.modules, {"psutil": mock_psutil}):
            with mock.patch.dict(os.environ, {"SOVEREIGN_WAN_MODE": "1"}):
                t = UdpTransport()
                ip = t._resolve_wan_ip()
                self.assertEqual(ip, "203.0.113.5")

    def test_udp_wan_resolution_fail_import(self):
        # Ensure psutil raises ImportError
        with mock.patch.dict(sys.modules):
            if "psutil" in sys.modules:
                sys.modules["psutil"] = None
            else:
                sys.modules["psutil"] = None

            with mock.patch.dict(os.environ, {"SOVEREIGN_WAN_MODE": "1"}):
                t = UdpTransport()
                ip = t._resolve_wan_ip()
                self.assertIsNone(ip)

    def test_udp_close_safe(self):
        t = UdpTransport()
        t.close()

    # --- QuicTransport ---
    def test_quic_init(self):
        import warm_logic.kernel.mesh.transport as mod

        if getattr(mod, "QuicConfiguration", None) is None:
            setattr(mod, "QuicConfiguration", mock.MagicMock())

        with mock.patch.object(mod, "AIOQUIC_AVAILABLE", True):
            qt = QuicTransport()
            self.assertIsNotNone(qt.config)

    def test_quic_missing(self):
        import warm_logic.kernel.mesh.transport as mod

        with mock.patch.object(mod, "AIOQUIC_AVAILABLE", False):
            with self.assertRaises(ImportError):
                QuicTransport()

    async def test_quic_methods(self):
        import warm_logic.kernel.mesh.transport as mod

        if getattr(mod, "QuicConfiguration", None) is None:
            setattr(mod, "QuicConfiguration", mock.MagicMock())

        with mock.patch.object(mod, "AIOQUIC_AVAILABLE", True):
            qt = QuicTransport()
            await qt.start_server("1.1.1.1", 1111, None)
            qt.sendto(b"d", ("1.1", 1))
            qt.close()

    # --- ChaosMiddleware ---
    def test_chaos_init(self):
        with mock.patch.dict(
            os.environ,
            {"WARM_LOGIC_CHAOS_LATENCY": "100", "WARM_LOGIC_CHAOS_LOSS": "0.5"},
        ):
            mock_inner = mock.MagicMock()
            cm = ChaosMiddleware(mock_inner)
            self.assertEqual(cm.latency_ms, 100)
            self.assertEqual(cm.packet_loss, 0.5)

    def test_chaos_packet_loss(self):
        mock_inner = mock.MagicMock()
        cm = ChaosMiddleware(mock_inner)
        cm.packet_loss = 1.0  # 100% loss
        cm.sendto(b"data", ("1.1", 1))
        mock_inner.sendto.assert_not_called()

    def test_chaos_latency(self):
        mock_inner = mock.MagicMock()
        cm = ChaosMiddleware(mock_inner)
        cm.latency_ms = 1000
        cm.packet_loss = 0.0

        with mock.patch("asyncio.get_running_loop") as mock_get_loop:
            mock_loop = mock.MagicMock()
            mock_get_loop.return_value = mock_loop

            cm.sendto(b"d", ("1.1", 1))

            mock_loop.call_later.assert_called_once()
            args = mock_loop.call_later.call_args[0]
            callback = args[1]
            callback()
            mock_inner.sendto.assert_called_with(b"d", ("1.1", 1))

    async def test_chaos_start_server(self):
        mock_inner = mock.MicroMock if hasattr(mock, "MicroMock") else mock.MagicMock()
        mock_inner.start_server = mock.AsyncMock()

        cm = ChaosMiddleware(mock_inner)
        await cm.start_server("h", 1, None)
        mock_inner.start_server.assert_called()

    def test_chaos_close(self):
        mock_inner = mock.MagicMock()
        cm = ChaosMiddleware(mock_inner)
        cm.close()
        mock_inner.close.assert_called()

    # --- create_transport ---
    def test_create_transport_auto(self):
        with mock.patch("warm_logic.kernel.mesh.transport.AIOQUIC_AVAILABLE", False):
            t = create_transport("AUTO")
            self.assertIsInstance(t, UdpTransport)

    def test_create_transport_quic_force_fail(self):
        with mock.patch("warm_logic.kernel.mesh.transport.AIOQUIC_AVAILABLE", False):
            with self.assertRaises(ImportError):
                create_transport("QUIC")

    def test_create_transport_quic_success(self):
        import warm_logic.kernel.mesh.transport as mod

        if getattr(mod, "QuicConfiguration", None) is None:
            setattr(mod, "QuicConfiguration", mock.MagicMock())

        with mock.patch("warm_logic.kernel.mesh.transport.AIOQUIC_AVAILABLE", True):
            t = create_transport("QUIC")
            self.assertIsInstance(t, QuicTransport)

    def test_create_transport_chaos(self):
        with mock.patch.dict(os.environ, {"WARM_LOGIC_CHAOS_LATENCY": "10"}):
            t = create_transport("AUTO")
            self.assertIsInstance(t, ChaosMiddleware)

    # --- EncryptedTransport ---
    def test_encrypted_transport(self):
        mock_inner = mock.MagicMock()
        et = EncryptedTransport(mock_inner)
        et.sendto(b"d", ("1", 1))
        mock_inner.sendto.assert_called()
        et.close()
        mock_inner.close.assert_called()

    async def test_encrypted_transport_start(self):
        mock_inner = mock.MagicMock()
        mock_inner.start_server = mock.AsyncMock()
        et = EncryptedTransport(mock_inner)
        await et.start_server("h", 1, None)
        mock_inner.start_server.assert_called()


if __name__ == "__main__":
    unittest.main()
