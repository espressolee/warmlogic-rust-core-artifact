import asyncio
import os
import sys

from warm_logic.intelligence.ml.llm_handler import LLMHandler


async def test_intelligence_reality():
    print("Starting Intelligence Layer (LLM Integrity) Reality Verification")

    # 1. Setup Environment
    hw_secret = "SIMULATED_HW_ROOT_SECRET_v1"
    os.environ["WARMLOGIC_HW_ROOT_SECRET"] = hw_secret
    os.environ["WARMLOGIC_DEV_MODE"] = "true"

    # Use mock backend for verification but with real proof logic
    handler = LLMHandler(backend_type="mock")

    # 2. Generate Response with Proof
    print("Generating response and proof...")
    prompt = "What is the nature of sovereignty?"
    result = await handler.generate_response(prompt)

    response = result["response"]
    proof = result["proof"]

    print(f"   Response: {response}")
    print(f"   Proof Hash: {proof['proof_hash'][:16]}...")

    # 3. Verify Proof (Positive)
    print("Verifying proof integrity (Positive Test)...")
    if LLMHandler.verify_proof(proof, prompt, response, hw_secret):
        print("   Proof verified successfully.")
    else:
        print("   Proof verification FAILED!")
        return 1

    # 4. Negative Test: Tampered Response
    print("Testing Integrity Breach: Tampered Response...")
    tampered_response = response + " (TAMPERED)"
    if not LLMHandler.verify_proof(proof, prompt, tampered_response, hw_secret):
        print("   Detected tampered response (Proof mismatch).")
    else:
        print("   FAILED: Proof accepted tampered response!")
        return 1

    # 5. Negative Test: Tampered Prompt
    print("Testing Integrity Breach: Tampered Prompt...")
    tampered_prompt = prompt + "?"
    if not LLMHandler.verify_proof(proof, tampered_prompt, response, hw_secret):
        print("   Detected tampered prompt (Proof mismatch).")
    else:
        print("   FAILED: Proof accepted tampered prompt!")
        return 1

    # 6. Negative Test: Invalid Hardware Secret
    print("Testing Integrity Breach: Invalid Enclave Secret...")
    if not LLMHandler.verify_proof(proof, prompt, response, "WRONG_SECRET"):
        print("   Detected invalid hardware secret.")
    else:
        print("   FAILED: Proof accepted wrong hardware secret!")
        return 1

    print("\nINTELLIGENCE REALITY VERIFIED: Cogntive Sovereignty Proofs Active.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(test_intelligence_reality()))
