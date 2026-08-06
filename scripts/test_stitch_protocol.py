""" Stitch Protocol E2E Verification.
Connects to the stream and verifies real-time telemetry from the kernel.
"""

import sys
import threading
import time
import unittest
import urllib.request
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from warm_logic.kernel.justice.refusal import RefusalEngine
from warm_logic.kernel.substrate.stitch_server import StitchServer


class TestStitchProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start Stitch Server
        cls.server = StitchServer(host="127.0.0.1", port=18033)
        cls.server.start()
        time.sleep(1)  # Wait for socket to bind

    def test_end_to_end_stream(self):
        """Verify that kernel events appear on the Stitch stream."""
        print("Testing Stitch: End-to-End Telemetry...")

        received_events = []

        def listener():
            try:
                # Open stream with timeout
                url = "http://127.0.0.1:18033/stream"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5) as response:
                    for line in response:
                        decoded_line = line.decode("utf-8").strip()
                        if decoded_line.startswith("data: "):
                            received_events.append(decoded_line[6:])
                            if len(received_events) >= 1:
                                break  # Got what we needed
            except Exception as e:
                print(f"   [Listener Error] {e}")

        # 1. Start listener thread
        t = threading.Thread(target=listener, daemon=True)
        t.start()
        time.sleep(1)

        # 2. Trigger Kernel Event
        engine = RefusalEngine()
        ctx = {
            "remote_attestation": {"tee_type": "AWSNitro"},
            "mesh_latch_active": False,
            "sieve_verdict": "ALLOW",
        }
        engine.enforce_sovereignty(ctx)

        # 3. Wait for propagation
        t.join(timeout=3)

        self.assertGreaterEqual(len(received_events), 1)
        event_json = received_events[0]
        print(f"   Stitch Caught Event: {event_json[:80]}...")

        self.assertIn("ACCESS_GRANTED", event_json)
        self.assertIn("sovereign_proof", event_json)
        self.assertIn("sp1_v1_", event_json)


if __name__ == "__main__":
    unittest.main()
