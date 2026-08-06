import time
import sys
import os

# Ensure we can import warm_logic_rs
sys.path.append(os.getcwd())

from warm_logic_rs import encode_packet, KernelPacket

MAGIC = b"SOV1"

def send_binary_packet(packet):
    body = encode_packet(packet)
    length = len(body)
    sys.stdout.buffer.write(MAGIC)
    sys.stdout.buffer.write(length.to_bytes(2, "little"))
    sys.stdout.buffer.write(bytes(body))
    sys.stdout.buffer.flush()

def main():
    print("[MOCK] Starting Economic Simulation...", file=sys.stderr)

    # 1. Sync low balance (simulating host sync)
    print("\n[MOCK] >>> (INPUT) Syncing Balance: 5.0 SC", file=sys.stderr)
    ledger_sync = KernelPacket.LedgerUpdate(balance=5.0, epoch=1000)
    send_binary_packet(ledger_sync)
    time.sleep(1)

    # 2. Kernel AI proposes ScaleUp
    print("[MOCK] <<< (KERNEL) AI proposes ScaleUp (Cost: 10 SC)", file=sys.stderr)
    print("[MOCK] [ECON] VETO: ScaleUp blocked (Insufficient Funds).", file=sys.stderr)

    # 3. Decision packet emitted by kernel (Optimal instead of ScaleUp due to veto)
    decision = KernelPacket.Decision(
        verdict="Economic Veto Active: Optimal Mode Force-Enforced",
        action=0, # Optimal
        amount=0
    )
    send_binary_packet(decision)
    time.sleep(2)

    # 4. Sync healthy balance
    print("\n[MOCK] >>> (INPUT) Syncing Balance: 1000.0 SC", file=sys.stderr)
    ledger_sync = KernelPacket.LedgerUpdate(balance=1000.0, epoch=1001)
    send_binary_packet(ledger_sync)
    time.sleep(1)

    # 5. Kernel AI proposes ScaleUp
    print("[MOCK] <<< (KERNEL) AI proposes ScaleUp (Cost: 10 SC)", file=sys.stderr)
    print("[MOCK] [ECON] VETO: Passing. Balance sufficient.", file=sys.stderr)

    # 6. Decision packet emitted (ScaleUp)
    decision = KernelPacket.Decision(
        verdict="Scaling Up authorized by internal Economics",
        action=2, # ScaleUp
        amount=1
    )
    send_binary_packet(decision)
    time.sleep(1)

if __name__ == "__main__":
    main()
