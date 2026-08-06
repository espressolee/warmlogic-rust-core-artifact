import argparse
import asyncio

from warm_logic.kernel.sys.memory import SovereignMemoryEngine
from warm_logic.sdk.identity import SovereignIdentity


async def main():
    parser = argparse.ArgumentParser(description="SMS Memory Sync")
    parser.add_argument("--log", type=str, help="Event detail to log")
    parser.add_argument("--type", type=str, default="MANUAL_ENTRY", help="Event type")
    parser.add_argument(
        "--compact", action="store_true", help="Compact today's log to Chronicle"
    )

    args = parser.parse_args()

    # Initialize Identity for signing
    identity = SovereignIdentity()
    engine = SovereignMemoryEngine(".", identity)

    if args.log:
        engine.log_event(args.type, args.log)
        print(f"Event logged to Ephemeris.")

    if args.compact:
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        summary = f"- Session on {today}: Completed Phase 15 SMS implementation."
        engine.compact_to_chronicle(summary)
        print(f"Compacted to Chronicle.")


if __name__ == "__main__":
    asyncio.run(main())
