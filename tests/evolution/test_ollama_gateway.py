import asyncio
import json

import httpx

from warm_logic.kernel.ops.stochastic_gateway import StochasticGateway


async def verify_ollama():
    gateway = StochasticGateway()

    # 1. Check if Ollama is active
    ollama_active = False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:11434/api/tags", timeout=2.0)
            if resp.status_code == 200:
                print("✅ Found local Ollama server.")
                ollama_active = True
    except:
        print("ℹ️ Local Ollama server not detected. Fallback will be used.")

    # 2. Test Gateway
    context = {"source_code": "def hello(): print('hello')"}
    strategy = await gateway.get_mutation_strategy(context)

    if strategy:
        print(f"🚀 Received strategy: {strategy.get('proposed_change')}")
        print(f"📊 Confidence: {strategy.get('confidence')}")

        if ollama_active and "Simulated" not in strategy.get("new_code", ""):
            print("✨ SUCCESS: Real LLM inference verified.")
        else:
            print("🎭 SUCCESS: Fallback simulation verified.")


if __name__ == "__main__":
    asyncio.run(verify_ollama())
