#!/usr/bin/env python3
"""
scripts/benchmarks/macro_suite.py Macro-Benchmark Suite.
Measures the "Vital Signs" of the Sovereign OS.
"""

import time
import asyncio
import logging
import tempfile
import os
import shutil
from pathlib import Path

# Configure logging to be concise
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("MacroBench")
logger.setLevel(logging.INFO)

# --- Metric 1: Sov-Boot ---
def benchmark_sov_boot():
    logger.info("⏱ [1/3] Measuring Sov-Boot (Cold Start)...")

    # We measure import time + init time
    start_time = time.time()

    # Simulate a clean process start by re-loading essential modules if possible,
    # but here we just measure the 'boot_system' call which does the heavy lifting
    # (Rust load, TPM read, Crypto init).

    try:
        from warm_logic.kernel.bootloader import Bootloader, HAS_RUST_CORE

        # Force a fresh loader instance
        loader = Bootloader()

        # 1. Init (Rust Load)
        loader.run_init()

        # 2. Hardware Bind (TPM)
        # We assume verify_secure_boot calls the HAL
        sealed, proof = loader.verify_secure_boot()

        # 3. Kernel Jump
        kernel = loader.jump_to_kernel()

        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        logger.info(f"   => Result: {duration_ms:.2f} ms")
        return duration_ms

    except Exception as e:
        logger.error(f"   => Failed: {e}")
        return None

# --- Metric 2: Darwin Reflex ---
def benchmark_darwin_reflex():
    logger.info("⏱ [2/3] Measuring Darwin Reflex (Mutation Pipeline)...")

    # Measure time to:
    # 1. Propose mutation (File Write)
    # 2. Verify mutation (Sandbox Config + Test Run)
    # 3. Commit mutation (Git/Storage)

    from warm_logic.system.replication.codebase import SovereignCodebase
    from warm_logic.kernel.ops.evolution import SandboxedVerifier

    class MockSovereignStore:
        def __init__(self, root):
            self.root = root
            self.blobs = {}
            self.meta = {}

        def put_blob(self, key, content):
            self.blobs[key] = content

        def get_blob(self, key):
            return self.blobs.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

        def get_meta(self, key):
            return self.meta.get(key)

    start_time = time.time()

    with tempfile.TemporaryDirectory() as tmp_root:
        # Setup dummy codebase
        store = MockSovereignStore(tmp_root)
        codebase = SovereignCodebase(store)
        verifier = SandboxedVerifier(tmp_root)

        # Create a dummy test file to pass verification
        (Path(tmp_root) / "tests").mkdir()
        (Path(tmp_root) / "tests" / "test_dummy.py").write_text("def test_pass(): assert True")

        # Create dummy target file
        (Path(tmp_root) / "kernel").mkdir()
        target_file = Path(tmp_root) / "kernel" / "module.py"
        target_file.write_text("x = 1")


        # 0. Ingest files to populate manifest
        codebase.ingest(tmp_root)

        # 1. Propose
        new_content = b"x = 2"
        mut_id = codebase.propose_mutation("kernel/module.py", new_content)

        # 2. Verify (This runs a subprocess pytest, usually the bottleneck)
        # We run a trivial test to measure the *overhead* of the sandbox mechanism
        cmd = [["python3", "-c", "exit(0)"]]
        verified = verifier.verify("kernel/module.py", new_content, cmd)

        if not verified:
            logger.error("   => Verification failed unexpectedly")
            return None

        # 3. Commit
        committed = codebase.commit_mutation(mut_id, tmp_root)

        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        logger.info(f"   => Result: {duration_ms:.2f} ms")
        return duration_ms

