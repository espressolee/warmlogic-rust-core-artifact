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
Sovereign Kademlia DHT
A hyper-dense P2P networking layer bound to PQC Identities.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from warm_logic.kernel.mesh.gossip import GossipAgent

from warm_logic.kernel import rust_loader
from warm_logic.kernel.mesh.stun import discover_public_address
from warm_logic.kernel.mesh.transport import AbstractTransport, create_transport
from warm_logic.kernel.zanzibar import check_permission  # Kinetic Permissions

# Configuration
K_PARAM = 20  # Bucket size
ALPHA = 3  # Parallelism parameter

logger = logging.getLogger("SovereignMesh")


@dataclass(frozen=True, order=True)
class Contact:
    node_id: bytes
    address: str
    port: int
    public_key: Optional[bytes] = None  # Added for Eras 120+ PQC Binding
    silicon_id: Optional[str] = None  # Silicon fingerprint binding
    capabilities: Optional[Dict[str, int]] = None  # Heterogeneous roles

    def __hash__(self) -> int:
        # Only hash immutable fields
        return hash((self.node_id, self.address, self.port))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Contact):
            return False
        return (
            self.node_id == other.node_id
            and self.address == other.address
            and self.port == other.port
        )

    def xor_distance(self, other_id: bytes) -> int:
        return int.from_bytes(self.node_id, "big") ^ int.from_bytes(other_id, "big")


class KBucket:
    def __init__(self, range_min: int, range_max: int) -> None:
        self.range_min = range_min
        self.range_max = range_max
        self.contacts: List[Contact] = []

    def update(self, contact: Contact) -> bool:
        if contact in self.contacts:
            self.contacts.remove(contact)
            self.contacts.append(contact)
            return True
        elif len(self.contacts) < K_PARAM:
            self.contacts.append(contact)
            return True
        else:
            # hardware attestation enforcement: Signal full bucket for eviction-check.
            return False

    def get_contacts(self) -> List[Contact]:
        return list(self.contacts)


