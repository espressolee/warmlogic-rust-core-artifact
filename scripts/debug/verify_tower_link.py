import logging
import os
import sys

import requests

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TowerLinkCheck")

TARGET_IP = os.getenv("CITADEL_IP", "100.116.80.23")
PORT = 8033


def check_link():
    url = f"http://{TARGET_IP}:{PORT}/health"
    logger.info(f"Attempting to contact Control Tower at {url}...")

    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            logger.info(
                f"✅ [Connection] Control Tower Service is ACTIVE via Tailscale."
            )
            logger.info(f"   Payload: {resp.json()}")
            return True
        else:
            logger.warning(
                f"⚠️ [Connection] Service reached but returned {resp.status_code}"
            )
            return False
    except requests.exceptions.ConnectionError:
        logger.error(
            f"❌ [Connection] Failed to connect to port {PORT}. Service likely NOT running."
        )
        return False
    except Exception as e:
        logger.error(f"[Connection] Unexpected error: {e}")
        return False


if __name__ == "__main__":
    if check_link():
        sys.exit(0)
    else:
        sys.exit(1)
