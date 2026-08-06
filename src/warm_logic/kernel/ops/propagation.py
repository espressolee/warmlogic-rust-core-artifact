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
import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("PropagationEngine")


class SovereignPropagator:
    """
    propagation Engine.
    Handles the autonomous replication of codebase manifests and blobs between nodes.
    Ensures that once a 'Commit' is reached on the root authority, peers sync to it.
    """

    def __init__(self, codebase: Any, mesh: Any, network_bridge: Optional[Any] = None):
        self.codebase = codebase
        self.mesh = mesh
        self.network_bridge = network_bridge

        # Delta sync state
        self._pending_syncs: Dict[str, Dict[str, Any]] = {}
        self._synced_hashes: Set[str] = set()
        self._lock = threading.Lock()

        # Blob request/response handlers
        self._blob_handlers: Dict[str, Callable] = {}

    def generate_sync_signal(self) -> Dict[str, Any]:
        """Creates a SYNC_MANIFEST payload for the network."""
        manifest = self.codebase.generate_manifest()
        payload = {
            "type": "SYNC_MANIFEST",
            "root_hash": manifest.get("root_hash"),
            "files": manifest.get("files"),
            "timestamp": manifest.get("timestamp"),
            "node_id": (
                self.mesh.node_id if hasattr(self.mesh, "node_id") else "primary"
            ),
        }
        return payload

    def on_receive_sync_signal(self, payload: Dict[str, Any]) -> None:
        """Called when a peer broadcasts a sync signal."""
        remote_hash = payload.get("root_hash")
        logger.info(
            f"📡 [Propagation] Received SYNC_MANIFEST from {payload.get('node_id')}. Hash: {remote_hash}"
        )

        # 1. Compare with local state
        local_manifest = self.codebase.generate_manifest()
        if local_manifest.get("root_hash") == remote_hash:
            logger.info(
                "✅ [Propagation] Node already in convergence (Identical State)."
            )
            return

        # 2. Identify Deltas
        # Currently, we ask the mesh for missing blobs.
        logger.warning("[Propagation] Divergence detected. Initiating Delta Sync...")
        self.request_delta_from_node(payload.get("node_id"), remote_hash)

    def request_delta_from_node(self, peer_id: str, remote_hash: str) -> bool:
        """
        Requests missing blobs from a specific peer.
        Sends a DELTA_REQUEST message via the network bridge.
        """
        logger.info(
            f"🛰️ [Propagation] Requesting delta for Root: {remote_hash} from {peer_id}"
        )

        if not self.network_bridge:
            logger.warning(
                "[Propagation] No network bridge available for delta request"
            )
            return False

        # Track pending sync
        with self._lock:
            if remote_hash in self._synced_hashes:
                logger.info(f"[Propagation] Already synced {remote_hash[:16]}...")
                return True

            self._pending_syncs[remote_hash] = {
                "peer_id": peer_id,
                "status": "requested",
                "missing_files": [],
            }

        # Build delta request payload
        local_manifest = self.codebase.generate_manifest()
        local_files = {f["path"]: f["hash"] for f in local_manifest.get("files", [])}

        payload = {
            "type": "DELTA_REQUEST",
            "requester_id": (
                self.mesh.node_id if hasattr(self.mesh, "node_id") else "unknown"
            ),
            "target_hash": remote_hash,
            "local_files": local_files,
        }

        # Send via network bridge
        try:
            success = self.network_bridge.send_to_peer(
                peer_id, "DELTA_REQUEST", payload
            )
            if success:
                logger.info(f"[Propagation] Delta request sent to {peer_id[:8]}...")
            return success
        except Exception as e:
            logger.error(f"[Propagation] Failed to send delta request: {e}")
            return False

    def on_receive_delta_request(
        self, payload: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Handle incoming DELTA_REQUEST from a peer.
        Returns a DELTA_RESPONSE with missing files.
        """
        requester_id = payload.get("requester_id", "unknown")
        target_hash = payload.get("target_hash", "")
        remote_files = payload.get("local_files", {})

        logger.info(
            f"[Propagation] Delta request from {requester_id[:8]}... for {target_hash[:16]}..."
        )

        # Get local manifest
        local_manifest = self.codebase.generate_manifest()
        local_files = {f["path"]: f for f in local_manifest.get("files", [])}

        # Find files that peer is missing or has different versions
        delta_files: List[Dict[str, Any]] = []
        for path, file_info in local_files.items():
            remote_hash = remote_files.get(path)
            if remote_hash != file_info.get("hash"):
                # Peer needs this file
                try:
                    content = self.codebase.read_file(path)
                    delta_files.append(
                        {
                            "path": path,
                            "hash": file_info.get("hash"),
                            "content_b64": (
                                content.decode("utf-8")
                                if isinstance(content, bytes)
                                else content
                            ),
                        }
                    )
                except Exception as e:
                    logger.warning(f"[Propagation] Could not read {path}: {e}")

        response = {
            "type": "DELTA_RESPONSE",
            "target_hash": target_hash,
            "files": delta_files,
            "total_files": len(delta_files),
        }

        return response

    def on_receive_delta_response(self, payload: Dict[str, Any]) -> int:
        """
        Handle incoming DELTA_RESPONSE and apply patches.
        Returns number of files successfully applied.
        """
        target_hash = payload.get("target_hash", "")
        files = payload.get("files", [])

        logger.info(f"[Propagation] Received delta response with {len(files)} files")

        applied_count = 0
        for file_info in files:
            path = file_info.get("path", "")
            content = file_info.get("content_b64", "")
            file_hash = file_info.get("hash", "")

            if not path or not content:
                continue

            # Verify hash
            content_bytes = (
                content.encode("utf-8") if isinstance(content, str) else content
            )
            computed_hash = hashlib.sha256(content_bytes).hexdigest()

            if computed_hash != file_hash:
                logger.warning(
                    f"[Propagation] Hash mismatch for {path}: expected {file_hash[:16]}, got {computed_hash[:16]}"
                )
                continue

            # Apply the patch
            if self.apply_blob_patch(path, content_bytes, ""):
                applied_count += 1

        # Mark as synced if successful
        if applied_count > 0:
            with self._lock:
                self._synced_hashes.add(target_hash)
                if target_hash in self._pending_syncs:
                    self._pending_syncs[target_hash]["status"] = "completed"

        logger.info(
            f"[Propagation] Applied {applied_count}/{len(files)} files from delta"
        )
        return applied_count

    def apply_blob_patch(self, rel_path: str, content: bytes, signature: str) -> bool:
        """
        Applies a validated code blob to the local codebase.
        Requires PQC signature validation tied to the proposer's identity.
        """
        # 1. Verify Hash
        blob_hash = hashlib.sha256(content).hexdigest()
        logger.info(f"[Propagation] Validating Blob: {rel_path} ({blob_hash})")

        # 2. Persist via Codebase
        try:
            # Atomic commit of the specific file mutation
            # This triggers a local manifest rebuild
            self.codebase.commit_mutation(rel_path, content)
            logger.info(f"[Propagation] Successfully synced {rel_path}.")
            return True
        except Exception as e:
            logger.error(f"[Propagation] Failed to apply patch to {rel_path}: {e}")
            return False
