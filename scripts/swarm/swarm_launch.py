import logging
import os
import random
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

# Setup paths
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from warm_logic.kernel.drone.control.controller import DroneController
from warm_logic.kernel.drone.types import Position

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("SwarmOrchestrator")


@dataclass
class DroneNode:
    id_hex: str
    public_key: str
    private_key: str
    drone: DroneController


class SwarmNetwork:
    """Simulates a P2P network bridge for BFT/Swarm packets."""

    def __init__(self, packet_loss_rate: float = 0.0):
        self.nodes: Dict[str, DroneNode] = {}
        self.packet_loss_rate = packet_loss_rate
        self.total_packets_sent = 0
        self.total_packets_dropped = 0

    def add_node(self, node: DroneNode):
        self.nodes[node.id_hex] = node

    def broadcast(self, sender_id: str, packet: bytes):
        """Broadcasts a swarm packet to all other nodes."""
        for node_id, node in self.nodes.items():
            if node_id == sender_id:
                continue

            self.total_packets_sent += 1
            if random.random() < self.packet_loss_rate:
                self.total_packets_dropped += 1
                continue

            # Deliver to Rust core
            if node.drone._rust_controller:
                node.drone._rust_controller.handle_swarm_packet(packet)


def generate_swarm_identities(count: int) -> List[Dict[str, str]]:
    identities = []
    for i in range(count):
        # Generate random unique NodeIDs and dummy keys
        node_id = "".join([random.choice("0123456789abcdef") for _ in range(64)])
        # Use a dummy BFT-friendly public key
        pk = f"SITL-DRONE-{i:03d}-PUB"
        sk = f"SITL-DRONE-{i:03d}-PRIV"
        identities.append({"id": node_id, "pk": pk, "sk": sk})
    return identities


def run_swarm_sim(
    num_drones: int = 5, packet_loss: float = 0.1, duration_s: float = 30
):
    logger.info(
        f"🚀 Starting Large Scale Swarm SITL: {num_drones} Drones (Loss: {packet_loss * 100}%)"
    )

    identities = generate_swarm_identities(num_drones)
    network = SwarmNetwork(packet_loss_rate=packet_loss)
    nodes: List[DroneNode] = []

    # 1. Initialize Drones
    for i in range(num_drones):
        drone_id = f"DRONE{i:03d}"
        identity = identities[i]

        # We manually initialize the Rust controller with identity
        # In a real app, DroneController.__init__ would handle this
        from warm_logic_rs import PyDroneController

        d = DroneController(drone_id, public_key=identity["pk"], node_id=identity["id"])

        node = DroneNode(
            id_hex=identity["id"],
            public_key=identity["pk"],
            private_key=identity["sk"],
            drone=d,
        )
        nodes.append(node)
        network.add_node(node)
        logger.info(f"  Initialized {drone_id} with NodeId {identity['id'][:8]}...")

    # 2. Simulation Loop
    start_time = time.time()
    last_tick = 0

    # Test Scenario: After 5 seconds, DRONE000 proposes a mission.
    # All drones should eventually agree if BFT quorum (3/5) is reached.
    mission_proposed = False
    equivocation_attack = False

    while time.time() - start_time < duration_s:
        current_time = time.time() - start_time
        dt = 0.01  # 100Hz

        # Periodic Tasks
        for node in nodes:
            # a. Update IMU (Mock hover data)
            # Gyro (rad/s), Accel (m/s^2)
            node.drone.update_state_from_sensors(
                {
                    "imu_accel": (0.0, 0.0, -9.81),
                    "imu_gyro": (0.0, 0.0, 0.0),
                    "gps_pos": (0.0, 0.0, 10.0),
                    "sim_time": current_time,
                }
            )

            # b. Poll for outgoing swarm packets
            if node.drone._rust_controller:
                packets = node.drone._rust_controller.poll_swarm_packets()
                for p in packets:
                    network.broadcast(node.id_hex, p)

        # Scenario Injection
        if not mission_proposed and current_time > 5.0:
            logger.info("DRONE000: Proposing Swarm Mission (BFT Start)...")
            # In SITL, we simulate the arrival of a PQC command at DRONE000
            # We mock the sequence that triggers propose_mission in Rust
            # Normally this comes from handle_mavlink_packet
            node0 = nodes[0]
            if node0.drone._rust_controller:
                # We tell DRONE000 to propose a mission hash
                # This simulates its local PQC verification passing
                mission_hash = "f00d" * 8  # 32-byte hash hex
                node0.drone._rust_controller.propose_mission(mission_hash)
            mission_proposed = True

        # Red Team Injection: DRONE001 attempts Equivocation after 5.5s
        if mission_proposed and not equivocation_attack and current_time > 5.5:
            logger.warning(
                "👺 DRONE001 (Mallory): Injecting Equivocation (Conflicting Mission)!"
            )
            bad_hash = "cc00" * 8
            nodes[1].drone._rust_controller.propose_mission(bad_hash)
            equivocation_attack = True

        # Monitoring
        if int(current_time) > last_tick:
            last_tick = int(current_time)
            # Check agreement on each node
            agreement_status = []
            for node in nodes:
                is_agreed = (
                    node.drone._rust_controller.check_agreement()
                    if node.drone._rust_controller
                    else False
                )
                agreement_status.append("✅" if is_agreed else "❌")

            logger.info(
                f"T={last_tick}s | Consensus: {' '.join(agreement_status)} | Net: {network.total_packets_sent} sent, {network.total_packets_dropped} dropped"
            )

        time.sleep(dt)

    logger.info("Simulation Complete.")

    # Summary of Consensus
    agreed_count = sum(
        1
        for node in nodes
        if node.drone._rust_controller and node.drone._rust_controller.check_agreement()
    )
    logger.info(f"Final Outcome: {agreed_count}/{num_drones} drones reached consensus.")
    if agreed_count >= 3:
        logger.info("BFT QUORUM REACHED! Swarm mission authorized.")
    else:
        logger.error("BFT FAILURE: Quorum not reached.")


if __name__ == "__main__":
    run_swarm_sim(num_drones=5, packet_loss=0.1, duration_s=15)
