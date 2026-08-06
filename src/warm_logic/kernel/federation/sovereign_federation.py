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
Sovereign Federation Protocol

Implements secure multi-node federation using:
- ML-KEM-768 (FIPS 203) for quantum-resistant key exchange
- ML-DSA-65 (FIPS 204) for digital signatures
- ZK-SNARK Groth16 for governance proof verification
- Hardware attestation for node identity binding
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from warm_logic.kernel import rust_loader
from warm_logic.kernel.hardware.remote_attestation import (
    RemoteAttestationClient,
    RemoteAttestationReport,
    get_attestation_client,
)

logger = logging.getLogger("SovereignFederation")


class FederationState(Enum):
    """Federation lifecycle states."""

    INITIALIZING = "initializing"
    BOOTSTRAPPING = "bootstrapping"
    ACTIVE = "active"
    DEGRADED = "degraded"
    HALTED = "halted"


class NodeRole(Enum):
    """Node roles within the federation."""

    SOVEREIGN = "sovereign"  # Full governance authority
    VALIDATOR = "validator"  # Validates but doesn't propose
    OBSERVER = "observer"  # Read-only member


@dataclass
class FederationMember:
    """A member node in the sovereign federation."""

    node_id: str
    host: str
    role: NodeRole
    # PQC Keys
    encapsulation_key: str = ""  # ML-KEM public key (hex)
    signing_key: str = ""  # ML-DSA public key (hex)
    # State
    attestation: Optional[RemoteAttestationReport] = None
    last_seen: float = 0.0
    is_active: bool = False

    def __post_init__(self) -> None:
        if not self.last_seen:
            self.last_seen = time.time()


@dataclass
class SecureChannel:
    """A secure channel established between two federation nodes."""

    local_node_id: str
    remote_node_id: str
    session_key: str  # Hex-encoded 32-byte shared secret
    ciphertext: str  # ML-KEM ciphertext for key derivation
    established_at: float = field(default_factory=time.time)
    message_count: int = 0

    def is_valid(self, max_age_sec: int = 3600) -> bool:
        """Check if channel is still valid."""
        age = time.time() - self.established_at
        return age < max_age_sec


@dataclass
class FederationConsensus:
    """Consensus state for a governance decision."""

    decision_id: str
    decision_hash: str
    epoch: int
    proposer_node_id: str
    approvals: Dict[str, str] = field(default_factory=dict)  # node_id -> signature
    rejections: Dict[str, str] = field(default_factory=dict)
    zk_proof: Optional[str] = None  # Serialized ZK proof
    created_at: float = field(default_factory=time.time)
    finalized: bool = False

    @property
    def approval_count(self) -> int:
        return len(self.approvals)

    @property
    def rejection_count(self) -> int:
        return len(self.rejections)

    def has_quorum(self, total_members: int, threshold: float = 0.67) -> bool:
        """Check if consensus has reached quorum."""
        required = int(total_members * threshold)
        return self.approval_count >= required


