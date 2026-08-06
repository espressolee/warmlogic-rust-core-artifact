import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))


class TestDHTEncryption(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "encrypted_db")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _run_python(self, code: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        repo_root = str(Path(__file__).resolve().parents[2])
        src_root = str(Path(repo_root) / "src")
        current_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            f"{src_root}{os.pathsep}{repo_root}{os.pathsep}{current_pythonpath}"
            if current_pythonpath
            else f"{src_root}{os.pathsep}{repo_root}"
        )
        return subprocess.run(
            [sys.executable, "-c", code, *args],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_encryption_at_rest(self):
        """
        Verify that data is encrypted at rest and unreadable without the key.
        """
        node_id_hex = ("42" * 32)
        wrong_node_id_hex = ("99" * 32)
        secret_value = {
            "value": "TOP_SECRET_CIVILIZATION_KEY",
            "commitment": "zk_0xabc",
        }
        key = "manifest_v1"
        payload = json.dumps(secret_value)

        store_script = """
import sys
from warm_logic.kernel.mesh.dht import SovereignDHT

db_path, node_hex, key, payload = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
dht = SovereignDHT(
    node_id=bytes.fromhex(node_hex),
    address="127.0.0.1",
    port=8000,
    db_path=db_path,
)
if isinstance(dht.storage, dict):
    raise RuntimeError("Rust-backed store not attached")
dht.storage.put(key, payload)
value = dht.storage.get(key)
print(value if value is not None else "None")
if hasattr(dht.storage, "close"):
    dht.storage.close()
"""
        stored = self._run_python(store_script, self.db_path, node_id_hex, key, payload)
        stored_value = stored.stdout.strip().splitlines()[-1]
        self.assertEqual(json.loads(stored_value), secret_value)

        raw_read_script = """
import json
import sys
import warm_logic_rs

db_path, key = sys.argv[1], sys.argv[2]
store = warm_logic_rs.SovereignStore(db_path)
raw = store.get(key)
print(json.dumps({"raw": raw}))
if hasattr(store, "close"):
    store.close()
"""
        raw_result = self._run_python(raw_read_script, self.db_path, key)
        raw_json = raw_result.stdout.strip().splitlines()[-1]
        raw_data = json.loads(raw_json)["raw"]

        # Verify it's NOT the plaintext
        self.assertNotEqual(raw_data, payload)

        # Verify it's not valid JSON (because it's encrypted binary garbage)
        try:
            json.loads(raw_data)
            self.fail("Encrypted data was valid JSON! (Likely not encrypted)")
        except json.JSONDecodeError:
            pass  # Expected failure

        wrong_key_script = """
import sys
from warm_logic.kernel.mesh.dht import SovereignDHT

db_path, node_hex, key = sys.argv[1], sys.argv[2], sys.argv[3]
dht = SovereignDHT(
    node_id=bytes.fromhex(node_hex),
    address="127.0.0.1",
    port=8001,
    db_path=db_path,
)
if isinstance(dht.storage, dict):
    raise RuntimeError("Rust-backed store not attached for wrong-key test")
try:
    dht.storage.get(key)
except Exception as exc:
    print(str(exc))
    if hasattr(dht.storage, "close"):
        dht.storage.close()
    raise SystemExit(0)
if hasattr(dht.storage, "close"):
    dht.storage.close()
raise SystemExit(2)
"""
        wrong_key = self._run_python(wrong_key_script, self.db_path, wrong_node_id_hex, key)
        wrong_output = wrong_key.stdout.strip()
        self.assertIn("Decryption error", wrong_output)


if __name__ == "__main__":
    unittest.main()
