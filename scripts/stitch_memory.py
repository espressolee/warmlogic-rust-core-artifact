import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Fix path for ad-hoc execution
sys.path.append(os.getcwd())

from warm_logic.kernel.sys.memory import SovereignMemoryEngine
from warm_logic.sdk.identity import SovereignIdentity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StitchMemory")


def stitch_to_context(ephemeris_dir: Path, chronicle_path: Path, context_path: Path):
    """
    Combines Chronicle and recent Ephemeris into a single .sovereign-context file.
    """
    logger.info("[Stitch] Consolidating memory into Sovereign Context...")

    context_content = []
    context_content.append("# WARM LOGIC SOVEREIGN CONTEXT\n")
    context_content.append(f"Generated: {datetime.now().isoformat()}\n")
    context_content.append(
        "--- IMPORTANT: AGENT MUST READ THIS BEFORE PROCEEDING ---\n\n"
    )

    # 1. Add Chronicle (The permanent ego)
    if chronicle_path.exists():
        context_content.append("## Permanent Chronicle\n")
        context_content.append(chronicle_path.read_text())
        context_content.append("\n---\n")

    # 2. Add Latest Ephemeris (Recent senses)
    today = datetime.now().strftime("%Y-%m-%d")
    today_log = ephemeris_dir / f"{today}.md"
    if today_log.exists():
        context_content.append(f"## Recent Activity ({today})\n")
        context_content.append(today_log.read_text())

    with open(context_path, "w") as f:
        f.writelines(context_content)

    logger.info(f"[Stitch] Sovereign Context anchored at {context_path}")


if __name__ == "__main__":
    root = Path(".")
    ephemeris = root / "meta/memory/ephemeris"
    chronicle = root / "meta/memory/chronicle.md"
    context = root / ".sovereign-context"

    stitch_to_context(ephemeris, chronicle, context)

    # Also perform compaction if requested via flag
    if "--compact" in sys.argv:
        identity = SovereignIdentity()
        engine = SovereignMemoryEngine(".", identity)
        today_str = datetime.now().strftime("%Y-%m-%d")
        summary = (
            f"Summary of {today_str}: Automated compaction triggered by stitch_memory."
        )
        engine.compact_to_chronicle(summary)
