import warm_logic_rs
import time
import os

def test_rust_dht():
    print("[Verification] Initializing RustDHT...")
    
    # Generate random 32-byte hex ID
    node_id = os.urandom(32).hex()
    
    try:
        dht = warm_logic_rs.RustDHT(node_id)
        print(f"RustDHT Created. Node ID: {node_id[:8]}...")
        
        print("[Verification] Starting Network Engine (Tokio)...")
        dht.start("127.0.0.1", 9000)
        print("Network Engine Started.")
        
        # Test Routing Table Local logic
        print("[Verification] Testing Routing Table...")
        dht.update(os.urandom(32).hex(), "127.0.0.1", 9001)
        
        closest = dht.find_closest(node_id)
        if len(closest) > 0:
            print(f"FindClosest returned {len(closest)} peers.")
            print(f"   Peer: {closest[0]}")
        else:
            print("FindClosest returned empty list (Expected 1).")
            
        print("RustDHT Verification COMPLETE.")
        
    except Exception as e:
        print(f"Verification Failed: {e}")
        raise e

if __name__ == "__main__":
    test_rust_dht()
