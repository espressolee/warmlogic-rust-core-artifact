import os
import sys
from datetime import datetime
from pathlib import Path


def stitch_lite():
    """
    A lightweight version of stitch_memory.py that only performs the
    file combining logic, avoiding complex kernel dependencies.
    """
    root = Path(".")
    ephemeris_dir = root / "meta/memory/ephemeris"
    chronicle_path = root / "meta/memory/chronicle.md"
    context_path = root / ".sovereign-context"

    print("[Stitch-Lite] Consolidating memory into Sovereign Context...")

    context_content = []
    context_content.append("# WARM LOGIC SOVEREIGN CONTEXT\n")
    context_content.append(f"Generated: {datetime.now().isoformat()}\n")
    context_content.append(
        "--- IMPORTANT: AGENT MUST READ THIS BEFORE PROCEEDING ---\n\n"
    )

    # 1. Add Chronicle
    if chronicle_path.exists():
        print(f"  + Adding Chronicle ({chronicle_path})")
        context_content.append("## Permanent Chronicle\n")
        context_content.append(chronicle_path.read_text())
        context_content.append("\n---\n")
    else:
        print("  ! Chronicle not found.")

    # 2. Add Latest Ephemeris
    today = datetime.now().strftime("%Y-%m-%d")
    today_log = ephemeris_dir / f"{today}.md"

    if today_log.exists():
        print(f"  + Adding Ephemeris ({today_log})")
        context_content.append(f"## Recent Activity ({today})\n")
        context_content.append(today_log.read_text())
    else:
        print(f"  ! No Ephemeris for today ({today}).")

    with open(context_path, "w") as f:
        f.writelines(context_content)

    print(f"[Stitch-Lite] Sovereign Context anchored at {context_path}")
    print("Content Preview:")
    print("-" * 40)
    print("".join(context_content[:15]))
    print("...")


if __name__ == "__main__":
    stitch_lite()
