import os

import pytest

from warm_logic.kernel.autonomy.vfs import SovereignVFS


@pytest.fixture
def vfs_root(tmp_path):
    root = tmp_path / "vfs_root"
    root.mkdir()
    (root / "kernel.py").write_text("print('kernel')")
    return root


def test_vfs_read_write_within_jail(vfs_root):
    vfs = SovereignVFS(root_path=str(vfs_root))

    # Read within jail
    content = vfs.read_text("kernel.py")
    assert content == "print('kernel')"

    # Write within jail
    vfs.write_text("config.json", '{"key": "value"}')
    assert (vfs_root / "config.json").exists()
    assert vfs.read_text("config.json") == '{"key": "value"}'


def test_vfs_blocks_traversal(vfs_root, tmp_path):
    vfs = SovereignVFS(root_path=str(vfs_root))

    # Try to access something outside the jail
    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secret")

    with pytest.raises(PermissionError, match="Path traversal violation"):
        vfs.read_text("../secret.txt")

    with pytest.raises(PermissionError, match="Path traversal violation"):
        vfs.write_text("/etc/passwd", "rogue")


def test_vfs_merkle_tracking(vfs_root):
    vfs = SovereignVFS(root_path=str(vfs_root))

    root_1 = vfs.get_merkle_root()

    # Initial read registers the file
    vfs.read_text("kernel.py")
    root_2 = vfs.get_merkle_root()
    assert root_1 != root_2

    # Modification changes the root
    vfs.write_text("kernel.py", "print('updated')")
    root_3 = vfs.get_merkle_root()
    assert root_2 != root_3

    print(
        f"\n✅ [Test] SovereignVFS correctly enforced containment and tracked integrity."
    )


if __name__ == "__main__":
    # Manual run support
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "vfs_root"
        root.mkdir()
        (root / "kernel.py").write_text("test")
        test_vfs_read_write_within_jail(root)
        test_vfs_blocks_traversal(root, Path(td))
        test_vfs_merkle_tracking(root)