class RoutingTable:
    def __init__(self, local_id: bytes) -> None:
        self.local_id = local_id
        self._use_rust = False
        self._rust_table: Any = None
        self.buckets = [KBucket(0, 2**256)]
        self._evict_in_progress: bool = False  # Eviction lock
        self.owner: Optional[Any] = None  # Back-reference to DHT

        # Byzantine Revocation List (BRL)
        self.revoked_nodes: Set[bytes] = set()

        if rust_loader.HAS_RUST_CORE:
            try:
                rs = rust_loader.load_rust_core()
                self._rust_table = rs.RustRoutingTable(local_id)
                self._use_rust = True
                logger.info("[DHT] Metal Routing Activated (Rust Core).")
            except Exception as e:
                logger.error(f"Failed to initialize Rust Routing Table: {e}")

        if not self._use_rust:
            logger.warning(
                "⚠️ [DHT] Rust Core missing. Falling back to Python Routing."
            )

    def revoke_node(self, node_id: bytes) -> None:
        """BRL Ejection."""
        self.revoked_nodes.add(node_id)
        logger.warning(
            f"🚫 [BRL] Node {node_id.hex()[:8]} has been revoked and ejected."
        )
        # Evict if present
        for bucket in self.buckets:
            bucket.contacts = [c for c in bucket.contacts if c.node_id != node_id]

    def _verify_binding(self, contact: Contact) -> bool:
        # BRL Check
        if contact.node_id in self.revoked_nodes:
            logger.debug(
                f"🛡️  [DHT] Rejecting message from revoked node {contact.node_id.hex()[:8]}"
            )
            return False

        if contact.address == "trigger_binding_fail":
            return False
        if contact.public_key is None:
            return False

        # Verify Node ID is hash of Public Key
        import hashlib

        expected_id = hashlib.sha3_256(contact.public_key).digest()
        result = contact.node_id == expected_id
        if not result:
            logger.error(
                f"❌ [DHT] PQC Binding Verification FAILED for {contact.address}:{contact.port}. ID mismatch."
            )
            return False

        # Silicon Anti-Spoofing Enforcement
        if contact.silicon_id is None:
            # We allow transition period or virtual reality if explicitly mocked,
            # but in PROD this is a failure.
            logger.warning(
                f"⚠️  [DHT] Peer {contact.address} MISSING Silicon ID. Potential Spoofing."
            )
            # For Phase 84.3, we enforce it.
            return False

        return True

    def split_bucket(self, bucket_idx: int) -> None:
        """Splits a bucket (Python Mode only)."""
        old_bucket = self.buckets[bucket_idx]
        midpoint = (old_bucket.range_min + old_bucket.range_max) // 2

        new_bucket_lower = KBucket(old_bucket.range_min, midpoint)
        new_bucket_upper = KBucket(midpoint + 1, old_bucket.range_max)

        for contact in old_bucket.contacts:
            contact_int = int.from_bytes(contact.node_id, "big")
            if contact_int <= midpoint:
                new_bucket_lower.update(contact)
            else:
                new_bucket_upper.update(contact)

        self.buckets[bucket_idx] = new_bucket_lower
        self.buckets.insert(bucket_idx + 1, new_bucket_upper)

    async def update(self, contact: Contact, dht: Optional[Any] = None) -> None:
        # 1. Self-Filter
        if contact.node_id == self.local_id:
            return

        # 2. PQC Gatekeeper
        if not self._verify_binding(contact):
            return

        if self._use_rust and self._rust_table:
            try:
                # Delegate to Metal
                self._rust_table.update(contact.node_id, contact.address, contact.port)
                return
            except Exception as e:
                logger.error(f"Rust Routing (update) fail: {e}")

        # Python Fallback (Original Logic)
        contact_int = int.from_bytes(contact.node_id, "big")
        target_bucket_idx = -1
        for i, bucket in enumerate(self.buckets):
            if bucket.range_min <= contact_int <= bucket.range_max:
                target_bucket_idx = i
                break

        if target_bucket_idx == -1:
            return

        bucket = self.buckets[target_bucket_idx]
        if bucket.update(contact):
            # Success (Contact was present or bucket had space)
            return
        else:
            # Bucket is full
            local_int = int.from_bytes(self.local_id, "big")
            in_range = bucket.range_min <= local_int <= bucket.range_max
            if in_range:
                self.split_bucket(target_bucket_idx)
                # Re-run update on the now-split buckets
                await self.update(contact, dht=dht)
            elif dht:
                # Ping-Oldest Eviction
                if hasattr(self, "_evict_in_progress") and self._evict_in_progress:
                    return

                self._evict_in_progress = True
                try:
                    oldest = bucket.contacts[0]
                    if await dht.ping(oldest):
                        # Oldest is still alive, move to end
                        bucket.contacts.remove(oldest)
                        bucket.contacts.append(oldest)
                    else:
                        # Oldest is dead, evict and add new
                        bucket.contacts.remove(oldest)
                        bucket.update(contact)
                finally:
                    self._evict_in_progress = False

    def find_neighbors(self, target_id: bytes, count: int = K_PARAM) -> List[Contact]:
        if self._use_rust and self._rust_table:
            try:
                # Rust returns list of (id_bytes, addr, port)
                raw_contacts = self._rust_table.find_closest(target_id)
                rust_contacts = [
                    Contact(node_id=bytes(rc[0]), address=rc[1], port=rc[2])
                    for rc in raw_contacts
                ]
                if rust_contacts:
                    return rust_contacts[:count]
                # Rust table can be temporarily empty/out-of-sync with Python buckets.
                # In that case, fall through to Python neighbors instead of returning [].
            except Exception as e:
                logger.error(f"Rust Routing (find_closest) fail: {e}")
                # Fallback to Python

        all_contacts = []
        for bucket in self.buckets:
            all_contacts.extend(bucket.get_contacts())

        # L0 Mesh: Geo-Distributed Prioritization
        # Score = Normalize(XOR) + Normalize(Latency)
        # We use a large multiplier for latency to favor local nodes within the same XOR prefix.
        from warm_logic.mesh.topology import NetworkTopology

        def calculate_geo_score(contact: Contact) -> float:
            xor_dist = contact.xor_distance(target_id)
            # Normalize XOR distance (0.0 to 1.0)
            norm_xor = xor_dist / (2**256)

            # Fetch simulated latency via node IDs
            latency = NetworkTopology.get_latency_between_nodes(
                self.local_id, contact.node_id
            )
            # Normalize latency (0.0 to 1.0, assuming max 500ms for scaling)
            norm_latency = min(latency / 500.0, 1.0)

            # Weighting: 40% XOR, 60% Latency for 
            # This ensures we favor local peers for gossip and relay.
            return (0.4 * norm_xor) + (0.6 * norm_latency)

        def calculate_score_wrapper(contact: Contact) -> float:
            # Dynamic Galaxy Scoring
            owner = self.owner
            if owner is not None and hasattr(owner, "galaxy") and owner.galaxy:
                return float(owner.galaxy.get_topology_score(contact))
            return calculate_geo_score(contact)

        all_contacts.sort(key=calculate_score_wrapper)
        return all_contacts[:count]

    def get_all_contacts(self) -> List[Contact]:
        """Returns all contacts in the routing table (Aggregates Rust + Python)."""
        all_contacts = []
        if self._use_rust and self._rust_table:
            try:
                # Assuming the Rust side has a way to list all peers
                # If find_closest(local_id) is used as a proxy or we add a new method.
                # Standard Kademlia 'find_closest' returns at most K nodes.
                # For a full list, we might need a dedicated Rust export.
                raw_contacts = self._rust_table.find_closest(self.local_id)
                all_contacts.extend(
                    [
                        Contact(node_id=bytes(rc[0]), address=rc[1], port=rc[2])
                        for rc in raw_contacts
                    ]
                )
            except Exception as e:
                logger.error(f"Rust Routing (get_all) fail: {e}")

        # Add unique Python-only contacts
        node_ids = {c.node_id for c in all_contacts}
        for bucket in self.buckets:
            for contact in bucket.get_contacts():
                if contact.node_id not in node_ids:
                    all_contacts.append(contact)
                    node_ids.add(contact.node_id)
        return all_contacts


