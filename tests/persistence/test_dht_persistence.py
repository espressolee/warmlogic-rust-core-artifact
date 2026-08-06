import json
import os
import shutil
import subprocess

# Adjust path to find warm_logic if needed
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))


class TestDHTPersistence(unittest.TestCase):
    def setUp(self):
        # Create a temp dir for the sled db
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "sovereign_test_db")

    def tearDown(self):
        # Cleanup
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

    def test_persistence_lifecycle(self):
        """
        Verify that data stored in SovereignDHT persists across 'restarts'
        (re-initialization of the DHT object pointing to the same DB).
        """
        node_id_hex = ("01" * 32)
        key = "persistent_key"
        value_blob = {"value": "vital_data", "commitment": "zk_proof_xyz"}
        payload = json.dumps(value_blob)

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
        store_result = self._run_python(
            store_script, self.db_path, node_id_hex, key, payload
        )
        stored = store_result.stdout.strip().splitlines()[-1]
        self.assertEqual(json.loads(stored), value_blob)

        read_script = """
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
    raise RuntimeError("Rust-backed store not attached after restart")
value = dht.storage.get(key)
print(value if value is not None else "None")
if hasattr(dht.storage, "close"):
    dht.storage.close()
"""
        read_result = self._run_python(read_script, self.db_path, node_id_hex, key)
        retrieved = read_result.stdout.strip().splitlines()[-1]
        self.assertNotEqual(retrieved, "None", "Data lost after restart!")
        self.assertEqual(json.loads(retrieved), value_blob)


if __name__ == "__main__":
    unittest.main()