# --- Metric 3: Lazarus (Healing) ---
async def benchmark_lazarus():
    logger.info("⏱ [3/3] Measuring Lazarus (Mesh Healing)...")

    # We simulate 5 DHT nodes in-process interacting via local transport
    from warm_logic.kernel.mesh.dht import SovereignDHT
    from warm_logic.kernel.mesh.transport import UdpTransport # Explicitly use UDP for stability in bench

    nodes = []
    base_port = 15000

    # Spin up 5 nodes
    for i in range(5):
        node_id = bytes([i]*32)
        dht = SovereignDHT(node_id, "127.0.0.1", base_port + i, transport_mode="UDP") # Force UDP to avoid strict checks
        await dht.start()
        nodes.append(dht)

    # Bootstrap them (Mesh formation)
    # Node 0 is seed
    seed = ("127.0.0.1", base_port)
    for node in nodes[1:]:
        # Manually inject seed into routing table to speed up "bootstrap" simulation
        # In real bench we'd call bootstrap(), but here we want to time *healing*.
        # Let's assume they know 0.
        from warm_logic.kernel.mesh.dht import Contact
        c0 = Contact(nodes[0].node_id, "127.0.0.1", base_port)
        await node.routing.update(c0)

    # Let them stabilize
    await asyncio.sleep(0.1)

    # KILL 2 Nodes (1 and 2)
    start_time = time.time()

    # "Killing" means stopping transport and removing from others' routing (simulating timeout)
    # For a benchmark, we measure how fast 'find_node' adapts.
    # We will simulate the *detection* logic.

    # Let's test: Node 4 tries to find Node 0. It should work.
    # Then Node 4 tries to find Node 1 (Dead). It should fail fast and evict.

    dead_node = nodes[1]
    alive_node = nodes[4]

    # Poison the routing table of 4 with 1
    c1 = Contact(dead_node.node_id, "127.0.0.1", base_port + 1)
    await alive_node.routing.update(c1)

    # Verify 1 is in 4's table
    # (Implementation detail check)

    # Now "Kill" 1 (Stop server)
    dead_node.transport.close()

    # Measure time for 4 to realize 1 is dead during a ping
    # dht.ping logic handles eviction
    # But dht.py doesn't expose 'ping' directly widely, it uses routing.update(dht=self)

    # We call a find_node that forces contact check
    # Or just ping directly
    try:
        # We simulate the ping mechanism:
        # We manually try to send a ping. It should fail/timeout.
        # But wait, UdpTransport.sendto doesn't raise on send. RPC calls timeout.

        # We measure the Timeout + Eviction latency.
        # Ideally this is configurable. Default timeout is often high.
        # We will check if we can configure timeout for the bench.

        # Using rpc_call with short timeout
        msg = {"type": "PING", "sender_id": alive_node.node_id.hex()}
        try:
            await alive_node.rpc_call(c1, msg, timeout=0.2)
        except asyncio.TimeoutError:
            # This is the "Detection"
            # Now "Heal": Remove from bucket
            # In real code this happens in update logic.
            pass

        end_time = time.time()
        # Lazarus = Time to Detect + Time to Evict.
        # Here we measured detection latency.

        duration_ms = (end_time - start_time) * 1000
        logger.info(f"   => Result: {duration_ms:.2f} ms")

        # Cleanup
        for n in nodes:
            if n != dead_node:
                if n.transport: n.transport.close()

        return duration_ms

    except Exception as e:
        logger.error(f"   => Lazarus Failed: {e}")
        return None

async def main():
    print("\n[Macro-Benchmark] Measuring Reality...\n")

    res_boot = benchmark_sov_boot()
    res_darwin = benchmark_darwin_reflex()
    res_lazarus = await benchmark_lazarus()

    print("\n" + "="*30)
    print("FINAL RESULTS")
    print("="*30)
    print(f"1. Sov-Boot:      {res_boot:.2f} ms" if res_boot else "1. Sov-Boot:      FAILED")
    print(f"2. Darwin Reflex: {res_darwin:.2f} ms" if res_darwin else "2. Darwin Reflex: FAILED")
    print(f"3. Lazarus:       {res_lazarus:.2f} ms" if res_lazarus else "3. Lazarus:       FAILED")
    print("="*30 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
