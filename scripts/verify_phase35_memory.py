import sys
import time
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from warm_logic.kernel.memory.episodic import EpisodicStore


def test_memory_persistence():
    print("Starting Memory Persistence Test...")

    # 1. Simulate Session A
    print("  - Creating Session A...")
    store_a = EpisodicStore()  # New session ID generated
    session_id_a = store_a.session_id

    store_a.add_memory("user", "Hello, do you remember me?")
    store_a.add_memory("assistant", "I am just being born, but I will try.")

    # 2. Simulate Session B (New Instance)
    print("  - Creating Session B (Simulating restart)...")
    store_b = EpisodicStore()

    # 3. Verify Session A data exists from Session B's store instance
    print(f"  - Verifying Session A ({session_id_a}) data...")
    history_a = store_b.get_session_history(session_id_a)

    if len(history_a) != 2:
        print(f"FAIL: Expected 2 messages, found {len(history_a)}")
        sys.exit(1)

    if history_a[0]["content"] != "Hello, do you remember me?":
        print("FAIL: Content mismatch.")
        sys.exit(1)

    # 4. Verify Summary Logic
    print("  - Verifying 'Last Conversation' logic...")
    summary = store_b.get_last_conversation_summary()
    print(f"    [Summary Output]:\n{summary}")

    if "No previous memories" in summary:
        # Note: If this is the VERY first run ever, this might be valid,
        # but since we just added Session A, it should find Session A.
        # However, summary logic excludes *current* session.
        # store_b is current. store_a is previous. So it should find store_a.
        print("FAIL: Could not find previous session summary.")
        sys.exit(1)

    if "try" not in summary:
        print("FAIL: Summary text seems missing key content.")
        sys.exit(1)

    print("SUCCESS: Memory is persistent and retrievable.")


if __name__ == "__main__":
    try:
        test_memory_persistence()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        sys.exit(1)
