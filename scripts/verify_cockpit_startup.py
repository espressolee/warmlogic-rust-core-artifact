import os
import signal
import subprocess
import sys
import time

import requests


def verify_cockpit():
    print("Starting Sovereign Cockpit Verification...")

    # Configuration
    PORT = 5001
    API_KEY = "test-sovereign-key-123"
    ENV = os.environ.copy()
    ENV["SOVEREIGN_COCKPIT_KEY"] = API_KEY
    ENV["COCKPIT_HTTP_PORT"] = str(PORT)
    ENV["PYTHONPATH"] = os.getcwd()

    # 1. Start Server Process
    print(f"   - Launching server on port {PORT}...")
    process = subprocess.Popen(
        [sys.executable, "scripts/start_cockpit_web.py"],
        env=ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Wait for startup
        print("   - Waiting for startup (5s)...")
        time.sleep(5)

        # Check if process died
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(
                f"❌ Server crashed immediately!\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )
            return False

        base_url = f"http://localhost:{PORT}"

        # 2. Health Check (Public)
        print(f"   - Checking {base_url}/health/live ...")
        try:
            resp = requests.get(f"{base_url}/health/live", timeout=2)
            if resp.status_code != 200:
                print(f"Health check failed: {resp.status_code}")
                return False
            print("     Alive")
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

        # 3. API Auth Check (Protected)
        print(f"   - Checking {base_url}/api/status with key...")
        try:
            headers = {"X-API-Key": API_KEY}
            resp = requests.get(f"{base_url}/api/status", headers=headers, timeout=2)
            if resp.status_code != 200:
                print(f"Auth check failed: {resp.status_code} - {resp.text}")
                return False
            data = resp.json()
            print(f"     Authenticated. System Status: {data.get('status')}")
        except Exception as e:
            print(f"API Request failed: {e}")
            return False

        print("\nVerification Successful: Cockpit is operational.")
        return True

    finally:
        # Cleanup
        print("   - Terminating server...")
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    success = verify_cockpit()
    sys.exit(0 if success else 1)
