import os
import shutil
from unittest.mock import MagicMock

import pytest

from warm_logic.kernel.autonomy.codex import LogicGap
from warm_logic.kernel.autonomy.mesh_sync import LogosPropagator


@pytest.fixture
def mock_infrastructure():
    dht = MagicMock()
    dht.node_id = b"node_a_id"
    galaxy = MagicMock()
    return dht, galaxy


@pytest.fixture
def node_environments(tmp_path):
    # Setup two separate directory environments for Node A and Node B
    dir_a = tmp_path / "node_a"
    dir_b = tmp_path / "node_b"
    dir_a.mkdir()
    dir_b.mkdir()

    # Create initial code in both
    init_code = "def start():\n    return 'original'\n"
    (dir_a / "app.py").write_text(init_code)
    (dir_b / "app.py").write_text(init_code)

    return dir_a, dir_b


@pytest.mark.asyncio
async def test_logos_propagation_cycle(mock_infrastructure, node_environments):
    """
    Verify that Node A can announce a mutation and Node B can apply it.
    """
    dht_a, galaxy_a = mock_infrastructure
    dir_a, dir_b = node_environments

    propagator_a = LogosPropagator(dht_a, galaxy_a, root_path=str(dir_a))
    propagator_b = LogosPropagator(MagicMock(), MagicMock(), root_path=str(dir_b))

    # 1. Node A undergoes a "Hot Patch" (manual modification in this test)
    (dir_a / "app.py").write_text("def start():\n    return 'evolved'\n")

    # 2. Node A announces mutation
    msg = await propagator_a.announce_mutation()
    assert msg["type"] == "LOGOS_MANIFEST"
    manifest_hash = msg["manifest_hash"]

    # 3. Simulate Node B receiving the gossip and pulling the bundle
    # In this simulation, Node B "asks" Node A for the bundle
    bundle_bytes = propagator_a._bundles[manifest_hash]

    # 4. Node B applies the logos
    propagator_b.apply_remote_logos(bundle_bytes, manifest_hash)

    # 5. Verify Node B's code is now synchronized with Node A
    node_b_code = (dir_b / "app.py").read_text()
    assert "evolved" in node_b_code
    assert propagator_b.current_manifest == manifest_hash

    print(f"\n✅ [Test] Node B successfully adopted kernel: {manifest_hash}")
