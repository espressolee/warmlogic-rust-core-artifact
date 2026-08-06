import base64
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.provenance import (
    CodeIntegrityGuard,
    GeneticIntegrityGuard,
    audit_guard,
)


class TestProvenanceSaturation:
    @pytest.fixture
    def tmp_dir(self, tmp_path):
        return tmp_path

    # --- CodeIntegrityGuard Tests ---
    def test_hash_file_edge(self, tmp_dir):
        guard = CodeIntegrityGuard()
        assert guard._hash_file(tmp_dir / "missing") is None

        path = tmp_dir / "exists.txt"
        path.write_text("content")
        h = guard._hash_file(path)
        assert h == hashlib.sha256(b"content").hexdigest()

    def test_enforce_no_manifest(self, tmp_dir):
        guard = CodeIntegrityGuard(strict=True)
        with patch("warm_logic.kernel.provenance.MANIFEST_PATH", tmp_dir / "none.json"):
            with pytest.raises(SystemExit) as exc:
                guard.enforce()
            assert exc.value.code == 1

        guard_soft = CodeIntegrityGuard(strict=False)
        with patch("warm_logic.kernel.provenance.MANIFEST_PATH", tmp_dir / "none.json"):
            guard_soft.enforce()  # Should just return

    def test_enforce_corrupt_manifest(self, tmp_dir):
        path = tmp_dir / "corrupt.json"
        path.write_text("{ corrupt }")
        guard = CodeIntegrityGuard()
        with patch("warm_logic.kernel.provenance.MANIFEST_PATH", path):
            with pytest.raises(SystemExit) as exc:
                guard.enforce()
            assert exc.value.code == 1

    def test_verify_signature_fallback_decoding(self, tmp_dir):
        guard = CodeIntegrityGuard()
        key_path = tmp_dir / "raw_hex.dat"
        key_content = b"fake_hex_string"
        key_path.write_bytes(key_content)

        manifest = {"files": {}, "signature": "sig"}
        with patch("warm_logic.kernel.provenance.PUB_KEY_PATH", key_path):
            with patch("warm_logic.kernel.provenance.MLDSA") as mock_mldsa_class:
                mock_mldsa = mock_mldsa_class.return_value
                # 1. Hit fallback (non-b64) path (Line 122)
                mock_mldsa.verify.return_value = False
                assert guard._verify_signature(manifest) is False  # Line 129 hit

                # 2. Hit success with valid sig
                mock_mldsa.verify.return_value = True
                assert guard._verify_signature(manifest) is True

    def test_enforce_signature_failure(self, tmp_dir):
        path = tmp_dir / "manifest.json"
        path.write_text(json.dumps({"files": {}, "signature": "bad"}))
        guard = CodeIntegrityGuard()
        with patch("warm_logic.kernel.provenance.MANIFEST_PATH", path):
            with patch.object(guard, "_verify_signature", return_value=False):
                with patch("sys.exit") as mock_exit:
                    guard.enforce()
                    mock_exit.assert_called_with(1)

    def test_enforce_tamper_detection(self, tmp_dir):
        path = tmp_dir / "manifest.json"
        # Relative to ROOT_DIR. provenance.py is at ROOT/src/warm_logic/kernel/
        # So manifest should point to files relative to ROOT.
        path.write_text(
            json.dumps(
                {
                    "files": {"file1.py": "hash1", "file2.py": "hash2"},
                    "signature": "sig",
                }
            )
        )

        guard = CodeIntegrityGuard(strict=True)
        with patch("warm_logic.kernel.provenance.MANIFEST_PATH", path):
            with patch("warm_logic.kernel.provenance.ROOT_DIR", tmp_dir):
                with patch.object(guard, "_verify_signature", return_value=True):
                    # file1 missing, file2 tampered
                    (tmp_dir / "file2.py").write_text("wrong")
                    with patch("sys.exit") as mock_exit:
                        guard.enforce()
                        mock_exit.assert_called_with(1)

    def test_enforce_success(self, tmp_dir):
        path = tmp_dir / "manifest.json"
        f1_content = "code1"
        h1 = hashlib.sha256(f1_content.encode()).hexdigest()
        path.write_text(json.dumps({"files": {"f1.py": h1}, "signature": "sig"}))

        guard = CodeIntegrityGuard()
        with patch("warm_logic.kernel.provenance.MANIFEST_PATH", path):
            with patch("warm_logic.kernel.provenance.ROOT_DIR", tmp_dir):
                with patch.object(guard, "_verify_signature", return_value=True):
                    (tmp_dir / "f1.py").write_text(f1_content)
                    guard.enforce()
                    assert guard.verified is True

    def test_verify_signature_logic(self, tmp_dir):
        guard = CodeIntegrityGuard()
        # 1. Missing keys
        assert guard._verify_signature({}) is False

        # 2. Missing Public Key
        with patch("warm_logic.kernel.provenance.PUB_KEY_PATH", tmp_dir / "no_key"):
            assert guard._verify_signature({"files": {}, "signature": "sig"}) is False

        # 3. MLDSA Success path
        key_path = tmp_dir / "pub.dat"
        key_path.write_bytes(base64.b64encode(b"fake_hex_pub"))
        manifest = {"files": {"a": 1}, "signature": "sig"}

        with patch("warm_logic.kernel.provenance.PUB_KEY_PATH", key_path):
            with patch("warm_logic.kernel.provenance.MLDSA") as mock_mldsa_class:
                mock_mldsa = mock_mldsa_class.return_value
                mock_mldsa.verify.return_value = True
                assert guard._verify_signature(manifest) is True

                # Exception path
                mock_mldsa.verify.side_effect = Exception("PQC Crash")
                assert guard._verify_signature(manifest) is False

    # --- GeneticIntegrityGuard Tests ---
    def test_genetic_integrity_guard(self):
        store = MagicMock()
        # We need to mock SovereignCodebase which is imported as a class
        with patch("warm_logic.kernel.provenance.SovereignCodebase") as mock_cb_class:
            mock_cb = mock_cb_class.return_value
            mock_cb.ingest.return_value = 10
            mock_cb.generate_manifest.return_value = "dna_hash"
            mock_cb.verify_integrity.return_value = True

            gig = GeneticIntegrityGuard(store, root_path="/tmp")
            h = gig.verify()
            assert h == "dna_hash"

            # Failure path
            mock_cb.verify_integrity.return_value = False
            with patch("sys.exit") as mock_exit:
                gig.verify()
                mock_exit.assert_called_with(1)

    def test_audit_guard_wrapper(self):
        with patch("warm_logic.kernel.provenance.CodeIntegrityGuard") as mock_code:
            with patch(
                "warm_logic.kernel.provenance.GeneticIntegrityGuard"
            ) as mock_genetic:
                with patch("warm_logic.kernel.provenance.SovereignStore"):
                    audit_guard()
                    mock_code.return_value.enforce.assert_called()
                    mock_genetic.return_value.verify.assert_called()
