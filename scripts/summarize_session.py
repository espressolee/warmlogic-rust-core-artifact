import os
import sys
from datetime import datetime
from pathlib import Path


def summarize_session():
    """
    A placeholder script to demonstrate where an LLM-based summarizer would sit.
    Since I cannot read binary .pb files directly, this script asks the USER
    to paste the key context they want to save.
    """
    chronicle_path = Path("meta/memory/chronicle.md")

    print("\n=== Sovereign Session Summarizer ===")
    print("Since we cannot parse .pb files directly, please describe the key decisions")
    print("or context from the heavy session that you want to preserve forever.")
    print("This will be appended to 'meta/memory/chronicle.md'.")
    print("==================================\n")

    summary = input("Enter session summary (or press Enter to skip): ").strip()

    if not summary:
        print("No summary entered. Exiting.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n\n### Session Summary: {timestamp}\n{summary}\n"

    with open(chronicle_path, "a") as f:
        f.write(entry)

    print(f"\nContext appended to {chronicle_path}")
    print("Run 'python scripts/stitch_memory.py' to update the active context.")


if __name__ == "__main__":
    summarize_session()
