import logging
import sys
from unittest.mock import MagicMock

logger = logging.getLogger("warm_logic_rs_mock")

# Global registry for shared persistence between mock instances
_STORE_REGISTRY = {}


class MockZKProof:
    def __init__(self, commitment, proof):
        self.commitment_hex = commitment
        self.proof_hex = proof


class RustZKProofGenerator:
    def generate_state_proof(self, val, blinding):
        return MockZKProof(f"mock_comm_{val}", f"mock_proof_{val}")

    def verify_state_proof(self, proof, commitment):
        if proof.startswith("mock_proof_") and commitment.startswith("mock_comm_"):
            return proof.replace("mock_proof_", "") == commitment.replace(
                "mock_comm_", ""
            )
        return False


class SovereignStore:
    def __new__(cls, path, key=None, *args, **kwargs):
        mock = MagicMock(name="SovereignStore")

        # Identity for persistence tracking
        if isinstance(key, bytes):
            key_str = key.hex()
        else:
            key_str = str(key) if key else None

        if path not in _STORE_REGISTRY:
            _STORE_REGISTRY[path] = {}
        data_registry = _STORE_REGISTRY[path]

        def put(k, v):
            # Store the key used and the "encrypted" value
            encrypted_v = f"ENCRYPTED_WITH_{key_str}:{v}" if key_str else v
            data_registry[k] = (key_str, encrypted_v)

        def get(k):
            entry = data_registry.get(k)
            if entry is None:
                return None

            orig_key_str, val = entry

            if orig_key_str is None:
                # Stored raw, returns raw
                return val

            if key_str == orig_key_str:
                # Decrypt (Success)
                return val.replace(f"ENCRYPTED_WITH_{key_str}:", "", 1)
            elif key_str is None:
                # Access without key returns raw "encrypted" blob
                return val
            else:
                # WRONG KEY provided - fail decryption
                raise ValueError("Decryption error: MAC mismatch or invalid key")

        mock.put.side_effect = put
        mock.get.side_effect = get
        mock.close.return_value = None
        return mock


class Vote:
    def __init__(self, *args, **kwargs):
        if len(args) >= 3:
            self.voter_id = args[0]
            self.block_hash = args[1]
            self.signature = args[2]
        else:
            self.voter_id = kwargs.get("voter_id")
            self.block_hash = kwargs.get("block_hash")
            self.signature = kwargs.get("signature")


class BFTEngine:
    def __new__(cls, quorum_size, *args, **kwargs):
        mock = MagicMock(name="BFTEngine")
        votes = {}

        def cast_vote(vote):
            if vote.voter_id in votes and votes[vote.voter_id] != vote.block_hash:
                return False
            votes[vote.voter_id] = vote.block_hash
            return len(votes) >= quorum_size

        mock.cast_vote.side_effect = cast_vote
        mock.quorum_size = quorum_size
        return mock


class RustReplicatedLedger:
    def __new__(cls, path, *args, **kwargs):
        mock = MagicMock(name="RustReplicatedLedger")
        blocks = {}
        # Shared balances registry keyed by path to persist across instantiations relative to path
        if path not in _STORE_REGISTRY:
            _STORE_REGISTRY[path] = {"balances": {}}

        # We use the registry entry for balances
        balances = _STORE_REGISTRY[path].setdefault("balances", {})

        mock.put_block.side_effect = lambda b: blocks.__setitem__(b.get("hash"), b)
        mock.get_block.side_effect = blocks.get
        mock.get_last_block.return_value = None

        # Ledger Balance Mocking
        def get_balance(addr):
            return balances.get(addr, 0)

        def update_balance(addr, amount):
            balances[addr] = amount

        mock.get_balance.side_effect = get_balance
        # We don't have explicit update_balance in RustReplicatedLedger usually?
        # But persistence.py calls it?
        # persistence.py calls self._rust_ledger.get_balance(address).
        # persistence.py UPDATE logic: calls self.store.update_balance ?
        # No, persistence.py update_balance logic:
        # if self._use_rust: ... try: pass except...
        # It PASSES. It assumes Rust updates via mining blocks.
        # But failing test calls `economy1.deduct` -> `store.update_balance`.
        # So we should probably allow updating mock balance if we want it to persist?
        # But `persistence.py` update_balance implementation for Rust is PASS (empty).
        # So it ONLY updates SQLite.
        # BUT `get_balance` reads RUST first.
        # So if Rust mock returns 1 (default MagicMock int), it ignores SQLite!
        # Fix: make get_balance return 0 if empty, or raise error?
        # If I make it return 0, persistence.py falls back to SQLite.

        return mock


def generate_keypair():
    return ("MOCK_PK", "MOCK_SK")


def sign(pk, msg):
    return f"MOCK_SIG_{msg}"


def verify(pk, msg, sig):
    return sig == f"MOCK_SIG_{msg}"


class MLDSA:
    @staticmethod
    def sign(pk, msg):
        return sign(pk, msg)

    @staticmethod
    def verify(pk, msg, sig):
        return verify(pk, msg, sig)


class PQCKeypair:
    @staticmethod
    def generate():
        return generate_keypair()


class MockReport:
    def __init__(self):
        self.provider = (
            "KINETIC_TPM_STUB_DARWIN" if sys.platform == "darwin" else "KINETIC_TPM"
        )
        self.pcr_hash = "MOCK_PCR_HASH"
        self.quote = f"SIGNED_BY_Sovereign_RoT_{self.pcr_hash}"


class ShieldGuard:
    def __init__(self):
        self.violations = 0

    def protect_secret(self, secret):
        if len(secret) < 10:
            self.violations += 1
            return False
        return True

    def verify_boundary(self, ptr, length, limit):
        # Simulating boundary check. Return True if safe.
        if length > limit:
            self.violations += 1
            return False
        return True

    def check_syscall(self, name, args):
        # Simulating boundary violation check logic if needed
        # test_memory_boundary_violation passes 1MB data.
        if name == "write" and args and len(args) > 1:
            # args[1] is data
            if len(args[1]) > 1024 * 1024:
                self.violations += 1
                return False  # Blocked
        return True  # Allowed


class HardwareAttestation:
    @staticmethod
    def generate_report():
        return MockReport()

    @staticmethod
    def verify_report(report):
        if isinstance(report, MockReport):
            return (
                True,
                "VERIFICATION_SUCCESS (SECURE_ENCLAVE_SIGNED) [PCR[MOCK_PCR_HASH]]",
            )
        return (False, "INVALID_REPORT")


class HardwareRealityBinder:
    @staticmethod
    def get_hardware_fingerprint():
        return "a" * 64

    @staticmethod
    def seal_to_silicon(data):
        return b"SEALED:" + data

    @staticmethod
    def unseal_from_silicon(data):
        if data.startswith(b"SEALED:"):
            return data[7:]
        raise ValueError("Hardware Mismatch or Unseal Failure")


def __getattr__(name):
    if name == "HardwareAttestation":
        return HardwareAttestation
    if name == "HardwareRealityBinder":
        return HardwareRealityBinder
    if name == "ShieldGuard":
        return ShieldGuard
    return MagicMock(name=name)
