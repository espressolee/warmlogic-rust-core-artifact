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
"""
WarmLogic REST API Gateway - Entry Point

Run with:
    python -m warm_logic.gateway

Or with uvicorn directly:
    uvicorn warm_logic.gateway:gateway_app --host 0.0.0.0 --port 8000
"""

import os


def main() -> None:
    """Run the WarmLogic REST API Gateway."""
    import uvicorn


    host = os.environ.get("WARMLOGIC_GATEWAY_HOST", "0.0.0.0")
    port = int(os.environ.get("WARMLOGIC_GATEWAY_PORT", "8000"))

    # SEC-006: Disable auto-reload in production
    _debug_requested = os.environ.get("WARMLOGIC_DEBUG", "0") == "1"
    _is_production = os.environ.get("ENVIRONMENT", "").lower() == "production"
    reload = _debug_requested and not _is_production

    if _debug_requested and _is_production:
        print(" SEC-006: Auto-reload disabled in production environment.")

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           WarmLogic REST API Gateway                         ║
╠══════════════════════════════════════════════════════════════╣
║  Host: {host:<10}  Port: {port:<6}                              ║
║  Docs: http://{host}:{port}/docs                              ║
║  Health: http://{host}:{port}/health                          ║
╠══════════════════════════════════════════════════════════════╣
║  research prototype - Research Prototype                                  ║
║  Post-Quantum Cryptography: ML-DSA-65 (FIPS 204)             ║
╚══════════════════════════════════════════════════════════════╝
""")

    uvicorn.run(
        "warm_logic.gateway:gateway_app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
