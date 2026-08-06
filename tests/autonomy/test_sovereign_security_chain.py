from unittest.mock import MagicMock

import pytest

from warm_logic.kernel.autonomy.mesh_sync import LogosPropagator
from warm_logic.security.pqc import SovereignSecurity


@pytest.fixture
def security_infrastructure():
    dht = MagicMock()
    dht.node_id = b"node_a"
    galaxy = MagicMock()
    return dht, galaxy


@pytest.mark.asyncio
async def test_security_chain_unsigned_rejected(security_infrastructure):
    """
    Phase 24.3: Verify that an unsigned manifest is rejected.
    """
    dht, galaxy = security_infrastructure
    propagator = LogosPropagator(dht, galaxy)

    malicious_msg = {
        "type": "LOGOS_MANIFEST",
        "manifest_hash": "hack_hash",
        "origin": "rogue_node",
        # Missing signature and public_key
    }

    # handle_logos_manifest should return False (Rejection)
    accepted = await propagator.handle_logos_manifest(malicious_msg)
    assert not accepted


@pytest.mark.asyncio
async def test_security_chain_invalid_sig_rejected(security_infrastructure):
    """
    Phase 24.3: Verify that an invalidly signed manifest is rejected.
    """
    dht, galaxy = security_infrastructure
    propagator = LogosPropagator(dht, galaxy)

    malicious_msg = {
        "type": "LOGOS_MANIFEST",
        "manifest_hash": "hack_hash",
        "signature": "MOCK_SIG_wrong_hash",
        "public_key": "MOCK_PK",
        "origin": "rogue_node",
    }

    accepted = await propagator.handle_logos_manifest(malicious_msg)
    assert not accepted


@pytest.mark.asyncio
async def test_security_chain_quorum_gating(security_infrastructure):
    """
    Phase 24.4: Verify that a manifest is only accepted after quorum.
    """
    dht, galaxy = security_infrastructure
    propagator = LogosPropagator(dht, galaxy)
    propagator.quorum_threshold = 2  # Requires 2 votes

    manifest_hash = "valid_hash"
    pk, sk = SovereignSecurity.generate_keypair()
    propagator.node_keypair = (pk, sk)
    sig = propagator.bundler.sign_bundle(sk, manifest_hash)

    # Vote 1 (Node B)
    msg1 = {
        "type": "LOGOS_MANIFEST",
        "manifest_hash": manifest_hash,
        "signature": sig,
        "public_key": pk,
        "origin": "node_b",
    }

    # First vote should be verified but return False (Waiting for quorum)
    accepted = await propagator.handle_logos_manifest(msg1)
    assert not accepted
    assert "node_b" in propagator._manifest_votes[manifest_hash]

    # Vote 2 (Node C)
    msg2 = msg1.copy()
    msg2["origin"] = "node_c"

    accepted = await propagator.handle_logos_manifest(msg2)
    assert accepted  # Quorum achieved!

    print("\n✅ [Test] Security Chain (PQC + Quorum) verified.")
