import os
import shutil

from warm_logic.kernel.intelligence.agency import AgencyExecutor


def test_agency_tools():
    """
    Phase 36.3: Verify Agency Tool Execution.
    Tests extraction and execution of shell and file logic.
    """
    # Setup Sandbox
    sandbox = "out/test_sandbox"
    if os.path.exists(sandbox):
        shutil.rmtree(sandbox)
    os.makedirs(sandbox, exist_ok=True)

    agency = AgencyExecutor(sandbox_dir=sandbox)

    # 1. Test Extraction (Single)
    llm_output = 'I will verify the system.\n<thought>Checking kernel.</thought>\n{"action": "shell", "command": "echo sovereign"}'
    actions = agency.extract_action(llm_output)
    assert len(actions) == 1
    assert actions[0]["action"] == "shell"
    assert actions[0]["command"] == "echo sovereign"

    # 2. Test Execution (Shell)
    result = agency.execute(actions[0])
    assert "sovereign" in result
    print(f"✅ Shell Action Verified: {result.strip()}")

    # 3. Test Extraction (List/Chain)
    llm_chain = """
    Plan:
    1. Write file
    2. Read file
    [
        {"action": "write_file", "path": "manifest.txt", "content": "Sovereignty"},
        {"action": "read_file", "path": "manifest.txt"}
    ]
    """
    actions = agency.extract_action(llm_chain)
    assert len(actions) == 2

    # 4. Test Execution (File I/O)
    res_write = agency.execute(actions[0])
    assert "Successfully wrote" in res_write

    res_read = agency.execute(actions[1])
    assert "Sovereignty" in res_read

    print(f"✅ File I/O Verified")

    # 5. Security Test (rm -rf /)
    unsafe_action = {"action": "shell", "command": "rm -rf /"}
    res_unsafe = agency.execute(unsafe_action)
    assert "Error: Dangerous" in res_unsafe or "blocked" in res_unsafe
    print(f"✅ Safety Guard Verified: {res_unsafe.strip()}")

    # Cleanup
    shutil.rmtree(sandbox)


if __name__ == "__main__":
    test_agency_tools()
