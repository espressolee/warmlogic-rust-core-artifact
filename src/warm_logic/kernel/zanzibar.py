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
import json  # Needed for serialization
import os
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional, Union

# Paths (Absolute Root Enforcement)
# File is at src/warm_logic/kernel/zanzibar.py -> parent.parent.parent.parent is root
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = os.environ.get(
    "SOVEREIGN_ZANZIBAR_DB", str(ROOT_DIR / "data" / "provenance" / "zanzibar.db")
)


@dataclass
class RelationTuple:
    namespace: str
    object_id: str
    relation: str
    subject_namespace: str
    subject_id: str
    subject_relation: Optional[str] = None  # For userset relations
    authority: Optional[str] = None  # Source of truth (DID)
    signature: Optional[str] = None  # PQC Signature (ML-DSA-65)


class ZanzibarEngine:
    """
    Lite implementation of Google Zanzibar's Relationship-Based Access Control.
    Enforces 'Inherited' permissions via graph expansion.
    """

    def __init__(self, db_path: Union[Path, str] = DB_PATH):
        self.db_path = Path(db_path)
        # Use check_same_thread=False for potential multi-threaded access, though not strictly needed for this example
        self.conn: Optional[sqlite3.Connection] = sqlite3.connect(
            self.db_path, check_same_thread=False
        )
        self._init_db()

    def close(self) -> None:
        conn = getattr(self, "conn", None)
        if conn is None:
            return
        try:
            conn.close()
        finally:
            self.conn = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _get_conn(self) -> sqlite3.Connection:
        """Returns the active connection or raises if closed."""
        if self.conn is None:
            raise RuntimeError("Database connection is closed")
        return self.conn

    def _init_db(self) -> None:
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._get_conn().execute("""
            CREATE TABLE IF NOT EXISTS relation_tuples (
                namespace TEXT,
                object_id TEXT,
                relation TEXT,
                subject_namespace TEXT,
                subject_id TEXT,
                subject_relation TEXT,
                authority TEXT,
                signature TEXT,
                PRIMARY KEY (namespace, object_id, relation, subject_namespace, subject_id, subject_relation)
            )
        """)
        self._get_conn().commit()

    def verify_signature(self, t: RelationTuple) -> bool:
        """
        Checks the signature marker (demonstration stub — not real PQC verification) of a relation tuple.
        """
        if not t.signature or not t.authority:
            return False

        # [Simulated PQC] In Phase 88, we check for 'ROOT_AUTHORITY' blessing
        if t.signature == "ROOT_AUTHORITY_SIG" and t.authority.startswith(
            "did:warm:root:"
        ):
            return True

        return False

    def write_tuple(
        self, t: RelationTuple, dht: Optional[Any] = None, replicate: bool = True
    ) -> bool:
        """
        Adds a relationship to the graph after PQC verification.
        If dht is provided and replicate=True, broadcasts to the mesh.
        """
        if not self.verify_signature(t):
            import logging

            logging.error(f"[Zanzibar] REJECTED unauthorized tuple: {t}")
            return False

        self._get_conn().execute(
            """
            INSERT OR REPLACE INTO relation_tuples
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                t.namespace,
                t.object_id,
                t.relation,
                t.subject_namespace,
                t.subject_id,
                t.subject_relation,
                t.authority,
                t.signature,
            ),
        )
        self._get_conn().commit()

        # Mesh Replication
        if replicate and dht:
            self._replicate_to_mesh(t, dht)

        return True

    def _replicate_to_mesh(self, t: RelationTuple, dht: Any) -> None:
        """Broadcasts the tuple to the swarm."""
        msg = asdict(t)
        msg["type"] = "ZANZIBAR_TUPLE"
        # We also need sender_id for the DHT message wrapper, but dht.broadcast handles wrapping usually?
        # dht.broadcast expects bytes.
        try:
            dht.broadcast(json.dumps(msg).encode("utf-8"))
        except Exception:
            # Avoid crashing storage if network fails
            pass

    def check(
        self,
        namespace: str,
        object_id: str,
        relation: str,
        subject_id: str,
        depth: int = 5,
    ) -> bool:
        """
        Interrogates the graph for a direct or inherited relationship.
        Zanzibar Style: 'Does <subject> have <relation> on <object>?'
        """
        if depth <= 0:
            return False

        # 1. Direct Check
        cursor = self._get_conn().execute(
            """
            SELECT 1 FROM relation_tuples
            WHERE namespace = ? AND object_id = ? AND relation = ?
            AND subject_namespace = 'user' AND subject_id = ?
        """,
            (namespace, object_id, relation, subject_id),
        )
        if cursor.fetchone():
            return True

        # 2. Transitive / Userset Check (Expansion)
        cursor = self._get_conn().execute(
            """
            SELECT subject_namespace, subject_id, subject_relation FROM relation_tuples
            WHERE namespace = ? AND object_id = ? AND relation = ?
        """,
            (namespace, object_id, relation),
        )

        candidates = cursor.fetchall()
        for sub_ns, sub_id, sub_rel in candidates:
            if sub_ns != "user":
                next_relation = sub_rel if sub_rel else relation
                if self.check(sub_ns, sub_id, next_relation, subject_id, depth - 1):
                    return True

        return False


# Global Engine Instance
zanzibar = ZanzibarEngine()


def check_permission(namespace: str, obj: str, rel: str, user: str) -> bool:
    return zanzibar.check(namespace, obj, rel, user)
