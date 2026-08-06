"""
E2E Mesh Sync Verification
Validates that messages propagate across a 3-node cluster via gossip.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
import requests

NODE_COUNT = 3

SERVER_SCRIPT = "warm_logic/ui/server.py"
REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_SCRIPT = str(REPO_ROOT / "src" / "warm_logic" / "ui" / "server.py")
PYTHON_CMD = os.getenv("WARM_PYTHON_CMD", sys.executable)


def _cleanup_path(path: str) -> None:
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        os.remove(path)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _close_proc_streams(proc: subprocess.Popen) -> None:
    for stream in (proc.stdout, proc.stderr):
        if stream is None:
            continue
        try:
            stream.close()
        except Exception:
            pass


def _wait_for_feed_message(
    node_url: str,
    content: str,
    timeout_s: float = 15.0,
    poll_interval_s: float = 0.5,
) -> tuple[bool, List[Dict[str, Any]]]:
    deadline = time.monotonic() + timeout_s
    last_feed: List[Dict[str, Any]] = []
    while time.monotonic() < deadline:
        try:
            response = requests.get(f"{node_url}/api/social/feed", timeout=2)
            if response.status_code == 200:
                feed = response.json()
                if isinstance(feed, list):
                    last_feed = feed
                    if any(item.get("content") == content for item in feed):
                        return True, feed
        except requests.exceptions.RequestException:
            pass
        time.sleep(poll_interval_s)
    return False, last_feed


class ClusterFixture:
    def __init__(self):
        self.procs = []
        self.db_paths = []
        self.nodes = []
        for _ in range(NODE_COUNT):
            port = _find_free_port()
            self.nodes.append({"port": port, "url": f"http://127.0.0.1:{port}"})

    def start(self):
        print("🚀 Starting 3-node Cluster...")
        base_env = os.environ.copy()
        # Force production mode for reality test (but we use separate DBs)
        base_env["WARM_LOGIC_SIMULATION"] = "0"
        base_env["WARM_SIM_SANDBOX"] = "1"
        # Avoid provenance race during parallel 3-node startup in CI.
        base_env["WARM_SKIP_PROVENANCE_GUARD"] = "1"

        for node in self.nodes:
            port = node["port"]
            db_path = f"/tmp/node_{port}_db"
            self.db_paths.append(db_path)

            # Wipe previous DB for clean state
            _cleanup_path(db_path)

            env = base_env.copy()
            env["WARM_HTTP_PORT"] = str(port)
            env["WARM_DB_PATH"] = db_path
            pythonpath_parts = [
                str(REPO_ROOT / "src"),
                str(REPO_ROOT / "packages" / "warm_logic_sdk"),
                env.get("PYTHONPATH", ""),
            ]
            env["PYTHONPATH"] = ":".join([p for p in pythonpath_parts if p])

            # Start process
            proc = subprocess.Popen(
                [PYTHON_CMD, SERVER_SCRIPT],
                env=env,
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.procs.append(proc)
            print(f"   - Node started on port {port}")
            time.sleep(0.2)

    def verify_health(self):
        print("Waiting for cluster health...")
        timeout = 40
        start = time.monotonic()

        while time.monotonic() - start < timeout:
            healthy_count = 0
            for node in self.nodes:
                try:
                    r = requests.get(f"{node['url']}/health/liveness", timeout=0.5)
                    if r.status_code == 200:
                        healthy_count += 1
                except requests.exceptions.RequestException:
                    pass

            if healthy_count == len(self.nodes):
                print("✅ Cluster is UP and READY.")
                return True
            time.sleep(1)

        diagnostics = []
        for idx, proc in enumerate(self.procs):
            node = self.nodes[idx]
            rc = proc.poll()
            if rc is None:
                diagnostics.append(f"port={node['port']} pid={proc.pid} still-running")
                continue

            stderr_text = ""
            stdout_text = ""
            if proc.stdout is not None:
                stdout_text = proc.stdout.read().decode(errors="replace").strip()
            if proc.stderr is not None:
                stderr_text = proc.stderr.read().decode(errors="replace").strip()
            if stdout_text:
                stdout_text = stdout_text.splitlines()[-1]
            if stderr_text:
                stderr_text = stderr_text.splitlines()[-1]
            diagnostics.append(
                f"port={node['port']} pid={proc.pid} exit={rc} "
                f"stdout={stdout_text} stderr={stderr_text}"
            )

        self.stop()
        raise RuntimeError(
            "Cluster failed to start "
            f"(only {healthy_count}/{len(self.nodes)} healthy). diagnostics={diagnostics}"
        )

    def stop(self):
        print("\n🛑 Stopping Cluster...")
        for proc in self.procs:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            _close_proc_streams(proc)
        self.procs.clear()

        # Cleanup DBs
        for db_path in self.db_paths:
            _cleanup_path(db_path)
        self.db_paths.clear()
        print("✅ Cluster stopped and cleaned up.")


def test_gossip_propagation():
    """
    1. Start 3-node cluster
    2. Post message to Node A (dynamic port)
    3. Wait for gossip interval
    4. Check Node C for the message
    """
    cluster = ClusterFixture()
    try:
        cluster.start()
        cluster.verify_health()

        # 1. Post to Node A
        target_node = cluster.nodes[0]
        message_content = f"Mesh Gossip Test {int(time.time())}"
        print(f"Posting to Node A ({target_node['port']}): '{message_content}'")

        try:
            r = requests.post(
                f"{target_node['url']}/api/social/post",
                json={"message": message_content},
                timeout=2,
            )
            assert r.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.fail("Failed to connect to Node A")

        # 2. Peer Discovery & Gossip Wait
        # Nodes need time to discover each other via Beacon and sync.
        # Poll feed until timeout instead of fixed sleep to reduce flakiness.
        check_node = cluster.nodes[2]
        wait_time = 15
        print(f"Polling Node C ({check_node['port']}) for up to {wait_time}s...")
        found, feed = _wait_for_feed_message(check_node["url"], message_content, wait_time)

        if found:
            print("✅ SUCCESS: Message propagated to Node C!")
        else:
            print("❌ FAILURE: Message NOT found in Node C.")
            print(f"Node C Feed Items ({len(feed)}): {feed}")
            # Debug info: Check peers
            peers = requests.get(
                f"{check_node['url']}/api/mesh/peers", timeout=1
            ).json()
            print(f"Node C Active Peers: {peers['active_peers']}")

        assert found, f"Message '{message_content}' did not propagate to Node C"

    finally:
        cluster.stop()


if __name__ == "__main__":
    test_gossip_propagation()
