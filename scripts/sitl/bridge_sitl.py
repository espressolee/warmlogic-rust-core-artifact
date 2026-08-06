"""
SITL Bridge - Routes MAVLink packets between SITL components and GCS.
"""

import logging
import threading
import time

from pymavlink import mavutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SITLBridge")


class SITLRouter:
    def __init__(
        self, sitl_addr="tcpin:127.0.0.1:5760", gcs_addr="udpout:127.0.0.1:14550"
    ):
        self.sitl_addr = sitl_addr
        self.gcs_addr = gcs_addr
        self.running = False
        self.sitl = None
        self.gcs = None

    def start(self):
        logger.info(f"Connecting to SITL at {self.sitl_addr}...")
        self.sitl = mavutil.mavlink_connection(self.sitl_addr)

        logger.info(f"Connecting to GCS at {self.gcs_addr}...")
        self.gcs = mavutil.mavlink_connection(self.gcs_addr)

        self.running = True

        # Threads for bidirectional routing
        self.t1 = threading.Thread(
            target=self._route, args=(self.sitl, self.gcs, "SITL -> GCS"), daemon=True
        )
        self.t2 = threading.Thread(
            target=self._route, args=(self.gcs, self.sitl, "GCS -> SITL"), daemon=True
        )

        self.t1.start()
        self.t2.start()

        logger.info("MAVLink routing active.")

    def _route(self, src, dst, label):
        while self.running:
            try:
                msg = src.recv_raw()
                if msg:
                    dst.write(msg)
            except Exception as e:
                logger.error(f"Routing Error [{label}]: {e}")
                time.sleep(1)

    def stop(self):
        self.running = False
        logger.info("SITL Bridge shutting down.")


if __name__ == "__main__":
    router = SITLRouter()
    router.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        router.stop()
