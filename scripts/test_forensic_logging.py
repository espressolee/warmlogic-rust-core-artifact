"""
Forensic Logging Verification (Phase 14).
Ensures logs are emitted as valid JSON with required forensic fields.
"""

import io
import json
import logging
import sys

from warm_logic.intelligence.observability.logging_setup import setup_logging


def test_forensic_logging():
    # Capture stdout
    capture = io.StringIO()
    handler = logging.StreamHandler(capture)

    # Needs to match the formatter in logging_setup.py
    # We can reuse the class by importing it ideally, but let's trust setup_logging for now
    # Actually, to capture we need to manually hook the formatter or rely on setup_logging using sys.stdout
    # Let's rely on intercepting the root logger configuration from setup_logging

    setup_logging()
    root = logging.getLogger()

    # Swap out the sys.stdout handler with our capture handler, keeping the formatter
    original_handler = root.handlers[0]
    formatter = original_handler.formatter
    handler.setFormatter(formatter)

    root.handlers = [handler]

    # Emit Log
    trace_id = "test_trace_123"
    adapter = logging.LoggerAdapter(
        logging.getLogger("TestLogger"), {"trace_id": trace_id, "actor": "tester"}
    )
    adapter.info("Forensic evidence captured.")

    # Verify
    output = capture.getvalue().strip()
    print(f"Captured Log: {output}")

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        print("FAILED: Output is not valid JSON.")
        sys.exit(1)

    required = ["timestamp", "level", "logger", "message", "trace_id", "actor"]
    for field in required:
        if field not in data:
            print(f"FAILED: Missing field '{field}'")
            sys.exit(1)

    if data["trace_id"] != trace_id:
        print(
            f"❌ FAILED: Trace ID mismatch. Expected {trace_id}, got {data['trace_id']}"
        )
        sys.exit(1)

    print("Forensic Logging Verified.")


if __name__ == "__main__":
    test_forensic_logging()
