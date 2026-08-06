import sys
import os
import time
import json

# Ensure we can import warm_logic_rs and warm_logic
sys.path.append(os.getcwd())

from warm_logic_rs import RustMind, decode_packet, KernelPacket
from warm_logic.sdk.client import SovereignClient

MAGIC = b"SOV1"

def main():
    print("[Strategic Advisor] Binary reasoning engine online.")
    print("[Strategic Advisor] Awaiting packets from kernel serial bridge...")

    mind = RustMind()
    client = SovereignClient()
    model_loaded = False
    last_heartbeat = 0

    # Align with verify_synthetic_mind_real.py naming
    model_candidates = ["smollm_135m_q8.gguf", "smollm-135m.gguf", "q8_0.gguf"]
    model_path = next((p for p in model_candidates if os.path.exists(p)), None)

    if model_path:
        print(f"[Strategic Advisor] Loading strategic model: {model_path}")
        try:
            mind.load(os.path.abspath(model_path))
            model_loaded = True
            print("[Strategic Advisor] Model loaded.")
        except Exception as e:
            print(f"[Strategic Advisor] Model load failed: {e}. Falling back to heuristic mode.")
    else:
        print(f"[Strategic Advisor] No model file found. Running in Heuristic Mode.")

    # Read from stdin buffer (piped from QEMU)
    while True:
        try:
            # Look for MAGIC "SOV1"
            header = sys.stdin.buffer.read(4)
            if not header:
                break

            if header == MAGIC:
                # Read 2-byte length
                len_bytes = sys.stdin.buffer.read(2)
                if not len_bytes: break
                length = int.from_bytes(len_bytes, "little")

                # Read Body
                body = sys.stdin.buffer.read(length)
                if not body: break

                try:
                    packet = decode_packet(list(body))
                    handle_packet(packet, mind, client, model_loaded, last_heartbeat)
                except Exception as e:
                    print(f"[Strategic Advisor] Decode Error: {e}")
            else:
                # Skip byte if not magic
                pass

        except KeyboardInterrupt:
            break

def handle_packet(packet, mind, client, model_loaded, last_heartbeat):
    p_type = type(packet).__name__
    if "Telemetry" in p_type:
        print(f"[Telemetry] Heap: {packet.heap_used}/{packet.heap_total} | Tasks: {packet.task_count}")

    elif "Decision" in p_type:
        print(f"[AI Verdict] Status: {packet.verdict} (Action: {packet.action})")

        # Strategic Second Opinion
        prompt = f"Kernel AI suggests action {packet.action} with verdict '{packet.verdict}'. Strategic advice?"
        if model_loaded:
            directive = mind.think(prompt)
        else:
            directive = "HEURISTIC: Strategic monitoring active."

        print(f"[STRATEGIC DIRECTIVE] {directive}")

        # Mesh Pulse
        try:
            client.submit_proposal("LOG_STOCHASTIC_DIRECTIVE", {"directive": directive, "state": {"action": packet.action, "verdict": packet.verdict}})
        except: pass

if __name__ == "__main__":
    main()
