from warm_logic.sdk import WarmClient

def run_demo():
    print("--- WarmLogic SDK Demo ---")
    client = WarmClient()
    
    packet = client.echo_truth("The Logic is Sovereign.")
    
    print(f"Message: {packet['message']}")
    print(f"ID:      {packet['identity']}")
    print(f"Sig:     {packet['signature'][:16]}...")
    print(f"Valid:   {packet['verified']}")

if __name__ == '__main__':
    run_demo()
