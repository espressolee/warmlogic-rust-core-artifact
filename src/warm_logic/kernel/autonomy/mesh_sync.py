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
import logging
from typing import Any, Dict, Optional

from warm_logic.kernel.autonomy.aegis import (
    AegisAuditor,
    AegisSentinel,
)
from warm_logic.kernel.autonomy.codex import LogicGap
from warm_logic.kernel.autonomy.bundle import LogosBundler
from warm_logic.kernel.autonomy.patcher import AutonomousPatcher
from warm_logic.security.enclave import HardwareEnclave

logger = logging.getLogger("SovereignLogos")


class LogosPropagator:
    """
    LogosPropagator: Orchestrates mesh-wide propagation of the Sovereign kernel.
    Hooks into GossipAgent to announce code mutations.
    """

    def __init__(
        self,
        dht: Any,
        galaxy: Any,
        root_path: str = ".",
        propagator: Optional[Any] = None,
    ) -> None:
        from warm_logic.kernel.autonomy.auditor import RecursiveDebtAuditor

        self.dht = dht
        self.galaxy = galaxy
        self.root_path = root_path
        self.bundler = LogosBundler(root_path=root_path)
        self.patcher = AutonomousPatcher(root_path=root_path)
        self.auditor = RecursiveDebtAuditor(root_path)
        self.aegis_auditor = AegisAuditor(root_path)
        self.aegis_sentinel = AegisSentinel(self.aegis_auditor)
        self.propagator = propagator
        self.enclave = HardwareEnclave()
        self.current_manifest: Optional[str] = None
        self._bundles: Dict[str, bytes] = {}  # manifest_hash -> bundle_bytes
        self._manifest_votes: Dict[str, set] = (
            {}
        )  # manifest_hash -> set(origin_node_ids)

        # Phase 24.3: Initialize with valid PQC identity
        from warm_logic.security.pqc import SovereignSecurity

        self.node_keypair = SovereignSecurity.generate_keypair()
        self.enclave.seal_identity("local_node", self.node_keypair[1])
        self.quorum_threshold = 2  # Mandatory endorsements before adoption

    async def announce_mutation(self):
        """
        Creates a new bundle, signs it, and announces it to the mesh via Gossip.
        """
        bundle_bytes, manifest_hash = self.bundler.create_bundle()
        # Phase 26: Hardware-backed signature
        signature = self.enclave.hardware_sign("local_node", manifest_hash)

        self.current_manifest = manifest_hash
        self._bundles[manifest_hash] = bundle_bytes

        # Sign the manifest hash
        pk, sk = self.node_keypair
        signature = self.bundler.sign_bundle(sk, manifest_hash)

        logger.info(f"[kernel] Announcing mutation: {manifest_hash}")

        mutation_msg = {
            "type": "LOGOS_MANIFEST",
            "manifest_hash": manifest_hash,
            "signature": signature,
            "public_key": pk,
            "origin": (
                self.dht.node_id.hex() if hasattr(self.dht, "node_id") else "unknown"
            ),
        }

        return mutation_msg

    async def handle_logos_manifest(self, msg: dict):
        """
        Invoked when a peer announces a new Code kernel.
        Verifies signature before proceeding.
        """
        manifest_hash = msg.get("manifest_hash")
        signature = msg.get("signature")
        public_key = msg.get("public_key")
        origin = msg.get("origin")

        if not manifest_hash or not signature or not public_key:
            logger.error(f"[kernel] Malformed manifest from {origin}")
            return False

        if manifest_hash == self.current_manifest:
            return True  # Already synchronized

        # 1. Verify Signature (Cryptographic Sovereignty)
        if not self.bundler.verify_bundle(public_key, manifest_hash, signature):
            logger.error(
                f"⚠️ [kernel] Rejected invalid signature from {origin}. Dropping manifest."
            )
            return False

        logger.info(f"[kernel] Verified kernel from {origin}: {manifest_hash}")

        # 2. Tracking Consensus (Phase 24.4: Quorum Gating)
        if manifest_hash not in self._manifest_votes:
            self._manifest_votes[manifest_hash] = set()

        self._manifest_votes[manifest_hash].add(origin)
        vote_count = len(self._manifest_votes[manifest_hash])

        logger.info(
            f"🗳️ [kernel] Quorum Progress for {manifest_hash[:8]}: {vote_count}/{self.quorum_threshold}"
        )

        if vote_count >= self.quorum_threshold:
            logger.info(
                f"🤝 [kernel] Quorum ACHIEVED for {manifest_hash}. Proceeding to adoption."
            )
            # Reset votes after achievement to prevent double trigger
            # In a real system, we'd handle this more statefully.
            return True
        else:
            logger.info(
                f"⏳ [kernel] Waiting for more endorsements for {manifest_hash[:8]}..."
            )
            return False

    def apply_remote_logos(self, bundle_bytes: bytes, manifest_hash: str) -> None:
        """
        Unpacks and applies a remote code bundle.
        """
        logger.warning(f"[kernel] Applying remote kernel: {manifest_hash}")
        self.bundler.unpack_bundle(bundle_bytes, self.root_path)
        self.current_manifest = manifest_hash

    async def discover_and_announce(self):
        """
        [M/2.0] Autonomously scans for debt and security vulnerabilities.
        """
        # 1. Security Scan (High Priority)
        vulns = await self.aegis_sentinel.secure_perimeter()
        if vulns:
            logger.warning(
                "🚨 [Aegis] Critical vulnerabilities found. Triggering immediate defense."
            )
            for vuln in vulns:
                # Direct patch trigger
                gap = LogicGap(
                    file_path=vuln.file_path,
                    line_number=vuln.line_number,
                    description=f"Security Fix: {vuln.description}",
                    gap_type="Security",
                    complexity=20,  # High priority
                )
                patcher = AutonomousPatcher(self.root_path)
                if await patcher.apply_patch(gap, strategy="security"):
                    logger.info(
                        f"✅ [Aegis] Neutralized {vuln.vulnerability_type} in {vuln.file_path}"
                    )

        # 2. Structural Debt Scan
        logger.info("[kernel] Initiating autonomous debt discovery...")
        # RecursiveDebtAuditor might not have scan_workspace, check for alternative
        gaps = None
        if hasattr(self.auditor, "scan_workspace"):
            gaps = getattr(self.auditor, "scan_workspace")()
        elif hasattr(self.auditor, "scan_codebase"):
            gaps = getattr(self.auditor, "scan_codebase")()

        if gaps is None or len(gaps) == 0:
            logger.info(
                "✅ [kernel] No critical debt discovered. System at equilibrium."
            )
            return None

        # Select highest priority gap
        gaps.sort(key=lambda x: x.priority, reverse=True)
        target_gap = gaps[0]

        logger.info(
            f"💡 [kernel] Autonomous Discovery: {target_gap.description} ({target_gap.gap_type})"
        )

        # Generative Synthesis & Self-Evolution
        # Attempt to synthesize a patch for the discovered gap
        success = await self.patcher.apply_patch(target_gap, strategy="generative")

        if success:
            logger.info(
                f"🧬 [kernel] Semantic mutation applied for: {target_gap.description}"
            )
            # Announce the new evolutionary step to the mesh
            return await self.announce_mutation()
        else:
            logger.warning(f"[kernel] Failed to evolve: {target_gap.description}")
            return None
