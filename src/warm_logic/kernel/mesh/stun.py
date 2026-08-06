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
"""
[Phase B1: Network ] STUN Client for NAT Traversal.
Discovers the public IP and port for P2P mesh communication.
"""

import asyncio
import logging
import struct
from typing import Optional, Tuple

logger = logging.getLogger("STUNClient")

# STUN message types (RFC 5389)
STUN_BINDING_REQUEST = 0x0001
STUN_BINDING_RESPONSE = 0x0101

# STUN attributes
STUN_ATTR_MAPPED_ADDRESS = 0x0001
STUN_ATTR_XOR_MAPPED_ADDRESS = 0x0020

# Magic cookie (RFC 5389)
STUN_MAGIC_COOKIE = 0x2112A442

# Public STUN servers (fallback list)
PUBLIC_STUN_SERVERS = [
    ("stun.l.google.com", 19302),
    ("stun1.l.google.com", 19302),
    ("stun.cloudflare.com", 3478),
    ("stun.stunprotocol.org", 3478),
]


class StunClient:
    """
    Minimal STUN client for discovering reflexive transport address.

    Usage:
        client = StunClient()
        public_ip, public_port = await client.discover()
    """

    def __init__(
        self,
        stun_servers: Optional[list] = None,
        timeout: float = 5.0,
    ):
        self.stun_servers = stun_servers or PUBLIC_STUN_SERVERS
        self.timeout = timeout

    def _build_binding_request(self, transaction_id: bytes) -> bytes:
        """Build a STUN Binding Request message."""
        # Message type (2 bytes) + length (2 bytes) + magic cookie (4 bytes) + transaction ID (12 bytes)
        msg_type = STUN_BINDING_REQUEST
        msg_length = 0  # No attributes in request
        header = (
            struct.pack(">HHI", msg_type, msg_length, STUN_MAGIC_COOKIE)
            + transaction_id
        )
        return header

    def _parse_binding_response(
        self, data: bytes, transaction_id: bytes
    ) -> Optional[Tuple[str, int]]:
        """Parse STUN Binding Response to extract XOR-MAPPED-ADDRESS."""
        if len(data) < 20:
            return None

        # Parse header
        msg_type, msg_length, magic = struct.unpack(">HHI", data[:8])
        recv_txn_id = data[8:20]

        if msg_type != STUN_BINDING_RESPONSE:
            logger.warning(f"Unexpected STUN message type: 0x{msg_type:04x}")
            return None

        if recv_txn_id != transaction_id:
            logger.warning("Transaction ID mismatch")
            return None

        # Parse attributes
        offset = 20
        while offset < len(data):
            if offset + 4 > len(data):
                break

            attr_type, attr_length = struct.unpack(">HH", data[offset : offset + 4])
            offset += 4

            if offset + attr_length > len(data):
                break

            attr_value = data[offset : offset + attr_length]

            if attr_type == STUN_ATTR_XOR_MAPPED_ADDRESS:
                return self._parse_xor_mapped_address(attr_value, transaction_id)
            elif attr_type == STUN_ATTR_MAPPED_ADDRESS:
                return self._parse_mapped_address(attr_value)

            # Align to 4-byte boundary
            offset += attr_length + (4 - attr_length % 4) % 4

        return None

    def _parse_xor_mapped_address(
        self, attr_value: bytes, transaction_id: bytes
    ) -> Optional[Tuple[str, int]]:
        """Parse XOR-MAPPED-ADDRESS attribute."""
        if len(attr_value) < 8:
            return None

        family = attr_value[1]
        xor_port = struct.unpack(">H", attr_value[2:4])[0]
        port = xor_port ^ (STUN_MAGIC_COOKIE >> 16)

        if family == 0x01:  # IPv4
            xor_ip = struct.unpack(">I", attr_value[4:8])[0]
            ip_int = xor_ip ^ STUN_MAGIC_COOKIE
            ip = ".".join(str((ip_int >> (24 - i * 8)) & 0xFF) for i in range(4))
            return (ip, port)

        # IPv6 not implemented yet
        return None

    def _parse_mapped_address(self, attr_value: bytes) -> Optional[Tuple[str, int]]:
        """Parse MAPPED-ADDRESS attribute (legacy fallback)."""
        if len(attr_value) < 8:
            return None

        family = attr_value[1]
        port = struct.unpack(">H", attr_value[2:4])[0]

        if family == 0x01:  # IPv4
            ip = ".".join(str(b) for b in attr_value[4:8])
            return (ip, port)

        return None

    async def discover(self, local_port: int = 0) -> Optional[Tuple[str, int]]:
        """
        Discover public IP and port using STUN.

        Args:
            local_port: Local port to bind (0 for random).

        Returns:
            Tuple of (public_ip, public_port) or None if discovery failed.
        """
        import os

        transaction_id = os.urandom(12)
        request = self._build_binding_request(transaction_id)

        for server_host, server_port in self.stun_servers:
            try:
                result = await self._query_server(
                    request, transaction_id, server_host, server_port, local_port
                )
                if result:
                    logger.info(
                        f"🌐 Discovered public address: {result[0]}:{result[1]}"
                    )
                    return result
            except Exception as e:
                logger.debug(f"STUN server {server_host}:{server_port} failed: {e}")
                continue

        logger.warning("NAT traversal failed: No STUN server responded")
        return None

    async def _query_server(
        self,
        request: bytes,
        transaction_id: bytes,
        server_host: str,
        server_port: int,
        local_port: int,
    ) -> Optional[Tuple[str, int]]:
        """Query a single STUN server."""
        loop = asyncio.get_running_loop()

        # Create UDP socket
        transport, protocol = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol, local_addr=("0.0.0.0", local_port)
        )

        try:
            # Resolve server address
            infos = await loop.getaddrinfo(
                server_host, server_port, type=2
            )  # SOCK_DGRAM
            if not infos:
                return None
            server_addr = infos[0][4]

            # Send request
            transport.sendto(request, server_addr)

            # Wait for response
            response_future = loop.create_future()

            class ResponseProtocol(asyncio.DatagramProtocol):
                def datagram_received(self, data, addr):
                    if not response_future.done():
                        response_future.set_result(data)

            # Replace protocol
            transport._protocol = ResponseProtocol()

            try:
                data = await asyncio.wait_for(response_future, timeout=self.timeout)
                return self._parse_binding_response(data, transaction_id)
            except asyncio.TimeoutError:
                return None

        finally:
            transport.close()


async def discover_public_address() -> Optional[Tuple[str, int]]:
    """Convenience function for NAT discovery."""
    client = StunClient()
    return await client.discover()
