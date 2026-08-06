#!/usr/bin/env python3
import os
import subprocess
import sys


def main():
    print("Running Comprehensive Sanity Check...")
    # Wrap the bash sanity check
    res = subprocess.run(["bash", "scripts/sanity_check.sh"], capture_output=False)
    sys.exit(res.returncode)


if __name__ == "__main__":
    main()
