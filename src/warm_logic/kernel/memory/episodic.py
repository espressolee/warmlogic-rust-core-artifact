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
import json
import sqlite3
import time
import uuid
from contextlib import closing
from typing import Dict, List, Optional


class EpisodicStore:
    """
    [Phase 35.1] Long-Term Episodic Memory.
    Persists conversation history using SQLite.
    """

    def __init__(self, db_path: str = "warm_logic.db"):
        self.db_path = db_path
        self._init_db()
        self.session_id = str(uuid.uuid4())

    def _init_db(self):
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp REAL,
                    metadata TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_session ON episodes(session_id)"
            )

    def add_memory(self, role: str, content: str, metadata: Dict = None):
        """Save a single turn of conversation."""
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                "INSERT INTO episodes (session_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
                (
                    self.session_id,
                    role,
                    content,
                    time.time(),
                    json.dumps(metadata or {}),
                ),
            )

    def get_session_history(
        self, session_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict]:
        """Retrieve history for a specific session (or current)."""
        target_session = session_id or self.session_id
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT role, content FROM episodes WHERE session_id = ? ORDER BY id ASC LIMIT ?",
                (target_session, limit),
            )
            return [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]

    def get_last_conversation_summary(self) -> str:
        """Get a brief glimpse of the previous session."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            # Find the most recent session excluding the current one
            cursor = conn.execute(
                "SELECT DISTINCT session_id, MAX(timestamp) as last_active FROM episodes WHERE session_id != ? GROUP BY session_id ORDER BY last_active DESC LIMIT 1",
                (self.session_id,),
            )
            row = cursor.fetchone()
            if not row:
                return "No previous memories found."

            prev_session_id = row[0]
            last_active = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[1]))

            # Get last 3 messages from that session
            msgs = self.get_session_history(prev_session_id)[-3:]
            summary = f"Last Active: {last_active}\n"
            for m in msgs:
                summary += f"- {m['role']}: {m['content'][:50]}...\n"
            return summary
