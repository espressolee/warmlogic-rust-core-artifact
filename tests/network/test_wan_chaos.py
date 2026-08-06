import asyncio
import logging
import os
from unittest.mock import MagicMock

import pytest

from warm_logic.kernel.mesh.transport import UdpTransport, create_transport

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestWANChaos")


@pytest.mark.asyncio
async def test_wan_chaos_resilience():
    """
    Verifies that messages can eventually be delivered or at least handled
    validation logic even under simulated chaos (latency/loss).
    Uses the ChaosMiddleware.
    """
    print("\n🌪️ Starting WAN Chaos Test...")

    # 1. Setup Environment for Chaos
    os.environ["WARM_LOGIC_CHAOS_LATENCY"] = "100"  # 100ms latency
    os.environ["WARM_LOGIC_CHAOS_LOSS"] = "0.2"  # 20% packet loss

    # 2. Create Transports (Node A and Node B)
    # We use loopback for connectivity, but chaos middleware will intercept
    host = "127.0.0.1"
    port_a = 9001
    port_b = 9002

    # This test validates UDP packet flow under chaos middleware.
    # Use raw ChaosMiddleware without SovereignTransport PQC wrapping
    # to test pure network chaos behavior.
    from warm_logic.kernel.mesh.transport import ChaosMiddleware

    transport_a = ChaosMiddleware(UdpTransport())
    transport_b = ChaosMiddleware(UdpTransport())

    received_messages = []

    def handler_b(data, addr):
        msg = data.decode()
        logger.info(f"📨 Node B received: {msg}")
        received_messages.append(msg)

    try:
        try:
            await transport_b.start_server(host, port_b, handler_b)
            await transport_a.start_server(host, port_a, lambda d, a: None)
        except OSError as exc:
            if getattr(exc, "errno", None) in {1, 13}:
                pytest.skip(f"UDP bind not permitted in this environment: {exc}")
            raise

        # 3. Send Burst of Messages (to tolerate 20% loss)
        # If we send 10 messages, ~8 should arrive.
        count = 20
        logger.info(f"📤 Node A sending {count} packets...")

        for i in range(count):
            msg = f"Ping-{i}"
            transport_a.sendto(msg.encode(), (host, port_b))
            # Small sleep to allow latency scheduler to work
            await asyncio.sleep(0.01)

        # 4. Wait for arrival (incorporating latency)
        # Latency is 100ms. Wait enough time.
        logger.info("⏳ Waiting for propagation...")
        await asyncio.sleep(3.0)

        # 5. Verification
        received_count = len(received_messages)
        logger.info(f"📊 Report: Sent={count}, Received={received_count}")

        # 20% loss expected, so we expect roughly 16.
        # Let's assert we got significant traffic (e.g. > 50%)
        # This proves flow is not broken, just degraded.
        assert received_count > (
            count * 0.5
        ), "Packet loss was too high or communication failed completely."
        assert (
            received_count < count
        ), "Chaos Loss failed? Received all packets (statistically unlikely with 0.2 loss)."

        # 6. Latency Check (Soft verification)
        # Ideally we'd timestamp send vs receive, but simple arrival check is good enough for 'resilience' logic validation.
    finally:
        transport_a.close()
        transport_b.close()
        os.environ.pop("WARM_LOGIC_CHAOS_LATENCY", None)
        os.environ.pop("WARM_LOGIC_CHAOS_LOSS", None)
    print("✅ Chaos Test Passed: System tolerates WAN traits.")
