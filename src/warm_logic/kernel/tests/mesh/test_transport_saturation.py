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
import asyncio
import os
import unittest
from unittest import mock

from warm_logic.kernel.mesh.transport import (
    ChaosMiddleware,
    EncryptedTransport,
    QuicTransport,
    UdpTransport,
    create_transport,
)


class TestTransportSaturation(unittest.IsolatedAsyncioTestCase):
    async def test_udp_transport_wan_resolve(self):
        with mock.patch.dict(os.environ, {"SOVEREIGN_WAN_MODE": "1"}):
            with mock.patch("psutil.net_if_addrs") as mock_if:
                addr = mock.MagicMock()
                addr.family = 2
                addr.address = "100.64.1.1"
                mock_if.return_value = {"tailscale0": [addr]}

                upd = UdpTransport()
                with mock.patch("asyncio.get_running_loop") as mock_loop:
                    mock_loop.return_value.create_datagram_endpoint = mock.AsyncMock(
                        return_value=(mock.MagicMock(), None)
                    )
                    await upd.start_server("0.0.0.0", 0, lambda d, a: None)
                    args, kwargs = (
                        mock_loop.return_value.create_datagram_endpoint.call_args
                    )
                    self.assertEqual(kwargs["local_addr"][0], "100.64.1.1")

    def test_udp_wan_resolve_fail(self):
        upd = UdpTransport()
        with mock.patch("psutil.net_if_addrs", side_effect=Exception("psutil fail")):
            res = upd._resolve_wan_ip()
            self.assertIsNone(res)

        with mock.patch.dict("sys.modules", {"psutil": None}):
            res = upd._resolve_wan_ip()
            self.assertIsNone(res)

    async def test_chaos_middleware(self):
        mock_inner = mock.MagicMock(spec=UdpTransport)
        with mock.patch.dict(os.environ, {"WARM_LOGIC_CHAOS_LOSS": "1.0"}):
            chaos = ChaosMiddleware(mock_inner)
            chaos.sendto(b"data", ("1.1.1.1", 80))
            mock_inner.sendto.assert_not_called()

        with mock.patch.dict(os.environ, {"WARM_LOGIC_CHAOS_LATENCY": "100"}):
            chaos = ChaosMiddleware(mock_inner)
            mock_loop = mock.MagicMock()
            with mock.patch("asyncio.get_running_loop", return_value=mock_loop):
                chaos.sendto(b"data", ("1.1.1.1", 80))
                mock_loop.call_later.assert_called()

        await chaos.start_server("0.0.0.0", 0, lambda d, a: None)
        mock_inner.start_server.assert_called()
        chaos.close()
        mock_inner.close.assert_called()
        chaos.get_port()
        mock_inner.get_port.assert_called()

    def test_encrypted_transport_edge(self):
        mock_inner = mock.MagicMock(spec=UdpTransport)
        with mock.patch(
            "warm_logic_rs.RustZKProofGenerator", side_effect=Exception("fail")
        ):
            enc = EncryptedTransport(mock_inner)

        enc = EncryptedTransport(mock_inner)
        self.assertTrue(enc._verify_packet_integrity(b'{"key":"val"}'))
        self.assertFalse(enc._verify_packet_integrity(b""))
        self.assertFalse(enc._verify_packet_integrity(b"not json"))

        enc.sendto(b"data", ("1.1.1.1", 80))
        mock_inner.sendto.assert_called()

    async def test_encrypted_transport_server(self):
        mock_inner = mock.AsyncMock(spec=UdpTransport)
        enc = EncryptedTransport(mock_inner)
        handler_called = False

        def my_handler(d, a):
            nonlocal handler_called
            handler_called = True

        await enc.start_server("0.0.0.0", 0, my_handler)
        args, kwargs = mock_inner.start_server.call_args
        secure_handler = args[2]
        await secure_handler(b'{"type":"PING"}', ("1.1.1.1", 80))
        self.assertTrue(handler_called)

    def test_encrypted_transport_delegation(self):
        mock_inner = mock.MagicMock(spec=UdpTransport)
        enc = EncryptedTransport(mock_inner)
        enc.close()
        mock_inner.close.assert_called()
        enc.get_port()
        mock_inner.get_port.assert_called()

        # Line 266-267: Exception in _verify_packet_integrity
        # We don't patch the method, we trigger the try/except block inside it.
        # But wait, it's: try: return len(data) > 0 ... except: return False
        # So we just pass something that triggers an exception in 'startswith' or 'len'.
        # Actually len(None) will trigger TypeError.
        self.assertFalse(enc._verify_packet_integrity(None))

    def test_quic_stubs(self):
        with (
            mock.patch("warm_logic.kernel.mesh.transport.AIOQUIC_AVAILABLE", True),
            mock.patch(
                "warm_logic.kernel.mesh.transport.QuicConfiguration"
            ) as mock_conf,
        ):
            qt = QuicTransport()
            self.assertEqual(qt.get_port(), 0)
            asyncio.run(qt.start_server("127.0.0.1", 0, lambda d, a: None))
            qt.sendto(b"d", ("1.1.1.1", 80))
            qt.close()

            self.assertIsInstance(create_transport("QUIC"), QuicTransport)
            self.assertIsInstance(create_transport("AUTO"), QuicTransport)

    def test_udp_wan_resolve_candidates(self):
        upd = UdpTransport()
        with mock.patch("psutil.net_if_addrs") as mock_if:
            addr = mock.MagicMock()
            addr.family = 2
            addr.address = "1.2.3.4"
            mock_if.return_value = {"eth0": [addr]}
            res = upd._resolve_wan_ip()
            self.assertEqual(res, "1.2.3.4")

    def test_udp_get_port_zero(self):
        upd = UdpTransport()
        self.assertEqual(upd.get_port(), 0)

    def test_create_transport_perm(self):
        with mock.patch.dict(os.environ, {"WARM_LOGIC_CHAOS_LATENCY": "100"}):
            self.assertIsInstance(create_transport("UDP"), ChaosMiddleware)
        with mock.patch("warm_logic.kernel.mesh.transport.AIOQUIC_AVAILABLE", False):
            with self.assertRaises(ImportError):
                create_transport("QUIC")


if __name__ == "__main__":
    unittest.main()
