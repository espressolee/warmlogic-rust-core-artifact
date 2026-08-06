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
# ==========================================================
# WarmLogic Demo Harness Entry Point
# ==========================================================
"""
Run the demo server as a module.

Usage:
    python -m warm_logic.app.harness [--port PORT]
"""

import argparse
from .demo_server import run_demo_server


def main():
    parser = argparse.ArgumentParser(description="WarmLogic Demo Server")
    parser.add_argument("--port", type=int, default=8888, help="Server port")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server host")
    args = parser.parse_args()

    run_demo_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