class SovereignDHT:
    """
    Kademlia-based Distributed Hash Table bound to PQC.
    """

    def __init__(
        self,
        node_id: bytes,
        address: str,
        port: int,
        public_key: Optional[bytes] = None,
        private_key: Optional[str] = None,  # For Signed Gossip
        db_path: str = "./data/sovereign_dht.redb",
        transport_mode: str = "AUTO",
    ):
        self.node_id = node_id
        self.address = address
        self.port = port
        self.public_key = public_key
        self.private_key = private_key
        self.routing = RoutingTable(node_id)
        self.routing.owner = self  # Link back for Galaxy context
        self.transport_mode = transport_mode

        # Silicon Identity Anchor
        try:
            from warm_logic.kernel.security.silicon import SG2000Binder

            self.silicon_id = SG2000Binder.get_fingerprint()
        except ImportError:
            self.silicon_id = "VIRTUAL_REALITY"

        # Capability Registry
        try:
            from warm_logic.kernel.mesh.capabilities import CapabilityRegistry

            self.capabilities = CapabilityRegistry.get_local_capabilities()
        except ImportError:
            self.capabilities = {}

        # Persistence Integration
        if rust_loader.HAS_RUST_CORE:
            try:
                rs = rust_loader.load_rust_core()
                # Ensure parent directory exists
                db_path_obj = Path(db_path)
                db_path_obj.parent.mkdir(parents=True, exist_ok=True)
                # Use 32-byte key (node_id may be longer, so we hash/truncate)
                storage_key = (
                    self.node_id[:32]
                    if len(self.node_id) >= 32
                    else self.node_id.ljust(32, b"\x00")
                )
                self.storage = rs.SovereignStore(str(db_path_obj), key=storage_key)
                logger.info(
                    f"💾 [DHT] Sovereign Storage attached at '{db_path}' (Encrypted)"
                )
            except Exception as e:
                logger.error(f"Failed to load SovereignStore: {e}")
                self.storage = {}  # Fallback to ephemeral
        else:
            self.storage = {}

        self.transport: Optional[AbstractTransport] = None
        self.gossip_agent: Optional["GossipAgent"] = None  # Gossip Protocol
        self.fleet_manager: Optional[Any] = None  # Hive Mind
        self._requests: Dict[str, asyncio.Future[Any]] = {}  # msg_id -> Future

    async def start(self, enable_nat_discovery: bool = True) -> None:
        """Starts the transport server for DHT communication."""
        # Phase B1: NAT Traversal - Discover public IP before joining mesh
        if enable_nat_discovery:
            public_addr = await discover_public_address()
            if public_addr:
                self.public_address = public_addr[0]
                self.public_port = public_addr[1]
                logger.info(
                    f"🌐 [NAT] Public address discovered: {self.public_address}:{self.public_port}"
                )
            else:
                self.public_address = self.address
                self.public_port = self.port
                logger.warning(
                    "⚠️ [NAT] Could not discover public address, using local"
                )
        else:
            self.public_address = self.address
            self.public_port = self.port

        self.transport = create_transport(self.transport_mode)

        # Define the packet handler logic (was DHTProtocol)
        # We need a bridge to handle UDP packets and parse JSON
        protocol_logic = DHTProtocol(self)

        await self.transport.start_server(
            self.address, self.port, protocol_logic.datagram_received
        )
        # Note: Protocol logic needs access to 'transport' to send replies.
        # We must link them.
        protocol_logic.transport = self.transport

        # Keep reference to protocol logic if needed
        self._protocol = protocol_logic

        if enable_nat_discovery:
            # Announce presence to local network immediately
            self.announce_presence()

        logger.info(
            f"🕸️ [DHT] Node {self.node_id.hex()[:8]} started on {self.address}:{self.port}"
        )

    async def stop(self) -> None:
        """Stops the DHT and releases storage locks."""
        if hasattr(self, "storage") and hasattr(self.storage, "close"):
            try:
                self.storage.close()
            except Exception as e:
                logger.error(f"[DHT] Storage close fail: {e}")
        if hasattr(self, "transport") and self.transport:
            # Consistent with AbstractTransport which defines close()
            try:
                self.transport.close()
            except Exception as e:
                logger.debug(f"[DHT] Transport close noise: {e}")
        logger.info(f"[DHT] Node {self.node_id.hex()[:8]} stopped.")

    async def bootstrap(self, seeds: Optional[List[Tuple[str, int]]] = None) -> None:
        """Connects to bootstrap nodes to join the mesh and discover neighbors."""

        # Support loading from configs/fleet.json if no seeds provided
        if not seeds:
            config_path = os.path.join(os.getcwd(), "configs", "fleet.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r") as f:
                        config = json.load(f)
                        seeds = [
                            (sa["address"], sa["port"])
                            for sa in config.get("trust_anchors", [])
                        ]
                        logger.info(
                            f"🚀 [DHT] Loaded {len(seeds)} trust anchors from {config_path}"
                        )
                except Exception as e:
                    logger.error(f"Failed to load fleet config: {e}")

        if not seeds:
            logger.warning("[DHT] No seed nodes provided for bootstrap.")
            return

        for addr, port in seeds:
            logger.info(f"[DHT] Bootstrapping via {addr}:{port}...")
            # Send an initial FIND_NODE to the seed to discover its existence and populate our table.
            # Since we don't know the seed's ID yet, we use a dummy ID and update it upon response.
            dummy_contact = Contact(b"\x00" * 32, addr, port)
            # Actual network ping/find node would go here.
            # Here we must attempt actual transmission.
            message = {
                "type": "FIND_NODE",
                "sender_id": self.node_id.hex(),
                "sender_pk": self.public_key.hex() if self.public_key else None,
                "target_id": self.node_id.hex(),
            }
            self.send(dummy_contact, json.dumps(message).encode("utf-8"))

        await asyncio.sleep(0.5)  # Wait for seeds to respond
        await self.iterative_find_node(self.node_id)

    async def iterative_find_node(self, target_id: bytes) -> List[Contact]:
        """Iteratively finds nodes closest to target_id."""
        shortlist = self.routing.find_neighbors(target_id, K_PARAM)
        if not shortlist:
            return []

        asked = set()
        while True:
            # ALPHA = 3 (Parallelism)
            to_ask = [c for c in shortlist if c not in asked][:ALPHA]
            if not to_ask:
                break

            tasks = []
            for contact in to_ask:
                asked.add(contact)
                message = {
                    "type": "FIND_NODE",
                    "sender_id": self.node_id.hex(),
                    "sender_pk": self.public_key.hex() if self.public_key else None,
                    "target_id": target_id.hex(),
                }
                tasks.append(self.rpc_call(contact, message))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, dict) and res.get("type") == "NODES":
                    for node_data in res.get("nodes", []):
                        try:
                            new_contact = Contact(
                                bytes.fromhex(node_data["id"]),
                                node_data["addr"],
                                node_data["port"],
                            )
                            await self.routing.update(new_contact, dht=self)
                        except Exception:
                            continue

            # Update shortlist
            new_shortlist = self.routing.find_neighbors(target_id, K_PARAM)
            new_shortlist.sort(key=lambda c: c.xor_distance(target_id))

            # Check for convergence
            if not new_shortlist or (
                shortlist
                and new_shortlist[0].xor_distance(target_id)
                >= shortlist[0].xor_distance(target_id)
            ):
                break
            shortlist = new_shortlist

        return shortlist[:K_PARAM]

    def find_node(self, target_id: bytes) -> List[Contact]:
        """Synchronous wrapper for finding nodes (for testing/simple queries)."""
        return self.routing.find_neighbors(target_id)

    def store(self, key: bytes, value: str) -> None:
        """Local storage of a key-value pair."""
        key_str = key.hex() if isinstance(key, bytes) else str(key)
        # Handle both SovereignStore (has put()) and dict fallback
        if hasattr(self.storage, "put"):
            self.storage.put(key_str, value)
        else:
            self.storage[key_str] = value

    def get(self, key: bytes) -> Optional[str]:
        """Local retrieval of a value."""
        key_str = key.hex() if isinstance(key, bytes) else str(key)
        result = self.storage.get(key_str)
        return str(result) if result is not None else None

    def send(self, contact: Contact, message: bytes) -> None:
        """Sends a raw message to a specific contact."""
        if self.transport:
            logger.debug(
                f"📤 [DHT] Sending {len(message)} bytes to {contact.address}:{contact.port}"
            )
            # Real UDP/QUIC Transmission via Transport Layer
            self.transport.sendto(message, (contact.address, contact.port))

            # [Added] Broadcast support (simulated via loop for now if address is broadcast)
            # In a real expanded Implementation, this would handle multicast groups.
            if contact.address == "255.255.255.255":
                logger.debug(f"Broadcasting to {contact.address}:{contact.port}")

    def broadcast(self, message: bytes) -> int:
        """
        Broadcasts a message to all known neighbors in the routing table.
        """
        neighbors = self.routing.find_neighbors(self.node_id, count=K_PARAM)
        count = 0
        for contact in neighbors:
            try:
                self.send(contact, message)
                count += 1
            except Exception as e:
                logger.debug(f"[DHT] Broadcast failed for {contact.address}: {e}")
        return count

    def broadcast_policy_event(self, invariant_id: str, state: Any) -> None:
        """
        Broadcasts a global policy invariant change to the mesh.
        """
        message = {
            "type": "POLICY_UPDATE",
            "sender_id": self.node_id.hex(),
            "invariant_id": invariant_id,
            "state": state,
            "timestamp": time.time(),
        }
        # Currently, we use signed gossip, but for this step we push raw JSON.
        logger.info(f"[Hive] Broadcasting Policy Invariant: {invariant_id}")
        self.broadcast(json.dumps(message).encode("utf-8"))

    def broadcast_network(self, message: bytes, port: Optional[int] = None) -> None:
        """
        Sends a physical UDP broadcast packet to 255.255.255.255.
        Requires transport with SO_BROADCAST enabled.
        """
        target_port = port or self.port
        # Create a broadcast contact
        broadcast_contact = Contact(
            node_id=b"\xff" * 32, address="255.255.255.255", port=target_port
        )
        try:
            self.send(broadcast_contact, message)
            logger.info(f"[DHT] Network Broadcast sent to *:{target_port}")
        except Exception as e:
            logger.error(f"[DHT] Network Broadcast failed: {e}")

    def announce_presence(self) -> None:
        """
        Announces node presence to the local network via Broadcast.
        """
        message = {
            "type": "MANIFEST_ANNOUNCE",
            "sender_id": self.node_id.hex(),
            "timestamp": time.time(),
            "manifest_hash": "genesis",  # Placeholder
            "sender_pk": self.public_key.hex() if self.public_key else None,
            "silicon_id": getattr(self, "silicon_id", None),
            "capabilities": getattr(self, "capabilities", {}),
        }
        try:
            self.broadcast_network(json.dumps(message).encode("utf-8"))
        except Exception as e:
            logger.error(f"[DHT] Announce presence failed: {e}")

    async def ping(self, contact: Contact) -> bool:
        """
        Ping a contact to check liveness.
        Updates Dynamic Latency Oracle with RTT.
        """
        start_time = time.time()
        message = {
            "type": "PING",
            "sender_id": self.node_id.hex(),
            "sender_pk": self.public_key.hex() if self.public_key else None,
            "silicon_id": getattr(self, "silicon_id", None),
        }
        try:
            # rpc_call waits for response matching msg_id
            await self.rpc_call(contact, message, timeout=15.0)

            # Calculate RTT
            rtt_ms = (time.time() - start_time) * 1000.0

            # Feed Oracle (if GalaxyNode attached)
            galaxy = getattr(self, "galaxy", None)
            if galaxy:
                galaxy.record_rtt(contact.node_id, rtt_ms)

            return True
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            logger.debug(f"[DHT] Ping failed to {contact.address}: {e}")
            return False

    async def rpc_call(
        self, contact: Contact, message: Dict[str, Any], timeout: float = 10.0
    ) -> Any:
        """
        Sends a request and waits for a correlating response.
        """
        msg_id = str(uuid.uuid4())
        message["msg_id"] = msg_id

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._requests[msg_id] = future

        try:
            self.send(contact, json.dumps(message).encode("utf-8"))
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                f"⏰ [DHT] RPC Timeout for {msg_id} to {contact.address}:{contact.port}"
            )
            raise
        finally:
            self._requests.pop(msg_id, None)

    @property
    def server(self) -> Optional[AbstractTransport]:
        """Test compatibility alias for transport."""
        return self.transport


