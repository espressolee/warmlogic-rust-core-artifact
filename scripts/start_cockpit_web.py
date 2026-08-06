#!/usr/bin/env python3
import os

import uvicorn

if __name__ == "__main__":
    # Ensure project root is in path
    import sys

    sys.path.insert(0, os.getcwd())

    port = int(os.environ.get("COCKPIT_HTTP_PORT", "5001"))
    print(f"Starting Sovereign Cockpit on port {port}...")

    from warm_logic.app.cockpit.server import app

    uvicorn.run(app, host="0.0.0.0", port=port)
