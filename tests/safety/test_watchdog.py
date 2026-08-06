import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WATCHDOG_SCRIPT = PROJECT_ROOT / "src" / "warm_logic" / "safety" / "watchdog.py"


def test_watchdog_kill():
    print("🛡️ Starting Watchdog Verification (Hard Kill)...")

    # 1. Spawn a 'Rogue' Process (Infinite Loop)
    # We use a simple python script that spins CPU
    print("   -> Spawning Rogue Process...")
    rogue_code = "while True: pass"

    rogue_proc = subprocess.Popen(
        [sys.executable, "-c", rogue_code],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    rogue_pid = rogue_proc.pid
    print(f"   -> Rogue PID: {rogue_pid}")

    # 2. Spawn Watchdog (Targeting Rogue)
    # CPU limit 10%, Patience 3s
    print("   -> Unleashing Watchdog (Limit: 10% CPU, 3s Patience)...")
    watchdog_proc = subprocess.Popen(
        [
            sys.executable,
            str(WATCHDOG_SCRIPT),
            str(rogue_pid),
            "10.0",
            "100",
            "0",
        ],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # 3. Wait for Kill
        start_wait = time.time()
        killed = False

        while time.time() - start_wait < 20:  # Wait max 20s
            if rogue_proc.poll() is not None:
                killed = True
                break
            time.sleep(0.5)

        # 4. Verify
        if killed:
            print(f"✅ [Safety] Rogue Process {rogue_pid} was terminated!")
            returncode = rogue_proc.returncode
            # -9 is SIGKILL
            print(f"   -> Return Code: {returncode} (Expected -9)")
            assert returncode == -9 or returncode == 9
        else:
            print("❌ [Safety] Watchdog failed to kill process in time.")
            assert False
    finally:
        if rogue_proc.poll() is None:
            rogue_proc.kill()
            rogue_proc.wait(timeout=2)
        if watchdog_proc.poll() is None:
            watchdog_proc.kill()
        try:
            watchdog_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            watchdog_proc.terminate()
            watchdog_proc.wait(timeout=2)


if __name__ == "__main__":
    test_watchdog_kill()
