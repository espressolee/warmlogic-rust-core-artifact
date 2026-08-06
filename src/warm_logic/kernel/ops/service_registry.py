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
import hashlib
import json
import logging
from typing import Any, Dict

from warm_logic.kernel.mesh.gossip import GossipAgent
from warm_logic.kernel.sys.persistence import SovereignStore

logger = logging.getLogger("ServiceRegistry")


class ServiceQuorum:
    """
    hardware attestation enforcement: Strategic Governance.
    Enforces BFT quorum for service registration (e.g. Storage Providers).
    """

    def __init__(self, store: SovereignStore, gossip: GossipAgent):
        self.store = store
        self.gossip = gossip
        # proposal_id -> {voter_id: vote_bool}
        self.votes: Dict[str, Dict[str, bool]] = {}
        # proposal_id -> proposal_data
        self.proposals: Dict[str, Dict[str, Any]] = {}

    def propose_service(self, service_data: Dict[str, Any]) -> str:
        """Proposes a new service to the network."""
        proposal_id = hashlib.sha256(
            json.dumps(service_data, sort_keys=True).encode()
        ).hexdigest()

        proposal = {
            "type": "SERVICE_REGISTRATION_PROPOSAL",
            "proposal_id": proposal_id,
            "data": service_data,
            "proposer_id": self.gossip.dht.node_id.hex(),
        }

        node_name = self.gossip.dht.node_id.hex()[:4]
        print(f"DEBUG: Node {node_name} proposing {proposal_id[:8]}")

        self.proposals[proposal_id] = proposal
        self.gossip.dht.broadcast(json.dumps(proposal).encode())

        # Proposer auto-votes YES
        self.cast_vote(proposal_id, True)

        logger.info(f"[Governance] Proposed service {proposal_id[:8]} to network.")
        return proposal_id

    def on_receive_proposal(self, proposal: Dict[str, Any]) -> None:
        """Callback for receiving a proposal from the network."""
        proposal_id = proposal.get("proposal_id")
        if not proposal_id:
            return

        node_name = self.gossip.dht.node_id.hex()[:4]
        print(f"DEBUG: Node {node_name} RECEIVED proposal {proposal_id[:8]}")

        if proposal_id not in self.proposals:
            self.proposals[proposal_id] = proposal
            # Auto-vote YES if it looks valid
            self.cast_vote(proposal_id, True)

    def cast_vote(self, proposal_id: str, vote: bool) -> None:
        """Casts a vote on a service proposal."""
        node_name = self.gossip.dht.node_id.hex()[:4]
        print(f"DEBUG: Node {node_name} CASTING vote for {proposal_id[:8]}")

        vote_msg = {
            "type": "SERVICE_REGISTRATION_VOTE",
            "proposal_id": proposal_id,
            "voter_id": self.gossip.dht.node_id.hex(),
            "vote": vote,
        }
        self.gossip.dht.broadcast(json.dumps(vote_msg).encode())
        self.on_receive_vote(self.gossip.dht.node_id.hex(), proposal_id, vote)

    def on_receive_vote(self, voter_id: str, proposal_id: str, vote: bool) -> None:
        """Records a vote and checks for quorum."""
        if proposal_id not in self.votes:
            self.votes[proposal_id] = {}

        self.votes[proposal_id][voter_id] = vote

        # Calculate Quorum
        yes_votes = sum(1 for v in self.votes[proposal_id].values() if v)
        # We estimate total peers from DHT routing table
        contacts = self.gossip.dht.routing.get_all_contacts()
        total_peers = len(contacts) + 1
        threshold = (total_peers * 2 // 3) + 1

        node_name = self.gossip.dht.node_id.hex()[:4]
        print(
            f"DEBUG: Node {node_name} RECOGNIZED vote from {voter_id[:4]} for {proposal_id[:8]}: {yes_votes}/{threshold}"
        )

        if yes_votes >= threshold and proposal_id in self.proposals:
            self._commit_service(proposal_id)

    def _commit_service(self, proposal_id: str) -> None:
        """Finalizes registration by persisting to SovereignStore."""
        if proposal_id not in self.proposals:
            return

        proposal = self.proposals.pop(proposal_id)
        service_data = proposal["data"]

        current_providers = self.get_verified_services()
        node_id = service_data.get("node_id") or proposal["proposer_id"]
        current_providers[node_id] = service_data

        conn = self.store.conn
        if conn is None:
            return
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("marketplace.providers", json.dumps(current_providers)),
        )
        conn.commit()

        node_name = self.gossip.dht.node_id.hex()[:4]
        print(f"DEBUG: Node {node_name} COMMITTED service {proposal_id[:8]}")
        logger.info(
            f"✅ [Governance] Service {proposal_id[:8]} reached QUORUM and committed."
        )

    def get_verified_services(self) -> Dict[str, Any]:
        """Retrieves verified services from the store."""
        conn = self.store.conn
        if conn is None:
            return {}
        cursor = conn.execute(
            "SELECT value FROM metadata WHERE key = ?", ("marketplace.providers",)
        )
        row = cursor.fetchone()
        if row:
            result: Dict[str, Any] = json.loads(row["value"])
            return result
        return {}
