import tarfile
from pathlib import Path


def test_vtracer_case_bytesvec_patch_changes_signature(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    crate_path = repo_root / "out" / "bridge_eval" / "_crates_cache" / "vtracer-0.6.5.crate"
    assert crate_path.exists()

    extracted_root = tmp_path / "src"
    extracted_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(crate_path) as tf:
        tf.extractall(extracted_root)

    stock_src = extracted_root / "vtracer-0.6.5"
    assert stock_src.exists()

    from scripts.eval import eval_paper09_vtracer_case as vtracer_case

    patched_src = tmp_path / "patched"
    vtracer_case._apply_bytesvec_patch(stock_dir=stock_src, patched_dir=patched_src)

    patched_file = patched_src / "src" / "python.rs"
    patched_text = patched_file.read_text(encoding="utf-8")

    assert "struct BytesVec" in patched_text
    assert "img_bytes: BytesVec" in patched_text
    assert "img_bytes: Vec<u8>" not in patched_text

