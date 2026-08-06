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
import struct
import unittest
from unittest import mock

from warm_logic.kernel.mesh.stun import StunClient, discover_public_address


class TestStunSaturation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = StunClient(timeout=0.1)

    def test_build_binding_request(self):
        txn_id = b"123456789012"
        req = self.client._build_binding_request(txn_id)
        self.assertEqual(len(req), 20)
        self.assertEqual(req[8:20], txn_id)

    def test_parse_binding_response_errors(self):
        txn_id = b"123456789012"
        # Too short
        self.assertIsNone(self.client._parse_binding_response(b"\x00" * 19, txn_id))

        # Wrong type
        header = struct.pack(">HHI", 0x0111, 0, 0x2112A442) + txn_id
        self.assertIsNone(self.client._parse_binding_response(header, txn_id))

        # Txn ID mismatch
        header = struct.pack(">HHI", 0x0101, 0, 0x2112A442) + b"wrongtxnxxxx"
        self.assertIsNone(self.client._parse_binding_response(header, txn_id))

    def test_parse_attributes_edge(self):
        txn_id = b"123456789012"
        # Partial attribute header
        header = struct.pack(">HHI", 0x0101, 2, 0x2112A442) + txn_id + b"\x00\x01"
        self.assertIsNone(self.client._parse_binding_response(header, txn_id))

        # Attribute length overflow
        header = (
            struct.pack(">HHI", 0x0101, 4, 0x2112A442)
            + txn_id
            + struct.pack(">HH", 0x0001, 10)
        )
        self.assertIsNone(self.client._parse_binding_response(header, txn_id))

    def test_parse_xor_mapped_address_v4(self):
        txn_id = b"123456789012"
        # XORed 1.2.3.4 (hex 01020304) with magic 2112A442 -> 2010A746
        # Port 1234 (hex 04D2) XOR with magic high half 2112 -> 25C0
        attr_value = b"\x00\x01\x25\xc0\x20\x10\xa7\x46"
        res = self.client._parse_xor_mapped_address(attr_value, txn_id)
        self.assertEqual(res, ("1.2.3.4", 1234))

        # Too short
        self.assertIsNone(self.client._parse_xor_mapped_address(b"\x00" * 7, txn_id))
        # Wrong family
        self.assertIsNone(
            self.client._parse_xor_mapped_address(
                b"\x00\x02\x00\x00\x00\x00\x00\x00", txn_id
            )
        )

    def test_parse_mapped_address(self):
        # 1.2.3.4, Port 1234
        attr_value = b"\x00\x01\x04\xd2\x01\x02\x03\x04"
        res = self.client._parse_mapped_address(attr_value)
        self.assertEqual(res, ("1.2.3.4", 1234))

        # Too short
        self.assertIsNone(self.client._parse_mapped_address(b"\x00" * 7))
        # Non-ipv4
        self.assertIsNone(
            self.client._parse_mapped_address(b"\x00\x02\x00\x00\x00\x00\x00\x00")
        )

    async def test_discover_full(self):
        # Mocking transport and protocol
        txn_id = b"123456789012"
        with mock.patch("asyncio.get_running_loop") as mock_loop:
            mock_transport = mock.MagicMock()
            mock_loop.return_value.create_datagram_endpoint = mock.AsyncMock(
                return_value=(mock_transport, None)
            )
            mock_loop.return_value.getaddrinfo = mock.AsyncMock(
                return_value=[(None, None, None, None, ("1.1.1.1", 3478))]
            )

            # Case 1.5: Success (Legacy Mapped + Padding/Alignment)
            with mock.patch("os.urandom", return_value=txn_id):
                # Unknown attribute (0x9999), length 3 (needs 1 byte padding)
                attr1 = struct.pack(">HH", 0x9999, 3) + b"123" + b"\x00"
                # Followed by valid MAPPED-ADDRESS
                attr2 = (
                    struct.pack(">HH", 0x0001, 8) + b"\x00\x01\x04\xd2\x01\x02\x03\x04"
                )
                attr = attr1 + attr2
                resp = (
                    struct.pack(">HHI", 0x0101, len(attr), 0x2112A442) + txn_id + attr
                )
                with mock.patch("asyncio.wait_for", return_value=resp):
                    res = await self.client.discover()
                    self.assertEqual(res, ("1.2.3.4", 1234))

            # Case 2: Timeout
            with mock.patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                res = await self.client.discover()
                self.assertIsNone(res)

            # Case 3: Empty getaddrinfo
            mock_loop.return_value.getaddrinfo.return_value = []
            res = await self.client.discover()
            self.assertIsNone(res)

    async def test_discover_public_address_helper(self):
        with mock.patch.object(StunClient, "discover", return_value=("8.8.8.8", 1234)):
            res = await discover_public_address()
            self.assertEqual(res, ("8.8.8.8", 1234))


if __name__ == "__main__":
    unittest.main()