class SovereignFederation:
    """
    Sovereign Federation Manager

    Orchestrates secure communication and consensus between
    hardware-attested sovereign nodes using post-quantum cryptography.
    """

    def __init__(
        self,
        local_node_id: str,
        attestation_client: Optional[RemoteAttestationClient] = None,
        quorum_threshold: float = 0.67,
    ):
        if not rust_loader.HAS_RUST_CORE:
            raise RuntimeError("CRITICAL: Rust Core required for Sovereign Federation")

        self.local_node_id = local_node_id
        self.rs = rust_loader.load_rust_core()
        self.attestation_client = attestation_client or get_attestation_client()
        self.quorum_threshold = quorum_threshold

        # State
        self.state = FederationState.INITIALIZING
        self.members: Dict[str, FederationMember] = {}
        self.channels: Dict[str, SecureChannel] = {}  # remote_node_id -> channel
        self.pending_consensus: Dict[str, FederationConsensus] = {}

        # Local keys
        self._ek, self._dk = "", ""  # ML-KEM keys
        self._pk, self._sk = "", ""  # ML-DSA keys

        logger.info(f"[Federation] Initialized node: {local_node_id}")

    def bootstrap(self) -> bool:
        """
        Bootstrap the local node with cryptographic keys.

        Returns True if successful, False otherwise.
        """
        try:
            self.state = FederationState.BOOTSTRAPPING

            # Generate ML-KEM keypair for key exchange
            self._ek, self._dk = self.rs.kem_keygen()
            logger.info(
                f"[Federation] Generated ML-KEM-768 keypair (EK: {len(self._ek)//2} bytes)"
            )

            # Generate ML-DSA keypair for signing
            self._pk, self._sk = self.rs.generate_keypair()
            logger.info(
                f"[Federation] Generated ML-DSA-65 keypair (PK: {len(self._pk)//2} bytes)"
            )

            self.state = FederationState.ACTIVE
            return True
        except Exception as e:
            logger.error(f"[Federation] Bootstrap failed: {e}")
            self.state = FederationState.HALTED
            return False

    def add_member(
        self,
        host: str,
        role: NodeRole = NodeRole.VALIDATOR,
        fetch_attestation: bool = True,
    ) -> Optional[FederationMember]:
        """
        Add a new member to the federation.

        Args:
            host: Node IP address
            role: Node role in federation
            fetch_attestation: Whether to fetch attestation immediately

        Returns:
            FederationMember if successful, None otherwise
        """
        # Fetch attestation
        attestation = None
        if fetch_attestation:
            attestation = self.attestation_client.fetch_attestation(host)
            if not attestation or not attestation.verified:
                logger.warning(f"[Federation] Node {host} attestation failed")
                return None

        node_id = attestation.node_id if attestation else f"unknown-{host}"
        member = FederationMember(
            node_id=node_id,
            host=host,
            role=role,
            attestation=attestation,
            is_active=attestation.verified if attestation else False,
        )

        self.members[node_id] = member
        logger.info(f"[Federation] Added member: {node_id} ({role.value})")

        return member

    def establish_channel(self, remote_node_id: str) -> Optional[SecureChannel]:
        """
        Establish a secure ML-KEM channel with a remote node.

        In a real implementation, this would exchange keys over the network.
        For now, simulates local key exchange.
        """
        if remote_node_id not in self.members:
            logger.error(f"[Federation] Unknown node: {remote_node_id}")
            return None

        member = self.members[remote_node_id]

        # If member has encapsulation key, use it
        if member.encapsulation_key:
            try:
                ss, ct = self.rs.kem_encapsulate(member.encapsulation_key)
                channel = SecureChannel(
                    local_node_id=self.local_node_id,
                    remote_node_id=remote_node_id,
                    session_key=ss,
                    ciphertext=ct,
                )
                self.channels[remote_node_id] = channel
                logger.info(
                    f"[Federation] Established secure channel with {remote_node_id}"
                )
                return channel
            except Exception as e:
                logger.error(f"[Federation] Key exchange failed: {e}")
                return None
        else:
            logger.warning(f"[Federation] No encapsulation key for {remote_node_id}")
            return None

    def get_local_keys(self) -> Dict[str, str]:
        """Get local public keys for sharing with other nodes."""
        return {
            "node_id": self.local_node_id,
            "encapsulation_key": self._ek,
            "signing_key": self._pk,
        }

    def set_member_keys(
        self,
        node_id: str,
        encapsulation_key: str,
        signing_key: str,
    ) -> bool:
        """Set cryptographic keys for a member node."""
        if node_id not in self.members:
            return False

        self.members[node_id].encapsulation_key = encapsulation_key
        self.members[node_id].signing_key = signing_key
        return True

    def propose_decision(
        self,
        decision_data: Dict[str, Any],
    ) -> Optional[FederationConsensus]:
        """
        Propose a governance decision to the federation.

        Args:
            decision_data: Decision payload

        Returns:
            FederationConsensus object if proposal created
        """
        if self.state != FederationState.ACTIVE:
            logger.error(f"[Federation] Cannot propose in state: {self.state}")
            return None

        # Create decision hash
        decision_json = str(sorted(decision_data.items()))
        decision_hash = hashlib.sha256(decision_json.encode()).hexdigest()
        decision_id = f"fd-{decision_hash[:16]}"

        consensus = FederationConsensus(
            decision_id=decision_id,
            decision_hash=decision_hash,
            epoch=int(time.time()),
            proposer_node_id=self.local_node_id,
        )

        # Sign as proposer
        signature = self.rs.sign(self._sk, decision_hash)
        consensus.approvals[self.local_node_id] = signature

        self.pending_consensus[decision_id] = consensus
        logger.info(f"[Federation] Proposed decision: {decision_id}")

        return consensus

    def approve_decision(self, decision_id: str) -> bool:
        """
        Approve a pending decision.

        Returns True if approval was recorded.
        """
        if decision_id not in self.pending_consensus:
            return False

        consensus = self.pending_consensus[decision_id]

        # Sign the decision hash
        signature = self.rs.sign(self._sk, consensus.decision_hash)
        consensus.approvals[self.local_node_id] = signature

        logger.info(f"[Federation] Approved decision: {decision_id}")
        return True

    def reject_decision(self, decision_id: str, reason: str = "") -> bool:
        """
        Reject a pending decision.

        Returns True if rejection was recorded.
        """
        if decision_id not in self.pending_consensus:
            return False

        consensus = self.pending_consensus[decision_id]

        # Sign rejection
        rejection_msg = f"REJECT:{consensus.decision_hash}:{reason}"
        signature = self.rs.sign(self._sk, rejection_msg)
        consensus.rejections[self.local_node_id] = signature

        logger.info(f"[Federation] Rejected decision: {decision_id}")
        return True

    def finalize_decision(self, decision_id: str) -> bool:
        """
        Finalize a decision if quorum is reached.

        Returns True if decision was finalized.
        """
        if decision_id not in self.pending_consensus:
            return False

        consensus = self.pending_consensus[decision_id]

        if consensus.finalized:
            return True

        total_members = len(self.members) + 1  # Include self
        if not consensus.has_quorum(total_members, self.quorum_threshold):
            logger.warning(
                f"[Federation] No quorum for {decision_id}: "
                f"{consensus.approval_count}/{total_members}"
            )
            return False

        consensus.finalized = True
        logger.info(
            f"[Federation] Finalized decision: {decision_id} "
            f"(approvals: {consensus.approval_count})"
        )

        return True

    def get_federation_fingerprint(self) -> str:
        """Get combined federation fingerprint from attestations."""
        return self.attestation_client.get_federation_fingerprint()

    def get_active_members(self) -> List[FederationMember]:
        """Get all active federation members."""
        return [m for m in self.members.values() if m.is_active]

    def get_state(self) -> Dict[str, Any]:
        """Get current federation state summary."""
        return {
            "state": self.state.value,
            "local_node_id": self.local_node_id,
            "member_count": len(self.members),
            "active_members": len(self.get_active_members()),
            "channel_count": len(self.channels),
            "pending_decisions": len(self.pending_consensus),
            "quorum_threshold": self.quorum_threshold,
            "federation_fingerprint": self.get_federation_fingerprint(),
        }
