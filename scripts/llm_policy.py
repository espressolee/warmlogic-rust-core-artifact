#!/usr/bin/env python3
import argparse
import json
import sys

from warm_logic.core.utils.ops.llm_policy import resolve_policy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", nargs="?", default="local_only")
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()

    # The test test_llm_policy.py:test_determine_patch_engine_mode_safe_local
    # expects outputs like "WL_LLM_MODE=safe_local LLM_PATCH_MODE=disabled ..."
    # Wait, looking at test_dev_loop_llm_policy.py:
    # outputs = "WL_LLM_MODE=safe_local LLM_PATCH_MODE=disabled LLM_PATCHING_ENABLED=0"

    policy = resolve_policy(args.mode, profile=args.profile)
    output = []
    for k, v in policy.items():
        output.append(f"{k}={v}")
    print(" ".join(output))


if __name__ == "__main__":
    main()
