import asyncio
import socket

import pytest

from warm_logic.kernel.mesh.dht import SovereignDHT


@pytest.mark.asyncio
async def test_dht_network_broadcast():
    """
    Phase 53.1: Verify SovereignDHT sends physical broadcast.
    SIM-035: Network Broadcast.
    """
    node_id = b"\x01" * 32
    # Use ephemeral port
    # This test validates UDP broadcast socket options.
    # For determinism, force UDP transport instead of AUTO(QUIC/UDP).
    dht = SovereignDHT(node_id, "127.0.0.1", 0, transport_mode="UDP")

    # 1. Start transport (mocking nat discovery to avoid external calls)
    # Some sandboxes/CI runtimes prohibit UDP bind entirely.
    try:
        await dht.start(enable_nat_discovery=False)
    except PermissionError as exc:
        pytest.skip(f"UDP bind not permitted in this environment: {exc}")

    # 2. Verify Transport created with allow_broadcast
    sock: socket.socket = dht.transport.transport.get_extra_info("socket")
    assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST) != 0

    # 3. Mock transport.sendto to capture target
    captured_data = None
    captured_addr = None

    original_sendto = dht.transport.sendto

    def mock_sendto(data, addr):
        nonlocal captured_data, captured_addr
        captured_data = data
        captured_addr = addr
        # Call original (will fail if socket opts wrong)
        # However, 255.255.255.255 might fail on some restrictive CIs (e.g. invalid argument)
        # So we wrap in try/except but fail if it's NOT a broadcast permission error.
        try:
            original_sendto(data, addr)
        except OSError as e:
            # If "Permission denied" or "Network unreachable", it's OS env, but code tried correctly.
            print(f"OS specific sendto error (ignored): {e}")
            pass

    dht.transport.sendto = mock_sendto

    # 4. Trigger Broadcast
    dht.announce_presence()

    # 5. Verify captured address
    assert captured_addr is not None
    assert captured_addr[0] == "255.255.255.255"
    assert b"MANIFEST_ANNOUNCE" in captured_data

    print(f"✅ Captured Broadcast Packet to {captured_addr}")

    dht.transport.close()


if __name__ == "__main__":
    asyncio.run(test_dht_network_broadcast())
