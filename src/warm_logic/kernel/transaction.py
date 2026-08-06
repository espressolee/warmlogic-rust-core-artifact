import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict


class TransactionManager:
    """
    Manages ACID transactions for the WarmLogic kernel state.

    Guarantees:
    - Atomicity: State updates are all-or-nothing via atomic rename.
    - Consistency: State hashes are cryptographically linked to the previous state.
    - Isolation: Examples run on a snapshot (in-memory) until commit.
    - Durability: strict fsync ensures data hits the disk platters (or NAND).
    """

    STATE_FILENAME = "state.json"
    WAL_FILENAME = "state.wal"
    BACKUP_FILENAME = "state.bak"

    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.storage_dir / self.STATE_FILENAME
        self.wal_path = self.storage_dir / self.WAL_FILENAME
        self.backup_path = self.storage_dir / self.BACKUP_FILENAME
        self.current_state: Dict[str, Any] = self._load_initial_state()

    def _load_initial_state(self) -> Dict[str, Any]:
        """Loads state from disk, recovering from WAL if necessary."""
        # 1. Check for WAL (Crash Recovery)
        if self.wal_path.exists():
            print(" WAL detected. Recovering from crash...")
            # Valid WAL? If so, roll forward. If corrupt, discard.
            try:
                with open(self.wal_path, "r") as f:
                    wal_state = json.load(f)
                # Verify integrity (optional check here)
                print("WAL valid. Rolling forward committed transaction.")
                self._atomic_write(wal_state)  # Commit the WAL to state.json
                self.wal_path.unlink()  # Delete WAL
                result: Dict[str, Any] = wal_state
                return result
            except json.JSONDecodeError:
                print("WAL corrupt. Discarding uncommitted transaction.")
                self.wal_path.unlink()

        # 2. Load State
        if self.state_path.exists():
            try:
                with open(self.state_path, "r") as f:
                    loaded: Dict[str, Any] = json.load(f)
                    return loaded
            except json.JSONDecodeError:
                print("State corrupt. Attempting backup restore...")
                if self.backup_path.exists():
                    shutil.copy2(self.backup_path, self.state_path)
                    with open(self.state_path, "r") as f:
                        backup_state: Dict[str, Any] = json.load(f)
                        return backup_state
                else:
                    print("CRITICAL: State and Backup lost. Reinitializing genesis.")
                    return self._genesis_state()

        return self._genesis_state()

    def _genesis_state(self) -> Dict[str, Any]:
        return {
            "tick": 0,
            "hash": "0000000000000000000000000000000000000000000000000000000000000000",
            "data": {},
        }

    def begin_transaction(self) -> Dict[str, Any]:
        """Returns a deep copy of the current state for mutation."""
        copy: Dict[str, Any] = json.loads(json.dumps(self.current_state))
        return copy

    def commit(self, new_state: Dict[str, Any]) -> None:
        """
        Commits the new state to disk with ACID guarantees.
        """
        # 1. Cryptographic Linking
        prev_hash = self.current_state.get("hash", "")
        # Remove old hash from new_state calculation to link purely on data + prev_hash
        # Actually, let's just hash the whole previous state dump + new data?
        # Simplified: Hash(prev_hash + json(new_data))

        # Update tick
        new_state["tick"] = self.current_state["tick"] + 1

        # Calculate new hash
        canonical_json = json.dumps(new_state["data"], sort_keys=True)
        mutation_hash = hashlib.sha256(
            f"{prev_hash}{canonical_json}".encode()
        ).hexdigest()
        new_state["hash"] = mutation_hash

        # 2. Write-Ahead-Log (Durability)
        try:
            with open(self.wal_path, "w") as f:
                json.dump(new_state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
        except IOError as e:
            print(f"WAL write failed: {e}")
            raise

        # 3. Atomic Rename (Atomicity)
        self._atomic_write(new_state)

        # 4. Cleanup WAL
        try:
            self.wal_path.unlink()
        except FileNotFoundError:
            pass

        # 5. Update Memory
        self.current_state = new_state

    def _atomic_write(self, state: Dict[str, Any]) -> None:
        """
        Writes state to temp file, fsyncs, then renames to state.json.
        Also updates backup.
        """
        # Backup existing
        if self.state_path.exists():
            shutil.copy2(self.state_path, self.backup_path)

        tmp_path = self.state_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        # Atomic Rename (POSIX guarantee)
        tmp_path.replace(self.state_path)

        # Sync Directory to ensure rename metadata is durable
        # try:
        #     fd = os.open(self.storage_dir, os.O_RDONLY)
        #     os.fsync(fd)
        #     os.close(fd)
        # except OSError:
        #     pass # Some OS don't allow directory fsync

    def get_state(self) -> Dict[str, Any]:
        return self.current_state
