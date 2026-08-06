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
Multi-Node Launcher
Launches a cluster of WarmLogic nodes for distributed operation.

Usage:
    # Start a seed node (leader)
    python -m warm_logic.gateway.multi_node --seed

    # Join existing cluster
    python -m warm_logic.gateway.multi_node --join 10.0.0.1:9000

    # Start local 4-node cluster for testing
    python -m warm_logic.gateway.multi_node --local-cluster 4
"""

import argparse
import asyncio
import hashlib
import logging
import signal
import sys
import time
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("MultiNodeLauncher")


class WarmLogicNode:
    """
    A complete WarmLogic node instance.
    Integrates:
    - REST API Gateway
    - StitchServer (SSE)
    - NetworkBridge (UDP/DHT)
    - ClusterOrchestrator
    - BFT Consensus
    - GossipAgent
    """

    def __init__(
        self,
        node_id: Optional[str] = None,
        gateway_port: int = 8000,
        stitch_port: int = 8033,
        p2p_port: int = 9000,
    ) -> None:
        # Generate node ID from ports if not provided
        self.node_id = (
            node_id
            or hashlib.sha256(
                f"node_{gateway_port}_{p2p_port}_{time.time()}".encode()
            ).hexdigest()
        )

        self.gateway_port = gateway_port
        self.stitch_port = stitch_port
        self.p2p_port = p2p_port

        # Components (initialized lazily)
        self._gateway: Optional[Any] = None
        self._stitch: Optional[Any] = None
        self._bridge: Optional[Any] = None
        self._cluster: Optional[Any] = None
        self._bft: Optional[Any] = None
        self._gossip: Optional[Any] = None

        self._running = False

    async def start(self) -> None:
        """Start all node components."""
        if self._running:
            return

        logger.info(f"[Node {self.node_id[:8]}] Starting node...")

        # 1. Start StitchServer
        await self._start_stitch()

        # 2. Initialize NetworkBridge
        await self._start_network()

        # 3. Initialize Cluster
        await self._start_cluster()

        # 4. Initialize BFT Engine
        await self._start_bft()

        # 5. Start REST Gateway (blocking - run in thread)
        self._start_gateway_thread()

        self._running = True
        logger.info(
            f"[Node {self.node_id[:8]}] Started on ports "
            f"gateway:{self.gateway_port} stitch:{self.stitch_port} p2p:{self.p2p_port}"
        )

    async def _start_stitch(self) -> None:
        """Start StitchServer."""
        from warm_logic.kernel.substrate.stitch_server import StitchServer

        self._stitch = StitchServer(port=self.stitch_port)
        self._stitch.start()
        logger.info(
            f"[Node {self.node_id[:8]}] StitchServer started on :{self.stitch_port}"
        )

    async def _start_network(self) -> None:
        """Start NetworkBridge with Rust DHT."""
        from warm_logic.kernel.substrate.network_bridge import (
            NetworkBridge,
            register_block_handlers,
        )

        self._bridge = NetworkBridge(
            node_id=self.node_id,
            bind_port=self.p2p_port,
        )

        # Try to connect Rust DHT
        if self._bridge.connect_rust_dht():
            logger.info(f"[Node {self.node_id[:8]}] Rust DHT connected")
        else:
            logger.warning(f"[Node {self.node_id[:8]}] Running without Rust DHT")

        # Connect StitchServer
        self._bridge.connect_stitch(self._stitch)

        # Register block handlers
        register_block_handlers(self._bridge, self._stitch)

        logger.info(f"[Node {self.node_id[:8]}] NetworkBridge started")

    async def _start_cluster(self) -> None:
        """Start ClusterOrchestrator."""
        from warm_logic.kernel.substrate.cluster import ClusterOrchestrator

        self._cluster = ClusterOrchestrator(node_id=self.node_id)
        self._cluster.connect_network(self._bridge)
        self._cluster.connect_stitch(self._stitch)

        await self._cluster.start()
        logger.info(f"[Node {self.node_id[:8]}] ClusterOrchestrator started")

    async def _start_bft(self) -> None:
        """Start BFT consensus engine."""
        try:
            import warm_logic_rs

            self._bft = warm_logic_rs.BFTEngine(quorum_size=3)
            if self._bridge:
                self._bridge.connect_bft(self._bft)
            logger.info(f"[Node {self.node_id[:8]}] BFT Engine started")
        except ImportError:
            logger.warning(f"[Node {self.node_id[:8]}] Rust core not available for BFT")

    def _start_gateway_thread(self) -> None:
        """Start REST API Gateway in a thread."""
        import threading

        def run_gateway() -> None:
            import uvicorn

            from warm_logic.gateway.app import gateway_app

            # Configure uvicorn
            uvicorn.run(
                gateway_app,
                host="0.0.0.0",
                port=self.gateway_port,
                log_level="warning",
            )

        thread = threading.Thread(target=run_gateway, daemon=True)
        thread.start()
        logger.info(
            f"[Node {self.node_id[:8]}] REST Gateway started on :{self.gateway_port}"
        )

    async def stop(self) -> None:
        """Stop all node components."""
        if not self._running:
            return

        logger.info(f"[Node {self.node_id[:8]}] Stopping...")

        if self._cluster:
            await self._cluster.stop()

        if self._stitch:
            self._stitch.stop()

        self._running = False
        logger.info(f"[Node {self.node_id[:8]}] Stopped")

    def join_cluster(self, seed_addr: str, seed_port: int) -> bool:
        """Join an existing cluster."""
        if self._cluster:
            return bool(self._cluster.join_cluster(seed_addr, seed_port))
        return False

    def add_peer(self, peer_id: str, addr: str, port: int) -> None:
        """Add a peer to the network."""
        if self._bridge:
            self._bridge.add_peer(peer_id, addr, port)

    def get_status(self) -> Dict[str, Any]:
        """Get node status."""
        status = {
            "node_id": self.node_id,
            "running": self._running,
            "gateway_port": self.gateway_port,
            "stitch_port": self.stitch_port,
            "p2p_port": self.p2p_port,
        }

        if self._cluster:
            status["cluster"] = self._cluster.get_status()

        if self._bridge:
            status["network"] = self._bridge.get_status()

        return status


async def run_seed_node(args: argparse.Namespace) -> None:
    """Run as a seed/leader node."""
    node = WarmLogicNode(
        gateway_port=args.gateway_port,
        stitch_port=args.stitch_port,
        p2p_port=args.p2p_port,
    )

    await node.start()

    logger.info(
        f"\n"
        f"╔══════════════════════════════════════════════════════════════╗\n"
        f"║           WarmLogic Seed Node Started                        ║\n"
        f"╠══════════════════════════════════════════════════════════════╣\n"
        f"║  Node ID: {node.node_id[:32]}...                    ║\n"
        f"║  REST API: http://0.0.0.0:{args.gateway_port}/docs             ║\n"
        f"║  Stitch SSE: http://0.0.0.0:{args.stitch_port}/stream          ║\n"
        f"║  P2P Port: {args.p2p_port}                                     ║\n"
        f"╠══════════════════════════════════════════════════════════════╣\n"
        f"║  Other nodes can join with:                                  ║\n"
        f"║  --join <this-ip>:{args.p2p_port}                              ║\n"
        f"╚══════════════════════════════════════════════════════════════╝\n"
    )

    # Wait for shutdown signal
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await node.stop()


async def run_join_node(args: argparse.Namespace) -> None:
    """Run as a follower node, joining existing cluster."""
    seed_parts = args.join.split(":")
    seed_addr = seed_parts[0]
    seed_port = int(seed_parts[1]) if len(seed_parts) > 1 else 9000

    node = WarmLogicNode(
        gateway_port=args.gateway_port,
        stitch_port=args.stitch_port,
        p2p_port=args.p2p_port,
    )

    await node.start()

    # Join the cluster
    if node.join_cluster(seed_addr, seed_port):
        logger.info(f"Join request sent to {seed_addr}:{seed_port}")
    else:
        logger.error("Failed to send join request")

    logger.info(
        f"\n"
        f"╔══════════════════════════════════════════════════════════════╗\n"
        f"║           WarmLogic Follower Node Started                    ║\n"
        f"╠══════════════════════════════════════════════════════════════╣\n"
        f"║  Node ID: {node.node_id[:32]}...                    ║\n"
        f"║  Joining: {seed_addr}:{seed_port}                              ║\n"
        f"║  REST API: http://0.0.0.0:{args.gateway_port}/docs             ║\n"
        f"╚══════════════════════════════════════════════════════════════╝\n"
    )

    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await node.stop()


async def run_local_cluster(args: argparse.Namespace) -> None:
    """Run a local multi-node cluster for testing."""
    node_count = args.local_cluster
    nodes: List[WarmLogicNode] = []

    base_gateway_port = 8000
    base_stitch_port = 8033
    base_p2p_port = 9000

    logger.info(f"Starting local cluster with {node_count} nodes...")

    # Start all nodes
    for i in range(node_count):
        node = WarmLogicNode(
            gateway_port=base_gateway_port + i,
            stitch_port=base_stitch_port + i,
            p2p_port=base_p2p_port + i,
        )
        await node.start()
        nodes.append(node)

        # Add peer connections (mesh topology)
        for j, other_node in enumerate(nodes[:-1]):
            node.add_peer(
                other_node.node_id,
                "127.0.0.1",
                base_p2p_port + j,
            )
            other_node.add_peer(
                node.node_id,
                "127.0.0.1",
                base_p2p_port + i,
            )

        await asyncio.sleep(0.5)  # Stagger startup

    logger.info(
        f"\n"
        f"╔══════════════════════════════════════════════════════════════╗\n"
        f"║           WarmLogic Local Cluster Started                    ║\n"
        f"╠══════════════════════════════════════════════════════════════╣\n"
        f"║  Nodes: {node_count}                                          ║\n"
    )

    for i, node in enumerate(nodes):
        role = "Leader" if i == 0 else "Follower"
        logger.info(
            f"║  Node {i+1} ({role}):                                      ║\n"
            f"║    API: http://127.0.0.1:{base_gateway_port + i}/docs      ║\n"
            f"║    P2P: 127.0.0.1:{base_p2p_port + i}                      ║"
        )

    logger.info("╚══════════════════════════════════════════════════════════════╝\n")

    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        for node in nodes:
            await node.stop()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WarmLogic Multi-Node Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Start seed node:     python -m warm_logic.gateway.multi_node --seed
  Join cluster:        python -m warm_logic.gateway.multi_node --join 10.0.0.1:9000
  Local 4-node test:   python -m warm_logic.gateway.multi_node --local-cluster 4
        """,
    )

    parser.add_argument(
        "--seed",
        action="store_true",
        help="Start as a seed node (cluster leader)",
    )
    parser.add_argument(
        "--join",
        type=str,
        help="Join existing cluster (format: host:port)",
    )
    parser.add_argument(
        "--local-cluster",
        type=int,
        metavar="N",
        help="Start a local cluster with N nodes",
    )
    parser.add_argument(
        "--gateway-port",
        type=int,
        default=8000,
        help="REST API Gateway port (default: 8000)",
    )
    parser.add_argument(
        "--stitch-port",
        type=int,
        default=8033,
        help="StitchServer SSE port (default: 8033)",
    )
    parser.add_argument(
        "--p2p-port",
        type=int,
        default=9000,
        help="P2P network port (default: 9000)",
    )

    args = parser.parse_args()

    # Set up signal handler
    def signal_handler(sig: int, frame: Any) -> None:
        logger.info("Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Determine mode and run
    if args.local_cluster:
        asyncio.run(run_local_cluster(args))
    elif args.join:
        asyncio.run(run_join_node(args))
    else:
        # Default to seed node
        asyncio.run(run_seed_node(args))


if __name__ == "__main__":
    main()
