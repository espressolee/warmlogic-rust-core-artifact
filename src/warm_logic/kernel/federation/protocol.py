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
Federation Protocol Messages

Defines the binary protocol for secure communication between
sovereign federation nodes using PQC-protected channels.
"""

import hashlib
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum

# Protocol version
PROTOCOL_VERSION = 0x0100  # v1.0

# Magic bytes for packet identification
MAGIC_BYTES = b"WLFED"  # WarmLogic Federation


class MessageType(IntEnum):
    """Federation message types."""

    # Handshake
    HELLO = 0x01
    HELLO_ACK = 0x02
    KEY_EXCHANGE = 0x03
    KEY_EXCHANGE_ACK = 0x04

    # Heartbeat
    PING = 0x10
    PONG = 0x11

    # Attestation
    ATTESTATION_REQUEST = 0x20
    ATTESTATION_RESPONSE = 0x21

    # Consensus
    PROPOSAL = 0x30
    VOTE = 0x31
    VOTE_ACK = 0x32
    COMMIT = 0x33
    FINALIZE = 0x34

    # State sync
    STATE_REQUEST = 0x40
    STATE_RESPONSE = 0x41
    STATE_DELTA = 0x42

    # Error
    ERROR = 0xFF


class ErrorCode(IntEnum):
    """Protocol error codes."""

    NONE = 0x00
    INVALID_MAGIC = 0x01
    INVALID_VERSION = 0x02
    INVALID_SIGNATURE = 0x03
    INVALID_NODE_ID = 0x04
    ATTESTATION_FAILED = 0x05
    TIMEOUT = 0x06
    CONSENSUS_FAILED = 0x07
    KEY_EXCHANGE_FAILED = 0x08
    CHANNEL_EXPIRED = 0x09
    UNKNOWN = 0xFF


@dataclass
class ProtocolHeader:
    """
    Federation Protocol Header (24 bytes)

    Layout:
    - magic: 5 bytes ("WLFED")
    - version: 2 bytes (big-endian)
    - msg_type: 1 byte
    - flags: 1 byte
    - reserved: 3 bytes
    - payload_len: 4 bytes (big-endian)
    - timestamp: 8 bytes (big-endian, microseconds since epoch)
    """

    version: int = PROTOCOL_VERSION
    msg_type: MessageType = MessageType.PING
    flags: int = 0
    payload_len: int = 0
    timestamp: int = 0

    HEADER_SIZE = 24
    FORMAT = ">5sHBBxxxIQ"  # Big-endian

    def __post_init__(self) -> None:
        if self.timestamp == 0:
            self.timestamp = int(time.time() * 1_000_000)

    def pack(self) -> bytes:
        """Serialize header to bytes."""
        return struct.pack(
            self.FORMAT,
            MAGIC_BYTES,
            self.version,
            self.msg_type,
            self.flags,
            self.payload_len,
            self.timestamp,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "ProtocolHeader":
        """Deserialize header from bytes."""
        if len(data) < cls.HEADER_SIZE:
            raise ValueError(f"Header too short: {len(data)} < {cls.HEADER_SIZE}")

        magic, version, msg_type, flags, payload_len, timestamp = struct.unpack(
            cls.FORMAT, data[: cls.HEADER_SIZE]
        )

        if magic != MAGIC_BYTES:
            raise ValueError(f"Invalid magic bytes: {magic}")

        return cls(
            version=version,
            msg_type=MessageType(msg_type),
            flags=flags,
            payload_len=payload_len,
            timestamp=timestamp,
        )


@dataclass
class FederationMessage:
    """
    Complete federation message with header, payload, and signature.

    Structure:
    - header: 24 bytes (ProtocolHeader)
    - sender_id: 32 bytes (node ID hash)
    - payload: variable length
    - signature: 64 bytes (ML-DSA signature, truncated)
    """

    header: ProtocolHeader
    sender_id: bytes  # 32 bytes
    payload: bytes
    signature: bytes = b""  # 64 bytes when signed

    SENDER_ID_SIZE = 32
    SIGNATURE_SIZE = 64

    def compute_hash(self) -> bytes:
        """Compute SHA3-256 hash of header + sender_id + payload."""
        h = hashlib.sha3_256()
        h.update(self.header.pack())
        h.update(self.sender_id)
        h.update(self.payload)
        return h.digest()

    def pack(self) -> bytes:
        """Serialize complete message to bytes."""
        header_bytes = self.header.pack()
        return header_bytes + self.sender_id + self.payload + self.signature

    @classmethod
    def unpack(cls, data: bytes) -> "FederationMessage":
        """Deserialize message from bytes."""
        header = ProtocolHeader.unpack(data)
        offset = ProtocolHeader.HEADER_SIZE

        sender_id = data[offset : offset + cls.SENDER_ID_SIZE]
        offset += cls.SENDER_ID_SIZE

        payload = data[offset : offset + header.payload_len]
        offset += header.payload_len

        signature = data[offset : offset + cls.SIGNATURE_SIZE]

        return cls(
            header=header,
            sender_id=sender_id,
            payload=payload,
            signature=signature,
        )

    def total_size(self) -> int:
        """Calculate total message size."""
        return (
            ProtocolHeader.HEADER_SIZE
            + self.SENDER_ID_SIZE
            + len(self.payload)
            + self.SIGNATURE_SIZE
        )


# --- Payload Structures ---


@dataclass
class HelloPayload:
    """HELLO message payload for initial handshake."""

    node_id: str
    encapsulation_key: str  # ML-KEM public key (hex)
    signing_key: str  # ML-DSA public key (hex)
    capabilities: int = 0xFFFF  # Bitmap of supported features

    def pack(self) -> bytes:
        """Serialize payload."""
        node_id_bytes = self.node_id.encode("utf-8")
        ek_bytes = bytes.fromhex(self.encapsulation_key)
        sk_bytes = bytes.fromhex(self.signing_key)

        return struct.pack(
            f">H{len(node_id_bytes)}sH{len(ek_bytes)}sH{len(sk_bytes)}sH",
            len(node_id_bytes),
            node_id_bytes,
            len(ek_bytes),
            ek_bytes,
            len(sk_bytes),
            sk_bytes,
            self.capabilities,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "HelloPayload":
        """Deserialize payload."""
        offset = 0

        node_id_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        node_id = data[offset : offset + node_id_len].decode("utf-8")
        offset += node_id_len

        ek_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        ek = data[offset : offset + ek_len].hex()
        offset += ek_len

        sk_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        sk = data[offset : offset + sk_len].hex()
        offset += sk_len

        capabilities = struct.unpack_from(">H", data, offset)[0]

        return cls(
            node_id=node_id,
            encapsulation_key=ek,
            signing_key=sk,
            capabilities=capabilities,
        )


@dataclass
class KeyExchangePayload:
    """KEY_EXCHANGE payload with ML-KEM ciphertext."""

    ciphertext: str  # ML-KEM ciphertext (hex)
    session_id: bytes = field(default_factory=lambda: b"\x00" * 16)

    def pack(self) -> bytes:
        ct_bytes = bytes.fromhex(self.ciphertext)
        return struct.pack(
            f">16sH{len(ct_bytes)}s", self.session_id, len(ct_bytes), ct_bytes
        )

    @classmethod
    def unpack(cls, data: bytes) -> "KeyExchangePayload":
        session_id = data[:16]
        ct_len = struct.unpack_from(">H", data, 16)[0]
        ciphertext = data[18 : 18 + ct_len].hex()
        return cls(ciphertext=ciphertext, session_id=session_id)


@dataclass
class ProposalPayload:
    """PROPOSAL payload for consensus."""

    decision_id: str
    decision_hash: str
    epoch: int
    proposal_data: bytes

    def pack(self) -> bytes:
        id_bytes = self.decision_id.encode("utf-8")
        hash_bytes = bytes.fromhex(self.decision_hash)
        return struct.pack(
            f">H{len(id_bytes)}s32sQI{len(self.proposal_data)}s",
            len(id_bytes),
            id_bytes,
            hash_bytes,
            self.epoch,
            len(self.proposal_data),
            self.proposal_data,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "ProposalPayload":
        offset = 0
        id_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        decision_id = data[offset : offset + id_len].decode("utf-8")
        offset += id_len

        decision_hash = data[offset : offset + 32].hex()
        offset += 32

        epoch = struct.unpack_from(">Q", data, offset)[0]
        offset += 8

        data_len = struct.unpack_from(">I", data, offset)[0]
        offset += 4
        proposal_data = data[offset : offset + data_len]

        return cls(
            decision_id=decision_id,
            decision_hash=decision_hash,
            epoch=epoch,
            proposal_data=proposal_data,
        )


@dataclass
class VotePayload:
    """VOTE payload for consensus voting."""

    decision_id: str
    approve: bool
    signature: str  # ML-DSA signature of decision_hash

    def pack(self) -> bytes:
        id_bytes = self.decision_id.encode("utf-8")
        sig_bytes = bytes.fromhex(self.signature)
        return struct.pack(
            f">H{len(id_bytes)}s?H{len(sig_bytes)}s",
            len(id_bytes),
            id_bytes,
            self.approve,
            len(sig_bytes),
            sig_bytes,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "VotePayload":
        offset = 0
        id_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        decision_id = data[offset : offset + id_len].decode("utf-8")
        offset += id_len

        approve = struct.unpack_from(">?", data, offset)[0]
        offset += 1

        sig_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        signature = data[offset : offset + sig_len].hex()

        return cls(decision_id=decision_id, approve=approve, signature=signature)


@dataclass
class ErrorPayload:
    """ERROR payload with error details."""

    code: ErrorCode
    message: str

    def pack(self) -> bytes:
        msg_bytes = self.message.encode("utf-8")
        return struct.pack(
            f">BH{len(msg_bytes)}s", self.code, len(msg_bytes), msg_bytes
        )

    @classmethod
    def unpack(cls, data: bytes) -> "ErrorPayload":
        code = ErrorCode(data[0])
        msg_len = struct.unpack_from(">H", data, 1)[0]
        message = data[3 : 3 + msg_len].decode("utf-8")
        return cls(code=code, message=message)


# --- Message Builder ---


class MessageBuilder:
    """Helper class for building federation messages."""

    def __init__(self, node_id: str, signing_key: str = ""):
        self.node_id = node_id
        self.signing_key = signing_key
        self._sender_id = hashlib.sha3_256(node_id.encode()).digest()

    def build(
        self,
        msg_type: MessageType,
        payload: bytes,
        sign: bool = True,
    ) -> FederationMessage:
        """Build a federation message."""
        header = ProtocolHeader(
            msg_type=msg_type,
            payload_len=len(payload),
        )

        msg = FederationMessage(
            header=header,
            sender_id=self._sender_id,
            payload=payload,
        )

        if sign and self.signing_key:
            # Sign the message hash
            from warm_logic.kernel import rust_loader

            if rust_loader.HAS_RUST_CORE:
                rs = rust_loader.load_rust_core()
                msg_hash = msg.compute_hash().hex()
                signature = rs.sign(self.signing_key, msg_hash)
                # Truncate to 64 bytes for protocol
                sig_bytes = bytes.fromhex(signature)[:64]
                msg.signature = sig_bytes.ljust(64, b"\x00")

        return msg

    def build_hello(
        self, encapsulation_key: str, signing_key: str, capabilities: int = 0xFFFF
    ) -> FederationMessage:
        """Build a HELLO message."""
        payload = HelloPayload(
            node_id=self.node_id,
            encapsulation_key=encapsulation_key,
            signing_key=signing_key,
            capabilities=capabilities,
        )
        return self.build(MessageType.HELLO, payload.pack())

    def build_key_exchange(
        self, ciphertext: str, session_id: bytes
    ) -> FederationMessage:
        """Build a KEY_EXCHANGE message."""
        payload = KeyExchangePayload(ciphertext=ciphertext, session_id=session_id)
        return self.build(MessageType.KEY_EXCHANGE, payload.pack())

    def build_proposal(
        self, decision_id: str, decision_hash: str, epoch: int, data: bytes
    ) -> FederationMessage:
        """Build a PROPOSAL message."""
        payload = ProposalPayload(
            decision_id=decision_id,
            decision_hash=decision_hash,
            epoch=epoch,
            proposal_data=data,
        )
        return self.build(MessageType.PROPOSAL, payload.pack())

    def build_vote(
        self, decision_id: str, approve: bool, signature: str
    ) -> FederationMessage:
        """Build a VOTE message."""
        payload = VotePayload(
            decision_id=decision_id,
            approve=approve,
            signature=signature,
        )
        return self.build(MessageType.VOTE, payload.pack())

    def build_ping(self) -> FederationMessage:
        """Build a PING message."""
        return self.build(MessageType.PING, b"", sign=False)

    def build_pong(self, ping_timestamp: int) -> FederationMessage:
        """Build a PONG message."""
        payload = struct.pack(">Q", ping_timestamp)
        return self.build(MessageType.PONG, payload, sign=False)

    def build_error(self, code: ErrorCode, message: str) -> FederationMessage:
        """Build an ERROR message."""
        payload = ErrorPayload(code=code, message=message)
        return self.build(MessageType.ERROR, payload.pack(), sign=False)
