import logging
import sys
from pathlib import Path
from typing import Dict, List

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from warm_logic.kernel.intelligence.agency import AgencyExecutor
from warm_logic.kernel.intelligence.llm_bridge import LocalInferenceClient


def main():
    # Setup minimal logging
    logging.basicConfig(level=logging.WARNING)

    client = LocalInferenceClient()
    executor = AgencyExecutor()

    # Phase 34.4: Conversation Memory
    history: List[Dict[str, str]] = []

    # Initialize with system message
    system_prompt = (
        "You are WarmLogic, a sovereign AI. "
        "If you need to perform an action, output a JSON block:\n"
        '1. Shell command: {"action": "shell", "command": "..."}\n'
        '2. Write file: {"action": "write_file", "path": "...", "content": "..."}\n'
        '3. Read file: {"action": "read_file", "path": "..."}\n'
        "Immediately stop after outputting the JSON block. Wait for the result."
    )
    history.append({"role": "system", "content": system_prompt})

    print("====================================================")
    print("Sovereign WarmLogic Chat Interface (v4.0)")
    print("Memory: Enabled | Auto-Retry: Enabled")
    print("====================================================")

    while True:
        try:
            user_input = input("\nUser: ")
            if not user_input.strip():
                continue

            history.append({"role": "user", "content": user_input})

            current_turn = 0
            max_turns = 3  # Phase 34.3: Max retries for self-correction

            while current_turn < max_turns:
                print("Thinking...", end="\r")
                response = client.generate_thought(messages=history)

                if not response:
                    print("Error: cannot reach the intelligence engine.")
                    break

                history.append({"role": "assistant", "content": response})

                # Check for Agency Action
                action = executor.extract_action(response)
                if action:
                    print(f"Sovereign (Action): {action}")
                    confirm = input("Execute? (y/n): ")
                    if confirm.lower() == "y":
                        result = executor.execute(action)
                        print(f"Result:\n{result}")

                        # Phase 34.3: Error Feedback Loop
                        if "Error" in result or "failed" in result.lower():
                            print("[Self-Correction] error detected; looking for a fix...")
                            history.append(
                                {
                                    "role": "user",
                                    "content": f"An error occurred while running the command:\n{result}\nAnalyse the problem and try an alternative.",
                                }
                            )
                            current_turn += 1
                            continue  # Loop back to 'generate_thought' with error info

                        # Successful action: Give the result back for summary
                        print("Analysing result...", end="\r")
                        summary = client.generate_thought(
                            messages=history
                            + [
                                {
                                    "role": "user",
                                    "content": f"Command result:\n{result}\nSummarise this result for the user.",
                                }
                            ]
                        )
                        print(f"Sovereign: {summary}")
                        if summary:
                            history.append({"role": "assistant", "content": summary})
                        break
                    else:
                        print("Action cancelled.")
                        break
                else:
                    print(f"Sovereign: {response}")
                    break

            # Keep history manageable (sliding window)
            if len(history) > 15:
                history = [history[0]] + history[-10:]

        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"\nUnexpected error: {e}")


if __name__ == "__main__":
    main()
