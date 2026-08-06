import os
import signal
import subprocess
import sys
import time
import requests

SERVER_SCRIPT = "scripts/start_cockpit_web.py"
PORT = 5001
BASE_URL = f"http://localhost:{PORT}"

print(f"DEBUG: Using python executable: {sys.executable}")


def test_missing_key_failure():
    print("TEST 1: Missing Key fails startup...", end=" ")
    env = os.environ.copy()
    if "SOVEREIGN_COCKPIT_KEY" in env:
        del env["SOVEREIGN_COCKPIT_KEY"]

    # Ensure it's gone
    if os.environ.get("SOVEREIGN_COCKPIT_KEY"):
        print(
            f"DEBUG: Host ENV still has key: {os.environ.get('SOVEREIGN_COCKPIT_KEY')}"
        )

    try:
        result = subprocess.run(
            [sys.executable, SERVER_SCRIPT],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if (
            result.returncode != 0
            and "CRITICAL: SOVEREIGN_COCKPIT_KEY" in result.stdout
        ):
            print("PASS (Server refused to start)")
        else:
            print(f"FAIL (Return Code: {result.returncode})")
            print("STDOUT:", result.stdout)
            # print("STDERR:", result.stderr)
            sys.exit(1)
    except subprocess.TimeoutExpired:
        print("FAIL (Server started indiscriminately or hung)")
        sys.exit(1)


def test_valid_key_and_cors():
    print("TEST 2: Valid Key starts server...", end=" ")
    env = os.environ.copy()
    secure_key = "test-hardening-key-v1"
    env["SOVEREIGN_COCKPIT_KEY"] = secure_key

    proc = subprocess.Popen(
        [sys.executable, SERVER_SCRIPT],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Wait for startup
        success = False
        for _ in range(20):  # 10 seconds timeout
            try:
                r = requests.get(BASE_URL + "/api/status", timeout=1)
                if r.status_code == 200:
                    success = True
                    break
            except Exception:
                time.sleep(0.5)

        if not success:
            print("FAIL (Server did not start in time)")
            # Print some logs to see why
            # print("Proc output:", proc.stdout.read())
            proc.terminate()
            sys.exit(1)

        print("PASS")

        # Test CORS
        print("TEST 3: CORS Headers...", end=" ")
        try:
            r = requests.options(
                BASE_URL + "/api/status",
                headers={
                    "Origin": "http://localhost:1234", # Random origin
                    "Access-Control-Request-Method": "GET",
                },
                timeout=2,
            )
            acao = r.headers.get("Access-Control-Allow-Origin")
            if acao in ["*", "http://localhost:1234"]:
                print(f"PASS (ACAO: {acao})")
            else:
                print(f"FAIL (ACAO: {acao}, Status: {r.status_code})")
        except Exception as e:
            print(f"FAIL: {e}")

    finally:
        os.kill(proc.pid, signal.SIGTERM)


if __name__ == "__main__":
    print(f"Running Hardening Tests on {SERVER_SCRIPT}")
    test_missing_key_failure()
    test_valid_key_and_cors()
