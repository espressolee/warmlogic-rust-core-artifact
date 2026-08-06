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
import os
import time
from typing import Any, Dict

logger = logging.getLogger("BlackBox")


class BlackBox:
    """
    [Phase 69] The Black Box.
    An Append-Only, Cryptographically Linked Ledger of Thoughts.

    Structure:
    {
        "index": 0,
        "timestamp": 123456.789,
        "content": {...},
        "prev_hash": "000000...",
        "hash": "abc123..."
    }
    """

    def __init__(self, ledger_path: str = "data/audit/blackbox.jsonl"):
        self.ledger_path = ledger_path
        self.last_hash = "0" * 64  # Genesis hash
        self.index = 0

        # Ensure dir
        os.makedirs(os.path.dirname(ledger_path), exist_ok=True)

        # Recover integration
        self._recover_state()

    def _recover_state(self):
        """Reads the last line to recover chain state."""
        if not os.path.exists(self.ledger_path):
            return

        try:
            with open(self.ledger_path, "r") as f:
                last_line = None
                for line in f:
                    if line.strip():
                        last_line = line

                if last_line:
                    entry = json.loads(last_line)
                    self.last_hash = entry.get("hash", self.last_hash)
                    self.index = entry.get("index", 0) + 1
        except Exception as e:
            logger.error(f"[BlackBox] Recovery failed: {e}")

    def log(self, content: Dict[str, Any]):
        """Logs a thought/action with a cryptographic seal."""
        timestamp = time.time()

        # Canonicalize content for consistent hashing
        content_str = json.dumps(content, sort_keys=True)

        # Calculate Hash: SHA256(index + timestamp + prev_hash + content)
        payload = f"{self.index}{timestamp}{self.last_hash}{content_str}".encode()
        current_hash = hashlib.sha256(payload).hexdigest()

        entry = {
            "index": self.index,
            "timestamp": timestamp,
            "content": content,
            "prev_hash": self.last_hash,
            "hash": current_hash,
        }

        # Append to file
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Update state
        self.last_hash = current_hash
        self.index += 1

        logger.debug(
            f"⛓️ [BlackBox] Sealed Entry #{self.index - 1} (Hash: {current_hash[:8]}...)"
        )

    def verify_integrity(self) -> bool:
        """Audits the entire chain for tampering."""
        logger.info("[BlackBox] Auditing ledger integrity...")
        if not os.path.exists(self.ledger_path):
            return True

        expected_prev_hash = "0" * 64

        try:
            with open(self.ledger_path, "r") as f:
                for i, line in enumerate(f):
                    if not line.strip():
                        continue

                    entry = json.loads(line)

                    # 1. Verify Link
                    if entry["prev_hash"] != expected_prev_hash:
                        logger.critical(
                            f"🚨 [BlackBox] BROKEN CHAIN at Index {entry['index']}. PrevHash mismatch."
                        )
                        return False

                    # 2. Verify Content Integrity
                    content_str = json.dumps(entry["content"], sort_keys=True)
                    payload = f"{entry['index']}{entry['timestamp']}{entry['prev_hash']}{content_str}".encode()
                    recalc_hash = hashlib.sha256(payload).hexdigest()

                    if recalc_hash != entry["hash"]:
                        logger.critical(
                            f"🚨 [BlackBox] TAMPER DETECTED at Index {entry['index']}. Hash mismatch."
                        )
                        return False

                    expected_prev_hash = entry["hash"]

            logger.info(f"[BlackBox] Ledger Valid. Verified {i + 1} blocks.")
            return True

        except Exception as e:
            logger.error(f"[BlackBox] Audit failed: {e}")
            return False
