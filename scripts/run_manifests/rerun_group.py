import argparse
import json
import re
import sys


def is_in_range(p_id, p_range):
    """Checks if P-ID (e.g. P345) is within range (e.g. P340-P349)"""
    if not p_range:
        return True

    match_id = re.match(r"P(\d+)", p_id)
    match_range = re.match(r"P(\d+)-P(\d+)", p_range)

    if match_id and match_range:
        val = int(match_id.group(1))
        low = int(match_range.group(1))
        high = int(match_range.group(2))
        return low <= val <= high
    return False


def main():
    parser = argparse.ArgumentParser(
        description="WarmLogic Rerun Group Override Script"
    )
    parser.add_argument("--range", help="Protocol range (e.g. P340-P349)")
    parser.add_argument(
        "--range-only-overrides",
        action="store_true",
        help="Only run overrides for range",
    )
    parser.add_argument("--overrides", nargs="+", help="Specific overrides to apply")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")

    args = parser.parse_args()

    overrides = {}
    if args.overrides:
        for ov_path in args.overrides:
            try:
                with open(ov_path, "r") as f:
                    data = json.load(f)
                    if "overrides" in data:
                        overrides.update(data["overrides"])
            except Exception:
                pass

    if args.dry_run:
        for p_id, cfg in overrides.items():
            if is_in_range(p_id, args.range):
                print(f"Dry-run: Rerunning {p_id}")
                if "expected_rc" in cfg:
                    print(f"  --expected-rc {cfg['expected_rc']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
