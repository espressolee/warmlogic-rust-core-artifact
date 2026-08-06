# scripts/train_sovereign_model_mlx.py
# Sovereignty Forge (Era 28)
# Optimized for Apple Silicon (M-series chips)

import argparse
import logging
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SovereignForge")


def check_mlx_installed():
    try:
        import mlx.core as mx
        import mlx.nn as nn
        from mlx_lm import generate, load
        from mlx_lm.tuner import train

        return True
    except ImportError:
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Train Sovereign Model on Apple Silicon"
    )
    parser.add_argument(
        "--data",
        type=str,
        default="meta/datasets/warmlogic_instruct_v1.jsonl",
        help="Path to instruction dataset",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
        help="Base model to fine-tune",
    )
    parser.add_argument("--iters", type=int, default=100, help="Training iterations")
    parser.add_argument(
        "--num-layers", type=int, default=16, help="Number of LoRA layers"
    )
    args = parser.parse_args()

    logger.info("[Ignition] Initializing Sovereign Forge (MLX Engine)...")

    if not check_mlx_installed():
        logger.error("MLX libraries not found.")
        logger.error("Please run: pip install mlx mlx-lm")
        sys.exit(1)

    dataset_path = Path(args.data)
    if not dataset_path.exists():
        logger.error(f"Dataset not found at {dataset_path}")
        logger.info(
            "Run 'venv/bin/python3.13 warm_logic/kernel/intelligence/harvest.py' first."
        )
        sys.exit(1)

    logger.info(f"Dataset: {dataset_path}")
    logger.info(f"Base Model: {args.model}")
    logger.info("Starting LoRA Fine-Tuning...")

    # We shell out to mlx_lm.lora because it has a complex CLI/API internal structure
    # that is best invoked via its standard entry point for stability.
    # In a real "Sovereign" script we might import the trainer class directly,
    # but for stability, we wrap the command.

    import subprocess

    # Needs to be converted to valid/train split folder for mlx_lm
    # We will do a quick split here
    data_dir = Path("meta/datasets/mlx_ready")
    data_dir.mkdir(parents=True, exist_ok=True)

    # Split 90/10
    with open(dataset_path, "r") as f:
        lines = f.readlines()

    split_idx = int(len(lines) * 0.9)
    train_lines = lines[:split_idx]
    valid_lines = lines[split_idx:]

    (data_dir / "train.jsonl").write_text("".join(train_lines))
    (data_dir / "valid.jsonl").write_text("".join(valid_lines))

    model_adapter_path = "models/adapters/warmlogic_v1"

    cmd = [
        sys.executable,
        "-m",
        "mlx_lm",
        "lora",
        "--model",
        args.model,
        "--train",
        "--data",
        str(data_dir),
        "--iters",
        str(args.iters),
        # Reduced to 1 to fit long context "Textbooks" in memory
        "--batch-size",
        "1",
        "--num-layers",
        str(args.num_layers),
        "--adapter-path",
        model_adapter_path,
        "--save-every",
        "50",
        "--learning-rate",
        "1e-5",
    ]

    try:
        subprocess.check_call(cmd)
        logger.info("Training Complete.")
        logger.info(f"Adapter saved to {model_adapter_path}")
        logger.info("To fuse and serve:")
        logger.info(
            f"python -m mlx_lm.fuse --model {args.model} --adapter-path {model_adapter_path} --save-path models/warmlogic-v1-fused"
        )

    except subprocess.CalledProcessError as e:
        logger.error(f"Training Failed: {e}")
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
