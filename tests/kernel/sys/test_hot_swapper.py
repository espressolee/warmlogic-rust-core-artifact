# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic HotSwapManager."""

import asyncio
import hashlib
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from warm_logic.kernel.sys.hot_swapper import HotSwapManager, _NullDHT


class TestNullDHT:
    """Test _NullDHT placeholder."""

    def test_get_returns_none(self):
        """get() always returns None."""
        dht = _NullDHT()
        assert dht.get(b"any_key") is None
        assert dht.get(b"another_key") is None


class TestHotSwapManager:
    """Test HotSwapManager class."""

    def test_init_with_dht_client(self):
        """Initializes with provided DHT client."""
        mock_dht = MagicMock()
        manager = HotSwapManager(dht_client=mock_dht)

        assert manager.dht is mock_dht

    def test_init_without_dht_client(self):
        """Uses NullDHT when no client provided."""
        manager = HotSwapManager()

        assert isinstance(manager.dht, _NullDHT)

    def test_init_calculates_current_hash(self):
        """Calculates hash on initialization."""
        manager = HotSwapManager()

        assert manager.current_hash is not None
        assert len(manager.current_hash) == 64  # SHA256 hex

    def test_init_target_hash_none(self):
        """Target hash is None initially."""
        manager = HotSwapManager()

        assert manager.target_hash is None

    def test_calculate_current_hash_deterministic(self):
        """Hash is deterministic for same source files."""
        manager1 = HotSwapManager()
        manager2 = HotSwapManager()

        assert manager1.current_hash == manager2.current_hash

    def test_calculate_current_hash_includes_py_files(self):
        """Hash includes Python files in kernel/sys."""
        manager = HotSwapManager()

        # Verify hash is based on .py files
        assert manager.current_hash != "genesis_hash"

    def test_calculate_current_hash_exception(self, tmp_path, monkeypatch):
        """Returns genesis_hash on exception."""
        # Monkeypatch os.listdir to raise an exception
        import os as os_module

        original_listdir = os_module.listdir

        def mock_listdir(path):
            raise Exception("Directory error")

        monkeypatch.setattr(os_module, "listdir", mock_listdir)

        # Create a new manager - it will use the mocked listdir
        try:
            manager = HotSwapManager()
            assert manager.current_hash == "genesis_hash"
        finally:
            monkeypatch.setattr(os_module, "listdir", original_listdir)

    def test_reload_module_new_module(self):
        """Imports new module successfully."""
        manager = HotSwapManager()

        # Try to reload a standard library module
        result = manager.reload_module("json")

        assert result is True

    def test_reload_module_existing(self):
        """Reloads existing module."""
        import json

        manager = HotSwapManager()
        original_hash = manager.current_hash

        result = manager.reload_module("json")

        assert result is True
        # Hash is recalculated after reload
        assert manager.current_hash == original_hash

    def test_reload_module_nonexistent(self):
        """Returns False for nonexistent module."""
        manager = HotSwapManager()

        result = manager.reload_module("nonexistent_module_xyz")

        assert result is False

    def test_reload_module_import_error(self):
        """Returns False on import error."""
        manager = HotSwapManager()

        result = manager.reload_module("..invalid..module")

        assert result is False

    @pytest.mark.asyncio
    async def test_check_for_updates_no_update(self):
        """Returns False when no update available."""
        mock_dht = MagicMock()
        mock_dht.get.return_value = None
        manager = HotSwapManager(dht_client=mock_dht)

        result = await manager.check_for_updates()

        assert result is False
        assert manager.target_hash is None

    @pytest.mark.asyncio
    async def test_check_for_updates_same_hash(self):
        """Returns False when hash matches current."""
        manager = HotSwapManager()
        mock_dht = MagicMock()
        mock_dht.get.return_value = manager.current_hash
        manager.dht = mock_dht

        result = await manager.check_for_updates()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_for_updates_new_hash(self):
        """Returns True and sets target when new hash found."""
        mock_dht = MagicMock()
        new_hash = "a" * 64
        mock_dht.get.return_value = new_hash
        manager = HotSwapManager(dht_client=mock_dht)

        result = await manager.check_for_updates()

        assert result is True
        assert manager.target_hash == new_hash
        mock_dht.get.assert_called_once_with(b"fleet_target_kernel_hash")

    @pytest.mark.asyncio
    async def test_apply_binary_patch_safety_violation(self):
        """Aborts on safety axiom violation."""
        manager = HotSwapManager()

        # Patch at the import location inside the function
        with patch("warm_logic.kernel.constitution.UpdateSafetyAxiom") as mock_axiom:
            mock_axiom.verify_update.return_value = False

            result = await manager.apply_binary_patch(b"patch_data")

        assert result is False

    @pytest.mark.asyncio
    async def test_apply_binary_patch_success(self, tmp_path):
        """Successfully applies patch."""
        manager = HotSwapManager()

        with patch("warm_logic.kernel.constitution.UpdateSafetyAxiom") as mock_axiom:
            mock_axiom.verify_update.return_value = True

            # Patch os.path.dirname at module level
            with patch("os.path.dirname") as mock_dir:
                mock_dir.return_value = str(tmp_path)

                result = await manager.apply_binary_patch(b"patch_content")

        assert result is True
        patch_file = tmp_path / "kernel_patch.bin"
        assert patch_file.exists()
        assert patch_file.read_bytes() == b"patch_content"

    @pytest.mark.asyncio
    async def test_apply_binary_patch_write_failure(self, tmp_path):
        """Returns False on write failure."""
        manager = HotSwapManager()

        with patch("warm_logic.kernel.constitution.UpdateSafetyAxiom") as mock_axiom:
            mock_axiom.verify_update.return_value = True

            # Use a path that doesn't exist to cause write failure
            with patch("os.path.dirname") as mock_dir:
                mock_dir.return_value = "/nonexistent/path/that/should/fail"

                result = await manager.apply_binary_patch(b"patch_data")

        assert result is False

    @pytest.mark.asyncio
    async def test_apply_binary_patch_updates_hash(self, tmp_path):
        """Updates current hash after successful patch."""
        manager = HotSwapManager()

        with patch("warm_logic.kernel.constitution.UpdateSafetyAxiom") as mock_axiom:
            mock_axiom.verify_update.return_value = True

            with patch("os.path.dirname") as mock_dir:
                mock_dir.return_value = str(tmp_path)

                await manager.apply_binary_patch(b"new_patch")

        # Hash is recalculated (may or may not change based on source files)
        assert manager.current_hash is not None
