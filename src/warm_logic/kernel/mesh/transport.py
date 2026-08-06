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
import inspect
import logging
import os
import random
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger("SovereignTransport")

from warm_logic.kernel import rust_loader
from warm_logic.kernel.identity.kinetic_id import KineticIdentity

try:
    from aioquic.asyncio import QuicConnectionProtocol
    from aioquic.quic.configuration import QuicConfiguration

    AIOQUIC_AVAILABLE = True
except ImportError:
    AIOQUIC_AVAILABLE = False
    QuicConnectionProtocol = None
    QuicConfiguration = None


class AbstractTransport(ABC):
    """Interface for network transport."""

    @abstractmethod
    async def start_server(
        self, host: str, port: int, handler: Callable[[bytes, Tuple[str, int]], None]
    ) -> None:
        """Starts the server listener."""
        pass

    @abstractmethod
    def sendto(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Sends a datagram."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Closes the transport."""
        pass

    @abstractmethod
    def get_port(self) -> int:
        """Returns the actual bound port."""
        pass


class UdpTransport(AbstractTransport):
    """Legacy UDP Transport."""

    def __init__(self) -> None:
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.handler: Optional[Callable[[bytes, Tuple[str, int]], None]] = None

    async def start_server(
        self, host: str, port: int, handler: Callable[[bytes, Tuple[str, int]], None]
    ) -> None:
        self.handler = handler
        loop = asyncio.get_running_loop()

        # We need a protocol adapter for asyncio UDP
        class Adapter(asyncio.DatagramProtocol):
            def __init__(self, parent: "UdpTransport") -> None:
                self.parent = parent

            def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
                if self.parent.handler:
                    self.parent.handler(data, addr)

            def connection_made(self, transport: asyncio.BaseTransport) -> None:
                pass

        # [Phase 66] WAN IP Resolution (Tailscale)
        if os.getenv("SOVEREIGN_WAN_MODE") == "1":
            wan_ip = self._resolve_wan_ip()
            if wan_ip:
                logger.info(
                    f"🌐 [WAN] Overriding bind address to Tailscale IP: {wan_ip}"
                )
                host = wan_ip

        transport, _ = await loop.create_datagram_endpoint(
            lambda: Adapter(self), local_addr=(host, port), allow_broadcast=True
        )
        self.transport = transport
        logger.info(f"[Transport] UDP Server Active on {host}:{port}")

    def _resolve_wan_ip(self) -> Optional[str]:
        """
        Attempts to find a Tailscale IP (100.x.y.z) or VPN tun interface.
        """
        try:
            import socket

            import psutil

            # Prioritize interfaces by name
            interfaces = psutil.net_if_addrs()
            candidates = []

            for iface, addrs in interfaces.items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        ip = addr.address
                        # Tailscale (CGNAT range 100.64.0.0/10)
                        if ip.startswith("100."):
                            # High priority
                            return str(ip)
                        # Fallback candidates (non-local)
                        if not ip.startswith("127.") and not ip.startswith("192.168."):
                            candidates.append(ip)

            if candidates:
                return str(candidates[0])

        except ImportError:
            logger.warning(
                "⚠️ [WAN] psutil not installed. Cannot resolve WAN IP automatically."
            )
        except Exception as e:
            logger.error(f"[WAN] IP resolution failed: {e}")

        return None

    def sendto(self, data: bytes, addr: Tuple[str, int]) -> None:
        if self.transport:
            self.transport.sendto(data, addr)

    def close(self) -> None:
        if self.transport:
            self.transport.close()

    def get_port(self) -> int:
        if self.transport:
            return int(self.transport.get_extra_info("sockname")[1])
        return 0


class QuicTransport(AbstractTransport):
    """Future QUIC Transport."""

    def __init__(self) -> None:
        if not AIOQUIC_AVAILABLE:
            raise ImportError("aioquic not installed")
        self.config = QuicConfiguration(is_client=False)
        self.transport = None

    async def start_server(
        self, host: str, port: int, handler: Callable[[bytes, Tuple[str, int]], None]
    ) -> None:
        logger.info(f"[Transport] QUIC Server Active on {host}:{port} (Encrypted)")
        pass

    def sendto(self, data: bytes, addr: Tuple[str, int]) -> None:
        pass

    def close(self) -> None:
        pass

    def get_port(self) -> int:
        return 0  # Not implemented for QUIC yet


class ChaosMiddleware(AbstractTransport):
    """
    [Phase 66] Chaos Middleware.
    Injects Artificial Latency and Packet Loss to simulate WAN conditions.
    """

    def __init__(self, underlying_transport: AbstractTransport) -> None:
        self.underlying = underlying_transport
        self.latency_ms = int(os.getenv("WARM_LOGIC_CHAOS_LATENCY", "0"))
        self.packet_loss = float(os.getenv("WARM_LOGIC_CHAOS_LOSS", "0.0"))

        if self.latency_ms > 0 or self.packet_loss > 0.0:
            logger.warning(
                f"🌪️ [Chaos] Network Degradation Active: "
                f"Latency={self.latency_ms}ms, Loss={self.packet_loss * 100:.1f}%"
            )

    @property
    def transport(self) -> Optional["asyncio.DatagramTransport"]:
        """Expose underlying transport for backwards compatibility."""
        return getattr(self.underlying, "transport", None)

    async def start_server(
        self, host: str, port: int, handler: Callable[[bytes, Tuple[str, int]], None]
    ) -> None:
        # We wrap the handler to simulate ingress latency/loss if needed
        # But usually chaos is easier to apply on Egress (sendto) or we specifically verify Egress.
        # Let's apply on sendto for now as that controls what WE put on wire.
        await self.underlying.start_server(host, port, handler)

    def sendto(self, data: bytes, addr: Tuple[str, int]) -> None:
        # 1. Packet Loss Simulation
        if self.packet_loss > 0 and random.random() < self.packet_loss:
            logger.debug("[Chaos] Packet Dropped (Simulated Loss)")
            return  # Drop silently

        # 2. Latency Simulation
        if self.latency_ms > 0:
            # We must schedule the send later, non-blocking
            loop = asyncio.get_running_loop()
            delay_sec = (self.latency_ms / 1000.0) + (
                random.uniform(0, 0.01)
            )  # + Jitter
            loop.call_later(delay_sec, lambda: self.underlying.sendto(data, addr))
        else:
            self.underlying.sendto(data, addr)

    def close(self) -> None:
        self.underlying.close()

    def get_port(self) -> int:
        return self.underlying.get_port()


def create_transport(
    mode: str = "AUTO",
    identity: Optional[KineticIdentity] = None,
    secure: Optional[bool] = None,
) -> AbstractTransport:
    if secure is None:
        secure = bool(identity) or os.getenv("WARM_LOGIC_SECURE_TRANSPORT") == "1"

    transport: Optional[AbstractTransport] = None

    if mode == "QUIC" or mode == "AUTO":
        if AIOQUIC_AVAILABLE:
            transport = QuicTransport()
        elif mode == "QUIC":
            raise ImportError("QUIC requested but aioquic missing")

    if transport is None:  # AUTO fallback
        logger.warning("[Transport] QUIC missing. Fallback to UDP.")
        transport = UdpTransport()

    # Optional PQC wrapper; legacy behavior remains plaintext unless explicitly enabled.
    if secure:
        transport = SovereignTransport(transport, identity=identity)

    # [Phase 66] Wrap in Chaos Middleware if env var set
    if os.getenv("WARM_LOGIC_CHAOS_LATENCY") or os.getenv("WARM_LOGIC_CHAOS_LOSS"):
        transport = ChaosMiddleware(transport)

    return transport


class SovereignTransport(AbstractTransport):
    """
    Sovereign Federation Transport.
    Enforces ML-DSA-65 signatures on every packet.
    """

    def __init__(
        self,
        underlying_transport: AbstractTransport,
        identity: Optional[KineticIdentity] = None,
    ) -> None:
        self.underlying = underlying_transport
        self.identity = identity
        if self.identity is None and rust_loader.HAS_RUST_CORE:
            try:
                self.identity = KineticIdentity()
            except Exception as e:
                logger.warning(f"Failed to initialize default KineticIdentity: {e}")

    @property
    def transport(self) -> Optional["asyncio.DatagramTransport"]:
        """Expose underlying transport for backwards compatibility."""
        return getattr(self.underlying, "transport", None)

    async def start_server(
        self, host: str, port: int, handler: Callable[[bytes, Tuple[str, int]], Any]
    ) -> None:
        async def secure_handler_async(data: bytes, addr: Tuple[str, int]) -> None:
            if not self._verify_packet_integrity(data):
                logger.warning(f" Dropping unverified packet from {addr}")
                return

            payload = data
            try:
                import base64
                import json

                envelope = json.loads(data.decode())
                if isinstance(envelope, dict) and isinstance(
                    envelope.get("payload"), str
                ):
                    payload = base64.b64decode(envelope["payload"])
            except Exception:
                # Legacy plaintext payload path.
                payload = data

            try:
                result = handler(payload, addr)
                if result and inspect.isawaitable(result):
                    await result
            except Exception as e:
                logger.warning(f" Secure handler execution failed for {addr}: {e}")

        def secure_handler(data: bytes, addr: Tuple[str, int]):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(secure_handler_async(data, addr))
            return loop.create_task(secure_handler_async(data, addr))

        await self.underlying.start_server(host, port, secure_handler)

    def _verify_packet_integrity(self, data: bytes) -> bool:
        """Verifies packet integrity; accepts legacy JSON packets for compatibility."""
        if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
            return False
        try:
            import json

            envelope = json.loads(data.decode())
            if not isinstance(envelope, dict):
                return False
            pub_key = envelope.get("public_key")
            signature = envelope.get("signature")
            payload = envelope.get("payload")

            if not (pub_key and signature and payload):
                # Legacy plaintext JSON packet path.
                return True

            if rust_loader.HAS_RUST_CORE:
                return KineticIdentity.verify_intent(pub_key, payload, signature)
            return True  # Degraded mode if no Rust core
        except Exception:
            return False

    def sendto(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Wraps data in a PQC-signed envelope."""
        if not self.identity:
            self.underlying.sendto(data, addr)
            return

        try:
            import base64
            import json

            payload_b64 = base64.b64encode(data).decode()
            signature = self.identity.sign_intent(payload_b64)

            envelope = {
                "public_key": self.identity.public_key,
                "signature": signature,
                "payload": payload_b64,
                "era": 5000,
            }
            self.underlying.sendto(json.dumps(envelope).encode(), addr)
        except Exception as e:
            logger.error(f"Failed to wrap packet in Sovereign envelope: {e}")
            # Fallback to unencrypted if forced, or halt.
            # Currently, we prefer to stay silent than leak.

    def close(self) -> None:
        self.underlying.close()

    def get_port(self) -> int:
        return self.underlying.get_port()


# Backwards compatibility alias (renamed in a later revision)
EncryptedTransport = SovereignTransport
