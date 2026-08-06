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
from typing import Dict, List

from warm_logic.kernel import rust_loader
from warm_logic.kernel.sys.persistence import SovereignStore

from .protocol import SovereignMessage


class SocialStore:
    """
    Manages a persistent, verified feed of Sovereign Messages.
    Wraps the SovereignStore (Sled/SQLite) for unified kernel durability.
    """

    def __init__(self, db_path: str = "data/social.db") -> None:
        # Resolve path relative to package root for consistency
        self._db = SovereignStore(db_path=db_path)

        # Integration with Rust Kernel for Verification
        rs = rust_loader.load_rust_core()
        self._verify_func = getattr(rs, "verify", None)

        self._messages: List[SovereignMessage] = []
        self._seen_signatures: set = set()

        # Recover from DB
        self._recover_messages()

    @property
    def store(self) -> SovereignStore:
        return self._db

    def _recover_messages(self) -> None:
        """Loads all valid messages from centralized persistence."""
        # Use unified metadata store for social messages
        stored_items = self._db.get_all_meta()
        for key, json_val in stored_items:
            # Simple heuristic: only recover keys that look like signatures (e.g. hex)
            if len(key) >= 64:
                try:
                    msg = SovereignMessage.from_json(json_val)
                    self._messages.append(msg)
                    self._seen_signatures.add(msg.signature)
                except Exception:
                    # Ignore non-message metadata
                    pass

        # Keep feed sorted
        self._messages.sort(key=lambda x: x.timestamp, reverse=True)

    def add_message(self, msg: SovereignMessage) -> bool:
        """
        Verifies a message and adds it to the persistent feed.
        """
        if msg.signature in self._seen_signatures:
            return False

        # Verify against the Rust Kernel
        is_valid = False
        if self._verify_func:
            is_valid = self._verify_func(msg.sender_id, msg.content, msg.signature)
        else:
            # In purely forensic mode without Rust, we might allow ingestion if signature is present
            is_valid = bool(msg.signature)

        if is_valid:
            # 1. Persist to Unified Store (Sled if avail, else SQLite)
            self._db.set_meta(msg.signature, msg.to_json())

            # 2. Add to memory feed
            self._messages.append(msg)
            self._seen_signatures.add(msg.signature)
            self._messages.sort(key=lambda x: x.timestamp, reverse=True)
            return True
        return False

    def get_feed(self, limit: int = 50) -> List[Dict]:
        return [
            {
                "sender_id": m.sender_id,
                "content": m.content,
                "signature": m.signature,
                "timestamp": m.timestamp,
                "id_hash": self._get_short_hash(m.sender_id),  # For UI avatars
            }
            for m in self._messages[:limit]
        ]

    def _get_short_hash(self, text: str) -> str:
        """Simple deterministic hash for UI pseudo-avatars (not for security)."""
        import hashlib

        # usedforsecurity=False: This is for UI display only, not cryptographic security
        return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:8]
