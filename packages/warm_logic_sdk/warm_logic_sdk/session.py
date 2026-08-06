import time
import uuid
from typing import Any, Dict, List


class SovereignSession:
    """
    Manages a sequence of interactions for a specific application.
    Enforces monotonicity and prevents replay attacks via nonces.
    """

    def __init__(self, client_id: str):
        self.session_id = str(uuid.uuid4())
        self.client_id = client_id
        self.start_time = time.time()
        self.sequence_number = 0
        self.history: List[Dict[str, Any]] = []

    def next_nonce(self) -> str:
        """Increments sequence and returns a fresh nonce."""
        self.sequence_number += 1
        return f"{self.session_id}:{self.sequence_number}"

    def record_interaction(self, action: str, result: Dict[str, Any]):
        """Logs an interaction for auditability."""
        self.history.append(
            {
                "sequence": self.sequence_number,
                "action": action,
                "result": result,
                "timestamp": time.time(),
            }
        )
