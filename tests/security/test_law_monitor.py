import pytest

from warm_logic.kernel.lineage import PolicyZone
from warm_logic.kernel.lineage import tracker as lineage_tracker
from warm_logic.kernel.ops.monitor import InvariantViolation, OSState, law_monitor
from warm_logic.kernel.zanzibar import RelationTuple, zanzibar


def test_formal_invariant_enforcement():
    # Setup: Create a restricted artifact
    artifact_id = "doc:confidential"
    zanzibar.write_tuple(
        RelationTuple("artifact", artifact_id, "execute", "user", "authorized_user")
    )
    lineage_tracker.track(artifact_id, PolicyZone.SECRET, "system")

    # 1. Success Case
    state_ok = OSState(
        execution_state="RUNNING",
        current_artifact=artifact_id,
        user_id="authorized_user",
        target_zone=PolicyZone.SECRET,
    )
    assert law_monitor.verify_transition(state_ok) == True
    print("✅ Formal Invariant Check: Success Case Passed.")

    # 2. Failure Case: Unauthorised User
    state_bad_user = OSState(
        execution_state="RUNNING",
        current_artifact=artifact_id,
        user_id="hacker",
        target_zone=PolicyZone.SECRET,
    )
    with pytest.raises(InvariantViolation) as exc:
        law_monitor.verify_transition(state_bad_user)
    print(f"✅ Formal Invariant Check: Auth Failure Caught: {exc.value}")

    # 3. Failure Case: Lineage Leak
    state_leak = OSState(
        execution_state="RUNNING",
        current_artifact=artifact_id,
        user_id="authorized_user",
        target_zone=PolicyZone.PUBLIC,
    )
    with pytest.raises(InvariantViolation) as exc:
        law_monitor.verify_transition(state_leak)
    print(f"✅ Formal Invariant Check: Lineage Leak Caught: {exc.value}")


if __name__ == "__main__":
    test_formal_invariant_enforcement()
