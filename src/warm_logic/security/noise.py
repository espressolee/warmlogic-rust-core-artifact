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
[Phase B2] Noise Protocol Implementation.
Provides encrypted communication channels using the Noise_XX pattern.
Primitives: X25519, ChaCha20Poly1305, SHA256.
"""

import logging
from enum import Enum
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger("SovereignNoise")


class HandshakeState(Enum):
    INITIATOR_START = 1
    EXPECT_RESPONDER_HELLO = 2
    RESPONDER_PART1 = 3
    INITIATOR_FINISH = 4
    ESTABLISHED = 5


class NoiseChannel:
    """
    Implements Noise_XX_25519_ChaChaPoly_SHA256.

    Handshake Pattern XX:
      -> e
      <- e, ee, s, es
      -> s, se
    """

    PROTOCOL_NAME = b"Noise_XX_25519_ChaChaPoly_SHA256"

    def __init__(self, s_key: Optional[x25519.X25519PrivateKey] = None) -> None:
        """Initialize Noise channel with optional static key (Noise 's' key)."""
        if s_key is None:
            self.static_key: x25519.X25519PrivateKey = (
                x25519.X25519PrivateKey.generate()
            )
        else:
            self.static_key = s_key

        self.static_pub = self.static_key.public_key()
        self.remote_static_pub: Optional[x25519.X25519PublicKey] = None

        self.ephemeral_key: Optional[x25519.X25519PrivateKey] = None
        self.remote_ephemeral_pub: Optional[x25519.X25519PublicKey] = None

        self.handshake_hash = self._init_hash()
        self.chaining_key = self._init_chain()
        self.encryptor = None
        self.decryptor = None
        self.state = HandshakeState.INITIATOR_START

    def _init_hash(self) -> bytes:
        """Initialize handshake hash h."""
        h = self.PROTOCOL_NAME
        if len(h) < 32:
            h = h + b"\0" * (32 - len(h))
        return h

    def _init_chain(self) -> bytes:
        """Initialize chaining key ck."""
        return self.PROTOCOL_NAME

    def _mix_hash(self, data: bytes) -> None:
        """h = SHA256(h || data)"""
        digest = hashes.Hash(hashes.SHA256())
        digest.update(self.handshake_hash + data)
        self.handshake_hash = digest.finalize()

    def _mix_key(self, input_key_material: bytes) -> bytes:
        """Derives new chaining key and cipher key."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=64,
            salt=None,
            info=b"",
        )
        output = hkdf.derive(self.chaining_key + input_key_material)
        self.chaining_key = output[:32]
        return output[32:]

    def _encrypt_and_hash(
        self, plaintext: bytes, key: bytes, nonce: Optional[bytes] = None
    ) -> bytes:
        """Encrypts data and update hash."""
        actual_nonce = nonce if nonce is not None else b"\0" * 12
        aad = self.handshake_hash
        chacha = ChaCha20Poly1305(key)
        ciphertext = chacha.encrypt(actual_nonce, plaintext, aad)
        self._mix_hash(ciphertext)
        return ciphertext

    def _decrypt_and_hash(
        self, ciphertext: bytes, key: bytes, nonce: Optional[bytes] = None
    ) -> bytes:
        """Decrypts data and update hash."""
        actual_nonce = nonce if nonce is not None else b"\0" * 12
        aad = self.handshake_hash
        chacha = ChaCha20Poly1305(key)
        plaintext = chacha.decrypt(actual_nonce, ciphertext, aad)
        self._mix_hash(ciphertext)
        return plaintext

    def initiator_start(self) -> bytes:
        """
        Stage 1: -> e
        """
        self.state = HandshakeState.EXPECT_RESPONDER_HELLO
        self.ephemeral_key = x25519.X25519PrivateKey.generate()
        pub_bytes = self.ephemeral_key.public_key().public_bytes(
            encoding=data_encoding(), format=data_format()
        )
        self._mix_hash(pub_bytes)
        # Payload is empty for start
        return pub_bytes

    def responder_part1(self, message: bytes) -> bytes:
        """
        Stage 1 (recv): -> e
        Stage 2 (send): <- e, ee, s, es
        """
        # Read e
        re_bytes = message[:32]
        self.remote_ephemeral_pub = x25519.X25519PublicKey.from_public_bytes(re_bytes)
        self._mix_hash(re_bytes)

        # Generate e
        self.ephemeral_key = x25519.X25519PrivateKey.generate()
        pub_bytes = self.ephemeral_key.public_key().public_bytes(
            encoding=data_encoding(), format=data_format()
        )
        self._mix_hash(pub_bytes)

        # DH(e, re) -> ee
        shared_secret = self.ephemeral_key.exchange(self.remote_ephemeral_pub)
        temp_k = self._mix_key(shared_secret)

        # Encrypt static key s
        my_static_bytes = self.static_pub.public_bytes(
            encoding=data_encoding(), format=data_format()
        )
        encrypted_s = self._encrypt_and_hash(my_static_bytes, temp_k)

        # DH(s, re) -> es
        shared_secret_2 = self.static_key.exchange(self.remote_ephemeral_pub)
        temp_k_2 = self._mix_key(shared_secret_2)

        # Encrypt payload (empty)
        encrypted_payload = self._encrypt_and_hash(b"", temp_k_2)

        self.state = HandshakeState.ESTABLISHED
        return pub_bytes + encrypted_s + encrypted_payload

    def initiator_finish(self, message: bytes) -> bytes:
        """
        Stage 2 (recv): <- e, ee, s, es
        Stage 3 (send): -> s, se
        """
        re_bytes = message[:32]
        self.remote_ephemeral_pub = x25519.X25519PublicKey.from_public_bytes(re_bytes)
        self._mix_hash(re_bytes)

        # DH(e, re) -> ee
        if self.ephemeral_key is None:
            raise RuntimeError("Ephemeral key not initialized")
        shared_secret = self.ephemeral_key.exchange(self.remote_ephemeral_pub)
        temp_k = self._mix_key(shared_secret)

        # Read encrypted s
        encrypted_s = message[32 : 32 + 48]  # 32 key + 16 poly1305
        rs_bytes = self._decrypt_and_hash(encrypted_s, temp_k)
        self.remote_static_pub = x25519.X25519PublicKey.from_public_bytes(rs_bytes)

        # DH(e, rs) -> es
        shared_secret_2 = self.ephemeral_key.exchange(self.remote_static_pub)
        temp_k_2 = self._mix_key(shared_secret_2)

        # Read payload (decrypted with k from es)
        encrypted_payload = message[32 + 48 :]
        self._decrypt_and_hash(encrypted_payload, temp_k_2)

        # Stage 3: -> s, se

        # 1. Encrypt static key s
        # Note: In strict Noise, we reuse the current cipher state (k from es).
        # Nonce increments. Since payload above used nonce 0 (implicit), we use nonce 1.
        my_static_bytes = self.static_pub.public_bytes(
            encoding=data_encoding(), format=data_format()
        )
        nonce_1 = b"\0" * 11 + b"\x01"
        encrypted_s_final = self._encrypt_and_hash(
            my_static_bytes, temp_k_2, nonce=nonce_1
        )

        # 2. DH(s, re) -> se
        shared_secret_3 = self.static_key.exchange(self.remote_ephemeral_pub)
        temp_k_3 = self._mix_key(shared_secret_3)

        # 3. Encrypt payload (empty) with new k (nonce 0)
        encrypted_payload_final = self._encrypt_and_hash(b"", temp_k_3)

        self.state = HandshakeState.ESTABLISHED
        # Store Split Keys for transport if we were doing full transport...

        return encrypted_s_final + encrypted_payload_final


def data_encoding() -> "serialization.Encoding":
    from cryptography.hazmat.primitives import serialization

    return serialization.Encoding.Raw


def data_format() -> "serialization.PublicFormat":
    from cryptography.hazmat.primitives import serialization

    return serialization.PublicFormat.Raw