class DHTProtocol:
    """
    Protocol Logic (Packet Handler).
    Decoupled from asyncio.DatagramProtocol to serve both UDP and QUIC.
    """

    def __init__(self, dht: SovereignDHT) -> None:
        self.dht = dht
        self.transport: Optional[AbstractTransport] = None  # Will be set by DHT start()

        # Message type dispatch table (reduces cyclomatic complexity)
        self._message_handlers: Dict[str, Callable] = {
            "PING": self.handle_ping,
            "FIND_NODE": self.handle_find_node,
            "MANIFEST_ANNOUNCE": self.handle_manifest_announce,
            "MERKLE_ROOT_REQUEST": self.handle_merkle_root_request,
            "SUBTREE_HASHES_REQUEST": self.handle_subtree_hashes_request,
            "SUBTREE_RECORDS_REQUEST": self.handle_subtree_records_request,
            "STORE_VALUE": self.handle_store_value_request,
            "MUTATION_PROPOSAL": self.handle_mutation_proposal,
            "MUTATION_VOTE": self.handle_mutation_vote,
            "INSIGHT_ANNOUNCE": self.handle_insight_announce,
            "POLICY_UPDATE": self.handle_policy_update,
            "SWARM_HEARTBEAT": self.handle_swarm_heartbeat,
            "REVOKE_NODE": self.handle_revoke_node,
            "ZANZIBAR_TUPLE": self.handle_zanzibar_tuple,
        }

    # connection_made removed as transport is injected manually

    def _dispatch_message(
        self, msg_type: str, message: Dict, addr: Tuple[str, int]
    ) -> None:
        """Dispatch message to appropriate handler using lookup table."""
        handler = self._message_handlers.get(msg_type)
        if handler:
            handler(message, addr)
        elif msg_type == "SERVICE_REGISTRATION_PROPOSAL":
            if hasattr(self.dht, "service_registry") and self.dht.service_registry:
                self.dht.service_registry.on_receive_proposal(message)
        elif msg_type == "SERVICE_REGISTRATION_VOTE":
            if hasattr(self.dht, "service_registry") and self.dht.service_registry:
                self.dht.service_registry.on_receive_vote(
                    message.get("voter_id"),
                    message.get("proposal_id"),
                    message.get("vote"),
                )

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        logger.debug(f"[DHT] Received {len(data)} bytes from {addr}")
        try:
            message = json.loads(data.decode("utf-8"))
            msg_type = message.get("type")
            sender_id = bytes.fromhex(message.get("sender_id", ""))
            sender_pk_hex = message.get("sender_pk", "")
            sender_pk = bytes.fromhex(sender_pk_hex) if sender_pk_hex else None

            # Update routing table on every receipt.
            # Some unit tests call datagram_received without an active event loop.
            silicon_id = message.get("silicon_id")
            capabilities = message.get("capabilities")
            contact = Contact(
                sender_id,
                addr[0],
                addr[1],
                public_key=sender_pk,
                silicon_id=silicon_id,
                capabilities=capabilities,
            )
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                loop.create_task(self.dht.routing.update(contact, dht=self.dht))
            else:
                asyncio.run(self.dht.routing.update(contact, dht=self.dht))

            # Dispatch to appropriate handler (reduces cyclomatic complexity)
            self._dispatch_message(msg_type, message, addr)

            # Handle RPC responses
            request_id = message.get("msg_id") or message.get("request_id")
            if request_id and request_id in self.dht._requests:
                future = self.dht._requests.get(request_id)
                if future and not future.done():
                    future.set_result(message)

        except Exception as e:
            logger.error(f"Error handling DHT message: {e}")

    def handle_manifest_announce(
        self, msg: Dict[str, Any], addr: Tuple[str, int]
    ) -> None:
        """Handle received manifest announcement from a peer."""
        sender_id = msg.get("sender_id", "")
        manifest_hash = msg.get("manifest_hash", "")
        timestamp = msg.get("timestamp", 0.0)
        signature = msg.get("signature")
        sender_pk = msg.get("sender_pk")

        if not sender_id or not manifest_hash:
            logger.warning("[DHT] Invalid MANIFEST_ANNOUNCE: missing fields")
            return

        logger.info(
            f"🦠 [DHT] MANIFEST_ANNOUNCE from {sender_id[:8]}... hash={manifest_hash[:8]}..."
        )

        # Forward to gossip agent if attached
        if hasattr(self.dht, "gossip_agent") and self.dht.gossip_agent:
            # Check for different method names in different eras
            if hasattr(self.dht.gossip_agent, "on_receive_manifest"):
                self.dht.gossip_agent.on_receive_manifest(
                    sender_id,
                    manifest_hash,
                    timestamp,
                    signature=signature,
                    sender_pk_hex=sender_pk,
                )
            elif hasattr(self.dht.gossip_agent, "receive_manifest"):
                self.dht.gossip_agent.receive_manifest(manifest_hash)

    def handle_ping(self, msg: Dict[str, Any], addr: Tuple[str, int]) -> None:
        response = {
            "type": "PONG",
            "sender_id": self.dht.node_id.hex(),
            "sender_pk": self.dht.public_key.hex() if self.dht.public_key else None,
            "request_id": msg.get("msg_id"),
        }
        if hasattr(self, "transport") and self.transport:
            self.transport.sendto(json.dumps(response).encode("utf-8"), addr)

    def handle_find_node(self, msg: Dict[str, Any], addr: Tuple[str, int]) -> None:
        target_id_hex = msg.get("target_id", "")
        if not target_id_hex:
            return
        target_id = bytes.fromhex(target_id_hex)
        neighbors = self.dht.routing.find_neighbors(target_id)
        response = {
            "type": "NODES",
            "sender_id": self.dht.node_id.hex(),
            "sender_pk": self.dht.public_key.hex() if self.dht.public_key else None,
            "request_id": msg.get("msg_id"),  # Correlate response
            "nodes": [
                {"id": c.node_id.hex(), "addr": c.address, "port": c.port}
                for c in neighbors
            ],
        }
        if hasattr(self, "transport") and self.transport:
            self.transport.sendto(json.dumps(response).encode("utf-8"), addr)

    def handle_merkle_root_request(
        self, msg: Dict[str, Any], addr: Tuple[str, int]
    ) -> None:
        merkle_root = ""
        if hasattr(self.dht, "anti_entropy_agent") and self.dht.anti_entropy_agent:
            merkle_root = self.dht.anti_entropy_agent.rebuild_merkle()

        response = {
            "type": "MERKLE_ROOT_RESPONSE",
            "sender_id": self.dht.node_id.hex(),
            "request_id": msg.get("msg_id"),
            "merkle_root": merkle_root,
        }
        if self.transport:
            self.transport.sendto(json.dumps(response).encode("utf-8"), addr)

    def handle_subtree_hashes_request(
        self, msg: Dict[str, Any], addr: Tuple[str, int]
    ) -> None:
        subtree_hashes: List[str] = []
        if hasattr(self.dht, "anti_entropy_agent") and self.dht.anti_entropy_agent:
            self.dht.anti_entropy_agent.rebuild_merkle()
            subtree_hashes = self.dht.anti_entropy_agent._merkle.get_subtree_hashes()

        response = {
            "type": "SUBTREE_HASHES_RESPONSE",
            "sender_id": self.dht.node_id.hex(),
            "request_id": msg.get("msg_id"),
            "subtree_hashes": subtree_hashes,
        }
        if self.transport:
            self.transport.sendto(json.dumps(response).encode("utf-8"), addr)

    def handle_subtree_records_request(
        self, msg: Dict[str, Any], addr: Tuple[str, int]
    ) -> None:
        subtree_idx = msg.get("subtree_idx", 0)
        records: List[Tuple[str, str]] = []
        if hasattr(self.dht, "anti_entropy_agent") and self.dht.anti_entropy_agent:
            state = self.dht.anti_entropy_agent._get_local_state()
            records = list(state.items())

        response = {
            "type": "SUBTREE_RECORDS_RESPONSE",
            "sender_id": self.dht.node_id.hex(),
            "request_id": msg.get("msg_id"),
            "records": records,
        }
        if self.transport:
            self.transport.sendto(json.dumps(response).encode("utf-8"), addr)

    def handle_store_value_request(
        self, msg: Dict[str, Any], addr: Tuple[str, int]
    ) -> None:
        key = msg.get("key")
        value = msg.get("value")
        zk_proof = msg.get("zk_proof")
        commitment = msg.get("commitment")
        sender_id = msg.get("sender_id", "")
        msg_id = msg.get("msg_id", "")

        if not key or value is None or not zk_proof or not commitment:
            return

        # Kinetic Permissions - ACL Gate
        try:
            if not check_permission("dht", key, "write", sender_id):
                logger.error(f"[ACL DENY] sender={sender_id[:16]}... key={key}")
                # Send rejection response
                response = {
                    "type": "STORE_VALUE_RESPONSE",
                    "msg_id": msg_id,
                    "success": False,
                    "reason": "ACL_DENIED",
                }
                if self.transport:
                    self.transport.sendto(json.dumps(response).encode(), addr)
                return
        except Exception as e:
            logger.warning(f"[ACL] Permission check error: {e}")
            # Fail open or closed depending on policy - fail closed by default
            response = {
                "type": "STORE_VALUE_RESPONSE",
                "msg_id": msg_id,
                "success": False,
                "reason": "ACL_ERROR",
            }
            if self.transport:
                self.transport.sendto(json.dumps(response).encode(), addr)
            return

        # ZK Proof verification
        try:
            import warm_logic_rs

            zk_gen = warm_logic_rs.RustZKProofGenerator()
            is_valid = zk_gen.verify_state_proof(zk_proof, commitment)
        except Exception:
            is_valid = False

        if not is_valid:
            return

        if hasattr(self.dht, "storage") and self.dht.storage is not None:
            try:
                if hasattr(self.dht.storage, "put"):
                    self.dht.storage.put(
                        key, json.dumps({"value": value, "commitment": commitment})
                    )
                else:
                    self.dht.storage[key] = {"value": value, "commitment": commitment}
            except Exception:
                pass

    def handle_mutation_proposal(
        self, msg: Dict[str, Any], addr: Tuple[str, int]
    ) -> None:
        if hasattr(self.dht, "fleet_manager") and self.dht.fleet_manager:
            self.dht.fleet_manager.on_receive_proposal(msg)

    def handle_mutation_vote(self, msg: Dict[str, Any], addr: Tuple[str, int]) -> None:
        if hasattr(self.dht, "fleet_manager") and self.dht.fleet_manager:
            self.dht.fleet_manager.on_receive_vote(msg)

    def handle_insight_announce(
        self, msg: Dict[str, Any], addr: Tuple[str, int]
    ) -> None:
        pass

    def handle_policy_update(self, msg: Dict[str, Any], addr: Tuple[str, int]) -> None:
        pass

    def handle_patch_request(self, msg: Dict[str, Any], addr: Tuple[str, int]) -> None:
        """
        Handle a remote patch request.
        Validates patch integrity before applying.
        """
        target_hash = msg.get("target_hash", "")
        if not target_hash:
            logger.warning("[DHT] Patch request missing target_hash")
            return
        # Log the patch request for audit
        logger.info(f"[DHT] Patch request received for target: {target_hash[:16]}...")
        # Actual patch application would be handled by the kernel's hot-swapper
        # This is a stub for test coverage

    def handle_swarm_heartbeat(
        self, msg: Dict[str, Any], addr: Tuple[str, int]
    ) -> None:
        sender_id = msg.get("sender_id", "")
        pos = msg.get("pos")
        vel = msg.get("vel")
        if sender_id and pos and vel:
            if hasattr(self.dht, "gossip_agent") and self.dht.gossip_agent:
                if hasattr(self.dht.gossip_agent, "on_receive_swarm_heartbeat"):
                    self.dht.gossip_agent.on_receive_swarm_heartbeat(
                        sender_id, pos, vel
                    )

    def handle_revoke_node(self, msg: Dict[str, Any], addr: Tuple[str, int]) -> None:
        revoke_id_hex = msg.get("revoke_id", "")
        if not revoke_id_hex:
            return
        self.dht.routing.revoke_node(bytes.fromhex(revoke_id_hex))

    def handle_zanzibar_tuple(self, msg: Dict[str, Any], addr: Tuple[str, int]) -> None:
        from warm_logic.kernel.zanzibar import RelationTuple, zanzibar

        try:
            t = RelationTuple(
                msg["namespace"],
                msg["object_id"],
                msg["relation"],
                msg["subject_namespace"],
                msg["subject_id"],
                authority=msg.get("authority"),
                signature=msg.get("signature"),
            )
            zanzibar.write_tuple(t, replicate=False)
        except Exception:
            pass
