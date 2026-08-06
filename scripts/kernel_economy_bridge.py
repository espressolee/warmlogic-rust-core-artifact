import sys
import os
import time

# Ensure we can import warm_logic
sys.path.append(os.getcwd())

from warm_logic_rs import decode_packet, encode_packet, KernelPacket
from warm_logic.sdk.client import SovereignClient

MAGIC = b"SOV1"

def main():
    print("[Economy Bridge] Monitoring Binary Stream for Economic Events...", file=sys.stderr)
    client = SovereignClient()
    last_sync = 0

    # Read from stdin buffer
    while True:
        try:
            # 1. Periodic Ledger Sync (Sync every 5 seconds)
            now = time.time()
            if now - last_sync > 5:
                try:
                    balance = client.get_balance()
                    print(f"\n[Economy Bridge] Syncing Balance: {balance} SC", file=sys.stderr)
                    # Create LedgerUpdate packet
                    p = KernelPacket.LedgerUpdate(balance=balance, epoch=int(now))
                    body = encode_packet(p)
                    # Push MAGIC + LEN + BODY to stdout (to be piped back/forward)
                    sys.stdout.buffer.write(MAGIC)
                    sys.stdout.buffer.write(len(body).to_bytes(2, "little"))
                    sys.stdout.buffer.write(bytes(body))
                    sys.stdout.buffer.flush()
                    last_sync = now
                except Exception as e:
                    print(f"[Economy Bridge] Sync Error: {e}", file=sys.stderr)

            # 2. Process Kernel -> Host stream
            # Non-blocking read would be better, but we'll use a small read
            header = sys.stdin.buffer.read(4)
            if not header:
                time.sleep(0.1)
                continue

            # Re-emit raw bytes
            sys.stdout.buffer.write(header)

            if header == MAGIC:
                len_bytes = sys.stdin.buffer.read(2)
                sys.stdout.buffer.write(len_bytes)
                length = int.from_bytes(len_bytes, "little")

                body = sys.stdin.buffer.read(length)
                sys.stdout.buffer.write(body)
                sys.stdout.buffer.flush()

                try:
                    packet = decode_packet(list(body))
                    p_type = type(packet).__name__
                    if "Decision" in p_type:
                        # Action 2 is ScaleUp
                        if packet.action == 2:
                            print("\n[Economy Bridge] Binary ScaleUp Detected. Deducting Tax...", file=sys.stderr)
                            try:
                                client.transfer_credits(
                                    to_id="TREASURY_RESERVE",
                                    amount=10.0,
                                    reason="Binary Sovereign ScaleUp Fee"
                                )
                                print("[Economy Bridge] Tax Proposal Submitted.", file=sys.stderr)
                            except Exception as e:
                                print(f"[Economy Bridge] Tax Error: {e}", file=sys.stderr)
                except:
                    pass
            else:
                sys.stdout.buffer.flush()

        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
