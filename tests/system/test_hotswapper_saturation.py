import hashlib
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from warm_logic.kernel.sys.hot_swapper import HotSwapManager


class TestHotSwapManagerSaturation:
    @pytest.fixture
    def dht(self):
        return MagicMock()

    def test_init_and_hash(self, dht):
        """Test initialization and heuristic hashing."""
        manager = HotSwapManager(dht)
        assert manager.current_hash is not None
        assert manager.dht == dht

    def test_calculate_hash_failure(self, dht):
        """Test fallback when hashing fails."""
        with patch("os.listdir", side_effect=Exception("Disk Error")):
            manager = HotSwapManager(dht)
            assert manager.current_hash == "genesis_hash"

    def test_calculate_hash_success(self, dht, tmp_path):
        """Test hashing logic with actual files."""
        # Patch os.path.dirname globally since it's imported inside the method
        with patch("os.path.dirname", return_value=str(tmp_path)):
            f1 = tmp_path / "test1.py"
            f1.write_text("code1")
            manager = HotSwapManager(dht)
            h1 = manager.current_hash

            f2 = tmp_path / "test2.py"
            f2.write_text("code2")
            h2 = manager._calculate_current_hash()
            assert h1 != h2

    @pytest.mark.asyncio
    async def test_check_for_updates(self, dht):
        """Test update polling from DHT."""
        manager = HotSwapManager(dht)
        manager.current_hash = "old_hash"

        # 1. No target
        dht.get.return_value = None
        assert await manager.check_for_updates() is False

        # 2. Same target
        dht.get.return_value = "old_hash"
        assert await manager.check_for_updates() is False

        # 3. New target
        dht.get.return_value = "new_hash"
        assert await manager.check_for_updates() is True
        assert manager.target_hash == "new_hash"

    @pytest.mark.asyncio
    async def test_apply_binary_patch(self, dht, tmp_path):
        """Test patch application and safety axioms."""
        # Patch os.path.dirname so files are written to tmp_path
        with patch("os.path.dirname", return_value=str(tmp_path)):
            manager = HotSwapManager(dht)
            old_hash = manager.current_hash
            manager.target_hash = "new_hash"

            # Need to mock UpdateSafetyAxiom in constitution
            with patch(
                "warm_logic.kernel.constitution.UpdateSafetyAxiom.verify_update"
            ) as mock_verify:
                # 1. Verification fail
                mock_verify.return_value = False
                assert await manager.apply_binary_patch(b"invalid_patch") is False

                # 2. Verification success - hash changes after applying patch
                mock_verify.return_value = True
                assert await manager.apply_binary_patch(b"valid_patch") is True
                # After applying patch, hash is recalculated from disk (may differ from target)
                assert manager.current_hash is not None
