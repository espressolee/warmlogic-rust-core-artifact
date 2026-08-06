import os
import shutil
from pathlib import Path

import pytest

from warm_logic.dominion.replication.codebase import SovereignCodebase
from warm_logic.kernel.sys.persistence import SovereignStore


@pytest.fixture
def clean_store():
    # Setup a temp location for the DB
    db_path = "test_replication.db"
    store = SovereignStore(db_path)
    yield store
    # Teardown
    store.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_ingest_and_manifest(clean_store):
    """
    Verifies that the codebase can ingest itself and generate a consistent manifest.
    """
    codebase = SovereignCodebase(clean_store)

    # We point it to the 'src/warm_logic/system' directory to keep the test fast
    target_dir = Path("src/warm_logic/system")
    assert target_dir.exists(), "Target directory for test does not exist"

    count = codebase.ingest(str(target_dir))
    assert count > 0, "Should have ingested at least one file (replication/codebase.py)"

    # Verify manifest generation
    manifest_hash = codebase.generate_manifest()
    assert len(manifest_hash) == 64, "Manifest hash should be SHA256 hex"

    # Verify we can retrieve a known file
    known_file = "replication/codebase.py"
    # Note: relative path logic in ingest depends on root.
    # If we ingest 'warm_logic/system', relative paths start inside that.
    # We need to find the key used in manual checking.

    # Let's verify via the public API
    assert codebase.verify_integrity(str(target_dir)) == True


def test_tamper_detection(clean_store, tmp_path):
    """
    Verifies that modifying a file on disk triggers an integrity failure.
    """
    # Create a dummy codebase in a temp dir
    d = tmp_path / "src"
    d.mkdir()
    p = d / "hello.py"
    p.write_text("print('hello')")

    codebase = SovereignCodebase(clean_store)
    codebase.ingest(str(d))
    manifest_initial = codebase.generate_manifest()

    assert codebase.verify_integrity(str(d)) == True

    # TAMPER: Modify file on disk
    p.write_text("print('hacked')")

    assert codebase.verify_integrity(str(d)) == False

    # Verify manifest changes if we re-ingest
    codebase.ingest(str(d))
    manifest_final = codebase.generate_manifest()
    assert manifest_initial != manifest_final
