# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""[Phase 200] Sovereign Chat - Interactive AI conversation interface."""

import json
import logging
import os
import time
from typing import Dict, List

# Imports relative to package are implied when installed,
# but absolute imports work best for entry points.
from warm_logic.kernel.intelligence.agency import AgencyExecutor
from warm_logic.kernel.intelligence.llm_bridge import LocalInferenceClient
from warm_logic.kernel.memory.episodic import EpisodicStore
from warm_logic.kernel.memory.semantic import SemanticMemory


def dump_working_memory(memory, history):
    """
    Phase 35.3: Persist active context window for Cockpit visualization.
    """
    try:
        wm_path = "out/sovereign/working_memory.json"
        os.makedirs(os.path.dirname(wm_path), exist_ok=True)
        with open(wm_path, "w") as f:
            dump_data = {
                "session_id": memory.session_id,
                "timestamp": time.time(),
                "turn": len(history),
                "history": history,
            }
            json.dump(dump_data, f, indent=2)
    except Exception:
        pass  # Non-critical


def main():
    # Setup minimal logging
    logging.basicConfig(level=logging.WARNING)

    client = LocalInferenceClient()
    executor = AgencyExecutor()
    memory = EpisodicStore()

    # Phase A1: Semantic Memory (Agent )
    semantic = SemanticMemory(episodic_db_path=memory.db_path)
    if semantic.is_available():
        # Sync past conversations into ChromaDB on startup
        synced = semantic.sync_from_episodic(limit=500)
        if synced > 0:
            print(f"Synced {synced} memories to semantic index.")

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
    print("Sovereign WarmLogic Chat Interface (v4.2: Semantic Memory)")
    print(f"Session ID: {memory.session_id}")
    print(f"Semantic Index: {semantic.count()} documents")
    print("----------------------------------------------------")
    print(memory.get_last_conversation_summary())
    print("====================================================")

    while True:
        try:
            user_input = input("\nUser: ")
            if not user_input.strip():
                continue

            # Phase A1: Inject semantic context before user message
            if semantic.is_available():
                context = semantic.get_context_for_query(user_input, max_tokens=2000)
                if context:
                    history.append({"role": "system", "content": context})

            # Save User Input
            history.append({"role": "user", "content": user_input})
            memory.add_memory("user", user_input)
            semantic.add(user_input, role="user", session_id=memory.session_id)

            # Dump Working Memory
            dump_working_memory(memory, history)

            current_turn = 0
            max_turns = 3  # Phase 34.3: Max retries for self-correction

            while current_turn < max_turns:
                print("Thinking...", end="\r")
                response = client.generate_thought(messages=history)

                if not response:
                    print("Error: cannot reach the intelligence engine.")
                    break

                history.append({"role": "assistant", "content": response})
                # [Phase 36.2] Self-Critique & Reflection Loop
                import re

                thought_match = re.search(
                    r"<thought>(.*?)</thought>", response, re.DOTALL
                )

                if thought_match:
                    thought_content = thought_match.group(1).strip()
                    print(f"\n[Reasoning]:\n{thought_content}\n")

                    # Trigger Self-Critique
                    print("[Self-Critique]: Verifying plan...", end="\r")
                    critique_prompt = (
                        "Review your previous thought and plan. "
                        "Critically check for: 1. Safety risks 2. Logic flaws 3. Better alternatives. "
                        "If the plan is solid, output 'CONFIRMED'. "
                        "If it needs fixing, output 'REVISION: <new plan/action>'."
                    )
                    # Temporary critique message, not added to permanent history to save context
                    critique_msgs = history + [
                        {"role": "assistant", "content": response},
                        {"role": "user", "content": critique_prompt},
                    ]
                    critique_response = client.generate_thought(messages=critique_msgs)

                    if critique_response and "REVISION:" in critique_response:
                        print("[Correction]: Logic flaw detected. Revising plan...")
                        # Extract revision
                        response = critique_response.split("REVISION:", 1)[1].strip()
                        print(f"[Revised Reasoning]:\n{response}\n")
                    else:
                        print("[Verified]: logic is sound.")

                # The response (potentially revised) is now added to memory
                memory.add_memory("assistant", response)

                # Dump Memory Again (after response)
                dump_working_memory(memory, history)

                # Check for Agency Action(s)
                actions = executor.extract_action(response)

                if actions:
                    # Confirm all actions at once (or step-by-step? For now, batch verify)
                    print(f"Sovereign (Propsoed Actions): {len(actions)} steps")
                    for i, act in enumerate(actions):
                        print(f"  Step {i + 1}: {act}")

                    confirm = input("Execute? (y/n): ")
                    if confirm.lower() == "y":
                        all_results = []
                        failed = False

                        for i, act in enumerate(actions):
                            print(f"▶Executing Step {i + 1}...", end="\r")
                            result = executor.execute(act)

                            # Phase 34.3: Error Feedback Loop (in-chain)
                            if "Error" in result or "failed" in result.lower():
                                print(f"Step {i + 1} Failed: {result}")
                                all_results.append(f"Step {i + 1} FAILED: {result}")

                                # Immediately trigger self-correction
                                print(
                                    "🔄 [Self-Correction] error detected; chain halted, looking for a fix..."
                                )
                                history.append(
                                    {
                                        "role": "user",
                                        "content": f"Action Chain stopped at Step {i + 1}.\nError: {result}\nAnalyze the failure and propose a fix.",
                                    }
                                )
                                current_turn += 1
                                failed = True
                                break  # Stop chaining
                            else:
                                print(
                                    f"✅ Step {i + 1} Done. (Length: {len(result)} chars)"
                                )
                                all_results.append(
                                    f"Step {i + 1} Result: {result[:200]}..."
                                )  # truncate for context saving

                        if not failed:
                            # All success
                            combined_result = "\n".join(all_results)
                            print(f"Full result:\n{combined_result}")

                            # Give the result back for summary
                            print("Analysing result...", end="\r")
                            summary = client.generate_thought(
                                messages=history
                                + [
                                    {
                                        "role": "user",
                                        "content": f"All steps completed. Result summary:\n{combined_result}\nReport it to the user.",
                                    }
                                ]
                            )
                            print(f"Sovereign: {summary}")
                            if summary:
                                history.append(
                                    {"role": "assistant", "content": summary}
                                )
                                # Final Dump
                                dump_working_memory(memory, history)
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
