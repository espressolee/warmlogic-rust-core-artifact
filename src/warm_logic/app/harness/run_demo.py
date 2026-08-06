# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#!/usr/bin/env python3
# ==========================================================
# WarmLogic Demo Runner
# Quick-start script for presentations and demos.
# ==========================================================
"""
WarmLogic Demo Runner

Usage:
    python -m warm_logic.app.harness.run_demo [--port PORT]

Or directly:
    python src/warm_logic/app/harness/run_demo.py
"""

import argparse
import sys
from pathlib import Path

# Ensure warm_logic is importable
_root = Path(__file__).parent.parent.parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def main():
    parser = argparse.ArgumentParser(
        description="WarmLogic Sovereign Governance Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run on default port 8888
    python run_demo.py

    # Run on custom port
    python run_demo.py --port 9000

    # Test LLM proxy
    curl -X POST http://localhost:8888/v1/chat/completions \\
         -H "Content-Type: application/json" \\
         -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}'
""",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8888,
        help="Server port (default: 8888)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Server host (default: 0.0.0.0)",
    )
    args = parser.parse_args()

    # Import and run
    from warm_logic.app.harness.demo_server import run_demo_server

    run_demo_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
