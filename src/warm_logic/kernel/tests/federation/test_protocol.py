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
Federation Protocol Tests

Tests for the binary protocol used in federation communication.
"""

import time
import unittest

from warm_logic.kernel.federation.protocol import (
    ErrorCode,
    ErrorPayload,
    FederationMessage,
    HelloPayload,
    KeyExchangePayload,
    MessageBuilder,
    MessageType,
    ProposalPayload,
    ProtocolHeader,
    VotePayload,
    MAGIC_BYTES,
    PROTOCOL_VERSION,
)


class TestProtocolHeader(unittest.TestCase):
    """Test ProtocolHeader serialization."""

    def test_header_pack_unpack(self):
        header = ProtocolHeader(
            version=PROTOCOL_VERSION,
            msg_type=MessageType.HELLO,
            flags=0x01,
            payload_len=256,
        )

        packed = header.pack()
        self.assertEqual(len(packed), ProtocolHeader.HEADER_SIZE)

        unpacked = ProtocolHeader.unpack(packed)
        self.assertEqual(unpacked.version, header.version)
        self.assertEqual(unpacked.msg_type, header.msg_type)
        self.assertEqual(unpacked.flags, header.flags)
        self.assertEqual(unpacked.payload_len, header.payload_len)

    def test_header_magic_bytes(self):
        header = ProtocolHeader()
        packed = header.pack()
        self.assertTrue(packed.startswith(MAGIC_BYTES))

    def test_header_invalid_magic(self):
        bad_data = b"BADMG" + b"\x00" * 19
        with self.assertRaises(ValueError):
            ProtocolHeader.unpack(bad_data)

    def test_header_timestamp(self):
        before = int(time.time() * 1_000_000)
        header = ProtocolHeader()
        after = int(time.time() * 1_000_000)

        self.assertGreaterEqual(header.timestamp, before)
        self.assertLessEqual(header.timestamp, after)


class TestHelloPayload(unittest.TestCase):
    """Test HelloPayload serialization."""

    def test_hello_pack_unpack(self):
        hello = HelloPayload(
            node_id="wl-test-node-123",
            encapsulation_key="abcd" * 64,  # 256 bytes hex
            signing_key="1234" * 64,  # 256 bytes hex
            capabilities=0xFFFF,
        )

        packed = hello.pack()
        unpacked = HelloPayload.unpack(packed)

        self.assertEqual(unpacked.node_id, hello.node_id)
        self.assertEqual(unpacked.encapsulation_key, hello.encapsulation_key)
        self.assertEqual(unpacked.signing_key, hello.signing_key)
        self.assertEqual(unpacked.capabilities, hello.capabilities)


class TestKeyExchangePayload(unittest.TestCase):
    """Test KeyExchangePayload serialization."""

    def test_key_exchange_pack_unpack(self):
        ke = KeyExchangePayload(
            ciphertext="deadbeef" * 32,  # 128 bytes hex
            session_id=b"\x01" * 16,
        )

        packed = ke.pack()
        unpacked = KeyExchangePayload.unpack(packed)

        self.assertEqual(unpacked.ciphertext, ke.ciphertext)
        self.assertEqual(unpacked.session_id, ke.session_id)


class TestProposalPayload(unittest.TestCase):
    """Test ProposalPayload serialization."""

    def test_proposal_pack_unpack(self):
        proposal = ProposalPayload(
            decision_id="fd-12345678",
            decision_hash="a" * 64,  # 32 bytes hex
            epoch=1000,
            proposal_data=b'{"action": "upgrade"}',
        )

        packed = proposal.pack()
        unpacked = ProposalPayload.unpack(packed)

        self.assertEqual(unpacked.decision_id, proposal.decision_id)
        self.assertEqual(unpacked.decision_hash, proposal.decision_hash)
        self.assertEqual(unpacked.epoch, proposal.epoch)
        self.assertEqual(unpacked.proposal_data, proposal.proposal_data)


class TestVotePayload(unittest.TestCase):
    """Test VotePayload serialization."""

    def test_vote_pack_unpack(self):
        vote = VotePayload(
            decision_id="fd-12345678",
            approve=True,
            signature="b" * 128,  # 64 bytes hex
        )

        packed = vote.pack()
        unpacked = VotePayload.unpack(packed)

        self.assertEqual(unpacked.decision_id, vote.decision_id)
        self.assertEqual(unpacked.approve, vote.approve)
        self.assertEqual(unpacked.signature, vote.signature)

    def test_vote_reject(self):
        vote = VotePayload(
            decision_id="fd-reject",
            approve=False,
            signature="c" * 128,
        )

        packed = vote.pack()
        unpacked = VotePayload.unpack(packed)

        self.assertFalse(unpacked.approve)


class TestErrorPayload(unittest.TestCase):
    """Test ErrorPayload serialization."""

    def test_error_pack_unpack(self):
        error = ErrorPayload(
            code=ErrorCode.ATTESTATION_FAILED,
            message="Hardware attestation verification failed",
        )

        packed = error.pack()
        unpacked = ErrorPayload.unpack(packed)

        self.assertEqual(unpacked.code, error.code)
        self.assertEqual(unpacked.message, error.message)


class TestFederationMessage(unittest.TestCase):
    """Test complete FederationMessage."""

    def test_message_pack_unpack(self):
        header = ProtocolHeader(
            msg_type=MessageType.PING,
            payload_len=4,
        )

        msg = FederationMessage(
            header=header,
            sender_id=b"\x00" * 32,
            payload=b"test",
            signature=b"\xff" * 64,
        )

        packed = msg.pack()
        unpacked = FederationMessage.unpack(packed)

        self.assertEqual(unpacked.header.msg_type, msg.header.msg_type)
        self.assertEqual(unpacked.sender_id, msg.sender_id)
        self.assertEqual(unpacked.payload, msg.payload)
        self.assertEqual(unpacked.signature, msg.signature)

    def test_message_hash(self):
        msg = FederationMessage(
            header=ProtocolHeader(msg_type=MessageType.PING, payload_len=4),
            sender_id=b"\x01" * 32,
            payload=b"data",
        )

        hash1 = msg.compute_hash()
        hash2 = msg.compute_hash()

        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 32)  # SHA3-256

    def test_message_total_size(self):
        msg = FederationMessage(
            header=ProtocolHeader(msg_type=MessageType.PING, payload_len=10),
            sender_id=b"\x00" * 32,
            payload=b"0123456789",
            signature=b"\x00" * 64,
        )

        expected_size = (
            ProtocolHeader.HEADER_SIZE  # 24
            + FederationMessage.SENDER_ID_SIZE  # 32
            + 10  # payload
            + FederationMessage.SIGNATURE_SIZE  # 64
        )
        self.assertEqual(msg.total_size(), expected_size)


class TestMessageBuilder(unittest.TestCase):
    """Test MessageBuilder helper."""

    def test_build_ping(self):
        builder = MessageBuilder("test-node")
        msg = builder.build_ping()

        self.assertEqual(msg.header.msg_type, MessageType.PING)
        self.assertEqual(len(msg.sender_id), 32)

    def test_build_pong(self):
        builder = MessageBuilder("test-node")
        ping_timestamp = int(time.time() * 1_000_000)
        msg = builder.build_pong(ping_timestamp)

        self.assertEqual(msg.header.msg_type, MessageType.PONG)

    def test_build_error(self):
        builder = MessageBuilder("test-node")
        msg = builder.build_error(ErrorCode.TIMEOUT, "Connection timed out")

        self.assertEqual(msg.header.msg_type, MessageType.ERROR)

        # Verify payload
        payload = ErrorPayload.unpack(msg.payload)
        self.assertEqual(payload.code, ErrorCode.TIMEOUT)
        self.assertEqual(payload.message, "Connection timed out")

    def test_build_hello(self):
        builder = MessageBuilder("test-node")
        msg = builder.build_hello(
            encapsulation_key="a" * 64,
            signing_key="b" * 64,
            capabilities=0x0F0F,
        )

        self.assertEqual(msg.header.msg_type, MessageType.HELLO)

        # Verify payload
        payload = HelloPayload.unpack(msg.payload)
        self.assertEqual(payload.node_id, "test-node")
        self.assertEqual(payload.capabilities, 0x0F0F)


class TestMessageTypes(unittest.TestCase):
    """Test message type enumeration."""

    def test_handshake_types(self):
        self.assertEqual(MessageType.HELLO, 0x01)
        self.assertEqual(MessageType.HELLO_ACK, 0x02)
        self.assertEqual(MessageType.KEY_EXCHANGE, 0x03)
        self.assertEqual(MessageType.KEY_EXCHANGE_ACK, 0x04)

    def test_heartbeat_types(self):
        self.assertEqual(MessageType.PING, 0x10)
        self.assertEqual(MessageType.PONG, 0x11)

    def test_consensus_types(self):
        self.assertEqual(MessageType.PROPOSAL, 0x30)
        self.assertEqual(MessageType.VOTE, 0x31)
        self.assertEqual(MessageType.COMMIT, 0x33)
        self.assertEqual(MessageType.FINALIZE, 0x34)


if __name__ == "__main__":
    unittest.main()
