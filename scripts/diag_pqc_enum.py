import sys
import os

sys.path.append(os.getcwd())
from warm_logic_rs import encode_packet, decode_packet, KernelPacket

def main():
    # Create a Telemetry packet
    tp = KernelPacket.Telemetry(
        heap_used=123,
        heap_total=456,
        task_count=7,
        ticks=890
    )
    
    print(f"Original Object: {tp}")
    print(f"Type: {type(tp)}")
    
    # Encode and Decode
    encoded = encode_packet(tp)
    decoded = decode_packet(list(encoded))
    
    print(f"Decoded Object: {decoded}")
    print(f"Decoded Type: {type(decoded)}")
    
    # Inspect attributes
    try:
        if hasattr(decoded, "Telemetry"):
            val = decoded.Telemetry
            print(f"decoded.Telemetry: {val} (Type: {type(val)})")
            # If it's a variant instance, we might need to check fields
    except Exception as e:
        print(f"Error inspecting Telemetry: {e}")

    # Try accessing fields directly on decoded if it's the variant itself
    try:
        print(f"decoded.heap_used: {getattr(decoded, 'heap_used', 'N/A')}")
    except Exception as e:
        print(f"Error accessing heap_used directly: {e}")

if __name__ == "__main__":
    main()
